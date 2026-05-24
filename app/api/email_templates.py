"""
/v1/email-templates — stage-notification email template CRUD.

Phase 5 of the 2026-05-23 Settings BUILD remediation plan. Replaces the
fake-save EmailBuilder.vue handlers with real CRUD against the
email_templates table created by migration 048.

Two scopes:
  * session_type_id = NULL → default-for-all-types template (one per stage)
  * session_type_id = <uuid> → per-Type override for a specific stage

Resolution rule: given (session_type_id, stage_id, locale), the resolver
returns the per-type row if present, else the default row, else 404.

Test-send reuses the existing /v1/admin/email-debug/send endpoint via
the frontend (subject + body are substituted client-side before POST,
identical to the production stage-transition hook that will land in a
separate plan).
"""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.auth import CurrentUser
from app.db import DbSession

router = APIRouter(prefix="/v1/email-templates", tags=["email-templates"])


# Admin allowlist (matches settings.py / email_debug.py / diagnostics.py).
ADMIN_EMAIL = "johndean@vin.com"


def _require_admin(user) -> None:
    if not hasattr(user, "email") or user.email != ADMIN_EMAIL:
        raise HTTPException(
            status_code=403,
            detail={"code": "ADMIN_ONLY", "message": "admin only"},
        )


# Eight canonical SOP stages. Migration 048 seeds one default row per stage.
_VALID_STAGES = frozenset({
    "prep", "copy_draft", "medical", "copy_final",
    "cms", "captions", "qa", "complete",
})


class EmailTemplateCreate(BaseModel):
    """Body for POST /v1/email-templates."""
    session_type_id: Optional[UUID] = None       # NULL = applies to every Type
    stage_id:        str = Field(..., min_length=1)
    locale:          str = Field(default="en-US", min_length=2, max_length=10)
    subject:         str = Field(..., min_length=1, max_length=300)
    body:            str = Field(..., min_length=1, max_length=200_000)


class EmailTemplatePatch(BaseModel):
    """Body for PUT /v1/email-templates/{id}. None = leave unchanged."""
    subject: Optional[str] = Field(default=None, max_length=300)
    body:    Optional[str] = Field(default=None, max_length=200_000)
    locale:  Optional[str] = Field(default=None, min_length=2, max_length=10)


class ResolveRequest(BaseModel):
    """Body for POST /v1/email-templates/resolve."""
    session_type_id: Optional[UUID] = None
    stage_id:        str = Field(..., min_length=1)
    locale:          str = Field(default="en-US")


def _row_to_template(r) -> dict:
    return {
        "id":              str(r["id"]),
        "session_type_id": (str(r["session_type_id"]) if r["session_type_id"] else None),
        "stage_id":        r["stage_id"],
        "locale":          r["locale"],
        "subject":         r["subject"],
        "body":            r["body"],
        "created_by":      r["created_by"],
        "created_at":      r["created_at"].isoformat() if r["created_at"] else None,
        "updated_at":      r["updated_at"].isoformat() if r["updated_at"] else None,
    }


@router.get("")
async def list_email_templates(
    db: DbSession, _u: CurrentUser,
    session_type_id: Optional[UUID] = None,
    stage_id:        Optional[str]  = None,
    include_defaults: bool = True,
) -> list[dict]:
    """List active email templates. Optional filters.

    If session_type_id is given AND include_defaults is true, the result
    interleaves per-type rows with the default-type fallback rows so the
    UI can show "this Type uses default for stage X" without an extra
    fetch. Default = TRUE matches what EmailBuilder needs."""
    where = ["is_active = TRUE"]
    params: dict[str, Any] = {}

    if session_type_id is not None and include_defaults:
        # Either the per-type row OR a default-type row.
        where.append("(session_type_id = :tid OR session_type_id IS NULL)")
        params["tid"] = str(session_type_id)
    elif session_type_id is not None:
        where.append("session_type_id = :tid")
        params["tid"] = str(session_type_id)
    elif not include_defaults:
        where.append("session_type_id IS NOT NULL")

    if stage_id:
        where.append("stage_id = :sid")
        params["sid"] = stage_id

    rows = (await db.execute(text(
        "SELECT id, session_type_id, stage_id, locale, subject, body, "
        "       created_by, created_at, updated_at "
        "FROM email_templates "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY session_type_id NULLS FIRST, stage_id, locale"
    ), params)).mappings().all()
    return [_row_to_template(r) for r in rows]


@router.get("/{template_id}")
async def get_email_template(template_id: UUID, db: DbSession, _u: CurrentUser) -> dict:
    row = (await db.execute(text(
        "SELECT id, session_type_id, stage_id, locale, subject, body, "
        "       created_by, created_at, updated_at "
        "FROM email_templates WHERE id = :id AND is_active = TRUE"
    ), {"id": str(template_id)})).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Template not found"})
    return _row_to_template(row)


