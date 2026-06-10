# Sessions — Demo Questions

> Module key: `sessions`. Every answer below is code-true as of `HEAD`
> 2026-06-08. Paths in Source Files are relative to the repo root.
> Personas with nothing code-true to ask are omitted.

---

## User

### Q: How do I find a specific recording in the Sessions list?
**Verified Answer:** Use the search box (matches title or presenter) or the filter
chips (All / In Workflow / Processing / Published). You can also deep-link with
URL query params `?stage=`, `?ai=`, and `?f=`, which the list watches and
re-fetches on. Search hits the backend `f` param (case-insensitive `LIKE` on code
or title) and is also re-filtered client-side across title/presenter.
**Supporting Evidence:** Search input bound to `query`; `filters` chips computed;
`load()` passes `stage/ai/f`; `watch(route.query…)` re-loads; server clause
`LOWER(code) LIKE :f OR LOWER(title) LIKE :f`.
**Source Files:** frontend/src/views/SessionsView.vue:182, frontend/src/views/SessionsView.vue:84, frontend/src/views/SessionsView.vue:33, app/api/sessions.py:158
**API References:** GET /v1/sessions (app/api/sessions.py:138)
**Database References:** sessions (code, title)

### Q: What happens when I click a session row?
**Verified Answer:** If the session is still `ingesting` you go to the processing
view (`/p/{id}`); otherwise you open the detail page (`/s/{id}`).
**Supporting Evidence:** `routeFor(s)` returns `/p/${id}` when `status ===
'ingesting'`, else `/s/${id}`.
**Source Files:** frontend/src/views/SessionsView.vue:98
**API References:** none (client routing)
**Database References:** sessions (status)

### Q: How do I rename a session or fix its code after upload?
**Verified Answer:** On the detail page, click the title or the code chip — it
becomes an inline input. Blur or Enter saves via PATCH; Escape cancels. If the new
code is already taken you get a warning and the input stays open so you can fix it.
**Supporting Evidence:** `SessionTextEdit` click-to-edit; `commit()` calls
`sessionsApi.update`; 409 → "Another session already uses that code."; server PATCH
whitelist + 409 on duplicate.
**Source Files:** frontend/src/components/session/SessionTextEdit.vue:54, frontend/src/components/session/SessionTextEdit.vue:82, app/api/sessions.py:569
**API References:** PATCH /v1/sessions/{id} (app/api/sessions.py:569)
**Database References:** sessions (code, title, title_long, title_short, presenter)

### Q: A session shows "Failed · why?" — how do I see the reason?
**Verified Answer:** Click the red "Failed · why?" pill on that row. A modal opens
showing the failure reason and category, the timestamp/actor, and the last ~10
state transitions, with a link to the full audit log.
**Supporting Evidence:** `showFailureReason` calls `sessionsApi.failureReason`;
modal renders `reason/category/ts/actor/log_tail`; server reads the last `failed`
entry from `session_audit.processing_log`.
**Source Files:** frontend/src/views/SessionsView.vue:129, frontend/src/views/SessionsView.vue:284, app/api/sessions.py:753
**API References:** GET /v1/sessions/{id}/failure-reason (app/api/sessions.py:753)
**Database References:** session_audit (processing_log), sessions

### Q: Why can't I edit a session someone else is already in?
**Verified Answer:** The Editor acquires a per-session lock on open and heartbeats
it. If another operator holds a fresh lock you drop to read-only and see who holds
it. The lock TTL is 90 seconds (3 missed 30-second heartbeats), after which it
becomes stale and can be taken over. If the lock service is unreachable, the app
fails closed (read-only).
**Supporting Evidence:** `useSessionLock` acquire + heartbeat; `LOCK_TTL_SECONDS =
90`; stale = `expires_at` in the past; `lockError` → fail-closed.
**Source Files:** frontend/src/composables/useSessionLock.ts:88, app/api/locks.py:42, app/api/locks.py:89, frontend/src/composables/useSessionLock.ts:55
**API References:** POST /v1/sessions/{id}/lock/acquire, /heartbeat (app/api/locks.py:99, app/api/locks.py:142)
**Database References:** session_locks (user_email, expires_at)

