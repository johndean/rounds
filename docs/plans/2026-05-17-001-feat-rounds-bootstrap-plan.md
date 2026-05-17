# Plan: Rounds (rounds.vin) — Pixel-by-Pixel Port of Transcript Software v4

**Type:** feat
**Status:** active
**Created:** 2026-05-17
**Target repos:** `vin-swe/rounds` (dev origin), `johndean/rounds` (production — Railway auto-deploy)
**Working directory:** `C:\Users\JohnDean\rounds` (mirror po-vin layout)
**Domain:** rounds.vin
**Stack:** Vue 3 + TypeScript + Vite (frontend) · FastAPI + Postgres+pgvector + Redis + Celery (backend) · GCS + Cloud STT + Gemini + Vertex AI (services) · Railway (hosting)

---

## 1. Context

`Rounds` is the successor to MIC (Media Intelligence Console / Center). It is a transcript-software product whose **frontend surface is fully specified** by the `Transcript Software v4.html` prototype documented in `IMPLEMENTATION.md` (the spec the user provided in the conversation), and whose **backend architecture is fully specified** by the MIC `GCS / Railway / AI services` exacting-duplication reference audit (also in the conversation).

The user's explicit constraint: **pixel-by-pixel with zero gaps**. Every surface from IMPLEMENTATION.md must reproduce in the Vue port. Every one of the 78 functional buttons must fire its toast/confirm/modal/audit primitive. Every route, every editor tab, every settings section, every drill-in, every state, every accent-color rollout — all of it ships.

The new stack diverges from the prototype's React-via-CDN: Rounds will be Vue 3 + TS + Vite (matching `po-vin` VIN convention) with the prototype's 16 JSX modules re-implemented as Vue SFCs + Pinia stores + Vue Router (hash mode). The backend is a 1:1 port of the MIC architecture from the audit, in a fresh GCP project / Railway project / GitHub repo pair.

This is a Deep-tier plan: ~12K LOC frontend + ~15K LOC backend + infra setup. Estimated 4-7 weeks of focused work, executed in phases. Each phase has a verifiable milestone.

---

## 2. Requirements

- **R1.** Every UX surface documented in IMPLEMENTATION.md §1-21 ships in the Vue port. The 13 routes, 6 layout patterns (A-F), 4-tab editor, 12-section settings, 5-step improvements wizard, 8-stage SOP workflow, audit ledger, GCS QA, and viewer all render and behave as documented.
- **R2.** All 78 wired buttons (IMPLEMENTATION.md §17) fire their documented primitive — toast / confirm / modal / inline editor / audit log / mock API.
- **R3.** Slide-accent palette + 3-branch nav + Focus/Filter mode + focus-clear button (F1-F3 closures) all work cross-tab in the editor.
- **R4.** Pipeline circles on the Dashboard (5 AI + 8 SOP + 2 ATTN states = 15 circles) navigate to filtered Sessions list via `?stage=` / `?ai=` query params.
- **R5.** Backend reproduces MIC's GCS upload flow, Cloud STT chunked transcription, Gemini AI MODE, discrepancy classification (Gemini + Vertex AI route selectable), SOP stage state machine, audit ledger, and improvements API.
- **R6.** Locked processing weights (FUSION_*, ALIGN_*, IIL_*, CELERY_*) from MIC audit §6 carry forward unchanged — Pydantic Settings defaults match the audit table.
- **R7.** Bucket security boundary: signed-URL endpoint rejects any `gcs_uri` outside `gs://<bucket>/sessions/<session_id>/` (MIC audit §2.4 / `_find_out_of_scope_uri`).
- **R8.** JWT auth with `AUTH_USERS` CSV; `johndean@vin.com` seeded as Superadmin via `scripts/seed-admin.sql` (gitignored). Matches po-vin pattern.
- **R9.** Railway pre-deploy command runs `scripts/migrate.py`. Two-remote git pattern: `origin=vin-swe/rounds`, `production=johndean/rounds`; Railway watches production remote.
- **R10.** `gitleaks` runs in `.github/workflows/quality.yml` via direct binary (ce.vin pattern — avoids paid GitHub Action).
- **R11.** Pixel-by-pixel parity verified by Playwright screenshot diffs against a captured baseline of the React-via-CDN prototype, run in CI.
- **R12.** No public-website indexing of internal app: VIN convention is dark-topbar + sans-serif on internal pages (memory `feedback_cevin_internal_design.md`). Rounds follows this.

---

## 3. Scope Boundaries

### In-scope (this plan)

- Full frontend port (all 13 routes, all 4 editor tabs, all 12 settings sections)
- Full backend port (FastAPI + auth + sessions + sources + segments + slides + SOP + audit + improvements + WS + exports)
- GCS / Cloud STT / Gemini / Vertex AI integration (port from MIC audit §2-3, §8 code map)
- Locked-weight processing pipeline (ingest → transcribe → align → fuse → ready)
- Railway production deploy + GitHub two-remote setup + GCP project provisioning
- Pixel-fidelity verification via Playwright screenshot diffs

### Deferred to follow-up work

- Real-time live transcription (WebSocket → frontend) — backend has the bridge; frontend ships with decorative status bar per IMPLEMENTATION.md §19. Wire the live feed in a follow-up.
- Vault integration — MIC audit §5 confirms Vault is unwired even in prod. Rounds inherits the same posture; secrets flow Railway env → Pydantic Settings.
- VERTEX_AI_GEMINI_API_KEY removal — vestigial field in MIC audit §3.3. Rounds will omit it from the start.
- Multi-region deploy, DR runbooks, GCP Cloud Audit Logs config — same gaps the MIC audit §12 calls out as out of scope.
- i18n — English-only per IMPLEMENTATION.md §19.
- Real Tiptap editor for inline segment editing — ships as textarea + toolbar like the prototype.

### Explicit non-goals

- No backwards-compat shim with the MIC backend. Rounds is a clean rewrite into a fresh project.
- No migration of MIC's existing production data. Rounds starts empty.
- Not changing the locked processing weights — MIC audit §6 marks them LOCKED and CLAUDE.md §2 reinforces. Rounds inherits values verbatim.

---

## 4. Key Technical Decisions

