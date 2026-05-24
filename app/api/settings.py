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


# Admin allowlist (matches sessions.py / email_debug.py).
ADMIN_EMAIL = "johndean@vin.com"


def _require_admin(user) -> None:
    if not hasattr(user, "email") or user.email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="admin only")


class SettingValue(BaseModel):
    key: str
    value: Any


class PersonPayload(BaseModel):
    email: str
    name: str
    role: str | None = None
    avatar_color: str | None = None


class PersonPatch(BaseModel):
    """Partial-update body for PUT /people/{id}. None means leave unchanged."""
    email:        str | None = None
    name:         str | None = None
    role:         str | None = None
    avatar_color: str | None = None
    is_active:    bool | None = None


class GroupPayload(BaseModel):
    name: str
    description: str | None = None


class GroupPatch(BaseModel):
    """Partial-update body for PUT /groups/{id}. None means leave unchanged."""
    name:        str | None = None
    description: str | None = None


class TypePayload(BaseModel):
    code: str = Field(..., min_length=1, max_length=128)
    label: str | None = None


class StageAssigneeRow(BaseModel):
    stage: str = Field(..., min_length=1, max_length=64)
    assignee_email: str = Field(..., min_length=1, max_length=255)
    notify_email: bool = False


class StageAssigneeBulk(BaseModel):
    rows: list[StageAssigneeRow]


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


@router.put("/people/{person_id}")
async def update_person(person_id: UUID, payload: PersonPatch, db: DbSession, user: CurrentUser) -> dict:
    """
    Partial update of a person row. Whitelisted fields only: email, name, role,
    avatar_color, is_active. Unknown / unset fields are ignored. Port of MIC
    PUT /v1/sop/people/{person_id}.
    """
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updatable fields provided")

    # Lowercase email at the boundary to match POST behavior.
    if "email" in updates and updates["email"]:
        updates["email"] = updates["email"].lower()

    set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
    sql = (
        f"UPDATE people SET {set_clauses} WHERE id = :pid "
        "RETURNING id, email, name, role, avatar_color, is_active"
    )
    try:
        row = (await db.execute(text(sql), {**updates, "pid": str(person_id)})).mappings().first()
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "people_email_key" in msg or ("email" in msg and "duplicate" in msg):
            raise HTTPException(
                status_code=409,
                detail={"code": "DUPLICATE_EMAIL", "message": "Another person already uses that email."},
            )
        raise HTTPException(status_code=500, detail=str(exc))
    if not row:
        raise HTTPException(status_code=404, detail="Person not found")
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) VALUES (:a, 'settings.people.update', :s)"
    ), {"a": user.email, "s": f"updated {person_id} fields={list(updates.keys())}"})
    await db.commit()
    return dict(row)


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
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) VALUES (:a, 'settings.groups.add', :s)"
    ), {"a": user.email, "s": f"added group {payload.name}"})
    await db.commit()
    return dict(row)


@router.put("/groups/{group_id}")
async def update_group(group_id: UUID, payload: GroupPatch, db: DbSession, user: CurrentUser) -> dict:
    """Partial update — rename + description. Port of MIC PUT /v1/sop/groups/{group_id}."""
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updatable fields provided")
    set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
    sql = (
        f"UPDATE groups SET {set_clauses} WHERE id = :gid "
        "RETURNING id, name, description"
    )
    try:
        row = (await db.execute(text(sql), {**updates, "gid": str(group_id)})).mappings().first()
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "groups_name_key" in msg or ("name" in msg and "duplicate" in msg):
            raise HTTPException(
                status_code=409,
                detail={"code": "DUPLICATE_NAME", "message": "Another group already uses that name."},
            )
        raise HTTPException(status_code=500, detail=str(exc))
    if not row:
        raise HTTPException(status_code=404, detail="Group not found")
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) VALUES (:a, 'settings.groups.update', :s)"
    ), {"a": user.email, "s": f"updated {group_id} fields={list(updates.keys())}"})
    await db.commit()
    return dict(row)


@router.delete("/groups/{group_id}", status_code=204, response_class=Response)
async def remove_group(group_id: UUID, db: DbSession, user: CurrentUser):
    """Hard-delete a group. group_members rows cascade. Port of MIC DELETE /v1/sop/groups/{group_id}.

    Stage assignees stored as "Group: X" strings in stage_assignees.assignee_email are
    not affected here — those are TEXT, not FKs. The follow-up Unit 5 plan migrates
    that surface to typed FKs and adds ON DELETE SET NULL behavior.
    """
    result = await db.execute(text("DELETE FROM groups WHERE id = :id"), {"id": str(group_id)})
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Group not found")
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) VALUES (:a, 'settings.groups.remove', :s)"
    ), {"a": user.email, "s": f"removed group {group_id}"})
    await db.commit()
    return Response(status_code=204)


