# Rounds — Developer Guide

> **Who this is for.** A new developer joining the Rounds codebase, expected to be productive within ~8–12 hours of cold reading. Existing maintainers can skim; the value is in the cross-references back to ADRs and business rules.
>
> **What this is.** A read-from-cold onboarding map of every load-bearing system in Rounds. Each section answers: *what does this system do, where does it live in the code, and where do I look next?*
>
> **What this is NOT.** It is not the API reference (use `/v1/openapi.json`), not the deployment runbook (use `CLAUDE.md` + Railway), and not a feature catalog. It is the **mental model** a maintainer needs in order to navigate the codebase.

---

## Table of Contents

1. [System architecture](#1-system-architecture)
2. [Application startup](#2-application-startup)
3. [Processing flow (the SOP pipeline)](#3-processing-flow-the-sop-pipeline)
4. [Session lifecycle](#4-session-lifecycle)
5. [Queue lifecycle](#5-queue-lifecycle)
6. [Editor lifecycle](#6-editor-lifecycle)
7. [Export lifecycle](#7-export-lifecycle)
8. [Security model](#8-security-model)
9. [Data flow](#9-data-flow)

Throughout: **ADR-NNN** links to `docs/adr/ADR-NNN-*.md`, **BR-NNN** links to `docs/BUSINESS_RULES.md#br-nnn`.

---

## 1. System architecture

### 1.1 Layered model

Rounds enforces a strict four-tier dependency direction:

```
HTTP (FastAPI)
  └─→ app/api/<domain>.py             (router — request/response)
        └─→ app/tasks/<job>.py        (Celery — async work)
             OR
            app/services/<concern>.py (sync utility — no async, no DB writes)
        └─→ app/engines/<algorithm>.py (deterministic OR LLM-dispatched)
             └─→ SQLAlchemy + Postgres
```

**Direction is one-way:**

- An engine never imports from `app/api/`.
- An engine never imports from `app/tasks/`.
- A task may import an engine (for the algorithm) but routes API calls through the engine's pure interface.
- The API may dispatch a task (Celery `delay`) or call an engine directly for sync work.

This is enforced by convention + code review, not by a linter. The audit confirms zero circular imports today.

### 1.2 Module-by-module responsibilities

| Path | What lives here | Examples |
|---|---|---|
| `app/api/` | FastAPI routers — one file per domain. Request/response shapes, validation, routing. No business logic. | `sessions.py`, `corrections.py`, `exports.py`, `diagnostics.py` |
| `app/tasks/` | Celery tasks — async pipeline. Each task is a unit of work that can retry, fail, or chain. | `ingest.py`, `transcribe.py`, `fusion.py`, `finalize.py`, `sop_tasks.py` |
| `app/engines/` | Pure algorithms. Deterministic where possible. No HTTP, no Celery, no DB writes — only reads. | `alignment.py`, `fusion.py`, `state_machine.py`, `artifact_transformer.py` |
| `app/services/` | Cross-cutting utilities. Sync. May touch external services (GCS, SMTP, Redis). | `gcs.py`, `auth_users.py`, `email.py` |
| `app/middleware/` | FastAPI ASGI middleware — request_id, envelope, idempotency. | `envelope.py`, `idempotency.py`, `request_id.py` |
| `app/security/` | Authorization helpers + role gates. | `roles.py` |
| `app/iil/` | Internal Intent Layer — normalization + validation invariants. | `normalization.py`, `validation.py` |
| `app/db/` | Database wiring. Connection, async session, migration applier. | `migrations.py`, `session.py` |
| `migrations/` | Numbered SQL files. Idempotent forward-only. See [ADR-011](./adr/ADR-011-migrations-ledger.md). | `000_*.sql` … `052_*.sql` |
| `tests/` | Backend tests. Health checks, locked-weight invariants, GCS scope, security helpers. | `test_health.py`, `test_gcs_scope.py` |
| `frontend/src/` | Vue 3 SPA. See section 6. | |

### 1.3 Key files to know

- `app/main.py` — FastAPI app instantiation, middleware stack, router registration, lifespan handler. Start here on the backend.
- `app/config.py` — all `Settings`. The locked weights live here ([ADR-007](./adr/ADR-007-locked-weights.md)).
- `app/engines/state_machine.py` — session FSM. [ADR-002](./adr/ADR-002-session-lifecycle.md), [ADR-003](./adr/ADR-003-fsm-python-only.md), [BR-007](./BUSINESS_RULES.md#br-007).
- `app/engines/ws_bridge.py` — Redis pub/sub → WebSocket fan-out. [ADR-008](./adr/ADR-008-websocket-architecture.md).
- `frontend/src/services/api.ts` — every backend route the frontend calls.
- `frontend/src/views/EditorView.vue` — the editor orchestrator. [ADR-009](./adr/ADR-009-editor-architecture.md).
- `docs/port-source/` — React SSOT for the UI. Read before porting any view.

---

## 2. Application startup

### 2.1 Backend boot order (`app/main.py`)

Reading top-to-bottom of `app/main.py`:

1. **Imports + router list.** Every domain router is imported at module top so registration is explicit. See `app/main.py:18–35`.
2. **Lifespan handler** (`app/main.py:46–91`). On `startup`:
   - Verify `GOOGLE_APPLICATION_CREDENTIALS` path exists (warns at runtime if missing — GCS calls will fail otherwise).
   - **Seed `auth_users` from env CSV.** Reads `Settings.AUTH_USERS`, calls `seed_from_env_if_empty()`. Idempotent — row-count short-circuit makes second-boot a no-op. Failure is logged but non-fatal (so login still works via the env-CSV fallback path; see [BR-020](./BUSINESS_RULES.md#br-020), [ADR-001](./adr/ADR-001-authentication.md)).
   - **Start the WebSocket bridge task.** `WSManager` + `start_ws_bridge()` — Redis subscriber + per-session client fan-out. See [ADR-008](./adr/ADR-008-websocket-architecture.md).
3. **FastAPI instantiation** (`app/main.py:94–98`). Title, version, lifespan.
4. **Middleware stack** (applied in REVERSE order — last `add_middleware` is the OUTER one):
   - `CORSMiddleware` — origin allow-list at `app/main.py:102–106`.
   - `IdempotencyMiddleware` — replays cached responses on `Idempotency-Key`. TTL = 86400s ([BR-012](./BUSINESS_RULES.md#br-012)).
   - `EnvelopeMiddleware` — wraps every JSON response in `{success, data, error, meta}` (MIC §9.1 locked invariant). MUST be below `RequestIdMiddleware` so envelope.meta.request_id can read.
   - `RequestIdMiddleware` — outermost. Stamps `x-request-id` on every response.
5. **Health + version routes** (`app/main.py:138–163`).
6. **WebSocket route** (`app/main.py:166–182`) at `/v1/ws/sessions/{session_id}`. See [ADR-008](./adr/ADR-008-websocket-architecture.md).
7. **Domain routers registered** (`app/main.py:186–205`).
8. **Static SPA mount** (`app/main.py:210+`). If `frontend/dist/` exists (production), mount `/assets` for hashed assets and serve `index.html` for every other path (with a path-traversal guard).

### 2.2 Worker boot

The Celery worker process imports `app.tasks.celery_app` which creates the Celery instance, registers tasks via the `bind=True, base=RoundsTask` decorator on each task function, and starts consuming from Redis. There is no lifespan hook on the worker — startup is what Celery does by default.

### 2.3 Migration apply

Railway's deploy command runs `python scripts/migrate.py` before the API/worker boots. The applier reads `migrations/`, checks `schema_migrations` for already-applied slugs, applies the rest in numeric order. See [ADR-011](./adr/ADR-011-migrations-ledger.md).

---

## 3. Processing flow (the SOP pipeline)

When a session is uploaded, it flows through ~8 named stages. Each stage is one or more Celery tasks. The DAG is wired in `app/tasks/ingest.py` (the head task) and chains forward by Celery `chord` / `chain`.

| Stage | Task file | Engine(s) | What it does |
|---|---|---|---|
| **1. Ingest** | `app/tasks/ingest.py` | (orchestrator) | Validates the GCS upload. Records source metadata. Fans out to transcribe + frame-sample in parallel. |
| **2. Transcribe** | `app/tasks/transcribe.py`, `app/tasks/ai_process.py` | `app/engines/llm_client.py` | Two paths: chunked Google STT (`google_stt_chunked` — default), or Gemini multimodal (`_process_direct`). The Gemini path has a runaway-loop detector ([BR-015](./BUSINESS_RULES.md#br-015)). |
| **3. Normalize** | `app/tasks/normalize.py` | `app/iil/normalization.py`, `app/iil/validation.py` | Removes TIER1 filler words (um/uh/er/ah/umm/uhh/hmm) where the normalization passes the IIL Tier 2 confidence gate ([BR-010](./BUSINESS_RULES.md#br-010)). Preserves clinical terms. |
| **4. Frame-sample** | `app/tasks/frame_task.py` | `app/engines/anchor.py`, ffmpeg | Samples frames at `FRAME_SAMPLE_FPS = 2/sec`. Computes visual-change scores. Flags frames exceeding `VISUAL_CHANGE_THRESHOLD = 8.0` ([BR-011](./BUSINESS_RULES.md#br-011)) as anchor candidates. |
| **5. Anchor** | `app/tasks/anchor_task.py` | `app/engines/anchor.py` | Cross-validates anchor candidates against slide changes within `ANCHOR_CROSS_VALIDATE_WINDOW = 5.0s`. |
| **6. Fusion** | `app/tasks/fusion.py` | `app/engines/fusion.py` | Combines visual + anchor + semantic scores using locked weights ([BR-008](./BUSINESS_RULES.md#br-008)). Threshold at `FUSION_BOUNDARY_THRESHOLD = 0.35` produces final segment boundaries. |
| **7. Align** | `app/tasks/align.py`, `app/tasks/lcs_discrepancies.py` | `app/engines/alignment.py`, `app/engines/diff.py` | Maps segments to slides via four-factor weighted alignment ([BR-009](./BUSINESS_RULES.md#br-009)). LCS pass produces `discrepancies` rows for reviewer attention. |
| **8. Finalize** | `app/tasks/finalize.py` | `app/engines/state_machine.py` | Marks the session `ready`. Triggers downstream: `kp_task` (keypoint extraction) + `sop_auto_init` (assignee init). |

The DAG is observable via `/v1/queue` (per-session view) and via Celery's Flower (worker-process view). Failure of any task marks the session `failed` via the state machine; operator rescue is `/v1/diag/reingest/<id>` ([ADR-006](./adr/ADR-006-queue-processing.md)).

**Live progress** is published to `session:{id}` Redis channel by each task; the WS bridge ([ADR-008](./adr/ADR-008-websocket-architecture.md)) fans out to the upload page + editor.

---

## 4. Session lifecycle

### 4.1 State diagram

```
            ┌────── /v1/sessions (POST) ──────┐
            ▼                                  │
       ┌──────────┐  upload finished   ┌──────────┐
       │uploading │─────────────────▶│ingesting │
       └──────────┘                    └──────────┘
            │                                │
            │ stuck > 5min                   │ task chain runs
            │ (upload_watchdog)              ▼
            ▼                          ┌──────────┐
       ┌──────────┐                    │processing│
       │  failed  │◀───────────────────└──────────┘
       └──────────┘   task failure          │
            │                               │ finalize OK
            │ /v1/diag/reingest             ▼
            └──────────────────────▶ ┌──────────┐
                                     │  ready   │
                                     └──────────┘
                                          │
                              published ─┐│┌─ archived
                                         ▼▼▼
                                  ┌──────────────┐
                                  │ terminal set │
                                  └──────────────┘
```

The full transition table lives in `app/engines/state_machine.py:37–44` ([BR-007](./BUSINESS_RULES.md#br-007), [ADR-002](./adr/ADR-002-session-lifecycle.md)).

### 4.2 Soft-delete + restore + purge

`sessions.deleted_at` is the soft-delete column. Trash + restore + purge are gated to a small allow-list (`SESSION_TRASH_ALLOWED` — [BR-002](./BUSINESS_RULES.md#br-002)). Operators with `LEGACY_ADMIN_EMAIL` and one external service account (`carlab@vin.com`) can perform any of those actions; everyone else gets 403.

### 4.3 What is NOT enforced at the DB

The FSM lives **only in Python** — `sessions.status` is `TEXT NOT NULL DEFAULT 'ingesting'` with no CHECK constraint. See [ADR-003](./adr/ADR-003-fsm-python-only.md) for why and what hardening would look like.

### 4.4 Where to look

- `app/engines/state_machine.py` — FSM source of truth.
- `app/api/sessions.py` — CRUD, list, soft-delete (`/v1/sessions/<id>` DELETE → soft, `/v1/sessions/<id>/purge` → hard).
- `app/api/diagnostics.py:435` — operator rescue (`reingest`).

---

## 5. Queue lifecycle

### 5.1 Task primitives

Every Celery task in Rounds inherits from `RoundsTask` (`app/tasks/celery_app.py`). The base class:

- Wraps the task in a try/except, marks the session `failed` on terminal error.
- Publishes a WebSocket event (`session:{id}` channel) on start, on progress, on finish.
- Defaults retries to 3 (`CELERY_MAX_RETRIES`) with 60s exponential backoff (`CELERY_RETRY_BACKOFF_BASE`).

### 5.2 Scheduled (Beat) tasks

| Task | Cadence | What it does |
|---|---|---|
| `sop_check_deadlines_task` | hourly | Scans `sop_state` for overdue stages. Sends a deadline email per `(session, stage)` with the 23h throttle ([BR-004](./BUSINESS_RULES.md#br-004), [BR-005](./BUSINESS_RULES.md#br-005)). Gated by `SOP_DEADLINE_EMAIL_ENABLED` flag (default off — flip in Railway worker env to activate). |
| `upload_watchdog_task` | 60s | Recovers sessions stuck on `status='uploading'` for > 5 min ([BR-014](./BUSINESS_RULES.md#br-014)). Gated by `UPLOAD_WATCHDOG_ENABLED` flag (default off). |

### 5.3 Operator visibility

- `/v1/queue` returns per-session task state for the operator dashboard.
- `/v1/diag/*` operator routes wrap common rescue actions (see `CLAUDE.md` "Emergency operator commands").

### 5.4 Where to look

- `app/tasks/celery_app.py` — Celery app config + `RoundsTask` base class.
- `app/tasks/<step>.py` — individual stage tasks.
- `app/api/queue.py` — operator queue endpoint.
- [ADR-006](./adr/ADR-006-queue-processing.md) — full decision context.

---

## 6. Editor lifecycle

### 6.1 Component map

`frontend/src/views/EditorView.vue` (1,164 LOC) is the orchestrator. It composes 17 sub-components from `frontend/src/components/editor/`:

| Component | What it shows |
|---|---|
| `VideoStrip.vue` | Video player + chapter markers + scrubber. `<track>` element wired to `/v1/sessions/{id}/captions.vtt` ([ADR-005](./adr/ADR-005-corrections-ledger.md)). |
| `TranscriptColumn.vue` | Scrollable segment list with corrections + chat/poll anchors. |
| `ChatTab.vue`, `PollsTab.vue` | Chat / poll panel with drag-to-anchor + drag-to-reorder. |
| `DiscrepanciesPane.vue` | Reviewer-priority discrepancies, sorted by [BR-006](./BUSINESS_RULES.md#br-006). Mark OK / Dismiss / resolve. |
| `AdminTab.vue` | Operator rescue (admin-only, gated by `LEGACY_ADMIN_EMAIL` — [BR-001](./BUSINESS_RULES.md#br-001)). |
| `DownloadMenu.vue` | Export dispatch (`.docx` / `.srt` / `.vtt` / `.txt` / `.html` / `.zip`). |
| `DecisionCard.vue` | Per-correction undo/redo + word-level diff display. |
| `AnchorBlock.vue` | The inline anchor for chat/poll placements; drag-to-re-anchor. |
| ... | (10 other ports — see directory listing) |

### 6.2 Page-load sequence

1. Route enters `/#/editor/<session_id>`.
2. `loadStages` map kicks off (`_trackLoad` helper). Stages: session metadata, segments, words, chat, polls, discrepancies, corrections.
3. Each stage hits an API in `frontend/src/services/api.ts`, populates a reactive ref, surfaces a per-stage loading-bar segment.
4. Keyboard shortcuts wire (Cmd+Z / Cmd+Y / Cmd+F) with input-focus guard.
5. WebSocket connects to `/v1/ws/sessions/{id}` to receive correction events from other tabs + worker.

### 6.3 Corrections

Every edit becomes a row in `corrections` ([ADR-005](./adr/ADR-005-corrections-ledger.md)). Undo / Redo are pointer moves over `sequence_number`. Find-Replace is one correction with N segment payloads.

Some types auto-close discrepancies ([BR-018](./BUSINESS_RULES.md#br-018)): `text_edit`, `mark_ok`.

### 6.4 Captions

The editor's `<track>` element loads from `/v1/sessions/{id}/captions.vtt`. The route ETag-caches on `W/"{session_id}-{max_correction_seq}"` — the browser sends `If-None-Match` on every reload and the server returns 304 (zero body) until a new correction lands. The `<track>` can't carry an `Authorization` header, so the editor wraps the response in a Blob URL (authenticated `fetch` → `URL.createObjectURL`).

### 6.5 Where to look

- `frontend/src/views/EditorView.vue` — orchestrator
- `frontend/src/components/editor/` — sub-components
- `frontend/src/services/api.ts` — backend wiring
- `frontend/src/composables/` — `toast`, `confirm`, `modal`
- `docs/port-source/EditorView.jsx` — React SSOT
- `app/api/exports.py:117` — captions endpoint
- [ADR-009](./adr/ADR-009-editor-architecture.md) — porting discipline

---

## 7. Export lifecycle

### 7.1 Route → engine

```
HTTP POST/GET /v1/sessions/{id}/exports/{format}
   └─ app/api/exports.py:38                       — fmt dispatch + auth
        └─ load_session_for_export(session_id)    — read every needed row
             └─ to_<fmt>(SessionExport)           — format-specific render
        └─ INSERT INTO artifacts                   — record bytes + generated_by
   └─ Response(content=body, media_type=…, attachment=…)
```

### 7.2 Format rules

- `.docx` / `.txt` / `.html` strip TIER1 filler words for readability ([BR-016](./BUSINESS_RULES.md#br-016)).
- `.srt` / `.vtt` preserve fillers so captions stay in lock-step with audio.
- Empty speaker labels → `"(Unknown)"` ([BR-017](./BUSINESS_RULES.md#br-017)).
- `.zip` packages every other format + the original media.

### 7.3 Captions specifically

`/v1/sessions/{id}/captions.vtt` is a separate route ([ADR-005](./adr/ADR-005-corrections-ledger.md) — added in Phase C1). It ETag-caches; the editor's `<track>` uses it.

### 7.4 Where to look

- `app/api/exports.py` — routes
- `app/engines/artifact_transformer.py` — loader + renderers
- `app/iil/normalization.py:37` — `TIER1_WORDS` filler set
- [ADR-004](./adr/ADR-004-export-engine.md) — single-source-transformer decision

---

## 8. Security model

### 8.1 Authentication

JWT-based ([ADR-001](./adr/ADR-001-authentication.md)). Sign with `API_SECRET_KEY`, HS256, 8-hour expiry. The dependency `CurrentUser` (`app/auth.py`) is the standard injection on every protected route.

Login flow:

1. `POST /v1/auth/login` with `username + password`.
2. Server validates against `auth_users` first, falls back to env CSV if missing ([BR-020](./BUSINESS_RULES.md#br-020)).
3. Returns access token.

### 8.2 Authorization

- **Bootstrap admin** is `LEGACY_ADMIN_EMAIL = "johndean@vin.com"` ([BR-001](./BUSINESS_RULES.md#br-001)). Gates `/v1/diag/*` and the editor's Admin tab.
- **Session trash** gated to `SESSION_TRASH_ALLOWED` ([BR-002](./BUSINESS_RULES.md#br-002)) — `LEGACY_ADMIN_EMAIL` + `carlab@vin.com`.
- **Session membership** does not exist today (Rounds is single-tenant). Any authenticated user can read any non-deleted session.
- **WebSocket** does not check session ACL today ([ADR-008](./adr/ADR-008-websocket-architecture.md)).

### 8.3 R7 invariant (GCS scope)

`/v1/gcs/upload-complete` rejects any `gcs_uri` outside `gs://<bucket>/sessions/<id>/`. Locked invariant. See `app/services/gcs.py::find_out_of_scope_uri` and `tests/test_gcs_scope.py`.

### 8.4 Idempotency

`Idempotency-Key` header → cached response replay for 24h ([BR-012](./BUSINESS_RULES.md#br-012)). Replay storage in Redis. See `app/middleware/idempotency.py`.

### 8.5 Envelope error contract

Every JSON response is `{success, data, error, meta}`. Locked invariant from MIC §9.1. See `app/middleware/envelope.py`. Errors raised as `MICException(code=, http_status=)` materialize as `{success:false, error:{code, message, context}}`.

### 8.6 Where to look

- `app/auth.py` — JWT + env fallback
- `app/security/roles.py` — admin gate
- `app/api/sessions.py:36` — trash allow-list
- `app/services/gcs.py` — R7 enforcement
- `app/middleware/idempotency.py` — replay cache
- `app/middleware/envelope.py` — response shape

---

## 9. Data flow

### 9.1 From upload to export

```
upload ─→ GCS bucket (gs://…/sessions/<id>/<file>)
        └─→ POST /v1/gcs/upload-complete  ─→ sources row (session_id, gcs_uri, kind)
                                              └─→ ingest_task.delay(session_id)
                                                    ├─→ transcribe_task → segments + words
                                                    ├─→ frame_task → slide_time_ranges + anchor candidates
                                                    ├─→ anchor_task → cross-validated anchors
                                                    ├─→ normalize_task → normalization_results + IIL validation
                                                    ├─→ fusion_task → segment boundary updates
                                                    ├─→ align_task → alignments + discrepancies
                                                    └─→ finalize_task → sessions.status = 'ready'
                                                          ├─→ kp_task → keypoints
                                                          └─→ sop_auto_init_task → sop_state + assignees

reviewer ─→ editor (/#/editor/<id>) ─→ POST /v1/corrections/<id>
                                          └─→ corrections row (append-only)
                                                ├─→ discrepancies auto-close ([BR-018](./BUSINESS_RULES.md#br-018))
                                                └─→ audit_events row (provenance)

export   ─→ GET /v1/sessions/<id>/exports/<fmt>
              └─→ load_session_for_export()
                    ├─→ apply corrections in sequence_number order
                    └─→ to_<fmt>() ─→ Response body + artifacts row
```

### 9.2 Key tables

| Table | Role | Append-only? |
|---|---|---|
| `sessions` | Top-level session row. `status` is FSM. | No (status mutates) |
| `sources` | Uploaded media files per session. | No |
| `segments`, `words` | Transcribed text + per-word timing. | No (corrections replay layered on top) |
| `slides`, `speakers` | Per-source structured metadata. | No |
| `slide_time_ranges`, `frames`, `anchors` | Per-frame visual signals. | Yes |
| `alignments` | Segment ↔ slide mapping with confidence. | No (status mutates) |
| `discrepancies` | Reviewer-attention items. | No (status mutates) |
| `corrections` | Append-only edit ledger ([ADR-005](./adr/ADR-005-corrections-ledger.md)). | **Yes** |
| `audit_events` | Provenance log + throttle slots ([BR-004](./BUSINESS_RULES.md#br-004)). | **Yes** |
| `sop_state`, `session_stage_assignees` | SOP state per session. | No |
| `artifacts` | Exported file bytes (one per (session, kind)). | No (`ON CONFLICT … DO UPDATE`) |
| `auth_users` | Authenticated users + roles ([ADR-001](./adr/ADR-001-authentication.md)). | No |
| `schema_migrations` | Migration application ledger ([ADR-011](./adr/ADR-011-migrations-ledger.md)). | **Yes** |

### 9.3 Where to look

- `migrations/000_*.sql` through `migrations/052_*.sql` — every schema mutation in chronological order.
- `app/api/<domain>.py` — read/write surface per table.
- `app/engines/artifact_transformer.py` — the single point that reads every export-relevant table.

---

## Reading order for a new developer

If you have 8–12 hours, here's the recommended path:

1. **(45 min)** Read this file end-to-end.
2. **(30 min)** Read `CLAUDE.md` — project conventions + operator commands.
3. **(45 min)** Read `docs/BUSINESS_RULES.md` — get the 20 rules into your head.
4. **(1.5h)** Read ADR-001 through ADR-011 — the architectural decisions.
5. **(1h)** Read `app/main.py` + `app/config.py` — the boot + config surface.
6. **(1h)** Read `app/engines/state_machine.py` + `app/engines/ws_bridge.py` — load-bearing engines.
7. **(1h)** Read `app/api/sessions.py` + `app/api/corrections.py` — the central API surfaces.
8. **(1h)** Read `frontend/src/views/EditorView.vue` (top-down, skim sub-components linked from it).
9. **(45 min)** Read one task end-to-end: `app/tasks/ingest.py` → `app/tasks/transcribe.py` → `app/engines/llm_client.py`. This is how the pipeline actually flows.
10. **(remainder)** Run the dev stack locally (`scripts/migrate.py` + `uvicorn` + Celery worker), hit `/v1/health`, upload a tiny test session, watch it flow.

At the end of that path, you can productively contribute a fix or small feature without needing extensive guidance.
