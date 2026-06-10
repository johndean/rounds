# API Reference — SOP Workflow (`/v1/sessions/{session_id}/sop` + `/v1/sop`)

The SOP (Standard Operating Procedure) workflow state machine for a session. The pipeline has 8 forward-only stages ([app/api/sop.py:24](../../app/api/sop.py#L24)):

```
prep · copy_draft · medical · copy_final · cms · captions · qa · complete
```

This file backs two routers:
- **Session-scoped router** — prefix `/v1/sessions/{session_id}/sop`, tag `sop` ([app/api/sop.py:20](../../app/api/sop.py#L20)).
- **Global router** — prefix `/v1/sop`, tag `sop` ([app/api/sop.py:22](../../app/api/sop.py#L22)).

- **Source file:** [`app/api/sop.py`](../../app/api/sop.py)
- **Mounted in:** [app/main.py:222](../../app/main.py#L222) (`sop_router.router`) and [app/main.py:223](../../app/main.py#L223) (`sop_router.global_router`)
- **Endpoints found:** 6 — `GET sop`, `POST sop/advance`, `POST sop/assign`, `PATCH sop/annotations`, `POST sop/checks/resolve`, `GET /v1/sop/dashboard-summary`

## Authentication & Authorization (router-wide)

Every handler takes a `CurrentUser` dependency — either `_u` (read endpoints) or `user` (write endpoints, which read `user.email`). **A valid JWT bearer token is required** on all 6 routes ([app/auth.py:208](../../app/auth.py#L208)).

**Authorization is JWT-only.** No `LEGACY_ADMIN_EMAIL`, `require_admin`, `is_admin`, or `johndean@vin.com` gate exists in this router — verified by grep over [app/api/sop.py](../../app/api/sop.py) (no matches). `user.email` is used only as the `actor_email` written to `sop_transitions` / `audit_events` / `sop_checks` / `assignees`, not for any permission check. Any authenticated user may advance/assign/annotate.

### Stage transition rule
`_validate_transition(from, to)` ([app/api/sop.py:80](../../app/api/sop.py#L80)) is **forward-only, one step at a time**: `to` must equal `from + 1` in the `STAGES` ordering. Unknown stages, jumps, and backward moves are all rejected with HTTP 400.

### Note on error envelopes
This router raises FastAPI `HTTPException` (not the `MICException` subclasses used elsewhere). The `EnvelopeMiddleware` maps these into the standard error envelope: status 400 → code `INVALID_INPUT`, 404 → `NOT_FOUND` ([app/middleware/envelope.py:298](../../app/middleware/envelope.py#L298)). The raw FastAPI `detail` string becomes the envelope `message`.

---

## `GET /v1/sessions/{session_id}/sop`

- **Decorator:** `@router.get("", response_model=SopState)` — [app/api/sop.py:93](../../app/api/sop.py#L93)
- **Handler:** `get_state(session_id, db, _u)` — [:94](../../app/api/sop.py#L94)

### Purpose
Returns the current SOP state for a session. **Auto-creates** the initial `prep` state on first read if none exists ([:100](../../app/api/sop.py#L100)).

### Authentication / Authorization
JWT required; JWT-only.

### Request Schema
Path param `session_id: UUID`. No body.

### Response Schema
`SopState` ([app/api/sop.py:41](../../app/api/sop.py#L41)) (envelope `data`):

| Field | Type | Notes |
|---|---|---|
| `current_stage` | `str` | one of the 8 stages |
| `is_blocked` | `bool` | |
| `blockers` | `list[dict]` | |
| `assignees` | `dict` | per-stage assignee map |
| `sla_target_hours` | `dict` | per-stage SLA overrides |
| `entered_current_at` | `str \| null` | ISO timestamp; `null` on first load |

On first load (auto-create branch) the response is `{current_stage: "prep", is_blocked: false, blockers: [], assignees: {}, sla_target_hours: {}, entered_current_at: null}` ([:106](../../app/api/sop.py#L106)).

### Validation Rules
`session_id` must be a valid UUID (FastAPI path coercion). No existence check on `sessions` — a missing row simply creates a fresh `sop_state`.

### Errors
| Condition | Code / Status | Source |
|---|---|---|
| Missing/invalid JWT | `UNAUTHORIZED` / 401 | [app/auth.py:164](../../app/auth.py#L164) |
| `session_id` not a UUID | FastAPI 422 | path type `UUID` |

### Example
`GET /v1/sessions/3f...uuid/sop` → `data`: `{ "current_stage": "copy_draft", "is_blocked": false, "blockers": [], "assignees": {"copy_draft": {...}}, "sla_target_hours": {}, "entered_current_at": "2026-06-08T12:00:00+00:00" }`

### Related Screens
- `SopView.vue` (`GET /v1/sessions/{id}/sop`, [frontend/src/views/SopView.vue:7](../../frontend/src/views/SopView.vue#L7)); `api.ts` `getSop` ([frontend/src/services/api.ts:631](../../frontend/src/services/api.ts#L631)).

### Related Tables
`sop_state` (SELECT; INSERT `ON CONFLICT (session_id) DO NOTHING` on auto-create, [:101](../../app/api/sop.py#L101)).

---

## `POST /v1/sessions/{session_id}/sop/advance`

- **Decorator:** `@router.post("/advance", response_model=SopState, status_code=status.HTTP_200_OK)` — [app/api/sop.py:113](../../app/api/sop.py#L113)
- **Handler:** `advance(session_id, payload, db, user)` — [:114](../../app/api/sop.py#L114)

### Purpose
Advances the session one stage forward. Records a `sop_transitions` row and an `audit_events` (`sop.advance`) row. Uses `SELECT ... FOR UPDATE` to lock the row ([:117](../../app/api/sop.py#L117)).

### Authentication / Authorization
JWT required; JWT-only. `user.email` is written as `actor_email`.

### Request Schema
`AdvancePayload` ([app/api/sop.py:50](../../app/api/sop.py#L50)):

| Field | Type | Required | Constraints |
|---|---|---|---|
| `to_stage` | `str` | yes | `min_length=1` |
| `note` | `str \| null` | no | |

### Response Schema
`SopState` (the post-advance row) — [:129](../../app/api/sop.py#L129) returns `current_stage, is_blocked, blockers, assignees, sla_target_hours`. (Note: the `RETURNING` clause here does not include `entered_current_at`, so it defaults to `null` in the model on this response, even though the column was set to `now()`.)

### Validation Rules
1. SOP state must already exist (else 404, [:120](../../app/api/sop.py#L120)).
2. `is_blocked` must be false (else 400 "Cannot advance while blocked", [:122](../../app/api/sop.py#L122)).
3. `_validate_transition(current, to_stage)` — forward-only single step ([:123](../../app/api/sop.py#L123)).

### Errors
| Condition | Code / Status | Source |
|---|---|---|
| Missing/invalid JWT | `UNAUTHORIZED` / 401 | [app/auth.py:164](../../app/auth.py#L164) |
| SOP state not initialized | 404 → `NOT_FOUND` ("SOP state not initialized; GET /sop first") | [:120](../../app/api/sop.py#L120) |
| Currently blocked | 400 → `INVALID_INPUT` ("Cannot advance while blocked") | [:122](../../app/api/sop.py#L122) |
| Unknown / non-forward / backward `to_stage` | 400 → `INVALID_INPUT` | [:82](../../app/api/sop.py#L82)–[:90](../../app/api/sop.py#L90) |

### Example
```http
POST /v1/sessions/3f...uuid/sop/advance
Authorization: Bearer <jwt>
{ "to_stage": "medical", "note": "copy draft done" }
```

### Related Screens
- `SopView.vue` (`POST .../sop/advance`, [frontend/src/views/SopView.vue:8](../../frontend/src/views/SopView.vue#L8)); `api.ts` `advanceSop` ([frontend/src/services/api.ts:639](../../frontend/src/services/api.ts#L639)).

### Related Tables
`sop_state` (SELECT FOR UPDATE + UPDATE), `sop_transitions` (INSERT, [:131](../../app/api/sop.py#L131)), `audit_events` (INSERT `sop.advance`, [:135](../../app/api/sop.py#L135)).

---

## `POST /v1/sessions/{session_id}/sop/assign`

- **Decorator:** `@router.post("/assign")` — [app/api/sop.py:145](../../app/api/sop.py#L145)
- **Handler:** `assign_stage(session_id, payload, db, user)` — [:146](../../app/api/sop.py#L146)

### Purpose
Reassigns a stage owner. Writes `{assignee, assigned_by, assigned_at}` into `sop_state.assignees[stage]` (jsonb) and records an `audit_events` (`sop.assign`) row with old/new values.

### Authentication / Authorization
JWT required; JWT-only. `user.email` recorded as `assigned_by` and `actor_email`.

### Request Schema
`AssignPayload` ([app/api/sop.py:60](../../app/api/sop.py#L60)):

| Field | Type | Required | Constraints |
|---|---|---|---|
| `stage` | `str \| null` | no | defaults to current stage ([:158](../../app/api/sop.py#L158)) |
| `assignee` | `str` | yes | `min_length=1`, `max_length=128`. May be a person email, a group (`group:NAME`), or `(unassigned)` to clear (per docstring [:61](../../app/api/sop.py#L61)) |
| `note` | `str \| null` | no | |

### Response Schema
Plain `dict` (envelope `data`) — [:188](../../app/api/sop.py#L188):

| Field | Type |
|---|---|
| `session_id` | `str` |
| `stage` | `str` |
| `assignee` | `str` |
| `prev` | the previous assignee value (or `null`) |

Note `assigned_at` is set to `null` in the stored jsonb (the inline comment says it would be filled by `now()` but the value written is literal `None`, [:167](../../app/api/sop.py#L167)) — PARTIALLY IMPLEMENTED.

### Validation Rules
1. SOP state must exist (else 404, [:156](../../app/api/sop.py#L156)).
2. `stage` (resolved) must be a known stage (else 400, [:159](../../app/api/sop.py#L159)).

### Errors
| Condition | Code / Status | Source |
|---|---|---|
| Missing/invalid JWT | `UNAUTHORIZED` / 401 | [app/auth.py:164](../../app/auth.py#L164) |
| Body fails Pydantic (`assignee` empty/too long) | FastAPI 422 | model at [:60](../../app/api/sop.py#L60) |
| SOP state not initialized | 404 → `NOT_FOUND` | [:156](../../app/api/sop.py#L156) |
| Unknown `stage` | 400 → `INVALID_INPUT` | [:160](../../app/api/sop.py#L160) |

### Example
```http
POST /v1/sessions/3f...uuid/sop/assign
Authorization: Bearer <jwt>
{ "stage": "medical", "assignee": "vet@vin.com", "note": "primary reviewer" }
```

### Related Screens
- `SopView.vue` (`POST .../sop/assign`, [frontend/src/views/SopView.vue:258](../../frontend/src/views/SopView.vue#L258)); `api.ts` `assignSop` ([frontend/src/services/api.ts:645](../../frontend/src/services/api.ts#L645)).

### Related Tables
`sop_state` (SELECT FOR UPDATE + UPDATE `assignees` jsonb), `audit_events` (INSERT `sop.assign`, [:173](../../app/api/sop.py#L173)).

---

## `PATCH /v1/sessions/{session_id}/sop/annotations`

- **Decorator:** `@router.patch("/annotations")` — [app/api/sop.py:196](../../app/api/sop.py#L196)
- **Handler:** `add_annotation(session_id, payload, db, user)` — [:197](../../app/api/sop.py#L197)

### Purpose
Appends an append-only, stage-scoped annotation to `sop_state.metadata.annotations` (jsonb array). Records an `audit_events` (`sop.annotation`) row.

### Authentication / Authorization
JWT required; JWT-only. `user.email` recorded as `actor_email`.

### Request Schema
`AnnotationPayload` ([app/api/sop.py:71](../../app/api/sop.py#L71)):

| Field | Type | Required | Constraints |
|---|---|---|---|
| `stage` | `str \| null` | no | defaults to current stage ([:209](../../app/api/sop.py#L209)) |
| `kind` | `str` | no | default `"note"`; must be `note`, `override`, or `blocker` ([:212](../../app/api/sop.py#L212)); `min_length=1`, `max_length=32` |
| `body` | `str` | yes | `min_length=1`, `max_length=2000` |

### Response Schema
Plain `dict` (envelope `data`) — [:241](../../app/api/sop.py#L241):

| Field | Type | Notes |
|---|---|---|
| `session_id` | `str` | |
| `stage` | `str` | resolved stage |
| `kind` | `str` | |
| `annotation` | `dict` | the new entry: `{stage, kind, body, actor_email, inserted_at}` ([:217](../../app/api/sop.py#L217)) |
| `total_count` | `int` | length of the annotations array after append |

### Validation Rules
1. SOP state must exist (else 404, [:207](../../app/api/sop.py#L207)).
2. Resolved `stage` must be known (else 400, [:211](../../app/api/sop.py#L211)).
3. `kind` must be one of `note`/`override`/`blocker` (else 400, [:213](../../app/api/sop.py#L213)).

### Errors
| Condition | Code / Status | Source |
|---|---|---|
| Missing/invalid JWT | `UNAUTHORIZED` / 401 | [app/auth.py:164](../../app/auth.py#L164) |
| `body` empty/too long, `kind` too long | FastAPI 422 | model at [:71](../../app/api/sop.py#L71) |
| SOP state not initialized | 404 → `NOT_FOUND` | [:207](../../app/api/sop.py#L207) |
| Unknown `stage` | 400 → `INVALID_INPUT` | [:211](../../app/api/sop.py#L211) |
| Unknown `kind` | 400 → `INVALID_INPUT` | [:213](../../app/api/sop.py#L213) |

### Example
```http
PATCH /v1/sessions/3f...uuid/sop/annotations
Authorization: Bearer <jwt>
{ "stage": "medical", "kind": "blocker", "body": "needs dosage confirmation" }
```

### Related Screens
- `SopView.vue`; `api.ts` annotations call ([frontend/src/services/api.ts:654](../../frontend/src/services/api.ts#L654)).

### Related Tables
`sop_state` (SELECT FOR UPDATE + UPDATE `metadata` jsonb), `audit_events` (INSERT `sop.annotation`, [:231](../../app/api/sop.py#L231)).

---

## `POST /v1/sessions/{session_id}/sop/checks/resolve`

- **Decorator:** `@router.post("/checks/resolve")` — [app/api/sop.py:250](../../app/api/sop.py#L250)
- **Handler:** `resolve_check(session_id, payload, db, user)` — [:251](../../app/api/sop.py#L251)

### Purpose
Marks a named per-stage check as resolved for the current stage (upsert into `sop_checks`). Records an `audit_events` (`sop.check.resolve`) row.

### Authentication / Authorization
JWT required; JWT-only. `user.email` recorded as `resolved_by` / `actor_email`.

### Request Schema
`CheckResolvePayload` ([app/api/sop.py:55](../../app/api/sop.py#L55)):

| Field | Type | Required |
|---|---|---|
| `check_id` | `str` | yes |
| `label` | `str` | yes |

### Response Schema
Plain `dict` (envelope `data`) — [:268](../../app/api/sop.py#L268): `{ "resolved": true, "check_id": <id>, "stage": <current_stage> }`.

### Validation Rules
SOP state must exist (else 404, [:256](../../app/api/sop.py#L256)). The check is resolved against `cur["current_stage"]` (the stage is not client-supplied).

### Errors
| Condition | Code / Status | Source |
|---|---|---|
| Missing/invalid JWT | `UNAUTHORIZED` / 401 | [app/auth.py:164](../../app/auth.py#L164) |
| Body missing `check_id`/`label` | FastAPI 422 | model at [:55](../../app/api/sop.py#L55) |
| SOP state not initialized | 404 → `NOT_FOUND` ("SOP state not initialized") | [:256](../../app/api/sop.py#L256) |

### Example
```http
POST /v1/sessions/3f...uuid/sop/checks/resolve
Authorization: Bearer <jwt>
{ "check_id": "spell_check", "label": "Spelling reviewed" }
```

### Related Screens
- `SopView.vue` (`POST .../sop/checks/resolve`, [frontend/src/views/SopView.vue:9](../../frontend/src/views/SopView.vue#L9)); `api.ts` `resolveSopCheck` ([frontend/src/services/api.ts:641](../../frontend/src/services/api.ts#L641)).

### Related Tables
`sop_state` (SELECT current stage), `sop_checks` (UPSERT `ON CONFLICT (session_id, stage, check_id)`, [:257](../../app/api/sop.py#L257)), `audit_events` (INSERT `sop.check.resolve`, [:263](../../app/api/sop.py#L263)).

---

## `GET /v1/sop/dashboard-summary`

- **Decorator:** `@global_router.get("/dashboard-summary", response_model=list[StageSummaryRow])` — [app/api/sop.py:279](../../app/api/sop.py#L279)
- **Handler:** `dashboard_summary(db, _u)` — [:280](../../app/api/sop.py#L280)

### Purpose
Returns per-stage session counts plus overdue counts for the dashboard's Pipeline-2 SOP row. **Read-only — no `audit_events` row written.** Overdue is computed in Python so the logic matches `sop_check_deadlines_task` and the client fallback ([:281](../../app/api/sop.py#L281)).

### Authentication / Authorization
JWT required (`_u: CurrentUser`); JWT-only. **Not session-scoped** — this is on the `/v1/sop` global router.

### Request Schema
No path params, no body, no query params.

### Response Schema
`list[StageSummaryRow]` ([app/api/sop.py:273](../../app/api/sop.py#L273)) — one row per stage in canonical order:

| Field | Type | Notes |
|---|---|---|
| `stage` | `str` | one of the 8 stages |
| `count` | `int` | sessions currently in that stage |
| `overdue_count` | `int` | sessions whose dwell time exceeds the per-stage SLA |

Overdue logic: per-stage SLA is `sop_state.sla_target_hours[stage]` if an int, else `_DEFAULT_SLA_HOURS` ([app/api/sop.py:29](../../app/api/sop.py#L29)) — `prep` 8h, `copy_draft` 24h, `medical` 48h, `copy_final` 24h, `cms` 12h, `captions` 12h, `qa` 8h, `complete` 0 (terminal, never overdue). A stage with `sla_hours <= 0` or no `entered_current_at` is never counted overdue ([:316](../../app/api/sop.py#L316)).

### Validation Rules
None on input. Unknown stages found in `sop_state` are skipped rather than poisoning the response ([:307](../../app/api/sop.py#L307)).

### Errors
| Condition | Code / Status | Source |
|---|---|---|
| Missing/invalid JWT | `UNAUTHORIZED` / 401 | [app/auth.py:164](../../app/auth.py#L164) |

### Example
`GET /v1/sop/dashboard-summary` → `data`: `[ { "stage": "prep", "count": 3, "overdue_count": 1 }, { "stage": "copy_draft", "count": 5, "overdue_count": 0 }, ... ]`

### Related Screens
- `DashboardView.vue` (Pipeline-2 SOP row, [frontend/src/views/DashboardView.vue:86](../../frontend/src/views/DashboardView.vue#L86)); `api.ts` `sopDashboardSummary` ([frontend/src/services/api.ts:636](../../frontend/src/services/api.ts#L636)). The `QueueView.vue` links into SOP per session ([frontend/src/views/QueueView.vue:91](../../frontend/src/views/QueueView.vue#L91)).

### Related Tables
`sop_state` (SELECT only — `current_stage`, `entered_current_at`, `sla_target_hours`).

---

## Source Verification
- **Files Used:** [app/api/sop.py](../../app/api/sop.py), [app/auth.py](../../app/auth.py), [app/middleware/envelope.py](../../app/middleware/envelope.py), [app/main.py](../../app/main.py), frontend/src/services/api.ts, frontend/src/views/SopView.vue, frontend/src/views/DashboardView.vue
- **Components Used:** SopView.vue, DashboardView.vue, QueueView.vue
- **APIs Used:** `GET /v1/sessions/{id}/sop`, `POST /v1/sessions/{id}/sop/advance`, `POST /v1/sessions/{id}/sop/assign`, `PATCH /v1/sessions/{id}/sop/annotations`, `POST /v1/sessions/{id}/sop/checks/resolve`, `GET /v1/sop/dashboard-summary`
- **Database Tables Used:** sop_state, sop_transitions, sop_checks, audit_events
- **Permission Logic Used:** JWT presence only (`CurrentUser` → `get_current_user`). No admin/role gate; `user.email` used solely as actor/assignee metadata.
- **Confidence Score:** High — all 6 decorators, all Pydantic models, the transition validator, and SLA defaults were read directly; both router mounts confirmed in main.py.
- **Evidence Links:** [session router app/api/sop.py:20](../../app/api/sop.py#L20), [global router :22](../../app/api/sop.py#L22), [GET sop :93](../../app/api/sop.py#L93), [advance :113](../../app/api/sop.py#L113), [assign :145](../../app/api/sop.py#L145), [annotations :196](../../app/api/sop.py#L196), [checks/resolve :250](../../app/api/sop.py#L250), [dashboard-summary :279](../../app/api/sop.py#L279), [mounts app/main.py:222](../../app/main.py#L222)