@router.get("/groups/{group_id}/members")
async def list_group_members(group_id: UUID, db: DbSession, _u: CurrentUser) -> list[dict]:
    """Members of a group, joined to people for display fields."""
    rows = (await db.execute(text(
        "SELECT p.id, p.email, p.name, p.role, p.avatar_color, p.is_active "
        "FROM group_members gm JOIN people p ON p.id = gm.person_id "
        "WHERE gm.group_id = :gid AND p.is_active = TRUE "
        "ORDER BY p.name"
    ), {"gid": str(group_id)})).mappings().all()
    return [dict(r) for r in rows]


@router.get("/groups-members")
async def list_all_group_members(db: DbSession, _u: CurrentUser) -> dict[str, list[dict]]:
    """Bulk fan-out of /groups/{id}/members across every group, returned as
    `{ group_id: [person, ...] }`. Replaces the N-RPC pattern in SectionTeam
    (one call per group on hydrate). Phase 7 of the 2026-05-23 perf plan.

    Same row shape as the per-group endpoint, same is_active filter, same
    ORDER BY name within a group. Groups with zero members are omitted
    (the caller already has the group ids from /groups and can default
    missing entries to []).
    """
    rows = (await db.execute(text(
        "SELECT gm.group_id, p.id, p.email, p.name, p.role, p.avatar_color, p.is_active "
        "FROM group_members gm JOIN people p ON p.id = gm.person_id "
        "WHERE p.is_active = TRUE "
        "ORDER BY gm.group_id, p.name"
    ))).mappings().all()
    out: dict[str, list[dict]] = {}
    for r in rows:
        gid = str(r["group_id"])
        person = {k: r[k] for k in ("id", "email", "name", "role", "avatar_color", "is_active")}
        out.setdefault(gid, []).append(person)
    return out


@router.post("/groups/{group_id}/members/{person_id}", status_code=201)
async def add_group_member(
    group_id: UUID, person_id: UUID, db: DbSession, user: CurrentUser,
) -> dict:
    """Add person to group. Idempotent via ON CONFLICT. Port of MIC POST /v1/sop/groups/{gid}/members/{pid}."""
    try:
        await db.execute(text(
            "INSERT INTO group_members (group_id, person_id) VALUES (:g, :p) "
            "ON CONFLICT (group_id, person_id) DO NOTHING"
        ), {"g": str(group_id), "p": str(person_id)})
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "foreign key" in msg or "fk" in msg:
            raise HTTPException(status_code=404, detail="Group or person not found")
        raise HTTPException(status_code=500, detail=str(exc))
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) VALUES (:a, 'settings.groups.member_add', :s)"
    ), {"a": user.email, "s": f"added {person_id} to {group_id}"})
    await db.commit()
    return {"group_id": str(group_id), "person_id": str(person_id), "added": True}


@router.delete("/groups/{group_id}/members/{person_id}", status_code=204, response_class=Response)
async def remove_group_member(
    group_id: UUID, person_id: UUID, db: DbSession, user: CurrentUser,
):
    """Remove person from group. Port of MIC DELETE /v1/sop/groups/{gid}/members/{pid}."""
    result = await db.execute(text(
        "DELETE FROM group_members WHERE group_id = :g AND person_id = :p"
    ), {"g": str(group_id), "p": str(person_id)})
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Membership not found")
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) VALUES (:a, 'settings.groups.member_remove', :s)"
    ), {"a": user.email, "s": f"removed {person_id} from {group_id}"})
    await db.commit()
    return Response(status_code=204)


# ─── Session types + stage assignee matrix ──────────────────────────────
@router.get("/types")
async def list_types(db: DbSession, _u: CurrentUser) -> list[dict]:
    """List Types ordered with the default row first, then alphabetical. Default
    flag is surfaced so the frontend can render the DEFAULT chip + prevent
    delete. is_default column is added by migration 038."""
    rows = (await db.execute(text(
        "SELECT id, code, label, is_default FROM session_types "
        "ORDER BY is_default DESC, label"
    ))).mappings().all()
    return [dict(r) for r in rows]


