# ADR-006 — Queue processing: Celery DAG + WS bridge

- **Status:** Accepted
- **Date:** 2026-05-17 (bootstrap), refined 2026-06-05
- **Deciders:** johndean@vin.com
- **Related:** [BR-003](../BUSINESS_RULES.md#br-003), [BR-004](../BUSINESS_RULES.md#br-004), [BR-014](../BUSINESS_RULES.md#br-014), [ADR-008](./ADR-008-websocket-architecture.md)

## Context

Ingest is a multi-step pipeline: transcribe → normalize → frame-sample → anchor → fusion → finalize → keypoints → SOP auto-init. Each step can take minutes; some hit Google Cloud STT / Gemini / Vertex; some require ffmpeg; all must be retryable. The constraints:

1. **No blocking the HTTP request.** A user uploading a 90-minute session cannot wait for ingest synchronously.
2. **Retryable on transient failure.** Network blips to Google APIs, ffmpeg OOM, Gemini quota — all must auto-retry.
3. **Live progress in the UI.** The user watches the upload page; they need to see "transcribing… 38%" not a spinner.
4. **Operator rescue.** A stuck session must be re-runnable from the diag routes ([ADR-002](./ADR-002-session-lifecycle.md)).
5. **Cost ceilings.** Concurrent ingests are capped (`MAX_CONCURRENT_SESSIONS = 3`) so we don't burn Gemini quota on a stampede.

## Decision

**Celery + Redis broker + Postgres result backend. The pipeline is a DAG of named tasks; live progress is published to a Redis pub/sub channel and bridged into FastAPI WebSockets.**

- Each pipeline step is a Celery task in `app/tasks/<step>.py` (e.g. `transcribe.py`, `frame_sample.py`, `anchor.py`, `fusion.py`, `finalize.py`, `kp_task.py`, `sop_tasks.py`).
- Tasks chain via Celery `chord` / `chain` primitives. Failure modes: retry inside the task (3 attempts with exponential backoff — `CELERY_MAX_RETRIES = 3`, `CELERY_RETRY_BACKOFF_BASE = 60` at `app/config.py:65–66`); on terminal failure, the task marks `sessions.status = 'failed'` via the state machine ([BR-007](../BUSINESS_RULES.md#br-007)).
- Each task emits progress events to Redis (`pub` on `session:{id}` channel) — picked up by the WS bridge ([ADR-008](./ADR-008-websocket-architecture.md)) and forwarded to every connected client.
- A Celery Beat scheduler runs periodic tasks: `sop_check_deadlines_task` (hourly — [BR-003](../BUSINESS_RULES.md#br-003), [BR-004](../BUSINESS_RULES.md#br-004)), `upload_watchdog_task` (every 60s — [BR-014](../BUSINESS_RULES.md#br-014)).
- The `app/api/queue.py` route surfaces queue state to the operator dashboard (job count per session, retry counts, last error).
- Operator rescue is a thin layer: `/v1/diag/reingest/<id>` resets state and enqueues the head task.

## Consequences

- **Positive.**
  - HTTP request stays sub-second.
  - Transient Google API failures are absorbed by the retry logic; the user doesn't see them.
  - WebSocket progress feels real-time (latency ~100ms from task event to UI).
  - Operator rescue is a curl call, not a code change.
- **Negative.**
  - Two-process deployment: the API and the worker both have to be alive on Railway. Either being down breaks the pipeline.
  - Celery's failure modes have a learning curve — task soft-time-limit vs hard-time-limit vs retry-eta is non-obvious.
  - Redis is now a hard dependency for both the broker and the pub/sub channel. Lose Redis → entire pipeline stops.
- **Risks.**
  - A task that dies between updating `sessions.status` and publishing the WS event leaves the UI showing the old state until a refresh.
  - Beat tasks have idempotency requirements ([BR-004](../BUSINESS_RULES.md#br-004) — 23h email throttle is implemented via an `audit_events` row + advisory lock to handle exactly this).
  - Concurrent reingest of the same session is not currently locked — the diag route trusts the caller to wait for the prior run to finish.

## Code locations

- `app/tasks/` — 10 task files, 21 tasks total
- `app/engines/ws_bridge.py` — Redis pub/sub → FastAPI WebSocket fan-out ([ADR-008](./ADR-008-websocket-architecture.md))
- `app/api/queue.py` — operator-visible queue state
- `app/api/diagnostics.py` — `/v1/diag/reingest`, `/v1/diag/revoke-task`, `/v1/diag/flush-celery-queue`, `/v1/diag/sop-check`
- `app/config.py:37–38` — `MAX_CONCURRENT_SESSIONS`, `MAX_QUEUE_LENGTH`
- `app/config.py:65–67` — Celery retry config
- `app/config.py:91–93` — upload watchdog flags ([BR-014](../BUSINESS_RULES.md#br-014))
- `app/config.py:101` — `SOP_DEADLINE_EMAIL_ENABLED` flag

## Alternatives considered

1. **RQ (Redis Queue)** — rejected because Celery's chord / chain primitives match the DAG shape and RQ would require hand-rolling the orchestration.
2. **Cloud Tasks / Pub/Sub directly** — rejected because the deploy target (Railway) makes Redis trivial and Cloud Tasks adds GCP-region coupling.
3. **A custom in-process task queue** — rejected because retries + visibility + Beat tasks would each need to be reinvented.
4. **Server-Sent Events (SSE) for progress instead of WebSockets** — viable, but the editor uses bidirectional WS for other features (caption stream, scrubber sync) so the bridge stayed WS-only.

## When this ADR should be revisited

- If Celery's chord / chain semantics turn out to be hard to evolve (we've added 21 tasks; future shapes may strain it).
- If the API + worker deploy ordering becomes a frequent incident source — then a "task runner inside the API container" simplification may pay off.
- If pipeline cost (Google STT + Gemini) becomes the dominant constraint, the queue may need throttling at a finer grain than `MAX_CONCURRENT_SESSIONS`.
