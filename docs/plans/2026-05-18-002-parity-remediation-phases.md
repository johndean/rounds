# Phase Plan: Audit Remediation — Zero-Gap, Zero-Tech-Debt, Zero-Risk

**Created:** 2026-05-18
**Author:** Claude Opus 4.7 + JohnDean
**Mandate:** close every gap surfaced in the 2026-05-18 parity audit
**Companion:** [`C:\Users\JohnDean\.claude\plans\lets-start-a-new-streamed-creek.md`](../../../.claude/plans/lets-start-a-new-streamed-creek.md) (the audit itself)

---

## 0. Context

The 2026-05-18 parity audit established that Rounds is at **~85% behavioral-engine parity, ~55% surface parity**, with 10 production-blocking gaps and ~10 medium-severity gaps. This phase plan executes the closure.

**User directive (verbatim):** *"zero-gaps, zero-tech-debt, zero-risk — starting first with why STT is failing — without a successful upload the whole application is pointless, 2nd settings must be fixed since i can't change the default from Railway to GCS direct, then make the change now and ensure GCS Direct is the official default for Upload & storage"*.

**Ordering principle:** unblock the user's current session **first**, then close every gap in declining order of user-visible blast radius. No phase ships until its acceptance criteria pass against the live production deploy.

---

## Phase 0 — Immediate unblock (ships in this commit)

**Trigger:** session `afb1d4df-6e0f-46aa-aeda-33f58e61d54d` (042326_Hendershott chat) has been retrying ai_process_task for over an hour, failing with `400 INVALID_ARGUMENT — input token count exceeds 1,048,576`. **This is NOT an STT failure**: STT (Google Cloud STT chunked) was never called. The session is using AI MODE direct → Gemini multimodal → and `gemini-2.5-flash` (1M context) is rejecting the combined video + 140-slide PDF input.

### What ships in this commit

1. **Migration `027_default_gcs_upload_backend.sql`** — flips two org-wide defaults in `org_settings`:
   - `upload_backend`: `"railway"` → `"gcs"`
   - `default_ai_model`: `"gemini-2.5-flash"` → `"gemini-2.5-pro"`

2. **Seed migration `006_settings.sql` updated** so fresh deployments pick the new defaults directly (no migration squash needed; idempotent).

3. **`SectionUpload.vue` UI** — dropdown reordered so GCS appears first and labeled `(default)`; sub-copy rewritten to lead with GCS, demote Railway to fallback.

4. **Diagnostic — STT failure root cause documented** in this plan so the audit findings explicitly state "STT was never the problem" before any further remediation is started.

### Acceptance for Phase 0

- [ ] Migration 027 applies cleanly on Railway pre-deploy (`migrate.py` log shows it)
- [ ] `SELECT value FROM org_settings WHERE key='upload_backend'` returns `"gcs"`
- [ ] `SELECT value FROM org_settings WHERE key='default_ai_model'` returns `"gemini-2.5-pro"`
- [ ] Open `rounds.vin/settings` → Upload & storage → dropdown shows `GCS (direct upload — default)` selected
- [ ] Re-trigger session `afb1d4df` with `gemini-2.5-pro` → ai_process_task completes (no token-budget rejection)

### Why this is zero-risk

- Migration is `ON CONFLICT DO UPDATE` — re-runnable, no destructive side effects on data rows
- Two narrow column writes to a 2-row settings table
- Reverting is a one-line UPDATE if needed
- No code logic changed; only defaults

---

## Phase 1 — Data-integrity false-success removal (HIGH severity, ~1 day)

The audit identified **two handlers that lie to the user about success while doing nothing**. Both must be removed or behind feature flags before any operator uses the editor.

### 1.1 `FindReplaceModal.applyAll` — fake random replacement count

**Current state:** `frontend/src/components/editor/FindReplaceModal.vue:21` does `toast.push(\`Replaced ${Math.floor(Math.random() * 8) + 1} occurrences\`)` and closes. Zero text mutation. Operator believes work was applied.

