# Rounds — System Architecture

Rounds is transcript software for VIN (Veterinary Information Network). Operators upload recorded sessions; a Celery-driven AI pipeline produces a first-pass transcript with speaker labels and slide alignment; a workflow then finishes it before CMS export. This document describes the runtime architecture **as it exists in this repository** — every claim below is grounded in source.

> Scope note: the originating brief mentioned "CE.VIN" and modules like Organizations / Sites / Vendors / Projects. **None of those exist in this repo** and they are not documented here.

---

## 1. The four tiers

```
+--------------------------------------------------------------------------------------+
|  TIER 1 — Browser (Vue 3 SPA)                                                        |
|                                                                                      |
|   main.ts  ->  createApp(App)                                                        |
|                +-- Pinia (stores: auth, ui, help, featureFlags)                      |
|                +-- vue-router  (hash mode, createWebHashHistory)                     |
|                                                                                      |
|   services/http.ts  --  fetch wrapper: injects "Authorization: Bearer <jwt>",        |
|                         unwraps {success,data,error,meta} envelope, 401 -> /#/login  |
+----------------------------------|---------------------------------------------------+
                                   |  HTTPS  (same origin in prod)
                                   |  /v1/* REST  +  /v1/ws/sessions/{id} WebSocket
                                   v
+--------------------------------------------------------------------------------------+
|  TIER 2 — FastAPI app (app/main.py)                                                  |
|                                                                                      |
|   Middleware (outer -> inner):                                                       |
|     RequestIdMiddleware -> EnvelopeMiddleware -> IdempotencyMiddleware -> CORS        |
|                                                                                      |
|   Routers (app.include_router): auth, gcs_upload, sessions, locks, add_to_session,   |
|     session_resources, corrections, segments, discrepancies, word_alignment,         |
|     sop (+ global_router), audit, improvements, settings, diagnostics, email_debug,  |
|     email_templates, exports (+ captions_router), queue, help                        |
|                                                                                      |
|   lifespan(): seed auth_users from env -> start WS bridge (Redis pub/sub listener)   |
|   Also serves frontend/dist as SPA fallback (path-traversal-guarded)                 |
+------------------|-----------------------------------------|---------------------------+
                   |                                         |
        sync SQLAlchemy engine                       enqueue tasks / pub-sub
                   |                                         |
                   v                                         v
+-----------------------------+      +------------------------------------------------+
|  TIER 3 — Data plane        |      |  TIER 4 — Celery workers (app/tasks/*)         |
|                             |      |                                                |
|   Postgres (sessions,       |<---->|   Worker process: -B embeds Celery Beat        |
|     segments, slides,       | SQL  |   broker + result backend = Redis              |
|     sources, sop_state,     |      |                                                |
|     audit_events,           |      |   ingest -> transcribe -> (anchor) -> finalize |
|     auth_users, ...)        |      |     -> align ; or ai_process (direct)          |
|                             |      |   + slide_extract, frame, classify, captions   |
|   Redis (broker, results,   |<-----|   + sop_tasks, upload_watchdog, help_tasks     |
|     rate-limit slots,       | pub  |                                                |
|     rounds:ws:* pub/sub)    | sub  |   External: GCS, Google STT, Gemini, Vertex AI |
+-----------------------------+      +------------------------------------------------+
```

