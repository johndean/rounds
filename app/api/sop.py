"""
/v1/sessions/{session_id}/sop — SOP workflow state machine.

8 stages per IMPLEMENTATION.md §8 / §9 Pipeline 2:
  prep · copy_draft · medical · copy_final · cms · captions · qa · complete
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.auth import CurrentUser
from app.db import DbSession

router = APIRouter(prefix="/v1/sessions/{session_id}/sop", tags=["sop"])

STAGES = ["prep", "copy_draft", "medical", "copy_final", "cms", "captions", "qa", "complete"]
_STAGE_INDEX = {s: i for i, s in enumerate(STAGES)}


class SopState(BaseModel):
    current_stage: str
    is_blocked: bool
    blockers: list[dict]
    assignees: dict
    sla_target_hours: dict


class AdvancePayload(BaseModel):
    to_stage: str = Field(..., min_length=1)
    note: Optional[str] = None


class CheckResolvePayload(BaseModel):
    check_id: str
    label: str


def _validate_transition(from_stage: str, to_stage: str) -> None:
    """Allow forward-only transitions; reject jumps + backward moves."""
    if to_stage not in _STAGE_INDEX:
        raise HTTPException(status_code=400, detail=f"Unknown stage: {to_stage}")
    if from_stage not in _STAGE_INDEX:
        raise HTTPException(status_code=400, detail=f"Unknown current stage: {from_stage}")
    if _STAGE_INDEX[to_stage] != _STAGE_INDEX[from_stage] + 1:
        raise HTTPException(
            status_code=400,
            detail=f"Illegal transition {from_stage} → {to_stage}; must advance one stage forward",
        )


@router.get("", response_model=SopState)
async def get_state(session_id: UUID, db: DbSession, _u: CurrentUser) -> dict:
    row = (await db.execute(text(
        "SELECT current_stage, is_blocked, blockers, assignees, sla_target_hours "
        "FROM sop_state WHERE session_id = :s"
    ), {"s": str(session_id)})).mappings().first()
    if not row:
        # Auto-create initial state on first read
        await db.execute(text(
            "INSERT INTO sop_state (session_id, current_stage) VALUES (:s, 'prep') "
            "ON CONFLICT (session_id) DO NOTHING"
        ), {"s": str(session_id)})
        await db.commit()
        return {"current_stage": "prep", "is_blocked": False, "blockers": [], "assignees": {}, "sla_target_hours": {}}
    return dict(row)


@router.post("/advance", response_model=SopState, status_code=status.HTTP_200_OK)
async def advance(session_id: UUID, payload: AdvancePayload, db: DbSession, user: CurrentUser) -> dict:
    import json
    cur = (await db.execute(text(
        "SELECT current_stage, is_blocked FROM sop_state WHERE session_id = :s FOR UPDATE"
    ), {"s": str(session_id)})).mappings().first()
    if not cur:
        raise HTTPException(status_code=404, detail="SOP state not initialized; GET /sop first")
    if cur["is_blocked"]:
        raise HTTPException(status_code=400, detail="Cannot advance while blocked")
    _validate_transition(cur["current_stage"], payload.to_stage)

    row = (await db.execute(text(
        "UPDATE sop_state SET current_stage = :to, entered_current_at = now(), updated_at = now() "
        "WHERE session_id = :s "
        "RETURNING current_stage, is_blocked, blockers, assignees, sla_target_hours"
    ), {"to": payload.to_stage, "s": str(session_id)})).mappings().one()

    await db.execute(text(
        "INSERT INTO sop_transitions (session_id, from_stage, to_stage, actor_email, note) "
        "VALUES (:s, :f, :t, :a, :n)"
    ), {"s": str(session_id), "f": cur["current_stage"], "t": payload.to_stage, "a": user.email, "n": payload.note})
    await db.execute(text(
        "INSERT INTO audit_events (session_id, actor_email, kind, summary, details) "
        "VALUES (:s, :a, 'sop.advance', :sum, CAST(:d AS jsonb))"
    ), {"s": str(session_id), "a": user.email,
        "sum": f"advanced {cur['current_stage']} → {payload.to_stage}",
        "d": json.dumps({"from": cur["current_stage"], "to": payload.to_stage, "note": payload.note})})
    await db.commit()
    return dict(row)


@router.post("/checks/resolve")
async def resolve_check(session_id: UUID, payload: CheckResolvePayload, db: DbSession, user: CurrentUser) -> dict:
    cur = (await db.execute(text(
        "SELECT current_stage FROM sop_state WHERE session_id = :s"
    ), {"s": str(session_id)})).mappings().first()
    if not cur:
        raise HTTPException(status_code=404, detail="SOP state not initialized")
    await db.execute(text(
        "INSERT INTO sop_checks (session_id, stage, check_id, label, is_resolved, resolved_by, resolved_at) "
        "VALUES (:s, :st, :cid, :l, TRUE, :a, now()) "
        "ON CONFLICT (session_id, stage, check_id) DO UPDATE "
        "SET is_resolved = TRUE, resolved_by = EXCLUDED.resolved_by, resolved_at = now()"
    ), {"s": str(session_id), "st": cur["current_stage"], "cid": payload.check_id, "l": payload.label, "a": user.email})
    await db.execute(text(
        "INSERT INTO audit_events (session_id, actor_email, kind, summary) "
        "VALUES (:s, :a, 'sop.check.resolve', :sum)"
    ), {"s": str(session_id), "a": user.email, "sum": f"resolved {payload.check_id}"})
    await db.commit()
    return {"resolved": True, "check_id": payload.check_id, "stage": cur["current_stage"]}
