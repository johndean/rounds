# Phase 1 Baseline — SopView + DashboardView (Phase 7 scope)
Generated 2026-06-04 against tip 6df4170 (post-F1.E)

Scope: read-only inventory of the surfaces Phase 7 (Workflow Automation) will touch — workflow notifications, ownership visibility, status visibility, queue visibility. No edits. Phase 7 mandate is pixel-parity / zero-unrequested-change, so this document captures the current truth before any wire-up work begins.

Tip 6df4170 already shipped: F1.S (red OVERDUE pill on SopView Dwell KPI + WS subscriber), F1.D (Pipeline 2 row backed by `GET /v1/sop/dashboard-summary`), F1.E (SMTP path `_maybe_send_deadline_email` behind `SOP_DEADLINE_EMAIL_ENABLED=False`).

---

## SopView.vue
File: `C:\Users\JohnDean\rounds\frontend\src\views\SopView.vue` (562 LOC, 109 `class=` occurrences)

### DOM map
- `<main class="page" data-screen-label="SOP Workflow">` (L287)
  - `.page-eyebrow` — breadcrumb Sessions / {code} / SOP Workflow (L288-294)
  - Loading skeleton (L296) shown until `loading` flips false
  - `.sop-header` (L298) — `.sop-header__left` (code/title/meta), `.sop-header__right` (Back to editor / Viewer)
  - `.sop-kpis` (L318) — 5 KPI tiles:
    1. Current Stage (`.sop-kpi__value` with `<StageBadge>`)
    2. Assigned to (avatar + name + role) — **OWNERSHIP VISIBILITY surface**
    3. Dwell in stage — **STATUS VISIBILITY surface; F1.S OVERDUE pill renders here** (L334-339, `data-test-id="sop-overdue-badge"`)
    4. Acceptance checks (pass/total + blocker count)
    5. Pipeline progress (% + progress bar)
  - `.sop-stepper` (L356) — 8 step buttons (`role="list"`), each a `<button class="sop-step">` with `is-current` / `is-done` / `is-pending` / `is-selected` modifier classes; per-step owner avatar + assignee name
  - `.sop-detail-grid` (L386) — two-column:
    - Left: `.sop-check-card` — stage header + per-check rows (`.sop-check.is-{pass|fail|pending}`) + `.sop-advance-row` (`is-ready` | `is-blocked`)
    - Right: `.sop-side` containing 3 `.card`s:
      - Stage owner card (`.sop-owner-card`) — **OWNERSHIP** + Reassign/Ping actions + SLA / Status meta
      - Approvals card — list of `.sop-approval` rows
      - Quick actions card — Open editor, Audit ledger, Override, Notes
  - Grid `1.4fr 1fr` (L505) — Stage Transition History `.sop-transition` + SOP Invariants `.sop-invariant`

### Class / test-id inventory
- Test-ids: `sop-overdue-badge` (L336), `sop-resolve-{label-slice}` (L429), `sop-advance` (L446). That's it — three.
- Distinctive classes: `sop-header`, `sop-kpis`, `sop-kpi__{label,value,sub,progress}`, `sop-stepper`, `sop-step{__n,__name,__meta,__owner}`, `sop-avatar` (`--sm`/`--lg`), `sop-check{__icon,__name,__meta}`, `sop-advance-row` (`is-ready`/`is-blocked`), `sop-owner-card`, `sop-owner`, `sop-owner-actions`, `sop-owner-meta`, `sop-lbl`, `sop-approval` (`__check`), `sop-transition{__t,__main,__actor}`, `sop-invariant`, plus shared `card`, `chip` (`--blue|--green|--ghost`), `btn` (`--primary|--secondary|--ghost`, `--sm`).

