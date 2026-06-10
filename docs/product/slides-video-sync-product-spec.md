# Slides & Video Synchronization — Product Spec

> Module key: `slides-video-sync`. Scope: how rounds.vin extracts slides from an uploaded deck, detects slide changes in the recording, aligns each transcript segment to the slide that was showing, and surfaces all of that in the Editor as a synchronized video player + slide rail + active-slide panel.

## Overview

The Slides & Video Synchronization module covers two things:

1. **Slide extraction** — turning an uploaded PDF or PPTX deck into per-slide rows (title, full text, bullets, thumbnail image) in the `slides` / `bullets` tables. See [`app/tasks/slide_extract.py`](../../app/tasks/slide_extract.py).
2. **Slide↔transcript alignment + synchronized playback** — a processing pipeline (visual frame diffing → anchor detection → fusion → 4-signal alignment) that assigns every transcript segment a `slide_id`, plus the Editor UI that plays the recording and keeps the slide rail and active-slide panel in step with playback time.

The alignment pipeline runs entirely in Celery during ingest. The Editor reads the results read-only: it fetches segments (each carrying a `slide_id`), slides, a signed media URL, and per-word STT timing, then derives which slide is active from the segment under the current playhead.

## Purpose

Operators reviewing an AI-produced transcript need to see, at any moment in the recording, which slide was on screen and which transcript text corresponds to it. The module exists to:

- Produce a first-pass mapping of transcript segments to slides automatically, so an editor does not have to scrub the whole recording to find slide boundaries.
- Give the editor a video/audio player with click-to-seek and slide chapter marks so they can jump directly to a slide's segments.
- Highlight the active slide and (where word-alignment data exists) the active word as playback advances.

## User Value

