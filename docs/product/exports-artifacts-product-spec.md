# Exports & Artifacts — Product Spec

> Module key: `exports-artifacts`. Code-verified against `HEAD` on 2026-06-08.
> Every claim below is traced to source. Unproven claims are tagged
> `NOT VERIFIED IN CODE`, `IMPLEMENTATION NOT FOUND`, or `PARTIALLY IMPLEMENTED`.

## Overview

The Exports & Artifacts module turns a finished session's transcript into
downloadable files. There are two distinct production surfaces:

1. **Text/document exports** — `GET /v1/sessions/{id}/exports/{format}` streams a
   generated artifact (`txt`, `srt`, `vtt`, `docx`, `html`, `zip`) back to the
   browser as a file download. See [app/api/exports.py:41](../../app/api/exports.py#L41).
2. **WebVTT caption track** — `GET /v1/sessions/{id}/captions.vtt` serves the same
   VTT body the editor's video `<track>` element consumes, with ETag caching. See
   [app/api/exports.py:120](../../app/api/exports.py#L120).

A third surface exists in the backend but has **no wired UI** (see Known
Constraints): **caption burn-in to MP4**, where ffmpeg renders SRT captions
directly onto the source video and stores a versioned `captioned_video` artifact
in GCS. Backend: [app/tasks/burn_captions.py](../../app/tasks/burn_captions.py),
[app/api/session_resources.py:92](../../app/api/session_resources.py#L92).

All generated outputs are produced on demand from the session's stored data
(`segments`, `slides`, `speakers`, `bullets`, `chat_messages`, parsed polls,
slide resources). The renderers live in a single engine,
[app/engines/artifact_transformer.py](../../app/engines/artifact_transformer.py).

## Purpose

- Give editors and reviewers a way to pull the transcript out of the app in the
  format each downstream consumer needs: a macro-compatible Word doc for the CMS
  prep workflow, SubRip/WebVTT captions for the video player, plain text for quick
  paste, a CMS-publish-ready HTML body, or a zip bundle of everything.
- Provide a cache-friendly caption track so the in-app video player can show
  closed captions without re-downloading on every editor mount
  ([app/api/exports.py:111-176](../../app/api/exports.py#L111-L176)).
- (Backend only) produce a captioned MP4 with operator-controlled caption styling
  for sessions that have a source video
  ([app/tasks/burn_captions.py:207](../../app/tasks/burn_captions.py#L207)).

## User Value

- One menu in the editor produces the file the user needs without leaving the app
  ([frontend/src/components/editor/DownloadMenu.vue](../../frontend/src/components/editor/DownloadMenu.vue)).
- Downloads always reflect the latest stored transcript, because each request
  re-reads the database and re-renders from scratch
  ([app/engines/artifact_transformer.py:545](../../app/engines/artifact_transformer.py#L545)).
- The caption track is cheap on repeat loads: the server returns `304 Not Modified`
  until a new correction lands, so the player skips re-downloading
  ([app/api/exports.py:150-157](../../app/api/exports.py#L150-L157)).

## Navigation

- **Editor download menu.** The `DownloadMenu` component renders a `Download`
  button (`data-test-id="editor-download"`) that opens a dropdown of formats
  ([frontend/src/components/editor/DownloadMenu.vue:58-79](../../frontend/src/components/editor/DownloadMenu.vue#L58-L79)).
  It is a component, not a route; it is mounted within the Editor view
  (`/e/:id` per [frontend/src/router/index.ts:11](../../frontend/src/router/index.ts#L11)).
- **Viewer / Preview page** (`/v/:id`,
  [frontend/src/views/ViewerView.vue](../../frontend/src/views/ViewerView.vue)).
  Renders an "Export Preview" section with four format cards and a "Publishing
  Checklist". **PARTIALLY IMPLEMENTED:** the Viewer's download buttons are
  stubbed — clicking one shows a warning toast and does not download
  ([frontend/src/views/ViewerView.vue:91-103](../../frontend/src/views/ViewerView.vue#L91-L103)).
- **Caption track** loads automatically inside the editor's video strip; there is
  no navigation element — the `<track>` element fetches `captions.vtt` on mount
  ([frontend/src/components/editor/VideoStrip.vue:74-82](../../frontend/src/components/editor/VideoStrip.vue#L74-L82)).

## Screens

### Editor Download menu

- A primary `Download` button toggling a dropdown menu
  ([DownloadMenu.vue:60-78](../../frontend/src/components/editor/DownloadMenu.vue#L60-L78)).
- Four menu items, each with a label, a file extension, and a one-line subtitle
  ([DownloadMenu.vue:27-32](../../frontend/src/components/editor/DownloadMenu.vue#L27-L32)):

  | Label | Ext | Subtitle (verbatim) |
  |---|---|---|
  | Word | `.docx` | Macro-compatible transcript |
  | Captions | `.srt` | SubRip for Wistia / video player |
  | Plain Text | `.txt` | Quick paste / email |
  | Word Macro | `.zip` | One-time install for SRT/CMS prep |

- Picking a format shows an info toast (`Preparing {label} (.{ext})…`), then
  triggers the download; failures show an error toast
  ([DownloadMenu.vue:42-55](../../frontend/src/components/editor/DownloadMenu.vue#L42-L55)).
- The menu closes on outside click
  ([DownloadMenu.vue:34-40](../../frontend/src/components/editor/DownloadMenu.vue#L34-L40)).
- **Note (discrepancy):** the menu only offers `docx`/`srt`/`txt`/`zip`. The
  backend additionally supports `vtt` and `html`
  ([app/api/exports.py:31-38](../../app/api/exports.py#L31-L38)), but neither is
  exposed in this menu, and the frontend `download` helper's TypeScript signature
  omits both (`'docx' | 'srt' | 'vtt' | 'txt' | 'zip'` — `html` is absent)
  ([frontend/src/services/api.ts:405](../../frontend/src/services/api.ts#L405)).

### Viewer / Preview Export section

- Session identity header (code, title, presenter, taxonomy chips)
  ([ViewerView.vue:110-117](../../frontend/src/views/ViewerView.vue#L110-L117)).
- An "Export Preview" toolbar with an "Include key points section" checkbox and an
  "Editor" link ([ViewerView.vue:119-128](../../frontend/src/views/ViewerView.vue#L119-L128)).
- Four format cards (`Word Document .docx`, `Captions .srt`, `Plain Text .txt`,
  `Word Macro .zip`) with longer descriptions
  ([ViewerView.vue:71-76](../../frontend/src/views/ViewerView.vue#L71-L76)).
- A "Publishing Checklist" listing seven links (Zoom recording, Slides, Podbean,
  VINcast, Intranet, Message board, Session page), all hard-coded to `href="#"`
  ([ViewerView.vue:78-86](../../frontend/src/views/ViewerView.vue#L78-L86)).
- A per-slide preview rendering segments grouped under each slide
  ([ViewerView.vue:157-175](../../frontend/src/views/ViewerView.vue#L157-L175)).

### Caption style / burn-in screen

- **IMPLEMENTATION NOT FOUND.** The backend `style_config_to_ass` translator
  references a "CaptionStyleDialog payload"
  ([app/tasks/burn_captions.py:67](../../app/tasks/burn_captions.py#L67)) and the
  API client exposes `burnCaptions(...)`
  ([frontend/src/services/api.ts:205](../../frontend/src/services/api.ts#L205)),
  but no Vue component invokes `burnCaptions` or `captionedVideo`, and there is no
  `CaptionStyleDialog` component in the frontend. There is no screen for this.

## User Flows

### Download an export from the editor

1. User clicks the `Download` button in the editor
   ([DownloadMenu.vue:60-64](../../frontend/src/components/editor/DownloadMenu.vue#L60-L64)).
2. User selects a format. The component calls `exportsApi.download(sessionId, ext)`
   ([DownloadMenu.vue:48](../../frontend/src/components/editor/DownloadMenu.vue#L48)).
3. The helper does an authenticated `fetch` of
   `GET /v1/sessions/{id}/exports/{format}`, reads the response as a Blob, and
   triggers a browser save via a transient `<a download>` element. The filename
   comes from the `Content-Disposition` header
   ([frontend/src/services/api.ts:405-429](../../frontend/src/services/api.ts#L405-L429)).
4. The backend loads the session, renders the requested format, records artifact
   metadata, and streams the bytes with
   `Content-Disposition: attachment; filename="{code}.{fmt}"`
   ([app/api/exports.py:65-108](../../app/api/exports.py#L65-L108)).

### Load captions in the video player

1. On mount, the video strip calls `exportsApi.captionsBlobUrl(sessionId)`
   ([VideoStrip.vue:75-83](../../frontend/src/components/editor/VideoStrip.vue#L75-L83)).
2. That helper fetches `GET /v1/sessions/{id}/captions.vtt` with the JWT header,
   converts the body to a Blob URL, and returns it (or `null` on 404)
   ([frontend/src/services/api.ts:439-453](../../frontend/src/services/api.ts#L439-L453)).
3. The `<track>` element is bound to that Blob URL; toggling the CC prop flips the
   text-track mode ([VideoStrip.vue:88-100,275-282](../../frontend/src/components/editor/VideoStrip.vue#L88-L100)).
4. On the server, the ETag fingerprints `(session_id, max(correction_ledger.sequence_number))`.
   If the client's `If-None-Match` matches, the server returns 304 with no body;
   otherwise it renders and returns the VTT
   ([app/api/exports.py:138-176](../../app/api/exports.py#L138-L176)).

### Burn captions into the video (backend flow — no UI caller)

1. A `POST /v1/sessions/{id}/captions/burn` request (with optional `style_config`)
   first verifies a `video` source exists, else returns 400; then enqueues
   `burn_captions_task` on the `celery` queue
   ([app/api/session_resources.py:92-127](../../app/api/session_resources.py#L92-L127)).
2. The task resolves the video source, builds an SRT (from cleaned segment text
   when `caption_source='ai'`, or word-level cues when `'stt'`), downloads the
   video, runs ffmpeg with a `force_style` derived from `style_config`, uploads the
   result to `gs://<bucket>/sessions/<id>/captioned/<uuid>.mp4`, marks prior
   `captioned_video` artifacts not current, inserts a new versioned row, and emits
   progress + `captioned_video_ready` WebSocket events
   ([app/tasks/burn_captions.py:207-384](../../app/tasks/burn_captions.py#L207-L384)).
3. `GET /v1/sessions/{id}/captioned-video` returns the current artifact with a fresh
   1-hour signed URL ([app/api/session_resources.py:130-177](../../app/api/session_resources.py#L130-L177)).

**Note:** steps 1-3 above are backend + API-client only. No frontend component
calls `burnCaptions` or `captionedVideo` (`IMPLEMENTATION NOT FOUND` for the UI).

## Business Rules

- **BR-016 — Format-specific markup stripping (PARTIALLY IMPLEMENTED as documented).**
  - What the code actually does: `to_srt` passes each segment's text through
    `apply_srt_transform`, an 11-step regex that strips *structural markup* —
    slide codes (`++N*+`), `[Video]` tags, speaker labels, `[pq]`/`[pq][HH:MM:SS]`
    tokens, curly annotations, poll markers — leaving plain speech
    ([app/engines/artifact_transformer.py:128-141,236-275](../../app/engines/artifact_transformer.py#L128-L275)).
  - `to_vtt` does **not** call that transform; it emits each segment's stored text
    verbatim ([app/engines/artifact_transformer.py:144-150](../../app/engines/artifact_transformer.py#L144-L150)).
  - **Discrepancy with the documented rule:** `docs/BUSINESS_RULES.md` BR-016 and
    the seed doc state that `.docx`/`.txt` *strip filler words* (`um`, `uh`, …).
    The export engine does **not** strip filler words — the code comment is
    explicit: "Filler words … are stripped earlier at the normalize phase
    (`app/iil/normalization.py:TIER1_WORDS`), not here."
    ([app/engines/artifact_transformer.py:247-249](../../app/engines/artifact_transformer.py#L247-L249)).
    `TIER1_WORDS = frozenset(["um","uh","er","ah","umm","uhh","hmm"])` lives in the
    IIL normalize engine ([app/iil/normalization.py:40](../../app/iil/normalization.py#L40))
    and is applied at ingest, not at export. So the *only* filler-stripping that
    affects an export is whatever the stored, already-normalized segment text
    carries. `to_docx`/`to_txt` do no filler removal of their own
    ([app/engines/artifact_transformer.py:106-205](../../app/engines/artifact_transformer.py#L106-L205)).
- **BR-017 — Empty speaker label fallback (NOT VERIFIED IN CODE / contradicted).**
  - The documented rule (`docs/BUSINESS_RULES.md` BR-017) says exports emit the
    literal string `(Unknown)` when a segment has no resolved speaker.
  - **No such behavior exists in the export engine.** When `speaker_name` is
    falsy, `to_txt` emits the text with no speaker prefix
    ([app/engines/artifact_transformer.py:121-124](../../app/engines/artifact_transformer.py#L121-L124)),
    `to_docx` adds no speaker run
    ([app/engines/artifact_transformer.py:187-188](../../app/engines/artifact_transformer.py#L187-L188)),
    and `_build_marked_transcript` skips the `**Name:**` label
    ([app/engines/artifact_transformer.py:229-231](../../app/engines/artifact_transformer.py#L229-L231)).
    No `(Unknown)` string appears anywhere in
    [app/engines/artifact_transformer.py](../../app/engines/artifact_transformer.py).
    (The only `(unknown)` literals in the backend are `applied_by`/user-email
    fallbacks in corrections / gcs upload, unrelated to export speaker labels.)
- **Idempotent artifact metadata (originally) / versioned (now).** The text/doc
  export path upserts one row per `(session_id, kind)`
  ([app/api/exports.py:84-98](../../app/api/exports.py#L84-L98)), a pattern from the
  original `UNIQUE (session_id, kind)` constraint
  ([migrations/018_artifacts.sql:14](../../migrations/018_artifacts.sql#L14)).
  Migration 023 dropped that unique constraint and added versioning, so the burn
  path keeps full version history
  ([migrations/023_artifact_versions.sql](../../migrations/023_artifact_versions.sql)).
- **Caption burn-in is non-critical.** A burn failure never marks the session
  `failed`; it only emits a `captioned_video_failed` WebSocket event
  ([app/tasks/burn_captions.py:168-191](../../app/tasks/burn_captions.py#L168-L191)).
- **CMS HTML publish gate.** `to_cms_html` runs the CMS transform in `strict=True`
  mode; if any unresolved marker (`[X]`, `[T=…]`, leftover curly, `{{token}}`,
  `[pq]`) remains, it raises `CMSValidationError`
  ([app/engines/artifact_transformer.py:439-450,378-398](../../app/engines/artifact_transformer.py#L439-L450)).

## Validation Rules

- **Format whitelist.** `export_session` rejects any format not in
  `{txt, srt, vtt, docx, html, zip}` with HTTP 400
  `{"code":"INVALID_FORMAT","supported":[...]}`
  ([app/api/exports.py:48-53](../../app/api/exports.py#L48-L53)).
- **Caption burn requires a video source.** `POST /captions/burn` returns HTTP 400
  ("No video source available — captions can only be burned into video sessions.")
  if no `sources` row with `role='video'` exists
  ([app/api/session_resources.py:104-117](../../app/api/session_resources.py#L104-L117)).
- **CMS doc validator (`_validate_cms_doc`).** Rejects unresolved markers when
  publishing HTML ([app/engines/artifact_transformer.py:378-398](../../app/engines/artifact_transformer.py#L378-L398)).
- **Caption-line validator (`validate_final_srt`).** A DCMP-style check for line
  length ≤42 chars, no HTML tags, no curly braces, no unresolved markers. **Note:**
  this function exists but is **not called** by any export route in
  [app/api/exports.py](../../app/api/exports.py) — it is a library helper
  ([app/engines/artifact_transformer.py:404-426](../../app/engines/artifact_transformer.py#L404-L426)).

## States

- **Text/doc export:** stateless from the user's view — each request renders fresh.
  Server-side it writes/updates one `artifacts` row per kind (best-effort; failures
  are swallowed) ([app/api/exports.py:83-101](../../app/api/exports.py#L83-L101)).
- **Caption track:** two HTTP states — `200` (full VTT body) or `304` (cache hit,
  no body) ([app/api/exports.py:150-176](../../app/api/exports.py#L150-L176)).
- **Captioned video (backend):** progress events at 5/15/30/40/85/95/100, then
  `captioned_video_ready` on success or `captioned_video_failed` on error
  ([app/tasks/burn_captions.py:226-370](../../app/tasks/burn_captions.py#L226-L370)).
  An artifact carries `is_current` (only one current per `(session, kind)`) and an
  incrementing `version`
  ([migrations/023_artifact_versions.sql:14-25](../../migrations/023_artifact_versions.sql#L14-L25)).

## Dependencies

- **Stored session data:** `sessions`, `segments`, `slides`, `bullets`, `speakers`,
  `chat_messages`, `session_slide_resources`, and `sessions.polls_parsed` /
  `sessions.publishing_links` JSONB — all read by `load_session_for_export`
  ([app/engines/artifact_transformer.py:545-684](../../app/engines/artifact_transformer.py#L545-L684)).
- **`correction_ledger`** — supplies the `max(sequence_number)` used in the
  captions ETag ([app/api/exports.py:138-148](../../app/api/exports.py#L138-L148)).
- **GCS** — source video download + captioned MP4 upload + signed URLs
  ([app/tasks/burn_captions.py:121-157](../../app/tasks/burn_captions.py#L121-L157)).
- **ffmpeg** — invoked via `subprocess` to render burned captions
  ([app/tasks/burn_captions.py:300-312](../../app/tasks/burn_captions.py#L300-L312)).
- **Celery** — `burn_captions_task` runs on the `celery` queue
  ([app/api/session_resources.py:121-124](../../app/api/session_resources.py#L121-L124)).
- **`python-docx`** — DOCX generation ([app/engines/artifact_transformer.py:154](../../app/engines/artifact_transformer.py#L154)).

## Error Handling

- **Session not found:** `load_session_for_export` raises `RuntimeError`, surfaced
  as HTTP 404 by both the export route and the captions route
  ([app/api/exports.py:65-68,160-163](../../app/api/exports.py#L65-L68);
  [app/engines/artifact_transformer.py:565-566](../../app/engines/artifact_transformer.py#L565-L566)).
- **Bad format:** HTTP 400 with the supported list
  ([app/api/exports.py:48-53](../../app/api/exports.py#L48-L53)).
- **Artifact-metadata write failure:** swallowed (rollback, non-fatal) so the
  download still succeeds even if the `artifacts` table is unmigrated or errors
  ([app/api/exports.py:99-101](../../app/api/exports.py#L99-L101)).
- **Burn enqueue failure:** HTTP 500 with the exception class name
  ([app/api/session_resources.py:126-127](../../app/api/session_resources.py#L126-L127)).
- **Burn runtime failure:** non-fatal; emits `captioned_video_failed`; ffmpeg
  non-zero exit raises `RuntimeError` with the stderr tail
  ([app/tasks/burn_captions.py:310-312](../../app/tasks/burn_captions.py#L310-L312)).
- **Frontend download failure:** error toast with the message
  ([DownloadMenu.vue:49-51](../../frontend/src/components/editor/DownloadMenu.vue#L49-L51)).
- **Captions 404:** `captionsBlobUrl` returns `null` and the CC toggle becomes
  cosmetic ([frontend/src/services/api.ts:445](../../frontend/src/services/api.ts#L445);
  [VideoStrip.vue:72-82](../../frontend/src/components/editor/VideoStrip.vue#L72-L82)).

## Permissions

Verified, no role tiers active:

- Every export route requires only a valid JWT via the `CurrentUser` /
  `_user` dependency — there is no admin gate, no role check
  ([app/api/exports.py:46,125](../../app/api/exports.py#L46);
  [app/api/session_resources.py:94,132](../../app/api/session_resources.py#L94)).
- `get_current_user` validates the JWT and (best-effort) that the user is active;
  it does **not** read any role column
  ([app/auth.py:172-208](../../app/auth.py#L172-L208)).
- The export-record's `generated_by` is set to the caller's email
  ([app/api/exports.py:96](../../app/api/exports.py#L96)); the burn artifact's
  `generated_by` is the literal `'burn_captions_task'`
  ([app/tasks/burn_captions.py:349](../../app/tasks/burn_captions.py#L349)).
- The Editor (`/e/:id`) and Viewer (`/v/:id`) routes that host these surfaces are
  not `adminOnly`; the only `adminOnly` client guard
  (`auth.email !== LEGACY_ADMIN_EMAIL`) applies to other routes
  ([frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63)).

## Reporting Impacts

- The `artifacts` table records `kind`, `bytes`, `generated_by`, `generated_at`
  for each generated text/doc export
  ([app/api/exports.py:84-98](../../app/api/exports.py#L84-L98);
  [migrations/018_artifacts.sql:6-15](../../migrations/018_artifacts.sql#L6-L15)),
  giving a per-session ledger of what was exported, how big, and by whom. This is
  a metadata ledger only — the artifact *bytes* for text/doc exports are not
  stored (`gcs_uri` stays null for those; only `bytes` length is recorded).
- Captioned-video artifacts persist `gcs_uri`, `bytes`, `version`, `is_current`,
  `style_config` ([app/tasks/burn_captions.py:337-360](../../app/tasks/burn_captions.py#L337-L360)),
  enabling version history per session.
- No aggregate reporting / dashboard over artifacts was found in code
  (`NOT VERIFIED IN CODE`).

## Audit Requirements

- The `artifacts` table is the audit surface for exports: `generated_by` +
  `generated_at` per `(session, kind)`
  ([migrations/018_artifacts.sql:6-15](../../migrations/018_artifacts.sql#L6-L15)).
- No entries to a dedicated `audit_events`-style trail are written from the export
  routes themselves (`NOT VERIFIED IN CODE` — the export path writes only to
  `artifacts`; see [app/api/exports.py:83-101](../../app/api/exports.py#L83-L101)).

## Data Relationships

- `artifacts.session_id` → `sessions(id)` with `ON DELETE CASCADE`
  ([migrations/018_artifacts.sql:8](../../migrations/018_artifacts.sql#L8)).
- `artifacts.kind` is one of `docx | srt | vtt | txt | zip | captioned_video`
  (+ `html` is produced by the engine and accepted by the endpoint though the
  migration comment lists the original six)
  ([migrations/018_artifacts.sql:9](../../migrations/018_artifacts.sql#L9);
  [app/api/exports.py:36](../../app/api/exports.py#L36)).
- After migration 023: at most one `is_current = TRUE` row per `(session_id, kind)`
  (partial unique index), with `version` incrementing
  ([migrations/023_artifact_versions.sql:20-25](../../migrations/023_artifact_versions.sql#L20-L25)).
- The render inputs join `segments → slides` (via `slide_id`) and
  `segments → speakers` (via `speaker_id`), with `slides → bullets`
  ([app/engines/artifact_transformer.py:568-598](../../app/engines/artifact_transformer.py#L568-L598)).

## Known Constraints

- **No caption-style/burn-in UI.** `burnCaptions` and `captionedVideo` API helpers
  exist ([frontend/src/services/api.ts:205-216](../../frontend/src/services/api.ts#L205-L216))
  but **no component calls them** (`IMPLEMENTATION NOT FOUND`). The whole burn
  feature is reachable only by direct API call.
- **Viewer download buttons are stubs.** They emit a warning toast and do not
  download ([ViewerView.vue:91-96](../../frontend/src/views/ViewerView.vue#L91-L96)).
- **Publishing checklist links are inert** (`href="#"`, `preventDefault` + warn
  toast) ([ViewerView.vue:78-86,97-103](../../frontend/src/views/ViewerView.vue#L78-L103)).
- **Editor menu hides `vtt` and `html`** even though the backend supports them
  ([DownloadMenu.vue:27-32](../../frontend/src/components/editor/DownloadMenu.vue#L27-L32)).
- **BR-016 / BR-017 do not match documented behavior** — see Business Rules above.
- **`validate_final_srt` is defined but never invoked** by any export route
  ([app/engines/artifact_transformer.py:404-426](../../app/engines/artifact_transformer.py#L404-L426)).
- **Text/doc export bytes are not persisted** to GCS — only re-rendered on demand
  and recorded by length ([app/api/exports.py:88-97](../../app/api/exports.py#L88-L97)).

## Source Verification
- **Files Used:** app/api/exports.py, app/engines/artifact_transformer.py, app/iil/normalization.py, app/tasks/burn_captions.py, app/api/session_resources.py, app/auth.py, migrations/018_artifacts.sql, migrations/023_artifact_versions.sql, frontend/src/components/editor/DownloadMenu.vue, frontend/src/views/ViewerView.vue, frontend/src/components/editor/VideoStrip.vue, frontend/src/services/api.ts, frontend/src/router/index.ts, docs/BUSINESS_RULES.md, docs/specs/workflow-and-export.spec.md
- **Components Used:** DownloadMenu.vue, ViewerView.vue, VideoStrip.vue
- **APIs Used:** GET /v1/sessions/{id}/exports/{format}, GET /v1/sessions/{id}/captions.vtt, POST /v1/sessions/{id}/captions/burn, GET /v1/sessions/{id}/captioned-video
- **Database Tables Used:** artifacts, sessions, segments, slides, bullets, speakers, chat_messages, session_slide_resources, sources, correction_ledger
- **Permission Logic Used:** JWT presence via CurrentUser/_user (no role tier; no admin gate on any export route)
- **Confidence Score:** High — every behavior traced to current source; BR-016 (filler stripping) and BR-017 ("(Unknown)" fallback) seed claims re-verified and found to NOT match code; corrected and flagged.
- **Evidence Links:** [app/api/exports.py:41](../../app/api/exports.py#L41), [app/api/exports.py:120](../../app/api/exports.py#L120), [app/engines/artifact_transformer.py:247-249](../../app/engines/artifact_transformer.py#L247-L249), [app/engines/artifact_transformer.py:121-124](../../app/engines/artifact_transformer.py#L121-L124), [app/tasks/burn_captions.py:207](../../app/tasks/burn_captions.py#L207), [migrations/023_artifact_versions.sql:20](../../migrations/023_artifact_versions.sql#L20), [frontend/src/components/editor/DownloadMenu.vue:48](../../frontend/src/components/editor/DownloadMenu.vue#L48)
