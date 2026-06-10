# Diagnostics & Operator Tools — Technical Spec

> Module key: `diagnostics-operator-tools`
> Backend: `app/api/diagnostics.py` (all `/v1/diag/*` routes). Frontend: `GcsView.vue`, `SectionDiagnostics.vue`, `GCSDebug.vue`, `AdminTab.vue` (Rescue), `SectionAuthUsers.vue` (reseed caller), and the `diag` client object in `services/api.ts`.

## Architecture

A single FastAPI router (`APIRouter(prefix="/v1/diag", tags=["diagnostics"])`) holds 13 endpoints across four families: read-only probes, per-session rescue, queue/task surgery, and rate-limit/auth recovery ([app/api/diagnostics.py:24](../../app/api/diagnostics.py#L24)). The router is mounted in [app/main.py:227](../../app/main.py#L227).

Every route depends on `CurrentUser` (JWT-decoded `User`). Two routes additionally inline-check `user.email == "johndean@vin.com"`. Async routes use the `DbSession` async dependency; routes that call sync services (`init_session_stages`, `auto_place_polls`, `seed_from_env_if_empty`) build a throwaway **synchronous** SQLAlchemy engine from `DATABASE_URL` with `+asyncpg` stripped, then `engine.dispose()` in a `finally` ([app/api/diagnostics.py:226-242](../../app/api/diagnostics.py#L226), [app/api/diagnostics.py:262-278](../../app/api/diagnostics.py#L262), [app/api/diagnostics.py:540-574](../../app/api/diagnostics.py#L540)).

The frontend is a thin layer: the `diag` object in `services/api.ts` wraps each endpoint with the shared `http()` helper; three components and one editor tab call a subset of those methods. `GcsView.vue` (route `/gcs`) is a static-fixture page with no backend call.

```
[Operator/User] ──JWT──> /v1/diag/* (FastAPI router, diagnostics.py)
                              ├─ probes ──────> GCS client (google.cloud.storage)
                              ├─ rescue ──────> Postgres (sessions/segments/session_audit)
                              │                 + Celery (enqueue_ingest / lcs_discrepancies_task)
                              │                 + sync services (session_init / poll_autoplace)
                              │                 + WS bridge (publish_ws_event_sync)
                              ├─ queue surgery > celery_app.control.purge()/.revoke()
                              └─ recovery ────> Redis (sessions:active:*) / auth_users seed
```

## Frontend Components

| Component | Path | Role | Endpoints called |
|---|---|---|---|
| `GcsView.vue` | frontend/src/views/GcsView.vue | Static fixture port of `processing.jsx::GcsRoute` — **no API call** | none |
| `SectionDiagnostics.vue` | frontend/src/components/settings/SectionDiagnostics.vue | Diagnostics landing: card stack + rate-limit reset + drill-ins | `clear-rate-limit-slots` |
| `GCSDebug.vue` | frontend/src/components/settings/GCSDebug.vue | Live G1–G14 probe table | `gcs-checks` |
| `AdminTab.vue` | frontend/src/components/editor/AdminTab.vue | Editor right-rail Rescue panel (admin-only v-if) | `reingest`, `realign`, `init-session-stages`, `autoplace-polls`, `abort-session` |
| `SectionAuthUsers.vue` | frontend/src/components/settings/SectionAuthUsers.vue | Auth recovery panel | `reseed-auth-users` |

- `GcsView` defines a hardcoded `Check[]` of 14 rows and computes `okCount` over them; it never imports the api client ([frontend/src/views/GcsView.vue:11-28](../../frontend/src/views/GcsView.vue#L11)).
- `GCSDebug` loads on mount and on the `gcs-checks-rerun` button; computes `okCount`/`failCount`/`deferredCount`/`totalChecks` over the live response; renders `pass`/`fail`/`deferred` chips by `ok === true | false | null` ([frontend/src/components/settings/GCSDebug.vue:26-29](../../frontend/src/components/settings/GCSDebug.vue#L26), [GCSDebug.vue:113-123](../../frontend/src/components/settings/GCSDebug.vue#L113)).
- `AdminTab` builds a `rescueActions` array of 5 `RescueAction` objects, gates the section on `isAdmin`, and runs each through `runRescue` with a `window.confirm()` and a `rescuing` lock ([frontend/src/components/editor/AdminTab.vue:50-82](../../frontend/src/components/editor/AdminTab.vue#L50)).

## Backend Services

| Endpoint | Backend work | Service / mechanism |
|---|---|---|
| `GET /gcs` | construct `gcs_lib.Client`, `bucket.reload()` | google.cloud.storage ([diagnostics.py:36-56](../../app/api/diagnostics.py#L36)) |
| `GET /classify-route` | read `VERTEX_AI_CLASSIFY_ENABLED`, key presence | settings only ([diagnostics.py:66-84](../../app/api/diagnostics.py#L66)) |
| `GET /gcs-checks` | G1–G6 probes + G7–G14 stubs + audit | `_gcs_time_probe`, `_gcs_put_probe`, `_gcs_acl_check` ([diagnostics.py:624-749](../../app/api/diagnostics.py#L624)) |
| `POST /reingest/{id}` | status→uploading, delete segments, audit, enqueue | `app.tasks.ingest.enqueue_ingest` ([diagnostics.py:94-171](../../app/api/diagnostics.py#L94)) |
| `POST /realign/{id}` | enqueue alignment | `lcs_discrepancies_task.apply_async(queue="celery")` ([diagnostics.py:180-199](../../app/api/diagnostics.py#L180)) |
| `POST /init-session-stages/{id}` | copy Type stage matrix | `app.services.session_init.init_session_stages` ([diagnostics.py:209-242](../../app/api/diagnostics.py#L209)) |
| `POST /autoplace-polls/{id}` | place polls onto anchor segments | `app.services.poll_autoplace.auto_place_polls` ([diagnostics.py:251-278](../../app/api/diagnostics.py#L251)) |
| `POST /clear-rate-limit-slots` | sweep Redis active set | `redis.from_url(settings.REDIS_URL)` ([diagnostics.py:289-328](../../app/api/diagnostics.py#L289)) |
| `POST /sop-check` | run deadline task inline | `sop_check_deadlines_task.apply().get(timeout=60)` ([diagnostics.py:331-346](../../app/api/diagnostics.py#L331)) |
| `POST /flush-celery-queue` | purge broker | `celery_app.control.purge()` ([diagnostics.py:355-388](../../app/api/diagnostics.py#L355)) |
| `POST /revoke-task/{task_id}` | revoke task | `celery_app.control.revoke(..., terminate=, signal='SIGTERM')` ([diagnostics.py:398-423](../../app/api/diagnostics.py#L398)) |
| `POST /abort-session/{id}` | status→failed, audit, WS event | `publish_ws_event_sync` ([diagnostics.py:433-512](../../app/api/diagnostics.py#L433)) |
| `POST /reseed-auth-users` | re-run env seed, audit | `app.services.auth_users.seed_from_env_if_empty` ([diagnostics.py:521-574](../../app/api/diagnostics.py#L521)) |

GCS helpers:
- `_gcs_time_probe(check_id, name, fn)` — times `fn()`, catches all exceptions, returns the `GcsCheckRow`-shaped dict ([diagnostics.py:598-621](../../app/api/diagnostics.py#L598)).
- `_gcs_put_probe(bucket)` — uploads a 1 KB blob to `_diag/gcs-probe-<ts>.bin` then deletes it (R7-safe, outside `sessions/`) ([diagnostics.py:727-736](../../app/api/diagnostics.py#L727)).
- `_gcs_acl_check(bucket)` — returns True if the default object ACL grants no READ to `allUsers`; buckets with uniform bucket-level access raise on iteration and are treated as "not public" (pass) ([diagnostics.py:739-749](../../app/api/diagnostics.py#L739)).

## APIs

All paths are prefixed `/v1/diag`. Auth: every route requires a valid JWT (`CurrentUser`); the **Admin** column marks the only two routes with the inline `johndean@vin.com` gate.

| Method | Path | Request | Response model | Admin? |
|---|---|---|---|---|
| GET | `/gcs` | — | `GcsCheckResult{project_id, bucket, credentials_loaded, bucket_reachable, detail?}` | no |
| GET | `/classify-route` | — | `ClassifyRouteResult{backend, model_id, healthy, detail?}` | no |
| GET | `/gcs-checks` | — | `list[GcsCheckRow]` (14 rows) | **yes** |
| POST | `/reingest/{session_id}` | path id | `ReingestResult{session_id, status_before, enqueued, detail?}` | no |
| POST | `/realign/{session_id}` | path id | `RealignResult{session_id, enqueued, detail?}` | no |
| POST | `/init-session-stages/{session_id}` | path id, `?type_id=` | `InitStagesResult{session_id, type_id, stages, detail?}` | no |
| POST | `/autoplace-polls/{session_id}` | path id | `AutoplacePollsResult{session_id, placed, detail?}` | no |
| POST | `/clear-rate-limit-slots` | — | `ClearSlotsResult{email, removed_count, removed_session_ids, cap, remaining}` | no |
| POST | `/sop-check` | — | `dict {ok, ...}` (no Pydantic model) | no |
| POST | `/flush-celery-queue` | — | `FlushQueueResult{purged, per_worker?, detail?}` | no |
| POST | `/revoke-task/{task_id}` | path id, `?terminate=true` | `RevokeTaskResult{task_id, revoked, terminate, detail?}` | no |
| POST | `/abort-session/{session_id}` | path id | `AbortSessionResult{session_id, status_before, status_after, detail?}` | no |
| POST | `/reseed-auth-users` | — | `ReseedAuthUsersResult{seeded, total, skipped_count}` | **yes** |

Frontend client surface (`services/api.ts` `diag` object, [frontend/src/services/api.ts:1038-1066](../../frontend/src/services/api.ts#L1038)):
- Wired with callers: `gcsChecks`, `clearRateLimitSlots`, `reseedAuthUsers`, `reingest`, `realign`, `initSessionStages`, `autoplacePolls`, `abortSession`.
- Defined but **no caller**: `gcs`, `classifyRoute`, `health` (the last points at `/v1/health`, not a diag route).

> Note: the `sessions.retry(id)` method ([frontend/src/services/api.ts:178-182](../../frontend/src/services/api.ts#L178)) also POSTs `/v1/diag/reingest/{id}` — a second client wrapper of the reingest endpoint outside the `diag` object.

## Data Models

Pydantic response models (all in `diagnostics.py`):
- `GcsCheckResult` ([diagnostics.py:27-32](../../app/api/diagnostics.py#L27)), `ClassifyRouteResult` ([diagnostics.py:59-63](../../app/api/diagnostics.py#L59)), `GcsCheckRow{id, name, ok: bool|None, ms: int, note?}` ([diagnostics.py:590-595](../../app/api/diagnostics.py#L590)).
- `ReingestResult`, `RealignResult`, `InitStagesResult`, `AutoplacePollsResult`, `ClearSlotsResult`, `FlushQueueResult`, `RevokeTaskResult`, `AbortSessionResult`, `ReseedAuthUsersResult`.

Persistent tables touched:
- **sessions** — `SELECT status`, `UPDATE status` (`uploading`/`failed`), `SELECT deleted_at`.
- **segments** — `DELETE WHERE session_id` on reingest.
- **session_audit** — `processing_log JSONB` array, PK `session_id` FK→sessions ON DELETE CASCADE; appended via `processing_log || EXCLUDED.processing_log` on conflict ([migrations/010_state_machine.sql:31-35](../../migrations/010_state_machine.sql#L31)).
- **audit_events** — `(actor_email, kind, summary)` insert for `gcs-checks` and `reseed-auth-users`; nullable `session_id` FK→sessions ON DELETE SET NULL ([migrations/004_audit.sql:3-11](../../migrations/004_audit.sql#L3)).
- **auth_users** — `SELECT count(*)` before/after reseed.

Redis structures:
- `sessions:active:{email}` — set of session ids (`smembers`/`srem`/`scard`).
- `sessions:queue` — list (`lrem`).

Frontend TS types: `ClearSlotsResult`, `GcsCheckRow` ([frontend/src/services/api.ts:1022-1036](../../frontend/src/services/api.ts#L1022)).

## Events

- **WebSocket:** `abort-session` publishes a `session_failed` event (`category="operator_abort"`, `reason="diag/abort-session"`, user message "Session aborted by operator. Reingest or delete to retry.") via `publish_ws_event_sync(session_id, {...})`, wrapped in try/except so a WS failure never fails the abort ([app/api/diagnostics.py:499-508](../../app/api/diagnostics.py#L499)). No other diag route emits a WS event.
- **Celery dispatch:** `reingest` → `enqueue_ingest(session_id)`; `realign` → `lcs_discrepancies_task.apply_async(queue="celery")`; `sop-check` → `sop_check_deadlines_task.apply()` (inline). `flush-celery-queue`/`revoke-task` issue Celery control commands.
- **Domain events / message bus:** none beyond the single WS publish.

## State Management

- **Backend:** stateless request handlers; the module-scoped sync engines are created per-call and disposed in `finally`. Session FSM state lives in the `sessions.status` column; reingest/abort write it directly, bypassing `ALLOWED_TRANSITIONS` (the documented escape hatch).
- **Frontend:** local component refs only — `GCSDebug` (`checks`, `loading`, `lastRunAt`), `SectionDiagnostics` (`view`, `resetting`, `lastReset`), `AdminTab` (`rescuing`). Admin identity comes from `useAuthStore()` (`auth.email`). No Pinia store is dedicated to diagnostics.

## Validation

- Path id existence: `reingest`/`abort-session` `SELECT status` first and raise `404` if absent ([diagnostics.py:110](../../app/api/diagnostics.py#L110), [diagnostics.py:453](../../app/api/diagnostics.py#L453)).
- Admin: `reseed-auth-users`/`gcs-checks` raise `403 {"code":"ADMIN_ONLY"}` if `user.email != "johndean@vin.com"` ([diagnostics.py:534](../../app/api/diagnostics.py#L534), [diagnostics.py:632](../../app/api/diagnostics.py#L632)).
- `abort-session` short-circuits with `status_after=status_before` + detail "already failed — no-op" when already failed ([diagnostics.py:457-461](../../app/api/diagnostics.py#L457)).
- No request-body validation is needed — all inputs are path params or optional query params (`type_id`, `terminate`); FastAPI coerces them.

## Security

- **Transport/auth:** OAuth2 bearer JWT (HS256, signed with `API_SECRET_KEY`, 8h default expiry) via `OAuth2PasswordBearer` with `auto_error=False`; `get_current_user` decodes the token and confirms the user is active (DB-first, env-CSV fallback) ([app/auth.py:161-205](../../app/auth.py#L161)).
- **R7 invariant:** the GCS PUT probe writes only under `gs://<bucket>/_diag/`, never `sessions/`, and deletes immediately ([diagnostics.py:727-736](../../app/api/diagnostics.py#L727)).
- **ACL probe:** G6 fails the check if the bucket's default object ACL grants READ to `allUsers` ([diagnostics.py:739-749](../../app/api/diagnostics.py#L739)).
- **Destructive routes have no confirmation token.** `reingest`, `abort-session`, and `flush-celery-queue` mutate without a server-side guard token; rescue confirmation is a client-side `window.confirm()` only. (CLAUDE.md flags adding a confirmation token as future hardening.)
- **Broad write access:** because only JWT presence is enforced, **any logged-in user can call the per-session rescue and queue-surgery routes** — there is no server-side admin restriction on them.

## Permissions

PERMISSION REALITY (verified): role-based authorization is scaffold-only and **not wired** into diagnostics.

- `app/security/roles.py` defines `is_admin`/`require_admin`/`LEGACY_ADMIN_EMAIL`, explicitly documented as "Phase 8 scaffold only — not yet wired into any endpoint" ([app/security/roles.py:10-19](../../app/security/roles.py#L10)). `diagnostics.py` does **not** import it.
- `get_current_user` never reads `auth_users.role` (migration 045); it only validates the JWT + active flag ([app/auth.py:172-205](../../app/auth.py#L172)).
- The two admin-gated diag routes use **inline** `user.email == "johndean@vin.com"` checks, not the `require_admin` helper.
- Client side: `AdminTab` `isAdmin` is `auth.email.toLowerCase() === 'johndean@vin.com'` — a v-if UX guard, not enforcement ([frontend/src/components/editor/AdminTab.vue:46](../../frontend/src/components/editor/AdminTab.vue#L46)). The router `adminOnly` guard ([frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63)) is applied only to `/admin/help`, not to any diagnostics route.

> Discrepancy: `diagnostics.py:8` docstring claims admin routes "enforce LEGACY_ADMIN_EMAIL via require_admin" — false; the helper is never imported and only 2 routes are gated, via inline checks.

## Integrations

- **Google Cloud Storage** (`google.cloud.storage`) — credential/bucket alignment, signed-URL gen, PUT round-trip, lifecycle/CORS/ACL probes. Uses `settings.GCP_PROJECT_ID`, `settings.GCS_BUCKET`.
- **Redis** (`redis.from_url(settings.REDIS_URL)`) — rate-limit slot sweep.
- **Celery** (`app.tasks.celery_app.celery_app`) — `control.purge()`, `control.revoke()`, plus task dispatch (`enqueue_ingest`, `lcs_discrepancies_task`, `sop_check_deadlines_task`).
- **WS bridge** (`app.engines.ws_bridge.publish_ws_event_sync`) — abort notification.
- **Vertex AI / Gemini** — `classify-route` only *reports* which backend is enabled (`settings.VERTEX_AI_CLASSIFY_ENABLED`, key presence); it does not call either service ([diagnostics.py:66-84](../../app/api/diagnostics.py#L66)).
- **PagerDuty:** NOT VERIFIED IN CODE — referenced only in static UI copy in `GcsView.vue`; no integration exists.

## Background Jobs

The diagnostics module **dispatches** background work but defines no Celery task of its own:
- `reingest` → `enqueue_ingest` (re-runs the full ingest pipeline).
- `realign` → `lcs_discrepancies_task` on the `celery` queue (idempotent; repopulates `word_alignment`).
- `sop-check` → `sop_check_deadlines_task.apply().get(timeout=60)` — runs **inline/synchronously** with a 60s timeout, not enqueued ([diagnostics.py:343](../../app/api/diagnostics.py#L343)).
- `init-session-stages` / `autoplace-polls` run their service synchronously inside the request.
- Queue surgery: `flush-celery-queue` purges all pending broker messages (running tasks finish); `revoke-task` adds the id to every worker's revoked set (TTL ~1h) and optionally SIGTERMs the worker process.

## Error Handling

- **gcs-checks probe isolation:** `_gcs_time_probe` converts any exception to `ok=False` with `"{ExceptionClass}: {message[:160]}"`; client-construction failure marks G1 failed and G2–G6 skipped ([diagnostics.py:614-621](../../app/api/diagnostics.py#L614), [diagnostics.py:648-659](../../app/api/diagnostics.py#L648)). The audit insert is best-effort try/except ([diagnostics.py:719-722](../../app/api/diagnostics.py#L719)).
- **Dispatch failures** (`reingest`, `realign`, `init-session-stages`, `autoplace-polls`, `revoke-task`, `flush-celery-queue`, `sop-check`) are caught and returned as `detail`/`error` strings with the failure flag set, never raising ([diagnostics.py:158-164](../../app/api/diagnostics.py#L158)).
- **flush no-worker:** `control.purge()` returning `None` yields `purged=0` + advisory detail; `int`/`dict` results are normalized ([diagnostics.py:378-388](../../app/api/diagnostics.py#L378)).
- **abort WS publish** is try/except-swallowed so a WS failure never fails the abort ([diagnostics.py:499-508](../../app/api/diagnostics.py#L499)).
- **Frontend:** `ApiError` → `"{status} — {message}"` toasts in `GCSDebug`/`SectionDiagnostics`; `AdminTab` → `"{label} failed — {message}"`.

## Performance Considerations

- **Per-call sync engines:** `init-session-stages`, `autoplace-polls`, and `reseed-auth-users` each `create_engine` + `dispose()` per request — a fresh pool per call, no reuse. Acceptable for rare operator invocations; not a hot path ([diagnostics.py:226-242](../../app/api/diagnostics.py#L226)).
- **gcs-checks latency:** dominated by live GCS round-trips (G3 PUT+DELETE is the slowest real probe); each row carries a measured `ms`. A single check failure cannot stall the others (per-probe try/except).
- **sop-check inline run** blocks the request up to 60s (`get(timeout=60)`) ([diagnostics.py:343](../../app/api/diagnostics.py#L343)).
- **clear-rate-limit-slots** issues one Postgres `SELECT deleted_at` per slot id in the user's Redis set — O(slots), bounded by `MAX_CONCURRENT_SESSIONS` ([diagnostics.py:307-318](../../app/api/diagnostics.py#L307)).
- **flush-celery-queue is global** — purges the entire Rounds queue, so concurrent unrelated work is also dropped; use sparingly ([diagnostics.py:367-370](../../app/api/diagnostics.py#L367)).

## Source Verification
- **Files Used:** app/api/diagnostics.py; app/auth.py; app/security/roles.py; app/main.py; app/services/auth_users.py; app/services/session_init.py; app/services/poll_autoplace.py; migrations/004_audit.sql; migrations/010_state_machine.sql; frontend/src/views/GcsView.vue; frontend/src/components/settings/SectionDiagnostics.vue; frontend/src/components/settings/GCSDebug.vue; frontend/src/components/editor/AdminTab.vue; frontend/src/services/api.ts; frontend/src/router/index.ts
- **Components Used:** GcsView.vue, SectionDiagnostics.vue, GCSDebug.vue, AdminTab.vue, SectionAuthUsers.vue
- **APIs Used:** all 13 /v1/diag/* routes (gcs, classify-route, gcs-checks, reingest, realign, init-session-stages, autoplace-polls, clear-rate-limit-slots, sop-check, flush-celery-queue, revoke-task, abort-session, reseed-auth-users)
- **Database Tables Used:** sessions, segments, session_audit, auth_users, audit_events; Redis keys sessions:active:{email}, sessions:queue
- **Permission Logic Used:** JWT presence (CurrentUser) on every route; inline `user.email == "johndean@vin.com"` (LEGACY_ADMIN_EMAIL) on reseed-auth-users + gcs-checks; client-side isAdmin v-if. roles.py require_admin scaffold NOT wired.
- **Confidence Score:** High — all routes, models, services, and integrations read directly from source; the require_admin-vs-inline and abort-vs-revoke discrepancies are flagged.
- **Evidence Links:** [app/api/diagnostics.py:24](../../app/api/diagnostics.py#L24), [app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534), [app/api/diagnostics.py:343](../../app/api/diagnostics.py#L343), [app/api/diagnostics.py:727](../../app/api/diagnostics.py#L727), [app/auth.py:172](../../app/auth.py#L172), [app/security/roles.py:10](../../app/security/roles.py#L10), [frontend/src/services/api.ts:1038](../../frontend/src/services/api.ts#L1038)