| Decision | Rationale |
|---|---|
| **Vue 3 SFC + `<script setup lang="ts">` + Pinia + Vue Router (hash mode)** | Matches po-vin VIN convention. TS gives the production guardrails the React-via-CDN prototype lacks. Hash routing preserves IMPLEMENTATION.md §5 routes (`#/dashboard`, `#/e/:id`, etc.) verbatim. |
| **Re-use prototype CSS verbatim where possible** | `colors_and_type.css`, `app.css`, `wiring.css`, `settings.css` from IMPLEMENTATION.md are CSS files — copy them into `frontend/src/styles/` and reference from Vue SFCs. Tokens stay identical. Pixel fidelity is easier when the stylesheet is the same artifact. |
| **JSX → Vue SFC port, 1 prototype module = 1 directory of Vue files** | `editor.jsx` (1500 LOC) becomes `views/EditorView.vue` + `components/editor/*.vue` (~10-15 SFCs). Pinia stores replace React state lifted into `app.jsx`. The line count grows ~25% (Vue templates verbose) but file count grows ~3-5×. |
| **`data.jsx` fixtures → `frontend/src/fixtures/*.ts` + Pinia store hydration** | Mock fixtures stay during dev (so frontend works in isolation); a `VITE_API_MODE=mock\|live` env switches between mock and real API. Eliminates the "is the backend up" friction for UI iteration. |
| **`wiring.jsx` toast / confirm / modal / palette → Vue composables + Teleport** | `useToast()`, `useConfirm()`, `useModal()` composables, each backed by a single mounted `<TeleportTarget>` in `App.vue`. The `wired` namespace ships as `frontend/src/services/wired.ts`. Mock API stays in `frontend/src/services/api.ts`. |
| **`SLIDE_PALETTE` and the 3-branch nav style helpers ship as TS utilities** | `frontend/src/utils/slidePalette.ts` exports the 10-color array + `colorForSlide(i)` + the precomputed Map for O(1) lookup. Vue components import and use it. |
| **Backend: monorepo `app/` package mirrors MIC code map** | Audit §8 names files like `app/api/gcs_upload.py`, `app/engines/llm_client.py`, `app/tasks/transcribe.py`. Rounds ports these 1:1 to keep the audit's `file:line` traceability working as living docs. |
| **Migrations: numbered SQL via `scripts/migrate.py`** | Audit §4.5 + memory `feedback_railway_migration_pattern.md`. Pattern is `migrations/[0-9][0-9][0-9]_*.sql` applied in autocommit order. No Alembic. |
| **GCP service account JSON via base64 env var on Railway** | Audit §4.4 Option A. Entrypoint script base64-decodes `GCP_KEY_B64` into `/etc/gcp/sa.json` at container start; `GOOGLE_APPLICATION_CREDENTIALS` points there. |
| **CI: Playwright e2e + screenshot diff + pytest + gitleaks** | gitleaks direct binary per memory `reference_gitleaks_repo_setup.md`. Playwright screenshot diffs against `tests/fixtures/baseline/*.png` (captured from the React-via-CDN prototype rendering the same routes/states). |
| **Two-remote git: `vin-swe/rounds` (dev origin), `johndean/rounds` (Railway production)** | Memory `project_po_vin_remotes.md` and `reference_po_vin_railway.md` patterns. Conventional commits. CI gates auto-deploy to production. |
| **Pixel parity verified by golden-screenshot diff, not visual heuristics** | "Zero gaps" demands an objective check. Capture the prototype's render at fixed viewport+seed for every route + every state (focus mode on/off, theme light/dark, filter combinations), then Playwright diffs the Vue port against the same captures. Tolerance configured per-route — text rendering may need 1-2px slack on font hinting. |

---

## 5. Output Structure

