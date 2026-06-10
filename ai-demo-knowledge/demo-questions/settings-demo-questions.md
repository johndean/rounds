# Settings — Demo Questions (Code-Verified)

> Every answer below is traceable to source. Items that cannot be proven from code are tagged **NOT VERIFIED IN CODE**, **IMPLEMENTATION NOT FOUND**, or **PARTIALLY IMPLEMENTED**. Permission answers describe only what is actually enforced today (JWT + a hardcoded `johndean@vin.com` admin gate); role tiers are scaffold-only and not active.

---

## User

### Q1. What can I configure in Settings, and how do I get to a section?
- **Verified Answer:** Settings is one route, `/settings/:section?`, with a left nav of 13 sections: General, Team & roles, Types & stage defaults, AI models, Upload & storage, Discrepancy classification, Export, Prompt templates, Session manifest, Email, Auth & logins, Diagnostics, Deleted sessions. Clicking a nav item navigates to `/settings/<id>`, so every section is deep-linkable; an unknown/blank section shows General.
- **Supporting Evidence:** Section list `SettingsView.vue:38-52`; `pick()` pushes `/settings/<id>` at `SettingsView.vue:56-58`; default/fallback to General at `SettingsView.vue:54,88`.
- **Source Files:** `frontend/src/views/SettingsView.vue`
- **API References:** none (navigation only)
- **Database References:** none

### Q2. I changed the organisation name and time zone — how do I save them?
- **Verified Answer:** Edit the fields in General and click Save. The screen writes all three values (name, locale, time zone) in parallel; a success toast confirms.
- **Supporting Evidence:** Save fires three parallel `settingsApi.set(...)` calls for `org_name`, `default_locale`, `default_timezone` at `SectionGeneral.vue:34-38`.
- **Source Files:** `frontend/src/components/settings/SectionGeneral.vue`
- **API References:** `PUT /v1/settings/{key}` (`settings.py:73-88`)
- **Database References:** `org_settings`

### Q3. I added a teammate but they don't show up as a possible stage assignee — why?
- **Verified Answer:** They will — the Types section hydrates its assignee dropdown live from the people list (`/v1/settings/people`), not a static fixture, so a person added in Team & roles appears in the Types stage matrix without a page reload. If you don't see them, the people fetch may have failed (the dropdown falls back to just `(unassigned)`).
- **Supporting Evidence:** Dropdown built from `people.map(p => p.name)` + groups at `SectionTypes.vue:111-115`; people loaded on mount at `SectionTypes.vue:105-110`.
- **Source Files:** `frontend/src/components/settings/SectionTypes.vue`, `frontend/src/components/settings/SectionTeam.vue`
- **API References:** `GET /v1/settings/people` (`settings.py:92-97`)
- **Database References:** `people`

### Q4. Why is the "Add person" button greyed out?
- **Verified Answer:** The button stays disabled until you enter a name AND a valid email. The email must match a basic `name@domain.tld` pattern. Helper text under the form tells you exactly what's missing.
- **Supporting Evidence:** `canAddPerson` requires non-empty name + `isEmailish(email)` at `SectionTeam.vue:74-77`; regex at `SectionTeam.vue:70-72`; hint text at `SectionTeam.vue:79-87`.
- **Source Files:** `frontend/src/components/settings/SectionTeam.vue`
- **API References:** `POST /v1/settings/people` (`settings.py:100-111`)
- **Database References:** `people`

### Q5. How do I download the Word macro?
- **Verified Answer:** In the Export section, click "Download (.zip)". It downloads the macro bundle. If the bundle isn't deployed, you get a clean "Macro bundle not deployed yet" message instead of a broken download.
- **Supporting Evidence:** `downloadMacro()` calls `settingsApi.downloadMacro()` and handles 404 `MACRO_NOT_FOUND` at `SectionExport.vue:40-65`; backend serves a zip from `docs/macros/` or 404s at `settings.py:680-746`.
- **Source Files:** `frontend/src/components/settings/SectionExport.vue`
- **API References:** `GET /v1/settings/export/macro` (`settings.py:680-746`)
- **Database References:** `audit_events` (download is logged)

