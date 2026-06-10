# Editor

Route: `#/e/:id` ([frontend/src/router/index.ts:34](../../frontend/src/router/index.ts#L34)) → [frontend/src/views/EditorView.vue](../../frontend/src/views/EditorView.vue), `props: true` (`id`, optional `initialTab`).

## Purpose

The transcript editing workspace for a single session. It loads the AI transcript, slide deck, speakers, chat/poll anchors, STT words, discrepancies, word alignment, and the corrections ledger, then presents a three-column layout: left = video + slide rail, center = the active tab pane (AI Transcript / STT Reference / Discrepancies / Audit), right = Active-slide card + Admin/Chat/Polls rail. Edits are written as append-only corrections. See [EditorView.vue:1-30](../../frontend/src/views/EditorView.vue#L1).

## User Types

Any authenticated user (no `adminOnly` meta — [router/index.ts:34](../../frontend/src/router/index.ts#L34)). One UX-only admin affordance exists: the **Force-take (admin)** button on the read-only lock banner is gated by `useIsAdmin()` ([EditorView.vue:1150](../../frontend/src/views/EditorView.vue#L1150)), and `AdminTab` shows an admin-only Rescue section gated by an email check (see Permissions).

## Entry Points

- Direct `#/e/:id` navigation.
- From SOP view ("Back to editor", "Open editor") and the per-session Audit breadcrumb (`RouterLink :to="/e/${id}"`).
- `props.initialTab` can preselect a tab (`tab = ref(props.initialTab || 'ai')` — [EditorView.vue:615](../../frontend/src/views/EditorView.vue#L615)).

## Navigation Paths

- Breadcrumb: `RouterLink` to `/sessions` and `/s/:id` ([EditorView.vue:1178-1181](../../frontend/src/views/EditorView.vue#L1178)).
- SOP stepper items link to `/e/:id/sop` ([EditorView.vue:1187](../../frontend/src/views/EditorView.vue#L1187)).
- "Workflow" → `/e/:id/sop`; "Audit" → `/e/:id/audit` ([EditorView.vue:1241-1242](../../frontend/src/views/EditorView.vue#L1241)).
- "Preview" button → `onPreview()` → `router.push('/v/:id')` (Viewer) ([EditorView.vue:917](../../frontend/src/views/EditorView.vue#L917)).
- `DownloadMenu` (child) handles exports for this session.

## Components

Imported children ([EditorView.vue:33-48](../../frontend/src/views/EditorView.vue#L33)):
- Layout: `EditorSkeleton`, `FlagLegend`, `VideoStrip`, `SlideRail`.
- Center panes (one active at a time): `TranscriptPane` (AI), `STTPane` (STT), `DiscrepanciesPane` (disc), `AuditTabInline` (audit).
- Right rail: `ActiveSlideCard`, `AdminTab`, `SpeakerEditPanel`, `ChatTab`, `PollsTab`, `STTSidePanel` (STT tab only).
- `DownloadMenu` (export menu in the sub-row).
- Overlay: `FindReplaceModal` opened via `modal.open(...)` ([EditorView.vue:934-939](../../frontend/src/views/EditorView.vue#L934)).
- `Icon` (shared) throughout.

Composables: `useSessionLock`, `useIsAdmin`, `useAutosave`, `useEditorPersistence`, `useSyncController`, `useWsSubscriber` ([EditorView.vue:49-62](../../frontend/src/views/EditorView.vue#L49)).

## Actions

- **Switch center tab** (AI / STT / Discrepancies / Audit) — `tab` ref ([EditorView.vue:1270-1288](../../frontend/src/views/EditorView.vue#L1270)). Switching tabs clears `focusedSlideId` ([EditorView.vue:631](../../frontend/src/views/EditorView.vue#L631)).
- **Switch right-rail tab** (Admin / Chat / Polls) — `rightTab` ref ([EditorView.vue:1445-1455](../../frontend/src/views/EditorView.vue#L1445)).
- **Filter by flag chip** — `flagFilter` toggles; `visibleSegments` recomputes the AI pane list ([EditorView.vue:847-883](../../frontend/src/views/EditorView.vue#L847)).
- **Click slide / segment / word** — seeks `time` (`onSlideClick`, `onSegmentClick`, `onWordClick`, `onScrubClick`) ([EditorView.vue:786-810](../../frontend/src/views/EditorView.vue#L786)).
- **Edit a segment (manual)** — `onEditSegment` → `correctionsApi.apply({ correction_type: 'text_edit' })` ([EditorView.vue:943-958](../../frontend/src/views/EditorView.vue#L943)).
- **Autosave a segment** — `onAutosaveSegment` → `autosave.schedule(...)`; flushed on blur via `onFlushAutosave` ([EditorView.vue:965-975](../../frontend/src/views/EditorView.vue#L965)). Autosave writes are gated on `isHolder` by `useAutosave`.
- **Reassign segment slide** — `onReassignSegment` → `correctionsApi.apply({ correction_type: 'slide_reassignment' })` ([EditorView.vue:977-992](../../frontend/src/views/EditorView.vue#L977)).
- **Reassign segment speaker** — `onReassignSpeakerLive` → `speakersApi.reassignSegment(...)` ([EditorView.vue:994-1019](../../frontend/src/views/EditorView.vue#L994)).
- **Place / remove / reorder / edit chat & polls** — `handleDropOnSegment`, `handleRemoveAnchor`, `handlePlaceAtActive`, `handleChatReorder`, `handlePollsReorder`, `handleChatEdit` → `placementsApi.*` and `correctionsApi.apply({ correction_type: 'chat_edit' })` ([EditorView.vue:686-784](../../frontend/src/views/EditorView.vue#L686)).
- **Undo / Redo** — `onUndo`/`onRedo` → `correctionsApi.undo/redo` then `load()` ([EditorView.vue:1022-1041](../../frontend/src/views/EditorView.vue#L1022)). Also bound to Cmd/Ctrl+Z, Shift+Cmd/Ctrl+Z, Ctrl+Y ([EditorView.vue:1086-1103](../../frontend/src/views/EditorView.vue#L1086)).
- **Find & Replace** — `openFind()` opens `FindReplaceModal` (Cmd/Ctrl+F) ([EditorView.vue:934-939](../../frontend/src/views/EditorView.vue#L934)).
- **Toggle Follow-video** — `followVideo` ref ([EditorView.vue:1229-1238](../../frontend/src/views/EditorView.vue#L1229)).
- **Discrepancy actions** — `onDiscRequestEdit` (pivot to AI tab + scroll) and `onDiscrepancyResolved` (optimistic local removal) ([EditorView.vue:922-933](../../frontend/src/views/EditorView.vue#L922)).
- **Resize columns** — `onResizeLeft`/`onResizeRight` persist widths to `localStorage` ([EditorView.vue:633-662](../../frontend/src/views/EditorView.vue#L633)).
- **Keyboard nav** — J/K/L video nav ([EditorView.vue:1069-1082](../../frontend/src/views/EditorView.vue#L1069)).

## States

- **Read-only (lock not held):** `isReadOnly = isHolder !== true` ([EditorView.vue:78](../../frontend/src/views/EditorView.vue#L78)); `data-readonly` set on the root, autosave gated.
- **Tab-specific layout:** the right rail renders `STTSidePanel` + `ActiveSlideCard` on the STT tab, otherwise the Admin/Chat/Polls rail ([EditorView.vue:1407-1495](../../frontend/src/views/EditorView.vue#L1407)).
- **Pipeline badge:** "AI: direct/enhanced" badge renders only when `pipelineCfg` is loaded ([EditorView.vue:1192-1198](../../frontend/src/views/EditorView.vue#L1192)).
- **Status pill:** "AI ready" when `session.status` is `ready`/`complete`, else the raw status ([EditorView.vue:1199-1201](../../frontend/src/views/EditorView.vue#L1199)).
- **Aligned count color:** green/amber/red by aligned-segment percentage ([EditorView.vue:606-613](../../frontend/src/views/EditorView.vue#L606)).
- **Statusbar:** shows `loading ? 'loading' : 'ready'`, segment/slide counts, session status, build sha ([EditorView.vue:1498-1509](../../frontend/src/views/EditorView.vue#L1498)).
- **WS live updates:** `useWsSubscriber` triggers quiet refetches on `correction_applied`, `discrepancy_resolved`, `classification_*`, `timeline_ready` ([EditorView.vue:440-458](../../frontend/src/views/EditorView.vue#L440)); `useSyncController` flips `sttReady`/`sttFailed` ([EditorView.vue:422-425](../../frontend/src/views/EditorView.vue#L422)).

## Empty States

- The editor renders its full chrome (breadcrumb, stepper, flag chips, tabs) even with zero data — the header comment explicitly documents graceful empty rendering ([EditorView.vue:15-17](../../frontend/src/views/EditorView.vue#L15)).
- **AI Transcript pane:** `TranscriptPane` simply renders zero `<article>` rows when its `segments` prop is empty — there is no dedicated "no segments" panel in the pane template ([TranscriptPane.vue:469](../../frontend/src/components/editor/TranscriptPane.vue#L469)). A dedicated empty panel is IMPLEMENTATION NOT FOUND.
- **STT pane:** explicit "no data" panel when a session has no words (`isSessionWithoutWords`) and a "live" panel when it does ([STTPane.vue:184-213](../../frontend/src/components/editor/STTPane.vue#L184)).
- **Discrepancy tab count:** the amber count badge only renders when `counts.disc > 0` ([EditorView.vue:1278-1283](../../frontend/src/views/EditorView.vue#L1278)).
- **Audit tab (inline):** `AuditTabInline` shows a "No decisions" empty branch when `decisions.length === 0` ([AuditTabInline.vue:107](../../frontend/src/components/editor/AuditTabInline.vue#L107)).

## Error States

- **Lock service unreachable:** red banner "Lock service unavailable" with a Retry button (`lockError` set) ([EditorView.vue:1125-1137](../../frontend/src/views/EditorView.vue#L1125)).
- **Held by another operator:** yellow banner "In use by {email}" with auto-expire time; Force-take button only for admins ([EditorView.vue:1138-1156](../../frontend/src/views/EditorView.vue#L1138)).
- **Per-stage load error:** `_trackLoad` flips a stage to `'error'` (falls back to empty data); the load bar gets `editor__loadbar--has-error` when any stage errored ([EditorView.vue:134-138](../../frontend/src/views/EditorView.vue#L134), [1163](../../frontend/src/views/EditorView.vue#L1163)).
- **Edit / reassign / undo / redo / placement failures:** caught and surfaced as error toasts (`ApiError` → `"<status> — <message>"`), with optimistic local state reverted where applicable ([EditorView.vue:954-957](../../frontend/src/views/EditorView.vue#L954), [735-738](../../frontend/src/views/EditorView.vue#L735)).
- **Background classification failure:** info toast "Background: discrepancy classification failed — <reason>" ([EditorView.vue:453-457](../../frontend/src/views/EditorView.vue#L453)).

## Loading States

- **Initial load:** `loading` ref true while `load()` runs `Promise.all` over 11 fetches ([EditorView.vue:352-417](../../frontend/src/views/EditorView.vue#L352)).
- **Skeleton:** `EditorSkeleton` replaces the grid while the segments stage is pending and no segments are loaded yet ([EditorView.vue:1300](../../frontend/src/views/EditorView.vue#L1300)).
- **Per-stage load bar:** renders only while `loading` and `SEGMENTS.length > 0`; shows a fill at `loadProgressPct` plus per-stage chips (`is-pending`/`is-done`/`is-error`) ([EditorView.vue:1160-1175](../../frontend/src/views/EditorView.vue#L1160)).
- **Quiet refresh:** WS-triggered refetches call `load({ silent: true })` which does not flip `loading` ([EditorView.vue:352-356](../../frontend/src/views/EditorView.vue#L352), [437](../../frontend/src/views/EditorView.vue#L437)).

## Permissions

- **Route:** JWT presence only via `beforeEach` (`auth.isAuthenticated`) — no `adminOnly` meta ([router/index.ts:53-67](../../frontend/src/router/index.ts#L53)).
- **Concurrent-edit lock:** `useSessionLock` fails closed — if the lock service is unreachable or another user holds it, `isReadOnly` is true and writes are gated ([useSessionLock.ts:10-17](../../frontend/src/composables/useSessionLock.ts#L10)). This is per-session edit ownership, not role-based authz.
- **Admin affordances (UX-only):**
  - Force-take button: `useIsAdmin()` returns true only when `auth.email === LEGACY_ADMIN_EMAIL_CLIENT` ("johndean@vin.com") ([useIsAdmin.ts:22-27](../../frontend/src/composables/useIsAdmin.ts#L22)).
  - `AdminTab` Rescue section: hardcoded `auth.email.toLowerCase() === 'johndean@vin.com'` ([AdminTab.vue:45-46](../../frontend/src/components/editor/AdminTab.vue#L45)).
  Both are UX guards only; the server is authoritative. Role tiers (`auth_users.role`) are not consulted by this view.

## Connected APIs

`load()` issues these in parallel ([EditorView.vue:361-373](../../frontend/src/views/EditorView.vue#L361)):
- `sessionsApi.get(id)` → `GET /v1/sessions/{id}` ([api.ts:139-140](../../frontend/src/services/api.ts#L139)).
- `segmentsApi.list(id)` → `GET /v1/sessions/{id}/segments` ([api.ts:619-620](../../frontend/src/services/api.ts#L619)).
- `http(...slides)` → `GET /v1/sessions/{id}/slides`.
- `http(...speakers)` → `GET /v1/sessions/{id}/speakers`.
- `http(...chat)` → `GET /v1/sessions/{id}/chat`.
- `http(...polls)` → `GET /v1/sessions/{id}/polls`.
- `discrepanciesApi.list(id)` → `GET /v1/sessions/{id}/discrepancies` ([api.ts:262-265](../../frontend/src/services/api.ts#L262)).
- `auditApi.corrections(id)` → `GET /v1/audit/sessions/{id}/corrections` ([api.ts:944-945](../../frontend/src/services/api.ts#L944)).
- `wordsApi.listBySession(id)` → `GET /v1/sessions/{id}/words` ([api.ts:281-282](../../frontend/src/services/api.ts#L281)).
- `sessionsApi.pipelineConfig(id)` → `GET /v1/sessions/{id}/pipeline-config` ([api.ts:174-177](../../frontend/src/services/api.ts#L174)).
- `wordAlignmentApi.get(id)` → `GET /v1/sessions/{id}/word-alignment` ([api.ts:304-307](../../frontend/src/services/api.ts#L304)).
- Separately: `mediaApi.url(id, 'video')` → `GET /v1/sessions/{id}/media-url?role=video` ([api.ts:343-348](../../frontend/src/services/api.ts#L343)).

Mutations from this view:
- `correctionsApi.apply(...)` → `POST /v1/sessions/{id}/corrections` (text_edit, slide_reassignment, chat_edit) ([api.ts:508-524](../../frontend/src/services/api.ts#L508)).
- `correctionsApi.undo/redo` → `POST /v1/sessions/{id}/corrections/undo|redo` ([api.ts:529-538](../../frontend/src/services/api.ts#L529)).
- `speakersApi.reassignSegment(...)` → `POST /v1/sessions/{id}/segments/{segId}/speaker-reassign` ([api.ts:328-332](../../frontend/src/services/api.ts#L328)).
- `placementsApi.chatAnchor/pollAnchor/chatReorder/pollsReorder` → `PATCH /v1/sessions/{id}/chat/{id}`, `.../polls/{id}/anchor`, `.../chat/order`, `.../polls/order` ([api.ts:369-393](../../frontend/src/services/api.ts#L369)).
- Lock endpoints via `useSessionLock`: `POST /v1/sessions/{id}/lock/acquire|heartbeat|release|force-take` ([useSessionLock.ts:88-116](../../frontend/src/composables/useSessionLock.ts#L88)).
- `FindReplaceModal` calls `correctionsApi.findReplace` (`POST /v1/sessions/{id}/find-replace`) — NOT VERIFIED IN CODE from this view; it is the modal's own call ([api.ts:539-546](../../frontend/src/services/api.ts#L539)).

## Data Sources

- All editor data comes from the backend fetches above, adapted to editor shapes by pure functions (`_adaptSegments`, `_adaptSlides`, `_adaptChat`, `_adaptPolls`, `_groupWordsBySegment`, `_unwrapAlignment`) ([EditorView.vue:198-338](../../frontend/src/views/EditorView.vue#L198)).
- `SOP_STAGES` fixture drives the topbar stepper ([EditorView.vue:58](../../frontend/src/views/EditorView.vue#L58), [1186](../../frontend/src/views/EditorView.vue#L1186)).
- `localStorage` holds column widths (`mic_left_w`/`mic_right_w`), slide-click mode (`mic_slide_click_mode`), and per-session editor persistence via `useEditorPersistence` ([EditorView.vue:618](../../frontend/src/views/EditorView.vue#L618), [633-636](../../frontend/src/views/EditorView.vue#L633), [512-519](../../frontend/src/views/EditorView.vue#L512)).
- `sessionStage` is hardcoded to `'prep'` pending per-editor SOP wiring ([EditorView.vue:350](../../frontend/src/views/EditorView.vue#L350)) — PARTIALLY IMPLEMENTED.
- `iilSignals` is hardcoded `null` (Instructor card hidden; no live IIL feed) ([EditorView.vue:629](../../frontend/src/views/EditorView.vue#L629)) — PARTIALLY IMPLEMENTED.

## Source Verification
- **Files Used:** frontend/src/views/EditorView.vue, frontend/src/services/api.ts, frontend/src/router/index.ts, frontend/src/composables/useSessionLock.ts, frontend/src/composables/useIsAdmin.ts, frontend/src/components/editor/TranscriptPane.vue, frontend/src/components/editor/STTPane.vue, frontend/src/components/editor/AuditTabInline.vue, frontend/src/components/editor/AdminTab.vue
- **Components Used:** EditorSkeleton, FlagLegend, VideoStrip, SlideRail, TranscriptPane, STTPane, STTSidePanel, DiscrepanciesPane, AuditTabInline, ActiveSlideCard, AdminTab, SpeakerEditPanel, ChatTab, PollsTab, DownloadMenu, FindReplaceModal, Icon
- **APIs Used:** GET /v1/sessions/{id}, /segments, /slides, /speakers, /chat, /polls, /discrepancies, /words, /pipeline-config, /word-alignment, /media-url; GET /v1/audit/sessions/{id}/corrections; POST /v1/sessions/{id}/corrections (+ /undo,/redo), /segments/{id}/speaker-reassign; PATCH chat/polls anchor + order; POST lock/acquire|heartbeat|release|force-take
- **Database Tables Used:** none read directly by the view (all via REST); server-side tables not asserted from frontend
- **Permission Logic Used:** JWT presence (route guard) + per-session edit lock (fail-closed) + LEGACY_ADMIN_EMAIL UX gate on Force-take and AdminTab Rescue
- **Confidence Score:** High — claims traced to view + child components + api.ts + composables.
- **Evidence Links:** [EditorView.vue:352-417](../../frontend/src/views/EditorView.vue#L352), [EditorView.vue:1119-1156](../../frontend/src/views/EditorView.vue#L1119), [api.ts:508-546](../../frontend/src/services/api.ts#L508), [useSessionLock.ts:49-116](../../frontend/src/composables/useSessionLock.ts#L49)