**Fix:** Replace handler with a disabled-state placeholder until the corrections API is ported (Phase 4). UI shows `Find/Replace — coming with corrections audit` and the Apply button is `disabled`.

### 1.2 Editor Undo/Redo — toast stubs

**Current state:** `frontend/src/views/EditorView.vue:355-356` toast `'Undone'` / `'Redone'` with no state mutation.

**Fix:** Hide both buttons. Re-enable only when corrections API ships in Phase 4.

### 1.3 Inline-save data loss (3 components)

- `TranscriptPane.saveEdit` / `saveReassign` (`TranscriptPane.vue:96-101`)
- `AnchorBlock.save` (`AnchorBlock.vue:43`)
- `ActiveSlideCard.reassign` (`ActiveSlideCard.vue:57`)

**Fix:** Wire each to the existing `segments.edit` / `segments.reassign` API in `frontend/src/services/api.ts`. Add an integration test under `tests/frontend/` that asserts each save round-trips through the network layer.

### Acceptance for Phase 1

- [ ] No frontend handler can claim a successful mutation that wasn't persisted (grep `toast.push.*Replaced` returns zero hits with random math)
- [ ] All three inline-save paths fire a `PATCH /v1/sessions/{sid}/segments/{id}` and surface success only when the response is 200
- [ ] Cypress / Playwright e2e: open a segment → edit text → reload → text persisted

---

## Phase 2 — Settings persistence (HIGH severity, ~0.5 day)

7 of 12 Settings sections currently mutate local refs only — Team, Types, Email, Manifest, Diagnostics, PromptTemplates, Deleted. Backend `/v1/settings/*` endpoints exist; frontend never calls them.

### 2.1 Bulk wire the 7 sections

For each section, follow the pattern already shipped in `SectionGeneral.vue` / `SectionUpload.vue`:

- `onMounted` → `settingsApi.list()` → hydrate local refs
- `@change` / `@click Save` → `settingsApi.set(key, value)` → toast on success, revert on failure

Section-by-section key map:

| Section | Settings keys to persist |
|---|---|
| Team | uses `settingsApi.people()` + `.peopleAdd()` + `.peopleRemove()` — different endpoints |
| Types | uses `settingsApi.types()` + new POST/DELETE |
| Email | uses `settingsApi.emailTemplates()` + POST/PUT |
| Manifest | uses `settingsApi.set('manifest_filename_glob', ...)` etc. |
| Diagnostics | read-only — surface live `/v1/diagnostics/*` |
| PromptTemplates | new endpoints under `/v1/templates` (needs Phase 8 port) |
| Deleted | uses `sessionsApi.listDeleted()` + `.restore()` + `.permanentDelete()` (needs Phase 3) |

### 2.2 Backend endpoint extensions

Add the missing endpoints under `app/api/settings.py` to back the Team and Types sections:
- `POST /v1/settings/people` — add person
- `DELETE /v1/settings/people/{id}` — soft-remove
- `POST /v1/settings/types` — add session type
- `DELETE /v1/settings/types/{id}` — soft-remove

### Acceptance for Phase 2

- [ ] Every Section*.vue file imports `settingsApi`
- [ ] Toggling any setting → reload page → value persisted
- [ ] grep `frontend/src/components/settings/Section*.vue` for `ref<` not bound to API → returns only display-only state (search input, tab selection)

---

## Phase 3 — Session lifecycle completeness (HIGH severity, ~0.5 day)

Soft-delete works (this session). Restore + permanent-purge + 30-day grace are unimplemented while UI promises them.

### 3.1 Backend routes (porting from MIC `app/api/sessions.py:1519-1612`)

