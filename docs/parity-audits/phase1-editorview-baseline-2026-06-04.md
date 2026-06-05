# Phase 1 Baseline — EditorView + Sub-Components (Phases 4, 5, 6 scope)
Generated 2026-06-04 against tip `6df4170` (feat(sop): SMTP notification path for stage deadline warnings (F1.E)).

Read-only inventory. No fixes proposed; no files modified.

---

## Shell — EditorView.vue

File: `C:\Users\JohnDean\rounds\frontend\src\views\EditorView.vue` (950 LOC; prior audit referenced ~1009 — small drift, no structural change).

### DOM map (topbar, 3-pane, tabs)

| Region | Lines | Notes |
|---|---|---|
| Root `.editor` | 715 | Carries `data-screen-label="Editor / <id>"`. |
| `.editor__topbar` | 716–794 | Holds eyebrow breadcrumbs, SOP stepper, title row, subrow, flagged chip row. |
| `.page-eyebrow` | 717–723 | Sessions / `<code>` / Editor breadcrumb. |
| `.editor__stepper` (SOP stages + AI badge + status pill) | 725–742 | Pipeline badge at 732–738 (`pipelineCfg.ai_pipeline`). Status pill at 739–741. |
| `.editor__title-row` (Undo / Redo / Preview) | 744–757 | Buttons: `editor-undo`, `editor-redo`, `editor-preview`. |
| `.editor__subrow` (aligned count, Find&Replace, Workflow, Audit, DownloadMenu) | 759–772 | `editor-find-replace` button; DownloadMenu at 770. |
| `.editor__flagged` chip row | 774–793 | 9 primary categories + 3 secondary (uncertain/drift/low_conf). |
| `.editor__tabs` (AI / STT / Discrepancies / Audit + spacer + FlagLegend) | 796–813 | 4 tabs + meta slot. |
| `.editor__grid` (3-column layout) | 815–994 | gridTemplateColumns from `gridStyle` (456–458) — `leftW | 6px | 1fr | 6px | rightW`. |
| Left column `aside.editor__leftcol` — `<VideoStrip>` + `<SlideRail>` | 816–847 | VideoStrip 817–836; SlideRail 837–846. |
| Left resizer | 848 | `onResizeLeft`. |
| Center pane (one of TranscriptPane / STTPane / DiscrepanciesPane / AuditTabInline) | 850–905 | `v-if`/`v-else-if` switch keyed on `tab`. |
| Right resizer | 907 | `onResizeRight`. |
| Right rail `aside.rightrail` | 909–993 | Two variants:  STT-tab variant (910–935) shows ActiveSlideCard + STTSidePanel.  Default (936–993) shows ActiveSlideCard + tab strip (admin/chat/polls) + panel containing AdminTab+SpeakerEditPanel or ChatTab or PollsTab. |
| `.editor__statusbar` | 996–1007 | Loading state, counts, autosave placeholder, build SHA. |

### Mounted sub-components and where

| Component | EditorView line | Mounted inside |
|---|---|---|
| `VideoStrip` | 817–836 | Left column. |
| `SlideRail` | 837–846 | Left column. |
| `TranscriptPane` | 850–870 | Center pane when `tab === 'ai'`. |
| `STTPane` | 871–885 | Center pane when `tab === 'stt'`. |
| `DiscrepanciesPane` | 886–897 | Center pane when `tab === 'disc'`. |
| `AuditTabInline` | 898–905 | Center pane when `tab === 'audit'`. |
| `ActiveSlideCard` | 919–928 (STT variant) and 937–946 (default) | Right rail. |
| `STTSidePanel` | 929–934 | Right rail (STT tab only). |
| `AdminTab` | 960–967 | Right rail when `rightTab === 'admin'`. |
| `SpeakerEditPanel` | 968–972 | Right rail with AdminTab. |
| `ChatTab` | 974–982 | Right rail when `rightTab === 'chat'`. |
| `PollsTab` | 983–991 | Right rail when `rightTab === 'polls'`. |
| `DownloadMenu` | 770 | Subrow. |
| `FlagLegend` | 812 | Tab meta slot. |
| `FindReplaceModal` | invoked via `modal.open` at 612–616 (no `<template>` mount; modal layer). | — |

