# Slides & Video Synchronization — Demo Questions

> Every answer below is verified against current code. Claims that could not be proven are marked with the exact uncertainty tags. Module key: `slides-video-sync`.

## User

### Q: When I open a session in the Editor, how does it know which slide was on screen at a given moment?
- **Verified Answer:** It is derived live from the transcript. The Editor finds the segment under the current playhead, then looks up the slide whose id equals that segment's `slide_id`. The slide alignment itself was computed during processing by the 4-signal alignment engine, which stamps each segment's `slide_id`.
- **Supporting Evidence:** `activeSlide = SLIDES.find(sl => sl.id === activeSegment.slide_id)` ([EditorView.vue:596](../../frontend/src/views/EditorView.vue#L596)); `align_task` updates `segments.slide_id` ([align.py:281-295](../../app/tasks/align.py#L281)).
- **Source Files:** frontend/src/views/EditorView.vue, app/tasks/align.py
- **API References:** GET /v1/sessions/{id}/slides, GET /v1/sessions/{id}/segments
- **Database References:** segments.slide_id, slides

### Q: Can I jump straight to where a slide starts in the recording?
- **Verified Answer:** Yes. The scrubber shows a chapter mark for each slide that has segments, positioned at that slide's first segment start time; clicking it seeks playback there.
- **Supporting Evidence:** Chapter marks computed in [VideoStrip.vue:169-179](../../frontend/src/components/editor/VideoStrip.vue#L169); click emits `seekTo` with the segment start ([VideoStrip.vue:374-384](../../frontend/src/components/editor/VideoStrip.vue#L374)).
- **Source Files:** frontend/src/components/editor/VideoStrip.vue
- **API References:** none (client-side seek)
- **Database References:** segments (start time), slides

### Q: What playback speeds can I use?
- **Verified Answer:** 0.75×, 1×, 1.25×, 1.5×, and 2×, via the rate selector under the video frame. (The older `docs/product/video-sync.md` seed says speed is "fixed at 1×" — that is outdated; the selector is implemented.)
- **Supporting Evidence:** Rate `<select>` options at [VideoStrip.vue:343-353](../../frontend/src/components/editor/VideoStrip.vue#L343); rate watcher applies it to the media element ([VideoStrip.vue:238-241](../../frontend/src/components/editor/VideoStrip.vue#L238)).
- **Source Files:** frontend/src/components/editor/VideoStrip.vue
- **API References:** none
- **Database References:** none

### Q: There's no video for my session — can I still play it?
- **Verified Answer:** Yes, if there is an audio source. The Editor requests video first and falls through to audio; for audio-only sessions it mounts a hidden `<audio>` element and shows the slide poster as visual chrome.
- **Supporting Evidence:** [EditorView.vue:383-389](../../frontend/src/views/EditorView.vue#L383); audio fallback + poster [VideoStrip.vue:285-306](../../frontend/src/components/editor/VideoStrip.vue#L285); media-url role fallthrough [session_resources.py:421-446](../../app/api/session_resources.py#L421).
- **Source Files:** frontend/src/views/EditorView.vue, frontend/src/components/editor/VideoStrip.vue, app/api/session_resources.py
- **API References:** GET /v1/sessions/{id}/media-url?role=video
- **Database References:** sources (role)

### Q: Why are some slides in the rail dimmed?
- **Verified Answer:** A slide renders dimmed (`is-empty`, opacity 0.55) when no transcript segments are aligned to it.
- **Supporting Evidence:** `isEmpty = segs.length === 0` and the dimmed style [SlideRail.vue:51-58](../../frontend/src/components/editor/SlideRail.vue#L51); count badge [SlideRail.vue:148](../../frontend/src/components/editor/SlideRail.vue#L148).
- **Source Files:** frontend/src/components/editor/SlideRail.vue
- **API References:** none
- **Database References:** segments.slide_id, slides

### Q: Does the highlighted word follow the audio accurately?
- **Verified Answer:** When `word_alignment` data exists, highlighting is anchored to real STT timestamps per Gemini word. For sessions ingested before that data existed (pre-migration-036), the editor falls back to whole-text rendering with no per-word highlight, but does not crash.
- **Supporting Evidence:** Purpose + fallback documented at [word_alignment.py:1-18](../../app/api/word_alignment.py#L1); per-word entries returned at [word_alignment.py:82-101](../../app/api/word_alignment.py#L82).
- **Source Files:** app/api/word_alignment.py
- **API References:** GET /v1/sessions/{id}/word-alignment
- **Database References:** word_alignment, words, segments

## Executive

### Q: How does the product map a recorded lecture to its slides without an operator doing it manually?
- **Verified Answer:** A four-stage pipeline runs during processing: it samples video frames to detect visual slide changes, scans the transcript for anchor phrases, fuses those into slide time-ranges, then scores every transcript segment against those ranges on four weighted signals to pick the dominant slide.
- **Supporting Evidence:** Pipeline frame→anchor→fusion→align ([frame_task.py](../../app/tasks/frame_task.py), [anchor_task.py](../../app/tasks/anchor_task.py), [fusion.py](../../app/tasks/fusion.py), [align.py:161-181](../../app/tasks/align.py#L161)); 4-signal scorer [alignment.py:120-197](../../app/engines/alignment.py#L120).
- **Source Files:** app/tasks/frame_task.py, app/tasks/anchor_task.py, app/tasks/fusion.py, app/tasks/align.py, app/engines/alignment.py
- **API References:** none (background pipeline)
- **Database References:** slide_time_ranges, alignments, segments

### Q: What happens to a session if the system can't confidently align the slides?
- **Verified Answer:** Rather than silently producing a noisy alignment, the system halts the session to a failed state with a durable diagnostic. If fusion produced zero slide time-ranges, or the pre-ready gate fails, alignment writes an audit record, transitions the session to `failed`, and emits a live failure event for the operator to inspect.
- **Supporting Evidence:** GATE 1 + GATE 2 and `_halt_session` at [align.py:91-110, 225-242, 348-392](../../app/tasks/align.py#L91).
- **Source Files:** app/tasks/align.py
- **API References:** none
- **Database References:** audit_events, sessions (status)

### Q: Is the alignment reproducible / auditable?
- **Verified Answer:** Fusion writes an append-only replay record per session containing an input hash plus the full fusion inputs and outputs, so a given alignment can be traced back to the signals that produced it.
- **Supporting Evidence:** `replay_log` insert [fusion.py:198-212](../../app/tasks/fusion.py#L198); table [013_fusion.sql:23-31](../../migrations/013_fusion.sql#L23).
- **Source Files:** app/tasks/fusion.py, migrations/013_fusion.sql
- **API References:** none
- **Database References:** replay_log

## Operations

### Q: A slide's thumbnail or text came out wrong. How do I re-extract just that slide?
- **Verified Answer:** Call `POST /v1/sessions/{id}/slides/re-extract` with a 1-based `page_indices` array. It enqueues a Celery task that re-renders those PDF pages and rewrites their slide + bullet rows idempotently. There is no UI button for this — it is an operator/curl endpoint.
- **Supporting Evidence:** Endpoint [session_resources.py:39-55](../../app/api/session_resources.py#L39); task [slide_extract.py:37-138](../../app/tasks/slide_extract.py#L37). No frontend caller exists (grep of frontend/src found none).
- **Source Files:** app/api/session_resources.py, app/tasks/slide_extract.py
- **API References:** POST /v1/sessions/{id}/slides/re-extract
- **Database References:** slides, bullets, sources

### Q: How do I get a playable link for a session's media for debugging?
- **Verified Answer:** `GET /v1/sessions/{id}/media-url?role=video` (or `audio`) returns a 24-hour signed GCS GET URL for the primary playback source. It defaults to audio, prefers the requested role, and 404s if neither audio nor video exists.
- **Supporting Evidence:** [session_resources.py:406-446](../../app/api/session_resources.py#L406).
- **Source Files:** app/api/session_resources.py
- **API References:** GET /v1/sessions/{id}/media-url
- **Database References:** sources

### Q: What media does frame detection actually run on, and what if it's audio-only?
- **Verified Answer:** `frame_task` picks the best source (video, then audio, then audio_enhance), downloads it, and probes for a video stream. If there is no video stream, it stores zero visual signals and returns cleanly — audio-only sessions skip visual boundary detection.
- **Supporting Evidence:** Source selection [frame_task.py:83-101](../../app/tasks/frame_task.py#L83); audio-only branch [frame_task.py:109-113](../../app/tasks/frame_task.py#L109).
- **Source Files:** app/tasks/frame_task.py
- **API References:** none
- **Database References:** sources

### Q: A session has no slide deck. Does alignment still work?
- **Verified Answer:** Yes, in a degraded form. If there are no slides at fusion time, fusion writes a single virtual time-range covering the whole session, and alignment proceeds against that one range.
- **Supporting Evidence:** Single virtual range [fusion.py:69-91](../../app/tasks/fusion.py#L69).
- **Source Files:** app/tasks/fusion.py
- **API References:** none
- **Database References:** slide_time_ranges, slides

### Q: Where do slide thumbnails get stored?
- **Verified Answer:** PDF thumbnails are rendered to PNG at 120 DPI and uploaded to `gs://<bucket>/sessions/<session_id>/slides/thumb_NNN.png`, and that gs:// URI is written to both `image_uri` and `thumbnail_uri`. PPTX slides get no thumbnail (text only).
- **Supporting Evidence:** PDF upload [slide_extract.py:277-279](../../app/tasks/slide_extract.py#L277); PPTX has no image columns [slide_extract.py:392-413](../../app/tasks/slide_extract.py#L392).
- **Source Files:** app/tasks/slide_extract.py
- **API References:** none
- **Database References:** slides (image_uri, thumbnail_uri)

## Finance

### Q: Does the slide/video sync pipeline make any paid LLM or external API calls?
- **Verified Answer:** The slide-extraction and alignment engines themselves use no LLM. Frame detection uses FFmpeg + OpenCV; PDF/PPTX extraction uses PyMuPDF/python-pptx; alignment is deterministic arithmetic over local signals. The only paid external dependency in this module is Google Cloud Storage (thumbnail storage + signed URLs). The per-word alignment rows are written by `lcs_discrepancies_task` in the same transaction as discrepancy detection, explicitly "zero new STT/LLM calls."
- **Supporting Evidence:** Engines are local ([alignment.py](../../app/engines/alignment.py), [anchor.py](../../app/engines/anchor.py), [frame_task.py:214-263](../../app/tasks/frame_task.py#L214)); "zero new STT/LLM calls" [036_word_alignment.sql:14-16](../../migrations/036_word_alignment.sql#L14).
- **Source Files:** app/engines/alignment.py, app/engines/anchor.py, app/tasks/frame_task.py, migrations/036_word_alignment.sql
- **API References:** GET /v1/sessions/{id}/media-url (issues GCS signed URLs)
- **Database References:** word_alignment

### Q: What's the storage footprint of the per-word alignment data?
- **Verified Answer:** Roughly 600 KB per session for an hour-long lecture (~50 bytes/word × ~12k words), documented as negligible.
- **Supporting Evidence:** Storage budget note [036_word_alignment.sql:18-20](../../migrations/036_word_alignment.sql#L18).
- **Source Files:** migrations/036_word_alignment.sql
- **API References:** none
- **Database References:** word_alignment

## Compliance

### Q: Who can access a session's slides, sources, and media?
- **Verified Answer:** Any authenticated user. Every slides/video-sync endpoint requires only a valid JWT (the `CurrentUser` dependency) and applies no role check, no owner check, and no per-session restriction. Role-based authorization exists only as un-wired scaffolding project-wide.
- **Supporting Evidence:** `_user: CurrentUser` with no further gate on list_slides/list_sources/media-url/words ([session_resources.py:58-59, 381-382, 406-412, 461-462](../../app/api/session_resources.py#L58)) and word-alignment ([word_alignment.py:54-59](../../app/api/word_alignment.py#L54)).
- **Source Files:** app/api/session_resources.py, app/api/word_alignment.py
- **API References:** GET /v1/sessions/{id}/{slides,sources,media-url,words,word-alignment}
- **Database References:** none

### Q: Is there an audit trail when alignment fails?
- **Verified Answer:** Yes. When an align gate halts a session, the system writes an `audit_events` row of kind `align.gate_failure` with the gate id and reason (actor is NULL/system). Routine slide extraction and media-URL issuance do not write audit rows.
- **Supporting Evidence:** `_halt_session` audit insert [align.py:362-374](../../app/tasks/align.py#L362).
- **Source Files:** app/tasks/align.py
- **API References:** none
- **Database References:** audit_events

### Q: How is media exposed to the browser — are credentials leaked?
- **Verified Answer:** No credentials reach the client. Media is served via short-lived GCS signed v4 URLs generated server-side (24h for playback, 1h regenerated for captioned video). The captions `<track>` even uses an authenticated-fetch Blob URL so the JWT never appears in a query string.
- **Supporting Evidence:** Signed URLs [session_resources.py:419-445, 159-164](../../app/api/session_resources.py#L419); Blob-URL track [VideoStrip.vue:69-83](../../frontend/src/components/editor/VideoStrip.vue#L69).
- **Source Files:** app/api/session_resources.py, frontend/src/components/editor/VideoStrip.vue
- **API References:** GET /v1/sessions/{id}/media-url, GET /v1/sessions/{id}/captioned-video
- **Database References:** sources, artifacts

## Administrator

### Q: Which alignment and visual-detection weights are locked, and where?
- **Verified Answer:** The alignment weights (semantic 0.35, coverage 0.25, temporal 0.25, sequential 0.15, backward penalty 0.8), the drift penalty (0.3), the visual-change threshold (8.0), frame sample rate (2 fps), and the anchor cross-validate window (5.0s) are all defined in `app/config.py` under the LOCKED block and are pinned by a test. Changing them requires a coordinated config + test + plan update.
- **Supporting Evidence:** [config.py:51-69](../../app/config.py#L51); locked-weights invariant note [config.py:9-12](../../app/config.py#L9); histogram threshold 0.05 in code [frame_task.py:42](../../app/tasks/frame_task.py#L42).
- **Source Files:** app/config.py, app/tasks/frame_task.py
- **API References:** none
- **Database References:** none

### Q: What is the exact rule for confirming a slide-change anchor?
- **Verified Answer:** A segment must contain one of 12 fixed ANCHORS phrases (e.g. "next slide", "moving on"). It is confirmed only if a visual change is within ±5s OR a semantic shift > 0.3 is within ±5s; otherwise it is speculative and not used as a boundary signal. Confirmed hits get confidence 0.9, speculative 0.3.
- **Supporting Evidence:** Phrase list [anchor.py:23-36](../../app/engines/anchor.py#L23); confirmation logic [anchor.py:84-101](../../app/engines/anchor.py#L84).
- **Source Files:** app/engines/anchor.py, app/tasks/anchor_task.py
- **API References:** none
- **Database References:** none (signals stored in Redis)

### Q: What does the "Re-assign segments to slide" button in the active-slide panel do?
- **Verified Answer:** Nothing functional yet. It only shows a toast: "Bulk slide reassign ships with Phase 4 corrections audit." There is no slide-reassignment endpoint behind it. (PARTIALLY IMPLEMENTED.)
- **Supporting Evidence:** [ActiveSlideCard.vue:64-68, 111-113](../../frontend/src/components/editor/ActiveSlideCard.vue#L64).
- **Source Files:** frontend/src/components/editor/ActiveSlideCard.vue
- **API References:** none
- **Database References:** none

### Q: What status values can an alignment have, and when is a segment left unassigned?
- **Verified Answer:** `alignments.status` is one of `assigned`, `uncertain`, or `review`. A segment is `uncertain` (and gets no `slide_id`) when the absolute score gap between the best slide and the runner-up is below 0.6; otherwise it is `assigned` (confidence ≥ 0.6) or `review`.
- **Supporting Evidence:** Status enum [014_align.sql:17](../../migrations/014_align.sql#L17); dominance/uncertain logic [alignment.py:170-186](../../app/engines/alignment.py#L170).
- **Source Files:** app/engines/alignment.py, migrations/014_align.sql
- **API References:** none
- **Database References:** alignments (status, uncertain_flag, slide_id)

### Q: How are signals passed between the frame, anchor, fusion, and align tasks?
- **Verified Answer:** Through Redis with a 24-hour TTL plus done-flag guards. `frame_task` writes `rounds:frame:{id}`; `anchor_task` reads those and writes `rounds:anchor:{id}` + `rounds:semantic:{id}`; `fusion_task` reads all three from Redis and persists `slide_time_ranges` to Postgres; `align_task` reads `slide_time_ranges` from the DB.
- **Supporting Evidence:** Redis keys [frame_task.py:39-41](../../app/tasks/frame_task.py#L39), [anchor_task.py:27-30](../../app/tasks/anchor_task.py#L27); fusion loads [fusion.py:93-96](../../app/tasks/fusion.py#L93); align reads slide_time_ranges [align.py:71-85](../../app/tasks/align.py#L71).
- **Source Files:** app/tasks/frame_task.py, app/tasks/anchor_task.py, app/tasks/fusion.py, app/tasks/align.py
- **API References:** none
- **Database References:** slide_time_ranges

## Power User

### Q: How exactly is each transcript segment scored against a slide?
- **Verified Answer:** Four signals, summed by weight: semantic = (segment∩slide tokens)/slide tokens (not Jaccard), coverage = fraction of the segment's duration inside the slide's soft window, temporal = linear 1 − distance/half-window from the slide center, sequential = 1.0 for forward/same slide and 0.8 (penalty) for a backward jump. The highest-scoring slide wins if it beats the runner-up by ≥ 0.6.
- **Supporting Evidence:** Signal functions [alignment.py:69-117](../../app/engines/alignment.py#L69); weighting + winner selection [alignment.py:147-186](../../app/engines/alignment.py#L147).
- **Source Files:** app/engines/alignment.py
- **API References:** none
- **Database References:** alignments (signals jsonb), slide_time_ranges

### Q: What does the `word-alignment` endpoint return, and what's the `g` field?
- **Verified Answer:** It returns `{session_id, count, matched, segments}` where `segments` maps each segment_id to a list of `{g, s, e, k}` entries. `g` is the 0-based index into `seg.text.split()` (the Gemini token position) — the frontend must split identically with no trim/normalize. `s`/`e` are STT start/end ms (null when unmatched), `k` is `'exact'` or `'unmatched'`.
- **Supporting Evidence:** Response model [word_alignment.py:37-101](../../app/api/word_alignment.py#L37); invariant note [word_alignment.py:60-67](../../app/api/word_alignment.py#L60).
- **Source Files:** app/api/word_alignment.py
- **API References:** GET /v1/sessions/{id}/word-alignment
- **Database References:** word_alignment, segments

### Q: The migration mentions a `'fuzzy'` match_kind — does the API ever return it?
- **Verified Answer:** No. Migration 036's comment lists `'exact' | 'fuzzy' | 'unmatched'`, but the LCS pairing engine (`align_words`) only ever emits `'exact'` and `'unmatched'`, and the API's `AlignmentEntry.k` is typed `'exact' | 'unmatched'`. `'fuzzy'` is dead/unreachable in the current code.
- **Supporting Evidence:** Engine emits only exact/unmatched [diff.py:38, 143-167](../../app/engines/diff.py#L143); API field type [word_alignment.py:44](../../app/api/word_alignment.py#L44); migration comment [036_word_alignment.sql:29](../../migrations/036_word_alignment.sql#L29).
- **Source Files:** app/engines/diff.py, app/api/word_alignment.py, migrations/036_word_alignment.sql
- **API References:** GET /v1/sessions/{id}/word-alignment
- **Database References:** word_alignment (match_kind)

### Q: How does the visual slide-change detector avoid false positives from flicker?
- **Verified Answer:** Two filters. First, a 3-frame persistence filter: a candidate boundary at frame i requires the mean grayscale pixel diff to exceed 8.0 at frames i, i+1, and i+2. Second, a histogram check: the Bhattacharyya distance between the previous and current frame's intensity histograms must exceed 0.05 to confirm a real content change.
- **Supporting Evidence:** Persistence filter [frame_task.py:238-242](../../app/tasks/frame_task.py#L238); histogram confirmation [frame_task.py:245-262](../../app/tasks/frame_task.py#L245).
- **Source Files:** app/tasks/frame_task.py
- **API References:** none
- **Database References:** none

### Q: How is the video playhead kept in sync without causing feedback loops?
- **Verified Answer:** The media element is the source of truth. `timeupdate` emits `update:time` (throttled to ~10 Hz). When the parent pushes a new `time` back down, the element only seeks if the difference exceeds 0.4s, and a `seeking` flag suppresses re-emitting during that programmatic seek. Rate changes only apply if they differ by more than 0.001.
- **Supporting Evidence:** Throttle [VideoStrip.vue:186-203](../../frontend/src/components/editor/VideoStrip.vue#L186); seek guard [VideoStrip.vue:219-229](../../frontend/src/components/editor/VideoStrip.vue#L219); rate guard [VideoStrip.vue:238-241](../../frontend/src/components/editor/VideoStrip.vue#L238).
- **Source Files:** frontend/src/components/editor/VideoStrip.vue
- **API References:** none
- **Database References:** none

### Q: Does re-extracting a slide overwrite the operator's edited title?
- **Verified Answer:** For the main `slides` upsert, the title is preserved via `COALESCE(slides.title, EXCLUDED.title)` — an existing non-null title is kept while image/thumbnail/full_text are overwritten. Bullets for that slide are fully wiped and rewritten.
- **Supporting Evidence:** Title COALESCE on conflict [slide_extract.py:102-106](../../app/tasks/slide_extract.py#L102); bullets delete+reinsert [slide_extract.py:113-127](../../app/tasks/slide_extract.py#L113).
- **Source Files:** app/tasks/slide_extract.py
- **API References:** POST /v1/sessions/{id}/slides/re-extract
- **Database References:** slides, bullets

## Source Verification
- **Files Used:** app/api/session_resources.py, app/api/word_alignment.py, app/tasks/slide_extract.py, app/tasks/frame_task.py, app/tasks/anchor_task.py, app/tasks/fusion.py, app/tasks/align.py, app/tasks/lcs_discrepancies.py, app/engines/anchor.py, app/engines/alignment.py, app/engines/diff.py, app/config.py, migrations/013_fusion.sql, migrations/014_align.sql, migrations/015_words.sql, migrations/036_word_alignment.sql, frontend/src/components/editor/VideoStrip.vue, frontend/src/components/editor/SlideRail.vue, frontend/src/components/editor/ActiveSlideCard.vue, frontend/src/views/EditorView.vue, frontend/src/services/api.ts
- **Components Used:** VideoStrip.vue, SlideRail.vue, ActiveSlideCard.vue, EditorView.vue
- **APIs Used:** GET /v1/sessions/{id}/slides, POST /v1/sessions/{id}/slides/re-extract, GET /v1/sessions/{id}/sources, GET /v1/sessions/{id}/media-url, GET /v1/sessions/{id}/words, GET /v1/sessions/{id}/word-alignment, GET /v1/sessions/{id}/captioned-video
- **Database Tables Used:** slides, bullets, sources, segments, slide_time_ranges, alignments, validation_results, words, word_alignment, replay_log, audit_events, artifacts
- **Permission Logic Used:** JWT presence via CurrentUser only — no role/owner/email gate on any module endpoint
- **Confidence Score:** High — every Q/A traced to current source; stale-seed and dead-`fuzzy` discrepancies explicitly flagged.
- **Evidence Links:** [app/engines/alignment.py:69-186](../../app/engines/alignment.py#L69), [app/tasks/frame_task.py:238-262](../../app/tasks/frame_task.py#L238), [app/tasks/align.py:91-110](../../app/tasks/align.py#L91), [app/api/word_alignment.py:37-101](../../app/api/word_alignment.py#L37), [frontend/src/components/editor/VideoStrip.vue:186-241](../../frontend/src/components/editor/VideoStrip.vue#L186)
