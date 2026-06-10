# rounds.vin — Architecture Overview

> Code-verified knowledge asset for a demo AI. Every claim is traceable to source.
> Unproven claims are tagged `NOT VERIFIED IN CODE`, `IMPLEMENTATION NOT FOUND`,
> or `PARTIALLY IMPLEMENTED`. Links are relative to `ai-demo-knowledge/`.

## High-level shape

```
Browser (Vue 3 SPA, hash-routed)
    │  HTTPS, JWT bearer
    ▼
FastAPI app  ──────────────  /v1/* routes (~24 routers)
    │  async SQLAlchemy            WebSocket /v1/ws/sessions/{id}
    ▼
Postgres  ◄──┐         Redis  (Celery broker/backend + pub/sub + rate-limit sets)
             │            ▲
             │            │
        Celery worker (single queue, Beat embedded)
             │
   Google Cloud Storage · Google Speech-to-Text · Google Gemini · FFmpeg/OpenCV/PyMuPDF
```

The same FastAPI process also serves the built Vue SPA as static files in
production (Dockerfile copies `frontend/dist` in; FastAPI mounts `/assets` and an
SPA fallback with a path-traversal guard)
([app/main.py:236-263](../app/main.py#L236)).

## Backend stack

- **FastAPI 0.115** application object created in
  [app/main.py:109-113](../app/main.py#L109). Title "Rounds API", version
  "0.0.1".
- **Async SQLAlchemy + asyncpg** for request-path DB access; the `DATABASE_URL`
  is coerced to the `postgresql+asyncpg://` scheme by a config validator
  ([app/config.py:137-149](../app/config.py#L137)). Celery tasks instead open
  their own **synchronous** engine per invocation
  (`DATABASE_URL.replace("+asyncpg", "")`) and dispose it in a `finally`
  ([docs/technical/processing-pipeline-technical-spec.md:43-45](../docs/technical/processing-pipeline-technical-spec.md#L43)).
- **Celery** workers for all heavy processing, on a single queue, one worker
  replica, with Celery Beat embedded via `-B`
  ([docs/technical/processing-pipeline-technical-spec.md:41-42](../docs/technical/processing-pipeline-technical-spec.md#L41)).
- **Pydantic Settings** central config in [app/config.py](../app/config.py),
  including locked processing weights (see "Locked weights" below).

### Middleware stack (order matters)

Added outermost-first: RequestId → Envelope → Idempotency → CORS
([app/main.py:115-150](../app/main.py#L115)).
- **RequestIdMiddleware** stamps `x-request-id` on every response (outermost).
- **EnvelopeMiddleware** wraps every JSON response as
  `{success, data, error, meta}` and catches `MICException` directly
  ([app/main.py:133-143](../app/main.py#L133)).
- **IdempotencyMiddleware** replays cached responses keyed on an
  `Idempotency-Key` header (TTL `IDEMPOTENCY_KEY_TTL_SECONDS`, default 86400s)
  ([app/main.py:127-131](../app/main.py#L127), [app/config.py:77](../app/config.py#L77)).
- **CORS** allows `https://rounds.vin` + localhost dev origins
  ([app/main.py:115-125](../app/main.py#L115)).

### Routers

The app includes routers for: auth, gcs_upload, sessions, locks,
add_to_session, session_resources, corrections, segments, discrepancies,
word_alignment, sop (+ global sop), audit, improvements, settings, diagnostics,
email_debug, email_templates, exports (+ captions), queue, help
([app/main.py:212-233](../app/main.py#L212)). Most are prefixed `/v1/...`.

## Frontend stack

- **Vue 3 SPA** with **vue-router in hash mode** (`createWebHashHistory`)
  ([frontend/src/router/index.ts:22-25](../frontend/src/router/index.ts#L22)).
- A global `beforeEach` guard: public routes pass; otherwise an unauthenticated
  user is redirected to `#/login?next=…`; `meta.adminOnly` routes additionally
  require `auth.email === 'johndean@vin.com'`
  ([frontend/src/router/index.ts:53-68](../frontend/src/router/index.ts#L53)).
- API access is via a typed client (`frontend/src/services/api.ts`) that injects
  the JWT; WebSocket-backed live state via composables such as
  `useSyncController` / `useWsSubscriber`
  ([docs/technical/processing-pipeline-technical-spec.md:50-67](../docs/technical/processing-pipeline-technical-spec.md#L50)).

## Authentication & token model

- `POST /v1/auth/login` takes username (treated as email) + password and returns
  a bearer token ([app/api/auth.py:15-28](../app/api/auth.py#L15)).
- Tokens are **HS256 JWTs** signed with `API_SECRET_KEY`, expiring after
  `ACCESS_TOKEN_EXPIRE_MINUTES` (default 480 = 8h)
  ([app/auth.py:153-158](../app/auth.py#L153),
  [app/config.py:42-43](../app/config.py#L42)).
- `authenticate()` verifies against the bcrypt-hashed `auth_users` table, with a
  constant-time env-CSV fallback when the DB path returns nothing or errors
  ([app/auth.py:100-143](../app/auth.py#L100)).
- `get_current_user()` decodes the JWT and confirms the user is still active (DB
  first, env-CSV fallback). It does **not** load any role
  ([app/auth.py:172-205](../app/auth.py#L172)).

## The AI processing pipeline (Celery DAG)

Triggered by `enqueue_ingest(session_id)` from upload-complete. The orchestrator
`ingest_task` routes by `ai_pipeline`:

- **`direct`**: `slide_extract` (parallel) + `ai_process` (Gemini multimodal →
  `ready`), followed by background word-level STT + discrepancies.
- **`standard` / `enhanced`**: `frame_task` (parallel) + `slide_extract`
  (parallel) + `chain(transcribe → finalize)`, where transcribe fans out to
  `anchor → normalize → fusion → align → finalize`
  ([docs/technical/processing-pipeline-technical-spec.md:11-31](../docs/technical/processing-pipeline-technical-spec.md#L11)).

Key engines (deterministic logic separated from Celery wiring):
- **Segmenter** — 4-rule word→segment grouping
  ([app/engines/segmenter.py](../app/engines/segmenter.py)).
- **Anchor** — phrase + visual + semantic anchor detection
  ([app/engines/anchor.py](../app/engines/anchor.py)).
- **Fusion** — weighted boundary fusion → slide time ranges
  ([app/engines/fusion.py](../app/engines/fusion.py)).
- **Alignment** — 4-signal per-segment slide scoring
  ([app/engines/alignment.py](../app/engines/alignment.py)).
- **State machine** — the only path to change `sessions.status`
  ([app/engines/state_machine.py](../app/engines/state_machine.py)).
- **LLM client** — Gemini calls + error categorization
  ([app/engines/llm_client.py](../app/engines/llm_client.py)).

Inter-task signals (frame/anchor outputs) are handed off via Redis keys with a
24h TTL; `frame_task` writes to Redis and `anchor_task` reads it, degrading
gracefully to empty signals if absent
([docs/technical/processing-pipeline-technical-spec.md:219-227](../docs/technical/processing-pipeline-technical-spec.md#L219)).

## Locked processing weights

A block of scoring constants is pinned by a test
(`tests/test_health.py::test_locked_weights_match_audit`) and must not be tuned
without explicit authorization ([app/config.py:51-77](../app/config.py#L51)):

- Fusion: visual 0.5 / anchor 0.3 / semantic 0.2; boundary threshold 0.35.
- Alignment: semantic 0.35 / coverage 0.25 / temporal 0.25 / sequential 0.15;
  backward-jump penalty 0.8.
- IIL: drift confidence penalty 0.3, realign window 20s, tier-2 default 0.7 /
  moderate 0.85.
- Frame sampling FPS 2; visual-change threshold 8.0; cross-validate window 5.0s.

## Real-time updates

A WebSocket endpoint `/v1/ws/sessions/{session_id}` streams processing/metrics/
failure events; a Redis pub/sub bridge (`WSManager` + `start_ws_bridge`) is
started in the FastAPI lifespan after the auth-users seed
([app/main.py:93-97](../app/main.py#L93),
[app/main.py:192-208](../app/main.py#L192)). Pipeline tasks publish events such
as `processing_update`, `metrics_update`, `session_failed`, `slide_progress`,
`stt_ready`, `timeline_ready`
([docs/technical/processing-pipeline-technical-spec.md:191-209](../docs/technical/processing-pipeline-technical-spec.md#L191)).

## Storage scope invariant (R7)

`/v1/gcs/upload-complete` rejects any `gcs_uri` that is not under
`gs://<bucket>/sessions/<id>/`, via `find_out_of_scope_uri`
([app/services/gcs.py](../app/services/gcs.py),
[docs/technical/processing-pipeline-technical-spec.md:231-232](../docs/technical/processing-pipeline-technical-spec.md#L231)).

## Rate limiting

`check_user_quota` rejects when a user already has `MAX_CONCURRENT_SESSIONS` (3)
in flight or the global queue exceeds `MAX_QUEUE_LENGTH` (10). Slots are reserved
on upload-complete and released on success/failure
([app/config.py:46-47](../app/config.py#L46),
[docs/technical/processing-pipeline-technical-spec.md:256-262](../docs/technical/processing-pipeline-technical-spec.md#L256)).

## Infrastructure / deployment

- Hosted on **Railway**: api + worker services, isolated Postgres + Redis
  plugins; production at `https://rounds.vin` (and an api Railway domain). The
  data plane (GCS bucket, Gemini quota, SMTP) is currently shared with the
  predecessor "MIC" project (CLAUDE.md, repo guidance).
- Two git remotes: `origin` (dev) and `production` (Railway auto-deploy).
- `GET /v1/health` (GET/HEAD) and `GET /v1/version` are unauthenticated probes;
  `/v1/version` exposes commit SHA + feature flags `help_ask_ai_enabled`,
  `split_merge_enabled` ([app/main.py:153-189](../app/main.py#L153)).

## Authorization (architecture note)

There is no role middleware. Authorization is: (1) JWT presence enforced per
endpoint via `CurrentUser`; (2) a single hardcoded `LEGACY_ADMIN_EMAIL`
(`johndean@vin.com`) gate applied through `require_admin(user)` on
admin/settings/help/email-template routes — always falling back to the email
check because no caller passes `role=`
([app/security/roles.py:88-117](../app/security/roles.py#L88)); (3) one
client-side `adminOnly` guard in the router
([frontend/src/router/index.ts:63](../frontend/src/router/index.ts#L63)).
`auth_users.role` is present but unused by `get_current_user`. Do not describe
this as a role tier system.

## Source Verification
- **Files Used:** app/main.py, app/config.py, app/auth.py, app/api/auth.py, app/engines/state_machine.py, app/engines/fusion.py, app/engines/alignment.py, app/engines/anchor.py, app/engines/segmenter.py, app/security/roles.py, frontend/src/router/index.ts, docs/technical/processing-pipeline-technical-spec.md
- **Components Used:** Vue 3 SPA router, useSyncController / useWsSubscriber (referenced)
- **APIs Used:** POST /v1/auth/login, GET /v1/health, GET /v1/version, WS /v1/ws/sessions/{id}, POST /v1/gcs/upload-complete
- **Database Tables Used:** auth_users, sessions (architecture-level references; full table set in module-catalog.md)
- **Permission Logic Used:** JWT presence + LEGACY_ADMIN_EMAIL hardcoded gate; one client-side adminOnly guard
- **Confidence Score:** High — middleware order, router list, token model, and pipeline DAG all traced to source.
- **Evidence Links:** [app/main.py:115-263](../app/main.py#L115), [app/config.py:51-77](../app/config.py#L51), [app/auth.py:100-205](../app/auth.py#L100), [docs/technical/processing-pipeline-technical-spec.md:11-31](../docs/technical/processing-pipeline-technical-spec.md#L11)
