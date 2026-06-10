# External Integrations — rounds.vin

> Only the integrations that exist in this repo today, verified against
> [app/config.py](../app/config.py), [app/engines/llm_client.py](../app/engines/llm_client.py),
> [app/services/gcs.py](../app/services/gcs.py), [app/services/email.py](../app/services/email.py),
> and [app/api/email_debug.py](../app/api/email_debug.py). No payment, calendar, SSO,
> analytics, or CRM integrations exist — none are documented here.

| Integration | Purpose | Status | Config source |
|---|---|---|---|
| Google Cloud Storage (GCS) | Media + slide + artifact object storage | Active | `GCS_BUCKET`, `GCP_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS` |
| Google Cloud STT (chunked) | Default transcription backend (`enhanced` path) | Active (default) | `TRANSCRIPTION_BACKEND`, `TRANSCRIPTION_CHUNK_MINUTES` |
| Gemini (Google GenAI dev API) | Multimodal STT (AI MODE direct), text classify, Help bulk-AI | Active (key-gated) | `GEMINI_API_KEY`, `GEMINI_CLASSIFY_MODEL` |
| Vertex AI Gemini | Alternate text-classify backend | **OFF by default** | `VERTEX_AI_CLASSIFY_ENABLED` (default `False`), `VERTEX_AI_LOCATION` |
| SMTP email | SOP deadline emails + email diagnostics | Active (flag-gated send) | `SMTP_HOST/PORT/USERNAME/PASSWORD/FROM` (env, not Settings) |
| Railway | Hosting / deploy / Postgres + Redis plumbing | Active (infra) | `DATABASE_URL`, `REDIS_URL` |

> **Shared data plane (per CLAUDE.md):** `GCP_PROJECT_ID`, `GCS_BUCKET`, `GEMINI_API_KEY`,
> `SMTP_*`, `AUTH_USERS` were copied verbatim from MIC's Railway env. Uploads land in
> MIC's bucket, Gemini bills MIC's quota, SMTP sends as MIC's address. Postgres + Redis
> are isolated to Rounds. (This is an operational fact from CLAUDE.md, not re-verified
> against live infra here.)

---

## 1. Google Cloud Storage (GCS)

[app/services/gcs.py](../app/services/gcs.py). Lazy-imports `google.cloud.storage` so
non-GCS unit tests don't pay the SDK/credential cost ([app/services/gcs.py:79](../app/services/gcs.py#L79)).

