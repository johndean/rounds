# API Reference — Diagnostics (`/v1/diag`)

Operator diagnostic, manual-rescue, queue-surgery, and auth-recovery router. Source: [app/api/diagnostics.py](../../app/api/diagnostics.py). Registered in [app/main.py:227](../../app/main.py#L227) via `app.include_router(diag_router.router)`.

Router declaration: `APIRouter(prefix="/v1/diag", tags=["diagnostics"])` — [app/api/diagnostics.py:24](../../app/api/diagnostics.py#L24).

These routes have **no UI surface** — they are operator tools intended for curl/Postman use (see CLAUDE.md "Emergency operator commands").

## Authentication & Authorization (router-wide)

- **Authentication:** Every endpoint depends on `CurrentUser` (the `_u: CurrentUser` or `user: CurrentUser` parameter), which is `Annotated[User, Depends(get_current_user)]` ([app/auth.py:208](../../app/auth.py#L208)). A valid HS256 JWT bearer token is required; no token → HTTP 401 "Could not validate credentials" ([app/auth.py:172](../../app/auth.py#L172)).
- **Authorization:** **Most routes in this router are JWT-only** — a valid token for *any* active user passes; there is no admin gate. Only **two** endpoints add an admin check, and they do it with an inline hardcoded comparison, NOT via the `require_admin` helper:
  - `POST /reseed-auth-users` — `if user.email != "johndean@vin.com": raise 403 ADMIN_ONLY` ([app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534)).
  - `GET /gcs-checks` — `if user.email != "johndean@vin.com": raise 403 ADMIN_ONLY` ([app/api/diagnostics.py:632](../../app/api/diagnostics.py#L632)).

  This is a literal-email comparison against `"johndean@vin.com"` (the same value as `LEGACY_ADMIN_EMAIL` in [app/security/roles.py:54](../../app/security/roles.py#L54), but this router does not import or call `require_admin` / `is_admin`). The `auth_users.role` column is not consulted anywhere in this router.

> The module docstring claims "admin-gated routes additionally enforce LEGACY_ADMIN_EMAIL via require_admin" ([app/api/diagnostics.py:8](../../app/api/diagnostics.py#L8)). That is **inaccurate to the code**: the two admin-gated routes use inline `user.email == "johndean@vin.com"` checks and do not call `require_admin`. Documented here as the docstring asserts more than the implementation does.

## Endpoint summary

| # | Method | Path | response_model | Authorization |
|---|---|---|---|---|
| 1 | GET | `/v1/diag/gcs` | `GcsCheckResult` | JWT only |
| 2 | GET | `/v1/diag/classify-route` | `ClassifyRouteResult` | JWT only |
| 3 | POST | `/v1/diag/reingest/{session_id}` | `ReingestResult` | JWT only |
| 4 | POST | `/v1/diag/realign/{session_id}` | `RealignResult` | JWT only |
| 5 | POST | `/v1/diag/init-session-stages/{session_id}` | `InitStagesResult` | JWT only |
| 6 | POST | `/v1/diag/autoplace-polls/{session_id}` | `AutoplacePollsResult` | JWT only |
| 7 | POST | `/v1/diag/clear-rate-limit-slots` | `ClearSlotsResult` | JWT only |
| 8 | POST | `/v1/diag/sop-check` | (plain dict) | JWT only |
| 9 | POST | `/v1/diag/flush-celery-queue` | `FlushQueueResult` | JWT only |
| 10 | POST | `/v1/diag/revoke-task/{task_id}` | `RevokeTaskResult` | JWT only |
| 11 | POST | `/v1/diag/abort-session/{session_id}` | `AbortSessionResult` | JWT only |
| 12 | POST | `/v1/diag/reseed-auth-users` | `ReseedAuthUsersResult` | **JWT + `email == johndean@vin.com`** |
| 13 | GET | `/v1/diag/gcs-checks` | `list[GcsCheckRow]` | **JWT + `email == johndean@vin.com`** |

13 endpoints total — one `@router` decorator each, all enumerated below.

---

## 1. `GET /v1/diag/gcs`

- **Decorator:** `@router.get("/gcs", response_model=GcsCheckResult)` — [app/api/diagnostics.py:35](../../app/api/diagnostics.py#L35)
- **Purpose:** Lightweight GCS QA — constructs a `google.cloud.storage` client for `settings.GCP_PROJECT_ID`, then calls `bucket.reload()` on `settings.GCS_BUCKET` to confirm credentials/project/bucket line up.
- **Authentication:** JWT (`_u: CurrentUser`).
- **Authorization:** JWT only — no admin gate.
- **Request Schema:** None.
- **Response Schema — `GcsCheckResult`** ([app/api/diagnostics.py:27](../../app/api/diagnostics.py#L27)): `{project_id: str, bucket: str, credentials_loaded: bool, bucket_reachable: bool, detail: str | null}`. On any exception, `detail` is `"{ExceptionClass}: {message}"` and the relevant bool stays `false` ([app/api/diagnostics.py:48](../../app/api/diagnostics.py#L48)).
- **Validation Rules:** None.
- **Errors:** `401` (no/invalid token). GCS failures are reported in `detail` with `200`, not raised.
- **Example:** `curl -s -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/gcs`
- **Related Screens:** Settings → Diagnostics (IMPLEMENTATION.md §10 per docstring). NOT VERIFIED IN CODE which Vue view.
- **Related Tables:** none.

---

## 2. `GET /v1/diag/classify-route`

- **Decorator:** `@router.get("/classify-route", response_model=ClassifyRouteResult)` — [app/api/diagnostics.py:66](../../app/api/diagnostics.py#L66)
- **Purpose:** Reports which classification backend is enabled (`vertex_ai` if `settings.VERTEX_AI_CLASSIFY_ENABLED` else `gemini_dev`), which model id (`settings.GEMINI_CLASSIFY_MODEL`), and whether the required credential is present.
- **Authentication:** JWT (`_u: CurrentUser`).
- **Authorization:** JWT only.
- **Request Schema:** None.
- **Response Schema — `ClassifyRouteResult`** ([app/api/diagnostics.py:59](../../app/api/diagnostics.py#L59)): `{backend: str, model_id: str, healthy: bool, detail: str | null}`. For `gemini_dev`, `healthy=false` with `detail="GEMINI_API_KEY not set"` when the key is missing. For `vertex_ai`, `healthy=false` with `detail="GOOGLE_APPLICATION_CREDENTIALS not set for Vertex AI"` when missing ([app/api/diagnostics.py:72-81](../../app/api/diagnostics.py#L72)).
- **Validation Rules:** None.
- **Errors:** `401`.
- **Example:** `curl -s -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/classify-route`
- **Related Screens:** Settings → Diagnostics. NOT VERIFIED IN CODE.
- **Related Tables:** none.

---

## 3. `POST /v1/diag/reingest/{session_id}`

- **Decorator:** `@router.post("/reingest/{session_id}", response_model=ReingestResult)` — [app/api/diagnostics.py:94](../../app/api/diagnostics.py#L94)
- **Purpose:** Re-trigger the ingest pipeline for a session. Resets `sessions.status` to `'uploading'`, deletes all `segments` for the session (so transcribe doesn't no-op via its check-before-execute guard), appends a `session_audit` log entry, then enqueues `ingest_task`. This bypasses the FSM transition table (explicit operator escape hatch).
- **Authentication:** JWT (`_u: CurrentUser`).
- **Authorization:** JWT only — no admin gate.
- **Request Schema:** Path param `session_id: str` (cast to uuid in SQL). `db: DbSession` injected.
- **Response Schema — `ReingestResult`** ([app/api/diagnostics.py:87](../../app/api/diagnostics.py#L87)): `{session_id: str, status_before: str, enqueued: bool, detail: str | null}`. `enqueued` is `false` with the exception in `detail` if `enqueue_ingest` raises ([app/api/diagnostics.py:163](../../app/api/diagnostics.py#L163)).
- **Validation Rules:** Session must exist.
- **Errors:** `404` — `"session {session_id} not found"` when no row ([app/api/diagnostics.py:111](../../app/api/diagnostics.py#L111)). `401`. Enqueue failures are reported in `detail`, not raised.
- **Side effects:** `UPDATE sessions SET status='uploading'`, `DELETE FROM segments`, upsert into `session_audit`, commit, then `enqueue_ingest(session_id)`.
- **Example:** `curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/reingest/<SESSION_ID>`
- **Related Screens:** none (curl-only operator tool).
- **Related Tables:** `sessions` (SELECT/UPDATE), `segments` (DELETE), `session_audit` (UPSERT).

---

## 4. `POST /v1/diag/realign/{session_id}`

- **Decorator:** `@router.post("/realign/{session_id}", response_model=RealignResult)` — [app/api/diagnostics.py:180](../../app/api/diagnostics.py#L180)
- **Purpose:** Manually re-trigger `lcs_discrepancies_task` for an already-ready session so it can populate `word_alignment` (migration 036 was added after some sessions finished STT+LCS). The task is idempotent. Enqueues via `apply_async(queue="celery")`.
- **Authentication:** JWT (`_u: CurrentUser`).
- **Authorization:** JWT only.
- **Request Schema:** Path param `session_id: str`. `_db: DbSession` is injected but unused in the handler body.
- **Response Schema — `RealignResult`** ([app/api/diagnostics.py:174](../../app/api/diagnostics.py#L174)): `{session_id: str, enqueued: bool, detail: str | null}`. `enqueued=false` with exception text in `detail` on failure ([app/api/diagnostics.py:197](../../app/api/diagnostics.py#L197)).
- **Validation Rules:** None (no existence check).
- **Errors:** `401`. Task-enqueue failures are reported in `detail`, not raised.
- **Side effects:** Enqueues `lcs_discrepancies_task` on the `celery` queue.
- **Example:** `curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/realign/<SESSION_ID>`
- **Related Screens:** none.
- **Related Tables:** none written directly here; the enqueued task populates `word_alignment` (NOT VERIFIED IN CODE within this file — stated by docstring).

---

## 5. `POST /v1/diag/init-session-stages/{session_id}`

- **Decorator:** `@router.post("/init-session-stages/{session_id}", response_model=InitStagesResult)` — [app/api/diagnostics.py:209](../../app/api/diagnostics.py#L209)
- **Purpose:** Manually fire `session_stage_assignees` initialization for a session (for sessions ingested before the auto-init hook, or after a Type change). Calls `init_session_stages(engine, session_id, type_id=..., actor="diag/init-session-stages")` on a synchronous engine. Idempotent — only writes stages without an existing assignee.
- **Authentication:** JWT (`_u: CurrentUser`).
- **Authorization:** JWT only.
- **Request Schema:** Path param `session_id: str`; optional query param `type_id: str | null` (default `None`) to force a specific Type. `_db: DbSession` injected but unused (a fresh sync engine is built from `settings.DATABASE_URL`).
- **Response Schema — `InitStagesResult`** ([app/api/diagnostics.py:202](../../app/api/diagnostics.py#L202)): `{session_id: str, type_id: str | null, stages: int, detail: str | null}`. On exception, `stages=0` and `detail` carries the error ([app/api/diagnostics.py:236](../../app/api/diagnostics.py#L236)).
- **Validation Rules:** None at the route layer.
- **Errors:** `401`. Service-layer failures are caught and returned in `detail`, not raised.
- **Side effects:** Writes rows into `session_stage_assignees` via the `init_session_stages` service ([app/services/session_init.py](../../app/services/session_init.py)).
- **Example:** `curl -s -X POST -H "Authorization: Bearer $TOKEN" "https://rounds.vin/v1/diag/init-session-stages/<SESSION_ID>?type_id=<UUID>"`
- **Related Screens:** none.
- **Related Tables:** `session_stage_assignees` (via service). Other tables read by the service NOT VERIFIED IN CODE within this file.

---

## 6. `POST /v1/diag/autoplace-polls/{session_id}`

- **Decorator:** `@router.post("/autoplace-polls/{session_id}", response_model=AutoplacePollsResult)` — [app/api/diagnostics.py:251](../../app/api/diagnostics.py#L251)
- **Purpose:** Manually fire poll auto-placement for an already-ingested session (backfill for sessions completed before the autoplace service was wired). Calls `auto_place_polls(engine, session_id)` on a sync engine. Idempotent — only places polls with `anchor_segment IS NULL`.
- **Authentication:** JWT (`_u: CurrentUser`).
- **Authorization:** JWT only.
- **Request Schema:** Path param `session_id: str`. `_db: DbSession` injected but unused.
- **Response Schema — `AutoplacePollsResult`** ([app/api/diagnostics.py:245](../../app/api/diagnostics.py#L245)): `{session_id: str, placed: int, detail: str | null}`. On exception, `placed=0` and `detail` carries the error ([app/api/diagnostics.py:272](../../app/api/diagnostics.py#L272)).
- **Validation Rules:** None at the route layer.
- **Errors:** `401`. Service-layer failures returned in `detail`, not raised.
- **Side effects:** Updates poll placement rows via `auto_place_polls` ([app/services/poll_autoplace.py](../../app/services/poll_autoplace.py)). Exact tables NOT VERIFIED IN CODE within this file.
- **Example:** `curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/autoplace-polls/<SESSION_ID>`
- **Related Screens:** none.
- **Related Tables:** poll-related tables via service (NOT VERIFIED IN CODE within this file).

---

## 7. `POST /v1/diag/clear-rate-limit-slots`

- **Decorator:** `@router.post("/clear-rate-limit-slots", response_model=ClearSlotsResult)` — [app/api/diagnostics.py:289](../../app/api/diagnostics.py#L289)
- **Purpose:** Sweep the Redis active-sessions set (`sessions:active:{email}`) for the **calling user** and remove any slot whose `session_id` is soft-deleted (`deleted_at IS NOT NULL`) or missing in the DB. Unblocks `429 RATE_LIMIT_USER` left by pre-fix create+delete leakage. Idempotent; slots for live sessions are preserved.
- **Authentication:** JWT (`_u: CurrentUser`). The Redis key is scoped to `_u.email`.
- **Authorization:** JWT only — operates only on the caller's own slots (no admin gate, none needed).
- **Request Schema:** None. `db: DbSession` injected.
- **Response Schema — `ClearSlotsResult`** ([app/api/diagnostics.py:281](../../app/api/diagnostics.py#L281)): `{email: str, removed_count: int, removed_session_ids: list[str], cap: int, remaining: int}`. `cap` is `settings.MAX_CONCURRENT_SESSIONS` ([app/api/diagnostics.py:324](../../app/api/diagnostics.py#L324)).
- **Validation Rules:** None.
- **Errors:** `401`. Redis errors would propagate (no broad catch around the connection itself; the connection is closed in a `finally`).
- **Side effects:** `SREM sessions:active:{email}` and `LREM sessions:queue` for each released slot in Redis ([app/api/diagnostics.py:316-317](../../app/api/diagnostics.py#L316)). Reads `sessions.deleted_at`.
- **Example:** `curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/clear-rate-limit-slots`
- **Related Screens:** none.
- **Related Tables:** `sessions` (SELECT `deleted_at`). Also touches Redis keys `sessions:active:{email}` and `sessions:queue`.

---

## 8. `POST /v1/diag/sop-check`

- **Decorator:** `@router.post("/sop-check")` — [app/api/diagnostics.py:331](../../app/api/diagnostics.py#L331)
- **Purpose:** Run `sop_check_deadlines_task` synchronously (`.apply().get(timeout=60)`) and return its result, so an operator can spot-check overdue stages without waiting for the next Celery Beat tick.
- **Authentication:** JWT (`_u: CurrentUser`).
- **Authorization:** JWT only.
- **Request Schema:** None.
- **Response Schema:** Plain `dict` (no `response_model`). Success: `{"ok": true, ...task_result}` where the task's returned dict is spread in ([app/api/diagnostics.py:344](../../app/api/diagnostics.py#L344)). Failure: `{"ok": false, "error": "{ExceptionClass}: {message}"}` ([app/api/diagnostics.py:346](../../app/api/diagnostics.py#L346)).
- **Validation Rules:** None.
- **Errors:** `401`. Task failures are caught and returned as `{"ok": false, "error": ...}` with `200`, not raised.
- **Side effects:** Whatever `sop_check_deadlines_task` does ([app/tasks/sop_tasks.py](../../app/tasks/sop_tasks.py)) — runs inline in the request process.
- **Example:** `curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/sop-check`
- **Related Screens:** none.
- **Related Tables:** none directly here; the task reads/writes SOP deadline state (NOT VERIFIED IN CODE within this file).

---

## 9. `POST /v1/diag/flush-celery-queue`

- **Decorator:** `@router.post("/flush-celery-queue", response_model=FlushQueueResult)` — [app/api/diagnostics.py:355](../../app/api/diagnostics.py#L355)
- **Purpose:** Drain ALL pending messages from the Celery broker via `celery_app.control.purge()`. Purges queued-but-not-yet-started messages (running tasks finish). No per-session filter.
- **Authentication:** JWT (`_u: CurrentUser`).
- **Authorization:** JWT only — note this is **not** admin-gated despite being a destructive queue-wide operation.
- **Request Schema:** None.
- **Response Schema — `FlushQueueResult`** ([app/api/diagnostics.py:349](../../app/api/diagnostics.py#L349)): `{purged: int, per_worker: dict | null, detail: str | null}`. `purge()` return is normalized: a `dict[worker, count]` sets `purged=sum(...)` and `per_worker=raw`; an `int` sets `purged=raw`; `None` → `purged=0` with `detail="no workers responded ..."`; any other type → `purged=0` with a type note ([app/api/diagnostics.py:378-386](../../app/api/diagnostics.py#L378)).
- **Validation Rules:** None.
- **Errors:** `401`. Broker exceptions are caught and returned as `purged=0` with `detail`, not raised.
- **Side effects:** Purges the entire Celery broker queue.
- **Example:** `curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/flush-celery-queue`
- **Related Screens:** none.
- **Related Tables:** none (Celery broker only).

---

## 10. `POST /v1/diag/revoke-task/{task_id}`

- **Decorator:** `@router.post("/revoke-task/{task_id}", response_model=RevokeTaskResult)` — [app/api/diagnostics.py:398](../../app/api/diagnostics.py#L398)
- **Purpose:** Revoke a running Celery task by id via `celery_app.control.revoke(task_id, terminate=terminate, signal='SIGTERM')`. Adds the id to every worker's revoked set (TTL 1h) and, when `terminate=True`, signals the worker process.
- **Authentication:** JWT (`_u: CurrentUser`).
- **Authorization:** JWT only.
- **Request Schema:** Path param `task_id: str`; query param `terminate: bool = True` (default `true`) ([app/api/diagnostics.py:399](../../app/api/diagnostics.py#L399)).
- **Response Schema — `RevokeTaskResult`** ([app/api/diagnostics.py:391](../../app/api/diagnostics.py#L391)): `{task_id: str, revoked: bool, terminate: bool, detail: str | null}`. On exception, `revoked=false` with the error in `detail` ([app/api/diagnostics.py:419](../../app/api/diagnostics.py#L419)).
- **Validation Rules:** None.
- **Errors:** `401`. Control-channel failures are caught and returned in `detail`, not raised.
- **Side effects:** Revokes/terminates the named Celery task.
- **Example:** `curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/revoke-task/<TASK_ID>`
- **Related Screens:** none.
- **Related Tables:** none.

---

## 11. `POST /v1/diag/abort-session/{session_id}`

- **Decorator:** `@router.post("/abort-session/{session_id}", response_model=AbortSessionResult)` — [app/api/diagnostics.py:433](../../app/api/diagnostics.py#L433)
- **Purpose:** Force a session into `'failed'` status, bypassing the FSM `ALLOWED_TRANSITIONS` (companion to `/flush-celery-queue`). Appends a `session_audit` log entry and publishes a `session_failed` WS event so open SessionDetail/Processing tabs break out of "Preparing files".
- **Authentication:** JWT (`_u: CurrentUser`).
- **Authorization:** JWT only.
- **Request Schema:** Path param `session_id: str`. `db: DbSession` injected.
- **Response Schema — `AbortSessionResult`** ([app/api/diagnostics.py:426](../../app/api/diagnostics.py#L426)): `{session_id: str, status_before: str, status_after: str, detail: str | null}`. If the session is already `'failed'`, returns a no-op result with `detail="already failed — no-op"` and `status_after = status_before` ([app/api/diagnostics.py:457-461](../../app/api/diagnostics.py#L457)).
- **Validation Rules:** Session must exist.
- **Errors:** `404` — `"session {session_id} not found"` ([app/api/diagnostics.py:454](../../app/api/diagnostics.py#L454)). `401`. The WS publish is wrapped in a best-effort `try/except` and never affects the response ([app/api/diagnostics.py:499-508](../../app/api/diagnostics.py#L499)).
- **Side effects:** `UPDATE sessions SET status='failed'`, upsert into `session_audit`, commit, then `publish_ws_event_sync` (best-effort).
- **Example:** `curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/abort-session/<SESSION_ID>`
- **Related Screens:** SessionDetail / ProcessingView (consume the `session_failed` WS event — referenced in docstring; exact Vue views NOT VERIFIED IN CODE).
- **Related Tables:** `sessions` (SELECT/UPDATE), `session_audit` (UPSERT).

---

## 12. `POST /v1/diag/reseed-auth-users`

- **Decorator:** `@router.post("/reseed-auth-users", response_model=ReseedAuthUsersResult)` — [app/api/diagnostics.py:521](../../app/api/diagnostics.py#L521)
- **Purpose:** Admin-only escape hatch — re-run the boot-time `AUTH_USERS` env seed against the live DB via `seed_from_env_if_empty`. Idempotent: if `auth_users` already has rows, returns `seeded=0` with no writes. Avoids a redeploy to re-fire the lifespan seed hook after a prior seed failure left the table empty.
- **Authentication:** JWT (`user: CurrentUser`).
- **Authorization:** **JWT + inline admin gate.** `if not hasattr(user, "email") or user.email != "johndean@vin.com": raise HTTPException(403, {"code": "ADMIN_ONLY", "message": "admin only"})` ([app/api/diagnostics.py:534-538](../../app/api/diagnostics.py#L534)). This is a hardcoded literal-email check; it does NOT call `require_admin`.
- **Request Schema:** None. `db: DbSession` injected.
- **Response Schema — `ReseedAuthUsersResult`** ([app/api/diagnostics.py:515](../../app/api/diagnostics.py#L515)): `{seeded: int, total: int, skipped_count: int}`. `seeded` = rows inserted by this call (0 if table already populated); `total` = `count(*)` after; `skipped_count` = `max(0, env_entries - after)` where `env_entries = len(_parse_auth_users(AUTH_USERS))` ([app/api/diagnostics.py:567-571](../../app/api/diagnostics.py#L567)).
- **Validation Rules:** Caller email must equal `johndean@vin.com`.
- **Errors:** `403` — `{"code": "ADMIN_ONLY", "message": "admin only"}` for non-admin callers. `401` — no/invalid token.
- **Side effects:** May INSERT into `auth_users` (via `seed_from_env_if_empty`); always INSERTs an audit row into `audit_events` (`kind='diag.reseed_auth_users'`, summary `before=.. seeded=.. after=..`) and commits ([app/api/diagnostics.py:558-565](../../app/api/diagnostics.py#L558)). Uses a separate synchronous engine for the seed.
- **Example:** `curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/reseed-auth-users`
- **Related Screens:** none.
- **Related Tables:** `auth_users` (SELECT count, INSERT via seed), `audit_events` (INSERT).

---

## 13. `GET /v1/diag/gcs-checks`

- **Decorator:** `@router.get("/gcs-checks", response_model=list[GcsCheckRow])` — [app/api/diagnostics.py:624](../../app/api/diagnostics.py#L624)
- **Purpose:** Run the GCS QA probe suite. Six real probes (G1–G6) plus eight explicit "deferred" stubs (G7–G14) returning `ok=null`. Each real probe is time-wrapped and try/except-guarded so one failure can't 500 the endpoint. Logs an `audit_events` row. R7-safe: the G3 PUT round-trip writes/deletes under `gs://<bucket>/_diag/`, never `sessions/`.
- **Authentication:** JWT (`user: CurrentUser`).
- **Authorization:** **JWT + inline admin gate.** Same hardcoded check as #12: `if not hasattr(user, "email") or user.email != "johndean@vin.com": raise 403 ADMIN_ONLY` ([app/api/diagnostics.py:632-636](../../app/api/diagnostics.py#L632)). Does NOT call `require_admin`.
- **Request Schema:** None. `db: DbSession` injected.
- **Response Schema — `list[GcsCheckRow]`** ([app/api/diagnostics.py:590](../../app/api/diagnostics.py#L590)): each row `{id: str, name: str, ok: bool | null, ms: int, note: str | null}`. `id` is `"G1".."G14"`; `ok=null` marks deferred stubs (`note="deferred"`); a failed real probe yields `ok=false` with `note="{ExceptionClass}: {message[:160]}"`. If the GCS client fails to construct, G1 is `ok=false` with the error and G2–G6 become `(skipped — client unavailable)` rows ([app/api/diagnostics.py:651-659](../../app/api/diagnostics.py#L651)).
  Real probes: G1 Bucket reachable, G2 Signed URL generation, G3 PUT round-trip to `_diag/`, G4 Lifecycle policy present, G5 CORS configured, G6 Default object ACL not public ([app/api/diagnostics.py:661-688](../../app/api/diagnostics.py#L661)). Deferred labels G7–G14 listed at [app/api/diagnostics.py:693-702](../../app/api/diagnostics.py#L693).
- **Validation Rules:** Caller email must equal `johndean@vin.com`.
- **Errors:** `403` — `{"code": "ADMIN_ONLY", "message": "admin only"}`. `401`. Individual probe failures are reported in-row (`ok=false`), never raised. The audit insert is best-effort (wrapped in try/except).
- **Side effects:** A 1 KB blob is written to and immediately deleted from `gs://<bucket>/_diag/` during G3 ([app/api/diagnostics.py:727](../../app/api/diagnostics.py#L727)). Best-effort INSERT into `audit_events` (`kind='diag.gcs_checks'`, summary `real_passed=N/M bucket=...`) ([app/api/diagnostics.py:711-718](../../app/api/diagnostics.py#L711)).
- **Example:** `curl -s -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/gcs-checks`
- **Related Screens:** Per the module comment this replaces the static `GCSDebug.vue` fixture page ([app/api/diagnostics.py:582](../../app/api/diagnostics.py#L582)); the live consumer view is NOT VERIFIED IN CODE within this file.
- **Related Tables:** `audit_events` (best-effort INSERT). Also exercises GCS (not a DB table).

---

## Notes

- All 13 `@router` decorators are enumerated above.
- Eleven endpoints are **JWT-only** (any authenticated user). Only `/reseed-auth-users` (#12) and `/gcs-checks` (#13) add an authorization check, and both use an inline hardcoded `user.email == "johndean@vin.com"` comparison rather than the `require_admin`/`is_admin` helper in `app/security/roles.py`. The module docstring's claim that admin routes "enforce LEGACY_ADMIN_EMAIL via require_admin" is inaccurate to the implementation.
- Many handlers swallow downstream exceptions and report them in a `detail`/`error` field with `200` rather than raising HTTP errors — only `reingest` and `abort-session` raise `404` (session-not-found), and the two admin routes raise `403`.

## Source Verification
- **Files Used:** app/api/diagnostics.py, app/auth.py, app/security/roles.py, app/main.py, migrations/030_email_attempts.sql (for cross-reference of audit-table pattern)
- **Components Used:** none (frontend consumers such as GCSDebug.vue / SessionDetail / ProcessingView referenced in docstrings only — NOT VERIFIED IN CODE within this assignment)
- **APIs Used:** /v1/diag/gcs, /v1/diag/classify-route, /v1/diag/reingest/{id}, /v1/diag/realign/{id}, /v1/diag/init-session-stages/{id}, /v1/diag/autoplace-polls/{id}, /v1/diag/clear-rate-limit-slots, /v1/diag/sop-check, /v1/diag/flush-celery-queue, /v1/diag/revoke-task/{id}, /v1/diag/abort-session/{id}, /v1/diag/reseed-auth-users, /v1/diag/gcs-checks
- **Database Tables Used:** sessions (SELECT/UPDATE/DELETE-via-segments), segments (DELETE), session_audit (UPSERT), session_stage_assignees (via service), auth_users (SELECT/INSERT), audit_events (INSERT). Also Redis keys `sessions:active:{email}` / `sessions:queue` and the Celery broker (not DB tables).
- **Permission Logic Used:** JWT (`get_current_user`) for all routes; PLUS an inline hardcoded `user.email == "johndean@vin.com"` (LEGACY_ADMIN_EMAIL value) gate on `/reseed-auth-users` and `/gcs-checks` only. `require_admin`/`is_admin` and `auth_users.role` are NOT used in this router.
- **Confidence Score:** High — every endpoint, Pydantic model, auth dependency, and admin gate was read directly from app/api/diagnostics.py; cross-router auth verified in app/auth.py and app/security/roles.py.
- **Evidence Links:** [app/api/diagnostics.py:24](../../app/api/diagnostics.py#L24), [app/api/diagnostics.py:35](../../app/api/diagnostics.py#L35), [app/api/diagnostics.py:94](../../app/api/diagnostics.py#L94), [app/api/diagnostics.py:355](../../app/api/diagnostics.py#L355), [app/api/diagnostics.py:398](../../app/api/diagnostics.py#L398), [app/api/diagnostics.py:433](../../app/api/diagnostics.py#L433), [app/api/diagnostics.py:521](../../app/api/diagnostics.py#L521), [app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534), [app/api/diagnostics.py:624](../../app/api/diagnostics.py#L624), [app/api/diagnostics.py:632](../../app/api/diagnostics.py#L632), [app/auth.py:172](../../app/auth.py#L172), [app/security/roles.py:54](../../app/security/roles.py#L54), [app/main.py:227](../../app/main.py#L227)