@router.post("/types", status_code=201)
async def add_type(payload: TypePayload, db: DbSession, user: CurrentUser) -> dict:
    _require_admin(user)
    row = (await db.execute(text(
        "INSERT INTO session_types (code, label) VALUES (:c, :l) "
        "ON CONFLICT (code) DO UPDATE SET label = EXCLUDED.label "
        "RETURNING id, code, label, is_default"
    ), {"c": payload.code, "l": payload.label or payload.code})).mappings().one()
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) VALUES (:a, 'settings.types.add', :s)"
    ), {"a": user.email, "s": f"added type {payload.code}"})
    await db.commit()
    return dict(row)


@router.delete("/types/{type_id}", status_code=204, response_class=Response)
async def remove_type(type_id: UUID, db: DbSession, user: CurrentUser):
    _require_admin(user)
    # Refuse to delete the org default — every session needs a starting Type.
    # Frontend hides the Remove button on the default row but a malicious client
    # could still send DELETE; enforce server-side too. Port of MIC SettingsTypes.vue:91.
    is_default_row = (await db.execute(text(
        "SELECT is_default FROM session_types WHERE id = :id"
    ), {"id": str(type_id)})).scalar()
    if is_default_row is True:
        raise HTTPException(
            status_code=409,
            detail={"code": "DEFAULT_TYPE_LOCKED", "message": "Cannot delete the default Type."},
        )
    # Hard delete is fine — stage_assignees + email_templates cascade.
    await db.execute(text("DELETE FROM session_types WHERE id = :id"), {"id": str(type_id)})
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) VALUES (:a, 'settings.types.remove', :s)"
    ), {"a": user.email, "s": f"removed type {type_id}"})
    await db.commit()
    return Response(status_code=204)


async def _resolve_assignee(
    db: DbSession, assignee_email: str,
) -> tuple[str | None, str | None, str]:
    """
    Translate the frontend's `assignee_email` value into typed FKs +
    a canonical display string. Returns (person_id, group_id, label).

    - "carlab@vin.com"   → ('<uuid>', None, 'carlab@vin.com')
    - "Group: External"  → (None, '<uuid>', 'Group: External')
    - "(unassigned)"     → (None, None, '')
    - unmatched person   → (None, None, '<email>')  (kept for back-compat)
    """
    if not assignee_email or assignee_email == "(unassigned)":
        return None, None, ""

    if assignee_email.startswith("Group: "):
        group_name = assignee_email[len("Group: "):]
        row = (await db.execute(
            text("SELECT id FROM groups WHERE name = :n"), {"n": group_name},
        )).first()
        return None, (str(row[0]) if row else None), assignee_email

    row = (await db.execute(
        text("SELECT id FROM people WHERE LOWER(email) = LOWER(:e)"),
        {"e": assignee_email},
    )).first()
    return (str(row[0]) if row else None), None, assignee_email


_TYPE_ASSIGNEES_SELECT = """
    SELECT sa.id, sa.stage, sa.notify_email,
           -- Prefer typed FK display fields; fall back to the legacy email
           -- so rows backfilled before migration 040 still render.
           COALESCE(p.email,
                    CASE WHEN sa.assignee_email LIKE 'Group: %'
                         THEN sa.assignee_email ELSE NULL END,
                    sa.assignee_email)   AS assignee_email,
           COALESCE(p.name,
                    'Group: ' || g.name,
                    NULLIF(sa.assignee_email, ''))   AS assignee_label,
           sa.person_id,
           sa.group_id
      FROM stage_assignees sa
      LEFT JOIN people p ON p.id = sa.person_id
      LEFT JOIN groups g ON g.id = sa.group_id
     WHERE sa.type_id = :t
     ORDER BY sa.stage
"""


@router.get("/types/{type_id}/assignees")
async def get_type_assignees(type_id: UUID, db: DbSession, _u: CurrentUser) -> list[dict]:
    """
    Per-Type stage matrix with typed FKs joined to display data. Renaming
    a person or group propagates here immediately via the JOIN — Unit 5
    of the Team & Roles port. assignee_email surface is preserved so the
    existing frontend picker continues to work unchanged.
    """
    rows = (await db.execute(text(_TYPE_ASSIGNEES_SELECT), {"t": str(type_id)})).mappings().all()
    return [dict(r) for r in rows]