- **Client:** `storage.Client(project=settings.GCP_PROJECT_ID)`, bucket `settings.GCS_BUCKET`.
- **Fixed bucket layout** (audit §2.4):
  ```
  gs://<bucket>/sessions/<id>/<filename>          role=video (session root)
  gs://<bucket>/sessions/<id>/slides/<filename>   role=slide
  gs://<bucket>/sessions/<id>/manifest/<filename> role=manifest
  gs://<bucket>/sessions/<id>/uploads/<filename>  role=audio / audio_enhance / other
  gs://<bucket>/sessions/<id>/chat/<filename>     role=chat
  ```
  Role→subdir map: `_ROLE_PREFIXES` ([app/services/gcs.py:24](../app/services/gcs.py#L24)). Unknown roles fall back to `uploads/`.
- **Signed PUT URLs:** `make_signed_put_url` issues a **v4** signed PUT URL, default TTL 60 min (BR-013, [app/services/gcs.py:73](../app/services/gcs.py#L73)).
- **R7 scope invariant:** `find_out_of_scope_uri` returns the first `gcs_uri` outside `gs://<bucket>/sessions/<id>/`; `/upload-complete` rejects any out-of-scope URI ([app/services/gcs.py:57](../app/services/gcs.py#L57)). Test: `tests/test_gcs_scope.py`.
- Also used downstream for slide-thumbnail PNG uploads and the caption burn-in MP4 (`gs://<bucket>/sessions/<id>/captioned/<uuid>.mp4`, 24h v4 signed download URL) — see [workflows.md](./workflows.md) §10.

## 2. Google Cloud Speech-to-Text (chunked)

`TRANSCRIPTION_BACKEND = "google_stt_chunked"`, `TRANSCRIPTION_CHUNK_MINUTES = 5`
([app/config.py:80](../app/config.py#L80)). This is the default STT backend for the
`enhanced` pipeline path (transcribe → … → finalize) and the background-STT companion
for AI MODE direct. The chunked-STT call implementation lives in `app/tasks/transcribe.py`
(not opened for this doc — NOT VERIFIED IN CODE beyond the config + the ingest-workflow
references); the config knobs above are the verified surface.

## 3. Gemini (Google GenAI developer API)

[app/engines/llm_client.py](../app/engines/llm_client.py). Reached via `from google import genai`;
`genai.Client(api_key=settings.GEMINI_API_KEY)`. **All Gemini paths raise
`LLMError(category="gemini_config")` when `GEMINI_API_KEY` is unset** ([app/engines/llm_client.py:118](../app/engines/llm_client.py#L118)).

Three call surfaces:

- **`call_gemini_multimodal`** ([:107](../app/engines/llm_client.py#L107)) — uploads local files to the Gemini File API, polls until `ACTIVE`, runs a pre-flight `count_tokens` probe against `MODEL_CONTEXT_LIMITS` (flash-lite/flash = 1,048,576; 2.5-pro = 2,097,152) and aborts with `gemini_context_overflow` before the expensive `generate_content` round-trip. Default model `gemini-2.5-pro` (only model whose 2M context fits a typical 30–60 min video + 100-slide deck). Temperature 0.1, `max_output_tokens=65536`. Used by AI MODE direct ingest.
- **`call_gemini_text`** ([:217](../app/engines/llm_client.py#L217)) — text-only, `response_mime_type="application/json"`, default `gemini-2.5-pro`, treats a non-`STOP` finish_reason as `gemini_overloaded`. Used by Help bulk-AI tasks and discrepancy classify.
- **`classify_discrepancies`** ([:422](../app/engines/llm_client.py#L422)) — dispatcher batching word-level diffs (`DISCREPANCY_BATCH_SIZE = 15`) with a per-batch missing-id retry; routes to Gemini or Vertex via `use_vertex`. Default classify model `settings.GEMINI_CLASSIFY_MODEL = "gemini-2.5-flash-lite"`.

**Error taxonomy** (`_categorize_gemini_error`, [:73](../app/engines/llm_client.py#L73)): `gemini_model_deprecated`, `gemini_context_overflow`, `gemini_overloaded`, `gemini_quota`, `gemini_config`, `gemini_error`. `TERMINAL_LLM_CATEGORIES` (context_overflow, config, model_deprecated, validation_error) bail without retry ([:42](../app/engines/llm_client.py#L42)).

Also used outside the engine: Help bulk-AI tasks call `call_gemini_text` and raise `RuntimeError` if `GEMINI_API_KEY` is unset (see [workflows.md](./workflows.md) §11).

## 4. Vertex AI Gemini — OFF by default

`call_vertex_ai_text` ([app/engines/llm_client.py:269](../app/engines/llm_client.py#L269)):
`genai.Client(vertexai=True, project=settings.GCP_PROJECT_ID, location=settings.VERTEX_AI_LOCATION)`,
default model `gemini-2.5-flash`. Routed **only** when the classify backend selects it.

Two independent ways Vertex can be chosen, and neither is on by default:

- **`VERTEX_AI_CLASSIFY_ENABLED` — default `False`** ([app/config.py:86](../app/config.py#L86)).
- **`org_settings.classify_backend`** — read by `classify_discrepancies_task`; `use_vertex = (backend == "vertex")`, default backend `gemini-dev` ([app/tasks/classify_task.py:109](../app/tasks/classify_task.py#L109)). The live route is reportable via `GET /v1/diag/classify-route` (per CLAUDE.md).

So in the default configuration all classification goes through the dev Gemini API, not Vertex. `VERTEX_AI_GEMINI_API_KEY` was removed as vestigial (audit §3.3, per the config docstring).

## 5. SMTP email

[app/services/email.py](../app/services/email.py) — a sync `send_smtp_email(...)` helper
that **never raises**, returning `{ok, error, latency_ms}`.

- **Env-driven (NOT in the Pydantic Settings class):** `SMTP_HOST` (required — `ok=False` if missing), `SMTP_PORT` (default `587`), `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` (default sentinel `rounds-noreply@vin.com`) ([app/services/email.py:52](../app/services/email.py#L52)). The diagnostic endpoints in [app/api/email_debug.py](../app/api/email_debug.py) read the same five vars ([app/api/email_debug.py:69](../app/api/email_debug.py#L69)).
- **Transport:** `smtplib.SMTP(host, port, timeout=10)` → `starttls()` → optional `login()` → `sendmail()`. Multipart (text + optional HTML).
- **Recipient validation:** `ok=False` (no raise) on missing `@`.
- **The only sender of operational email** is the SOP deadline task, and **only when `SOP_DEADLINE_EMAIL_ENABLED` is true (default OFF, [app/config.py:110](../app/config.py#L110))**. See [workflows.md](./workflows.md) §3. The email-debug endpoints can send a test message on demand (admin-gated). No other workflow sends email — ingest, exports, corrections, polls, locks are all WS-only.

## 6. Railway (hosting / infra)

Per CLAUDE.md, Railway hosts the api + worker services and provides the isolated
Postgres + Redis plugins. The app consumes them as `DATABASE_URL` and `REDIS_URL`
([app/config.py:33](../app/config.py#L33)). A config validator normalizes Railway's
`postgresql://` to the `postgresql+asyncpg://` scheme the async engine needs
([app/config.py:137](../app/config.py#L137)). This is infrastructure, not an application
API integration; the service IDs and deploy commands are in CLAUDE.md and were not
re-verified against live infra here.

## What is NOT integrated (so the demo doesn't overclaim)

- **No Vertex by default** — see §4.
- **No payment / billing, calendar, SSO/OAuth, third-party analytics, Slack/webhook, or CRM** integrations exist in the config or service layer. IMPLEMENTATION NOT FOUND.
- **`VERTEX_AI_GEMINI_API_KEY`** is intentionally removed (vestigial).
- **Build-time `VITE_HELP_ASK_AI_ENABLED`** is NOT plumbed through the Dockerfile and is intentionally not consulted; the runtime `HELP_ASK_AI_ENABLED` flag (default OFF) is the SSOT for the Help Ask-AI endpoint ([app/config.py:121](../app/config.py#L121)).

## Source Verification
- **Files Used:** app/config.py, app/engines/llm_client.py, app/services/gcs.py, app/services/email.py, app/api/email_debug.py, app/tasks/classify_task.py, app/api/gcs_upload.py
- **Components Used:** none
- **APIs Used:** Google Cloud Storage (signed PUT/GET URLs), Gemini File API + generate_content, Vertex AI generate_content (off), SMTP; internal `/v1/diag/classify-route` and `/v1/gcs/upload-url`/`upload-complete` referenced
- **Database Tables Used:** org_settings (classify_backend / classify_model); sessions/sources for upload scope (referenced)
- **Permission Logic Used:** none in the integration layer itself; the SMTP-debug and Help bulk-AI endpoints that drive these integrations are admin-gated (`require_admin` → `johndean@vin.com`); read-only diag probes require only JWT.
- **Confidence Score:** High — GCS, Gemini, Vertex, and SMTP surfaces read directly; Google STT call internals not opened (config-level only, flagged).
- **Evidence Links:** [app/config.py:80](../app/config.py#L80), [app/config.py:84](../app/config.py#L84), [app/config.py:86](../app/config.py#L86), [app/config.py:110](../app/config.py#L110), [app/engines/llm_client.py:118](../app/engines/llm_client.py#L118), [app/engines/llm_client.py:269](../app/engines/llm_client.py#L269), [app/services/gcs.py:57](../app/services/gcs.py#L57), [app/services/email.py:52](../app/services/email.py#L52)
