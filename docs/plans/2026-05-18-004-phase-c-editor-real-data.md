# Phase C — Editor real-data wiring + extras2 speakers surfacing + SOP Types matrix fix

**Type:** feature wiring (frontend-heavy, small backend additions)
**Status:** awaiting approval 2026-05-18
**Working directory:** `C:\Users\JohnDean\rounds`
**Predecessor:** Phase A+B shipped 2026-05-18 (commit `b1a5f16`) — polls bridge + hashed slide accents.

---

## Why this exists

After a successful 154/154 upload (session `057b7ba8`), the editor surface looked nothing like MIC:

- Speakers tab showed `Dr. Pamela Mueller / Dr. Reggie Okafor / Jenna Hsu` — fixture names, not the parsed extras2 names.
- Chat panel: empty in some cases; Polls panel: empty.
- Slide rail uniform color (Phase B addresses this).
- Inline edit/reassign/save: every action toasts "deferred" instead of writing through.
- Settings → Types: the 17-row list shows correctly but the matrix on the right is **static** — clicking AAFV vs ARAV shows the same assignees, and "Save matrix" persists to a single key per active without ever loading per-type.

Backend already has the data + endpoints (Phase 3+4+5+6+7+9+10 shipped earlier today). The wiring is the gap.

---

## Scope (one PR, ~1-2 days)

### C.1 — Editor: switch off `@/fixtures/transcript`

Files that still `import { SLIDES, SPEAKERS, SEGMENTS, CHAT, POLLS } from '@/fixtures/transcript'`:

| File | Fixture imports it uses | Replace with |
|---|---|---|
| `views/EditorView.vue` | SLIDES, SPEAKERS, SEGMENTS | live hydrate from `sessionsApi.get(id)` + `segmentsApi.list(id)` + `speakersApi.list(id)` |
| `components/editor/TranscriptPane.vue` | SLIDES, SPEAKERS, SEGMENTS | props passed from EditorView |
| `components/editor/SlideRail.vue` | SLIDES, Slide, Segment types | props |
| `components/editor/ActiveSlideCard.vue` | SLIDES, SEGMENTS | props |
| `components/editor/AdminTab.vue` | SLIDES, SEGMENTS | props |
| `components/editor/STTPane.vue` | SEGMENTS, slideById | props |
| `components/editor/DiscrepanciesPane.vue` | SEGMENTS, SPEAKERS, slideAccent | props + `discrepancyApi.list(id)` |
| `components/editor/ChatPane.vue` (or whatever surfaces chat) | CHAT fixture | new `sessionResourcesApi.chat(id)` → `chat_messages` rows |
| `components/editor/PollsPane.vue` | POLLS fixture | new `sessionResourcesApi.polls(id)` → `polls + poll_options` joined |
| `components/editor/KPPane.vue` | fixture KP | new `sessionResourcesApi.keypoints(id)` |

`slideAccent` and `withAlpha` stay imported from fixtures — they're pure utilities, no fixture data.

### C.2 — Speakers panel + speaker chips

- Port MIC's `SpeakersPanel.vue` from `Desktop\mic\frontend\src\components\editor\SpeakersPanel.vue` (or equivalent).
- Hydrate from `GET /v1/sessions/{id}/speakers` (already exists — Phase 9).
- Each segment row's speaker chip resolves `seg.speaker_id` → name/short/color from the loaded speakers map. Fall back to "Unknown" if no row.
- For sessions where extras2 only parsed 0-2 speakers but transcript references more, allow inline `Add speaker` from the Speakers panel (`POST /v1/sessions/{id}/speakers` exists).

### C.3 — Re-enable inline saves via corrections API

Phase 4 backend (`/v1/corrections/*`) is live. Re-enable:

- `TranscriptPane.saveEdit` → `correctionsApi.apply(session_id, { type:'text_edit', segment_id, before, after })`.
- `TranscriptPane.saveReassign` → `correctionsApi.apply(session_id, { type:'slide_reassign', segment_id, before_slide_id, after_slide_id })`.
- `TranscriptPane.saveSpeaker` → `correctionsApi.apply(session_id, { type:'speaker_reassign', segment_id, before_speaker_id, after_speaker_id })`.
- `AnchorBlock.save` → `correctionsApi.apply` with `type:'anchor_*'` (existing types).
- `ActiveSlideCard.reassign` → same as slide_reassign above.
- After successful apply, locally mutate the segment so the UI reflects the change without a refetch (corrections API returns the new authoritative state).

### C.4 — Undo/Redo + Find/Replace

- Re-enable EditorView's Undo/Redo buttons. Wire to `correctionsApi.undo` / `correctionsApi.redo` (Phase 4 backend exists).
- Re-enable `FindReplaceModal.applyAll` against `correctionsApi.findReplace(session_id, { pattern, replacement, case_sensitive, whole_word })`. Remove the "disabled" banner I added in Phase 4.

### C.5 — Settings → SOP Types matrix per-Type

Three concrete bugs in `SectionTypes.vue`:

