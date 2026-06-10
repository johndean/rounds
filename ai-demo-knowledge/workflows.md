# Workflows — rounds.vin

> Code-verified summary of the eleven workflow docs in [`docs/workflows/`](../docs/workflows/).
> Each section links to the full per-workflow doc (which carries its own line-level
> evidence) and restates only the load-bearing facts verified against source. No
> CE.VIN modules (Organizations/Sites/Vendors/Projects) exist in this repo and none
> are documented here.

Rounds runs two distinct control planes that are deliberately decoupled:

1. **Ingest pipeline** — Celery tasks that move a session through
   `sessions.status` (`uploading → … → ready`). Fully automated; no human approval.
2. **SOP control layer** — an 8-stage editorial workflow tracked in its own
   `sop_state` table, advanced manually. **The SOP `complete` stage does NOT drive
   `sessions.status` to `complete`** — IMPLEMENTATION NOT FOUND in the SOP handlers
   ([docs/workflows/sop-stage-advancement.md](../docs/workflows/sop-stage-advancement.md), Status Changes).

---

## 1. Ingest pipeline (`uploading → ready`)

Full doc: [docs/workflows/ingest-pipeline.md](../docs/workflows/ingest-pipeline.md)

Celery-driven pipeline that turns uploaded media + slide files into a first-pass
transcript with segments, slides, speakers, and slide alignment. Two paths,
selected by `session_templates.ai_pipeline` ([app/tasks/ingest.py:88](../app/tasks/ingest.py#L88)):

- **`enhanced`** (default) — STT chain `transcribe → anchor → normalize → fusion → align → finalize`, with `frame` + `slide_extract` in parallel.
- **`direct`** (AI MODE) — `ai_process` sends media + slides straight to Gemini multimodal and writes everything atomically, marking `ready` itself.

- **Trigger:** `enqueue_ingest(session_id)` from `/v1/gcs/upload-complete` (per the ingest task docstring, [app/tasks/ingest.py:5](../app/tasks/ingest.py#L5)).
- **Approvals:** none — fully automated between `uploading` and `ready`.
- **Status transitions** are mutated only through the FSM ([app/engines/state_machine.py:40](../app/engines/state_machine.py#L40)): `uploading → transcribing → normalizing → fusing → aligning → ready`; `ready → complete`; any task failure → `failed`; `failed → ingesting/processing` is the only escape hatch (operator reingest).
- **Gates that halt the session:** fusion gate ([app/tasks/fusion.py:156](../app/tasks/fusion.py#L156)), align GATE 1 (0 slide ranges) and GATE 2 (pre-ready) ([app/tasks/align.py:96](../app/tasks/align.py#L96)), finalize `no_segments` check ([app/tasks/finalize.py:59](../app/tasks/finalize.py#L59)).
- **Non-fatal tasks** (never mark the session failed): `slide_extract`, `lcs_discrepancies`, `template_autodetect`, background STT.
- **Notifications:** WebSocket only (`processing_update`, `metrics_update`, `session_failed`, etc.). **No email anywhere in ingest.**
- **Retry discipline:** all tasks subclass `RoundsTask` with exponential backoff (60/120/240s) and per-task `max_retries` ([app/tasks/celery_app.py:194](../app/tasks/celery_app.py#L194)).

## 2. SOP stage advancement

Full doc: [docs/workflows/sop-stage-advancement.md](../docs/workflows/sop-stage-advancement.md)

Forward-only 8-stage editorial lifecycle ([app/api/sop.py:24](../app/api/sop.py#L24)):

```
prep → copy_draft → medical → copy_final → cms → captions → qa → complete
```

- **Three entry points:** auto-init at ingest completion (`sop_auto_init_task`), lazy auto-create on first `GET /sop`, and manual `POST /sop/advance`.
- **Validation:** `_validate_transition` enforces forward-only, exactly `current_index + 1` — no jumps, no backward moves (400 on violation, [app/api/sop.py:80](../app/api/sop.py#L80)); advance rejected with 400 when `is_blocked` ([app/api/sop.py:121](../app/api/sop.py#L121)).
- **Approvals:** none. Any authenticated user advances a single step; `medical` and `qa` are positions in the order, NOT enforced approval handoffs.
- **Default SLA hours per stage:** prep 8, copy_draft 24, medical 48, copy_final 24, cms 12, captions 12, qa 8, complete 0 (BR-003).
- **Audit:** `sop.advance`, `sop.assign`, `sop.annotation`, `sop.check.resolve`, `sop.initialized` rows in `audit_events`.

## 3. SOP stage deadline notifications

Full doc: [docs/workflows/sop-deadline-email.md](../docs/workflows/sop-deadline-email.md)

Hourly Celery Beat scan (`sop_check_deadlines_task`, [app/tasks/sop_tasks.py:455](../app/tasks/sop_tasks.py#L455)) that flags overdue stages.

- **Feature flag `SOP_DEADLINE_EMAIL_ENABLED` — default OFF** ([app/config.py:110](../app/config.py#L110)). With the flag off, the WS warning + audit row still fire; only the SMTP send is gated.
- **Trigger:** Beat schedule every 3600s ([app/tasks/celery_app.py:84](../app/tasks/celery_app.py#L84)), or manual `POST /v1/diag/sop-check`.
- **Overdue gate:** `deadline = entered_current_at + sla_hours`; overdue when `now > deadline`. No grace period (BR-005).
- **Email throttle (BR-004):** at most one email per `(session_id, stage)` per 23 hours, under a Postgres advisory lock.
- **Skips** group assignees (`group:`), non-email assignees, and stages with no assignee.
- **Status changes:** none — purely additive (writes `audit_events` only).

## 4. Upload watchdog recovery

Full doc: [docs/workflows/upload-watchdog-recovery.md](../docs/workflows/upload-watchdog-recovery.md)

Background Beat task that re-enqueues sessions stuck on `status='uploading'` after a silent enqueue failure.

- **Feature flag `UPLOAD_WATCHDOG_ENABLED` — default OFF** ([app/config.py:100](../app/config.py#L100)). When false the task returns `{"disabled": True}`.
- **Selection criteria (all must hold):** `status='uploading'`, `updated_at` older than `UPLOAD_STUCK_THRESHOLD_SEC` (default 300s, BR-014), an `audio`/`video` source row EXISTS, and no watchdog audit row within `UPLOAD_WATCHDOG_COOLDOWN_SEC` (default 600s). `LIMIT 50`/tick.
- **Action:** calls the same `enqueue_ingest(sid)` as `/v1/diag/reingest`; ingest's own check-before-execute guards make this idempotent.
- **Status changes:** none directly — the downstream ingest task performs any transition.

## 5. Poll auto-placement

Full doc: [docs/workflows/poll-autoplacement.md](../docs/workflows/poll-autoplacement.md)

Anchors each unplaced poll onto the first segment of its declared slide (`auto_place_polls`, [app/services/poll_autoplace.py:84](../app/services/poll_autoplace.py#L84)).

- **Three call sites:** `finalize_task`, `ai_process_task` (direct), and manual `POST /v1/diag/autoplace-polls/{session_id}`. All non-fatal.
- **Idempotency guard:** the UPDATE only touches polls where `anchor_segment IS NULL`; a placed (or user-cleared-then-eligible) poll is never re-touched.
- **Index bridge:** extras2 emits 1-based `slide_n`; `slides.slide_index` is 0-based — the join is `slide_index + 1 = slide_n`.
- **Notification:** single `polls_autoplaced` WS event when count > 0. No email, no audit row.

## 6. Session soft-delete / restore / permanent purge

Full doc: [docs/workflows/session-soft-delete-restore-purge.md](../docs/workflows/session-soft-delete-restore-purge.md)

Three-stage trash lifecycle expressed via the `deleted_at` column (NOT `sessions.status`).

- **Soft-delete** `DELETE /v1/sessions/{id}` — gated by the `SESSION_TRASH_ALLOWED` set `{johndean@vin.com, carlab@vin.com}` (BR-002, [app/api/sessions.py:52](../app/api/sessions.py#L52)); non-members get 403.
- **List-deleted / restore / permanent** — gated by `require_admin`, which (no role arg loaded) resolves to the `johndean@vin.com` email comparison.
- **Permanent** requires prior soft-delete; a single `DELETE FROM sessions` cascades children (segments→words), while `audit_events.session_id` is `ON DELETE SET NULL` so historical audit survives.
- **Notifications / audit:** none written by these handlers (soft-delete + permanent call `release_slot`, a Redis rate-limit cleanup, not a notification).

## 7. Session edit locking

Full doc: [docs/workflows/session-edit-locking.md](../docs/workflows/session-edit-locking.md)

Single-writer advisory lock in `session_locks`, one row per session, 30s client heartbeat / 90s TTL (`LOCK_TTL_SECONDS = 90`, [app/api/locks.py:44](../app/api/locks.py#L44)).

- **Advisory only:** the DB lock never blocks data writes; enforcement is the frontend composable [`useSessionLock.ts`](../frontend/src/composables/useSessionLock.ts), which fails **closed** (read-only when not the holder or service unreachable).
- **Endpoints:** acquire / heartbeat / release (204) / holder / force-take — all require JWT.
- **`force-take` is the only admin-gated route** (`is_admin(user)` → resolves to the `johndean@vin.com` gate). Writes a `session.lock_force_take` audit row.
- **Staleness** evaluated lazily at acquire time. IMPLEMENTATION NOT FOUND: a server-side cron sweeper for expired rows.

## 8. Correction ledger + undo/redo

Full doc: [docs/workflows/correction-ledger-undo-redo.md](../docs/workflows/correction-ledger-undo-redo.md)

Append-only correction ledger (`correction_ledger`) with a per-session pointer (`ledger_pointers.current_pointer`). Rows are never mutated or deleted; undo/redo move the pointer.

- **Allowed correction types** ([app/api/corrections.py:49](../app/api/corrections.py#L49)): `slide_reassignment, text_edit, split, merge, mark_ok, chat_insert, chat_edit, chat_remove, poll_insert, poll_remove, speaker_reassignment`.
- **`split`/`merge` gated by `SPLIT_MERGE_ENABLED`** (default OFF, [app/config.py:134](../app/config.py#L134)) → 503 `SPLIT_MERGE_DISABLED` when off; all other correction types still work. Serialized on a `(session_id, "split_merge")` advisory lock (409 `SPLIT_MERGE_BUSY`).
- **Optimistic lock** on `text_edit` via `expected_content_hash` (stale autosave dropped as `{stale: True}`).
- **BR-018 auto-close:** only `text_edit` and `mark_ok` auto-close a matching discrepancy.
- **Audit:** the ledger rows themselves are the audit trail; no `audit_events` rows except a `merge.slide_mismatch` row on cross-slide merges.

## 9. Discrepancy generation & resolution

Full doc: [docs/workflows/discrepancy-generation-resolution.md](../docs/workflows/discrepancy-generation-resolution.md)

LCS diff between raw STT and AI-normalized text → `transcription_discrepancies`; Gemini classifies each as `is_meaningful` + `category`; editor edits auto-close them.

- **Generation** (`lcs_discrepancies_task`) runs after `normalize_task`; re-fireable via `POST /v1/diag/realign/{id}`. Non-fatal — "an editor convenience, not a gate."
- **Classification** (`classify_discrepancies_task`) reads `org_settings.classify_backend` (default `gemini-dev`) / `classify_model`; **must NEVER mark the session failed**.
- **Resolution:** `text_edit`/`mark_ok` correction closes the discrepancy (BR-018) and emits `discrepancy_resolved`.
- **Approvals:** none. **Notifications:** WS only, no email.

## 10. Export generation

Full doc: [docs/workflows/export-generation.md](../docs/workflows/export-generation.md)

Two surfaces: synchronous artifact export (`txt/srt/vtt/docx/html/zip`, [app/api/exports.py:41](../app/api/exports.py#L41)) and async caption burn-in (Celery `burn_captions_task`).

- **BR-016 filler stripping is format-specific:** `srt` strips markup; `vtt` deliberately preserves it; `docx`/`txt` strip fillers; `html`/`zip` run the strict CMS transform.
- **CMS publish gate (html/zip):** `_validate_cms_doc` raises `CMSValidationError` on any unresolved marker — note this is NOT caught in the export handler and would surface as a 500.
- **Approvals:** none — any authenticated user can export any format. The only publish-readiness check is the structural CMS marker validation.
- **captions.vtt** caches with ETag `W/"{session_id}-{max_correction_seq}"`; invalidates the moment any correction lands.
- **Notifications:** burn-in emits WS progress/ready/failed events; synchronous exports return bytes. No email.

## 11. Help article bulk publish & bulk-AI rewrites

Full doc: [docs/workflows/help-article-bulk-publish.md](../docs/workflows/help-article-bulk-publish.md)

Admin Help-Center CMS tooling: one synchronous `bulk-publish` endpoint + four Gemini-backed bulk-AI tasks (fix-summaries, expand-steps, expand-faqs, generate-faq-corpus).

- **All five endpoints are admin-gated** via `require_admin` → resolves to the `johndean@vin.com` email gate.
- **The publish step IS the approval:** every AI task lands its output as a draft (`is_published=FALSE`); an admin must promote it. `bulk-publish` only publishes drafts where `compute_compliance(a)['allPass']`.
- **Idempotency:** Redis SETNX key `rounds:help:task:{name}:{article_id}` (24h TTL) per article; `generate_faq_corpus` adds a global guard + `ON CONFLICT (slug) DO NOTHING`.
- **Audit:** every AI rewrite/insert emits a `help.ai_rewrite` audit row; **bulk-publish writes no audit row** (records only via `version` bump + `last_edited_by`).
- **Hard dependency:** `GEMINI_API_KEY` set. IMPLEMENTATION NOT FOUND: a `*_ENABLED` flag gating these endpoints.

---

## Source Verification
- **Files Used:** docs/workflows/ingest-pipeline.md, docs/workflows/sop-stage-advancement.md, docs/workflows/sop-deadline-email.md, docs/workflows/upload-watchdog-recovery.md, docs/workflows/poll-autoplacement.md, docs/workflows/session-soft-delete-restore-purge.md, docs/workflows/session-edit-locking.md, docs/workflows/correction-ledger-undo-redo.md, docs/workflows/discrepancy-generation-resolution.md, docs/workflows/export-generation.md, docs/workflows/help-article-bulk-publish.md; cross-checked against app/config.py, app/engines/state_machine.py, app/api/sop.py, app/api/corrections.py, app/api/sessions.py, app/api/locks.py
- **Components Used:** frontend/src/composables/useSessionLock.ts (lock enforcement, referenced)
- **APIs Used:** /v1/gcs/upload-complete, /v1/sessions/{id}/sop*, /v1/diag/sop-check, /v1/diag/reingest/{id}, /v1/diag/realign/{id}, /v1/diag/autoplace-polls/{id}, /v1/sessions/{id} (delete/restore/permanent/deleted), /v1/sessions/{id}/lock/*, /v1/sessions/{id}/corrections*, /v1/sessions/{id}/discrepancies, /v1/sessions/{id}/exports/{format}, /v1/sessions/{id}/captions*, /v1/help/admin/*
- **Database Tables Used:** sessions, session_templates, sources, segments, words, slides, bullets, speakers, normalization_results, slide_time_ranges, alignments, transcription_discrepancies, word_alignment, sop_state, sop_transitions, sop_checks, session_stage_assignees, correction_ledger, ledger_pointers, session_locks, polls, artifacts, help_articles, help_article_versions, audit_events, session_audit, org_settings
- **Permission Logic Used:** JWT (`CurrentUser`) on all routes; admin-gated surfaces (session restore/permanent/list-deleted, lock force-take, help admin) resolve to the `LEGACY_ADMIN_EMAIL = "johndean@vin.com"` gate; soft-delete via the `SESSION_TRASH_ALLOWED` set. Celery tasks run with no per-user auth.
- **Confidence Score:** High — each summary is drawn from a per-workflow doc that itself carries line-level evidence, and the load-bearing flags/transitions were re-verified directly against app/config.py and the FSM.
- **Evidence Links:** [app/engines/state_machine.py:40](../app/engines/state_machine.py#L40), [app/api/sop.py:80](../app/api/sop.py#L80), [app/config.py:100](../app/config.py#L100), [app/config.py:110](../app/config.py#L110), [app/config.py:134](../app/config.py#L134), [app/api/corrections.py:49](../app/api/corrections.py#L49)
