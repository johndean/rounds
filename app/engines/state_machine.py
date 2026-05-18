"""
State machine — the only path for changing sessions.status.

Ports MIC's `app/engines/state_machine.py` invariant:
  • ALLOWED_TRANSITIONS map — no other moves are permitted
  • `failed` is terminal — no transitions out
  • Every transition appends a row to session_audit.processing_log
  • Every transition emits a WS event via the bridge (no-op until 6n lands)

Two entry points:
  • `transition_session()`        async, used by FastAPI handlers
  • `transition_session_sync()`   sync, used by Celery tasks

Both raise `ConflictError` on illegal transitions — FastAPI maps to 409.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class ConflictError(Exception):
    """Raised when an attempted state transition is not allowed."""

    def __init__(self, message: str, details: Optional[dict] = None) -> None:
        super().__init__(message)
        self.details = details or {}


# Locked transition map — single source of truth.
# `uploading → ready` is the AI MODE direct path (skips intermediate stages).
# `ready → complete` is the SOP final-stage promotion (Phase 6q).
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "uploading":    {"transcribing", "ready", "failed"},
    "transcribing": {"normalizing",  "failed"},
    "normalizing":  {"fusing",       "failed"},
    "fusing":       {"aligning",     "failed"},
    "aligning":     {"ready",        "failed"},
    "ready":        {"complete",     "failed"},
}

TERMINAL_STATES = {"failed", "complete"}


def _append_log_entry(
    conn, session_id: str, prev: str, new: str,
    actor: Optional[str] = None, reason: Optional[str] = None,
) -> None:
    """Append one entry to session_audit.processing_log (JSONB array)."""
    from sqlalchemy import text

    entry = {
        "ts":    datetime.now(timezone.utc).isoformat(),
        "prev":  prev,
        "next":  new,
        "actor": actor,
        "reason": reason,
    }
    conn.execute(
        text(
            """
            INSERT INTO session_audit (session_id, processing_log)
            VALUES (CAST(:sid AS uuid), CAST(:entry AS jsonb))
            ON CONFLICT (session_id) DO UPDATE
              SET processing_log = session_audit.processing_log || EXCLUDED.processing_log,
                  updated_at = now()
            """
        ),
        {"sid": session_id, "entry": json.dumps([entry])},
    )


def _emit_ws(session_id: str, prev: str, new: str) -> None:
    """Emit processing_update WS event. No-op until ws_bridge ships in 6n."""
    try:
        from app.engines.ws_bridge import publish_ws_event_sync  # type: ignore

        publish_ws_event_sync(
            session_id,
            {"type": "processing_update", "prev": prev, "next": new},
        )
    except ImportError:
        # 6n not yet shipped — silent no-op.
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"ws emit failed for {session_id}: {exc}")


def transition_session_sync(
    session_id: str, new_status: str,
    actor: Optional[str] = None, reason: Optional[str] = None,
) -> None:
    """
    Sync transition for Celery tasks. Raises ConflictError on illegal moves.

    Atomicity: locks the session row with SELECT FOR UPDATE inside a single
    transaction. The status flip, audit log append, and (eventual) WS emit
    all commit together.
    """
    from sqlalchemy import create_engine, text

    from app.config import settings

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT status FROM sessions WHERE id = CAST(:sid AS uuid) FOR UPDATE"),
                {"sid": session_id},
            ).fetchone()
            if not row:
                raise ConflictError(f"Session {session_id} not found")
            current = row[0]
            if current in TERMINAL_STATES:
                raise ConflictError(
                    f"Session {session_id} is terminal ({current})",
                    details={"current": current, "attempted": new_status},
                )
            allowed = ALLOWED_TRANSITIONS.get(current, set())
            if new_status not in allowed:
                raise ConflictError(
                    f"Invalid transition: {current} → {new_status}",
                    details={
                        "current": current,
                        "attempted": new_status,
                        "allowed": sorted(allowed),
                    },
                )
            conn.execute(
                text(
                    """
                    UPDATE sessions
                       SET status = :new, updated_at = now()
                     WHERE id = CAST(:sid AS uuid)
                    """
                ),
                {"new": new_status, "sid": session_id},
            )
            _append_log_entry(conn, session_id, current, new_status, actor, reason)
    finally:
        engine.dispose()

    _emit_ws(session_id, current, new_status)
    logger.info(f"state: {session_id} {current} → {new_status} (actor={actor})")


async def transition_session(
    session_id: str, new_status: str, db,
    actor: Optional[str] = None, reason: Optional[str] = None,
) -> None:
    """
    Async transition for FastAPI handlers. Same invariants as sync version.

    The caller's `db` (AsyncSession) handles the transaction — this function
    does NOT commit. The caller's request handler commits at the end of the
    request lifecycle so the transition is atomic with whatever else the
    handler is writing.
    """
    from sqlalchemy import text

    row = (
        await db.execute(
            text("SELECT status FROM sessions WHERE id = CAST(:sid AS uuid) FOR UPDATE"),
            {"sid": session_id},
        )
    ).fetchone()
    if not row:
        raise ConflictError(f"Session {session_id} not found")
    current = row[0]
    if current in TERMINAL_STATES:
        raise ConflictError(
            f"Session {session_id} is terminal ({current})",
            details={"current": current, "attempted": new_status},
        )
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise ConflictError(
            f"Invalid transition: {current} → {new_status}",
            details={"current": current, "attempted": new_status, "allowed": sorted(allowed)},
        )
    await db.execute(
        text("UPDATE sessions SET status = :new, updated_at = now() WHERE id = CAST(:sid AS uuid)"),
        {"new": new_status, "sid": session_id},
    )
    # Append audit entry — same JSONB merge pattern as sync.
    entry = {
        "ts":    datetime.now(timezone.utc).isoformat(),
        "prev":  current,
        "next":  new_status,
        "actor": actor,
        "reason": reason,
    }
    await db.execute(
        text(
            """
            INSERT INTO session_audit (session_id, processing_log)
            VALUES (CAST(:sid AS uuid), CAST(:entry AS jsonb))
            ON CONFLICT (session_id) DO UPDATE
              SET processing_log = session_audit.processing_log || EXCLUDED.processing_log,
                  updated_at = now()
            """
        ),
        {"sid": session_id, "entry": json.dumps([entry])},
    )

    _emit_ws(session_id, current, new_status)
    logger.info(f"state: {session_id} {current} → {new_status} (actor={actor})")