@router.put("/types/{type_id}/assignees")
async def set_type_assignees(
    type_id: UUID, payload: StageAssigneeBulk, db: DbSession, user: CurrentUser,
) -> list[dict]:
    """
    Bulk-replace this Type's stage_assignees rows. Frontend sends all 8 stages
    in one PUT; we delete the existing rows for the type and re-insert with
    typed person_id / group_id FKs resolved from assignee_email at write time
    (Unit 5). assignee_email is also persisted for back-compat with any
    consumer that hasn't migrated yet.
    """
    _require_admin(user)
    exists = (await db.execute(
        text("SELECT 1 FROM session_types WHERE id = :id"), {"id": str(type_id)},
    )).first()
    if not exists:
        raise HTTPException(status_code=404, detail="type not found")

    await db.execute(text("DELETE FROM stage_assignees WHERE type_id = :t"), {"t": str(type_id)})
    for r in payload.rows:
        if not r.assignee_email or r.assignee_email == "(unassigned)":
            continue
        person_id, group_id, canonical_email = await _resolve_assignee(db, r.assignee_email)
        await db.execute(text(
            "INSERT INTO stage_assignees "
            "    (type_id, stage, person_id, group_id, assignee_email, notify_email) "
            "VALUES (:t, :s, :pid, :gid, :ae, :ne)"
        ), {
            "t":   str(type_id),
            "s":   r.stage,
            "pid": person_id,
            "gid": group_id,
            "ae":  canonical_email,
            "ne":  r.notify_email,
        })
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) VALUES (:a, 'settings.types.assignees', :s)"
    ), {"a": user.email, "s": f"updated matrix for type {type_id} ({len(payload.rows)} rows)"})
    await db.commit()

    rows = (await db.execute(text(_TYPE_ASSIGNEES_SELECT), {"t": str(type_id)})).mappings().all()
    return [dict(r) for r in rows]


# Email templates moved to /v1/email-templates (its own router) in Phase 5
# of the 2026-05-23 Settings BUILD plan. The placeholder GET that used to
# live here referenced an outdated column schema (type_id / stage / enabled)
# that doesn't match migration 048's table; it had zero frontend callers.


# ─── Auth users (Settings → Auth & Logins) ──────────────────────────────
# Reset-only password model: passwords are bcrypt-hashed at rest and never
# returned by any GET. The only way to set a new password is the explicit
# reset endpoint, which accepts plaintext over the same TLS boundary as
# /v1/auth/login. See docs/plans/2026-05-21-auth-users-db-backed.md.
_AUTH_USER_SELECT = (
    "SELECT id, email, role, is_active, last_login_at, password_reset_at, "
    "       created_at, updated_at "
    "  FROM auth_users "
)


class AuthUserCreate(BaseModel):
    email:    str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=10, max_length=256)
    role:     str = Field(default="user")


class AuthUserPatch(BaseModel):
    """Role / activation toggles. Password changes go through the dedicated
    reset endpoint so we never overload PATCH with privileged plaintext."""
    role:      str | None = None
    is_active: bool | None = None


class AuthUserResetPassword(BaseModel):
    password: str = Field(..., min_length=10, max_length=256)


def _row_to_auth_user(row) -> dict:
    """Whitelist projection — password_hash is NEVER included in API responses."""
    return {
        "id":                 str(row["id"]),
        "email":              row["email"],
        "role":               row["role"],
        "is_active":          bool(row["is_active"]),
        "last_login_at":      row["last_login_at"].isoformat() if row["last_login_at"] else None,
        "password_reset_at":  row["password_reset_at"].isoformat() if row["password_reset_at"] else None,
        "created_at":         row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at":         row["updated_at"].isoformat() if row["updated_at"] else None,
    }


async def _count_active_admins(db) -> int:
    return (await db.execute(text(
        "SELECT count(*) FROM auth_users WHERE role = 'admin' AND is_active = TRUE"
    ))).scalar() or 0


async def _get_auth_user_or_404(db, user_id: UUID) -> dict:
    row = (await db.execute(
        text(_AUTH_USER_SELECT + "WHERE id = :id"),
        {"id": str(user_id)},
    )).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="user not found")
    return dict(row)


@router.get("/auth-users")
async def list_auth_users(db: DbSession, user: CurrentUser) -> list[dict]:
    _require_admin(user)
    rows = (await db.execute(text(_AUTH_USER_SELECT + "ORDER BY email"))).mappings().all()
    return [_row_to_auth_user(r) for r in rows]


@router.post("/auth-users", status_code=201)
async def add_auth_user(payload: AuthUserCreate, db: DbSession, user: CurrentUser) -> dict:
    _require_admin(user)
    if payload.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail={"code": "BAD_ROLE", "message": "role must be 'admin' or 'user'"})

    from app.services.auth_users import hash_password

    hashed = hash_password(payload.password)
    try:
        row = (await db.execute(text(
            "INSERT INTO auth_users (email, password_hash, role) "
            "VALUES (:e, :h, :r) "
            "RETURNING id, email, role, is_active, last_login_at, password_reset_at, "
            "          created_at, updated_at"
        ), {"e": payload.email.lower().strip(), "h": hashed, "r": payload.role})).mappings().one()
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "auth_users_email_lower_uq" in msg or ("email" in msg and ("duplicate" in msg or "unique" in msg)):
            raise HTTPException(
                status_code=409,
                detail={"code": "DUPLICATE_EMAIL", "message": "That email already has a login."},
            )
        raise HTTPException(status_code=500, detail=str(exc))

    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) "
        "VALUES (:a, 'settings.auth_user.add', :s)"
    ), {"a": user.email, "s": f"added {payload.email.lower()} role={payload.role}"})
    await db.commit()
    return _row_to_auth_user(row)


