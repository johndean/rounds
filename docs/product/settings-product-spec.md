# Settings — Product Specification

> Code-verified against the rounds.vin repository. Every claim below is traceable to a source file via the links provided. Statements that could not be proven from code are tagged with one of: **NOT VERIFIED IN CODE**, **IMPLEMENTATION NOT FOUND**, **PARTIALLY IMPLEMENTED**.

## Overview

Settings is the operator-facing configuration surface for the Rounds transcript application. It is a single Vue route (`/settings/:section?`) rendering a left-hand section nav plus a content pane, with 13 sections covering organization identity, team membership, session types and per-stage assignee matrices, AI model selection, upload transport, discrepancy-classifier routing, export options, prompt templates, the session-manifest reference, email templates, login (auth-users) administration, diagnostics, and deleted-session recovery.

The 13 sections are defined in [`SettingsView.vue`](../../frontend/src/views/SettingsView.vue#L38-L52):

| Section id | Nav label | Component |
|---|---|---|
| `general` | General | `SectionGeneral.vue` |
| `team` | Team & roles | `SectionTeam.vue` |
| `types` | Types & stage defaults | `SectionTypes.vue` |
| `ai-models` | AI models | `SectionAIModels.vue` |
| `upload` | Upload & storage | `SectionUpload.vue` |
| `discrepancy` | Discrepancy classification | `SectionDiscrepancy.vue` |
| `export` | Export | `SectionExport.vue` |
| `prompts` | Prompt templates | `SectionPromptTemplates.vue` |
| `manifest` | Session manifest | `SectionManifest.vue` |
| `email` | Email | `SectionEmail.vue` |
| `auth-users` | Auth & logins | `SectionAuthUsers.vue` |
| `diagnostics` | Diagnostics | `SectionDiagnostics.vue` |
| `deleted` | Deleted sessions | `SectionDeleted.vue` |

Most write operations persist to the backend under the `/v1/settings/*` router ([`app/api/settings.py`](../../app/api/settings.py)). Key/value org settings persist to the `org_settings` table; people/groups/types/assignees/auth-users/prompt-templates each have dedicated tables. Email templates persist via a separate router (`/v1/email-templates`) not defined in `settings.py`.

## Purpose

Settings exists to let an operator configure the workspace and the processing pipeline without code changes:

- Set workspace identity, default locale, and time zone ([`SectionGeneral.vue`](../../frontend/src/components/settings/SectionGeneral.vue)).
- Maintain the roster of people who can be assigned workflow stages, and the groups used for routing ([`SectionTeam.vue`](../../frontend/src/components/settings/SectionTeam.vue)).
- Define session Types and, per Type, a default assignee + notify-on-entry flag for each of the 8 SOP stages ([`SectionTypes.vue`](../../frontend/src/components/settings/SectionTypes.vue)).
- Choose the default AI model for new AI-mode sessions ([`SectionAIModels.vue`](../../frontend/src/components/settings/SectionAIModels.vue)).
- Choose the upload transport (direct-to-GCS vs server-routed) ([`SectionUpload.vue`](../../frontend/src/components/settings/SectionUpload.vue)).
- Route and model the discrepancy classifier ([`SectionDiscrepancy.vue`](../../frontend/src/components/settings/SectionDiscrepancy.vue)).
- Toggle key-points inclusion in exports and download the Word macro bundle ([`SectionExport.vue`](../../frontend/src/components/settings/SectionExport.vue)).
- Manage prompt templates (STT processing presets + Gemini system prompts), including binding one prompt as the default for an AI mode ([`SectionPromptTemplates.vue`](../../frontend/src/components/settings/SectionPromptTemplates.vue)).
- Manage login accounts (add, role toggle, enable/disable, password reset, delete) ([`SectionAuthUsers.vue`](../../frontend/src/components/settings/SectionAuthUsers.vue)).
- Recover or permanently purge soft-deleted sessions ([`SectionDeleted.vue`](../../frontend/src/components/settings/SectionDeleted.vue)).

## User Value

- **Configuration without deploys.** Org name, locale, time zone, default model, upload transport, classifier routing, and the active Gemini transcript prompt are all editable at runtime and read by the pipeline / other views (e.g. the default AI model is read by Upload — [`SectionAIModels.vue:43-45`](../../frontend/src/components/settings/SectionAIModels.vue#L43-L45)).
- **Live SSOT for the Gemini prompt.** Editing a prompt template marked `default_for_mode='transcript'` immediately changes what Gemini receives on the next upload, because [`app/prompts.py::get_prompt_for_mode`](../../app/prompts.py#L131) reads `prompt_templates` on the hot path ([`migration 049`](../../migrations/049_prompt_templates_default_for_mode.sql#L1-L20)).
- **Self-service login administration** with bcrypt-at-rest passwords and a reset-only model — passwords are never displayed ([`SectionAuthUsers.vue:3-16`](../../frontend/src/components/settings/SectionAuthUsers.vue#L3-L16)).
- **Stale-state recovery.** Empty auth-users table can be reseeded from the `AUTH_USERS` env in one click; leaked rate-limit slots can be swept from Diagnostics.
- **30-day recoverability** for deleted sessions before only ledger entries remain ([`SectionDeleted.vue:98-99`](../../frontend/src/components/settings/SectionDeleted.vue#L98-L99)).

## Navigation

- Route: `/settings/:section?` registered in [`router/index.ts:40`](../../frontend/src/router/index.ts#L40) as a hash route (`createWebHashHistory`), `props: true`.
- The optional `:section` param drives the active pane; when absent it defaults to `general` ([`SettingsView.vue:54`](../../frontend/src/views/SettingsView.vue#L54)).
- Clicking a nav item calls `router.push('/settings/<id>')`, keeping each section deep-linkable ([`SettingsView.vue:56-58`](../../frontend/src/views/SettingsView.vue#L56-L58)).
- An unknown section value falls through to `SectionGeneral` ([`SettingsView.vue:88`](../../frontend/src/views/SettingsView.vue#L88)).
- **There is no `adminOnly` route guard on `/settings`.** The only `adminOnly` route in the router is `/admin/help` ([`router/index.ts:44`](../../frontend/src/router/index.ts#L44)); the guard at [`router/index.ts:63`](../../frontend/src/router/index.ts#L63) only redirects when `to.meta.adminOnly` is set, which Settings does not set. Any authenticated user can open any Settings section; access control is enforced (where it exists) by the backend per endpoint. See **Permissions**.

## Screens

Each "screen" is a section component rendered into `.settings-content`.

### General — [`SectionGeneral.vue`](../../frontend/src/components/settings/SectionGeneral.vue)
Three controls: Organisation name (text), Default locale (`en-US`/`en-GB`/`es-ES`), Time zone (4 options). On mount, reads `org_name`, `default_locale`, `default_timezone` from `GET /v1/settings`; a single Save button writes all three via three parallel `PUT /v1/settings/{key}` calls.

> **Flag — key-name drift:** the seed in [`migration 006`](../../migrations/006_settings.sql#L11-L20) seeds the time-zone default under key `time_zone`, but the component reads/writes `default_timezone` ([`SectionGeneral.vue:23,37`](../../frontend/src/components/settings/SectionGeneral.vue#L23)). The seeded `time_zone` row is therefore never read by this screen; the screen persists its own `default_timezone` key on first save and falls back to the in-component default `America/Chicago` otherwise.

### Team & roles — [`SectionTeam.vue`](../../frontend/src/components/settings/SectionTeam.vue)
Two panes. **People**: inline add form (name + email required, optional role from a datalist of distinct existing roles merged with a baseline set, plus a chip-color picker), inline edit (name/email/role/color), and delete (soft via `is_active=FALSE`). **Groups**: add by name, rename, delete (hard), and per-group member chips with add/remove. Hydrates people, groups, and a bulk members map in parallel.

### Types & stage defaults — [`SectionTypes.vue`](../../frontend/src/components/settings/SectionTypes.vue)
Two panes. **Type list**: add a Type, click to select, remove (the default Type / code `default` shows a DEFAULT pill and cannot be removed — Remove button hidden). **Stage matrix**: 8 SOP stages, each with an assignee dropdown (people + `Group: <name>` + `(unassigned)`) and an Email notify checkbox. "Save matrix" replaces all 8 rows for the active Type. The 8 stages come from `SOP_STAGE_KEYS` ([`fixtures/settings.ts:34-43`](../../frontend/src/fixtures/settings.ts#L34-L43)): prep, copy_draft, medical, copy_final, cms, captions, qa, complete.

### AI models — [`SectionAIModels.vue`](../../frontend/src/components/settings/SectionAIModels.vue)
Single select for `default_ai_model`, options from the `AI_MODELS` fixture ([`fixtures/settings.ts:21-31`](../../frontend/src/fixtures/settings.ts#L21-L31)). Saves on change (no separate Save button).

### Upload & storage — [`SectionUpload.vue`](../../frontend/src/components/settings/SectionUpload.vue)
Single select for `upload_backend`: `gcs` (direct) or `railway` (server-routed). Saves on change with optimistic revert on failure.

### Discrepancy classification — [`SectionDiscrepancy.vue`](../../frontend/src/components/settings/SectionDiscrepancy.vue)
Two selects: `classify_backend` (`gemini-dev` / `vertex`) and `classify_model` (from `AI_MODELS`). Each saves independently on change. A static callout notes "Default: Gemini 2.0 Flash; switch to Vertex on persistent 503s."

### Export — [`SectionExport.vue`](../../frontend/src/components/settings/SectionExport.vue)
A toggle for `export_include_keypoints` and a "Download (.zip)" button that calls `GET /v1/settings/export/macro` (fetch+blob). 404 `MACRO_NOT_FOUND` surfaces a clean "not deployed" toast.

> **Flag — key-name drift:** [`migration 006`](../../migrations/006_settings.sql#L11-L20) seeds `include_key_points`, but this screen reads/writes `export_include_keypoints` ([`SectionExport.vue:20,32`](../../frontend/src/components/settings/SectionExport.vue#L20)). The seeded `include_key_points` value is not read here.

### Prompt templates — [`SectionPromptTemplates.vue`](../../frontend/src/components/settings/SectionPromptTemplates.vue)
Catalog of two kinds: **Processing** (STT/IIL presets, grouped by category Education/Technical/Conversational/Business/Custom) and **AI Prompt** (Gemini system prompts). Per card: Edit, Duplicate, and Delete (Delete hidden for system templates). A New/Edit form supports the processing config (filler policy, tone, terminology, rewrite level, structure/key-points toggles) or, for ai_prompt, the system-prompt textarea + a "Default for" mode binding (transcript/summary/key-moments/structured-notes, or unbound).

### Session manifest — [`SectionManifest.vue`](../../frontend/src/components/settings/SectionManifest.vue)
**Static reference only.** Documents the expected `extras2.txt` fields and filename conventions. No backend calls, no editable state.

### Email — [`SectionEmail.vue`](../../frontend/src/components/settings/SectionEmail.vue)
Home view with two static info cards (stage triggers live in the Types matrix; admin test-email lives in Diagnostics) plus an "Open builder" CTA that swaps to `EmailBuilder.vue`. The builder edits per-Type × per-Stage HTML templates via the `/v1/email-templates` router (migration 048) and reuses the email-debug send endpoint for test sends ([`EmailBuilder.vue:3-16`](../../frontend/src/components/settings/EmailBuilder.vue#L3-L16)).

### Auth & logins — [`SectionAuthUsers.vue`](../../frontend/src/components/settings/SectionAuthUsers.vue)
Add-login form (email + initial password min 10 chars + role), a user table (email, role chip, status chip, last login, password-set timestamp), per-row actions (Reset password modal, Make user/admin, Disable/Enable, Delete), and an empty-state recovery panel offering "Seed from AUTH_USERS env". On a 403 from the list call, surfaces "Admin only — your account does not have access."

### Diagnostics — [`SectionDiagnostics.vue`](../../frontend/src/components/settings/SectionDiagnostics.vue)
Home view with cards for telemetry counters, GCS QA (drill into `GCSDebug.vue`), test email (drill into `EmailDebug.vue`), links to standalone `/upload-test.html` and `/process-test.html` diagnostic pages, and a "Reset my stale slots" button calling the clear-rate-limit-slots diag endpoint.

> **Flag — illustrative telemetry:** the counter values shown in the telemetry and GCS cards (`longtasks/min: 1`, `heap: 108 MB`, `WS RTT: 18ms`, `99.98%` uptime, `Failing G13`, etc.) are hardcoded literals in the template ([`SectionDiagnostics.vue:49-61`](../../frontend/src/components/settings/SectionDiagnostics.vue#L49-L61)), not live values. **NOT VERIFIED IN CODE** as live telemetry.

### Deleted sessions — [`SectionDeleted.vue`](../../frontend/src/components/settings/SectionDeleted.vue)
Lists soft-deleted sessions (`GET /v1/sessions/deleted`), each with Restore and "Purge now". A 403 renders an "Admin-only" banner with no rows. 30-day elapsed counter per row.

## User Flows

### Save General settings
1. Operator opens `/settings/general`; component hydrates from `GET /v1/settings`.
2. Edits name / locale / time zone; clicks Save.
3. Three `PUT /v1/settings/{key}` calls fire in parallel ([`SectionGeneral.vue:34-38`](../../frontend/src/components/settings/SectionGeneral.vue#L34-L38)); success toast on completion.

### Add a person and assign them to a stage
1. In Team, fill name + valid email (button stays disabled until both are valid), pick a role/color, click "Add person" → `POST /v1/settings/people` ([`SectionTeam.vue:145-150`](../../frontend/src/components/settings/SectionTeam.vue#L145-L150)).
2. In Types, select a Type; the person now appears in each stage's assignee dropdown (the dropdown hydrates from `/v1/settings/people`).
3. Choose the person for one or more stages, optionally check Email, click "Save matrix" → `PUT /v1/settings/types/{id}/assignees` with all 8 stages ([`SectionTypes.vue:174-179`](../../frontend/src/components/settings/SectionTypes.vue#L174-L179)).

### Bind a Gemini prompt as the transcript default
1. In Prompt templates, edit (or create) an `ai_prompt` template, set "Default for" = `transcript`.
2. Save → `PUT` (or `POST`) `/v1/settings/templates` with `default_for_mode='transcript'`.
3. The next upload's Gemini call reads that template's `system_prompt` via `get_prompt_for_mode` ([`app/prompts.py:165-172`](../../app/prompts.py#L165-L172)).
4. If another active template already holds the `transcript` slot, the backend returns 409 `DEFAULT_MODE_TAKEN` naming the conflicting template ([`settings.py:906-916`](../../app/api/settings.py#L906-L916)).

### Add a login and reset a password
1. In Auth & logins, enter email + password (min 10) + role; submit → `POST /v1/settings/auth-users` ([`SectionAuthUsers.vue:128`](../../frontend/src/components/settings/SectionAuthUsers.vue#L128)).
2. To reset, click "Reset password", type a new password (min 10), submit → `POST /v1/settings/auth-users/{id}/reset-password`. The response returns only `email` + `password_reset_at`; the plaintext is never echoed ([`settings.py:632-635`](../../app/api/settings.py#L632-L635)).

### Recover a deleted session
1. In Deleted sessions, click Restore (`POST` restore) or "Purge now" (permanent delete) on a row.
2. Both prompt a confirm; non-admins get a 403 and the Admin-only banner ([`SectionDeleted.vue:29-31`](../../frontend/src/components/settings/SectionDeleted.vue#L29-L31)).

## Business Rules

| Rule | Where enforced | Evidence |
|---|---|---|
| **One default Type per org; it cannot be deleted.** | DB partial unique index + server check | `session_types_is_default_uq` ([`migration 038:18-19`](../../migrations/038_session_types_is_default.sql#L18-L19)); server 409 `DEFAULT_TYPE_LOCKED` ([`settings.py:341-348`](../../app/api/settings.py#L341-L348)); UI hides Remove on default row ([`SectionTypes.vue:212-216`](../../frontend/src/components/settings/SectionTypes.vue#L212-L216)). |
| **Last active admin cannot be demoted, disabled, or deleted.** | Server | 409 `LAST_ADMIN_PROTECTED` on update ([`settings.py:584-593`](../../app/api/settings.py#L584-L593)) and delete ([`settings.py:651-660`](../../app/api/settings.py#L651-L660)); count via `_count_active_admins` ([`settings.py:513-516`](../../app/api/settings.py#L513-L516)). |
| **Auth-user role must be `admin` or `user`.** | Server | 400 `BAD_ROLE` ([`settings.py:539-540`, `577-578`](../../app/api/settings.py#L539-L540)). |
| **One prompt template default per AI mode.** | DB partial unique index + server | `prompt_templates_default_for_mode_uq` ([`migration 049:44-46`](../../migrations/049_prompt_templates_default_for_mode.sql#L44-L46)); 409 `DEFAULT_MODE_TAKEN` ([`settings.py:906`, `975`](../../app/api/settings.py#L906)). |
| **Only `ai_prompt` templates may be marked `default_for_mode`.** | Server | 400 `DEFAULT_REQUIRES_AI_PROMPT` ([`settings.py:879-884`](../../app/api/settings.py#L879-L884)). |
| **`default_for_mode` must be one of transcript/summary/key-moments/structured-notes (or null).** | Server + DB CHECK | `_validate_default_for_mode` 400 `INVALID_DEFAULT_FOR_MODE` ([`settings.py:809-819`](../../app/api/settings.py#L809-L819)); CHECK in [`migration 049:34-38`](../../migrations/049_prompt_templates_default_for_mode.sql#L34-L38). |
| **System prompt templates can be edited but not deleted.** | Server | Delete returns 409 `SYSTEM_TEMPLATE_LOCKED` for `is_system` rows ([`settings.py:1022-1027`](../../app/api/settings.py#L1022-L1027)); UI hides Delete on system cards ([`SectionPromptTemplates.vue:351`](../../frontend/src/components/settings/SectionPromptTemplates.vue#L351)). |
| **Template delete is a soft-delete** (`is_active=FALSE`) so version + audit history stay queryable. | Server | [`settings.py:1011-1036`](../../app/api/settings.py#L1011-L1036). |
| **Person delete is a soft-delete** (`is_active=FALSE`); group delete is a hard delete (members cascade). | Server | [`settings.py:114-121`](../../app/api/settings.py#L114-L121) (person), [`settings.py:213-228`](../../app/api/settings.py#L213-L228) (group). |
| **Person/group add are upserts** (`ON CONFLICT DO UPDATE`); group-member add is idempotent (`ON CONFLICT DO NOTHING`). | Server | [`settings.py:102-106`](../../app/api/settings.py#L102-L106), [`settings.py:171-175`](../../app/api/settings.py#L171-L175), [`settings.py:274-277`](../../app/api/settings.py#L274-L277). |
| **Setting key in URL must match key in body.** | Server | 400 "Key mismatch" ([`settings.py:76-77`](../../app/api/settings.py#L76-L77)). |
| **Saving the stage matrix drops unassigned/`(unassigned)` rows.** | Server + UI | server skips empty/unassigned ([`settings.py:440-441`](../../app/api/settings.py#L440-L441)); UI filters out empty emails before sending ([`SectionTypes.vue:178`](../../frontend/src/components/settings/SectionTypes.vue#L178)). |
| **Deleted sessions are recoverable for 30 days.** | UI copy + window | [`SectionDeleted.vue:98-99`](../../frontend/src/components/settings/SectionDeleted.vue#L98-L99). The 30-day window itself is enforced by the sessions module, not Settings. **NOT VERIFIED IN CODE** here (outside this module). |

## Validation Rules

- **People add (UI):** name non-empty AND email matches `/^[^@\s]+@[^@\s]+\.[^@\s]+$/` ([`SectionTeam.vue:70-77`](../../frontend/src/components/settings/SectionTeam.vue#L70-L77)). Email lowercased before send ([`SectionTeam.vue:147`](../../frontend/src/components/settings/SectionTeam.vue#L147)); server also lowercases ([`settings.py:106`](../../app/api/settings.py#L106)).
- **Auth-user password:** min 10 chars enforced both client-side (button disabled, hint text — [`SectionAuthUsers.vue:42-51`](../../frontend/src/components/settings/SectionAuthUsers.vue#L42-L51)) and server-side (Pydantic `min_length=10, max_length=256` — [`settings.py:483-484`, `496`](../../app/api/settings.py#L483-L484)).
- **Auth-user email:** Pydantic `min_length=3, max_length=255` ([`settings.py:483`](../../app/api/settings.py#L483)); lowercased + stripped on insert ([`settings.py:551`](../../app/api/settings.py#L551)); duplicate → 409 `DUPLICATE_EMAIL` ([`settings.py:554-558`](../../app/api/settings.py#L554-L558)).
- **Type code:** Pydantic `min_length=1, max_length=128` ([`settings.py:53`](../../app/api/settings.py#L53)); label defaults to code if absent ([`settings.py:327`](../../app/api/settings.py#L327)).
- **Stage assignee row:** `stage` 1–64 chars, `assignee_email` 1–255 chars ([`settings.py:57-60`](../../app/api/settings.py#L57-L60)).
- **Template name:** Pydantic `min_length=1, max_length=120` ([`settings.py:767`](../../app/api/settings.py#L767)); duplicate (case-insensitive index) → 409 `DUPLICATE_NAME` ([`settings.py:917-921`](../../app/api/settings.py#L917-L921)).
- **Template kind:** must be `processing` or `ai_prompt` → 400 `INVALID_KIND` ([`settings.py:873-877`](../../app/api/settings.py#L873-L877)).
- **People/group/auth-user PUT with no fields:** 400 "No updatable fields provided" ([`settings.py:132-133`](../../app/api/settings.py#L132-L133), [`187-188`](../../app/api/settings.py#L187-L188), [`574-575`](../../app/api/settings.py#L574-L575)). Template PUT with no fields: 400 `NO_CHANGES` ([`settings.py:959-960`](../../app/api/settings.py#L959-L960)).
- **Person email duplicate on update:** 409 `DUPLICATE_EMAIL` ([`settings.py:148-152`](../../app/api/settings.py#L148-L152)); group name duplicate: 409 `DUPLICATE_NAME` ([`settings.py:198-202`](../../app/api/settings.py#L198-L202)).

## States

- **Loading:** every data-backed section has a `loading` ref; Auth & logins and Team render an explicit "Loading…" block ([`SectionAuthUsers.vue:267-269`](../../frontend/src/components/settings/SectionAuthUsers.vue#L267-L269), [`SectionTeam.vue:324`](../../frontend/src/components/settings/SectionTeam.vue#L324)).
- **Empty (auth-users):** when `users.length === 0`, a dashed-border recovery panel offers the env reseed ([`SectionAuthUsers.vue:329-358`](../../frontend/src/components/settings/SectionAuthUsers.vue#L329-L358)).
- **Empty (deleted):** "No deleted sessions in the 30-day window." ([`SectionDeleted.vue:134-138`](../../frontend/src/components/settings/SectionDeleted.vue#L134-L138)).
- **Forbidden:** auth-users and deleted sessions catch 403 and render an admin-only message instead of erroring ([`SectionAuthUsers.vue:81-83`](../../frontend/src/components/settings/SectionAuthUsers.vue#L81-L83), [`SectionDeleted.vue:29-31`](../../frontend/src/components/settings/SectionDeleted.vue#L29-L31)).
- **Saving / busy:** buttons disable and show "Saving…"/"Adding…"/"Working…" during in-flight calls; per-row busy sets prevent double-fire in Auth & logins ([`SectionAuthUsers.vue:66-74`](../../frontend/src/components/settings/SectionAuthUsers.vue#L66-L74)).
- **Optimistic with revert:** Upload and Export revert the local value on save failure ([`SectionUpload.vue:38-41`](../../frontend/src/components/settings/SectionUpload.vue#L38-L41), [`SectionExport.vue:34-37`](../../frontend/src/components/settings/SectionExport.vue#L34-L37)).
- **Fixture-only Type rows:** Types may show fixture rows with `id: null` before persistence; saving the matrix on such a row warns "Type not yet persisted — Add it first." ([`SectionTypes.vue:168-170`](../../frontend/src/components/settings/SectionTypes.vue#L168-L170)).

## Dependencies

- **Backend router:** `/v1/settings/*` ([`app/api/settings.py`](../../app/api/settings.py)), mounted at [`app/main.py:226`](../../app/main.py#L226).
- **Email builder backend:** `/v1/email-templates` router, mounted at [`app/main.py:229`](../../app/main.py#L229) — separate from `settings.py`.
- **Auth dependency:** every endpoint takes `CurrentUser` (JWT) ([`app/auth.py:208`](../../app/auth.py#L208)).
- **Password hashing service:** `app/services/auth_users.hash_password` ([`settings.py:542`](../../app/api/settings.py#L542)).
- **Prompt pipeline consumer:** `app/prompts.py::get_prompt_for_mode` reads `prompt_templates.default_for_mode` on every upload ([`app/prompts.py:131-172`](../../app/prompts.py#L131-L172)).
- **Fixtures:** `SESSION_TYPES`, `AI_MODELS`, `SOP_STAGE_KEYS` ([`fixtures/settings.ts`](../../frontend/src/fixtures/settings.ts)).
- **Macro bundle:** `GET /v1/settings/export/macro` serves a zip built on the fly from `docs/macros/` in the repo ([`settings.py:680-746`](../../app/api/settings.py#L680-L746)).
- **Diagnostics:** drill-ins `GCSDebug.vue`, `EmailDebug.vue`, and the `diag.clearRateLimitSlots` / `diag.reseedAuthUsers` API calls.
- **Composables:** `useToast`, `useConfirm`; HTTP layer `services/http.ts` (`ApiError`) and `services/api.ts` (`settingsApi`).

## Error Handling

- API errors are normalized to `ApiError` with a `body` carrying the FastAPI `detail`. Sections unwrap `detail.code` / `detail.message` to show human-readable toasts ([`SectionTeam.vue:123-137`](../../frontend/src/components/settings/SectionTeam.vue#L123-L137), [`SectionAuthUsers.vue:97-112`](../../frontend/src/components/settings/SectionAuthUsers.vue#L97-L112)).
- 403 is special-cased to an "admin-only" message (Auth & logins, Deleted sessions) rather than a generic error.
- Macro download 404 `MACRO_NOT_FOUND` shows a "not deployed" warn toast ([`SectionExport.vue:51-57`](../../frontend/src/components/settings/SectionExport.vue#L51-L57)).
- Server error codes surfaced to users: `DEFAULT_TYPE_LOCKED`, `LAST_ADMIN_PROTECTED`, `BAD_ROLE`, `DUPLICATE_EMAIL`, `DUPLICATE_NAME`, `DEFAULT_MODE_TAKEN`, `INVALID_KIND`, `INVALID_DEFAULT_FOR_MODE`, `DEFAULT_REQUIRES_AI_PROMPT`, `SYSTEM_TEMPLATE_LOCKED`, `NO_CHANGES`, `MACRO_NOT_FOUND` (all in [`settings.py`](../../app/api/settings.py)).
- Hydration is defensive: Team/Types wrap each fetch in `.catch(() => [])` so one broken endpoint doesn't blank the whole page ([`SectionTeam.vue:103-108`](../../frontend/src/components/settings/SectionTeam.vue#L103-L108), [`SectionTypes.vue:105-109`](../../frontend/src/components/settings/SectionTypes.vue#L105-L109)).

## Permissions

**Authoritative description of what is actually enforced today.**

- **Real authorization = JWT presence + a hardcoded admin-email gate.** Every `/v1/settings/*` endpoint requires a valid JWT via the `CurrentUser` dependency ([`app/auth.py:172-208`](../../app/auth.py#L172-L208)). There is no per-user role on the `User` object — `get_current_user` only sets `email` ([`app/auth.py:36-39`, `203`](../../app/auth.py#L36-L39)).
- **`require_admin` reduces to the `LEGACY_ADMIN_EMAIL` gate in this module.** `settings.py` imports and calls `require_admin(user)` ([`settings.py:15`](../../app/api/settings.py#L15)), but always **without** the `role` keyword. With `role=None`, `is_admin` falls back to `user.email == "johndean@vin.com"` ([`roles.py:62-92`](../../app/security/roles.py#L62-L92)). `auth_users.role` (migration 045) is **not** read by `get_current_user`, so role tiers are not active — the effective admin is the single hardcoded email.
- **Admin-gated endpoints** (call `require_admin`, hence email-gated): add/remove Type ([`settings.py:322`, `337`](../../app/api/settings.py#L322)), set type assignees ([`settings.py:431`](../../app/api/settings.py#L431)), all auth-users endpoints ([`settings.py:531`, `538`, `571`, `617`, `647`](../../app/api/settings.py#L531)), and all template create/update/delete ([`settings.py:872`, `938`, `1016`](../../app/api/settings.py#L872)).
- **NOT admin-gated** (any authenticated user): `GET/PUT /v1/settings` org k/v ([`settings.py:68`, `74`](../../app/api/settings.py#L68)), all people CRUD ([`settings.py:93`, `101`, `115`, `125`](../../app/api/settings.py#L93)), all groups + members CRUD ([`settings.py:164`, `170`, `184`, `214`, `232`, `269`, `291`](../../app/api/settings.py#L164)), `GET /types` and `GET /types/{id}/assignees` ([`settings.py:309`, `409`](../../app/api/settings.py#L309)), `GET /templates*` ([`settings.py:835`, `856`](../../app/api/settings.py#L835)), and macro download ([`settings.py:681`](../../app/api/settings.py#L681), explicitly "No admin gate" per its docstring).
- **Client-side guard does NOT cover Settings.** The `adminOnly` guard at [`router/index.ts:63`](../../frontend/src/router/index.ts#L63) only fires for routes with `meta.adminOnly` — that is the `/admin/help` route only ([`router/index.ts:44`](../../frontend/src/router/index.ts#L44)). Settings sets no such meta, so the nav and all sections are reachable by any authenticated user; the auth-users/deleted sections rely on the backend 403 to gate content.

## Reporting Impacts

- **No reporting/analytics surface is produced by Settings.** Settings has no charts, exports of metrics, or aggregate reports. **IMPLEMENTATION NOT FOUND** for any reporting feature within this module.
- The only counters shown (Diagnostics telemetry / GCS uptime) are hardcoded display literals, not data ([`SectionDiagnostics.vue:49-61`](../../frontend/src/components/settings/SectionDiagnostics.vue#L49-L61)).
- Indirect reporting input: Settings changes are recorded in `audit_events` (see Audit Requirements), which the separate Audit view can surface.

## Audit Requirements

Most write operations insert a row into `audit_events (actor_email, kind, summary)` and commit in the same transaction. Verified `kind` values emitted by `settings.py`:

| Action | `kind` | Evidence |
|---|---|---|
| Set org setting | `settings.set` | [`settings.py:84-86`](../../app/api/settings.py#L84-L86) |
| Add person | `settings.people.add` | [`settings.py:107-109`](../../app/api/settings.py#L107-L109) |
| Deactivate person | `settings.people.remove` | [`settings.py:117-119`](../../app/api/settings.py#L117-L119) |
| Update person | `settings.people.update` | [`settings.py:156-158`](../../app/api/settings.py#L156-L158) |
| Add group | `settings.groups.add` | [`settings.py:176-178`](../../app/api/settings.py#L176-L178) |
| Update group | `settings.groups.update` | [`settings.py:206-208`](../../app/api/settings.py#L206-L208) |
| Remove group | `settings.groups.remove` | [`settings.py:224-226`](../../app/api/settings.py#L224-L226) |
| Add group member | `settings.groups.member_add` | [`settings.py:283-285`](../../app/api/settings.py#L283-L285) |
| Remove group member | `settings.groups.member_remove` | [`settings.py:300-302`](../../app/api/settings.py#L300-L302) |
| Add Type | `settings.types.add` | [`settings.py:328-330`](../../app/api/settings.py#L328-L330) |
| Remove Type | `settings.types.remove` | [`settings.py:351-353`](../../app/api/settings.py#L351-L353) |
| Save stage matrix | `settings.types.assignees` | [`settings.py:455-457`](../../app/api/settings.py#L455-L457) |
| Add auth user | `settings.auth_user.add` | [`settings.py:561-564`](../../app/api/settings.py#L561-L564) |
| Update auth user | `settings.auth_user.update` | [`settings.py:605-608`](../../app/api/settings.py#L605-L608) |
| Reset password | `settings.auth_user.reset_password` | [`settings.py:627-630`](../../app/api/settings.py#L627-L630) |
| Delete auth user | `settings.auth_user.delete` | [`settings.py:663-666`](../../app/api/settings.py#L663-L666) |
| Macro download | `settings.export.macro_download` | [`settings.py:731-737`](../../app/api/settings.py#L731-L737) |
| Add template | `settings.templates.add` | [`settings.py:923-927`](../../app/api/settings.py#L923-L927) |
| Update template | `settings.templates.update` | [`settings.py:1003-1006`](../../app/api/settings.py#L1003-L1006) |
| Remove template | `settings.templates.remove` | [`settings.py:1031-1034`](../../app/api/settings.py#L1031-L1034) |

Notes: the macro-download audit insert is wrapped in a try/except that swallows failures so a logging error can't block the download ([`settings.py:730-740`](../../app/api/settings.py#L730-L740)). Template-update audit summaries explicitly call out `default_for_mode` set/clear changes ([`settings.py:997-1002`](../../app/api/settings.py#L997-L1002)).

## Data Relationships

- `org_settings` — flat key → JSONB value, with `updated_by` / `updated_at` ([`migration 006:3-8`](../../migrations/006_settings.sql#L3-L8)).
- `people` (1) ──< `group_members` >── (1) `groups`. `group_members` FKs cascade-delete on both sides ([`migration 006:40-44`](../../migrations/006_settings.sql#L40-L44)).
- `session_types` (1) ──< `stage_assignees` (one row per (type_id, stage), unique). `stage_assignees` also carries nullable `person_id` / `group_id` typed FKs (added by [`migration 040`](../../migrations/040_stage_assignees_typed_fk.sql)) that `ON DELETE SET NULL` and a CHECK that at most one of person/group is set ([`migration 040:17-35`](../../migrations/040_stage_assignees_typed_fk.sql#L17-L35)). `stage_assignees` cascade-deletes when its Type is deleted ([`migration 006:54-61`](../../migrations/006_settings.sql#L54-L61)).
- `email_templates` — one active row per (session_type_id, stage_id, locale); NULL `session_type_id` = default-for-all-types; `session_type_id` FK cascades on Type delete ([`migration 048:28-53`](../../migrations/048_email_templates.sql#L28-L53)). Reshaped from the legacy 006 schema by migration 048 (which `DROP TABLE`s the empty legacy table first).
- `prompt_templates` — single table with JSONB `config`; `is_system` (lockable), `is_active` (soft-delete), `version`, and nullable `default_for_mode` with a partial unique index (one default per mode among active rows) ([`migration 047`](../../migrations/047_prompt_templates.sql), [`migration 049`](../../migrations/049_prompt_templates_default_for_mode.sql)). Replaced the legacy 006 `prompt_templates` table (DROP + recreate in 047).
- `auth_users` — login accounts; unique on `lower(email)`; carries `role`, `is_active`, `last_login_at`, `password_reset_at` ([`migration 045`](../../migrations/045_auth_users.sql)).
- `audit_events` — append-only sink for all settings mutations (see Audit Requirements).

### Seed data
- 17 session Types seeded ([`migration 031`](../../migrations/031_seed_settings_types.sql), [`migration 039`](../../migrations/039_seed_session_types.sql)); the `default` code row promoted to `is_default=TRUE` ([`migration 038:23-25`](../../migrations/038_session_types_is_default.sql#L23-L25)).
- 10 people + 5 groups + memberships seeded ([`migration 032`](../../migrations/032_seed_people_and_groups.sql)).
- 6 processing + 2 ai_prompt templates seeded ([`migration 047:64-90`](../../migrations/047_prompt_templates.sql#L64-L90)); the `Transcript` ai_prompt row bound to `transcript` mode ([`migration 049:57-62`](../../migrations/049_prompt_templates_default_for_mode.sql#L57-L62)) and its body replaced with the verbatim MIC transcript prompt ([`migration 050`](../../migrations/050_seed_mic_transcript_prompt.sql)).
- 8 default email templates (one per SOP stage) seeded ([`migration 048:64-90`](../../migrations/048_email_templates.sql#L64-L90)).

> **Flag — seed-vs-current discrepancies:** [`migration 031`](../../migrations/031_seed_settings_types.sql#L8) seeds the default Type label as lowercase `'default'`; [`migration 039`](../../migrations/039_seed_session_types.sql#L11) seeds it as `'Default'`. Because both use `ON CONFLICT (code) DO NOTHING`, whichever runs first wins on a fresh DB; 031 runs first so the persisted label is `'default'`. Also, the `org_settings` seed keys `time_zone` and `include_key_points` ([`migration 006:14,19`](../../migrations/006_settings.sql#L14)) are NOT the keys the General/Export screens read (`default_timezone`, `export_include_keypoints`) — see Screens flags.

## Known Constraints

- **Single hardcoded admin.** Admin power across Settings is gated by `user.email == "johndean@vin.com"`; there is no working role tier despite `auth_users.role` existing and being editable in the UI. Editing a user's role in Auth & logins updates the DB column but does not grant/revoke admin at runtime, because `get_current_user` never loads that column ([`roles.py:10-19`](../../app/security/roles.py#L10-L19), [`app/auth.py:203`](../../app/auth.py#L203)). **PARTIALLY IMPLEMENTED** role system.
- **Org k/v and people/groups are unguarded.** Any authenticated user can change `org_name`, locale, time zone, default model, upload backend, classifier routing, and the entire team roster — no admin check (see Permissions).
- **Settings route has no client guard.** Even sections that are backend-admin-gated render their chrome to any user; the gate is only the resulting 403.
- **Manifest section is documentation only** — no editable state or backend ([`SectionManifest.vue`](../../frontend/src/components/settings/SectionManifest.vue)).
- **Diagnostics telemetry is illustrative,** not live (see Reporting Impacts).
- **Macro bundle depends on repo contents.** `GET /v1/settings/export/macro` 404s with `MACRO_NOT_FOUND` unless files exist under `docs/macros/` in the deployed repo ([`settings.py:696-720`](../../app/api/settings.py#L696-L720)).
- **Email-template stage-transition firing is out of scope of migration 048** — that migration ships only the table + 8 default rows; the Celery hook that sends on stage advance is explicitly separate ([`migration 048:23-26`](../../migrations/048_email_templates.sql#L23-L26)). **NOT VERIFIED IN CODE** within this module.

## Source Verification
- **Files Used:** `frontend/src/views/SettingsView.vue`; `frontend/src/components/settings/{SectionGeneral,SectionTeam,SectionTypes,SectionAIModels,SectionUpload,SectionDiscrepancy,SectionExport,SectionPromptTemplates,SectionManifest,SectionEmail,SectionAuthUsers,SectionDiagnostics,SectionDeleted,EmailBuilder}.vue`; `frontend/src/fixtures/settings.ts`; `frontend/src/services/api.ts`; `frontend/src/router/index.ts`; `app/api/settings.py`; `app/auth.py`; `app/security/roles.py`; `app/prompts.py`; `app/main.py`; `migrations/{006,031,032,038,039,040,045,047,048,049,050}*.sql`
- **Components Used:** SettingsView + 13 section components + EmailBuilder
- **APIs Used:** `/v1/settings` (GET/PUT), `/v1/settings/people` (GET/POST/PUT/DELETE), `/v1/settings/groups` (+ members + bulk), `/v1/settings/types` (+ `/{id}/assignees` GET/PUT), `/v1/settings/templates` (GET/POST/PUT/DELETE), `/v1/settings/auth-users` (+ reset-password), `/v1/settings/export/macro` (GET); `/v1/email-templates` (separate router); diag endpoints `clear-rate-limit-slots`, `reseed-auth-users`
- **Database Tables Used:** `org_settings`, `people`, `groups`, `group_members`, `session_types`, `stage_assignees`, `email_templates`, `prompt_templates`, `auth_users`, `audit_events`
- **Permission Logic Used:** JWT (`CurrentUser`) on every endpoint + `require_admin(user)` reducing to the `LEGACY_ADMIN_EMAIL` (`johndean@vin.com`) gate on Type/assignee/auth-user/template writes; org-k/v + people/groups unguarded; client router `adminOnly` guard does NOT apply to `/settings`
- **Confidence Score:** High — every claim cross-checked against current source; key-name drifts and the email-template firing scope are explicitly flagged as discrepancies/out-of-scope.
- **Evidence Links:** [`SettingsView.vue:38-52`](../../frontend/src/views/SettingsView.vue#L38-L52), [`settings.py:67-89`](../../app/api/settings.py#L67-L89), [`settings.py:336-355`](../../app/api/settings.py#L336-L355), [`settings.py:529-668`](../../app/api/settings.py#L529-L668), [`roles.py:62-92`](../../app/security/roles.py#L62-L92), [`app/auth.py:172-208`](../../app/auth.py#L172-L208), [`router/index.ts:53-68`](../../frontend/src/router/index.ts#L53-L68), [`migration 049:44-46`](../../migrations/049_prompt_templates_default_for_mode.sql#L44-L46)
