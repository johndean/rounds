# Exports & Artifacts — Technical Spec

> Module key: `exports-artifacts`. Code-verified against `HEAD` on 2026-06-08.
> Claims that cannot be proven from code are tagged `NOT VERIFIED IN CODE`,
> `IMPLEMENTATION NOT FOUND`, or `PARTIALLY IMPLEMENTED`.

## Architecture

Three cooperating layers:

1. **Render engine** — a single stateless module,
   [app/engines/artifact_transformer.py](../../app/engines/artifact_transformer.py),
   exposes `to_txt`/`to_srt`/`to_vtt`/`to_docx`/`to_cms_html`/`to_zip` (each returns
   raw `bytes`) and `load_session_for_export` (a synchronous single-read DB loader).
2. **HTTP routes** — [app/api/exports.py](../../app/api/exports.py) defines two
   routers: `router` (`/v1/sessions/{session_id}/exports`) for file downloads and
   `captions_router` (`/v1/sessions/{session_id}`) for the cache-friendly
   `captions.vtt` track. Both are mounted in
   [app/main.py:230-231](../../app/main.py#L230-L231). The caption *burn-in*
   routes live in [app/api/session_resources.py](../../app/api/session_resources.py)
   (mounted at [app/main.py:217](../../app/main.py#L217)).
3. **Background render** — [app/tasks/burn_captions.py](../../app/tasks/burn_captions.py)
   is a Celery task that shells out to ffmpeg to produce a captioned MP4, stores a
   versioned `artifacts` row, and pushes progress via WebSocket.

Data flow for a text/doc download:

```
DownloadMenu.vue ──fetch──▶ GET /exports/{format}
   exportsApi.download()       │
                               ├─ load_session_for_export(id)  (sync SQLAlchemy engine)
                               ├─ to_<fmt>(sess) → bytes
                               ├─ upsert artifacts row (best-effort)
                               └─ Response(bytes, Content-Disposition: attachment)
```

`load_session_for_export` opens its **own synchronous** SQLAlchemy engine
(`DATABASE_URL` with `+asyncpg` stripped) rather than using the request's async
session — it is a self-contained read
([app/engines/artifact_transformer.py:545-628](../../app/engines/artifact_transformer.py#L545-L628)).

## Frontend Components

| Component | Role | File |
|---|---|---|
| `DownloadMenu.vue` | Editor dropdown (docx/srt/txt/zip); calls `exportsApi.download` | [frontend/src/components/editor/DownloadMenu.vue](../../frontend/src/components/editor/DownloadMenu.vue) |
| `ViewerView.vue` | Preview page; download buttons are **stubs** (warn toast) | [frontend/src/views/ViewerView.vue](../../frontend/src/views/ViewerView.vue) |
| `VideoStrip.vue` | Loads `captions.vtt` as a Blob URL into `<track>` | [frontend/src/components/editor/VideoStrip.vue](../../frontend/src/components/editor/VideoStrip.vue) |

API client (`exportsApi` / internal `exports_`) in
[frontend/src/services/api.ts:403-457](../../frontend/src/services/api.ts#L403-L457):

- `download(sessionId, format)` — raw `fetch` (not the JSON `http()` wrapper),
  injects `Authorization: Bearer <token>`, reads a Blob, derives the filename from
  `Content-Disposition`, and triggers a `<a download>` click; revokes the object
  URL afterward. TypeScript signature is `'docx' | 'srt' | 'vtt' | 'txt' | 'zip'`
  (no `html`) ([api.ts:405-429](../../frontend/src/services/api.ts#L405-L429)).
- `captionsBlobUrl(sessionId)` — fetches `captions.vtt`, returns a Blob URL or
  `null` on 404 ([api.ts:439-453](../../frontend/src/services/api.ts#L439-L453)).
- `burnCaptions(id, styleConfig)` and `captionedVideo(id)` — defined on the
  `sessions` API object ([api.ts:205-216](../../frontend/src/services/api.ts#L205-L216))
  but **no component invokes them** (`IMPLEMENTATION NOT FOUND` for callers).

## Backend Services

### Render engine — `artifact_transformer.py`

- **Dataclasses:** `SegmentForExport` (incl. `speaker_role`),
  `SlideForExport`, `PollForExport`, `ChatForExport`, `SessionForExport`
  ([artifact_transformer.py:26-77](../../app/engines/artifact_transformer.py#L26-L77)).
- **`to_txt`** — markdown-ish: `# title`, `Code:`, optional `Presenter:`, per-slide
  `## Slide N: title`, `Speaker: text` lines
  ([artifact_transformer.py:106-125](../../app/engines/artifact_transformer.py#L106-L125)).
- **`to_srt`** — numbered cues with `HH:MM:SS,mmm` timestamps; each line passes
  through `apply_srt_transform`
  ([artifact_transformer.py:128-141](../../app/engines/artifact_transformer.py#L128-L141)).
- **`to_vtt`** — `WEBVTT` header + `HH:MM:SS.mmm` cues; **no** transform applied
  ([artifact_transformer.py:144-150](../../app/engines/artifact_transformer.py#L144-L150)).
- **`to_docx`** — `python-docx`; H1 title, presenter/code paragraphs, H2 per slide,
  bold speaker prefix. A `speaker_role == 'primary'` prefix is rendered in navy
  `RGBColor(0x00,0x28,0x55)`. Segment text splits on `\n\n` (paragraph) / `\n`
  (soft break) ([artifact_transformer.py:153-205](../../app/engines/artifact_transformer.py#L153-L205)).
- **`to_cms_html`** — builds a marked transcript, runs `apply_cms_transform(strict=True)`,
  then converts to inline HTML (slide markers → `<h2>`, `**bold**`, links, `<ul>`)
  ([artifact_transformer.py:439-520](../../app/engines/artifact_transformer.py#L439-L520)).
- **`to_zip`** — bundles `.txt`, `.srt`, `.vtt`, `.docx`, `.html`, plus a
  `_slides.txt` outline ([artifact_transformer.py:523-539](../../app/engines/artifact_transformer.py#L523-L539)).
- **Macro layer:** `apply_srt_transform` (11-step structural strip),
  `apply_cms_transform` (9-step publish transform with poll/chat/resource injection
  and hyperlink replacement), `_validate_cms_doc` (`CMSValidationError` on
  unresolved markers), `validate_final_srt` (DCMP line check — **unused** by routes)
  ([artifact_transformer.py:236-426](../../app/engines/artifact_transformer.py#L236-L426)).
- **`load_session_for_export`** — synchronous reads of `sessions`, `segments`
  (joined to `slides`+`speakers`), `slides` (joined to `bullets`),
  `sessions.polls_parsed`, `chat_messages`, `session_slide_resources`; returns a
  populated `SessionForExport`
  ([artifact_transformer.py:545-684](../../app/engines/artifact_transformer.py#L545-L684)).

### Burn task — `burn_captions.py`

- `style_config_to_ass` — translates the (UI-less) CaptionStyleDialog payload to an
  ffmpeg `force_style=` string. Clamps numeric ranges, maps
  `(vertical_position, horizontal_align)` → ASS alignment code, computes BGR colors
  ([burn_captions.py:66-113,43-63](../../app/tasks/burn_captions.py#L66-L113)).
- GCS helpers: `_download_video_from_gcs`, `_upload_to_gcs`, `_generate_signed_url`
  ([burn_captions.py:121-157](../../app/tasks/burn_captions.py#L121-L157)).
- `_BurnCaptionsTask` overrides `on_failure` so a failure never marks the session
  failed; it emits `captioned_video_failed`
  ([burn_captions.py:168-191](../../app/tasks/burn_captions.py#L168-L191)).
- `burn_captions_task` — `max_retries=2`, `time_limit=3600`, `soft_time_limit=3300`;
  builds SRT (`caption_source` `'ai'` = cleaned segments, `'stt'` = word-level cues
  grouped to ~3s), runs ffmpeg, uploads, versions the artifact, emits WS events
  ([burn_captions.py:199-384](../../app/tasks/burn_captions.py#L199-L384)).

## APIs

| Method | Path | Auth | File:Line |
|---|---|---|---|
| GET | `/v1/sessions/{session_id}/exports/{format}` | JWT (`CurrentUser`) | [app/api/exports.py:41](../../app/api/exports.py#L41) |
| GET | `/v1/sessions/{session_id}/captions.vtt` | JWT (`CurrentUser`) | [app/api/exports.py:120](../../app/api/exports.py#L120) |
| POST | `/v1/sessions/{session_id}/captions/burn` | JWT (`_user`) | [app/api/session_resources.py:92](../../app/api/session_resources.py#L92) |
| GET | `/v1/sessions/{session_id}/captioned-video` | JWT (`_user`) | [app/api/session_resources.py:130](../../app/api/session_resources.py#L130) |

- **`GET /exports/{format}`** — lowercases + whitelists the format
  (`txt|srt|vtt|docx|html|zip`); 400 on miss. Lazily imports the engine, loads the
  session (404 on `RuntimeError`), renders, upserts the artifact row (best-effort),
  and returns `Response(content=body, media_type=_KIND_TO_MIME[fmt],
  headers={Content-Disposition: attachment; filename="{code}.{fmt}"})`
  ([app/api/exports.py:41-108](../../app/api/exports.py#L41-L108)).
- **`GET /captions.vtt`** — computes `etag = W/"{session_id}-{max_seq}"` from
  `MAX(correction_ledger.sequence_number)`; returns 304 when `If-None-Match` matches
  (with `Cache-Control: private, max-age=60`), else renders VTT with
  `Content-Disposition: inline`
  ([app/api/exports.py:120-176](../../app/api/exports.py#L120-L176)).
- **`POST /captions/burn`** — 400 if no `video` source; else `apply_async` on the
  `celery` queue; returns `{enqueued, session_id}`; 500 on enqueue error
  ([app/api/session_resources.py:92-127](../../app/api/session_resources.py#L92-L127)).
- **`GET /captioned-video`** — returns the current `captioned_video` artifact with a
  fresh 1-hour signed URL (`CaptionedVideoArtifact` model), or `null`
  ([app/api/session_resources.py:81-177](../../app/api/session_resources.py#L81-L177)).

`_KIND_TO_MIME` ([app/api/exports.py:31-38](../../app/api/exports.py#L31-L38)):

```
txt → text/plain; charset=utf-8       srt → application/x-subrip; charset=utf-8
vtt → text/vtt; charset=utf-8         docx → application/vnd.openxml…wordprocessingml.document
html → text/html; charset=utf-8       zip → application/zip
```

## Data Models

`artifacts` table — [migrations/018_artifacts.sql](../../migrations/018_artifacts.sql),
altered by [migrations/023_artifact_versions.sql](../../migrations/023_artifact_versions.sql):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `session_id` | UUID NOT NULL | FK → `sessions(id)` ON DELETE CASCADE |
| `kind` | TEXT NOT NULL | `docx`\|`srt`\|`vtt`\|`txt`\|`zip`\|`captioned_video` (engine also emits `html`) |
| `gcs_uri` | TEXT | set for `captioned_video`; null for text/doc exports |
| `bytes` | BIGINT | byte length (text/doc) or file size (burn) |
| `generated_by` | TEXT | caller email (export) / `'burn_captions_task'` (burn) |
| `generated_at` | TIMESTAMPTZ NOT NULL | `now()` |
| `version` | INTEGER NOT NULL DEFAULT 1 | added in 023 |
| `is_current` | BOOLEAN NOT NULL DEFAULT TRUE | added in 023 |
| `style_config` | JSONB NOT NULL DEFAULT '{}' | added in 023 |

Constraints / indexes:

- Original `UNIQUE (session_id, kind)` — **dropped** in 023
  ([018_artifacts.sql:14](../../migrations/018_artifacts.sql#L14);
  [023_artifact_versions.sql:18](../../migrations/023_artifact_versions.sql#L18)).
- `artifacts_session_idx` (018), `artifacts_unique_current_idx`
  (partial unique on `(session_id, kind) WHERE is_current = TRUE`, 023),
  `artifacts_session_kind_version_idx` (`version DESC`, 023)
  ([023_artifact_versions.sql:20-25](../../migrations/023_artifact_versions.sql#L20-L25)).

API DTOs: `BurnCaptionsRequest` (`style_config?`), `CaptionedVideoArtifact`
(`artifact_id, gcs_uri, download_url?, bytes?, version, is_current, generated_at?,
style_config?`) ([app/api/session_resources.py:75-89](../../app/api/session_resources.py#L75-L89)).

## Events

WebSocket events emitted by the burn task (`publish_ws_event_sync`):

| Event | When | Payload | Line |
|---|---|---|---|
| `captioned_video_progress` | each stage (5/15/30/40/85/95/100) | `{progress, substage}` | [burn_captions.py:226-231](../../app/tasks/burn_captions.py#L226-L231) |
| `captioned_video_ready` | success | `{artifact_id, download_url, byte_size}` | [burn_captions.py:365-370](../../app/tasks/burn_captions.py#L365-L370) |
| `captioned_video_failed` | task failure | `{reason}` | [burn_captions.py:185-189](../../app/tasks/burn_captions.py#L185-L189) |

The text/doc export and captions.vtt routes emit no events.

## State Management

- **Frontend:** `DownloadMenu` holds local `open`/`downloading` refs only
  ([DownloadMenu.vue:22-24](../../frontend/src/components/editor/DownloadMenu.vue#L22-L24)).
  `VideoStrip` holds the `captionsBlobUrl` ref and revokes it on unmount
  ([VideoStrip.vue:74-86](../../frontend/src/components/editor/VideoStrip.vue#L74-L86)).
  No Pinia store backs exports.
- **Backend:** text/doc exports are upsert-on-write (one row per `(session, kind)`
  pre-023 semantics, [app/api/exports.py:84-98](../../app/api/exports.py#L84-L98));
  burn artifacts use the `is_current` versioning pattern
  ([burn_captions.py:324-360](../../app/tasks/burn_captions.py#L324-L360)).

## Validation

- **Format whitelist** → 400 `INVALID_FORMAT`
  ([app/api/exports.py:48-53](../../app/api/exports.py#L48-L53)).
- **Burn requires video source** → 400
  ([app/api/session_resources.py:104-117](../../app/api/session_resources.py#L104-L117)).
- **CMS strict validation** (`_validate_cms_doc`) raises `CMSValidationError` on
  unresolved `[X]`, `[T=…]`, leftover `{…}`, `{{token}}`, or `[pq]`
  ([artifact_transformer.py:378-398](../../app/engines/artifact_transformer.py#L378-L398)).
- **`validate_final_srt`** (≤42 chars/line, no HTML/curly/markers) is defined but
  **not invoked by any route** ([artifact_transformer.py:404-426](../../app/engines/artifact_transformer.py#L404-L426)).
- **`style_config_to_ass`** clamps font size (8-96), outline (0-4), margin (0-200)
  ([burn_captions.py:77-88](../../app/tasks/burn_captions.py#L77-L88)).

## Security

- All four routes require a valid JWT and nothing more (`CurrentUser` / `_user`)
  ([app/api/exports.py:46,125](../../app/api/exports.py#L46);
  [app/api/session_resources.py:94,132](../../app/api/session_resources.py#L94)).
- `get_current_user` decodes the JWT and best-effort checks `user_is_active`; no
  role is read ([app/auth.py:172-208](../../app/auth.py#L172-L208)).
- The captions route cannot rely on the `<track>` element to send the JWT, so the
  frontend fetches the VTT authenticated and wraps it in a Blob URL
  ([api.ts:431-453](../../frontend/src/services/api.ts#L431-L453)).
- ffmpeg input is shell-escaped before being placed in the `-vf` argument
  (`safe_style`/`safe_srt`) ([burn_captions.py:294-297](../../app/tasks/burn_captions.py#L294-L297)).
- The captioned MP4 is written under the session-scoped GCS prefix
  `sessions/{id}/captioned/<uuid>.mp4` ([burn_captions.py:317-318](../../app/tasks/burn_captions.py#L317-L318)).

## Permissions

Role-based authorization is **not** enforced here. There is no `require_admin`,
no role column read, and no `LEGACY_ADMIN_EMAIL` gate on any export route. The only
admin construct in the codebase is the client-side `adminOnly` router guard
(`auth.email !== LEGACY_ADMIN_EMAIL`,
[frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63)), and the
Editor/Viewer routes that host these surfaces are not flagged `adminOnly`.
Real authorization for exports = JWT presence.

## Integrations

- **GCS** (`google.cloud.storage`) — video download, captioned MP4 upload, v4
  signed URLs ([burn_captions.py:121-157](../../app/tasks/burn_captions.py#L121-L157)).
- **ffmpeg** — `subprocess.run(["ffmpeg", "-y", "-i", …, "-vf", vf, "-c:a","copy",
  "-movflags","+faststart", out])`, 3300s timeout
  ([burn_captions.py:300-312](../../app/tasks/burn_captions.py#L300-L312)).
- **python-docx** — DOCX rendering ([artifact_transformer.py:154-155](../../app/engines/artifact_transformer.py#L154-L155)).
- **Celery** — burn task dispatch ([app/api/session_resources.py:120-124](../../app/api/session_resources.py#L120-L124)).
- **WebSocket bridge** (`publish_ws_event_sync`) — progress/ready/failed events
  ([burn_captions.py:221](../../app/tasks/burn_captions.py#L221)).
- The text/doc export and captions.vtt routes touch **no** external service — pure
  DB read + in-process render.

## Background Jobs

- **`burn_captions_task`** (`name="rounds.tasks.burn_captions"`, queue `celery`).
  Steps: resolve video source → build SRT → download → ffmpeg → upload →
  mark prior `captioned_video` artifacts `is_current=FALSE` and insert a new
  versioned row → emit `captioned_video_ready` with a 24h signed URL → clean tmp
  files ([burn_captions.py:199-386](../../app/tasks/burn_captions.py#L199-L386)).
  Version is computed as `coalesce((SELECT max(version)+1 …), 1)`
  ([burn_captions.py:345-347](../../app/tasks/burn_captions.py#L345-L347)).
- The text/doc export and captions routes run **synchronously** within the request
  (no Celery) — `load_session_for_export` + render happen inline
  ([app/api/exports.py:65-108](../../app/api/exports.py#L65-L108)).

## Error Handling

- `RuntimeError` from the loader → HTTP 404 (export + captions routes)
  ([app/api/exports.py:65-68,160-163](../../app/api/exports.py#L65-L68)).
- Bad format → 400 `INVALID_FORMAT`
  ([app/api/exports.py:48-53](../../app/api/exports.py#L48-L53)).
- Artifact-metadata upsert wrapped in try/except + rollback — never blocks the
  download ([app/api/exports.py:99-101](../../app/api/exports.py#L99-L101)).
- Burn enqueue error → HTTP 500 with exception class name
  ([app/api/session_resources.py:126-127](../../app/api/session_resources.py#L126-L127)).
- ffmpeg non-zero exit → `RuntimeError` carrying the last 800 chars of stderr;
  handled by `_BurnCaptionsTask.on_failure` (non-fatal, WS event)
  ([burn_captions.py:310-312,177-191](../../app/tasks/burn_captions.py#L310-L312)).
- Signed-URL generation in `GET /captioned-video` is wrapped so a failure yields a
  null `download_url` rather than a 500
  ([app/api/session_resources.py:161-166](../../app/api/session_resources.py#L161-L166)).
- Frontend: `download` throws `ApiError(status, envelope)` on non-OK
  ([api.ts:411-415](../../frontend/src/services/api.ts#L411-L415)); `DownloadMenu`
  catches it into an error toast
  ([DownloadMenu.vue:49-51](../../frontend/src/components/editor/DownloadMenu.vue#L49-L51)).

## Performance Considerations

- **Captions ETag.** `captions.vtt` computes the ETag from
  `MAX(correction_ledger.sequence_number)` *before* materializing the body and
  returns 304 with no body on a cache hit; `Cache-Control: private, max-age=60`
  also lets the browser skip the network for the first minute
  ([app/api/exports.py:129-176](../../app/api/exports.py#L129-L176)).
- **Synchronous engine inside an async route.** `load_session_for_export` creates
  and disposes its own blocking SQLAlchemy engine on each export call
  ([artifact_transformer.py:551-628](../../app/engines/artifact_transformer.py#L551-L628)).
  This runs in the request path and will block the event loop for the duration of
  the read + render (`NOT VERIFIED IN CODE` whether it is offloaded to a threadpool;
  the route is `async def` and calls it directly).
- **Burn task limits** — `time_limit=3600` (hard kill), `soft_time_limit=3300`,
  `max_retries=2`; ffmpeg gets a 3300s subprocess timeout
  ([burn_captions.py:199-206,309](../../app/tasks/burn_captions.py#L199-L206)).
- **`to_zip` renders every format** (txt/srt/vtt/docx/html + slide outline) in one
  request — the most expensive export
  ([artifact_transformer.py:523-539](../../app/engines/artifact_transformer.py#L523-L539)).
- **Constants** (e.g. the docx navy `RGBColor`) are hoisted to function scope to
  avoid per-segment reconstruction
  ([artifact_transformer.py:161](../../app/engines/artifact_transformer.py#L161)).

## Source Verification
- **Files Used:** app/api/exports.py, app/engines/artifact_transformer.py, app/iil/normalization.py, app/tasks/burn_captions.py, app/api/session_resources.py, app/auth.py, app/main.py, migrations/018_artifacts.sql, migrations/023_artifact_versions.sql, frontend/src/components/editor/DownloadMenu.vue, frontend/src/views/ViewerView.vue, frontend/src/components/editor/VideoStrip.vue, frontend/src/services/api.ts, frontend/src/router/index.ts
- **Components Used:** DownloadMenu.vue, ViewerView.vue, VideoStrip.vue
- **APIs Used:** GET /v1/sessions/{id}/exports/{format}, GET /v1/sessions/{id}/captions.vtt, POST /v1/sessions/{id}/captions/burn, GET /v1/sessions/{id}/captioned-video
- **Database Tables Used:** artifacts, sessions, segments, slides, bullets, speakers, chat_messages, session_slide_resources, sources, correction_ledger, words
- **Permission Logic Used:** JWT presence via CurrentUser/_user; no role/admin gate on any export route
- **Confidence Score:** High — every route, model, event, and task traced to current source; the unused validate_final_srt and the sync-engine-in-async-route concern are flagged, and the absent burn-in UI caller is noted as IMPLEMENTATION NOT FOUND.
- **Evidence Links:** [app/api/exports.py:41](../../app/api/exports.py#L41), [app/api/exports.py:120](../../app/api/exports.py#L120), [app/tasks/burn_captions.py:199-384](../../app/tasks/burn_captions.py#L199-L384), [migrations/023_artifact_versions.sql:14-25](../../migrations/023_artifact_versions.sql#L14-L25), [app/api/session_resources.py:92-177](../../app/api/session_resources.py#L92-L177), [frontend/src/services/api.ts:403-457](../../frontend/src/services/api.ts#L403-L457)