### Interactive elements
| Element | Action | Wiring |
|---|---|---|
| Stage buttons in stepper | `@click="selectedStage = s.id"` | client-only view selection |
| Prev / Next stage nav | step ± 1 | client-only |
| Resolve check button | `resolveCheck(label)` → `POST /v1/sessions/{id}/sop/checks/resolve` | real |
| Advance to next stage | `advance()` → `POST /v1/sessions/{id}/sop/advance` (confirm modal first) | real |
| Reassign | `reassign(name)` → window.prompt → `POST /v1/sessions/{id}/sop/assign` | real (writes `sop_state.assignees[stage]`) |
| Ping | `ping(name)` → toast warn "Slack not wired" | **not wired** |
| Override with reason | `addOverride()` → window.prompt → `PATCH /v1/sessions/{id}/sop/annotations` (kind=override) | real |
| Stage notes | `addNote()` → window.prompt → `PATCH /sop/annotations` (kind=note) | real |
| Open editor / Audit ledger / Viewer | RouterLinks | client-only |

### WS event handlers (incl. freshly-shipped sop.deadline_warning subscriber)
Single subscriber at L170-176:
```ts
useWsSubscriber(props.id, {
  'sop.deadline_warning': (msg) => {
    const stage = typeof msg.stage === 'string' ? msg.stage : '';
    const hours = typeof msg.overdue_hours === 'number' ? msg.overdue_hours : 0;
    if (stage) overdueByStage.value = { ...overdueByStage.value, [stage]: hours };
  },
});
```
The `currentOverdueHours` computed (L153-168) merges WS-reported hours with a client-side fallback computed from `sop_state.entered_current_at + sla` so the badge is correct on first load before the hourly beat ticks.

### Backend endpoints called
- `GET /v1/sessions/{id}` (via `sessionsApi.get`)
- `GET /v1/sessions/{id}/sop` (via `sopApi.state`)
- `POST /v1/sessions/{id}/sop/advance`
- `POST /v1/sessions/{id}/sop/checks/resolve`
- `POST /v1/sessions/{id}/sop/assign`
- `PATCH /v1/sessions/{id}/sop/annotations`

Static SSOT data: `palette` (L66-75) — 8 hardcoded assignee/role/avatar/color rows. **Real assignees from `sop_state.assignees` JSONB are NOT rendered in SopView today** — the `assignees` field is read into `sopState.assignees` (L27) but never read out by the template. Every assignee name on the screen ("Kate Schultz", "Dr. Mueller", etc.) is from the static palette.

---

## DashboardView.vue
File: `C:\Users\JohnDean\rounds\frontend\src\views\DashboardView.vue` (365 LOC, 111 `class=` occurrences)

### DOM map
- `<main class="page dash-page" data-screen-label="Dashboard">` (L118)
  - `.dash-header` — eyebrow date / `.dash-title` greeting / `.dash-lead` lead / "New upload" primary CTA
  - `.dash-kpis.dash-kpis--6` — 6 top KPIs (AI Sessions, SOP Sessions, Segments, Words, CMS Published, Improvement RQs) (L135)
  - `.dash-section` "Your Queue" — `.dash-queue` 3 cards (L146) — **QUEUE VISIBILITY surface**
  - `.dash-section` Pipeline — two `.dash-pipeline-card`s:
    - Pipeline 1 · AI Processing · `session.status` · 7 stages (L195)
    - Pipeline 2 · SOP Control Layer · `sop_state.stage` · 8 stages (L216) — **F1.D real-data wiring lives here**
  - `.dash-section.dash-section--ops` System overview — 6 ops KPIs + `.dash-sla` per-stage dwell-vs-target grid
  - `.dash-three` grid #1 — SOP Age Alerts / Correction Hotspots / Storage Top Sessions widgets
  - `.dash-three` grid #2 — Jobs Queue / Storage Breakdown / Assignment Coverage widgets

