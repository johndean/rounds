"""
/v1/improvements — master/detail + 5-step wizard.
IMPLEMENTATION.md §13.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.auth import CurrentUser
from app.db import DbSession

router = APIRouter(prefix="/v1/improvements", tags=["improvements"])


class ImprovementSummary(BaseModel):
    id: UUID
    title: str
    status: str
    risk: str
    priority: str
    submitted_at: str
    submitted_by: str
    is_security: bool


class ImprovementDetail(ImprovementSummary):
    description: Optional[str]
    type: Optional[str]
    area: Optional[str]
    target_version: Optional[str]
    admin_notes: Optional[str]
    requirements_md: Optional[str]
    implementation_md: Optional[str]
    testing_md: Optional[str]
    review_md: Optional[str]


class SuggestPayload(BaseModel):
    title: str = Field(..., min_length=3, max_length=512)
    description: Optional[str] = None
    type: Optional[str] = None
    priority: str = "medium"
    area: Optional[str] = None
    is_security: bool = False


class WizardStepPayload(BaseModel):
    body_md: str


class AdminPatch(BaseModel):
    status: Optional[str] = None
    risk: Optional[str] = None
    target_version: Optional[str] = None
    admin_notes: Optional[str] = None


def _row_to_summary(r: dict) -> dict:
    return {
        "id": r["id"],
        "title": r["title"],
        "status": r["status"],
        "risk": r["risk"],
        "priority": r["priority"],
        "submitted_at": r["submitted_at"].isoformat() if hasattr(r["submitted_at"], "isoformat") else r["submitted_at"],
        "submitted_by": r["submitted_by"],
        "is_security": r["is_security"],
    }


@router.get("", response_model=list[ImprovementSummary])
async def list_improvements(db: DbSession, _u: CurrentUser, status_filter: Optional[str] = None) -> list[dict]:
    if status_filter and status_filter != "all":
        rows = (await db.execute(text(
            "SELECT id, title, status, risk, priority, submitted_at, submitted_by, is_security "
            "FROM improvements WHERE deleted_at IS NULL AND status = :st "
            "ORDER BY submitted_at DESC"
        ), {"st": status_filter})).mappings().all()
    else:
        rows = (await db.execute(text(
            "SELECT id, title, status, risk, priority, submitted_at, submitted_by, is_security "
            "FROM improvements WHERE deleted_at IS NULL "
            "ORDER BY submitted_at DESC"
        ))).mappings().all()
    return [_row_to_summary(dict(r)) for r in rows]


@router.post("", response_model=ImprovementSummary, status_code=201)
async def suggest(payload: SuggestPayload, db: DbSession, user: CurrentUser) -> dict:
    import json
    row = (await db.execute(text(
        "INSERT INTO improvements (title, description, type, priority, area, is_security, submitted_by) "
        "VALUES (:t, :d, :ty, :p, :a, :sec, :sb) "
        "RETURNING id, title, status, risk, priority, submitted_at, submitted_by, is_security"
    ), {
        "t": payload.title, "d": payload.description, "ty": payload.type,
        "p": payload.priority, "a": payload.area, "sec": payload.is_security,
        "sb": user.email,
    })).mappings().one()
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary, details) "
        "VALUES (:a, 'improvement.suggest', :sum, CAST(:d AS jsonb))"
    ), {"a": user.email, "sum": f"suggested: {payload.title}",
        "d": json.dumps(payload.model_dump())})
    await db.commit()
    return _row_to_summary(dict(row))


@router.get("/{improvement_id}", response_model=ImprovementDetail)
async def get_improvement(improvement_id: UUID, db: DbSession, _u: CurrentUser) -> dict:
    row = (await db.execute(text(
        "SELECT * FROM improvements WHERE id = :id AND deleted_at IS NULL"
    ), {"id": str(improvement_id)})).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Improvement not found")
    base = _row_to_summary(dict(row))
    base.update({
        "description": row["description"],
        "type": row["type"],
        "area": row["area"],
        "target_version": row["target_version"],
        "admin_notes": row["admin_notes"],
        "requirements_md": row["requirements_md"],
        "implementation_md": row["implementation_md"],
        "testing_md": row["testing_md"],
        "review_md": row["review_md"],
    })
    return base


_WIZARD_COLUMNS = {
    "requirements":   "requirements_md",
    "implementation": "implementation_md",
    "testing":        "testing_md",
    "review":         "review_md",
}


@router.put("/{improvement_id}/wizard/{step}", response_model=ImprovementDetail)
async def save_wizard_step(improvement_id: UUID, step: str, payload: WizardStepPayload, db: DbSession, user: CurrentUser) -> dict:
    col = _WIZARD_COLUMNS.get(step)
    if not col:
        raise HTTPException(status_code=400, detail=f"Unknown wizard step: {step}")
    row = (await db.execute(text(
        f"UPDATE improvements SET {col} = :body, updated_at = now() "
        "WHERE id = :id AND deleted_at IS NULL RETURNING *"
    ), {"body": payload.body_md, "id": str(improvement_id)})).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Improvement not found")
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) "
        "VALUES (:a, 'improvement.wizard', :sum)"
    ), {"a": user.email, "sum": f"updated {step} on {improvement_id}"})
    await db.commit()
    return await get_improvement(improvement_id, db, user)


@router.patch("/{improvement_id}", response_model=ImprovementDetail)
async def admin_patch(improvement_id: UUID, payload: AdminPatch, db: DbSession, user: CurrentUser) -> dict:
    fields = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    sets = ", ".join(f"{k} = :{k}" for k in fields) + ", updated_at = now()"
    params = {**fields, "id": str(improvement_id)}
    row = (await db.execute(text(
        f"UPDATE improvements SET {sets} WHERE id = :id AND deleted_at IS NULL RETURNING *"
    ), params)).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Improvement not found")
    await db.commit()
    return await get_improvement(improvement_id, db, user)


@router.delete("/{improvement_id}", status_code=204, response_class=Response)
async def delete_improvement(improvement_id: UUID, db: DbSession, user: CurrentUser):
    await db.execute(text(
        "UPDATE improvements SET deleted_at = now() WHERE id = :id"
    ), {"id": str(improvement_id)})
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) VALUES (:a, 'improvement.delete', :s)"
    ), {"a": user.email, "s": f"deleted {improvement_id}"})
    await db.commit()
    return Response(status_code=204)