---

## Executive

### Q1. Without code changes, what can an operator reconfigure at runtime?
- **Verified Answer:** Organisation name, default locale, time zone, default AI model, upload transport (GCS vs Railway), discrepancy-classifier backend + model, key-points-in-export toggle, the team roster + groups, session Types and their per-stage assignee matrices, the active Gemini prompts, email templates, and login accounts — all editable in Settings and persisted to the database.
- **Supporting Evidence:** Org k/v via `GET/PUT /v1/settings` (`settings.py:67-88`); model `SectionAIModels.vue`; upload `SectionUpload.vue`; classifier `SectionDiscrepancy.vue`; export `SectionExport.vue`; team/types/templates/auth-users in their respective sections + `settings.py`.
- **Source Files:** `frontend/src/views/SettingsView.vue`, `app/api/settings.py`
- **API References:** `/v1/settings/*`
- **Database References:** `org_settings`, `people`, `groups`, `session_types`, `stage_assignees`, `prompt_templates`, `auth_users`

### Q2. Does changing a setting in the UI actually affect the production pipeline?
- **Verified Answer:** Yes for the Gemini transcript prompt: binding a prompt template as the default for `transcript` mode changes what Gemini receives on the very next upload, because the upload pipeline reads `prompt_templates.default_for_mode` on the hot path (with a hardcoded fallback if no row is bound). The default AI model setting is read by the Upload screen to prefill the model picker.
- **Supporting Evidence:** `get_prompt_for_mode` reads the active default-for-mode row at `app/prompts.py:131-172`; migration 049 wires the column; `SectionAIModels.vue:43-45` notes Upload reads `default_ai_model`.
- **Source Files:** `app/prompts.py`, `frontend/src/components/settings/SectionPromptTemplates.vue`, `migrations/049_prompt_templates_default_for_mode.sql`
- **API References:** `PUT /v1/settings/templates/{id}`
- **Database References:** `prompt_templates`

### Q3. How is the org protected from accidentally losing all admin access?
- **Verified Answer:** The auth-users API refuses to demote, disable, or delete the only active admin, returning a 409 "Cannot demote or disable the only active admin. Add a second admin first." Caveat: today the *effective* admin is a single hardcoded email, so this guard protects the `auth_users.role='admin'` count, not runtime privilege (see Administrator/Compliance sections).
- **Supporting Evidence:** Last-admin guard on update `settings.py:580-593` and delete `settings.py:649-660`; count helper `settings.py:513-516`.
- **Source Files:** `app/api/settings.py`
- **API References:** `PUT/DELETE /v1/settings/auth-users/{id}`
- **Database References:** `auth_users`

### Q4. Is there reporting or analytics in Settings?
- **Verified Answer:** No. Settings produces no reports, charts, or metric exports. The counter values shown in Diagnostics (heap, RTT, uptime %) are hardcoded display literals, not live telemetry. The only data Settings feeds reporting-wise is the audit trail it writes on every change.
- **Supporting Evidence:** Hardcoded telemetry literals at `SectionDiagnostics.vue:49-61`; no reporting code in the module — **IMPLEMENTATION NOT FOUND**.
- **Source Files:** `frontend/src/components/settings/SectionDiagnostics.vue`
- **API References:** none
- **Database References:** `audit_events` (indirect)

---

## Operations

