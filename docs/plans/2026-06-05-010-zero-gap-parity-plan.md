# Rounds.vin — Zero-Gap Parity Plan

> **Source audit:** [docs/parity-audits/qa-tracker-parity-2026-06-05.md](../parity-audits/qa-tracker-parity-2026-06-05.md) — 84 unique tracker items + 8 technical risks. Current parity score: **27.4 %**.
>
> **Hard constraints (non-negotiable):**
> - **Zero performance impact** on any hot path (editor load, segment list, dashboard counts, video playback).
> - **Zero risk to stability** — every phase ships behind a feature flag where it touches live editor surfaces, every DB change is forward-only (ADR-011), every Celery change is idempotent, every export change runs in a v2 dual-path until verified.
> - **Locked weights** (`CELERY_*`, `FUSION_*`, `ALIGN_*`, `IIL_*`) are NEVER touched without explicit user authorization. Affected phase is gated and called out.
> - **Single rollback per phase:** revert the frontend bundle OR flip a feature flag OR run a forward-only NULL-default migration.

This plan is the synthesized winner from a 17-agent workflow (`wgwy30uh7`) that ran three alternative phase structures (Risk-First, Dependency-First, User-Impact-First) through nine adversarial reviews (stability + performance + sequencing lenses on each) and a completeness critic. The winner is **User-Impact-First** with **4 critic grafts + 30 reviewer corrections** folded in.

