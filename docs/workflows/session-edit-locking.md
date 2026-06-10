# Workflow: Session Edit Locking

A single-writer advisory lock that prevents two operators from editing the same session transcript at once. One row per session in `session_locks`, kept alive by a 30-second client heartbeat with a 90-second TTL. The lock is **advisory at the DB layer** (it never blocks INSERT/UPDATE on the session's data) — enforcement is the frontend's responsibility: the editor composable [`useSessionLock.ts`](../../frontend/src/composables/useSessionLock.ts) fails **closed**, dropping to read-only when it is not the holder or when the lock service is unreachable.

Backend: [`app/api/locks.py`](../../app/api/locks.py). Table: [`migrations/057_session_locks.sql`](../../migrations/057_session_locks.sql). Per-stage advisory-lock helpers used elsewhere (split/merge, ingest): [`app/services/db_locks.py`](../../app/services/db_locks.py).

## Trigger

- **Acquire** — the editor mounts. `useSessionLock` calls `POST /v1/sessions/{id}/lock/acquire` in `onMounted` ([useSessionLock.ts:131-133](../../frontend/src/composables/useSessionLock.ts#L131)).
- **Heartbeat** — a `setInterval` fires `POST .../lock/heartbeat` every 30s (`HEARTBEAT_INTERVAL_MS = 30_000`), skipped while `document.hidden` ([useSessionLock.ts:93-100](../../frontend/src/composables/useSessionLock.ts#L93)).
- **Release** — `onUnmounted`, `beforeunload`, and tab-hide call `POST .../lock/release` ([useSessionLock.ts:102-152](../../frontend/src/composables/useSessionLock.ts#L102)).
- **Holder poll** — `GET .../lock/holder` reads the current holder for the read-only banner ([locks.py:204](../../app/api/locks.py#L204)).
- **Force-take** — an operator clicks force-take; `POST .../lock/force-take` ([locks.py:218](../../app/api/locks.py#L218)).

All five endpoints require a logged-in user (`CurrentUser` dependency).

## Inputs

- `session_id` — path parameter, typed `UUID` on every route ([locks.py:99-100](../../app/api/locks.py#L99)).
- `user.email` — the lock owner identity, taken from the authenticated user (`user.email`), not from the request body ([locks.py:110](../../app/api/locks.py#L110)).
- No request body on any of the five endpoints.

`LOCK_TTL_SECONDS = 90` is the only configuration constant and is hardcoded in the module ([locks.py:44](../../app/api/locks.py#L44)). The migration's column default also encodes 90 seconds (`expires_at ... DEFAULT (now() + INTERVAL '90 seconds')`, [057_session_locks.sql:19](../../migrations/057_session_locks.sql#L19)).

## Validations

- **acquire** — branches on the current row ([locks.py:112-139](../../app/api/locks.py#L112)):
  - no row, or caller already holds it, or row is stale → UPSERT to caller, return `acquired=True`.
  - held by another user and fresh → return `acquired=False` with the other holder; no write.
  - Staleness: `expires_at < now()` (UTC) ([locks.py:89-93](../../app/api/locks.py#L89)).
  - The UPSERT preserves the original `acquired_at` when the same user refreshes, but resets it when a different user steals (`ON CONFLICT ... DO UPDATE SET acquired_at = CASE WHEN ... = EXCLUDED.user_email THEN session_locks.acquired_at ELSE EXCLUDED.acquired_at END`, [locks.py:119-123](../../app/api/locks.py#L119)).
- **heartbeat** — caller must be the current holder ([locks.py:155-179](../../app/api/locks.py#L155)):
  - no row → `{acquired:false, is_self:false, holder:null}` (idempotent; caller may re-acquire).
  - held by another user → `acquired=false` with that holder (no 409 raised here — the docstring notes 409 is reserved for active steal, but the code path returns 200 with the holder so the frontend can render the banner without losing context).
  - held by caller → UPDATE `heartbeat_at`/`expires_at`, return `acquired=True`.
- **release** — `DELETE ... WHERE session_id = :s AND user_email = :u`; a no-op if the caller is not the holder ([locks.py:192-199](../../app/api/locks.py#L192)).
- **force-take** — requires admin (see Approvals). No staleness check — takes the lock regardless ([locks.py:218-262](../../app/api/locks.py#L218)).
- Idempotency is structural: `session_id` is the PRIMARY KEY, so acquire is a single UPSERT ([057_session_locks.sql:11-15](../../migrations/057_session_locks.sql#L11)).

## Approvals

- **Most routes: none.** acquire / heartbeat / release / holder require only a valid JWT.
- **force-take requires admin.** `if not is_admin(user): raise HTTPException(403, "admin required")` ([locks.py:225-226](../../app/api/locks.py#L225)). `is_admin` comes from [`app/security/roles.py`](../../app/security/roles.py).

  **Permission reality:** `is_admin(user)` is called with **no `role` argument**, so it falls through to the legacy email gate: `user.email == LEGACY_ADMIN_EMAIL` where `LEGACY_ADMIN_EMAIL = "johndean@vin.com"` ([roles.py:54](../../app/security/roles.py#L54), [roles.py:88-92](../../app/security/roles.py#L88)). The `User` object carries only `email` — `get_current_user` never loads `auth_users.role` ([app/auth.py:37-38](../../app/auth.py#L37), [app/auth.py:172-203](../../app/auth.py#L172)). So in production, "admin" for force-take = the single hardcoded address `johndean@vin.com`. NOT VERIFIED IN CODE: any role-tier resolution beyond this single email.

  > Note: the module docstrings of `roles.py` describe the helper as "scaffold only — not yet wired into any endpoint." That is out of date for this surface: `force-take` here (and the Help admin routes) **do** import and call it. The effective behavior is still the single `johndean@vin.com` email gate described above.

## Notifications

- **No email and no Celery task.** The only outbound signal is the HTTP response body.
- The response carries holder identity so the frontend can render banners (`lockError` → red "Lock service unavailable"; `!isHolder && holder` → yellow "In use by {email}") ([useSessionLock.ts:22-24](../../frontend/src/composables/useSessionLock.ts#L22)).
- NOT VERIFIED IN CODE: any WebSocket broadcast on lock change. The lock endpoints do not call the WS bridge.

## Outputs

- A row in `session_locks` (`session_id`, `user_email`, `acquired_at`, `heartbeat_at`, `expires_at`) ([057_session_locks.sql:14-20](../../migrations/057_session_locks.sql#L14)).
- `LockState` JSON on acquire/heartbeat/holder/force-take: `{acquired, is_self, holder}` where `holder` is `{user_email, acquired_at, heartbeat_at, expires_at}` or `null` ([locks.py:50-62](../../app/api/locks.py#L50)).
- `release` returns **HTTP 204** with `response_class=Response` (per the project's FastAPI 0.115 convention) ([locks.py:188-201](../../app/api/locks.py#L188)).
- force-take additionally writes one `audit_events` row (see Audit Events).

## Status Changes

- **No session status transition.** This workflow does not touch the `sessions` table or any pipeline state. It only inserts/updates/deletes the `session_locks` row.
- Lock lifecycle (not a session status): **held → refreshed (heartbeat) → released (explicit) | expired (TTL lapse) | stolen (stale acquire / force-take)**.

## Audit Events

- **force-take only.** Writes `audit_events` with `kind = 'session.lock_force_take'`, `actor_email = caller`, a human summary `"Force-took editor lock from {prior_holder}"`, and `details = {"prior_holder": <email|null>}` ([locks.py:246-255](../../app/api/locks.py#L246)). Columns match [`migrations/004_audit.sql`](../../migrations/004_audit.sql) (`session_id, actor_email, kind, summary, details`).
- acquire / heartbeat / release / holder write **no** audit row.

## Exception Handling

- **Frontend fails closed.** Any error on a lock POST sets `lockError` and leaves `isHolder=false`; a `null` state from `_post` forces `isHolder=false` while keeping the last-known holder for the banner ([useSessionLock.ts:61-86](../../frontend/src/composables/useSessionLock.ts#L61)). The editor must gate destructive writes on `isHolder`.
- A 403 from force-take (non-admin) is surfaced as `lockError` ([useSessionLock.ts:67-69](../../frontend/src/composables/useSessionLock.ts#L67)).
- `release` swallows errors (best-effort); the 90s TTL is the safety net if a release POST is dropped on tab close ([useSessionLock.ts:102-111](../../frontend/src/composables/useSessionLock.ts#L102)).
- Heartbeats pause while the tab is hidden, allowing a forgotten background tab's lock to age out naturally ([useSessionLock.ts:94-97](../../frontend/src/composables/useSessionLock.ts#L94)).
- Backend routes do not wrap their SQL in try/except; a DB failure propagates as an unhandled 500 (FastAPI default handler). NOT VERIFIED IN CODE: any retry or structured error envelope on the backend lock routes.
- IMPLEMENTATION NOT FOUND: a server-side cron sweeper that deletes expired rows. The migration comment calls `idx_session_locks_expires_at` a helper for a "future cron sweeper" ([057_session_locks.sql:22-25](../../migrations/057_session_locks.sql#L22)); staleness is evaluated lazily at acquire time, not swept.

## Source Verification
- **Files Used:** app/api/locks.py, app/services/db_locks.py, migrations/057_session_locks.sql, frontend/src/composables/useSessionLock.ts, app/security/roles.py, app/auth.py, migrations/004_audit.sql
- **Components Used:** useSessionLock.ts (composable; no .vue component read)
- **APIs Used:** POST /v1/sessions/{id}/lock/acquire, POST .../lock/heartbeat, POST .../lock/release (204), GET .../lock/holder, POST .../lock/force-take
- **Database Tables Used:** session_locks, audit_events (force-take only)
- **Permission Logic Used:** JWT presence on all routes; force-take additionally gated by `is_admin(user)` which resolves to the `LEGACY_ADMIN_EMAIL = "johndean@vin.com"` email gate (no role arg passed; `auth_users.role` not loaded)
- **Confidence Score:** High — every claim traced to the read source files; the only flagged item is the stale roles.py docstring vs. the actual call site.
- **Evidence Links:** [locks.py:44](../../app/api/locks.py#L44), [locks.py:112-139](../../app/api/locks.py#L112), [locks.py:225-255](../../app/api/locks.py#L225), [057_session_locks.sql:14-25](../../migrations/057_session_locks.sql#L14), [useSessionLock.ts:131-152](../../frontend/src/composables/useSessionLock.ts#L131), [roles.py:54-92](../../app/security/roles.py#L54)