```
C:\Users\JohnDean\rounds\
├── .env.example                      # full var contract (audit §6) + frontend VITE_* vars
├── .gitignore                        # secrets/, .env, frontend/dist, __pycache__, etc.
├── .gitleaks.toml                    # allowlist patterns (memory: reference_gitleaks_repo_setup.md)
├── .github/workflows/
│   └── quality.yml                   # gitleaks (direct binary) + pytest + Playwright + screenshot-diff
├── Dockerfile                        # python:3.11-slim + ffmpeg + Poetry; npm build for frontend; entrypoint base64-decodes GCP_KEY_B64
├── docker-compose.yml                # dev mirror: db (pgvector) + redis + api + worker
├── railway.json                      # build cmd, start cmd, healthcheck, restart policy (po-vin pattern)
├── pyproject.toml                    # Poetry: fastapi, sqlalchemy[asyncio], asyncpg, pgvector, celery, redis, google-cloud-storage/speech/aiplatform, google-genai, ffmpeg-python, pydantic-settings, python-jose[cryptography]
├── README.md                         # bootstrap instructions, env var checklist, deploy steps
├── CLAUDE.md                         # locked weights notice (audit §6), VIN conventions
├── frontend/
│   ├── package.json                  # vue@3.4 + typescript + vite + pinia + vue-router + lucide-vue-next + @playwright/test
│   ├── vite.config.ts                # alias @ → src; proxy /v1 → http://localhost:8000 in dev
│   ├── tsconfig.json
│   ├── index.html                    # single hash-routed entry
│   ├── public/
│   │   └── favicon.svg
│   ├── src/
│   │   ├── main.ts                   # createApp + Pinia + router + mount
│   │   ├── App.vue                   # router-view + <TeleportTarget>s for toast/confirm/modal/palette
│   │   ├── router/
│   │   │   └── index.ts              # 13 hash routes (IMPLEMENTATION.md §5)
│   │   ├── styles/
│   │   │   ├── colors_and_type.css   # copied verbatim from IMPLEMENTATION.md
│   │   │   ├── app.css               # copied verbatim
│   │   │   ├── wiring.css            # copied verbatim
│   │   │   └── settings.css          # copied verbatim
│   │   ├── stores/                   # Pinia
│   │   │   ├── ui.ts                 # theme/brand/density, slide focus, classify backend/model
│   │   │   ├── sessions.ts           # sessions list + filters
│   │   │   ├── editor.ts             # active session, segments, slides, polls, chat, audit
│   │   │   ├── auth.ts               # JWT, current user
│   │   │   └── improvements.ts       # improvements list + wizard state
│   │   ├── services/
│   │   │   ├── api.ts                # ports data.jsx mock API; same shape as real backend; switched by VITE_API_MODE
│   │   │   ├── wired.ts              # the `wired` namespace from wiring.jsx
│   │   │   ├── auditLog.ts           # append-only audit event sink
│   │   │   └── http.ts               # axios/fetch wrapper with JWT injection
│   │   ├── composables/
│   │   │   ├── useToast.ts
│   │   │   ├── useConfirm.ts
│   │   │   ├── useModal.ts
│   │   │   ├── useCommandPalette.ts  # ⌘K
│   │   │   ├── useFindReplace.ts     # ⌘F
│   │   │   ├── useResizableColumns.ts # editor 3-column + localStorage
│   │   │   └── useFocusMode.ts       # focusedSlideId mode-clear logic (F1-F3)
│   │   ├── utils/
│   │   │   ├── slidePalette.ts       # SLIDE_PALETTE + colorForSlide() + Map lookup
│   │   │   ├── format.ts             # timecode, duration, mono-uppercase helpers
│   │   │   └── stages.ts             # SOP_STAGES + AI_STAGES constants
│   │   ├── fixtures/                 # ports data.jsx
│   │   │   ├── speakers.ts
│   │   │   ├── slides.ts
│   │   │   ├── segments.ts
│   │   │   ├── chat.ts
│   │   │   ├── polls.ts
│   │   │   ├── sop_stages.ts
│   │   │   ├── sessions.ts
│   │   │   ├── discrepancies.ts
│   │   │   ├── corrections.ts
│   │   │   └── improvements.ts
│   │   ├── components/
│   │   │   ├── AppHeader.vue         # TopBar (50px navy band) — IMPLEMENTATION.md §3
│   │   │   ├── StatusBar.vue         # sticky bottom 30px (editor only) — toggleable
│   │   │   ├── Icon.vue              # icon dispatcher
│   │   │   ├── StageBadge.vue
│   │   │   ├── Avatar.vue
│   │   │   ├── primitives/
│   │   │   │   ├── Button.vue        # .btn variants
│   │   │   │   ├── Chip.vue
│   │   │   │   ├── Card.vue
│   │   │   │   ├── Pill.vue
│   │   │   │   └── SegmentedControl.vue
│   │   │   ├── overlays/
│   │   │   │   ├── ToastHost.vue
│   │   │   │   ├── ConfirmHost.vue
│   │   │   │   ├── ModalHost.vue
│   │   │   │   ├── CommandPalette.vue
│   │   │   │   ├── FindReplaceModal.vue
│   │   │   │   ├── SuggestImprovementModal.vue
│   │   │   │   └── SegmentEditModal.vue
│   │   │   ├── editor/
│   │   │   │   ├── EditorTopbar.vue        # breadcrumb + mini SOP + title row + flag chips
│   │   │   │   ├── EditorTabs.vue          # AI · STT · Discrepancies · Audit
│   │   │   │   ├── VideoStrip.vue          # 16:9 poster + HUD
│   │   │   │   ├── MiniAudioBar.vue        # 38px transport row
│   │   │   │   ├── SlideRail.vue           # left column slide list + Focus/Filter
│   │   │   │   ├── TranscriptPane.vue      # AI tab body
│   │   │   │   ├── SegmentCard.vue         # inline edit/reassign/speaker
│   │   │   │   ├── AnchorBlock.vue         # poll/chat anchors inline
│   │   │   │   ├── STTPane.vue             # STT Reference tab
│   │   │   │   ├── DiscrepanciesPane.vue   # synced 2-column grid
│   │   │   │   ├── AuditPane.vue           # decisions + ledger
│   │   │   │   ├── RightRail.vue           # Active Slide + tabs (Admin · Chat · Polls)
│   │   │   │   ├── ActiveSlideCard.vue
│   │   │   │   ├── TimelineMinimap.vue     # single SVG, N rects (P17 perf)
│   │   │   │   ├── ColumnResizer.vue
│   │   │   │   └── DownloadMenu.vue
│   │   │   ├── dashboard/
│   │   │   │   ├── KpiStrip.vue
│   │   │   │   ├── Sparkline.vue
│   │   │   │   ├── PipelineRail.vue        # AI + SOP — pipeline circles wire to ?stage/?ai
│   │   │   │   ├── QueueCards.vue
│   │   │   │   ├── SlaGrid.vue
│   │   │   │   ├── HotspotsWidget.vue
│   │   │   │   ├── StorageBreakdown.vue
│   │   │   │   └── AssignmentCoverage.vue
│   │   │   ├── sessions/
│   │   │   │   ├── SessionsTable.vue
│   │   │   │   ├── FilterChips.vue
│   │   │   │   └── ActiveFilterChip.vue    # "SOP: Medical review ×"
│   │   │   ├── session-detail/
│   │   │   │   ├── MetaCard.vue
│   │   │   │   ├── KpiGrid.vue
│   │   │   │   ├── FilesAttention.vue
│   │   │   │   ├── StageAssignments.vue
│   │   │   │   ├── PublishingLinks.vue
│   │   │   │   ├── TimelineCard.vue
│   │   │   │   ├── SegmentConfidence.vue
│   │   │   │   ├── SlideAssignmentList.vue
│   │   │   │   └── ReviewQueue.vue
│   │   │   ├── sop/
│   │   │   │   ├── SopKpiStrip.vue
│   │   │   │   ├── SopStepper.vue
│   │   │   │   ├── StageDetail.vue
│   │   │   │   ├── StageOwnerCard.vue
│   │   │   │   ├── ApprovalsCard.vue
│   │   │   │   ├── QuickActions.vue
│   │   │   │   ├── TransitionHistory.vue
│   │   │   │   └── SopInvariants.vue
│   │   │   ├── settings/
│   │   │   │   ├── SettingsSidebar.vue
│   │   │   │   ├── SettingsHeader.vue
│   │   │   │   ├── General.vue
│   │   │   │   ├── TeamRoles.vue
│   │   │   │   ├── TypesStages.vue          # 8-stage × N-type assignee matrix
│   │   │   │   ├── AiModels.vue
│   │   │   │   ├── UploadStorage.vue
│   │   │   │   ├── DiscrepancyClassification.vue # Gemini/Vertex toggle + model picker
│   │   │   │   ├── Export.vue                # Word macro download
│   │   │   │   ├── PromptTemplates.vue
│   │   │   │   ├── SessionManifest.vue
│   │   │   │   ├── Email.vue                 # 8-stage tabs + body + variables + preview
│   │   │   │   ├── Diagnostics.vue           # Phase 0 + GCS QA drill-ins
│   │   │   │   └── DeletedSessions.vue
│   │   │   ├── improvements/
│   │   │   │   ├── ImprovementsTable.vue
│   │   │   │   ├── WizardOverview.vue
│   │   │   │   ├── WizardRequirements.vue
│   │   │   │   ├── WizardImplementation.vue
│   │   │   │   ├── WizardTesting.vue
│   │   │   │   ├── WizardReview.vue
│   │   │   │   └── AdminControls.vue
│   │   │   ├── upload/
│   │   │   │   ├── UploadHero.vue
│   │   │   │   ├── AttachmentRow.vue
│   │   │   │   └── ProcessButton.vue
│   │   │   ├── viewer/
│   │   │   │   └── ExportDocument.vue
│   │   │   ├── processing/
│   │   │   │   ├── PipelineTrace.vue         # 8-hop
│   │   │   │   └── GcsQa.vue                 # G1-G14
│   │   │   ├── audit/
│   │   │   │   ├── DecisionCard.vue
│   │   │   │   └── AuditLedger.vue
│   │   │   └── TweaksPanel.vue
│   │   └── views/
│   │       ├── DashboardView.vue       # /dashboard
│   │       ├── SessionsView.vue        # /sessions
│   │       ├── SessionDetailView.vue   # /s/:id
│   │       ├── UploadView.vue          # /upload
│   │       ├── EditorView.vue          # /e/:id
│   │       ├── SopView.vue             # /e/:id/sop
│   │       ├── EditorAuditView.vue     # /e/:id/audit
│   │       ├── ViewerView.vue          # /v/:id
│   │       ├── ProcessingView.vue      # /p/:id
│   │       ├── ImprovementsView.vue    # /improvements
│   │       ├── SettingsView.vue        # /settings
│   │       ├── AuditView.vue           # /audit
│   │       └── GcsView.vue             # /gcs
│   └── tests/
│       ├── e2e/                        # Playwright route smoke + interaction
│       │   ├── dashboard.spec.ts
│       │   ├── editor.spec.ts
│       │   ├── sessions-filter.spec.ts
│       │   └── ...
│       └── visual/                     # pixel-diff against baseline/*.png
│           ├── baseline/               # captured from React-via-CDN prototype, checked in
│           ├── visual.config.ts
│           └── all-routes.spec.ts
├── app/                                # FastAPI backend (ports MIC audit §8 code map)
│   ├── __init__.py
│   ├── main.py                         # FastAPI app, lifespan, CORS, sub-routers
│   ├── config.py                       # Pydantic Settings — all 47 vars from audit §6
│   ├── db.py                           # async SQLAlchemy + session factory
│   ├── auth.py                         # JWT, AUTH_USERS CSV, get_current_user
│   ├── deps.py                         # FastAPI dependencies
│   ├── models/                         # ORM
│   │   ├── session.py
│   │   ├── source.py
│   │   ├── segment.py
│   │   ├── slide.py
│   │   ├── speaker.py
│   │   ├── discrepancy.py
│   │   ├── correction.py
│   │   ├── sop_stage.py
│   │   ├── improvement.py
│   │   └── audit_event.py
│   ├── schemas/                        # Pydantic IO
│   │   └── (mirrors models/)
│   ├── api/
│   │   ├── auth.py                     # /v1/auth/login
│   │   ├── sessions.py                 # CRUD + ?stage/?ai filters
│   │   ├── gcs_upload.py               # /upload-url, /upload-complete (audit §8 line refs)
│   │   ├── segments.py
│   │   ├── slides.py
│   │   ├── discrepancies.py
│   │   ├── sop.py                      # stage transitions + approvals + invariants
│   │   ├── audit.py
│   │   ├── improvements.py
│   │   ├── settings.py
│   │   ├── exports.py                  # .docx / .srt / .txt / .zip + Word macro zip
│   │   ├── diagnostics.py              # /v1/diag/* — Phase 0 telemetry, GCS QA G1-G14, test email
│   │   └── ws.py                       # WebSocket bridge (status only in v1)
│   ├── tasks/
│   │   ├── celery_app.py
│   │   ├── ingest.py                   # manifest parser
│   │   ├── transcribe.py               # Cloud STT chunked (audit §8 ref)
│   │   ├── frame_task.py               # frame sampling at FRAME_SAMPLE_FPS
│   │   ├── slide_extract.py
│   │   ├── align.py                    # locked ALIGN_WEIGHT_*
│   │   ├── fuse.py                     # locked FUSION_WEIGHT_*
│   │   ├── iil.py                      # locked IIL_*
│   │   ├── ai_mode.py                  # Gemini multimodal
│   │   ├── classify_discrepancies.py   # Gemini text + Vertex AI route
│   │   └── burn_captions.py            # ffmpeg burn-in
│   ├── engines/
│   │   ├── llm_client.py               # call_gemini_multimodal / call_gemini_text / call_vertex_ai_text / classify_discrepancies dispatcher (audit §3 + §8)
│   │   └── stt_client.py
│   ├── services/
│   │   ├── gcs.py                      # signed URL gen + scope validation (_find_out_of_scope_uri)
│   │   ├── manifest.py                 # extras2_parser equivalent
│   │   ├── sop_engine.py               # stage state machine
│   │   ├── audit_log.py
│   │   └── email.py                    # Resend SMTP (ce.vin pattern) — VIN-branded templates per IMPLEMENTATION.md §11
│   └── middleware/
│       ├── idempotency.py
│       └── rate_limit.py               # MAX_CONCURRENT_SESSIONS / MAX_QUEUE_LENGTH
├── migrations/
│   ├── 001_init.sql                    # schemas, sessions, sources, segments, slides
│   ├── 002_sop.sql
│   ├── 003_audit.sql
│   ├── 004_improvements.sql
│   ├── 005_settings.sql
│   ├── 006_discrepancies.sql
│   └── 007_pgvector.sql                # pgvector extension + embedding cols
├── scripts/
│   ├── migrate.py                      # ports MIC scripts/migrate.py:32-80
│   ├── seed-admin.sql                  # .gitignored — johndean@vin.com as Superadmin
│   ├── seed-admin.sql.example          # checked in, redacted
│   ├── check-secrets.mjs               # po-vin pattern
│   ├── capture-prototype-baselines.mjs # runs prototype + Playwright, writes tests/visual/baseline/*.png
│   └── start.sh                        # entrypoint: base64-decode GCP_KEY_B64 → /etc/gcp/sa.json; exec uvicorn|celery
├── tests/                              # pytest backend
│   ├── conftest.py
│   ├── test_gcs_scope.py               # _find_out_of_scope_uri (R7)
│   ├── test_auth.py
│   ├── test_sessions_api.py
│   ├── test_signed_url.py
│   ├── test_classify_dispatch.py       # Gemini vs Vertex route selection
│   ├── test_sop_transitions.py
│   ├── test_improvements_wizard.py
│   └── test_migrate.py
└── secrets/                            # gitignored
    └── gcp-key.json                    # local dev only
```

