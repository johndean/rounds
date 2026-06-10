# Queue API — `/v1/queue`

Per-user work queue. Returns the sessions where the current user is the assignee for the session's **current SOP stage** — i.e., the work the user needs to act on right now.

Router declaration: [app/api/queue.py:29](../../app/api/queue.py#L29) — `APIRouter(prefix="/v1/queue", tags=["queue"])`.

The router defines **one** endpoint. The data is sourced by joining the `sessions` table to `sop_state` and reading the per-stage assignee out of the `sop_state.assignees` JSONB column.

---

## `GET /v1/queue/mine`

- **Endpoint:** `/v1/queue/mine`
- **Method:** `GET`
- **Decorator:** [app/api/queue.py:45](../../app/api/queue.py#L45) — `@router.get("/mine", response_model=list[QueueItemOut])`
- **Handler:** `list_my_queue` ([app/api/queue.py:46](../../app/api/queue.py#L46))
- **Purpose:** Return the sessions where the calling user's email is the assignee for the session's current SOP stage, ordered so the longest-waiting items surface first. Read-only — no mutations.

### Authentication

JWT bearer token required. The handler signature is `(db: DbSession, user: CurrentUser)` ([app/api/queue.py:46](../../app/api/queue.py#L46)). `CurrentUser` resolves through `get_current_user`, which decodes the HS256 JWT and confirms the user is still active (DB lookup with env-CSV fallback) — see [app/auth.py:172](../../app/auth.py#L172) and [app/auth.py:208](../../app/auth.py#L208). A missing or invalid token yields `401 Could not validate credentials`.

### Authorization

JWT-only. There is **no** `LEGACY_ADMIN_EMAIL` / `require_admin` gate on this route. Scoping is implicit: the query filters on `user.email`, so a caller only ever sees their own queue rows. No role check is applied.

### Request Schema

No request body. No path parameters. Query parameters: **none** — `list_my_queue` takes only `db` and `user` ([app/api/queue.py:46](../../app/api/queue.py#L46)).

### Response Schema

`200 OK` — `list[QueueItemOut]`. `QueueItemOut` ([app/api/queue.py:32](../../app/api/queue.py#L32)):

| Field | Type | Notes |
|---|---|---|
| `session_id` | `str` | Session UUID, stringified ([app/api/queue.py:133](../../app/api/queue.py#L133)). |
| `code` | `str` | Session code (e.g. a lecture identifier). |
| `title` | `str \| null` | |
| `title_short` | `str \| null` | |
| `title_long` | `str \| null` | |
| `status` | `str` | Session status. |
| `current_stage` | `str` | SOP stage from `sop_state.current_stage`. |
| `entered_current_at` | `str \| null` | ISO-8601 timestamp of when the session entered its current stage, or `null` ([app/api/queue.py:140](../../app/api/queue.py#L140)). |
| `overdue_hours` | `float \| null` | Hours past SLA, rounded to 1 decimal. `null` when the stage is on-time or has no elapsed/SLA basis. |

Note: `QueueItemOut` uses `ConfigDict(from_attributes=True)` ([app/api/queue.py:33](../../app/api/queue.py#L33)), but the handler returns plain dicts it builds by hand, not ORM objects.

### Validation Rules / Behavior

The query ([app/api/queue.py:87](../../app/api/queue.py#L87)) applies these filters:

- **Assignee match:** `COALESCE(sop.assignees -> sop.current_stage ->> 'assignee', sop.assignees ->> sop.current_stage) = :email`, where `:email` is bound to `user.email` ([app/api/queue.py:112](../../app/api/queue.py#L112)). The `COALESCE` handles both writers' JSONB shapes: a nested object `{"assignee": "user@vin.com", ...}` (written by `app/api/sop.py::assign_stage`) and a plain string email (written by `app/tasks/sop_tasks.py` / the Settings → Stages matrix). See the comment at [app/api/queue.py:79](../../app/api/queue.py#L79).
- **Excludes soft-deleted sessions:** `s.deleted_at IS NULL` ([app/api/queue.py:106](../../app/api/queue.py#L106)).
- **Excludes the terminal stage:** `sop.current_stage != 'complete'` ([app/api/queue.py:107](../../app/api/queue.py#L107)).
- **Group assignments are excluded for v1.** Per the docstring ([app/api/queue.py:54](../../app/api/queue.py#L54)), `group:NAME` assignments do not match because the filter compares against the caller's literal email; group expansion is deferred. (No code path expands groups — confirmed by the absence of any `group:` handling in this file.)
- **Ordering:** `ORDER BY sop.entered_current_at ASC NULLS LAST` ([app/api/queue.py:108](../../app/api/queue.py#L108)) — longest-waiting first.
- **Limit:** `LIMIT 200` ([app/api/queue.py:109](../../app/api/queue.py#L109)).

`overdue_hours` computation ([app/api/queue.py:116](../../app/api/queue.py#L116)):

- A per-stage default SLA map is inlined in the handler ([app/api/queue.py:69](../../app/api/queue.py#L69)): `prep=8, copy_draft=24, medical=48, copy_final=24, cms=12, captions=12, qa=8, complete=0`. The comment states this mirrors `app/tasks/sop_tasks.py:_DEFAULT_SLA_HOURS` (NOT VERIFIED IN CODE against that file in this assignment).
- A per-session override from `sop_state.sla_target_hours[stage]` takes precedence when it is an `int` ([app/api/queue.py:124](../../app/api/queue.py#L124)); otherwise the default map is used (falling back to `24` for unknown stages, [app/api/queue.py:126](../../app/api/queue.py#L126)).
- Overdue is computed only when `entered_current_at` is non-null and the resolved SLA is `> 0`. If elapsed hours exceed the SLA, `overdue_hours = round(elapsed - sla, 1)`; otherwise it stays `null` ([app/api/queue.py:127](../../app/api/queue.py#L127)).

### Errors

| Status | Cause |
|---|---|
| `401` | Missing/invalid/expired JWT, or the user is no longer active — raised by `get_current_user` ([app/auth.py:172](../../app/auth.py#L172)). |

No `4xx` is raised inside the handler itself. An empty queue returns `200` with `[]`.

### Example

```bash
TOKEN=$(curl -s -X POST https://rounds.vin/v1/auth/login \
  -d "username=johndean@vin.com&password=<PW>" \
  | python -c "import sys,json;print(json.load(sys.stdin)['data']['access_token'])")

curl -s -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/queue/mine
```

Response (envelope applied by middleware; `data` holds the array):

```json
{
  "data": [
    {
      "session_id": "3f2c…",
      "code": "VIN-2026-001",
      "title": "Feline Cardiology Update",
      "title_short": "Feline Cardio",
      "title_long": "Feline Cardiology Update — 2026 Spring Series",
      "status": "ready",
      "current_stage": "medical",
      "entered_current_at": "2026-06-06T14:00:00+00:00",
      "overdue_hours": 3.5
    }
  ]
}
```

Frontend caller: `queue.mine()` → `GET /v1/queue/mine` ([frontend/src/services/api.ts:366](../../frontend/src/services/api.ts#L366)).

### Related Screens

- **QueueView** — route `/queue`, name `queue` ([frontend/src/router/index.ts:43](../../frontend/src/router/index.ts#L43)); component `frontend/src/views/QueueView.vue`.
- The Dashboard's "Your Queue" widget references the same data (DashboardView.vue appears in the queue-related grep set).

### Related Tables

- **`sessions`** — base table; columns `code`, `title`, `deleted_at` from [migrations/001_init.sql:13](../../migrations/001_init.sql#L13); `title_short` / `title_long` added in [migrations/011_manifest.sql:10](../../migrations/011_manifest.sql#L10).
- **`sop_state`** — joined on `session_id`; columns `current_stage`, `assignees`, `entered_current_at`, `sla_target_hours` from [migrations/003_sop.sql:5](../../migrations/003_sop.sql#L5).

---

## Source Verification
- **Files Used:** app/api/queue.py, app/auth.py, migrations/001_init.sql, migrations/003_sop.sql, migrations/011_manifest.sql, frontend/src/services/api.ts, frontend/src/router/index.ts
- **Components Used:** QueueView.vue (route `/queue`), DashboardView.vue (referenced)
- **APIs Used:** `GET /v1/queue/mine`
- **Database Tables Used:** sessions, sop_state
- **Permission Logic Used:** JWT only (CurrentUser dependency); query is implicitly scoped to `user.email`. No admin gate.
- **Confidence Score:** High — single endpoint read in full; every field, filter, and SLA constant traced to source lines; tables verified against migrations.
- **Evidence Links:** [app/api/queue.py:45](../../app/api/queue.py#L45) (decorator), [app/api/queue.py:69](../../app/api/queue.py#L69) (SLA map), [app/api/queue.py:104](../../app/api/queue.py#L104) (assignee filter), [migrations/003_sop.sql:5](../../migrations/003_sop.sql#L5) (sop_state), [app/auth.py:172](../../app/auth.py#L172) (auth)
