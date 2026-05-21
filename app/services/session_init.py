"""
Per-session stage assignee initialization from the chosen Type's matrix.

Unit 6 of the Team & Roles port. Called after ingest determines (or the
operator picks) `sessions.session_type_id`. Copies the Type's
`stage_assignees` rows into `session_stage_assignees` so the Editor's
right-rail Admin chip + the SOP stepper render assignees from the start.

Idempotent: ON CONFLICT (session_id, stage) DO NOTHING — re-running for
an already-initialized session is a no-op so the operator's manual
overrides survive a reingest.

Wrapped at the call site in try/except so a transient failure here never
blocks the ingest pipeline. Same safety posture as `auto_place_polls`.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection, Engine

logger = logging.getLogger(__name__)


def init_session_stages(
    engine_or_conn: "Engine | Connection",
    session_id: str,
    type_id: Optional[str] = None,
    *,
    actor: str = "system:auto_init",
) -> int:
    """
    Copy the given Type's `stage_assignees` rows into
    `session_stage_assignees` for the session. Returns the number of
    rows written (zero on re-run since ON CONFLICT skips).

    If `type_id` is None, falls back to the org default Type
    (session_types.is_default = TRUE). The default row is guaranteed by
    migration 038's UPDATE clause.

    Accepts either a SQLAlchemy Engine (opens its own transaction) or an
    already-open Connection (joins the caller's transaction) — same pattern
    as `auto_place_polls`.
    """
    from sqlalchemy import text
    from sqlalchemy.engine import Connection

    # If the session doesn't have a Type pinned yet, persist the resolved
    # default into sessions.session_type_id so future reads + the operator
    # UI know which matrix this session was initialized against.
    resolve_type_sql = text("""
        WITH chosen AS (
            SELECT
                CASE
                    WHEN :tid IS NOT NULL THEN CAST(:tid AS uuid)
                    ELSE (SELECT id FROM session_types WHERE is_default = TRUE LIMIT 1)
                END AS type_id
        )
        UPDATE sessions
           SET session_type_id = chosen.type_id
          FROM chosen
         WHERE sessions.id = CAST(:sid AS uuid)
           AND sessions.session_type_id IS DISTINCT FROM chosen.type_id
         RETURNING sessions.session_type_id
    """)

    insert_sql = text("""
        INSERT INTO session_stage_assignees
            (session_id, stage, person_id, group_id, notify_email, source, assigned_by, assigned_at)
        SELECT
            CAST(:sid AS uuid),
            sa.stage,
            sa.person_id,
            sa.group_id,
            sa.notify_email,
            'default',
            :actor,
            now()
          FROM stage_assignees sa
          JOIN sessions s ON s.id = CAST(:sid AS uuid)
         WHERE sa.type_id = COALESCE(
             s.session_type_id,
             (SELECT id FROM session_types WHERE is_default = TRUE LIMIT 1)
         )
        ON CONFLICT (session_id, stage) DO NOTHING
        RETURNING stage
    """)

    params_resolve = {"sid": session_id, "tid": type_id}
    params_insert = {"sid": session_id, "actor": actor}

    def _exec(conn) -> int:
        conn.execute(resolve_type_sql, params_resolve)
        rows = conn.execute(insert_sql, params_insert).fetchall()
        return len(rows)

    if isinstance(engine_or_conn, Connection):
        count = _exec(engine_or_conn)
    else:
        with engine_or_conn.begin() as conn:
            count = _exec(conn)

    if count > 0:
        logger.info(
            f"init_session_stages: session={session_id} stages_written={count} actor={actor}"
        )
    else:
        logger.info(f"init_session_stages: session={session_id} no_op (already initialized)")
    return count


def resolve_type_by_code(engine_or_conn: "Engine | Connection", code: str) -> Optional[str]:
    """
    Look up a session_types row by code (case-insensitive). Returns the
    UUID string, or None if no match.

    Used by the manifest-parse hook in gcs_upload.py to translate a
    manifest's `type: AAFV` field into the FK value.
    """
    from sqlalchemy import text
    from sqlalchemy.engine import Connection

    sql = text("SELECT id FROM session_types WHERE LOWER(code) = LOWER(:code) LIMIT 1")
    params = {"code": code}

    if isinstance(engine_or_conn, Connection):
        row = engine_or_conn.execute(sql, params).fetchone()
    else:
        with engine_or_conn.connect() as conn:
            row = conn.execute(sql, params).fetchone()
    return str(row[0]) if row else None