---

## Sub-component inventory

| Component | File | LOC | Mounted (EditorView line) | Key props / events |
|---|---|---|---|---|
| `VideoStrip` | `frontend/src/components/editor/VideoStrip.vue` | 237 | 817–836 | Props: `session`, `activeSlide`, `slides`, `time`, `total`, `playing`, `rate`, `cc`, `segmentsBySlide`, `mediaUrl`, `mediaKind`. Emits: `togglePlay`, `update:rate`, `update:cc`, `update:time`, `update:playing`, `update:total`, `scrubClick`. |
| `SlideRail` | `components/editor/SlideRail.vue` | 143 | 837–846 | Props: `slides`, `activeSlideId`, `focusedSlideId`, `mode`, `segmentsBySlide`. Emits: `modeChange`, `slideClick`, `clearFocus`. |
| `TranscriptPane` | `components/editor/TranscriptPane.vue` | 504 | 850–870 | Props: `segments`, `activeSegmentId`, `activeWordIdx`, `focusedSlideId`, `slideRailMode`, `anchorsBySegment`, `liveSpeakers`, `liveSlides`, `liveAlignment`, `time`. Emits: `segmentClick`, `wordClick`, `clearFocus`, `dropOnSegment`, `removeAnchor`, `editSegment`, `reassignSegment`, `reassignSpeakerLive`. |
| `STTPane` | `components/editor/STTPane.vue` | 238 | 871–885 | Props: `segments`, `activeSegmentId`, `activeWordIdx`, `focusedSlideId`, `slideRailMode`, `sttReady`, `sttFailed`, `liveWords`, `liveSlides`. Emits: `segmentClick`, `wordClick`, `clearFocus`. |
| `STTSidePanel` | `components/editor/STTSidePanel.vue` | 62 | 929–934 | Props: `time`, `totalDuration`, `segments`, `liveDiscrepancies`. No emits. |
| `DiscrepanciesPane` | `components/editor/DiscrepanciesPane.vue` | 280 | 886–897 | Props: `activeSegmentId`, `focusedSlideId`, `slideRailMode`, `liveSegments`, `liveSlides`, `liveDiscrepancies`, `liveWords`. Emits: `segmentClick`, `clearFocus`. |
| `AuditTabInline` | `components/editor/AuditTabInline.vue` | 105 | 898–905 | Props: `session`, `activeSegmentId`, `liveCorrections`, `liveSegments`. Emits: `segmentClick`. |
| `ActiveSlideCard` | `components/editor/ActiveSlideCard.vue` | 107 | 919–928, 937–946 | Props: `slide`, `segmentCount`, `collapsed`, `time`, `totalDuration`, `liveSlides`, `liveSegments`. Emits: `toggle`. |
| `AdminTab` | `components/editor/AdminTab.vue` | 110 | 960–967 | Props: `slide`, `segments`, `time`, `totalDuration`, `slides`, `iil`. No emits. |
| `SpeakerEditPanel` | `components/editor/SpeakerEditPanel.vue` | 296 | 968–972 | Props: `sessionId`, `liveSpeakers`. Emits: `changed`. |
| `ChatTab` | `components/editor/ChatTab.vue` | 94 | 974–982 | Props: `chat`, `slides`, `segmentsById`, `placements`. Emits: `unplace`, `placeAtActive`. |
| `PollsTab` | `components/editor/PollsTab.vue` | 76 | 983–991 | Props: `polls`, `segmentsById`, `slides`, `placements`. Emits: `unplace`, `placeAtActive`. |
| `DownloadMenu` | `components/editor/DownloadMenu.vue` | 51 | 770 | Props: `code`. No emits. |
| `FlagLegend` | `components/editor/FlagLegend.vue` | 20 | 812 | No props/emits. |
| `AnchorBlock` | `components/editor/AnchorBlock.vue` | 125 | rendered inside TranscriptPane per anchor (TranscriptPane.vue:518–525). | Props: `item`, `kind`, `slide`. Emits: `remove`. |
| `SegmentText` | `components/editor/SegmentText.vue` | 145 | rendered inside TranscriptPane (484–491), STTPane, DiscrepanciesPane. | Props: `text`, `flags`, `activeWordIdx`, `liveWords`, `liveAlignment`. Emits: `wordClick`. |
| `DecisionCard` | `components/editor/DecisionCard.vue` | 108 | rendered inside AuditTabInline. | Props: `c`, `segmentsById`, … |