---

## 6. High-Level Technical Design

> *Directional guidance for review, not implementation specification.*

**Frontend route → view → component graph (hash-routed):**

```
URL hash         → View                  → Composes
─────────────────────────────────────────────────────────────────────
#/dashboard      → DashboardView         → KpiStrip · QueueCards · PipelineRail × 2 · SlaGrid · 3-widget × 2 rows
#/sessions       → SessionsView          → FilterChips · ActiveFilterChip · SessionsTable
#/s/:id          → SessionDetailView     → MetaCard · KpiGrid · FilesAttention · StageAssignments · PublishingLinks · TimelineCard · 3-widget row
#/upload         → UploadView            → UploadHero · AttachmentRow × N · ProcessButton
#/e/:id          → EditorView            → EditorTopbar · EditorTabs · {leftCol: VideoStrip+MiniAudioBar+SlideRail} | resizer | {center: TranscriptPane | STTPane | DiscrepanciesPane | AuditPane} | resizer | {rightCol: ActiveSlideCard+RightRail tabs}
#/e/:id/sop      → SopView               → breadcrumb + SopKpiStrip · SopStepper · {StageDetail | StageOwnerCard+ApprovalsCard+QuickActions} · TransitionHistory · SopInvariants
#/e/:id/audit    → EditorAuditView       → DecisionCard list | AuditLedger
#/v/:id          → ViewerView            → ExportDocument
#/p/:id          → ProcessingView        → PipelineTrace (8-hop)
#/improvements   → ImprovementsView      → ImprovementsTable | Wizard{Overview..Review}
#/settings/*     → SettingsView          → SettingsSidebar + dispatched section
#/audit          → AuditView             → AuditLedger (standalone)
#/gcs            → GcsView               → GcsQa (G1-G14)
```

**Backend request flow for the load-bearing upload path (R7):**

```
Frontend                  Backend                              GCS
────────────────────────────────────────────────────────────────────────────
POST /v1/gcs/upload-url
  {session_id, filename, role}
                       → app/api/gcs_upload.py
                          validate session_id + role
                          _blob_name_for_role(s, r, f)
                          client.bucket.blob.generate_signed_url(PUT, 60min)
                       ← {signed_url, gcs_uri, blob_name}

PUT <signed_url>                                            → object stored at
  binary body                                                  gs://<bucket>/sessions/<id>/[slides|manifest|]/<f>

POST /v1/gcs/upload-complete
  {session_id, files: [{gcs_uri, role, ...}]}
                       → _find_out_of_scope_uri(files, expected_prefix=gs://<bucket>/sessions/<id>/)
                          ─ any uri outside prefix → 400 VALIDATION_FAILED  (R7 invariant)
                          ─ all in scope → create Source rows, parse manifest, enqueue ingest
                       ← {sources: [...], jobs: [...]}
```

