"""
/v1/settings — org-wide settings k/v + the 12 sections from IMPLEMENTATION.md §10.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.auth import CurrentUser
from app.db import DbSession

router = APIRouter(prefix="/v1/settings", tags=["settings"])


class SettingValue(BaseModel):
    key: str
    value: Any


class PersonPayload(BaseModel):
    email: str
    name: str
    role: str | None = None
    avatar_color: str | None = None


class GroupPayload(BaseModel):
    name: str
    description: str | None = None


@router.get("", response_model=dict[str, Any])
async def list_settings(db: DbSession, _u: CurrentUser) -> dict[str, Any]:
    rows = (await db.execute(text("SELECT key, value FROM org_settings"))).mappings().all()
    return {r["key"]: r["value"] for r in rows}


@router.put("/{key}", response_model=SettingValue)
async def set_setting(key: str, payload: SettingValue, db: DbSession, user: CurrentUser) -> dict:
    import json
    if payload.key != key:
        raise HTTPException(status_code=400, detail="Key mismatch")
    await db.execute(text(
        "INSERT INTO org_settings (key, value, updated_by) "
        "VALUES (:k, CAST(:v AS jsonb), :u) "
        "ON CONFLICT (key) DO UPDATE "
        "SET value = EXCLUDED.value, updated_by = EXCLUDED.updated_by, updated_at = now()"
    ), {"k": key, "v": json.dumps(payload.value), "u": user.email})
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) VALUES (:a, 'settings.set', :s)"
    ), {"a": user.email, "s": f"updated {key}"})
    await db.commit()
    return payload


# ─── People / groups ────────────────────────────────────────────────────
@router.get("/people")
async def list_people(db: DbSession, _u: CurrentUser) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT id, email, name, role, avatar_color, is_active FROM people ORDER BY name"
    ))).mappings().all()
    return [dict(r) for r in rows]


@router.post("/people", status_code=201)
async def add_person(payload: PersonPayload, db: DbSession, user: CurrentUser) -> dict:
    row = (await db.execute(text(
        "INSERT INTO people (email, name, role, avatar_color) VALUES (:e, :n, :r, :ac) "
        "ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name, role = EXCLUDED.role, avatar_color = EXCLUDED.avatar_color, is_active = TRUE "
        "RETURNING id, email, name, role, avatar_color, is_active"
    ), {"e": payload.email.lower(), "n": payload.name, "r": payload.role, "ac": payload.avatar_color})).mappings().one()
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) VALUES (:a, 'settings.people.add', :s)"
    ), {"a": user.email, "s": f"added {payload.email}"})
    await db.commit()
    return dict(row)


@router.delete("/people/{person_id}", status_code=204, response_class=Response)
async def remove_person(person_id: UUID, db: DbSession, user: CurrentUser):
    await db.execute(text("UPDATE people SET is_active = FALSE WHERE id = :id"), {"id": str(person_id)})
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) VALUES (:a, 'settings.people.remove', :s)"
    ), {"a": user.email, "s": f"deactivated {person_id}"})
    await db.commit()
    return Response(status_code=204)


@router.get("/groups")
async def list_groups(db: DbSession, _u: CurrentUser) -> list[dict]:
    rows = (await db.execute(text("SELECT id, name, description FROM groups ORDER BY name"))).mappings().all()
    return [dict(r) for r in rows]


@router.post("/groups", status_code=201)
async def add_group(payload: GroupPayload, db: DbSession, user: CurrentUser) -> dict:
    row = (await db.execute(text(
        "INSERT INTO groups (name, description) VALUES (:n, :d) "
        "ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description "
        "RETURNING id, name, description"
    ), {"n": payload.name, "d": payload.description})).mappings().one()
    await db.commit()
    return dict(row)


# ─── Session types + stage assignee matrix ──────────────────────────────
@router.get("/types")
async def list_types(db: DbSession, _u: CurrentUser) -> list[dict]:
    rows = (await db.execute(text("SELECT id, code, label FROM session_types ORDER BY label"))).mappings().all()
    return [dict(r) for r in rows]


@router.get("/types/{type_id}/assignees")
async def get_type_assignees(type_id: UUID, db: DbSession, _u: CurrentUser) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT id, stage, assignee_email, notify_email FROM stage_assignees "
        "WHERE type_id = :t ORDER BY stage"
    ), {"t": str(type_id)})).mappings().all()
    return [dict(r) for r in rows]


# ─── Email templates ────────────────────────────────────────────────────
@router.get("/email-templates")
async def list_email_templates(db: DbSession, _u: CurrentUser) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT id, type_id, stage, subject, enabled, updated_at "
        "FROM email_templates ORDER BY stage"
    ))).mappings().all()
    return [dict(r) for r in rows]
