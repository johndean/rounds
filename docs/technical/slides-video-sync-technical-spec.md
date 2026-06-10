# Slides & Video Synchronization — Technical Spec

> Module key: `slides-video-sync`. This document describes the implemented architecture: a Celery slide-extraction + alignment pipeline (frame → anchor → fusion → align), the read-only sub-resource APIs the Editor consumes, and the three Vue editor components that render synchronized playback.

## Architecture

Two concerns, both backed by the same `slides` / `segments` data:

1. **Slide extraction** (`slide_extract_task`) — converts uploaded decks (`sources.role='slide'`) into `slides` + `bullets` rows, rendering PNG thumbnails for PDFs to GCS. Runs during ingest.

2. **Slide↔transcript alignment** — a 4-task chain that produces `slide_time_ranges` and per-segment `alignments`, and stamps `segments.slide_id`:

   ```
   frame_task        (video → VisualSignal[] in Redis)
        │  (triggered by transcribe_task, not by frame_task itself)
   anchor_task       (segments + visual signals → AnchorHit[] + SemanticShift[] in Redis) → triggers normalize_task
        │
   fusion_task       (visual + anchor + semantic → slide_time_ranges + replay_log) → triggers align_task
        │
   align_task        (segments + slide_time_ranges → alignments + segments.slide_id) → triggers finalize_task
   ```

   Source: [`app/tasks/frame_task.py`](../../app/tasks/frame_task.py), [`app/tasks/anchor_task.py`](../../app/tasks/anchor_task.py), [`app/tasks/fusion.py`](../../app/tasks/fusion.py), [`app/tasks/align.py`](../../app/tasks/align.py). `frame_task` explicitly notes it does NOT trigger the next task — `anchor_task` is fired by `transcribe_task`, which reads frame output from Redis at that point ([`app/tasks/frame_task.py:21-22`](../../app/tasks/frame_task.py#L21)).

The Editor is purely a consumer: it fetches slides, segments (each carrying `slide_id`), a signed media URL, words, and word-alignment, then derives the active slide client-side from the playhead.

## Frontend Components

### `VideoStrip.vue`
The video/audio player ([`frontend/src/components/editor/VideoStrip.vue`](../../frontend/src/components/editor/VideoStrip.vue)).

- Props include `session`, `activeSlide`, `slides`, `time`, `total`, `playing`, `rate`, `cc`, `segmentsBySlide`, `mediaUrl`, `mediaKind` ([`VideoStrip.vue:41-53`](../../frontend/src/components/editor/VideoStrip.vue#L41)).
- Mounts a `<video>` for `mediaKind==='video'`, a hidden `<audio>` for `'audio'`, else a poster ([`VideoStrip.vue:259-306`](../../frontend/src/components/editor/VideoStrip.vue#L259)).
- Two-way time/playing/rate sync via `update:*` emits; parent → element pushes guarded against feedback loops (seek tolerance 0.4s, rate tolerance 0.001) ([`VideoStrip.vue:219-241`](../../frontend/src/components/editor/VideoStrip.vue#L219)).
- `timeupdate` throttled to ~10 Hz (100 ms min, leading + trailing edge) — a port of MIC `stores/playback.js:116-139` ([`VideoStrip.vue:148-203`](../../frontend/src/components/editor/VideoStrip.vue#L148)).
- Scrubber drag-to-seek is pointer-based with `requestAnimationFrame` throttling ([`VideoStrip.vue:102-146`](../../frontend/src/components/editor/VideoStrip.vue#L102)).
- Chapter marks computed from `segmentsBySlide` — one per slide that has segments, positioned at the first segment's start / total ([`VideoStrip.vue:169-179`](../../frontend/src/components/editor/VideoStrip.vue#L169)).
- Captions `<track>` is fed a Blob URL fetched authenticated (`exportsApi.captionsBlobUrl`), because `<track>` cannot carry an Authorization header ([`VideoStrip.vue:69-100`](../../frontend/src/components/editor/VideoStrip.vue#L69)).

### `SlideRail.vue`
The slide list ([`frontend/src/components/editor/SlideRail.vue`](../../frontend/src/components/editor/SlideRail.vue)). Props: `slides`, `activeSlideId`, `focusedSlideId`, `mode` (`'focus' | 'filter'`), `segmentsBySlide` ([`SlideRail.vue:11-17`](../../frontend/src/components/editor/SlideRail.vue#L11)). Per-slide accent + style snapshots are memoized in `slideBase`; the `rows` computed only re-derives active/focused classes ([`SlideRail.vue:46-89`](../../frontend/src/components/editor/SlideRail.vue#L46)). Emits `modeChange`, `slideClick`, `clearFocus`.

### `ActiveSlideCard.vue`
The right-rail active-slide panel ([`frontend/src/components/editor/ActiveSlideCard.vue`](../../frontend/src/components/editor/ActiveSlideCard.vue)). Props: `slide`, `segmentCount`, `collapsed`, `time`, `totalDuration`, `liveSlides`, `liveSegments` ([`ActiveSlideCard.vue:13-23`](../../frontend/src/components/editor/ActiveSlideCard.vue#L13)). Renders a preview, "Slide NN of M", and an SVG minimap with one rect per slide that has segments (segment span scaled to a 200-unit viewbox) plus a playhead marker ([`ActiveSlideCard.vue:40-62`](../../frontend/src/components/editor/ActiveSlideCard.vue#L40)). The "Re-assign segments to slide" button only toasts a warning ([`ActiveSlideCard.vue:64-68`](../../frontend/src/components/editor/ActiveSlideCard.vue#L64)).

### `EditorView.vue` (host)
Fetches slides at [`EditorView.vue:364`](../../frontend/src/views/EditorView.vue#L364); fetches the media URL (`?role=video`, falling through to audio) and sets `mediaKind` from content type at [`EditorView.vue:383-389`](../../frontend/src/views/EditorView.vue#L383); computes `segmentsBySlide` ([`EditorView.vue:484`](../../frontend/src/views/EditorView.vue#L484)) and `activeSlide` from the active segment's `slide_id` ([`EditorView.vue:596`](../../frontend/src/views/EditorView.vue#L596)).

## Backend Services

### Sub-resource router (`app/api/session_resources.py`)
Mounted at prefix `/v1/sessions/{session_id}` ([`app/api/session_resources.py:21`](../../app/api/session_resources.py#L21)). Relevant endpoints: `GET /slides`, `POST /slides/re-extract`, `GET /sources`, `GET /media-url`, `GET /words`, plus captions burn/fetch. All are thin SQLAlchemy `text()` queries against the DbSession; the re-extract endpoint enqueues a Celery task.

### Word-alignment router (`app/api/word_alignment.py`)
Mounted at `/v1/sessions/{session_id}/word-alignment` ([`app/api/word_alignment.py:31-34`](../../app/api/word_alignment.py#L31)). Joins `word_alignment` → `segments`, groups rows by `segment_id`, and returns compact `{g,s,e,k}` entries ([`app/api/word_alignment.py:54-101`](../../app/api/word_alignment.py#L54)).

### Engines
- **`app/engines/anchor.py`** — `detect_anchors` (phrase match + cross-validation), `compute_semantic_shifts` (adjacent token-overlap dissimilarity) ([`app/engines/anchor.py:56-136`](../../app/engines/anchor.py#L56)).
- **`app/engines/alignment.py`** — `align_segment` 4-signal scorer producing `AlignmentRecord` ([`app/engines/alignment.py:120-197`](../../app/engines/alignment.py#L120)).
- **`app/engines/diff.py`** — `align_words` LCS pairing producing `WordPair` with `match_kind` `'exact' | 'unmatched'` ([`app/engines/diff.py:125-167`](../../app/engines/diff.py#L125)).

## APIs

| Method | Path | Purpose | Source |
|---|---|---|---|
| GET | `/v1/sessions/{id}/slides` | List slides (id, slide_index, title, image_uri, start_ms, end_ms) ordered by slide_index | [session_resources.py:58-71](../../app/api/session_resources.py#L58) |
| POST | `/v1/sessions/{id}/slides/re-extract` | Enqueue `slide_extract_selected_pages_task` for 1-based `page_indices` | [session_resources.py:39-55](../../app/api/session_resources.py#L39) |
| GET | `/v1/sessions/{id}/sources` | List uploaded files (role, filename, gcs_uri, content_type, size_bytes, duration_sec) | [session_resources.py:381-394](../../app/api/session_resources.py#L381) |
| GET | `/v1/sessions/{id}/media-url?role=audio\|video` | 24h signed v4 GET URL for primary playback source; audio default, falls through; 404 if none | [session_resources.py:406-446](../../app/api/session_resources.py#L406) |
| GET | `/v1/sessions/{id}/words` | Per-word STT tokens ordered by segment start then word seq | [session_resources.py:461-485](../../app/api/session_resources.py#L461) |
| GET | `/v1/sessions/{id}/word-alignment` | Per-Gemini-word STT timing grouped by segment_id | [word_alignment.py:54-101](../../app/api/word_alignment.py#L54) |
| POST | `/v1/sessions/{id}/captions/burn` | Enqueue `burn_captions_task`; 400 if no video source | [session_resources.py:92-127](../../app/api/session_resources.py#L92) |
| GET | `/v1/sessions/{id}/captioned-video` | Current captioned MP4 artifact + fresh 1h signed URL, or null | [session_resources.py:130-177](../../app/api/session_resources.py#L130) |

Frontend client bindings: `media.url` ([api.ts:343-348](../../frontend/src/services/api.ts#L343)), `words.listBySession` ([api.ts:280-283](../../frontend/src/services/api.ts#L280)), `wordAlignment.get` ([api.ts:304-307](../../frontend/src/services/api.ts#L304)), `burnCaptions`/`captionedVideo` ([api.ts:204-215](../../frontend/src/services/api.ts#L204)). There is no client binding for `/slides/re-extract`.

## Data Models

### `slides` ([`migrations/001_init.sql:54-64`](../../migrations/001_init.sql#L54), extended [`migrations/016_bullets.sql:6-7`](../../migrations/016_bullets.sql#L6))
`id`, `session_id` (FK→sessions, CASCADE), `slide_index` (0-based int), `title`, `image_uri`, `start_ms`, `end_ms`, `metadata` jsonb, plus `full_text`, `thumbnail_uri`. UNIQUE `(session_id, slide_index)`. (Note: `slide_extract_task` also references `slide_number` in the docstring, but the INSERT columns used are `slide_index, title, image_uri, thumbnail_uri, full_text` — [`app/tasks/slide_extract.py:97-99`](../../app/tasks/slide_extract.py#L97).)

### `bullets` ([`migrations/016_bullets.sql:9-16`](../../migrations/016_bullets.sql#L9))
`id`, `slide_id` (FK→slides, CASCADE), `text`, `position`, `created_at`. UNIQUE `(slide_id, position)`.

### `slide_time_ranges` ([`migrations/013_fusion.sql:6-20`](../../migrations/013_fusion.sql#L6))
`id`, `session_id`, `slide_id` (nullable FK→slides), `start_time`, `end_time`, `slide_soft_start`, `slide_soft_end`, `confidence` (CHECK 0..1), `sources` jsonb (`{visual,anchor,semantic}`), `status`, `attempt_number`, `created_at`.

### `alignments` ([`migrations/014_align.sql:6-25`](../../migrations/014_align.sql#L6))
`id`, `session_id`, `segment_id` (FK→segments, CASCADE), `slide_id` (nullable FK→slides), `confidence` (CHECK 0..1), `signals` jsonb (`{semantic,coverage,temporal,sequential}`), `sources` jsonb, `drift_flag`, `anchor_hit`, `uncertain_flag`, `status` (CHECK `assigned|uncertain|review`), `attempt_number`, `created_at`. UNIQUE `(session_id, segment_id)`. Partial index on uncertain rows.

### `validation_results` ([`migrations/014_align.sql:27-33`](../../migrations/014_align.sql#L27))
`id`, `alignment_id` (FK→alignments, CASCADE), `verdict` (CHECK `APPROVE|REVIEW|ESCALATE`), `details` jsonb, `created_at`. (Align only writes APPROVE/REVIEW — ESCALATE is removed because gate failure now halts the session: [`app/tasks/align.py:297-305`](../../app/tasks/align.py#L297).)

### `words` ([`migrations/015_words.sql:10-19`](../../migrations/015_words.sql#L10))
`id`, `segment_id` (FK→segments, CASCADE), `seq`, `word`, `start_ms`, `end_ms`, `confidence` (default 0.85, CHECK 0..1). UNIQUE `(segment_id, seq)`.

### `word_alignment` ([`migrations/036_word_alignment.sql:23-32`](../../migrations/036_word_alignment.sql#L23))
`segment_id` (FK→segments, CASCADE), `gemini_idx` (0-based index into `seg.text.split()`), `stt_word_id` (nullable FK→words, SET NULL), `stt_start_ms`, `stt_end_ms`, `match_kind` (`'exact' | 'unmatched'` in practice; migration comment also lists `'fuzzy'` which is never emitted), `created_at`. PK `(segment_id, gemini_idx)`.

### `replay_log` ([`migrations/013_fusion.sql:23-31`](../../migrations/013_fusion.sql#L23))
Append-only fusion record: `id`, `session_id`, `input_hash`, `fusion_inputs` jsonb, `fusion_output` jsonb, `created_at`.

## Events

### WebSocket (publish-only, consumed by Processing view)
- `slide_progress` — per page during PDF extraction: `{slide, total}` ([`app/tasks/slide_extract.py:268-272`](../../app/tasks/slide_extract.py#L268)).
- `metrics_update` — final `{slides_total, bullets}` after extraction ([`app/tasks/slide_extract.py:210-218`](../../app/tasks/slide_extract.py#L210)).
- `align_gate_failed` — `{gate, reason}` when an align gate halts the session ([`app/tasks/align.py:385-390`](../../app/tasks/align.py#L385)).

All published via `publish_ws_event_sync` ([`app/engines/ws_bridge.py`](../../app/engines/ws_bridge.py)).

### Redis hand-off keys (24h TTL)
- `rounds:frame:{id}` / `rounds:frame:done:{id}` — VisualSignal list + done guard ([`app/tasks/frame_task.py:39-41`](../../app/tasks/frame_task.py#L39)).
- `rounds:anchor:{id}`, `rounds:semantic:{id}`, `rounds:anchor:done:{id}` — AnchorHit + SemanticShift lists + done guard ([`app/tasks/anchor_task.py:27-30`](../../app/tasks/anchor_task.py#L27)).

### Component events
`VideoStrip` emits `togglePlay`, `update:rate`, `update:cc`, `update:time`, `update:playing`, `update:total`, `scrubClick`, `seekTo` ([`VideoStrip.vue:55-64`](../../frontend/src/components/editor/VideoStrip.vue#L55)). `SlideRail` emits `modeChange`, `slideClick`, `clearFocus`.

## State Management

- **Playback state lives in the media element**, mirrored to props via `update:*` emits; `EditorView` owns `time`, `playing`, `rate`, `mediaUrl`, `mediaKind` ([`VideoStrip.vue:14-19`](../../frontend/src/components/editor/VideoStrip.vue#L14), [`EditorView.vue:348, 383-389`](../../frontend/src/views/EditorView.vue#L348)).
- **Active slide is derived, not stored** — `activeSlide` is `SLIDES.find(sl => sl.id === activeSegment.slide_id)` ([`EditorView.vue:596`](../../frontend/src/views/EditorView.vue#L596)).
- **Pipeline state is passed through Redis** (frame/anchor/semantic signals) and persisted to Postgres (`slide_time_ranges`, `alignments`); each task has an idempotency skip-if-exists guard ([`app/tasks/fusion.py:44-51`](../../app/tasks/fusion.py#L44), [`app/tasks/align.py:53-59`](../../app/tasks/align.py#L53), [`app/tasks/slide_extract.py:156-178`](../../app/tasks/slide_extract.py#L156)).
- **`segments.slide_id` is the denormalized join** the Editor reads, written by `align_task` ([`app/tasks/align.py:281-295`](../../app/tasks/align.py#L281)).

## Validation

- Re-extract page indices out of range are skipped ([`app/tasks/slide_extract.py:81-84`](../../app/tasks/slide_extract.py#L81)).
- Captions burn validates a `role='video'` source exists (400 otherwise) ([`app/api/session_resources.py:103-117`](../../app/api/session_resources.py#L103)).
- DB CHECK constraints enforce confidence ∈ [0,1], alignment status enum, validation verdict enum ([`migrations/014_align.sql:11,17,30`](../../migrations/014_align.sql#L11)).
- `align_segment` clamps confidence to [0,1] and gates uncertain (dominance < 0.6) before assigning a slide ([`app/engines/alignment.py:170-197`](../../app/engines/alignment.py#L170)).
- Anchor cross-validation requires phrase + (visual within window OR semantic > threshold) ([`app/engines/anchor.py:84-101`](../../app/engines/anchor.py#L84)).

## Security

- All module HTTP endpoints depend on `CurrentUser` (JWT bearer) and run no additional authorization ([`app/api/session_resources.py:18`](../../app/api/session_resources.py#L18), [`app/api/word_alignment.py:28`](../../app/api/word_alignment.py#L28)).
- Media access is via short-lived GCS signed v4 URLs (24h playback, 1h captioned-video) generated server-side from `gcs_uri`; clients never see GCS credentials ([`app/api/session_resources.py:419-445, 159-164`](../../app/api/session_resources.py#L419)).
- Captions `<track>` uses a Blob URL from an authenticated fetch so the JWT is never placed in a query string ([`VideoStrip.vue:69-83`](../../frontend/src/components/editor/VideoStrip.vue#L69)).
- Thumbnail uploads stay inside the session scope `sessions/{id}/slides/` ([`app/tasks/slide_extract.py:90-92`](../../app/tasks/slide_extract.py#L90)). (The R7 out-of-scope GCS guard lives in upload-complete, outside this module — CLAUDE.md.)

## Permissions

Role-based authorization (`app/security/roles.py`, `auth_users.role`) is scaffold-only project-wide and is **not** wired into any slides/video-sync endpoint. None of these endpoints apply the `johndean@vin.com` legacy-admin gate. Real authorization here is solely JWT presence. There is no `adminOnly` client guard on the Editor route for this module. **NOT VERIFIED IN CODE:** any role-tiered access to slides, sources, or media.

## Integrations

- **Google Cloud Storage** — thumbnail upload + signed playback URLs ([`app/tasks/slide_extract.py:72-92`](../../app/tasks/slide_extract.py#L72), [`app/api/session_resources.py:419-445`](../../app/api/session_resources.py#L419)).
- **FFmpeg / ffprobe** — frame extraction at `FRAME_SAMPLE_FPS`, duration + video-stream probing ([`app/tasks/frame_task.py:176-211`](../../app/tasks/frame_task.py#L176)).
- **OpenCV (`cv2`) + NumPy** — grayscale diff + histogram Bhattacharyya distance ([`app/tasks/frame_task.py:214-263`](../../app/tasks/frame_task.py#L214)).
- **PyMuPDF (`fitz`)** — PDF page text + pixmap rendering ([`app/tasks/slide_extract.py:243, 264-279`](../../app/tasks/slide_extract.py#L243)).
- **python-pptx** — PPTX shape/paragraph extraction ([`app/tasks/slide_extract.py:358-389`](../../app/tasks/slide_extract.py#L358)).
- **Redis** — inter-task signal hand-off ([`app/tasks/frame_task.py:266-287`](../../app/tasks/frame_task.py#L266)).

## Background Jobs

| Task | Celery name | Retries | Triggers next | Source |
|---|---|---|---|---|
| `slide_extract_task` | `rounds.tasks.slide_extract` | 2 | none (emits WS metrics) | [slide_extract.py:141-236](../../app/tasks/slide_extract.py#L141) |
| `slide_extract_selected_pages_task` | `rounds.tasks.slide_extract.selected_pages` | 2 | none | [slide_extract.py:31-138](../../app/tasks/slide_extract.py#L31) |
| `frame_task` | `rounds.tasks.frame` | 3 | none (read later by transcribe) | [frame_task.py:53-159](../../app/tasks/frame_task.py#L53) |
| `anchor_task` | `rounds.tasks.anchor` | 3 | `normalize_task` | [anchor_task.py:33-137](../../app/tasks/anchor_task.py#L33) |
| `fusion_task` | `rounds.tasks.fusion` | 3 | `align_task` | [fusion.py:17-239](../../app/tasks/fusion.py#L17) |
| `align_task` | `rounds.tasks.align` | 2 | `finalize_task` (unless halted) | [align.py:395-431](../../app/tasks/align.py#L395) |

All extend `RoundsTask` with `retry_with_backoff` (base 60s, jitter) ([`app/config.py:74-76`](../../app/config.py#L74)). Idempotency guards skip re-runs when output rows already exist. `align_task` does NOT advance state or fire finalize when a gate halts the session ([`app/tasks/align.py:407-413`](../../app/tasks/align.py#L407)).

## Error Handling

- **Tasks** retry-with-backoff up to their `max_retries`, then re-raise (frame/anchor/fusion) or return a soft error dict (`slide_extract`) ([`app/tasks/slide_extract.py:229-234`](../../app/tasks/slide_extract.py#L229), [`app/tasks/frame_task.py:149-153`](../../app/tasks/frame_task.py#L149)).
- **Align gates** (`fusion_output`, pre-ready) halt the session to `failed`, write `audit_events`, and emit `align_gate_failed`; the time-proportional fallback was removed ([`app/tasks/align.py:91-110, 225-242, 348-392`](../../app/tasks/align.py#L91)).
- **API endpoints** raise `HTTPException` 404 (no media / not found) and 400 (no video for captions); the re-extract enqueue is wrapped to return `{enqueued:false,error}` ([`app/api/session_resources.py:54-55, 113-117, 435-437`](../../app/api/session_resources.py#L54)).
- **Signed-URL generation failures** for captioned-video are swallowed (download_url stays null) ([`app/api/session_resources.py:161-166`](../../app/api/session_resources.py#L161)).
- **Editor** treats media-fetch and captions-fetch failures as non-fatal (poster/scrubber static, CC cosmetic) ([`EditorView.vue:389`](../../frontend/src/views/EditorView.vue#L389), [`VideoStrip.vue:78-82`](../../frontend/src/components/editor/VideoStrip.vue#L78)).

## Performance Considerations

- **`timeupdate` throttled to ~10 Hz** to keep the per-word highlight watcher from thrashing on large sessions ([`VideoStrip.vue:148-203`](../../frontend/src/components/editor/VideoStrip.vue#L148)).
- **Scrubber drag throttled via rAF** to repaint at most once per frame ([`VideoStrip.vue:102-146`](../../frontend/src/components/editor/VideoStrip.vue#L102)).
- **`SlideRail` memoizes per-slide style snapshots** so active/focused clicks don't reallocate the slide objects ([`SlideRail.vue:46-89`](../../frontend/src/components/editor/SlideRail.vue#L46)).
- **Word-alignment payload is deliberately compact** — short field names (`g/s/e/k`), ~16 bytes/entry, ~12k entries/hour-long lecture; timestamps are denormalized into `word_alignment` for O(1) frontend lookup ([`app/api/word_alignment.py:37-44`](../../app/api/word_alignment.py#L37), [`migrations/036_word_alignment.sql:28`](../../migrations/036_word_alignment.sql#L28)).
- **Frame sampling bounded** — sessions over `MAX_VIDEO_DURATION_MINUTES` (180) are rejected before frame extraction ([`app/tasks/frame_task.py:116-121`](../../app/tasks/frame_task.py#L116)).
- **Thumbnail storage budget** ~600 KB/session for word_alignment is documented as negligible ([`migrations/036_word_alignment.sql:18-20`](../../migrations/036_word_alignment.sql#L18)).
- **Tasks use sync engines** (`create_engine` on `+asyncpg`-stripped URL) with `engine.dispose()` in `finally` to avoid leaking pool connections from the Celery worker ([`app/tasks/align.py:48-51, 344-345`](../../app/tasks/align.py#L48)).

## Source Verification
- **Files Used:** app/api/session_resources.py, app/api/word_alignment.py, app/tasks/slide_extract.py, app/tasks/frame_task.py, app/tasks/anchor_task.py, app/tasks/fusion.py, app/tasks/align.py, app/tasks/lcs_discrepancies.py, app/engines/anchor.py, app/engines/alignment.py, app/engines/diff.py, app/config.py, migrations/001_init.sql, migrations/013_fusion.sql, migrations/014_align.sql, migrations/015_words.sql, migrations/016_bullets.sql, migrations/036_word_alignment.sql, frontend/src/components/editor/VideoStrip.vue, frontend/src/components/editor/SlideRail.vue, frontend/src/components/editor/ActiveSlideCard.vue, frontend/src/views/EditorView.vue, frontend/src/services/api.ts
- **Components Used:** VideoStrip.vue, SlideRail.vue, ActiveSlideCard.vue, EditorView.vue
- **APIs Used:** GET/POST endpoints under /v1/sessions/{id}/ for slides, slides/re-extract, sources, media-url, words, word-alignment, captions/burn, captioned-video
- **Database Tables Used:** slides, bullets, slide_time_ranges, alignments, validation_results, words, word_alignment, replay_log, segments, sources, audit_events
- **Permission Logic Used:** JWT presence via CurrentUser only — no role/email gate
- **Confidence Score:** High — every architectural claim, weight, and field traced to current source.
- **Evidence Links:** [app/engines/alignment.py:120-197](../../app/engines/alignment.py#L120), [app/tasks/fusion.py:134-212](../../app/tasks/fusion.py#L134), [app/tasks/frame_task.py:214-263](../../app/tasks/frame_task.py#L214), [app/api/word_alignment.py:54-101](../../app/api/word_alignment.py#L54), [VideoStrip.vue:148-241](../../frontend/src/components/editor/VideoStrip.vue#L148)