(Discovered also: `AnchorBlock`, `SegmentText`, `DecisionCard`, `FlagLegend` beyond the explicitly named set. No other `editor/*.vue` files exist.)

---

## Phase 4 surface (video ↔ segment sync)

### Player implementation

- Native HTML5 `<video>` and `<audio>` elements (no Plyr / video.js / hls.js dependency). See `VideoStrip.vue:166–192`.
- Element selection driven by `mediaKind` prop: `'video'` → visible `<video class="vstrip__video">`; `'audio'` → hidden `<audio style="display:none">`; null → poster only.
- Media source URL fetched by `EditorView.load` via `mediaApi.url(session_id, 'video')` (EditorView.vue:111–117), with fall-through to audio because backend SQL orders `role='video' DESC`.
- No third-party player library in `frontend/package.json` (deps are `lucide-vue-next`, `pinia`, `vue`, `vue-router`).

### Current playback-time tracking

- Source of truth is the `<video>` / `<audio>` element's `currentTime`. Component-local ref `mediaEl` (VideoStrip.vue:54).
- Element → parent: throttled `timeupdate` handler at 10 Hz (VideoStrip.vue:94–111) emits `update:time` to EditorView.
- Parent → element: `watch(() => props.time, ...)` (VideoStrip.vue:127–137) writes `el.currentTime` when the externally requested time drifts > 0.4 s. Uses a `seeking` flag + a one-shot `seeked` listener to avoid feedback loops.
- Parent-level state lives in `EditorView.vue:320–323` as `const time = ref(...)` (initialized from `localStorage` per session). Persisted back to `localStorage` on every change (EditorView.vue:330).
- `playing`, `rate`, `cc` are also parent refs (EditorView.vue:324–326), mirrored via `update:*` emits.
- `TOTAL_DURATION` is a parent ref (EditorView.vue:83); seeded by `session.duration_sec`, supplemented by `loadedmetadata` (VideoStrip.vue:113–119) if missing.

### Segment data model — does it carry a timestamp today?

YES, in `start_ms` / `end_ms` (INTEGER, ms offset from session start). Already populated by ingest.

Evidence:
- DB schema: `migrations/001_init.sql:82-99` — segments table has `start_ms INTEGER NOT NULL`, `end_ms INTEGER NOT NULL`, plus `seq INTEGER NOT NULL` (per-session ordering) and `UNIQUE (session_id, seq)`.
- API DTO: `app/api/segments.py:22-35` (`SegmentOut`) exposes `start_ms`, `end_ms`, `seq`.
- API list endpoint: `app/api/segments.py:91-103` selects `id, seq, start_ms, end_ms, text, confidence, flags, is_anchor, anchor_kind, slide_id, speaker_id`.
- Frontend Segment type: `frontend/src/fixtures/transcript.ts:129-151` (`Segment` interface) has `start: number; end: number` (seconds — converted in EditorView.vue:131-132 from ms).
- PATCH endpoint (`app/api/segments.py:106-154`) currently allows updating `text`, `slide_id`, `speaker_id`, `flags`; it does **not** accept `start_ms`/`end_ms` in `SegmentPatch` today.

### Existing seek-from-segment wiring (with line numbers)

