"""
/v1/sessions — list / get / create / delete sessions.

Supports the frontend's ?stage / ?ai / ?f query params for filtered lists
(IMPLEMENTATION.md §6 + §9 Pipeline circles → /sessions?ai=… or ?stage=…).
"""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db import DbSession

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])

# Admin allowlist for destructive session ops (port from MIC `app/api/sessions.py:51-52`).
# `johndean@vin.com` is the seeded admin. SESSION_TRASH_ALLOWED gates soft-delete;
# restore + permanent purge require strict `ADMIN_EMAIL` only (one-person blast radius).
# Could move to `org_settings.session_trash_allowed_emails` in a follow-up phase.
ADMIN_EMAIL = "johndean@vin.com"
SESSION_TRASH_ALLOWED = {ADMIN_EMAIL, "carlab@vin.com"}


# ─── Pydantic schemas ──────────────────────────────────────────────────
class PipelineConfig(BaseModel):
    """
    Pipeline routing captured at upload. Persisted to `session_templates`.
    The 7 UploadView form fields all live here.
    """
    ai_pipeline: str = Field(default="direct")               # direct | enhanced — default flipped 2026-05-20 so legacy clients without a pipeline_config don't silently land on enhanced+transcript (STT-quality output)
    ai_mode: str     = Field(default="transcript")           # transcript | summary | key-moments | structured-notes | custom-prompt
    ai_model: str    = Field(default="gemini-2.5-pro")
    prompt_mode: str = Field(default="transcript")
    custom_prompt: Optional[str] = None
    stt_backend: str = Field(default="google_latest_long")
    template_id: str = Field(default="lecture_v1")
    iil_config: dict[str, Any] = Field(default_factory=lambda: {"enabled": True, "tier1": True, "tier2": True, "tier3": True})


class SessionIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=512)
    presenter: Optional[str] = None
    duration_sec: Optional[int] = None
    attendee_count: Optional[int] = None
    taxonomy: list[str] = Field(default_factory=list)
    pipeline_config: Optional[PipelineConfig] = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    title: str
    # extras2 manifest-derived titles. title_long is the full lecture title
    # ("Cardiac Biomarkers — NT-proBNP & Troponin"); title_short is the
    # display label ("NT-proBNP"). Frontend cascades title_long > title_short
    # > title so the ugly auto-generated upload code never wins when the
    # manifest provided real metadata. MIC parity (mic/app/api/sessions.py:751-752).
    title_long: Optional[str] = None
    title_short: Optional[str] = None
    presenter: Optional[str]
    status: str
    duration_sec: Optional[int]
    word_count: Optional[int]
    segment_count: Optional[int]
    attendee_count: Optional[int]
    taxonomy: list[str]
    # FK to session_types row chosen at ingest. Drives auto-init of
    # session_stage_assignees from that Type's matrix (Unit 6). Nullable
    # until migration 044 backfills or the manifest assigns one.
    session_type_id: Optional[UUID] = None


class SessionPatch(BaseModel):
    """PATCH body — partial update. None means "leave unchanged"; an empty
    string ("") explicitly clears the field. Whitelist enforced server-side
    so unknown fields are silently ignored (MIC parity)."""
    code:            Optional[str] = None
    title:           Optional[str] = None
    title_long:      Optional[str] = None
    title_short:    Optional[str] = None
    presenter:       Optional[str] = None
    session_type_id: Optional[UUID] = None


class StageAssigneePatch(BaseModel):
    """Body for `PUT /v1/sessions/{id}/stage-assignees/{stage}`.

    Supports two shapes:
      1. Frontend-friendly: `{assignee_email: "...", notify_email: true}` —
         server resolves the email to either person_id or group_id (matches
         the existing Settings → Types matrix picker contract).
      2. Typed: `{person_id: "<uuid>"}` or `{group_id: "<uuid>"}` — direct
         FK assignment, used when the inline picker knows the ID.

    Empty body (all None) resets the stage to its Type-matrix default via
    a re-init lookup. CHECK constraint enforces exactly one of
    person_id/group_id is set; the resolver in the handler upholds that."""
    assignee_email: Optional[str] = None     # "carlab@vin.com" | "Group: External" | "(unassigned)"
    person_id:      Optional[UUID] = None
    group_id:       Optional[UUID] = None
    notify_email:   Optional[bool] = None


