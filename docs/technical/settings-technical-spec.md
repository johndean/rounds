# Settings — Technical Specification

> Code-verified against the rounds.vin repository. Claims trace to source via the links provided. Unproven items are tagged **NOT VERIFIED IN CODE**, **IMPLEMENTATION NOT FOUND**, or **PARTIALLY IMPLEMENTED**. Paths are relative to this file at `docs/technical/`.

## Architecture

Settings is a Vue 3 (Composition API, `<script setup lang="ts">`) feature backed by a FastAPI router and Postgres. Layout:

```
Browser (Vue)                                  Backend (FastAPI + SQLAlchemy)        Postgres
─────────────                                  ──────────────────────────────       ─────────
SettingsView.vue  ──route /settings/:section──> /v1/settings/* (settings.py) ──────> org_settings
 ├─ 13 Section*.vue components                  /v1/email-templates (separate)        people / groups / group_members
 │   call settingsApi.* (services/api.ts) ───>  CurrentUser dep (auth.py, JWT)        session_types / stage_assignees
 │                                              require_admin (security/roles.py)     prompt_templates / email_templates
 └─ EmailBuilder.vue → emailTemplatesApi                                              auth_users / audit_events
```

- One route, `/settings/:section?`, hash-history, `props: true` ([`router/index.ts:40`](../../frontend/src/router/index.ts#L40)). The `section` prop selects which of 13 section components renders via `v-if/v-else-if` ([`SettingsView.vue:75-88`](../../frontend/src/views/SettingsView.vue#L75-L88)).
- The Vue layer is a faithful port of the React prototype (per repo CLAUDE.md); class names like `.settings-page`, `.settings-nav`, `.settings-content` are preserved ([`SettingsView.vue:62-90`](../../frontend/src/views/SettingsView.vue#L62-L90)).
- The backend router is async SQLAlchemy using raw `text()` SQL with bound params, committing per request and writing an `audit_events` row in the same transaction ([`app/api/settings.py`](../../app/api/settings.py)).

## Frontend Components

| Component | Backend it talks to | Notes |
|---|---|---|
| [`SettingsView.vue`](../../frontend/src/views/SettingsView.vue) | none (router only) | Section nav + content switch; default + fallback to `general`. |
| [`SectionGeneral.vue`](../../frontend/src/components/settings/SectionGeneral.vue) | `GET/PUT /v1/settings` | `org_name`, `default_locale`, `default_timezone`; one Save → 3 parallel PUTs. |
| [`SectionTeam.vue`](../../frontend/src/components/settings/SectionTeam.vue) | people/groups/members CRUD | inline add/edit/delete; bulk members hydrate. |
| [`SectionTypes.vue`](../../frontend/src/components/settings/SectionTypes.vue) | types + assignees | per-Type 8-stage matrix; per-Type client cache (`typeRowsCache`). |
| [`SectionAIModels.vue`](../../frontend/src/components/settings/SectionAIModels.vue) | `GET/PUT /v1/settings` | `default_ai_model`; saves on change. |
| [`SectionUpload.vue`](../../frontend/src/components/settings/SectionUpload.vue) | `GET/PUT /v1/settings` | `upload_backend`; optimistic+revert. |
| [`SectionDiscrepancy.vue`](../../frontend/src/components/settings/SectionDiscrepancy.vue) | `GET/PUT /v1/settings` | `classify_backend`, `classify_model`; each saves on change. |
| [`SectionExport.vue`](../../frontend/src/components/settings/SectionExport.vue) | `GET/PUT /v1/settings`, `GET /export/macro` | `export_include_keypoints` toggle + macro zip download (fetch+blob). |
| [`SectionPromptTemplates.vue`](../../frontend/src/components/settings/SectionPromptTemplates.vue) | templates CRUD | catalog + new/edit form; processing vs ai_prompt; default-for-mode binding. |
| [`SectionManifest.vue`](../../frontend/src/components/settings/SectionManifest.vue) | none | static reference of extras2 fields + filename conventions. |
| [`SectionEmail.vue`](../../frontend/src/components/settings/SectionEmail.vue) → [`EmailBuilder.vue`](../../frontend/src/components/settings/EmailBuilder.vue) | `/v1/email-templates`, email-debug send | resolve/save per-Type×stage HTML; test-send. |
| [`SectionAuthUsers.vue`](../../frontend/src/components/settings/SectionAuthUsers.vue) | auth-users CRUD + reset; diag reseed | table + add form + reset modal + empty-state reseed. |
| [`SectionDiagnostics.vue`](../../frontend/src/components/settings/SectionDiagnostics.vue) → `GCSDebug.vue`/`EmailDebug.vue` | diag clear-rate-limit-slots | mostly static cards + slot sweep; telemetry literals are hardcoded. |
| [`SectionDeleted.vue`](../../frontend/src/components/settings/SectionDeleted.vue) | `sessionsApi` deleted/restore/permanentDelete | not under settings router; 403 → admin-only banner. |

Shared sub-components: `SettingsHeader.vue`, `FormRow.vue`, `TogglePill.vue` (presentational only).

### State within a section
Typical pattern (Auth & logins, Team, Types, Prompt templates): `ref` for the data array + `loading` + per-item busy/edit refs; `onMounted(hydrate)`; mutating actions call `settingsApi.*`, then patch the local array and toast. Types maintains a client-side `typeRowsCache: Map<string, StageAssigneeRow[]>` keyed by type id, invalidated on save/remove ([`SectionTypes.vue:52`](../../frontend/src/components/settings/SectionTypes.vue#L52)).

## Backend Services

All in [`app/api/settings.py`](../../app/api/settings.py), router prefix `/v1/settings`, tag `settings` ([`settings.py:17`](../../app/api/settings.py#L17)), mounted at [`app/main.py:226`](../../app/main.py#L226).

Helpers:
- `_resolve_assignee(db, assignee_email)` → `(person_id, group_id, label)` — translates the UI's free-text assignee into typed FKs (`"Group: X"` → group, email → person, `(unassigned)`/empty → both NULL) ([`settings.py:358-384`](../../app/api/settings.py#L358-L384)).
- `_TYPE_ASSIGNEES_SELECT` — the read query that `COALESCE`s typed-FK display fields over legacy `assignee_email` so renames propagate and legacy rows still render ([`settings.py:387-405`](../../app/api/settings.py#L387-L405)).
- `_row_to_auth_user` — whitelist projection that NEVER includes `password_hash` ([`settings.py:499-510`](../../app/api/settings.py#L499-L510)).
- `_count_active_admins`, `_get_auth_user_or_404` — last-admin-guard support ([`settings.py:513-526`](../../app/api/settings.py#L513-L526)).
- `_row_to_template`, `_validate_default_for_mode`, `_resolve_default_mode_conflict` — template projection + validation + 409 enrichment ([`settings.py:791-831`](../../app/api/settings.py#L791-L831)).
- `hash_password` imported from `app/services/auth_users` for add + reset ([`settings.py:542`, `618`](../../app/api/settings.py#L542)).

Macro download builds a zip in memory by walking `docs/macros/` (repo root computed three levels up from `__file__`), 404s with `MACRO_NOT_FOUND` if the dir is missing or empty ([`settings.py:680-746`](../../app/api/settings.py#L680-L746)).

EmailBuilder's backend is the separate `email_templates` router, mounted at [`app/main.py:229`](../../app/main.py#L229); it is not part of `settings.py`.

## APIs

Prefix `/v1/settings` unless noted. All require `CurrentUser`. ✗ = no admin gate; ★ = calls `require_admin` (email-gated, see Permissions).

| Method | Path | Gate | Request | Response | Source |
|---|---|---|---|---|---|
| GET | `` | ✗ | — | `{key: value}` map | [`settings.py:67-70`](../../app/api/settings.py#L67-L70) |
| PUT | `/{key}` | ✗ | `SettingValue{key,value}` | echoes payload | [`settings.py:73-88`](../../app/api/settings.py#L73-L88) |
| GET | `/people` | ✗ | — | `[{id,email,name,role,avatar_color,is_active}]` | [`settings.py:92-97`](../../app/api/settings.py#L92-L97) |
| POST | `/people` | ✗ | `PersonPayload` | created row (upsert) | [`settings.py:100-111`](../../app/api/settings.py#L100-L111) |
| PUT | `/people/{id}` | ✗ | `PersonPatch` | updated row | [`settings.py:124-160`](../../app/api/settings.py#L124-L160) |
| DELETE | `/people/{id}` | ✗ | — | 204 (soft) | [`settings.py:114-121`](../../app/api/settings.py#L114-L121) |
| GET | `/groups` | ✗ | — | `[{id,name,description}]` | [`settings.py:163-166`](../../app/api/settings.py#L163-L166) |
| POST | `/groups` | ✗ | `GroupPayload` | created (upsert) | [`settings.py:169-180`](../../app/api/settings.py#L169-L180) |
| PUT | `/groups/{id}` | ✗ | `GroupPatch` | updated | [`settings.py:183-210`](../../app/api/settings.py#L183-L210) |
| DELETE | `/groups/{id}` | ✗ | — | 204 (hard, cascade) | [`settings.py:213-228`](../../app/api/settings.py#L213-L228) |
| GET | `/groups/{id}/members` | ✗ | — | `[person]` (active only) | [`settings.py:231-240`](../../app/api/settings.py#L231-L240) |
| GET | `/groups-members` | ✗ | — | `{group_id: [person]}` bulk | [`settings.py:243-265`](../../app/api/settings.py#L243-L265) |
| POST | `/groups/{gid}/members/{pid}` | ✗ | — | `{added:true}` (idempotent) | [`settings.py:268-287`](../../app/api/settings.py#L268-L287) |
| DELETE | `/groups/{gid}/members/{pid}` | ✗ | — | 204 | [`settings.py:290-304`](../../app/api/settings.py#L290-L304) |
| GET | `/types` | ✗ | — | `[{id,code,label,is_default}]` default-first | [`settings.py:308-317`](../../app/api/settings.py#L308-L317) |
| POST | `/types` | ★ | `TypePayload` | created (upsert) | [`settings.py:320-332`](../../app/api/settings.py#L320-L332) |
| DELETE | `/types/{id}` | ★ | — | 204 / 409 `DEFAULT_TYPE_LOCKED` | [`settings.py:335-355`](../../app/api/settings.py#L335-L355) |
| GET | `/types/{id}/assignees` | ✗ | — | `[{id,stage,notify_email,assignee_email,assignee_label,person_id,group_id}]` | [`settings.py:408-417`](../../app/api/settings.py#L408-L417) |
| PUT | `/types/{id}/assignees` | ★ | `StageAssigneeBulk{rows}` | new rows | [`settings.py:420-461`](../../app/api/settings.py#L420-L461) |
| GET | `/templates` | ✗ | `?kind=` | `[PromptTemplate]` | [`settings.py:834-852`](../../app/api/settings.py#L834-L852) |
| GET | `/templates/{id}` | ✗ | — | `PromptTemplate` / 404 | [`settings.py:855-864`](../../app/api/settings.py#L855-L864) |
| POST | `/templates` | ★ | `TemplateCreate` | created | [`settings.py:867-929`](../../app/api/settings.py#L867-L929) |
| PUT | `/templates/{id}` | ★ | `TemplatePatch` | updated (version+1) | [`settings.py:932-1008`](../../app/api/settings.py#L932-L1008) |
| DELETE | `/templates/{id}` | ★ | — | 204 (soft) / 409 system | [`settings.py:1011-1036`](../../app/api/settings.py#L1011-L1036) |
| GET | `/auth-users` | ★ | — | `[AuthUser]` (no hash) | [`settings.py:529-533`](../../app/api/settings.py#L529-L533) |
| POST | `/auth-users` | ★ | `AuthUserCreate` | created | [`settings.py:536-566`](../../app/api/settings.py#L536-L566) |
| PUT | `/auth-users/{id}` | ★ | `AuthUserPatch` | updated | [`settings.py:569-610`](../../app/api/settings.py#L569-L610) |
| POST | `/auth-users/{id}/reset-password` | ★ | `AuthUserResetPassword` | `{email,password_reset_at}` | [`settings.py:613-635`](../../app/api/settings.py#L613-L635) |
| DELETE | `/auth-users/{id}` | ★ | — | 204 | [`settings.py:645-668`](../../app/api/settings.py#L645-L668) |
| GET | `/export/macro` | ✗ | — | `application/zip` / 404 | [`settings.py:680-746`](../../app/api/settings.py#L680-L746) |

Frontend bindings for all of the above live in `settingsApi` ([`services/api.ts:779-884`](../../frontend/src/services/api.ts#L779-L884)).

## Data Models

### Pydantic request/response (settings.py)
`SettingValue{key:str, value:Any}`; `PersonPayload{email,name,role?,avatar_color?}`; `PersonPatch{email?,name?,role?,avatar_color?,is_active?}`; `GroupPayload`/`GroupPatch`; `TypePayload{code(1-128),label?}`; `StageAssigneeRow{stage(1-64),assignee_email(1-255),notify_email=False}`; `StageAssigneeBulk{rows:[…]}`; `AuthUserCreate{email(3-255),password(10-256),role='user'}`; `AuthUserPatch{role?,is_active?}`; `AuthUserResetPassword{password(10-256)}`; `TemplateCreate{kind,name(1-120),icon?,description?,category?,config={},default_for_mode?}`; `TemplatePatch{…,default_for_mode? with model_fields_set semantics}` ([`settings.py:20-65`, `482-497`, `764-789`](../../app/api/settings.py#L20-L65)).

### TypeScript interfaces (services/api.ts)
`SettingsPerson`, `SettingsGroup`, `SettingsType{…,is_default?}`, `StageAssigneeRow`, `AiModeDefault = 'transcript'|'summary'|'key-moments'|'structured-notes'`, `PromptTemplate`, `TemplateCreate`, `TemplatePatch`, `SettingsPersonPatch`, `SettingsGroupPatch`, `AuthUser` (no `password_hash`), `AuthUserPatch` ([`services/api.ts:687-777`](../../frontend/src/services/api.ts#L687-L777)).

### Tables (migrations)
- `org_settings(key PK, value JSONB, updated_by, updated_at)` ([`006`](../../migrations/006_settings.sql#L3-L8)).
- `people(id, email UNIQUE, name, role, avatar_color, is_active, created_at)` ([`006`](../../migrations/006_settings.sql#L23-L31)).
- `groups(id, name UNIQUE, description, created_at)`; `group_members(group_id, person_id PK, cascade)` ([`006`](../../migrations/006_settings.sql#L33-L44)).
- `session_types(id, code UNIQUE, label, metadata JSONB, is_default)` + partial unique index `session_types_is_default_uq` ([`006`](../../migrations/006_settings.sql#L47-L52), [`038`](../../migrations/038_session_types_is_default.sql#L13-L19)).
- `stage_assignees(id, type_id→session_types cascade, stage, assignee_email, notify_email, UNIQUE(type_id,stage), person_id→people SET NULL, group_id→groups SET NULL, CHECK single assignee)` ([`006`](../../migrations/006_settings.sql#L54-L61), [`040`](../../migrations/040_stage_assignees_typed_fk.sql#L17-L35)).
- `email_templates(id, session_type_id→session_types cascade NULLable, stage_id, locale, subject, body, is_active, created_by, created_at, updated_at)` + unique index on `(COALESCE(session_type_id::text,'_default_'), stage_id, locale)` ([`048`](../../migrations/048_email_templates.sql#L28-L53)).
- `prompt_templates(id, kind, name, icon, description, category, config JSONB, is_system, is_active, version, created_by, created_at, updated_at, default_for_mode)` + unique on `lower(name)`, partial unique on `default_for_mode` where active, CHECK on mode values ([`047`](../../migrations/047_prompt_templates.sql#L30-L57), [`049`](../../migrations/049_prompt_templates_default_for_mode.sql#L22-L52)).
- `auth_users(id, email, password_hash, role='user', is_active, last_login_at, password_reset_at, created_at, updated_at)` + unique on `lower(email)`, active partial index ([`045`](../../migrations/045_auth_users.sql#L11-L31)).

> **Flag — legacy table reshapes:** both `prompt_templates` and `email_templates` were created with a *different* schema by [`migration 006`](../../migrations/006_settings.sql#L64-L112); migrations 047 and 048 `DROP TABLE … CASCADE` the empty legacy tables and recreate them in the current shape ([`047:28`](../../migrations/047_prompt_templates.sql#L28), [`048:21`](../../migrations/048_email_templates.sql#L21)). Documented as safe because the legacy tables never held real data.

## Events

- **Audit events:** every settings write inserts into `audit_events(actor_email, kind, summary)` and commits in-transaction. 20 distinct `kind` values (full table in the product spec's Audit Requirements). The macro-download audit insert is wrapped in try/except so it cannot block the download ([`settings.py:730-740`](../../app/api/settings.py#L730-L740)).
- **No domain/message-bus events** are emitted by `settings.py`. There is no WebSocket broadcast or Celery enqueue from settings writes. **NOT VERIFIED IN CODE** as any event emission beyond the audit row.
- **Indirect pipeline effect:** writing `prompt_templates.default_for_mode` changes the prompt read by `app/prompts.py::get_prompt_for_mode` on the next upload — a data dependency, not an event ([`app/prompts.py:131-172`](../../app/prompts.py#L131-L172)).

## State Management

- **No Pinia store for Settings.** State is local to each section component. The only global store touched is the auth store, read by the router guard ([`router/index.ts:58`](../../frontend/src/router/index.ts#L58)).
- **Server is the source of truth**; sections hydrate `onMounted` and patch local refs after each successful mutation rather than re-fetching (e.g. Auth & logins splices the returned row into `users` — [`SectionAuthUsers.vue:129`, `147`](../../frontend/src/components/settings/SectionAuthUsers.vue#L129)).
- **Caches:** Types caches per-type assignee rows client-side (`typeRowsCache`) to make tab-switching instant ([`SectionTypes.vue:52,86-91`](../../frontend/src/components/settings/SectionTypes.vue#L52)).
- **Cross-section freshness:** Types hydrates its assignee dropdown from `/v1/settings/people` (not a stale fixture) so a person added in Team appears without reload ([`SectionTypes.vue:39-44,105-115`](../../frontend/src/components/settings/SectionTypes.vue#L39-L44)).
- **Org settings are read by other views,** e.g. `default_ai_model` consumed by Upload (per [`SectionAIModels.vue:43-45`](../../frontend/src/components/settings/SectionAIModels.vue#L43-L45)).

## Validation

- **Pydantic Field constraints** enforce length bounds server-side (see Data Models). Pydantic also rejects unknown body shapes.
- **PUT partial-update guards:** people/groups/auth-users PUTs reject empty patches with 400; people/groups build the SET clause only from `model_dump(exclude_unset=True)` fields ([`settings.py:131-139`, `186-189`](../../app/api/settings.py#L131-L139)).
- **Template PUT `default_for_mode` tri-state:** uses `payload.model_fields_set` to distinguish field-absent (leave alone) from explicit-null (unbind) ([`settings.py:956-958`](../../app/api/settings.py#L956-L958)); the frontend only sends the field when the operator actually changed it ([`SectionPromptTemplates.vue:229-231`](../../frontend/src/components/settings/SectionPromptTemplates.vue#L229-L231)).
- **DB-level validation:** unique indexes (`people.email`, `groups.name`, `auth_users lower(email)`, `prompt_templates lower(name)`, `default_for_mode` partial), CHECK constraints (`default_for_mode` allowed values, single stage-assignee), partial unique on `session_types.is_default`. The handlers catch the resulting integrity errors and map them to typed 409/400 bodies (e.g. matching on `people_email_key`, `auth_users_email_lower_uq`, `prompt_templates_default_for_mode_uq` in the exception string — [`settings.py:147-152`, `554-558`, `906-916`](../../app/api/settings.py#L147-L152)).
- **Client validation:** email regex + min-length checks gate Add buttons in Team and Auth & logins before any request ([`SectionTeam.vue:70-77`](../../frontend/src/components/settings/SectionTeam.vue#L70-L77), [`SectionAuthUsers.vue:40-51`](../../frontend/src/components/settings/SectionAuthUsers.vue#L40-L51)).

## Security

- **Authentication:** JWT bearer (HS256, `API_SECRET_KEY`, default 8h expiry). `get_current_user` decodes the token and re-checks the user is active against `auth_users` with an env-CSV fallback ([`app/auth.py:172-208`](../../app/auth.py#L172-L208)). Every settings endpoint depends on `CurrentUser`.
- **Password storage:** bcrypt-hashed at rest; `password_hash` is never returned by any GET (whitelist projection `_row_to_auth_user`) ([`settings.py:499-510`](../../app/api/settings.py#L499-L510)). Reset-only model: new plaintext is accepted over TLS and immediately hashed; the response surfaces only `password_reset_at` ([`settings.py:613-635`](../../app/api/settings.py#L613-L635)).
- **Last-admin protection:** prevents locking the org out of admin (409 `LAST_ADMIN_PROTECTED`) on demote/disable/delete ([`settings.py:580-593`, `649-660`](../../app/api/settings.py#L580-L593)).
- **SQL injection:** all SQL uses bound parameters via `text()`; SET clauses are built only from a fixed whitelist of column names derived from Pydantic field names, never from raw user keys ([`settings.py:139`, `595`, `944-958`](../../app/api/settings.py#L139)).
- **Macro download** is intentionally not admin-gated (publishable docs, not secrets) per its docstring ([`settings.py:682-685`](../../app/api/settings.py#L682-L685)).

> **Flag — known debt:** `AUTH_USERS` remains a plaintext env CSV used as the DR/bootstrap source and login fallback ([`app/auth.py:81-143`](../../app/auth.py#L81-L143)). Documented debt per repo CLAUDE.md.

## Permissions

**What is actually enforced (do not present role tiers as active).**

- **Effective gate = JWT presence + a hardcoded admin-email check.** `get_current_user` returns a `User` carrying only `email`; it never loads `auth_users.role` ([`app/auth.py:36-39`, `203`](../../app/auth.py#L36-L39)).
- `settings.py` imports `require_admin` ([`settings.py:15`](../../app/api/settings.py#L15)) and calls it as `require_admin(user)` — always **without** `role`. With `role=None`, `is_admin` falls back to `user.email == LEGACY_ADMIN_EMAIL` (`"johndean@vin.com"`), case- and whitespace-sensitive ([`roles.py:54`, `62-92`](../../app/security/roles.py#L54)). So in this module `require_admin` ≡ the legacy email gate. The role-param branch of `is_admin` exists but is **scaffold only — never wired** ([`roles.py:10-19`](../../app/security/roles.py#L10-L19)).
- **Admin-gated (★ in APIs table):** Type add/remove, set type assignees, all auth-users endpoints, all template create/update/delete.
- **Unguarded (any authenticated user):** org k/v GET/PUT, all people/groups/members CRUD, GET types + GET assignees, GET templates, macro download.
- **Client guard does NOT apply to Settings.** `router.beforeEach` only redirects when `to.meta.adminOnly` is set; the sole `adminOnly` route is `/admin/help`, not `/settings` ([`router/index.ts:44`, `53-68`](../../frontend/src/router/index.ts#L44)). Auth-users/Deleted sections instead catch the backend 403 and render an admin-only message.
- **Net effect:** editing a user's role in the UI updates the `auth_users.role` column but grants no runtime privilege; the only admin is the hardcoded email. **PARTIALLY IMPLEMENTED** role system.

## Integrations

- **Gemini prompt pipeline:** `prompt_templates.default_for_mode` is read by `app/prompts.py::get_prompt_for_mode` on every upload (resolution order: custom-prompt → DB default-for-mode row → hardcoded fallback) ([`app/prompts.py:131-172`](../../app/prompts.py#L131-L172)).
- **Email builder backend:** `/v1/email-templates` (resolve/save) + `/v1/admin/email-debug/send` reused for test sends from `EmailBuilder.vue` ([`EmailBuilder.vue:18-28`, `77-82`](../../frontend/src/components/settings/EmailBuilder.vue#L18-L28)).
- **Diagnostics integrations:** `diag.clearRateLimitSlots` (Redis slot sweep) and `diag.reseedAuthUsers` (env→table seed) consumed from `SectionDiagnostics.vue` / `SectionAuthUsers.vue`.
- **Macro bundle source:** repo `docs/macros/` directory, zipped on demand ([`settings.py:692-725`](../../app/api/settings.py#L692-L725)).
- **GCS/Email debug:** drill-in components `GCSDebug.vue` / `EmailDebug.vue` (their own endpoints; outside the settings router).

## Background Jobs

- **Settings itself enqueues no Celery work.** No task dispatch appears in `settings.py`.
- **Out-of-scope but adjacent:** migration 048 explicitly notes that the stage-transition email-firing Celery hook is a separate plan, not part of the email-templates table ship ([`048:23-26`](../../migrations/048_email_templates.sql#L23-L26)). **NOT VERIFIED IN CODE** within this module whether/where that hook runs.
- **Boot-time seed:** `app/services/auth_users.seed_from_env_if_empty` (referenced by `app/auth.py:6-8`) populates `auth_users` from `AUTH_USERS` on first boot; the Auth & logins reseed button re-triggers the same idempotent seed via the diag endpoint ([`SectionAuthUsers.vue:238-258`](../../frontend/src/components/settings/SectionAuthUsers.vue#L238-L258)).

## Error Handling

- **Backend:** raises `HTTPException` with structured `detail` objects `{code, message}` for business errors (e.g. `DEFAULT_TYPE_LOCKED`, `LAST_ADMIN_PROTECTED`, `DUPLICATE_EMAIL`, `DEFAULT_MODE_TAKEN`, `SYSTEM_TEMPLATE_LOCKED`, `MACRO_NOT_FOUND`). Integrity-error branches inspect the lowercased exception message to map a DB unique violation to the right 409 ([`settings.py:147-153`, `554-559`, `901-922`](../../app/api/settings.py#L147-L153)). Unknown failures fall through to 500 with the exception string.
- **Frontend:** `ApiError` (from `services/http.ts`) carries `status` + parsed `body`. Sections share an `err()`/`surfaceError()` helper that unwraps `body.detail.message` (object form) or `body.detail` (string form) for the toast, falling back to `${status}: ${message}` ([`SectionTeam.vue:123-137`](../../frontend/src/components/settings/SectionTeam.vue#L123-L137), [`SectionAuthUsers.vue:97-112`](../../frontend/src/components/settings/SectionAuthUsers.vue#L97-L112), [`SectionPromptTemplates.vue:293-309`](../../frontend/src/components/settings/SectionPromptTemplates.vue#L293-L309)).
- **403 handling:** Auth & logins and Deleted sessions special-case 403 to an admin-only message + empty list rather than a hard error.
- **Defensive hydration:** Team/Types `.catch(() => [])` per fetch so a single failing endpoint doesn't blank the page; General/Upload/Export/AIModels/Discrepancy fall back to in-component defaults when `GET /v1/settings` fails.

## Performance Considerations

- **Bulk members endpoint** `/v1/settings/groups-members` replaces an N-per-group fan-out with one round-trip on Team hydrate (Phase 7 perf plan) ([`settings.py:243-265`](../../app/api/settings.py#L243-L265), [`SectionTeam.vue:105-108`](../../frontend/src/components/settings/SectionTeam.vue#L105-L108)).
- **Client-side type-matrix cache** avoids re-fetching assignees when toggling between previously-loaded Types ([`SectionTypes.vue:52,86-87`](../../frontend/src/components/settings/SectionTypes.vue#L52)).
- **Parallel hydration:** General saves 3 keys with `Promise.all`; Team/Types fetch people+groups(+members) in parallel ([`SectionGeneral.vue:34-38`](../../frontend/src/components/settings/SectionGeneral.vue#L34-L38), [`SectionTypes.vue:105-109`](../../frontend/src/components/settings/SectionTypes.vue#L105-L109)).
- **Prompt hot-path indexes:** `prompt_templates_default_mode_lookup_idx` supports the per-upload `get_prompt_for_mode` query ([`049:50-52`](../../migrations/049_prompt_templates_default_for_mode.sql#L50-L52)); `auth_users_active_idx`, `prompt_templates_kind_active_idx`, `stage_assignees_person/group_idx`, `email_templates_*_active_idx` keep the common filtered reads small ([`045`](../../migrations/045_auth_users.sql#L30-L31), [`047`](../../migrations/047_prompt_templates.sql#L46-L57), [`040`](../../migrations/040_stage_assignees_typed_fk.sql#L37-L38), [`048`](../../migrations/048_email_templates.sql#L54-L57)).
- **Auth DB engine** is module-scoped + pooled (`pool_pre_ping`, size 5) and reused across every protected request's `get_current_user` ([`app/auth.py:66-78`](../../app/auth.py#L66-L78)).
- **Macro zip** is built in-memory on each request (no caching); size depends on `docs/macros/` contents.

## Source Verification
- **Files Used:** `app/api/settings.py`; `app/auth.py`; `app/security/roles.py`; `app/prompts.py`; `app/main.py`; `frontend/src/views/SettingsView.vue`; `frontend/src/components/settings/*` (all 13 sections + EmailBuilder + shared); `frontend/src/services/api.ts`; `frontend/src/fixtures/settings.ts`; `frontend/src/router/index.ts`; `migrations/{006,031,032,038,039,040,045,047,048,049,050}*.sql`
- **Components Used:** SettingsView, SectionGeneral/Team/Types/AIModels/Upload/Discrepancy/Export/PromptTemplates/Manifest/Email/AuthUsers/Diagnostics/Deleted, EmailBuilder
- **APIs Used:** `/v1/settings` (GET/PUT key); people/groups/members CRUD; types + `/{id}/assignees`; templates CRUD; auth-users CRUD + reset-password; `/export/macro`; (separate) `/v1/email-templates`; diag `clear-rate-limit-slots`, `reseed-auth-users`
- **Database Tables Used:** `org_settings`, `people`, `groups`, `group_members`, `session_types`, `stage_assignees`, `email_templates`, `prompt_templates`, `auth_users`, `audit_events`
- **Permission Logic Used:** JWT (`CurrentUser`) everywhere; `require_admin(user)` → `LEGACY_ADMIN_EMAIL` (`johndean@vin.com`) gate on Type/assignee/auth-user/template writes; org-k/v + people/groups unguarded; role-param branch of `is_admin` is scaffold-only; client `adminOnly` guard does NOT cover `/settings`
- **Confidence Score:** High — endpoint gates, validation, schemas, and migrations all read directly from source; legacy-table reshapes and the email-firing-out-of-scope note are flagged explicitly.
- **Evidence Links:** [`settings.py:15`](../../app/api/settings.py#L15), [`settings.py:320-355`](../../app/api/settings.py#L320-L355), [`settings.py:529-668`](../../app/api/settings.py#L529-L668), [`settings.py:867-1036`](../../app/api/settings.py#L867-L1036), [`roles.py:62-92`](../../app/security/roles.py#L62-L92), [`app/auth.py:172-208`](../../app/auth.py#L172-L208), [`app/prompts.py:131-172`](../../app/prompts.py#L131-L172), [`router/index.ts:40-68`](../../frontend/src/router/index.ts#L40-L68)
