# Editor — Demo Questions

> Code-verified against `HEAD` on 2026-06-08. Every answer is traceable to source.
> Paths in this file are relative to `ai-demo-knowledge/demo-questions/` so source
> links use `../../`. Uncertainty is tagged `NOT VERIFIED IN CODE`,
> `IMPLEMENTATION NOT FOUND`, or `PARTIALLY IMPLEMENTED`.

## User

### Q: How do I edit a line of transcript?
- **Verified Answer:** Click the segment's "Edit" action to open an inline editor pre-filled with `**Speaker:** text` plus a markdown toolbar (bold, italic, underline, strikethrough, lists, marks, link, poll reference). Typing autosaves; Save commits a `text_edit` correction and Cancel discards the draft.
- **Supporting Evidence:** Inline edit modes + toolbar at TranscriptPane lines 203–339 and 519–566; save handler emits `text_edit` from EditorView.
- **Source Files:** [TranscriptPane.vue:519](../../frontend/src/components/editor/TranscriptPane.vue#L519), [EditorView.vue:943](../../frontend/src/views/EditorView.vue#L943)
- **API References:** `POST /v1/sessions/{id}/corrections`
- **Database References:** correction_ledger, audit_events

### Q: Do I have to click Save, or does it save automatically?
- **Verified Answer:** It autosaves. Typing schedules a debounced save (400 ms), and blur or switching segments flushes pending writes immediately. A per-segment badge shows Saving / Saved / Unsaved — retry. Manual Save still works.
- **Supporting Evidence:** `schedule`/`flush` with 400 ms debounce + 3 s compaction; blur fires `flushAutosave`.
- **Source Files:** [useAutosave.ts:130](../../frontend/src/composables/useAutosave.ts#L130), [TranscriptPane.vue:250](../../frontend/src/components/editor/TranscriptPane.vue#L250)
- **API References:** `POST /v1/sessions/{id}/corrections` (`text_edit`)
- **Database References:** correction_ledger

### Q: Can I undo a mistake?
- **Verified Answer:** Yes. Use the Undo/Redo buttons or Cmd/Ctrl+Z and Shift+Cmd/Ctrl+Z (Ctrl+Y also redoes). Undo/redo move a ledger pointer — corrections are never deleted, so history is preserved.
- **Supporting Evidence:** Keyboard handlers + button handlers; backend moves `current_pointer` only.
- **Source Files:** [EditorView.vue:1086](../../frontend/src/views/EditorView.vue#L1086), [corrections.py:883](../../app/api/corrections.py#L883)
- **API References:** `POST /v1/sessions/{id}/corrections/undo`, `/redo`
- **Database References:** ledger_pointers, correction_ledger

### Q: A segment is on the wrong slide — how do I fix it?
- **Verified Answer:** Click the segment's "Reassign" action to open a grid of slide tiles, then click the correct slide. This writes a `slide_reassignment` correction.
- **Supporting Evidence:** Reassign tile grid; backend updates `segments.slide_id` and records the correction + audit row.
- **Source Files:** [TranscriptPane.vue:568](../../frontend/src/components/editor/TranscriptPane.vue#L568), [segments.py:224](../../app/api/segments.py#L224)
- **API References:** `POST /v1/sessions/{id}/segments/{sid}/reassign`
- **Database References:** segments, corrections, audit_events

### Q: How do I change which speaker said a line?
- **Verified Answer:** Click "Speaker" on the segment to open a picker of the session's speakers and select one. It calls the speaker-reassign endpoint and the chip updates immediately.
- **Supporting Evidence:** Speaker picker uses live session speakers; handler calls `speakersApi.reassignSegment`.
- **Source Files:** [TranscriptPane.vue:264](../../frontend/src/components/editor/TranscriptPane.vue#L264), [EditorView.vue:994](../../frontend/src/views/EditorView.vue#L994)
- **API References:** `POST /v1/sessions/{id}/segments/{sid}/speaker-reassign`
- **Database References:** segments, speakers

### Q: How do I do a sweeping find-and-replace across the whole transcript?
- **Verified Answer:** Use the Find & Replace button in the topbar. The backend replaces all literal occurrences across every segment, writing one `text_edit` per affected segment under a shared action so a single undo reverses the whole batch. A dry-run preview is available.
- **Supporting Evidence:** Topbar opens `FindReplaceModal`; backend find-replace logic with shared `action_id` and `dry_run`.
- **Source Files:** [EditorView.vue:934](../../frontend/src/views/EditorView.vue#L934), [corrections.py:653](../../app/api/corrections.py#L653)
- **API References:** `POST /v1/sessions/{id}/find-replace`
- **Database References:** correction_ledger, segments, normalization_results

### Q: How do I export the finished transcript?
- **Verified Answer:** Use the Download menu in the topbar: Word (`.docx`), Captions (`.srt`), Plain Text (`.txt`), or Word Macro (`.zip`). Selecting one streams the file and triggers a browser save.
- **Supporting Evidence:** Four formats defined; `pick()` streams via `exportsApi.download`.
- **Source Files:** [DownloadMenu.vue:27](../../frontend/src/components/editor/DownloadMenu.vue#L27), [api.ts:405](../../frontend/src/services/api.ts#L405)
- **API References:** `GET /v1/sessions/{id}/exports/{format}`
- **Database References:** none (reads artifacts/segments server-side; `NOT VERIFIED IN CODE` for the export query)

### Q: How do I place a chat message or poll onto a moment in the transcript?
- **Verified Answer:** Drag the chat/poll card from the right rail onto a segment, or use "place at active." The placement persists; you can also remove it. Inline chat editing only works once the chat is placed.
- **Supporting Evidence:** Drop/place/remove handlers persist via the chat/poll anchor PATCH endpoints; chat edit requires a placement segment.
- **Source Files:** [EditorView.vue:700](../../frontend/src/views/EditorView.vue#L700), [EditorView.vue:760](../../frontend/src/views/EditorView.vue#L760)
- **API References:** `PATCH /v1/sessions/{id}/chat/{mid}`, `PATCH /v1/sessions/{id}/polls/{pid}/anchor`
- **Database References:** chat_messages, polls

## Operations

### Q: A teammate's tab crashed and the session is locked. Can I take it over?
- **Verified Answer:** Yes, but only the admin email can force-take. A normal lock expires after 90 seconds (3 missed 30s heartbeats) and can then be stolen on acquire; before that, the admin "Force-take" button bypasses staleness and writes an audit row.
- **Supporting Evidence:** 90s TTL; `force_take` requires `is_admin(user)` and inserts a `session.lock_force_take` audit row.
- **Source Files:** [locks.py:218](../../app/api/locks.py#L218), [EditorView.vue:1149](../../frontend/src/views/EditorView.vue#L1149)
- **API References:** `POST /v1/sessions/{id}/lock/force-take`, `/acquire`
- **Database References:** session_locks, audit_events

### Q: What happens if the lock service is down — can people still edit?
- **Verified Answer:** No. The lock composable fails closed: if the lock service is unreachable, the editor goes read-only and autosave silently no-ops. A red "Lock service unavailable" banner with a Retry button is shown.
- **Supporting Evidence:** `_apply(null)` sets `isHolder=false`; autosave gated on `enabled===true`; red banner on `lockError`.
- **Source Files:** [useSessionLock.ts:77](../../frontend/src/composables/useSessionLock.ts#L77), [EditorView.vue:1125](../../frontend/src/views/EditorView.vue#L1125)
- **API References:** `POST /v1/sessions/{id}/lock/acquire`, `/heartbeat`
- **Database References:** session_locks

### Q: The STT Reference tab says "processing in background." Is something broken?
- **Verified Answer:** Not necessarily. In AI-direct mode the session becomes ready before Google STT finishes; the STT tab shows that spinner until segments/STT are available. If there are segments but no STT words, an amber "No STT words for this session yet" banner explains the worker may need to retry. A true failure shows a red note.
- **Supporting Evidence:** `sttReady` gating; no-words banner; failed banner.
- **Source Files:** [STTPane.vue:145](../../frontend/src/components/editor/STTPane.vue#L145), [EditorView.vue:473](../../frontend/src/views/EditorView.vue#L473)
- **API References:** `GET /v1/sessions/{id}/words`; WS `stt_ready` / `stt_failed`
- **Database References:** words, segments

### Q: A session won't load some data — does the whole editor break?
- **Verified Answer:** No. Each of the 11 data sources loads independently and a failed source marks only its own load stage as error (returning a safe fallback). The editor chrome and other panes still render.
- **Supporting Evidence:** `_trackLoad` per-stage state; per-stage load strip.
- **Source Files:** [EditorView.vue:134](../../frontend/src/views/EditorView.vue#L134), [EditorView.vue:361](../../frontend/src/views/EditorView.vue#L361)
- **API References:** the 11 load endpoints (session, segments, slides, speakers, chat, polls, discrepancies, corrections, words, pipeline-config, word-alignment)
- **Database References:** segments, slides, speakers, chat_messages, polls, words, word_alignment, correction_ledger

### Q: The video won't play / has no captions. Is the session unusable?
- **Verified Answer:** No. Media and captions are non-fatal: if the signed media URL or captions.vtt fetch fails, the poster and scrubber stay static and the CC toggle becomes cosmetic. The transcript still loads and is editable.
- **Supporting Evidence:** Media fetch `.catch` clears URL; captions blob fetch failure is silent.
- **Source Files:** [EditorView.vue:389](../../frontend/src/views/EditorView.vue#L389), [VideoStrip.vue:75](../../frontend/src/components/editor/VideoStrip.vue#L75)
- **API References:** `GET /v1/sessions/{id}/media-url`, `/captions.vtt`
- **Database References:** sources, artifacts

## Compliance

### Q: Is there a complete record of who changed what?
- **Verified Answer:** Yes. Every segment edit writes both an append-only `correction_ledger` row (with `applied_by` email) and a human-readable `audit_events` row. Reassign, speaker change, chat/poll reorder, and lock force-take all write audit rows.
- **Supporting Evidence:** PATCH writes corrections + audit_events; reorder + force-take write audit_events.
- **Source Files:** [segments.py:202](../../app/api/segments.py#L202), [locks.py:247](../../app/api/locks.py#L247)
- **API References:** `GET /v1/audit/sessions/{id}/corrections`, `GET /v1/sessions/{id}/corrections`
- **Database References:** correction_ledger, audit_events, corrections

### Q: Can edit history ever be deleted or rewritten?
- **Verified Answer:** No. The correction ledger is append-only by invariant — UPDATE/DELETE on corrections is forbidden. Undo/redo move a pointer; the rows themselves are never mutated.
- **Supporting Evidence:** Module docstring states the append-only invariant; undo/redo update `ledger_pointers` only.
- **Source Files:** [corrections.py:9](../../app/api/corrections.py#L9), [corrections.py:911](../../app/api/corrections.py#L911)
- **API References:** `POST /v1/sessions/{id}/corrections/undo`, `/redo`
- **Database References:** correction_ledger, ledger_pointers

### Q: Does correcting a flagged segment clear the flag, and is that auditable?
- **Verified Answer:** Yes. Applying a `text_edit` or `mark_ok` correction at a segment with an unresolved discrepancy auto-closes that discrepancy and back-references the resolving correction. Only those two types auto-close (BR-018).
- **Supporting Evidence:** `CLOSES_DISCREPANCY_TYPES = {text_edit, mark_ok}`; resolution back-reference returned.
- **Source Files:** [corrections.py:63](../../app/api/corrections.py#L63), [corrections.py:341](../../app/api/corrections.py#L341)
- **API References:** `POST /v1/sessions/{id}/corrections`
- **Database References:** correction_ledger, discrepancies/transcription_discrepancies

### Q: Can a user edit a segment that belongs to another session, or a deleted session?
- **Verified Answer:** No. The PATCH query joins on `(id, session_id)` (blocking cross-session edits) and requires `sessions.deleted_at IS NULL` (blocking edits to soft-deleted sessions); a mismatch returns 404.
- **Supporting Evidence:** Containment + soft-delete guard in `edit_segment`.
- **Source Files:** [segments.py:133](../../app/api/segments.py#L133)
- **API References:** `PATCH /v1/sessions/{id}/segments/{sid}`
- **Database References:** segments, sessions

## Administrator

### Q: Who has admin powers in the editor, and what can they do?
- **Verified Answer:** The only admin-gated editor action is lock force-take. Admin is determined by `is_admin(user)`, which — because no role is loaded into the JWT identity — resolves to a single hardcoded email, `johndean@vin.com` (`LEGACY_ADMIN_EMAIL`). All other editor actions need only a valid login.
- **Supporting Evidence:** `force_take` calls `is_admin`; `is_admin` falls back to email equality with `LEGACY_ADMIN_EMAIL`; `User` carries email only.
- **Source Files:** [locks.py:225](../../app/api/locks.py#L225), [roles.py:62](../../app/security/roles.py#L62), [auth.py:36](../../app/auth.py#L36)
- **API References:** `POST /v1/sessions/{id}/lock/force-take`
- **Database References:** auth_users (role column exists but is unread), session_locks

### Q: Are role tiers (editor / reviewer / admin) enforced on editor endpoints?
- **Verified Answer:** No. Role-based authorization is scaffold-only. `auth_users.role` (migration 045) is not loaded by `get_current_user`, and every editor endpoint depends only on JWT presence (`CurrentUser`). The `roles.py` helper exists and is called by a few admin routes (including lock force-take) but always resolves via the email fallback.
- **Supporting Evidence:** roles.py self-documents "scaffold only — not yet wired"; editor endpoints use `_user`/`user: CurrentUser` with no role check.
- **Source Files:** [roles.py:11](../../app/security/roles.py#L11), [segments.py:71](../../app/api/segments.py#L71), [auth.py:172](../../app/auth.py#L172)
- **API References:** all editor endpoints (`CurrentUser` dependency)
- **Database References:** auth_users

### Q: Can a non-admin open the editor for any session?
- **Verified Answer:** Yes. The editor route (`#/e/:id`) requires authentication but has no `adminOnly` meta — the only route with that guard is `/admin/help`. There is no per-session membership model; Rounds is a single-tenant operator pool.
- **Supporting Evidence:** Router guard checks auth + `adminOnly`; only `/admin/help` sets `adminOnly`; segment code notes single-tenant operator pool.
- **Source Files:** [router/index.ts:53](../../frontend/src/router/index.ts#L53), [router/index.ts:44](../../frontend/src/router/index.ts#L44), [segments.py:125](../../app/api/segments.py#L125)
- **API References:** none (client-side routing)
- **Database References:** none

## Power User

### Q: What keyboard shortcuts does the editor support?
- **Verified Answer:** J = back 10s, L = forward 10s, K = play/pause (single-key, no modifier). Cmd/Ctrl+Z = undo, Shift+Cmd/Ctrl+Z or Ctrl+Y = redo, Cmd/Ctrl+F = Find & Replace. Shortcuts are ignored while a textarea/input is focused so native editing works.
- **Supporting Evidence:** `_handleVideoNavKey` (J/K/L) and `_handleModifierShortcut` (Z/Y/F); editable-target guard.
- **Source Files:** [EditorView.vue:1069](../../frontend/src/views/EditorView.vue#L1069), [EditorView.vue:1062](../../frontend/src/views/EditorView.vue#L1062)
- **API References:** undo/redo + find-replace endpoints (indirectly)
- **Database References:** correction_ledger

### Q: What does the "Follow video" toggle do?
- **Verified Answer:** It controls whether the transcript auto-scrolls to keep the active segment in view as the video plays. When on (default), the pane scrolls to the active segment unless you've manually scrolled in the last 1.5 seconds. Turn it off to keep your scroll position fixed.
- **Supporting Evidence:** Toggle button; auto-scroll watcher respects `followVideo===false` and a 1500 ms user-scroll grace window.
- **Source Files:** [EditorView.vue:1229](../../frontend/src/views/EditorView.vue#L1229), [TranscriptPane.vue:156](../../frontend/src/components/editor/TranscriptPane.vue#L156)
- **API References:** none
- **Database References:** none

### Q: How does per-word highlighting stay in sync with the audio?
- **Verified Answer:** On the AI tab, each Gemini word is rendered with real STT start/end timestamps from the word-alignment table; a time watcher toggles `.dw-active` on the word whose window contains the current playback time. Unmatched words have no timestamps and are skipped. This replaces proportional interpolation.
- **Supporting Evidence:** Alignment render path + `data-ws/data-we`; the time watcher with span cache.
- **Source Files:** [SegmentText.vue:150](../../frontend/src/components/editor/SegmentText.vue#L150), [TranscriptPane.vue:423](../../frontend/src/components/editor/TranscriptPane.vue#L423)
- **API References:** `GET /v1/sessions/{id}/word-alignment`
- **Database References:** word_alignment

### Q: Can I split or merge segments?
- **Verified Answer:** `PARTIALLY IMPLEMENTED`. The UI exists — right-click a word for "Split here" / "Merge with previous" / "Merge with next", or use Ctrl+Shift+S / Ctrl+Shift+M — but it only activates when the `splitMergeEnabled` feature flag is true (default false). The backend likewise returns `503 SPLIT_MERGE_DISABLED` when its flag is off.
- **Supporting Evidence:** `splitMergeActive` gates the menu/keystrokes; store default false; backend 503 when disabled.
- **Source Files:** [SegmentText.vue:96](../../frontend/src/components/editor/SegmentText.vue#L96), [featureFlags.ts:22](../../frontend/src/stores/featureFlags.ts#L22), [corrections.py:362](../../app/api/corrections.py#L362)
- **API References:** `POST /v1/sessions/{id}/corrections` (`split` / `merge`)
- **Database References:** correction_ledger, segments

### Q: What's the difference between Focus mode and Filter mode in the slide rail?
- **Verified Answer:** Focus mode scrolls to a slide's first segment but keeps all segments visible; Filter mode shows only that slide's segments (legacy). The choice is remembered in localStorage; switching center tabs clears the current focus.
- **Supporting Evidence:** Mode toggle with tooltips; filter narrows `visible`; tab-switch clears `focusedSlideId`.
- **Source Files:** [SlideRail.vue:113](../../frontend/src/components/editor/SlideRail.vue#L113), [TranscriptPane.vue:142](../../frontend/src/components/editor/TranscriptPane.vue#L142), [EditorView.vue:631](../../frontend/src/views/EditorView.vue#L631)
- **API References:** none
- **Database References:** none

### Q: What do the colored "Flagged" chips at the top filter by, and why are some always zero?
- **Verified Answer:** Chips filter the transcript to segments matching that flag class. Drift / uncertain / low-confidence come from segment AI flags and/or discrepancy categories; filler/punctuation/medication/terminology/other come from discrepancy categories only. Name, Number, Date, and Style have no data source today, so their counts are 0 and filtering by them yields no segments.
- **Supporting Evidence:** `flagCounts` + `visibleSegments` two-source matching; name/number/date/style return empty.
- **Source Files:** [EditorView.vue:825](../../frontend/src/views/EditorView.vue#L825), [EditorView.vue:858](../../frontend/src/views/EditorView.vue#L858)
- **API References:** `GET /v1/sessions/{id}/discrepancies`
- **Database References:** discrepancies/transcription_discrepancies, segments

### Q: Can I reorder chat messages and polls?
- **Verified Answer:** Yes. Reordering is optimistic locally and persisted via a single bulk PATCH that sets `order_index` per row; on API failure the list reverts. Every id must belong to the session or the request is rejected.
- **Supporting Evidence:** `handleChatReorder`/`handlePollsReorder` with revert; backend single-statement renumber + membership check.
- **Source Files:** [EditorView.vue:724](../../frontend/src/views/EditorView.vue#L724), [session_resources.py:527](../../app/api/session_resources.py#L527)
- **API References:** `PATCH /v1/sessions/{id}/chat/order`, `PATCH /v1/sessions/{id}/polls/order`
- **Database References:** chat_messages, polls, audit_events

## Source Verification
- **Files Used:** frontend/src/views/EditorView.vue, frontend/src/components/editor/{TranscriptPane,SegmentText,STTPane,STTSidePanel,SlideRail,VideoStrip,ActiveSlideCard,FlagLegend,DownloadMenu}.vue, frontend/src/composables/{useSessionLock,useAutosave,useIsAdmin}.ts, frontend/src/stores/featureFlags.ts, frontend/src/router/index.ts, frontend/src/services/api.ts, app/api/segments.py, app/api/session_resources.py, app/api/corrections.py, app/api/locks.py, app/auth.py, app/security/roles.py
- **Components Used:** EditorView, TranscriptPane, SegmentText, STTPane, STTSidePanel, SlideRail, VideoStrip, ActiveSlideCard, FlagLegend, DownloadMenu
- **APIs Used:** corrections apply/undo/redo/find-replace; segments reassign/speaker-reassign; chat & polls order/anchor; lock force-take/acquire/heartbeat; media-url; captions.vtt; exports/{format}; words; word-alignment; discrepancies; audit/sessions/{id}/corrections
- **Database Tables Used:** segments, sessions, slides, speakers, words, word_alignment, chat_messages, polls, poll_options, sources, artifacts, normalization_results, correction_ledger, ledger_pointers, corrections, audit_events, session_locks, auth_users
- **Permission Logic Used:** JWT presence (CurrentUser) on all editor endpoints; is_admin() → LEGACY_ADMIN_EMAIL ("johndean@vin.com") email fallback only on lock force-take; client-side email match for the Force-take button; editor route has no adminOnly guard
- **Confidence Score:** High — every Q/A maps to a read source line; only the export server-side query and split/merge executor internals are flagged as unread.
- **Evidence Links:** [corrections.py:9](../../app/api/corrections.py#L9), [locks.py:225](../../app/api/locks.py#L225), [roles.py:62](../../app/security/roles.py#L62), [useAutosave.ts:130](../../frontend/src/composables/useAutosave.ts#L130), [EditorView.vue:1069](../../frontend/src/views/EditorView.vue#L1069)
