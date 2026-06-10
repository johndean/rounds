# API Reference — `email_templates` router (`/v1/email-templates`)

Stage-notification email template CRUD plus a resolver that picks the template that would actually fire for a given `(session_type_id, stage_id, locale)`.

- **Source file:** [`app/api/email_templates.py`](../../app/api/email_templates.py)
- **Router prefix / tag:** `prefix="/v1/email-templates"`, `tags=["email-templates"]` — [app/api/email_templates.py:35](../../app/api/email_templates.py#L35)

## Two-scope model

- `session_type_id = NULL` → default-for-all-types template (one per stage).
- `session_type_id = <uuid>` → per-Type override for a specific stage.
- **Resolution rule** ([email_templates.py:12](../../app/api/email_templates.py#L12)): for `(session_type_id, stage_id, locale)` return the per-type row if present, else the default row, else 404.

## Authentication & authorization model (read this first)

Every HTTP endpoint depends on `CurrentUser` = `Annotated[User, Depends(get_current_user)]` ([app/auth.py:208](../../app/auth.py#L208)). `get_current_user` validates the JWT bearer token and confirms the email is an active user; it does NOT load a role onto the `User` object ([app/auth.py:172](../../app/auth.py#L172), [app/auth.py:37](../../app/auth.py#L37)). Baseline auth = a valid JWT.

Mutating endpoints call `require_admin(user)` ([app/security/roles.py:95](../../app/security/roles.py#L95)). With no `role=` argument, this resolves to `is_admin`'s legacy branch: a **case-sensitive exact-string compare of `user.email` against `LEGACY_ADMIN_EMAIL = "johndean@vin.com"`** ([app/security/roles.py:62](../../app/security/roles.py#L62), [app/security/roles.py:54](../../app/security/roles.py#L54)). Failure → `403 {"code":"ADMIN_ONLY","message":"admin only"}`.

Authorization legend:
- **JWT-only** — any authenticated user; handler binds `_u: CurrentUser` and does not gate.
- **JWT + LEGACY_ADMIN_EMAIL gate** — handler calls `require_admin(user)`; effectively only `johndean@vin.com`.

Mutating endpoints also insert an `audit_events` row before commit.

---

## Pydantic models

| Model | Fields | Source |
|---|---|---|
| `EmailTemplateCreate` | `session_type_id: UUID\|None` (NULL = all types), `stage_id: str` (min 1), `locale: str` (default "en-US", 2–10), `subject: str` (1–300), `body: str` (1–200000) | [email_templates.py:128](../../app/api/email_templates.py#L128) |
| `EmailTemplatePatch` | `subject: str\|None` (≤300), `body: str\|None` (≤200000), `locale: str\|None` (2–10) — all default None | [email_templates.py:137](../../app/api/email_templates.py#L137) |
| `ResolveRequest` | `session_type_id: UUID\|None`, `stage_id: str` (min 1), `locale: str` (default "en-US") | [email_templates.py:144](../../app/api/email_templates.py#L144) |

Response serializer `_row_to_template` ([email_templates.py:151](../../app/api/email_templates.py#L151)) → `{id, session_type_id, stage_id, locale, subject, body, created_by, created_at, updated_at}`. The resolve endpoints add a `resolved_from` discriminator (`"per_type"` or `"default"`).

### Valid stages (`_VALID_STAGES`, [email_templates.py:118](../../app/api/email_templates.py#L118))
Stage-transition (migration 048): `prep, copy_draft, medical, copy_final, cms, captions, qa, complete`.
Deadline-overdue (migration 051): `prep_overdue, copy_draft_overdue, medical_overdue, copy_final_overdue, cms_overdue, captions_overdue, qa_overdue`.
(`complete` is terminal and has no `_overdue` variant.) This allowlist is enforced on `POST`, and `POST /resolve`.

---

## Endpoints

### 1. `GET /v1/email-templates` — list templates
- **Decorator:** [email_templates.py:165](../../app/api/email_templates.py#L165) — `@router.get("")`
- **Purpose:** List active templates with optional filters; interleaves per-type and default rows when a type is given and defaults are requested. Ordered `session_type_id NULLS FIRST, stage_id, locale`.
- **Authentication / Authorization:** JWT-only (`_u`).
- **Request Schema:** query `session_type_id: UUID|None`, `stage_id: str|None`, `include_defaults: bool` (default `True`).
- **Response Schema:** `list[dict]` (`_row_to_template`).
- **Validation Rules:** filter logic ([email_templates.py:181](../../app/api/email_templates.py#L181)):
  - `session_type_id` set + `include_defaults=True` → rows where `session_type_id = :tid OR session_type_id IS NULL`.
  - `session_type_id` set + `include_defaults=False` → only `session_type_id = :tid`.
  - no `session_type_id` + `include_defaults=False` → only `session_type_id IS NOT NULL`.
  - `stage_id` adds `stage_id = :sid`.
  - always `is_active = TRUE`.
- **Errors:** 401; 422 (bad UUID query).
- **Related Screens:** Settings → Email templates (`EmailBuilder.vue`).
- **Related Tables:** `email_templates`.

### 2. `GET /v1/email-templates/{template_id}` — get one template
- **Decorator:** [email_templates.py:205](../../app/api/email_templates.py#L205) — `@router.get("/{template_id}")`
- **Purpose:** Fetch one active template by id.
- **Authentication / Authorization:** JWT-only (`_u`).
- **Request Schema:** path `template_id: UUID`.
- **Response Schema:** `dict` (`_row_to_template`).
- **Validation Rules:** missing/inactive → **404 `{"code":"NOT_FOUND"}`** ([email_templates.py:213](../../app/api/email_templates.py#L213)).
- **Errors:** 404; 401; 422 (bad UUID).
- **Related Screens:** Settings → Email templates (open one).
- **Related Tables:** `email_templates`.

### 3. `POST /v1/email-templates` — create template
- **Decorator:** [email_templates.py:217](../../app/api/email_templates.py#L217) — `@router.post("", status_code=201)`
- **Purpose:** Create a per-Type or default-Type template for a stage.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([email_templates.py:223](../../app/api/email_templates.py#L223)).
- **Request Schema:** `EmailTemplateCreate`.
- **Response Schema:** `dict` (`_row_to_template`), 201.
- **Validation Rules:** `stage_id` must be in `_VALID_STAGES` → else **400 `{"code":"INVALID_STAGE"}`** ([email_templates.py:224](../../app/api/email_templates.py#L224)); `subject`/`body` length bounds enforced by Pydantic.
- **Errors:** 400 `INVALID_STAGE`; **409 `{"code":"DUPLICATE_TEMPLATE"}`** on a unique-constraint collision for `(type, stage, locale)` ([email_templates.py:246](../../app/api/email_templates.py#L246)); 403; 401; 422.
- **Example:** body `{"stage_id":"medical","subject":"Ready for medical review","body":"<p>{{ session_title }}</p>"}` → 201 (default-type row, `session_type_id` omitted → NULL).
- **Related Screens:** Settings → Email templates (new).
- **Related Tables:** `email_templates`, `audit_events` (`kind='settings.email_templates.add'`).

### 4. `PUT /v1/email-templates/{template_id}` — partial update
- **Decorator:** [email_templates.py:261](../../app/api/email_templates.py#L261) — `@router.put("/{template_id}")`
- **Purpose:** Partial update of `subject` / `body` / `locale` on an active row; stamps `updated_at`.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([email_templates.py:266](../../app/api/email_templates.py#L266)).
- **Request Schema:** `EmailTemplatePatch`.
- **Response Schema:** `dict` (`_row_to_template`).
- **Validation Rules:** no fields supplied → **400 `{"code":"NO_CHANGES"}`** ([email_templates.py:272](../../app/api/email_templates.py#L272)). Note: `stage_id` and `session_type_id` are NOT editable here.
- **Errors:** 400 `NO_CHANGES`; missing/inactive row → **404 `{"code":"NOT_FOUND"}`** ([email_templates.py:286](../../app/api/email_templates.py#L286)); 403; 401; 422.
- **Related Screens:** Settings → Email templates (edit).
- **Related Tables:** `email_templates`, `audit_events` (`kind='settings.email_templates.update'`).

### 5. `DELETE /v1/email-templates/{template_id}` — soft-delete
- **Decorator:** [email_templates.py:295](../../app/api/email_templates.py#L295) — `@router.delete("/{template_id}", status_code=204, response_class=Response)`
- **Purpose:** Soft-delete (`is_active = FALSE`).
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([email_templates.py:298](../../app/api/email_templates.py#L298)).
- **Request Schema:** path `template_id: UUID`.
- **Response Schema:** 204 No Content.
- **Validation Rules:** missing/inactive row → **404 `{"code":"NOT_FOUND"}`** ([email_templates.py:303](../../app/api/email_templates.py#L303)).
- **Errors:** 404; 403; 401; 422.
- **Related Screens:** Settings → Email templates (delete).
- **Related Tables:** `email_templates`, `audit_events` (`kind='settings.email_templates.remove'`).

### 6. `POST /v1/email-templates/resolve` — resolve effective template
- **Decorator:** [email_templates.py:316](../../app/api/email_templates.py#L316) — `@router.post("/resolve")`
- **Purpose:** Given `(session_type_id, stage_id, locale)`, return the template that would actually fire — per-type if it exists, else default. Shared by the EmailBuilder preview and the future stage-transition Celery hook.
- **Authentication / Authorization:** JWT-only (`_u`). No admin gate — read-only resolution.
- **Request Schema:** `ResolveRequest`.
- **Response Schema:** `dict` = `_row_to_template` plus `"resolved_from": "per_type" | "default"`.
- **Validation Rules:** `stage_id` must be in `_VALID_STAGES` → else **400 `{"code":"INVALID_STAGE"}`** ([email_templates.py:324](../../app/api/email_templates.py#L324)).
- **Errors:** 400 `INVALID_STAGE`; no active match (per-type and default both absent) → **404 `{"code":"NOT_FOUND"}`** ([email_templates.py:356](../../app/api/email_templates.py#L356)); 401; 422.
- **Example:** body `{"session_type_id":"<uuid>","stage_id":"copy_draft","locale":"en-US"}` → `{...,"resolved_from":"per_type"}` or the default row with `"resolved_from":"default"`.
- **Related Screens:** Settings → Email templates (preview "which template fires").
- **Related Tables:** `email_templates`.

---

## Non-endpoint module surface (not routes)

These are referenced for completeness; they carry no `@router` decorator and are not HTTP-reachable through this router:

- `substitute_variables(template_str, variables)` ([email_templates.py:46](../../app/api/email_templates.py#L46)) — replaces `{{ var }}` placeholders with **HTML-escaped** values (`html.escape(..., quote=True)`); for email **body** rendering. Missing keys → empty string.
- `substitute_variables_text(template_str, variables)` ([email_templates.py:82](../../app/api/email_templates.py#L82)) — same but **without** HTML escaping; for plain-text contexts such as email **subject** lines.
- `resolve_template_sync(conn, *, session_type_id=None, stage_id, locale="en-US")` ([email_templates.py:365](../../app/api/email_templates.py#L365)) — sync counterpart of `POST /resolve` for Celery tasks. Returns `None` instead of raising 404, and does NOT validate `stage_id` against `_VALID_STAGES`. Per the docstring it is **not yet adopted by `_maybe_send_deadline_email`** — PARTIALLY IMPLEMENTED for the deadline path.

---

## Notes / discrepancies
- The `resolve` route is the only POST in this router that is JWT-only (no admin gate); all other mutations are admin-gated.
- IMPLEMENTATION NOT FOUND in this router: the actual send path. The module header ([email_templates.py:15](../../app/api/email_templates.py#L15)) says test-send reuses `/v1/admin/email-debug/send` (a different router) with client-side substitution; that endpoint is not part of this file.
- The `(session_type_id, stage_id, locale)` uniqueness that drives the 409 is enforced by a DB constraint from migration 048 (per the module docstring); the constraint name is not asserted in code — the handler matches on generic `"duplicate key"` / `"unique constraint"` substrings ([email_templates.py:246](../../app/api/email_templates.py#L246)).

## Source Verification
- **Files Used:** `app/api/email_templates.py`, `app/security/roles.py`, `app/auth.py`
- **Components Used:** none (Vue screen `EmailBuilder.vue` named only from in-code comments, not opened/verified here)
- **APIs Used:** none (this IS the API surface); references `/v1/admin/email-debug/send` (different router, not opened)
- **Database Tables Used:** `email_templates`, `audit_events`
- **Permission Logic Used:** JWT presence (`CurrentUser`) on all routes; `require_admin(user)` → `LEGACY_ADMIN_EMAIL` gate on `POST`, `PUT`, `DELETE`. `GET ""`, `GET /{id}`, and `POST /resolve` are JWT-only.
- **Confidence Score:** High — every endpoint, decorator line, model, error code, and gate read directly from source.
- **Evidence Links:** [email_templates.py:35](../../app/api/email_templates.py#L35) (router), [email_templates.py:217](../../app/api/email_templates.py#L217) (POST create), [email_templates.py:316](../../app/api/email_templates.py#L316) (resolve), [roles.py:54](../../app/security/roles.py#L54) (LEGACY_ADMIN_EMAIL), [auth.py:172](../../app/auth.py#L172) (get_current_user — no role loaded)
