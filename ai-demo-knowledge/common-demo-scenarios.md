# Common Demo Scenarios — rounds.vin

End-to-end flows that work **today**, traced to the code that backs each step.
Every route, status value, and behavior below is verified against the FastAPI
routers in [`app/api/`](../app/api/) and the Vue router in
[`frontend/src/router/index.ts`](../frontend/src/router/index.ts). Where a step
depends on a default-OFF feature flag, that is called out inline.

> **Permission reality for every step below:** the only authorization enforced
> at runtime is **JWT presence** (every `/v1/*` route except `/v1/auth/login`
> depends on `CurrentUser` → `get_current_user`) plus a hardcoded
> `user.email == "johndean@vin.com"` gate on a handful of destructive/admin
> actions. There are no role tiers in effect. See
> [known-limitations.md](known-limitations.md) for the full picture.

---

## Scenario 0 — Sign in

1. The app is hash-routed. Any non-public route redirects to `#/login` when
   `auth.isAuthenticated` is false ([router/index.ts:53-67](../frontend/src/router/index.ts#L53)).
2. Login posts `username` + `password` (form-encoded) to
   `POST /v1/auth/login` ([app/api/auth.py:15-28](../app/api/auth.py#L15)).
   `username` is treated as the email.
3. `authenticate()` checks the `auth_users` table (bcrypt) first, then falls
   back to the `AUTH_USERS` env CSV if the DB has no row or errors
   ([app/auth.py:100-143](../app/auth.py#L100)).
4. On success the server returns an HS256 JWT signed with `API_SECRET_KEY`,
   expiring after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 480 = 8h)
   ([app/auth.py:153-158](../app/auth.py#L153)).
5. `GET /v1/auth/me` echoes the authenticated email ([app/api/auth.py:31-34](../app/api/auth.py#L31)).

> There is no account-lockout / failed-attempt counter in the auth code. See
> [known-limitations.md](known-limitations.md) and
> [frequently-asked-questions.md](frequently-asked-questions.md).

---

## Scenario 1 — Upload a recording (browser → GCS → ingest)

This is the canonical "happy path" demo opener.

1. **Create the session row.** `POST /v1/sessions` inserts a `sessions` row
   with `status = 'uploading'` and a matching `session_templates` row carrying
   the pipeline routing ([app/api/sessions.py:178-256](../app/api/sessions.py#L178)).
   The pipeline config fields are `ai_pipeline` (`direct`|`enhanced`),
   `ai_mode` (`transcript`|`summary`|`key-moments`|`structured-notes`|`custom-prompt`),
   `ai_model` (default `gemini-2.5-pro`), `stt_backend`, `template_id`, and
   `iil_config` ([app/api/sessions.py:56-68](../app/api/sessions.py#L56)).
2. **Get a signed upload URL.** `POST /v1/gcs/upload-url` returns a 60-minute
   v4 PUT signed URL ([app/api/gcs_upload.py:69-86](../app/api/gcs_upload.py#L69)).
   This is gated by `check_user_quota` — a user already at
   `MAX_CONCURRENT_SESSIONS` (default 3) or a queue at `MAX_QUEUE_LENGTH`
   (default 10) gets a 429 ([app/middleware/rate_limit.py:33-66](../app/middleware/rate_limit.py#L33)).
3. **Upload bytes.** The browser PUTs the file directly to GCS using the signed
   URL. The Upload view infers each file's role from its extension —
   video (`mp4/mov/mkv/webm/avi/m4v`), audio (`mp3/m4a/wav/ogg/flac/aac`),
   slide (`pdf/pptx/ppt`), or `txt` → manifest/chat
   ([frontend/src/views/UploadView.vue:86-97](../frontend/src/views/UploadView.vue#L86)).
4. **Confirm upload.** `POST /v1/gcs/upload-complete` validates every
   `gcs_uri` against the **R7 invariant** (must start with
   `gs://<bucket>/sessions/<id>/`) and 400s otherwise
   ([app/api/gcs_upload.py:110-137](../app/api/gcs_upload.py#L110)). It inserts
   `sources` rows, parses any manifest/chat files (populating
   `session_speakers`, `polls`, `poll_options`, `session_slide_resources`,
   `chat_messages`), reserves the rate-limit slot, and enqueues the Celery
   ingest pipeline via `enqueue_ingest` ([app/api/gcs_upload.py:196-219](../app/api/gcs_upload.py#L196)).

**Demo talking point:** the R7 scope check is a hard security invariant —
show it rejecting a `gcs_uri` from a different session prefix.

---

## Scenario 2 — Watch processing progress

1. After upload-complete the session moves through the status state machine.
   The allowed `sessions.status` values are `uploading`, `transcribing`,
   `normalizing`, `fusing`, `aligning`, `ready`, `complete`, `failed`
   (see the data dictionary's `sessions` entry and migration 010 CHECK;
   referenced in [data-model-reference.md](data-model-reference.md)).
2. The Processing view (`#/p/:id`) reads session status. The per-session
   processing log is exposed by
   `GET /v1/sessions/{id}/audit-log` (returns `session_audit.processing_log`,
   an append-only `[{ts, prev, next, actor, reason}]` array)
   ([app/api/sessions.py:306-320](../app/api/sessions.py#L306)).
3. If a session ends in `failed`, `GET /v1/sessions/{id}/failure-reason`
   surfaces the last failed transition's `reason` + a 10-entry log tail
   ([app/api/sessions.py:753-804](../app/api/sessions.py#L753)).

**Operator rescue (curl-only, no UI):** a stuck session can be re-ingested via
`POST /v1/diag/reingest/<id>` (admin-gated). See CLAUDE.md's operator section.

---

## Scenario 3 — Edit the transcript

The Editor (`#/e/:id`) is the heart of the demo.

1. **Load segments.** `GET /v1/sessions/{id}/segments` returns ordered
   segments. Effective text follows a 3-layer precedence: user edit from
   `correction_ledger` (≤ the undo/redo pointer) → normalized text
   (`normalization_results`) → raw `segments.text`
   ([app/api/segments.py:70-117](../app/api/segments.py#L70)).
2. **Take the edit lock.** Before editing, the client acquires a single-writer
   lock: `POST /v1/sessions/{id}/lock/acquire`. If someone else holds a fresh
   lock the response is `acquired: false` with the holder's email; a stale lock
   (TTL 90s) is auto-stolen ([app/api/locks.py:99-139](../app/api/locks.py#L99)).
   The client heartbeats every ~30s via `/lock/heartbeat` and releases on tab
   close via `/lock/release` ([app/api/locks.py:142-201](../app/api/locks.py#L142)).
3. **Save an edit.** Inline saves post to
   `POST /v1/sessions/{id}/corrections` with `correction_type` one of
   `slide_reassignment`, `text_edit`, `split`, `merge`, `mark_ok`,
   `chat_insert`, `chat_edit`, `chat_remove`, `poll_insert`, `poll_remove`,
   `speaker_reassignment` ([app/api/corrections.py:49-53](../app/api/corrections.py#L49)).
   The ledger is **append-only** — no UPDATE/DELETE.
4. **Undo / Redo.** `POST /v1/sessions/{id}/corrections/undo` and `/redo` move
   the `ledger_pointers.current_pointer`; rows are never mutated
   ([app/api/corrections.py:16-19](../app/api/corrections.py#L16)).
5. **Find / Replace.** `POST /v1/sessions/{id}/find-replace` does a bulk
   `text_edit` with a `dry_run` preview ([app/api/corrections.py:15](../app/api/corrections.py#L15)).
6. **Reassign speaker / slide.** Patch a segment via
   `PATCH /v1/sessions/{id}/segments/{segment_id}` (fields `text`, `slide_id`,
   `speaker_id`, `flags`, `start_ms`, `end_ms`)
   ([app/api/segments.py:37-56](../app/api/segments.py#L37)).

> **Split / Merge is behind a default-OFF flag.** A `split`/`merge` correction
> returns `503 SPLIT_MERGE_DISABLED` unless `SPLIT_MERGE_ENABLED=true`
> ([app/api/corrections.py:362-363](../app/api/corrections.py#L362),
> [app/config.py:134](../app/config.py#L134)). The frontend reads this flag from
> `/v1/version` at mount ([app/main.py:188](../app/main.py#L188)) and hides the
> Split/Merge controls when off. Do not demo split/merge unless the flag is set
> in the target environment.

---

## Scenario 4 — Review discrepancies

1. The Editor's Discrepancies tab calls
   `GET /v1/sessions/{id}/discrepancies` ([app/api/discrepancies.py:49-111](../app/api/discrepancies.py#L49)).
2. This reads from `transcription_discrepancies` (the per-segment LCS diff
   between AI-normalized text and raw STT), **not** the legacy `discrepancies`
   table. Each row carries `ai_text`, `stt_text`, `category`, `is_meaningful`,
   `classifier_model`, `classified_at` ([app/api/discrepancies.py:29-39](../app/api/discrepancies.py#L29)).
3. Optional filters: `?category=` (`medication`|`terminology`|`filler`|
   `punctuation`|`drift`|`low_confidence`|`other`) and `?meaningful_only=true`
   ([app/api/discrepancies.py:54-70](../app/api/discrepancies.py#L54)).
4. The response carries a `classification_status` of `complete` | `partial` |
   `pending` so the UI can show whether the classifier finished
   ([app/api/discrepancies.py:96-103](../app/api/discrepancies.py#L96)).
5. **Resolving** a discrepancy: applying a `text_edit` at the segment, or a
   `mark_ok` correction, auto-closes the related discrepancy (BR-018). Other
   correction types deliberately do not auto-close
   ([app/api/corrections.py:55-63](../app/api/corrections.py#L55)).

---

## Scenario 5 — Drive the SOP workflow

The 8-stage workflow is the "finishing" half of the demo.

1. **Read state.** `GET /v1/sessions/{id}/sop` returns `current_stage`,
   `is_blocked`, `blockers`, `assignees`, `sla_target_hours`. It auto-creates
   the `sop_state` row at `prep` on first read
   ([app/api/sop.py:93-110](../app/api/sop.py#L93)).
2. **Stages (canonical order):** `prep` → `copy_draft` → `medical` →
   `copy_final` → `cms` → `captions` → `qa` → `complete`
   ([app/api/sop.py:24](../app/api/sop.py#L24)).
3. **Advance.** `POST /v1/sessions/{id}/sop/advance` is **forward-only by
   exactly one stage** — backward moves and jumps are rejected 400, and you
   cannot advance while `is_blocked` ([app/api/sop.py:80-90](../app/api/sop.py#L80),
   [app/api/sop.py:113-142](../app/api/sop.py#L113)). Each advance writes a
   `sop_transitions` row + an `audit_events` row.
4. **Assign / annotate / resolve checks.** `POST .../sop/assign`,
   `PATCH .../sop/annotations` (kinds `note`|`override`|`blocker`), and
   `POST .../sop/checks/resolve` mutate the stage state and audit it
   ([app/api/sop.py:145-268](../app/api/sop.py#L145)).
5. **Dashboard rollup.** `GET /v1/sop/dashboard-summary` returns per-stage
   `count` + `overdue_count`. Overdue is computed in Python against
   `sla_target_hours` (per-stage defaults: prep 8, copy_draft 24, medical 48,
   copy_final 24, cms 12, captions 12, qa 8, complete 0)
   ([app/api/sop.py:279-325](../app/api/sop.py#L279)).

> **Deadline emails are default-OFF.** The hourly `sop_check_deadlines_task`
> only sends mail when `SOP_DEADLINE_EMAIL_ENABLED=true`
> ([app/config.py:110](../app/config.py#L110)). With the flag off, overdue
> stages are still counted and shown — no email goes out.

---

## Scenario 6 — Export the finished transcript

1. The Editor's Export menu hits `GET /v1/sessions/{id}/exports/{format}`.
   Supported formats: `txt`, `srt`, `vtt`, `docx`, `html`, `zip`
   ([app/api/exports.py:31-38](../app/api/exports.py#L31),
   [app/api/exports.py:41-53](../app/api/exports.py#L41)). An unknown format
   returns 400 `INVALID_FORMAT`.
2. The artifact is generated **fresh from the current transcript** every call
   via `app/engines/artifact_transformer.py`, then an `artifacts` row is
   upserted (idempotent on `(session_id, kind)`)
   ([app/api/exports.py:55-108](../app/api/exports.py#L55)).
3. The download filename is `<session.code>.<format>`
   ([app/api/exports.py:103-107](../app/api/exports.py#L103)).
4. **Captions for the video `<track>`:** `GET /v1/sessions/{id}/captions.vtt`
   is a cache-friendly WebVTT route with an ETag that fingerprints
   `(session_id, max correction_ledger.sequence_number)` — it returns 304 until
   a new correction lands ([app/api/exports.py:120-176](../app/api/exports.py#L120)).

> The CLAUDE.md note that "filler words are stripped from docx/txt but kept in
> srt/vtt" is a behavior of `artifact_transformer` (BR-016, referenced in the
> exports module docstring). The format-specific stripping itself lives in
> `app/engines/artifact_transformer.py` — NOT VERIFIED IN CODE here at the
> line level; verify in that engine before stating it as fact in a demo.

---

## Scenario 7 — Session lifecycle (delete / restore / purge)

1. **Soft-delete.** `DELETE /v1/sessions/{id}` sets `deleted_at`; allowed only
   for emails in `SESSION_TRASH_ALLOWED` = `{johndean@vin.com, carlab@vin.com}`
   ([app/api/sessions.py:52](../app/api/sessions.py#L52),
   [app/api/sessions.py:621-665](../app/api/sessions.py#L621)). Data is kept and
   the rate-limit slot is released.
2. **List trash.** `GET /v1/sessions/deleted` (admin only via `require_admin`)
   shows soft-deleted sessions within a 30-day window
   ([app/api/sessions.py:266-303](../app/api/sessions.py#L266)).
3. **Restore.** `POST /v1/sessions/{id}/restore` clears `deleted_at` — admin
   only ([app/api/sessions.py:668-694](../app/api/sessions.py#L668)).
4. **Permanent purge.** `DELETE /v1/sessions/{id}/permanent` hard-deletes
   (must be soft-deleted first) — admin only, irreversible
   ([app/api/sessions.py:697-750](../app/api/sessions.py#L697)).

> "Admin" here means the hardcoded `LEGACY_ADMIN_EMAIL` (`johndean@vin.com`)
> via `require_admin` — not a role column ([app/security/roles.py:54](../app/security/roles.py#L54)).

---

## What NOT to demo (flag- or scaffold-gated)

| Feature | Why | Evidence |
|---|---|---|
| Segment Split / Merge | `SPLIT_MERGE_ENABLED` default false → 503 | [app/config.py:134](../app/config.py#L134), [app/api/corrections.py:362](../app/api/corrections.py#L362) |
| Help Center "Ask AI" tab | `HELP_ASK_AI_ENABLED` default false → 404 | [app/config.py:121](../app/config.py#L121), [app/api/help.py:174](../app/api/help.py#L174) |
| SOP deadline emails | `SOP_DEADLINE_EMAIL_ENABLED` default false | [app/config.py:110](../app/config.py#L110) |
| Upload-stuck auto-recovery | `UPLOAD_WATCHDOG_ENABLED` default false | [app/config.py:100](../app/config.py#L100) |
| Role-based admin tiers | `auth_users.role` not read by `get_current_user` | [app/security/roles.py:10-19](../app/security/roles.py#L10) |

---

## Source Verification
- **Files Used:** `app/api/auth.py`, `app/auth.py`, `app/api/sessions.py`, `app/api/gcs_upload.py`, `app/middleware/rate_limit.py`, `app/api/segments.py`, `app/api/corrections.py`, `app/api/locks.py`, `app/api/discrepancies.py`, `app/api/sop.py`, `app/api/exports.py`, `app/config.py`, `app/security/roles.py`, `app/main.py`, `frontend/src/router/index.ts`, `frontend/src/views/UploadView.vue`
- **Components Used:** `UploadView.vue` (file-role inference); Editor / Processing / SOP / Sessions views referenced via the Vue router
- **APIs Used:** `POST /v1/auth/login`, `GET /v1/auth/me`, `POST /v1/sessions`, `GET/PATCH/DELETE /v1/sessions/{id}`, `GET /v1/sessions/deleted`, `POST /v1/sessions/{id}/restore`, `DELETE /v1/sessions/{id}/permanent`, `GET /v1/sessions/{id}/audit-log`, `GET /v1/sessions/{id}/failure-reason`, `POST /v1/gcs/upload-url`, `POST /v1/gcs/upload-complete`, `GET /v1/sessions/{id}/segments`, `PATCH /v1/sessions/{id}/segments/{segment_id}`, `POST /v1/sessions/{id}/corrections` (+ `/undo`, `/redo`), `POST /v1/sessions/{id}/find-replace`, `POST /v1/sessions/{id}/lock/*`, `GET /v1/sessions/{id}/discrepancies`, `GET/POST /v1/sessions/{id}/sop` (+ `/advance`, `/assign`, `/annotations`, `/checks/resolve`), `GET /v1/sop/dashboard-summary`, `GET /v1/sessions/{id}/exports/{format}`, `GET /v1/sessions/{id}/captions.vtt`
- **Database Tables Used:** `sessions`, `session_templates`, `sources`, `segments`, `correction_ledger`, `ledger_pointers`, `normalization_results`, `transcription_discrepancies`, `session_locks`, `sop_state`, `sop_transitions`, `sop_checks`, `audit_events`, `session_audit`, `artifacts`, `auth_users`
- **Permission Logic Used:** JWT presence (`CurrentUser`) on every route + `LEGACY_ADMIN_EMAIL`/`SESSION_TRASH_ALLOWED` gate on destructive session ops + admin force-take lock
- **Confidence Score:** High — every step links to the exact router line; the one un-line-verified claim (format-specific filler stripping) is tagged NOT VERIFIED IN CODE.
- **Evidence Links:** [app/api/gcs_upload.py:110](../app/api/gcs_upload.py#L110), [app/api/sop.py:80](../app/api/sop.py#L80), [app/api/corrections.py:362](../app/api/corrections.py#L362), [app/api/exports.py:41](../app/api/exports.py#L41), [app/api/locks.py:99](../app/api/locks.py#L99)