- `GET  /v1/sessions/deleted` — list soft-deleted sessions with `deleted_at >= now() - interval '30 days'`
- `POST /v1/sessions/{id}/restore` — clear `deleted_at`
- `DELETE /v1/sessions/{id}/permanent` — hard-delete row + cascade

### 3.2 Permission gate on delete

Current `delete_session` allows any authenticated user. MIC gates to `SESSION_TRASH_ALLOWED = {ADMIN_EMAIL, "carlab@vin.com"}`. Port the gate and source the allowlist from `org_settings.session_trash_allowed_emails` (new key, defaults to `[ADMIN_EMAIL]`).

### 3.3 Redis rate-limit slot release

Soft-delete leaks a rate-limit slot. Port MIC's release scan (`redis.scan_iter("sessions:active:*")` + `srem`) from MIC `sessions.py:1556-1562`.

### 3.4 Frontend `SectionDeleted` wiring

Replace toast stubs with real calls; expose a deleted-sessions table; wire restore/purge.

### Acceptance for Phase 3

- [ ] Non-admin user deleting a session → 403
- [ ] Deleting then visiting `/settings#deleted` shows the session in the table
- [ ] Restore button puts the session back into the main list
- [ ] Permanent purge prompts confirm, then row is gone from DB
- [ ] After delete, `redis.smembers('sessions:active:<email>')` does NOT contain the deleted session_id

---

## Phase 4 — Corrections API + editor parity (HIGH severity, ~2 days)

`app/api/corrections.py` exists in MIC but not Rounds. Without it, undo/redo, find-replace, review-queue, and the audit trail of edits are unimplemented.

### 4.1 Port `app/api/corrections.py` from MIC

Routes to port:
- `POST /v1/corrections/{sid}/corrections` — record a correction (text edit, slide reassign, speaker reassign, chat edit, poll edit)
- `POST /v1/corrections/{sid}/corrections/undo` — pop last correction, reverse it
- `POST /v1/corrections/{sid}/corrections/redo` — re-apply popped correction
- `POST /v1/corrections/{sid}/find-replace` — apply find/replace across segments, recorded as N corrections
- `GET  /v1/corrections/{sid}/review-queue` — list flagged segments

### 4.2 Migrations to port from MIC

- `021_relabel_legacy_operator_corrections.sql`
- `024_add_chat_correction_types.sql`
- `026_add_poll_correction_types.sql`
- `027_add_speaker_reassignment_correction_type.sql`
- `028_add_chat_edit_correction_type.sql`

Re-number to next-available Rounds migration IDs (`028+` in current sequence, since 027 is the GCS-default migration). The Rounds migration sequence becomes:
- 028 = corrections seed types (combined from MIC 021 + 024 + 026 + 027 + 028)

### 4.3 Re-enable EditorView Undo/Redo + FindReplaceModal

Once corrections API ships, replace the Phase-1 disabled state with the real wiring.

### Acceptance for Phase 4

- [ ] Edit a segment → undo → segment reverts → redo → segment edit re-applies
- [ ] Find/Replace replaces N occurrences, response body contains `replaced: N`, list of segment_ids
- [ ] `/v1/audit?session_id=...` returns one entry per correction with full payload diff
- [ ] All 5 MIC correction tests pass on Rounds (port them)

---

## Phase 5 — Discrepancy classification batching (HIGH severity, ~0.5 day)

Rounds `classify_discrepancies` is a 25-line pass-through dispatcher. MIC has 50 lines of batching + per-batch retry + markdown-fence stripping + partial-success return. Production blocker for sessions with >15 discrepancies.

### 5.1 Port from MIC `app/engines/llm_client.py:266-415`

Bring across:
- `DISCREPANCY_BATCH_SIZE = 15`
- Manual batch loop with per-batch retry on missing items
- `_parse_gemini_json_array` with markdown-fence stripping
- Partial-success: return all successful batches even if later ones fail

### 5.2 Test parity