# ─── Endpoints ─────────────────────────────────────────────────────────
@router.get("", response_model=list[SessionOut])
async def list_sessions(
    db: DbSession,
    _user: CurrentUser,
    stage: Optional[str] = None,    # SOP stage filter — ?stage=medical
    ai: Optional[str]    = None,    # AI pipeline stage   — ?ai=transcribe
    f: Optional[str]     = None,    # free-text query     — ?f=…
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """
    Lists non-deleted sessions, optionally filtered by SOP stage (via sop_state
    join), AI processing stage (via sessions.status), or free-text on code/title.
    """
    from sqlalchemy import text
    where = ["deleted_at IS NULL"]
    params: dict[str, object] = {"limit": limit, "offset": offset}
    if ai:
        where.append("status = :ai")
        params["ai"] = ai
    if f:
        where.append("(LOWER(code) LIKE :f OR LOWER(title) LIKE :f)")
        params["f"] = f"%{f.lower()}%"
    sql = f"""
        SELECT s.id, s.code, s.title, s.title_long, s.title_short,
               s.presenter, s.status, s.duration_sec,
               s.word_count, s.segment_count, s.attendee_count, s.taxonomy,
               s.session_type_id
        FROM sessions s
        {"JOIN sop_state st ON st.session_id = s.id AND st.stage = :stage" if stage else ""}
        WHERE {' AND '.join(where)}
        ORDER BY s.created_at DESC NULLS LAST, s.code DESC
        LIMIT :limit OFFSET :offset
    """
    if stage:
        params["stage"] = stage
    rows = (await db.execute(text(sql), params)).mappings().all()
    return [dict(r) for r in rows]


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(payload: SessionIn, db: DbSession, user: CurrentUser) -> dict:
    """
    Create a session row + the matching `session_templates` row that carries
    the pipeline routing chosen on Upload. The two writes happen in the same
    transaction so `ingest_task` always finds a config row.

    Code collision handling: a prior failed/abandoned session leaves a row
    with the same code. Frontend genCode() now appends a 4-char random
    suffix to make collisions astronomically unlikely — but if one still
    happens (e.g. legacy clients without the suffix), surface it as a clean
    409 CONFLICT envelope rather than letting the IntegrityError bubble up
    as a 500.
    """
    import json

    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from app.middleware.envelope import ConflictError

    try:
        row = (
            await db.execute(
                text(
                    """
                    INSERT INTO sessions (code, title, presenter, duration_sec, attendee_count, taxonomy, status)
                    VALUES (:code, :title, :presenter, :duration_sec, :attendee_count, CAST(:taxonomy AS jsonb), 'uploading')
                    RETURNING id, code, title, title_long, title_short, presenter, status, duration_sec, word_count, segment_count, attendee_count, taxonomy, session_type_id
                    """
                ),
                {
                    "code": payload.code,
                    "title": payload.title,
                    "presenter": payload.presenter,
                    "duration_sec": payload.duration_sec,
                    "attendee_count": payload.attendee_count,
                    "taxonomy": '["' + '","'.join(payload.taxonomy) + '"]' if payload.taxonomy else '[]',
                },
            )
        ).mappings().one()
    except IntegrityError as exc:
        await db.rollback()
        # Detect the specific sessions_code_key UNIQUE constraint violation.
        msg = str(exc.orig).lower() if getattr(exc, "orig", None) else str(exc).lower()
        if "sessions_code_key" in msg or ("code" in msg and "duplicate" in msg):
            raise ConflictError(
                message="A session with that code already exists. Retry — the upload form generates a fresh code on each submit.",
                details={"code": payload.code, "constraint": "sessions_code_key"},
            ) from exc
        raise

    # Pipeline config — fall back to defaults if not supplied (legacy clients).
    cfg = payload.pipeline_config or PipelineConfig()
    await db.execute(
        text(
            """
            INSERT INTO session_templates
                (session_id, ai_pipeline, ai_mode, ai_model, prompt_mode, custom_prompt,
                 stt_backend, template_id, iil_config)
            VALUES
                (:sid, :ai_pipeline, :ai_mode, :ai_model, :prompt_mode, :custom_prompt,
                 :stt_backend, :template_id, CAST(:iil_config AS jsonb))
            """
        ),
        {
            "sid":           str(row["id"]),
            "ai_pipeline":   cfg.ai_pipeline,
            "ai_mode":       cfg.ai_mode,
            "ai_model":      cfg.ai_model,
            "prompt_mode":   cfg.prompt_mode,
            "custom_prompt": cfg.custom_prompt,
            "stt_backend":   cfg.stt_backend,
            "template_id":   cfg.template_id,
            "iil_config":    json.dumps(cfg.iil_config),
        },
    )
    await db.commit()
    return dict(row)


# ─── /v1/sessions/{id}/pipeline-config ────────────────────────────────
class PipelineConfigOut(PipelineConfig):
    auto_detected_template_id: Optional[str] = None
    auto_detected_confidence: Optional[float] = None


# ─── Soft-deleted lifecycle (Phase 3 — port from MIC sessions.py:161-1687) ──
@router.get("/deleted")
async def list_deleted_sessions(db: DbSession, _user: CurrentUser) -> list[dict]:
    """
    Admin-only listing of soft-deleted sessions (deleted_at IS NOT NULL,
    within 30-day recovery window). Backs Settings → Deleted Sessions.
    Rows older than 30 days are hidden from this view but the DB row remains
    until permanent purge so the audit ledger can still join.

    Must be declared BEFORE `GET /{session_id}` so the literal path wins.
    """
    if not hasattr(_user, "email") or _user.email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Only admin can view deleted sessions")

    from sqlalchemy import text
    rows = (
        await db.execute(
            text(
                """
                SELECT id, code, title, presenter, status, created_at, deleted_at
                  FROM sessions
                 WHERE deleted_at IS NOT NULL
                   AND deleted_at >= now() - interval '30 days'
                 ORDER BY deleted_at DESC
                """
            )
        )
    ).mappings().all()
    return [
        {
            "session_id": str(r["id"]),
            "code":       r["code"],
            "title":      r["title"],
            "presenter":  r["presenter"],
            "status":     r["status"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "deleted_at": r["deleted_at"].isoformat() if r["deleted_at"] else None,
        }
        for r in rows
    ]


@router.get("/{session_id}/audit-log")
async def get_audit_log(session_id: UUID, db: DbSession, _u: CurrentUser) -> list[dict]:
    """Returns the append-only state-transition log written by the state machine."""
    from sqlalchemy import text

    row = (
        await db.execute(
            text("SELECT processing_log FROM session_audit WHERE session_id = :sid"),
            {"sid": str(session_id)},
        )
    ).mappings().first()
    if not row:
        return []
    log = row["processing_log"]
    return log if isinstance(log, list) else []


@router.get("/{session_id}/pipeline-config", response_model=PipelineConfigOut)
async def get_pipeline_config(session_id: UUID, db: DbSession, _u: CurrentUser) -> dict:
    from sqlalchemy import text

    row = (
        await db.execute(
            text(
                """
                SELECT ai_pipeline, ai_mode, ai_model, prompt_mode, custom_prompt,
                       stt_backend, template_id, iil_config,
                       auto_detected_template_id, auto_detected_confidence
                FROM session_templates WHERE session_id = :sid
                """
            ),
            {"sid": str(session_id)},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="No pipeline config for session")
    return dict(row)


@router.get("/{session_id}/stage-assignees")
async def get_session_stage_assignees(
    session_id: UUID, db: DbSession, _user: CurrentUser,
) -> list[dict]:
    """
    Per-session, per-stage assignees populated at ingest from the chosen
    Type's matrix (Unit 6 of the Team & Roles port). Returns one row per
    stage with the typed FK joined to people/groups so renames + deletes
    propagate immediately. The Editor's right-rail Admin chip + the SOP
    stepper render assignees from this endpoint.

    `source` distinguishes 'default' (auto-populated at ingest) from
    'manual' (operator override via future PATCH endpoint).
    """
    rows = (await db.execute(text(
        """
        SELECT ssa.stage, ssa.notify_email, ssa.source, ssa.assigned_at,
               ssa.person_id, ssa.group_id,
               p.email AS person_email, p.name AS person_name, p.role AS person_role,
               p.avatar_color AS person_avatar_color,
               g.name  AS group_name,
               -- Display label that survives rename — JOIN-resolved.
               COALESCE(p.name, 'Group: ' || g.name, '(unassigned)') AS assignee_label
          FROM session_stage_assignees ssa
          LEFT JOIN people p ON p.id = ssa.person_id
          LEFT JOIN groups g ON g.id = ssa.group_id
         WHERE ssa.session_id = :sid
         ORDER BY ssa.stage
        """
    ), {"sid": str(session_id)})).mappings().all()
    return [dict(r) for r in rows]


@router.put("/{session_id}/stage-assignees/{stage}")
async def set_session_stage_assignee(
    session_id: UUID,
    stage:      str,
    payload:    StageAssigneePatch,
    db:         DbSession,
    user:       CurrentUser,
) -> dict:
    """
    Override a single stage's assignee for this session. Sets `source='manual'`
    so the widget can render an override-indicator dot. Empty body resets the
    stage to its Type-matrix default and flips `source` back to 'default'.

    Resolution order:
      1. payload.person_id (typed) wins if non-null.
      2. payload.group_id (typed) wins if person_id is null.
      3. payload.assignee_email parsed: "carlab@vin.com" → person,
         "Group: External" → group, "(unassigned)" → both null (= reset).
      4. All three null → reset to Type-matrix default for this stage.

    CHECK constraint chk_session_stage_assignees_single_assignee guarantees
    exactly one of person_id/group_id can be non-null at the DB level.
    """
    from sqlalchemy import text

    person_id: str | None = str(payload.person_id) if payload.person_id else None
    group_id:  str | None = str(payload.group_id)  if payload.group_id  else None

    # Frontend-friendly assignee_email shape (matches the Settings matrix picker).
    if person_id is None and group_id is None and payload.assignee_email:
        email = payload.assignee_email.strip()
        if email and email != "(unassigned)":
            if email.startswith("Group: "):
                row = (await db.execute(
                    text("SELECT id FROM groups WHERE name = :n"),
                    {"n": email[len("Group: "):]},
                )).first()
                group_id = str(row[0]) if row else None
            else:
                row = (await db.execute(
                    text("SELECT id FROM people WHERE LOWER(email) = LOWER(:e)"),
                    {"e": email},
                )).first()
                person_id = str(row[0]) if row else None

    is_reset = person_id is None and group_id is None and payload.assignee_email != "(unassigned)" \
        and not (payload.assignee_email and payload.assignee_email != "(unassigned)")

    if is_reset:
        # Pull the default for this stage from the session's Type (or org default).
        default_row = (await db.execute(text(
            """
            SELECT sa.person_id, sa.group_id, sa.notify_email
              FROM stage_assignees sa
              JOIN sessions s ON s.id = CAST(:sid AS uuid)
             WHERE sa.type_id = COALESCE(
                 s.session_type_id,
                 (SELECT id FROM session_types WHERE is_default = TRUE LIMIT 1)
             )
               AND sa.stage = :stage
            """
        ), {"sid": str(session_id), "stage": stage})).first()
        if default_row:
            person_id     = str(default_row[0]) if default_row[0] else None
            group_id      = str(default_row[1]) if default_row[1] else None
            notify_email  = bool(default_row[2]) if default_row[2] is not None else True
            source        = "default"
        else:
            notify_email = True if payload.notify_email is None else payload.notify_email
            source       = "default"
    else:
        notify_email = True if payload.notify_email is None else payload.notify_email
        source       = "manual"

    await db.execute(text(
        """
        INSERT INTO session_stage_assignees
            (session_id, stage, person_id, group_id, notify_email, source, assigned_by, assigned_at)
        VALUES
            (CAST(:sid AS uuid), :stage,
             CASE WHEN :pid IS NULL THEN NULL ELSE CAST(:pid AS uuid) END,
             CASE WHEN :gid IS NULL THEN NULL ELSE CAST(:gid AS uuid) END,
             :ne, :src, :actor, now())
        ON CONFLICT (session_id, stage) DO UPDATE
          SET person_id    = EXCLUDED.person_id,
              group_id     = EXCLUDED.group_id,
              notify_email = EXCLUDED.notify_email,
              source       = EXCLUDED.source,
              assigned_by  = EXCLUDED.assigned_by,
              assigned_at  = now()
        """
    ), {
        "sid":   str(session_id),
        "stage": stage,
        "pid":   person_id,
        "gid":   group_id,
        "ne":    notify_email,
        "src":   source,
        "actor": user.email,
    })
    await db.commit()

    row = (await db.execute(text(
        """
        SELECT ssa.stage, ssa.notify_email, ssa.source, ssa.assigned_at,
               ssa.person_id, ssa.group_id,
               p.email AS person_email, p.name AS person_name, p.role AS person_role,
               p.avatar_color AS person_avatar_color,
               g.name  AS group_name,
               COALESCE(p.name, 'Group: ' || g.name, '(unassigned)') AS assignee_label
          FROM session_stage_assignees ssa
          LEFT JOIN people p ON p.id = ssa.person_id
          LEFT JOIN groups g ON g.id = ssa.group_id
         WHERE ssa.session_id = :sid AND ssa.stage = :stage
        """
    ), {"sid": str(session_id), "stage": stage})).mappings().first()
    return dict(row) if row else {"stage": stage, "source": source}


@router.post("/{session_id}/stage-assignees/apply-type-defaults")
async def apply_type_defaults(
    session_id: UUID,
    db:         DbSession,
    user:       CurrentUser,
    type_id:    Optional[UUID] = None,
) -> dict:
    """
    Bulk-apply the session's Type matrix into session_stage_assignees.

    Operator-triggered from the Session Detail Type picker's "Apply Type
    defaults" banner. Overwrites every stage with the (optionally specified)
    Type's matrix and marks `source='default'`. If `type_id` is omitted,
    uses the session's existing `session_type_id` (falling back to org default).

    Idempotent: re-running is safe.
    """
    from sqlalchemy import create_engine

    from app.config import settings
    from app.services.session_init import init_session_stages

    # If the operator passed a new type_id, persist it first so init reads it.
    if type_id is not None:
        await db.execute(text(
            "UPDATE sessions SET session_type_id = :tid, updated_at = now() "
            "WHERE id = :sid AND deleted_at IS NULL"
        ), {"tid": str(type_id), "sid": str(session_id)})

    # Wipe existing rows so 'manual' overrides are intentionally replaced.
    # The banner flow asks the operator to confirm this before clicking Apply.
    await db.execute(text(
        "DELETE FROM session_stage_assignees WHERE session_id = :sid"
    ), {"sid": str(session_id)})
    await db.commit()

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    try:
        stages = init_session_stages(
            engine, str(session_id),
            type_id=str(type_id) if type_id else None,
            actor=f"apply-type-defaults:{user.email}",
        )
    finally:
        engine.dispose()
    return {"session_id": str(session_id), "stages": stages}


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: UUID, db: DbSession, _user: CurrentUser) -> dict:
    from sqlalchemy import text
    row = (
        await db.execute(
            text(
                """
                SELECT id, code, title, title_long, title_short,
                       presenter, status, duration_sec, word_count, segment_count,
                       attendee_count, taxonomy, session_type_id
                FROM sessions
                WHERE id = :id AND deleted_at IS NULL
                """
            ),
            {"id": str(session_id)},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    return dict(row)


@router.patch("/{session_id}", response_model=SessionOut)
async def update_session(
    session_id: UUID,
    payload:    SessionPatch,
    db:         DbSession,
    _user:      CurrentUser,
) -> dict:
    """
    Partial update of session metadata. Whitelisted fields only: code, title,
    title_long, title_short, presenter. Unknown fields are ignored. An empty
    string explicitly clears a field; null leaves it unchanged.

    Port of MIC `app/api/sessions.py:1479-1513`. Used by the inline-edit UI
    in SessionDetailView / SessionsView to rename a session or fix a code
    after upload.
    """
    from sqlalchemy import text

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updatable fields provided")

    set_clauses = [f"{k} = :{k}" for k in updates]
    set_clauses.append("updated_at = now()")
    sql = (
        f"UPDATE sessions SET {', '.join(set_clauses)} "
        "WHERE id = :sid AND deleted_at IS NULL "
        "RETURNING id, code, title, title_long, title_short, presenter, status, "
        "          duration_sec, word_count, segment_count, attendee_count, taxonomy, "
        "          session_type_id"
    )
    params = {**updates, "sid": str(session_id)}
    try:
        row = (await db.execute(text(sql), params)).mappings().first()
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "sessions_code_key" in msg or ("code" in msg and "duplicate" in msg):
            raise HTTPException(
                status_code=409,
                detail={
                    "code":    "DUPLICATE_CODE",
                    "message": "Another session already uses that code.",
                },
            )
        raise HTTPException(status_code=500, detail=str(exc))

    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.commit()
    return dict(row)


@router.delete("/{session_id}")
async def delete_session(session_id: UUID, db: DbSession, _user: CurrentUser) -> dict:
    """
    Soft-delete a session. Sets `deleted_at`; data preserved for 30 days.

    Admin-gated (Phase 3 port from MIC `sessions.py:1529`): only emails in
    SESSION_TRASH_ALLOWED can soft-delete. Restore + permanent purge are
    strictly ADMIN_EMAIL only.
    """
    if not hasattr(_user, "email") or _user.email not in SESSION_TRASH_ALLOWED:
        raise HTTPException(status_code=403, detail="Only admin can delete sessions")

    from sqlalchemy import text

    row = (
        await db.execute(
            text("SELECT id, deleted_at FROM sessions WHERE id = :id"),
            {"id": str(session_id)},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    if row["deleted_at"] is not None:
        from app.middleware.envelope import ConflictError
        raise ConflictError(message="Session is already deleted")

    await db.execute(
        text("UPDATE sessions SET deleted_at = now(), updated_at = now() WHERE id = :id"),
        {"id": str(session_id)},
    )
    await db.commit()

    # Release the Redis rate-limit slot. Without this, every soft-deleted
    # session continues to count against the operator's MAX_CONCURRENT_SESSIONS
    # cap (=3), which manifests as a 429 toast on the next upload. Mirrors
    # MIC `sessions.py:1556-1562`.
    try:
        from app.middleware.rate_limit import release_slot
        release_slot(_user.email if hasattr(_user, "email") else None, str(session_id))
    except Exception as exc:  # noqa: BLE001
        # Non-fatal — the DB delete already succeeded.
        import logging
        logging.getLogger(__name__).warning(f"delete_session: release_slot failed: {exc}")

    return {"session_id": str(session_id), "deleted": True}


@router.post("/{session_id}/restore")
async def restore_session(session_id: UUID, db: DbSession, _user: CurrentUser) -> dict:
    """
    Restore a soft-deleted session — clears `deleted_at`. Admin-only.
    Port of MIC `app/api/sessions.py:1570-1606`.
    """
    if not hasattr(_user, "email") or _user.email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Only admin can restore sessions")

    from sqlalchemy import text
    row = (
        await db.execute(
            text("SELECT id, deleted_at FROM sessions WHERE id = :id"),
            {"id": str(session_id)},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    if row["deleted_at"] is None:
        from app.middleware.envelope import ConflictError
        raise ConflictError(message="Session is not deleted")

    await db.execute(
        text("UPDATE sessions SET deleted_at = NULL, updated_at = now() WHERE id = :id"),
        {"id": str(session_id)},
    )
    await db.commit()
    return {"session_id": str(session_id), "restored": True}


@router.delete("/{session_id}/permanent")
async def permanent_delete_session(session_id: UUID, db: DbSession, _user: CurrentUser) -> dict:
    """
    Hard-delete a session and all its child rows. Must be soft-deleted first
    so the operator has had a chance to reconsider. Admin-only. Irreversible.

    Manual cascade: some child tables lack `ON DELETE CASCADE` on their FK.
    We delete in dependency order, then the parent. Port of MIC
    `app/api/sessions.py:1612-1687` adapted to the Rounds schema.
    """
    if not hasattr(_user, "email") or _user.email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Only admin can permanently delete sessions")

    from sqlalchemy import text
    row = (
        await db.execute(
            text("SELECT id, deleted_at FROM sessions WHERE id = :id"),
            {"id": str(session_id)},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    if row["deleted_at"] is None:
        from app.middleware.envelope import ConflictError
        raise ConflictError(message="Session must be soft-deleted before permanent deletion")

    # Rounds schema declares `ON DELETE CASCADE` on every child FK referencing
    # `sessions(id)` (segments → words also cascades), so a single DELETE on
    # the parent row reaps the entire dependency tree. The MIC port used a
    # manual cascade because MIC's schema lacks CASCADE; that workaround is
    # unnecessary here. Keep `audit_events.session_id` (ON DELETE SET NULL,
    # migration 004) so historical events survive for forensic queries.
    try:
        await db.execute(
            text("DELETE FROM sessions WHERE id = CAST(:sid AS uuid)"),
            {"sid": str(session_id)},
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        import logging
        logging.getLogger(__name__).error(
            f"permanent_delete_session({session_id}) cascade failed: {exc}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Cascade delete failed: {exc.__class__.__name__}")

    # Release the rate-limit slot just in case it wasn't released on soft-delete.
    try:
        from app.middleware.rate_limit import release_slot
        release_slot(_user.email if hasattr(_user, "email") else None, str(session_id))
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning(f"permanent_delete: release_slot failed: {exc}")

    return {"session_id": str(session_id), "permanently_deleted": True}


@router.get("/{session_id}/failure-reason")
async def get_failure_reason(session_id: UUID, db: DbSession, _u: CurrentUser) -> dict:
    """
    Surfaces the reason a session is in `failed` status. Returns the last
    audit-log transition that flipped the session into `failed`, plus the
    raw `reason` string the worker wrote.

    Used by the Sessions list page's failure-detail modal.
    """
    from sqlalchemy import text

    sess = (
        await db.execute(
            text(
                """
                SELECT id, code, title, status, deleted_at, created_at, updated_at
                FROM sessions WHERE id = :id
                """
            ),
            {"id": str(session_id)},
        )
    ).mappings().first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    audit = (
        await db.execute(
            text("SELECT processing_log FROM session_audit WHERE session_id = :sid"),
            {"sid": str(session_id)},
        )
    ).mappings().first()
    log = (audit or {}).get("processing_log") or []
    if not isinstance(log, list):
        log = []

    last_failed = None
    for entry in reversed(log):
        if isinstance(entry, dict) and (entry.get("next") == "failed" or entry.get("status") == "failed"):
            last_failed = entry
            break

    return {
        "session_id": str(session_id),
        "code":       sess["code"],
        "title":      sess["title"],
        "status":     sess["status"],
        "reason":     (last_failed or {}).get("reason") if last_failed else None,
        "category":   (last_failed or {}).get("category") if last_failed else None,
        "ts":         (last_failed or {}).get("ts") if last_failed else None,
        "actor":      (last_failed or {}).get("actor") if last_failed else None,
        "log_tail":   log[-10:],
    }