### Class / test-id inventory
- Test-ids: `pipe-ai-{id}` (one per AI pipeline stage button, L204), `pipe-sop-{id}` (one per SOP pipeline stage button, L225). That's it.
- Distinctive classes: `dash-page`, `dash-header`, `dash-eyebrow`, `dash-title`, `dash-lead`, `dash-kpis` (`--6`), `dash-kpi{__label,__value,__sub}`, `dash-section{__head,__title,__sub,__action,__filter,__eyebrow}` (`--ops`, `__title--big`), `dash-queue{__card,__head,__code,__title,__meta,__foot,__status}`, `dash-pipeline-card{__eyebrow}`, `dash-pipeline`, `dash-pipe-step`, `dash-pipe-circle` (`--idle|--active|--failed`, `.is-populated`, `.is-attn`), `dash-pipe-name`, `dash-pipe-code`, `dash-pipe-arrow`, `dash-pipe-attn`, `dash-tab` (`.is-active`), `dash-sla{__head,__legend,__grid,__cell,__label,__value,__bar,__foot}` (cell `--ok|--breach|--empty`), `dash-three`, `dash-widget{__head,__body}`, `dash-coverage-row{__name,__role,__load}` (`--unassigned`).

### Interactive elements
| Element | Action | Wiring |
|---|---|---|
| New upload button | `router.push('/upload')` | client-only |
| Queue card click | `router.push(q.status === 'ingesting' ? '/p/:id' : '/e/:id')` | client-only |
| Type filter chips (All types / ARAV / NAVAS) | `pipelineFilter = t` | **decorative — `pipelineFilter` is never read anywhere** |
| AI pipeline step button | `router.push('/sessions?ai={id}')` | client-only |
| SOP pipeline step button | `router.push('/sessions?stage={id}')` | client-only |
| Time-range tabs (7d/30d/90d/All) | `timeRange = t` | **decorative — `timeRange` is never read anywhere** |
| `/sessions` view-all links | `<a href="#/sessions">` (NOT RouterLink) | client-only |

### Real-data vs fixture map (per section)
| Section | Source |
|---|---|
| Top 6 KPIs · AI Sessions, SOP Sessions, Segments, Words | `sessionsApi.list({})` → `allSessions` (real) |
| Top 6 KPIs · CMS Published | derived from sessions where `status === 'complete'` (real but coarse) |
| Top 6 KPIs · Improvement RQs | hardcoded `0` (fixture) |
| Sparklines on every KPI | hardcoded empty `spark: []` (fixture) |
| `dash-lead` lead | real (counts derived from `allSessions`) |
| Your Queue cards | `allSessions.value.slice(0, 3)` — 3 most-recent globally; **NOT assignee-filtered** |
| Pipeline 1 (AI Processing) | partial real — `Transcribe` = processingCount, `Ready` = readyCount, `Failed` = failed-count; **all other stages hardcoded 0** |
| Pipeline 2 (SOP Control Layer) | **real via F1.D** — `sopApi.dashboardSummary()` → `GET /v1/sop/dashboard-summary` returns per-stage `{count, overdue_count}`; ATTN badge shows when `overdue_count > 0` |
| Operations KPIs (Discrepancies / QA Tasks / Storage / Avg Processing / Avg Feedback / Fusion Runs) | hardcoded 0 / `'—'` (fixture) |
| SLA by stage grid | derived from `SOP_STAGES` with `dAvg: null, sess: 0, state: 'empty'` (fixture) |
| SOP Age Alerts / Correction Hotspots / Storage Top Sessions | hardcoded "No data yet." (fixture) |
| Jobs Queue widget | hardcoded "Celery queue is empty." (fixture) |
| Storage Breakdown | hardcoded "No data yet." (fixture) |
| Assignment Coverage | one row `Unassigned: {aiCount}` — partial real but only shows the catch-all bucket |

### Pipeline 2 wiring (post-F1.D)
- `sopApi.dashboardSummary()` fetched in `onMounted` parallel with `sessionsApi.list({})`, both swallow errors to `[]`.
- `sopPipeline` computed (L90-97) maps each `SOP_STAGES` entry to `{id, count, attn: overdue_count > 0}` by indexing into the response.
- Backend handler `app/api/sop.py::dashboard_summary` (L279-325) scans `sop_state`, computes overdue in Python using `_DEFAULT_SLA_HOURS` keyed by stage with per-row override from `sla_target_hours`. Mirror logic in `sop_tasks.py::sop_check_deadlines_task` and SopView client fallback — one definition replicated in three call sites.
- The `is-attn` class is the only new visual signal; circle uses `dash-pipe-circle--active` when count > 0 else `--idle`.

