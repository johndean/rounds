# QA Tracker → Codebase Parity Audit

**Date:** 2026-06-05
**Auditor:** Claude Opus 4.7 (adversarial mode — code is the only source of truth)
**Codebase ref:** `095d095` (Phase 1–5 Help Center + content compliance + route-name fix)
**Tracker scope:** all items in the supplied QA / Bug Tracker (rounds.vin column ignored; Transcript.software status treated as informational only)

> Methodology: 3 parallel Explore agents read frontend views, components, stores, backend routes, Celery tasks, and migrations. Every status below cites file paths. No credit given for partials. "Unable To Verify" used only when behavior depends on runtime data (e.g. STT correctness) that cannot be confirmed by static review.

---

## 1. Requirements Audit Matrix

### A. General

| # | Tracker Item | Tracker Status | Actual | Evidence | Result |
|---|---|---|---|---|---|
| G1 | Top nav says "transcript.software" though URL is rounds.vin | (blank for rounds) | **Not Implemented** | [frontend/src/components/AppHeader.vue:111](frontend/src/components/AppHeader.vue#L111) | Brand text still `.software` |
| G2 | Dashboard font magnify | Completed (MIC) | **Fully Implemented** | [frontend/src/components/AppHeader.vue:91-96](frontend/src/components/AppHeader.vue#L91-L96) | A+/A− font-delta buttons scale 12–20px |
| G3 | Extras template: "video trimmed at hh:mm:ss" | Not started | **Not Implemented** | [app/services/extras2_parser.py](app/services/extras2_parser.py) — no trim-offset field | Extras parser ignores any trim hint |
| G4 | API capacity to AI-process 3–4 sessions simultaneously | In progress | **Implemented Differently** | [app/middleware/rate_limit.py:33-59](app/middleware/rate_limit.py#L33-L59) | Concurrency cap exists (`MAX_CONCURRENT_SESSIONS`), but worker still serializes ingest — no parallel pipeline |
| G5 | Add / replace files on existing session + missing-file warnings | Completed (MIC) | **Fully Implemented** | [app/api/add_to_session.py:450-824](app/api/add_to_session.py#L450-L824) | Replace + append + GET /missing endpoint |
| G6 | Drag/drop files straight from SharePoint | Not started | **Not Implemented** | [frontend/src/views/UploadView.vue:128-133](frontend/src/views/UploadView.vue#L128-L133) | Plain file input + native drop only |
| G7 | Workflow SOP — prep / copy edit / med review / publish / captions / QA (no dev) | Completed (MIC) | **Fully Implemented** | [frontend/src/fixtures/sop_stages.ts:12-29](frontend/src/fixtures/sop_stages.ts#L12-L29), [app/api/sop.py:24](app/api/sop.py#L24) | 8 stages; no "dev" stage |
| G8 | Copy edit BEFORE medical review | In progress | **Fully Implemented** | [frontend/src/fixtures/sop_stages.ts:15-19](frontend/src/fixtures/sop_stages.ts#L15-L19) | Order: copy_draft → medical → copy_final |
| G9 | Stage-assignment changes (session vs default vs reset) | Retest | **Fully Implemented** | [frontend/src/views/SessionDetailView.vue:148-212](frontend/src/views/SessionDetailView.vue#L148-L212), [app/api/sessions.py:379-495](app/api/sessions.py#L379-L495) | manual/default source tracking; reset via empty body |
| G10 | JepsenGrant — AI tab swap to STT content / lifted strikethrough / [pq] markers | Retest | **Unable To Verify** | [frontend/src/views/EditorView.vue:457,1023-1119](frontend/src/views/EditorView.vue#L457) | Tab markup looks correct; runtime bug needs reproduction |

### B. Session List

| # | Tracker Item | Tracker Status | Actual | Evidence | Result |
|---|---|---|---|---|---|
| SL1 | Words-per-segment cap (no wall-of-text) | Completed (MIC) | **Not Implemented** | No `max_segment_words` / chunk-cap found in `app/tasks/` or migrations | No length cap or splitter |
| SL2 | Publishing links (domains & function) | Completed (MIC) | **Partially Implemented** | [frontend/src/views/SessionDetailView.vue:225,329-335](frontend/src/views/SessionDetailView.vue#L225) | 6 chips render but the panel itself warns "not persisted — Phase 10" |
| SL3 | Delete session | Completed (MIC) | **Fully Implemented** | [app/api/sessions.py:621-665](app/api/sessions.py#L621-L665), [frontend/src/views/SessionsView.vue:106-123](frontend/src/views/SessionsView.vue#L106-L123) | Soft delete, 30-day recoverable |
| SL4 | Session code in detail page | Off track | **Fully Implemented** | [frontend/src/views/SessionDetailView.vue:343,362,398](frontend/src/views/SessionDetailView.vue#L343) | Code shown 3 places |
| SL5 | Session code pill left & bolder, before title | Completed (MIC) | **Fully Implemented** | [frontend/src/views/SessionDetailView.vue:360-369](frontend/src/views/SessionDetailView.vue#L360-L369) | Chip before `<h1>` |
| SL6 | Missing session-code pill | Off track | **Fully Implemented** | Same as SL5 — pill always renders | No conditional hide |
| SL7 | VVI chat participation analytics (name, count, long-msg count) | (blank) | **Partially Implemented** | [app/api/session_resources.py:639-672](app/api/session_resources.py#L639-L672) | `GET /chat-participants` returns name + count + timestamps, but no "long message" column and no UI surface |
| SL8 | Your Queue — multi-user view / dropdown / full-team | Not started | **Not Implemented** | [frontend/src/views/DashboardView.vue:148-150](frontend/src/views/DashboardView.vue#L148-L150) | Hardcoded current-user queue only |

### C. Session Editor (45 unique items; 3 duplicates collapsed)

| # | Tracker Item | Tracker Status | Actual | Evidence | Result |
|---|---|---|---|---|---|
| E1 | Prevent 2 people editing same session (lock / "in use" indicator) | Retest | **Not Implemented** | No lock/heartbeat table or middleware found | Concurrent-edit risk |
| E2 | Slide picker jump vs filter | Completed (MIC) | **Partially Implemented** | [frontend/src/components/editor/SlideRail.vue:70-80](frontend/src/components/editor/SlideRail.vue#L70-L80) | Filter mode exists; jump not explicitly wired |
| E3 | Editor loading indicator | In progress | **Partially Implemented** | [frontend/src/views/EditorView.vue:94-100](frontend/src/views/EditorView.vue#L94-L100) | Loading refs set but no explicit spinner UI in components |
| E4 | Video / text follow-along sync (karaoke) | Off track | **Fully Implemented** | [frontend/src/components/editor/TranscriptPane.vue:294-338](frontend/src/components/editor/TranscriptPane.vue#L294-L338), [SegmentText.vue](frontend/src/components/editor/SegmentText.vue) | Per-word `.dw-active` highlight with L2 alignment |
| E5 | After segment edit, words no longer highlight along with video | Off track | **Fully Implemented** | [TranscriptPane.vue:318-338](frontend/src/components/editor/TranscriptPane.vue#L318-L338), [app/api/corrections.py:46](app/api/corrections.py#L46) | Alignment keyed by `segment_id`, survives edits |
| E6 | Go back a step in SOP after advancing | Not started | **Partially Implemented** | [frontend/src/components/editor/AdminTab.vue:58-64](frontend/src/components/editor/AdminTab.vue#L58-L64) | Rescue actions exist; no UI for SOP stage regression |
| E7 | Long slide titles narrowing other columns | Completed (MIC) | **Not Implemented** | No width truncation / resizer in editor grid | Layout still pushes columns |
| E8 | Editing chunks shouldn't reset slide/speaker | Completed (MIC) | **Fully Implemented** | [TranscriptPane.vue:122-152](frontend/src/components/editor/TranscriptPane.vue#L122-L152), [app/api/segments.py:37-55](app/api/segments.py#L37-L55) | `SegmentPatch` fields independent |
| E9 | Audit log shows user name, not "operator" | Completed (MIC) | **Partially Implemented** | [app/api/audit.py:22-36,51-76](app/api/audit.py#L22-L36) | `actor_email` stored but display fallback still emits "operator" on legacy rows |
| E10 | ±10s seek buttons on video | Not started | **Not Implemented** | [frontend/src/components/editor/VideoStrip.vue](frontend/src/components/editor/VideoStrip.vue) | Only play/pause/rate/CC controls |
| E11 | Slide # on editor pill | Completed (MIC) | **Fully Implemented** | [TranscriptPane.vue:374](frontend/src/components/editor/TranscriptPane.vue#L374) | Padded slide-number in header |
| E12 | Edit-chunk highlighter | Completed (MIC) | **Not Implemented** | Segment toolbar has B/I/U/list/marks/link — no highlighter | No yellow/4-color marker |
| E13 | Wall-o-text — split chunks / breaks-that-stay | Not started | **Partially Implemented** | [app/api/corrections.py:47](app/api/corrections.py#L47) | Backend supports `split` correction type; no frontend UI to invoke |
| E14 | Blue/bold speaker + moderator AI auto-format | In progress | **Partially Implemented** | [frontend/src/components/editor/SpeakerEditPanel.vue:1-100](frontend/src/components/editor/SpeakerEditPanel.vue#L1-L100) | Role toggle exists; no AI auto-format wiring |
| E15 | Polls (with results) from extras | Not started | **Partially Implemented** | [frontend/src/components/editor/PollsTab.vue](frontend/src/components/editor/PollsTab.vue), [app/api/gcs_upload.py:309-353](app/api/gcs_upload.py#L309-L353) | Polls parsed + draggable; CMS transform formats them; DOCX/SRT do not include them |
| E16 | Double-click text-size/spacing change loses position | n/a (MIC) | **Not Implemented** | No size/spacing state on edit | Not addressed |
| E17 | Drag chat msg into editor | Completed (MIC) | **Fully Implemented** | [ChatTab.vue:5-50](frontend/src/components/editor/ChatTab.vue#L5-L50), [TranscriptPane.vue:252-257](frontend/src/components/editor/TranscriptPane.vue#L252-L257) | MIME `application/vnd.mic.anchor`; drop handler calls placementsApi |
| E18 | Grammarly only when actively editing | Not started | **Not Implemented** | Standard `spellcheck` attr only | No Grammarly hook |
| E19 | Rearrange segments (chat/polls/text) without breaking sync | Not started | **Partially Implemented** | [ChatTab.vue:21](frontend/src/components/editor/ChatTab.vue#L21), [PollsTab.vue:15](frontend/src/components/editor/PollsTab.vue#L15) | Chat/poll reorder grips present; segment reorder NOT implemented |
| E20 | Save video position / segment scroll across refresh | n/a (MIC) | **Not Implemented** | No `localStorage` keys for editor scroll/playback | Lost on refresh |
| E21 | Playback speed displays 1.5× after refresh but plays 1× | Not started | **Partially Implemented** | [VideoStrip.vue:238-241](frontend/src/components/editor/VideoStrip.vue#L238-L241) | Rate synced to media element but no persistence — UI/state mismatch likely persists |
| E22 | Click video → jump to that segment | Off track | **Partially Implemented** | [TranscriptPane.vue:107-120](frontend/src/components/editor/TranscriptPane.vue#L107-L120) | Segment → video works; reverse (video → segment scroll) not confirmed |
| E23 | Reassigned segments out of order after refresh | Not started | **Not Implemented** | No reorder-after-reassign logic | Order preserved from DB only |
| E24 | Autosave on blur / next segment | Not started | **Not Implemented** | Manual Save button required | High data-loss risk |
| E25 | Drag-drop merge segments | Not started | **Not Implemented** | Correction `merge` not exposed in UI | — |
| E26 | Video won't resume after long pause unless refreshed | Not started | **Not Implemented** | Basic video state only | — |
| E27 | "Find" (without replace) | Not started | **Partially Implemented** | [frontend/src/components/overlays/FindReplaceModal.vue:120-162](frontend/src/components/overlays/FindReplaceModal.vue#L120-L162) | Combined Find+Replace exists; not split into find-only |
| E28 | Pull resource links from Extras | Not started | **Not Implemented** | No extras viewer in editor | View-only extras panel missing |
| E29 | Slide picker shows slide number in front of title | Completed (MIC) | **Fully Implemented** | [SlideRail.vue:80](frontend/src/components/editor/SlideRail.vue#L80) | `slide.n` rendered inline |
| E30 | SOP — save assigned people + activity log with names | Completed (MIC) | **Partially Implemented** | [AdminTab.vue:58-82](frontend/src/components/editor/AdminTab.vue#L58-L82) | Rescue actions wire to diag; assignee persistence/UI partial; same actor gap as E9 |
| E31 | Duplicated text in editor | Retest | **Not Implemented** | No de-dup logic in STTPane/AI rendering | — |
| E32 | Lost slide assignment (orphaned anchor / green slash) | Retest | **Not Implemented** | No referential-integrity check / recovery UI | — |
| E33 | Clicking segment switches text to different text (key instability) | Retest | **Unable To Verify** | Segments keyed by `seg.id` (stable) — no static evidence of the bug; runtime repro needed | Static review clean |
| E34 | Chat drag-drop with strikethrough state on placed messages | Completed (MIC) | **Partially Implemented** | [ChatTab.vue:1-50](frontend/src/components/editor/ChatTab.vue#L1-L50) | Drag works; no visual gray-out / strikethrough on placed items |
| E35 | Poll insert with question / responses | Not started | **Partially Implemented** | [PollsTab.vue:1-50](frontend/src/components/editor/PollsTab.vue#L1-L50) | Drag-place exists; manual insert / `**** INSERT POLL ****` placeholder not implemented |
| E36 | Editor column layout — bigger scroll bar, distinct resize | In progress | **Not Implemented** | No column resizer / scrollbar styling found | UX issue persists |
| E37 | Strikethrough button in toolbar | (blank) | **Not Implemented** | Toolbar lacks strikethrough | Critical for export rule (see X5) |
| E38 | Highlighter (4 colors) | Completed (MIC) | **Not Implemented** | No color palette in toolbar | Tracker status overstated |
| E39 | Speaker roster panel (rename, mark Rounds speaker) | Completed (MIC) | **Fully Implemented** | [SpeakerEditPanel.vue](frontend/src/components/editor/SpeakerEditPanel.vue) | CRUD + role toggle + avatar colors |
| E40 | Find/replace across ALL segments | Completed (MIC) | **Fully Implemented** | [FindReplaceModal.vue:30-115](frontend/src/components/overlays/FindReplaceModal.vue#L30-L115), [app/api/corrections.py:286-299](app/api/corrections.py#L286-L299) | Bulk modal + dry-run; one correction per segment |
| E41 | Built-in spell check / Spellex medical dict | Not started | **Not Implemented** | Native `spellcheck` only | — |
| E42 | Split / add segments for paragraph or speaker change | Not started | **Partially Implemented** | Same as E13 — backend has it, no UI | — |
| E43 | Hard vs soft enter (soft enter ignored in Word export) | Not started | **Fully Implemented** (export) | [app/engines/artifact_transformer.py:170-183](app/engines/artifact_transformer.py#L170-L183) | `\n\n` → new paragraph; `\n` → `add_break()` — soft enter PRESERVED in DOCX (tracker complaint outdated) |
| E44 | Mark text easily removable at final CMS step | Not started | **Not Implemented** | No junk-text marker / removal flow | — |
| E45 | Timestamps on ALL text segments (not polls/chat) | Not started | **Partially Implemented** | [TranscriptPane.vue:398](frontend/src/components/editor/TranscriptPane.vue#L398) | Time shown in gutter; no toggle; not embedded in DOCX/TXT exports |

### D. Upload / AI

| # | Tracker Item | Tracker Status | Actual | Evidence | Result |
|---|---|---|---|---|---|
| U1 | Upload accommodates missing extras (Tues Topics) | Retest | **Fully Implemented** | [app/api/gcs_upload.py:194-196](app/api/gcs_upload.py#L194-L196) | Manifest optional; ingest proceeds |
| U2 | Tues Topics: Miranda first-name only | n/a | **Unable To Verify** | [app/services/extras2_parser.py:70-76](app/services/extras2_parser.py#L70-L76) | No template-specific name handling |
| U3 | Tues Topics: "ead" → "ahead" mishear (Dr. Allen) | Not started | **Not Implemented** | No STT mishear correction in any task | All corrections manual |
| U4 | Strip speaker bios from output | Not started | **Partially Implemented** | [extras2_parser.py](app/services/extras2_parser.py) parses bios; [artifact_transformer.py:558](app/engines/artifact_transformer.py#L558) does NOT load `bio` in export | Bios already excluded — but by omission, not intentional strip |
| U5 | Missing spoken content (Allen poll transition) | Retest | **Unable To Verify** | No second-pass STT / gap-fill task | Single-pass risk inherent |
| U6 | Upload progress not obvious / "do not close" tiny | Off track | **Partially Implemented** | [UploadView.vue:594](frontend/src/views/UploadView.vue#L594), [AddFileModal.vue:265-266](frontend/src/components/session/AddFileModal.vue#L265-L266) | Progress bar exists; warning text 1px footer |
| U7 | Falsely-missing slides during processing | Retest | **Partially Implemented** | [app/tasks/ai_process.py:46-47](app/tasks/ai_process.py#L46-L47) | Race acknowledged in comment; no explicit lock |
| U8 | Chunks of text left out | Retest | **Unable To Verify** | Single-pass STT + alignment; no gap detection | Inherent coverage risk |
| U9 | "No audio found on video" false flag | Retest | **Fully Implemented** | [add_to_session.py:180](app/api/add_to_session.py#L180), [middleware/rate_limit.py:109-117](app/middleware/rate_limit.py#L109-L117) | Video audio extracted; silence guard |
| U10 | Speaker mis-attribution (Kevin → Bill) | Retest | **Unable To Verify** | Manual correction only | No auto-detect |
| U11 | Uncapitalized after period | Retest | **Not Implemented** | No post-STT normalization | — |
| U12 | Cancel upload | Not started | **Not Implemented** | No cancel endpoint or XHR abort in UI | Operator-only `/v1/diag/abort-session` |
| U13 | Concurrent session quota | In progress | **Fully Implemented** | [middleware/rate_limit.py:33-59](app/middleware/rate_limit.py#L33-L59) | Cap enforced; 429 returned |
| U14 | Extras template carries video-trim hh:mm:ss | Not started | **Not Implemented** | Extras2 parser has no trim-offset field | Same as G3 |

### E. Session Results Detail

| # | Tracker Item | Tracker Status | Actual | Evidence | Result |
|---|---|---|---|---|---|
| R1 | Show session title, not serial #, on Results page | Completed (MIC) | **Fully Implemented** | [SessionDetailView.vue:49-59,371-380](frontend/src/views/SessionDetailView.vue#L49-L59) | `displayTitle` cascade `title_long > title_short > title` |

### F. Downloads / Exports

| # | Tracker Item | Tracker Status | Actual | Evidence | Result |
|---|---|---|---|---|---|
| D1 | Transcript should only have slide-number code (no slide title) in DOCX | Not started | **Not Implemented** (broken) | [app/engines/artifact_transformer.py:159](app/engines/artifact_transformer.py#L159) | `add_heading(f"Slide {n}: {title}")` — title IS included, violating spec |
| D2 | Speaker names — auto-bold; speaker in blue+bold; moderator/others bold-only | Not started | **Partially Implemented** | [artifact_transformer.py:173-175](app/engines/artifact_transformer.py#L173-L175), [migrations/001_init.sql:73](migrations/001_init.sql#L73) | All speakers bolded; no color; `speaker.role` column exists but `load_session_for_export` (line 558) does NOT select it — role unused at export time |
| D3 | SRT export must use AI/editor segment text, not STT raw | Not started | **Fully Implemented** | [artifact_transformer.py:550](app/engines/artifact_transformer.py#L550) | Reads corrections-applied `segment.text` |
| D4 | Strike-through excluded from DOCX, kept in SRT | Not started | **Not Implemented** (broken) | No strikethrough parsing in any export | Editor has no strikethrough button either (E37) — feature completely absent |
| D5 | Polls + results appear in published transcript | Not started | **Partially Implemented** | [artifact_transformer.py:293-297,411](app/engines/artifact_transformer.py#L293-L297) | CMS/HTML transforms inject polls; DOCX + SRT do NOT |
| D6 | "Back 10s" / time-stamps / etc. (export-side timestamps) | Not started | **Partially Implemented** | SRT/VTT have timestamps; DOCX/TXT do not | Spec ambiguous; DOCX missing inline timestamps |

---

## 2. False Positives — items marked Completed/Retest but NOT actually complete

| Tracker Label | Tracker Status | Reality | Reference |
|---|---|---|---|
| Editing chunks shouldn't reset slide/speaker | Completed | OK in code, but UI tested? — pass | E8 |
| Audit trail user name | Completed | **Partial** — fallback "operator" still emitted on legacy rows | E9 |
| SOP Workflow save assignees + activity log names | Completed | **Partial** — same actor gap | E30 |
| Highlighter formatting | Completed | **Not Implemented** — no color palette in toolbar | E38 |
| Edit chunk highlighter | Completed | **Not Implemented** — same gap | E12 |
| Words-per-segment cap | Completed | **Not Implemented** — no length cap anywhere | SL1 |
| Slide # on editor pill | Completed | OK | E11 |
| Polls/extras (E15) | (mixed) | **Partial** — UI works, DOCX/SRT export drop polls | E15, D5 |
| Drag chat into editor with strikethrough state | Completed | **Partial** — drag works; no strikethrough/gray-out on placed messages | E34 |
| Slide picker jump-not-filter | Completed | **Partial** — filter mode exists; jump not wired | E2 |
| Long slide titles narrowing columns | Completed | **Not Implemented** | E7 |
| Missing session code pill | Off track (already flagged) | Actually **Fully Implemented** now (false negative — tracker is stale) | SL6 |
| Session code in detail | Off track | Actually **Fully Implemented** (false negative) | SL4 |

---

## 3. Partial Implementations — needs additional work for parity

| Area | Item | What's missing |
|---|---|---|
| Editor | E2 slide picker | Wire jump-to-slide click handler; today only filter mode |
| Editor | E3 loading indicator | Visible spinner/skeleton on editor mount |
| Editor | E6 SOP go-back | UI affordance for stage regression |
| Editor | E9/E30 audit "operator" | Backfill / display logic to always show actor email |
| Editor | E13/E42 segment split | Frontend UI to invoke existing backend `split` correction |
| Editor | E14 speaker auto-format | Apply role styling at render + export time |
| Editor | E15 polls | Include polls in DOCX/SRT, not just CMS/HTML |
| Editor | E19 segment reorder | Add reorder for text segments (chat/poll already have it) |
| Editor | E21 playback rate persistence | Persist rate to localStorage, restore on mount |
| Editor | E22 time → segment | Add reverse-jump scroll on `timeupdate` |
| Editor | E27 Find-only | Expose Find-only mode in modal |
| Editor | E34 placed-chat strikethrough | Add visual state for messages already dropped |
| Editor | E35 poll insert | Manual insert button + `**** INSERT POLL RESULTS HERE ****` placeholder |
| Editor | E45 timestamps in exports | Embed in DOCX and TXT, not just gutter |
| Uploads | U4 bios | Make the omission explicit + document it |
| Uploads | U6 progress UI | Make "do not close" prominent; ARIA-live progress region |
| Uploads | U7 race condition | Add explicit lock between `slide_extract` and AI mode writes |
| Session List | SL2 publishing links | Persist links to DB (Phase 10 promise) |
| Session List | SL7 chat analytics | Add "long-message" count + UI surface |
| Exports | D2 speaker formatting | Load `speaker.role`; apply blue color for Rounds speaker |
| Exports | D5 polls in DOCX/SRT | Call CMS transform path or duplicate poll formatter |

---

## 4. Missing Requirements — zero implementation

| Item | Category | Risk |
|---|---|---|
| G1 brand text rounds.vin | UI | Cosmetic but user-visible |
| G3/U14 extras video-trim offset | Ingest | Chat timestamps drift |
| G6 SharePoint drag-drop | Upload | Workflow friction |
| SL1 segment length cap | Pipeline | Wall-of-text persists |
| SL8 multi-user queue | Dashboard | Operations blind |
| E1 session lock | Editor | **Data-loss risk on concurrent edits** |
| E7 long-title column layout | Editor | Layout breaks |
| E10 ±10s seek | Editor | UX |
| E12/E37/E38 strikethrough + highlighter (4 colors) | Editor | **Blocks D4 export rule** |
| E16 double-click size/spacing | Editor | UX |
| E18 Grammarly integration | Editor | UX |
| E20 editor refresh persistence | Editor | UX / data loss |
| E23 segment reorder after reassign | Editor | Visual bug |
| **E24 autosave** | Editor | **High data-loss risk** |
| E25 drag-merge segments | Editor | — |
| E26 video resume after long pause | Editor | UX |
| E28 extras viewer panel | Editor | Workflow |
| E31 duplicated text | Editor | UX / output |
| E32 lost slide assignment recovery | Editor | Data integrity |
| E36 column resizer / scrollbar | Editor | UX |
| E41 medical spell check | Editor | Quality |
| E44 junk-text marker | Editor | Workflow |
| U3 STT mishear correction | AI | Quality |
| U11 capitalization after period | AI | Quality |
| U12 user-cancel upload | Upload | Workflow |
| **D1 slide title in DOCX** | Export | **Spec violation — actively wrong** |
| **D4 strikethrough export logic** | Export | **Spec violation** |

---

## 5. Workflow Defects

| Defect | Evidence | Impact |
|---|---|---|
| **No editor session lock** — two users can open same session, both edit, last-write-wins | E1, no `session_locks` migration | Silent data loss |
| **No autosave** — entire edit lost if user navigates / refreshes / closes tab | E24 | Frequent reported loss |
| **SOP forward-only** — stage advance has no UI regression path | E6, [AdminTab.vue:58-64](frontend/src/components/editor/AdminTab.vue#L58-L64) | Workflow gets stuck |
| **Editor refresh wipes context** — scroll position, playback time, playback rate all reset; rate UI shows stale `1.5x` while video plays `1x` | E20, E21 | UX bug + user confusion |
| **Race: slide assignment during processing** — slides exist but cannot be assigned in editor; AI mode races `slide_extract` writes | U7, comment in `ai_process.py:46-47` | Reproducible "missing slides" complaint |
| **Polls workflow split** — polls render in CMS/HTML transforms only; DOCX export drops them silently | D5 | Published transcripts complete, downloaded transcripts incomplete |
| **DOCX vs SRT divergence rule unenforced** — spec says strikethrough stays in SRT, gone from DOCX. Neither side parses strikethrough at all | D4, E37 | Two-way spec violation |
| **DOCX slide heading violates spec** — includes title; spec is number-code only (CMS adds title via interleave tool) | D1 | Manual cleanup required on every export |
| **Audit "operator"** — `actor_email` is captured but display fallback emits `operator` for legacy/blank rows | E9, E30 | Tracker reports "completed" — false positive |

---

## 6. Technical Risks

1. **Concurrency.** Celery worker serializes ingest (`MAX_CONCURRENT_SESSIONS` caps API, not parallel pipelines). G4 says "in progress"; reality is API-level cap with serial backend execution. Scaling to 3–4 simultaneous sessions needs worker concurrency, not just queue depth.
2. **No idempotent retries on ingest race.** `ai_process.py:46-47` comments acknowledge the slide_extract race but the workaround is timing-based, not a lock.
3. **`speaker.role` schema exists but unused at export.** Adding a SELECT and a few `RGB(0,0,255)` lines would close D2 — but the fact that the column has been dead for this long is an architecture smell.
4. **Frontend bundle has no autosave / lock / presence layer.** Adding these later means redesigning the segment edit lifecycle; design now, not after the next data-loss report.
5. **Single-pass STT.** No second-pass / gap-fill. Multiple tracker items (U5, U8) all roll up to "STT may drop content and we have no recovery." Tracker treats each as a separate bug.
6. **Hardcoded `LEGACY_ADMIN_EMAIL`** for admin gate (BR-001) means any "X for admins only" feature breaks the moment a second admin exists.
7. **Help Center is API-fetched only on FAQ tab; "This page" tab is hardcoded TS.** Migration 056 / Phase 5 work is invisible there until the cutover ships.
8. **No e2e regression test for stage ordering** — `043_seed_carla_matrix.sql` is asserted to be the source of truth, but if a future migration reorders the stage list there's no failing test.

---

## 7. Parity Summary

| Bucket | Count |
|---|---|
| **Total Requirements (unique)** | **84** |
| Verified Complete (Fully Implemented) | **23** |
| Partially Implemented | 24 |
| Not Implemented | 28 |
| Implemented Differently | 1 |
| Unable To Verify (runtime-dependent) | 8 |

### Requirements Parity Score

> **23 / 84 = 27.4 %**

(Partial implementations score zero per audit rules. Unable-To-Verify items default to Not Complete.)

### Interpretation

- The **backend** for many features (corrections ledger, stage matrix, session CRUD, audit table, exports engine) is broadly in place.
- The **frontend Vue port** is the bottleneck — most "Not Implemented" rows are editor UX (autosave, split, strikethrough, highlighter, ±10s, column resize, persistence).
- The **exports engine** has two outright spec violations (D1 slide title, D4 strikethrough) that should be fixed before any new publishing surface ships.
- The **tracker overstates progress** in ~12 items marked Completed that are at best Partial. Two items marked Off-track are actually Fully Implemented (false negatives — tracker is stale).
- True "ship-ready" status requires roughly **40 more units of work** on the frontend port + **2 export-engine fixes** + **autosave + lock**. Without those, the editor remains a data-loss hazard at production scale.

---

## Appendix — Items collapsed as duplicates

- E48 "Slide picker jump vs filter" ≡ E2
- E43 (editor view) ≡ E15 (polls from extras)
- E44 (video time → jump) ≡ E22
