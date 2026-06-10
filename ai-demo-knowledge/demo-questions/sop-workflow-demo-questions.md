# SOP Workflow — Demo Questions (Code-Verified)

> Module key: `sop-workflow`. Every answer below is traceable to repo code as of 2026-06-08.
> Only questions with a code-true answer are included. Personas with nothing code-true are omitted.

---

## User

### Q1. How does a session move from one review stage to the next?
**Verified Answer:** A user clicks "Advance to <next stage>" on the SOP page, confirms, and the session moves exactly one stage forward. Movement is forward-only and one step at a time — you cannot skip ahead or go back. The transition is recorded in history with your email as the actor.
**Supporting Evidence:** `_validate_transition` requires `index(to) == index(from)+1`; `POST /advance` writes a `sop_transitions` row and an audit row ([app/api/sop.py:80](../../app/api/sop.py#L80), [app/api/sop.py:113](../../app/api/sop.py#L113)). UI confirm + advance at [frontend/src/views/SopView.vue:239](../../frontend/src/views/SopView.vue#L239).
**Source Files:** app/api/sop.py, frontend/src/views/SopView.vue
**API References:** POST /v1/sessions/{id}/sop/advance
**Database References:** sop_state, sop_transitions, audit_events

### Q2. What are the eight workflow stages?
**Verified Answer:** Prep, Copy edit (draft), Medical review, Copy edit (final), CMS published, Captions on video, QA, Complete — in that order.
**Supporting Evidence:** [frontend/src/fixtures/sop_stages.ts:12](../../frontend/src/fixtures/sop_stages.ts#L12); backend stage list [app/api/sop.py:24](../../app/api/sop.py#L24).
**Source Files:** frontend/src/fixtures/sop_stages.ts, app/api/sop.py
**API References:** GET /v1/sessions/{id}/sop
**Database References:** sop_state.current_stage

### Q3. How do I see who owns the current stage and how long it has been there?
**Verified Answer:** The SOP page's KPI row shows "Assigned to" (avatar + name + role) and "Dwell in stage" in hours, computed from when the stage was entered. If the stage is past its SLA, a red "+Nh OVERDUE" badge appears.
**Supporting Evidence:** KPI row + overdue badge [frontend/src/views/SopView.vue:356](../../frontend/src/views/SopView.vue#L356), [frontend/src/views/SopView.vue:368](../../frontend/src/views/SopView.vue#L368); dwell from `entered_current_at` [frontend/src/views/SopView.vue:163](../../frontend/src/views/SopView.vue#L163).
**Source Files:** frontend/src/views/SopView.vue
**API References:** GET /v1/sessions/{id}/sop
**Database References:** sop_state.entered_current_at, sop_state.assignees

### Q4. Can I reassign a stage to someone else?
**Verified Answer:** Yes. The Stage-owner card has a "Reassign" button that prompts for an email or `group:NAME`. The new assignee is stored and an audit row records who reassigned and the old/new values.
**Supporting Evidence:** UI prompt [frontend/src/views/SopView.vue:256](../../frontend/src/views/SopView.vue#L256); backend writes `sop_state.assignees[stage]` + `sop.assign` audit row [app/api/sop.py:145](../../app/api/sop.py#L145).
**Source Files:** frontend/src/views/SopView.vue, app/api/sop.py
**API References:** POST /v1/sessions/{id}/sop/assign
**Database References:** sop_state.assignees, audit_events

### Q5. Can I leave a note or record an override on a stage?
**Verified Answer:** Yes. "Stage notes" adds a note and "Override with reason" records an override; both are appended to the stage's annotation history (append-only, never edited in place) and audited.
**Supporting Evidence:** `addNote`/`addOverride` [frontend/src/views/SopView.vue:281](../../frontend/src/views/SopView.vue#L281); backend append + `sop.annotation` audit [app/api/sop.py:196](../../app/api/sop.py#L196).
**Source Files:** frontend/src/views/SopView.vue, app/api/sop.py
**API References:** PATCH /v1/sessions/{id}/sop/annotations
**Database References:** sop_state.metadata.annotations, audit_events

### Q6. Why is the "Ping" button not doing anything?
**Verified Answer:** Ping is not wired. Clicking it shows a warning toast saying Slack integration is out of scope. There is no Slack integration in the codebase.
**Supporting Evidence:** [frontend/src/views/SopView.vue:273](../../frontend/src/views/SopView.vue#L273).
**Source Files:** frontend/src/views/SopView.vue
**API References:** none
**Database References:** none

---

## Executive

### Q1. What guarantees that review steps are never skipped?
**Verified Answer:** The backend enforces forward-only, single-step transitions: a move is legal only if the target stage is exactly one position ahead of the current stage. Jumps and backward moves are rejected with an HTTP 400. Every advance also writes an append-only transition record.
**Supporting Evidence:** [app/api/sop.py:80](../../app/api/sop.py#L80), [app/api/sop.py:131](../../app/api/sop.py#L131).
**Source Files:** app/api/sop.py
**API References:** POST /v1/sessions/{id}/sop/advance
**Database References:** sop_transitions

### Q2. How many sessions are sitting in each review stage right now, and how many are overdue?
**Verified Answer:** The dashboard summary returns one row per stage with a live count and an overdue count. A stage is overdue when its dwell time exceeds the per-stage SLA.
**Supporting Evidence:** [app/api/sop.py:279](../../app/api/sop.py#L279); overdue computed at [app/api/sop.py:316](../../app/api/sop.py#L316).
**Source Files:** app/api/sop.py, frontend/src/services/api.ts
**API References:** GET /v1/sop/dashboard-summary
**Database References:** sop_state

### Q3. Is there historical reporting on how long stages take?
**Verified Answer:** No. Only point-in-time counts and overdue flags exist. There is no historical dwell-time or SLA-trend reporting in this module.
**Supporting Evidence:** dashboard summary returns only current `count`/`overdue_count` ([app/api/sop.py:322](../../app/api/sop.py#L322)); seed doc confirms the gap ([docs/product/workflow-and-export.md:49](../../docs/product/workflow-and-export.md#L49)).
**Source Files:** app/api/sop.py, docs/product/workflow-and-export.md
**API References:** GET /v1/sop/dashboard-summary
**Database References:** sop_state

### Q4. Is the full review history reconstructable for an audit?
**Verified Answer:** Yes. Every advance, reassign, annotation, and check-resolve writes a row to `audit_events`, and every advance additionally writes an append-only `sop_transitions` row. Neither is mutated after the fact.
**Supporting Evidence:** audit inserts across [app/api/sop.py:135](../../app/api/sop.py#L135), [app/api/sop.py:173](../../app/api/sop.py#L173), [app/api/sop.py:231](../../app/api/sop.py#L231), [app/api/sop.py:263](../../app/api/sop.py#L263).
**Source Files:** app/api/sop.py
**API References:** POST /advance, /assign, /annotations, /checks/resolve
**Database References:** audit_events, sop_transitions

---

## Operations

### Q1. When does a session get its SOP state, and what's the starting stage?
**Verified Answer:** When a session finishes processing and lands `ready`, an auto-init task creates the SOP state at stage `prep` with the default SLA map and an initial transition row (actor `system:sop_auto_init`). If a row already exists the task only re-emits the init event. A `GET /sop` on a session with no row will also auto-create one at `prep`.
**Supporting Evidence:** triggers [app/tasks/finalize.py:103](../../app/tasks/finalize.py#L103), [app/tasks/ai_process.py:561](../../app/tasks/ai_process.py#L561); task body [app/tasks/sop_tasks.py:54](../../app/tasks/sop_tasks.py#L54); GET auto-create [app/api/sop.py:99](../../app/api/sop.py#L99).
**Source Files:** app/tasks/sop_tasks.py, app/tasks/finalize.py, app/tasks/ai_process.py, app/api/sop.py
**API References:** GET /v1/sessions/{id}/sop
**Database References:** sop_state, sop_transitions, audit_events

### Q2. How often does the overdue scan run, and can I run it on demand?
**Verified Answer:** Celery Beat runs the deadline scan every hour (3600s). Operators can also run it synchronously via `POST /v1/diag/sop-check`, which returns the count of warnings emitted and rows scanned.
**Supporting Evidence:** beat schedule [app/tasks/celery_app.py:84](../../app/tasks/celery_app.py#L84); diag route [app/api/diagnostics.py:331](../../app/api/diagnostics.py#L331).
**Source Files:** app/tasks/celery_app.py, app/api/diagnostics.py, app/tasks/sop_tasks.py
**API References:** POST /v1/diag/sop-check
**Database References:** sop_state, audit_events

### Q3. What are the default SLA windows per stage?
**Verified Answer:** prep 8h, copy_draft 24h, medical 48h, copy_final 24h, cms 12h, captions 12h, qa 8h, complete 0h (terminal — never overdue). Any stage can be overridden per session via `sop_state.sla_target_hours`.
**Supporting Evidence:** [app/api/sop.py:29](../../app/api/sop.py#L29), [app/tasks/sop_tasks.py:36](../../app/tasks/sop_tasks.py#L36).
**Source Files:** app/api/sop.py, app/tasks/sop_tasks.py
**API References:** GET /v1/sessions/{id}/sop
**Database References:** sop_state.sla_target_hours

### Q4. What happens when the deadline scan finds an overdue stage?
**Verified Answer:** For each overdue stage it emits a `sop.deadline_warning` WebSocket event and writes a `sop.deadline_warning` audit row. If `SOP_DEADLINE_EMAIL_ENABLED` is on, it may also send a throttled email to the assignee. WS, audit, and email failures are individually caught and logged so the scan continues.
**Supporting Evidence:** [app/tasks/sop_tasks.py:500](../../app/tasks/sop_tasks.py#L500), [app/tasks/sop_tasks.py:519](../../app/tasks/sop_tasks.py#L519), [app/tasks/sop_tasks.py:540](../../app/tasks/sop_tasks.py#L540).
**Source Files:** app/tasks/sop_tasks.py
**API References:** POST /v1/diag/sop-check
**Database References:** audit_events, sop_state

### Q5. How are stage assignees set up for a new session?
**Verified Answer:** At ingest, `init_session_stages` copies the chosen session Type's `stage_assignees` matrix into `session_stage_assignees` (marked `source='default'`). If the session has no Type pinned, it falls back to the org default Type. Operators can override one stage (`PUT`) or bulk re-apply the Type matrix (`apply-type-defaults`).
**Supporting Evidence:** [app/services/session_init.py:27](../../app/services/session_init.py#L27); routes [app/api/sessions.py:379](../../app/api/sessions.py#L379), [app/api/sessions.py:498](../../app/api/sessions.py#L498); backfill for old sessions [migrations/044_backfill_session_stage_assignees.sql:16](../../migrations/044_backfill_session_stage_assignees.sql#L16).
**Source Files:** app/services/session_init.py, app/api/sessions.py, migrations/044_backfill_session_stage_assignees.sql
**API References:** GET/PUT /v1/sessions/{id}/stage-assignees[/{stage}], POST /stage-assignees/apply-type-defaults
**Database References:** session_stage_assignees, stage_assignees, session_types

### Q6. Why might an overdue stage not generate an email?
**Verified Answer:** Email sending is off by default (`SOP_DEADLINE_EMAIL_ENABLED=False`). Even when on, an email is skipped when the assignee is missing, is a group (`group:NAME`), isn't an email address, or a send/failure already happened within the last 23 hours.
**Supporting Evidence:** flag [app/config.py:110](../../app/config.py#L110); skip conditions [app/tasks/sop_tasks.py:271](../../app/tasks/sop_tasks.py#L271); 23h throttle [app/tasks/sop_tasks.py:310](../../app/tasks/sop_tasks.py#L310).
**Source Files:** app/config.py, app/tasks/sop_tasks.py
**API References:** none
**Database References:** sop_state.assignees, audit_events

---

## Finance

### Q1. Does the SOP workflow track CE hours or billing?
**Verified Answer:** No financial or CE-hour computation lives in the SOP module. One CMS-stage acceptance-check *label* reads "CE hours computed and attested," but that is a static fixture string with no backing computation in this module.
**Supporting Evidence:** label only [frontend/src/fixtures/sop_stages.ts:22](../../frontend/src/fixtures/sop_stages.ts#L22); no finance logic in [app/api/sop.py](../../app/api/sop.py).
**Source Files:** frontend/src/fixtures/sop_stages.ts, app/api/sop.py
**API References:** none
**Database References:** none

---

## Compliance

### Q1. Is the workflow audit trail tamper-resistant?
**Verified Answer:** It is append-only. `sop_transitions` rows are inserted and never updated, and `sop_state.metadata.annotations` are appended (never edited in place). Every mutating action also writes an `audit_events` row. (Note: there is no cryptographic immutability — "append-only" is enforced by code conventions and INSERT-only paths, not by DB-level write protection.)
**Supporting Evidence:** transitions INSERT [app/api/sop.py:131](../../app/api/sop.py#L131); annotations append-only [app/api/sop.py:198](../../app/api/sop.py#L198); schema [migrations/003_sop.sql:20](../../migrations/003_sop.sql#L20).
**Source Files:** app/api/sop.py, migrations/003_sop.sql
**API References:** POST /advance, PATCH /annotations
**Database References:** sop_transitions, sop_state.metadata, audit_events

### Q2. Who can advance or reassign a stage — is it restricted to admins?
**Verified Answer:** No. Every SOP endpoint authorizes on JWT presence only. There is no role check, no admin gate, and no `LEGACY_ADMIN_EMAIL` gate on any SOP route, and the SOP page has no `adminOnly` guard. Any authenticated user can advance, reassign, annotate, or resolve checks. (The seed doc's claim that "an admin can reassign" is not enforced in code.)
**Supporting Evidence:** `CurrentUser`-only deps [app/api/sop.py:114](../../app/api/sop.py#L114), [app/api/sop.py:146](../../app/api/sop.py#L146); no admin gate in the file; only `/admin/help` carries `adminOnly` [frontend/src/router/index.ts:44](../../frontend/src/router/index.ts#L44); seed claim [docs/product/workflow-and-export.md:16](../../docs/product/workflow-and-export.md#L16).
**Source Files:** app/api/sop.py, frontend/src/router/index.ts, docs/product/workflow-and-export.md
**API References:** all /v1/sessions/{id}/sop/* routes
**Database References:** none

### Q3. Are reviewer attestations / signoffs captured?
**Verified Answer:** Partially. The actor email is captured on every transition and annotation, and a `sop_approvals` table exists for signatures — but no endpoint in this module writes to `sop_approvals`, and the UI "Approvals" card is derived synthetically from the current stage index, not from real signoff rows.
**Supporting Evidence:** `sop_approvals` schema [migrations/003_sop.sql:50](../../migrations/003_sop.sql#L50); no writer found in [app/api/sop.py](../../app/api/sop.py); synthetic approvers [frontend/src/views/SopView.vue:210](../../frontend/src/views/SopView.vue#L210).
**Source Files:** migrations/003_sop.sql, app/api/sop.py, frontend/src/views/SopView.vue
**API References:** none (no approval-write endpoint — IMPLEMENTATION NOT FOUND)
**Database References:** sop_approvals (unused), sop_transitions

### Q4. Is recipient PII protected in the deadline-email audit log?
**Verified Answer:** Yes. The email recipient's local-part is masked in the audit summary (e.g. `jan***@vin.com`); the full address is kept only in `audit_events.details->>'recipient'` for operator forensics.
**Supporting Evidence:** `_mask_email` [app/tasks/sop_tasks.py:144](../../app/tasks/sop_tasks.py#L144); summary uses masked, details carries raw [app/tasks/sop_tasks.py:321](../../app/tasks/sop_tasks.py#L321).
**Source Files:** app/tasks/sop_tasks.py
**API References:** none
**Database References:** audit_events

---

## Administrator

### Q1. How do I enable deadline emails, and what's the throttle?
**Verified Answer:** Set `SOP_DEADLINE_EMAIL_ENABLED=true` (default off) in the worker env and restart. Once on, the hourly scan sends at most one email per (session, stage) per 23 hours, enforced under a per-(session,stage) Postgres advisory lock against the audit log.
**Supporting Evidence:** flag [app/config.py:110](../../app/config.py#L110); enable check [app/tasks/sop_tasks.py:542](../../app/tasks/sop_tasks.py#L542); 23h throttle + advisory lock [app/tasks/sop_tasks.py:283](../../app/tasks/sop_tasks.py#L283).
**Source Files:** app/config.py, app/tasks/sop_tasks.py
**API References:** none
**Database References:** audit_events

### Q2. Where do default stage owners come from?
**Verified Answer:** From Carla's per-Type matrix seeded into `stage_assignees` (17 conference Types + a default Type). For example, Tina Payton owns Prep/Copy/CMS on most Types, Erica Hulse owns Captions on every Type, Lacy Sanders owns QA on every Type, and the "External" group handles Medical Review on 11 Types. New sessions inherit their Type's matrix.
**Supporting Evidence:** matrix seed [migrations/043_seed_carla_matrix.sql:37](../../migrations/043_seed_carla_matrix.sql#L37); Type seed [migrations/039_seed_session_types.sql:10](../../migrations/039_seed_session_types.sql#L10); people seed [migrations/032_seed_people_and_groups.sql:5](../../migrations/032_seed_people_and_groups.sql#L5).
**Source Files:** migrations/043_seed_carla_matrix.sql, migrations/039_seed_session_types.sql, migrations/032_seed_people_and_groups.sql
**API References:** GET /v1/sessions/{id}/stage-assignees
**Database References:** stage_assignees, session_types, people, groups

### Q3. What happens to a stage assignment when I reset it to default, or when a person is deleted?
**Verified Answer:** Sending an empty assignee body (or `(unassigned)`) to the PUT route resets the stage to its Type-matrix default and flips `source` back to `'default'`. Because `person_id`/`group_id` are FKs with `ON DELETE SET NULL`, deleting a person or group leaves the row intact and renders as "(unassigned)" rather than orphaning data.
**Supporting Evidence:** reset logic [app/api/sessions.py:424](../../app/api/sessions.py#L424); SET NULL FKs [migrations/042_session_stage_assignees.sql:23](../../migrations/042_session_stage_assignees.sql#L23); JOIN-resolved label [app/api/sessions.py:368](../../app/api/sessions.py#L368).
**Source Files:** app/api/sessions.py, migrations/042_session_stage_assignees.sql
**API References:** PUT /v1/sessions/{id}/stage-assignees/{stage}
**Database References:** session_stage_assignees, people, groups

### Q4. Why is there an "is_blocked" field but no way to block a session in the UI?
**Verified Answer:** `sop_state.is_blocked` defaults FALSE and gates advancement (advancing while blocked returns 400), but no endpoint in this module sets it true and no UI exposes blocking. The `blockers` JSONB is likewise never written. It is a defined-but-unimplemented capability.
**Supporting Evidence:** gate [app/api/sop.py:121](../../app/api/sop.py#L121); column default [migrations/003_sop.sql:8](../../migrations/003_sop.sql#L8); no writer found — IMPLEMENTATION NOT FOUND.
**Source Files:** app/api/sop.py, migrations/003_sop.sql
**API References:** POST /v1/sessions/{id}/sop/advance
**Database References:** sop_state.is_blocked, sop_state.blockers

### Q5. Are the seeded team members' roles and avatar colors stored in the DB?
**Verified Answer:** No. The people seed inserts only email and name; `people.role` and `people.avatar_color` columns exist but are NULL for seeded members. The role/color/avatar shown on the SOP page come from a static decorative palette in the view, not the DB.
**Supporting Evidence:** seed inserts email+name only [migrations/032_seed_people_and_groups.sql:5](../../migrations/032_seed_people_and_groups.sql#L5); decorative palette [frontend/src/views/SopView.vue:66](../../frontend/src/views/SopView.vue#L66).
**Source Files:** migrations/032_seed_people_and_groups.sql, frontend/src/views/SopView.vue
**API References:** GET /v1/sessions/{id}/stage-assignees
**Database References:** people

---

## Power User

### Q1. Can I assign a stage to a group instead of an individual?
**Verified Answer:** Yes for the typed table — `session_stage_assignees` supports `group_id` (e.g. the "External" group seeded for Medical Review). And the SOP reassign endpoint accepts a `group:NAME` string into `sop_state.assignees`. Note: a stage assigned to a group will NOT receive a deadline email — group expansion is deferred, so group assignees are skipped in the email path.
**Supporting Evidence:** group rows in matrix [migrations/043_seed_carla_matrix.sql:175](../../migrations/043_seed_carla_matrix.sql#L175); `group:` accepted by assign UI [frontend/src/views/SopView.vue:85](../../frontend/src/views/SopView.vue#L85); group skip in email [app/tasks/sop_tasks.py:272](../../app/tasks/sop_tasks.py#L272).
**Source Files:** migrations/043_seed_carla_matrix.sql, frontend/src/views/SopView.vue, app/tasks/sop_tasks.py
**API References:** POST /sop/assign, PUT /stage-assignees/{stage}
**Database References:** session_stage_assignees, groups, sop_state.assignees

### Q2. Why are there two different places that store stage assignees?
**Verified Answer:** There are two unreconciled stores. `sop_state.assignees` (JSONB, free-text identifiers) is what the SOP advance/assign endpoints and `SopView.vue` use. `session_stage_assignees` (typed person/group FKs, seeded from the Type matrix) is the store the Editor's right-rail Admin chip uses per its docstring. `SopView.vue` does not read the typed table, so the two can diverge.
**Supporting Evidence:** SopView reads only `sop_state.assignees` [frontend/src/views/SopView.vue:98](../../frontend/src/views/SopView.vue#L98); typed table + its consumer docstring [app/api/sessions.py:350](../../app/api/sessions.py#L350); typed schema [migrations/042_session_stage_assignees.sql:1](../../migrations/042_session_stage_assignees.sql#L1).
**Source Files:** frontend/src/views/SopView.vue, app/api/sessions.py, migrations/042_session_stage_assignees.sql
**API References:** POST /sop/assign, GET /stage-assignees
**Database References:** sop_state.assignees, session_stage_assignees

### Q3. How is "overdue" computed, and why is the same logic in three places?
**Verified Answer:** Overdue means `now > entered_current_at + SLA_hours` (per-session override else the default map; SLA ≤ 0 stages never overdue). The same computation lives in the dashboard summary, the deadline task, and the SopView client fallback so all three agree on the definition.
**Supporting Evidence:** dashboard [app/api/sop.py:314](../../app/api/sop.py#L314); task [app/tasks/sop_tasks.py:492](../../app/tasks/sop_tasks.py#L492); client [frontend/src/views/SopView.vue:185](../../frontend/src/views/SopView.vue#L185).
**Source Files:** app/api/sop.py, app/tasks/sop_tasks.py, frontend/src/views/SopView.vue
**API References:** GET /v1/sop/dashboard-summary, GET /v1/sessions/{id}/sop
**Database References:** sop_state.entered_current_at, sop_state.sla_target_hours

### Q4. If I resolve a failing acceptance check, does the Advance button unlock?
**Verified Answer:** Not in the current UI. `POST /sop/checks/resolve` does persist a resolution row to `sop_checks`, but the SopView check states are derived from static fixture labels — current-stage checks render `'pending'` and are never recomputed from `sop_checks`. Since `canAdvance` requires every check to be `'pass'`, the in-UI check gate does not open from a resolve. The backend `/advance` itself does not consult `sop_checks` at all.
**Supporting Evidence:** resolve persists [app/api/sop.py:250](../../app/api/sop.py#L250); checks hard-`pending` [frontend/src/views/SopView.vue:114](../../frontend/src/views/SopView.vue#L114); `canAdvance` [frontend/src/views/SopView.vue:139](../../frontend/src/views/SopView.vue#L139); `/advance` ignores checks [app/api/sop.py:113](../../app/api/sop.py#L113).
**Source Files:** app/api/sop.py, frontend/src/views/SopView.vue
**API References:** POST /sop/checks/resolve, POST /sop/advance
**Database References:** sop_checks

### Q5. Can I override the SLA hours for a single session's stage?
**Verified Answer:** The data model supports it — `sop_state.sla_target_hours` is read with per-session overrides taking precedence over the defaults in both the dashboard summary and the deadline task. However, no endpoint in this module writes `sla_target_hours` (auto-init seeds the default map; the SOP endpoints don't expose an SLA-edit path), so today an override would have to be set out-of-band.
**Supporting Evidence:** override read [app/api/sop.py:315](../../app/api/sop.py#L315), [app/tasks/sop_tasks.py:492](../../app/tasks/sop_tasks.py#L492); auto-init writes defaults [app/tasks/sop_tasks.py:87](../../app/tasks/sop_tasks.py#L87); no SLA-write endpoint — IMPLEMENTATION NOT FOUND.
**Source Files:** app/api/sop.py, app/tasks/sop_tasks.py
**API References:** GET /v1/sessions/{id}/sop
**Database References:** sop_state.sla_target_hours

---

## Source Verification
- **Files Used:** app/api/sop.py, app/tasks/sop_tasks.py, app/tasks/celery_app.py, app/tasks/finalize.py, app/tasks/ai_process.py, app/api/diagnostics.py, app/api/sessions.py, app/services/session_init.py, app/config.py, frontend/src/views/SopView.vue, frontend/src/fixtures/sop_stages.ts, frontend/src/services/api.ts, frontend/src/router/index.ts, migrations/003_sop.sql, migrations/032_seed_people_and_groups.sql, migrations/039_seed_session_types.sql, migrations/042_session_stage_assignees.sql, migrations/043_seed_carla_matrix.sql, migrations/044_backfill_session_stage_assignees.sql, docs/product/workflow-and-export.md
- **Components Used:** SopView.vue, StageBadge.vue, sop_stages.ts fixture
- **APIs Used:** /v1/sessions/{id}/sop (GET/advance/assign/annotations/checks/resolve), /v1/sop/dashboard-summary, /v1/sessions/{id}/stage-assignees[/{stage}], /stage-assignees/apply-type-defaults, /v1/diag/sop-check
- **Database Tables Used:** sop_state, sop_transitions, sop_checks, sop_approvals (unused), session_stage_assignees, stage_assignees, session_types, people, groups, audit_events
- **Permission Logic Used:** JWT presence (CurrentUser) only — no role/admin/LEGACY_ADMIN_EMAIL gate on SOP endpoints
- **Confidence Score:** High — each answer cites specific file:line; unimplemented/partial behaviors explicitly flagged.
- **Evidence Links:** [app/api/sop.py:80](../../app/api/sop.py#L80), [app/api/sop.py:279](../../app/api/sop.py#L279), [app/tasks/sop_tasks.py:283](../../app/tasks/sop_tasks.py#L283), [app/tasks/celery_app.py:84](../../app/tasks/celery_app.py#L84), [migrations/043_seed_carla_matrix.sql:37](../../migrations/043_seed_carla_matrix.sql#L37), [frontend/src/views/SopView.vue:114](../../frontend/src/views/SopView.vue#L114)