---

## Notification surface — what exists today?

### Email surfaces
- `app/services/email.py::send_smtp_email` — sync SMTP helper, never raises, returns `{ok, error, latency_ms}`. Reads `SMTP_HOST/PORT/FROM/USERNAME/PASSWORD` from env. Plain `MIMEMultipart("alternative")` with `text_body` + optional `html_body`.
- `app/api/email_debug.py` — admin diagnostic surface (config check, test send).
- `app/api/email_templates.py` — full CRUD on `email_templates` table (migration 048) for **per-Type × per-Stage stage-notification templates** (see below).
- `app/tasks/sop_tasks.py::_maybe_send_deadline_email` (F1.E) — the only live send path consuming a template-shaped subject/body, **but it does NOT yet call the template resolver** — subject + body are constructed inline via f-strings (L195-207). Feature-flagged off (`SOP_DEADLINE_EMAIL_ENABLED=False`). Throttle: one email per (session_id, stage) per 23h, gated by `audit_events.kind='sop.deadline_email_sent'`.

### Template engine
- **No Jinja2 / no Handlebars / no `render_template`.** Backend uses f-strings everywhere.
- BUT: a structured template *table* exists with two-tier resolution (per-Type override → default fallback). See below.

### Configurable-template UI
- **YES — `frontend/src/components/settings/EmailBuilder.vue` (432 LOC)** under Settings → Email templates, drilled in via `SectionEmail.vue`.
- API client `emailTemplatesApi` in `services/api.ts` (L728-772) — `list/get/add/update/remove/resolve` against `/v1/email-templates*`.
- Backend `app/api/email_templates.py` — admin-only (`ADMIN_EMAIL = "johndean@vin.com"`), 8 valid stages (`prep` … `complete`), `(session_type_id, stage_id, locale)` unique with `session_type_id NULL` = default; PUT/POST/DELETE write `audit_events` `settings.email_templates.{add,update,remove}` rows.
- POST `/v1/email-templates/resolve` returns `{...template, resolved_from: 'per_type' | 'default'}` — explicitly built so "the EmailBuilder preview AND the future stage-transition Celery hook share the resolution logic" (per docstring L246-249). **That stage-transition hook does not yet exist.**

### In-app / push
- **No.** `toast.push` (`useToast` composable) is the only in-app surface — transient bottom-corner messages for user-triggered actions. No persistent in-app notification list / bell / inbox / unread badge.
- WS events deliver real-time stage updates (`sop.initialized`, `sop.deadline_warning`, `session_failed`) but no dedicated subscriber turns them into persistent UI notifications — `sop.deadline_warning` only colors a KPI on SopView, doesn't notify the dashboard.

---

## Ownership / status / queue visibility today

### Ownership
- **SopView KPI tile #2 (`Assigned to`)** — `SopView.vue:325-331` — shows `stageMeta[current.id].assignee` (from static `palette`), **NOT `sop_state.assignees`** despite the data being loaded.
- **SopView stepper per-step owner** — `SopView.vue:375-382` — same static `palette`.
- **SopView "Stage owner" right-side card** — `SopView.vue:453-473` — same static `palette`, plus Reassign / Ping buttons.
- **Reassign IS wired** to `POST /v1/sessions/{id}/sop/assign` which writes to `sop_state.assignees[stage]` and an `audit_events` `sop.assign` row — but the write-side has no read-side. The next page load shows the same hardcoded palette name.
- **Dashboard Assignment Coverage widget** — `DashboardView.vue:350-361` — single hardcoded "Unassigned: {aiCount}" row.
- **No avatars/owners on the Dashboard Queue cards** — presenter is rendered in the foot, not assignee.

### Status
- **SopView**: Current Stage KPI (StageBadge), per-step badges (`is-current` / `is-done` / `is-pending` / `is-selected`), per-check state (`is-pass` / `is-fail` / `is-pending`), advance row (`is-ready` / `is-blocked`), Dwell KPI with OVERDUE pill (F1.S).
- **DashboardView**: AI Pipeline 1 row (idle/active/failed per stage), SOP Pipeline 2 row (idle/active + `is-attn`), per-session status text in queue card meta + foot, SLA grid (all `--empty` today).
- **Status drives no notification fan-out today** — only the FE renders state visually; no transition triggers a notification beyond the F1.E SMTP path (off).

