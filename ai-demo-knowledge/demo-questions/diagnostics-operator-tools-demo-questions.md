# Diagnostics & Operator Tools — Demo Questions

> Module key: `diagnostics-operator-tools`. Every answer below is verified against the source files in the Source Verification block. Paths are relative to this file (`ai-demo-knowledge/demo-questions/`).

## User

### Q: I keep getting a "429 RATE_LIMIT_USER" error after deleting a session. Can I fix it myself?
- **Verified Answer:** Yes. Go to Settings → Diagnostics and click "Reset my stale slots". This calls `POST /v1/diag/clear-rate-limit-slots`, which sweeps your Redis active-sessions set and removes any slot whose session is soft-deleted or no longer exists, while preserving live ones. A toast reports how many were cleared and your `remaining/cap`. Any logged-in user can run this for their own account — no admin required.
- **Supporting Evidence:** Endpoint sweeps `sessions:active:{email}`, releases slots where the session is missing or `deleted_at IS NOT NULL`, returns `removed_count`/`remaining`/`cap` ([app/api/diagnostics.py:289-328](../../app/api/diagnostics.py#L289)). UI button + toast ([frontend/src/components/settings/SectionDiagnostics.vue:22-40](../../frontend/src/components/settings/SectionDiagnostics.vue#L22)).
- **Source Files:** app/api/diagnostics.py; frontend/src/components/settings/SectionDiagnostics.vue
- **API References:** POST /v1/diag/clear-rate-limit-slots
- **Database References:** sessions (deleted_at); Redis sessions:active:{email}, sessions:queue

### Q: Where can I see whether the GCS pipeline checks are passing?
- **Verified Answer:** Settings → Diagnostics → GCS Pipeline QA. It runs a live probe suite on open (and on "Re-run checks") and shows 14 rows: six real probes (bucket reachable, signed-URL generation, PUT round-trip, lifecycle policy, CORS, default-object-ACL) plus eight deferred stubs labeled "deferred" so they aren't mistaken for healthy.
- **Supporting Evidence:** `GCSDebug.vue` calls `GET /v1/diag/gcs-checks` on mount + rerun ([frontend/src/components/settings/GCSDebug.vue:31-46](../../frontend/src/components/settings/GCSDebug.vue#L31)); backend returns G1–G6 real + G7–G14 deferred ([app/api/diagnostics.py:624-704](../../app/api/diagnostics.py#L624)).
- **Source Files:** frontend/src/components/settings/GCSDebug.vue; app/api/diagnostics.py
- **API References:** GET /v1/diag/gcs-checks
- **Database References:** audit_events (probe run is logged)

### Q: The standalone `/gcs` page shows 13/14 checks passing with a 5-minute cadence — is that live?
- **Verified Answer:** No. The `/gcs` page (`GcsView.vue`) is a static fixture: the 14 rows, the "5-minute cadence", "PagerDuty after two consecutive misses", and "99.98% uptime" are hardcoded display text with no backend call. For live results use Settings → Diagnostics → GCS Pipeline QA instead.
- **Supporting Evidence:** Hardcoded `checks` array and static copy ([frontend/src/views/GcsView.vue:11-40](../../frontend/src/views/GcsView.vue#L11)); the file imports no API client.
- **Source Files:** frontend/src/views/GcsView.vue
- **API References:** none
- **Database References:** none

## Operations

### Q: A session is stuck. What manual rescue actions are available, and where?
- **Verified Answer:** Open the session in the editor, go to the right-rail Admin tab. The Rescue panel (visible to the admin only) has five buttons: Re-ingest pipeline (`/v1/diag/reingest/{id}`), Re-run alignment (`/realign/{id}`), Initialize SOP stages (`/init-session-stages/{id}`), Auto-place polls (`/autoplace-polls/{id}`), and Force-abort session (`/abort-session/{id}`). Each prompts a browser confirmation before dispatch.
- **Supporting Evidence:** `rescueActions` array of 5 entries mapped to `diag.*` calls, gated by `isAdmin`, run through `runRescue` with `window.confirm` ([frontend/src/components/editor/AdminTab.vue:58-82](../../frontend/src/components/editor/AdminTab.vue#L58), [AdminTab.vue:178-199](../../frontend/src/components/editor/AdminTab.vue#L178)).
- **Source Files:** frontend/src/components/editor/AdminTab.vue; app/api/diagnostics.py
- **API References:** POST /v1/diag/reingest/{id}, /realign/{id}, /init-session-stages/{id}, /autoplace-polls/{id}, /abort-session/{id}
- **Database References:** sessions, segments, session_audit

### Q: What exactly does "Re-ingest" do to a session?
- **Verified Answer:** It resets the session status to `uploading` (bypassing the state machine), deletes all existing `segments` rows for that session so the transcribe step doesn't no-op, appends a `session_audit` log entry recording the prev→next status, commits, and then enqueues `ingest_task` to re-run the full pipeline. If the session id doesn't exist it returns 404.
- **Supporting Evidence:** UPDATE status→uploading, DELETE segments, INSERT session_audit, `enqueue_ingest` ([app/api/diagnostics.py:104-171](../../app/api/diagnostics.py#L104)).
- **Source Files:** app/api/diagnostics.py
- **API References:** POST /v1/diag/reingest/{id}
- **Database References:** sessions (status), segments (deleted), session_audit (processing_log)

### Q: Does "Force-abort session" actually kill the running Celery task?
- **Verified Answer:** No. Despite the button copy ("kill any in-flight Celery task"), `abort-session` only sets the session status to `failed`, appends a `session_audit` entry, and publishes a `session_failed` WebSocket event so open tabs leave the "Preparing files" loop. It does not call Celery `revoke()`. To actually revoke a running task you must call `/v1/diag/revoke-task/{task_id}` separately. This is a known UI-copy vs backend discrepancy.
- **Supporting Evidence:** abort handler only UPDATEs status + audit + WS publish, no revoke ([app/api/diagnostics.py:463-508](../../app/api/diagnostics.py#L463)); button desc claims it kills the task ([frontend/src/components/editor/AdminTab.vue:63](../../frontend/src/components/editor/AdminTab.vue#L63)).
- **Source Files:** app/api/diagnostics.py; frontend/src/components/editor/AdminTab.vue
- **API References:** POST /v1/diag/abort-session/{id}; POST /v1/diag/revoke-task/{task_id}
- **Database References:** sessions (status), session_audit

### Q: After a reingest stampede I have redundant tasks queued. How do I clear the queue?
- **Verified Answer:** `POST /v1/diag/flush-celery-queue` calls `celery_app.control.purge()` to drain all pending broker messages; currently-running tasks finish (purge can't cancel mid-execution). It is global — there is no per-session filter — so use it sparingly. Pair it with `/abort-session/{id}` to break the target session out of `uploading`. If no workers respond it returns `purged=0` with an advisory note.
- **Supporting Evidence:** `control.purge()` with int/dict/None normalization ([app/api/diagnostics.py:355-388](../../app/api/diagnostics.py#L355)).
- **Source Files:** app/api/diagnostics.py
- **API References:** POST /v1/diag/flush-celery-queue
- **Database References:** none (Celery broker)

### Q: How do I revoke one specific runaway task without flushing the whole queue?
- **Verified Answer:** `POST /v1/diag/revoke-task/{task_id}` calls `celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')` — it adds the id to every worker's revoked set (TTL ~1h) and SIGTERMs the worker handling it. Pass `?terminate=false` to skip the SIGTERM. Get the `task_id` from Celery logs or Flower.
- **Supporting Evidence:** revoke call + `terminate` query param default True ([app/api/diagnostics.py:398-423](../../app/api/diagnostics.py#L398)).
- **Source Files:** app/api/diagnostics.py
- **API References:** POST /v1/diag/revoke-task/{task_id}?terminate=
- **Database References:** none (Celery control)

### Q: Can I run the SOP deadline check on demand instead of waiting for the Beat tick?
- **Verified Answer:** Yes. `POST /v1/diag/sop-check` runs `sop_check_deadlines_task` inline (`.apply().get(timeout=60)`) and returns `{ok: true, ...}` with the task result, or `{ok: false, error: ...}` on failure. It blocks up to 60 seconds.
- **Supporting Evidence:** inline apply+get with 60s timeout ([app/api/diagnostics.py:331-346](../../app/api/diagnostics.py#L331)).
- **Source Files:** app/api/diagnostics.py
- **API References:** POST /v1/diag/sop-check
- **Database References:** none directly (task internals)

## Administrator

### Q: Which diagnostics endpoints are actually admin-restricted on the server?
- **Verified Answer:** Only two: `GET /v1/diag/gcs-checks` and `POST /v1/diag/reseed-auth-users`. Both raise `403 {"code":"ADMIN_ONLY"}` unless `user.email == "johndean@vin.com"`. All other `/v1/diag/*` routes only require a valid JWT — any logged-in user can call the per-session rescue, queue-flush, and revoke routes. The editor Rescue panel hides those buttons for non-admins, but that is a client-side UX guard only, not server enforcement.
- **Supporting Evidence:** inline email gates ([app/api/diagnostics.py:534-538](../../app/api/diagnostics.py#L534), [app/api/diagnostics.py:632-636](../../app/api/diagnostics.py#L632)); every route depends on `CurrentUser` only ([app/auth.py:208](../../app/auth.py#L208)); client v-if ([frontend/src/components/editor/AdminTab.vue:46](../../frontend/src/components/editor/AdminTab.vue#L46)).
- **Source Files:** app/api/diagnostics.py; app/auth.py; frontend/src/components/editor/AdminTab.vue
- **API References:** GET /v1/diag/gcs-checks; POST /v1/diag/reseed-auth-users
- **Database References:** auth_users

### Q: Login is broken because `auth_users` is empty after a Railway env change. How do I recover without a redeploy?
- **Verified Answer:** As admin, open Settings → Auth & Logins recovery panel and trigger reseed, or curl `POST /v1/diag/reseed-auth-users`. It re-runs the boot-time `seed_from_env_if_empty` against the live DB from the `AUTH_USERS` env CSV and returns `{seeded, total, skipped_count}`. It is idempotent — if the table already has rows it returns `seeded:0` with no writes. The action is logged to `audit_events`.
- **Supporting Evidence:** reseed handler calls `seed_from_env_if_empty`, writes audit row ([app/api/diagnostics.py:521-572](../../app/api/diagnostics.py#L521)); seed idempotency ([app/services/auth_users.py:199-203](../../app/services/auth_users.py#L199)); UI caller ([frontend/src/components/settings/SectionAuthUsers.vue:242](../../frontend/src/components/settings/SectionAuthUsers.vue#L242)).
- **Source Files:** app/api/diagnostics.py; app/services/auth_users.py; frontend/src/components/settings/SectionAuthUsers.vue
- **API References:** POST /v1/diag/reseed-auth-users
- **Database References:** auth_users, audit_events

### Q: How do I check the GCS credentials and which classification backend is live?
- **Verified Answer:** Two read-only endpoints (curl-only — they have no UI surface): `GET /v1/diag/gcs` returns `{project_id, bucket, credentials_loaded, bucket_reachable, detail}` by constructing a GCS client and reloading the bucket; `GET /v1/diag/classify-route` reports `backend` ("vertex_ai" if `VERTEX_AI_CLASSIFY_ENABLED` else "gemini_dev"), `model_id`, and `healthy` based on whether the relevant key/credential is set. Both require only a JWT.
- **Supporting Evidence:** gcs probe ([app/api/diagnostics.py:35-56](../../app/api/diagnostics.py#L35)); classify-route ([app/api/diagnostics.py:66-84](../../app/api/diagnostics.py#L66)). No `.vue` calls `diag.gcs`/`diag.classifyRoute` (verified).
- **Source Files:** app/api/diagnostics.py
- **API References:** GET /v1/diag/gcs; GET /v1/diag/classify-route
- **Database References:** none

### Q: Is the role-based admin system live? Why is admin just one email?
- **Verified Answer:** Role-based auth is scaffold-only. `app/security/roles.py` defines `is_admin`/`require_admin` but is documented as "not yet wired into any endpoint", and `get_current_user` never reads `auth_users.role`. The only real admin gate is the hardcoded `user.email == "johndean@vin.com"` (the `LEGACY_ADMIN_EMAIL` constant), used inline in two diag routes plus a few other endpoints, mirrored by a client-side check. So "admin" is effectively one email today.
- **Supporting Evidence:** scaffold note ([app/security/roles.py:10-19](../../app/security/roles.py#L10)); `get_current_user` reads only JWT + active ([app/auth.py:172-205](../../app/auth.py#L172)); inline gate ([app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534)).
- **Source Files:** app/security/roles.py; app/auth.py; app/api/diagnostics.py
- **API References:** GET /v1/diag/gcs-checks; POST /v1/diag/reseed-auth-users
- **Database References:** auth_users (role column exists but unread)

## Compliance

### Q: Which operator actions are recorded in an audit trail?
- **Verified Answer:** Four diagnostics actions write audit records. `reingest` and `abort-session` append a `{ts, prev, next, actor, reason}` entry to the per-session `session_audit.processing_log` (actors `diag/reingest`, `diag/abort-session`). `gcs-checks` and `reseed-auth-users` insert a row into the global `audit_events` table with `actor_email` and a `kind` of `diag.gcs_checks` / `diag.reseed_auth_users`. `init-session-stages` passes `actor="diag/init-session-stages"` to its service. The remaining routes (realign, autoplace-polls, clear-rate-limit-slots, flush-celery-queue, revoke-task, sop-check) write no diag-specific audit row.
- **Supporting Evidence:** reingest/abort session_audit ([app/api/diagnostics.py:142-153](../../app/api/diagnostics.py#L142), [app/api/diagnostics.py:482-493](../../app/api/diagnostics.py#L482)); gcs-checks/reseed audit_events ([app/api/diagnostics.py:711-717](../../app/api/diagnostics.py#L711), [app/api/diagnostics.py:558-564](../../app/api/diagnostics.py#L558)).
- **Source Files:** app/api/diagnostics.py; migrations/004_audit.sql; migrations/010_state_machine.sql
- **API References:** /v1/diag/reingest, /abort-session, /gcs-checks, /reseed-auth-users, /init-session-stages
- **Database References:** session_audit, audit_events

### Q: Does the GCS PUT health probe write into customer session storage?
- **Verified Answer:** No. The PUT round-trip probe writes a 1 KB blob strictly to `gs://<bucket>/_diag/gcs-probe-<ts>.bin` and deletes it immediately — never under the `sessions/` prefix. This deliberately honors the R7 storage-scope invariant.
- **Supporting Evidence:** `_gcs_put_probe` writes to `_diag/` then deletes ([app/api/diagnostics.py:727-736](../../app/api/diagnostics.py#L727)); R7 comment ([app/api/diagnostics.py:585-587](../../app/api/diagnostics.py#L585)).
- **Source Files:** app/api/diagnostics.py
- **API References:** GET /v1/diag/gcs-checks (G3)
- **Database References:** none (GCS object)

### Q: Are the destructive operator actions protected by a confirmation token?
- **Verified Answer:** Not on the server. The only confirmation is a client-side `window.confirm()` prompt in the editor Rescue panel. The backend `reingest`, `abort-session`, and `flush-celery-queue` routes have no server-side confirmation token — and because they require only a JWT, any logged-in user can invoke them. Adding a confirmation-token requirement to destructive routes is documented as a future hardening item.
- **Supporting Evidence:** client confirm ([frontend/src/components/editor/AdminTab.vue:71](../../frontend/src/components/editor/AdminTab.vue#L71)); routes depend on `CurrentUser` only, no token check ([app/api/diagnostics.py:94](../../app/api/diagnostics.py#L94), [app/api/diagnostics.py:355](../../app/api/diagnostics.py#L355)).
- **Source Files:** frontend/src/components/editor/AdminTab.vue; app/api/diagnostics.py
- **API References:** POST /v1/diag/reingest/{id}, /abort-session/{id}, /flush-celery-queue
- **Database References:** sessions, segments, session_audit

## Power User

### Q: Can I force which session Type matrix is applied when I re-initialize SOP stages?
- **Verified Answer:** Yes. `POST /v1/diag/init-session-stages/{id}?type_id=<uuid>` forces a specific Type. Omit `type_id` to use the session's existing `session_type_id`, falling back to the org default Type. It is idempotent — only stages without an existing assignee are written — and returns `{session_id, type_id, stages}` where `stages` is the count written.
- **Supporting Evidence:** optional `type_id` param + idempotency note ([app/api/diagnostics.py:209-242](../../app/api/diagnostics.py#L209)); service default fallback ([app/services/session_init.py:39-41](../../app/services/session_init.py#L39)).
- **Source Files:** app/api/diagnostics.py; app/services/session_init.py
- **API References:** POST /v1/diag/init-session-stages/{id}?type_id=
- **Database References:** sessions, session_stage_assignees, session_types

### Q: My session has discrepancies but no word-alignment rows. How do I backfill them?
- **Verified Answer:** `POST /v1/diag/realign/{id}` re-enqueues `lcs_discrepancies_task` on the `celery` queue. The task is idempotent: it preserves existing discrepancies and only fills in the missing `word_alignment` rows (added in migration 036 after some sessions had already finished). The endpoint returns `{session_id, enqueued, detail}`.
- **Supporting Evidence:** realign enqueues `lcs_discrepancies_task.apply_async(queue="celery")`, idempotency described ([app/api/diagnostics.py:180-199](../../app/api/diagnostics.py#L180)).
- **Source Files:** app/api/diagnostics.py
- **API References:** POST /v1/diag/realign/{id}
- **Database References:** word_alignment (populated by the task)

### Q: How do I backfill poll placements for an older session?
- **Verified Answer:** `POST /v1/diag/autoplace-polls/{id}` calls `auto_place_polls`, which is idempotent — it only places polls where `anchor_segment IS NULL` — so it backfills sessions that completed ingest before the autoplace service was wired, and re-applies defaults after anchors are cleared. Returns `{session_id, placed, detail}`.
- **Supporting Evidence:** endpoint + idempotency note ([app/api/diagnostics.py:251-278](../../app/api/diagnostics.py#L251)); service ([app/services/poll_autoplace.py:84](../../app/services/poll_autoplace.py#L84)).
- **Source Files:** app/api/diagnostics.py; app/services/poll_autoplace.py
- **API References:** POST /v1/diag/autoplace-polls/{id}
- **Database References:** polls (anchor_segment)

### Q: When a single GCS probe fails, does the whole `gcs-checks` call error out?
- **Verified Answer:** No. Each real probe (G1–G6) is wrapped by `_gcs_time_probe`, which catches any exception and returns `ok=False` with `"{ExceptionClass}: {message}"` (truncated to 160 chars) in the note. If the GCS client itself fails to build, G1 is marked failed and G2–G6 are emitted as "(skipped — client unavailable)". The audit insert is also best-effort. So one failure never 500s the suite.
- **Supporting Evidence:** `_gcs_time_probe` try/except ([app/api/diagnostics.py:598-621](../../app/api/diagnostics.py#L598)); client-fail fallback ([app/api/diagnostics.py:648-659](../../app/api/diagnostics.py#L648)).
- **Source Files:** app/api/diagnostics.py
- **API References:** GET /v1/diag/gcs-checks
- **Database References:** audit_events (best-effort)

## Source Verification
- **Files Used:** app/api/diagnostics.py; app/auth.py; app/security/roles.py; app/services/auth_users.py; app/services/session_init.py; app/services/poll_autoplace.py; migrations/004_audit.sql; migrations/010_state_machine.sql; frontend/src/views/GcsView.vue; frontend/src/components/settings/SectionDiagnostics.vue; frontend/src/components/settings/GCSDebug.vue; frontend/src/components/editor/AdminTab.vue; frontend/src/components/settings/SectionAuthUsers.vue; frontend/src/services/api.ts
- **Components Used:** GcsView.vue, SectionDiagnostics.vue, GCSDebug.vue, AdminTab.vue, SectionAuthUsers.vue
- **APIs Used:** GET /v1/diag/gcs, GET /v1/diag/classify-route, GET /v1/diag/gcs-checks, POST /v1/diag/reingest/{id}, /realign/{id}, /init-session-stages/{id}, /autoplace-polls/{id}, /clear-rate-limit-slots, /sop-check, /flush-celery-queue, /revoke-task/{task_id}, /abort-session/{id}, /reseed-auth-users
- **Database Tables Used:** sessions, segments, session_audit, audit_events, auth_users, session_stage_assignees, session_types, word_alignment, polls; Redis sessions:active:{email}, sessions:queue
- **Permission Logic Used:** JWT presence (CurrentUser) on all routes; hardcoded `user.email == "johndean@vin.com"` gate on gcs-checks + reseed-auth-users; client-side isAdmin v-if. roles.py require_admin NOT wired.
- **Confidence Score:** High — every Q/A pairs to a verified file:line; UI-vs-backend discrepancies (abort/revoke, static `/gcs` page) are stated as such.
- **Evidence Links:** [app/api/diagnostics.py:289](../../app/api/diagnostics.py#L289), [app/api/diagnostics.py:463](../../app/api/diagnostics.py#L463), [app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534), [app/api/diagnostics.py:632](../../app/api/diagnostics.py#L632), [app/auth.py:172](../../app/auth.py#L172), [app/security/roles.py:10](../../app/security/roles.py#L10), [frontend/src/components/editor/AdminTab.vue:58](../../frontend/src/components/editor/AdminTab.vue#L58)