- TranscriptPane click handler: clicking a segment article emits `segmentClick(id)` (TranscriptPane.vue:366); EditorView handles via `onSegmentClick` (EditorView.vue:522-525) which sets `time.value = s.start`.
- STTPane click handler: same `segmentClick` → `onSegmentClick` (mounted at EditorView.vue:882).
- DiscrepanciesPane: same pattern (EditorView.vue:895).
- AuditTabInline: same pattern (EditorView.vue:904).
- SlideRail slide-click in "focus" mode also seeks to the first segment's `start` (EditorView.vue:515-521).
- Word-level seek: `onWordClick(segId, w)` (EditorView.vue:526-533) — clicks on a `.word` span seek proportionally inside the segment.
- Scrubber click on the playback bar: `onScrubClick` (EditorView.vue:534-539) — pct of the timeline.

### Existing highlight-from-time wiring (with line numbers)

- `activeSegment` (EditorView.vue:355-378): O(log n) binary search over segments using `time.value` between `start` and `end`, with VTT-cue-style gap fallback (picks nearer neighbor).
- `activeWordIdx` (EditorView.vue:380-389): proportional interpolation across the active segment's words.
- `activeSlide` (EditorView.vue:391): derived from `activeSegment.slide_id`.
- L2 word-highlight watcher inside TranscriptPane (TranscriptPane.vue:295-338, 342-344): walks `.dw[data-ws][data-we]` spans of the active segment, toggles `.dw-active` based on real STT timestamps from `word_alignment` table (migration 036). Span cache + boundary-crossing optimization.
- TranscriptPane auto-scrolls the active segment into view (TranscriptPane.vue:107-120).
- VideoStrip renders the playhead position via `trackWidth` (VideoStrip.vue:73-76) and per-slide "chapter marks" (78-87) using segment `start` data.

### Gap analysis — what Phase 4 requires that doesn't exist yet

Inventory only. Observed facts about gaps (no remediation proposals):

- `start_ms`/`end_ms` already persisted per segment; no schema change needed for a per-segment timestamp.
- No frontend mechanism currently lets the user **assign a new timestamp to a segment**. Inline-edit modes are `'edit'` (text), `'reassign'` (slide), `'speaker'` — there is no `'time'` mode (TranscriptPane.vue:88-94).
- `SegmentPatch` (`app/api/segments.py:37-42`) does not include `start_ms` / `end_ms`.
- Correction-ledger kinds today: `text_edit`, `slide_reassignment` (plus `slide_reassigned` in audit). No timestamp-change kind exists yet (see EditorView.vue:620-652 + `corrections` table from `migrations/029_corrections.sql`).
- Click-segment → seek-video and time-tick → highlight-segment paths both already exist; both are bidirectional through the `time` ref.

---

## Phase 5 surface (formatting)

### Segment text rendering (file:line)

- AI Transcript: `TranscriptPane.vue:404-516` — renders each segment's `text` through `SegmentText` (484-491) when not in edit mode.
- Inline editor: `TranscriptPane.vue:405-443` — `<textarea class="segment-editor__textarea" wrap="soft">` bound to `inline.draft`. Toolbar at 409-428 (Bold/Italic/Underline/lists/Strike/marks/Link/Poll-ref). Uses `tbWrap` (182-189), `tbLine` (190-197), `tbInsert` (198-204).
- The textarea's value persists `\n` literally because `wrap="soft"` doesn't insert breaks but does preserve typed Enter keypresses; `tbLine('- ')` is the only thing that inserts a `\n` programmatically (via lastIndexOf logic — see 190-197).
- Save path strips the speaker prefix and emits `editSegment(id, before, after)` (TranscriptPane.vue:143-152). EditorView calls `correctionsApi.apply` with `correction_type: 'text_edit'` (EditorView.vue:620-635).
- SegmentText itself uses `text.split(/(\s+)/)` (SegmentText.vue:52) which preserves whitespace tokens as items so the rendered output keeps spacing. Vue's whitespace condenser would normally collapse `<span> </span>` — this is mitigated by interleaving as text content (see header comment at SegmentText.vue:22-26).
- Vue compiler default `whitespace: 'condense'` applies. There is no `white-space: pre` / `pre-wrap` rule called out for `.segment__text` in the inventory (no grep performed beyond the JS path; CSS file is `frontend/src/styles/app.css`).