### Queue
- **No per-user / "your queue" view.** `frontend/src/router/index.ts` has no `/queue`, `/inbox`, `/my-tasks`, or `/mine` route.
- The Dashboard "Your Queue" section is `allSessions.slice(0, 3)` — most-recent globally, not assignee-filtered. (React SSOT `docs/port-source/dashboard.jsx` is the same — hardcoded `queue` fixture array.)
- `SessionsView.vue` is the only list view; takes URL query params (`?ai=...`, `?stage=...`) for filtering by pipeline stage, but no `?assignee=me`-style filter exists in the FE today.
- **No backend endpoint returns "items assigned to me."** No grep hit for `assigned_to_me` / `MyTasks` / `/queue` / `/inbox` outside legacy MIC plan docs.

---

## Beat schedule (from `app/tasks/celery_app.py`)

Two entries (L70-88):

| entry name | task name | schedule | queue | notes |
|---|---|---|---|---|
| `upload-watchdog` | `rounds.tasks.upload_watchdog` | `float(settings.UPLOAD_WATCHDOG_INTERVAL_SEC)` (default `60.0`s) | `celery` | Default-OFF via `UPLOAD_WATCHDOG_ENABLED=False`; the beat tick still fires but the task body no-ops when disabled |
| `sop-check-deadlines` | `rounds.tasks.sop.check_deadlines` | `3600.0` (every hour) | `celery` | Emits `sop.deadline_warning` WS + `audit_events` per overdue stage. SMTP send via `_maybe_send_deadline_email` gated by `SOP_DEADLINE_EMAIL_ENABLED=False` |

Single-worker replica per `railway.json` keeps beat correctness without leader election.

---

## Phase 7 gap analysis

| Phase 7 requirement | Exists today | Needs building | Needs only wiring |
|---|---|---|---|
| Automatic notifications (workflow events trigger email) | Hourly deadline notifications scaffolded (F1.E, off) | Stage-transition trigger (no `on_advance` hook fires email today); per-event policy (which kinds fire mail) | Flip `SOP_DEADLINE_EMAIL_ENABLED=True` after stakeholder review; wire `advance` endpoint to template resolver + `send_smtp_email` |
| Configurable templates | Full CRUD UI (`EmailBuilder.vue`) + API (`email_templates.py`) + `email_templates` table (migration 048) + `resolve` endpoint | Nothing — already shipped end-to-end | Connect deadline email path to `resolve_template` (currently hardcoded f-strings in `_maybe_send_deadline_email`) |
| Workflow-specific templates | Per-Type × per-Stage already supported (`session_type_id NULL` = default, UUID = override) | Nothing | Same wiring step as above |
| Ownership visibility | KPI tile + stepper + side card already render owners, Reassign endpoint persists | **Read side from `sop_state.assignees` JSONB** — replace static `palette` with merged real-data → palette fallback | Same file edit, one location |
| Status visibility | Comprehensive — KPI, stepper, checks, advance row, badges, OVERDUE pill | Persistent notification surface (bell / inbox / unread-count) if Phase 7 calls for it | — |
| Queue visibility | Pipeline 2 row has per-stage counts (F1.D), Dashboard "Your Queue" exists in shape | **"Your Queue" must become assignee-filtered** OR a new `/queue` route built. Backend endpoint returning "items where assignees[*] = me" does not exist yet | Once endpoint exists, swap `allSessions.slice(0,3)` for the new query |

---

## Risk notes for Phase 7

