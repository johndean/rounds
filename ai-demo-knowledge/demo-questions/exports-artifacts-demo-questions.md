# Exports & Artifacts — Demo Questions

> Module key: `exports-artifacts`. Every answer below is code-true as of
> `HEAD` on 2026-06-08. Links are relative to this file
> (`ai-demo-knowledge/demo-questions/`), so paths use `../../`.

---

## User

### Q: What file formats can I download from the editor?
- **Verified Answer:** The editor's Download menu offers four: Word (`.docx`),
  Captions (`.srt`), Plain Text (`.txt`), and Word Macro (`.zip`). The backend can
  also produce `.vtt` and `.html`, but those two are not exposed in the editor menu.
- **Supporting Evidence:** The menu's `formats` array lists exactly docx/srt/txt/zip;
  the backend `_KIND_TO_MIME` whitelists txt/srt/vtt/docx/html/zip.
- **Source Files:** [frontend/src/components/editor/DownloadMenu.vue:27-32](../../frontend/src/components/editor/DownloadMenu.vue#L27-L32), [app/api/exports.py:31-38](../../app/api/exports.py#L31-L38)
- **API References:** GET /v1/sessions/{id}/exports/{format}
- **Database References:** none

### Q: How do I download a transcript as a Word document?
- **Verified Answer:** Click `Download` in the editor, then `Word (.docx)`. The app
  fetches the docx and triggers a browser save dialog. The filename is the session
  code plus the extension (e.g. `ABC123.docx`).
- **Supporting Evidence:** `pick()` calls `exportsApi.download`; the server sets
  `Content-Disposition: attachment; filename="{code}.{fmt}"`.
- **Source Files:** [frontend/src/components/editor/DownloadMenu.vue:42-55](../../frontend/src/components/editor/DownloadMenu.vue#L42-L55), [frontend/src/services/api.ts:405-429](../../frontend/src/services/api.ts#L405-L429), [app/api/exports.py:103-108](../../app/api/exports.py#L103-L108)
- **API References:** GET /v1/sessions/{id}/exports/docx
- **Database References:** sessions, segments, slides, speakers

### Q: Does my download reflect my latest edits?
- **Verified Answer:** Yes. Each export request re-reads the session from the
  database and re-renders from scratch — there is no stale cache for the file itself.
- **Supporting Evidence:** `load_session_for_export` runs a fresh read on every call;
  the route renders the format inline per request.
- **Source Files:** [app/engines/artifact_transformer.py:545-628](../../app/engines/artifact_transformer.py#L545-L628), [app/api/exports.py:65-81](../../app/api/exports.py#L65-L81)
- **API References:** GET /v1/sessions/{id}/exports/{format}
- **Database References:** sessions, segments, slides, speakers, bullets, chat_messages, session_slide_resources

### Q: Why do the download buttons on the Preview/Viewer page not do anything?
- **Verified Answer:** On the Viewer page the download buttons are stubs — they show
  a warning toast and do not download. Use the editor's Download menu instead, which
  is wired to the real export endpoint.
- **Supporting Evidence:** `downloadFile()` only pushes a warn toast; the real
  download lives in `DownloadMenu.vue`.
- **Source Files:** [frontend/src/views/ViewerView.vue:91-96](../../frontend/src/views/ViewerView.vue#L91-L96), [frontend/src/components/editor/DownloadMenu.vue:42-55](../../frontend/src/components/editor/DownloadMenu.vue#L42-L55)
- **API References:** none (Viewer buttons are not wired)
- **Database References:** none

### Q: What's in the ZIP download?
- **Verified Answer:** The zip bundles the txt, srt, vtt, docx, and html renders of
  the transcript plus a `_slides.txt` slide outline — one of each, all named with the
  session code.
- **Supporting Evidence:** `to_zip` writes those six entries.
- **Source Files:** [app/engines/artifact_transformer.py:523-539](../../app/engines/artifact_transformer.py#L523-L539)
- **API References:** GET /v1/sessions/{id}/exports/zip
- **Database References:** sessions, segments, slides, bullets

### Q: Do the captions in the video player update after I make a correction?
- **Verified Answer:** Yes. The caption track is keyed to the latest correction; once
  a new correction lands, the browser's cached caption file is invalidated and the
  player re-fetches the updated captions.
- **Supporting Evidence:** The captions ETag fingerprints
  `(session_id, MAX(correction_ledger.sequence_number))`; the server returns 304
  until a new correction changes that max.
- **Source Files:** [app/api/exports.py:138-176](../../app/api/exports.py#L138-L176), [frontend/src/components/editor/VideoStrip.vue:74-100](../../frontend/src/components/editor/VideoStrip.vue#L74-L100)
- **API References:** GET /v1/sessions/{id}/captions.vtt
- **Database References:** correction_ledger

---

## Operations

### Q: How are captions burned into a video, operationally?
- **Verified Answer:** A `POST /v1/sessions/{id}/captions/burn` enqueues a Celery
  task that downloads the source video from GCS, builds an SRT, runs ffmpeg to render
  the captions onto the video, uploads the result to GCS, and stores a versioned
  artifact. Note: there is no UI for this today — it is invoked by direct API call.
- **Supporting Evidence:** The route enqueues `burn_captions_task`; the task performs
  the ffmpeg render and upload. No frontend component calls `burnCaptions`.
- **Source Files:** [app/api/session_resources.py:92-127](../../app/api/session_resources.py#L92-L127), [app/tasks/burn_captions.py:207-384](../../app/tasks/burn_captions.py#L207-L384)
- **API References:** POST /v1/sessions/{id}/captions/burn
- **Database References:** sources, artifacts, segments, words

### Q: What happens if the caption burn-in fails?
- **Verified Answer:** Nothing breaks for the session. A burn failure is treated as
  non-critical: the session is never marked `failed`; the task emits a
  `captioned_video_failed` WebSocket event instead.
- **Supporting Evidence:** `_BurnCaptionsTask.on_failure` logs a warning and emits the
  failure event without changing session status.
- **Source Files:** [app/tasks/burn_captions.py:168-191](../../app/tasks/burn_captions.py#L168-L191)
- **API References:** POST /v1/sessions/{id}/captions/burn
- **Database References:** none (status unchanged)

### Q: Can I burn captions for an audio-only session?
- **Verified Answer:** No. The burn endpoint first checks for a `sources` row with
  `role='video'`; if none exists it returns HTTP 400 ("No video source available —
  captions can only be burned into video sessions.").
- **Supporting Evidence:** The video-source COUNT check precedes the enqueue.
- **Source Files:** [app/api/session_resources.py:104-117](../../app/api/session_resources.py#L104-L117)
- **API References:** POST /v1/sessions/{id}/captions/burn
- **Database References:** sources

### Q: How do I monitor burn progress?
- **Verified Answer:** The task emits `captioned_video_progress` WebSocket events at
  5/15/30/40/85/95/100 percent with a substage label, then `captioned_video_ready`
  with the download URL on success.
- **Supporting Evidence:** `_emit(...)` calls at each stage; final ready event.
- **Source Files:** [app/tasks/burn_captions.py:226-370](../../app/tasks/burn_captions.py#L226-L370)
- **API References:** POST /v1/sessions/{id}/captions/burn
- **Database References:** artifacts

### Q: Where does the captioned video get stored, and how long are links valid?
- **Verified Answer:** It is uploaded to
  `gs://<bucket>/sessions/<id>/captioned/<uuid>.mp4`. The `captioned_video_ready`
  event carries a 24-hour signed URL; the `GET /captioned-video` endpoint mints a
  fresh 1-hour signed URL on each call.
- **Supporting Evidence:** `out_blob` path; `_generate_signed_url(..., hours=24)` in
  the task and `hours=1` in the GET endpoint.
- **Source Files:** [app/tasks/burn_captions.py:317-362](../../app/tasks/burn_captions.py#L317-L362), [app/api/session_resources.py:159-166](../../app/api/session_resources.py#L159-L166)
- **API References:** GET /v1/sessions/{id}/captioned-video
- **Database References:** artifacts

### Q: If something goes wrong recording export metadata, does my download still work?
- **Verified Answer:** Yes. The `artifacts`-row write is best-effort: it is wrapped
  in a try/except that rolls back on any error (e.g. unmigrated schema) and the
  download bytes are returned regardless.
- **Supporting Evidence:** The upsert is inside a try/except with rollback; the
  `Response` is returned after it.
- **Source Files:** [app/api/exports.py:83-108](../../app/api/exports.py#L83-L108)
- **API References:** GET /v1/sessions/{id}/exports/{format}
- **Database References:** artifacts

---

## Administrator

### Q: Who can download exports — is there a role restriction?
- **Verified Answer:** Any authenticated user can download. The export, captions,
  burn, and captioned-video routes require only a valid JWT; there is no role check
  and no admin gate anywhere in the export path.
- **Supporting Evidence:** Routes depend on `CurrentUser` / `_user` only;
  `get_current_user` reads no role column; no `require_admin`/`LEGACY_ADMIN_EMAIL`
  appears in the export files.
- **Source Files:** [app/api/exports.py:46,125](../../app/api/exports.py#L46), [app/api/session_resources.py:94,132](../../app/api/session_resources.py#L94), [app/auth.py:172-208](../../app/auth.py#L172-L208)
- **API References:** GET /v1/sessions/{id}/exports/{format}, POST /v1/sessions/{id}/captions/burn
- **Database References:** none (no role read)

### Q: How is artifact version history tracked?
- **Verified Answer:** Migration 023 added `version`, `is_current`, and
  `style_config` to the `artifacts` table and dropped the old
  `UNIQUE(session_id, kind)` constraint. A partial unique index now allows only one
  `is_current = TRUE` row per `(session, kind)`, with `version` incrementing. The burn
  task marks prior rows not-current and inserts `max(version)+1`.
- **Supporting Evidence:** Migration 023 DDL; the burn task's UPDATE-then-INSERT.
- **Source Files:** [migrations/023_artifact_versions.sql:14-25](../../migrations/023_artifact_versions.sql#L14-L25), [app/tasks/burn_captions.py:324-360](../../app/tasks/burn_captions.py#L324-L360)
- **API References:** GET /v1/sessions/{id}/captioned-video
- **Database References:** artifacts

### Q: What does the `generated_by` field hold?
- **Verified Answer:** For text/doc exports it's the caller's email (from the JWT).
  For captioned-video artifacts it's the literal string `'burn_captions_task'`.
- **Supporting Evidence:** `"u": user.email` in the export upsert;
  `'burn_captions_task'` in the burn INSERT.
- **Source Files:** [app/api/exports.py:88-97](../../app/api/exports.py#L88-L97), [app/tasks/burn_captions.py:340-349](../../app/tasks/burn_captions.py#L340-L349)
- **API References:** GET /v1/sessions/{id}/exports/{format}
- **Database References:** artifacts

### Q: Is the caption burn-in feature usable from the UI?
- **Verified Answer:** No. The backend task and the `burnCaptions` / `captionedVideo`
  API-client helpers exist, but no Vue component invokes them and there is no caption-
  style dialog. The feature is reachable only by direct API call today.
- **Supporting Evidence:** API helpers defined in `api.ts`; no component references
  `burnCaptions`/`captionedVideo`; no `CaptionStyleDialog` exists.
- **Source Files:** [frontend/src/services/api.ts:205-216](../../frontend/src/services/api.ts#L205-L216), [app/tasks/burn_captions.py:66-67](../../app/tasks/burn_captions.py#L66-L67)
- **API References:** POST /v1/sessions/{id}/captions/burn, GET /v1/sessions/{id}/captioned-video
- **Database References:** artifacts

---

## Compliance

### Q: Are filler words ("um", "uh") removed from exported documents?
- **Verified Answer:** Not by the export engine. Filler-word removal happens earlier,
  at the IIL normalize phase at ingest (TIER1 words um/uh/er/ah/umm/uhh/hmm). The
  export functions (`to_docx`, `to_txt`) do no filler stripping of their own — they
  serialize whatever normalized text is stored. (This contradicts the documented
  BR-016 wording, which says docx/txt strip fillers at export.)
- **Supporting Evidence:** The export-engine comment states fillers are stripped at
  normalize, "not here"; `TIER1_WORDS` lives in the normalize engine.
- **Source Files:** [app/engines/artifact_transformer.py:247-249](../../app/engines/artifact_transformer.py#L247-L249), [app/iil/normalization.py:40](../../app/iil/normalization.py#L40), [docs/BUSINESS_RULES.md:250-260](../../docs/BUSINESS_RULES.md#L250-L260)
- **API References:** GET /v1/sessions/{id}/exports/docx
- **Database References:** segments, normalization_results

### Q: Do caption files preserve the spoken audio (no filler removal)?
- **Verified Answer:** `.vtt` captions are emitted verbatim from the stored segment
  text (no transform). `.srt` captions run an 11-step transform that strips
  *structural markup* (slide codes, speaker labels, `[pq]` tags, curly annotations,
  poll markers) but not filler words.
- **Supporting Evidence:** `to_vtt` does not call `apply_srt_transform`; `to_srt`
  does, and that transform targets markup only.
- **Source Files:** [app/engines/artifact_transformer.py:144-150](../../app/engines/artifact_transformer.py#L144-L150), [app/engines/artifact_transformer.py:236-275](../../app/engines/artifact_transformer.py#L236-L275)
- **API References:** GET /v1/sessions/{id}/exports/srt, GET /v1/sessions/{id}/exports/vtt
- **Database References:** segments

### Q: How are unattributed (no-speaker) segments shown in exports?
- **Verified Answer:** They are exported with no speaker label at all — the line is
  just the text. Despite the documented BR-017 rule, the export engine does NOT emit a
  literal `(Unknown)` label; when `speaker_name` is empty, `to_txt`/`to_docx` simply
  omit the prefix and the marked transcript skips the `**Name:**` line.
- **Supporting Evidence:** Conditional `if seg.speaker_name:` guards in `to_txt`,
  `to_docx`, and `_build_marked_transcript`; no `(Unknown)` string exists in the
  export module.
- **Source Files:** [app/engines/artifact_transformer.py:121-124](../../app/engines/artifact_transformer.py#L121-L124), [app/engines/artifact_transformer.py:187-188](../../app/engines/artifact_transformer.py#L187-L188), [app/engines/artifact_transformer.py:229-231](../../app/engines/artifact_transformer.py#L229-L231)
- **API References:** GET /v1/sessions/{id}/exports/txt, GET /v1/sessions/{id}/exports/docx
- **Database References:** segments, speakers

### Q: What prevents an unfinished transcript from being published as CMS HTML?
- **Verified Answer:** The HTML export runs the CMS transform in strict mode, which
  rejects the document if any unresolved marker remains — editor placeholders `[X]`,
  unresolved `[T=…]` timestamps, leftover curly braces, unreplaced `{{token}}`
  hyperlinks, or `[pq]` tokens — raising `CMSValidationError`.
- **Supporting Evidence:** `to_cms_html` calls `apply_cms_transform(..., strict=True)`;
  `_validate_cms_doc` scans the unresolved-marker patterns.
- **Source Files:** [app/engines/artifact_transformer.py:439-450](../../app/engines/artifact_transformer.py#L439-L450), [app/engines/artifact_transformer.py:378-398](../../app/engines/artifact_transformer.py#L378-L398)
- **API References:** GET /v1/sessions/{id}/exports/html
- **Database References:** sessions, segments, slides, chat_messages, session_slide_resources

### Q: Is there a caption-accessibility (DCMP) line-length check?
- **Verified Answer:** A `validate_final_srt` function exists that enforces ≤42
  characters per line, no HTML tags, no curly braces, and no unresolved markers — but
  it is NOT called by any export route. It is a library helper, not an enforced gate
  in the current export flow.
- **Supporting Evidence:** Function defined in the engine; no call site in
  `app/api/exports.py`.
- **Source Files:** [app/engines/artifact_transformer.py:404-426](../../app/engines/artifact_transformer.py#L404-L426), [app/api/exports.py:41-108](../../app/api/exports.py#L41-L108)
- **API References:** none (not wired)
- **Database References:** none

### Q: What audit trail exists for who exported what?
- **Verified Answer:** The `artifacts` table records, per `(session_id, kind)`, the
  `generated_by` user email and `generated_at` timestamp. That is the only audit
  surface written by the export path; the routes do not write to a separate audit-
  events ledger.
- **Supporting Evidence:** The export upsert writes generated_by/generated_at; no
  other audit write in the route.
- **Source Files:** [app/api/exports.py:83-98](../../app/api/exports.py#L83-L98), [migrations/018_artifacts.sql:6-15](../../migrations/018_artifacts.sql#L6-L15)
- **API References:** GET /v1/sessions/{id}/exports/{format}
- **Database References:** artifacts

---

## Power User

### Q: Can I download the WebVTT caption file directly?
- **Verified Answer:** Yes, the backend supports `vtt` as an export format
  (`GET /exports/vtt`) and also serves a cache-friendly `GET /captions.vtt`. Note the
  editor's Download menu does not list VTT, so you'd call the endpoint directly.
- **Supporting Evidence:** `vtt` is in `_KIND_TO_MIME`; the dedicated captions route
  serves VTT with ETag caching. The menu's format list omits vtt.
- **Source Files:** [app/api/exports.py:31-38](../../app/api/exports.py#L31-L38), [app/api/exports.py:120-176](../../app/api/exports.py#L120-L176), [frontend/src/components/editor/DownloadMenu.vue:27-32](../../frontend/src/components/editor/DownloadMenu.vue#L27-L32)
- **API References:** GET /v1/sessions/{id}/exports/vtt, GET /v1/sessions/{id}/captions.vtt
- **Database References:** segments, correction_ledger

### Q: What's the difference between the `srt` export and the `vtt` export?
- **Verified Answer:** `srt` runs the structural-markup strip transform
  (`apply_srt_transform`) so cues are clean speech, with `HH:MM:SS,mmm` timestamps.
  `vtt` emits each segment's stored text verbatim (no transform) with a `WEBVTT`
  header and `HH:MM:SS.mmm` timestamps — preserving structural markup so editors can
  correlate cues to anchors.
- **Supporting Evidence:** `to_srt` calls the transform; `to_vtt` does not; the
  timestamp formatters differ (comma vs dot).
- **Source Files:** [app/engines/artifact_transformer.py:128-150](../../app/engines/artifact_transformer.py#L128-L150), [app/engines/artifact_transformer.py:83-100](../../app/engines/artifact_transformer.py#L83-L100)
- **API References:** GET /v1/sessions/{id}/exports/srt, GET /v1/sessions/{id}/exports/vtt
- **Database References:** segments

### Q: How does the docx export handle a Rounds (primary) speaker versus others?
- **Verified Answer:** The speaker prefix is bold for all speakers; if
  `speaker_role == 'primary'` the prefix is additionally rendered in Rounds navy
  (`RGBColor(0x00,0x28,0x55)`). Moderator/guest/None stay bold-only.
- **Supporting Evidence:** `to_docx` sets `speaker_run.bold = True` and conditionally
  applies the navy color when role is primary; the role is SELECTed in the loader.
- **Source Files:** [app/engines/artifact_transformer.py:187-193](../../app/engines/artifact_transformer.py#L187-L193), [app/engines/artifact_transformer.py:574](../../app/engines/artifact_transformer.py#L574)
- **API References:** GET /v1/sessions/{id}/exports/docx
- **Database References:** speakers, segments

### Q: How can captions burn-in choose between AI-cleaned text and raw STT words?
- **Verified Answer:** The `style_config.caption_source` key controls it: `'ai'`
  (default) builds the SRT from cleaned segment text; `'stt'` builds word-level cues
  from the `words` table grouped into ~3-second cues, falling back to segments if no
  words exist.
- **Supporting Evidence:** The task reads `caption_source` and branches between
  `_build_srt_from_words` (with a segment fallback) and `_build_srt_from_segments`.
- **Source Files:** [app/tasks/burn_captions.py:235-280](../../app/tasks/burn_captions.py#L235-L280), [app/tasks/burn_captions.py:416-433](../../app/tasks/burn_captions.py#L416-L433)
- **API References:** POST /v1/sessions/{id}/captions/burn
- **Database References:** words, segments
- **Database References (source):** sources

### Q: What caption-style keys can I pass to the burn endpoint?
- **Verified Answer:** `style_config_to_ass` accepts: `font_family`, `font_size`
  (8-96), `text_color`, `outline_color`, `outline_thickness` (0-4), `shadow`,
  `background`, `bold`, `italic`, `vertical_position` (top/middle/bottom),
  `horizontal_align` (left/center/right), and `margin` (0-200) — plus `caption_source`
  read separately. Values are clamped/defaulted, then translated to an ffmpeg
  `force_style` string.
- **Supporting Evidence:** The translator parses each key with clamps and maps
  position/align to ASS alignment codes.
- **Source Files:** [app/tasks/burn_captions.py:66-113](../../app/tasks/burn_captions.py#L66-L113), [app/tasks/burn_captions.py:43-53](../../app/tasks/burn_captions.py#L43-L53)
- **API References:** POST /v1/sessions/{id}/captions/burn
- **Database References:** none

### Q: How does the caption track avoid re-downloading on every editor mount?
- **Verified Answer:** The `captions.vtt` route uses a weak ETag of
  `(session_id, max correction sequence)` plus `Cache-Control: private, max-age=60`.
  The browser sends `If-None-Match`; the server returns 304 (no body) until a new
  correction lands. The frontend fetches it authenticated and wraps it in a Blob URL
  so the `<track>` element doesn't need to send the JWT.
- **Supporting Evidence:** ETag computed pre-render; 304 branch; Blob-URL helper.
- **Source Files:** [app/api/exports.py:129-176](../../app/api/exports.py#L129-L176), [frontend/src/services/api.ts:431-453](../../frontend/src/services/api.ts#L431-L453)
- **API References:** GET /v1/sessions/{id}/captions.vtt
- **Database References:** correction_ledger, segments

---

## Source Verification
- **Files Used:** app/api/exports.py, app/engines/artifact_transformer.py, app/iil/normalization.py, app/tasks/burn_captions.py, app/api/session_resources.py, app/auth.py, migrations/018_artifacts.sql, migrations/023_artifact_versions.sql, frontend/src/components/editor/DownloadMenu.vue, frontend/src/views/ViewerView.vue, frontend/src/components/editor/VideoStrip.vue, frontend/src/services/api.ts, docs/BUSINESS_RULES.md
- **Components Used:** DownloadMenu.vue, ViewerView.vue, VideoStrip.vue
- **APIs Used:** GET /v1/sessions/{id}/exports/{format}, GET /v1/sessions/{id}/captions.vtt, POST /v1/sessions/{id}/captions/burn, GET /v1/sessions/{id}/captioned-video
- **Database Tables Used:** artifacts, sessions, segments, slides, bullets, speakers, chat_messages, session_slide_resources, sources, correction_ledger, words, normalization_results
- **Permission Logic Used:** JWT presence via CurrentUser/_user (no role tier, no admin gate)
- **Confidence Score:** High — every answer traced to current source; BR-016 (filler strip) and BR-017 ("(Unknown)") answers corrected to match code, and the absent burn-in UI is noted.
- **Evidence Links:** [app/api/exports.py:41](../../app/api/exports.py#L41), [app/api/exports.py:138-176](../../app/api/exports.py#L138-L176), [app/engines/artifact_transformer.py:247-249](../../app/engines/artifact_transformer.py#L247-L249), [app/tasks/burn_captions.py:235-280](../../app/tasks/burn_captions.py#L235-L280), [migrations/023_artifact_versions.sql:14-25](../../migrations/023_artifact_versions.sql#L14-L25)