### Q1. A new VIN conference type came up — how do I add it and route its stages?
- **Verified Answer:** In Types & stage defaults, type the new Type name and click "+ Add type" (admin-gated). Select it, then for each of the 8 SOP stages choose an assignee (a person or a `Group: …`) and optionally check Email to notify on entry; click "Save matrix" to replace all 8 rows for that Type. The 8 stages are prep, copy_draft, medical, copy_final, cms, captions, qa, complete.
- **Supporting Evidence:** Add at `SectionTypes.vue:130-143`; save matrix at `SectionTypes.vue:166-188`; stages from `SOP_STAGE_KEYS` `fixtures/settings.ts:34-43`; server add `settings.py:320-332`, bulk-replace assignees `settings.py:420-461`.
- **Source Files:** `frontend/src/components/settings/SectionTypes.vue`, `frontend/src/fixtures/settings.ts`, `app/api/settings.py`
- **API References:** `POST /v1/settings/types`, `PUT /v1/settings/types/{id}/assignees`
- **Database References:** `session_types`, `stage_assignees`

### Q2. Why can't I delete the default Type?
- **Verified Answer:** The default Type cannot be deleted because every session needs a starting Type. The UI hides its Remove button, and the server independently rejects a delete of the default row with 409 `DEFAULT_TYPE_LOCKED`. A DB partial unique index also guarantees at most one default exists.
- **Supporting Evidence:** UI hides Remove at `SectionTypes.vue:212-216`; server 409 at `settings.py:341-348`; unique index `session_types_is_default_uq` `migration 038:18-19`.
- **Source Files:** `frontend/src/components/settings/SectionTypes.vue`, `app/api/settings.py`, `migrations/038_session_types_is_default.sql`
- **API References:** `DELETE /v1/settings/types/{id}`
- **Database References:** `session_types`

### Q3. After lots of create/delete, I'm getting 429 RATE_LIMIT_USER. How do I recover?
- **Verified Answer:** Go to Diagnostics → "Reset my stale slots". It sweeps your active-sessions set in Redis and removes slots whose sessions are soft-deleted or gone, preserving live slots. The toast reports how many were cleared and how many remain.
- **Supporting Evidence:** `onResetSlots()` calls `diag.clearRateLimitSlots()` at `SectionDiagnostics.vue:22-40`; the card explains the leak at `SectionDiagnostics.vue:103-117`.
- **Source Files:** `frontend/src/components/settings/SectionDiagnostics.vue`
- **API References:** `POST /v1/diag/clear-rate-limit-slots`
- **Database References:** none (Redis)

### Q4. The login table is empty after a deploy/cutover — what do I do?
- **Verified Answer:** In Auth & logins, when the table is empty a recovery panel appears with "Seed from AUTH_USERS env". Clicking it re-runs the idempotent boot-time seed from the `AUTH_USERS` env CSV without redeploying; the result shows seeded/total/skipped counts.
- **Supporting Evidence:** Empty-state panel at `SectionAuthUsers.vue:329-358`; `reseedFromEnv()` calls `diag.reseedAuthUsers()` at `SectionAuthUsers.vue:238-258`.
- **Source Files:** `frontend/src/components/settings/SectionAuthUsers.vue`
- **API References:** `POST /v1/diag/reseed-auth-users`
- **Database References:** `auth_users`

### Q5. How do I change which AI model new sessions use, or switch the discrepancy classifier off Gemini?
- **Verified Answer:** AI models section sets `default_ai_model` (used as the default for new AI-mode sessions, overridable per upload). Discrepancy classification section sets `classify_backend` (Gemini Developer API vs Vertex AI, with independent billing) and `classify_model`. All save on change.
- **Supporting Evidence:** Model save `SectionAIModels.vue:30-39`; backend/model saves `SectionDiscrepancy.vue:29-40`; options from `AI_MODELS` `fixtures/settings.ts:21-31`.
- **Source Files:** `frontend/src/components/settings/SectionAIModels.vue`, `frontend/src/components/settings/SectionDiscrepancy.vue`
- **API References:** `PUT /v1/settings/{key}` (keys `default_ai_model`, `classify_backend`, `classify_model`)
- **Database References:** `org_settings`