- **Date:** 2026-06-05
- **Author:** johndean@vin.com + Claude Opus 4.7
- **Working tree:** `C:\Users\JohnDean\rounds\` (commit `095d095`)
- **Total scope:** 14 phases (0 → 10b), ~62–80 working days

---

## Table of phases

| Phase | Name | Audit IDs | Days |
|---|---|---|---|
| **0** | Tracker reconciliation (no code) | 22 already-done IDs | 0.5 |
| **1** | Concurrent-edit lock + spinner + brand | E1, E3, G1 | 3–4 |
| **1.5** | Ingest idempotency primitives (GRAFT) | U7 prep, TR2 prep | 2–3 |
| **2** | Autosave | E24 | 3–4 |
| **2a** | Ledger ↔ segments.text materialization (NEW from review) | Blocker for Phase 6 | 1–2 |
| **3** | Video + nav pain | E10, E20, E21, E22 | 2–3 |
| **3.5** | Split/merge backend executor (GRAFT) | E13, E25, E42 backend | 3–4 |
| **4** | Edit-time felt polish | E2, E7, E12, E13/E25/E42 UI, E16, E27, E37, E38 | 4–5 |
| **5** | Speaker correctness end-to-end | D2, E14, TR3 | 2 |
| **6** | Downloads parity (dual-path v2) | D1, D4, D5, D6, E15, E43, E45 | 3–4 |
| **7** | Ingest correctness | G3, SL1, U2, U3, U4, U11, U14 | 5–7 |
| **8** | Editor long-tail | E6, E9, E19, E23, E28, E30, E32, E34, E35, E36, E44 | 8–10 |
| **9a** | Platform/FE-additive | E26, SL2, SL7, SL8, TR6, TR7, TR8, U6, U10, U12, U13 | 6–8 |
| **9b** | Platform/locked-weights (authorization-gated) | G4, TR1, TR2, U5, U7, U8 | 8–10 |
| **10a** | Dedup repro (ship-now) | E31 | 1–2 |
| **10b** | Vendor-blocked bucket | E18, E41, G6 | as-availability |

> **Total mapped audit items:** 84/84 + 8/8 technical risks. **Zero unmapped.**

---

## Section 1 — Phase definitions

### Phase 0 — Tracker reconciliation (no code change)

**Goal.** Flip the 22 tracker IDs that the audit confirms are already-implemented or duplicative. Removes false-negative noise so the team isn't planning code work that's already shipped.

| Tracker ID | Audit finding | Action |
|---|---|---|
| E4, E5 | karaoke highlight already works (`TranscriptPane.vue:294-338`) | Flip to Completed |
| E8 | segment edit preserves slide/speaker (`segments.py:37-55`) | Flip to Completed |
| E11 | slide # pill on editor exists (`TranscriptPane.vue:374`) | Flip to Completed |
| E17 | drag chat into editor works (`ChatTab.vue:5-50`) | Flip to Completed |
| E29 | slide picker shows # (`SlideRail.vue:80`) | Flip to Completed |
| E33 | "double-click switches text" — not reproducible; keys stable | Mark Cannot Reproduce |
| E39 | speaker roster panel (`SpeakerEditPanel.vue`) | Flip to Completed |
| E40 | find/replace across all segments (`FindReplaceModal.vue`) | Flip to Completed |
| G2 | dashboard font magnify works (`AppHeader.vue:91-96`) | Flip to Completed |
| G5 | add/replace files on session (`add_to_session.py:450-824`) | Flip to Completed |
| G7 | SOP stage list without "dev" (`sop_stages.ts:12-29`) | Flip to Completed |
| G8 | copy-edit before medical review | Flip to Completed |
| G9 | stage assignment per-session/default/reset | Flip to Completed |
| G10 | JepsenGrant AI/STT swap — runtime; not reproducible in static review | Move to Needs Repro |
| SL3 | delete session works (`sessions.py:621-665`) | Flip to Completed |
| SL4, SL5, SL6 | session code pill on detail view | Flip from Off-track to Completed (tracker false-negative) |
| U1 | upload accommodates missing extras (`gcs_upload.py:194-196`) | Flip to Completed |
| U9 | audio detection from video (`add_to_session.py:180`) | Flip to Completed |
| U13 | concurrent quota enforced (`middleware/rate_limit.py:33-59`) | Flip to Completed (note: API-level cap, NOT parallel workers — see G4/Phase 9b) |
| R1 | session title not serial # on Results (`SessionDetailView.vue:49-59`) | Flip to Completed |
| TR4 | "no autosave/lock/presence layer" — covered by Phases 1+2 design itself | Mark Plan-Covered |

**Deliverable.** A one-line PR to whatever holds the tracker (or a flip-list email to the QA lead). No code changes.

**Rollback.** Status flips are reversible by the tracker tool.

---

### Phase 1 — Concurrent-edit lock + visible loading + brand fix

**Audit IDs:** E1, E3, G1
**Days:** 3–4

**Goal.** Eliminate silent overwrite between two operators on the same session. Lay autosave's foundation (lock + heartbeat) without yet enabling autosave. Replace the embarrassing brand string. Make initial load feel responsive.

**Critical correction from review (fail-CLOSED, not fail-open):**

The original UIFER plan said "if lock service is unreachable, fall back to write-allowed." Three reviewers flagged this as the exact silent-overwrite bug Phase 1 is supposed to prevent. **Lock failures MUST fail closed:** EditorView shows a yellow banner "Lock service unavailable, edits disabled — retry," and the lock endpoint runs on the same Postgres connection pool the editor already uses (no new infra dependency to fail).

**Files / migrations.**
- `migrations/057_session_locks.sql` — `(session_id PK, user_email, acquired_at, heartbeat_at, expires_at)` + index on `expires_at`.
- `app/api/locks.py` — `POST /v1/sessions/{id}/lock/acquire`, `POST /lock/heartbeat`, `POST /lock/release`, `GET /lock/holder`.
- `app/api/sessions.py` — `GET /v1/sessions/{id}` payload extended with `lock: { holder, expires_at }` (avoids a separate poll — perf-reviewer recommendation).
- `frontend/src/composables/useSessionLock.ts` — fail-closed gating; Page Visibility API to pause heartbeat when `document.hidden`; `beforeunload` + `visibilitychange` explicit release.
- `frontend/src/views/EditorView.vue` — banner + read-only mode.
- `frontend/src/components/shared/EditorSkeleton.vue` — skeleton/spinner rendered while existing loading refs are true.
- `frontend/src/components/AppHeader.vue:111` — brand text → "rounds.vin".

**Lock TTL:** 90 s (3 missed heartbeats). Operator-facing "force-take lock" admin button surfaces after the lock has gone stale; logged to audit_events.

**Stability mitigations.**
- Lock is advisory at the DB level (never blocks writes); enforcement is in the API layer on the autosave path (Phase 2).
- Heartbeat is a single `INSERT … ON CONFLICT UPDATE` on a new table — no existing read path touches it.
- Skeleton renders only while existing loading refs are true (no new fetch).
- Brand string is a literal swap.
- `beforeunload` + `visibilitychange` listeners explicitly release the lock so the next operator doesn't wait 90 s.

**Perf mitigations.**
- Heartbeat conditional on `!document.hidden` → most tabs idle out cheaply.
- Lock READ piggybacks on the existing `/v1/sessions/{id}` payload (the editor already fetches it on mount). Banner refresh uses the existing `useWsSubscriber` channel (LISTEN/NOTIFY for `lock_changed` on `session_locks`), not a new poll. **Zero new polling overhead.**
- New `session_locks` table is single-row-per-session, indexed on `expires_at` for stale-lock sweep (cron is in Phase 1.5).

**Verification.**
- Two browser sessions in different accounts: second one gets the read-only banner; closing the first releases the lock within heartbeat TTL.
- Force-take button works after 90 s stale.
- Kill `app/api/locks.py` in test → editor shows yellow banner, autosave gate (Phase 2) blocks writes.
- Playwright: skeleton renders before `/sessions/{id}` responds.
- Visual diff: header brand reads "rounds.vin".

**Rollback.** Revert frontend bundle (lock UI inert, banner gone). Leave `session_locks` table (unused tables cost nothing at runtime). Brand string revert is one line. Skeleton is purely additive.

---

### Phase 1.5 — Ingest idempotency primitives (GRAFT 1 from critic)

**Audit IDs:** prep work for U7, TR2 (formally closed in Phase 9b)
**Days:** 2–3

**Goal.** Build the advisory-lock helpers + dedup-aware upsert primitives that Phases 2, 3.5, 4, 7, and 9b all need. Closes the Phase 2 autosave race risk + Phase 4 split/merge race risk + Phase 9b worker-concurrency safety prerequisites.

**Why now (before Phase 2):** Phase 2's autosave fires `/v1/corrections` on every blur — corrections.py:188 calls `_truncate_redo_tail` on every append, which silently destroys redo history if autosave fires a no-op `text_edit`. The fix needs primitives: a "skip if no-op" guard + a `pg_try_advisory_xact_lock` around append/truncate.

**Pre-migration dedup audit.** Run a one-shot script against prod that catalogs every existing INSERT path in `app/tasks/*` and its `ON CONFLICT` strategy. Reuse the audit format from `migrations/020+022+034` commit messages (per stability reviewer). **No code change** — informational baseline so Phase 7 + Phase 9b unique-index choices don't repeat the 022 mistake.

**Files / migrations.**
- `app/db/locks.py` — `pg_try_advisory_lock(key)` / `pg_advisory_unlock(key)` helpers. Per-stage scope, not per-session, not per-transaction. Released at task end.
- `app/api/corrections.py` — add `_is_noop(payload)` guard; skip `_truncate_redo_tail` when new_text == effective_text.
- `app/tasks/ingest.py`, `app/tasks/slide_extract.py`, `app/tasks/ai_process.py` — wrap idempotent sections in `pg_try_advisory_lock` keyed by `(session_id, stage_name)`.
- `scripts/audit_insert_paths.py` (new, runs once) — catalog every INSERT in app/tasks/ and emit a markdown report to `docs/research/insert-path-audit-2026-06-N.md`.

**No new migrations** (advisory locks are session-state, not schema).

**Stability mitigations.** Advisory locks are advisory (`pg_try_advisory_lock` returns false on conflict; caller decides). All wrappers are no-op when the lock is already held by the same connection. Audit script is read-only.

**Perf mitigations.** Advisory locks add ~50 µs per task; per-stage scope means concurrent sessions are NOT serialized on the same key.

**Verification.**
- Existing test suite stays green.
- Chaos: kill `ai_process` mid-run, retry → no duplicate segment rows.
- Audit script runs cleanly + writes report.

**Rollback.** Revert the wrapping `with pg_try_advisory_lock(...)` blocks. Removes the helper. No schema change.

---

### Phase 2 — Autosave (never lose another keystroke)

**Audit IDs:** E24
**Days:** 3–4

**Goal.** Make manual Save optional. Every edit autosaves on actual change events (not on blur with no-op) with a visible "saved"/"saving" indicator per segment. Refresh restores the saved state.

**Critical corrections from review.**
1. **Anti-no-op gate:** autosave only appends a correction if `new_text != effective_text`. Otherwise `_truncate_redo_tail` would silently delete undone edits.
2. **Use the soft-save endpoint, not raw corrections:** a new `POST /v1/segments/{id}/soft_save` updates an in-memory draft + persists via a NEW endpoint that does NOT call `_truncate_redo_tail`; flush to ledger only on explicit Save or session close. Keeps redo intact.
3. **Per-segment indicator using `shallowRef<Map>`** + manual `triggerRef`, NOT a reactive Map (would re-render all 600 segments on every save and kill the karaoke watcher).
4. **Compaction:** when N consecutive `text_edit`s on the same segment by the same `applied_by` within M seconds (default 3), collapse to one row at flush time. Or rate-limit autosave append to ≥3 s. Prevents `correction_ledger` row explosion on 3 hr lectures.
5. **Lock gate (Phase 1 dependency):** autosave does NOT fire when the lock check fails or shows another holder.

**Files.**
- `app/api/segments.py` — `POST /v1/segments/{id}/soft_save` (draft update; does not append to ledger).
- `app/api/corrections.py` — compaction helper + `_is_noop` guard (from Phase 1.5).
- `frontend/src/components/editor/SegmentText.vue` — debounce 400 ms + on-blur + on-segment-switch hooks calling soft_save.
- `frontend/src/composables/useAutosave.ts` — orchestrates; reads lock state; shows red "unsaved" badge on failure.
- `frontend/src/components/editor/TranscriptPane.vue` — per-segment status via `shallowRef<Map>` + `triggerRef`.

**Stability mitigations.** Reuses existing PATCH shape. Failure shows red unsaved badge instead of swallowing. Lock check (Phase 1) prevents autosave when read-only. Anti-no-op + compaction protect redo + ledger integrity.

**Perf mitigations.** Debounce + per-segment payload; no polling; no whole-list re-render thanks to `shallowRef`. Compaction keeps `correction_ledger` row count bounded.

**Verification.**
- Edit + blur → soft_save fires once.
- Three edits within 400 ms → one fire.
- Edit + switch segment → flush immediately.
- Refresh → state restored.
- Edit + undo + click another segment → original undone edit STILL undoable (anti-no-op verified).
- Network drop → red badge.
- Two-tab race: second tab shows read-only banner; autosave disabled.
- Perf: type 100 chars + blur in a 600-segment session; assert no long tasks > 50 ms in Playwright.

**Rollback.** `VITE_AUTOSAVE_ENABLED=false` reverts to manual Save only. Backend `soft_save` endpoint stays dormant.

---

### Phase 2a — Ledger ↔ segments.text materialization (NEW from stability review)

**Audit IDs:** Pre-requisite for Phase 6
**Days:** 1–2

**Goal.** Reconcile the silent divergence between corrections ledger replay (what the editor sees) and `segments.text` (what `artifact_transformer.load_session_for_export` reads). Without this, Phase 2 autosave makes the divergence 10–100× worse and Phase 6's "fix every CMS handoff defect" silently ships pre-autosave text.

**Decision (pick one, document in plan PR):**
- **Option A — Materialize on commit.** On every `corrections.append` (including `soft_save → flush`), update `segments.text` in the same transaction. Pros: simple, every reader sees the latest. Cons: small additional write per correction.
- **Option B — Exporter replays ledger.** `load_session_for_export` consumes the ledger like the editor does. Pros: single source of truth (ledger). Cons: every export pays replay cost.

**Recommendation: Option A.** Smaller blast radius; export perf budget stays small.

**Files.**
- `app/api/corrections.py` — add `UPDATE segments SET text = :new_text WHERE id = :seg_id` inside the transaction that appends.
- New test: `tests/test_autosave_export_parity.py` — autosave 3 edits → download DOCX → contains the autosaved text.

**Stability mitigations.** Single UPDATE per commit; transaction-safe. Existing `segments.text` writers (`ai_process.py`, `normalize.py`) unchanged. Materialization is forward-compatible with future ledger replay.

**Perf mitigations.** Adds one indexed UPDATE per correction (PK lookup). With Phase 2's compaction, the rate stays bounded.

**Verification.** New golden test passes. Existing export goldens unchanged. Two-tab autosave race resolves to the last-write-wins state in segments.text.

**Rollback.** Revert the materialization UPDATE; exporter continues reading whatever was last written by ingest. Existing behavior preserved.

---

### Phase 3 — Video + navigation pain

**Audit IDs:** E10 (±10 s), E20 (refresh persistence), E21 (rate persistence), E22 (video → segment)
**Days:** 2–3

**Goal.** Pure-frontend, pure-additive. ±10 s seek with J/L keyboard shortcuts; reverse-jump as video plays; refresh restores scroll + active segment + currentTime + rate.

**Critical corrections from review.**
1. **Reverse-jump uses an explicit segment-time index** (`Float32Array` of start times + binary search, O(log n) per tick, <0.1 ms for 600 segs). Not an implicit walk.
2. **scrollTo({behavior: 'auto'})** for follow-mode (smooth only for explicit user clicks) + coalesce to rAF + skip if scrollTop delta < threshold (avoid no-op layout thrashes).
3. **localStorage keyed by `(session_id, tabRole)`** where tabRole = writer vs reader from Phase 1 lock state. Skip persistence in read-only tabs (otherwise reader's scroll clobbers writer's on next refresh).
4. **Schema-versioned localStorage** so a stale read-only tab can't corrupt the writer's record.
5. **Explicit `follow video` UI toggle** so the user can override the heuristic on weird touchpad input.

**Files.**
- `frontend/src/components/editor/VideoStrip.vue` — ±10 s buttons + J/L shortcuts.
- `frontend/src/components/editor/TranscriptPane.vue` — reverse-jump scroll, `isUserScrolling` guard.
- `frontend/src/composables/useEditorPersistence.ts` — `localStorage` writer with role-keyed schema-versioned blob.
- `frontend/src/composables/useSegmentTimeIndex.ts` — binary search.
- `frontend/src/views/EditorView.vue` — restore on mount.

**Stability mitigations.** localStorage only — no server state, no migration. Reverse-jump uses `isUserScrolling` guard (debounced 300 ms after last manual scroll). Rate restore happens once on mount before play. If localStorage is full/disabled, all features silently no-op.

**Perf mitigations.** Reverse-jump throttled to 250 ms via rAF, only when video is playing. Debounced 500 ms localStorage writes (single small JSON blob per session). No new network calls. No DOM scans on timeupdate — uses the new segment-time index.

**Verification.**
- ±10 / J / L shortcut keys move video 10 s.
- Play video → list scrolls; manual scroll stops auto-scroll until next segment click.
- Refresh → exact same scroll + active segment + currentTime + rate.
- Read-only tab does NOT persist scroll.
- Test on touchpad + mouse wheel + keyboard + screen reader.

**Rollback.** `VITE_EDITOR_PERSISTENCE=false` flag; ±10 s buttons additive — revert template block.

---

### Phase 3.5 — Split/merge backend executor (GRAFT 4 from critic)

**Audit IDs:** E13 backend, E25 backend, E42 backend
**Days:** 3–4

**Goal.** Build the real server-side split/merge handlers. Today `corrections.py:47` only WHITELISTS `'split'` / `'merge'` as types; no handler actually creates two `segments` rows from one or merges two into one. Without this, Phase 4's split UI button is a silent no-op.

**Files.**
- `app/services/segment_split.py` — split executor: insert new `segments` row with halved time range + new `content_hash`, redistribute `word_alignment` rows by ts boundary, decide `kp_annotations` policy (clone to both halves with operator confirmation; default = drop on the half that loses the anchor).
- `app/services/segment_merge.py` — merge executor: concat text, sum durations, delete second row, rebuild `word_alignment`.
- `app/api/corrections.py` — dispatch `'split'`/`'merge'` to the executors instead of just appending to the ledger.
- `tests/test_segment_split.py`, `tests/test_segment_merge.py` — fixtures including `word_alignment` integrity + `kp_annotations` policy + `content_hash` uniqueness via existing `(session_id, content_hash)` unique index (mig 020).

**Stability mitigations.**
- Idempotent via `pg_try_advisory_lock` from Phase 1.5 (key = `(session_id, "split_merge")`).
- All writes in a single transaction; rollback on any failure.
- Uses existing `(session_id, content_hash)` uniqueness from mig 020 — no new unique index needed.
- `kp_annotations` policy is explicit and documented; tests assert behavior.

**Perf mitigations.** One transaction per split/merge; word_alignment redistribution is O(words in split segment) ≈ <100 rows; negligible.

**Verification.** Tests for split/merge happy path, kp_annotations policy, word_alignment timing redistribution, content_hash uniqueness, ledger trail. Hand-test in dev: split + re-export DOCX → two rows.

**Rollback.** Revert `app/services/segment_*.py` and the dispatch in `corrections.py`. Executor disappears; the type whitelist stays (Phase 4 UI gated separately).

---

### Phase 4 — Edit-time felt polish

**Audit IDs:** E2, E7, E12, E13/E25/E42 UI, E16, E27, E37, E38
**Days:** 4–5

**Goal.** Kill wall-of-text pain (split UI on top of Phase 3.5 executor), add toolbar marks operators reach for hourly (strikethrough, 4-color highlighter, find-only), stop losing scroll on font-size change, fix slide-picker jump-vs-filter, fix long-title columns.

**Critical corrections from review.**
1. **Marks live in a sibling table, NOT inline in `segments.text`.** Reviewer flagged that Phase 7 normalization regexes will corrupt inline `~~strike~~` tokens, and ledger replay of old `text_edit`s deterministically loses marks. Schema: `segment_marks(segment_id, kind, start_offset, end_offset, color)`. Render layer composes them. Keeps `segments.text` pristine for ingest normalization, exporters, search, and ledger replay.
2. **Marks must wrap whole `.dw` word spans, not split them.** Karaoke watcher needs `data-ws` / `data-we` attributes intact. Order regex pass BEFORE word-span tokenization. Add test: a segment with `the [strike]quick[/strike] brown fox` still highlights word-by-word during playback.
3. **Export strip ships in Phase 4 itself (GRAFT 3 from critic).** Don't wait for Phase 6. From the moment users can author a mark, exports strip it (or render it correctly). Even though marks now live in a sibling table — not inline tokens — the export pipeline still needs to read the marks table to apply the strikethrough = exclude rule.
4. **Find-only uses a dedicated read-only endpoint** that does NOT touch the ledger pointer. Debounce client-side to ≥250 ms. Prevents fast-scan-during-typing from running `MAX(seq) + segment replay` per keystroke.

**Files / migrations.**
- `migrations/058_segment_marks.sql` — sibling table `(segment_id FK, kind TEXT, start_offset INT, end_offset INT, color TEXT, created_by TEXT, created_at TIMESTAMPTZ)` + index on `segment_id`.
- `app/api/segments.py` — `POST /v1/segments/{id}/marks`, `DELETE /v1/segments/{id}/marks/{mark_id}`.
- `app/api/corrections.py` — read-only `POST /v1/corrections/find-dry-run` that scans `segments.text` without touching ledger pointer.
- `app/engines/artifact_transformer.py` — load `segment_marks` in `load_session_for_export`; consume to skip strikethrough runs in DOCX (D4 export rule) and render highlight color (E38 follow-on).
- `frontend/src/components/editor/SegmentText.vue` — toolbar with strikethrough + 4-color highlighter; marks applied via mark endpoints, rendered at paint time.
- `frontend/src/components/overlays/SegmentEditModal.vue` — same toolbar wiring.
- `frontend/src/components/overlays/FindReplaceModal.vue` — find-only mode toggle.
- `frontend/src/components/editor/SlideRail.vue` — jump-vs-filter mode toggle (E2).
- `frontend/src/styles/app.css` — slide-title `max-width + text-overflow:ellipsis` + tooltip (E7).
- `frontend/src/views/EditorView.vue` — scroll anchor preservation on font-size change (E16).
- `frontend/src/components/editor/SegmentText.vue` — split-here right-click + keystroke → calls `POST /v1/corrections` with `correction_type='split'` (dispatched by Phase 3.5 executor).

**Stability mitigations.**
- Marks table is forward-only; if export consumer doesn't read it (rollback), marks are simply not rendered — text is still pristine.
- Split UI rides on Phase 3.5 backend executor; no silent no-op possible.
- Find-only uses dedicated endpoint — cannot touch ledger.
- All toolbar additions are additive UI; revert template block to rollback.

**Perf mitigations.**
- Marks render at paint time (one extra `segment_marks` lookup per segment in `load_session_for_export`; LEFT JOIN once, not per-row).
- `segment_marks` typically zero-rows-per-segment for most sessions; cost amortized via index.
- Find-only debounced 250 ms; dry-run endpoint is read-only.
- Slide-rail ellipsis is CSS-only.
- Font-size scroll anchor is one `getBoundingClientRect` read.

**Verification.**
- Cursor in middle of segment → Split → two segments with correct timing (uses Phase 3.5 executor).
- Toolbar strike/highlight toggle persists across reload via `segment_marks` table.
- Karaoke playback: words still highlight word-by-word inside a marked range.
- Find-only mode hides replace controls; no ledger pointer movement.
- Slide click in jump mode scrolls TranscriptPane to first segment for slide.
- A+/A− → scroll preserved within 1 px.
- Long slide title truncates with tooltip.

**Rollback.** `VITE_EDITOR_MARKS=false` reverts toolbar buttons. Marks table dormant. Jump/filter toggle defaults to filter. Ellipsis CSS is one rule.

---

### Phase 5 — Speaker correctness end-to-end (data was always there)

**Audit IDs:** D2, E14, TR3
**Days:** 2

**Goal.** Thread `speaker.role` from DB through render + export. One root cause closes three audit items.

**Correction from review:** the rollback is multi-file, not a one-line revert — `SessionForExport` is a typed dataclass consumed by `to_docx` / `to_srt` / `to_vtt` / `to_cms_html` / `to_txt` + every golden. Add `role` to the dataclass as optional; consumers default to bold-only when None.

**Files.**
- `app/engines/artifact_transformer.py:558` — add `speaker.role` to the SELECT.
- `app/engines/artifact_transformer.py` — `SessionForExport.role: str | None = None`; consumers branch on role for color.
- `frontend/src/components/editor/TranscriptPane.vue` — apply role-based color class.
- `frontend/src/components/editor/SegmentText.vue` — same.
- `frontend/src/components/editor/SpeakerEditPanel.vue` — already has the toggle UI; verify wiring posts the role correctly.

**Stability mitigations.** `role` is optional on the dataclass; consumers ignore unknown values. If role is NULL (every existing row today is NULL or `'Instructor'`), falls back to current bold-only behavior. Export golden tests refreshed to cover both branches.

**Perf mitigations.** Zero — same row count, one extra TEXT field per speaker in the existing JOIN result. No new queries. Color set via inline run formatting on the existing `add_run` call.

**Verification.**
- Mark a speaker as Rounds speaker → name shows blue+bold in editor.
- Download DOCX → `RGBColor(0,0,255)` on speaker run.
- New unit test asserts color set when role matches; unset otherwise.

**Rollback.** Revert the SELECT addition + color branch + dataclass field across consumers (multi-file revert, acknowledged in this section).

---

### Phase 6 — Downloads parity (dual-path v2, per critic graft 2)

**Audit IDs:** D1, D4, D5, D6, E15 (composes), E43 (verify+flip), E45
**Days:** 3–4

**Goal.** Fix every export-side defect blocking CMS handoff. Apply critic GRAFT 2: don't refactor `artifact_transformer.to_docx` in place. Instead introduce `to_docx_v2` (and `to_srt_v2`, etc.) behind `EXPORT_PARITY_V2` flag with PER-RULE sub-flags (`EXPORT_D1`, `EXPORT_D2`, `EXPORT_D4`, `EXPORT_D5`, `EXPORT_D6`). Closes the stability concern that one bad rule (likely D5 polls) forces rollback of all five.

**Critical corrections from review.**
1. **CMS coordination BEFORE default-on flip.** Add `?format_version=v1|v2` param that CMS pins explicitly. Default-on only after CMS confirms v2 ingest works on a known-bad fixture set including each session_type × (polls only / chat only / both / neither).
2. **Define the canary set explicitly** (not "one canary session" — too vague).
3. **Strikethrough strip is scoped to `segment_marks` table entries** (Phase 4) — does NOT touch legacy literal `~~ish~~` typos in old session text.
4. **Phase 2a (ledger materialization) is a hard dependency.** Phase 6 cannot ship until Phase 2a lands.
5. **Export perf golden:** 600-segment fixture must export in <2 s; cache compiled regex at module level.
6. **Timestamps gated behind `?ts=1`** with explicit default-on flip after sampling user preference (DOCX file size grows ~7 KB unzipped per 600 paragraphs).
7. **Polls injection only fires when `session.polls` is non-empty** (already loaded by `load_session_for_export`).

**Files.**
- `app/engines/artifact_transformer.py` — add `to_docx_v2`, `to_srt_v2`, `to_vtt_v2`, `to_txt_v2` alongside existing functions.
- `app/api/exports.py` — accept `?format_version` and per-rule flags; dispatch to v1 or v2.
- `app/config.py` — `EXPORT_PARITY_V2: bool`, `EXPORT_D1/D2/D4/D5/D6: bool`.
- `tests/test_export_goldens.py` — v2 goldens for: (a) slide heading == `Slide N` no title, (b) timestamp prefix on every text paragraph, (c) strikethrough mark removed from DOCX kept in SRT, (d) poll renders between slide segments in DOCX and SRT, (e) hard/soft enter preserved (verify E43 is already-correct).
- `frontend/src/components/editor/DownloadMenu.vue` — append `?format_version=v2` once CMS confirms.

**Stability mitigations.** Pure transform functions; no I/O. Golden tests added BEFORE flag flips default-on. Polls injection only fires when `session.polls` non-empty. Strikethrough consumption reads `segment_marks` table from Phase 4 (no false positives on legacy `~~text~~` typos). v1 path remains accessible until tracker confirms.

**Perf mitigations.** Same iteration over segments/polls; one extra `segment_marks` JOIN; one extra regex per segment for legacy support; one extra run per paragraph for timestamps. Module-level compiled regexes. Export perf golden enforces <2 s for 600-segment fixture.

**Verification.**
- Golden DOCX/TXT/SRT/VTT fixtures for each of D1, D4, D5, D6, E15, E45.
- CMS partner runs v2 outputs through their pipeline; signs off per session_type + per (polls/chat) combination.
- Hard/soft enter test asserts current behavior is correct (E43 verify+flip).
- Perf golden: 600-segment session exports <2 s.
- Default-on flip is a separate tiny PR after CMS sign-off.

**Rollback.** Per-rule flag flip. Per-format-version param keeps v1 alive indefinitely as a kill-switch.

---

### Phase 7 — Ingest correctness

**Audit IDs:** G3, SL1, U2, U3, U4, U11, U14
**Days:** 5–7

**Goal.** Pipeline-side defects that bite on every new upload but never on existing sessions. All post-STT additive passes behind feature flags; locked `CELERY_*/FUSION_*/ALIGN_*` weights are **NOT** touched.

**Critical corrections from review.**
1. **`video_trim_offset` goes on `sessions`, NOT `session_templates`** — trim is a per-session property (each session has its own template-extras2 "Video trimmed at HH:MM:SS"), not per-template.
2. **Word-cap splitter runs BEFORE alignment in the Celery chain** (verify chain in `celery_app.py`) — otherwise `word_alignment` writes orphan rows keyed by old `segment_id`s.
3. **Apply trim offset only on first ingest.** On `/v1/diag/reingest`, read the stored offset from `sessions` and skip re-application (chat that's been operator-reordered would re-shuffle otherwise).
4. **Bound mishear dictionary to <10 K entries** — compile a single combined alternation regex at startup.
5. **Word-cap respects sentence boundaries** + preserves word-level timing (use existing word-level STT output).
6. **Move `(session_id, slide_number)` unique-index migration from Phase 9b into Phase 7** so the integrity guard is live while ingest behavior changes. Do NOT add `(session_id, seq)` unique index — contradicts mig 022 (uniqueness already on `(session_id, content_hash)` per mig 020).

**Files / migrations.**
- `migrations/059_sessions_video_trim_offset.sql` — `ALTER TABLE sessions ADD COLUMN video_trim_offset_ms INTEGER NULL`.
- `migrations/060_unique_slide_per_session.sql` — `CREATE UNIQUE INDEX CONCURRENTLY idx_slides_session_number ON slides(session_id, slide_number)` (run pre-migration dedup script from Phase 1.5 first).
- `app/services/stt_normalize.py` — mishear dict (YAML at `config/stt_mishears.yaml`) + capitalization regex.
- `app/services/extras2_parser.py` — extract `Video trimmed at HH:MM:SS` → ms.
- `app/tasks/ai_process.py`, `app/tasks/transcribe.py` — wire normalize pass post-STT pre-segment-commit.
- `app/tasks/ingest.py` — word-cap splitter inserted in Celery chain BEFORE alignment.
- `app/tasks/ingest_chat.py` — apply trim offset to `sent_at_ms` ONLY on first ingest; check `sessions.video_trim_offset_ms` IS NULL or matches stored value.
- `app/config.py` — `NORMALIZE_STT_MISHEARS`, `NORMALIZE_CAPITALIZATION`, `SEGMENT_WORD_CAP_ENABLED` (default cap = 80), `TRIM_OFFSET_ENABLED`.
- `app/engines/artifact_transformer.py` — `tests/test_export_no_bios.py` confirms bios are not loaded (U4: codify existing behavior as a test).
- `config/stt_mishears.yaml` — initial entries: `{ead: ahead, BVI: VVI}` (extend as audit U3 examples surface).

**Stability mitigations.**
- All passes are post-STT, idempotent, applied BEFORE segment commit so a bug produces no DB writes.
- Each behind a config flag → flip OFF reverts to current behavior for new uploads.
- Existing sessions unaffected — passes only run on first ingest.
- Bios stripped by omission today; new test codifies + protects against regression.
- Migration 060 built CONCURRENTLY; pre-dedup audit (from Phase 1.5) catches conflicts BEFORE the build runs.
- Unique-index correction: do NOT use `NOT VALID` (Postgres rejects it on unique indexes — perf reviewer correction).

**Perf mitigations.**
- Normalize pass is O(n) regex per segment; microseconds.
- Word-cap splitter runs once per session at ingest.
- Trim subtraction is one int op per row.
- Single combined alternation regex compiled at startup.

**Verification.**
- Fixture: 1000-word raw STT segment → cap triggers → alignment runs on split segments → no orphan `word_alignment` rows.
- `ead` → `ahead`; `foo. bar.` → `Foo. Bar.`.
- Miranda first-name fixture → Speaker row created.
- Trim-offset fixture → chat shifted N seconds.
- Reingest the trim-offset fixture → chat order preserved (offset not re-applied).
- `test_export_no_bios.py` green.
- Migration 060 builds without failure on prod-shaped data.

**Rollback.** Config flags flip; new sessions revert to current behavior. Existing sessions never touched. Migration 060 is forward-only; if the dedup audit revealed conflicts that re-emerge, drop the index (CONCURRENTLY).

---

### Phase 8 — Editor long-tail

**Audit IDs:** E6 (SOP regress), E9 (audit names), E19 (segment reorder), E23 (reassign reorder), E28 (extras viewer), E30 (SOP assignee save), E32 (orphaned slides), E34 (chat-placed strike), E35 (poll insert), E36 (column resizer), E44 (junk marker)
**Days:** 8–10

**Goal.** Close every remaining editor parity item now that lock + autosave + marks + downloads are solid. Each feature independently rollback-able.

**Critical corrections from review.**
1. **Reorder via `display_order` must update the exporter's `ORDER BY` atomically.** `artifact_transformer.load_session_for_export` uses `ORDER BY seg.seq ASC` — without exporter change, editor shows reordered list but DOCX/SRT show the original order. Update `ORDER BY` in the same PR as the reorder feature.
2. **Backfill `display_order = start_ms` for ALL segments on first reorder** of a session — no NULL/non-NULL interleave; functional index becomes unnecessary.
3. **`ExtrasTab` lazy-load** via `defineAsyncComponent + onActivated`, NOT `onMounted` — avoids extra GET on every editor mount.
4. **Orphan detection (E32) runs lazily** (when operator opens a "segments with issues" panel) OR precomputed on ingest into `sessions.has_orphans BOOLEAN`. Not per-editor-load.
5. **SOP regress (E6) requires admin.** Phase 9a TR6 (multi-admin) must land first OR ship E6 as single-admin-only with a note. **Decision: move TR6 into Phase 8** since several Phase 8 features (regress, audit naming attribution) implicitly need it — pulls one small additive migration forward.
6. **Audit display ternary needs `SELECT DISTINCT applied_by FROM audit_events`** first to confirm current values; if it's literal `'operator'`, the ternary doesn't trigger on a NULL check — backfill or extend.
7. **`display_order` migration with functional index** OR `display_order = start_ms` backfill on first reorder write (latter is simpler).
8. **Removable column nullable** + ignored by export when flag off.

**Files / migrations.**
- `migrations/061_segment_display_order.sql` — `ALTER TABLE segments ADD COLUMN display_order INTEGER NULL` + on first reorder, the server backfills `display_order = start_ms` for all segments in the session, then sets the dragged segment.
- `migrations/062_segment_removable.sql` — `ALTER TABLE segments ADD COLUMN is_removable BOOLEAN NULL`.
- `migrations/063_sessions_has_orphans.sql` — `ALTER TABLE sessions ADD COLUMN has_orphans BOOLEAN NULL` + ingest sets it.
- `migrations/064_auth_users_role_admin_seed.sql` — `UPDATE auth_users SET role='admin' WHERE email IN (...)` — pure data change using existing `auth_users.role` column from mig 045 (per critic correction; no new column).
- `app/api/sop.py` — `POST /v1/sessions/{id}/sop/regress` endpoint.
- `app/api/audit.py` — display ternary `actor_email ?? 'system'` (post `SELECT DISTINCT` confirmation).
- `app/api/segments.py` — reorder accepts `display_order` patch; first reorder backfills all siblings.
- `app/api/segments.py` — merge endpoint (uses Phase 3.5 executor).
- `app/api/session_resources.py` — orphan list endpoint (read-only flagging).
- `app/api/corrections.py` — wire removable flag to export pipeline filter.
- `app/security/roles.py` — read `auth_users.role` instead of hardcoded `LEGACY_ADMIN_EMAIL`; fall back if NULL.
- `frontend/src/components/editor/AdminTab.vue` — SOP regress button + confirm modal.
- `frontend/src/components/editor/ChatTab.vue` — placed-message gray-out + strike state.
- `frontend/src/components/editor/PollsTab.vue` — Insert-at-cursor button.
- `frontend/src/components/editor/ExtrasTab.vue` — NEW (lazy-loaded).
- `frontend/src/components/editor/TranscriptPane.vue` — reorder drag, junk-text toggle.
- `frontend/src/composables/useResizableColumns.ts` — column dividers persist to localStorage.
- `frontend/src/components/audit/AuditTabInline.vue` — display ternary; `'system'` fallback.
- `app/engines/artifact_transformer.py` — `ORDER BY COALESCE(display_order, start_ms) ASC` to match editor; filter `is_removable=true` rows out of CMS export.

**Stability mitigations.**
- Each feature isolated behind `VITE_EDITOR_*` flag.
- New columns nullable with safe defaults.
- Reorder backfill makes `display_order` consistent on first touch.
- Orphan recovery is read-only flagging — fix is operator-initiated.
- SOP regress requires confirm modal + writes `audit_events`.
- Multi-admin migration is pure data; canonical `is_admin()` helper updated to read `auth_users.role`.

**Perf mitigations.**
- Reorder is one PATCH per drop (after first-touch backfill).
- Merge uses Phase 3.5 executor.
- ExtrasTab lazy via `defineAsyncComponent + onActivated`.
- Orphan detection lazy OR precomputed; no per-editor-load query.
- Column resize persists to localStorage.
- Audit display change is in-memory.

**Verification.**
- Drag segment up/down, refresh → order preserved AND export shows new order.
- Merge two segments → `word_alignment` intact.
- ExtrasTab fetches only on tab open.
- Toggle removable → segment vanishes from CMS export only.
- Audit log shows `jane@vin.com` on new rows, `system` on legacy NULL rows.
- SOP regress button rolls stage back + audits.
- Multi-admin: add a second admin via SQL → can access admin routes without `LEGACY_ADMIN_EMAIL` match.
- Chat dropped items appear struck.
- Insert poll places block at cursor.
- Column drag persists.

**Rollback.** Per-feature flags. Migrations are nullable column additions — drop columns CONCURRENTLY if needed. Multi-admin migration: `UPDATE auth_users SET role=NULL` reverts.

---

### Phase 9a — Platform / FE-additive (no locked-weights gate)

**Audit IDs:** E26 (signed-URL refresh), SL2 (publishing links), SL7 (chat analytics), SL8 (team queue), TR6 (multi-admin — already in Phase 8 per correction), TR7/TR8 (help-center cutover), U6 (upload banner), U10 (mis-attribution surfacing), U12 (cancel upload)
**Days:** 6–8

**Goal.** Ship every audit item that does NOT touch locked weights, so they're not blocked behind authorization. Split from monolithic Phase 9 per sequencing reviewer.

**Critical corrections from review.**
1. **SL2 publishing links is a frontend store hydration bug, NOT a schema bug.** `sessions.publishing_links` already exists as JSONB (mig 011). DELETE the proposed parallel table. Fix the Pinia store to hydrate from the existing column.
2. **TR6 multi-admin migration uses existing `auth_users.role` column** (mig 045) — already added in Phase 8.
3. **`ThisPageTab` cutover adds ETag + 304 support** on `/v1/help/articles?page=<route>`. Cache in Pinia for session lifetime, not per-mount. Strip `version_history` from list response.
4. **Dashboard team queue (SL8) requires `(assigned_user_id, status)` composite index** — verify dashboard p95 stays <100 ms.
5. **Signed-URL refresh (E26) triggers on `stalled` or `error` event** (not on `timeupdate` gap which would fire on every scrub). Single retry per event; N = 45 min for 1 h TTL.
6. **Cancel upload (U12) requires session in `'uploading'` state** — endpoint validates state before action.

**Files / migrations.**
- `migrations/065_dashboard_assignee_status_index.sql` — `CREATE INDEX CONCURRENTLY idx_sessions_assignee_status ON sessions(assigned_user_id, status)`.
- `app/api/sessions.py` — `POST /v1/sessions/{id}/cancel` (only if `status='uploading'`); releases rate-limit slot.
- `app/api/dashboard.py` — team-queue dropdown query (uses new composite index).
- `app/api/session_resources.py` — chat-participants extended with `long_message_count` column.
- `app/api/help.py` — ETag + 304 on `/v1/help/articles?page=<route>`; strip `version_history` from list.
- `app/services/gcs.py` — `refresh_signed_url(session_id)` helper.
- `app/security/roles.py` — finalize `is_admin()` switch from `LEGACY_ADMIN_EMAIL` to `auth_users.role` (Phase 8 added the data; Phase 9a removes the legacy check).
- `frontend/src/views/UploadView.vue` — prominent "do not close this tab" banner + per-file progress bar + Cancel button.
- `frontend/src/views/DashboardView.vue` — Me / User / Team queue dropdown.
- `frontend/src/views/SessionDetailView.vue` — publishing links hydrate from `session.publishing_links` JSONB.
- `frontend/src/stores/sessions.ts` — store hydration fix.
- `frontend/src/components/helpcenter/ThisPageTab.vue` (or wherever the panel lives) — fetch from `/v1/help/articles?page=<route>` with ETag.
- `frontend/src/components/editor/VideoStrip.vue` — `stalled`/`error` → refresh signed URL + single retry.
- `frontend/src/components/upload/UploadProgressBanner.vue` — new component.

**Stability mitigations.**
- Each feature behind per-feature flag (`VITE_DASHBOARD_TEAM_QUEUE`, `VITE_HELP_THIS_PAGE_API`, etc.).
- Cancel endpoint returns 409 when not in `uploading` state.
- Publishing links fix is read-only-fix-in-store.
- Signed-URL refresh has explicit single-retry to avoid loops.
- New index built CONCURRENTLY.

**Perf mitigations.**
- Composite index on `(assigned_user_id, status)` makes team-queue query fast.
- ETag on help articles → 304 on unchanged.
- Pinia caches help articles per session lifetime.
- Signed-URL refresh adds one GCS call only after >N-min stall event (not per-tick).
- No new polls.

**Verification.**
- Add a second admin via SQL → can access admin routes; `LEGACY_ADMIN_EMAIL` check removed.
- Publishing links survive refresh.
- Dashboard queue dropdown shows other operators; p95 < 100 ms.
- ThisPageTab pulls live from API with ETag.
- Long pause → video resumes after one extra GCS call.
- Upload Cancel button → DELETE returns 200 → rate-limit slot released.
- New chat analytics column shows long-message count.

**Rollback.** Per-feature flags. Composite index drop is reversible.

---

### Phase 9b — Platform / locked-weights (REQUIRES USER AUTHORIZATION)

**Audit IDs:** G4 (parallel AI processing), TR1 (concurrency), TR2 (idempotent retries — formalized), U5/U8 (single-pass STT → gap-fill), U7 (slide-extract race)
**Days:** 8–10

> **⚠ This phase modifies `tests/test_health.py::test_locked_weights_match_audit`.** Per CLAUDE.md "Backend boundaries — do NOT change without explicit user authorization." Phase 9a above ships without this gate; Phase 9b is the only phase that requires the gate.

**Goal.** Bump worker concurrency safely (with RAM ceiling + GCP-quota verification), ship STT gap-fill second-pass, formalize advisory locks across all ingest paths, fix the slide-extract race.

**Critical corrections from review.**
1. **Confirm Rounds has its own GCP project / Gemini key / Vertex quota BEFORE bumping concurrency** (per CLAUDE.md, Rounds currently shares MIC's quota — 4× concurrency = 4× pressure on a quota that's not Rounds's).
2. **Ramp 1× → 2× → 4× over 1-week observation windows.** Stage rollout.
3. **Add RAM ceiling check to perf test** — RSS during 4× load < worker_limit × 0.7.
4. **Advisory lock scope:** prefer `pg_try_advisory_lock` (session-scoped) not `pg_try_advisory_xact_lock` (transaction-scoped). Use per-stage locks not per-session, released at task end. Add metric: lock wait time p99 per task.
5. **Gap-fill chains AFTER existing ingest success** — never blocks the main pipeline. Triggers only when `uncovered > GAP_THRESHOLD_MS` (default 5000).
6. **Do NOT add `(session_id, seq)` unique index** (already added in Phase 7 as the slide-only variant; segment uniqueness lives on `(session_id, content_hash)` per mig 020).
7. **Slide-extract race (U7):** wrap in `pg_try_advisory_lock(session_id, 'slide_extract')`; if held, requeue with backoff.

**Files / migrations.**
- `app/tasks/stt_gapfill.py` — NEW second-pass STT on gap-detected segments.
- `app/tasks/slide_extract.py` — wrapped in advisory lock.
- `app/tasks/ai_process.py` — wrapped in advisory lock; uses Phase 1.5 primitives.
- `app/tasks/celery_app.py` — chain `stt_gapfill` AFTER `ingest` success.
- `app/config.py` — `STT_GAPFILL_ENABLED`, `STT_GAP_THRESHOLD_MS`, `CELERY_WORKER_CONCURRENCY`.
- `tests/test_health.py` — update `test_locked_weights_match_audit` with new `CELERY_WORKER_CONCURRENCY` value (REQUIRES USER AUTHORIZATION).
- `tests/perf/test_4x_concurrent.py` — baseline; RSS ceiling check.
- `tests/test_idempotent_ingest.py` — chaos tests for advisory-lock-protected paths.

**Stability mitigations.**
- Advisory locks: `pg_try_advisory_lock` (never blocks existing writers).
- Gap-fill chains AFTER existing success; never blocks main pipeline.
- Concurrency bump requires test_locked_weights update with user authorization.
- Ramp 1× → 2× → 4× with 1-week observation windows.
- Quota check before any concurrency bump.

**Perf mitigations.**
- Advisory locks add ~50 µs per task; per-stage scope means concurrent sessions are NOT serialized.
- Gap-fill only fires when `uncovered > GAP_THRESHOLD_MS` — most sessions skip it.
- Worker concurrency bump IS the perf win; measured via `tests/perf/test_4x_concurrent.py`.

**Verification.**
- Concurrent test: kick 4 uploads → 4 worker slots active; wall time ≈ max(single).
- Chaos: kill `ai_process` mid-run, retry → no duplicate rows.
- Gap fixture: 30 s silence → gap-fill task runs → segments now cover it.
- RAM ceiling check passes at 4× concurrency.
- Lock wait p99 < 100 ms per task.
- `test_health.py::test_locked_weights_match_audit` updated AND user signs off.

**Rollback.** `STT_GAPFILL_ENABLED=false`. `CELERY_WORKER_CONCURRENCY` env-driven (revert env var). Advisory-lock wrappers are no-op when lock not contended; remove the `with` blocks to fully revert.

---

### Phase 10a — Dedup repro (ship-now)

**Audit IDs:** E31
**Days:** 1–2

**Goal.** Capture the duplicated-text bug in a reproducible test fixture; ship a targeted fix scoped to the repro.

**Files.**
- `tests/fixtures/dedup_repro.json` — minimal fixture that triggers duplicates.
- `app/tasks/ai_process.py` OR `app/tasks/transcribe.py` — targeted fix (dedup pass keyed by `(start_ms, content_hash)` at merge boundary).
- `tests/test_dedup.py` — pre-fix produces dupes; post-fix doesn't.

**Verification.** Fixture proves the fix.

**Rollback.** Revert the dedup pass.

---

### Phase 10b — Vendor-blocked bucket (parallel, as availability permits)

**Audit IDs:** E18 (Grammarly), E41 (Spellex), G6 (SharePoint)
**Days:** as-availability

**Goal.** Final cleanup; can be deferred or descoped.

**Critical correction from review:** **SharePoint (G6) requires Microsoft Graph OAuth.** Rounds doesn't currently store Graph tokens. Either ship Graph OAuth as multi-day work OR descope SharePoint drag entirely to a follow-up plan. Do NOT ship a feature that always errors.

**Files (if all three proceed).**
- `frontend/src/components/editor/SegmentText.vue` — Grammarly attribute toggle on edit mode only.
- `docs/decisions/spellex-evaluation.md` — vendor decision doc.
- `frontend/src/services/sharepointResolver.ts` + Graph OAuth flow + token storage (multi-day) OR a `docs/decisions/sharepoint-descoped.md`.

**Stability mitigations.** All purely additive. Dedup fix lives behind a regression test (covered in 10a). Spellex stays disabled by default until licensing approved.

**Perf mitigations.** Grammarly attribute is a class toggle. SharePoint resolution happens at drop time only.

**Verification.** Dedup test passes. Grammarly underlines appear only while editing. SharePoint either fully works (if Graph OAuth shipped) or is descoped with a written decision.

**Rollback.** Each item independently revertible.

---

## Section 2 — Migrations omitted from original UIFER (per critic + reviewers)

Three migrations from the original UIFER design were **DELETED** because they would have created new sources of truth that drift from existing schema:

| Originally proposed | Status | Reason |
|---|---|---|
| `NNN_unique_indexes.sql` with `UNIQUE (session_id, seq)` | **DELETED** | Contradicts mig 022 (uniqueness already on `(session_id, content_hash)` per mig 020). Reused that existing index. |
| `NNN_publishing_links.sql` (new table) | **DELETED** | `sessions.publishing_links` already exists as JSONB (mig 011). SL2 is a frontend store hydration bug. |
| `NNN_auth_users_is_admin.sql` (new column) | **DELETED** | `auth_users.role TEXT` already exists (mig 045). Multi-admin is a pure data UPDATE (Phase 8 `mig 064`). |

---

## Section 3 — Cross-cutting verification matrix

| Phase | Backend test | Frontend test | Manual / canary |
|---|---|---|---|
| 0 | — | — | Tracker flips visible |
| 1 | `test_session_locks.py` (acquire, heartbeat, release, force-take, fail-closed) | Playwright two-tab read-only banner | Production smoke: brand reads rounds.vin |
| 1.5 | `test_advisory_locks.py` chaos test | — | `scripts/audit_insert_paths.py` writes report |
| 2 | `test_autosave_endpoint.py` + anti-no-op test | Playwright 100-char + blur on 600-seg fixture, assert no long task >50 ms | Edit + refresh round-trip |
| 2a | `test_autosave_export_parity.py` (autosave → DOCX contains autosaved text) | — | Operator hand-test |
| 3 | — | Playwright keyboard shortcuts + scroll restore | Touchpad + mouse wheel + keyboard + screen reader |
| 3.5 | `test_segment_split.py`, `test_segment_merge.py` | — | Hand-split in dev, re-export DOCX |
| 4 | `test_segment_marks.py` (CRUD + export consumption) | Karaoke-with-mark Playwright spec | A+/A− scroll preservation |
| 5 | `test_export_speaker_role.py` (color set + unset branches) | — | Mark Rounds speaker → blue+bold |
| 6 | `test_export_goldens_v2.py` (per session_type × polls/chat combo) | — | CMS partner sign-off |
| 7 | `test_stt_normalize.py`, `test_word_cap_splitter.py`, `test_trim_offset.py` | — | Upload known-bad fixtures |
| 8 | `test_segment_reorder.py`, `test_sop_regress.py`, `test_audit_display.py` | Reorder + export Playwright | Drag in 200+ segment session |
| 9a | `test_etag_help.py`, `test_team_queue.py`, `test_signed_url_refresh.py` | Playwright cancel upload | Dashboard p95 < 100 ms |
| 9b | `test_advisory_lock_perf.py`, `tests/perf/test_4x_concurrent.py`, `test_stt_gapfill.py` | — | 4 concurrent uploads on canary |
| 10a | `test_dedup.py` | — | Fixture-driven |
| 10b | (vendor decision dependent) | (vendor decision dependent) | (vendor decision dependent) |

---

## Section 4 — Rollback matrix

| Phase | Single rollback action |
|---|---|
| 0 | Reverse tracker flips |
| 1 | `git revert` frontend bundle |
| 1.5 | `git revert` `with pg_try_advisory_lock` wrappers |
| 2 | `VITE_AUTOSAVE_ENABLED=false` |
| 2a | `git revert` materialization UPDATE |
| 3 | `VITE_EDITOR_PERSISTENCE=false` |
| 3.5 | `git revert` `app/services/segment_*.py` + dispatch |
| 4 | `VITE_EDITOR_MARKS=false` (toolbar disabled; marks table dormant) |
| 5 | Revert SELECT + dataclass field + consumer branches (multi-file) |
| 6 | Per-rule flag flip (`EXPORT_D1`/`D2`/`D4`/`D5`/`D6`) or `?format_version=v1` |
| 7 | Per-pass config flag flips |
| 8 | Per-feature `VITE_EDITOR_*` flag; nullable columns drop CONCURRENTLY |
| 9a | Per-feature flags; new index drop CONCURRENTLY |
| 9b | `STT_GAPFILL_ENABLED=false`; revert `CELERY_WORKER_CONCURRENCY` env; remove lock `with` blocks |
| 10a | `git revert` dedup pass |
| 10b | Per-item revert |

---

## Section 5 — Sequencing graph (dependencies)

```
0 ── (no-op)
1 ──┐
    ├── 1.5 ──┐
