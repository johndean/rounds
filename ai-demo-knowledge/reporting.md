# Reporting & Dashboard — rounds.vin (what is actually computed)

> Verified against [frontend/src/views/DashboardView.vue](../frontend/src/views/DashboardView.vue),
> [frontend/src/components/dashboard/Sparkline.vue](../frontend/src/components/dashboard/Sparkline.vue),
> [app/api/queue.py](../app/api/queue.py), and [docs/specs/reporting.spec.md](../docs/specs/reporting.spec.md).
> Reporting is **pull-based**: the Dashboard aggregates over the session list + SOP
> state on read. **There is no time-series store**, so every sparkline and trend visual
> is decorative chrome only.

## How the Dashboard gets its data

On mount, `DashboardView.vue` issues exactly two calls in parallel
([DashboardView.vue:29](../frontend/src/views/DashboardView.vue#L29)):

1. `sessionsApi.list({})` -> `GET /v1/sessions` (the full session list).
2. `sopApi.dashboardSummary()` -> `GET /v1/sop/dashboard-summary` (per-stage counts + overdue counts).

Both `.catch(() => [])` to an empty array on failure. **There is no dedicated metrics
endpoint** — every KPI is derived client-side from those two responses
([docs/specs/reporting.spec.md](../docs/specs/reporting.spec.md), API routes table).

## Top KPI cards — REAL (computed client-side)

`topKpis` ([DashboardView.vue:50](../frontend/src/views/DashboardView.vue#L50)):

| Card | Value | Computation |
|---|---|---|
| AI Sessions | `allSessions.length` | total session count |
| SOP Sessions | `allSessions.length` (same count) | labeled "8-stage workflow" |
| Segments | sum of `segment_count` | `reduce` over sessions |
| Words | sum of `word_count` | `reduce` over sessions |
| CMS Published | count of `status === complete` | filter |
| Improvement RQs | **hardcoded `0`** | sub-label "see /improvements" — NOT wired to `/v1/improvements` |

Header line counts: `aiCount`, `readyCount` (status in {ready, complete}),
`processingCount` (status === ingesting) — all real filters over the session list
([DashboardView.vue:43](../frontend/src/views/DashboardView.vue#L43)).

## Pipeline rows — PARTIALLY REAL

**AI Processing row** (`aiPipeline`, [DashboardView.vue:75](../frontend/src/views/DashboardView.vue#L75)) — 7 stages, but only three counts are real:
- `Transcribe` = `processingCount` (sessions with status=ingesting), `Ready` = `readyCount`, `Failed` = count of status=failed.
- `Upload`, `Normalize`, `Align`, `Fuse` are **hardcoded `0`** — the session list does not expose intermediate FSM states, so these are placeholders.

**SOP Control row** (`sopPipeline`, [DashboardView.vue:90](../frontend/src/views/DashboardView.vue#L90)) — **fully real.** Each of the 8 stages maps to a row from `/v1/sop/dashboard-summary`: `count` and `attn = overdue_count > 0`. The overdue logic mirrors `sop_check_deadlines_task` so the ATTN badge matches what fires the hourly WS warnings.

Clicking any stage routes to `/sessions?ai=<id>` or `/sessions?stage=<id>` to filter the list.

## Your Queue — REAL DATA EXISTS, but the Dashboard widget does NOT use it

The Dashboard Queue widget is `allSessions.slice(0, 3)` ([DashboardView.vue:59](../frontend/src/views/DashboardView.vue#L59)) — the three most-recent sessions, **globally sliced, NOT assignee-filtered.**

A real per-user queue endpoint **does** exist: `GET /v1/queue/mine`
([app/api/queue.py:45](../app/api/queue.py#L45)) returns sessions where `user.email` is
the assignee for the session current SOP stage, with server-computed `overdue_hours`
(using the same `_DEFAULT_SLA_HOURS` map as BR-003), excluding soft-deleted, terminal
(`complete`), and group assignments. **The DashboardView read in this repo does not
call it** — the queue.py docstring notes the widget was just `allSessions.slice(0, 3)`.
PARTIALLY IMPLEMENTED: the backend is wired, the Dashboard widget is not.

## Operations section — PLACEHOLDER / DECORATIVE

`opsKpis` is a **static array of zeros and em-dashes** ([DashboardView.vue:61](../frontend/src/views/DashboardView.vue#L61)) — these are not computed at all:
- Unresolved Discrepancies `0`, QA Tasks `0`, Storage Used (dash), Avg Processing (dash), Avg Feedback (dash), Fusion Runs `0`.

The 7d / 30d / 90d / All time-range tabs and the All types / ARAV / NAVAS type chips
are **inert UI state** — flipping them changes a local ref but filters nothing
([DashboardView.vue:40](../frontend/src/views/DashboardView.vue#L40), [:101](../frontend/src/views/DashboardView.vue#L101)).

**SLA-by-stage grid** (`sla`, [DashboardView.vue:71](../frontend/src/views/DashboardView.vue#L71)): every cell is `{ dAvg: null, target: 2, sess: 0, state: empty }` and every bar renders width 0%. There is **no dwell-time history**, so this whole grid is empty chrome.

**Bottom widgets** (SOP Age Alerts, Correction Hotspots, Storage Top Sessions, Jobs Queue, Storage Breakdown) all render a literal **"No data yet."** / **"Celery queue is empty."** ([DashboardView.vue:297](../frontend/src/views/DashboardView.vue#L297)). The lone exception is **Assignment Coverage**, whose single Unassigned row shows `aiCount` (total session count) — not a real coverage computation.

## Sparklines — ALWAYS EMPTY

`Sparkline.vue` ([frontend/src/components/dashboard/Sparkline.vue](../frontend/src/components/dashboard/Sparkline.vue)) renders an empty div `dash-spark dash-spark--empty` whenever `data.length < 2`. **Every KPI card passes `spark: []`** ([DashboardView.vue:50](../frontend/src/views/DashboardView.vue#L50), [:61](../frontend/src/views/DashboardView.vue#L61)), so no sparkline ever draws a polyline. The component is fully functional; it is simply never fed a time series because none exists.

## The audit trail — REAL, append-only

The genuinely durable reporting surface is the audit ledger
([docs/specs/reporting.spec.md](../docs/specs/reporting.spec.md)):
- `GET /v1/audit`, `GET /v1/audit/sessions/{id}/corrections`, `GET /v1/sessions/{id}/audit-log`.
- `audit_events` rows are **never updated or deleted** — the ledger is the complete history and the provenance source for undo/redo.
- The editor correction history is the append-only `correction_ledger` (see [workflows.md](./workflows.md) section 8).

## Improvements board — REAL, separate workflow

`GET/POST/PUT/PATCH/DELETE /v1/improvements*` ([app/api/improvements.py](../app/api/improvements.py)),
backed by the `improvements` table, with its own status workflow
proposed -> in_review -> approved -> completed. Note the Dashboard Improvement RQs
KPI is hardcoded `0` and does not reflect this board real count.

## Documented reporting gaps (from the product doc)

[docs/product/reporting.md](../docs/product/reporting.md) Known gaps: no historical
trend charts (sparklines not time-series-backed), no SLA dwell-time history, no
per-operator productivity metrics, no cost tracking, no exportable reports.

## Real vs. decorative — at a glance

| Surface | Status |
|---|---|
| AI/SOP/Segments/Words/CMS KPI cards | REAL (client-side aggregates over `/v1/sessions`) |
| Improvement RQs KPI | placeholder `0` (not wired) |
| SOP Control pipeline row | REAL (`/v1/sop/dashboard-summary`) |
| AI pipeline row (Transcribe/Ready/Failed) | REAL; Upload/Normalize/Align/Fuse placeholder `0` |
| Your Queue widget | global slice (real endpoint `/v1/queue/mine` exists but unused here) |
| Ops KPIs, SLA grid, time-range tabs, type chips | PLACEHOLDER / inert |
| Sparklines | always empty (`spark: []`) |
| Bottom widgets | No data yet except Assignment-Coverage total |
| Audit trail + Improvements board | REAL, separate endpoints |

## Source Verification
- **Files Used:** frontend/src/views/DashboardView.vue, frontend/src/components/dashboard/Sparkline.vue, app/api/queue.py, docs/specs/reporting.spec.md, docs/product/reporting.md
- **Components Used:** DashboardView.vue, Sparkline.vue, StageBadge/Icon (referenced)
- **APIs Used:** GET /v1/sessions, GET /v1/sop/dashboard-summary (both called by the Dashboard), GET /v1/queue/mine (exists, NOT called by this view), GET /v1/audit*, /v1/sessions/{id}/audit-log, /v1/improvements*
- **Database Tables Used:** sessions, sop_state (via dashboard-summary), audit_events, correction_ledger, improvements (referenced)
- **Permission Logic Used:** JWT (CurrentUser) on every reporting route; no admin gate on dashboard/audit/queue/improvements reads.
- **Confidence Score:** High — every KPI/widget classification was read directly from DashboardView.vue computed/static definitions; the empty-sparkline behavior confirmed in Sparkline.vue.
- **Evidence Links:** [frontend/src/views/DashboardView.vue:29](../frontend/src/views/DashboardView.vue#L29), [DashboardView.vue:50](../frontend/src/views/DashboardView.vue#L50), [DashboardView.vue:59](../frontend/src/views/DashboardView.vue#L59), [DashboardView.vue:61](../frontend/src/views/DashboardView.vue#L61), [DashboardView.vue:297](../frontend/src/views/DashboardView.vue#L297), [Sparkline.vue:11](../frontend/src/components/dashboard/Sparkline.vue#L11), [app/api/queue.py:45](../app/api/queue.py#L45)
