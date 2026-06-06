"""
/v1/sessions/{id}/lock/* — concurrent-edit lock for the editor.

Plan ref: docs/plans/2026-06-05-010-zero-gap-parity-plan.md §Phase 1.
Audit IDs closed: E1 (silent concurrent-edit overwrite).

The lock is ADVISORY at the DB layer (never blocks INSERT/UPDATE) but
ENFORCED at the API layer on the autosave path (Phase 2). When the lock
service is unreachable the frontend MUST fail closed (see useSessionLock.ts)
— the reviewer specifically flagged fail-open as the exact bug we are trying
to prevent.

Endpoints:
    POST   /v1/sessions/{id}/lock/acquire      — take or steal a stale lock
    POST   /v1/sessions/{id}/lock/heartbeat    — extend; 409 if held by other
    POST   /v1/sessions/{id}/lock/release      — explicit release on tab close
    GET    /v1/sessions/{id}/lock/holder       — read holder (banner state)
    POST   /v1/sessions/{id}/lock/force-take   — admin force-take stale lock

Heartbeat TTL is 90s (3 missed 30s heartbeats). Holder rows are upserted
keyed by session_id (single-row-per-session). No new infra dependency —
runs on the same Postgres connection pool the editor already uses.

Related ADRs: ADR-005 (corrections — autosave gates on this), ADR-009
(editor architecture).
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from app.auth import CurrentUser
from app.db import DbSession
from app.security.roles import is_admin

router = APIRouter(prefix="/v1/sessions", tags=["session-locks"])

# Lock TTL: 90 seconds = 3 missed 30-second heartbeats. The reviewer
# wanted this explicit; documenting here so future changes are deliberate.
LOCK_TTL_SECONDS = 90


# ─── Schemas ───────────────────────────────────────────────────────────


class LockHolder(BaseModel):
    user_email: str
    acquired_at: str
    heartbeat_at: str
    expires_at: str


class LockState(BaseModel):
    """Returned by acquire/heartbeat/holder."""

    acquired: bool                                # did the caller end up holding the lock?
    is_self: bool                                  # is the holder the calling user?
    holder: Optional[LockHolder] = None            # None if the lock row was deleted (no holder)


# ─── Helpers ───────────────────────────────────────────────────────────


def _holder_dict(row) -> dict:
    return {
        "user_email":   row["user_email"],
        "acquired_at":  row["acquired_at"].isoformat(),
        "heartbeat_at": row["heartbeat_at"].isoformat(),
        "expires_at":   row["expires_at"].isoformat(),
    }


async def _current_holder(db, sid: str) -> Optional[dict]:
    row = (await db.execute(
        text(
            "SELECT user_email, acquired_at, heartbeat_at, expires_at "
            "  FROM session_locks "
            " WHERE session_id = CAST(:s AS uuid)"
        ),
        {"s": sid},
    )).mappings().first()
    return dict(row) if row else None


def _is_stale(row: dict) -> bool:
    """A lock row is stale if its expires_at is in the past."""
    from datetime import datetime, timezone
    expires_at = row["expires_at"]
    return expires_at < datetime.now(timezone.utc)


# ─── Routes ─────────────────────────────────────────────────────────────


@router.post("/{session_id}/lock/acquire", response_model=LockState)
async def acquire(session_id: UUID, db: DbSession, user: CurrentUser) -> dict:
    """
    Acquire or refresh the lock for this session.

    - If no row exists → insert + acquire.
    - If the row's holder is the caller → refresh heartbeat + return acquired=True.
    - If the row exists and is held by someone else AND is fresh → return acquired=False with the holder.
    - If the row exists and is held by someone else AND is stale → steal (UPDATE to caller) + return acquired=True.
    """
    sid = str(session_id)
    actor = user.email

    current = await _current_holder(db, sid)
    if current is None or current["user_email"] == actor or _is_stale(current):
        # Steal or refresh
        new_row = (await db.execute(
            text(
                "INSERT INTO session_locks (session_id, user_email, acquired_at, heartbeat_at, expires_at) "
                "VALUES (CAST(:s AS uuid), :u, now(), now(), now() + (:ttl || ' seconds')::interval) "
                "ON CONFLICT (session_id) DO UPDATE SET "
                "    user_email   = EXCLUDED.user_email, "
                "    acquired_at  = CASE WHEN session_locks.user_email = EXCLUDED.user_email THEN session_locks.acquired_at ELSE EXCLUDED.acquired_at END, "
                "    heartbeat_at = EXCLUDED.heartbeat_at, "
                "    expires_at   = EXCLUDED.expires_at "
                "RETURNING user_email, acquired_at, heartbeat_at, expires_at"
            ),
            {"s": sid, "u": actor, "ttl": str(LOCK_TTL_SECONDS)},
        )).mappings().first()
        await db.commit()
        return {
            "acquired": True,
            "is_self":  True,
            "holder":   _holder_dict(new_row),
        }

    return {
        "acquired": False,
        "is_self":  False,
        "holder":   _holder_dict(current),
    }


@router.post("/{session_id}/lock/heartbeat", response_model=LockState)
async def heartbeat(session_id: UUID, db: DbSession, user: CurrentUser) -> dict:
    """
    Refresh the heartbeat. Caller MUST be the current holder; otherwise
    returns acquired=False + the actual holder so the frontend can drop to
    read-only mode without losing context.

    Does NOT raise on contention — frontend wants the holder back to render
    the banner. We surface 409 only when the caller's session has been
    actively stolen.
    """
    sid = str(session_id)
    actor = user.email
    current = await _current_holder(db, sid)

    if current is None:
        # Lock was released by someone else (or never held). Caller can
        # re-acquire by calling /lock/acquire — keep this idempotent.
        return {"acquired": False, "is_self": False, "holder": None}

    if current["user_email"] != actor:
        return {
            "acquired": False,
            "is_self":  False,
            "holder":   _holder_dict(current),
        }

    refreshed = (await db.execute(
        text(
            "UPDATE session_locks SET "
            "    heartbeat_at = now(), "
            "    expires_at   = now() + (:ttl || ' seconds')::interval "
            "  WHERE session_id = CAST(:s AS uuid) "
            "    AND user_email = :u "
            "RETURNING user_email, acquired_at, heartbeat_at, expires_at"
        ),
        {"s": sid, "u": actor, "ttl": str(LOCK_TTL_SECONDS)},
    )).mappings().first()
    await db.commit()
    return {
        "acquired": True,
        "is_self":  True,
        "holder":   _holder_dict(refreshed) if refreshed else None,
    }


@router.post("/{session_id}/lock/release", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def release(session_id: UUID, db: DbSession, user: CurrentUser) -> Response:
    """Release the lock if the caller holds it. No-op if the caller is not the holder."""
    sid = str(session_id)
    await db.execute(
        text(
            "DELETE FROM session_locks "
            " WHERE session_id = CAST(:s AS uuid) "
            "   AND user_email = :u"
        ),
        {"s": sid, "u": user.email},
    )
    await db.commit()
    return Response(status_code=204)


@router.get("/{session_id}/lock/holder", response_model=LockState)
async def holder(session_id: UUID, db: DbSession, user: CurrentUser) -> dict:
    """Read the current holder. Used by the banner on read-only tabs."""
    sid = str(session_id)
    current = await _current_holder(db, sid)
    if current is None:
        return {"acquired": False, "is_self": False, "holder": None}
    return {
        "acquired": current["user_email"] == user.email and not _is_stale(current),
        "is_self":  current["user_email"] == user.email,
        "holder":   _holder_dict(current),
    }


@router.post("/{session_id}/lock/force-take", response_model=LockState)
async def force_take(session_id: UUID, db: DbSession, user: CurrentUser) -> dict:
    """
    Admin-only: force-take a lock regardless of staleness. Used when an
    operator's tab crashed and the 90-second TTL is too long to wait.
    Writes an audit_events row so the action is visible.
    """
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="admin required")

    sid = str(session_id)
    actor = user.email

    prior = await _current_holder(db, sid)
    new_row = (await db.execute(
        text(
            "INSERT INTO session_locks (session_id, user_email, acquired_at, heartbeat_at, expires_at) "
            "VALUES (CAST(:s AS uuid), :u, now(), now(), now() + (:ttl || ' seconds')::interval) "
            "ON CONFLICT (session_id) DO UPDATE SET "
            "    user_email   = EXCLUDED.user_email, "
            "    acquired_at  = EXCLUDED.acquired_at, "
            "    heartbeat_at = EXCLUDED.heartbeat_at, "
            "    expires_at   = EXCLUDED.expires_at "
            "RETURNING user_email, acquired_at, heartbeat_at, expires_at"
        ),
        {"s": sid, "u": actor, "ttl": str(LOCK_TTL_SECONDS)},
    )).mappings().first()

    import json
    await db.execute(text(
        "INSERT INTO audit_events (session_id, actor_email, kind, summary, details) "
        "VALUES (CAST(:s AS uuid), :a, 'session.lock_force_take', :sum, CAST(:d AS jsonb))"
    ), {
        "s":   sid,
        "a":   actor,
        "sum": f"Force-took editor lock from {prior['user_email'] if prior else '(no prior holder)'}",
        "d":   json.dumps({"prior_holder": prior["user_email"] if prior else None}),
    })

    await db.commit()
    return {
        "acquired": True,
        "is_self":  True,
        "holder":   _holder_dict(new_row),
    }
