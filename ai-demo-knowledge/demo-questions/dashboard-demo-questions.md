# Dashboard — Demo Questions (Code-Verified)

> Module key: `dashboard`. Surfaces: `/dashboard` ([frontend/src/views/DashboardView.vue](../../frontend/src/views/DashboardView.vue)) and `/queue` ([frontend/src/views/QueueView.vue](../../frontend/src/views/QueueView.vue)). Every answer below is true against current code; placeholder/unbacked UI is called out as such. Link paths are relative to this file (`ai-demo-knowledge/demo-questions/`).

---

## User

### Q: What do I see right after I log in?
- **Verified Answer:** The Dashboard at `/dashboard` (the router redirects `/` there). You get a time-of-day greeting with your first name, a strip of six count cards, a "Your Queue" shortlist of recent sessions, the AI + SOP pipeline rows, an Operations section, and six lower widgets.
- **Supporting Evidence:** `/` redirects to `/dashboard` ([frontend/src/router/index.ts:28](../../frontend/src/router/index.ts#L28)); greeting/first-name/layout ([frontend/src/views/DashboardView.vue:103-133](../../frontend/src/views/DashboardView.vue#L103)).
- **Source Files:** frontend/src/router/index.ts, frontend/src/views/DashboardView.vue
- **API References:** GET /v1/sessions, GET /v1/sop/dashboard-summary
- **Database References:** sessions, sop_state

### Q: What does "Your Queue" on the dashboard actually show?
- **Verified Answer:** The three most recent sessions overall — not the sessions assigned to you. It is `allSessions.slice(0, 3)` over a list ordered newest-first. The assignee-specific queue is a separate screen at `/queue`.
- **Supporting Evidence:** `queue = allSessions.slice(0, 3)` ([frontend/src/views/DashboardView.vue:59](../../frontend/src/views/DashboardView.vue#L59)); list ordered `created_at DESC` ([app/api/sessions.py:169](../../app/api/sessions.py#L169)); the queue endpoint docstring calls the slice the old behavior it replaced ([app/api/queue.py:11-13](../../app/api/queue.py#L11)).
- **Source Files:** frontend/src/views/DashboardView.vue, app/api/sessions.py, app/api/queue.py
- **API References:** GET /v1/sessions
- **Database References:** sessions

### Q: How do I jump to all sessions sitting in a particular workflow stage?
- **Verified Answer:** Click that stage's circle in the SOP pipeline row. It navigates to `/sessions?stage=<stage>`, and the sessions list filters by joining `sop_state` on the current stage. AI-step circles navigate to `/sessions?ai=<step>`, filtering by session status.
- **Supporting Evidence:** SOP click -> `/sessions?stage=<id>` ([frontend/src/views/DashboardView.vue:226](../../frontend/src/views/DashboardView.vue#L226)); AI click -> `/sessions?ai=<id>` ([:205](../../frontend/src/views/DashboardView.vue#L205)); backend filters ([app/api/sessions.py:155-167](../../app/api/sessions.py#L155)).
- **Source Files:** frontend/src/views/DashboardView.vue, app/api/sessions.py
- **API References:** GET /v1/sessions?stage= , GET /v1/sessions?ai=
- **Database References:** sessions, sop_state

### Q: How do I open a recent session from the dashboard?
- **Verified Answer:** Click its card in "Your Queue." Sessions still ingesting open in the processing view (`/p/<id>`); everything else opens in the editor (`/e/<id>`).
- **Supporting Evidence:** click handler routes by status ([frontend/src/views/DashboardView.vue:157](../../frontend/src/views/DashboardView.vue#L157)).
- **Source Files:** frontend/src/views/DashboardView.vue
- **API References:** none
- **Database References:** none

### Q: Where do I see the work assigned specifically to me?
- **Verified Answer:** The `/queue` view ("My queue"). It lists sessions where you are the assignee for the session's current SOP stage, longest-waiting first, with time-in-stage and an OVERDUE pill when past the stage SLA.
- **Supporting Evidence:** QueueView loads `GET /v1/queue/mine` ([frontend/src/views/QueueView.vue:42](../../frontend/src/views/QueueView.vue#L42)); endpoint filters by your email and orders oldest-first ([app/api/queue.py:104-108](../../app/api/queue.py#L104)).
- **Source Files:** frontend/src/views/QueueView.vue, app/api/queue.py
- **API References:** GET /v1/queue/mine
- **Database References:** sessions, sop_state

### Q: How often does My Queue refresh?
- **Verified Answer:** Every 30 seconds in the background, plus an immediate refresh when you switch back to the tab. The dashboard itself does not auto-refresh — it loads once when opened.
- **Supporting Evidence:** 30s interval + visibility refresh ([frontend/src/views/QueueView.vue:30](../../frontend/src/views/QueueView.vue#L30), [:62-66](../../frontend/src/views/QueueView.vue#L62)); dashboard loads only `onMounted` ([frontend/src/views/DashboardView.vue:27-38](../../frontend/src/views/DashboardView.vue#L27)).
- **Source Files:** frontend/src/views/QueueView.vue, frontend/src/views/DashboardView.vue
- **API References:** GET /v1/queue/mine
- **Database References:** none

---

## Executive

### Q: Which dashboard numbers are real today versus placeholder?
- **Verified Answer:** Real (live): total AI Sessions, ready/processing split, Segments total, Words total, CMS Published count, the SOP per-stage counts, and the per-stage overdue (ATTN) flags. Placeholder (hardcoded zeros/dashes): Improvement RQs, the entire Operations KPI strip (Unresolved Discrepancies, QA Tasks, Storage Used, Avg Processing, Avg Feedback, Fusion Runs), the SLA dwell-time grid, the sparklines, and all six lower widgets.
- **Supporting Evidence:** live KPIs ([frontend/src/views/DashboardView.vue:43-57](../../frontend/src/views/DashboardView.vue#L43)); static ops array ([:61-68](../../frontend/src/views/DashboardView.vue#L61)); empty SLA cells ([:71-73](../../frontend/src/views/DashboardView.vue#L71)); "No data yet."/"Celery queue is empty." widgets ([:305](../../frontend/src/views/DashboardView.vue#L305), [:337](../../frontend/src/views/DashboardView.vue#L337)); the component's own header comment ([:7-9](../../frontend/src/views/DashboardView.vue#L7)).
- **Source Files:** frontend/src/views/DashboardView.vue
- **API References:** GET /v1/sessions, GET /v1/sop/dashboard-summary
- **Database References:** sessions, sop_state

### Q: Can the dashboard show throughput trends over time (7d/30d/90d)?
- **Verified Answer:** No. The 7d/30d/90d/All tabs and the sparklines are visual chrome only. The tabs toggle a local variable that nothing reads, and every sparkline is fed an empty array so no line is ever drawn. There is no time-series data behind the dashboard.
- **Supporting Evidence:** `timeRange` ref is toggled but unused ([frontend/src/views/DashboardView.vue:41](../../frontend/src/views/DashboardView.vue#L41), [:245-252](../../frontend/src/views/DashboardView.vue#L245)); all `spark: []` ([:51-67](../../frontend/src/views/DashboardView.vue#L51)); Sparkline empties on `< 2` points ([frontend/src/components/dashboard/Sparkline.vue:11](../../frontend/src/components/dashboard/Sparkline.vue#L11)).
- **Source Files:** frontend/src/views/DashboardView.vue, frontend/src/components/dashboard/Sparkline.vue
- **API References:** none
- **Database References:** none

### Q: Does the dashboard tell me how many sessions have been published to the CMS?
- **Verified Answer:** Yes — the "CMS Published" card counts sessions whose `status` is `complete`. (Caveat: this count is bounded by the 50-session page limit, see Operations below.)
- **Supporting Evidence:** `status === 'complete'` count ([frontend/src/views/DashboardView.vue:55](../../frontend/src/views/DashboardView.vue#L55)).
- **Source Files:** frontend/src/views/DashboardView.vue
- **API References:** GET /v1/sessions
- **Database References:** sessions

### Q: Are there exportable reports from the dashboard?
- **Verified Answer:** No export path exists in code. The reporting notes recommend a screenshot or browser print-to-PDF. NOT VERIFIED IN CODE: any CSV/PDF export.
- **Supporting Evidence:** no export code in DashboardView; reporting seed lists "No exportable reports" as a known gap (re-verified) ([../../docs/product/reporting.md](../../docs/product/reporting.md)).
- **Source Files:** frontend/src/views/DashboardView.vue, docs/product/reporting.md
- **API References:** none
- **Database References:** none

---

## Operations

### Q: How are the SOP pipeline per-stage counts and "ATTN" flags computed?
- **Verified Answer:** From `GET /v1/sop/dashboard-summary`, which scans all `sop_state` rows and returns, per stage, a `count` and `overdue_count`. The dashboard shows the count in each stage circle and an ATTN badge when `overdue_count > 0`. A stage is overdue when its dwell time exceeds the per-stage SLA, computed in Python so it matches the deadline Celery task.
- **Supporting Evidence:** dashboard mapping ([frontend/src/views/DashboardView.vue:90-97](../../frontend/src/views/DashboardView.vue#L90)); endpoint logic ([app/api/sop.py:295-325](../../app/api/sop.py#L295)).
- **Source Files:** frontend/src/views/DashboardView.vue, app/api/sop.py
- **API References:** GET /v1/sop/dashboard-summary
- **Database References:** sop_state

### Q: What are the default SLA hours per stage?
- **Verified Answer:** prep 8h, copy_draft 24h, medical 48h, copy_final 24h, cms 12h, captions 12h, qa 8h, complete 0h (terminal). A per-session integer override in `sop_state.sla_target_hours` wins when present.
- **Supporting Evidence:** queue map ([app/api/queue.py:69-78](../../app/api/queue.py#L69)); canonical map ([app/tasks/sop_tasks.py:36-45](../../app/tasks/sop_tasks.py#L36)); override precedence ([app/api/queue.py:123-126](../../app/api/queue.py#L123); [app/api/sop.py:314-315](../../app/api/sop.py#L314)).
- **Source Files:** app/api/queue.py, app/tasks/sop_tasks.py, app/api/sop.py
- **API References:** GET /v1/queue/mine, GET /v1/sop/dashboard-summary
- **Database References:** sop_state

### Q: Why might the dashboard's session count undercount our real total?
- **Verified Answer:** The dashboard fetches `GET /v1/sessions` with no `limit`, and the backend defaults `limit=50`. So AI Sessions, Segments, Words, CMS Published, and Assignment-Coverage are computed over at most 50 sessions. The SOP Pipeline 2 counts are NOT capped (they aggregate the whole `sop_state` table), so the two pipeline rows can disagree once you exceed 50 sessions.
- **Supporting Evidence:** no-limit call ([frontend/src/views/DashboardView.vue:30](../../frontend/src/views/DashboardView.vue#L30)); default 50 ([app/api/sessions.py:145](../../app/api/sessions.py#L145)); unbounded SOP scan ([app/api/sop.py:295-298](../../app/api/sop.py#L295)).
- **Source Files:** frontend/src/views/DashboardView.vue, app/api/sessions.py, app/api/sop.py
- **API References:** GET /v1/sessions, GET /v1/sop/dashboard-summary
- **Database References:** sessions, sop_state

### Q: How does My Queue decide an item is overdue, and how is "time in stage" shown?
- **Verified Answer:** The server sets `overdue_hours = round(elapsed - sla, 1)` only when elapsed exceeds the stage SLA (else null), and the row shows a "+Nh OVERDUE" pill. "Time in stage" is computed client-side from `entered_current_at` (minutes under 1h, decimal hours under 24h, else `Xd Yh`), clamped to non-negative to absorb clock skew.
- **Supporting Evidence:** server overdue ([app/api/queue.py:127-131](../../app/api/queue.py#L127)); pill ([frontend/src/views/QueueView.vue:139-143](../../frontend/src/views/QueueView.vue#L139)); `hoursInStage` ([:77-88](../../frontend/src/views/QueueView.vue#L77)).
- **Source Files:** app/api/queue.py, frontend/src/views/QueueView.vue
- **API References:** GET /v1/queue/mine
- **Database References:** sop_state

### Q: What does My Queue deliberately exclude?
- **Verified Answer:** Soft-deleted sessions (`deleted_at IS NULL`), sessions in the terminal `complete` stage, and group assignments (`group:NAME` — group expansion is deferred to a future roster table). Results are capped at 200 rows.
- **Supporting Evidence:** filters + LIMIT ([app/api/queue.py:53-58](../../app/api/queue.py#L53), [:106-109](../../app/api/queue.py#L106)).
- **Source Files:** app/api/queue.py
- **API References:** GET /v1/queue/mine
- **Database References:** sessions, sop_state

### Q: Does the dashboard's "Jobs Queue" widget show real Celery activity?
- **Verified Answer:** No. It is a static "Celery queue is empty." placeholder; there is no Celery introspection wired into the dashboard.
- **Supporting Evidence:** static text ([frontend/src/views/DashboardView.vue:337](../../frontend/src/views/DashboardView.vue#L337)).
- **Source Files:** frontend/src/views/DashboardView.vue
- **API References:** none
- **Database References:** none

---

## Compliance

### Q: Does viewing the dashboard or my queue create an audit record?
- **Verified Answer:** No. Both surfaces are strictly read-only. `dashboard_summary` is documented "Reads only; no audit_events row" and `list_my_queue` "Read-only. No mutations."
- **Supporting Evidence:** ([app/api/sop.py:293](../../app/api/sop.py#L293); [app/api/queue.py:63](../../app/api/queue.py#L63)).
- **Source Files:** app/api/sop.py, app/api/queue.py
- **API References:** GET /v1/sop/dashboard-summary, GET /v1/queue/mine
- **Database References:** none

### Q: Is the overdue/SLA logic shown on the dashboard the same as the system uses for deadline enforcement?
- **Verified Answer:** Yes — by design. The dashboard's ATTN flag and the queue's OVERDUE pill re-derive overdue using the same SLA map and rule as the Celery `sop_check_deadlines_task`. The dashboard only reads; the task is what emits warnings on the Beat cadence.
- **Supporting Evidence:** shared-logic note ([app/api/sop.py:290-293](../../app/api/sop.py#L290)); task SLA map + deadline check ([app/tasks/sop_tasks.py:36-45](../../app/tasks/sop_tasks.py#L36), [:485-499](../../app/tasks/sop_tasks.py#L485)).
- **Source Files:** app/api/sop.py, app/tasks/sop_tasks.py
- **API References:** GET /v1/sop/dashboard-summary
- **Database References:** sop_state

### Q: Can one user see another user's queue?
- **Verified Answer:** No. `/v1/queue/mine` filters strictly by the email in the caller's JWT; there is no parameter to query another user's queue.
- **Supporting Evidence:** email comes from `user.email`, used as the SQL filter ([app/api/queue.py:104-112](../../app/api/queue.py#L104)).
- **Source Files:** app/api/queue.py
- **API References:** GET /v1/queue/mine
- **Database References:** sessions, sop_state

---

## Administrator

### Q: What controls access to the dashboard and queue?
- **Verified Answer:** A valid JWT, and nothing more. The router guard requires the user to be authenticated, and all three backend endpoints require the `CurrentUser` dependency, which decodes the JWT and confirms the user is active. No role is read; there are no role tiers for these screens.
- **Supporting Evidence:** route guard ([frontend/src/router/index.ts:59-62](../../frontend/src/router/index.ts#L59)); `CurrentUser` on endpoints ([app/api/sessions.py:141](../../app/api/sessions.py#L141); [app/api/sop.py:280](../../app/api/sop.py#L280); [app/api/queue.py:46](../../app/api/queue.py#L46)); `get_current_user` returns email-only `User`, reads no role ([app/auth.py:172-205](../../app/auth.py#L172), [:37-38](../../app/auth.py#L37)).
- **Source Files:** frontend/src/router/index.ts, app/auth.py, app/api/queue.py
- **API References:** GET /v1/sessions, GET /v1/sop/dashboard-summary, GET /v1/queue/mine
- **Database References:** sessions, sop_state, auth_users (active check only)
- **Permission Logic Used:** JWT presence only; no role tiers.

### Q: Is there any admin-only gate near the dashboard?
- **Verified Answer:** The only admin gate in the router is a client-side check on `/admin/help` that compares the logged-in email to the hardcoded `johndean@vin.com`. It does not apply to `/dashboard` or `/queue`. It is also UI-only — the server is the authoritative check on the help routes, not these.
- **Supporting Evidence:** `LEGACY_ADMIN_EMAIL` + `adminOnly` guard ([frontend/src/router/index.ts:51](../../frontend/src/router/index.ts#L51), [:63-66](../../frontend/src/router/index.ts#L63)).
- **Source Files:** frontend/src/router/index.ts
- **API References:** none
- **Database References:** none
- **Permission Logic Used:** Client-side LEGACY_ADMIN_EMAIL gate (on /admin/help only).

### Q: Where are the dashboard endpoints registered on the backend?
- **Verified Answer:** In `app/main.py`: the sessions router, the SOP global router (which serves `/v1/sop/dashboard-summary`), and the queue router are all included there.
- **Supporting Evidence:** includes ([app/main.py:214](../../app/main.py#L214), [:223](../../app/main.py#L223), [:232](../../app/main.py#L232)).
- **Source Files:** app/main.py
- **API References:** GET /v1/sessions, GET /v1/sop/dashboard-summary, GET /v1/queue/mine
- **Database References:** none

---

## Power User

### Q: Are the "All types / ARAV / NAVAS" chips and the time-range tabs functional filters?
- **Verified Answer:** No. Both only toggle a local component variable that nothing downstream reads. They highlight visually but do not change any displayed data.
- **Supporting Evidence:** `pipelineFilter`/`timeRange` refs toggled in template, never read by a data computed ([frontend/src/views/DashboardView.vue:40-41](../../frontend/src/views/DashboardView.vue#L40), [:184-192](../../frontend/src/views/DashboardView.vue#L184), [:245-252](../../frontend/src/views/DashboardView.vue#L245)).
- **Source Files:** frontend/src/views/DashboardView.vue
- **API References:** none
- **Database References:** none

### Q: Why does the badge on a "Your Queue" card always say "1. Prep"?
- **Verified Answer:** Because the StageBadge is hardcoded with `id="prep"` on those cards; it does not reflect the session's real current stage.
- **Supporting Evidence:** `<StageBadge id="prep" />` ([frontend/src/views/DashboardView.vue:161](../../frontend/src/views/DashboardView.vue#L161)); StageBadge renders `<order>. <name>` for the given id ([frontend/src/components/shared/StageBadge.vue:14](../../frontend/src/components/shared/StageBadge.vue#L14)).
- **Source Files:** frontend/src/views/DashboardView.vue, frontend/src/components/shared/StageBadge.vue
- **API References:** none
- **Database References:** none

### Q: The queue endpoint matches my email two ways — why?
- **Verified Answer:** Because two writers store the stage assignee differently: the SOP assign-stage flow writes a nested object `{assignee, assigned_by, assigned_at}` keyed by stage, while the Settings/Celery path writes a plain email string (or `group:NAME`). The SQL `COALESCE` reads the nested `assignee` first and falls back to the flat string, so either shape matches.
- **Supporting Evidence:** dual-shape COALESCE + rationale ([app/api/queue.py:79-105](../../app/api/queue.py#L79)).
- **Source Files:** app/api/queue.py
- **API References:** GET /v1/queue/mine
- **Database References:** sop_state (assignees JSONB)
- **Permission Logic Used:** JWT email used as data filter (not a role check).

### Q: What exact fields come back from the SOP dashboard summary, and in what order?
- **Verified Answer:** A list of `{ stage, count, overdue_count }`, one entry per stage, always in canonical order: prep, copy_draft, medical, copy_final, cms, captions, qa, complete — including zero-count stages.
- **Supporting Evidence:** response model ([app/api/sop.py:273-276](../../app/api/sop.py#L273)); canonical `STAGES` ([app/api/sop.py:24](../../app/api/sop.py#L24)); fixed-order return ([:322-325](../../app/api/sop.py#L322)).
- **Source Files:** app/api/sop.py
- **API References:** GET /v1/sop/dashboard-summary
- **Database References:** sop_state

### Q: Does the dashboard survive one of its API calls failing?
- **Verified Answer:** Yes. The two mount fetches are each caught and degraded to an empty array, so if (say) the SOP summary fails, the rest of the dashboard still renders with empty SOP counts and no error screen.
- **Supporting Evidence:** `.catch(() => [])` on both calls ([frontend/src/views/DashboardView.vue:30-31](../../frontend/src/views/DashboardView.vue#L30)).
- **Source Files:** frontend/src/views/DashboardView.vue
- **API References:** GET /v1/sessions, GET /v1/sop/dashboard-summary
- **Database References:** none

---

## Source Verification
- **Files Used:** frontend/src/views/DashboardView.vue, frontend/src/views/QueueView.vue, frontend/src/components/dashboard/Sparkline.vue, frontend/src/components/shared/StageBadge.vue, frontend/src/fixtures/sop_stages.ts, frontend/src/router/index.ts, frontend/src/services/api.ts, app/api/queue.py, app/api/sop.py, app/api/sessions.py, app/tasks/sop_tasks.py, app/auth.py, app/main.py, docs/product/reporting.md (seed)
- **Components Used:** DashboardView.vue, QueueView.vue, Sparkline.vue, StageBadge.vue
- **APIs Used:** GET /v1/sessions, GET /v1/sop/dashboard-summary, GET /v1/queue/mine
- **Database Tables Used:** sessions, sop_state, auth_users (active check only)
- **Permission Logic Used:** JWT presence only via CurrentUser (no role read); client-side LEGACY_ADMIN_EMAIL gate exists only on /admin/help.
- **Confidence Score:** High — every answer is grounded in a cited source line; placeholder vs. live behavior verified in DashboardView.vue.
- **Evidence Links:** [DashboardView.vue:30-97](../../frontend/src/views/DashboardView.vue#L30), [DashboardView.vue:59](../../frontend/src/views/DashboardView.vue#L59), [queue.py:45-143](../../app/api/queue.py#L45), [sop.py:279-325](../../app/api/sop.py#L279), [sessions.py:138-175](../../app/api/sessions.py#L138), [auth.py:37-208](../../app/auth.py#L37), [router/index.ts:51-66](../../frontend/src/router/index.ts#L51)