- **Tier 1 — Vue 3 SPA.** Bootstrapped in [frontend/src/main.ts](../../frontend/src/main.ts): `createApp(App)` plus Pinia and the router. Five CSS files are imported verbatim from the React prototype. Routing is **hash-based** (`createWebHashHistory`) — see [frontend/src/router/index.ts:25](../../frontend/src/router/index.ts#L25).
- **Tier 2 — FastAPI.** [app/main.py](../../app/main.py) constructs the app with a `lifespan` context, a three-layer custom middleware stack, ~21 sub-routers, and (in production) static serving of the built SPA.
- **Tier 3 — Postgres + Redis.** Postgres is reached through a synchronous SQLAlchemy engine (the `DATABASE_URL` is normalized between `postgresql+asyncpg://` for the app and the psycopg2 form for migrations — [app/config.py:137](../../app/config.py#L137)). Redis is the Celery broker/result backend AND the WebSocket pub/sub bus AND the rate-limit slot store ([app/tasks/celery_app.py:27](../../app/tasks/celery_app.py#L27), [app/engines/ws_bridge.py:26](../../app/engines/ws_bridge.py#L26)).
- **Tier 4 — Celery workers + external services.** Worker tasks live under `app/tasks/`. They call out to Google Cloud Storage, Google Speech-to-Text, Gemini, and (optionally) Vertex AI.

The SPA and API share an origin in production: the FastAPI image serves `frontend/dist` ([app/main.py:238](../../app/main.py#L238)), so `API_BASE` is the empty string ([frontend/src/services/http.ts:10](../../frontend/src/services/http.ts#L10)).

---

## 2. Request and auth flow

### 2.1 Login and token issuance

1. The SPA posts an OAuth2 password form to `POST /v1/auth/login` ([app/api/auth.py:15](../../app/api/auth.py#L15)). `form.username` is the email.
2. `authenticate()` verifies the credential against the `auth_users` table (bcrypt), falling back to the plaintext `AUTH_USERS` env CSV when the DB has no row or errors ([app/auth.py:100](../../app/auth.py#L100)).
3. On success, `create_access_token()` issues an **HS256 JWT** signed with `API_SECRET_KEY`, `sub = email`, expiring after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 480 = 8h) ([app/auth.py:153](../../app/auth.py#L153), [app/config.py:43](../../app/config.py#L43)).
4. The frontend stores the token in `localStorage` and persists the email for synchronous route-guard evaluation ([frontend/src/stores/auth.ts:23](../../frontend/src/stores/auth.ts#L23)).

### 2.2 Authenticated requests

- Every request flows through `http()` which attaches `Authorization: Bearer <jwt>` unless `anonymous` is set ([frontend/src/services/http.ts:40](../../frontend/src/services/http.ts#L40)).
- On the server, protected endpoints depend on `CurrentUser` = `Depends(get_current_user)`, which decodes the JWT and confirms the subject is still an active user (DB lookup, env-CSV fallback) ([app/auth.py:172](../../app/auth.py#L172), [app/auth.py:208](../../app/auth.py#L208)).
- A `401` from any non-anonymous call clears the token and redirects to `#/login` ([frontend/src/services/http.ts:71](../../frontend/src/services/http.ts#L71)).

### 2.3 Authorization reality (what actually gates access today)

Authorization in this repo is **JWT presence plus a hardcoded admin-email gate** — there is no active role tier.

- The role helper module [app/security/roles.py](../../app/security/roles.py) defines `is_admin()` / `require_admin()`. Its own docstring states it is **"Phase 8 scaffold only — not yet wired into any endpoint"** for the *role* path, and that `auth_users.role` (migration 045) "is never consulted by `get_current_user`" ([app/security/roles.py:10](../../app/security/roles.py#L10)).
- `get_current_user` does **not** read `role` — confirmed: no `role` reference exists in [app/auth.py](../../app/auth.py). The `User` object carries only `email` ([app/auth.py:36](../../app/auth.py#L36)).
- `require_admin()` and `is_admin()` **are** imported and called in several routers (settings, email_templates, email_debug, help, sessions, locks). However, **no caller ever passes the `role=` argument**, so every call resolves to the fallback branch: `user.email == LEGACY_ADMIN_EMAIL` where `LEGACY_ADMIN_EMAIL = "johndean@vin.com"` ([app/security/roles.py:54](../../app/security/roles.py#L54), [app/security/roles.py:88](../../app/security/roles.py#L88)). The effective admin check is therefore the single hardcoded email — **PARTIALLY IMPLEMENTED** as a role system.
- Two diagnostics endpoints inline the literal email comparison directly rather than going through the helper ([app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534), [app/api/diagnostics.py:632](../../app/api/diagnostics.py#L632)).
- A second, *wider* allowlist exists for session-trash operations: `SESSION_TRASH_ALLOWED = {ADMIN_EMAIL, "carlab@vin.com"}` ([app/api/sessions.py:52](../../app/api/sessions.py#L52)). Restore and permanent-delete still require strict `require_admin` ([app/api/sessions.py:674](../../app/api/sessions.py#L674), [app/api/sessions.py:707](../../app/api/sessions.py#L707)).
- On the client, exactly one route guard enforces admin: `adminOnly` on `/admin/help`, comparing `auth.email` against a mirrored `LEGACY_ADMIN_EMAIL` constant ([frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63)). This is explicitly UI-only; the comment notes the server is authoritative.

### 2.4 Response envelope and middleware

Three custom middleware wrap every request, added outermost-first ([app/main.py:115](../../app/main.py#L115)):

1. `RequestIdMiddleware` (outermost) — stamps `x-request-id`.
2. `EnvelopeMiddleware` — wraps every JSON response as `{success, data, error, meta}`; it catches `MICException` inside `dispatch()`.
3. `IdempotencyMiddleware` — replays cached responses keyed on an `Idempotency-Key` header (TTL `IDEMPOTENCY_KEY_TTL_SECONDS`, default 86400 — [app/config.py:77](../../app/config.py#L77)).
4. `CORSMiddleware` (innermost) — allows `https://rounds.vin` and the two localhost dev origins ([app/main.py:116](../../app/main.py#L116)).

The frontend `http()` wrapper auto-unwraps the envelope, returning the raw `data` to callers ([frontend/src/services/http.ts:89](../../frontend/src/services/http.ts#L89)).

---

## 3. Celery processing DAG (high level)

A session is driven from upload to `ready` by Celery tasks. The orchestrator is `ingest_task` ([app/tasks/ingest.py:38](../../app/tasks/ingest.py#L38)), enqueued by `enqueue_ingest()` from `POST /v1/gcs/upload-complete` ([app/tasks/ingest.py:204](../../app/tasks/ingest.py#L204)).

`ingest_task` guards execution before doing work:
- Skips if the session is missing or its status is not `uploading` ([app/tasks/ingest.py:58](../../app/tasks/ingest.py#L58)).
- Refuses to re-run if `segments` already exist for the session (anti cross-pipeline overwrite); directs the operator to `/v1/diag/reingest/<id>` ([app/tasks/ingest.py:96](../../app/tasks/ingest.py#L96)).
- Reads `session_templates.ai_pipeline` to choose a branch ([app/tasks/ingest.py:88](../../app/tasks/ingest.py#L88)).

Two pipeline branches:

```
                         POST /v1/gcs/upload-complete
                                     |
                                enqueue_ingest
                                     |
                                ingest_task
                                     |
         ai_pipeline == 'direct'  ---+---  ai_pipeline == 'enhanced' (default branch in code)
                 |                                          |
       (if slide sources>0)                     transition -> 'transcribing'
        slide_extract_task                                  |
                 |                              +-----------+-----------+--------------------+
         ai_process_task                        |           |           |                    |
   (Gemini multimodal: parses               frame_task  slide_extract  chain([transcribe_task, finalize_task])
    transcript + ++N*+ slide                (parallel)  (parallel,        |
    markers + **Name:** speakers;                       if slides>0)   transcribe_task
    writes segments/slides/                                              |  triggers anchor_task internally
    alignments; marks 'ready')                                          |  + template_autodetect_task
                                                                         v
                                                                  finalize_task
                                                                   (runs align_task,
                                                                    marks 'ready')
```

Key facts from code:

- **Enhanced (STT) branch.** `frame_task` and (conditionally) `slide_extract_task` are fired in parallel via `apply_async`. The main chain is `chain(transcribe_task.s, finalize_task.s)` ([app/tasks/ingest.py:181](../../app/tasks/ingest.py#L181)). `transcribe_task` internally triggers `anchor_task` and `template_autodetect_task` on completion ([app/tasks/transcribe.py:201](../../app/tasks/transcribe.py#L201), [app/tasks/transcribe.py:212](../../app/tasks/transcribe.py#L212)). The inline comment notes `normalize`/`fusion`/`align` steps hang off this chain when present; `finalize_task` is chained explicitly so it always runs ([app/tasks/ingest.py:173](../../app/tasks/ingest.py#L173)).
- **Direct (AI MODE) branch.** `ai_process_task` sends media straight to Gemini multimodal, parses the formatted transcript, and writes segments/slides/alignments/speakers atomically before marking `ready` ([app/tasks/ai_process.py:1](../../app/tasks/ai_process.py#L1)). It includes a hallucination-loop detector (BR-015) that truncates Gemini repeat-spew ([app/tasks/ai_process.py:37](../../app/tasks/ai_process.py#L37)).
- **Task base class.** Every task subclasses `RoundsTask` ([app/tasks/celery_app.py:104](../../app/tasks/celery_app.py#L104)). It provides categorized failure handling (`on_failure` maps exceptions to stable categories: `gemini_overloaded`, `gemini_quota`, `gemini_config`, `storage_error`, `stt_error`, `validation_error`, `unknown` — [app/tasks/celery_app.py:92](../../app/tasks/celery_app.py#L92)), transitions the session to `failed`, releases the rate-limit slot, and emits a `session_failed` WS event ([app/tasks/celery_app.py:147](../../app/tasks/celery_app.py#L147)). Retries use exponential backoff 60/120/240s with optional jitter ([app/tasks/celery_app.py:194](../../app/tasks/celery_app.py#L194)).
- **Celery config.** `task_acks_late=True`, `task_reject_on_worker_lost=True`, `worker_prefetch_multiplier=1`, JSON serialization, single default queue `celery` ([app/tasks/celery_app.py:51](../../app/tasks/celery_app.py#L51)). Retry/backoff/jitter values come from `CELERY_MAX_RETRIES=3`, `CELERY_RETRY_BACKOFF_BASE=60`, `CELERY_RETRY_JITTER=True` ([app/config.py:74](../../app/config.py#L74)).
- **Locked scoring weights.** Fusion/alignment/IIL weights (`FUSION_*`, `ALIGN_*`, `IIL_*`) are pinned constants under the "LOCKED weights" block ([app/config.py:51](../../app/config.py#L51)); CLAUDE.md notes these are pinned by `tests/test_health.py`.

### 3.1 Celery Beat (scheduled tasks)

Beat is embedded in the worker process via `-B` (single replica, no leader election). Two scheduled entries ([app/tasks/celery_app.py:71](../../app/tasks/celery_app.py#L71)):

- `upload-watchdog` — runs every `UPLOAD_WATCHDOG_INTERVAL_SEC` (60s), but the task body is feature-flagged **off** by default (`UPLOAD_WATCHDOG_ENABLED=False`).
- `sop-check-deadlines` — hourly scan of `sop_state` for overdue stages, writing `audit_events` and emitting a `sop.deadline_warning` WS event.

---

## 4. WebSocket bridge

Live session updates use a **Redis pub/sub fan-out** between Celery workers and connected browsers ([app/engines/ws_bridge.py](../../app/engines/ws_bridge.py)).

```
Celery task                Redis                       FastAPI                Browser
-----------                -----                       -------                -------
publish_ws_event_sync  -> PUBLISH rounds:ws:{id}  ->  start_ws_bridge       ws.send_json(payload)
  {session_id, payload}    (channel per session)      (PSUBSCRIBE rounds:ws:*)  -->  /v1/ws/sessions/{id}
                                                       WSManager.broadcast
```

- **Publish side (sync).** Tasks call `publish_ws_event_sync(session_id, payload)`, which `PUBLISH`es JSON `{"session_id", "payload"}` onto `rounds:ws:{session_id}` ([app/engines/ws_bridge.py:30](../../app/engines/ws_bridge.py#L30)).
- **Bridge.** `start_ws_bridge()` runs as a background asyncio task started in the FastAPI `lifespan` ([app/main.py:96](../../app/main.py#L96)). It `PSUBSCRIBE`s to `rounds:ws:*`, unwraps each message, and calls `ws_manager.broadcast()` ([app/engines/ws_bridge.py:55](../../app/engines/ws_bridge.py#L55)).
- **WSManager.** An in-memory per-session set of connections, lock-guarded, with `connect` / `disconnect` / `broadcast` ([app/engines/ws_bridge.py:89](../../app/engines/ws_bridge.py#L89)). Broadcasting only the inner `payload` means the browser receives `{type, ...}` without the session_id wrapper.
- **Endpoint.** `@app.websocket("/v1/ws/sessions/{session_id}")` accepts the socket, registers it with the manager, and treats client messages as keep-alive pings ([app/main.py:192](../../app/main.py#L192)). If the bridge/manager isn't up yet, the socket closes with code `1011`.
- **Ordering invariant.** The bridge is started **after** the `auth_users` seed in `lifespan`; the module docstring notes tasks that publish before the bridge is up "will simply have no listeners" ([app/main.py:13](../../app/main.py#L13)).

Event types seen in code include `processing_update`, `metrics_update`, `session_failed`, and `sop.deadline_warning` ([app/main.py:194](../../app/main.py#L194), [app/tasks/celery_app.py:179](../../app/tasks/celery_app.py#L179)).

---

## 5. Feature-flag plumbing (`/v1/version`)

Backend kill-switches are the single source of truth and are surfaced to the SPA through the **unauthenticated** `GET /v1/version` endpoint ([app/main.py:159](../../app/main.py#L159)). It returns `commit`, `env`, `help_ask_ai_enabled`, and `split_merge_enabled`.

`AppHeader.vue` fetches `/v1/version` on mount and pipes the flags into stores ([frontend/src/components/AppHeader.vue:44](../../frontend/src/components/AppHeader.vue#L44)):
- `help_ask_ai_enabled` -> `help.setAskEnabled()` (gates the Ask AI composer).
- `split_merge_enabled` -> `featureFlags.setSplitMergeEnabled()` ([frontend/src/stores/featureFlags.ts:20](../../frontend/src/stores/featureFlags.ts#L20)), which gates the split/merge UI in `SegmentText.vue` ([frontend/src/components/editor/SegmentText.vue:95](../../frontend/src/components/editor/SegmentText.vue#L95)).

The build-time `VITE_HELP_ASK_AI_ENABLED` flag is **not** consulted by the frontend — confirmed in the `/v1/version` docstring ([app/main.py:178](../../app/main.py#L178)) and the config comment ([app/config.py:113](../../app/config.py#L113)).

### Pinia stores

| Store | File | Role |
|---|---|---|
| `auth` | [frontend/src/stores/auth.ts](../../frontend/src/stores/auth.ts) | current email, JWT-backed `isAuthenticated`, login/logout/bootstrap |
| `ui` | [frontend/src/stores/ui.ts](../../frontend/src/stores/ui.ts) | theme/brand/density, editor toggles, classify backend selection (localStorage-persisted) |
| `help` | [frontend/src/stores/help.ts](../../frontend/src/stores/help.ts) | Help Center state incl. Ask-AI-enabled flag |
| `featureFlags` | [frontend/src/stores/featureFlags.ts](../../frontend/src/stores/featureFlags.ts) | backend-SSOT `splitMergeEnabled` |

---

## 6. Deployment topology (Railway)

The following is sourced from CLAUDE.md (project infra facts), corroborated by code where noted.

- **Project:** Rounds Railway project `5741583d-47dd-4697-9732-d7744e82f215`.
- **Services:**
  - `api` (`e1b3da55-8789-4326-9362-b5a8e7c409cc`) — the FastAPI app. The Dockerfile builds `frontend/dist` and the app serves it as an SPA fallback ([app/main.py:236](../../app/main.py#L236)).
  - `worker` (`22ecca2b-5b8f-4757-ba94-ec1f2cd90e39`) — Celery worker with embedded Beat (`-B` via `scripts/start.sh`, per [app/tasks/celery_app.py:67](../../app/tasks/celery_app.py#L67)). Single replica.
  - `Postgres` (`3eab9a85-562f-4c8a-86a6-fb4ccb027578`).
  - `Redis` (`639d68f5-35d4-4479-b0d1-1b16c95e3108`).
- **Database + Redis are isolated** to Rounds (own plugins). Per CLAUDE.md, **GCP / GCS / Gemini / SMTP are currently shared with MIC's data plane** — uploads land in `video-pipeline-uploads-mic`, Gemini bills MIC's quota, SMTP sends as `mic@design.veterinary.support`.
- **Two-remote git** per CLAUDE.md: `origin=vin-swe/rounds` (dev) and `production=johndean/rounds` (Railway auto-deploy).
- **Live URLs:** `https://rounds.vin` and `https://api-production-c198.up.railway.app`.
- **Build identity:** `/v1/version` returns the git SHA baked in as `ROUNDS_COMMIT_SHA` (defaults to `dev` outside Railway) ([app/main.py:172](../../app/main.py#L172)).

> The Railway service IDs, remotes, MIC-shared-infra posture, and live URLs are documented in CLAUDE.md, not directly verifiable from application source in this audit. Treat them as **NOT VERIFIED IN CODE** beyond what the cited source lines confirm.

---

## 7. Release readiness — PARTIALLY IMPLEMENTED systems

The following are present in code but intentionally inactive or scaffold-only. None should be presented as live behavior.

| System | State | Evidence |
|---|---|---|
| **Role-based authorization** | Scaffold. `app/security/roles.py` exists and `require_admin`/`is_admin` are called, but `role=` is never passed and `get_current_user` never reads `auth_users.role`. Effective auth = JWT + hardcoded `johndean@vin.com` gate. | [app/security/roles.py:10](../../app/security/roles.py#L10), [app/auth.py:172](../../app/auth.py#L172) |
| **Upload watchdog** | Default OFF. Beat schedule registered, task body gated by `UPLOAD_WATCHDOG_ENABLED=False`. | [app/config.py:100](../../app/config.py#L100), [app/tasks/celery_app.py:71](../../app/tasks/celery_app.py#L71) |
| **Segment split / merge** | Default OFF. `SPLIT_MERGE_ENABLED=False`; with the flag off the executor returns `503 SPLIT_MERGE_DISABLED` and the UI hides the controls. | [app/config.py:134](../../app/config.py#L134), [frontend/src/stores/featureFlags.ts:20](../../frontend/src/stores/featureFlags.ts#L20) |
| **Help Center Ask AI** | Default OFF. `HELP_ASK_AI_ENABLED=False`; the Ask tab/composer appears only when the backend flag is true (read via `/v1/version`). | [app/config.py:121](../../app/config.py#L121), [frontend/src/components/AppHeader.vue:58](../../frontend/src/components/AppHeader.vue#L58) |
| **Vertex AI discrepancy classification** | Default OFF. `VERTEX_AI_CLASSIFY_ENABLED=False`; `classify_discrepancies_task` reads `org_settings.classify_backend` and only uses Vertex when that value is `"vertex"`. | [app/config.py:86](../../app/config.py#L86), [app/tasks/classify_task.py:109](../../app/tasks/classify_task.py#L109) |
| **SOP deadline emails** | Default OFF. `SOP_DEADLINE_EMAIL_ENABLED=False`; the hourly deadline task still writes audit rows + WS events, but does not send SMTP unless enabled. | [app/config.py:110](../../app/config.py#L110) |

Additional note: the `app/main.py` module docstring still describes a "Phase 1 scaffold" with only `/v1/health` wired, which is stale — the file actually wires ~21 routers. The route count is corroborated against CLAUDE.md's "32 routes live" claim but the exact total was not re-tallied per-router in this audit (**PARTIALLY VERIFIED**).

---

## Source Verification
- **Files Used:** app/main.py, app/config.py, app/auth.py, app/api/auth.py, app/api/sessions.py, app/api/diagnostics.py (line refs), app/security/roles.py, app/tasks/celery_app.py, app/tasks/ingest.py, app/tasks/transcribe.py (grep), app/tasks/ai_process.py, app/tasks/classify_task.py (grep), app/engines/ws_bridge.py, frontend/src/main.ts, frontend/src/router/index.ts, frontend/src/services/http.ts, frontend/src/stores/auth.ts, frontend/src/stores/ui.ts, frontend/src/stores/featureFlags.ts, frontend/src/components/AppHeader.vue (grep), CLAUDE.md
- **Components Used:** AppHeader.vue, SegmentText.vue (gating refs only), Pinia stores (auth, ui, help, featureFlags)
- **APIs Used:** POST /v1/auth/login, GET /v1/auth/me, GET /v1/health, GET /v1/version, WS /v1/ws/sessions/{id}, POST /v1/gcs/upload-complete (referenced), POST /v1/diag/reingest/{id} (referenced)
- **Database Tables Used:** auth_users, sessions, segments, sources, session_templates, org_settings, sop_state, audit_events, session_locks (referenced via code paths)
- **Permission Logic Used:** JWT presence (get_current_user) + hardcoded LEGACY_ADMIN_EMAIL gate (johndean@vin.com) via is_admin/require_admin (role param never passed) + client-side adminOnly route guard. auth_users.role NOT read.
- **Confidence Score:** High — every tier, the auth flow, the Celery DAG branches, the WS bridge, the feature flags, and the release-readiness items were read directly from source; Railway topology is High-confidence-from-CLAUDE.md but not independently verifiable from application code.
- **Evidence Links:** [app/main.py:115](../../app/main.py#L115), [app/main.py:192](../../app/main.py#L192), [app/auth.py:172](../../app/auth.py#L172), [app/security/roles.py:54](../../app/security/roles.py#L54), [app/tasks/celery_app.py:71](../../app/tasks/celery_app.py#L71), [app/tasks/ingest.py:141](../../app/tasks/ingest.py#L141), [app/engines/ws_bridge.py:30](../../app/engines/ws_bridge.py#L30), [app/config.py:100](../../app/config.py#L100), [frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63)