@router.put("/auth-users/{user_id}")
async def update_auth_user(user_id: UUID, payload: AuthUserPatch, db: DbSession, user: CurrentUser) -> dict:
    _require_admin(user)

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updatable fields provided")

    if "role" in updates and updates["role"] not in ("admin", "user"):
        raise HTTPException(status_code=400, detail={"code": "BAD_ROLE", "message": "role must be 'admin' or 'user'"})

    # Last-admin guard: refuse to demote or disable the only active admin.
    current = await _get_auth_user_or_404(db, user_id)
    would_demote = (current["role"] == "admin" and updates.get("role") == "user")
    would_disable = (current["is_active"] is True and updates.get("is_active") is False)
    if (would_demote or (would_disable and current["role"] == "admin")):
        admins = await _count_active_admins(db)
        if admins <= 1:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "LAST_ADMIN_PROTECTED",
                    "message": "Cannot demote or disable the only active admin. Add a second admin first.",
                },
            )

    set_clauses = ", ".join(f"{k} = :{k}" for k in updates) + ", updated_at = now()"
    sql = (
        f"UPDATE auth_users SET {set_clauses} WHERE id = :uid "
        "RETURNING id, email, role, is_active, last_login_at, password_reset_at, "
        "          created_at, updated_at"
    )
    row = (await db.execute(text(sql), {**updates, "uid": str(user_id)})).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="user not found")

    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) "
        "VALUES (:a, 'settings.auth_user.update', :s)"
    ), {"a": user.email, "s": f"updated {user_id} fields={list(updates.keys())}"})
    await db.commit()
    return _row_to_auth_user(row)


@router.post("/auth-users/{user_id}/reset-password")
async def reset_auth_user_password(
    user_id: UUID, payload: AuthUserResetPassword, db: DbSession, user: CurrentUser,
) -> dict:
    _require_admin(user)
    from app.services.auth_users import hash_password

    current = await _get_auth_user_or_404(db, user_id)
    hashed = hash_password(payload.password)
    await db.execute(text(
        "UPDATE auth_users "
        "   SET password_hash = :h, password_reset_at = now(), updated_at = now() "
        " WHERE id = :uid"
    ), {"h": hashed, "uid": str(user_id)})
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) "
        "VALUES (:a, 'settings.auth_user.reset_password', :s)"
    ), {"a": user.email, "s": f"reset password for {current['email']}"})
    await db.commit()
    return {
        "email":              current["email"],
        "password_reset_at":  datetime_now_iso(),
    }