**SLIDE_PALETTE mapping (IMPLEMENTATION.md §4):**

```
SLIDE_PALETTE = [
  '#2563eb', '#7c3aed', '#059669', '#d97706', '#dc2626',
  '#0891b2', '#6366f1', '#ea580c', '#0d9488', '#be185d'
]
colorForSlide(i) = SLIDE_PALETTE[i % 10]    // O(1) Map lookup precomputed at module load
```

Applied (per IMPLEMENTATION.md §4) to: slide rail row tints · segment 3px left stripe · slide-chip dots · AI/STT/Discrepancies/Audit segment chrome · minimap rects · ActiveSlide card border + gradient · Session Detail timeline strip + slide-assignment list + per-segment confidence dots.

---

## 7. Implementation Phases & Units

### Phase 1 — Repo bootstrap (Days 1-2)

- **U1. Greenfield repo init.** Create `C:\Users\JohnDean\rounds`. `git init`. Add `origin` (vin-swe/rounds), `production` (johndean/rounds — create empty GitHub repo first). Write `.gitignore` (covers `secrets/`, `.env`, `frontend/dist`, `__pycache__`, `node_modules`, `.venv`). Write `README.md` stub + this plan into `docs/plans/2026-05-17-001-feat-rounds-bootstrap-plan.md` (copy of this file for repo-local discoverability).
- **U2. Pyproject + Dockerfile + docker-compose.** Port MIC's `pyproject.toml`, `Dockerfile`, `docker-compose.yml` (4-service: db pgvector + redis + api + worker). Strip Vault dep (`hvac`) — audit §5 + §10 finding #2.
- **U3. Frontend scaffold.** `npm create vite@latest frontend -- --template vue-ts`. Install pinia, vue-router, lucide-vue-next, @playwright/test. Copy the 4 prototype CSS files into `frontend/src/styles/` verbatim. Wire `main.ts` to import them globally.
- **U4. CI workflow.** `.github/workflows/quality.yml`: gitleaks direct-binary install (memory pattern) + pytest + Playwright (e2e + visual). Block deploy on red.
- **U5. railway.json.** Pre-deploy command `python scripts/migrate.py`. Healthcheck `GET /v1/health`. Two services declared: api (uvicorn) + worker (celery). Postgres + Redis plugins linked.

**Verify Phase 1:** `docker-compose up db redis` succeeds. `cd frontend && npm run dev` serves on `localhost:5173`. CI workflow runs green on an empty PR.

### Phase 2 — Frontend foundation (Days 3-7)

- **U6. Design tokens + base styles.** `colors_and_type.css`, `app.css`, `wiring.css`, `settings.css` referenced from `App.vue`. Verify token variables resolve in dev tools (`--color-navy: #002855`, etc.).
- **U7. Router.** 13 hash routes per IMPLEMENTATION.md §5 wired to placeholder views. Verify each URL renders its view name.
- **U8. AppHeader (TopBar).** 50px navy band. Brand · build pill · 5 nav links · ⌘K · A−/A+ · status pill · avatar · Logout. All wired (search → palette, font controls → store, Logout → confirm → toast). IMPLEMENTATION.md §3.
- **U9. Wiring infrastructure.** `useToast`, `useConfirm`, `useModal`, `useCommandPalette`, `useFindReplace` composables. Each backed by one mounted host in `App.vue` (TeleportTarget). `wired.ts` namespace with all named actions from IMPLEMENTATION.md §12.
- **U10. Mock API + fixtures.** Port `data.jsx` to `frontend/src/fixtures/*.ts`. Port `api.*` stubs to `frontend/src/services/api.ts`. Pinia stores hydrate from fixtures when `VITE_API_MODE=mock`.
- **U11. Primitives.** Button (variants), Chip, Card, Pill, SegmentedControl, Avatar, Icon dispatcher, StageBadge. Used everywhere downstream.
- **U12. Slide-accent utilities.** `slidePalette.ts` (palette + `colorForSlide` + Map). Verify Storybook-style preview page or inline test.

**Verify Phase 2:** Every route loads without console errors. TopBar interactions all toast/confirm. `colorForSlide(0..15)` returns documented colors.

### Phase 3 — Frontend non-editor routes (Days 8-14)

- **U13. Dashboard (F pattern).** All zones from IMPLEMENTATION.md §9: KPI strip with sparklines · queue cards · 2 pipeline rails (5 AI + 8 SOP states) with circle-buttons that navigate to `/sessions?ai=...` / `/sessions?stage=...` · system overview tabs · SLA grid · 3-widget × 2 rows.
- **U14. Sessions list (B pattern).** Filter chips · `?stage` / `?ai` / `?f` query param parsing → ActiveFilterChip with × clear · grid table with fixed pixel cols.
- **U15. Session Detail (mixed).** 3-column grid · Files attention card · Stage Assignments · Publishing Links · Timeline card with SVG accent rectangles · 3-widget row.
- **U16. Upload (A pattern).** UploadHero (centered 680-900px intent block) · AttachmentRow with × remove · ProcessButton → confirm → toast.
- **U17. SOP workflow.** KPIs · 8-stage stepper · stage detail with prev/next · check rows with by-actor footnote · stage owner card · approvals card · transition history · invariants card.
- **U18. Improvements (master/detail, C pattern).** Status tabs · master table · 5-step wizard (Overview / Requirements / Implementation / Testing / Review) · Suggest Improvement modal.
- **U19. Settings (E pattern).** Sidebar + 12 sections + drill-ins (Email Builder, Diagnostics, Prompt Templates). VIN-branded email templates per IMPLEMENTATION.md §11.
- **U20. Viewer + Processing + GCS QA + standalone Audit + Tweaks.** Smaller surfaces; one unit each is fine because they share patterns from prior units.

**Verify Phase 3:** Manual walkthrough of every non-editor route. Pipeline circles on Dashboard navigate to filtered Sessions and show the active-filter chip.

### Phase 4 — Frontend editor (Days 15-22)

This is the heaviest surface — single-unit-per-tab split.

