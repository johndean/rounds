# Frequently Asked Questions — rounds.vin (code-verified)

This is the demo-AI version of the operator FAQ. It is synthesized from
[`docs/help-center/faq.md`](../docs/help-center/faq.md) and
[`app/data/help_content.py`](../app/data/help_content.py), then **checked against
the implementation**. Where the help-center copy and the code disagree, the code
wins and the discrepancy is flagged so a demo AI never repeats an unverified
claim.

> **Authorization reality:** every answer that says "admins can…" means the
> single hardcoded `LEGACY_ADMIN_EMAIL` (`johndean@vin.com`), not a role tier.
> `auth_users.role` exists but is not read at request time
> ([app/security/roles.py:10-19](../app/security/roles.py#L10),
> [app/security/roles.py:54](../app/security/roles.py#L54)).

---

## Getting started

**What is rounds.vin?**
Transcript software for VIN. You upload a recorded session; an AI pipeline
produces a first-pass transcript with speaker labels and slide alignment; then
the transcript moves through an 8-stage workflow (`prep → copy_draft → medical
→ copy_final → cms → captions → qa → complete`) before CMS export
([app/api/sop.py:24](../app/api/sop.py#L24)).

**How do I sign in?**
`POST /v1/auth/login` with your email as the username
([app/api/auth.py:15-28](../app/api/auth.py#L15)). On success you get a JWT good
for 8 hours by default (`ACCESS_TOKEN_EXPIRE_MINUTES = 480`)
([app/auth.py:153-158](../app/auth.py#L153), [app/config.py:43](../app/config.py#L43)).

**I forgot my password — what do I do?**
Contact your admin to set a new password.

> ⚠️ **Flag:** the help-center FAQ adds "Five failed sign-in attempts in fifteen
> minutes will briefly lock the account"
> ([app/data/help_content.py:250](../app/data/help_content.py#L250)). **This
> lockout is NOT IMPLEMENTED IN CODE.** `authenticate()` and the login route
> have no attempt counter or lockout window
> ([app/auth.py:100-143](../app/auth.py#L100), [app/api/auth.py:15-28](../app/api/auth.py#L15)).
> Do not state the lockout behavior as fact in a demo.

**Why does the app sometimes say "Slow down" / return 429?**
Upload requests are rate-limited per user: a 429 `RATE_LIMIT_USER` fires when
you already have `MAX_CONCURRENT_SESSIONS` (default 3) in flight, and a 429
`RATE_LIMIT_QUEUE` fires when the global ingest queue is at `MAX_QUEUE_LENGTH`
(default 10) ([app/middleware/rate_limit.py:33-66](../app/middleware/rate_limit.py#L33),
[app/config.py:46-47](../app/config.py#L46)). Wait, then retry.

---

## Uploading & processing

**What file types can I upload?**
The Upload view infers a role from the file extension
([frontend/src/views/UploadView.vue:86-97](../frontend/src/views/UploadView.vue#L86)):
- **Video:** mp4, mov, mkv, webm, avi, m4v
- **Audio:** mp3, m4a, wav, ogg, flac, aac
- **Slides:** pdf, pptx, ppt
- **Text (`.txt`):** treated as a manifest (if the name matches `extras2` /
  `_manifest` / `manifest_`) or otherwise a chat transcript

> ⚠️ **Flag:** the help-center FAQ says "MP4, MOV, and WAV … and PDFs … The
> upload page rejects other types up front." That is **inaccurate**. The code
> accepts a much wider set, and unknown extensions are not rejected — they fall
> through to `role: 'other'`
> ([frontend/src/views/UploadView.vue:96](../frontend/src/views/UploadView.vue#L96)).
> The drag-drop hint in the UI reads "Video, audio, PDF, PPTX, text · multiple
> files supported" ([frontend/src/views/UploadView.vue:372](../frontend/src/views/UploadView.vue#L372)).

**Is there a size / length limit?**
`upload-complete` rejects media longer than `MAX_VIDEO_DURATION_MINUTES`
(default 180) and rejects `audio_enhance` files under ~100 KB as likely-silent
([app/middleware/rate_limit.py:98-129](../app/middleware/rate_limit.py#L98)).
`MAX_UPLOAD_SIZE_MB` defaults to 2048 ([app/config.py:48](../app/config.py#L48)).

**What is "AI Mode" vs "Default Mode"?**
The pipeline routing recorded at upload uses two fields, not those exact labels:
- `ai_pipeline`: `direct` (standard STT) or `enhanced` (richer pass)
- `ai_mode`: `transcript` | `summary` | `key-moments` | `structured-notes` |
  `custom-prompt`
([app/api/sessions.py:56-68](../app/api/sessions.py#L56)). The default model is
`gemini-2.5-pro` ([app/api/sessions.py:63](../app/api/sessions.py#L63)).

> ⚠️ **Flag:** the help-center "AI Mode / Default Mode" wording is end-user
> framing; map it to `ai_pipeline` (`enhanced` vs `direct`) when talking to
> anyone technical. Processing-time estimates ("ten to fifteen minutes per hour
> of video") are help-center copy, NOT a code-enforced value — do not present
> them as a guarantee.

**My upload says it is stuck — what now?**
There is a background watchdog that can recover sessions stuck on
`status='uploading'`, but it is **default-OFF** (`UPLOAD_WATCHDOG_ENABLED`,
[app/config.py:100](../app/config.py#L100)). With it off, recovery is manual: an
admin re-ingests via `POST /v1/diag/reingest/<id>` (curl-only operator tool).

**Can I retry a failed session safely?**
Yes — `POST /v1/diag/reingest/<id>` restarts the pipeline from the upload; the
ingest tasks are built to be retried (Celery retry with backoff,
`CELERY_MAX_RETRIES = 3`, [app/config.py:74](../app/config.py#L74)). It is
admin-gated.

---

## Editing a transcript

**How do I edit a segment?**
Click the segment, edit, save. The save posts a `text_edit` correction to
`POST /v1/sessions/{id}/corrections`
([app/api/corrections.py:14](../app/api/corrections.py#L14)). The ledger is
append-only — your edit is recorded as a new row, never an overwrite.

**Can I undo it?**
Yes. `POST .../corrections/undo` and `/redo` move a per-session pointer; nothing
is deleted ([app/api/corrections.py:17-18](../app/api/corrections.py#L17)). The
displayed text resolves edits ≤ the current pointer
([app/api/segments.py:77-93](../app/api/segments.py#L77)).

**Can two people edit the same session at once?**
No. Editing is single-writer via a session lock (TTL 90s). A second editor sees
the holder and drops to read-only; an admin can force-take a stuck lock
([app/api/locks.py:99-139](../app/api/locks.py#L99),
[app/api/locks.py:218-262](../app/api/locks.py#L218)).

**Can I split or merge segments?**
Only if `SPLIT_MERGE_ENABLED=true` in the target environment. With the flag off
(the default), a `split`/`merge` correction returns `503 SPLIT_MERGE_DISABLED`
and the UI hides the controls
([app/config.py:134](../app/config.py#L134), [app/api/corrections.py:362-363](../app/api/corrections.py#L362)).

---

## Discrepancies & quality

**Why is a segment flagged?**
The discrepancy list is the per-segment LCS diff between AI-normalized text and
raw STT, classified into categories (`medication`, `terminology`, `filler`,
`punctuation`, `drift`, `low_confidence`, `other`) with an `is_meaningful` flag
([app/api/discrepancies.py:54-70](../app/api/discrepancies.py#L54)). It reads
from `transcription_discrepancies`.

**How do I clear a discrepancy?**
Apply a `text_edit` at that segment (which auto-closes it) or apply a `mark_ok`
correction for "no change needed". Other correction types do not auto-close
(BR-018, [app/api/corrections.py:55-63](../app/api/corrections.py#L55)).

---

## Workflow & publishing

**What are the SOP stages?**
`prep → copy_draft → medical → copy_final → cms → captions → qa → complete`.
The session advances **one stage forward at a time** — backward moves and jumps
are rejected, and you cannot advance while blocked
([app/api/sop.py:24](../app/api/sop.py#L24), [app/api/sop.py:80-90](../app/api/sop.py#L80)).

**What happens if a stage runs past its deadline?**
The dashboard counts it as overdue against the per-stage SLA
([app/api/sop.py:279-325](../app/api/sop.py#L279)). A deadline **email** is sent
only if `SOP_DEADLINE_EMAIL_ENABLED=true`; this is default-OFF
([app/config.py:110](../app/config.py#L110)), so by default no email is sent.

**Where do exports come from?**
`GET /v1/sessions/{id}/exports/{format}` regenerates the file fresh from the
current transcript every call. Formats: `txt`, `srt`, `vtt`, `docx`, `html`,
`zip` ([app/api/exports.py:31-38](../app/api/exports.py#L31)).

---

## Sessions & history

**I deleted a session by accident — can I get it back?**
If you are an admin, yes — `POST /v1/sessions/{id}/restore` within the 30-day
window ([app/api/sessions.py:668-694](../app/api/sessions.py#L668)). Permanent
purge (`DELETE .../permanent`) is irreversible and requires the session to be
soft-deleted first ([app/api/sessions.py:697-750](../app/api/sessions.py#L697)).

**Who can delete a session?**
Only emails in `SESSION_TRASH_ALLOWED` (`johndean@vin.com`, `carlab@vin.com`)
can soft-delete; restore + permanent purge are `johndean@vin.com` only
([app/api/sessions.py:52](../app/api/sessions.py#L52),
[app/api/sessions.py:630](../app/api/sessions.py#L630)).

**Where can I see who edited a transcript?**
Audit is split across `audit_events` (global UI-action log),
`correction_ledger` (append-only edits), and `sop_transitions` (stage moves).
The Editor's Audit tab and the Audit view read these.

---

## Help & support

**When will Ask AI work?**
The Help Center "Ask AI" tab is gated by `HELP_ASK_AI_ENABLED` (default OFF). The
`/v1/help/ask` endpoint returns 404 when off
([app/config.py:121](../app/config.py#L121), [app/api/help.py:174](../app/api/help.py#L174)).
The frontend reads this flag from `/v1/version` and only shows the tab when true
([app/main.py:183](../app/main.py#L183)).

---

## Source Verification
- **Files Used:** `docs/help-center/faq.md`, `app/data/help_content.py`, `app/api/auth.py`, `app/auth.py`, `app/config.py`, `app/middleware/rate_limit.py`, `frontend/src/views/UploadView.vue`, `app/api/sessions.py`, `app/api/corrections.py`, `app/api/segments.py`, `app/api/locks.py`, `app/api/discrepancies.py`, `app/api/sop.py`, `app/api/exports.py`, `app/api/help.py`, `app/main.py`, `app/security/roles.py`
- **Components Used:** `UploadView.vue` (extension→role inference + UI hint text)
- **APIs Used:** `POST /v1/auth/login`, `POST /v1/gcs/upload-url`, `POST /v1/gcs/upload-complete`, `POST /v1/sessions/{id}/corrections` (+ `/undo`, `/redo`), `GET /v1/sessions/{id}/segments`, `POST /v1/sessions/{id}/lock/*`, `GET /v1/sessions/{id}/discrepancies`, `GET/POST /v1/sessions/{id}/sop` (+ `/advance`), `GET /v1/sessions/{id}/exports/{format}`, `POST /v1/sessions/{id}/restore`, `DELETE /v1/sessions/{id}/permanent`, `POST /v1/help/ask`
- **Database Tables Used:** `auth_users`, `sessions`, `session_templates`, `correction_ledger`, `ledger_pointers`, `transcription_discrepancies`, `session_locks`, `sop_state`, `sop_transitions`, `audit_events`, `artifacts`
- **Permission Logic Used:** JWT presence + `LEGACY_ADMIN_EMAIL` / `SESSION_TRASH_ALLOWED` gate
- **Confidence Score:** High — all factual claims line-linked; two help-center claims (account lockout, narrow file-type list) were found false vs code and flagged as IMPLEMENTATION NOT FOUND / inaccurate rather than repeated.
- **Evidence Links:** [app/auth.py:100](../app/auth.py#L100) (no lockout), [frontend/src/views/UploadView.vue:86](../frontend/src/views/UploadView.vue#L86) (wide file types), [app/api/sop.py:80](../app/api/sop.py#L80) (forward-only), [app/config.py:121](../app/config.py#L121) (Ask AI flag)
