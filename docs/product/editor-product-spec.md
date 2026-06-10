# Editor — Product Spec

> Code-verified against `HEAD` on 2026-06-08. Every claim below is traceable to a
> source file and line. Where behavior could not be proven from code it is tagged
> `NOT VERIFIED IN CODE`, `IMPLEMENTATION NOT FOUND`, or `PARTIALLY IMPLEMENTED`.

## Overview

The Editor is the workspace where an operator reviews and corrects a single
session's AI-produced transcript. It mounts at the `#/e/:id` route
([frontend/src/router/index.ts:34](../../frontend/src/router/index.ts#L34)) and
renders a five-column grid: a left rail (video + slide list), a draggable
resizer, a center transcript/STT/discrepancies/audit pane, a second resizer, and
a right rail (Active Slide card + Admin/Chat/Polls tabs)
([frontend/src/views/EditorView.vue:1301](../../frontend/src/views/EditorView.vue#L1301)).

On mount the view fetches eleven data sources in parallel — session shell,
segments, slides, speakers, chat, polls, discrepancies, corrections/audit,
words, pipeline config, and word alignment — each tracked as an independent
load stage
([frontend/src/views/EditorView.vue:361](../../frontend/src/views/EditorView.vue#L361)).
Every list endpoint is safe against an empty session and renders empty-state copy
([app/api/session_resources.py:1](../../app/api/session_resources.py#L1)).

All text/slide/speaker edits are written through an **append-only correction
ledger**; undo/redo move a `sequence_number` pointer rather than mutating rows
([app/api/corrections.py:9](../../app/api/corrections.py#L9)).

## Purpose

Turn a raw AI first-pass transcript into a publish-ready one. The operator can:

- Read each segment beside the lecture video/audio with a karaoke playhead
  ([frontend/src/components/editor/TranscriptPane.vue:423](../../frontend/src/components/editor/TranscriptPane.vue#L423)).
- Inline-edit segment text with a markdown toolbar, autosave, and manual Save
  ([frontend/src/components/editor/TranscriptPane.vue:519](../../frontend/src/components/editor/TranscriptPane.vue#L519)).
- Reassign a segment to a different slide
  ([app/api/segments.py:224](../../app/api/segments.py#L224)).
- Reassign a segment's speaker
  ([app/api/session_resources.py:318](../../app/api/session_resources.py#L318)).
- Cross-check against a read-only Google STT reference and review classified
  discrepancies
  ([frontend/src/components/editor/STTPane.vue:1](../../frontend/src/components/editor/STTPane.vue#L1)).
- Place chat and poll cards onto segments
  ([frontend/src/views/EditorView.vue:700](../../frontend/src/views/EditorView.vue#L700)).
- Export the transcript as docx / srt / txt / zip
  ([frontend/src/components/editor/DownloadMenu.vue:27](../../frontend/src/components/editor/DownloadMenu.vue#L27)).

## User Value

- **Nothing is lost.** Every edit appends a correction row; undo/redo is a pointer
  move, never a row deletion
  ([app/api/corrections.py:883](../../app/api/corrections.py#L883),
  [app/api/corrections.py:928](../../app/api/corrections.py#L928)).
- **Edits persist without a Save click.** Debounced autosave fires on typing,
  blur, and segment switch
  ([frontend/src/composables/useAutosave.ts:130](../../frontend/src/composables/useAutosave.ts#L130)).
- **One editor at a time.** A 90-second TTL lock serializes editing and shows who
  holds the session
  ([app/api/locks.py:42](../../app/api/locks.py#L42),
  [frontend/src/composables/useSessionLock.ts:34](../../frontend/src/composables/useSessionLock.ts#L34)).
- **Real audio timing.** Per-word highlight is anchored to real STT timestamps
  from the word-alignment table, not proportional interpolation
  ([frontend/src/components/editor/SegmentText.vue:1](../../frontend/src/components/editor/SegmentText.vue#L1)).

## Navigation

Reached at `#/e/:id` with the session id as a route prop
([frontend/src/router/index.ts:34](../../frontend/src/router/index.ts#L34)). An
optional `initialTab` prop selects the starting center tab (`ai` | `stt` | `disc`
| `audit`)
([frontend/src/views/EditorView.vue:70](../../frontend/src/views/EditorView.vue#L70)).

In-view navigation links from the topbar:

- Breadcrumb: Sessions (`/sessions`) / session code (`/s/:id`) / Editor
  ([frontend/src/views/EditorView.vue:1177](../../frontend/src/views/EditorView.vue#L1177)).
- SOP stepper → `/e/:id/sop`
  ([frontend/src/views/EditorView.vue:1187](../../frontend/src/views/EditorView.vue#L1187)).
- Workflow → `/e/:id/sop`; Audit → `/e/:id/audit`
  ([frontend/src/views/EditorView.vue:1241](../../frontend/src/views/EditorView.vue#L1241)).
- Preview → `/v/:id` (viewer)
  ([frontend/src/views/EditorView.vue:917](../../frontend/src/views/EditorView.vue#L917)).

## Screens

The Editor is a single screen composed of these regions:

**Topbar** — breadcrumb, SOP stepper, AI-mode pipeline badge, AI-ready badge,
session-code title, Undo/Redo/Preview actions, `aligned` count, Find & Replace,
Follow-video toggle, stage badge, Workflow/Audit links, Download menu, and the
Flagged chip row
([frontend/src/views/EditorView.vue:1176](../../frontend/src/views/EditorView.vue#L1176)).

**Center tabs** — four tabs with counts
([frontend/src/views/EditorView.vue:1269](../../frontend/src/views/EditorView.vue#L1269)):

| Tab | Component | Count source |
|---|---|---|
| AI Transcript | `TranscriptPane` | segment count |
| STT Reference | `STTPane` | segment count |
| Discrepancies | `DiscrepanciesPane` | discrepancies where `is_meaningful === true` |
| Audit | `AuditTabInline` | correction count |

Counts are computed at
[frontend/src/views/EditorView.vue:812](../../frontend/src/views/EditorView.vue#L812).

**Left rail** — `VideoStrip` (16:9 frame with real `<video>`/`<audio>`, scrubber,
±10s seek, rate select, CC toggle, slide-chapter marks) over `SlideRail`
(slide list with Focus/Filter mode toggle)
([frontend/src/components/editor/VideoStrip.vue:250](../../frontend/src/components/editor/VideoStrip.vue#L250),
[frontend/src/components/editor/SlideRail.vue:109](../../frontend/src/components/editor/SlideRail.vue#L109)).

**Right rail** — `ActiveSlideCard` (slide preview + timeline minimap +
"Re-assign segments to slide" button) plus, on non-STT tabs, the Admin / Chat /
Polls tab group; on the STT tab it is replaced by `ActiveSlideCard` +
`STTSidePanel`
([frontend/src/views/EditorView.vue:1407](../../frontend/src/views/EditorView.vue#L1407),
[frontend/src/components/editor/ActiveSlideCard.vue:71](../../frontend/src/components/editor/ActiveSlideCard.vue#L71),
[frontend/src/components/editor/STTSidePanel.vue:28](../../frontend/src/components/editor/STTSidePanel.vue#L28)).

**Status bar** — loading/ready dot, segment + slide count, session status, and
build SHA
([frontend/src/views/EditorView.vue:1498](../../frontend/src/views/EditorView.vue#L1498)).

## User Flows

**Inline text edit.** Click a segment's "Edit" action → an inline editor opens
pre-filled with `**Short:** text` and a markdown toolbar (bold, italic,
underline, strikethrough, bullet/numbered list, undo/redo, mark uncertain /
verified / drift, clear marks, link, poll reference)
([frontend/src/components/editor/TranscriptPane.vue:522](../../frontend/src/components/editor/TranscriptPane.vue#L522)).
Typing fires debounced autosave; the speaker prefix is stripped before save
([frontend/src/components/editor/TranscriptPane.vue:241](../../frontend/src/components/editor/TranscriptPane.vue#L241)).
Save emits a `text_edit` correction
([frontend/src/views/EditorView.vue:943](../../frontend/src/views/EditorView.vue#L943)).

**Reassign to slide.** Click "Reassign" → a grid of slide tiles; clicking a tile
emits a `slide_reassignment` correction and optimistically updates the segment
([frontend/src/components/editor/TranscriptPane.vue:568](../../frontend/src/components/editor/TranscriptPane.vue#L568),
[frontend/src/views/EditorView.vue:977](../../frontend/src/views/EditorView.vue#L977)).

**Reassign speaker.** Click "Speaker" → a picker of the session's live speakers;
selecting one calls `POST .../segments/{id}/speaker-reassign`
([frontend/src/views/EditorView.vue:994](../../frontend/src/views/EditorView.vue#L994),
[app/api/session_resources.py:318](../../app/api/session_resources.py#L318)).

**Find & Replace.** The topbar button opens `FindReplaceModal`; on apply the view
reloads. The backend does literal-substring replace across all segments, one
`text_edit` per affected segment under a shared `action_id` so undo reverses the
batch, with a `dry_run` preview option
([frontend/src/views/EditorView.vue:934](../../frontend/src/views/EditorView.vue#L934),
[app/api/corrections.py:653](../../app/api/corrections.py#L653)).

**Undo / Redo.** Topbar buttons or Cmd/Ctrl+Z and Shift+Cmd/Ctrl+Z (or Ctrl+Y)
call the undo/redo endpoints then reload
([frontend/src/views/EditorView.vue:1022](../../frontend/src/views/EditorView.vue#L1022),
[frontend/src/views/EditorView.vue:1086](../../frontend/src/views/EditorView.vue#L1086)).

**Chat/Poll placement.** Drag a chat or poll card onto a segment (drop target) or
use "place at active"; placement persists via the chat/poll anchor PATCH
endpoints. Removing an anchor clears placement
([frontend/src/views/EditorView.vue:700](../../frontend/src/views/EditorView.vue#L700),
[app/api/session_resources.py:598](../../app/api/session_resources.py#L598),
[app/api/session_resources.py:795](../../app/api/session_resources.py#L795)).

**Discrepancy review.** The Discrepancies tab can request an edit (pivots to AI
tab + scrolls to the segment) or mark resolved (optimistically removes the rows)
([frontend/src/views/EditorView.vue:922](../../frontend/src/views/EditorView.vue#L922)).

**Split / merge.** `PARTIALLY IMPLEMENTED` — right-click a word ("Split here",
"Merge with previous", "Merge with next") or Ctrl+Shift+S / Ctrl+Shift+M, but
only when the `splitMergeEnabled` feature flag is true (default `false`)
([frontend/src/components/editor/SegmentText.vue:96](../../frontend/src/components/editor/SegmentText.vue#L96),
[frontend/src/stores/featureFlags.ts:22](../../frontend/src/stores/featureFlags.ts#L22)).
The backend likewise returns `503 SPLIT_MERGE_DISABLED` when its
`SPLIT_MERGE_ENABLED` flag is off
([app/api/corrections.py:362](../../app/api/corrections.py#L362)).

**Export.** The Download menu offers Word (`.docx`), Captions (`.srt`), Plain Text
(`.txt`), and Word Macro (`.zip`); selecting one streams the artifact via
`GET /v1/sessions/{id}/exports/{format}` and triggers a browser save
([frontend/src/components/editor/DownloadMenu.vue:42](../../frontend/src/components/editor/DownloadMenu.vue#L42)).

## Business Rules

- **Append-only ledger.** Corrections are never UPDATEd or DELETEd; undo/redo move
  the pointer ([app/api/corrections.py:9](../../app/api/corrections.py#L9)).
- **Allowed correction types** (`POST .../corrections`): `slide_reassignment`,
  `text_edit`, `split`, `merge`, `mark_ok`, `chat_insert`, `chat_edit`,
  `chat_remove`, `poll_insert`, `poll_remove`, `speaker_reassignment`
  ([app/api/corrections.py:49](../../app/api/corrections.py#L49)). An out-of-set
  type returns 400.
- **Discrepancy auto-close (BR-018).** Only `text_edit` and `mark_ok` corrections
  auto-close a segment's unresolved discrepancy
  ([app/api/corrections.py:63](../../app/api/corrections.py#L63),
  [app/api/corrections.py:341](../../app/api/corrections.py#L341)).
- **Anti-no-op guard.** A `text_edit` whose `old_text == new_text` (or a
  `slide_reassignment` to the same slide) is treated as a no-op so autosave-on-blur
  cannot silently truncate the redo tail
  ([app/api/corrections.py:74](../../app/api/corrections.py#L74)).
- **Single-editor lock.** TTL is 90 seconds (3 missed 30s heartbeats); a stale
  lock can be stolen on acquire, and the frontend fails closed to read-only when
  the lock service is unreachable
  ([app/api/locks.py:42](../../app/api/locks.py#L42),
  [frontend/src/composables/useSessionLock.ts:84](../../frontend/src/composables/useSessionLock.ts#L84)).
- **Find/Replace** replaces ALL occurrences and shares one `action_id` per run
  ([app/api/corrections.py:662](../../app/api/corrections.py#L662)).
- **Effective text precedence** (3 layers): most-recent `text_edit` ≤ pointer →
  `normalized_text` (if present) → raw `segments.text`
  ([app/api/segments.py:75](../../app/api/segments.py#L75),
  [app/api/corrections.py:666](../../app/api/corrections.py#L666)).
- **`aligned` count** counts only segments that actually carry a `slide_id`, not
  the total segment count; the color thresholds are 100% green / ≥80% amber /
  else red
  ([frontend/src/views/EditorView.vue:606](../../frontend/src/views/EditorView.vue#L606)).
- **Poll auto-placement.** A poll's anchor is the explicit `anchor_segment`, else
  the first segment of the slide named in `metadata.slide_n`
  ([frontend/src/views/EditorView.vue:158](../../frontend/src/views/EditorView.vue#L158)).
- **Chat edit requires placement.** The inline chat edit only runs when the chat is
  placed on a segment; the correction's `segment_id` is the placement segment
  ([frontend/src/views/EditorView.vue:760](../../frontend/src/views/EditorView.vue#L760)).

## Validation Rules

- **Segment timestamp edit.** `start_ms`/`end_ms` must be ≥ 0 and `end_ms >
  start_ms`; violation returns 400 `INVALID_TIMESTAMP`. The pydantic field also
  enforces `ge=0`
  ([app/api/segments.py:54](../../app/api/segments.py#L54),
  [app/api/segments.py:146](../../app/api/segments.py#L146)).
- **PATCH segment with no fields** returns 400 "No fields to update"
  ([app/api/segments.py:173](../../app/api/segments.py#L173)).
- **Find** is 1–512 chars; **replace** is 0–512 chars
  ([app/api/corrections.py:115](../../app/api/corrections.py#L115)).
- **Reorder** requires a non-empty `ids` array (400 `EMPTY_REORDER`) and every id
  must belong to the session (400 `UNKNOWN_CHAT_IDS` / `UNKNOWN_POLL_IDS`)
  ([app/api/session_resources.py:543](../../app/api/session_resources.py#L543),
  [app/api/session_resources.py:749](../../app/api/session_resources.py#L749)).
- **Speaker reassign** validates that both the segment and the target speaker
  belong to the session (404 otherwise)
  ([app/api/session_resources.py:332](../../app/api/session_resources.py#L332)).
- **Caption burn** rejects sessions with no `role='video'` source (400)
  ([app/api/session_resources.py:113](../../app/api/session_resources.py#L113)).

## States

- **Loading.** `loading` true → an editor skeleton renders in the grid slot while
  the segments stage is pending and no segments exist; once segments arrive a
  per-stage load progress strip shows
  ([frontend/src/views/EditorView.vue:1300](../../frontend/src/views/EditorView.vue#L1300),
  [frontend/src/views/EditorView.vue:1160](../../frontend/src/views/EditorView.vue#L1160)).
- **Empty session.** All list endpoints return empty arrays; panes render
  empty-state copy ("Unassigned" slide labels, no STT tokens, etc.)
  ([app/api/session_resources.py:1](../../app/api/session_resources.py#L1)).
- **Read-only.** When another user holds the lock or the lock service is
  unreachable, `isReadOnly` is true and autosave silently no-ops; the editor sets
  `data-readonly` on the root
  ([frontend/src/views/EditorView.vue:78](../../frontend/src/views/EditorView.vue#L78),
  [frontend/src/composables/useAutosave.ts:131](../../frontend/src/composables/useAutosave.ts#L131)).
- **STT background.** Until segments exist `sttReady` is false → the STT pane shows
  "Speech-to-text processing in background"; on STT failure it shows a failure
  note; `sttReady` is promoted true as soon as any segments exist
  ([frontend/src/views/EditorView.vue:473](../../frontend/src/views/EditorView.vue#L473),
  [frontend/src/components/editor/STTPane.vue:145](../../frontend/src/components/editor/STTPane.vue#L145)).
- **STT no-words.** Segments present but no STT word rows → amber "No STT words for
  this session yet" banner
  ([frontend/src/components/editor/STTPane.vue:183](../../frontend/src/components/editor/STTPane.vue#L183)).
- **Autosave badge** per segment: idle / saving / saved / error
  ([frontend/src/components/editor/TranscriptPane.vue:255](../../frontend/src/components/editor/TranscriptPane.vue#L255),
  [frontend/src/composables/useAutosave.ts:50](../../frontend/src/composables/useAutosave.ts#L50)).

## Dependencies

- **Backend endpoints** the editor calls on load: session shell, segments, slides,
  speakers, chat, polls, discrepancies, audit corrections, words, pipeline config,
  word alignment, plus a signed media URL
  ([frontend/src/views/EditorView.vue:361](../../frontend/src/views/EditorView.vue#L361)).
- **Live media** via `GET .../media-url` (24h signed GCS URL, prefers video, falls
  through to audio) ([app/api/session_resources.py:406](../../app/api/session_resources.py#L406)).
- **Captions** via `GET .../captions.vtt`, fetched as a Blob URL for the `<track>`
  element ([frontend/src/components/editor/VideoStrip.vue:75](../../frontend/src/components/editor/VideoStrip.vue#L75)).
- **WebSocket** sync for `stt_ready`/`stt_failed` and remote-change events
  (`correction_applied`, `discrepancy_resolved`, `timeline_ready`, classification
  events) ([frontend/src/views/EditorView.vue:418](../../frontend/src/views/EditorView.vue#L418)).
- **Word alignment** rows (populated by `lcs_discrepancies_task`) drive per-word
  highlight ([frontend/src/services/api.ts:286](../../frontend/src/services/api.ts#L286)).

## Error Handling

- **Save / reassign / speaker failures** show a toast with the API status +
  message and revert optimistic state where applicable
  ([frontend/src/views/EditorView.vue:954](../../frontend/src/views/EditorView.vue#L954),
  [frontend/src/views/EditorView.vue:1015](../../frontend/src/views/EditorView.vue#L1015)).
- **Autosave error** sets the per-segment badge to "error" (an `Unsaved — retry`
  pill); a 401 exits quietly because `http.ts` already redirected
  ([frontend/src/composables/useAutosave.ts:111](../../frontend/src/composables/useAutosave.ts#L111)).
- **Split/merge** maps backend codes to toasts: `409 SPLIT_MERGE_BUSY` retries once
  after 1s; `409 MERGE_NEIGHBOR_CHANGED` emits `reload-required`; `503
  SPLIT_MERGE_DISABLED` shows a defensive toast
  ([frontend/src/components/editor/SegmentText.vue:314](../../frontend/src/components/editor/SegmentText.vue#L314)).
- **Lock unreachable** renders a red banner with a Retry button; another holder
  renders a yellow read-only banner
  ([frontend/src/views/EditorView.vue:1125](../../frontend/src/views/EditorView.vue#L1125)).
- **Media / captions fetch failure** is non-fatal — the poster + scrubber stay
  static and the CC toggle becomes cosmetic
  ([frontend/src/views/EditorView.vue:389](../../frontend/src/views/EditorView.vue#L389),
  [frontend/src/components/editor/VideoStrip.vue:78](../../frontend/src/components/editor/VideoStrip.vue#L78)).
- **Download failure** shows an error toast naming the format
  ([frontend/src/components/editor/DownloadMenu.vue:48](../../frontend/src/components/editor/DownloadMenu.vue#L48)).

## Permissions

Authorization in the Editor today is **JWT presence only** for every editor data
endpoint, plus a **single hardcoded admin-email gate** on one action.

- The route guard requires authentication (redirect to login when not
  authenticated) but the editor route has **no** `adminOnly` meta — any logged-in
  user can open it ([frontend/src/router/index.ts:53](../../frontend/src/router/index.ts#L53)).
- Every editor backend endpoint depends on `CurrentUser`, which only decodes the
  JWT and confirms the user is active. `auth_users.role` is **not** loaded into the
  `User` object (it carries `email` only)
  ([app/auth.py:36](../../app/auth.py#L36),
  [app/auth.py:172](../../app/auth.py#L172)).
- The **only** admin gate that touches editor code is the lock force-take endpoint,
  which calls `is_admin(user)`. Because `role` is never loaded, `is_admin` falls
  back to comparing `user.email` against `LEGACY_ADMIN_EMAIL = "johndean@vin.com"`
  ([app/api/locks.py:225](../../app/api/locks.py#L225),
  [app/security/roles.py:62](../../app/security/roles.py#L62)). The "Force-take
  (admin)" button in the lock banner is shown client-side via the same email match
  ([frontend/src/views/EditorView.vue:1150](../../frontend/src/views/EditorView.vue#L1150),
  [frontend/src/composables/useIsAdmin.ts:22](../../frontend/src/composables/useIsAdmin.ts#L22)).
- Role tiers are **not active**. `app/security/roles.py` documents itself as a
  scaffold pending `auth_users.role` being wired into `get_current_user`
  ([app/security/roles.py:11](../../app/security/roles.py#L11)).

There is no per-segment, per-session membership, or per-role permission model on
any editor action ([app/api/segments.py:125](../../app/api/segments.py#L125)
notes Rounds is a "single-tenant operator pool").

## Reporting Impacts

- **Audit events.** Segment edits write an `audit_events` row with kind
  `segment.edit` (or `segment.time_edit` when only timestamps changed); reassign
  writes `segment.reassign`; chat/poll reorder writes `chat.reorder` /
  `polls.reorder`; lock force-take writes `session.lock_force_take`
  ([app/api/segments.py:195](../../app/api/segments.py#L195),
  [app/api/segments.py:248](../../app/api/segments.py#L248),
  [app/api/session_resources.py:580](../../app/api/session_resources.py#L580),
  [app/api/locks.py:247](../../app/api/locks.py#L247)).
- **Discrepancy resolution.** A `text_edit`/`mark_ok` at a discrepancy spot
  back-references the resolving correction, surfacing in the Discrepancies count
  ([app/api/corrections.py:341](../../app/api/corrections.py#L341)).
- **Exports** reflect the post-undo/redo state because segments are materialized to
  the current pointer after each undo/redo
  ([app/api/corrections.py:921](../../app/api/corrections.py#L921)).
- There is no editor-specific dashboard or analytics surface beyond the audit log
  and the chat-participants tally endpoint. `NOT VERIFIED IN CODE` for any other
  reporting.

## Audit Requirements

- Two parallel records: the **correction ledger** (`correction_ledger`, drives
  undo/redo and effective text) and **`audit_events`** (human-readable activity
  log). Segment PATCH writes to BOTH `corrections` and `audit_events`
  ([app/api/segments.py:202](../../app/api/segments.py#L202),
  [app/api/segments.py:213](../../app/api/segments.py#L213)).
- The editor's Audit tab reads `GET /v1/audit/sessions/{id}/corrections`
  ([frontend/src/services/api.ts:944](../../frontend/src/services/api.ts#L944),
  [frontend/src/views/EditorView.vue:369](../../frontend/src/views/EditorView.vue#L369)).
- Every correction records `applied_by` (the actor's email)
  ([app/api/corrections.py:874](../../app/api/corrections.py#L874)).

## Data Relationships

- A **session** has many **segments**; each segment optionally references one
  **slide** and one **speaker**
  ([app/api/segments.py:22](../../app/api/segments.py#L22)).
- Each segment has many **words** (real STT tokens) and many **word-alignment**
  entries (one per Gemini word)
  ([app/api/session_resources.py:461](../../app/api/session_resources.py#L461),
  [frontend/src/services/api.ts:290](../../frontend/src/services/api.ts#L290)).
- **Chat messages** and **polls** optionally anchor to one segment via
  `anchor_segment`; polls own many **poll options**
  ([app/api/session_resources.py:489](../../app/api/session_resources.py#L489),
  [app/api/session_resources.py:676](../../app/api/session_resources.py#L676)).
- **Discrepancies** optionally reference a segment and carry an AI/STT text pair +
  category ([frontend/src/services/api.ts:241](../../frontend/src/services/api.ts#L241)).
- **Corrections** reference a session + segment; **audit_events** reference a
  session ([app/api/segments.py:202](../../app/api/segments.py#L202)).
- Deleting a speaker sets referencing segments' `speaker_id` to NULL via FK
  ON DELETE SET NULL ([app/api/session_resources.py:292](../../app/api/session_resources.py#L292)).

## Known Constraints

- **Split/merge is behind a default-off flag** on both client and server, so it is
  inert in default deployments
  ([frontend/src/stores/featureFlags.ts:22](../../frontend/src/stores/featureFlags.ts#L22),
  [app/api/corrections.py:362](../../app/api/corrections.py#L362)).
- **No real-time collaborative editing** — editing is serialized by the lock, not
  merged ([app/api/locks.py:8](../../app/api/locks.py#L8)).
- **The right-rail "Re-assign segments to slide" button is not wired to a bulk
  reassign.** It only toasts a placeholder warning
  ([frontend/src/components/editor/ActiveSlideCard.vue:66](../../frontend/src/components/editor/ActiveSlideCard.vue#L66)). This
  corrects the seed `editor.md` which described general reassign — single-segment
  reassign works via the transcript pane, but the Active-Slide bulk button does
  not.
- **STT side-panel engine facts are static labels** ("Google STT v3",
  "latest_long", "48 kHz", "mono"), not read from session config
  ([frontend/src/components/editor/STTSidePanel.vue:31](../../frontend/src/components/editor/STTSidePanel.vue#L31)).
- **The STT Reference pane renders real per-word tokens but no live STT-specific
  re-transcription is triggered from the editor.** `PARTIALLY IMPLEMENTED` — tokens
  come from the `words` table written by `stt_background_task`
  ([frontend/src/components/editor/STTPane.vue:67](../../frontend/src/components/editor/STTPane.vue#L67)).
- **IIL signals are stubbed to `null`** in the editor, so the Admin tab's IIL
  section hides; the hardcoded MIC fixtures were removed
  ([frontend/src/views/EditorView.vue:629](../../frontend/src/views/EditorView.vue#L629)).
- **Some flag chips have no data source** (`name`, `number`, `date`, `style`):
  their counts are 0 and filtering by them yields zero segments
  ([frontend/src/views/EditorView.vue:880](../../frontend/src/views/EditorView.vue#L880),
  [frontend/src/views/EditorView.vue:895](../../frontend/src/views/EditorView.vue#L895)).
- **Slide focus does not persist across center-tab switches** — switching tabs
  clears `focusedSlideId` ([frontend/src/views/EditorView.vue:631](../../frontend/src/views/EditorView.vue#L631)).
- **The status-bar autosave readout shows a static `—`**; per-segment autosave
  status lives on each segment badge instead
  ([frontend/src/views/EditorView.vue:1501](../../frontend/src/views/EditorView.vue#L1501)).

## Source Verification
- **Files Used:** frontend/src/views/EditorView.vue, frontend/src/components/editor/{TranscriptPane,SegmentText,STTPane,STTSidePanel,SlideRail,VideoStrip,ActiveSlideCard,FlagLegend,DownloadMenu}.vue, frontend/src/composables/{useSessionLock,useAutosave,useIsAdmin}.ts, frontend/src/stores/featureFlags.ts, frontend/src/router/index.ts, frontend/src/services/api.ts, app/api/segments.py, app/api/session_resources.py, app/api/corrections.py, app/api/locks.py, app/auth.py, app/security/roles.py, docs/product/editor.md (seed), docs/specs/editor.spec.md (seed)
- **Components Used:** EditorView, TranscriptPane, SegmentText, STTPane, STTSidePanel, SlideRail, VideoStrip, ActiveSlideCard, FlagLegend, DownloadMenu
- **APIs Used:** GET/PATCH/POST `/v1/sessions/{id}/segments[/{id}][/reassign][/speaker-reassign]`, `/v1/sessions/{id}/{slides,speakers,chat,polls,sources,words,media-url,captioned-video,captions/burn}`, `/v1/sessions/{id}/{chat/order,chat/{id},polls/order,polls/{id}/anchor}`, `/v1/sessions/{id}/corrections[/undo|/redo]`, `/v1/sessions/{id}/find-replace`, `/v1/sessions/{id}/discrepancies`, `/v1/sessions/{id}/word-alignment`, `/v1/sessions/{id}/exports/{format}`, `/v1/sessions/{id}/captions.vtt`, `/v1/sessions/{id}/lock/*`, `/v1/audit/sessions/{id}/corrections`
- **Database Tables Used:** segments, slides, speakers, words, word_alignment, chat_messages, polls, poll_options, correction_ledger, ledger_pointers, corrections, audit_events, session_locks, sources, artifacts, normalization_results, discrepancies/transcription_discrepancies
- **Permission Logic Used:** JWT presence (CurrentUser) on all editor endpoints; LEGACY_ADMIN_EMAIL email gate via is_admin() only on lock force-take; client-side email match for the Force-take button
- **Confidence Score:** High — every claim traced to a read source file/line; the few unimplemented surfaces are explicitly tagged.
- **Evidence Links:** [EditorView.vue:361](../../frontend/src/views/EditorView.vue#L361), [corrections.py:49](../../app/api/corrections.py#L49), [segments.py:120](../../app/api/segments.py#L120), [locks.py:225](../../app/api/locks.py#L225), [roles.py:62](../../app/security/roles.py#L62)