### Segment text data type

- Backend: `segments.text TEXT NOT NULL` (migrations/001_init.sql:90). Plain TEXT — newlines allowed.
- Frontend: `Segment.text: string` (fixtures/transcript.ts:135-136).
- No `paragraphs: string[]` or `runs[]` shape today. Single string. Soft vs hard breaks would have to be encoded inline (`\n` for paragraph, `\n` + space, or HTML, etc. — currently undefined).

### Export pipeline files

Primary:
- `app/api/exports.py` — `/v1/sessions/{id}/exports/{format}` route handling `txt | srt | vtt | docx | html | zip`.
- `app/engines/artifact_transformer.py` (634 LOC) — implements `to_txt`, `to_srt`, `to_vtt`, `to_docx`, `to_cms_html`, `to_zip`, plus the CMS macro (`apply_cms_transform`), SRT macro (`apply_srt_transform`), and `validate_final_srt` caption compliance check.

Secondary (referenced but not the primary export shapers):
- `app/engines/anchor.py`, `app/engines/segmenter.py`, `app/engines/normalize.py` (`app/tasks/normalize.py`) — ingest-time text shaping.
- `app/engines/fusion.py`, `app/tasks/fusion.py` — base text + STT fusion.

CMS / DOCX / SRT mapping:

| Export | Function | File:Line | Inputs |
|---|---|---|---|
| CMS HTML | `to_cms_html` | `app/engines/artifact_transformer.py:391-426` | `SessionForExport` → `_build_marked_transcript` (172-194) → `apply_cms_transform` (234-312) → `_markdown_to_html` (444-472). |
| DOCX | `to_docx` | `app/engines/artifact_transformer.py:143-166` | Uses `python-docx`. `add_paragraph` per segment; bold speaker prefix. |
| SRT | `to_srt` | `app/engines/artifact_transformer.py:118-131` | Per-segment, run `apply_srt_transform` (197-227) on `seg.text`. |
| VTT | `to_vtt` | `app/engines/artifact_transformer.py:134-140` | Plain `(seg.text or '').strip()`. |
| TXT | `to_txt` | `app/engines/artifact_transformer.py:96-115` | Plain text with `## Slide N: title` headings. |
| ZIP | `to_zip` | `app/engines/artifact_transformer.py:475-491` | Bundles all of the above. |

### How exports currently handle line breaks today

- **TXT**: each segment becomes a single `lines.append(...)` entry — no preservation of intra-segment `\n`. Final join is `"\n".join(lines)`.
- **SRT**: `apply_srt_transform` step 9 splits on `\n` and strips each line; step 10 collapses 3+ newlines to 2. Intra-segment newlines from segment text would survive unless other steps strip them. There is also a hard `max_line_chars: 42` validator in `validate_final_srt` (354-378) that rejects long lines.
- **VTT**: only `.strip()` per segment — no newline normalization. Intra-segment `\n` would be emitted verbatim into the cue text.
- **DOCX**: one paragraph per segment via `doc.add_paragraph()` — does **not** split `\n` inside `seg.text` into separate paragraphs. Embedded newlines would render as a single soft break inside one Word paragraph.
- **CMS HTML**: `_build_marked_transcript` (172-194) appends `seg.text or ''` as a single line. `apply_cms_transform` step 2 joins by `\n.strip()`; step 8 collapses 3+ newlines. `_markdown_to_html` (444-472) splits the body on `\n\n` for paragraph blocks and converts intra-paragraph `\n` to `<br/>` (470: `"<br/>".join(lines)`).
- Net: paragraph-level breaks (`\n\n`) survive only in CMS HTML; soft `\n` within a segment becomes `<br/>` in CMS HTML, is preserved unsanitized in VTT, gets normalized in SRT, and is lost (or rendered as a soft break) in DOCX and TXT.