def datetime_now_iso() -> str:
    """Tiny helper so the reset response surface uses the same shape as
    other timestamps without dragging a datetime import to module top."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


@router.delete("/auth-users/{user_id}", status_code=204, response_class=Response)
async def remove_auth_user(user_id: UUID, db: DbSession, user: CurrentUser):
    _require_admin(user)

    current = await _get_auth_user_or_404(db, user_id)
    # Last-admin guard.
    if current["role"] == "admin" and current["is_active"]:
        admins = await _count_active_admins(db)
        if admins <= 1:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "LAST_ADMIN_PROTECTED",
                    "message": "Cannot delete the only active admin. Add a second admin first.",
                },
            )

    await db.execute(text("DELETE FROM auth_users WHERE id = :uid"), {"uid": str(user_id)})
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) "
        "VALUES (:a, 'settings.auth_user.delete', :s)"
    ), {"a": user.email, "s": f"deleted {current['email']}"})
    await db.commit()
    return Response(status_code=204)


# ── /v1/settings/export/macro ───────────────────────────────────────────────
# Phase 3 of the 2026-05-23 Settings BUILD remediation plan.
#
# Streams a zip generated on-the-fly from `docs/macros/` in the repo. If the
# directory is empty or absent, returns a clean 404 with code=MACRO_NOT_FOUND
# so the frontend can surface "not available in this deploy" instead of
# silently failing. When the macro source files are committed under
# docs/macros/, the next deploy serves the bundle with zero code change.

@router.get("/export/macro")
async def download_macro(db: DbSession, user: CurrentUser):
    """Serve the Word + CMS export macro bundle as a zip. Files live in
    `docs/macros/` in the repo so the bundle ships with each deploy and the
    history is in git. No admin gate — every authenticated user can download
    the macros (they're publishable docs, not secrets). Logs to audit_events."""
    import io
    import os
    import zipfile

    from fastapi.responses import StreamingResponse

    # __file__ = /<repo>/app/api/settings.py → repo root is three levels up.
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    macro_dir = os.path.join(repo_root, "docs", "macros")

    if not os.path.isdir(macro_dir):
        raise HTTPException(
            status_code=404,
            detail={
                "code":    "MACRO_NOT_FOUND",
                "message": "Macro bundle not deployed. Commit files under docs/macros/ to enable downloads.",
            },
        )

    # Walk the directory; reject empty (so an accidental empty dir doesn't
    # serve a 22-byte empty zip that looks healthy to the browser).
    file_paths: list[tuple[str, str]] = []
    for root, _, files in os.walk(macro_dir):
        for f in files:
            full = os.path.join(root, f)
            arc  = os.path.relpath(full, macro_dir)
            file_paths.append((full, arc))
    if not file_paths:
        raise HTTPException(
            status_code=404,
            detail={
                "code":    "MACRO_NOT_FOUND",
                "message": "Macro directory is present but empty.",
            },
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for full, arc in file_paths:
            zf.write(full, arc)
    buf.seek(0)

    # Audit trail — log who downloaded when, plus how many files were in
    # the bundle so we can see the macro source set evolve over time.
    try:
        await db.execute(
            text(
                "INSERT INTO audit_events (actor_email, kind, summary) "
                "VALUES (:a, 'settings.export.macro_download', :s)"
            ),
            {"a": getattr(user, "email", None), "s": f"files={len(file_paths)} bytes={buf.getbuffer().nbytes}"},
        )
        await db.commit()
    except Exception:  # noqa: BLE001
        pass

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="rounds-macros.zip"'},
    )


# ── /v1/settings/templates — Prompt template CRUD ───────────────────────────
# Phase 4 of the 2026-05-23 Settings BUILD remediation plan. Backs the
# Settings → Prompt templates surface (SectionPromptTemplates.vue) that
# previously rendered the @/fixtures/settings PROMPT_TEMPLATES array with
# warn-toast no-op buttons. Migration 047 creates the table + seeds 8 system
# templates so the page is non-empty on day-one without any user action.


# Valid ai_mode strings a template can be marked default for. Mirrors the
# CHECK constraint in migration 049. 'custom-prompt' is intentionally NOT
# bindable here — it comes from the upload form's free-text field, not the
# catalog.
_DEFAULT_FOR_MODE_VALUES = {"transcript", "summary", "key-moments", "structured-notes"}


class TemplateCreate(BaseModel):
    """Body for POST /v1/settings/templates."""
    kind:             str                                    # 'processing' | 'ai_prompt'
    name:             str = Field(..., min_length=1, max_length=120)
    icon:             str | None = '📝'
    description:      str | None = None
    category:         str | None = 'Custom'
    config:           dict[str, Any] = Field(default_factory=dict)
    default_for_mode: str | None = None                      # ai_prompt rows only; one default per mode


class TemplatePatch(BaseModel):
    """Body for PUT /v1/settings/templates/{id}.

    Field-absent vs explicit-null: standard fields use 'None means leave
    unchanged' semantics. default_for_mode is special — clients need a way
    to *clear* it (unbind) as well as set it, so the handler checks
    model_fields_set: present-and-null → SET NULL, absent → leave alone.
    """
    name:             str | None = None
    icon:             str | None = None
    description:      str | None = None
    category:         str | None = None
    config:           dict[str, Any] | None = None
    default_for_mode: str | None = None


def _row_to_template(r) -> dict:
    return {
        "id":               str(r["id"]),
        "kind":             r["kind"],
        "name":             r["name"],
        "icon":             r["icon"],
        "description":      r["description"],
        "category":         r["category"],
        "config":           r["config"] or {},
        "is_system":        bool(r["is_system"]),
        "default_for_mode": r["default_for_mode"],
        "version":          int(r["version"] or 1),
        "created_by":       r["created_by"],
        "created_at":       r["created_at"].isoformat() if r["created_at"] else None,
        "updated_at":       r["updated_at"].isoformat() if r["updated_at"] else None,
    }


def _validate_default_for_mode(value: str | None) -> None:
    """Raise 400 if value is set but not a known ai_mode."""
    if value is not None and value not in _DEFAULT_FOR_MODE_VALUES:
        raise HTTPException(
            status_code=400,
            detail={
                "code":    "INVALID_DEFAULT_FOR_MODE",
                "message": f"default_for_mode must be one of "
                           f"{sorted(_DEFAULT_FOR_MODE_VALUES)} or null.",
            },
        )


async def _resolve_default_mode_conflict(db, mode: str) -> dict:
    """When the partial unique index fires, look up the row currently
    holding that slot so the 409 body can name it for the operator."""
    row = (await db.execute(text(
        "SELECT id, name FROM prompt_templates "
        " WHERE default_for_mode = :m AND is_active = TRUE LIMIT 1"
    ), {"m": mode})).mappings().first()
    if row:
        return {"other_template_id": str(row["id"]), "other_template_name": row["name"]}
    return {}


@router.get("/templates")
async def list_templates(
    db: DbSession, _u: CurrentUser,
    kind: str | None = None,
) -> list[dict]:
    """List active templates. Optional ?kind=processing|ai_prompt filter."""
    where = ["is_active = TRUE"]
    params: dict[str, Any] = {}
    if kind:
        where.append("kind = :k")
        params["k"] = kind
    rows = (await db.execute(text(
        "SELECT id, kind, name, icon, description, category, config, is_system, "
        "       default_for_mode, version, created_by, created_at, updated_at "
        "FROM prompt_templates "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY is_system DESC, category, name"
    ), params)).mappings().all()
    return [_row_to_template(r) for r in rows]


@router.get("/templates/{template_id}")
async def get_template(template_id: UUID, db: DbSession, _u: CurrentUser) -> dict:
    row = (await db.execute(text(
        "SELECT id, kind, name, icon, description, category, config, is_system, "
        "       default_for_mode, version, created_by, created_at, updated_at "
        "FROM prompt_templates WHERE id = :id AND is_active = TRUE"
    ), {"id": str(template_id)})).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Template not found"})
    return _row_to_template(row)


@router.post("/templates", status_code=201)
async def create_template(
    payload: TemplateCreate, db: DbSession, user: CurrentUser,
) -> dict:
    """Create a new template. Admin-only. Returns the inserted row."""
    _require_admin(user)
    if payload.kind not in ("processing", "ai_prompt"):
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_KIND", "message": "kind must be 'processing' or 'ai_prompt'"},
        )
    _validate_default_for_mode(payload.default_for_mode)
    if payload.default_for_mode is not None and payload.kind != "ai_prompt":
        raise HTTPException(
            status_code=400,
            detail={"code": "DEFAULT_REQUIRES_AI_PROMPT",
                    "message": "Only ai_prompt templates can be marked default_for_mode."},
        )
    import json
    try:
        row = (await db.execute(text(
            "INSERT INTO prompt_templates (kind, name, icon, description, category, config, is_system, default_for_mode, created_by) "
            "VALUES (:k, :n, :ic, :d, :c, CAST(:cfg AS jsonb), FALSE, :dfm, :u) "
            "RETURNING id, kind, name, icon, description, category, config, is_system, default_for_mode, version, created_by, created_at, updated_at"
        ), {
            "k": payload.kind,
            "n": payload.name.strip(),
            "ic": payload.icon or "📝",
            "d": payload.description,
            "c": payload.category or "Custom",
            "cfg": json.dumps(payload.config or {}),
            "dfm": payload.default_for_mode,
            "u": user.email,
        })).mappings().one()
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        # Default-for-mode unique-index collision must be diagnosed BEFORE the
        # generic duplicate-name branch (both are unique_violation, but only the
        # default_for_mode index name matches here).
        if "prompt_templates_default_for_mode_uq" in msg:
            conflict = await _resolve_default_mode_conflict(db, payload.default_for_mode or "")
            raise HTTPException(
                status_code=409,
                detail={
                    "code":    "DEFAULT_MODE_TAKEN",
                    "message": f"Mode '{payload.default_for_mode}' is already the default for another template. "
                               f"Unassign it from '{conflict.get('other_template_name', '?')}' first.",
                    **conflict,
                },
            )
        if "duplicate key" in msg or "unique constraint" in msg or "unique_violation" in msg:
            raise HTTPException(
                status_code=409,
                detail={"code": "DUPLICATE_NAME", "message": f"A template named '{payload.name}' already exists."},
            )
        raise
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) "
        "VALUES (:a, 'settings.templates.add', :s)"
    ), {"a": user.email, "s": f"added template {payload.kind}:{payload.name}"
                              + (f" (default for {payload.default_for_mode})" if payload.default_for_mode else "")})
    await db.commit()
    return _row_to_template(row)