2 ──┤         ├── 2 ──┐
    │         │       ├── 2a ──┐
3 ──┘         │       │        ├── 6 (BLOCKED until 2a)
              │       │        │
3.5 ──────────┘       │        │
              ┌───────┘        │
4 ────────────┘                │
                               │
5 ─────────────────────────────┤
                               │
6 ─────────────────────────────┘
7 ── (parallel; can start after 1.5)
8 ── (blocks on 3.5 for split/merge; on 4 for marks table; on 7 for mig 060)
9a ── (parallel; ships any time after 8 lands TR6 data migration)
9b ── (REQUIRES USER AUTH; ships independently after 1.5 + 7)
10a ── (any time)
10b ── (any time, vendor-blocked)
```

**Critical path:** 1 → 1.5 → 2 → 2a → 6 (≈ 13–17 days) — must ship in order; rest can parallelize.

---

## Section 6 — Performance budget

For each phase, the worst-case marginal cost added to the editor / export hot paths:

| Phase | Marginal hot-path cost |
|---|---|
| 1 | 0 (heartbeat is background; lock READ piggybacks on existing session fetch; LISTEN/NOTIFY, no poll) |
| 1.5 | +50 µs per ingest task (advisory lock) |
| 2 | 1 PATCH per blur (existing endpoint); `shallowRef<Map>` avoids re-render storm |
| 2a | +1 UPDATE per correction commit (PK lookup, ≤ 1 ms) |
| 3 | rAF-throttled; binary search O(log n) on 600 segs <0.1 ms; debounced 500 ms localStorage |
| 3.5 | 0 (executor only runs on operator action) |
| 4 | +1 LEFT JOIN on `segment_marks` per export load; render at paint (already paying for B/I/U) |
| 5 | +1 TEXT column in existing speaker SELECT |
| 6 | +40–80 ms per export (regex + timestamp run); enforced <2 s via golden |
| 7 | 0 on existing sessions; ingest pipeline adds O(n) regex + O(1) trim |
| 8 | `ExtrasTab` lazy; orphan lazy; `display_order` backfilled to `start_ms` (no functional index needed) |
| 9a | +1 GCS call per stalled video; ETag avoids re-fetch of help articles |
| 9b | Concurrency win is intended; RAM ceiling enforced via perf test |
| 10a/b | 0 |

**Overall editor TTI delta target: < 30 ms p95.** Verified via Playwright perf assertions added in each phase.

---

## Section 7 — Success criteria

This plan succeeds when:

1. Every audit item (84) + technical risk (8) has either shipped or been formally descoped with a written decision doc.
2. Editor TTI p95 stays within +30 ms of pre-plan baseline.
3. No production incident attributable to a phase rollout in any of the 14 phases.
4. CMS partner has confirmed v2 export parity on the documented canary set.
5. `tests/test_health.py::test_locked_weights_match_audit` updated with user authorization for Phase 9b.
6. Parity score climbs from 27.4 % → ≥ 95 % at Phase 9a completion; ≥ 100 % at 10a (10b vendor-dependent).

---

## Section 8 — Non-goals (explicit descope candidates)

These were considered and explicitly excluded from the plan:

- **Real-time collaborative editing.** Lock + autosave handles the 99 % case; full CRDT collaboration would 5× the scope.
- **Migration off `LEGACY_ADMIN_EMAIL` to OIDC SSO.** Phase 9a finishes the `auth_users.role` cutover; OIDC is a separate plan.
- **Search infrastructure.** Find/replace stays as `MAX(seq) + segment replay`; full-text search (e.g. Postgres FTS / Meilisearch) is a separate plan.
- **i18n / locale.** Single locale (English) only.
- **Inline image embeds.** Not in this plan.
- **Cross-session bulk operations.** Out of scope.

---

## Appendix — Workflow provenance

This plan was synthesized from workflow run `wgwy30uh7` (17 agents, 1.22 M tokens, 14 min 57 s):

- **Map phase:** 4 parallel agents producing 67 structured gap items.
- **Design phase:** 3 parallel agents producing 28 alternative phases (Risk-First / Dependency-First / User-Impact-First).
- **Review phase:** 9 parallel agents (3 designs × 3 lenses: stability, performance, sequencing) producing 38 risk findings + 16 sequencing problems.
- **Completeness phase:** 1 critic recommending UIFER as winning approach + 4 grafts to close stability/sequencing gaps + a Phase 0 tracker reconciliation.

This plan applies the critic's 4 grafts + 30 additional reviewer-flagged corrections (anti-no-op autosave, ledger materialization, marks-as-sibling-table, fail-closed lock, dual-path v2 exports, CMS coordination, multi-admin via existing column, etc.).

— *End of plan.*