1. `matrix.value` is a single ref — clicking a different Type doesn't reload its assignees.
2. `saveMatrix` persists to `org_settings.stage_matrix.<active>` JSONB blob, but `GET /v1/settings/types/{id}/assignees` reads `stage_assignees` rows. Two storage paths, never reconciled.
3. No POST endpoint to create a Type. Frontend toasts "deferred".

Fix:

- On Type click: `await settingsApi.typeAssignees(id)` → rebuild `matrix.value` + `emails.value` from the rows. Show "(unassigned)" / unchecked for missing stages.
- On Save: `await settingsApi.setTypeAssignees(id, { stage, assignee_email, notify_email }[])`. Delete-then-bulk-insert under the hood, or upsert per stage. Add the route to `app/api/settings.py`.
- Add `POST /v1/settings/types` + `DELETE /v1/settings/types/{id}` (admin gate via `ADMIN_EMAIL`).
- Seed migration `031_seed_session_types.sql` — INSERT the 17 fixture codes/labels (`default, AAFV, ABVP, AEMV, ...`) idempotently on UNIQUE (code) conflict. So DB matches MIC out-of-box.

### C.6 — Seed people + groups

Currently `people` and `groups` tables are empty. Add `032_seed_people_and_groups.sql`:
- 10 people rows from `fixtures/settings.ts::TEAM_PEOPLE`.
- 5 groups rows from `TEAM_GROUPS`.
- Group memberships from the fixture.

All seeds idempotent on UNIQUE conflict.

### C.7 — Extras2 speaker parsing (optional / data-driven)

Rounds' extras2 parser is a verbatim MIC port — moderator + primary only. **Both repos cap at 2 speakers.** If real producer manifests include a third "guest" speaker, the parser doesn't capture it. Defer this unless we find a producer file in the wild that has more than 2 speakers — at which point we port the gap to both Rounds + MIC.

Action: search GCS for the 3 most recent extras2 files, eyeball their format, and decide whether to extend `_parse_speakers` to catch a `*Co-host = ` or `*Guest = ` line. Track as a 1-hour follow-up, not a Phase C blocker.

### C.8 — Slide accents: real-slide deterministic palette (already shipped in Phase B)

Already done in `b1a5f16`. Real slide UUIDs now hash to stable colors. No-op for Phase C — listed for completeness.

---

## Backend additions

| Endpoint | Method | Status | File |
|---|---|---|---|
| `/v1/sessions/{id}/chat` | GET | exists (verify) | `app/api/session_resources.py` |
| `/v1/sessions/{id}/polls` | GET | **NEW** — joined polls + poll_options | `app/api/session_resources.py` |
| `/v1/sessions/{id}/keypoints` | GET | exists or NEW | check `app/api/session_resources.py` |
| `/v1/settings/types` | POST | **NEW** — admin-only | `app/api/settings.py` |
| `/v1/settings/types/{id}` | DELETE | **NEW** — admin-only soft delete | `app/api/settings.py` |
| `/v1/settings/types/{id}/assignees` | PUT | **NEW** — bulk replace 8 stages | `app/api/settings.py` |
| `/v1/corrections/*` | various | shipped Phase 4 | — |

Migrations:
- `031_seed_session_types.sql` — idempotent INSERT of 17 codes.
- `032_seed_people_and_groups.sql` — idempotent INSERT of 10 people + 5 groups + memberships.

---

## Verification

1. Re-deploy. Open `https://rounds.vin/session/<id>/editor` for the Mueller session (`057b7ba8`).
2. Speaker chips show the real extras2-parsed names, not the fixture names.
3. Polls panel shows the manifest-parsed polls (Phase A bridge produced rows).
4. Chat panel shows chat_messages rows if chat file uploaded.
5. Slide rail shows varied colors (Phase B).
6. Edit a segment → save → reload page → edit persists.
7. Undo → segment reverts. Redo → returns.
8. Find/Replace → real count of replacements, persists.
9. Settings → Types → click AAFV → matrix populates from DB. Change assignee → Save → click ARAV → ARAV's matrix loads (not AAFV's).
10. Add "Test Type" → appears in list + persists across reload.
11. Permission gate: log in as a non-admin → Settings → Types Add/Remove are gated (existing patterns from Phase 3 deleted-sessions).

---

## Out of scope (still-deferred)

- Help admin system, dashboard stats endpoint, session-presence banner, AUTH_USERS hashing migration, email-template editor — same items as the prior audit's "out-of-scope" list.
- 45+ remaining MIC SOP routes — Phase 6 long-tail.
- The 14 absent MIC migrations — port alongside the features they support.

---

## Estimated effort

| Block | LOC est | Wall-clock |
|---|---|---|
| C.1 (editor fixture excision) | 200-400 | 4-6 h |
| C.2 (SpeakersPanel + chip resolution) | 150 | 1.5 h |
| C.3 (inline saves via corrections) | 100 | 1 h |
| C.4 (undo/redo + find/replace) | 60 | 30 min |
| C.5 (Types matrix per-type + endpoints) | 200 + 1 migration | 2 h |
| C.6 (people + groups seed) | 1 migration | 15 min |
| C.7 (extras2 multi-speaker survey) | 0 (deferred) | 1 h investigation later |
| Verification + smoke | — | 1 h |

**Total ~10-12 hours focused work. One PR.**
