# Phase 1 Baseline — SessionsView + SessionDetailView (Phase 3 scope)
Generated 2026-06-04 against tip `6df4170` (`6df4170d22fd27127cdd413e0765e1c57ef8eb37`)

> **2026-06-04 stakeholder update (after this baseline was written)**: the "chat widget" referenced in the original mandate is the **participant tally** — a list of every chat participant with the count of messages each posted, ordered by count desc. Currently shipping in EditorView's right-rail CHAT tab (e.g. `Heather Howell (she/her) — 6`, `Gaelle Roth — 5`, `Teresa Bousquet — 4`...). Stakeholder direction: this widget **should go on the details view, NOT the editor view**. Phase 3 implementation = surface the participant-tally widget on SessionDetailView. The "Questions!!??" sub-section below the tally in EditorView is editor-specific and stays in EditorView. Source-widget retention in EditorView is TBD (likely stays, since editors use it during prep).
>
> Phase 3 technical needs: (a) backend aggregation endpoint returning `[{speaker, message_count}]` per session — or piggyback on existing chat-message list + aggregate client-side, (b) a new participant-tally component mounted in SessionDetailView's `sd-widgets` row or as an additional KPI tile in the `.sd-kpis` strip.
>
> Original baseline body preserved below for reference. The "Chat Count panel does not exist in SessionsView" finding was correct — the chat surface is in EditorView, never was in SessionsView, and the destination is SessionDetailView per the new direction.

---

## SessionsView.vue
File: `C:\Users\JohnDean\rounds\frontend\src\views\SessionsView.vue` (352 lines)

### DOM section map

Line numbers from `Read` (1-indexed).