- **U21. Editor shell + 3-column resizable layout.** `useResizableColumns` composable, localStorage persistence (`mic_left_w` / `mic_right_w` keys → rename `rounds_left_w` / `rounds_right_w`).
- **U22. EditorTopbar.** Breadcrumb · mini SOP stepper · big title row (Result / Undo / Redo / Preview) · sub-row (alignment chip · F&R · current stage · Workflow · Audit · Download dropdown) · FLAGGED chip row with counts.
- **U23. Left column.** VideoStrip · MiniAudioBar · SlideRail (Focus/Filter segmented control · Clear focus button F1 · 3-branch nav style).
- **U24. AI Transcript tab.** Segment cards with slide-chip header · inline Edit (textarea + Tiptap-style toolbar with `onMouseDown preventDefault` for selection preservation) · inline Reassign (slide tile grid) · inline Speaker (card grid) · inline anchor blocks (poll/chat).
- **U25. STT Reference tab.** Same shell · accent stripes · mono lowercase text · token-time superscripts · drift wavy underlines · filler chips · read-only banner.
- **U26. Discrepancies tab.** Synced 2-column grid via CSS grid · All/Flagged/Meaningful filter pills · focus-mode banner · STT side hides header via `visibility: hidden` to preserve row height.
- **U27. Audit tab.** Decisions/Ledger toggle · per-correction cards · WAS/NOW panels (red strike + green highlight) · flat correction-lineage table.
- **U28. Right rail.** ActiveSlideCard (4px accent border, accent gradient) · tab dispatch (Admin · Chat · Polls) · TimelineMinimap (single SVG, P17 perf) · Instructor/IIL signals card · draggable chat/poll placement.
- **U29. Mode-switch focus-clear (F2).** When tab changes, clear `focusedSlideId`. Wire across all 4 editor tabs via a single watcher on the editor store.
- **U30. Editor StatusBar + keyboard shortcuts.** ⌘K opens palette, ⌘F opens Find&Replace, sticky 30px navy at bottom (toggleable via Tweaks).

**Verify Phase 4:** Every editor tab renders with the documented chrome. Inline edit/reassign/speaker all save into the editor store. Resizers persist widths across reload. Focus mode clears on tab switch.

### Phase 5 — Backend foundation (Days 23-28)

- **U31. FastAPI scaffold.** `app/main.py` with lifespan, CORS for `rounds.vin`, sub-router registration. `/v1/health` returns ok.
- **U32. Pydantic Settings.** Port `app/config.py` from MIC audit §6 verbatim. All 47 vars typed with defaults. Locked weights (FUSION_*, ALIGN_*, IIL_*, CELERY_*) match audit values. Drop `VERTEX_AI_GEMINI_API_KEY` (vestigial per §3.3) and Vault fields (audit §5 + §10).
- **U33. DB session + migrations.** Async SQLAlchemy + asyncpg. `scripts/migrate.py` ports MIC `scripts/migrate.py:32-80` — globs `migrations/[0-9][0-9][0-9]_*.sql`, applies in order, converts `postgresql+asyncpg://` → `postgresql://` for psycopg2.
- **U34. Auth.** `app/auth.py` — JWT via `python-jose` with `API_SECRET_KEY` + `ALGORITHM=HS256` + `ACCESS_TOKEN_EXPIRE_MINUTES=480`. `AUTH_USERS` CSV parsed at startup; passwords bcrypt-verified. `/v1/auth/login` returns Bearer token. `get_current_user` dependency.
- **U35. Migrations 001-007.** SQL files for sessions / sources / segments / slides / speakers / discrepancies / corrections / sop_stages / improvements / audit_events / pgvector. Idempotent CREATE statements.
- **U36. Seed admin.** `scripts/seed-admin.sql.example` checked in. `scripts/seed-admin.sql` gitignored, inserts `johndean@vin.com` as Superadmin (memory `reference_po_vin_admin.md` pattern).

**Verify Phase 5:** `python scripts/migrate.py` runs clean against a fresh Postgres. Login with seeded admin returns a JWT. `/v1/health` returns 200.

### Phase 6 — Backend ingest & AI pipelines (Days 29-38)

Each task ports the named MIC file from audit §8.

