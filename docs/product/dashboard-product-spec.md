# Dashboard — Product Spec

> Module key: `dashboard`. Scope: the `/dashboard` landing view ([frontend/src/views/DashboardView.vue](../../frontend/src/views/DashboardView.vue)) and the related per-user work queue at `/queue` ([frontend/src/views/QueueView.vue](../../frontend/src/views/QueueView.vue)). Every claim below is verified against the source files listed in Source Verification. Items that render in the UI but are not backed by live data are flagged explicitly.

## Overview

The Dashboard is the default landing screen after login. The router redirects `/` to `/dashboard` ([frontend/src/router/index.ts:28](../../frontend/src/router/index.ts#L28)). It presents a single scrolling page composed of: a greeting header, a six-card KPI strip, a "Your Queue" shortlist, a two-row pipeline visualization (AI processing + SOP control layer), an Operations section (six more KPI cards, an SLA-by-stage grid, four time-range tabs), and six lower widgets (SOP Age Alerts, Correction Hotspots, Storage Top Sessions, Jobs Queue, Storage Breakdown, Assignment Coverage).

Data is loaded once on mount from two endpoints in parallel: `GET /v1/sessions` (the session list) and `GET /v1/sop/dashboard-summary` (per-stage SOP counts) ([frontend/src/views/DashboardView.vue:27-38](../../frontend/src/views/DashboardView.vue#L27)). Several cards and all six lower widgets render their visual chrome with hardcoded zero/empty/dash values because the backing aggregate endpoints do not exist yet — this is stated in the component's own header comment ([frontend/src/views/DashboardView.vue:7-9](../../frontend/src/views/DashboardView.vue#L7)) and is detailed under States and Known Constraints below.

A separate, fully wired per-user work queue lives at `/queue` (QueueView). The Dashboard's "Your Queue" widget is **not** the same thing: it shows the three most recent sessions globally, not the sessions assigned to the current user (see Business Rules).

## Purpose

Give an operator a single at-a-glance view of:

- How many sessions exist and how many are ready vs. processing ([frontend/src/views/DashboardView.vue:43-45](../../frontend/src/views/DashboardView.vue#L43)).
- Where sessions sit across the 7-step AI processing pipeline and the 8-stage SOP control layer ([frontend/src/views/DashboardView.vue:75-97](../../frontend/src/views/DashboardView.vue#L75)).
- Which SOP stages have sessions running past their deadline (the `ATTN` badge), driven by `overdue_count` from the SOP summary ([frontend/src/views/DashboardView.vue:90-97](../../frontend/src/views/DashboardView.vue#L90)).
- A fast jump into a recent session or into the upload flow.

The `/queue` view's purpose is narrower and assignee-specific: list the sessions where the logged-in user is the assignee for the session's current SOP stage, longest-waiting first, so the user can act on their own backlog ([app/api/queue.py:1-17](../../app/api/queue.py#L1)).

## User Value

- One screen to see total throughput (AI Sessions, Segments, Words, CMS Published counts) without opening the Sessions list ([frontend/src/views/DashboardView.vue:50-57](../../frontend/src/views/DashboardView.vue#L50)).
- Pipeline rows act as filters: clicking an AI step navigates to `/sessions?ai=<step>` and clicking a SOP stage navigates to `/sessions?stage=<stage>` ([frontend/src/views/DashboardView.vue:204-226](../../frontend/src/views/DashboardView.vue#L204)). Both query params are honored by the sessions list endpoint ([app/api/sessions.py:155-173](../../app/api/sessions.py#L155)).
- Overdue stages are flagged with an `ATTN` badge so a reviewer knows where work is stalling ([frontend/src/views/DashboardView.vue:228-231](../../frontend/src/views/DashboardView.vue#L228)).
- The `/queue` view tells a user exactly what is waiting on them and how long it has waited, with an `OVERDUE` pill past SLA ([frontend/src/views/QueueView.vue:139-143](../../frontend/src/views/QueueView.vue#L139)).

## Navigation

- **Entry:** `/` redirects to `/dashboard` ([frontend/src/router/index.ts:28](../../frontend/src/router/index.ts#L28)). The dashboard route requires authentication (no `public` meta) ([frontend/src/router/index.ts:30](../../frontend/src/router/index.ts#L30), guard at [:53-67](../../frontend/src/router/index.ts#L53)).
- **Outbound from the Dashboard:**
  - "New upload" button -> `/upload` ([frontend/src/views/DashboardView.vue:129](../../frontend/src/views/DashboardView.vue#L129)).
  - "Your Queue" "View all →" link -> `/sessions` ([frontend/src/views/DashboardView.vue:150](../../frontend/src/views/DashboardView.vue#L150)).
  - Queue card click -> `/p/<id>` if status is `ingesting`, else `/e/<id>` ([frontend/src/views/DashboardView.vue:157](../../frontend/src/views/DashboardView.vue#L157)).
  - AI pipeline step click -> `/sessions?ai=<id>` ([frontend/src/views/DashboardView.vue:205](../../frontend/src/views/DashboardView.vue#L205)).
  - SOP pipeline step click -> `/sessions?stage=<id>` ([frontend/src/views/DashboardView.vue:226](../../frontend/src/views/DashboardView.vue#L226)).
  - The three lower-left widgets ("SOP Age Alerts", "Correction Hotspots", "Storage Top Sessions") each have an "All →" anchor to `#/sessions` ([frontend/src/views/DashboardView.vue:302](../../frontend/src/views/DashboardView.vue#L302), [:312](../../frontend/src/views/DashboardView.vue#L312), [:322](../../frontend/src/views/DashboardView.vue#L322)).
- **Outbound from `/queue`:** clicking any row navigates to `/e/<session_id>/sop` ([frontend/src/views/QueueView.vue:90-92](../../frontend/src/views/QueueView.vue#L90)).
- **The `/queue` route** is registered separately ([frontend/src/router/index.ts:43](../../frontend/src/router/index.ts#L43)). There is no link to `/queue` from within DashboardView in the verified source. NOT VERIFIED IN CODE: how a user reaches `/queue` from the chrome/nav.

## Screens

### Dashboard (`/dashboard`)

A single `<main class="page dash-page">` ([frontend/src/views/DashboardView.vue:118](../../frontend/src/views/DashboardView.vue#L118)) containing, top to bottom:

1. **Header** — eyebrow `Today · <DATE>`, greeting (`Good morning/afternoon/evening, <FirstName>`), and a lead line. The greeting is time-of-day based ([:103-106](../../frontend/src/views/DashboardView.vue#L103)); the first name is derived from the local-part of the authenticated email ([:110-113](../../frontend/src/views/DashboardView.vue#L110)); the lead shows live session/ready/processing counts once loaded ([:123-126](../../frontend/src/views/DashboardView.vue#L123)). A "New upload" primary button sits on the right ([:128-132](../../frontend/src/views/DashboardView.vue#L128)).
2. **Top KPI strip (6 cards)** — AI Sessions, SOP Sessions, Segments, Words, CMS Published, Improvement RQs ([:50-57](../../frontend/src/views/DashboardView.vue#L50)). Each card renders a `Sparkline` ([:142](../../frontend/src/views/DashboardView.vue#L142)).
3. **Your Queue section** — up to three cards, one per recent session, plus an empty state ([:146-178](../../frontend/src/views/DashboardView.vue#L146)).
4. **Pipeline section** — type chips (`All types`, `ARAV`, `NAVAS`) ([:101](../../frontend/src/views/DashboardView.vue#L101), [:184-192](../../frontend/src/views/DashboardView.vue#L184)) and two pipeline cards: Pipeline 1 (AI Processing, 7 steps) and Pipeline 2 (SOP Control Layer, 8 stages) ([:195-236](../../frontend/src/views/DashboardView.vue#L195)).
5. **Operations section** — eyebrow + "System overview" title, four time-range tabs (`7d`, `30d`, `90d`, `All`) ([:245-252](../../frontend/src/views/DashboardView.vue#L245)), a second 6-card KPI strip ([:255-264](../../frontend/src/views/DashboardView.vue#L255)), and an "SLA by stage" grid with one cell per SOP stage ([:266-294](../../frontend/src/views/DashboardView.vue#L266)).
6. **Two rows of three widgets** — SOP Age Alerts, Correction Hotspots, Storage Top Sessions ([:297-328](../../frontend/src/views/DashboardView.vue#L297)); Jobs Queue, Storage Breakdown, Assignment Coverage ([:330-362](../../frontend/src/views/DashboardView.vue#L330)).

### My queue (`/queue`)

A `<main class="route">` with a header (title "My queue", subtitle, item-count chip, overdue chip) and a list of clickable rows ([frontend/src/views/QueueView.vue:99-149](../../frontend/src/views/QueueView.vue#L99)). Each row shows code, title, current stage, time-in-stage, and an `OVERDUE` pill when past SLA ([:130-145](../../frontend/src/views/QueueView.vue#L130)). Loading, error, and empty states are distinct branches ([:114-119](../../frontend/src/views/QueueView.vue#L114)).

## User Flows

**Land on dashboard.** User logs in -> redirected `/` -> `/dashboard`. On mount, `Promise.all` fetches sessions and SOP summary; both calls have `.catch(() => [])` fallbacks so a failure of one does not blank the page ([frontend/src/views/DashboardView.vue:27-38](../../frontend/src/views/DashboardView.vue#L27)). While `loading` is true the lead reads "Loading sessions…" ([:124](../../frontend/src/views/DashboardView.vue#L124)).

**Drill into a pipeline stage.** User clicks a SOP stage circle -> `/sessions?stage=<id>` -> sessions list joins `sop_state` on `current_stage = :stage` and returns only sessions in that stage ([app/api/sessions.py:167](../../app/api/sessions.py#L167)). An AI step click filters by `status = :ai` ([app/api/sessions.py:155-157](../../app/api/sessions.py#L155)).

**Open a recent session from Your Queue.** Click a card -> `ingesting` sessions go to the processing view `/p/<id>`, all others to the editor `/e/<id>` ([frontend/src/views/DashboardView.vue:157](../../frontend/src/views/DashboardView.vue#L157)).

**Work your own queue (`/queue`).** On mount, `GET /v1/queue/mine` loads the user's current-stage assignments, ordered longest-waiting first ([app/api/queue.py:108](../../app/api/queue.py#L108)). The view re-polls every 30 seconds and on tab re-focus, silently (no spinner, no error toast on background refresh) ([frontend/src/views/QueueView.vue:30](../../frontend/src/views/QueueView.vue#L30), [:54-66](../../frontend/src/views/QueueView.vue#L54)). Overlapping loads are dropped via an `inFlight` guard ([:32](../../frontend/src/views/QueueView.vue#L32), [:36-37](../../frontend/src/views/QueueView.vue#L36)). Click a row -> `/e/<session_id>/sop` ([:90-92](../../frontend/src/views/QueueView.vue#L90)).

## Business Rules

- **BR-D1 — "Your Queue" is most-recent-3, not assignee-filtered.** The Dashboard widget is `allSessions.slice(0, 3)` ([frontend/src/views/DashboardView.vue:59](../../frontend/src/views/DashboardView.vue#L59)). Because the session list is ordered `created_at DESC` server-side ([app/api/sessions.py:169](../../app/api/sessions.py#L169)), this is the three newest sessions globally. The queue.py docstring explicitly identifies this as the prior behavior that the dedicated `/queue` endpoint was built to replace ([app/api/queue.py:11-13](../../app/api/queue.py#L11)).
- **BR-D2 — Assignee match supports two JSONB shapes.** `/v1/queue/mine` matches the current user when they are either the `assignee` field of a nested object keyed by stage, or a plain string keyed by stage, using a SQL `COALESCE` over both paths ([app/api/queue.py:100-105](../../app/api/queue.py#L100)).
- **BR-D3 — Per-stage SLA hours.** Both the queue endpoint and the SOP dashboard summary use the same default SLA map: prep 8h, copy_draft 24h, medical 48h, copy_final 24h, cms 12h, captions 12h, qa 8h, complete 0h (terminal) ([app/api/queue.py:69-78](../../app/api/queue.py#L69); canonical source [app/tasks/sop_tasks.py:36-45](../../app/tasks/sop_tasks.py#L36)). A per-session override in `sop_state.sla_target_hours` takes precedence when present and integer-typed ([app/api/queue.py:123-126](../../app/api/queue.py#L123); [app/api/sop.py:314-315](../../app/api/sop.py#L314)).
- **BR-D4 — Overdue computation.** `overdue_hours = round(elapsed - sla, 1)`, set only when elapsed > SLA and SLA > 0; otherwise null. Negatives are not emitted ([app/api/queue.py:127-131](../../app/api/queue.py#L127)). The SOP summary counts a session as overdue when `now > entered_current_at + sla_hours` ([app/api/sop.py:318-320](../../app/api/sop.py#L318)).
- **BR-D5 — Queue exclusions.** `/v1/queue/mine` excludes soft-deleted sessions (`deleted_at IS NULL`), excludes the terminal `complete` stage, and (by relying on the string/nested-assignee match) does not expand `group:NAME` assignments — group expansion is explicitly deferred ([app/api/queue.py:53-58](../../app/api/queue.py#L53), [:106-107](../../app/api/queue.py#L106)). Results are capped at `LIMIT 200` ([:109](../../app/api/queue.py#L109)).
- **BR-D6 — SOP stage order.** Eight stages in fixed order: prep, copy_draft, medical, copy_final, cms, captions, qa, complete ([app/api/sop.py:24](../../app/api/sop.py#L24); frontend mirror [frontend/src/fixtures/sop_stages.ts:12-29](../../frontend/src/fixtures/sop_stages.ts#L12)). The dashboard summary always returns one row per stage in this order, including zero-count stages ([app/api/sop.py:322-325](../../app/api/sop.py#L322)).
- **BR-D7 — AI pipeline steps are a fixed 7-step display list.** Upload, Transcribe, Normalize, Align, Fuse, Ready, Failed ([frontend/src/views/DashboardView.vue:75-83](../../frontend/src/views/DashboardView.vue#L75)). Only Transcribe (`status === 'ingesting'`), Ready (`status` in `ready`/`complete`), and Failed (`status === 'failed'`) derive live counts; Upload/Normalize/Align/Fuse are hardcoded to 0. PARTIALLY IMPLEMENTED — there is no per-step backend breakdown; counts are inferred from `session.status` client-side.

## Validation Rules

- The Dashboard view performs no form input or write operations; there is nothing to validate. NOT VERIFIED IN CODE: any client-side validation (none present).
- `/queue` performs no writes either; it is read-only ([app/api/queue.py:63](../../app/api/queue.py#L63)). Client guards: `hoursInStage` clamps elapsed time to `Math.max(0, …)` to avoid negative durations from client clock skew ([frontend/src/views/QueueView.vue:84](../../frontend/src/views/QueueView.vue#L84)); the overdue pill only renders when `overdue_hours > 0` ([:140](../../frontend/src/views/QueueView.vue#L140)).

## States

**Dashboard load states.**
- `loading` true on mount until both fetches settle; lead shows "Loading sessions…" ([frontend/src/views/DashboardView.vue:124](../../frontend/src/views/DashboardView.vue#L124)).
- Loaded: lead shows live counts ([:125](../../frontend/src/views/DashboardView.vue#L125)).
- Empty queue (loaded, zero sessions): "No sessions yet — upload one" inline message with an upload button ([:173-176](../../frontend/src/views/DashboardView.vue#L173)).

**Live vs. placeholder data on the Dashboard (verified).**
- *Live:* AI Sessions count, ready/processing split, Segments total, Words total, CMS Published count (`status === 'complete'`), the AI pipeline Transcribe/Ready/Failed counts, the SOP Pipeline 2 per-stage counts and `ATTN` badges, and the "Assignment Coverage" Unassigned count (`= aiCount`) ([:43-57](../../frontend/src/views/DashboardView.vue#L43), [:75-97](../../frontend/src/views/DashboardView.vue#L75), [:358](../../frontend/src/views/DashboardView.vue#L358)).
- *Hardcoded zero/empty placeholders:* "SOP Sessions" card actually shows `aiCount` (same value, labeled differently) ([:52](../../frontend/src/views/DashboardView.vue#L52)); "Improvement RQs" is `0` ([:56](../../frontend/src/views/DashboardView.vue#L56)); the entire Operations KPI strip (Unresolved Discrepancies, QA Tasks, Storage Used, Avg Processing, Avg Feedback, Fusion Runs) is a static array of zeros and dashes ([:61-68](../../frontend/src/views/DashboardView.vue#L61)); the SLA grid renders every stage with `dAvg: null`, `state: 'empty'`, `sess: 0`, and a `0%` bar ([:71-73](../../frontend/src/views/DashboardView.vue#L71), [:283-287](../../frontend/src/views/DashboardView.vue#L283)); the lower widgets render "No data yet." / "Celery queue is empty." ([:305](../../frontend/src/views/DashboardView.vue#L305), [:337](../../frontend/src/views/DashboardView.vue#L337)). The component header comment confirms these "render their visual chrome with safe zero/empty values until the matching stats endpoints land" ([:7-9](../../frontend/src/views/DashboardView.vue#L7)).
- *Always-empty sparklines:* every KPI passes `spark: []`, and `Sparkline` renders the empty `.dash-spark--empty` div whenever data has fewer than 2 points ([frontend/src/components/dashboard/Sparkline.vue:11](../../frontend/src/components/dashboard/Sparkline.vue#L11), [:29](../../frontend/src/components/dashboard/Sparkline.vue#L29)). No sparkline ever draws a line.
- *Inert controls:* the type chips (`All types/ARAV/NAVAS`) toggle a local `pipelineFilter` ref and the time-range tabs toggle a local `timeRange` ref, but neither value is read anywhere that changes displayed data ([:40-41](../../frontend/src/views/DashboardView.vue#L40), [:184-192](../../frontend/src/views/DashboardView.vue#L184), [:245-252](../../frontend/src/views/DashboardView.vue#L245)). They are visual-only toggles. PARTIALLY IMPLEMENTED.

**`/queue` states.** Loading ("Loading…"), error (red message + toast on foreground load), empty ("You have no pending items."), and populated list ([frontend/src/views/QueueView.vue:114-148](../../frontend/src/views/QueueView.vue#L114)). Each row may additionally carry the overdue modifier class/pill ([:126](../../frontend/src/views/QueueView.vue#L126), [:139-143](../../frontend/src/views/QueueView.vue#L139)).

## Dependencies

- **APIs:** `GET /v1/sessions` ([app/api/sessions.py:138](../../app/api/sessions.py#L138)), `GET /v1/sop/dashboard-summary` ([app/api/sop.py:279](../../app/api/sop.py#L279)), and (for `/queue`) `GET /v1/queue/mine` ([app/api/queue.py:45](../../app/api/queue.py#L45)).
- **Frontend services:** `sessions.list`, `sop.dashboardSummary`, `queue.mine` in [frontend/src/services/api.ts](../../frontend/src/services/api.ts) ([:137-138](../../frontend/src/services/api.ts#L137), [:634-637](../../frontend/src/services/api.ts#L634), [:366](../../frontend/src/services/api.ts#L366)).
- **Shared components:** `Icon`, `StageBadge`, and the dashboard-local `Sparkline` ([frontend/src/views/DashboardView.vue:13-15](../../frontend/src/views/DashboardView.vue#L13)). `StageBadge` resolves stage names from the `SOP_STAGES` fixture ([frontend/src/components/shared/StageBadge.vue:7](../../frontend/src/components/shared/StageBadge.vue#L7)).
- **Stores:** `useAuthStore` for the email used in the greeting ([frontend/src/views/DashboardView.vue:18](../../frontend/src/views/DashboardView.vue#L18), [:21](../../frontend/src/views/DashboardView.vue#L21)).
- **Fixtures:** `SOP_STAGES` drives the SOP pipeline row, the SLA grid, and the StageBadge ([frontend/src/fixtures/sop_stages.ts:12](../../frontend/src/fixtures/sop_stages.ts#L12)).
- **Database tables:** `sessions` (and its `deleted_at`, `status`, count columns), `sop_state` (`current_stage`, `entered_current_at`, `sla_target_hours`, `assignees`) ([app/api/sessions.py:162-167](../../app/api/sessions.py#L162); [app/api/sop.py:295-298](../../app/api/sop.py#L295); [app/api/queue.py:91-107](../../app/api/queue.py#L91)).

## Error Handling

- **Dashboard:** each of the two mount fetches is independently `.catch`'d to an empty array, so a failed call degrades to empty data rather than an error screen ([frontend/src/views/DashboardView.vue:30-31](../../frontend/src/views/DashboardView.vue#L30)). There is no error banner on the Dashboard. NOT VERIFIED IN CODE: any retry behavior (none present).
- **`/queue`:** a failed `queue.mine()` sets `error` and, only on a foreground (spinner) load, pushes an error toast; background 30s refreshes swallow the error silently to avoid a recurring red banner on transient network blips ([frontend/src/views/QueueView.vue:43-51](../../frontend/src/views/QueueView.vue#L43)). The error message is the thrown `Error.message` or the fallback string "Failed to load queue" ([:44](../../frontend/src/views/QueueView.vue#L44)).
- **Backend:** both `dashboard_summary` and `list_my_queue` skip unknown stages rather than erroring, keeping the response well-formed ([app/api/sop.py:306-307](../../app/api/sop.py#L306)).

## Permissions

Authorization here is **JWT presence only**. There are no role tiers in effect for the Dashboard or queue.

- The dashboard route has no `public` meta, so the router guard requires `auth.isAuthenticated` and otherwise redirects to login ([frontend/src/router/index.ts:30](../../frontend/src/router/index.ts#L30), [:59-62](../../frontend/src/router/index.ts#L59)).
- All three backend endpoints take a `CurrentUser` dependency, which only decodes the JWT and confirms the user is active (DB lookup with env-CSV fallback) — it returns `User(email=…)` and **does not read any role** ([app/auth.py:172-205](../../app/auth.py#L172), [:208](../../app/auth.py#L208); the `User` dataclass has a single `email` field [app/auth.py:37-38](../../app/auth.py#L37)). The sessions and SOP-summary endpoints bind the user as `_user`/`_u` and never branch on identity ([app/api/sessions.py:141](../../app/api/sessions.py#L141); [app/api/sop.py:280](../../app/api/sop.py#L280)).
- `/v1/queue/mine` is per-user only in the sense that it filters rows by `user.email`; any authenticated user sees their own assignments and no one else's ([app/api/queue.py:104-112](../../app/api/queue.py#L104)). This is data scoping, not a permission tier.
- The only admin gate anywhere in the router is the client-side `adminOnly` guard on `/admin/help`, comparing `auth.email` to a hardcoded `johndean@vin.com` ([frontend/src/router/index.ts:51](../../frontend/src/router/index.ts#L51), [:63-66](../../frontend/src/router/index.ts#L63)). It does **not** apply to the Dashboard or `/queue`.

## Reporting Impacts

The Dashboard *is* the primary reporting surface, but most reporting promised by the layout is not yet backed by data:

- **Live, reportable now:** total sessions, ready/processing split, segment total, word total, CMS-published count, per-SOP-stage session counts, and per-stage overdue counts ([frontend/src/views/DashboardView.vue:43-57](../../frontend/src/views/DashboardView.vue#L43); [app/api/sop.py:322-325](../../app/api/sop.py#L322)).
- **Not backed by data (placeholders):** Improvement RQs, all six Operations KPIs, the SLA dwell-time grid, the sparkline trends, SOP Age Alerts, Correction Hotspots, Storage Top Sessions, Jobs Queue, and Storage Breakdown — all render static zero/empty chrome ([:56](../../frontend/src/views/DashboardView.vue#L56), [:61-73](../../frontend/src/views/DashboardView.vue#L61), [:297-347](../../frontend/src/views/DashboardView.vue#L297)). These match the "Known gaps" already documented in the reporting seed (no historical trend charts, no SLA dwell-time history, no per-operator metrics, no cost tracking, no exportable reports) — re-verified against current code as still accurate. See Known Constraints.
- **No export.** There is no CSV/PDF export path from the Dashboard in the verified source. NOT VERIFIED IN CODE.

## Audit Requirements

- The Dashboard and `/queue` are read-only and produce no audit rows. `dashboard_summary` notes explicitly "Reads only; no `audit_events` row" ([app/api/sop.py:293](../../app/api/sop.py#L293)). `list_my_queue` is documented "Read-only. No mutations." ([app/api/queue.py:63](../../app/api/queue.py#L63)).
- The overdue logic shown on the Dashboard (the `ATTN` badge) is the *same* SLA computation that, in the Celery deadline task, does emit warnings and is intended to align with `audit_events` rows generated there — but that emission happens in `sop_check_deadlines_task`, not in the Dashboard read path ([frontend/src/views/DashboardView.vue:86-89](../../frontend/src/views/DashboardView.vue#L86); [app/tasks/sop_tasks.py:485-501](../../app/tasks/sop_tasks.py#L485)). NOT VERIFIED IN CODE here: the exact audit row shape (out of module scope).

## Data Relationships

- A `session` (in `sessions`) has exactly one `sop_state` row joined on `sop_state.session_id = sessions.id` ([app/api/queue.py:102-103](../../app/api/queue.py#L102); [app/api/sessions.py:167](../../app/api/sessions.py#L167)).
- `sop_state.current_stage` is one of the eight `STAGES` values ([app/api/sop.py:24](../../app/api/sop.py#L24)). The Dashboard's SOP row, the Sessions `?stage=` filter, and the queue all key off this column.
- `sop_state.assignees` is a JSONB map of stage -> assignee (string email or `{assignee, assigned_by, assigned_at}` object), and `sop_state.sla_target_hours` is a JSONB map of stage -> hours override ([app/api/queue.py:79-86](../../app/api/queue.py#L79), [:100-105](../../app/api/queue.py#L100); [app/api/sop.py:314](../../app/api/sop.py#L314)).
- The Dashboard's AI pipeline counts derive purely from `sessions.status` string values (`ingesting`, `ready`, `complete`, `failed`); there is no separate per-AI-step table behind those counts ([frontend/src/views/DashboardView.vue:43-45](../../frontend/src/views/DashboardView.vue#L43), [:75-83](../../frontend/src/views/DashboardView.vue#L75)).

## Known Constraints

- **The Dashboard reads at most ~50 sessions for its aggregates.** `sessions.list({})` calls `GET /v1/sessions` with no `limit`, and the backend defaults `limit = 50` ([frontend/src/views/DashboardView.vue:30](../../frontend/src/views/DashboardView.vue#L30); [app/api/sessions.py:145](../../app/api/sessions.py#L145)). Therefore AI Sessions / Segments / Words / CMS Published / Assignment-Coverage counts on the Dashboard are bounded by 50 and will under-report once more than 50 sessions exist. The SOP Pipeline 2 counts are *not* subject to this limit — they come from `dashboard_summary`, which aggregates all `sop_state` rows ([app/api/sop.py:295-298](../../app/api/sop.py#L295)). This is a discrepancy worth noting: the two pipeline rows can disagree at scale.
- **"SOP Sessions" card is mislabeled-but-equal.** It displays `aiCount`, identical to "AI Sessions" ([frontend/src/views/DashboardView.vue:52](../../frontend/src/views/DashboardView.vue#L52)).
- **No live trend/time-series.** Sparklines and the time-range tabs (`7d/30d/90d/All`) have no backing data; tabs change a local ref only ([frontend/src/views/DashboardView.vue:71-73](../../frontend/src/views/DashboardView.vue#L71), [:245-252](../../frontend/src/views/DashboardView.vue#L245)).
- **No SLA dwell-time history.** The SLA-by-stage grid is structurally present but every cell is empty (`dAvg: null`, `0%` bar) ([:71-73](../../frontend/src/views/DashboardView.vue#L71)). Matches the reporting seed's stated gap; re-verified.
- **No auto-refresh on the Dashboard.** Unlike `/queue` (30s poll), the Dashboard loads once on mount and never re-fetches ([frontend/src/views/DashboardView.vue:27-38](../../frontend/src/views/DashboardView.vue#L27)).
- **`/queue` is capped at 200 items** and excludes `complete`-stage and group assignments ([app/api/queue.py:106-109](../../app/api/queue.py#L106)).

## Source Verification
- **Files Used:** frontend/src/views/DashboardView.vue, frontend/src/views/QueueView.vue, frontend/src/components/dashboard/Sparkline.vue, frontend/src/components/shared/StageBadge.vue, frontend/src/fixtures/sop_stages.ts, frontend/src/router/index.ts, frontend/src/services/api.ts, app/api/queue.py, app/api/sop.py, app/api/sessions.py, app/tasks/sop_tasks.py, app/auth.py, app/main.py, docs/product/reporting.md (seed)
- **Components Used:** DashboardView.vue, QueueView.vue, Sparkline.vue, StageBadge.vue, Icon.vue (imported)
- **APIs Used:** GET /v1/sessions, GET /v1/sop/dashboard-summary, GET /v1/queue/mine
- **Database Tables Used:** sessions, sop_state
- **Permission Logic Used:** JWT presence only (CurrentUser decodes JWT, returns email, reads no role) + client-side authenticated-route guard. No role tiers in effect for this module.
- **Confidence Score:** High — every claim traces to a read line in the listed files; placeholder vs. live data distinctions verified directly in DashboardView.vue.
- **Evidence Links:** [DashboardView.vue:27-38](../../frontend/src/views/DashboardView.vue#L27), [DashboardView.vue:59](../../frontend/src/views/DashboardView.vue#L59), [DashboardView.vue:61-73](../../frontend/src/views/DashboardView.vue#L61), [queue.py:45-143](../../app/api/queue.py#L45), [sop.py:279-325](../../app/api/sop.py#L279), [sessions.py:138-175](../../app/api/sessions.py#L138), [auth.py:172-208](../../app/auth.py#L172)