### Q6. Where do stage-notification emails come from?
- **Verified Answer:** Email templates are per-Type × per-Stage HTML, edited in the Email → Open builder flow; a NULL-Type row is the default for all Types. The triggers (which stage fires which email) live in the Types matrix via each stage's Email checkbox. Note: migration 048 ships the templates table + 8 default rows only — the Celery hook that actually fires emails on stage advance is a separate, out-of-scope component.
- **Supporting Evidence:** Email home cards at `SectionEmail.vue:21-34`; builder wiring at `EmailBuilder.vue:3-28`; 8 default rows + out-of-scope note at `migration 048:23-26,64-90`.
- **Source Files:** `frontend/src/components/settings/SectionEmail.vue`, `frontend/src/components/settings/EmailBuilder.vue`, `migrations/048_email_templates.sql`
- **API References:** `/v1/email-templates` (separate router, `app/main.py:229`)
- **Database References:** `email_templates`

---

## Finance

### Q1. Can I route AI billing to a separate quota?
- **Verified Answer:** For discrepancy classification, yes — the Discrepancy section lets you switch the backend from "Gemini Developer API" (uses `GEMINI_API_KEY`) to "Vertex AI Gemini", described in the UI as separate billing/quota using a distinct key. This setting (`classify_backend`) is read on classify calls. The main transcription model is selected separately under AI models.
- **Supporting Evidence:** Backend select + billing copy at `SectionDiscrepancy.vue:48-66`; persisted via `PUT /v1/settings/{key}` `settings.py:73-88`.
- **Source Files:** `frontend/src/components/settings/SectionDiscrepancy.vue`
- **API References:** `PUT /v1/settings/classify_backend`
- **Database References:** `org_settings`
- **Note:** Whether the classify task actually honors `classify_backend` at runtime is outside this module — **NOT VERIFIED IN CODE** here.

### Q2. Does Settings expose any cost or usage figures?
- **Verified Answer:** No. There are no cost, usage, or billing metrics anywhere in Settings. The only billing-adjacent control is the classifier backend toggle (which quota to bill against). **IMPLEMENTATION NOT FOUND** for any cost/usage reporting.
- **Supporting Evidence:** No cost/usage code in any section component or `settings.py`.
- **Source Files:** `frontend/src/components/settings/*`, `app/api/settings.py`
- **API References:** none
- **Database References:** none

---

## Compliance

### Q1. Which Settings actions are written to an audit trail, and what's captured?
- **Verified Answer:** Nearly every write logs to `audit_events` with the actor's email, a `kind`, and a human summary, committed in the same transaction. Captured actions include: set org setting; person add/update/remove; group add/update/remove; group member add/remove; Type add/remove; stage-matrix save; auth-user add/update/reset-password/delete; macro download; template add/update/remove (20 distinct `kind` values, all prefixed `settings.`).
- **Supporting Evidence:** Examples — `settings.set` `settings.py:84-86`; `settings.auth_user.reset_password` `settings.py:627-630`; `settings.export.macro_download` `settings.py:731-737`; `settings.templates.update` `settings.py:1003-1006`.
- **Source Files:** `app/api/settings.py`
- **API References:** all write endpoints under `/v1/settings/*`
- **Database References:** `audit_events`

### Q2. Are passwords ever stored or shown in plaintext?
- **Verified Answer:** Passwords are bcrypt-hashed at rest and never returned by any API — the auth-user response projection explicitly excludes `password_hash`. The model is reset-only: an admin types a new plaintext over TLS, the server hashes it immediately, and the response surfaces only `password_reset_at`, never the plaintext. Known debt: the bootstrap/DR source `AUTH_USERS` is still a plaintext env CSV.
- **Supporting Evidence:** Whitelist projection `settings.py:499-510`; reset returns only email + timestamp `settings.py:632-635`; env-CSV debt `app/auth.py:81-143`.
- **Source Files:** `app/api/settings.py`, `app/auth.py`
- **API References:** `POST /v1/settings/auth-users/{id}/reset-password`
- **Database References:** `auth_users`

