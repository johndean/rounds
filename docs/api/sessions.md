# API Reference — `sessions`

Router source: [app/api/sessions.py](../../app/api/sessions.py)

Mounted in [app/main.py:214](../../app/main.py#L214) via `app.include_router(sessions_router.router)`.

Router prefix: `/v1/sessions` (declared at [app/api/sessions.py:30](../../app/api/sessions.py#L30)). Tag: `sessions`.

This router defines **13 endpoints** for the session list / detail / lifecycle surface plus per-session stage-assignee management and a few read-only diagnostics (pipeline config, audit log, failure reason).

## Authentication & authorization model (verified)

- **Authentication** = a valid JWT bearer token. Every endpoint takes a `CurrentUser` dependency (named `_user`, `_u`, or `user` depending on whether the email is used). Resolution is `get_current_user` ([app/auth.py:172](../../app/auth.py#L172)); missing/invalid token → `401`.
- **Authorization** is JWT-only for the **majority** of routes. Three lifecycle routes carry an explicit admin gate, and `delete` uses a wider allowlist:
  - `require_admin(_user, …)` ([app/security/roles.py:95](../../app/security/roles.py#L95)) gates: `GET /deleted`, `POST /{id}/restore`, `DELETE /{id}/permanent`. `require_admin` raises `403 {"code":"ADMIN_ONLY", …}` unless `user.email == LEGACY_ADMIN_EMAIL` (`"johndean@vin.com"`, [app/security/roles.py:54](../../app/security/roles.py#L54)).
  - `DELETE /{id}` (soft-delete) checks membership in `SESSION_TRASH_ALLOWED = {LEGACY_ADMIN_EMAIL, "carlab@vin.com"}` ([app/api/sessions.py:52](../../app/api/sessions.py#L52)) — a wider allowlist than the admin gate (BR-002 carve-out), raising `403 "Only admin can delete sessions"` for anyone else.
- **PERMISSION REALITY:** the admin checks above are the only authorization beyond JWT presence. They are an email-equality gate, not a role tier — `auth_users.role` (migration 045) is not consulted by `get_current_user`, and `app/security/roles.py` is explicitly described as "scaffold only — not yet wired into any endpoint" at [app/security/roles.py:10-19](../../app/security/roles.py#L10). The `require_admin` usages in this file are an exception: they are wired here and they collapse to the `LEGACY_ADMIN_EMAIL` email compare.

> **Response envelope:** all JSON is wrapped by `EnvelopeMiddleware` into `{success, data, error, meta}` ([app/middleware/envelope.py:196](../../app/middleware/envelope.py#L196)). Schemas below describe the `data` payload. `ConflictError` and other `MICException` subclasses ([app/middleware/envelope.py:65-123](../../app/middleware/envelope.py#L65)) map to `409`/etc. error envelopes.

## Shared Pydantic schemas

Defined at [app/api/sessions.py:56-134](../../app/api/sessions.py#L56):

- **`PipelineConfig`** ([:56](../../app/api/sessions.py#L56)): `ai_pipeline` (str, default `"direct"`), `ai_mode` (str, default `"transcript"`), `ai_model` (str, default `"gemini-2.5-pro"`), `prompt_mode` (str, default `"transcript"`), `custom_prompt` (str|null), `stt_backend` (str, default `"google_latest_long"`), `template_id` (str, default `"lecture_v1"`), `iil_config` (dict, default `{"enabled":true,"tier1":true,"tier2":true,"tier3":true}`).
- **`PipelineConfigOut`** ([:260](../../app/api/sessions.py#L260)) extends `PipelineConfig` with `auto_detected_template_id` (str|null) and `auto_detected_confidence` (float|null).
- **`SessionIn`** ([:71](../../app/api/sessions.py#L71)): `code` (str, 1–64), `title` (str, 1–512), `presenter` (str|null), `duration_sec` (int|null), `attendee_count` (int|null), `taxonomy` (list[str], default `[]`), `pipeline_config` (`PipelineConfig`|null).
- **`SessionOut`** ([:81](../../app/api/sessions.py#L81), `from_attributes=True`): `id` (UUID), `code`, `title`, `title_long` (str|null), `title_short` (str|null), `presenter` (str|null), `status` (str), `duration_sec` (int|null), `word_count` (int|null), `segment_count` (int|null), `attendee_count` (int|null), `taxonomy` (list[str]), `session_type_id` (UUID|null).
- **`SessionPatch`** ([:106](../../app/api/sessions.py#L106)): all optional — `code`, `title`, `title_long`, `title_short`, `presenter`, `session_type_id` (UUID). Whitelist enforced; unknown fields ignored.
- **`StageAssigneePatch`** ([:118](../../app/api/sessions.py#L118)): `assignee_email` (str|null), `person_id` (UUID|null), `group_id` (UUID|null), `notify_email` (bool|null).

---

## GET `/v1/sessions`

- **Decorator:** [app/api/sessions.py:138](../../app/api/sessions.py#L138) — `@router.get("", response_model=list[SessionOut])`
- **Method:** GET
- **Purpose:** List non-deleted sessions, optionally filtered by SOP stage (join on `sop_state`), AI processing stage (`sessions.status`), or free-text on code/title ([:148-151](../../app/api/sessions.py#L148)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** query params — `stage` (str|null → joins `sop_state.current_stage`), `ai` (str|null → `status = :ai`), `f` (str|null → free-text `LOWER(code/title) LIKE %f%`), `limit` (int, default 50), `offset` (int, default 0).
- **Response Schema:** `list[SessionOut]` (raw SQL row dicts matching `SessionOut`).
- **Validation Rules:** `deleted_at IS NULL` always enforced; ordered by `created_at DESC NULLS LAST, code DESC` ([:169](../../app/api/sessions.py#L169)).
- **Errors:** No explicit handler-raised errors (envelope wraps any 500). Empty list when nothing matches.
- **Example:** `GET /v1/sessions?ai=transcribe&f=cardiac&limit=20`
- **Related Screens:** SessionsView list — [frontend/src/services/api.ts:138](../../frontend/src/services/api.ts#L138).
- **Related Tables:** `sessions`, `sop_state` (only when `?stage=`).

---

## POST `/v1/sessions`

- **Decorator:** [app/api/sessions.py:178](../../app/api/sessions.py#L178) — `@router.post("", response_model=SessionOut, status_code=201)`
- **Method:** POST
- **Purpose:** Create a `sessions` row + the matching `session_templates` row (pipeline routing) in one transaction so `ingest_task` always finds a config row ([:180-191](../../app/api/sessions.py#L180)).
- **Authentication:** Required (`user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** `SessionIn` (body).
- **Response Schema:** `SessionOut`, HTTP **201**.
- **Validation Rules:** New session inserted with `status = 'uploading'`. `taxonomy` serialized to JSONB. If `pipeline_config` is omitted, defaults from `PipelineConfig()` are written to `session_templates` ([:230-254](../../app/api/sessions.py#L230)).
- **Errors:**
  - `409 CONFLICT` — `ConflictError` when the insert hits the `sessions_code_key` UNIQUE constraint (duplicate `code`); `details` carries `{code, constraint}` ([:219-228](../../app/api/sessions.py#L219)).
  - Other `IntegrityError`s re-raise (→ 500 envelope).
- **Example:** `POST /v1/sessions` body `{"code":"S-AB12","title":"NT-proBNP","pipeline_config":{"ai_pipeline":"enhanced"}}`
- **Related Screens:** Upload view — [frontend/src/services/api.ts:142](../../frontend/src/services/api.ts#L142).
- **Related Tables:** `sessions`, `session_templates`.

---

## GET `/v1/sessions/deleted`

- **Decorator:** [app/api/sessions.py:266](../../app/api/sessions.py#L266) — `@router.get("/deleted")`
- **Method:** GET
- **Purpose:** List soft-deleted sessions within the 30-day recovery window (`deleted_at IS NOT NULL AND deleted_at >= now() - interval '30 days'`). Backs Settings → Deleted Sessions ([:267-275](../../app/api/sessions.py#L267)). Declared before `GET /{session_id}` so the literal path wins.
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** **Admin-gated** — `require_admin(_user, message="Only admin can view deleted sessions")` ([:276](../../app/api/sessions.py#L276)). Effective check: `user.email == "johndean@vin.com"`.
- **Request Schema:** None.
- **Response Schema:** `list[dict]` — each: `session_id` (str), `code`, `title`, `presenter`, `status`, `created_at` (ISO|null), `deleted_at` (ISO|null) ([:292-302](../../app/api/sessions.py#L292)). No `response_model`.
- **Validation Rules:** Only rows newer than 30 days shown; older rows hidden but retained in DB for audit joins.
- **Errors:** `403 ADMIN_ONLY` for non-admin.
- **Example:** `GET /v1/sessions/deleted`
- **Related Screens:** Settings → Deleted Sessions — [frontend/src/services/api.ts:167](../../frontend/src/services/api.ts#L167).
- **Related Tables:** `sessions`.

---

## GET `/v1/sessions/{session_id}/audit-log`

- **Decorator:** [app/api/sessions.py:306](../../app/api/sessions.py#L306) — `@router.get("/{session_id}/audit-log")`
- **Method:** GET
- **Purpose:** Return the append-only state-transition log written by the state machine ([:307-308](../../app/api/sessions.py#L307)).
- **Authentication:** Required (`_u: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID).
- **Response Schema:** `list[dict]` — the `processing_log` array from `session_audit`; `[]` if no row or non-list ([:317-320](../../app/api/sessions.py#L317)).
- **Validation Rules:** None.
- **Errors:** None handler-raised; returns `[]` when absent.
- **Example:** `GET /v1/sessions/<id>/audit-log`
- **Related Screens:** Editor / session detail audit surfaces (server route; consumed alongside SessionDetailView).
- **Related Tables:** `session_audit`.

---

## GET `/v1/sessions/{session_id}/pipeline-config`

- **Decorator:** [app/api/sessions.py:323](../../app/api/sessions.py#L323) — `@router.get("/{session_id}/pipeline-config", response_model=PipelineConfigOut)`
- **Method:** GET
- **Purpose:** Return the stored pipeline routing for a session, including auto-detected template hints ([:324-342](../../app/api/sessions.py#L324)).
- **Authentication:** Required (`_u: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID).
- **Response Schema:** `PipelineConfigOut`.
- **Validation Rules:** None.
- **Errors:** `404` — `detail="No pipeline config for session"` when no `session_templates` row ([:341](../../app/api/sessions.py#L341)).
- **Example:** `GET /v1/sessions/<id>/pipeline-config`
- **Related Screens:** Session detail / pipeline panel — [frontend/src/services/api.ts:176](../../frontend/src/services/api.ts#L176).
- **Related Tables:** `session_templates`.

---

## GET `/v1/sessions/{session_id}/stage-assignees`

- **Decorator:** [app/api/sessions.py:345](../../app/api/sessions.py#L345) — `@router.get("/{session_id}/stage-assignees")`
- **Method:** GET
- **Purpose:** Per-session, per-stage assignees populated at ingest from the chosen Type's matrix; one row per stage with typed FK joined to `people`/`groups` so renames/deletes propagate ([:346-358](../../app/api/sessions.py#L346)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID).
- **Response Schema:** `list[dict]` (no `response_model`) — per row: `stage`, `notify_email`, `source` (`'default'`|`'manual'`), `assigned_at`, `person_id`, `group_id`, `person_email`, `person_name`, `person_role`, `person_avatar_color`, `group_name`, `assignee_label` (COALESCE of name / `Group: <name>` / `(unassigned)`) ([:360-376](../../app/api/sessions.py#L360)).
- **Validation Rules:** None.
- **Errors:** None handler-raised; `[]` if no rows.
- **Example:** `GET /v1/sessions/<id>/stage-assignees`
- **Related Screens:** SessionDetailView assignees / Editor right-rail Admin chip / SOP stepper — [frontend/src/services/api.ts:146](../../frontend/src/services/api.ts#L146).
- **Related Tables:** `session_stage_assignees`, `people`, `groups`.

---

## PUT `/v1/sessions/{session_id}/stage-assignees/{stage}`

- **Decorator:** [app/api/sessions.py:379](../../app/api/sessions.py#L379) — `@router.put("/{session_id}/stage-assignees/{stage}")`
- **Method:** PUT
- **Purpose:** Override a single stage's assignee for this session; sets `source='manual'`. Empty body resets to the Type-matrix default and flips `source` back to `'default'` ([:387-401](../../app/api/sessions.py#L387)).
- **Authentication:** Required (`user: CurrentUser`; email written to `assigned_by`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID), `stage` (str); body `StageAssigneePatch`.
- **Response Schema:** `dict` (no `response_model`) — same row shape as the GET stage-assignees endpoint; falls back to `{"stage", "source"}` if the post-write SELECT returns nothing ([:481-495](../../app/api/sessions.py#L481)).
- **Validation Rules:** Resolution order ([:392-399](../../app/api/sessions.py#L392)): (1) `person_id` typed wins; (2) else `group_id` typed; (3) else parse `assignee_email` — `"Group: X"` → group lookup, `"(unassigned)"` → both null (reset), else email → `people` lookup; (4) all null → reset to Type-matrix default for the stage. Upserts via `ON CONFLICT (session_id, stage)`. DB CHECK `chk_session_stage_assignees_single_assignee` enforces exactly one of person/group.
- **Errors:** None explicitly raised in the handler.
- **Example:** `PUT /v1/sessions/<id>/stage-assignees/medical` body `{"assignee_email":"carlab@vin.com","notify_email":true}`
- **Related Screens:** SessionDetailView inline stage picker — [frontend/src/services/api.ts:154](../../frontend/src/services/api.ts#L154).
- **Related Tables:** `session_stage_assignees`, `people`, `groups`, `stage_assignees` (default lookup), `session_types`, `sessions`.

---

## POST `/v1/sessions/{session_id}/stage-assignees/apply-type-defaults`

- **Decorator:** [app/api/sessions.py:498](../../app/api/sessions.py#L498) — `@router.post("/{session_id}/stage-assignees/apply-type-defaults")`
- **Method:** POST
- **Purpose:** Bulk-apply the session's Type matrix into `session_stage_assignees`; overwrites every stage and marks `source='default'`. Idempotent ([:505-514](../../app/api/sessions.py#L505)).
- **Authentication:** Required (`user: CurrentUser`; passed to `init_session_stages` as `actor`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID); query `type_id` (UUID|null). If `type_id` given, it is persisted to `sessions.session_type_id` first.
- **Response Schema:** `dict` — `{"session_id": str, "stages": <result of init_session_stages>}` ([:544](../../app/api/sessions.py#L544)).
- **Validation Rules:** Deletes all existing `session_stage_assignees` rows for the session before re-init ([:529-531](../../app/api/sessions.py#L529)); a synchronous engine is created from `DATABASE_URL` (minus `+asyncpg`) and disposed in a `finally`.
- **Errors:** None handler-raised (engine errors propagate → 500 envelope).
- **Example:** `POST /v1/sessions/<id>/stage-assignees/apply-type-defaults?type_id=<type-uuid>`
- **Related Screens:** SessionDetailView Type picker "Apply Type defaults" banner — [frontend/src/services/api.ts:159](../../frontend/src/services/api.ts#L159).
- **Related Tables:** `sessions`, `session_stage_assignees`, `session_types`, `stage_assignees` (via `init_session_stages`).

---

## GET `/v1/sessions/{session_id}`

- **Decorator:** [app/api/sessions.py:547](../../app/api/sessions.py#L547) — `@router.get("/{session_id}", response_model=SessionOut)`
- **Method:** GET
- **Purpose:** Fetch a single non-deleted session ([:548](../../app/api/sessions.py#L548)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID).
- **Response Schema:** `SessionOut`.
- **Validation Rules:** `deleted_at IS NULL` filter — a soft-deleted session reads as 404.
- **Errors:** `404` — `detail="Session not found"` ([:565](../../app/api/sessions.py#L565)).
- **Example:** `GET /v1/sessions/<id>`
- **Related Screens:** SessionDetailView / Editor header — [frontend/src/services/api.ts:140](../../frontend/src/services/api.ts#L140).
- **Related Tables:** `sessions`.

---

## PATCH `/v1/sessions/{session_id}`

- **Decorator:** [app/api/sessions.py:569](../../app/api/sessions.py#L569) — `@router.patch("/{session_id}", response_model=SessionOut)`
- **Method:** PATCH
- **Purpose:** Partial update of session metadata; whitelisted fields only (`code`, `title`, `title_long`, `title_short`, `presenter`, `session_type_id`) ([:576-584](../../app/api/sessions.py#L576)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID); body `SessionPatch`. Uses `model_dump(exclude_unset=True)` — unset fields untouched; an empty string clears a field; only set keys produce `SET` clauses.
- **Response Schema:** `SessionOut`.
- **Validation Rules:** `WHERE id = :sid AND deleted_at IS NULL`; `updated_at = now()` always set.
- **Errors:**
  - `400` — `detail="No updatable fields provided"` when the patch body has no set fields ([:589](../../app/api/sessions.py#L589)).
  - `409` — `detail={"code":"DUPLICATE_CODE", "message":…}` on a `sessions_code_key`/duplicate-code violation ([:605-612](../../app/api/sessions.py#L605)).
  - `404` — `detail="Session not found"` when no row updated ([:616](../../app/api/sessions.py#L616)).
  - `500` — `detail=str(exc)` for other update exceptions ([:613](../../app/api/sessions.py#L613)).
- **Example:** `PATCH /v1/sessions/<id>` body `{"title":"Corrected title"}`
- **Related Screens:** SessionsView / SessionDetailView inline rename — [frontend/src/services/api.ts:144](../../frontend/src/services/api.ts#L144).
- **Related Tables:** `sessions`.

---

## DELETE `/v1/sessions/{session_id}`

- **Decorator:** [app/api/sessions.py:621](../../app/api/sessions.py#L621) — `@router.delete("/{session_id}")`
- **Method:** DELETE
- **Purpose:** Soft-delete a session — sets `deleted_at`; data preserved for 30 days ([:622-629](../../app/api/sessions.py#L622)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** **Allowlist-gated** — caller's email must be in `SESSION_TRASH_ALLOWED = {"johndean@vin.com", "carlab@vin.com"}` ([:52](../../app/api/sessions.py#L52), check at [:630](../../app/api/sessions.py#L630)). This is a wider set than `require_admin` (the `carlab@vin.com` BR-002 partner carve-out).
- **Request Schema:** path `session_id` (UUID).
- **Response Schema:** `dict` — `{"session_id": str, "deleted": true}` ([:665](../../app/api/sessions.py#L665)).
- **Validation Rules:** Sets `deleted_at = now()` + `updated_at = now()`. After delete, attempts `release_slot` (Redis rate-limit slot) — failure is logged, non-fatal ([:653-663](../../app/api/sessions.py#L653)).
- **Errors:**
  - `403` — `detail="Only admin can delete sessions"` if not in the allowlist ([:631](../../app/api/sessions.py#L631)).
  - `404` — `detail="Session not found"` ([:642](../../app/api/sessions.py#L642)).
  - `409 CONFLICT` — `ConflictError("Session is already deleted")` when `deleted_at` is already set ([:645](../../app/api/sessions.py#L645)).
- **Example:** `DELETE /v1/sessions/<id>`
- **Related Screens:** SessionsView / SessionDetailView delete — [frontend/src/services/api.ts:165](../../frontend/src/services/api.ts#L165).
- **Related Tables:** `sessions`; Redis rate-limit slots (side effect, not a table).

---

## POST `/v1/sessions/{session_id}/restore`

- **Decorator:** [app/api/sessions.py:668](../../app/api/sessions.py#L668) — `@router.post("/{session_id}/restore")`
- **Method:** POST
- **Purpose:** Restore a soft-deleted session — clears `deleted_at` ([:669-673](../../app/api/sessions.py#L669)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** **Admin-gated** — `require_admin(_user, message="Only admin can restore sessions")` ([:674](../../app/api/sessions.py#L674)) → effective `user.email == "johndean@vin.com"`.
- **Request Schema:** path `session_id` (UUID).
- **Response Schema:** `dict` — `{"session_id": str, "restored": true}` ([:694](../../app/api/sessions.py#L694)).
- **Validation Rules:** Sets `deleted_at = NULL`, `updated_at = now()`.
- **Errors:**
  - `403 ADMIN_ONLY` for non-admin.
  - `404` — `detail="Session not found"` ([:684](../../app/api/sessions.py#L684)).
  - `409 CONFLICT` — `ConflictError("Session is not deleted")` when `deleted_at` is null ([:687](../../app/api/sessions.py#L687)).
- **Example:** `POST /v1/sessions/<id>/restore`
- **Related Screens:** Settings → Deleted Sessions restore — [frontend/src/services/api.ts:169](../../frontend/src/services/api.ts#L169).
- **Related Tables:** `sessions`.

---

## DELETE `/v1/sessions/{session_id}/permanent`

- **Decorator:** [app/api/sessions.py:697](../../app/api/sessions.py#L697) — `@router.delete("/{session_id}/permanent")`
- **Method:** DELETE
- **Purpose:** Hard-delete a session and all child rows (via `ON DELETE CASCADE`). Must be soft-deleted first. Irreversible ([:699-706](../../app/api/sessions.py#L699)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** **Admin-gated** — `require_admin(_user, message="Only admin can permanently delete sessions")` ([:707](../../app/api/sessions.py#L707)).
- **Request Schema:** path `session_id` (UUID).
- **Response Schema:** `dict` — `{"session_id": str, "permanently_deleted": true}` ([:750](../../app/api/sessions.py#L750)).
- **Validation Rules:** Single `DELETE FROM sessions` relies on schema CASCADE (`audit_events.session_id` is `ON DELETE SET NULL`, retained for forensics — comment at [:722-727](../../app/api/sessions.py#L722)). Attempts `release_slot` afterward (non-fatal).
- **Errors:**
  - `403 ADMIN_ONLY` for non-admin.
  - `404` — `detail="Session not found"` ([:717](../../app/api/sessions.py#L717)).
  - `409 CONFLICT` — `ConflictError("Session must be soft-deleted before permanent deletion")` when `deleted_at` is null ([:720](../../app/api/sessions.py#L720)).
  - `500` — `detail="Cascade delete failed: <ExcClass>"` on cascade failure (rolled back) ([:740](../../app/api/sessions.py#L740)).
- **Example:** `DELETE /v1/sessions/<id>/permanent`
- **Related Screens:** Settings → Deleted Sessions permanent purge — [frontend/src/services/api.ts:171](../../frontend/src/services/api.ts#L171).
- **Related Tables:** `sessions` (+ all CASCADE children); `audit_events` (SET NULL, retained).

---

## GET `/v1/sessions/{session_id}/failure-reason`

- **Decorator:** [app/api/sessions.py:753](../../app/api/sessions.py#L753) — `@router.get("/{session_id}/failure-reason")`
- **Method:** GET
- **Purpose:** Surface why a session is in `failed` status — the last audit-log transition into `failed` plus the worker's raw `reason` string ([:754-761](../../app/api/sessions.py#L754)).
- **Authentication:** Required (`_u: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID).
- **Response Schema:** `dict` — `session_id`, `code`, `title`, `status`, `reason` (str|null), `category` (str|null), `ts` (str|null), `actor` (str|null), `log_tail` (last 10 log entries) ([:794-804](../../app/api/sessions.py#L794)).
- **Validation Rules:** Scans `session_audit.processing_log` in reverse for the entry whose `next`/`status` is `"failed"`.
- **Errors:** `404` — `detail="Session not found"` ([:776](../../app/api/sessions.py#L776)).
- **Example:** `GET /v1/sessions/<id>/failure-reason`
- **Related Screens:** SessionsView failure-detail modal — [frontend/src/services/api.ts:173](../../frontend/src/services/api.ts#L173).
- **Related Tables:** `sessions`, `session_audit`.

---

## Source Verification
- **Files Used:** app/api/sessions.py, app/auth.py, app/security/roles.py, app/middleware/envelope.py, app/db.py, app/main.py, frontend/src/services/api.ts
- **Components Used:** none (Vue views consume via api.ts; no SFC read directly — screen names inferred from service call sites)
- **APIs Used:** GET/POST /v1/sessions, GET /v1/sessions/deleted, GET /v1/sessions/{id}, PATCH /v1/sessions/{id}, DELETE /v1/sessions/{id}, POST /v1/sessions/{id}/restore, DELETE /v1/sessions/{id}/permanent, GET /v1/sessions/{id}/audit-log, GET /v1/sessions/{id}/pipeline-config, GET+PUT /v1/sessions/{id}/stage-assignees[/{stage}], POST .../apply-type-defaults, GET /v1/sessions/{id}/failure-reason
- **Database Tables Used:** sessions, session_templates, session_audit, sop_state, session_stage_assignees, stage_assignees, session_types, people, groups, audit_events
- **Permission Logic Used:** JWT presence for all; require_admin (LEGACY_ADMIN_EMAIL email gate) on /deleted, /restore, /permanent; SESSION_TRASH_ALLOWED allowlist on DELETE soft-delete
- **Confidence Score:** High — all 13 decorators and their handler bodies, schemas, and gates read in source.
- **Evidence Links:** [app/api/sessions.py:30](../../app/api/sessions.py#L30), [app/api/sessions.py:52](../../app/api/sessions.py#L52), [app/api/sessions.py:138](../../app/api/sessions.py#L138), [app/api/sessions.py:276](../../app/api/sessions.py#L276), [app/api/sessions.py:630](../../app/api/sessions.py#L630), [app/security/roles.py:95](../../app/security/roles.py#L95)