---

## Operations

### Q: How do I assign a person or group to a workflow stage for one session?
**Verified Answer:** On the detail page's Stage Assignments card, click the edit
icon on a stage and pick a person or group. That writes a manual override
(`source='manual'`, shown with an amber dot). "Reset" returns the stage to its
Type-matrix default. An empty selection also resets it.
**Supporting Evidence:** `selectAssignee`/`resetStageToDefault` call
`setStageAssignee`; manual dot rendered when `source === 'manual'`; server marks
manual vs default and resolves person/group.
**Source Files:** frontend/src/views/SessionDetailView.vue:178, frontend/src/views/SessionDetailView.vue:596, app/api/sessions.py:379, app/api/sessions.py:449
**API References:** PUT /v1/sessions/{id}/stage-assignees/{stage} (app/api/sessions.py:379)
**Database References:** session_stage_assignees, people, groups

### Q: What does changing a session's Type do to its stage assignments?
**Verified Answer:** Selecting a new Type immediately saves `session_type_id`, then
shows a banner offering to apply that Type's stage defaults. Confirming
**wipes every existing per-session stage row** and re-seeds them from the Type
matrix (`source='default'`). It is idempotent.
**Supporting Evidence:** `onTypePickerChange` PATCHes the FK; `applyTypeDefaults`
confirms then calls the apply endpoint; server deletes all rows then calls
`init_session_stages`.
**Source Files:** frontend/src/views/SessionDetailView.vue:131, frontend/src/views/SessionDetailView.vue:148, app/api/sessions.py:498, app/services/session_init.py:27
**API References:** POST /v1/sessions/{id}/stage-assignees/apply-type-defaults (app/api/sessions.py:498)
**Database References:** sessions (session_type_id), session_stage_assignees, stage_assignees, session_types

### Q: Where does a session's status come from and can it skip steps?
**Verified Answer:** Status is constrained to eight values and only moves along a
fixed transition map. The AI-direct path allows `uploading → ready` (skipping the
intermediate transcribing/normalizing/fusing/aligning stages); `ready → complete`
is the final promotion. `failed` and `complete` are terminal. There is no
DB-level transition check — the Python state machine is the only legal path.
**Supporting Evidence:** `ALLOWED_TRANSITIONS` map; `uploading` allows
`{transcribing, ready, failed}`; `TERMINAL_STATES = {failed, complete}`; CHECK lists
the 8 values.
**Source Files:** app/engines/state_machine.py:40, app/engines/state_machine.py:49, migrations/010_state_machine.sql:23
**API References:** none directly (FSM invoked by ingest tasks / handlers)
**Database References:** sessions (status), session_audit

### Q: My upload says "Already at N concurrent sessions" — what is that?
**Verified Answer:** A per-user concurrency cap of `MAX_CONCURRENT_SESSIONS = 3`,
plus a global `MAX_QUEUE_LENGTH = 10`. It's enforced at upload time via Redis slot
sets, returning `429 RATE_LIMIT_USER` (or `RATE_LIMIT_QUEUE`). Soft-deleting or
purging a session releases its slot. If Redis is down the check is skipped (warn
only) rather than blocking uploads.
**Supporting Evidence:** `check_user_quota` raises 429 at the cap; constants in
config; `release_slot` on delete; Redis-down → warn.
**Source Files:** app/middleware/rate_limit.py:33, app/config.py:46, app/api/sessions.py:657, app/middleware/rate_limit.py:64
**API References:** GET /v1/sessions/deleted, DELETE /v1/sessions/{id} (slot release)
**Database References:** none (Redis: sessions:active:{user}, sessions:queue)

### Q: An operator's editor tab crashed and the lock is stuck — what can I do?
**Verified Answer:** Wait out the 90-second TTL, or have an admin force-take the
lock immediately. Force-take overrides staleness and writes an `audit_events` row
recording the prior holder.
**Supporting Evidence:** force-take route gated by `is_admin`; inserts
`audit_events` with `kind='session.lock_force_take'`.
**Source Files:** app/api/locks.py:218, app/api/locks.py:246
**API References:** POST /v1/sessions/{id}/lock/force-take (app/api/locks.py:218)
**Database References:** session_locks, audit_events