### Q3. Is access to sensitive Settings actions restricted to admins?
- **Verified Answer:** Partially, and the reality matters. Type/assignee changes, all auth-user management, and template create/update/delete call `require_admin`, which today resolves to a single hardcoded email gate (`johndean@vin.com`) because the system never loads a per-user role. However, the org key/value settings (org name, locale, time zone, default model, upload backend, classifier routing) and the entire people/groups roster are NOT admin-gated — any authenticated user can change them. The Settings route also has no client-side admin guard.
- **Supporting Evidence:** `require_admin` call sites `settings.py:322,337,431,531,538,571,617,647,872,938,1016`; gate resolves to email at `roles.py:62-92`; unguarded org-k/v `settings.py:68,74`; unguarded people/groups `settings.py:101,170,...`; no `adminOnly` meta on `/settings` `router/index.ts:40,44,63`.
- **Source Files:** `app/api/settings.py`, `app/security/roles.py`, `frontend/src/router/index.ts`
- **API References:** all `/v1/settings/*`
- **Database References:** `auth_users` (role column not consulted at request time)
- **Tag:** **PARTIALLY IMPLEMENTED** role-based access.

### Q4. Can a template's history be reconstructed after edits or deletion?
- **Verified Answer:** Yes. Prompt templates carry a `version` that increments on every update, deletion is a soft-delete (`is_active=FALSE`) so the row stays queryable, and each add/update/remove writes an audit event (with default-for-mode set/clear flips called out explicitly in the audit summary).
- **Supporting Evidence:** `version = version + 1` on update `settings.py:961`; soft-delete `settings.py:1028-1030`; audit summary flags default changes `settings.py:997-1006`.
- **Source Files:** `app/api/settings.py`, `migrations/047_prompt_templates.sql`
- **API References:** `PUT/DELETE /v1/settings/templates/{id}`
- **Database References:** `prompt_templates`, `audit_events`

### Q5. How long are deleted sessions recoverable?
- **Verified Answer:** The Deleted sessions UI states soft-deleted sessions are recoverable for 30 days, after which only append-only ledger entries persist; each row shows an "N/30 days elapsed" counter. The 30-day window itself is enforced by the sessions module, not Settings.
- **Supporting Evidence:** Copy + counter at `SectionDeleted.vue:98-99,41-44`.
- **Source Files:** `frontend/src/components/settings/SectionDeleted.vue`
- **API References:** `GET /v1/sessions/deleted`, restore, permanent-delete (sessions module)
- **Database References:** sessions tables (outside this module — **NOT VERIFIED IN CODE** here)

---

## Administrator

### Q1. How do I add a login, set its role, and reset its password?
- **Verified Answer:** In Auth & logins: enter email + an initial password (min 10 chars) + role, click "Add user" (`POST`). Per row you can Make admin/Make user (role toggle), Disable/Enable, Reset password (a modal that takes a new min-10 password), and Delete. All these endpoints are admin-gated.
- **Supporting Evidence:** Add `SectionAuthUsers.vue:115-139`; role/active toggles `SectionAuthUsers.vue:142-168`; reset modal `SectionAuthUsers.vue:182-202`; server add/update/reset `settings.py:536-635`.
- **Source Files:** `frontend/src/components/settings/SectionAuthUsers.vue`, `app/api/settings.py`
- **API References:** `POST /v1/settings/auth-users`, `PUT /v1/settings/auth-users/{id}`, `POST /v1/settings/auth-users/{id}/reset-password`, `DELETE /v1/settings/auth-users/{id}`
- **Database References:** `auth_users`

