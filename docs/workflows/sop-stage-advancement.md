# Workflow: SOP Stage Advancement

The SOP (Standard Operating Procedure) layer is a forward-only, 8-stage workflow that tracks a session's post-ingest editorial lifecycle. It is separate from the ingest pipeline's `sessions.status` state machine — SOP state lives in its own `sop_state` table.

Stages, in order ([app/api/sop.py:24](../../app/api/sop.py#L24)):

```
prep → copy_draft → medical → copy_final → cms → captions → qa → complete
```

`complete` is terminal.

---

## Trigger

Three independent entry points:

1. **Auto-init at ingest completion.** `sop_auto_init_task` is fired by `finalize_task` ([app/tasks/finalize.py:103](../../app/tasks/finalize.py#L103)) and by `ai_process_task` direct ([app/tasks/ai_process.py:561](../../app/tasks/ai_process.py#L561)). It creates the `sop_state` row at stage `prep` if missing ([app/tasks/sop_tasks.py:54](../../app/tasks/sop_tasks.py#L54)).
2. **Lazy auto-create on first read.** `GET /v1/sessions/{id}/sop` inserts a `prep` row (`ON CONFLICT DO NOTHING`) if none exists ([app/api/sop.py:99](../../app/api/sop.py#L99)).
3. **Manual advancement.** `POST /v1/sessions/{id}/sop/advance` moves the stage forward ([app/api/sop.py:113](../../app/api/sop.py#L113)).

Additional operator endpoints on the same router: `/sop/assign` ([app/api/sop.py:145](../../app/api/sop.py#L145)), `/sop/annotations` ([app/api/sop.py:196](../../app/api/sop.py#L196)), `/sop/checks/resolve` ([app/api/sop.py:250](../../app/api/sop.py#L250)). A non-session global route `GET /v1/sop/dashboard-summary` returns per-stage counts ([app/api/sop.py:279](../../app/api/sop.py#L279)).

Stage assignees (a typed-FK matrix separate from `sop_state.assignees`) are managed under `/v1/sessions/{id}/stage-assignees` ([app/api/sessions.py:345](../../app/api/sessions.py#L345)).

## Inputs

- **Advance** (`AdvancePayload`): `to_stage` (required), `note` (optional) ([app/api/sop.py:50](../../app/api/sop.py#L50)).
- **Assign** (`AssignPayload`): `stage` (defaults to current), `assignee` (person email, `group:NAME`, or `(unassigned)`), `note` ([app/api/sop.py:60](../../app/api/sop.py#L60)).
- **Annotation** (`AnnotationPayload`): `stage` (defaults to current), `kind` ∈ {`note`, `override`, `blocker`}, `body` ([app/api/sop.py:71](../../app/api/sop.py#L71)).
- **Check resolve** (`CheckResolvePayload`): `check_id`, `label` ([app/api/sop.py:55](../../app/api/sop.py#L55)).
- **Stage-assignee PUT** (`StageAssigneePatch`): `person_id` / `group_id` (typed) or `assignee_email`, `notify_email` ([app/api/sessions.py:379](../../app/api/sessions.py#L379)).

Default SLA per stage in hours (editable per-session via `sop_state.sla_target_hours`): prep 8, copy_draft 24, medical 48, copy_final 24, cms 12, captions 12, qa 8, complete 0 ([app/api/sop.py:29](../../app/api/sop.py#L29) and [app/tasks/sop_tasks.py:36](../../app/tasks/sop_tasks.py#L36)).

## Validations

- **Forward-only, single-step.** `_validate_transition` rejects unknown stages, unknown current stage, and any move that is not exactly `current_index + 1` (no jumps, no backward moves) ([app/api/sop.py:80](../../app/api/sop.py#L80)). Violations → HTTP 400.
- **Block guard.** Advance is rejected with 400 when `sop_state.is_blocked` is true ([app/api/sop.py:121](../../app/api/sop.py#L121)).
- **Uninitialized state.** Advance / assign / annotation return 404 if no `sop_state` row exists ("GET /sop first") ([app/api/sop.py:119](../../app/api/sop.py#L119), [app/api/sop.py:156](../../app/api/sop.py#L156), [app/api/sop.py:207](../../app/api/sop.py#L207)).
- **Row lock.** Advance and assign read with `FOR UPDATE` to serialize concurrent mutations ([app/api/sop.py:117](../../app/api/sop.py#L117), [app/api/sop.py:152](../../app/api/sop.py#L152)).
- **Stage / kind validation.** Assign and annotation reject unknown `stage`; annotation rejects unknown `kind` ([app/api/sop.py:159](../../app/api/sop.py#L159), [app/api/sop.py:210](../../app/api/sop.py#L210), [app/api/sop.py:212](../../app/api/sop.py#L212)).
- **Stage-assignee DB constraint.** `chk_session_stage_assignees_single_assignee` guarantees exactly one of `person_id` / `group_id` is non-null ([app/api/sessions.py:399](../../app/api/sessions.py#L399)).

## Approvals

None. Advancement is a single forward step taken by any authenticated user; there is no second-party approval gate. The `qa` stage and `medical` stage are positions in the stage order, not approval handoffs enforced in code.

## Notifications

- **WebSocket on auto-init:** `sop.initialized` (with `stage`) ([app/tasks/sop_tasks.py:106](../../app/tasks/sop_tasks.py#L106)).
- **WebSocket on overdue scan:** `sop.deadline_warning` (with `stage`, `overdue_hours`) ([app/tasks/sop_tasks.py:503](../../app/tasks/sop_tasks.py#L503)).
- **No WS event is emitted by the `/advance`, `/assign`, `/annotations`, or `/checks/resolve` HTTP handlers** — they write DB + audit only. NOT VERIFIED: no `publish_ws_event` call exists in those handlers ([app/api/sop.py:113](../../app/api/sop.py#L113)–[app/api/sop.py:268](../../app/api/sop.py#L268)).
- **Email (feature-flagged, default OFF):** `sop_check_deadlines_task` optionally calls `_maybe_send_deadline_email` only when `SOP_DEADLINE_EMAIL_ENABLED` is true ([app/tasks/sop_tasks.py:542](../../app/tasks/sop_tasks.py#L542)). Env flag `SOP_DEADLINE_EMAIL_ENABLED` defaults to `False` ([app/config.py:110](../../app/config.py#L110)). Email specifics:
  - Throttle BR-004: one email per `(session_id, stage)` per 23 hours, enforced under a per-(session,stage) Postgres advisory lock ([app/tasks/sop_tasks.py:282](../../app/tasks/sop_tasks.py#L282)).
  - Skips group assignees (`group:`), non-email assignees, and any stage with no assignee ([app/tasks/sop_tasks.py:271](../../app/tasks/sop_tasks.py#L271)).
  - Recipient is masked in `audit_events.summary`; full address kept in `details->>'recipient'` ([app/tasks/sop_tasks.py:144](../../app/tasks/sop_tasks.py#L144)).
  - Subject/body resolve from `email_templates` (`stage_id = '<stage>_overdue'`) with an inline f-string fallback ([app/tasks/sop_tasks.py:360](../../app/tasks/sop_tasks.py#L360)).

## Outputs

- `sop_state` row created/updated: `current_stage`, `entered_current_at`, `assignees` (jsonb), `sla_target_hours` (jsonb), `metadata.annotations` (append-only), `updated_at` ([app/api/sop.py:126](../../app/api/sop.py#L126), [app/api/sop.py:169](../../app/api/sop.py#L169), [app/api/sop.py:227](../../app/api/sop.py#L227); [app/tasks/sop_tasks.py:81](../../app/tasks/sop_tasks.py#L81)).
- `sop_transitions` append-only row per advance and per auto-init (from_stage/to_stage/actor) ([app/api/sop.py:131](../../app/api/sop.py#L131), [app/tasks/sop_tasks.py:93](../../app/tasks/sop_tasks.py#L93)).
- `sop_checks` upsert on resolve (`is_resolved`, `resolved_by`, `resolved_at`) ([app/api/sop.py:257](../../app/api/sop.py#L257)).
- `session_stage_assignees` row per stage on PUT / apply-type-defaults ([app/api/sessions.py:455](../../app/api/sessions.py#L455), [app/api/sessions.py:529](../../app/api/sessions.py#L529)).
- `dashboard-summary` returns one row per stage `{stage, count, overdue_count}`; overdue computed in Python (not SQL) to share logic with the deadline task and client fallback ([app/api/sop.py:322](../../app/api/sop.py#L322)).

## Status Changes

- SOP stage moves only via `/sop/advance` (single-step forward), `sop_auto_init_task` (sets initial `prep`), or the lazy `GET` auto-create.
- `entered_current_at` is reset to `now()` on every advance — this timestamp drives SLA / overdue computation ([app/api/sop.py:126](../../app/api/sop.py#L126)).
- The SOP stage is independent of `sessions.status`. The `sessions.status` transition `ready → complete` exists in the ingest state machine ([app/engines/state_machine.py:46](../../app/engines/state_machine.py#L46)) but is NOT triggered by the SOP `/advance` handler. IMPLEMENTATION NOT FOUND: no code in the listed SOP files transitions `sessions.status` to `complete` when SOP reaches the `complete` stage.

## Audit Events

`audit_events` rows written (each with `actor_email`, `kind`, `summary`, `details`):

- `sop.advance` ([app/api/sop.py:136](../../app/api/sop.py#L136)).
- `sop.assign` ([app/api/sop.py:174](../../app/api/sop.py#L174)).
- `sop.annotation` ([app/api/sop.py:231](../../app/api/sop.py#L231)).
- `sop.check.resolve` ([app/api/sop.py:264](../../app/api/sop.py#L264)).
- `sop.initialized` (actor `system:sop_auto_init`) ([app/tasks/sop_tasks.py:118](../../app/tasks/sop_tasks.py#L118)).
- `sop.deadline_warning` (actor `system:sop_check_deadlines`) ([app/tasks/sop_tasks.py:519](../../app/tasks/sop_tasks.py#L519)).
- `sop.deadline_email_sent` / `sop.deadline_email_failed` (email path only, flag-gated) ([app/tasks/sop_tasks.py:312](../../app/tasks/sop_tasks.py#L312), [app/tasks/sop_tasks.py:429](../../app/tasks/sop_tasks.py#L429)).

## Exception Handling

- **`sop_auto_init_task`** is non-fatal: retries up to 2 with backoff, then returns `{error}` without ever marking the session failed ([app/tasks/sop_tasks.py:133](../../app/tasks/sop_tasks.py#L133)). WS and audit inserts are individually wrapped so a failure there doesn't abort init.
- **`sop_check_deadlines_task`** wraps each per-session WS emit, audit insert, and email attempt in its own try/except so one bad row doesn't halt the scan ([app/tasks/sop_tasks.py:500](../../app/tasks/sop_tasks.py#L500)–[app/tasks/sop_tasks.py:545](../../app/tasks/sop_tasks.py#L545)). It returns `{warnings, scanned}` ([app/tasks/sop_tasks.py:549](../../app/tasks/sop_tasks.py#L549)).
- **Email throttle race:** advisory-lock failure on slot claim logs a warning and skips (drops one notification rather than double-sending) ([app/tasks/sop_tasks.py:329](../../app/tasks/sop_tasks.py#L329)).
- HTTP handlers raise `HTTPException` (400/404) for the validations listed above; SQLAlchemy errors propagate as 500 (default FastAPI handler).

### Scheduling / feature flags

- **Deadline scan cadence:** `sop_check_deadlines_task` is scheduled via Celery Beat every hour (`3600.0`) under key `sop-check-deadlines` ([app/tasks/celery_app.py:84](../../app/tasks/celery_app.py#L84)). It can also be run synchronously via `/v1/diag/sop-check` ([app/tasks/sop_tasks.py:462](../../app/tasks/sop_tasks.py#L462)).
- **Deadline email:** default OFF, flag `SOP_DEADLINE_EMAIL_ENABLED = False` ([app/config.py:110](../../app/config.py#L110)). The hourly WS+audit warning fires regardless of this flag; only the SMTP send is gated.

---

## Source Verification
- **Files Used:** app/api/sop.py, app/tasks/sop_tasks.py, app/api/sessions.py (stage-assignees), app/tasks/finalize.py, app/tasks/ai_process.py, app/tasks/celery_app.py, app/engines/state_machine.py, app/config.py
- **Components Used:** none (backend; SopView/editor right-rail referenced in code comments but frontend not read for this workflow)
- **APIs Used:** GET/POST `/v1/sessions/{id}/sop`, POST `/v1/sessions/{id}/sop/advance`, POST `/v1/sessions/{id}/sop/assign`, PATCH `/v1/sessions/{id}/sop/annotations`, POST `/v1/sessions/{id}/sop/checks/resolve`, GET `/v1/sop/dashboard-summary`, GET/PUT/POST `/v1/sessions/{id}/stage-assignees[/...]`, `/v1/diag/sop-check`
- **Database Tables Used:** sop_state, sop_transitions, sop_checks, session_stage_assignees, stage_assignees, session_types, people, groups, sessions, audit_events, email_templates
- **Permission Logic Used:** JWT presence via `CurrentUser` dependency on every route ([app/api/sop.py:94](../../app/api/sop.py#L94)). No role tiers and no `johndean@vin.com` gate are read in these handlers.
- **Confidence Score:** High — all stage/SLA/validation/audit claims verified against source lines.
- **Evidence Links:** [app/api/sop.py:80](../../app/api/sop.py#L80), [app/api/sop.py:113](../../app/api/sop.py#L113), [app/tasks/sop_tasks.py:54](../../app/tasks/sop_tasks.py#L54), [app/tasks/sop_tasks.py:542](../../app/tasks/sop_tasks.py#L542), [app/config.py:110](../../app/config.py#L110)