- **Pixel-parity constraint**: Phase 7's mandate prohibits dashboard redesign. The temptation to add an inbox / bell / unread-count to `AppHeader` must be resisted unless explicitly approved — any new top-bar element is by definition a dashboard-appearance change.
- **`palette` regression risk**: replacing the SopView static palette with real `sop_state.assignees` will visibly change every screen that's not been reassigned. Mitigation: render-time fallback — if `assignees[stage]` is null/missing, use the palette entry as today.
- **Three definitions of "overdue"**: `app/api/sop.py::dashboard_summary`, `app/tasks/sop_tasks.py::sop_check_deadlines_task`, and `SopView.vue`'s `_slaHoursFor` all compute overdue independently with copy-paste'd `_DEFAULT_SLA_HOURS`. Phase 7 introducing an "is the assignee overdue?" notification gate widens this — risk of drift between FE indicator, dashboard count, and email trigger. Consider consolidating before adding the fourth caller.
- **`_maybe_send_deadline_email` does not use the template resolver** — the entire `email_templates.py` surface exists for stage-notification templates, but the only live SMTP path constructs subject+body with f-strings (L195-207 of `sop_tasks.py`). Wiring it through `POST /v1/email-templates/resolve` is the simplest path to "configurable templates work end-to-end" without new infrastructure — but the resolver is `POST` and admin-gated; calling it from a worker means either an internal in-process call (`from app.api.email_templates import resolve_template`) or relaxing the admin gate, neither obvious.
- **WS fan-out is per-session-id**: `ws_bridge.py` publishes to `rounds:ws:{session_id}` and clients subscribe per-session via `useWsSubscriber(props.id, ...)`. There is no global / per-user channel — so a persistent in-app notification list requires either a polling endpoint or a new `rounds:ws:user:{email}` channel. Both are out of "pixel-parity / zero-unrequested-change" territory unless Phase 7 calls them out explicitly.
- **`pipelineFilter` and `timeRange` chips are decorative today** — `DashboardView.vue:40-41` declares them, the chips toggle them, but nothing reads them. If Phase 7 adds queue/notification scoping, these may become the natural UI handles — beware connecting them without checking SSOT alignment.
- **`AssignPayload.assignee` accepts arbitrary strings** including `"group:NAME"`, but the email path explicitly skips groups (`raw.startswith("group:")` → return). Group expansion requires a roster table that does not exist. Phase 7 should decide whether group-fan-out is in scope; the "Notify on entry" toggle on the SopView Stage owner card (L468) implies it should work.
- **Settings → Types & Stages matrix is referenced** by `SectionEmail.vue` lead copy ("Stage-level email triggers live in the Types & stage defaults matrix per Type. Each stage has a default assignee … and an optional Email toggle"). Verify the toggle persistence + read-out path is real before Phase 7 relies on it.

---

## Rollback procedure

Phase 1 (this audit) writes ONLY this Markdown file under `docs/parity-audits/`. No code, schema, env, or config changes were made by the inventory step.

To roll back the F1 commits referenced by this baseline (if a stakeholder objects after Phase 7 work begins):

1. F1.E (SMTP path) — kept dormant by `SOP_DEADLINE_EMAIL_ENABLED=False`; no rollback needed unless the flag was flipped. To revert code, `git revert` the commit that added `_maybe_send_deadline_email` in `app/tasks/sop_tasks.py` and `app/services/email.py`.
2. F1.D (Pipeline 2 real data) — revert the commit that added `dashboard_summary` to `app/api/sop.py` and the `sopApi.dashboardSummary` block in `DashboardView.vue` `onMounted` (lines 27-38 + 90-97). The fallback `[].catch(() => [])` keeps the UI alive.
3. F1.S (OVERDUE pill) — revert the commit that added the `useWsSubscriber` block (L170-176), `currentOverdueHours` computed (L153-168), and the inline `data-test-id="sop-overdue-badge"` span (L336-338). All other SopView code is untouched.
4. Beat schedule — to disable hourly SOP scan without code revert, comment out the `sop-check-deadlines` entry in `app/tasks/celery_app.py` (L83-87) and redeploy the worker. The task itself remains callable via `/v1/diag/sop-check`.

For this audit's deliverable specifically: `rm docs/parity-audits/phase1-sop-dashboard-baseline-2026-06-04.md`. No other artifacts.