| Lines | Element | Purpose |
|---|---|---|
| 144 | `<main class="page" data-screen-label="Sessions List">` | Page root |
| 145-147 | `<div class="page-eyebrow">` | Breadcrumb "Workspace / Sessions" |
| 148-161 | `<div style="flex space-between">` | Header strip: title + page-actions |
| 150 | `<h1 class="page-title">Sessions</h1>` | Page title |
| 151 | `<p class="page-desc">` | Page description |
| 153-160 | `<div class="page-actions">` | Export CSV + New upload buttons |
| 163-180 | `<div class="kpi-row">` | **The only KPI strip on this page.** Four cards: In Workflow / Processing / Published / Total |
| 182-218 | `<div class="toolbar">` | Search + filter-chip-row + Sort select |
| 183-186 | `<div class="search">` | Search input |
| 187-209 | `<div class="filter-chip-row">` | Active stage/AI chip + filter-tab chips |
| 210-217 | `<div style="marginLeft auto">` | Sort `<select>` |
| 220-281 | `<div class="sessions-table" role="table">` | Session rows table |
| 221-229 | `<div class="sessions-table__row sessions-table__row--head">` | Column headers (Code / Session / AI Status / SOP / Segs / Words / blank) |
| 230-271 | `v-for` body rows | Each session row (clickable → routeFor(s)) |
| 272 | loading state | "Loading sessions…" |
| 273 | error state | error message |
| 274-280 | empty state | "No sessions yet — upload one" / "No sessions match this filter." |
| 284-349 | `<div class="modal-overlay" v-if="failureModal">` | Failure-detail modal (opened by clicking a row's "Failed · why?" pill) |

### Class inventory (unique, in order of first appearance)

`page`, `page-eyebrow`, `sep`, `page-title`, `page-desc`, `page-actions`, `btn`, `btn--secondary`, `btn--primary`, `kpi-row`, `kpi`, `kpi__label`, `kpi__value`, `toolbar`, `search`, `filter-chip-row`, `chip`, `chip--solid`, `btn--sm`, `sessions-table`, `sessions-table__row`, `sessions-table__row--head`, `sessions-table__row--body`, `sessions-table__code`, `sessions-table__title`, `sessions-table__sub`, `chip--red`, `chip__dot`, `chip--green`, `chip--amber`, `sessions-table__meta`, `sessions-table__updated`, `btn--ghost`, `btn--icon`, `modal-overlay`, `card`.

(Inline `:style="{ ... }"` attributes are used heavily — those are not captured here since they're not class-based.)

### data-test-id inventory

| Test-id | Line | Element |
|---|---|---|
| `sessions-export` | 154 | Export CSV button |
| `sessions-new-upload` | 157 | New upload button |
| `sessions-failure-${s.id}` | 247 | Per-row "Failed · why?" pill |
| `sessions-delete-${s.id}` | 264 | Per-row delete button |
| `failure-modal-close` | 305 | Failure modal close button |

### Interactive elements

| Line | Element | Handler | Action |
|---|---|---|---|
| 154 | `<button>` Export CSV | `@click="exportCsv"` (102-104) | `toast.push('Sessions CSV download started')` — stub |
| 157 | `<button>` New upload | `@click="router.push('/upload')"` | Navigate to /upload |
| 185 | `<input v-model="query">` | `@keyup.enter="load"` | Reload sessions list with search query |
| 196 | `<button>` × clear chip | `@click="clearStageOrAi"` (78-82) | Reset stage/ai filter and navigate to /sessions |
| 200 | `<button v-for>` filter chips | `@click="activeFilter = f.id"` | Set local filter state |
| 212 | `<select v-model="sortBy">` | n/a | Local state only (no API call — sort not yet wired) |
| 230 | `<div role="row">` session row | `@click="router.push(routeFor(s))"` (98-100) | Open editor or processing view |
| 243 | `<button>` Failed pill | `@click="showFailureReason(s, e)"` (129-139) | Call `sessionsApi.failureReason(s.id)`, open modal |
| 262 | `<button>` delete | `@click="deleteRow(s, e)"` (106-123) | Confirm → `sessionsApi.remove(s.id)` → splice row |
| 277 | `<button>` upload one | `@click="router.push('/upload')"` | Navigate to /upload |
| 290 | modal overlay | `@click.self="closeFailureModal"`, `@keydown.esc` | Close modal |
| 303 | modal close button | `@click="closeFailureModal"` | Close modal |
| 343 | `<RouterLink>` Open audit log | n/a | Navigate to `/e/${id}/audit` |
| 346 | `<button>` Close | `@click="closeFailureModal"` | Close modal |

### Backend endpoints (via `@/services/api`)

- `sessionsApi.list({ stage, ai, f })` — line 37 — used in `load()`
- `sessionsApi.remove(s.id)` — line 116 — used in `deleteRow()`
- `sessionsApi.failureReason(s.id)` — line 133 — used in `showFailureReason()`

These correspond to:
- `GET /v1/sessions` (list)
- `DELETE /v1/sessions/{id}` (remove)
- `GET /v1/sessions/{id}/failure-reason` (failureReason)

No `/v1/chat` or `/v1/sessions/{id}/chat` endpoint is called from this file. (The chat endpoint exists — see `EditorView.vue:97` `GET /v1/sessions/{id}/chat` — but is not consumed by SessionsView.)

### Permission gates

None. No `v-if="can*"` or role checks present. The page renders identically for all authenticated users. The only conditional rendering is data-driven: `v-if="s.status === 'failed'"` (line 244), `v-if="stageFilter || aiFilter"` (line 189), `v-if="loading"` / `v-else-if="error"` / `v-else-if="filtered.length === 0"` (lines 272-274), and modal `v-if="failureModal"` (line 285).

### Chat Count panel — precise location (SessionsView)

**There is no Chat Count panel in `SessionsView.vue`.**

Search evidence:
1. `Grep -n "[Cc]hat" frontend/src/views/SessionsView.vue` → **No matches found.**
2. `Grep -n "[Cc]hat[\s_-]?[Cc]ount|chatCount|chat_count"` across `frontend/src` → **No matches found.**
3. The KPI strip (lines 163-180) contains exactly four cards — In Workflow / Processing / Published / Total — none of which reference chat.
4. The sessions-table columns (lines 221-229) are: Code / Session / AI Status / SOP / Segs / Words / blank — no chat column.
5. The React SSOT `docs/port-source/sessions.jsx` likewise contains no `chat` token; its KPI strip cards are In Workflow / Awaiting Medical Review / Open Discrepancies / Published this Month (jsx lines 80-101).

The only places `chat` + a numeric display co-occur in the frontend codebase are:
- `frontend/src/views/EditorView.vue:951-952` — right-rail tab label `<span class="count">{{ CHAT.length }}</span>`.
- `frontend/src/components/editor/ChatTab.vue:69` — `<span>Chat · {{ chat.length }}</span>` in the tab header.
- `frontend/src/components/session/AddFileModal.vue:477` — conflict-resolution copy "This session already has {{ existingCount }} chat message(s)."

None of these are on the Sessions list page.

**Phase 3 implication:** the move-from source does not exist. The work cannot be executed as written without stakeholder clarification.

---

## SessionDetailView.vue
File: `C:\Users\JohnDean\rounds\frontend\src\views\SessionDetailView.vue` (726 lines)

### DOM section map

| Lines | Element | Purpose |
|---|---|---|
| 326 | `<main class="page">` | Page root, `data-screen-label="Session Detail / ${id}"` |
| 327-331 | `<div class="page-eyebrow">` | Breadcrumb Sessions / `<code>` |
| 333 | `v-if="loading"` | Loading state |
| 334 | `v-else-if="error"` | Error state |
| 335-338 | `v-else-if="!session"` | Not-found state |
| 339-713 | `<template v-else>` | Main body (everything below requires `session` to be loaded) |
| 341-378 | `<div class="sd-header">` | Header strip: status chip + code edit + title + presenter + action chips/buttons |
| 372 | `<span class="chip">` | "{{ reviewSegs }} to review" chip |
| 373 | `<span :class="alignedChipClass">` | "{{ alignedPct }}% aligned" chip |
| 374-376 | Workflow / Audit / Open Editor RouterLinks | |
| 380-630 | `<div class="sd-grid">` | Three-column grid |
| 382-424 | `<div class="sd-meta">` | LEFT col: code + title + tags + Downloads |
| 427-492 | `<div class="sd-center">` | CENTER col: KPIs + Alignment/AI-Mode + Session files |
| 428-434 | `<div class="sd-kpis">` | KPI strip (5 cards: Segments / Avg Confidence / Words / Sources / Duration) |
| 436-462 | `<div class="sd-row-2">` | Alignment card + AI Mode card side by side |
| 464-491 | `<div class="card">` Session files | Slides / Chat log / Manifest / Bios presence list |
| 495-629 | `<div class="sd-right">` | RIGHT col: Stage Assignments + Publishing Links |
| 496-614 | `<div class="card">` Stage Assignments | Header (Type select), optional "Type changed" banner, per-stage rows + inline picker |
| 616-628 | `<div class="card">` Publishing Links | Pub-link chips |
| 633-660 | `<div class="sd-timeline-card">` | Full-width timeline bar |
| 663-712 | `<div class="sd-widgets">` | Three-card row: Segment Confidence / Slide Assignment / Review Queue |
| 715-723 | `<AddFileModal>` | Session-files upload modal |

### Class inventory (unique, in order of first appearance)

`page`, `page-eyebrow`, `sep`, `sd-header`, `chip`, `chip--green`, `chip--amber`, `chip--ghost`, `sd-header__title`, `sd-header__sub`, `sd-header__actions`, `chip__dot`, `btn`, `btn--secondary`, `btn--primary`, `sd-grid`, `sd-meta`, `sd-meta__code`, `sd-meta__title`, `sd-meta__sub`, `sd-meta__tags`, `chip--blue`, `sd-meta__downloads`, `sd-meta__downloads-head`, `sd-meta__download`, `sd-meta__download-kind`, `sd-meta__download-ext`, `sd-center`, `sd-kpis`, `kpi`, `kpi__label`, `kpi__value`, `kpi__delta`, `sd-row-2`, `card`, `card__header`, `card__body`, `sd-aimode`, `sd-file`, `sd-file__icon`, `btn--sm`, `sd-right`, `sd-stage-row`, `sd-stage-row__name`, `sd-stage-row__who`, `is-faded`, `btn--ghost`, `btn--icon`, `sd-timeline-card`, `sd-timeline-card__head`, `sd-timeline`, `sd-timeline__seg`, `sd-timeline__axis`, `sd-widgets`, `sd-confrow`, `sd-slideassign`, `sd-reviewrow`.

### data-test-id inventory

| Test-id (template) | Line | Element |
|---|---|---|
| `sd-download-${ext}` | 415 | Per-download button (`.docx` / `.srt` / `.txt` / `.zip`) |
| `sd-file-${name.replace(/\s/g, '_')}` | 486 | Per-file Add/Update button (`sd-file-Slides`, `sd-file-Chat_log`, `sd-file-Session_manifest`, `sd-file-Speaker_bios`) |
| `sd-reset-${st.id}` | 565 | Per-stage Reset to default button |
| `sd-reassign-${st.id}` | 571 | Per-stage Reassign button (opens inline picker) |
| `sd-pub-${p.replace(/\s/g, '_')}` | 623 | Per-publishing-link chip |

### Interactive elements

| Line | Element | Handler | Action |
|---|---|---|---|
| 348-355 | `<SessionTextEdit>` code | `@save="onCodeSaved"` (59-62) | Update local session.code |
| 359-367 | `<SessionTextEdit>` title | `@save="onTitleSaved('title_long', v)"` (55-58) | Update local session.title_long |
| 374 | `<RouterLink>` Workflow | n/a | `/e/${id}/sop` |
| 375 | `<RouterLink>` Audit | n/a | `/e/${id}/audit` |
| 376 | `<RouterLink>` Open Editor | n/a | `/e/${id}` |
| 384-391 | `<SessionTextEdit>` code (meta) | `@save="onCodeSaved"` | duplicate of header code edit |
| 394-402 | `<SessionTextEdit>` title (meta) | `@save="onTitleSaved('title_long', v)"` | duplicate of header title edit |
| 411-422 | per-download `<button>` | `@click="downloadFile(d.ext)"` (286-291) | Demoted warn toast (not yet wired) |
| 484-488 | per-file Add/Update `<button>` | `@click="fileAction(f)"` (306-309) | Open AddFileModal with type |
| 499-509 | Type picker `<select>` | `@change="onTypePickerChange"` (122-137) | `sessionsApi.update(id, { session_type_id })` |
| 525-529 | Apply Type defaults `<button>` | `@click="applyTypeDefaults"` (139-159) | Confirm → `sessionsApi.applyTypeDefaults` → refetch |
| 530 | Dismiss banner `<button>` | `@click="dismissTypeBanner"` (161-163) | Clear pendingTypeId |
| 561-568 | per-stage Reset `<button>` | `@click="resetStageToDefault(st.id)"` (187-203) | `sessionsApi.setStageAssignee(id, stage, {})` |
| 569-574 | per-stage Reassign `<button>` | `@click="openReassign(st.id)"` (165-167) | Toggle picker |
| 589-596 | per-person `<button>` | `@click="selectAssignee(st.id, { person_id })"` (169-185) | `sessionsApi.setStageAssignee` |
| 602-609 | per-group `<button>` | `@click="selectAssignee(st.id, { group_id })"` | `sessionsApi.setStageAssignee` |
| 619-626 | per-pub-link chip `<button>` | `@click="pubLink(p)"` (316-322) | Warn toast (not yet wired) |

### Backend endpoints

Loaded in `load()` (lines 86-113):
- `sessionsApi.get(id)` → `GET /v1/sessions/{id}`
- `http<SourceRow[]>('/v1/sessions/{id}/sources')` → `GET /v1/sessions/{id}/sources`
- `http<SlideRow[]>('/v1/sessions/{id}/slides')` → `GET /v1/sessions/{id}/slides`
- `segmentsApi.list(id)` → `GET /v1/sessions/{id}/segments`
- `sessionsApi.stageAssignees(id)` → `GET /v1/sessions/{id}/stage-assignees`
- `settingsApi.types()` → `GET /v1/settings/types`
- `settingsApi.people()` → `GET /v1/settings/people`
- `settingsApi.groups()` → `GET /v1/settings/groups`

Mutations:
- `sessionsApi.update(id, { session_type_id })` (line 131)
- `sessionsApi.applyTypeDefaults(id, typeId)` (line 150)
- `sessionsApi.setStageAssignee(id, stageId, body)` (lines 173, 192)

**No `/v1/sessions/{id}/chat` call is made by this file.** Chat presence is inferred indirectly from `sources.some(s => s.role === 'chat')` via the `hasFile('chat')` helper (line 243), which only produces a "PRESENT"/"MISSING" chip — not a count.

### Permission gates

None. Same posture as SessionsView — no role checks anywhere in the file. Conditional rendering is purely data-driven (`v-if="loading"`, `v-if="pendingTypeId"`, `v-if="reassignStageOpen === st.id"`, etc.).

### Chat Count landing-zone candidates

Since the source page has no Chat Count panel to move, these candidates are best read as "if a Chat Count card needs to be **added** to SessionDetailView, here are the highest-parity insertion points":

- **Candidate A — extend the existing `.sd-kpis` strip (line 428-434).**
  Insert a new `<div class="kpi">` after the existing five (Segments / Avg Confidence / Words / Sources / Duration). Use the same `kpi` / `kpi__label` / `kpi__value` / `kpi__delta` skeleton as its siblings. This is the highest-parity option visually — it is literally a "count" displayed in the same row as Segments and Words counts.
  Adjacent test-ids: none on the strip itself; this is between the `sd-header` block ending line 378 and the `sd-row-2` Alignment/AI-Mode card pair starting line 436.
  Rationale: zero new CSS, zero new layout decisions, identical typographic weight to the other counts. The page is already responsible for fetching every count it shows; adding one more KPI is the minimum-diff change.
  Data source: would require a new `GET /v1/sessions/{id}/chat` (or `chat-count`) fetch in `load()`, or expose `chat_message_count` on the SessionSummary payload returned by `sessionsApi.get(id)`. The `chat_message_count` token already exists as a template variable in `EmailBuilder.vue:247,263` — backend-side it is computed by counting `ChatMessage` rows; whether the API surfaces it on the session detail payload is a backend-only check (see § Risk notes).

- **Candidate B — augment the "Chat log" row inside the "Session files — attention" card (line 474, between `data-test-id="sd-file-Slides"` (Update/Add at line 486 row 1) and `sd-file-Session_manifest` (row 3)).**
  Specifically: extend the existing Chat-log `sd-file` row (lines 474-489 with `f.role === 'chat'`) so its description sub-line (line 482) includes the count, or add a chip beside the PRESENT/MISSING chip on line 479-481.
  Rationale: contextually attached to the chat asset, no new card. Limitation: it lives inside an iterator over `sessionFiles`, so the change is a per-row override, not a clean separate panel.

- **Candidate C — new dedicated card inserted into the `.sd-widgets` row (lines 663-712) as a fourth card after Review Queue.**
  Add a `<div class="card">` mirroring the Segment Confidence / Slide Assignment / Review Queue siblings. Useful if the Chat Count needs to be visually equal-weight with other "transcript widgets," and if a future expansion includes a breakdown (e.g., placed vs unplaced chat). Currently the row uses a 3-column grid in CSS — adding a 4th card would require a CSS grid-template tweak in `app.css`. **This violates the no-other-modifications rule unless the grid auto-flows.**

### Other notable observations

- The `sources` array is the only source of chat-presence truth on this page today. Counting chat messages requires either (a) a new endpoint or (b) extending `SessionSummary` to include `chat_message_count`. The backend already has a `ChatMessage` model and a `chat_parser.py` engine (per `Grep`), so the count is derivable.
- All chips on this page use the canonical `.chip` / `.chip--green` / `.chip--amber` / `.chip--ghost` / `.chip--blue` styles from `app.css`. No new color tokens needed.

---

## Risk notes for Phase 3 implementation

1. **No source panel to move.** As documented above, the "Chat Count" panel does not exist in `SessionsView.vue`. Phase 3 cannot be executed verbatim. Required clarification: did the stakeholder mean (a) one of the four existing KPI cards (In Workflow / Processing / Published / Total), (b) the `<span class="count">{{ CHAT.length }}</span>` badge on `EditorView.vue:952`, or (c) an entirely new panel they want added? Without an answer, executing Phase 3 will produce a different artifact than they expect.
2. **Backend data plumbing not yet on the wire.** The SessionDetailView `load()` already fans out 8 parallel fetches. Adding chat-count would either require a 9th fetch (`GET /v1/sessions/{id}/chat` then `.length`, wasteful on the wire) or a backend change to project `chat_message_count` onto `SessionSummary` / `GET /v1/sessions/{id}`. Both options touch surfaces outside the Vue files.
3. **`sd-kpis` row already at 5 cards.** Adding a 6th may push the row to wrap on smaller viewports. The current CSS grid behavior should be eyeballed against `https://rounds.vin/prototype.html` before assuming it auto-flows cleanly.
4. **Test-id parity with React SSOT.** React `sessions.jsx` defines no chat-count test-id; if Phase 3 introduces one, it diverges from the SSOT. Per CLAUDE.md "THE REACT JSX IS THE SINGLE SOURCE OF TRUTH" — adding UI not present in the JSX needs the JSX updated first, or the change documented as an intentional Vue-side addition with stakeholder approval.
5. **`SessionTextEdit` duplication.** SessionDetailView already renders code+title twice (lines 348-356 in `sd-header` AND 384-402 in `sd-meta`). This is existing behavior, but worth flagging: any Phase 3 cleanup that "tidies" the page risks deleting one of these surfaces. Phase 3 must explicitly preserve both edit surfaces.

---

## Rollback procedure for Phase 3

Assuming Phase 3 lands as one or more commits on a feature branch:

```bash
# 1. Identify the Phase 3 commits
cd C:\Users\JohnDean\rounds
git log --oneline 6df4170..HEAD -- frontend/src/views/SessionsView.vue frontend/src/views/SessionDetailView.vue

# 2. Verify only the expected files were touched
git diff 6df4170..HEAD --stat -- frontend/src/views/SessionsView.vue frontend/src/views/SessionDetailView.vue

# 3. Revert by commit (preferred — keeps history)
git revert <phase3-commit-sha>            # repeat for each commit in reverse order
git push origin HEAD
git push production HEAD                  # both remotes per CLAUDE.md two-remote rule

# 4. OR hard-reset the two files to the Phase 1 baseline (use only if reverts conflict)
git checkout 6df4170 -- frontend/src/views/SessionsView.vue frontend/src/views/SessionDetailView.vue
git commit -m "revert(sessions): roll Phase 3 chat-count move back to 6df4170 baseline"
git push origin HEAD && git push production HEAD

# 5. Verify rollback
git diff 6df4170 -- frontend/src/views/SessionsView.vue frontend/src/views/SessionDetailView.vue
# (should print nothing)

# 6. Verify production tip rebuilds cleanly
cd frontend && npm run build
# (should exit 0 with no vue-tsc errors)

# 7. Visual parity check
# Open https://rounds.vin/sessions and https://rounds.vin/s/<known-session-id>
# Side-by-side diff vs https://rounds.vin/prototype.html
# Sessions KPI strip must show: In Workflow / Processing / Published / Total
# SessionDetail KPI strip must show: Segments / Avg Confidence / Words / Sources / Duration
# No Chat-related KPI or panel on either page after rollback
```

Acceptance gate: `git diff 6df4170 -- frontend/src/views/SessionsView.vue frontend/src/views/SessionDetailView.vue` prints zero output AND the production build exits zero AND the visual diff against the prototype shows no regressions on either page.