### Q2. I made a user an admin in the UI — do they now have admin powers?
- **Verified Answer:** No, not at runtime. Toggling role updates the `auth_users.role` column in the database, but `get_current_user` never loads that column, and every `require_admin` call in Settings runs without a role and therefore falls back to the hardcoded email gate (`johndean@vin.com`). So the role tier is currently scaffolding: the only effective admin is that one email.
- **Supporting Evidence:** `User` carries only `email`, role never loaded `app/auth.py:36-39,203`; `require_admin(user)` (no role) → email gate `roles.py:62-92`; scaffold-only docstring `roles.py:10-19`.
- **Source Files:** `app/auth.py`, `app/security/roles.py`, `app/api/settings.py`
- **API References:** `PUT /v1/settings/auth-users/{id}`
- **Database References:** `auth_users` (role column written but not read for auth)
- **Tag:** **PARTIALLY IMPLEMENTED**.

### Q3. Which Settings endpoints require admin and which don't?
- **Verified Answer:** Admin-gated (email gate): Type add/remove, save type assignees, all auth-users endpoints, and template create/update/delete. NOT gated (any logged-in user): GET/PUT org settings, all people CRUD, all groups + members CRUD, GET types, GET type assignees, GET templates, and the macro download (intentionally public — they're publishable docs).
- **Supporting Evidence:** Gated call sites `settings.py:322,337,431,531,538,571,617,647,872,938,1016`; unguarded GET/PUT settings `settings.py:68,74`; macro "No admin gate" docstring `settings.py:682-685`.
- **Source Files:** `app/api/settings.py`
- **API References:** `/v1/settings/*`
- **Database References:** n/a

### Q4. What happens if I try to bind two templates as the default for the same AI mode?
- **Verified Answer:** The second one is rejected with 409 `DEFAULT_MODE_TAKEN`, and the error names the template currently holding that mode so you can unbind it first. Only `ai_prompt` templates can be marked a default, and the mode must be one of transcript/summary/key-moments/structured-notes. A DB partial unique index enforces one default per mode among active rows.
- **Supporting Evidence:** 409 with conflict name on create `settings.py:906-916` and update `settings.py:975-986`; `ai_prompt`-only `settings.py:879-884`; mode validation `settings.py:809-819`; index `migration 049:44-46`.
- **Source Files:** `app/api/settings.py`, `migrations/049_prompt_templates_default_for_mode.sql`
- **API References:** `POST/PUT /v1/settings/templates`
- **Database References:** `prompt_templates`

### Q5. Why can't I delete a system prompt template?
- **Verified Answer:** System templates (`is_system=TRUE`) are locked from deletion — the server returns 409 `SYSTEM_TEMPLATE_LOCKED` and the UI hides the Delete button on system cards. You can edit them or Duplicate them to make an editable copy.
- **Supporting Evidence:** Server lock `settings.py:1022-1027`; UI hides Delete + Duplicate path `SectionPromptTemplates.vue:347-354,250-270`.
- **Source Files:** `app/api/settings.py`, `frontend/src/components/settings/SectionPromptTemplates.vue`
- **API References:** `DELETE /v1/settings/templates/{id}`
- **Database References:** `prompt_templates`

### Q6. What seed data ships out of the box?
- **Verified Answer:** 17 VIN session Types (with `default` promoted to the org default), 10 people + 5 groups + memberships, 6 processing + 2 ai_prompt templates (the `Transcript` one bound to `transcript` mode and seeded with the verbatim MIC transcript prompt), and 8 default email templates (one per SOP stage).
- **Supporting Evidence:** Types `migration 031`/`039`; default promotion `migration 038:23-25`; people/groups `migration 032`; templates `migration 047:64-90`; transcript binding `migration 049:57-62`; MIC prompt `migration 050`; email defaults `migration 048:64-90`.
- **Source Files:** `migrations/031,032,038,039,047,048,049,050*.sql`
- **API References:** n/a (seed)
- **Database References:** `session_types`, `people`, `groups`, `group_members`, `prompt_templates`, `email_templates`

---

## Power User

### Q1. Where does the live Gemini transcript prompt actually come from, and how do I edit it?
- **Verified Answer:** From the `prompt_templates` row whose `default_for_mode='transcript'`. Edit its system prompt in Prompt templates (AI Prompt Templates section) and save — the upload pipeline reads `config->>'system_prompt'` for the active default-for-mode row on every upload, with a hardcoded fallback only if no row is bound. Binding is by column, so renaming the template is safe.
- **Supporting Evidence:** Hot-path read `app/prompts.py:165-172`; binding column + rename-safety `migration 049:1-20`; UI default-for-mode select `SectionPromptTemplates.vue:475-481`.
- **Source Files:** `app/prompts.py`, `frontend/src/components/settings/SectionPromptTemplates.vue`, `migrations/049_prompt_templates_default_for_mode.sql`
- **API References:** `PUT /v1/settings/templates/{id}`
- **Database References:** `prompt_templates`

### Q2. How does the stage-assignee matrix store a person vs a group, and does renaming break assignments?
- **Verified Answer:** The save sends each stage's `assignee_email`; the server resolves it to typed FKs — a `"Group: X"` string to a `group_id`, an email to a `person_id`, and `(unassigned)`/empty to neither. Reads JOIN those FKs and COALESCE display fields over the legacy email, so renaming a person or group propagates immediately and doesn't break the assignment. Deleting the person/group sets the FK to NULL (chip becomes unassigned) rather than orphaning the row.
- **Supporting Evidence:** Resolver `settings.py:358-384`; read query COALESCE `settings.py:387-405`; `ON DELETE SET NULL` FKs `migration 040:17-19`.
- **Source Files:** `app/api/settings.py`, `migrations/040_stage_assignees_typed_fk.sql`
- **API References:** `PUT /v1/settings/types/{id}/assignees`, `GET /v1/settings/types/{id}/assignees`
- **Database References:** `stage_assignees`, `people`, `groups`

### Q3. How does the template PUT know whether to clear vs keep `default_for_mode`?
- **Verified Answer:** It uses Pydantic's `model_fields_set`: if the field is absent from the body, the binding is left unchanged; if present and null, it's unbound (SET NULL). The frontend only sends the field when the operator actually changed the dropdown, so a normal name/description edit never disturbs the binding.
- **Supporting Evidence:** `model_fields_set` branch `settings.py:956-958`; tri-state docstring `settings.py:775-789`; frontend conditional send `SectionPromptTemplates.vue:229-231`.
- **Source Files:** `app/api/settings.py`, `frontend/src/components/settings/SectionPromptTemplates.vue`
- **API References:** `PUT /v1/settings/templates/{id}`
- **Database References:** `prompt_templates`

### Q4. The General screen seeds `time_zone` but I see `default_timezone` — what's the real key?
- **Verified Answer:** The General screen reads and writes `default_timezone` and `export's key is `export_include_keypoints`; migration 006 seeds different keys (`time_zone`, `include_key_points`). So the seeded values aren't read by those screens — the screens fall back to their in-component defaults until you save, at which point they persist under their own key names. This is a real seed-vs-code key-name drift.
- **Supporting Evidence:** Screen reads `default_timezone` `SectionGeneral.vue:23,37`; `export_include_keypoints` `SectionExport.vue:20,32`; seed keys `time_zone`/`include_key_points` `migration 006:14,19`.
- **Source Files:** `frontend/src/components/settings/SectionGeneral.vue`, `frontend/src/components/settings/SectionExport.vue`, `migrations/006_settings.sql`
- **API References:** `GET/PUT /v1/settings`
- **Database References:** `org_settings`
- **Tag:** seed-vs-code discrepancy (flagged).

### Q5. Why did the legacy prompt_templates / email_templates tables get dropped and recreated?
- **Verified Answer:** Migration 006 created both tables with an older schema that the current code doesn't use. Because `CREATE TABLE IF NOT EXISTS` would no-op on the existing table, migrations 047 and 048 `DROP TABLE … CASCADE` the empty legacy tables and recreate them in the current shape (with `config` JSONB / `default_for_mode` for prompts; `session_type_id`/`stage_id`/`locale`/`body` for emails). Documented as safe because the legacy tables never held real data (the UI used fixtures / warn-toasts before wiring).
- **Supporting Evidence:** Prompt drop+recreate rationale `migration 047:11-28`; email drop+recreate `migration 048:12-21`.
- **Source Files:** `migrations/047_prompt_templates.sql`, `migrations/048_email_templates.sql`
- **API References:** n/a
- **Database References:** `prompt_templates`, `email_templates`

### Q6. How does Team avoid an N+1 fetch when loading group members?
- **Verified Answer:** It calls a single bulk endpoint `/v1/settings/groups-members` that returns `{group_id: [person]}` for every group in one round-trip, instead of one members call per group. It falls back to `{}` if that endpoint is unavailable on an older API build.
- **Supporting Evidence:** Bulk endpoint `settings.py:243-265`; parallel hydrate + fallback `SectionTeam.vue:102-115`.
- **Source Files:** `app/api/settings.py`, `frontend/src/components/settings/SectionTeam.vue`
- **API References:** `GET /v1/settings/groups-members`
- **Database References:** `group_members`, `people`

---

## Source Verification
- **Files Used:** `frontend/src/views/SettingsView.vue`; `frontend/src/components/settings/{SectionGeneral,SectionTeam,SectionTypes,SectionAIModels,SectionUpload,SectionDiscrepancy,SectionExport,SectionPromptTemplates,SectionManifest,SectionEmail,SectionAuthUsers,SectionDiagnostics,SectionDeleted,EmailBuilder}.vue`; `frontend/src/fixtures/settings.ts`; `frontend/src/services/api.ts`; `frontend/src/router/index.ts`; `app/api/settings.py`; `app/auth.py`; `app/security/roles.py`; `app/prompts.py`; `app/main.py`; `migrations/{006,031,032,038,039,040,045,047,048,049,050}*.sql`
- **Components Used:** SettingsView + 13 sections + EmailBuilder
- **APIs Used:** `/v1/settings` (GET/PUT); people/groups/members CRUD; types + `/{id}/assignees`; templates CRUD; auth-users CRUD + reset-password; `/export/macro`; `/v1/email-templates` (separate); diag `clear-rate-limit-slots`, `reseed-auth-users`
- **Database Tables Used:** `org_settings`, `people`, `groups`, `group_members`, `session_types`, `stage_assignees`, `email_templates`, `prompt_templates`, `auth_users`, `audit_events`
- **Permission Logic Used:** JWT (`CurrentUser`) on every endpoint; `require_admin(user)` → `LEGACY_ADMIN_EMAIL` (`johndean@vin.com`) gate on Type/assignee/auth-user/template writes; org-k/v + people/groups unguarded; role tiers scaffold-only; client `adminOnly` guard does NOT cover `/settings`
- **Confidence Score:** High — every Q/A traced to current source; permission reality, seed-vs-code key drift, and email-firing out-of-scope are flagged rather than glossed.
- **Evidence Links:** [`settings.py:529-668`](../../app/api/settings.py#L529-L668), [`settings.py:867-1036`](../../app/api/settings.py#L867-L1036), [`roles.py:62-92`](../../app/security/roles.py#L62-L92), [`app/auth.py:36-39`](../../app/auth.py#L36-L39), [`app/prompts.py:131-172`](../../app/prompts.py#L131-L172), [`SectionTypes.vue:166-188`](../../frontend/src/components/settings/SectionTypes.vue#L166-L188), [`router/index.ts:40-68`](../../frontend/src/router/index.ts#L40-L68)