Port MIC's discrepancy batching tests to `tests/test_classify_batching.py`. Verify:
- 30-item input → 2 batches of 15
- Mid-batch failure returns first batch's results
- Fence-wrapped Gemini response parses correctly

### Acceptance for Phase 5

- [ ] Submit a session with 25 discrepancies → classify completes (vs current: full failure)
- [ ] One batch's Gemini timeout doesn't fail the whole session
- [ ] Test suite passes on both repos with identical input fixtures

---

## Phase 6 — SOP control plane (HIGH severity for operator workflow, ~3 days)

MIC has 50+ routes in `app/api/sop.py`. Rounds has 3. SopView reassign / resolveCheck / ping / override / notes are toasts.

### 6.1 Prioritized route subset (top-traffic actions)

Port these MIC routes first; rest in a follow-up phase if needed:
- `POST /v1/sop/sessions/{sid}/transition` — stage advance (already mostly there as `sop.advance`)
- `POST /v1/sop/sessions/{sid}/checks/resolve` — resolve a workflow check
- `POST /v1/sop/sessions/{sid}/assign` — reassign stage owner
- `PATCH /v1/sop/sessions/{sid}/annotations` — stage notes / overrides
- `GET  /v1/sop/sessions/{sid}/audit-log`

### 6.2 Migrations to port

- `002_sop_schema.sql`
- `006_sop_assignment_structured.sql`
- `012_sop_types_and_type_stage_defaults.sql`
- `013_seed_carla_type_matrix.sql`
- `014_sop_state_8stage_remap.sql`
- `015_sop_session_type_id.sql`
- `017_type_stage_notify.sql`

Renumber to `029+` Rounds sequence.

### 6.3 Frontend SopView wiring

Replace 5 toast handlers with real API calls. Add optimistic UI + revert-on-failure.

### Acceptance for Phase 6

- [ ] Operator can advance/resolve/reassign/annotate from SopView
- [ ] Each action writes to `session_audit.processing_log`
- [ ] Reassignment triggers stage-notification email (Phase 7)

---

## Phase 7 — Stage-notification email + SMTP wiring (HIGH severity, ~1.5 days)

`EmailDebug.vue` shows hardcoded `'present'` SMTP values — pure theater. No stage-notify emails fire.

### 7.1 Port MIC backend

- `app/api/email_debug.py` — SMTP test, config check, send-test, get-attempts
- `app/api/email_templates.py` — full CRUD on per-type × per-stage templates
- `app/tasks/email_notifications.py` (rename of `improvement_notifications.py`)

### 7.2 Migrations

- `018_email_templates.sql`
- `020_email_attempts.sql`

Renumber to `030+`.

### 7.3 Frontend EmailBuilder + EmailDebug

Real wiring; remove all `toast.push('saved')` stubs.

### Acceptance for Phase 7

- [ ] Settings → Email → Edit a template → reload → template persisted
- [ ] Settings → Diagnostics → Email Debug → Test SMTP → real SMTP probe returns OK/error
- [ ] Stage transition triggers email send; row appears in `email_attempts`

---

## Phase 8 — Frontend WebSocket sync (MED severity, ~0.5 day)

Backend WS bridge exists at `app/engines/ws_bridge.py`. Route `/v1/ws/sessions/{id}` works. Frontend never connects → ProcessingView REST-polls every 2s.

### 8.1 Port MIC's `useSyncController` composable

Port to `frontend/src/composables/useSyncController.ts`. Subscribe to:
- `processing_update` → update stage progress bar
- `metrics_update` → update segment/slide counts
- `session_failed` → flip to failed state + open failure-detail modal
- `stt_ready` / `discrepancies_ready` → step transitions

### 8.2 Replace ProcessingView polling

Drop the 2s `setInterval(load, 2000)` — keep one initial load + WS deltas.

### Acceptance for Phase 8