---

## Administrator

### Q: Who can delete a session, and is it reversible?
**Verified Answer:** Soft-delete is limited to `SESSION_TRASH_ALLOWED` =
`johndean@vin.com` and `carlab@vin.com`; it sets `deleted_at` and keeps data for a
30-day recovery window. Restore (clears `deleted_at`) and permanent purge are
admin-only and a session must be soft-deleted before it can be purged. Purge
hard-deletes the row and cascades to children — irreversible.
**Supporting Evidence:** `SESSION_TRASH_ALLOWED` set + 403 gate; restore/purge call
`require_admin`; purge requires prior soft-delete; cascade on the parent.
**Source Files:** app/api/sessions.py:52, app/api/sessions.py:630, app/api/sessions.py:668, app/api/sessions.py:697, app/api/sessions.py:718
**API References:** DELETE /v1/sessions/{id}, POST /v1/sessions/{id}/restore, DELETE /v1/sessions/{id}/permanent
**Database References:** sessions (deleted_at), and ON DELETE CASCADE children (sources, slides, speakers, segments, session_audit)

### Q: How is "admin" actually decided in this app?
**Verified Answer:** Today, admin = the hardcoded email `johndean@vin.com`
(`LEGACY_ADMIN_EMAIL`). The `User` object only carries an email — the JWT path
never loads `auth_users.role`. The `is_admin`/`require_admin` helpers do have a
role-aware branch, but it is scaffold-only and never exercised because no caller
passes a role. So restore, purge, list-deleted, and lock force-take all effectively
check `email == johndean@vin.com`.
**Supporting Evidence:** `LEGACY_ADMIN_EMAIL = "johndean@vin.com"`; `is_admin`
falls back to email equality; `User` has only `email`; `get_current_user` returns
`User(email=...)` with no role; roles.py marked "scaffold only — not yet wired".
**Source Files:** app/security/roles.py:54, app/security/roles.py:62, app/auth.py:37, app/auth.py:172, app/security/roles.py:10
**API References:** none (auth dependency)
**Database References:** auth_users (role column exists per migration 045 but is not read)

### Q: Is there a UI permission boundary anywhere?
**Verified Answer:** One client-side guard: the `/admin/help` route carries
`meta.adminOnly` and redirects anyone who isn't `johndean@vin.com` to the
dashboard. No Sessions route uses it; Sessions authorization is enforced
server-side (e.g., the delete button renders for everyone but the server returns
403 for non-allowlisted users).
**Supporting Evidence:** router `adminOnly` check vs `LEGACY_ADMIN_EMAIL`; only
`/admin/help` has the meta; delete row button is unconditional; server 403 on
delete.
**Source Files:** frontend/src/router/index.ts:44, frontend/src/router/index.ts:63, frontend/src/views/SessionsView.vue:262, app/api/sessions.py:630
**API References:** DELETE /v1/sessions/{id}
**Database References:** none

### Q: What recovery tools exist for deleted sessions?
**Verified Answer:** `GET /v1/sessions/deleted` (admin) lists sessions soft-deleted
within the last 30 days; older rows are hidden but the DB row survives until purge
so audit joins still work. From there an admin can restore or permanently delete.
**Supporting Evidence:** deleted listing filters `deleted_at >= now() - 30 days`;
admin gate; restore/purge routes.
**Source Files:** app/api/sessions.py:266, app/api/sessions.py:668, app/api/sessions.py:697
**API References:** GET /v1/sessions/deleted, POST /v1/sessions/{id}/restore, DELETE /v1/sessions/{id}/permanent
**Database References:** sessions (deleted_at)

---

## Compliance

### Q: What is recorded when a session changes processing state?
**Verified Answer:** Every transition appends one append-only entry to
`session_audit.processing_log` (JSONB array) with `stage`, `status`, `started_at`,
`completed_at`, `actor`, `reason`, and `metadata`. The status flip, audit append,
and WS emit are committed together in one transaction (row-locked with
`SELECT … FOR UPDATE`).
**Supporting Evidence:** `_append_log_entry` builds the entry; sync transition
locks the row in `engine.begin()`; one row per session keyed by `session_id`.
**Source Files:** app/engines/state_machine.py:52, app/engines/state_machine.py:114, migrations/010_state_machine.sql:31
**API References:** GET /v1/sessions/{id}/audit-log (app/api/sessions.py:306)
**Database References:** session_audit (processing_log)