---

## Phase 6 surface (poll/chat reorder)

### PollsTab — existing drag/drop wiring or lack thereof

- File: `frontend/src/components/editor/PollsTab.vue` (76 LOC).
- Each poll card is `:draggable="!placements[p.id]"` (line 54) — HTML5 native drag attribute. Dragging is **outward only**: `dragstart` sets `application/vnd.mic.anchor` to the poll id (lines 37-41) to drop on a transcript segment.
- There is **no vertical reorder within the PollsTab list**. No `dragover` / `dragenter` / `drop` handlers on sibling poll cards. No `sortable.js`, no `vue-draggable`/`vue-draggable-next` (verified absent in `frontend/package.json`).
- Rendering order: `v-for="p in polls"` (line 51) — uses parent's array order verbatim.
- No `data-test-id` on poll cards (`Grep test-id` against `PollsTab.vue` returns zero matches). The only test-ids in the broader editor are `editor-undo`, `editor-redo`, `editor-preview`, `editor-find-replace`, `editor-download`, `dl-{ext}` (DownloadMenu) and `seg-edit/seg-reassign/seg-speaker` on TranscriptPane.

### ChatTab — existing drag/drop wiring or lack thereof

- File: `frontend/src/components/editor/ChatTab.vue` (94 LOC).
- Chat msg row is `:draggable="!placements[row.msg.id]"` (line 79) — same outward-only pattern as polls. `dragstart` sets `application/vnd.mic.anchor` to the msg id (55-59).
- No sibling-reorder DnD. No external sortable lib.
- Rows are produced by a `grouped` computed (lines 30-43) that injects slide-divider headers in iteration order; otherwise the chat array's order is preserved.
- No `data-test-id` on chat rows.

### Poll/chat ordering data model

- DB schema: `migrations/008_chat_polls.sql`:
  - `chat_messages` has `sent_at_ms INTEGER NOT NULL` — ms offset from session start. No `seq` / `order_index` column.
  - `polls` has `opened_at_ms INTEGER NOT NULL`. Same — no explicit ordering column.
- API ORDER BY:
  - Chat list: `app/api/session_resources.py:506` — `ORDER BY sent_at_ms ASC`.
  - Polls list: `app/api/session_resources.py:588` — `ORDER BY opened_at_ms ASC`.
- Placement vs. order: `placements` is a separate map (parent-side, EditorView.vue:460) that records which segment an item is anchored to. It does **not** record list ordering. The `placedCount` computeds (PollsTab.vue:23, ChatTab.vue:45) are derived.
- Backend has poll-anchor + chat-anchor persist routes (referenced via `placementsApi.chatAnchor(...)`, `placementsApi.pollAnchor(...)` at EditorView.vue:487-509). These set the `anchor_segment` FK and `placed` boolean; they do not touch ordering.
- Reordering after placement (the explicit Phase 6 requirement) has no current backend representation — there is no `order_index INTEGER` column on either table, and no PATCH route accepts list position.

---

## Risk notes for Phases 4, 5, 6

