# Workflow: Export Generation

Exports turn a `ready` (or further-along) session's `segments` + `slides` + `speakers` + `chat` + `polls` + `resources` into downloadable artifacts. There are two distinct surfaces:

1. **Synchronous artifact export** — `txt / srt / vtt / docx / html / zip` produced inline by the request handler and streamed back ([app/api/exports.py:41](../../app/api/exports.py#L41)).
2. **Asynchronous caption burn-in** — a Celery task renders subtitles into a copy of the source MP4 and stores it in GCS ([app/tasks/burn_captions.py:207](../../app/tasks/burn_captions.py#L207)).

A dedicated cache-friendly `captions.vtt` route serves the HTML5 `<track>` element ([app/api/exports.py:120](../../app/api/exports.py#L120)).

---

## Trigger

- **Artifact download:** `GET /v1/sessions/{id}/exports/{format}` ([app/api/exports.py:41](../../app/api/exports.py#L41)).
- **Captions VTT (cached):** `GET /v1/sessions/{id}/captions.vtt` ([app/api/exports.py:120](../../app/api/exports.py#L120)).
- **Caption burn-in:** `POST /v1/sessions/{id}/captions/burn` enqueues `burn_captions_task` ([app/api/session_resources.py:92](../../app/api/session_resources.py#L92), [app/api/session_resources.py:120](../../app/api/session_resources.py#L120)). Latest burned artifact fetched via `GET .../captions/current` ([app/api/session_resources.py:133](../../app/api/session_resources.py#L133)).

## Inputs

- **Export:** `session_id`, `format` ∈ `{txt, srt, vtt, docx, html, zip}` ([app/api/exports.py:31](../../app/api/exports.py#L31)). The data loader `load_session_for_export` reads everything in one pass ([app/engines/artifact_transformer.py:545](../../app/engines/artifact_transformer.py#L545)): `sessions` (code, title, presenter, duration_sec, publishing_links, polls_parsed), `segments` (joined to `slides` + `speakers`, ordered by `seq`), `slides` (joined to `bullets`), `chat_messages`, `session_slide_resources`.
- **Captions VTT:** `session_id`; request header `If-None-Match` for conditional fetch.
- **Burn-in** (`BurnCaptionsRequest`): optional `style_config` dict ([app/api/session_resources.py:75](../../app/api/session_resources.py#L75)). `caption_source` ∈ `{ai, stt}` is read from `style_config` (default `ai`) ([app/tasks/burn_captions.py:236](../../app/tasks/burn_captions.py#L236)). `style_config_to_ass` accepts: `font_family`, `font_size`, `text_color`, `outline_color`, `outline_thickness`, `shadow`, `background`, `bold`, `italic`, `vertical_position`, `horizontal_align`, `margin` ([app/tasks/burn_captions.py:66](../../app/tasks/burn_captions.py#L66)).

## Validations

- **Format check:** unknown `format` → 400 `INVALID_FORMAT` with the supported list ([app/api/exports.py:49](../../app/api/exports.py#L49)).
- **Session existence:** `load_session_for_export` raises `RuntimeError` → mapped to 404 ([app/engines/artifact_transformer.py:565](../../app/engines/artifact_transformer.py#L565), [app/api/exports.py:67](../../app/api/exports.py#L67)).
- **CMS publish gate (html/zip):** `to_cms_html` runs `apply_cms_transform(..., strict=True)`, and `_validate_cms_doc` raises `CMSValidationError` if any unresolved marker remains (`[X]`, `[T=...]`, leftover `{curly}`, unreplaced `{{token}}`, any `[pq]` marker) ([app/engines/artifact_transformer.py:444](../../app/engines/artifact_transformer.py#L444), [app/engines/artifact_transformer.py:387](../../app/engines/artifact_transformer.py#L387)). NOTE: `CMSValidationError` is not caught in `export_session` — it would surface as an uncaught 500 (default FastAPI handler). NOT VERIFIED IN CODE: no try/except around `to_cms_html` in [app/api/exports.py:78](../../app/api/exports.py#L78).
- **SRT compliance (available, not auto-invoked on export):** `validate_final_srt` enforces ≤42 chars/line, no HTML, no markers ([app/engines/artifact_transformer.py:404](../../app/engines/artifact_transformer.py#L404)). It is a standalone validator; `to_srt`/`export_session` do not call it. PARTIALLY IMPLEMENTED for the export path.
- **Burn-in source check:** the `/captions/burn` handler requires a video source, else 400 ([app/api/session_resources.py:114](../../app/api/session_resources.py#L114)); the task itself raises `RuntimeError` if no `role='video'` source or no transcript content ([app/tasks/burn_captions.py:250](../../app/tasks/burn_captions.py#L250), [app/tasks/burn_captions.py:282](../../app/tasks/burn_captions.py#L282)).

## Approvals

None. Any authenticated user can request any export format or trigger a burn. There is no publish-approval gate enforced in code; the only publish-readiness check is the structural `CMSValidationError` marker validation described above.

## Notifications

- **Synchronous exports:** none (the bytes are the response).
- **Caption burn-in WS events** (`publish_ws_event_sync`):
  - `captioned_video_progress` at 5/15/30/40/85/95/100 ([app/tasks/burn_captions.py:226](../../app/tasks/burn_captions.py#L226)).
  - `captioned_video_ready` with `artifact_id`, signed `download_url`, `byte_size` ([app/tasks/burn_captions.py:365](../../app/tasks/burn_captions.py#L365)).
  - `captioned_video_failed` with `reason` on failure ([app/tasks/burn_captions.py:186](../../app/tasks/burn_captions.py#L186)).

No email notifications.

## Outputs

### Format transforms (artifact_transformer.py)

- **txt** — slide-headed plain text with `Speaker: text` lines ([app/engines/artifact_transformer.py:106](../../app/engines/artifact_transformer.py#L106)).
- **srt** — cue-numbered subtitles; each cue text passed through `apply_srt_transform` (11-step BR-016 markup strip: slide codes, `[Video]`, speaker labels, `[pq]` tags, `{curly}` kept, poll markers, whitespace) ([app/engines/artifact_transformer.py:128](../../app/engines/artifact_transformer.py#L128), [app/engines/artifact_transformer.py:236](../../app/engines/artifact_transformer.py#L236)).
- **vtt** — `WEBVTT` cues; deliberately does NOT strip structural markup ([app/engines/artifact_transformer.py:144](../../app/engines/artifact_transformer.py#L144)).
- **docx** — python-docx document with slide headings; `\n\n` = new paragraph, `\n` = soft line break; speaker prefix bold, and navy when `speaker_role == 'primary'` ([app/engines/artifact_transformer.py:153](../../app/engines/artifact_transformer.py#L153)).
- **html** — publish-ready CMS HTML via marked transcript → `apply_cms_transform(strict=True)` → `_markdown_to_html`; injects poll blocks at slide markers, resolves `[pq][HH:MM:SS]` to nearest chat, appends a Resources section ([app/engines/artifact_transformer.py:439](../../app/engines/artifact_transformer.py#L439), [app/engines/artifact_transformer.py:282](../../app/engines/artifact_transformer.py#L282)).
- **zip** — bundles txt + srt + vtt + docx + html + a `_slides.txt` slide outline ([app/engines/artifact_transformer.py:523](../../app/engines/artifact_transformer.py#L523)).
- Response: bytes streamed with the format MIME type + `Content-Disposition: attachment; filename="<code>.<fmt>"` ([app/api/exports.py:103](../../app/api/exports.py#L103)).

### Artifacts table

- `export_session` upserts an `artifacts` row keyed by `(session_id, kind)` recording `bytes` (length) and `generated_by` (user email) — best-effort; failure rolls back and is non-fatal ([app/api/exports.py:85](../../app/api/exports.py#L85)).
- `burn_captions_task` marks prior `kind='captioned_video'` artifacts `is_current = FALSE` then INSERTs a new versioned row (`version = max+1`, `is_current = TRUE`, `gcs_uri`, `bytes`, `style_config`, `generated_by = 'burn_captions_task'`) ([app/tasks/burn_captions.py:324](../../app/tasks/burn_captions.py#L324)).

### Caption burn-in artifact (GCS)

- ffmpeg burns the SRT into the video (`-vf subtitles=...:force_style=...`, `-c:a copy`, `+faststart`) and uploads to `gs://<bucket>/sessions/<id>/captioned/<uuid>.mp4` ([app/tasks/burn_captions.py:300](../../app/tasks/burn_captions.py#L300), [app/tasks/burn_captions.py:317](../../app/tasks/burn_captions.py#L317)). A 24h v4 signed URL is generated for download ([app/tasks/burn_captions.py:362](../../app/tasks/burn_captions.py#L362)). SRT source is segment text (`ai`) or word-level cues grouped into ~3s (`stt`, falling back to segments if no words) ([app/tasks/burn_captions.py:254](../../app/tasks/burn_captions.py#L254)).

### captions.vtt caching

- ETag = `W/"{session_id}-{max_seq}"` where `max_seq = MAX(correction_ledger.sequence_number)`; matching `If-None-Match` returns 304 with no body. `Cache-Control: private, max-age=60`, `Content-Disposition: inline` ([app/api/exports.py:138](../../app/api/exports.py#L138)). The cache invalidates the moment any correction lands (the ledger sequence number bumps).

## Status Changes

None. Generating any export or burning captions does not transition `sessions.status` or any SOP stage. The only mutations are `artifacts` rows and (for burn) a new GCS object.

## Audit Events

None. No `audit_events` table rows are written by the export handler, the captions.vtt route, the artifact transformer, or `burn_captions_task`. The `artifacts` table rows are the only persisted record of an export.

## Exception Handling

- **Export handler:** 400 on bad format, 404 on missing session; the `artifacts` upsert is wrapped (`rollback` + continue) so a metadata write failure never breaks the download ([app/api/exports.py:99](../../app/api/exports.py#L99)). `CMSValidationError` from the html/zip path is NOT caught here and would surface as a 500.
- **Burn-in is NON-CRITICAL:** `_BurnCaptionsTask.on_failure` never marks the session `failed`; it logs and emits `captioned_video_failed` ([app/tasks/burn_captions.py:168](../../app/tasks/burn_captions.py#L168)). The task retries up to 2 times, with `time_limit=3600s` / `soft_time_limit=3300s` hard/soft kill for large videos ([app/tasks/burn_captions.py:199](../../app/tasks/burn_captions.py#L199)). ffmpeg non-zero exit raises `RuntimeError` with the stderr tail ([app/tasks/burn_captions.py:310](../../app/tasks/burn_captions.py#L310)).
- **Burn enqueue:** enqueue failure in the `/captions/burn` handler returns 500 with the exception class/message ([app/api/session_resources.py:127](../../app/api/session_resources.py#L127)).

### Feature flags

None. No feature flag gates the export or caption-burn paths (verified: no env-flag reads in exports.py, artifact_transformer.py, or burn_captions.py).

---

## Source Verification
- **Files Used:** app/api/exports.py, app/engines/artifact_transformer.py, app/tasks/burn_captions.py, app/api/session_resources.py (burn trigger), app/config.py (flag absence check)
- **Components Used:** none (backend; editor download UI / CaptionStyleDialog referenced in docstrings but frontend not read for this workflow)
- **APIs Used:** GET `/v1/sessions/{id}/exports/{format}`, GET `/v1/sessions/{id}/captions.vtt`, POST `/v1/sessions/{id}/captions/burn`, GET `/v1/sessions/{id}/captions/current`
- **Database Tables Used:** sessions, segments, slides, bullets, speakers, chat_messages, session_slide_resources, words, artifacts, correction_ledger (read for ETag)
- **Permission Logic Used:** JWT presence via `CurrentUser` / `_user: CurrentUser` dependency on every route. No role tiers and no `johndean@vin.com` gate in these handlers.
- **Confidence Score:** High — transform behaviors, validation gates, artifact writes, and WS events all verified against source lines. One discrepancy flagged: CMSValidationError on html/zip is uncaught in the export handler.
- **Evidence Links:** [app/api/exports.py:41](../../app/api/exports.py#L41), [app/engines/artifact_transformer.py:439](../../app/engines/artifact_transformer.py#L439), [app/tasks/burn_captions.py:207](../../app/tasks/burn_captions.py#L207), [app/api/exports.py:138](../../app/api/exports.py#L138)