@router.put("/templates/{template_id}")
async def update_template(
    template_id: UUID, payload: TemplatePatch, db: DbSession, user: CurrentUser,
) -> dict:
    """Partial update. Admin-only. System templates can be edited (so admins
    can adjust org-wide presets) but cannot be deleted."""
    _require_admin(user)
    import json

    # Build a SET clause from non-None fields only.
    # default_for_mode uses model_fields_set to distinguish absent (leave
    # alone) from explicit-null (unbind the default).
    sets: list[str] = []
    params: dict[str, Any] = {"id": str(template_id)}
    if payload.name is not None:
        sets.append("name = :n"); params["n"] = payload.name.strip()
    if payload.icon is not None:
        sets.append("icon = :ic"); params["ic"] = payload.icon
    if payload.description is not None:
        sets.append("description = :d"); params["d"] = payload.description
    if payload.category is not None:
        sets.append("category = :c"); params["c"] = payload.category
    if payload.config is not None:
        sets.append("config = CAST(:cfg AS jsonb)"); params["cfg"] = json.dumps(payload.config)
    if "default_for_mode" in payload.model_fields_set:
        _validate_default_for_mode(payload.default_for_mode)
        sets.append("default_for_mode = :dfm"); params["dfm"] = payload.default_for_mode
    if not sets:
        raise HTTPException(status_code=400, detail={"code": "NO_CHANGES", "message": "No fields to update."})
    sets.append("version = version + 1")
    sets.append("updated_at = now()")

    try:
        row = (await db.execute(text(
            f"UPDATE prompt_templates SET {', '.join(sets)} "
            f"WHERE id = :id AND is_active = TRUE "
            f"RETURNING id, kind, name, icon, description, category, config, is_system, default_for_mode, version, created_by, created_at, updated_at"
        ), params)).mappings().first()
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        # Default-for-mode unique-index collision: diagnose BEFORE the generic
        # duplicate-name branch (both are unique_violation but the index names
        # differ — the dfm one we can specifically describe).
        if "prompt_templates_default_for_mode_uq" in msg:
            target_mode = payload.default_for_mode or ""
            conflict = await _resolve_default_mode_conflict(db, target_mode)
            raise HTTPException(
                status_code=409,
                detail={
                    "code":    "DEFAULT_MODE_TAKEN",
                    "message": f"Mode '{target_mode}' is already the default for another template. "
                               f"Unassign it from '{conflict.get('other_template_name', '?')}' first.",
                    **conflict,
                },
            )
        if "duplicate key" in msg or "unique constraint" in msg:
            raise HTTPException(
                status_code=409,
                detail={"code": "DUPLICATE_NAME", "message": "Another template already uses that name."},
            )
        raise
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Template not found"})
    # Audit summary mentions default_for_mode flips explicitly so the audit
    # trail captures SSOT-affecting changes distinctly from cosmetic edits.
    summary = f"updated template {row['name']}"
    if "default_for_mode" in payload.model_fields_set:
        if payload.default_for_mode:
            summary += f" (set default for {payload.default_for_mode})"
        else:
            summary += " (cleared default_for_mode)"
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) "
        "VALUES (:a, 'settings.templates.update', :s)"
    ), {"a": user.email, "s": summary})
    await db.commit()
    return _row_to_template(row)


@router.delete("/templates/{template_id}", status_code=204, response_class=Response)
async def remove_template(template_id: UUID, db: DbSession, user: CurrentUser):
    """Soft-delete (is_active = FALSE) so versions + audit history stay
    queryable. Refuses to delete a system template — those can only be
    duplicated. Admin-only."""
    _require_admin(user)
    row = (await db.execute(text(
        "SELECT name, is_system FROM prompt_templates WHERE id = :id AND is_active = TRUE"
    ), {"id": str(template_id)})).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Template not found"})
    if row["is_system"]:
        raise HTTPException(
            status_code=409,
            detail={"code": "SYSTEM_TEMPLATE_LOCKED",
                    "message": "System templates cannot be deleted. Duplicate it to make an editable copy."},
        )
    await db.execute(text(
        "UPDATE prompt_templates SET is_active = FALSE, updated_at = now() WHERE id = :id"
    ), {"id": str(template_id)})
    await db.execute(text(
        "INSERT INTO audit_events (actor_email, kind, summary) "
        "VALUES (:a, 'settings.templates.remove', :s)"
    ), {"a": user.email, "s": f"removed template {row['name']}"})
    await db.commit()
    return Response(status_code=204)