- Phase 4 — Adding a "set timestamp" affordance must avoid replacing or restyling the existing player chrome in `VideoStrip.vue` (poster, scrubber, chapter marks, 10 Hz `timeupdate` throttle, mediaKind switch). Any new inline `time` mode on a segment should sit alongside `edit`/`reassign`/`speaker` modes in `TranscriptPane.vue:88-94` and reuse the existing `time` ref + `onSegmentClick` pathway.
- Phase 4 — `SegmentPatch` does not currently accept `start_ms`/`end_ms`; the corrections ledger has no `'time_edit'` kind. Both backend and frontend correction-type enums need to accommodate any new mutation (out of scope here — flagging surface only).
- Phase 4 — Word-level karaoke highlight (`TranscriptPane.vue:295-338`) is driven off `word_alignment` (migration 036), which is keyed off existing segment timestamps. Changing a segment's `start_ms`/`end_ms` after alignment is computed could leave aligned words pointing into the wrong time window. Realignment hook is `/v1/diag/realign/<SESSION_ID>` (per CLAUDE.md).
- Phase 5 — TranscriptPane's editor stores draft in a single string (`inline.draft`). Vue compiler `whitespace: 'condense'` plus the lack of explicit `white-space: pre-wrap` on `.segment__text` means soft newlines inside `Segment.text` will not survive round-trip rendering unless the renderer is changed to honor them. Today the inline-edit textarea can capture `\n`, but the read-only render in `SegmentText.vue` splits on `\s+` (treats all whitespace identically).
- Phase 5 — Export pipelines treat newlines very differently: CMS HTML preserves paragraph + soft breaks, DOCX collapses everything into one paragraph per segment, SRT runs an aggressive macro, VTT passes text through. Any "preserve paragraph" feature has to be defined per format.
- Phase 5 — SRT enforces a 42-char-per-line cap (`validate_final_srt`, `artifact_transformer.py:354-378`); adding hard line breaks could push the validator into rejecting otherwise-valid output.
- Phase 6 — Backend has no per-row ordering column for chat_messages or polls. Anything beyond a frontend-only sort would need a migration + API change.
- Phase 6 — Test-ids are absent on the draggable poll/chat items; any new reorder DnD tests will need IDs added (best done together with the new wiring).
- Phase 6 — `polls.opened_at_ms` and `chat_messages.sent_at_ms` are presently the ordering keys. If a manual reorder ships, the SQL `ORDER BY` clauses (`session_resources.py:506`, `588`) and the export-time `chat_by_ms = sorted(chat, key=lambda c: c.sent_at_ms or 0)` (`artifact_transformer.py:270`) must be revisited so manual order is reflected downstream.

---

## Rollback procedure for each phase

- **Phase 4 rollback** — Revert any commits touching `frontend/src/components/editor/TranscriptPane.vue` (inline edit modes), `EditorView.vue` (any new `onTimeEdit`-style handler), `app/api/segments.py` (SegmentPatch additions), `app/api/corrections.py` (new correction kind), and any migration introducing a timestamp-correction column. Because `start_ms` / `end_ms` already exist, no schema rollback is needed for the existing columns. Restart API + worker so the cached schema reflects the revert. Confirm with: `curl /v1/sessions/<id>/segments` returning the original `start_ms`/`end_ms` shape.

- **Phase 5 rollback** — Revert commits touching `frontend/src/components/editor/SegmentText.vue` (split / whitespace handling), `TranscriptPane.vue` (textarea + toolbar paragraph handling), and `app/engines/artifact_transformer.py` (`to_txt` / `to_srt` / `to_vtt` / `to_docx` / `to_cms_html` / macros). Wipe cached artifacts so re-exports regenerate without preserved breaks: `DELETE FROM artifacts WHERE session_id = '<sid>' AND kind IN ('txt','srt','vtt','docx','html','zip')` then re-export via `/v1/sessions/{id}/exports/{format}`. Confirm no behavioral change to `validate_final_srt` 42-char cap.

- **Phase 6 rollback** — Revert frontend changes to `PollsTab.vue` and `ChatTab.vue` (any new dragover/drop or sortable wiring). If a backend migration added `order_index` to either table, drop it (`ALTER TABLE polls DROP COLUMN order_index`; same for `chat_messages`) and revert `app/api/session_resources.py` ORDER BY changes. Restart API; confirm GETs return `ORDER BY sent_at_ms` / `ORDER BY opened_at_ms` ascending. If a PATCH route was added (e.g. `/v1/sessions/{id}/polls/{poll_id}/order`), remove it from `app/api/__init__.py` router registration.

---

End of Phase 1 baseline.
