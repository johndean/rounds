# Workflow: Upload Watchdog Recovery

Background watchdog that recovers sessions stuck on `status='uploading'`. It targets the silent-enqueue-failure gap: cases where `/v1/gcs/upload-complete` persisted the source rows but `ingest_task` never started. Recovery re-enqueues ingest via the same `enqueue_ingest()` the `/v1/diag/reingest` operator endpoint uses.

**Feature flag:** `UPLOAD_WATCHDOG_ENABLED` — **default OFF** ([app/config.py:100](../../app/config.py#L100)). When false the task returns `{"disabled": True}` in ~1 ms ([app/tasks/upload_watchdog.py:67-68](../../app/tasks/upload_watchdog.py#L67)). Activate by setting the env var on the Railway worker service and restarting the worker; no code change required ([app/tasks/upload_watchdog.py:17-21](../../app/tasks/upload_watchdog.py#L17)).

Implemented by `upload_watchdog_task` ([app/tasks/upload_watchdog.py:51](../../app/tasks/upload_watchdog.py#L51)).

## Trigger

**Celery Beat schedule only.** The `upload-watchdog` entry fires every `UPLOAD_WATCHDOG_INTERVAL_SEC` seconds (default `60`) ([app/tasks/celery_app.py:71-76](../../app/tasks/celery_app.py#L71), [app/config.py:102](../../app/config.py#L102)). Beat is embedded in the worker process via the `-B` flag (per the module docstring at [app/tasks/upload_watchdog.py:5-8](../../app/tasks/upload_watchdog.py#L5)). There is no HTTP endpoint that invokes this task directly.

## Inputs

The task takes no arguments. Each tick reads from the DB using these config-derived parameters:

- `UPLOAD_STUCK_THRESHOLD_SEC` — default `300` (5 min). Minimum age (since `sessions.updated_at`) before a session is considered stuck ([app/config.py:101](../../app/config.py#L101)).
- `UPLOAD_WATCHDOG_COOLDOWN_SEC` — default `600` (10 min). Minimum gap between watchdog retries on the same session ([app/config.py:111](../../app/config.py#L111)).
- `UPLOAD_WATCHDOG_INTERVAL_SEC` — default `60`. Beat tick cadence (used by the schedule, not the query) ([app/config.py:102](../../app/config.py#L102)).

## Validations

A session is selected only if **all** of these hold (SQL at [app/tasks/upload_watchdog.py:76-94](../../app/tasks/upload_watchdog.py#L76)):

1. `sessions.status = 'uploading'`.
2. `sessions.updated_at < now() - UPLOAD_STUCK_THRESHOLD_SEC seconds`.
3. EXISTS a `sources` row for the session with `role IN ('audio', 'video')` — proves `/upload-complete` ran and persisted sources, so a user mid-PUT is not a false positive.
4. NO `session_audit` row for the session updated within `UPLOAD_WATCHDOG_COOLDOWN_SEC` whose `processing_log::text LIKE '%upload_watchdog%'` — avoids retry storms on a session whose broker outage is sustained.

`LIMIT 50` per tick bounds any single scan if there is a backlog ([app/tasks/upload_watchdog.py:93](../../app/tasks/upload_watchdog.py#L93)).

## Approvals

None. Fully automated.

## Notifications

None directly from the watchdog. The watchdog only re-enqueues `ingest_task`; any WS events come from the downstream ingest pipeline, not this task. The re-enqueue is recorded in `session_audit` (see Audit Events) but there is no email or WS emit in `upload_watchdog.py`.

## Outputs

- **Recovery action:** for each matched session, calls `enqueue_ingest(sid)` — the identical call the `/v1/diag/reingest` endpoint uses ([app/tasks/upload_watchdog.py:110-112](../../app/tasks/upload_watchdog.py#L110)). `ingest_task` has its own check-before-execute guards (status check, existing-segments check) that make re-enqueue idempotent (per docstring [app/tasks/upload_watchdog.py:12-15](../../app/tasks/upload_watchdog.py#L12)).
- **Return dict:** `{"scanned": <n>, "recovered": <n>}`, plus `"failures": [<sid: ExcClass>, ...]` when any re-enqueue raised ([app/tasks/upload_watchdog.py:123-129](../../app/tasks/upload_watchdog.py#L123)).
- When disabled: `{"disabled": True}` ([app/tasks/upload_watchdog.py:68](../../app/tasks/upload_watchdog.py#L68)).

## Status Changes

The watchdog itself does **not** write `sessions.status`. It re-enqueues `ingest_task`; any status transition is performed by that downstream task, not here. The session remains `uploading` until ingest progresses it ([app/tasks/upload_watchdog.py:51-132](../../app/tasks/upload_watchdog.py#L51)).

## Audit Events

For each successfully re-enqueued session, `_log_audit` appends a JSONB entry to `session_audit.processing_log` (UPSERT with `ON CONFLICT (session_id) DO UPDATE` array-append) ([app/tasks/upload_watchdog.py:135-159](../../app/tasks/upload_watchdog.py#L135)). Entry shape: `{ts, actor: "upload_watchdog", reason: "watchdog re-enqueued ingest_task"}` ([app/tasks/upload_watchdog.py:142-146](../../app/tasks/upload_watchdog.py#L142)). The `actor: "upload_watchdog"` tag is what the cooldown SELECT matches on the next tick. This is the same append pattern as `/v1/diag/reingest`'s audit write.

## Exception Handling

- `max_retries=0` — one-shot per beat tick; a task-level failure does not requeue, the next tick retries ([app/tasks/upload_watchdog.py:49](../../app/tasks/upload_watchdog.py#L49)).
- The `enqueue_ingest` import is lazy and each per-session re-enqueue is wrapped in try/except; a failure appends `"{sid}: {ExcClass}"` to `re_enqueue_failures`, logs a warning, and continues to the next session ([app/tasks/upload_watchdog.py:105-121](../../app/tasks/upload_watchdog.py#L105)).
- The engine is always disposed in a `finally` block ([app/tasks/upload_watchdog.py:131-132](../../app/tasks/upload_watchdog.py#L131)).

## Source Verification
- **Files Used:** app/tasks/upload_watchdog.py, app/config.py, app/tasks/celery_app.py
- **Components Used:** none
- **APIs Used:** none (Beat-scheduled task; no HTTP entry point)
- **Database Tables Used:** sessions, sources, session_audit
- **Permission Logic Used:** none — runs inside the Celery worker, no JWT/user context
- **Confidence Score:** High — every match criterion, default, and output traced to source; flag default OFF confirmed in config.
- **Evidence Links:** [app/config.py:100](../../app/config.py#L100), [app/tasks/upload_watchdog.py:51](../../app/tasks/upload_watchdog.py#L51), [app/tasks/upload_watchdog.py:76](../../app/tasks/upload_watchdog.py#L76), [app/tasks/celery_app.py:71](../../app/tasks/celery_app.py#L71)