### Q: Are metadata edits (title, code, presenter) audited?
**Verified Answer:** No. PATCH on session metadata is not written to any audit
table — only status transitions (`session_audit`) and editor lock force-takes
(`audit_events`) are logged. This is a known gap; there is no per-field session
audit.
**Supporting Evidence:** `update_session` does a plain UPDATE with no audit write;
only the FSM and force-take write audit rows.
**Source Files:** app/api/sessions.py:569, app/engines/state_machine.py:52, app/api/locks.py:246
**API References:** PATCH /v1/sessions/{id}
**Database References:** sessions (no audit row written), session_audit (status only), audit_events (force-take only)

### Q: Does an audit trail survive permanent deletion of a session?
**Verified Answer:** Partially. Permanent delete cascades and removes
`session_audit` (FK `ON DELETE CASCADE`), but `audit_events.session_id` is
deliberately `ON DELETE SET NULL` so historical events survive for forensic
queries after the session row is gone.
**Supporting Evidence:** purge comment notes CASCADE on children and keeps
`audit_events` via SET NULL; `session_audit` PK FK is ON DELETE CASCADE.
**Source Files:** app/api/sessions.py:722, migrations/010_state_machine.sql:32
**API References:** DELETE /v1/sessions/{id}/permanent
**Database References:** session_audit (cascaded), audit_events (preserved, session_id nulled)

### Q: How is concurrent-edit data loss prevented?
**Verified Answer:** A single-row-per-session lock (`session_locks`) with a 90s
heartbeat TTL. The editor acquires it on open and the frontend fails closed if the
lock service is unreachable. An admin force-take is auditable via `audit_events`.
The lock is advisory at the DB layer but enforced at the API layer on the autosave
path.
**Supporting Evidence:** locks module header; TTL constant; fail-closed comment;
force-take audit write.
**Source Files:** app/api/locks.py:1, app/api/locks.py:42, frontend/src/composables/useSessionLock.ts:55, app/api/locks.py:246
**API References:** POST /v1/sessions/{id}/lock/acquire, /heartbeat, /release, /force-take
**Database References:** session_locks, audit_events

---

## Power User

### Q: What gets created when I POST a new session, and how are code clashes handled?
**Verified Answer:** A `sessions` row (status `'uploading'`) and a matching
`session_templates` row carrying the pipeline routing, written in one transaction.
If the `code` collides with the `sessions_code_key` unique constraint, you get a
`409 CONFLICT` envelope (not a 500), telling you to retry with a fresh code.
**Supporting Evidence:** single-transaction INSERT of both rows; `IntegrityError`
on `sessions_code_key` → `ConflictError`.
**Source Files:** app/api/sessions.py:178, app/api/sessions.py:219, app/api/sessions.py:232
**API References:** POST /v1/sessions (app/api/sessions.py:178)
**Database References:** sessions, session_templates

### Q: How do PATCH semantics distinguish "leave unchanged" from "clear"?
**Verified Answer:** `null` (field omitted) leaves a field unchanged; an empty
string `""` explicitly clears it. The server uses
`model_dump(exclude_unset=True)`, so only fields you actually send are written; an
entirely empty patch returns `400`. Only `code`, `title`, `title_long`,
`title_short`, `presenter`, and `session_type_id` are accepted (whitelist).
**Supporting Evidence:** `SessionPatch` docstring; `exclude_unset` and empty-update
400; whitelisted fields.
**Source Files:** app/api/sessions.py:106, app/api/sessions.py:587
**API References:** PATCH /v1/sessions/{id}
**Database References:** sessions