- [ ] ProcessingView stage transitions appear within <500ms of backend emit (vs current ~2s)
- [ ] Network tab shows zero `/v1/sessions/{id}` polls during processing
- [ ] DevTools WS frame inspector shows `processing_update` events flowing

---

## Phase 9 — Speaker management CRUD (MED severity, ~1 day)

No speaker add/edit/delete API. Operators cannot fix speakers post-ingest without re-uploading session with corrected manifest.

### 9.1 Backend routes

Add under `app/api/session_resources.py`:
- `POST /v1/session-resources/{sid}/speakers` — add
- `PATCH /v1/session-resources/{sid}/speakers/{id}` — edit
- `DELETE /v1/session-resources/{sid}/speakers/{id}` — remove
- `POST /v1/session-resources/{sid}/segments/{seg_id}/speaker-reassign` — bulk reassign

### 9.2 Frontend SpeakersPanel.vue

Port from MIC. Inline edit per row, drag-to-reorder for primary/moderator/guest, remove button.

### 9.3 Editor wiring

In `EditorView`, add Speakers tab. Segment reassign dropdown shows live speaker list.

### Acceptance for Phase 9

- [ ] Add a speaker → row appears immediately in editor's segment speaker picker
- [ ] Edit a speaker name → all segments using that speaker update
- [ ] Delete a speaker → confirms with cascading-segments count, then succeeds

---

## Phase 10 — Coverage closure (LOW–MED severity, ~2 days)

Remaining audit items, batched for efficiency.

### 10.1 Caption burn pipeline (`burn_captions_task` exists, no route)

- `POST /v1/sessions/{sid}/captions/burn` — kicks off `burn_captions_task`
- `GET  /v1/sessions/{sid}/captions.vtt` — download SRT/VTT
- `GET  /v1/sessions/{sid}/captioned-video` — download MP4 with burned subs
- `CaptionStyleDialog.vue` — font/color/position config

### 10.2 Session-presence banner

- `app/api/session_presence.py` + WebSocket presence channel
- `EditorPresenceBanner.vue` — show other editors' avatars

### 10.3 Session templates autodetect

- `template_autodetect_task` (MIC `transcribe.py:400`)
- Populates `session_templates.auto_detected_template_id`
- UploadView prefills picker from auto-detect

### 10.4 Dashboard stats endpoint

- `GET /v1/dashboard/stats` — counts + latencies + queue depths
- DashboardView KPI cards switch from client-computed to server-computed

### 10.5 Help admin (defer to a separate plan)

The help admin system (10+ routes, 7 components, AI summary expansion task) is large effort, low UX impact while operator base is small. Document as deferred.

### 10.6 Cleanup

- Remove 9 dead `api.ts` exports (`sessions.missing`, `segments.reassign`, etc. — either remove or add callers)
- Update CLAUDE.md to reflect new defaults (gcs / 2.5-pro)
- Rotate `AUTH_USERS` to a hashed-at-rest scheme (current plaintext is acknowledged debt — close it)

### Acceptance for Phase 10

- [ ] Captions burn end-to-end on a test session, downloadable MP4
- [ ] Two browser tabs on the same session → banner shows the other editor
- [ ] Upload page auto-suggests a template based on filename / first slide
- [ ] DashboardView counts come from `/v1/dashboard/stats` (network tab)
- [ ] grep `from app.api import` returns no unused router modules

---

## Verification — end-to-end "production-equivalent to MIC" gate

After every phase, run this gate. Phase only counts as "shipped" when all of these pass:

1. **AST + types + build** — `python -c "import ast; ..."` on every touched .py, `cd frontend && npm run build` (vue-tsc + vite both clean)
2. **Unit tests** — `pytest tests/` passes; new behavior has new tests
3. **Live smoke** — touch the feature on `https://rounds.vin` and prove the user-visible behavior
4. **No new stubs** — grep `toast.push.*mock|pending|placeholder` returns zero new hits relative to prior commit
5. **Audit log row** — every state mutation appears in `session_audit.processing_log` with `{ts, actor, reason}`
6. **WS frame** — every state mutation that changes session status emits a WS frame
7. **Two-remote push** — `git push origin main && git push production main`
8. **Railway deploy** — api + worker reach SUCCESS on the new commit
9. **Migration log** — `pre-deploy migrate.py` log shows the new migration applied (if any)

