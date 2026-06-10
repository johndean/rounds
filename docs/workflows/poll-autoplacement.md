# Workflow: Poll Auto-Placement

Auto-anchors each unplaced poll onto the first segment of its declared slide. Polls arrive from the extras2 manifest with a 1-based `slide_n` preserved in `polls.metadata`. Until this service runs, `polls.anchor_segment` is NULL and the poll shows as unplaced in the right-rail Polls panel for the operator to drag manually.

Implemented by `auto_place_polls` ([app/services/poll_autoplace.py:84](../../app/services/poll_autoplace.py#L84)).

## Trigger

`auto_place_polls(engine, session_id)` is called from three sites:

1. **Ingest pipeline — `finalize_task`** ([app/tasks/finalize.py:113-120](../../app/tasks/finalize.py#L113)). Runs after `align_task` has assigned `segment.slide_id`, so the JOIN has data. Non-fatal.
2. **Ingest pipeline — `ai_process_task` (AI-mode direct shortcut)** ([app/tasks/ai_process.py:519-526](../../app/tasks/ai_process.py#L519)). Runs just before the `uploading → ready` transition. Non-fatal.
3. **Manual operator backfill — `POST /v1/diag/autoplace-polls/{session_id}`** ([app/api/diagnostics.py:251-278](../../app/api/diagnostics.py#L251)). Re-runs placement for an already-ingested session; useful for sessions that completed before the service was wired, or to restore defaults after an operator cleared anchors.

## Inputs

- `engine_or_conn` — a SQLAlchemy `Engine` (opens its own transaction) or an open `Connection` (joins the caller's transaction, letting ingest fold placement atomically into its segment writes) ([app/services/poll_autoplace.py:84-106](../../app/services/poll_autoplace.py#L84)).
- `session_id` — bound as `:sid` (cast to uuid) in the SQL ([app/services/poll_autoplace.py:97-98](../../app/services/poll_autoplace.py#L97)).

Reads from `segments`, `slides`, and `polls` for the session. The placement logic is a single SQL statement ([app/services/poll_autoplace.py:60-81](../../app/services/poll_autoplace.py#L60)):
- A CTE selects `DISTINCT ON (slide_index)` the first segment per slide, ordered by `start_ms ASC, seq ASC`.
- An UPDATE sets `polls.anchor_segment` and `placed = TRUE` for matching unplaced polls.

## Validations

Enforced in the SQL WHERE clauses ([app/services/poll_autoplace.py:67-79](../../app/services/poll_autoplace.py#L67)):

- CTE side: `seg.session_id = :sid`, `sl.session_id = :sid`, and `seg.slide_id IS NOT NULL` (only aligned segments).
- UPDATE side: `p.session_id = :sid`, `p.anchor_segment IS NULL` (only unplaced polls — this is the idempotency guard; once a user or this service has placed a poll, it is never touched again), `p.metadata ? 'slide_n'` (poll must carry a slide number), and `(p.metadata->>'slide_n')::int = fs.slide_index + 1`.
- **Index convention bridge:** extras2 emits `slide_n` as 1-based; `slides.slide_index` is 0-based (set as `marker - 1` by ai_process.py). The join bridges with `slide_index + 1 = slide_n` ([app/services/poll_autoplace.py:29-32](../../app/services/poll_autoplace.py#L29)).
- Polls whose `slide_n` has no aligned segment are silently skipped (the JOIN finds no match); they stay unplaced for manual drag ([app/services/poll_autoplace.py:36-38](../../app/services/poll_autoplace.py#L36)).

## Approvals

None. Automated placement; the operator can override afterward by dragging polls (drag-to-place and drag-to-clear continue to work, and a cleared poll with `anchor_segment IS NULL` becomes re-eligible on the next run) ([app/services/poll_autoplace.py:16-18](../../app/services/poll_autoplace.py#L16)).

## Notifications

When `count > 0`, publishes a single WebSocket event `{"type": "polls_autoplaced", "count": <n>}` via `publish_ws_event_sync` ([app/services/poll_autoplace.py:110-117](../../app/services/poll_autoplace.py#L110)). WS emit failure is caught and logged at debug level (non-fatal). No email.

## Outputs

- **Return value:** the integer count of polls newly placed (length of the `RETURNING p.id` rows) ([app/services/poll_autoplace.py:101-121](../../app/services/poll_autoplace.py#L101)).
- **DB writes:** `polls.anchor_segment` (segment FK) and `polls.placed = TRUE` for each matched poll ([app/services/poll_autoplace.py:72-80](../../app/services/poll_autoplace.py#L72)).
- **`/v1/diag/autoplace-polls/{session_id}` response:** `AutoplacePollsResult{session_id, placed, detail}` ([app/api/diagnostics.py:245-276](../../app/api/diagnostics.py#L245)).
- Logs `placed=<n>` on success or `placed=0 (none unplaced or no slide matches)` when nothing matched ([app/services/poll_autoplace.py:108-119](../../app/services/poll_autoplace.py#L108)).

## Status Changes

None. This service does not touch `sessions.status`. (In the ingest call sites the surrounding task performs the `uploading → ready` transition separately — e.g. [app/tasks/ai_process.py:528-533](../../app/tasks/ai_process.py#L528) — but that is the task's responsibility, not this service's.)

## Audit Events

None. `auto_place_polls` writes no `audit_events` or `session_audit` rows. The docstring notes this is a deliberate simplification from MIC, which used a `poll_insert` correction row as its placement ledger; Rounds uses the structured `polls.anchor_segment` column directly with no ledger ([app/services/poll_autoplace.py:20-27](../../app/services/poll_autoplace.py#L20)).

## Exception Handling

- The service performs one SQL statement; on the Engine path it opens its own `begin()` transaction ([app/services/poll_autoplace.py:103-106](../../app/services/poll_autoplace.py#L103)).
- All three call sites wrap the call in try/except and treat failure as non-fatal — a failure logs a warning and leaves polls unplaced rather than blocking the session from reaching `ready` ([app/tasks/finalize.py:113-120](../../app/tasks/finalize.py#L113), [app/tasks/ai_process.py:520-526](../../app/tasks/ai_process.py#L520), docstring [app/services/poll_autoplace.py:39-41](../../app/services/poll_autoplace.py#L39)).
- The diag endpoint catches exceptions and returns them in the `detail` field with `placed=0`, always disposing the engine in `finally` ([app/api/diagnostics.py:269-278](../../app/api/diagnostics.py#L269)).
- The WS emit is independently wrapped so a broker failure does not undo the DB placement ([app/services/poll_autoplace.py:110-117](../../app/services/poll_autoplace.py#L110)).

## Source Verification
- **Files Used:** app/services/poll_autoplace.py, app/api/diagnostics.py, app/tasks/finalize.py, app/tasks/ai_process.py
- **Components Used:** none
- **APIs Used:** POST /v1/diag/autoplace-polls/{session_id} (manual backfill)
- **Database Tables Used:** polls, segments, slides
- **Permission Logic Used:** /v1/diag/autoplace-polls requires JWT (CurrentUser); no admin gate. Ingest-pipeline call sites run in the worker with no user context.
- **Confidence Score:** High — SQL, idempotency guard, WS event, and all three call sites verified in source.
- **Evidence Links:** [app/services/poll_autoplace.py:60](../../app/services/poll_autoplace.py#L60), [app/services/poll_autoplace.py:84](../../app/services/poll_autoplace.py#L84), [app/api/diagnostics.py:251](../../app/api/diagnostics.py#L251), [app/tasks/finalize.py:116](../../app/tasks/finalize.py#L116), [app/tasks/ai_process.py:522](../../app/tasks/ai_process.py#L522)