@router.post("", status_code=201)
async def create_email_template(
    payload: EmailTemplateCreate, db: DbSession, user: CurrentUser,
) -> dict:
    """Create a new per-Type or default-Type template for a given stage.
    Admin-only. 409 if an active row already exists for (type, stage, locale)."""
    _require_admin(user)
    if payload.stage_id not in _VALID_STAGES:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_STAGE", "message": f"stage_id must be one of {sorted(_VALID_STAGES)}"},
        )
    try:
        row = (await db.execute(text(
            "INSERT INTO email_templates "
            "  (session_type_id, stage_id, locale, subject, body, created_by) "
            "VALUES (:tid, :sid, :loc, :sub, :bod, :u) "
            "RETURNING id, session_type_id, stage_id, locale, subject, body, "
            "          created_by, created_at, updated_at"
        ), {
            "tid": (str(payload.session_type_id) if payload.session_type_id else None),
            "sid": payload.stage_id,
            "loc": payload.locale,
            "sub": payload.subject,
            "bod": payload.body,
            "u":   user.email,
        })).mappings().one()
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "duplicate key" in msg or "unique constraint" in msg:
            raise HTTPException(
                status_code=409,
                detail={"code": "DUPLICATE_TEMPLATE",
                        "message": "An active template already exists for that (type, stage, locale)."},
            )
        raise
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) "
        "VALUES (:a, 'settings.email_templates.add', :s)"
    ), {"a": user.email, "s": f"added template stage={payload.stage_id} type={payload.session_type_id or 'default'}"})
    await db.commit()
    return _row_to_template(row)


@router.put("/{template_id}")
async def update_email_template(
    template_id: UUID, payload: EmailTemplatePatch, db: DbSession, user: CurrentUser,
) -> dict:
    """Partial update. Admin-only."""
    _require_admin(user)
    sets: list[str] = []
    params: dict[str, Any] = {"id": str(template_id)}
    if payload.subject is not None: sets.append("subject = :sub"); params["sub"] = payload.subject
    if payload.body    is not None: sets.append("body = :bod");    params["bod"] = payload.body
    if payload.locale  is not None: sets.append("locale = :loc");  params["loc"] = payload.locale
    if not sets:
        raise HTTPException(
            status_code=400,
            detail={"code": "NO_CHANGES", "message": "No fields to update."},
        )
    sets.append("updated_at = now()")

    row = (await db.execute(text(
        f"UPDATE email_templates SET {', '.join(sets)} "
        f"WHERE id = :id AND is_active = TRUE "
        f"RETURNING id, session_type_id, stage_id, locale, subject, body, "
        f"          created_by, created_at, updated_at"
    ), params)).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Template not found"})
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) "
        "VALUES (:a, 'settings.email_templates.update', :s)"
    ), {"a": user.email, "s": f"updated template {template_id} stage={row['stage_id']}"})
    await db.commit()
    return _row_to_template(row)


@router.delete("/{template_id}", status_code=204, response_class=Response)
async def remove_email_template(template_id: UUID, db: DbSession, user: CurrentUser):
    """Soft-delete (is_active = FALSE). Admin-only."""
    _require_admin(user)
    row = (await db.execute(text(
        "SELECT stage_id, session_type_id FROM email_templates "
        "WHERE id = :id AND is_active = TRUE"
    ), {"id": str(template_id)})).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Template not found"})
    await db.execute(text(
        "UPDATE email_templates SET is_active = FALSE, updated_at = now() WHERE id = :id"
    ), {"id": str(template_id)})
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) "
        "VALUES (:a, 'settings.email_templates.remove', :s)"
    ), {"a": user.email, "s": f"removed template stage={row['stage_id']} type={row['session_type_id'] or 'default'}"})
    await db.commit()
    return Response(status_code=204)


@router.post("/resolve")
async def resolve_template(
    payload: ResolveRequest, db: DbSession, _u: CurrentUser,
) -> dict:
    """Given (session_type_id, stage_id, locale), return the template that
    would actually fire — per-type if it exists, else default. Used by the
    EmailBuilder preview AND by the future stage-transition Celery hook
    so both code paths share the resolution logic."""
    if payload.stage_id not in _VALID_STAGES:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_STAGE", "message": f"stage_id must be one of {sorted(_VALID_STAGES)}"},
        )
    # Try per-type first.
    if payload.session_type_id is not None:
        row = (await db.execute(text(
            "SELECT id, session_type_id, stage_id, locale, subject, body, "
            "       created_by, created_at, updated_at "
            "FROM email_templates "
            "WHERE session_type_id = :tid AND stage_id = :sid AND locale = :loc "
            "  AND is_active = TRUE"
        ), {
            "tid": str(payload.session_type_id),
            "sid": payload.stage_id,
            "loc": payload.locale,
        })).mappings().first()
        if row:
            return {**_row_to_template(row), "resolved_from": "per_type"}

    # Fall back to default (session_type_id IS NULL).
    row = (await db.execute(text(
        "SELECT id, session_type_id, stage_id, locale, subject, body, "
        "       created_by, created_at, updated_at "
        "FROM email_templates "
        "WHERE session_type_id IS NULL AND stage_id = :sid AND locale = :loc "
        "  AND is_active = TRUE"
    ), {"sid": payload.stage_id, "loc": payload.locale})).mappings().first()
    if row:
        return {**_row_to_template(row), "resolved_from": "default"}

    raise HTTPException(
        status_code=404,
        detail={"code": "NOT_FOUND",
                "message": f"No active template for stage={payload.stage_id} locale={payload.locale}."},
    )
