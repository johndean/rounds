# Editor — Technical Spec

> Code-verified against `HEAD` on 2026-06-08. Paths are relative to this file
> (`docs/technical/`), so source links use `../../`. Uncertainty is tagged
> `NOT VERIFIED IN CODE`, `IMPLEMENTATION NOT FOUND`, or `PARTIALLY IMPLEMENTED`.

## Architecture

The Editor is a single Vue 3 SFC view (`EditorView.vue`) that orchestrates a set
of presentational child components and wires them to FastAPI raw-SQL endpoints.
It is reached via the hash router at `#/e/:id`
([../../frontend/src/router/index.ts:34](../../frontend/src/router/index.ts#L34)).

Data flow:

1. `EditorView.load()` fetches eleven sources in parallel, each wrapped in a
   `_trackLoad()` that flips a per-stage `'pending' → 'done' | 'error'` state and
   returns a typed fallback on rejection
   ([../../frontend/src/views/EditorView.vue:352](../../frontend/src/views/EditorView.vue#L352)).
2. Pure adapter functions (`_adaptSegments`, `_adaptSlides`, `_adaptChat`,
   `_adaptPolls`, `_groupWordsBySegment`, `_unwrapAlignment`, …) transform wire
   shapes into editor shapes
   ([../../frontend/src/views/EditorView.vue:192](../../frontend/src/views/EditorView.vue#L192)).
3. Refs feed computeds (`activeSegment`, `activeWordIdx`, `segmentsBySlide`,
   `anchorsBySegment`, `flagCounts`, `visibleSegments`, …) that drive the panes.
4. Edits emit up from child components to `EditorView` handlers, which call the
   corrections / segments APIs and apply optimistic local mutations.

The backend is FastAPI routers using raw parameterized SQL via SQLAlchemy `text()`
on the async `DbSession` dependency
([../../app/api/segments.py:12](../../app/api/segments.py#L12)).

## Frontend Components

| Component | Role | Source |
|---|---|---|
| `EditorView` | Orchestrator: data load, state, all edit handlers, keyboard shortcuts, layout grid | [EditorView.vue](../../frontend/src/views/EditorView.vue) |
| `TranscriptPane` | AI tab: segment cards, inline edit/reassign/speaker, drop targets, edit toolbar, follow-video auto-scroll | [TranscriptPane.vue](../../frontend/src/components/editor/TranscriptPane.vue) |
| `SegmentText` | Word-level render (3 paths: alignment / live STT words / plain split) + split/merge context menu | [SegmentText.vue](../../frontend/src/components/editor/SegmentText.vue) |
| `STTPane` | STT Reference tab: monospace tokens with timing superscripts; background/failed/no-words banners | [STTPane.vue](../../frontend/src/components/editor/STTPane.vue) |
| `STTSidePanel` | STT-tab right rail: static engine facts + token-distribution counts from discrepancies | [STTSidePanel.vue](../../frontend/src/components/editor/STTSidePanel.vue) |
| `SlideRail` | Left-rail slide list; Focus/Filter mode toggle; per-slide segment counts | [SlideRail.vue](../../frontend/src/components/editor/SlideRail.vue) |
| `VideoStrip` | Real `<video>`/`<audio>` element, scrubber, ±10s seek, rate select, CC `<track>`, chapter marks | [VideoStrip.vue](../../frontend/src/components/editor/VideoStrip.vue) |
| `ActiveSlideCard` | Right-rail slide preview + SVG timeline minimap + bulk-reassign button (stub) | [ActiveSlideCard.vue](../../frontend/src/components/editor/ActiveSlideCard.vue) |
| `FlagLegend` | Static 3-chip legend (drift / uncertain / low confidence) in the tab meta slot | [FlagLegend.vue](../../frontend/src/components/editor/FlagLegend.vue) |
| `DownloadMenu` | Export dropdown (docx/srt/txt/zip) → streams artifact via blob save | [DownloadMenu.vue](../../frontend/src/components/editor/DownloadMenu.vue) |

Additional children referenced by `EditorView` but outside this assignment's read
set: `DiscrepanciesPane`, `AuditTabInline`, `AdminTab`, `SpeakerEditPanel`,
`ChatTab`, `PollsTab`, `AnchorBlock`, `EditorSkeleton`, `FindReplaceModal`
([../../frontend/src/views/EditorView.vue:40](../../frontend/src/views/EditorView.vue#L40)).

## Backend Services

| Concern | Module / route |
|---|---|
| Segment list + inline edit/reassign | [../../app/api/segments.py](../../app/api/segments.py) |
| Slides, speakers, sources, words, media URL, chat, polls, captions burn | [../../app/api/session_resources.py](../../app/api/session_resources.py) |
| Correction ledger: apply / find-replace / list / undo / redo / review-queue | [../../app/api/corrections.py](../../app/api/corrections.py) |
| Editor lock: acquire / heartbeat / release / holder / force-take | [../../app/api/locks.py](../../app/api/locks.py) |
| Auth (JWT decode → `CurrentUser`) | [../../app/auth.py](../../app/auth.py) |
| Admin gate helper (scaffold; email-fallback) | [../../app/security/roles.py](../../app/security/roles.py) |

Split/merge executors (`segment_split`, `segment_merge`, `segment_inverse`) and
diff/caption engines are referenced from `corrections.py` but live in
`app/services/` and `app/tasks/`; per the seed spec
([../../docs/specs/editor.spec.md](../../docs/specs/editor.spec.md)).
`NOT VERIFIED IN CODE` here beyond the dispatch at
[../../app/api/corrections.py:383](../../app/api/corrections.py#L383).

## APIs

All paths require a valid JWT (`CurrentUser` / `_user` dependency). Editor-used
routes:

| Method | Path | Purpose | Source |
|---|---|---|---|
| GET | `/v1/sessions/{id}/segments` | List segments (effective text replayed) | [segments.py:70](../../app/api/segments.py#L70) |
| PATCH | `/v1/sessions/{id}/segments/{sid}` | Edit text/slide/speaker/flags/timestamps + audit | [segments.py:120](../../app/api/segments.py#L120) |
| POST | `/v1/sessions/{id}/segments/{sid}/reassign` | Reassign slide + audit | [segments.py:224](../../app/api/segments.py#L224) |
| POST | `/v1/sessions/{id}/segments/{sid}/speaker-reassign` | Reassign speaker | [session_resources.py:318](../../app/api/session_resources.py#L318) |
| GET | `/v1/sessions/{id}/slides` | Slide list | [session_resources.py:58](../../app/api/session_resources.py#L58) |
| POST | `/v1/sessions/{id}/slides/re-extract` | Re-extract chosen PDF pages | [session_resources.py:39](../../app/api/session_resources.py#L39) |
| GET/POST/PATCH/DELETE | `/v1/sessions/{id}/speakers[/{id}]` | Speaker CRUD | [session_resources.py:206](../../app/api/session_resources.py#L206) |
| GET | `/v1/sessions/{id}/words` | Real STT word tokens | [session_resources.py:461](../../app/api/session_resources.py#L461) |
| GET | `/v1/sessions/{id}/media-url?role=` | 24h signed playback URL | [session_resources.py:406](../../app/api/session_resources.py#L406) |
| GET | `/v1/sessions/{id}/chat` | Chat messages (order_index aware) | [session_resources.py:499](../../app/api/session_resources.py#L499) |
| PATCH | `/v1/sessions/{id}/chat/order` | Bulk reorder chat | [session_resources.py:527](../../app/api/session_resources.py#L527) |
| PATCH | `/v1/sessions/{id}/chat/{mid}` | Set/clear chat anchor | [session_resources.py:598](../../app/api/session_resources.py#L598) |
| GET | `/v1/sessions/{id}/polls` | Polls + options | [session_resources.py:704](../../app/api/session_resources.py#L704) |
| PATCH | `/v1/sessions/{id}/polls/order` | Bulk reorder polls | [session_resources.py:739](../../app/api/session_resources.py#L739) |
| PATCH | `/v1/sessions/{id}/polls/{pid}/anchor` | Set/clear poll anchor | [session_resources.py:795](../../app/api/session_resources.py#L795) |
| POST | `/v1/sessions/{id}/corrections` | Apply correction (incl. split/merge branch) | [corrections.py:332](../../app/api/corrections.py#L332) |
| POST | `/v1/sessions/{id}/find-replace` | Bulk text_edit, shared action_id, dry_run | [corrections.py:653](../../app/api/corrections.py#L653) |
| GET | `/v1/sessions/{id}/corrections` | Full ledger + current pointer | [corrections.py:832](../../app/api/corrections.py#L832) |
| POST | `/v1/sessions/{id}/corrections/undo` | Decrement pointer + materialize | [corrections.py:883](../../app/api/corrections.py#L883) |
| POST | `/v1/sessions/{id}/corrections/redo` | Increment pointer + materialize | [corrections.py:928](../../app/api/corrections.py#L928) |
| POST | `/v1/sessions/{id}/lock/{acquire,heartbeat,force-take}` | Lock lifecycle | [locks.py:99](../../app/api/locks.py#L99) |
| GET | `/v1/sessions/{id}/lock/holder` | Read holder | [locks.py:204](../../app/api/locks.py#L204) |
| POST 204 | `/v1/sessions/{id}/lock/release` | Release | [locks.py:188](../../app/api/locks.py#L188) |

Frontend service wrappers: `segments`, `corrections` (incl. `splitSegment` /
`mergeSegment`), `discrepancies`, `words`, `wordAlignment`, `speakers`, `media`,
`placements`, `exportsApi`, `audit`
([../../frontend/src/services/api.ts:508](../../frontend/src/services/api.ts#L508)).

## Data Models

**SegmentOut** — `id, seq, start_ms, end_ms, text, confidence, flags[],
is_anchor, anchor_kind, slide_id, speaker_id`
([../../app/api/segments.py:22](../../app/api/segments.py#L22)). The adapter maps
`start_ms/end_ms` to seconds and derives `confidence: 'low'` when `< 0.75`
([../../frontend/src/views/EditorView.vue:209](../../frontend/src/views/EditorView.vue#L209)).

**SegmentPatch** — optional `text, slide_id, speaker_id, flags[], start_ms (ge=0),
end_ms (ge=0)`
([../../app/api/segments.py:37](../../app/api/segments.py#L37)).

**CorrectionRequest** — `segment_id, correction_type, old_slide_id, new_slide_id,
old_text, new_text, action_id, after_word_index, expected_right_segment_id,
expected_content_hash`
([../../app/api/corrections.py:90](../../app/api/corrections.py#L90)).

**SlideOut / SpeakerOut / SourceOut / MediaUrlOut / WordOut / ChatMessageOut /
PollOut / PollOptionOut** are defined in
[../../app/api/session_resources.py:25](../../app/api/session_resources.py#L25)
onward. Notable: `SpeakerOut.short` is aliased to `name` in SQL (the table has no
distinct short column) ([../../app/api/session_resources.py:206](../../app/api/session_resources.py#L206));
`PollOut.metadata` carries `slide_n` for client anchor inference
([../../app/api/session_resources.py:694](../../app/api/session_resources.py#L694)).

**DiscrepancyRow / WordRow / WordAlignmentEntry** (frontend types)
([../../frontend/src/services/api.ts:241](../../frontend/src/services/api.ts#L241),
[../../frontend/src/services/api.ts:270](../../frontend/src/services/api.ts#L270),
[../../frontend/src/services/api.ts:290](../../frontend/src/services/api.ts#L290)).

Tables (verified via SQL references): `segments`, `slides`, `speakers`, `words`,
`word_alignment`, `chat_messages`, `polls`, `poll_options`, `sources`,
`artifacts`, `normalization_results`, `correction_ledger`, `ledger_pointers`,
`corrections`, `audit_events`, `session_locks`.

## Events

- **WebSocket subscribe** (`useWsSubscriber`): `correction_applied`,
  `discrepancy_resolved` → debounced quiet refetch; `timeline_ready` → full
  reload; `classification_complete` / `classification_partial` → quiet refetch;
  `classification_failed` → info toast
  ([../../frontend/src/views/EditorView.vue:440](../../frontend/src/views/EditorView.vue#L440)).
- **Sync controller** (`useSyncController`): `stt_ready` / `stt_failed` flip the
  STT pane state
  ([../../frontend/src/views/EditorView.vue:422](../../frontend/src/views/EditorView.vue#L422)).
- **Backend emits** `correction_applied` over WS after a correction, undo, and redo
  ([../../app/api/corrections.py:438](../../app/api/corrections.py#L438),
  [../../app/api/corrections.py:923](../../app/api/corrections.py#L923)).
- **DOM events** between components are Vue emits: e.g. `editSegment`,
  `autosaveSegment`, `flushAutosave`, `reassignSegment`, `reassignSpeakerLive`,
  `dropOnSegment`, `removeAnchor`, `segmentsChanged`, `reloadRequired`
  ([../../frontend/src/components/editor/TranscriptPane.vue:90](../../frontend/src/components/editor/TranscriptPane.vue#L90)).

## State Management

- **Local refs** in `EditorView` hold every data collection (`SEGMENTS`,
  `SLIDES`, `SPEAKERS_API`, `CHAT`, `POLLS`, `DISCREPANCIES`, `CORRECTIONS`,
  `WORDS_BY_SEGMENT`, `ALIGNMENT_BY_SEGMENT`, `placements`) plus playback state
  (`time`, `playing`, `rate`, `cc`, `followVideo`)
  ([../../frontend/src/views/EditorView.vue:88](../../frontend/src/views/EditorView.vue#L88)).
- **Pinia** is used only for the `featureFlags` store (`splitMergeEnabled`,
  default false) and the auth store (email/auth)
  ([../../frontend/src/stores/featureFlags.ts:20](../../frontend/src/stores/featureFlags.ts#L20)).
- **provide/inject** passes the autosave status map down to `TranscriptPane`/
  `SegmentText` via `AUTOSAVE_STATUS_KEY`
  ([../../frontend/src/views/EditorView.vue:85](../../frontend/src/views/EditorView.vue#L85)).
- **localStorage** persists rail widths (`mic_left_w`, `mic_right_w`), slide-click
  mode (`mic_slide_click_mode`), and (via `useEditorPersistence`) time/rate/scroll
  keyed by session + lock role
  ([../../frontend/src/views/EditorView.vue:633](../../frontend/src/views/EditorView.vue#L633),
  [../../frontend/src/views/EditorView.vue:512](../../frontend/src/views/EditorView.vue#L512)).
- **Active segment** is resolved by O(log n) binary search over `time` with a
  gap-fallback to the nearer neighbor
  ([../../frontend/src/views/EditorView.vue:560](../../frontend/src/views/EditorView.vue#L560)).
- **Optimistic updates** with revert-on-failure are used for inline edits, speaker
  reassign, chat edit, and reorder
  ([../../frontend/src/views/EditorView.vue:724](../../frontend/src/views/EditorView.vue#L724)).

## Validation

- **Timestamp edit**: `start_ms`/`end_ms` ≥ 0 (`Field(ge=0)`) and `end_ms >
  start_ms`, else 400 `INVALID_TIMESTAMP`
  ([../../app/api/segments.py:54](../../app/api/segments.py#L54),
  [../../app/api/segments.py:146](../../app/api/segments.py#L146)).
- **Empty PATCH** → 400 "No fields to update"
  ([../../app/api/segments.py:173](../../app/api/segments.py#L173)).
- **Correction type** must be in `ALLOWED_CORRECTION_TYPES`, else 400
  ([../../app/api/corrections.py:345](../../app/api/corrections.py#L345)).
- **No-op guard**: identical `text_edit`/`slide_reassignment` payloads are dropped
  to protect the redo tail
  ([../../app/api/corrections.py:74](../../app/api/corrections.py#L74)).
- **Find/Replace** length bounds 1–512 / 0–512
  ([../../app/api/corrections.py:115](../../app/api/corrections.py#L115)).
- **Reorder** non-empty + session-membership checks
  ([../../app/api/session_resources.py:543](../../app/api/session_resources.py#L543)).
- **Containment + soft-delete guard** on segment PATCH: the `(id, session_id)` join
  + `sessions.deleted_at IS NULL` prevents cross-session and deleted-session edits
  ([../../app/api/segments.py:133](../../app/api/segments.py#L133)).
- **Frontend** strips the `**Short:**` speaker prefix before sending text edits and
  short-circuits when text is unchanged
  ([../../frontend/src/components/editor/TranscriptPane.vue:224](../../frontend/src/components/editor/TranscriptPane.vue#L224)).

## Security

- **JWT bearer** auth (HS256, signed with `API_SECRET_KEY`); `get_current_user`
  decodes the token and confirms the user is active, with an env-CSV fallback
  ([../../app/auth.py:172](../../app/auth.py#L172)).
- **All SQL is parameterized** via SQLAlchemy `text()` bind params — no string
  interpolation of user values into queries
  ([../../app/api/segments.py:64](../../app/api/segments.py#L64)).
- **Signed GCS URLs** for media/captioned video carry a TTL (24h media, 1h
  captioned video) ([../../app/api/session_resources.py:403](../../app/api/session_resources.py#L403),
  [../../app/api/session_resources.py:164](../../app/api/session_resources.py#L164)).
- **Captions `<track>`** uses an authenticated `fetch` + Blob URL because `<track>`
  cannot carry an Authorization header
  ([../../frontend/src/components/editor/VideoStrip.vue:69](../../frontend/src/components/editor/VideoStrip.vue#L69)).
- **Fail-closed lock**: when the lock service is unreachable the editor goes
  read-only and gates writes on `isHolder === true`
  ([../../frontend/src/composables/useSessionLock.ts:84](../../frontend/src/composables/useSessionLock.ts#L84)).

## Permissions

`PARTIALLY IMPLEMENTED` (scaffold-only role system):

- Every editor endpoint depends on `CurrentUser` (JWT presence) with **no role
  check** ([../../app/api/segments.py:71](../../app/api/segments.py#L71),
  [../../app/api/corrections.py:333](../../app/api/corrections.py#L333),
  [../../app/api/session_resources.py:207](../../app/api/session_resources.py#L207)).
- `User` carries `email` only; `auth_users.role` is **not** loaded into the JWT
  identity ([../../app/auth.py:36](../../app/auth.py#L36)).
- The **only** admin gate touching editor code is lock force-take via
  `is_admin(user)`; with no `role` loaded, `is_admin` reduces to
  `user.email == "johndean@vin.com"` (`LEGACY_ADMIN_EMAIL`)
  ([../../app/api/locks.py:225](../../app/api/locks.py#L225),
  [../../app/security/roles.py:62](../../app/security/roles.py#L62)).
- `app/security/roles.py` is documented as a "Phase 8 scaffold only — not yet wired
  into any endpoint" for role tiers; the helper is wired in a few admin routes but
  resolves through the email fallback, not roles
  ([../../app/security/roles.py:11](../../app/security/roles.py#L11)).
- Client-side, only `/admin/help` carries `adminOnly` meta; the editor route does
  not, so any authenticated user can open it. The Force-take button is gated by an
  email match in `useIsAdmin`
  ([../../frontend/src/router/index.ts:44](../../frontend/src/router/index.ts#L44),
  [../../frontend/src/composables/useIsAdmin.ts:22](../../frontend/src/composables/useIsAdmin.ts#L22)).

> Discrepancy with brief: the brief stated roles.py is "NOT wired into endpoints."
> In reality `is_admin` IS imported and called by `locks.py` (and `email_debug.py`,
> `email_templates.py`, `help.py`), but because `role` is never loaded it always
> resolves via the `LEGACY_ADMIN_EMAIL` email fallback. The effective behavior the
> brief describes (email gate) is correct; the "not wired" wording is not.

## Integrations

- **Google Cloud Storage** — signed media/caption URLs via
  `app.tasks.burn_captions._generate_signed_url`
  ([../../app/api/session_resources.py:419](../../app/api/session_resources.py#L419)).
- **Google Speech-to-Text** — populates the `words` table out-of-band
  (`stt_background_task`); the editor only reads it
  ([../../app/api/session_resources.py:461](../../app/api/session_resources.py#L461)).
- **Celery** — caption burn (`burn_captions_task`) and PDF page re-extract
  (`slide_extract_selected_pages_task`) are enqueued from session_resources
  ([../../app/api/session_resources.py:120](../../app/api/session_resources.py#L120),
  [../../app/api/session_resources.py:47](../../app/api/session_resources.py#L47)).
- **WebSocket bridge** — `_emit_ws` publishes correction/undo/redo events
  ([../../app/api/corrections.py:438](../../app/api/corrections.py#L438)).

## Background Jobs

The editor does not run jobs itself; it consumes their output and can enqueue two:

- `burn_captions_task` (Phase 10.1) — produces a captioned MP4; failure does NOT
  fail the session ([../../app/api/session_resources.py:92](../../app/api/session_resources.py#L92)).
- `slide_extract_selected_pages_task` — re-extracts chosen PDF pages
  ([../../app/api/session_resources.py:39](../../app/api/session_resources.py#L39)).
- Read-only dependence on `stt_background_task` (words) and `lcs_discrepancies_task`
  (word alignment + discrepancies) `NOT VERIFIED IN CODE` here beyond the consumer
  comments ([../../frontend/src/views/EditorView.vue:98](../../frontend/src/views/EditorView.vue#L98)).

## Error Handling

- **Backend** raises `HTTPException` with structured detail bodies (e.g.
  `INVALID_TIMESTAMP`, `EMPTY_REORDER`, `UNKNOWN_CHAT_IDS`, `SPLIT_MERGE_BUSY`,
  `SPLIT_MERGE_DISABLED`, `SPLIT_MERGE_EXEC_ERROR`)
  ([../../app/api/segments.py:150](../../app/api/segments.py#L150),
  [../../app/api/corrections.py:362](../../app/api/corrections.py#L362)).
- **Split/merge dispatch** is wrapped so any unhandled exception is logged with a
  traceback and returned as a structured 500 carrying the exception class/message
  ([../../app/api/corrections.py:420](../../app/api/corrections.py#L420)).
- **Frontend** surfaces `ApiError.status`/`message` in toasts and reverts
  optimistic state ([../../frontend/src/views/EditorView.vue:954](../../frontend/src/views/EditorView.vue#L954));
  per-segment autosave errors render an "Unsaved — retry" badge
  ([../../frontend/src/composables/useAutosave.ts:116](../../frontend/src/composables/useAutosave.ts#L116)).
- **Non-fatal** failures (media, captions) leave the chrome static rather than
  blocking the editor ([../../frontend/src/components/editor/VideoStrip.vue:78](../../frontend/src/components/editor/VideoStrip.vue#L78)).
- **Per-stage load errors** mark only the failing stage `error` so a slow
  dependency doesn't hide the rest of the load
  ([../../frontend/src/views/EditorView.vue:134](../../frontend/src/views/EditorView.vue#L134)).

## Performance Considerations

- **Parallel load** of all 11 sources via `Promise.all`
  ([../../frontend/src/views/EditorView.vue:361](../../frontend/src/views/EditorView.vue#L361)).
- **Binary-search active-segment lookup** is O(log n) over the segment list
  ([../../frontend/src/views/EditorView.vue:560](../../frontend/src/views/EditorView.vue#L560)).
- **Word-highlight watcher** caches `.dw` spans per segment and early-outs when the
  previous word's window still contains `time`, so only boundary crossings scan
  ([../../frontend/src/components/editor/TranscriptPane.vue:410](../../frontend/src/components/editor/TranscriptPane.vue#L410)).
- **timeupdate throttle** at ~10 Hz (100 ms min between emits, leading+trailing)
  to avoid firing the highlight watcher on every native 30+ Hz tick
  ([../../frontend/src/components/editor/VideoStrip.vue:186](../../frontend/src/components/editor/VideoStrip.vue#L186)).
- **Scrubber drag** uses pointer events + requestAnimationFrame throttle on
  `update:time` ([../../frontend/src/components/editor/VideoStrip.vue:124](../../frontend/src/components/editor/VideoStrip.vue#L124)).
- **Autosave status** uses a `shallowRef<Map>` + manual `triggerRef` so the v-for
  over hundreds of segments does not reconcile on every save
  ([../../frontend/src/composables/useAutosave.ts:75](../../frontend/src/composables/useAutosave.ts#L75)).
- **Autosave compaction**: 400 ms debounce + 3 s rate-limit on consecutive writes
  to bound `correction_ledger` growth; blur/segment-switch flush bypasses the limit
  ([../../frontend/src/composables/useAutosave.ts:58](../../frontend/src/composables/useAutosave.ts#L58)).
- **WS quiet refresh** coalesces bursts (e.g. find/replace fan-out) into a single
  250 ms-debounced refetch
  ([../../frontend/src/views/EditorView.vue:433](../../frontend/src/views/EditorView.vue#L433)).
- **Reorder** collapses N per-row UPDATEs into one `jsonb_to_recordset` statement
  ([../../app/api/session_resources.py:563](../../app/api/session_resources.py#L563)).
- **Lock heartbeats pause** while the tab is hidden (Page Visibility API)
  ([../../frontend/src/composables/useSessionLock.ts:97](../../frontend/src/composables/useSessionLock.ts#L97)).

## Source Verification
- **Files Used:** frontend/src/views/EditorView.vue, frontend/src/components/editor/{TranscriptPane,SegmentText,STTPane,STTSidePanel,SlideRail,VideoStrip,ActiveSlideCard,FlagLegend,DownloadMenu}.vue, frontend/src/composables/{useSessionLock,useAutosave,useIsAdmin}.ts, frontend/src/stores/featureFlags.ts, frontend/src/router/index.ts, frontend/src/services/api.ts, app/api/segments.py, app/api/session_resources.py, app/api/corrections.py, app/api/locks.py, app/auth.py, app/security/roles.py, docs/specs/editor.spec.md (seed)
- **Components Used:** EditorView, TranscriptPane, SegmentText, STTPane, STTSidePanel, SlideRail, VideoStrip, ActiveSlideCard, FlagLegend, DownloadMenu
- **APIs Used:** segments list/PATCH/reassign/speaker-reassign; slides + slides/re-extract; speakers CRUD; words; media-url; chat + chat/order + chat/{id}; polls + polls/order + polls/{id}/anchor; corrections apply/find-replace/list/undo/redo/review-queue; lock acquire/heartbeat/release/holder/force-take; captions/burn; captioned-video; captions.vtt; exports/{format}; audit/sessions/{id}/corrections; word-alignment; discrepancies
- **Database Tables Used:** segments, slides, speakers, words, word_alignment, chat_messages, polls, poll_options, sources, artifacts, normalization_results, correction_ledger, ledger_pointers, corrections, audit_events, session_locks
- **Permission Logic Used:** JWT presence (CurrentUser) on all endpoints; is_admin() → LEGACY_ADMIN_EMAIL email fallback only on lock force-take; client adminOnly guard not applied to editor route
- **Confidence Score:** High — line-level evidence for every architectural and API claim; service internals (split/merge executors) flagged where unread.
- **Evidence Links:** [EditorView.vue:352](../../frontend/src/views/EditorView.vue#L352), [corrections.py:332](../../app/api/corrections.py#L332), [segments.py:120](../../app/api/segments.py#L120), [session_resources.py:406](../../app/api/session_resources.py#L406), [locks.py:42](../../app/api/locks.py#L42)