- **U37. GCS signed URL + upload-complete.** `app/api/gcs_upload.py` — `/upload-url` (60min v4 PUT signed) + `/upload-complete` with `_find_out_of_scope_uri` invariant (R7). Test: `tests/test_gcs_scope.py` verifies cross-session URI rejected with 400.
- **U38. Manifest parser.** `app/services/manifest.py` — port `extras2_parser` logic; called from `_parse_manifest_from_gcs` (audit §8).
- **U39. Celery + Redis bootstrap.** `app/tasks/celery_app.py` with retry policy (LOCKED CELERY_MAX_RETRIES=3, CELERY_RETRY_BACKOFF_BASE=60, jitter).
- **U40. Transcribe task.** `app/tasks/transcribe.py` — Cloud STT chunked (TRANSCRIPTION_BACKEND=`google_stt_chunked`, TRANSCRIPTION_CHUNK_MINUTES=5). Split + parallel + merge per audit §8.
- **U41. Frame + slide extract.** `frame_task.py` (FRAME_SAMPLE_FPS=2, VISUAL_CHANGE_THRESHOLD=8.0) + `slide_extract.py`.
- **U42. Align + fuse + IIL.** Locked weights from audit §6. No tuning unless user explicitly approves.
- **U43. AI MODE.** `app/engines/llm_client.py` — `call_gemini_multimodal` (gemini-2.5-flash default) + `call_gemini_text` (gemini-2.5-pro) + `call_vertex_ai_text` (when VERTEX_AI_CLASSIFY_ENABLED=true). Bare `except: pass` cleanups replaced with logged exceptions (audit §10 finding #6).
- **U44. Classification dispatcher.** `classify_discrepancies()` routes to Gemini or Vertex based on settings + frontend toggle. Batches per audit §8. Test: `tests/test_classify_dispatch.py` verifies both routes hit the right client.
- **U45. WS bridge.** Status-only in v1 (frontend status bar wires later). Pub via Redis pub/sub.

**Verify Phase 6:** Upload a fixture lecture via `/v1/gcs/upload-url` + PUT + `/upload-complete`. Celery worker picks up ingest task, runs transcribe (mock STT response in tests, real STT in staging), produces segments. AI MODE returns Gemini-classified discrepancies.

### Phase 7 — Backend domain APIs (Days 39-44)

- **U46. Sessions API.** CRUD + list with `?stage` / `?ai` / `?f` filters (matches frontend U14).
- **U47. Segments / Slides / Discrepancies / Speakers APIs.** Read + edit + reassign endpoints to back the editor's inline actions.
- **U48. SOP API.** Stage state machine + transitions + approvals + invariants. 8 stages: prep / copy_draft / medical / copy_final / cms / captions / qa / complete (matches IMPLEMENTATION.md §9 Pipeline 2 + §8). Tests: `test_sop_transitions.py` covers illegal transitions reject.
- **U49. Audit API + ledger persistence.** All UI actions write append-only audit events. Decisions endpoint returns grouped corrections.
- **U50. Improvements API.** Master/detail + 5-step wizard endpoints. Status transitions enforce workflow.
- **U51. Settings API.** 12 sections. Includes Discrepancy classification toggle (Gemini Dev / Vertex AI) + region selector + Word macro download endpoint.
- **U52. Exports API.** `.docx` / `.srt` / `.txt` / `.zip` / Word macro. Use python-docx + srt + zipfile.
- **U53. Diagnostics API.** GCS QA G1-G14 + Phase 0 telemetry endpoints + test email endpoint with Resend SMTP.

**Verify Phase 7:** Hit each endpoint with `httpx` smoke tests. SOP transitions persist and reject illegal moves. Audit events accumulate.

### Phase 8 — Frontend↔Backend wiring (Days 45-49)

- **U54. Real-mode API client.** `frontend/src/services/api.ts` switches on `VITE_API_MODE=live` to use `axios` + JWT injection via `http.ts`. Endpoint shapes match the mock.
- **U55. Auth flow.** Login screen (out of IMPLEMENTATION.md scope — minimal screen with Instrument Serif aesthetic per memory `feedback_cevin_internal_design.md`; internal pages stay MIC-aesthetic). Login → store JWT → enter dashboard.
- **U56. Editor wiring.** Inline edits → PATCH segments/{id}. Reassign → POST segments/{id}/reassign. Anchor block edits → POST polls/chat endpoints. Audit events fire on every action.
- **U57. SOP wiring.** Stage advance / resolve check / reassign owner → backend transitions.
- **U58. Improvements wizard wiring.** Save → POST improvements/{id}/wizard/{step}. Status update → PATCH.
- **U59. Settings wiring.** All 12 sections persist via `settings` API. Stage assignee matrix (8×N) saves atomically.
- **U60. Discrepancy classification toggle.** UI store `classifyBackend` + `classifyModel` → header `X-Classify-Backend` on POST classify endpoint. Backend routes per U44.

**Verify Phase 8:** End-to-end: upload a fixture lecture from the UI → see ingest progress → editor opens with real segments → edit a segment → audit event appears in ledger.

### Phase 9 — Infrastructure provisioning (Days 50-52)

Manual operator checklist (per MIC audit §9):

- **U61. GCP project setup.** Create `rounds-prod-*` project. Enable Cloud Storage, Speech-to-Text, Vertex AI APIs. Enable billing. Create bucket (`rounds-prod-sessions`, uniform access, public access prevention enforced, us-central1). Create service account `rounds-app@…iam.gserviceaccount.com` with 3 roles: `storage.objectAdmin` (scoped to bucket), `speech.client`, `aiplatform.user`. Download JSON key → `secrets/gcp-key.json`. Audit §10 finding #8 — scope `storage.objectAdmin` to bucket-level, not project.
- **U62. Google AI Studio key.** Visit aistudio.google.com → Get API key → save as `GEMINI_API_KEY` in Railway.
- **U63. GitHub repos.** `gh repo create vin-swe/rounds --private` and `gh repo create johndean/rounds --public` (or whichever visibility matches po-vin/ce.vin pattern). Push to both. Railway watches `johndean/rounds`.
- **U64. Railway project.** Create project `Rounds`. Add Postgres plugin (capital P naming per ce.vin memory if applicable). Add Redis plugin. Create api service (deploy from johndean/rounds main, start cmd `bash scripts/start.sh`). Create worker service (same repo, start cmd `celery -A app.tasks.celery_app.celery_app worker --loglevel=info --concurrency=2 --queues=celery`). Set pre-deploy command `python scripts/migrate.py` on api.
- **U65. Railway env vars.** Set all required vars from audit §6 table. Inject `GCP_KEY_B64` (base64 of `secrets/gcp-key.json`) — `scripts/start.sh` decodes to `/etc/gcp/sa.json`. Generate `API_SECRET_KEY` with `python -c "import secrets; print(secrets.token_hex(32))"`. Hand-author `AUTH_USERS`. Wire `DATABASE_URL` + `REDIS_URL` via Railway references `${{Postgres.DATABASE_URL}}` / `${{Redis.REDIS_URL}}`.
- **U66. DNS.** Point `rounds.vin` to Railway custom domain. Configure SSL.
- **U67. Smoke test.** Hit production `/v1/health` + `/v1/auth/login` with seeded admin + load `https://rounds.vin/#/dashboard` in a browser. Confirm no console errors, TopBar renders, fixtures load (since DB is empty).

**Verify Phase 9:** Production URL reachable. Admin can log in. CI auto-deploys on push to main.

### Phase 10 — Pixel parity verification (Days 53-56)

This is where the "zero gaps" promise gets enforced.

- **U68. Baseline capture.** Stand up the original React-via-CDN prototype locally (one-off — clone/extract the design bundle). Write `scripts/capture-prototype-baselines.mjs` that uses Playwright to navigate every route + every documented state (focus on/off, theme light/dark, filter combinations from IMPLEMENTATION.md §16/§17) and writes `tests/visual/baseline/*.png`. Commit baselines.
- **U69. Visual diff test suite.** `tests/visual/all-routes.spec.ts` — for each route+state in the baseline manifest, render Rounds Vue port at the same viewport + seed and assert `toMatchSnapshot` with per-route tolerance config (1-2px slack for font hinting where needed).
- **U70. Gap remediation.** Run the suite. Every failing diff is a documented gap. Triage each: (a) genuine port bug → fix the Vue component; (b) acceptable rendering difference (e.g., font subpixel) → adjust tolerance with a justification comment; (c) framework rendering difference (e.g., Vue scoped styles producing different specificity) → fix via CSS. Loop until all routes pass.
- **U71. Functional parity audit.** Walk IMPLEMENTATION.md §17 "78 functional buttons wired" checklist. For each, confirm Vue port fires equivalent toast/confirm/modal/audit. Track in `tests/e2e/buttons.spec.ts`.
- **U72. Closures F1-F3 + slide-accent rollout audit.** Walk IMPLEMENTATION.md §15-16. Confirm each closure (focus-clear button, mode-switch focus reset, minimap in both Active Slide and Admin tab) and each P1-P18 slide-accent gap is closed in the Vue port.

**Verify Phase 10:** `npm run test:visual` passes green. Zero gaps documented against IMPLEMENTATION.md §17 / §15 / §16. CI runs the diff suite on every PR.

---

## 8. Existing patterns & code references to reuse

- **Two-remote git** — memory `project_po_vin_remotes.md` (origin=vin-swe, production=johndean) — apply to Rounds.
- **Railway target setup** — memory `reference_po_vin_railway.md` — model Rounds Railway project after po-vin's.
- **Seed admin** — memory `reference_po_vin_admin.md` — johndean@vin.com Superadmin, SQL gitignored, `.example` checked in.
- **Gitleaks workflow** — memory `reference_gitleaks_repo_setup.md` — direct binary in `quality.yml`, allowlist in `.gitleaks.toml`.
- **Migration runner** — port from `C:\Users\JohnDean\Desktop\mic\scripts\migrate.py` (the MIC repo); proven Railway pattern.
- **GCS signed URL + scope validation** — port from `mic/app/api/gcs_upload.py` (audit §8 line refs verbatim).
- **Cloud STT chunked transcription** — port from `mic/app/tasks/transcribe.py`.
- **Gemini + Vertex AI clients** — port from `mic/app/engines/llm_client.py`.
- **Internal-page aesthetic** — memory `feedback_cevin_internal_design.md`: dark topbar + sans-serif. IMPLEMENTATION.md TopBar uses navy + ProximaNova — already aligned.
- **Don't optimize for token cost in dev/pre-scale** — memory `feedback_cost_consciousness.md`: choose simplest/most reliable Gemini retry, not cheapest, until rounds.vin has paying customers.
- **Multi-audio enhance poisoning STT** — memory `feedback_multi_audio_stt_pollution.md`: sanity-check enhance audio size before upload (tiny mp3 can preempt primary). Add validator in `app/api/gcs_upload.py` `/upload-complete`.

---

## 9. System-Wide Impact

- **External contracts (R7 invariant):** The signed-URL scope check is load-bearing. Any frontend code that synthesizes a `gcs_uri` must use the URI returned by `/upload-url`; never construct on the client. Backend rejects with 400 otherwise.
- **Locked weights (R6):** Frontend Settings → Discrepancy classification UI must NOT expose FUSION_* / ALIGN_* / IIL_* / CELERY_* knobs. Pydantic Settings defaults are the single source of truth.
- **Slide-accent palette:** A `colorForSlide(i)` change cascades to 8+ surfaces (IMPLEMENTATION.md §4). The Map lookup must stay O(1).
- **SOP state machine:** Stage transitions are append-only and enforce ordering. Frontend U17 and backend U48 must agree on the 8-stage list and acceptance checks.
- **Auth blast radius:** `API_SECRET_KEY` rotation invalidates all JWTs; document in README.md as a known operational behavior.
- **GCS bucket layout:** `sessions/<id>/[video|slides/|manifest/|uploads/]` is the only valid layout (audit §2.4). Any new role added later must update `_blob_name_for_role` and `_find_out_of_scope_uri` together.

---

## 10. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Pixel diff fails on Vue scoped-style specificity differences | High | Medium | Use unscoped `<style>` or `:deep()` for surfaces that need to match exactly; verify per-component during Phase 4. |
| Babel-in-browser baseline rendering is non-deterministic (font hint, JIT) | Medium | Medium | Capture baselines on the same OS/browser/font config as CI. Use Playwright Docker image with pinned Chrome. Tolerance per route documented in `visual.config.ts`. |
| Locked weights drift from MIC values during port | Low | High | `tests/test_settings_defaults.py` asserts each LOCKED weight matches the audit table verbatim. CI fails on drift. |
| GCS service account JSON leaks into git | Medium | Critical | `secrets/` in `.gitignore` from U1. `gitleaks` in CI from U4. `scripts/check-secrets.mjs` runs pre-commit (po-vin pattern). Rotate immediately if leaked (audit §9.4). |
| AUTH_USERS plaintext passwords (audit §10 finding #7) | High | High | Acknowledged debt — same posture as MIC. Document in README.md as v1 limitation. Schedule "Recovery v16" follow-up plan to migrate to hashed-at-rest + invitation flow. Outside this plan's scope. |
| Vertex AI fallback path latent until quota actually hits | Medium | Low | Add a `/v1/diag/classify-route-test` endpoint (U53 diagnostics) that exercises both routes with a fixture. Run nightly. |
| Frontend baseline drifts when prototype is updated | Medium | Low | Pin the prototype version that baselines were captured against. Re-capture is a deliberate decision documented in a follow-up plan. |
| Pre-deploy migration on Railway fails silently | Low | High | `scripts/migrate.py` exits non-zero on any SQL failure. Audit §4.5 — Railway aborts deploy. Smoke test `/v1/health` in U67 verifies post-deploy. |
| GCP `storage.objectAdmin` project-wide is too broad (audit §10 finding #8) | Low | Medium | U61 scopes to bucket-level IAM binding from the start. |
| `MAX_VIDEO_DURATION_MINUTES=180` allows runaway STT cost | Medium | Medium | Default carried from MIC. Document tuning knob in README.md. Add cost-monitoring TODO in CLAUDE.md. |

---

## 11. Verification (end-to-end)

Each phase has its own verify step (§7). The overall ship gate:

1. **`docker-compose up`** locally — all 4 services healthy.
2. **`python scripts/migrate.py`** — applies all migrations against empty Postgres without error.
3. **Login** as `johndean@vin.com` via `POST /v1/auth/login` → receives JWT.
4. **`cd frontend && npm run dev`** → `http://localhost:5173/#/dashboard` loads.
5. **Upload** a fixture lecture via the Upload route → confirm session lands in GCS bucket (verify in GCS Console) → confirm ingest task fires → editor opens with real segments.
6. **Inline edit** a segment in the editor → confirm `PATCH /v1/segments/{id}` → confirm audit event appears in the Audit tab.
7. **SOP advance** through 8 stages → confirm transitions persist → confirm illegal transition rejected with 400.
8. **Suggest Improvement** modal → submit → confirm row appears in `/improvements` master table.
9. **Settings → Discrepancy classification → Vertex AI** → re-run classification → confirm Vertex AI route hit (verify via GCP Vertex AI logs).
10. **`npm run test:visual`** — pixel diff suite passes for every route + state in `tests/visual/baseline/`.
11. **`npm run test:e2e`** — button-parity suite covers all 78 wired buttons from IMPLEMENTATION.md §17.
12. **`pytest`** — backend test suite green, including `test_gcs_scope.py` (R7), `test_classify_dispatch.py`, `test_sop_transitions.py`, `test_migrate.py`.
13. **Push to `production` remote** → Railway auto-deploys → pre-deploy `migrate.py` runs → swap → `/v1/health` returns 200 on production URL.
14. **Hit `https://rounds.vin/#/dashboard`** → confirm production UI matches the dev UI byte-for-byte.

When all 14 verify steps pass, the plan is complete.

---

## 12. Open Questions (deferred to implementation)

- Exact line counts for Vue SFC ports (Vue templates are ~25% more verbose than JSX; sizing estimates assume this).
- Whether to use `<style scoped>` or `<style>` per-component for pixel-match (decide per component in Phase 4).
- Final Playwright tolerance per route (calibrate in Phase 10 against captured baselines — not knowable up-front).
- Whether Settings → "Default model select" should expose all 8 Gemini variants or filter to currently-available models (audit notes `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-2.5-flash-lite` are the only ones actually used — others are UI candy). Defer to U51 implementation.
- Sentry / observability wiring — audit §12 notes none currently wired. Out of scope for v1; reserved as future-scope.

---

## 13. Sources & References

- **Frontend spec:** `IMPLEMENTATION.md` (Transcript Software v4 zero-gap reference, v4.0.0-ssot-r2) — provided inline in conversation.
- **Backend audit:** `GCS / Railway / AI services — Exacting duplication reference` (2026-05-17) — provided inline in conversation.
- **MIC source (reference port target):** `C:\Users\JohnDean\Desktop\mic\` — copy file structure + line refs from `app/`, `migrations/`, `scripts/migrate.py`, `Dockerfile`, `docker-compose.yml`, `pyproject.toml`.
- **po-vin (reference for VIN frontend convention):** `C:\Users\JohnDean\po-vin\` — copy `package.json` dep choices, `railway.json` shape, `scripts/seed-admin.sql` pattern.
- **Memory files:** `MEMORY.md` index in `C:\Users\JohnDean\.claude\projects\C--Users-JohnDean\memory\` — especially `project_po_vin_remotes.md`, `reference_po_vin_railway.md`, `reference_po_vin_admin.md`, `reference_gitleaks_repo_setup.md`, `feedback_cevin_internal_design.md`, `feedback_cost_consciousness.md`, `feedback_multi_audio_stt_pollution.md`, `feedback_railway_removed_status.md`.