### Q: What pipeline defaults apply if I don't send a pipeline_config?
**Verified Answer:** `ai_pipeline='direct'` (the default was flipped from
`enhanced` on 2026-05-20 so legacy clients don't silently land on
enhanced+transcript), `ai_mode='transcript'`, `ai_model='gemini-2.5-pro'`,
`prompt_mode='transcript'`, `stt_backend='google_latest_long'`,
`template_id='lecture_v1'`, and `iil_config` with all tiers enabled.
**Supporting Evidence:** `PipelineConfig` field defaults; fallback `cfg =
payload.pipeline_config or PipelineConfig()`.
**Source Files:** app/api/sessions.py:56, app/api/sessions.py:231
**API References:** POST /v1/sessions, GET /v1/sessions/{id}/pipeline-config (app/api/sessions.py:323)
**Database References:** session_templates

### Q: Why might a list filter show zero even though sessions exist?
**Verified Answer:** Some UI filters key off status strings the backend no longer
allows. The `sessions.status` CHECK permits only `uploading, transcribing,
normalizing, fusing, aligning, ready, complete, failed`. The list view's "In
Workflow"/"Processing" filters and the `aiStatusFor` mapping reference
`'ingesting'` and `'archived'`, which can never appear in current data — so those
counts and the hardcoded "SOP: prep" badge don't reflect live state.
**Supporting Evidence:** client filters use `'ingesting'`/`'archived'`; CHECK
excludes them; SOP badge hardcoded to `prep`.
**Source Files:** frontend/src/views/SessionsView.vue:63, frontend/src/views/SessionsView.vue:258, migrations/010_state_machine.sql:23
**API References:** GET /v1/sessions?ai=… (app/api/sessions.py:155)
**Database References:** sessions (status)

### Q: Sync vs async — how does a Celery task change status differently from an API call?
**Verified Answer:** Celery uses `transition_session_sync`, which opens its own sync
engine, row-locks, validates, updates, appends the audit entry, and **commits**
itself. FastAPI handlers use `transition_session` (async), which does the same
validation/update/append but does **not** commit — the request handler owns the
transaction so the transition is atomic with the rest of the request. Both raise
`ConflictError` → 409 on illegal moves.
**Supporting Evidence:** sync version uses `engine.begin()` and disposes; async
version's docstring "does NOT commit … caller's request handler commits".
**Source Files:** app/engines/state_machine.py:114, app/engines/state_machine.py:173
**API References:** none (internal)
**Database References:** sessions (status), session_audit

---

## Source Verification
- **Files Used:** app/api/sessions.py, app/engines/state_machine.py, app/services/session_init.py, app/api/locks.py, app/middleware/rate_limit.py, app/security/roles.py, app/auth.py, app/config.py, migrations/001_init.sql, migrations/010_state_machine.sql, migrations/057_session_locks.sql, frontend/src/views/SessionsView.vue, frontend/src/views/SessionDetailView.vue, frontend/src/components/session/SessionTextEdit.vue, frontend/src/composables/useSessionLock.ts, frontend/src/router/index.ts
- **Components Used:** SessionsView.vue, SessionDetailView.vue, SessionTextEdit.vue, useSessionLock.ts
- **APIs Used:** GET/POST /v1/sessions, GET/PATCH/DELETE /v1/sessions/{id}, /restore, /permanent, /deleted, /audit-log, /failure-reason, /pipeline-config, /stage-assignees[/{stage}], /stage-assignees/apply-type-defaults, lock/{acquire,heartbeat,release,holder,force-take}
- **Database References:** sessions, session_audit, session_templates, session_stage_assignees, stage_assignees, session_types, session_locks, audit_events, people, groups, auth_users
- **Permission Logic Used:** JWT (CurrentUser); SESSION_TRASH_ALLOWED email allowlist; require_admin/is_admin via LEGACY_ADMIN_EMAIL email gate only; client-side adminOnly guard limited to /admin/help
- **Confidence Score:** High — each answer maps to read source lines; the two "zero filter / role scaffold" answers are flagged in-text as PARTIALLY IMPLEMENTED realities.
- **Evidence Links:** [sessions.py:178](../../app/api/sessions.py#L178), [state_machine.py:40](../../app/engines/state_machine.py#L40), [locks.py:218](../../app/api/locks.py#L218), [roles.py:54](../../app/security/roles.py#L54), [auth.py:37](../../app/auth.py#L37), [010_state_machine.sql:23](../../migrations/010_state_machine.sql#L23)
