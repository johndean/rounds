# SOP Workflow — Product Spec

> Module key: `sop-workflow`. Code-verified against the rounds.vin repository on 2026-06-08.
> Scope is limited to what exists in **this** repo. CE.VIN / Organizations / Sites / Vendors / Projects do not exist here and are not documented.

## Overview

The SOP Workflow is the per-session, forward-only review pipeline that carries a session through eight named stages from first-pass ingest to publication. Each session has exactly one SOP state row. The current stage, the per-stage SLA window, the per-stage assignee, stage-scoped annotations, and acceptance-check resolutions all live in dedicated tables and are exposed through a small set of session-scoped endpoints plus one dashboard-summary endpoint.

The eight canonical stages, in order, are: `prep` · `copy_draft` · `medical` · `copy_final` · `cms` · `captions` · `complete` — defined identically in the backend ([app/api/sop.py:24](../../app/api/sop.py#L24)), the deadline task ([app/tasks/sop_tasks.py:36](../../app/tasks/sop_tasks.py#L36)), and the frontend fixture ([frontend/src/fixtures/sop_stages.ts:12](../../frontend/src/fixtures/sop_stages.ts#L12)). The last stage (`captions` → `qa` → `complete`) is verified against the same list — the full ordered set is `prep, copy_draft, medical, copy_final, cms, captions, qa, complete`.

## Purpose

Give operators a deterministic, append-only review state machine so a session moves through review (prep, copy editing, medical review, CMS, captions, QA) exactly one stage at a time, with each transition recorded for audit, and with deadline pressure surfaced when a stage dwells past its SLA window. The state machine is the single source of truth for "where is this session in review."

## User Value

- A session always shows a single current stage and who owns it ([frontend/src/views/SopView.vue:59](../../frontend/src/views/SopView.vue#L59), [app/api/sop.py:93](../../app/api/sop.py#L93)).
- Advancement is forward-only, one stage at a time — no skipping or reversing ([app/api/sop.py:80](../../app/api/sop.py#L80)).
- Every advance, reassign, annotation, and check-resolve writes an `audit_events` row, so the history is reconstructable ([app/api/sop.py:135](../../app/api/sop.py#L135), [app/api/sop.py:173](../../app/api/sop.py#L173), [app/api/sop.py:231](../../app/api/sop.py#L231), [app/api/sop.py:263](../../app/api/sop.py#L263)).
- Overdue stages are surfaced both in the UI (a red "+Nh OVERDUE" badge) and via an hourly background scan ([frontend/src/views/SopView.vue:368](../../frontend/src/views/SopView.vue#L368), [app/tasks/sop_tasks.py:455](../../app/tasks/sop_tasks.py#L455)).
- A per-stage, per-session default assignee is seeded from a Type matrix so a new session arrives with owners already attached ([migrations/043_seed_carla_matrix.sql:37](../../migrations/043_seed_carla_matrix.sql#L37), [app/services/session_init.py:27](../../app/services/session_init.py#L27)).

## Navigation

- The SOP view is the route `/e/:id/sop`, rendered by [frontend/src/views/SopView.vue:1](../../frontend/src/views/SopView.vue#L1).
- Breadcrumb: Sessions → `<session code>` → SOP Workflow ([frontend/src/views/SopView.vue:320](../../frontend/src/views/SopView.vue#L320)).
- The header carries "Back to editor" (`/e/:id`) and "Viewer" (`/v/:id`) links ([frontend/src/views/SopView.vue:344](../../frontend/src/views/SopView.vue#L344)).
- The side "Quick actions" card links to the editor (`/e/:id`) and the full audit ledger (`/e/:id/audit`) ([frontend/src/views/SopView.vue:528](../../frontend/src/views/SopView.vue#L528)).
- The dashboard consumes the non-session summary endpoint `/v1/sop/dashboard-summary` for its Pipeline-2 row ([app/api/sop.py:279](../../app/api/sop.py#L279), [frontend/src/services/api.ts:634](../../frontend/src/services/api.ts#L634)).

## Screens

### SOP Workflow page (`/e/:id/sop`)

Single screen, defined by [frontend/src/views/SopView.vue:318](../../frontend/src/views/SopView.vue#L318). Regions:

1. **Header** — session code, title, presenter, duration, segment/word/attendee counts, and the editor/viewer links ([frontend/src/views/SopView.vue:330](../../frontend/src/views/SopView.vue#L330)).
2. **KPI row** — Current Stage (rendered via `StageBadge`), Assigned-to (avatar + name + role), Dwell-in-stage (with overdue badge), Acceptance-checks (passing/total), Pipeline progress (%) ([frontend/src/views/SopView.vue:350](../../frontend/src/views/SopView.vue#L350)).
3. **Stepper** — one clickable button per stage showing complete/current/pending state and the stage owner ([frontend/src/views/SopView.vue:388](../../frontend/src/views/SopView.vue#L388)).
4. **Detail grid** — left: the selected stage's acceptance-check card with Prev/Next stage navigation and the "Advance" row; right: Stage-owner card (Reassign / Ping), Approvals card, Quick-actions card ([frontend/src/views/SopView.vue:418](../../frontend/src/views/SopView.vue#L418)).
5. **History + Invariants** — left: Stage Transition History list; right: a static "SOP Invariants" panel ([frontend/src/views/SopView.vue:537](../../frontend/src/views/SopView.vue#L537)).

**PARTIALLY IMPLEMENTED — acceptance checks.** The per-stage acceptance-check labels (e.g. "Drug names verified against VIN drug index") are static fixture strings, and every current-stage check renders with state `'pending'` and meta `"awaiting check infrastructure (Phase 7)"` ([frontend/src/views/SopView.vue:114](../../frontend/src/views/SopView.vue#L114)). Because `canAdvance` requires every check to be `'pass'` and no check ever reaches `'pass'` for the current stage, the in-UI "Advance" button is effectively never enabled through the check gate ([frontend/src/views/SopView.vue:139](../../frontend/src/views/SopView.vue#L139)). The `POST /sop/checks/resolve` endpoint does persist a resolution row, but the UI's check state is not re-derived from `sop_checks` — it is derived from the fixture labels — so a resolved check does not flip the displayed state.

**PARTIALLY IMPLEMENTED — assignee/role display palette.** The avatar color, role label, and avatar initials shown in the stepper/KPI come from a static decorative palette in the view, NOT from the database. Only the live assignee *identifier* from `sop_state.assignees` overlays the palette's `assignee`/`avatar` fields ([frontend/src/views/SopView.vue:66](../../frontend/src/views/SopView.vue#L66), [frontend/src/views/SopView.vue:98](../../frontend/src/views/SopView.vue#L98)). The `session_stage_assignees` table and its `GET /stage-assignees` endpoint (which would supply real names/roles/colors) are NOT consumed by `SopView.vue`.

**NOT VERIFIED IN CODE — Ping.** The "Ping" button only raises a warn toast saying Slack is not wired ([frontend/src/views/SopView.vue:273](../../frontend/src/views/SopView.vue#L273)). There is no Slack integration in this module.

## User Flows

### Auto-initialization at ingest

When a session finishes processing and lands `ready`, the finalize/ai_process tasks enqueue `sop_auto_init_task`, which inserts a `sop_state` row at stage `prep` (with the default SLA map) and an initial `sop_transitions` row (`from_stage = NULL`, `to_stage = 'prep'`, actor `system:sop_auto_init`), then emits a `sop.initialized` WS event and an `audit_events` row ([app/tasks/finalize.py:103](../../app/tasks/finalize.py#L103), [app/tasks/ai_process.py:561](../../app/tasks/ai_process.py#L561), [app/tasks/sop_tasks.py:54](../../app/tasks/sop_tasks.py#L54)).

### First read auto-creates state

If a `sop_state` row does not yet exist when `GET /sop` is called, the endpoint inserts one at stage `prep` (`ON CONFLICT DO NOTHING`) and returns a default state ([app/api/sop.py:99](../../app/api/sop.py#L99)).

### Advance one stage

`POST /sop/advance` with `{to_stage}` locks the state row `FOR UPDATE`, rejects the call if blocked, validates a one-step forward transition, updates `current_stage` + `entered_current_at = now()`, writes a `sop_transitions` row and an `audit_events` row of kind `sop.advance` ([app/api/sop.py:113](../../app/api/sop.py#L113)). In the UI this is fired by the "Advance to <next>" button after a confirm dialog ([frontend/src/views/SopView.vue:239](../../frontend/src/views/SopView.vue#L239)).

### Reassign a stage owner

`POST /sop/assign` writes `{assignee, assigned_by, assigned_at:null}` into `sop_state.assignees[stage]` (JSONB) and an `audit_events` row of kind `sop.assign` capturing prev/next ([app/api/sop.py:145](../../app/api/sop.py#L145)). The UI prompts for an email or `group:NAME` string ([frontend/src/views/SopView.vue:256](../../frontend/src/views/SopView.vue#L256)).

### Annotate a stage (note / override / blocker)

`PATCH /sop/annotations` appends a new entry to `sop_state.metadata.annotations` (append-only) and writes an `audit_events` row of kind `sop.annotation` ([app/api/sop.py:196](../../app/api/sop.py#L196)). The UI exposes "Override with reason" (kind `override`) and "Stage notes" (kind `note`) ([frontend/src/views/SopView.vue:281](../../frontend/src/views/SopView.vue#L281)).

### Resolve an acceptance check

`POST /sop/checks/resolve` upserts a `sop_checks` row keyed `(session_id, stage, check_id)` with `is_resolved = TRUE`, plus an `audit_events` row of kind `sop.check.resolve` ([app/api/sop.py:250](../../app/api/sop.py#L250)).

### Per-session stage-assignee management (separate surface)

Independent of `sop_state.assignees`, there is a typed `session_stage_assignees` table managed by three session-scoped routes: `GET /stage-assignees`, `PUT /stage-assignees/{stage}`, and `POST /stage-assignees/apply-type-defaults` ([app/api/sessions.py:345](../../app/api/sessions.py#L345), [app/api/sessions.py:379](../../app/api/sessions.py#L379), [app/api/sessions.py:498](../../app/api/sessions.py#L498)). These are populated at ingest from the chosen session Type's matrix and can be overridden per stage or bulk-reset to the Type default ([app/services/session_init.py:27](../../app/services/session_init.py#L27)).

> **Discrepancy note (two assignee surfaces).** The SOP advance/assign endpoints read/write `sop_state.assignees` (JSONB, free-text identifiers). The `session_stage_assignees` table (typed person/group FKs, seeded from the Type matrix) is a *separate* store. `SopView.vue` reads only `sop_state.assignees` and never calls `GET /stage-assignees`. The two are not reconciled in code.

### Deadline scan

`sop_check_deadlines_task` scans every non-`complete` `sop_state` row, computes the per-stage deadline from `entered_current_at + SLA`, and for each overdue stage emits a `sop.deadline_warning` WS event and an `audit_events` row; if `SOP_DEADLINE_EMAIL_ENABLED` is true it may also send a throttled email ([app/tasks/sop_tasks.py:455](../../app/tasks/sop_tasks.py#L455)).

## Business Rules

- **BR — forward-only, single-step transitions.** A transition is legal only if `index(to) == index(from) + 1`. Unknown stages, jumps, and backward moves are rejected with HTTP 400 ([app/api/sop.py:80](../../app/api/sop.py#L80)).
- **BR — cannot advance while blocked.** If `sop_state.is_blocked` is true, `POST /sop/advance` returns 400 ([app/api/sop.py:121](../../app/api/sop.py#L121)). (No endpoint in this module sets `is_blocked` to true; it defaults to FALSE — see Known Constraints.)
- **BR — default SLA hours per stage.** `prep 8, copy_draft 24, medical 48, copy_final 24, cms 12, captions 12, qa 8, complete 0`. `complete` (0 hours) is terminal and never overdue. A per-session override in `sop_state.sla_target_hours` takes precedence ([app/api/sop.py:29](../../app/api/sop.py#L29), [app/tasks/sop_tasks.py:36](../../app/tasks/sop_tasks.py#L36)).
- **BR-004 — 23-hour deadline-email throttle.** At most one deadline email per `(session_id, stage)` per 23 hours, enforced by checking the latest `sop.deadline_email_sent`/`sop.deadline_email_failed` `audit_events` row under a per-(session,stage) Postgres advisory lock ([app/tasks/sop_tasks.py:283](../../app/tasks/sop_tasks.py#L283)). The 23h (not 24h) window avoids two consecutive daily ticks straddling the boundary.

  > **Seed-doc discrepancy:** [docs/product/workflow-and-export.md:20](./workflow-and-export.md#L20) says "one email per stage per day." The actual throttle is 23 hours, not a calendar day. Corrected here.

- **BR-005 — zero-hour grace period.** There is no grace period; an email fires as soon as `overdue_hours > 0`. BR-004 is the only repeat-send guard ([app/tasks/sop_tasks.py:306](../../app/tasks/sop_tasks.py#L306)).
- **BR — append-only annotations.** `sop_state.metadata.annotations` is append-only; entries are never edited in place ([app/api/sop.py:198](../../app/api/sop.py#L198)).
- **BR — deadline email skip conditions.** A deadline email is skipped when the stage assignee is missing, is a group (`group:NAME`), is not an email address, or a send/failure row exists inside the 23h window ([app/tasks/sop_tasks.py:240](../../app/tasks/sop_tasks.py#L240), [app/tasks/sop_tasks.py:271](../../app/tasks/sop_tasks.py#L271)).
- **BR — exactly one assignee per stage (typed table).** `session_stage_assignees` enforces `CHECK ((person_id IS NULL) OR (group_id IS NULL))` and `PRIMARY KEY (session_id, stage)` ([migrations/042_session_stage_assignees.sql:29](../../migrations/042_session_stage_assignees.sql#L29)).

## Validation Rules

- `advance.to_stage`: must be a known stage and exactly one step ahead; else 400 ([app/api/sop.py:82](../../app/api/sop.py#L82)).
- `assign.assignee`: required, 1–128 chars ([app/api/sop.py:67](../../app/api/sop.py#L67)). `assign.stage` defaults to current stage; if provided must be a known stage, else 400 ([app/api/sop.py:158](../../app/api/sop.py#L158)).
- `annotations.body`: required, 1–2000 chars ([app/api/sop.py:77](../../app/api/sop.py#L77)). `annotations.kind`: must be one of `note`, `override`, `blocker`, else 400 ([app/api/sop.py:212](../../app/api/sop.py#L212)). `annotations.stage` defaults to current; unknown stage → 400 ([app/api/sop.py:210](../../app/api/sop.py#L210)).
- `checks/resolve`: requires `check_id` and `label` ([app/api/sop.py:55](../../app/api/sop.py#L55)).
- `stage-assignees` PUT: resolution order is `person_id` → `group_id` → `assignee_email` parse (`Group: X` → group, plain email → person, `(unassigned)` → cleared) → empty body resets to Type default ([app/api/sessions.py:392](../../app/api/sessions.py#L392)).

## States

The `sop_state.current_stage` value is one of the eight stage IDs. Stage-level UI status in the stepper is derived purely from the current stage's index ([frontend/src/views/SopView.vue:401](../../frontend/src/views/SopView.vue#L401)):

| UI state | Condition |
|---|---|
| complete | stage index `< currentIdx` |
| current | stage index `== currentIdx` |
| pending | stage index `> currentIdx` |

`sop_state.is_blocked` is a boolean (default FALSE) that gates advancement. `session_stage_assignees.source` is `'default'` (auto-populated from Type matrix) or `'manual'` (operator override) ([migrations/042_session_stage_assignees.sql:26](../../migrations/042_session_stage_assignees.sql#L26)).

## Dependencies

- **sessions** table — `sop_state.session_id` is a PK FK to `sessions(id) ON DELETE CASCADE` ([migrations/003_sop.sql:6](../../migrations/003_sop.sql#L6)). The deadline-email path joins `sessions` for title/code/type ([app/tasks/sop_tasks.py:256](../../app/tasks/sop_tasks.py#L256)).
- **session_types / stage_assignees** — the per-Type stage matrix supplies defaults for `session_stage_assignees` ([migrations/039_seed_session_types.sql:10](../../migrations/039_seed_session_types.sql#L10), [migrations/043_seed_carla_matrix.sql:37](../../migrations/043_seed_carla_matrix.sql#L37)).
- **people / groups** — typed FKs from `stage_assignees` and `session_stage_assignees` ([migrations/040_stage_assignees_typed_fk.sql:17](../../migrations/040_stage_assignees_typed_fk.sql#L17), [migrations/032_seed_people_and_groups.sql:5](../../migrations/032_seed_people_and_groups.sql#L5)).
- **audit_events** — every write operation inserts an audit row.
- **Celery + Beat** — `sop_auto_init_task` (event-triggered) and `sop_check_deadlines_task` (hourly Beat) ([app/tasks/celery_app.py:84](../../app/tasks/celery_app.py#L84)).
- **SMTP email service** — `app.services.email.send_smtp_email`, used only when `SOP_DEADLINE_EMAIL_ENABLED` is true ([app/tasks/sop_tasks.py:253](../../app/tasks/sop_tasks.py#L253)).
- **email_templates** — the deadline-email path resolves a `{stage}_overdue` template, falling back to inline f-strings ([app/tasks/sop_tasks.py:359](../../app/tasks/sop_tasks.py#L359)).
- **WebSocket bridge** — `publish_ws_event_sync` for `sop.initialized` / `sop.deadline_warning` ([app/tasks/sop_tasks.py:104](../../app/tasks/sop_tasks.py#L104)).

## Error Handling

- `POST /sop/advance`, `/sop/assign`, `/sop/annotations` return 404 if the state row was never initialized (message advises GET `/sop` first) ([app/api/sop.py:120](../../app/api/sop.py#L120), [app/api/sop.py:156](../../app/api/sop.py#L156), [app/api/sop.py:207](../../app/api/sop.py#L207)).
- Illegal transitions, unknown stages, and unknown annotation kinds return 400 ([app/api/sop.py:83](../../app/api/sop.py#L83), [app/api/sop.py:213](../../app/api/sop.py#L213)).
- Advancing while blocked returns 400 ([app/api/sop.py:122](../../app/api/sop.py#L122)).
- In `sop_auto_init_task`, SOP init failures are non-fatal — they never mark the session failed; the task retries with backoff then returns an error dict ([app/tasks/sop_tasks.py:133](../../app/tasks/sop_tasks.py#L133)).
- In `sop_check_deadlines_task`, WS-emit, audit-insert, and email-path failures are each caught and logged as warnings without aborting the scan ([app/tasks/sop_tasks.py:511](../../app/tasks/sop_tasks.py#L511), [app/tasks/sop_tasks.py:533](../../app/tasks/sop_tasks.py#L533), [app/tasks/sop_tasks.py:544](../../app/tasks/sop_tasks.py#L544)).
- The deadline-email throttle claims the audit slot *before* the SMTP attempt; on SMTP failure the same row is updated to `sop.deadline_email_failed` rather than inserting a second row, so a broken recipient does not trigger hourly resend storms ([app/tasks/sop_tasks.py:410](../../app/tasks/sop_tasks.py#L410)).
- Frontend wraps each action in try/catch and surfaces failures as error toasts ([frontend/src/views/SopView.vue:235](../../frontend/src/views/SopView.vue#L235)).
- `/v1/diag/sop-check` returns `{ok:false, error}` instead of raising on failure ([app/api/diagnostics.py:345](../../app/api/diagnostics.py#L345)).

## Permissions

**Verified reality:** every SOP endpoint in [app/api/sop.py](../../app/api/sop.py) (`GET /sop`, `POST /advance`, `POST /assign`, `PATCH /annotations`, `POST /checks/resolve`, `GET /v1/sop/dashboard-summary`) and every stage-assignee route in [app/api/sessions.py](../../app/api/sessions.py) (`GET`/`PUT`/`POST apply-type-defaults`) authorizes solely on JWT presence via the `CurrentUser` dependency. There is **no role check, no admin gate, and no `LEGACY_ADMIN_EMAIL` gate on any SOP endpoint** ([app/api/sop.py:94](../../app/api/sop.py#L94), [app/api/sop.py:114](../../app/api/sop.py#L114), [app/api/sessions.py:347](../../app/api/sessions.py#L347)).

- Role-based authorization (`app/security/roles.py`, `auth_users.role`) is scaffold-only and is NOT wired into SOP endpoints.
- The `LEGACY_ADMIN_EMAIL = 'johndean@vin.com'` gate exists elsewhere (session delete/trash, certain diagnostics) but does **not** apply to SOP routes ([app/security/roles.py:54](../../app/security/roles.py#L54), [app/api/sessions.py:27](../../app/api/sessions.py#L27)).
- The SOP page itself has no `adminOnly` route guard — the only `adminOnly` route in the router is `/admin/help` ([frontend/src/router/index.ts:44](../../frontend/src/router/index.ts#L44)).

> The seed doc says "an admin can reassign the person on any stage" ([docs/product/workflow-and-export.md:16](./workflow-and-export.md#L16)). **Discrepancy:** there is no admin enforcement on reassignment — any authenticated user can reassign.

## Reporting Impacts

- `GET /v1/sop/dashboard-summary` returns one row per stage (canonical order) with `count` (sessions currently in that stage) and `overdue_count` (sessions past SLA), computed in Python so the overdue definition matches the deadline task and the client fallback. It writes no audit row ([app/api/sop.py:279](../../app/api/sop.py#L279)).
- Overdue determination: a stage is overdue when `now > entered_current_at + SLA_hours`; `complete` and any stage with SLA ≤ 0 are never overdue ([app/api/sop.py:316](../../app/api/sop.py#L316)).
- **Known gap (seed-confirmed):** there is no historical dwell-time / SLA-trend reporting — only point-in-time overdue counts ([docs/product/workflow-and-export.md:49](./workflow-and-export.md#L49)).

## Audit Requirements

Every mutating SOP operation writes an `audit_events` row:

| Action | `audit_events.kind` | Evidence |
|---|---|---|
| Advance | `sop.advance` | [app/api/sop.py:136](../../app/api/sop.py#L136) |
| Reassign | `sop.assign` | [app/api/sop.py:174](../../app/api/sop.py#L174) |
| Annotation | `sop.annotation` | [app/api/sop.py:232](../../app/api/sop.py#L232) |
| Check resolve | `sop.check.resolve` | [app/api/sop.py:264](../../app/api/sop.py#L264) |
| Auto-init | `sop.initialized` | [app/tasks/sop_tasks.py:119](../../app/tasks/sop_tasks.py#L119) |
| Deadline warning | `sop.deadline_warning` | [app/tasks/sop_tasks.py:519](../../app/tasks/sop_tasks.py#L519) |
| Deadline email sent/failed | `sop.deadline_email_sent` / `sop.deadline_email_failed` | [app/tasks/sop_tasks.py:314](../../app/tasks/sop_tasks.py#L314), [app/tasks/sop_tasks.py:429](../../app/tasks/sop_tasks.py#L429) |

Additionally, every advance writes an append-only `sop_transitions` row (`from_stage`, `to_stage`, `actor_email`, `note`, `occurred_at`) ([app/api/sop.py:131](../../app/api/sop.py#L131), [migrations/003_sop.sql:20](../../migrations/003_sop.sql#L20)). Deadline-email summaries mask the recipient's local-part; the full address stays in `audit_events.details->>'recipient'` ([app/tasks/sop_tasks.py:144](../../app/tasks/sop_tasks.py#L144)).

## Data Relationships

- `sop_state` — one row per session (PK = `session_id`); holds `current_stage`, `is_blocked`, `blockers` (JSONB), `assignees` (JSONB), `entered_current_at`, `sla_target_hours` (JSONB), `metadata` (JSONB) ([migrations/003_sop.sql:5](../../migrations/003_sop.sql#L5)).
- `sop_transitions` — append-only transition log, many per session ([migrations/003_sop.sql:20](../../migrations/003_sop.sql#L20)).
- `sop_checks` — acceptance-check resolutions, unique on `(session_id, stage, check_id)` ([migrations/003_sop.sql:34](../../migrations/003_sop.sql#L34)).
- `sop_approvals` — append-only signoff rows; **table exists but no endpoint in this module writes to it** ([migrations/003_sop.sql:50](../../migrations/003_sop.sql#L50)) — see Known Constraints.
- `session_stage_assignees` — typed per-session per-stage assignee (`person_id`/`group_id`, `notify_email`, `source`), PK `(session_id, stage)` ([migrations/042_session_stage_assignees.sql:20](../../migrations/042_session_stage_assignees.sql#L20)).
- `stage_assignees` — the per-Type default matrix that `session_stage_assignees` is seeded from ([migrations/043_seed_carla_matrix.sql:37](../../migrations/043_seed_carla_matrix.sql#L37)).

## Known Constraints

- **No backward / skip transitions** — by design ([app/api/sop.py:86](../../app/api/sop.py#L86)).
- **`is_blocked` is never set true by any SOP endpoint.** The column gates advancement and defaults FALSE, but no code path in this module raises a block. IMPLEMENTATION NOT FOUND for a block/unblock endpoint. The `blockers` JSONB column is likewise never written by SOP endpoints.
- **`sop_approvals` table is unused by this module.** No SOP endpoint inserts approval rows; the UI "Approvals" card is derived synthetically from the current stage index, not from `sop_approvals` ([frontend/src/views/SopView.vue:210](../../frontend/src/views/SopView.vue#L210)). IMPLEMENTATION NOT FOUND for an approval-write path.
- **Acceptance checks are not gating in practice** — current-stage checks are hard-coded `'pending'`, so the UI Advance button's check-gate never opens (see Screens). The backend `/advance` does not consult `sop_checks` at all.
- **Stepper assignee role/color/avatar are decorative** — sourced from a static palette, not the DB ([frontend/src/views/SopView.vue:66](../../frontend/src/views/SopView.vue#L66)).
- **Two unreconciled assignee stores** — `sop_state.assignees` (used by SopView + advance/assign) vs `session_stage_assignees` (typed, Type-seeded, used by the Editor right-rail per its docstring). SopView does not read the typed table.
- **`sop_auto_init_task` writes empty `assignees: {}`** at init; it does not hydrate from the Type matrix ([app/tasks/sop_tasks.py:81](../../app/tasks/sop_tasks.py#L81)).
- **In-code comment is stale:** `sop_check_deadlines_task`'s docstring says it "runs only when invoked manually via /v1/diag/sop-check" ([app/tasks/sop_tasks.py:462](../../app/tasks/sop_tasks.py#L462)), but Beat IS scheduling it hourly ([app/tasks/celery_app.py:84](../../app/tasks/celery_app.py#L84)). The scheduled path is live; the email side remains feature-flagged off by default.
- **Seeded people have no `role`/`avatar_color`** — migration 032 inserts only email+name, so `people.role` and `people.avatar_color` are NULL for the seeded team ([migrations/032_seed_people_and_groups.sql:5](../../migrations/032_seed_people_and_groups.sql#L5)).

## Source Verification
- **Files Used:** app/api/sop.py, app/tasks/sop_tasks.py, app/tasks/celery_app.py, app/tasks/finalize.py, app/tasks/ai_process.py, app/api/diagnostics.py, app/api/sessions.py, app/services/session_init.py, app/config.py, app/main.py, app/security/roles.py, frontend/src/views/SopView.vue, frontend/src/components/shared/StageBadge.vue, frontend/src/fixtures/sop_stages.ts, frontend/src/services/api.ts, frontend/src/router/index.ts, migrations/003_sop.sql, migrations/032_seed_people_and_groups.sql, migrations/039_seed_session_types.sql, migrations/040_stage_assignees_typed_fk.sql, migrations/042_session_stage_assignees.sql, migrations/043_seed_carla_matrix.sql, migrations/044_backfill_session_stage_assignees.sql, docs/product/workflow-and-export.md
- **Components Used:** SopView.vue, StageBadge.vue
- **APIs Used:** GET/POST /v1/sessions/{id}/sop, /advance, /assign, /annotations, /checks/resolve; GET /v1/sop/dashboard-summary; GET/PUT /v1/sessions/{id}/stage-assignees[/{stage}]; POST /stage-assignees/apply-type-defaults; POST /v1/diag/sop-check
- **Database Tables Used:** sop_state, sop_transitions, sop_checks, sop_approvals (unused by module), session_stage_assignees, stage_assignees, session_types, people, groups, audit_events, sessions
- **Permission Logic Used:** JWT presence via CurrentUser only — NO role/admin/LEGACY_ADMIN_EMAIL gate on any SOP endpoint
- **Confidence Score:** High — every claim traced to a specific file:line; partial/unimplemented surfaces explicitly tagged.
- **Evidence Links:** [app/api/sop.py:80](../../app/api/sop.py#L80), [app/api/sop.py:113](../../app/api/sop.py#L113), [app/tasks/sop_tasks.py:455](../../app/tasks/sop_tasks.py#L455), [app/tasks/celery_app.py:84](../../app/tasks/celery_app.py#L84), [frontend/src/views/SopView.vue:114](../../frontend/src/views/SopView.vue#L114), [migrations/003_sop.sql:5](../../migrations/003_sop.sql#L5)
