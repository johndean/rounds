# Audit / Word Track Changes Screen

Route: `#/audit` — registered in [frontend/src/router/index.ts:41](../../frontend/src/router/index.ts#L41) as the `audit` route (no `props`). Implemented by [frontend/src/views/AuditView.vue](../../frontend/src/views/AuditView.vue). The same view file is reused per-session at `#/e/:id/audit` via the `EditorAuditView` wrapper ([router/index.ts:36](../../frontend/src/router/index.ts#L36)); this doc focuses on `#/audit` (global mode) but documents both modes since one file drives both.

## Purpose

A read-only, append-only activity ledger. The view runs in two modes selected by whether an `id` prop is present ([frontend/src/views/AuditView.vue:46](../../frontend/src/views/AuditView.vue#L46)):
- **Global mode** (`#/audit`, no `id`): "System Audit Log" — reads `audit_events` and shows system-wide activity (SOP deadline warnings, settings changes, improvement events, alignment gates, etc.).
- **Per-session mode** (`#/e/:id/audit`, `id` present): "Word Track Changes" — reads the session's `correction_ledger` and shows user-edit history.

Both feeds render through the shared `AuditLedger` component by adapting `audit_events` rows into the `Correction` shape ([frontend/src/views/AuditView.vue:70-79](../../frontend/src/views/AuditView.vue#L70)).

## User Types

Any authenticated user. No role gate on this route (not `adminOnly`, no `LEGACY_ADMIN_EMAIL` check). Auth presence enforced by the global router guard ([frontend/src/router/index.ts:59-62](../../frontend/src/router/index.ts#L59)). NOT VERIFIED IN CODE: any restriction limiting the system audit log to admins.

## Entry Points

- Direct hash navigation to `#/audit` (global). NOT VERIFIED IN CODE: the nav-bar link into `#/audit` is not declared in this view.
- Per-session mode is reached via `#/e/:id/audit` (the `EditorAuditView` wrapper).
- The breadcrumb links to `/sessions` and, in per-session mode, to `/e/{session.id}` ([frontend/src/views/AuditView.vue:142-149](../../frontend/src/views/AuditView.vue#L142)).

## Navigation Paths

- **Breadcrumb → Sessions** — `RouterLink to="/sessions"` ([frontend/src/views/AuditView.vue:143](../../frontend/src/views/AuditView.vue#L143)).
- **Breadcrumb → Editor** (per-session mode only, when `session` is loaded) — `RouterLink :to="`/e/${session.id}`"` ([frontend/src/views/AuditView.vue:145](../../frontend/src/views/AuditView.vue#L145)).
- The ledger's "Segment" cell is styled clickable (`cursor: pointer`) but has **no click handler** in `AuditLedger` — it does not navigate ([frontend/src/components/audit/AuditLedger.vue:72](../../frontend/src/components/audit/AuditLedger.vue#L72)). IMPLEMENTATION NOT FOUND: "jump to the segment in the editor" described in the page copy ([AuditView.vue:159](../../frontend/src/views/AuditView.vue#L159)) is not wired.

## Components

- `<main class="page" data-screen-label="Audit / Word Track Changes">` root ([frontend/src/views/AuditView.vue:141](../../frontend/src/views/AuditView.vue#L141)).
- `Icon` shared component ([frontend/src/components/shared/Icon.vue](../../frontend/src/components/shared/Icon.vue)) — `download`, `check`.
- **Eyebrow / breadcrumb** `.page-eyebrow` ([frontend/src/views/AuditView.vue:142-149](../../frontend/src/views/AuditView.vue#L142)).
- **Title + description** — switches text by mode ("System Audit Log" vs "Word Track Changes") ([frontend/src/views/AuditView.vue:150-160](../../frontend/src/views/AuditView.vue#L150)).
- **KPI row** `.kpi-row` — mode-dependent. Global: Total Events, Distinct Kinds, SOP Deadline Warnings (counts `stats['sop.deadline_warning']`), Distinct Actors. Per-session: Total Corrections, Text Edits (dirty), Non-dirty Corrections, Distinct Actors ([frontend/src/views/AuditView.vue:161-197](../../frontend/src/views/AuditView.vue#L161)).
- **Toolbar** `.toolbar` — a filter-chip row (mode-dependent chip set) and an "Export JSONL" button (`data-test-id="audit-wtc-export-jsonl"`) ([frontend/src/views/AuditView.vue:199-215](../../frontend/src/views/AuditView.vue#L199)).
- **`AuditLedger`** child ([frontend/src/components/audit/AuditLedger.vue](../../frontend/src/components/audit/AuditLedger.vue)) — a 6-column table (Time UTC / Type / Segment / Actor / Delta / Note). Rows are reversed (newest first) and client-filtered by `filter` ([AuditLedger.vue:41-44](../../frontend/src/components/audit/AuditLedger.vue#L41)). Each type maps to a chip color + note via `correctionTypeLabel` ([AuditLedger.vue:26-39](../../frontend/src/components/audit/AuditLedger.vue#L26)).
- **L1 invariant card** (per-session mode only) — a static explainer that only `text_edit` flips `has_user_override`, with a grid of all 12 correction types tagged "→ flips" / "preserves" ([frontend/src/views/AuditView.vue:223-248](../../frontend/src/views/AuditView.vue#L223)). The "11/11 types pass" chip and per-type tags are **static literals**, not test results.

## Actions

- **Filter by type/kind** — clicking a chip sets `filter`; `AuditLedger` filters its rows ([frontend/src/views/AuditView.vue:204-210](../../frontend/src/views/AuditView.vue#L204)). Per-session chips are a fixed correction-type list; global chips are derived from the kinds actually present in the data ([frontend/src/views/AuditView.vue:98-118](../../frontend/src/views/AuditView.vue#L98)).
- **Export JSONL** — `exportJsonl()` serializes the current `corrections` array to NDJSON and triggers a client-side Blob download (`audit-events.jsonl` global / `audit.jsonl` per-session), then toasts success ([frontend/src/views/AuditView.vue:125-137](../../frontend/src/views/AuditView.vue#L125)). Real, fully client-side; no API.

No create/edit/delete actions — the ledger is read-only by design ("append-only — no destructive edits at rest", [AuditView.vue:157-158](../../frontend/src/views/AuditView.vue#L157)).

## States

- **Loading** — `loading` true shows "Loading audit log…" in place of the ledger ([frontend/src/views/AuditView.vue:217](../../frontend/src/views/AuditView.vue#L217)).
- **Loaded with rows** — `AuditLedger` renders ([frontend/src/views/AuditView.vue:221](../../frontend/src/views/AuditView.vue#L221)).
- **Mode** — `globalMode` computed from `!props.id` drives all the title/copy/KPI/chip branching ([frontend/src/views/AuditView.vue:46](../../frontend/src/views/AuditView.vue#L46)).
- **Filtered subset** — when a chip other than "all" is active and no rows match, the ledger simply renders its header row with no body rows (AuditLedger's `rows` computed returns an empty filtered list; there is no per-filter empty message inside the ledger) ([AuditLedger.vue:41-44](../../frontend/src/components/audit/AuditLedger.vue#L41)).

## Empty States

- **No rows** — when `corrections.length === 0` (and not loading), a centered message renders instead of the ledger ([frontend/src/views/AuditView.vue:218-220](../../frontend/src/views/AuditView.vue#L218)): global → "No audit events yet — system activity accumulates here as users + workers run."; per-session → "No corrections yet — audit events accumulate as you edit segments."

## Error States

IMPLEMENTATION NOT FOUND — there is no error branch. Both fetches in `load()` are wrapped in `.catch(() => [])` / `.catch(() => null)`, so a failed request degrades silently to the empty state above; no toast or error banner is shown ([frontend/src/views/AuditView.vue:57-66](../../frontend/src/views/AuditView.vue#L57)).

## Loading States

Single `loading` boolean (init true, cleared in `load()`'s `finally`), gating only the ledger region; the header, KPIs, and toolbar render immediately ([frontend/src/views/AuditView.vue:50](../../frontend/src/views/AuditView.vue#L50), [52-85](../../frontend/src/views/AuditView.vue#L52)). No skeleton; just the centered "Loading audit log…" text.

## Permissions

JWT presence only via the global router guard ([frontend/src/router/index.ts:53-67](../../frontend/src/router/index.ts#L53)). This route is **not** `adminOnly` and has no `LEGACY_ADMIN_EMAIL` gate, even though the global system audit log is system-wide. Role-based authorization is scaffold-only and not wired into this screen. NOT VERIFIED IN CODE: server-side authorization on `GET /v1/audit`.

## Connected APIs

Selected by mode in `load()` ([frontend/src/views/AuditView.vue:52-84](../../frontend/src/views/AuditView.vue#L52)):

- **Per-session mode** (`props.id` present):
  - `GET /v1/sessions/{id}` via `sessionsApi.get` ([frontend/src/services/api.ts:139-140](../../frontend/src/services/api.ts#L139); called at [AuditView.vue:58](../../frontend/src/views/AuditView.vue#L58)).
  - `GET /v1/audit/sessions/{id}/corrections` via `auditApi.corrections(id)` ([frontend/src/services/api.ts:944-945](../../frontend/src/services/api.ts#L944); called at [AuditView.vue:59](../../frontend/src/views/AuditView.vue#L59)).
- **Global mode** (no `id`):
  - `GET /v1/audit?limit=500` via `auditApi.list({ limit: 500 })` ([frontend/src/services/api.ts:942-943](../../frontend/src/services/api.ts#L942); called at [AuditView.vue:66](../../frontend/src/views/AuditView.vue#L66)).

The Export JSONL action calls no API (client-side Blob). No write endpoints.

## Data Sources

- **Live**: `corrections` ref — either correction-ledger rows (per-session) or `audit_events` rows adapted to the `Correction` shape (global); `session` ref from `sessions.get` in per-session mode ([frontend/src/views/AuditView.vue:48-49](../../frontend/src/views/AuditView.vue#L48), [70-79](../../frontend/src/views/AuditView.vue#L70)).
- **Adapter**: global `audit_events` (`{id, session_id, actor_email, kind, summary, details, occurred_at}`) → `Correction` (`t=occurred_at`, `seg=session_id[:8]`, `type=kind`, `actor=actor_email||'system'`, `note=summary`, `prior/next=null`) ([frontend/src/views/AuditView.vue:36-44](../../frontend/src/views/AuditView.vue#L36), [70-79](../../frontend/src/views/AuditView.vue#L70)).
- **Derived**: `stats` (count per type), `types` (chip set), `distinctActors`, `distinctKinds` ([frontend/src/views/AuditView.vue:89-123](../../frontend/src/views/AuditView.vue#L89)).
- **Static**: `allTypes` (the 12 correction types for the L1 invariant grid) ([frontend/src/views/AuditView.vue:120](../../frontend/src/views/AuditView.vue#L120)); `correctionTypeLabel` chip/note map inside `AuditLedger` ([AuditLedger.vue:26-39](../../frontend/src/components/audit/AuditLedger.vue#L26)).

Per backend reality, the global feed reads the `audit_events` table and the per-session feed reads `correction_ledger` (named in the view's header comment and `seg`/`type` adaptation), but those table reads happen behind the two GET endpoints — NOT VERIFIED IN CODE at the DB layer from these frontend files.

## Source Verification
- **Files Used:** frontend/src/views/AuditView.vue, frontend/src/components/audit/AuditLedger.vue, frontend/src/services/api.ts, frontend/src/router/index.ts, frontend/src/components/shared/Icon.vue (referenced), frontend/src/composables/useToast.ts (referenced)
- **Components Used:** Icon (shared), AuditLedger
- **APIs Used:** GET /v1/audit (global), GET /v1/audit/sessions/{id}/corrections (per-session), GET /v1/sessions/{id} (per-session)
- **Database Tables Used:** audit_events and correction_ledger named in view comments/adapters (reached via the GET endpoints; not verified at the DB layer from the frontend)
- **Permission Logic Used:** JWT presence (global router beforeEach); no adminOnly / LEGACY_ADMIN_EMAIL gate on this route
- **Confidence Score:** High — both modes' endpoints and the global→Correction adapter traced to the view + api.ts; the "jump to segment" and "11/11 types pass" claims flagged as static/unwired UI copy.
- **Evidence Links:** [AuditView.vue:52-84](../../frontend/src/views/AuditView.vue#L52), [AuditView.vue:125-137](../../frontend/src/views/AuditView.vue#L125), [AuditLedger.vue:41-44](../../frontend/src/components/audit/AuditLedger.vue#L41), [api.ts:941-946](../../frontend/src/services/api.ts#L941), [router/index.ts:41](../../frontend/src/router/index.ts#L41)
