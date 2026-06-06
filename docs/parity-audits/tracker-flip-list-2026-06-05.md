# Tracker Reconciliation — Flip List

**Source audit:** [qa-tracker-parity-2026-06-05.md](./qa-tracker-parity-2026-06-05.md)
**Date:** 2026-06-05
**Action for QA lead:** Flip the following tracker statuses to match what the codebase actually does.

## False negatives — flip "Off-track" / blank → "Completed"

| ID | Tracker label | Evidence | New status |
|---|---|---|---|
| SL4 | Session code in session detail | [SessionDetailView.vue:343,362,398](../../frontend/src/views/SessionDetailView.vue) | **Completed** |
| SL5 | Session code pill left & bolder | [SessionDetailView.vue:360-369](../../frontend/src/views/SessionDetailView.vue) | **Completed** |
| SL6 | Missing session code pill | Pill renders unconditionally | **Completed** |

## Confirmed-complete in code — keep "Completed" / promote ambiguous

| ID | Tracker label | Evidence | New status |
|---|---|---|---|
| E4, E5 | Video/text sync; segment edit doesn't break highlight | [TranscriptPane.vue:294-338](../../frontend/src/components/editor/TranscriptPane.vue) | **Completed** |
| E8 | Segment edit preserves slide/speaker | [segments.py:37-55](../../app/api/segments.py) | **Completed** |
| E11 | Slide # on editor pill | [TranscriptPane.vue:374](../../frontend/src/components/editor/TranscriptPane.vue) | **Completed** |
| E17 | Drag chat into editor | [ChatTab.vue:5-50](../../frontend/src/components/editor/ChatTab.vue) | **Completed** |
| E29 | Slide picker shows slide # | [SlideRail.vue:80](../../frontend/src/components/editor/SlideRail.vue) | **Completed** |
| E39 | Speaker roster panel | [SpeakerEditPanel.vue](../../frontend/src/components/editor/SpeakerEditPanel.vue) | **Completed** |
| E40 | Find/replace across all segments | [FindReplaceModal.vue](../../frontend/src/components/overlays/FindReplaceModal.vue) | **Completed** |
| G2 | Dashboard font magnify | [AppHeader.vue:91-96](../../frontend/src/components/AppHeader.vue) | **Completed** |
| G5 | Add/replace files on session | [add_to_session.py:450-824](../../app/api/add_to_session.py) | **Completed** |
| G7 | SOP stage list without "dev" | [sop_stages.ts:12-29](../../frontend/src/fixtures/sop_stages.ts) | **Completed** |
| G8 | Copy edit before medical review | Same fixture | **Completed** |
| G9 | Stage assignment / reset | [SessionDetailView.vue:148-212](../../frontend/src/views/SessionDetailView.vue) | **Completed** |
| SL3 | Delete session | [sessions.py:621-665](../../app/api/sessions.py) | **Completed** |
| U1 | Upload accommodates missing extras | [gcs_upload.py:194-196](../../app/api/gcs_upload.py) | **Completed** |
| U9 | Audio detection from video | [add_to_session.py:180](../../app/api/add_to_session.py) | **Completed** |
| U13 | Concurrent session quota enforced | [middleware/rate_limit.py:33-59](../../app/middleware/rate_limit.py) | **Completed** *(API-level cap; parallel worker bump is Phase 9b/G4)* |
| R1 | Session title not serial # on Results | [SessionDetailView.vue:49-59](../../frontend/src/views/SessionDetailView.vue) | **Completed** |

## Runtime-only — move to "Needs Repro" with steps

| ID | Tracker label | Why moved |
|---|---|---|
| E33 | Double-click switches text | Segments keyed by `seg.id` (stable in code); needs reproduction with browser + session ID |
| G10 | JepsenGrant AI tab shows STT content / `[pq]` markers / lifted strikethrough | Runtime artifact; capture with screen recording before fixing |

## Plan-covered (no separate fix needed)

| ID | Tracker label | Covered by |
|---|---|---|
| TR4 | "No autosave / lock / presence layer" | Plan Phases 1 + 2 (this PR series) |

## How to flip

Open the QA tracker (Excel / Sheets / Linear / ClickUp — wherever it lives) and update the `Rounds.vin status` column for each row above.

— *End of flip list.*