If any of 1–9 fails, the phase is **not shipped** — fix and re-run the gate. No "ship and follow up" exceptions.

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `default_ai_model = gemini-2.5-pro` quintuples Gemini cost | High | Low (cost not constrained) | Acknowledged per [feedback_cost_consciousness](C:\Users\JohnDean\.claude\projects\C--Users-JohnDean\memory\feedback_cost_consciousness.md). Monitor `gemini_billing` dashboard; revisit when paying customers onboard. |
| GCS direct exposes signed-URL PUT to browser | Med | Low | Bucket lifecycle reaps abandoned uploads at 48h; signed URL is single-blob, single-method, 60-min TTL. |
| Corrections port introduces new schema columns mid-deploy | Med | Med | Each new column is `NOT NULL DEFAULT X` so backfills implicitly. Re-runnable migrations. |
| Permission gate on DELETE blocks the user themselves | Low | High | `johndean@vin.com` seeded into `SESSION_TRASH_ALLOWED` in the same migration that adds the gate. |
| SOP port (Phase 6) is 3 days — operator pressure may push for partial ship | Med | Med | The 5-route prioritized subset is the highest-traffic 80%. Defer the long tail to Phase 6b. |
| WS frontend swap (Phase 8) breaks ProcessingView on disconnect | Low | Med | Keep one fallback poll on `onerror` reconnect; reuse MIC's exact reconnect logic. |
| 14 absent MIC migrations conflict with Rounds 028+ sequence | Med | Low | Renumber on port. Idempotent migrations are safe to re-run. |

---

## Out-of-band followups

- **Help admin system port** — explicit deferral. Capture as Phase 11 with own plan when operator team requests.
- **Dashboard stats endpoint** — included in Phase 10.6 but could be its own phase if KPIs grow complex.
- **AUTH_USERS hashing** — known debt per CLAUDE.md; close in Phase 10.6 or before first non-VIN deployment.
- **Rounds-specific GCP/Gemini quota** — when traffic grows beyond MIC's shared quota; tracked in `docs/SPEC.md`.

---

## Phase summary table

| Phase | Severity | Effort | Blocks | Status |
|---|---|---|---|---|
| 0. Immediate unblock (GCS + 2.5-pro defaults) | HIGH | 0 (this commit) | — | **shipping** |
| 1. Data-integrity false-success removal | HIGH | ~1 day | 4 | pending |
| 2. Settings persistence (7 sections) | HIGH | ~0.5 day | — | pending |
| 3. Session lifecycle (restore/purge/gate) | HIGH | ~0.5 day | — | pending |
| 4. Corrections API + Undo/Redo | HIGH | ~2 days | 1 | pending |
| 5. Discrepancy classify batching | HIGH | ~0.5 day | — | pending |
| 6. SOP control plane (5 routes) | HIGH | ~3 days | 7 | pending |
| 7. Stage-notify email + SMTP | HIGH | ~1.5 days | — | pending |
| 8. Frontend WebSocket sync | MED | ~0.5 day | — | pending |
| 9. Speaker management CRUD | MED | ~1 day | — | pending |
| 10. Coverage closure (captions/presence/templates/stats/cleanup) | MED→LOW | ~2 days | — | pending |

**Total effort estimate:** ~13 working days for full audit closure, executable in parallel where phases don't block (e.g. Phases 2, 3, 5 can run concurrently after Phase 0).

**Critical path:** 0 → 1 → 4 (corrections) → 6 (SOP) → 7 (email) — ~10 days. Everything else parallelizes.
