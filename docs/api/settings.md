# API Reference — `settings` router (`/v1/settings`)

Org-wide settings key/value store plus People, Groups, Session Types, the per-Type stage-assignee matrix, DB-backed auth users, a macro-bundle download, and prompt-template CRUD.

- **Source file:** [`app/api/settings.py`](../../app/api/settings.py)
- **Router prefix / tag:** `prefix="/v1/settings"`, `tags=["settings"]` — [app/api/settings.py:17](../../app/api/settings.py#L17)

## Authentication & authorization model (read this first)

Every endpoint in this router depends on `CurrentUser` (sometimes bound as `_u` when the handler does not read it). `CurrentUser` is `Annotated[User, Depends(get_current_user)]` — [app/auth.py:208](../../app/auth.py#L208). `get_current_user` decodes the JWT bearer token and confirms the email is still an active user, then returns `User(email=...)`; **no role is loaded onto the `User` object** — [app/auth.py:172](../../app/auth.py#L172), [app/auth.py:37](../../app/auth.py#L37). So baseline auth = a valid JWT.

A subset of endpoints additionally call `require_admin(user)` — [app/security/roles.py:95](../../app/security/roles.py#L95). Because no caller passes a `role=` argument, `require_admin` falls through to `is_admin`'s legacy branch, which is a **case-sensitive, whitespace-sensitive exact-string compare of `user.email` against `LEGACY_ADMIN_EMAIL = "johndean@vin.com"`** — [app/security/roles.py:62](../../app/security/roles.py#L62), [app/security/roles.py:54](../../app/security/roles.py#L54). On failure it raises `403 {"code": "ADMIN_ONLY", "message": "admin only"}`.

> Note: the `role` column returned in People rows and Auth-User rows is **stored data only**. It is NOT read by `get_current_user` and does NOT grant authorization. Only the hardcoded `johndean@vin.com` email gate is live. This matches the documented "Phase 8 scaffold only — not yet wired" status in [app/security/roles.py:11](../../app/security/roles.py#L11).

Authorization legend used below:
- **JWT-only** — any authenticated user. Handler binds `_u: CurrentUser` (or `user`) but does not call `require_admin`.
- **JWT + LEGACY_ADMIN_EMAIL gate** — handler calls `require_admin(user)`; effectively only `johndean@vin.com`.

All write handlers also insert an `audit_events` row (`actor_email`, `kind`, `summary`) before commit.

---

## Pydantic models

| Model | Fields | Source |
|---|---|---|
| `SettingValue` | `key: str`, `value: Any` | [settings.py:20](../../app/api/settings.py#L20) |
| `PersonPayload` | `email: str`, `name: str`, `role: str\|None`, `avatar_color: str\|None` | [settings.py:25](../../app/api/settings.py#L25) |
| `PersonPatch` | `email`, `name`, `role`, `avatar_color` (`str\|None`), `is_active: bool\|None` — all default `None` | [settings.py:32](../../app/api/settings.py#L32) |
| `GroupPayload` | `name: str`, `description: str\|None` | [settings.py:41](../../app/api/settings.py#L41) |
| `GroupPatch` | `name: str\|None`, `description: str\|None` | [settings.py:46](../../app/api/settings.py#L46) |
| `TypePayload` | `code: str` (min 1, max 128), `label: str\|None` | [settings.py:52](../../app/api/settings.py#L52) |
| `StageAssigneeRow` | `stage: str` (1–64), `assignee_email: str` (1–255), `notify_email: bool=False` | [settings.py:57](../../app/api/settings.py#L57) |
| `StageAssigneeBulk` | `rows: list[StageAssigneeRow]` | [settings.py:63](../../app/api/settings.py#L63) |
| `AuthUserCreate` | `email: str` (3–255), `password: str` (10–256), `role: str="user"` | [settings.py:482](../../app/api/settings.py#L482) |
| `AuthUserPatch` | `role: str\|None`, `is_active: bool\|None` | [settings.py:488](../../app/api/settings.py#L488) |
| `AuthUserResetPassword` | `password: str` (10–256) | [settings.py:495](../../app/api/settings.py#L495) |
| `TemplateCreate` | `kind: str`, `name: str` (1–120), `icon: str\|None='📝'`, `description: str\|None`, `category: str\|None='Custom'`, `config: dict[str,Any]={}`, `default_for_mode: str\|None=None` | [settings.py:764](../../app/api/settings.py#L764) |
| `TemplatePatch` | `name`, `icon`, `description`, `category`, `config`, `default_for_mode` — all optional; `default_for_mode` distinguishes present-null (unbind) from absent via `model_fields_set` | [settings.py:775](../../app/api/settings.py#L775) |

`auth_user` response projection (`_row_to_auth_user`, [settings.py:499](../../app/api/settings.py#L499)) NEVER returns `password_hash`. `template` response projection is `_row_to_template`, [settings.py:791](../../app/api/settings.py#L791).

---

## Endpoints

### 1. `GET /v1/settings` — list all org settings
- **Decorator:** [settings.py:67](../../app/api/settings.py#L67) — `@router.get("", response_model=dict[str, Any])`
- **Purpose:** Return every row in `org_settings` as a flat `{key: value}` map.
- **Authentication:** JWT-only (`_u: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** none.
- **Response Schema:** `dict[str, Any]` — `{ "<key>": <json value>, ... }`.
- **Validation Rules:** none.
- **Errors:** 401 if no/invalid JWT.
- **Example:** `GET /v1/settings` → `{"theme":"dark","retention_days":90}`
- **Related Screens:** Settings view (org-level config).
- **Related Tables:** `org_settings`.

### 2. `PUT /v1/settings/{key}` — upsert one setting
- **Decorator:** [settings.py:73](../../app/api/settings.py#L73) — `@router.put("/{key}", response_model=SettingValue)`
- **Purpose:** Insert-or-update one `org_settings` row (value stored as `jsonb`), recording `updated_by`.
- **Authentication:** JWT-only (`user: CurrentUser`).
- **Authorization:** JWT-only (no `require_admin`).
- **Request Schema:** `SettingValue` `{ "key": str, "value": Any }`.
- **Response Schema:** `SettingValue` (echoes the submitted payload).
- **Validation Rules:** `payload.key` must equal the path `{key}` — else **400 "Key mismatch"** ([settings.py:76](../../app/api/settings.py#L76)).
- **Errors:** 400 Key mismatch; 401.
- **Example:** `PUT /v1/settings/theme` body `{"key":"theme","value":"dark"}`.
- **Related Screens:** Settings.
- **Related Tables:** `org_settings`, `audit_events` (`kind='settings.set'`).

### 3. `GET /v1/settings/people` — list people
- **Decorator:** [settings.py:92](../../app/api/settings.py#L92) — `@router.get("/people")`
- **Purpose:** List all people ordered by name.
- **Authentication / Authorization:** JWT-only (`_u`).
- **Request Schema:** none.
- **Response Schema:** `list[dict]` of `{id, email, name, role, avatar_color, is_active}`.
- **Validation Rules:** none.
- **Errors:** 401.
- **Related Screens:** Settings → Team.
- **Related Tables:** `people`.

### 4. `POST /v1/settings/people` — add/upsert a person
- **Decorator:** [settings.py:100](../../app/api/settings.py#L100) — `@router.post("/people", status_code=201)`
- **Purpose:** Insert a person; on email conflict, update name/role/avatar_color and re-activate (`is_active = TRUE`). Email is lowercased.
- **Authentication / Authorization:** JWT-only (`user`).
- **Request Schema:** `PersonPayload`.
- **Response Schema:** `dict` `{id, email, name, role, avatar_color, is_active}`.
- **Validation Rules:** `ON CONFLICT (email)` upsert.
- **Errors:** 401.
- **Example:** `POST /v1/settings/people` body `{"email":"vet@vin.com","name":"Dr Vet"}` → 201.
- **Related Screens:** Settings → Team.
- **Related Tables:** `people`, `audit_events` (`kind='settings.people.add'`).

### 5. `DELETE /v1/settings/people/{person_id}` — deactivate person
- **Decorator:** [settings.py:114](../../app/api/settings.py#L114) — `@router.delete("/people/{person_id}", status_code=204, response_class=Response)`
- **Purpose:** Soft-delete — sets `is_active = FALSE` (no hard delete).
- **Authentication / Authorization:** JWT-only (`user`).
- **Request Schema:** path `person_id: UUID`.
- **Response Schema:** 204 No Content (empty `Response`).
- **Validation Rules:** none (no rowcount check — a non-existent id still returns 204).
- **Errors:** 401; 422 if `person_id` is not a valid UUID.
- **Related Screens:** Settings → Team.
- **Related Tables:** `people`, `audit_events` (`kind='settings.people.remove'`).

### 6. `PUT /v1/settings/people/{person_id}` — partial update person
- **Decorator:** [settings.py:124](../../app/api/settings.py#L124) — `@router.put("/people/{person_id}")`
- **Purpose:** Partial update of whitelisted fields (`email, name, role, avatar_color, is_active`). Only fields present in the body (`exclude_unset`) are written. Email lowercased.
- **Authentication / Authorization:** JWT-only (`user`).
- **Request Schema:** `PersonPatch`.
- **Response Schema:** `dict` `{id, email, name, role, avatar_color, is_active}`.
- **Validation Rules:** empty body → **400 "No updatable fields provided"** ([settings.py:132](../../app/api/settings.py#L132)).
- **Errors:** 400 (no fields); **409 `{"code":"DUPLICATE_EMAIL"}`** on `people_email_key` collision ([settings.py:148](../../app/api/settings.py#L148)); **404 "Person not found"** ([settings.py:155](../../app/api/settings.py#L155)); 500 on other DB errors; 401.
- **Related Screens:** Settings → Team.
- **Related Tables:** `people`, `audit_events` (`kind='settings.people.update'`).

### 7. `GET /v1/settings/groups` — list groups
- **Decorator:** [settings.py:163](../../app/api/settings.py#L163) — `@router.get("/groups")`
- **Purpose:** List all groups ordered by name.
- **Authentication / Authorization:** JWT-only (`_u`).
- **Response Schema:** `list[dict]` of `{id, name, description}`.
- **Errors:** 401.
- **Related Screens:** Settings → Team (Groups).
- **Related Tables:** `groups`.

### 8. `POST /v1/settings/groups` — add/upsert group
- **Decorator:** [settings.py:169](../../app/api/settings.py#L169) — `@router.post("/groups", status_code=201)`
- **Purpose:** Insert a group; on name conflict, update description.
- **Authentication / Authorization:** JWT-only (`user`).
- **Request Schema:** `GroupPayload`.
- **Response Schema:** `dict` `{id, name, description}`.
- **Validation Rules:** `ON CONFLICT (name)` upsert.
- **Errors:** 401.
- **Related Screens:** Settings → Team (Groups).
- **Related Tables:** `groups`, `audit_events` (`kind='settings.groups.add'`).

### 9. `PUT /v1/settings/groups/{group_id}` — partial update group
- **Decorator:** [settings.py:183](../../app/api/settings.py#L183) — `@router.put("/groups/{group_id}")`
- **Purpose:** Partial update of `name` / `description`.
- **Authentication / Authorization:** JWT-only (`user`).
- **Request Schema:** `GroupPatch`.
- **Response Schema:** `dict` `{id, name, description}`.
- **Validation Rules:** empty body → **400 "No updatable fields provided"** ([settings.py:187](../../app/api/settings.py#L187)).
- **Errors:** 400; **409 `{"code":"DUPLICATE_NAME"}`** on `groups_name_key` collision ([settings.py:199](../../app/api/settings.py#L199)); **404 "Group not found"** ([settings.py:204](../../app/api/settings.py#L204)); 500 on other DB errors; 401.
- **Related Screens:** Settings → Team (Groups).
- **Related Tables:** `groups`, `audit_events` (`kind='settings.groups.update'`).

### 10. `DELETE /v1/settings/groups/{group_id}` — hard-delete group
- **Decorator:** [settings.py:213](../../app/api/settings.py#L213) — `@router.delete("/groups/{group_id}", status_code=204, response_class=Response)`
- **Purpose:** Hard-delete a group; `group_members` rows cascade. Stage-assignee `"Group: X"` TEXT strings are NOT affected (not FKs).
- **Authentication / Authorization:** JWT-only (`user`).
- **Request Schema:** path `group_id: UUID`.
- **Response Schema:** 204 No Content.
- **Validation Rules:** `rowcount == 0` → **404 "Group not found"** ([settings.py:222](../../app/api/settings.py#L222)).
- **Errors:** 404; 401; 422 (bad UUID).
- **Related Screens:** Settings → Team (Groups).
- **Related Tables:** `groups`, `group_members` (cascade), `audit_events` (`kind='settings.groups.remove'`).

### 11. `GET /v1/settings/groups/{group_id}/members` — list members of one group
- **Decorator:** [settings.py:231](../../app/api/settings.py#L231) — `@router.get("/groups/{group_id}/members")`
- **Purpose:** Members of a group joined to `people`, active only, ordered by name.
- **Authentication / Authorization:** JWT-only (`_u`).
- **Response Schema:** `list[dict]` of `{id, email, name, role, avatar_color, is_active}`.
- **Errors:** 401.
- **Related Screens:** Settings → Team (Groups → members).
- **Related Tables:** `group_members`, `people`.

### 12. `GET /v1/settings/groups-members` — bulk all group memberships
- **Decorator:** [settings.py:243](../../app/api/settings.py#L243) — `@router.get("/groups-members")`
- **Purpose:** Single fan-out replacing N per-group calls. Returns `{ group_id: [person, ...] }`; groups with zero active members are omitted.
- **Authentication / Authorization:** JWT-only (`_u`).
- **Response Schema:** `dict[str, list[dict]]`; each person is `{id, email, name, role, avatar_color, is_active}`.
- **Errors:** 401.
- **Related Screens:** Settings → Team (`SectionTeam` hydrate).
- **Related Tables:** `group_members`, `people`.

### 13. `POST /v1/settings/groups/{group_id}/members/{person_id}` — add member
- **Decorator:** [settings.py:268](../../app/api/settings.py#L268) — `@router.post("/groups/{group_id}/members/{person_id}", status_code=201)`
- **Purpose:** Add a person to a group. Idempotent via `ON CONFLICT (group_id, person_id) DO NOTHING`.
- **Authentication / Authorization:** JWT-only (`user`).
- **Request Schema:** path `group_id: UUID`, `person_id: UUID`.
- **Response Schema:** `dict` `{group_id, person_id, added: true}`.
- **Validation Rules:** none beyond UUID coercion.
- **Errors:** **404 "Group or person not found"** if a FK violation is detected in the exception message ([settings.py:281](../../app/api/settings.py#L281)); 500 on other DB errors; 401; 422 (bad UUID).
- **Related Screens:** Settings → Team (Groups → members).
- **Related Tables:** `group_members`, `audit_events` (`kind='settings.groups.member_add'`).

### 14. `DELETE /v1/settings/groups/{group_id}/members/{person_id}` — remove member
- **Decorator:** [settings.py:290](../../app/api/settings.py#L290) — `@router.delete(..., status_code=204, response_class=Response)`
- **Purpose:** Remove a person from a group.
- **Authentication / Authorization:** JWT-only (`user`).
- **Response Schema:** 204 No Content.
- **Validation Rules:** `rowcount == 0` → **404 "Membership not found"** ([settings.py:298](../../app/api/settings.py#L298)).
- **Errors:** 404; 401; 422.
- **Related Screens:** Settings → Team (Groups → members).
- **Related Tables:** `group_members`, `audit_events` (`kind='settings.groups.member_remove'`).

### 15. `GET /v1/settings/types` — list session types
- **Decorator:** [settings.py:308](../../app/api/settings.py#L308) — `@router.get("/types")`
- **Purpose:** List session types, default row first then alphabetical by label. Surfaces `is_default`.
- **Authentication / Authorization:** JWT-only (`_u`).
- **Response Schema:** `list[dict]` of `{id, code, label, is_default}`.
- **Errors:** 401.
- **Related Screens:** Settings → Types.
- **Related Tables:** `session_types`.

### 16. `POST /v1/settings/types` — add/upsert session type
- **Decorator:** [settings.py:320](../../app/api/settings.py#L320) — `@router.post("/types", status_code=201)`
- **Purpose:** Insert a type; on code conflict, update label (defaults label to code).
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** — `require_admin(user)` at [settings.py:322](../../app/api/settings.py#L322).
- **Request Schema:** `TypePayload` (`code` required 1–128, `label` optional).
- **Response Schema:** `dict` `{id, code, label, is_default}`.
- **Validation Rules:** `ON CONFLICT (code)` upsert.
- **Errors:** 403 `ADMIN_ONLY` if not the admin email; 401; 422 (code length).
- **Related Screens:** Settings → Types.
- **Related Tables:** `session_types`, `audit_events` (`kind='settings.types.add'`).

### 17. `DELETE /v1/settings/types/{type_id}` — delete session type
- **Decorator:** [settings.py:335](../../app/api/settings.py#L335) — `@router.delete("/types/{type_id}", status_code=204, response_class=Response)`
- **Purpose:** Hard-delete a type; `stage_assignees` + `email_templates` cascade. Refuses the org default.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([settings.py:337](../../app/api/settings.py#L337)).
- **Response Schema:** 204 No Content.
- **Validation Rules:** if the row's `is_default` is `True` → **409 `{"code":"DEFAULT_TYPE_LOCKED"}`** ([settings.py:344](../../app/api/settings.py#L344)).
- **Errors:** 403 `ADMIN_ONLY`; 409 `DEFAULT_TYPE_LOCKED`; 401; 422.
- **Related Screens:** Settings → Types.
- **Related Tables:** `session_types`, `stage_assignees` + `email_templates` (cascade), `audit_events` (`kind='settings.types.remove'`).

### 18. `GET /v1/settings/types/{type_id}/assignees` — per-type stage matrix
- **Decorator:** [settings.py:408](../../app/api/settings.py#L408) — `@router.get("/types/{type_id}/assignees")`
- **Purpose:** Per-Type stage-assignee matrix, joined to `people`/`groups` for display (`assignee_email`, `assignee_label`, `person_id`, `group_id`). Renames propagate via the JOIN.
- **Authentication / Authorization:** JWT-only (`_u`).
- **Response Schema:** `list[dict]` of `{id, stage, notify_email, assignee_email, assignee_label, person_id, group_id}` (the `_TYPE_ASSIGNEES_SELECT` projection, [settings.py:387](../../app/api/settings.py#L387)).
- **Errors:** 401; 422.
- **Related Screens:** Settings → Types (stage-assignee matrix).
- **Related Tables:** `stage_assignees`, `people`, `groups`.

### 19. `PUT /v1/settings/types/{type_id}/assignees` — bulk replace stage matrix
- **Decorator:** [settings.py:420](../../app/api/settings.py#L420) — `@router.put("/types/{type_id}/assignees")`
- **Purpose:** Delete all `stage_assignees` rows for the type and re-insert from the payload, resolving `assignee_email` into typed `person_id`/`group_id` FKs via `_resolve_assignee` ([settings.py:358](../../app/api/settings.py#L358)). `"(unassigned)"` / empty rows are skipped.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([settings.py:431](../../app/api/settings.py#L431)).
- **Request Schema:** `StageAssigneeBulk` `{ "rows": [ {stage, assignee_email, notify_email}, ... ] }`.
- **Response Schema:** the re-read matrix (`list[dict]`, same shape as endpoint 18).
- **Validation Rules:** type must exist → else **404 "type not found"** ([settings.py:435](../../app/api/settings.py#L435)). Resolution: `"Group: <name>"` → group FK; bare email → person FK (case-insensitive); unmatched → email kept for back-compat.
- **Errors:** 403 `ADMIN_ONLY`; 404 (type not found); 401; 422 (row field lengths).
- **Related Screens:** Settings → Types (stage-assignee matrix save).
- **Related Tables:** `stage_assignees`, `session_types`, `people`, `groups`, `audit_events` (`kind='settings.types.assignees'`).

### 20. `GET /v1/settings/auth-users` — list login accounts
- **Decorator:** [settings.py:529](../../app/api/settings.py#L529) — `@router.get("/auth-users")`
- **Purpose:** List all `auth_users` (no `password_hash`), ordered by email.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([settings.py:531](../../app/api/settings.py#L531)).
- **Response Schema:** `list[dict]` via `_row_to_auth_user` → `{id, email, role, is_active, last_login_at, password_reset_at, created_at, updated_at}`.
- **Errors:** 403 `ADMIN_ONLY`; 401.
- **Related Screens:** Settings → Auth & Logins.
- **Related Tables:** `auth_users`.

### 21. `POST /v1/settings/auth-users` — create login account
- **Decorator:** [settings.py:536](../../app/api/settings.py#L536) — `@router.post("/auth-users", status_code=201)`
- **Purpose:** Create a login. Password is bcrypt-hashed via `app.services.auth_users.hash_password`; email lowercased+trimmed.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([settings.py:538](../../app/api/settings.py#L538)).
- **Request Schema:** `AuthUserCreate` (`email` 3–255, `password` 10–256, `role` default `"user"`).
- **Response Schema:** `dict` (`_row_to_auth_user`, no hash).
- **Validation Rules:** `role` must be `"admin"` or `"user"` → else **400 `{"code":"BAD_ROLE"}`** ([settings.py:539](../../app/api/settings.py#L539)).
- **Errors:** 400 `BAD_ROLE`; **409 `{"code":"DUPLICATE_EMAIL"}`** on `auth_users_email_lower_uq` ([settings.py:554](../../app/api/settings.py#L554)); 500 other DB; 403; 401; 422 (password length).
- **Example:** body `{"email":"new@vin.com","password":"a-strong-pw-10","role":"user"}` → 201.
- **Related Screens:** Settings → Auth & Logins.
- **Related Tables:** `auth_users`, `audit_events` (`kind='settings.auth_user.add'`).

### 22. `PUT /v1/settings/auth-users/{user_id}` — update role/activation
- **Decorator:** [settings.py:569](../../app/api/settings.py#L569) — `@router.put("/auth-users/{user_id}")`
- **Purpose:** Partial update of `role` and/or `is_active`. Password changes are NOT allowed here (dedicated reset endpoint only).
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([settings.py:571](../../app/api/settings.py#L571)).
- **Request Schema:** `AuthUserPatch` (`role: str|None`, `is_active: bool|None`).
- **Response Schema:** `dict` (`_row_to_auth_user`).
- **Validation Rules:** empty body → **400 "No updatable fields provided"** ([settings.py:575](../../app/api/settings.py#L575)); `role` (if set) must be `admin`/`user` → **400 `BAD_ROLE`** ([settings.py:577](../../app/api/settings.py#L577)); **last-admin guard** — refusing to demote or disable the only active admin → **409 `{"code":"LAST_ADMIN_PROTECTED"}`** ([settings.py:584](../../app/api/settings.py#L584)).
- **Errors:** 400 (no fields / BAD_ROLE); 409 `LAST_ADMIN_PROTECTED`; **404 "user not found"** ([settings.py:603](../../app/api/settings.py#L603)); 403; 401; 422.
- **Related Screens:** Settings → Auth & Logins.
- **Related Tables:** `auth_users`, `audit_events` (`kind='settings.auth_user.update'`).

### 23. `POST /v1/settings/auth-users/{user_id}/reset-password` — reset password
- **Decorator:** [settings.py:613](../../app/api/settings.py#L613) — `@router.post("/auth-users/{user_id}/reset-password")`
- **Purpose:** Set a new bcrypt-hashed password and stamp `password_reset_at`.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([settings.py:617](../../app/api/settings.py#L617)).
- **Request Schema:** `AuthUserResetPassword` (`password` 10–256).
- **Response Schema:** `dict` `{email, password_reset_at}` (ISO timestamp from `datetime_now_iso`).
- **Validation Rules:** target user must exist → **404 "user not found"** (via `_get_auth_user_or_404`, [settings.py:519](../../app/api/settings.py#L519)).
- **Errors:** 404; 403; 401; 422 (password length).
- **Related Screens:** Settings → Auth & Logins (reset password).
- **Related Tables:** `auth_users`, `audit_events` (`kind='settings.auth_user.reset_password'`).

### 24. `DELETE /v1/settings/auth-users/{user_id}` — delete login account
- **Decorator:** [settings.py:645](../../app/api/settings.py#L645) — `@router.delete("/auth-users/{user_id}", status_code=204, response_class=Response)`
- **Purpose:** Hard-delete a login account.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([settings.py:647](../../app/api/settings.py#L647)).
- **Response Schema:** 204 No Content.
- **Validation Rules:** target must exist → **404 "user not found"**; **last-admin guard** — deleting the only active admin → **409 `{"code":"LAST_ADMIN_PROTECTED"}`** ([settings.py:651](../../app/api/settings.py#L651)).
- **Errors:** 404; 409 `LAST_ADMIN_PROTECTED`; 403; 401; 422.
- **Related Screens:** Settings → Auth & Logins.
- **Related Tables:** `auth_users`, `audit_events` (`kind='settings.auth_user.delete'`).

### 25. `GET /v1/settings/export/macro` — download macro bundle (zip)
- **Decorator:** [settings.py:680](../../app/api/settings.py#L680) — `@router.get("/export/macro")`
- **Purpose:** Stream a zip generated on the fly from `docs/macros/` in the repo.
- **Authentication / Authorization:** JWT-only (`user`) — comment explicitly states "No admin gate" ([settings.py:684](../../app/api/settings.py#L684)).
- **Response Schema:** `StreamingResponse` `application/zip`, `Content-Disposition: attachment; filename="rounds-macros.zip"`.
- **Validation Rules:** macro dir absent → **404 `{"code":"MACRO_NOT_FOUND"}`** ([settings.py:696](../../app/api/settings.py#L696)); present but empty → **404 `{"code":"MACRO_NOT_FOUND"}`** ([settings.py:713](../../app/api/settings.py#L713)).
- **Errors:** 404 `MACRO_NOT_FOUND`; 401. (Audit insert is best-effort, wrapped in try/except.)
- **Related Screens:** Settings → Export / Macro download.
- **Related Tables:** `audit_events` (`kind='settings.export.macro_download'`, best-effort). Source files live in the repo `docs/macros/` directory, not a DB table.

### 26. `GET /v1/settings/templates` — list prompt templates
- **Decorator:** [settings.py:834](../../app/api/settings.py#L834) — `@router.get("/templates")`
- **Purpose:** List active prompt templates; optional `?kind=processing|ai_prompt` filter. Ordered system-first, then category, name.
- **Authentication / Authorization:** JWT-only (`_u`).
- **Request Schema:** query `kind: str | None`.
- **Response Schema:** `list[dict]` via `_row_to_template` → `{id, kind, name, icon, description, category, config, is_system, default_for_mode, version, created_by, created_at, updated_at}`.
- **Errors:** 401.
- **Related Screens:** Settings → Prompt templates (`SectionPromptTemplates.vue`).
- **Related Tables:** `prompt_templates`.

### 27. `GET /v1/settings/templates/{template_id}` — get one template
- **Decorator:** [settings.py:855](../../app/api/settings.py#L855) — `@router.get("/templates/{template_id}")`
- **Purpose:** Fetch one active template.
- **Authentication / Authorization:** JWT-only (`_u`).
- **Response Schema:** `dict` (`_row_to_template`).
- **Validation Rules:** missing/inactive → **404 `{"code":"NOT_FOUND"}`** ([settings.py:863](../../app/api/settings.py#L863)).
- **Errors:** 404; 401; 422.
- **Related Screens:** Settings → Prompt templates.
- **Related Tables:** `prompt_templates`.

### 28. `POST /v1/settings/templates` — create template
- **Decorator:** [settings.py:867](../../app/api/settings.py#L867) — `@router.post("/templates", status_code=201)`
- **Purpose:** Create a non-system template (`is_system = FALSE`).
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([settings.py:872](../../app/api/settings.py#L872)).
- **Request Schema:** `TemplateCreate`.
- **Response Schema:** `dict` (`_row_to_template`).
- **Validation Rules:** `kind` must be `processing`/`ai_prompt` → **400 `{"code":"INVALID_KIND"}`** ([settings.py:873](../../app/api/settings.py#L873)); `default_for_mode` (if set) must be one of `transcript, summary, key-moments, structured-notes` → **400 `{"code":"INVALID_DEFAULT_FOR_MODE"}`** (`_validate_default_for_mode`, [settings.py:809](../../app/api/settings.py#L809)); `default_for_mode` only allowed when `kind == 'ai_prompt'` → **400 `{"code":"DEFAULT_REQUIRES_AI_PROMPT"}`** ([settings.py:879](../../app/api/settings.py#L879)).
- **Errors:** 400 (INVALID_KIND / INVALID_DEFAULT_FOR_MODE / DEFAULT_REQUIRES_AI_PROMPT); **409 `{"code":"DEFAULT_MODE_TAKEN"}`** on `prompt_templates_default_for_mode_uq` ([settings.py:906](../../app/api/settings.py#L906)); **409 `{"code":"DUPLICATE_NAME"}`** on other unique violation ([settings.py:917](../../app/api/settings.py#L917)); 403; 401; 422.
- **Related Screens:** Settings → Prompt templates.
- **Related Tables:** `prompt_templates`, `audit_events` (`kind='settings.templates.add'`).

### 29. `PUT /v1/settings/templates/{template_id}` — update template
- **Decorator:** [settings.py:932](../../app/api/settings.py#L932) — `@router.put("/templates/{template_id}")`
- **Purpose:** Partial update (system templates may be edited but not deleted). Increments `version`. `default_for_mode` uses `model_fields_set` so present-null clears the binding.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([settings.py:938](../../app/api/settings.py#L938)).
- **Request Schema:** `TemplatePatch`.
- **Response Schema:** `dict` (`_row_to_template`).
- **Validation Rules:** no fields set → **400 `{"code":"NO_CHANGES"}`** ([settings.py:960](../../app/api/settings.py#L960)); `default_for_mode` validated by `_validate_default_for_mode` → 400 `INVALID_DEFAULT_FOR_MODE`.
- **Errors:** 400 (NO_CHANGES / INVALID_DEFAULT_FOR_MODE); **409 `DEFAULT_MODE_TAKEN`** ([settings.py:975](../../app/api/settings.py#L975)); **409 `DUPLICATE_NAME`** ([settings.py:987](../../app/api/settings.py#L987)); **404 `{"code":"NOT_FOUND"}`** ([settings.py:994](../../app/api/settings.py#L994)); 403; 401; 422.
- **Related Screens:** Settings → Prompt templates.
- **Related Tables:** `prompt_templates`, `audit_events` (`kind='settings.templates.update'`).

### 30. `DELETE /v1/settings/templates/{template_id}` — soft-delete template
- **Decorator:** [settings.py:1011](../../app/api/settings.py#L1011) — `@router.delete("/templates/{template_id}", status_code=204, response_class=Response)`
- **Purpose:** Soft-delete (`is_active = FALSE`) so versions + audit history stay queryable. System templates cannot be deleted.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([settings.py:1016](../../app/api/settings.py#L1016)).
- **Response Schema:** 204 No Content.
- **Validation Rules:** missing/inactive → **404 `{"code":"NOT_FOUND"}`** ([settings.py:1021](../../app/api/settings.py#L1021)); `is_system` row → **409 `{"code":"SYSTEM_TEMPLATE_LOCKED"}`** ([settings.py:1022](../../app/api/settings.py#L1022)).
- **Errors:** 404; 409 `SYSTEM_TEMPLATE_LOCKED`; 403; 401; 422.
- **Related Screens:** Settings → Prompt templates.
- **Related Tables:** `prompt_templates`, `audit_events` (`kind='settings.templates.remove'`).

---

## Notes / discrepancies
- The `role` value stored on People rows and Auth-User rows is descriptive metadata; authorization is NOT derived from it (see auth model above). PARTIALLY IMPLEMENTED: a self-aware last-admin guard counts `role='admin'` rows in `auth_users` ([settings.py:513](../../app/api/settings.py#L513)) to protect that data set, but that role is still not what `get_current_user` checks for request authorization.
- A module comment at [settings.py:464](../../app/api/settings.py#L464) notes email-template CRUD moved out to the `/v1/email-templates` router — see [email-templates.md](./email-templates.md).

## Source Verification
- **Files Used:** `app/api/settings.py`, `app/security/roles.py`, `app/auth.py`
- **Components Used:** none (backend router; related Vue screens named from in-code comments — `SectionTeam`, `SectionPromptTemplates.vue`, `SettingsTypes.vue` — not opened/verified here)
- **APIs Used:** none (this IS the API surface)
- **Database Tables Used:** `org_settings`, `people`, `groups`, `group_members`, `session_types`, `stage_assignees`, `auth_users`, `prompt_templates`, `email_templates` (cascade target), `audit_events`
- **Permission Logic Used:** JWT presence (`CurrentUser` → `get_current_user`) on all routes; `require_admin(user)` → `LEGACY_ADMIN_EMAIL` exact-match gate on `POST/DELETE /types`, `PUT /types/{id}/assignees`, all `/auth-users*`, and `POST/PUT/DELETE /templates`. `GET /export/macro` is explicitly JWT-only by code comment.
- **Confidence Score:** High — every endpoint, decorator line, model, error code, and gate read directly from source.
- **Evidence Links:** [settings.py:17](../../app/api/settings.py#L17) (router), [settings.py:322](../../app/api/settings.py#L322) (require_admin example), [roles.py:54](../../app/security/roles.py#L54) (LEGACY_ADMIN_EMAIL), [auth.py:172](../../app/auth.py#L172) (get_current_user — no role loaded)