- **Visual verification.** With a video source, the operator can watch the recording and confirm the slide the alignment claims is active matches the slide actually on the presenter's screen ([`VideoStrip.vue`](../../frontend/src/components/editor/VideoStrip.vue) header comment, lines 8-12).
- **Fast navigation.** The slide rail lists every slide with its segment count; chapter marks on the scrubber jump to a slide's first segment ([`VideoStrip.vue:374-384`](../../frontend/src/components/editor/VideoStrip.vue#L374)).
- **Word-level highlighting.** When `word_alignment` rows exist, highlighting is anchored to real STT timing rather than proportional interpolation ([`app/api/word_alignment.py:1-18`](../../app/api/word_alignment.py#L1)).
- **Resilience to missing data.** Audio-only sessions, decks-only sessions, and sessions ingested before alignment landed all degrade to a usable state rather than crashing (see States).

## Navigation

The module has no standalone route. It is rendered inside the Editor view ([`frontend/src/views/EditorView.vue`](../../frontend/src/views/EditorView.vue)), which mounts:

- `VideoStrip` — the video/audio player + scrubber (left pane), bound at [`EditorView.vue:1305-1314`](../../frontend/src/views/EditorView.vue#L1305).
- `SlideRail` — the slide list with Focus/Filter toggle, bound at [`EditorView.vue:1325-1329`](../../frontend/src/views/EditorView.vue#L1325).
- `ActiveSlideCard` — the right-rail "Active Slide" panel with preview + minimap, bound at [`EditorView.vue:1418-1443`](../../frontend/src/views/EditorView.vue#L1418).

There is no menu entry, breadcrumb, or deep link specific to slides/video sync beyond opening a session in the Editor. **NOT VERIFIED IN CODE:** any dedicated navigation affordance.

## Screens

### Video player (`VideoStrip`)

A 16:9 frame ([`VideoStrip.vue:251-319`](../../frontend/src/components/editor/VideoStrip.vue#L251)) that mounts:

- A visible `<video>` element when the backend returns a `role='video'` source ([`VideoStrip.vue:259-283`](../../frontend/src/components/editor/VideoStrip.vue#L259)).
- A hidden `<audio>` element when only an audio source exists ([`VideoStrip.vue:285-296`](../../frontend/src/components/editor/VideoStrip.vue#L285)).
- A poster (slide title/number/meta) when there is no media, or when media is audio-only ([`VideoStrip.vue:298-306`](../../frontend/src/components/editor/VideoStrip.vue#L298)).

Controls below the frame ([`VideoStrip.vue:320-388`](../../frontend/src/components/editor/VideoStrip.vue#L320)):

- Back-10s / play-pause / forward-10s buttons (`data-test-id="vstrip-seek-back-10"`, `vstrip-seek-forward-10`).
- A playback-rate `<select>` with options 0.75×, 1×, 1.25×, 1.5×, 2× ([`VideoStrip.vue:343-353`](../../frontend/src/components/editor/VideoStrip.vue#L343)).
- A `CC` captions toggle ([`VideoStrip.vue:354-358`](../../frontend/src/components/editor/VideoStrip.vue#L354)).
- A scrubber with a track, slide chapter marks, and a playhead ([`VideoStrip.vue:359-386`](../../frontend/src/components/editor/VideoStrip.vue#L359)).

### Slide rail (`SlideRail`)

A vertical list of slide cards ([`SlideRail.vue:109-153`](../../frontend/src/components/editor/SlideRail.vue#L109)). Header shows `Slides · {count}` and a Focus/Filter radio toggle ([`SlideRail.vue:111-135`](../../frontend/src/components/editor/SlideRail.vue#L111)). Each card shows a colored thumbnail with the 2-digit slide number, a trimmed title, and the count of segments assigned to that slide ([`SlideRail.vue:144-148`](../../frontend/src/components/editor/SlideRail.vue#L144)). Empty slides (no segments) render dimmed (`is-empty`, opacity 0.55, [`SlideRail.vue:57-58`](../../frontend/src/components/editor/SlideRail.vue#L57)).

### Active-slide panel (`ActiveSlideCard`)

A collapsible right-rail card ([`ActiveSlideCard.vue:71-116`](../../frontend/src/components/editor/ActiveSlideCard.vue#L71)) showing the active slide's preview, "Slide NN of M", its `kind`, its segment count, and a timeline minimap that draws one rect per slide that has segments, highlighting the current slide and a playhead marker ([`ActiveSlideCard.vue:41-62`](../../frontend/src/components/editor/ActiveSlideCard.vue#L41)). It also has a "Re-assign segments to slide" button — see Known Constraints.

## User Flows

### Watch + verify alignment
1. Operator opens a session in the Editor.
2. `EditorView` fetches the media URL (requesting `?role=video`, falling through to audio) ([`EditorView.vue:383-389`](../../frontend/src/views/EditorView.vue#L383)) and sets `mediaKind` from the content type ([`EditorView.vue:386`](../../frontend/src/views/EditorView.vue#L386)).
3. `VideoStrip` mounts the appropriate media element and plays. On `timeupdate` (throttled to ~10 Hz) it emits `update:time` ([`VideoStrip.vue:186-203`](../../frontend/src/components/editor/VideoStrip.vue#L186)).
4. `EditorView` derives `activeSegment` from the playhead and `activeSlide` from `activeSegment.slide_id` ([`EditorView.vue:596`](../../frontend/src/views/EditorView.vue#L596)).
5. The slide rail marks that slide active; `ActiveSlideCard` shows its preview.

### Click-to-seek via chapter mark
1. Each slide that has segments gets a chapter mark on the scrubber at the position of its first segment's start time ([`VideoStrip.vue:170-179`](../../frontend/src/components/editor/VideoStrip.vue#L170)).
2. Clicking a mark emits `seekTo` with that segment's start, jumping playback ([`VideoStrip.vue:382`](../../frontend/src/components/editor/VideoStrip.vue#L382)).

### Scrubber drag-to-seek
Pointer-based drag on the scrubber computes a fractional position and emits `update:time`, throttled with `requestAnimationFrame` ([`VideoStrip.vue:124-146`](../../frontend/src/components/editor/VideoStrip.vue#L124)).

### Slide extraction (automatic, during ingest)
`slide_extract_task` reads `sources` rows with `role='slide'`, processes PDF pages via PyMuPDF or PPTX slides via python-pptx, and writes `slides` + `bullets` rows with a rendered thumbnail (PDF only) ([`app/tasks/slide_extract.py:147-236`](../../app/tasks/slide_extract.py#L147)).

### Operator-triggered page re-extract (backend only)
`POST /v1/sessions/{id}/slides/re-extract` with a 1-based `page_indices` array enqueues `slide_extract_selected_pages_task`, which re-renders those PDF pages and rewrites their slide + bullet rows ([`app/api/session_resources.py:39-55`](../../app/api/session_resources.py#L39), [`app/tasks/slide_extract.py:37-138`](../../app/tasks/slide_extract.py#L37)). **No frontend caller exists** (verified by grep of `frontend/src`); this is a backend/operator endpoint.

## Business Rules

- **Anchor confirmation (locked, CLAUDE.md §7).** A slide anchor is CONFIRMED only when an ANCHORS phrase appears in a segment AND a visual change is within ±`ANCHOR_CROSS_VALIDATE_WINDOW` OR a semantic shift > 0.3 nearby; otherwise it is speculative and not used as a boundary signal ([`app/engines/anchor.py:1-9, 56-105`](../../app/engines/anchor.py#L56)). The ANCHORS phrase list is fixed (12 phrases, [`app/engines/anchor.py:23-36`](../../app/engines/anchor.py#L23)).
- **4-signal alignment weights (locked, audit §6).** Each segment is scored against every slide time-range using semantic 0.35, coverage 0.25, temporal 0.25, sequential 0.15, with a 0.8 backward-jump penalty ([`app/engines/alignment.py:5-11`](../../app/engines/alignment.py#L5), [`app/config.py:63-67`](../../app/config.py#L63)).
- **Sequential constraint.** Forward or same-slide moves score 1.0; only backward jumps are penalized ([`app/engines/alignment.py:108-117`](../../app/engines/alignment.py#L108)).
- **Dominance gate.** A segment is `uncertain` (and gets no `slide_id`) when the absolute score gap between the top slide and the runner-up is < 0.6 ([`app/engines/alignment.py:170-186`](../../app/engines/alignment.py#L170)).
- **Drift flag.** Set when the winning score < 0.6 but the assignment is still confident (not uncertain); confidence is then reduced by `IIL_DRIFT_CONFIDENCE_PENALTY` (0.3) ([`app/engines/alignment.py:174-179`](../../app/engines/alignment.py#L174), [`app/config.py:69`](../../app/config.py#L69)).
- **Visual change detection (locked, audit §6).** A candidate boundary requires the mean grayscale pixel diff to exceed `VISUAL_CHANGE_THRESHOLD` (8.0) on three consecutive frames, then a histogram Bhattacharyya distance > 0.05 to confirm ([`app/tasks/frame_task.py:6-19, 240-255`](../../app/tasks/frame_task.py#L240), [`app/config.py:52-53`](../../app/config.py#L52)). Frames are sampled at `FRAME_SAMPLE_FPS` (2) ([`app/config.py:52`](../../app/config.py#L52)).
- **One slide source per session for re-extract.** `slide_extract_selected_pages_task` uses the first `role='slide'` source ordered by `created_at` ([`app/tasks/slide_extract.py:59-70`](../../app/tasks/slide_extract.py#L59)).
- **Title heuristic.** A slide's title is the first non-empty line of its text (PDF) or the title-named shape / first paragraph (PPTX), truncated to 200 chars ([`app/tasks/slide_extract.py:328-334, 385-389`](../../app/tasks/slide_extract.py#L328)).
- **Word-alignment invariant.** The `g` (gemini_idx) field is the 0-based index into `seg.text.split()` with no trim/normalize; the frontend must split identically ([`app/api/word_alignment.py:60-67`](../../app/api/word_alignment.py#L60)).

## Validation Rules

- **Re-extract payload.** `page_indices` is a list of ints; out-of-range pages (idx < 0 or ≥ page count) are silently skipped ([`app/tasks/slide_extract.py:36, 81-84`](../../app/tasks/slide_extract.py#L81)).
- **Captions burn requires video.** `POST /captions/burn` returns 400 if the session has no `role='video'` source ([`app/api/session_resources.py:103-117`](../../app/api/session_resources.py#L103)).
- **Media URL role fallback.** `GET /media-url` accepts `role` of `audio` (default) or `video`, ordering audio/video sources so the preferred role is first; 404 if neither exists ([`app/api/session_resources.py:406-446`](../../app/api/session_resources.py#L406)).
- **Confidence bounds.** `alignments.confidence` and `slide_time_ranges.confidence` are CHECK-constrained to [0.0, 1.0] ([`migrations/014_align.sql:11`](../../migrations/014_align.sql#L11), [`migrations/013_fusion.sql:14`](../../migrations/013_fusion.sql#L14)).
- **Alignment status enum.** `alignments.status` must be `assigned`, `uncertain`, or `review` ([`migrations/014_align.sql:17`](../../migrations/014_align.sql#L17)).

## States

- **No slide source.** `slide_extract_task` returns `{slide_count: 0}` and no slides are written ([`app/tasks/slide_extract.py:173-175`](../../app/tasks/slide_extract.py#L173)).
- **Slides already exist.** Extraction is skipped per session ([`app/tasks/slide_extract.py:176-178`](../../app/tasks/slide_extract.py#L176)).
- **Audio-only recording.** `frame_task` detects no video stream and stores zero visual signals ([`app/tasks/frame_task.py:109-113`](../../app/tasks/frame_task.py#L109)); the Editor plays a hidden `<audio>` element with the poster visible ([`VideoStrip.vue:285-306`](../../frontend/src/components/editor/VideoStrip.vue#L285)).
- **No slides at fusion time.** `fusion_task` writes a single virtual time-range covering the whole session ([`app/tasks/fusion.py:69-91`](../../app/tasks/fusion.py#L69)).
- **Fusion produced no ranges (GATE 1).** `align_task` halts the session to `failed`, writes an `audit_events` row, and emits an `align_gate_failed` WS event rather than falling back to time-proportional bucketing ([`app/tasks/align.py:91-110, 348-392`](../../app/tasks/align.py#L91)).
- **Pre-ready gate failure (GATE 2).** Same halt behavior as GATE 1 ([`app/tasks/align.py:225-242`](../../app/tasks/align.py#L225)).
- **Segment uncertain.** No `slide_id` assigned; shows as unaligned in the rail ([`app/engines/alignment.py:181-186`](../../app/engines/alignment.py#L181)).
- **No word-alignment rows (pre-migration-036 sessions).** The word-alignment endpoint returns empty `segments`; the Editor falls back to legacy whole-text rendering ([`app/api/word_alignment.py:15-18`](../../app/api/word_alignment.py#L15)).
- **No captions.** `VideoStrip` leaves the CC toggle cosmetic (blob URL stays null) ([`VideoStrip.vue:72-83`](../../frontend/src/components/editor/VideoStrip.vue#L72)).

## Dependencies

- **`sources` table** — slide extraction, frame sampling, and media playback all read uploaded files by `role` (`slide`, `video`, `audio`, `audio_enhance`) ([`app/tasks/slide_extract.py:162-171`](../../app/tasks/slide_extract.py#L162), [`app/tasks/frame_task.py:83-98`](../../app/tasks/frame_task.py#L83)).
- **`segments` table** — alignment, word-alignment, and active-slide derivation all depend on transcribed segments existing first ([`app/tasks/anchor_task.py:76-79`](../../app/tasks/anchor_task.py#L76)).
- **Upstream pipeline order** — frame → anchor → fusion → align. `anchor_task` reads frame signals from Redis; `fusion_task` reads visual/anchor/semantic from Redis; `align_task` reads `slide_time_ranges` from fusion ([`app/tasks/fusion.py:93-145`](../../app/tasks/fusion.py#L93), [`app/tasks/align.py:71-85`](../../app/tasks/align.py#L71)).
- **Google Cloud Storage** — slide thumbnails are uploaded to `gs://<bucket>/sessions/<id>/slides/`; media playback uses signed v4 GET URLs ([`app/tasks/slide_extract.py:90-92`](../../app/tasks/slide_extract.py#L90), [`app/api/session_resources.py:419-445`](../../app/api/session_resources.py#L419)).
- **FFmpeg / OpenCV / PyMuPDF / python-pptx** — frame sampling uses ffmpeg+cv2; PDF extraction uses PyMuPDF (`fitz`); PPTX uses python-pptx ([`app/tasks/frame_task.py:202-211`](../../app/tasks/frame_task.py#L202), [`app/tasks/slide_extract.py:243, 359`](../../app/tasks/slide_extract.py#L243)).
- **Redis** — visual signals, anchor hits, and semantic shifts are passed between tasks via Redis keys with a 24h TTL ([`app/tasks/frame_task.py:39-41`](../../app/tasks/frame_task.py#L39), [`app/tasks/anchor_task.py:27-30`](../../app/tasks/anchor_task.py#L27)).

## Error Handling

- **Slide extraction** retries up to `max_retries=2` with backoff; terminal failure returns `{slide_count: 0, error}` without failing the session ([`app/tasks/slide_extract.py:229-234`](../../app/tasks/slide_extract.py#L229)).
- **Re-extract endpoint** wraps enqueue in try/except and returns `{enqueued: false, error}` instead of raising ([`app/api/session_resources.py:54-55`](../../app/api/session_resources.py#L54)).
- **Frame task** retries up to 3 times, then re-raises; raises immediately if no media source or video too long (> `MAX_VIDEO_DURATION_MINUTES`, 180) ([`app/tasks/frame_task.py:99-121, 149-153`](../../app/tasks/frame_task.py#L116)).
- **Anchor/fusion tasks** retry up to 3 times; raise if no segments / no duration ([`app/tasks/anchor_task.py:76-79, 128-132`](../../app/tasks/anchor_task.py#L76), [`app/tasks/fusion.py:58-59, 233-237`](../../app/tasks/fusion.py#L58)).
- **Align gates** halt to `failed` with audit + WS diagnostic rather than retrying ([`app/tasks/align.py:348-392`](../../app/tasks/align.py#L348)).
- **Captions burn failure is non-fatal** — does not mark the session failed; original transcript remains canonical ([`app/api/session_resources.py:96-101`](../../app/api/session_resources.py#L96)).
- **Editor media fetch failure is non-fatal** — `mediaUrl`/`mediaKind` reset to null, poster + scrubber stay static ([`EditorView.vue:380-389`](../../frontend/src/views/EditorView.vue#L380)).

## Permissions

All slides/video-sync HTTP endpoints require a logged-in user via the `CurrentUser` dependency (JWT presence) and apply **no** role check, no owner check, and no `johndean@vin.com` email gate. Verified across `list_slides`, `re_extract_slides`, `list_sources`, `session_media_url`, `list_words`, and `get_word_alignment` ([`app/api/session_resources.py:39-59, 381-462`](../../app/api/session_resources.py#L39), [`app/api/word_alignment.py:54-59`](../../app/api/word_alignment.py#L54)).

Role-based authorization is scaffold-only project-wide and is not wired into these endpoints. There is no client-side `adminOnly` route guard on the Editor route for this module. **NOT VERIFIED IN CODE:** any per-slide or per-source access restriction.

## Reporting Impacts

- **No dedicated reporting/analytics surface for this module.** IMPLEMENTATION NOT FOUND for slide-sync dashboards or metrics rollups.
- The processing pipeline emits WebSocket telemetry consumed by the Processing view: `slide_progress` per page during extraction ([`app/tasks/slide_extract.py:268-272`](../../app/tasks/slide_extract.py#L268)) and a final `metrics_update` with `slides_total` + `bullets` counts ([`app/tasks/slide_extract.py:208-218`](../../app/tasks/slide_extract.py#L208)). These are live progress signals, not stored reports.
- Alignment writes per-segment `validation_results` rows (verdict APPROVE/REVIEW) ([`app/tasks/align.py:297-328`](../../app/tasks/align.py#L297)), which feed the review workflow rather than a slides report.

## Audit Requirements

- **Chat/poll reorder** within the editor writes `audit_events` rows (`chat.reorder`, `polls.reorder`) with the actor email ([`app/api/session_resources.py:578-589, 779-790`](../../app/api/session_resources.py#L578)). These are adjacent editor actions, not slide-alignment events.
- **Align gate failures** write an `audit_events` row (`align.gate_failure`) with the gate id + reason; the actor is NULL (system) ([`app/tasks/align.py:362-374`](../../app/tasks/align.py#L362)).
- Slide extraction, re-extraction, and media-URL issuance do **not** write audit rows. **NOT VERIFIED IN CODE:** any audit trail for slide thumbnail generation or signed-URL issuance.
- Fusion writes an append-only `replay_log` row (input hash + inputs + outputs) for replayability ([`app/tasks/fusion.py:198-212`](../../app/tasks/fusion.py#L198), [`migrations/013_fusion.sql:23-31`](../../migrations/013_fusion.sql#L23)).

## Data Relationships

- `sessions` 1—N `slides` (`slides.session_id`, UNIQUE on `(session_id, slide_index)`) ([`migrations/001_init.sql:54-64`](../../migrations/001_init.sql#L54)).
- `slides` 1—N `bullets` (`bullets.slide_id`, UNIQUE on `(slide_id, position)`) ([`migrations/016_bullets.sql:9-16`](../../migrations/016_bullets.sql#L9)).
- `sessions` 1—N `slide_time_ranges`; each range optionally references one `slides` row ([`migrations/013_fusion.sql:6-20`](../../migrations/013_fusion.sql#L6)).
- `segments` 1—1 `alignments` (UNIQUE on `(session_id, segment_id)`), `alignments.slide_id` → `slides` ([`migrations/014_align.sql:6-21`](../../migrations/014_align.sql#L6)).
- `alignments` 1—N `validation_results` ([`migrations/014_align.sql:27-33`](../../migrations/014_align.sql#L27)).
- `segments.slide_id` is updated directly by `align_task` so the Editor can group segments by slide without joining `alignments` ([`app/tasks/align.py:281-295`](../../app/tasks/align.py#L281)).
- `segments` 1—N `words`; `words` 1—N `word_alignment` (per Gemini token, `word_alignment.stt_word_id` → `words`) ([`migrations/015_words.sql:10-19`](../../migrations/015_words.sql#L10), [`migrations/036_word_alignment.sql:23-32`](../../migrations/036_word_alignment.sql#L23)).

## Known Constraints

- **"Re-assign segments to slide" button is a no-op.** It toasts "Bulk slide reassign ships with Phase 4 corrections audit." and performs no reassignment ([`ActiveSlideCard.vue:64-68, 111-113`](../../frontend/src/components/editor/ActiveSlideCard.vue#L64)). PARTIALLY IMPLEMENTED.
- **Re-extract has no UI.** `POST /slides/re-extract` is a backend-only operator endpoint with no frontend caller.
- **PPTX slides have no thumbnail.** `_process_pptx` writes `title` + `full_text` only; no `image_uri`/`thumbnail_uri` ([`app/tasks/slide_extract.py:392-413`](../../app/tasks/slide_extract.py#L392)). The Editor renders a generated gradient placeholder rather than a real slide image ([`SlideRail.vue:95-100`](../../frontend/src/components/editor/SlideRail.vue#L95)).
- **`match_kind='fuzzy'` is declared but never produced.** Migration 036 lists `'fuzzy'` as a possible value, but the alignment engine only emits `'exact'` and `'unmatched'` ([`migrations/036_word_alignment.sql:29`](../../migrations/036_word_alignment.sql#L29) vs [`app/engines/diff.py:38, 157-167`](../../app/engines/diff.py#L157)).
- **Signed media URLs expire.** Media URLs are 24h ([`app/api/session_resources.py:403, 445`](../../app/api/session_resources.py#L403)); captioned-video URLs are regenerated at 1h on every fetch ([`app/api/session_resources.py:159-164`](../../app/api/session_resources.py#L159)).
- **Captions `<track>` cannot use the legacy proportional fallback for word highlight** — the editor only word-highlights when `word_alignment` data exists; otherwise it falls back to legacy whole-text rendering ([`app/api/word_alignment.py:15-18`](../../app/api/word_alignment.py#L15)).
- **Seed-doc corrections (`docs/product/video-sync.md`):** that seed claims "Playback speed control is fixed at 1×" and "No audio-only playback." Both are false against current code — `VideoStrip` has a 5-option rate selector ([`VideoStrip.vue:343-353`](../../frontend/src/components/editor/VideoStrip.vue#L343)) and an audio fallback element ([`VideoStrip.vue:285-296`](../../frontend/src/components/editor/VideoStrip.vue#L285)) with the Editor explicitly requesting video then falling through to audio ([`EditorView.vue:383-389`](../../frontend/src/views/EditorView.vue#L383)).

## Source Verification
- **Files Used:** app/api/session_resources.py, app/api/word_alignment.py, app/tasks/slide_extract.py, app/tasks/frame_task.py, app/tasks/anchor_task.py, app/tasks/align.py, app/tasks/fusion.py, app/tasks/lcs_discrepancies.py, app/engines/anchor.py, app/engines/alignment.py, app/engines/diff.py, app/config.py, migrations/001_init.sql, migrations/013_fusion.sql, migrations/014_align.sql, migrations/015_words.sql, migrations/016_bullets.sql, migrations/036_word_alignment.sql, frontend/src/components/editor/VideoStrip.vue, frontend/src/components/editor/SlideRail.vue, frontend/src/components/editor/ActiveSlideCard.vue, frontend/src/views/EditorView.vue, frontend/src/services/api.ts, docs/product/video-sync.md
- **Components Used:** VideoStrip.vue, SlideRail.vue, ActiveSlideCard.vue, EditorView.vue
- **APIs Used:** GET /v1/sessions/{id}/slides, POST /v1/sessions/{id}/slides/re-extract, GET /v1/sessions/{id}/sources, GET /v1/sessions/{id}/media-url, GET /v1/sessions/{id}/words, GET /v1/sessions/{id}/word-alignment, POST /v1/sessions/{id}/captions/burn, GET /v1/sessions/{id}/captioned-video
- **Database Tables Used:** slides, bullets, sources, segments, slide_time_ranges, alignments, validation_results, words, word_alignment, replay_log, audit_events
- **Permission Logic Used:** JWT presence via CurrentUser only — no role/owner/email gate on any slides/video-sync endpoint
- **Confidence Score:** High — every claim traced to current source; the only corrections are to the stale seed doc, which I re-verified and flagged.
- **Evidence Links:** [app/engines/alignment.py:120-197](../../app/engines/alignment.py#L120), [app/tasks/align.py:91-110](../../app/tasks/align.py#L91), [app/tasks/frame_task.py:240-255](../../app/tasks/frame_task.py#L240), [VideoStrip.vue:259-306](../../frontend/src/components/editor/VideoStrip.vue#L259), [app/api/session_resources.py:406-446](../../app/api/session_resources.py#L406)
