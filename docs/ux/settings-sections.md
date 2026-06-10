# Settings Sections (`components/settings/Section*`)

Each section component renders inside the Settings shell ([settings.md](./settings.md)) when its id is the active route param. This file enumerates every `Section*` component — its purpose, its connected API calls, and its real loading/empty/error/permission behavior. Shared helpers (`SettingsHeader`, `FormRow`, `TogglePill`) and sub-views (`EmailBuilder`, `EmailDebug`, `GCSDebug`) are covered at the end.

All API wrappers below resolve through `http(...)` in [frontend/src/services/api.ts](../../frontend/src/services/api.ts) (the `settingsApi`, `emailTemplatesApi`, `emailDebug`, `diag`, and `sessions` objects).

---

## SectionGeneral (`general`)

[frontend/src/components/settings/SectionGeneral.vue](../../frontend/src/components/settings/SectionGeneral.vue)

- **Purpose:** Edit `org_name`, `default_locale`, `default_timezone`. Defaults shown until the backend responds ([SectionGeneral.vue:12-14](../../frontend/src/components/settings/SectionGeneral.vue#L12)).
- **Connected APIs:**
  - `GET /v1/settings` via `settingsApi.list()` on mount ([SectionGeneral.vue:20](../../frontend/src/components/settings/SectionGeneral.vue#L20); [api.ts:780](../../frontend/src/services/api.ts#L780)).
  - `PUT /v1/settings/{key}` via `settingsApi.set(...)` x3 on Save ([SectionGeneral.vue:34-38](../../frontend/src/components/settings/SectionGeneral.vue#L34); [api.ts:781-782](../../frontend/src/services/api.ts#L781)).
- **Loading:** `loading` ref disables the inputs while the GET is in flight ([SectionGeneral.vue:52-66](../../frontend/src/components/settings/SectionGeneral.vue#L52)). No spinner element.
- **Empty/Error:** load failure is swallowed (`catch {}`) and keeps defaults ([SectionGeneral.vue:24-25](../../frontend/src/components/settings/SectionGeneral.vue#L24)); save failure pushes an error toast ([SectionGeneral.vue:40-41](../../frontend/src/components/settings/SectionGeneral.vue#L40)). No dedicated empty/error markup.
- **Permissions:** none beyond the shell's JWT requirement.

## SectionTeam (`team`)

[frontend/src/components/settings/SectionTeam.vue](../../frontend/src/components/settings/SectionTeam.vue)

- **Purpose:** Two-pane People + Groups CRUD. People rows support inline add/edit/delete with name/email/role/avatar-color; Groups support add/rename/delete and member chip add/remove ([SectionTeam.vue:1-9](../../frontend/src/components/settings/SectionTeam.vue#L1)).
- **Connected APIs:**
  - On mount (parallel): `settingsApi.people()` `GET /v1/settings/people`, `settingsApi.groups()` `GET /v1/settings/groups`, `settingsApi.groupMembersBulk()` `GET /v1/settings/groups-members` ([SectionTeam.vue:102-109](../../frontend/src/components/settings/SectionTeam.vue#L102); [api.ts:783,790,799-800](../../frontend/src/services/api.ts#L783)).
  - People: `peopleAdd` `POST /v1/settings/people`, `peopleUpdate` `PUT /v1/settings/people/{id}`, `peopleRemove` `DELETE /v1/settings/people/{id}` ([api.ts:784-789](../../frontend/src/services/api.ts#L784)).
  - Groups: `groupsAdd` `POST /v1/settings/groups`, `groupsUpdate` `PUT /v1/settings/groups/{id}`, `groupsRemove` `DELETE /v1/settings/groups/{id}` ([api.ts:791-796](../../frontend/src/services/api.ts#L791)).
  - Members: `groupMemberAdd` `POST .../groups/{gid}/members/{pid}`, `groupMemberRemove` `DELETE .../groups/{gid}/members/{pid}` ([api.ts:827-836](../../frontend/src/services/api.ts#L827)).
- **Loading:** `loading` ref renders "Loading team…" until `hydrate()` resolves ([SectionTeam.vue:324](../../frontend/src/components/settings/SectionTeam.vue#L324)).
- **Empty:** IMPLEMENTATION NOT FOUND — empty people/groups render zero rows with no empty-state copy.
- **Error:** 409/locked errors are surfaced via `err()` which prefers `detail.message` from the ApiError body, shown as a toast ([SectionTeam.vue:123-137](../../frontend/src/components/settings/SectionTeam.vue#L123)). Mount-time list fetches each `.catch(() => [])` so a broken endpoint degrades to an empty pane ([SectionTeam.vue:103-108](../../frontend/src/components/settings/SectionTeam.vue#L103)).
- **Permissions:** shell JWT only at the client; write endpoints are server-gated. Uses `confirm.open()` for deletes ([SectionTeam.vue:209-213](../../frontend/src/components/settings/SectionTeam.vue#L209)).

## SectionTypes (`types`)

[frontend/src/components/settings/SectionTypes.vue](../../frontend/src/components/settings/SectionTypes.vue)

- **Purpose:** Type list + an 8-stage assignee matrix per Type, each stage with an assignee dropdown and an email-on-entry checkbox. New sessions auto-populate from the selected Type's matrix ([SectionTypes.vue:1-12](../../frontend/src/components/settings/SectionTypes.vue#L1)).
- **Connected APIs:**
  - On mount (parallel): `settingsApi.types()` `GET /v1/settings/types`, `settingsApi.people()`, `settingsApi.groups()` ([SectionTypes.vue:105-109](../../frontend/src/components/settings/SectionTypes.vue#L105); [api.ts:837,783,790](../../frontend/src/services/api.ts#L837)).
  - Per active Type: `settingsApi.typeAssignees(id)` `GET /v1/settings/types/{id}/assignees` ([SectionTypes.vue:90](../../frontend/src/components/settings/SectionTypes.vue#L90); [api.ts:842-843](../../frontend/src/services/api.ts#L842)).
  - Save matrix: `settingsApi.setTypeAssignees(id, rows)` `PUT /v1/settings/types/{id}/assignees` ([SectionTypes.vue:179](../../frontend/src/components/settings/SectionTypes.vue#L179); [api.ts:844-848](../../frontend/src/services/api.ts#L844)).
  - Add/remove type: `typesAdd` `POST /v1/settings/types`, `typesRemove` `DELETE /v1/settings/types/{id}` ([api.ts:838-841](../../frontend/src/services/api.ts#L838)).
- **Loading:** `loadingMatrix` ref shows an inline "loading…" next to the matrix header ([SectionTypes.vue:223](../../frontend/src/components/settings/SectionTypes.vue#L223)).
- **Empty:** if `GET /v1/settings/types` returns no rows, the view falls back to the seed fixture `SESSION_TYPES` and a reset (empty) matrix ([SectionTypes.vue:33](../../frontend/src/components/settings/SectionTypes.vue#L33), [SectionTypes.vue:123-125](../../frontend/src/components/settings/SectionTypes.vue#L123)). No "no types" copy.
- **Error:** matrix/save/add/remove failures push toasts formatted as `{status} — {message}` for `ApiError` ([SectionTypes.vue:93-95](../../frontend/src/components/settings/SectionTypes.vue#L93), [SectionTypes.vue:182-183](../../frontend/src/components/settings/SectionTypes.vue#L182)).
- **Permissions:** add/remove are noted as "admin-gated server-side" in the docstring ([SectionTypes.vue:11](../../frontend/src/components/settings/SectionTypes.vue#L11)); default Types cannot be removed client-side ([SectionTypes.vue:146](../../frontend/src/components/settings/SectionTypes.vue#L146)).

## SectionAIModels (`ai-models`)

[frontend/src/components/settings/SectionAIModels.vue](../../frontend/src/components/settings/SectionAIModels.vue)

- **Purpose:** Pick the org-wide `default_ai_model` for new AI-mode sessions; UploadView reads it to prefill its model picker ([SectionAIModels.vue:1-8](../../frontend/src/components/settings/SectionAIModels.vue#L1)).
- **Connected APIs:** `GET /v1/settings` on mount ([SectionAIModels.vue:21](../../frontend/src/components/settings/SectionAIModels.vue#L21)); `PUT /v1/settings/default_ai_model` on change via `settingsApi.set` ([SectionAIModels.vue:34](../../frontend/src/components/settings/SectionAIModels.vue#L34)).
- **Loading:** `loading` ref disables the select until the GET resolves ([SectionAIModels.vue:49](../../frontend/src/components/settings/SectionAIModels.vue#L49)).
- **Empty/Error:** no empty markup; save failure pushes an error toast ([SectionAIModels.vue:36-37](../../frontend/src/components/settings/SectionAIModels.vue#L36)). Model option list comes from the `AI_MODELS` fixture ([SectionAIModels.vue:12](../../frontend/src/components/settings/SectionAIModels.vue#L12)).
- **Permissions:** shell JWT only.

## SectionUpload (`upload`)

[frontend/src/components/settings/SectionUpload.vue](../../frontend/src/components/settings/SectionUpload.vue)

- **Purpose:** Set `upload_backend` (`gcs` direct vs `railway` server-routed). Default is `gcs` ([SectionUpload.vue:14](../../frontend/src/components/settings/SectionUpload.vue#L14)).
- **Connected APIs:** `GET /v1/settings` on mount ([SectionUpload.vue:20](../../frontend/src/components/settings/SectionUpload.vue#L20)); `PUT /v1/settings/upload_backend` on change ([SectionUpload.vue:36](../../frontend/src/components/settings/SectionUpload.vue#L36)).
- **Loading/Error:** `loading`+`saving` refs disable the select ([SectionUpload.vue:54](../../frontend/src/components/settings/SectionUpload.vue#L54)); on save failure the previous value is restored and an error toast fires ([SectionUpload.vue:38-40](../../frontend/src/components/settings/SectionUpload.vue#L38)).
- **Empty:** not applicable (fixed two-option select).
- **Permissions:** shell JWT only.

## SectionDiscrepancy (`discrepancy`)

[frontend/src/components/settings/SectionDiscrepancy.vue](../../frontend/src/components/settings/SectionDiscrepancy.vue)

- **Purpose:** Configure the discrepancy classifier: `classify_backend` (`gemini-dev` vs `vertex`) and `classify_model`. Separate from the main pipeline model ([SectionDiscrepancy.vue:1-7](../../frontend/src/components/settings/SectionDiscrepancy.vue#L1)).
- **Connected APIs:** `GET /v1/settings` on mount ([SectionDiscrepancy.vue:21](../../frontend/src/components/settings/SectionDiscrepancy.vue#L21)); `PUT /v1/settings/classify_backend` and `PUT /v1/settings/classify_model` on the respective change handlers ([SectionDiscrepancy.vue:32,38](../../frontend/src/components/settings/SectionDiscrepancy.vue#L32)).
- **Loading:** `loading` ref disables both selects ([SectionDiscrepancy.vue:53,62](../../frontend/src/components/settings/SectionDiscrepancy.vue#L53)).
- **Empty/Error:** no empty markup; save failures push "Failed to save" toasts ([SectionDiscrepancy.vue:33,39](../../frontend/src/components/settings/SectionDiscrepancy.vue#L33)). Model options from `AI_MODELS` fixture.
- **Permissions:** shell JWT only.

## SectionExport (`export`)

[frontend/src/components/settings/SectionExport.vue](../../frontend/src/components/settings/SectionExport.vue)

- **Purpose:** Toggle `export_include_keypoints`, and download the one-time Word VBA macro bundle ([SectionExport.vue:1-4](../../frontend/src/components/settings/SectionExport.vue#L1)).
- **Connected APIs:**
  - `GET /v1/settings` on mount ([SectionExport.vue:19](../../frontend/src/components/settings/SectionExport.vue#L19)); `PUT /v1/settings/export_include_keypoints` on toggle ([SectionExport.vue:32](../../frontend/src/components/settings/SectionExport.vue#L32)).
  - `GET /v1/settings/export/macro` via `settingsApi.downloadMacro()` — a `fetch`+blob download with the JWT header, throwing `ApiError` on non-2xx ([SectionExport.vue:48](../../frontend/src/components/settings/SectionExport.vue#L48); [api.ts:806-826](../../frontend/src/services/api.ts#L806)).
- **Loading:** `loading` ref guards the toggle; `downloading` ref shows "Downloading…" on the macro button ([SectionExport.vue:91-92](../../frontend/src/components/settings/SectionExport.vue#L91)).
- **Error:** 404 `MACRO_NOT_FOUND` surfaces a warn toast ("Macro bundle not deployed yet."), other failures an error toast; toggle save failure reverts the value ([SectionExport.vue:51-64](../../frontend/src/components/settings/SectionExport.vue#L51), [SectionExport.vue:34-37](../../frontend/src/components/settings/SectionExport.vue#L34)).
- **Empty:** not applicable.
- **Permissions:** shell JWT only.

## SectionPromptTemplates (`prompts`)

[frontend/src/components/settings/SectionPromptTemplates.vue](../../frontend/src/components/settings/SectionPromptTemplates.vue)

- **Purpose:** CRUD catalog for two template kinds sharing one table — `processing` (STT presets) and `ai_prompt` (Gemini system prompts). Catalog view + New/Edit form view; supports Edit, Duplicate, Delete, and binding an `ai_prompt` template as the default for an AI mode ([SectionPromptTemplates.vue:1-14](../../frontend/src/components/settings/SectionPromptTemplates.vue#L1)).
- **Connected APIs:**
  - `templatesList()` `GET /v1/settings/templates` on mount ([SectionPromptTemplates.vue:54](../../frontend/src/components/settings/SectionPromptTemplates.vue#L54); [api.ts:857-858](../../frontend/src/services/api.ts#L857)).
  - `templatesAdd` `POST /v1/settings/templates` (new + duplicate) ([SectionPromptTemplates.vue:199,262](../../frontend/src/components/settings/SectionPromptTemplates.vue#L199); [api.ts:861-862](../../frontend/src/services/api.ts#L861)).
  - `templatesUpdate` `PUT /v1/settings/templates/{id}` ([SectionPromptTemplates.vue:232](../../frontend/src/components/settings/SectionPromptTemplates.vue#L232); [api.ts:863-864](../../frontend/src/services/api.ts#L863)).
  - `templatesRemove` `DELETE /v1/settings/templates/{id}` ([SectionPromptTemplates.vue:285](../../frontend/src/components/settings/SectionPromptTemplates.vue#L285); [api.ts:865-866](../../frontend/src/services/api.ts#L865)).
- **Loading:** `loading` ref shows an inline "loading…" in the catalog subnav ([SectionPromptTemplates.vue:317](../../frontend/src/components/settings/SectionPromptTemplates.vue#L317)).
- **Empty:** IMPLEMENTATION NOT FOUND — categories with no templates simply don't render (`v-if="templatesInCategory(cat).length"`); no "no templates" message ([SectionPromptTemplates.vue:331](../../frontend/src/components/settings/SectionPromptTemplates.vue#L331)).
- **Error:** `surfaceError()` extracts `detail.message`/`detail` string from `ApiError` and toasts it ([SectionPromptTemplates.vue:293-309](../../frontend/src/components/settings/SectionPromptTemplates.vue#L293)). System templates can't be deleted client-side (warn toast) ([SectionPromptTemplates.vue:273-275](../../frontend/src/components/settings/SectionPromptTemplates.vue#L273)).
- **Permissions:** shell JWT only at the client; back button uses `history.back()`.

## SectionManifest (`manifest`)

[frontend/src/components/settings/SectionManifest.vue](../../frontend/src/components/settings/SectionManifest.vue)

- **Purpose:** Static reference doc for the producer-prepared `extras2.txt` session manifest — expected fields and filename conventions ([SectionManifest.vue:1-4](../../frontend/src/components/settings/SectionManifest.vue#L1)).
- **Connected APIs:** none. The `fields` array is a hardcoded literal ([SectionManifest.vue:8-17](../../frontend/src/components/settings/SectionManifest.vue#L8)).
- **Loading/Empty/Error:** IMPLEMENTATION NOT FOUND — purely static markup, no async work.
- **Permissions:** shell JWT only.

## SectionEmail (`email`)

[frontend/src/components/settings/SectionEmail.vue](../../frontend/src/components/settings/SectionEmail.vue)

- **Purpose:** Home view describing per-Type × per-Stage email templates, with an "Open builder" CTA that swaps to the embedded `EmailBuilder` ([SectionEmail.vue:1-5](../../frontend/src/components/settings/SectionEmail.vue#L1)).
- **Connected APIs:** none directly. Drills into `EmailBuilder` via a local `view` ref (`'home' | 'builder'`) ([SectionEmail.vue:10](../../frontend/src/components/settings/SectionEmail.vue#L10)).
- **Loading/Empty/Error:** none at the home level (static cards).
- **Permissions:** shell JWT only at this level; the builder's test-send is admin-gated server-side (see EmailBuilder below).

## SectionAuthUsers (`auth-users`)

[frontend/src/components/settings/SectionAuthUsers.vue](../../frontend/src/components/settings/SectionAuthUsers.vue)

- **Purpose:** Manage login accounts — list, add (email + initial password ≥10 chars), toggle role admin/user, disable/enable, reset password (plaintext over TLS; never echoed back), delete. Plus an empty-state "Seed from AUTH_USERS env" recovery panel ([SectionAuthUsers.vue:1-16](../../frontend/src/components/settings/SectionAuthUsers.vue#L1)).
- **Connected APIs:**
  - `authUsersList()` `GET /v1/settings/auth-users` on mount ([SectionAuthUsers.vue:79](../../frontend/src/components/settings/SectionAuthUsers.vue#L79); [api.ts:871-872](../../frontend/src/services/api.ts#L871)).
  - `authUsersAdd` `POST /v1/settings/auth-users` ([SectionAuthUsers.vue:128](../../frontend/src/components/settings/SectionAuthUsers.vue#L128); [api.ts:873-874](../../frontend/src/services/api.ts#L873)).
  - `authUsersUpdate` `PUT /v1/settings/auth-users/{id}` (role + is_active toggles) ([SectionAuthUsers.vue:146,160](../../frontend/src/components/settings/SectionAuthUsers.vue#L146); [api.ts:875-876](../../frontend/src/services/api.ts#L875)).
  - `authUsersResetPassword` `POST /v1/settings/auth-users/{id}/reset-password` ([SectionAuthUsers.vue:190](../../frontend/src/components/settings/SectionAuthUsers.vue#L190); [api.ts:877-881](../../frontend/src/services/api.ts#L877)).
  - `authUsersRemove` `DELETE /v1/settings/auth-users/{id}` ([SectionAuthUsers.vue:215](../../frontend/src/components/settings/SectionAuthUsers.vue#L215); [api.ts:882-883](../../frontend/src/services/api.ts#L882)).
  - `diag.reseedAuthUsers()` `POST /v1/diag/reseed-auth-users` from the empty-state panel ([SectionAuthUsers.vue:242](../../frontend/src/components/settings/SectionAuthUsers.vue#L242); [api.ts:1051-1055](../../frontend/src/services/api.ts#L1051)).
- **Loading:** `loading` ref shows "Loading users…" ([SectionAuthUsers.vue:267](../../frontend/src/components/settings/SectionAuthUsers.vue#L267)). Per-row `busyIds` set disables that row's action buttons mid-request ([SectionAuthUsers.vue:67-74](../../frontend/src/components/settings/SectionAuthUsers.vue#L67)).
- **Empty:** explicit "No logins in the database" dashed panel + reseed button when `users.length === 0` ([SectionAuthUsers.vue:329-358](../../frontend/src/components/settings/SectionAuthUsers.vue#L329)).
- **Error:** a 403 on list shows the toast "Admin only — your account does not have access to Auth & Logins." then clears the list ([SectionAuthUsers.vue:82-83](../../frontend/src/components/settings/SectionAuthUsers.vue#L82)); other failures route through `surfaceError()` (prefers `detail.message`) ([SectionAuthUsers.vue:97-112](../../frontend/src/components/settings/SectionAuthUsers.vue#L97)).
- **Permissions:** all endpoints are admin-gated **server-side** (docstring + 403 handling). The client does not pre-check admin; non-admins simply receive 403 and see the toast/empty list. Delete uses `confirm.open()` ([SectionAuthUsers.vue:206-211](../../frontend/src/components/settings/SectionAuthUsers.vue#L206)).

## SectionDiagnostics (`diagnostics`)

[frontend/src/components/settings/SectionDiagnostics.vue](../../frontend/src/components/settings/SectionDiagnostics.vue)

- **Purpose:** Operational home: telemetry counters (static text), and entry points to GCS QA, the Test-Email page, two standalone HTML diagnostics (`/upload-test.html`, `/process-test.html`), and a rate-limit-slot reset ([SectionDiagnostics.vue:1-5](../../frontend/src/components/settings/SectionDiagnostics.vue#L1)).
- **Connected APIs:** `diag.clearRateLimitSlots()` `POST /v1/diag/clear-rate-limit-slots` on the "Reset my stale slots" button ([SectionDiagnostics.vue:26](../../frontend/src/components/settings/SectionDiagnostics.vue#L26); [api.ts:1042-1043](../../frontend/src/services/api.ts#L1042)). Drilling into `view = 'test'` mounts `EmailDebug`; `view = 'gcs'` mounts `GCSDebug` (those call their own endpoints — see below). The §20 telemetry counter values are hardcoded literals in the copy ([SectionDiagnostics.vue:51-52](../../frontend/src/components/settings/SectionDiagnostics.vue#L51)).
- **Loading:** `resetting` ref shows "Sweeping…" on the slot-reset button ([SectionDiagnostics.vue:113-116](../../frontend/src/components/settings/SectionDiagnostics.vue#L113)).
- **Empty:** not applicable (static cards).
- **Error:** slot-reset failure pushes a toast formatted `{status} — {message}` ([SectionDiagnostics.vue:34-36](../../frontend/src/components/settings/SectionDiagnostics.vue#L34)).
- **Permissions:** the home view is shell-JWT only; the GCS and Email sub-views hit server-gated routes.

## SectionDeleted (`deleted`)

[frontend/src/components/settings/SectionDeleted.vue](../../frontend/src/components/settings/SectionDeleted.vue)

- **Purpose:** Soft-deleted-session recovery within a 30-day window: list, restore, or permanently purge. Admin-only ([SectionDeleted.vue:1-8](../../frontend/src/components/settings/SectionDeleted.vue#L1)).
- **Connected APIs:**
  - `sessionsApi.listDeleted()` `GET /v1/sessions/deleted` on mount ([SectionDeleted.vue:27](../../frontend/src/components/settings/SectionDeleted.vue#L27); [api.ts:166-167](../../frontend/src/services/api.ts#L166)).
  - `sessionsApi.restore(id)` `POST /v1/sessions/{id}/restore` ([SectionDeleted.vue:57](../../frontend/src/components/settings/SectionDeleted.vue#L57); [api.ts:168-169](../../frontend/src/services/api.ts#L168)).
  - `sessionsApi.permanentDelete(id)` `DELETE /v1/sessions/{id}/permanent` ([SectionDeleted.vue:78](../../frontend/src/components/settings/SectionDeleted.vue#L78); [api.ts:170-171](../../frontend/src/services/api.ts#L170)).
- **Loading:** `loading` ref shows "Loading deleted sessions…" ([SectionDeleted.vue:125-127](../../frontend/src/components/settings/SectionDeleted.vue#L125)).
- **Empty:** explicit "No deleted sessions in the 30-day window." when not forbidden and `items.length === 0` ([SectionDeleted.vue:133-138](../../frontend/src/components/settings/SectionDeleted.vue#L133)).
- **Error:** a 403 sets `forbidden` and renders an "Admin-only." banner; other errors render an error message block ([SectionDeleted.vue:29-34](../../frontend/src/components/settings/SectionDeleted.vue#L29), [SectionDeleted.vue:102-118](../../frontend/src/components/settings/SectionDeleted.vue#L102), [SectionDeleted.vue:129-131](../../frontend/src/components/settings/SectionDeleted.vue#L129)).
- **Permissions:** admin-gated **server-side** — the client reacts to a 403 with the banner; it does not pre-check role. Restore/purge use `confirm.open()` ([SectionDeleted.vue:53,69-74](../../frontend/src/components/settings/SectionDeleted.vue#L53)).

---

## Shared helpers

### SettingsHeader
[frontend/src/components/settings/SettingsHeader.vue](../../frontend/src/components/settings/SettingsHeader.vue) — presentational header (`title`, `lead`, optional `headerCta` button). No API ([SettingsHeader.vue:5-9](../../frontend/src/components/settings/SettingsHeader.vue#L5)).

### FormRow / TogglePill
Layout/control primitives used across sections (label+control row; on/off pill). Read-only props, no API. Referenced by SectionGeneral, SectionExport, SectionPromptTemplates, EmailDebug, etc.

---

## Embedded sub-views (not routed, mounted inside sections)

### EmailBuilder (inside SectionEmail)
[frontend/src/components/settings/EmailBuilder.vue](../../frontend/src/components/settings/EmailBuilder.vue)

- **Purpose:** Per-Type × per-Stage HTML email template editor with live preview and a variable palette. Resolution: per-Type row wins, else the default row ([EmailBuilder.vue:1-16](../../frontend/src/components/settings/EmailBuilder.vue#L1)).
- **Connected APIs:**
  - `settingsApi.types()` `GET /v1/settings/types` on mount (Type dropdown) ([EmailBuilder.vue:104](../../frontend/src/components/settings/EmailBuilder.vue#L104)).
  - `emailTemplatesApi.resolve()` `POST /v1/email-templates/resolve` to load the active template ([EmailBuilder.vue:77](../../frontend/src/components/settings/EmailBuilder.vue#L77); [api.ts:933-934](../../frontend/src/services/api.ts#L933)).
  - `emailTemplatesApi.update()` `PUT /v1/email-templates/{id}` and `emailTemplatesApi.add()` `POST /v1/email-templates` on save ([EmailBuilder.vue:122,131,147,157](../../frontend/src/components/settings/EmailBuilder.vue#L122); [api.ts:927-931](../../frontend/src/services/api.ts#L927)).
  - `emailTemplatesApi.remove()` `DELETE /v1/email-templates/{id}` on revert-to-default ([EmailBuilder.vue:187](../../frontend/src/components/settings/EmailBuilder.vue#L187)).
  - `auth.me()` to prefill the test recipient, then `emailDebug.send()` `POST /v1/admin/email-debug/send` for the test send ([EmailBuilder.vue:210,230](../../frontend/src/components/settings/EmailBuilder.vue#L210); [api.ts:1014-1015](../../frontend/src/services/api.ts#L1014)).
- **Loading/Error:** `loading`/`saving`/`sending` refs gate buttons; failures route through `extractApiMessage()` toasts ([EmailBuilder.vue:246-252](../../frontend/src/components/settings/EmailBuilder.vue#L246)). On a 404 resolve the editor clears ([EmailBuilder.vue:86-99](../../frontend/src/components/settings/EmailBuilder.vue#L86)).
- **Permissions:** the test-send hits the admin-only `/v1/admin/email-debug/send`; CRUD authority is enforced server-side. Test recipient is collected via `window.prompt` ([EmailBuilder.vue:214](../../frontend/src/components/settings/EmailBuilder.vue#L214)).

### EmailDebug (inside SectionDiagnostics, `view='test'`)
[frontend/src/components/settings/EmailDebug.vue](../../frontend/src/components/settings/EmailDebug.vue)

- **Purpose:** Admin SMTP diagnostics — config presence, connectivity probe, test send, recent-attempts ledger, client event log ([EmailDebug.vue:1-15](../../frontend/src/components/settings/EmailDebug.vue#L1)).
- **Connected APIs:** `emailDebug.config()` `GET /v1/admin/email-debug/config`, `emailDebug.connectivity()` `POST /v1/admin/email-debug/connectivity`, `emailDebug.send()` `POST /v1/admin/email-debug/send`, `emailDebug.attempts()` `GET /v1/admin/email-debug/attempts` ([EmailDebug.vue:61,86,111,137](../../frontend/src/components/settings/EmailDebug.vue#L61); [api.ts:1011-1018](../../frontend/src/services/api.ts#L1011)).
- **Loading:** per-section refs (`loadingCfg`, `probing`, `sending`, `loadingAttempts`) plus a "Loading…" placeholder for config ([EmailDebug.vue:220](../../frontend/src/components/settings/EmailDebug.vue#L220)).
- **Empty:** "No send attempts logged yet." when the attempts table is empty ([EmailDebug.vue:302-304](../../frontend/src/components/settings/EmailDebug.vue#L302)); "Not yet run." for connectivity before first probe ([EmailDebug.vue:239](../../frontend/src/components/settings/EmailDebug.vue#L239)).
- **Error:** a 403 on config/attempts sets `forbidden` and renders an "Admin-only." banner ([EmailDebug.vue:64-66,140-142,193-206](../../frontend/src/components/settings/EmailDebug.vue#L64)); SMTP failures surface in the table + toasts + the event log.
- **Permissions:** all four endpoints are admin-only; non-admins get the 403 banner. The recipient defaults to `johndean@vin.com` in the form ([EmailDebug.vue:36](../../frontend/src/components/settings/EmailDebug.vue#L36)).

### GCSDebug (inside SectionDiagnostics, `view='gcs'`)
[frontend/src/components/settings/GCSDebug.vue](../../frontend/src/components/settings/GCSDebug.vue)

- **Purpose:** **Live** GCS probe table (unlike the static `#/gcs` route view). Calls `GET /v1/diag/gcs-checks` on mount and on "Re-run checks". Returns 14 rows: G1–G6 real probes, G7–G14 deferred stubs (`ok=null`) shown with a neutral "deferred" chip so the table never fakes health ([GCSDebug.vue:1-13](../../frontend/src/components/settings/GCSDebug.vue#L1)).
- **Connected APIs:** `diag.gcsChecks()` `GET /v1/diag/gcs-checks` ([GCSDebug.vue:34](../../frontend/src/components/settings/GCSDebug.vue#L34); [api.ts:1047](../../frontend/src/services/api.ts#L1047)).
- **Loading:** `loading` ref shows "Running…"/"Running probes…" row while in flight ([GCSDebug.vue:110-112](../../frontend/src/components/settings/GCSDebug.vue#L110)).
- **Empty:** IMPLEMENTATION NOT FOUND for a zero-row case (the endpoint returns 14 rows); KPI tiles compute counts off the result.
- **Error:** failures push a `{status} — {message}` toast ([GCSDebug.vue:36-40](../../frontend/src/components/settings/GCSDebug.vue#L36)).
- **Permissions:** server-gated diagnostic route; client does not pre-check.

## Source Verification
- **Files Used:** SettingsView.vue and all components under frontend/src/components/settings/ (SectionGeneral, SectionTeam, SectionTypes, SectionAIModels, SectionUpload, SectionDiscrepancy, SectionExport, SectionPromptTemplates, SectionManifest, SectionEmail, SectionAuthUsers, SectionDiagnostics, SectionDeleted, SettingsHeader, FormRow, TogglePill, EmailBuilder, EmailDebug, GCSDebug); frontend/src/services/api.ts
- **Components Used:** all Section* listed above plus SettingsHeader, FormRow, TogglePill, EmailBuilder, EmailDebug, GCSDebug, Icon
- **APIs Used:** GET/PUT /v1/settings(/{key}); /v1/settings/people; /v1/settings/groups(+/members, /groups-members); /v1/settings/types(/{id}/assignees); /v1/settings/templates; /v1/settings/auth-users(+/reset-password); /v1/settings/export/macro; /v1/email-templates(+/resolve); /v1/admin/email-debug/{config,connectivity,send,attempts}; /v1/diag/{gcs-checks,clear-rate-limit-slots,reseed-auth-users}; /v1/sessions/deleted; /v1/sessions/{id}/restore; /v1/sessions/{id}/permanent
- **Database Tables Used:** not asserted from the frontend; api.ts wrappers reference endpoints, not tables. Section docstrings cite org_settings, prompt_templates (migration 047), email templates (migration 048), auth_users — treat as PARTIALLY IMPLEMENTED references, not verified against migration files here.
- **Permission Logic Used:** JWT presence (router guard) for the shell; Auth & Logins / Deleted / Email diagnostics are admin-gated server-side and react to HTTP 403 (banner/toast). No active client-side role tiers.
- **Confidence Score:** High — every Section* component and the three sub-views were read in full and cross-checked against api.ts wrappers.
- **Evidence Links:** [api.ts:779-884](../../frontend/src/services/api.ts#L779), [SectionAuthUsers.vue:79](../../frontend/src/components/settings/SectionAuthUsers.vue#L79), [SectionDeleted.vue:27](../../frontend/src/components/settings/SectionDeleted.vue#L27), [GCSDebug.vue:34](../../frontend/src/components/settings/GCSDebug.vue#L34)
