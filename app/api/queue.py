"""
/v1/queue — per-user work queue.

Returns the sessions where the current user is the assignee for the
session's CURRENT SOP stage — i.e., the work the user needs to act on
right now. Sourced from sop_state.assignees JSONB which is written by
the stage-assignee reassign flow.

Phase 7-broader (2 of 2) of the 2026-06-04 stakeholder remediation.
Closes the "Queue visibility" requirement. The Phase 1 baseline
flagged that there was no per-user queue endpoint and the Dashboard's
"Your Queue" widget was just `allSessions.slice(0, 3)` — globally
sliced, not assignee-filtered.

Related ADRs: ADR-006 (queue processing).
Related business rules: BR-003 (SLA hours table mirrored here).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from app.auth import CurrentUser
from app.db import DbSession

router = APIRouter(prefix="/v1/queue", tags=["queue"])


class QueueItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    session_id:         str
    code:               str
    title:              Optional[str]
    title_short:        Optional[str]
    title_long:         Optional[str]
    status:             str
    current_stage:      str
    entered_current_at: Optional[str]
    overdue_hours:      Optional[float]


@router.get("/mine", response_model=list[QueueItemOut])
async def list_my_queue(db: DbSession, user: CurrentUser) -> list[dict]:
    """Sessions where ``user.email`` is the assignee for the session's
    current SOP stage. Ordered by ``entered_current_at`` ascending so
    the longest-waiting items surface first.

    Filters applied:
      * Excludes soft-deleted sessions
      * Excludes sessions in terminal stage ('complete')
      * Excludes group assignments ('group:NAME') for v1 — group
        expansion is deferred until a per-group roster table lands

    ``overdue_hours`` is computed server-side using the same
    _DEFAULT_SLA_HOURS map as app/tasks/sop_tasks.py so the client
    doesn't have to duplicate the per-stage SLA constants. Null when
    the stage is on-time. Negative semantically meaningless so capped
    at 0.

    Phase 7-broader (2 of 2). Read-only. No mutations.
    """
    # Per-stage SLA hours — mirrors app/tasks/sop_tasks.py:_DEFAULT_SLA_HOURS.
    # Inlined here (vs. importing from sop_tasks) because importing a Celery
    # task module from a FastAPI route would pull in the broker config; not
    # worth the indirection for an 8-entry constant.
    sla_hours = {
        "prep":       8,
        "copy_draft": 24,
        "medical":    48,
        "copy_final": 24,
        "cms":        12,
        "captions":   12,
        "qa":         8,
        "complete":   0,
    }
    # Phase 7-broader-2 hardening (2026-06-05): handle BOTH writers'
    # assignees JSONB shapes. Two writers exist:
    #   * app/api/sop.py::assign_stage writes a NESTED OBJECT:
    #       {"assignee": "user@vin.com", "assigned_by": ..., "assigned_at": ...}
    #   * app/tasks/sop_tasks.py + Settings -> Stages matrix writes a
    #     PLAIN STRING email (or "group:NAME" for groups).
    # The COALESCE matches either shape — nested-object path falls
    # back to flat-string path when the value isn't an object.
    rows = (
        await db.execute(
            text(
                """
                SELECT s.id            AS session_id,
                       s.code,
                       s.title,
                       s.title_short,
                       s.title_long,
                       s.status,
                       sop.current_stage,
                       sop.entered_current_at,
                       sop.sla_target_hours,
                       COALESCE(sop.assignees -> sop.current_stage ->> 'assignee',
                                sop.assignees ->> sop.current_stage) AS current_assignee
                  FROM sessions s
                  JOIN sop_state sop ON sop.session_id = s.id
                 WHERE COALESCE(sop.assignees -> sop.current_stage ->> 'assignee',
                                sop.assignees ->> sop.current_stage) = :email
                   AND s.deleted_at IS NULL
                   AND sop.current_stage != 'complete'
                 ORDER BY sop.entered_current_at ASC NULLS LAST
                 LIMIT 200
                """
            ),
            {"email": user.email},
        )
    ).mappings().all()

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    out: list[dict] = []
    for r in rows:
        entered = r["entered_current_at"]
        stage = r["current_stage"]
        # Per-session SLA override takes precedence over the default.
        sla_override = None
        if isinstance(r["sla_target_hours"], dict):
            sla_override = r["sla_target_hours"].get(stage)
        sla = sla_override if isinstance(sla_override, int) else sla_hours.get(stage, 24)
        overdue: Optional[float] = None
        if entered is not None and sla > 0:
            elapsed = (now - entered).total_seconds() / 3600.0
            if elapsed > sla:
                overdue = round(elapsed - sla, 1)
        out.append({
            "session_id":         str(r["session_id"]),
            "code":               r["code"],
            "title":              r["title"],
            "title_short":        r["title_short"],
            "title_long":         r["title_long"],
            "status":             r["status"],
            "current_stage":      stage,
            "entered_current_at": entered.isoformat() if entered else None,
            "overdue_hours":      overdue,
        })
    return out
