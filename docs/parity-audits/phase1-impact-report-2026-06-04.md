# Phase 1 — Impact Report

**Generated**: 2026-06-04 against tip `6df4170` (post-F1.E)

What gets touched per phase. Files, components, APIs, migrations, dependencies, tests, permissions. Sourced from the four baseline inventories.

## Legend
- 🟢 **Net-new file** — no risk to existing surface
- 🟡 **Modifies existing file** — additive change, low parity risk
- 🔴 **Modifies existing file** — structural change, parity risk
- 🔒 **C1-LOCKED file** — DO NOT touch
- ⚠️ **C2-LOCKED file** — touch only with explicit authorization

## Phase 2 — Help Center

| Path | Change kind | Risk |
|---|---|---|
| 🟡 `frontend/src/components/AppHeader.vue` | Add 1 button to `.app-header__tools` cluster | Pixel — drawer trigger only |
| 🟡 `frontend/src/App.vue` | Add 1 `<HelpCenterDrawer />` host alongside `<TweaksPanel />` | Pixel — only when open |
| 🟢 `frontend/src/components/HelpCenterDrawer.vue` | New component | None (greenfield) |
| 🟢 `frontend/src/content/help/*.md` | New markdown content (per workflow page) | None |
| 🟢 `frontend/src/stores/rightDrawer.ts` | New pinia store (mutex with TweaksPanel) | None |
| 🟢 `frontend/.env.example` | Add `VITE_HELP_ASK_AI_ENABLED=false` | None |
| 🟡 `frontend/src/stores/tweaks.ts` | Adapt to read/write via rightDrawer mutex | LOW |

**No backend changes**. **No migration**. **No new dependency**.

## Phase 3 — Chat Count panel move
**BLOCKED on stakeholder clarification.** No impact map until premise confirmed.

## Phase 4 — Video ↔ Segment timestamp sync

| Path | Change kind | Risk |
|---|---|---|
| 🟡 `app/api/segments.py` | Extend `SegmentPatch` model + PATCH handler to accept `start_ms`, `end_ms` | API contract |
| 🟢 `migrations/0XX_correction_kinds.sql` | Add `time_edit` kind to correction ledger enum (if enum'd) | LOW |
| 🟡 `frontend/src/views/EditorView.vue` | Wire click-segment → seek + time → highlight (using existing `time` ref at L320-323) | Pixel |
| 🟡 `frontend/src/components/editor/VideoStrip.vue` | Confirm 10Hz `timeupdate` propagation | None expected |
| 🟡 `frontend/src/components/editor/TranscriptPane.vue` | Add "active segment" visual indicator (within existing styles) | Pixel-MEDIUM |
| 🟢 `tests/test_segments_patch.py` | New tests for time edits | None |

🔒 **Forbidden**: `app/tasks/align.py`, `app/tasks/anchor_task.py`, `app/tasks/fusion.py` — locked weights.

## Phase 5 — Segment formatting (soft/hard returns + paragraphs)

| Path | Change kind | Risk |
|---|---|---|
| 🟡 `frontend/src/components/editor/TranscriptPane.vue` | Preserve `\n` in segment text editor (verify contenteditable behavior) | Pixel-MEDIUM |
| 🟡 `app/engines/artifact_transformer.py` | DOCX export — stop collapsing paragraphs (L143-166); CMS preserve confirmed (L391-426); SRT keep 42-char cap (L197-227) | Export regression |
| 🟢 `tests/test_export_formats.py` | Snapshot tests per format (known input → expected output) | None |

🔒 **Forbidden**: `app/tasks/transcribe.py`, `app/tasks/normalize.py` — locked.

## Phase 6 — Poll & Chat reordering

| Path | Change kind | Risk |
|---|---|---|
| 🟢 `migrations/0XX_chat_polls_order_index.sql` | Add `order_index INTEGER` nullable to `chat_messages` + `polls` tables | Schema |
| 🟡 `app/api/session_resources.py` | Modify ORDER BY (L506, L588) to use `COALESCE(order_index, sent_at_ms)` / `COALESCE(order_index, opened_at_ms)` | API |
| 🟢 `app/api/session_resources.py` | New PATCH endpoint to persist reorder | None |
| 🟡 `frontend/src/components/editor/PollsTab.vue` | Add sibling drag handlers + drop targets (preserve outward drag at L37-41) | Pixel-MEDIUM |
| 🟡 `frontend/src/components/editor/ChatTab.vue` | Same | Pixel-MEDIUM |
| 🟢 `frontend/package.json` | Add `sortablejs` (~30KB gzipped) | Dep |
| 🟢 `tests/test_resource_reorder.py` | Reorder persistence tests | None |

## Phase 7 — Workflow automation

### Phase 7 quick-win (highest leverage, smallest diff)

| Path | Change kind | Risk |
|---|---|---|
| 🟡 `app/tasks/sop_tasks.py` | `_maybe_send_deadline_email` — replace inline f-strings (L195-207) with internal call to `email_templates.resolve_internal()` | LOW (function-local) |
| 🟢 `app/api/email_templates.py` | Extract `resolve_internal(db, session_type_id, stage, locale)` for non-HTTP callers | None |
| 🟡 `app/services/email.py` | No change (helper is already template-shape-agnostic) | None |

### Phase 7 broader scope (queue + ownership visibility)

| Path | Change kind | Risk |
|---|---|---|
| 🟡 `frontend/src/views/SopView.vue` | Replace `palette` array (L66-75) with `sop_state.assignees` JSONB rendering | Pixel — display change |
| 🟢 `frontend/src/views/QueueView.vue` | New per-user queue view | None |
| 🟢 `app/api/queue.py` | New endpoint: `GET /v1/queue/mine` | None |
| 🟢 `frontend/src/router/index.ts` | Add `/queue` route | None |
| 🟡 `frontend/src/views/DashboardView.vue` | Replace "Your Queue" globals slice (3 most-recent) with `/v1/queue/mine` call | Pixel |
| 🟡 `frontend/src/components/AppHeader.vue` | Add queue-badge indicator (count of pending items for current user) | Pixel |

## Phase 8 — Open Builder permissions fix

| Path | Change kind | Risk |
|---|---|---|
| 🟢 `app/security/roles.py` | New helper module: `require_admin(user)`, `is_admin(user)` | None |
| 🟡 `app/api/email_templates.py` | Replace `_require_admin` body (L39-44) to call new helper; remove email-literal | LOW |
| 🟡 `app/api/settings.py` | L20-25 replace email-literal with new helper | LOW |
| 🟡 `app/api/email_debug.py` | Replace email-literal with new helper | LOW |
| 🟡 `app/auth.py` | Modify `get_current_user` (L169-202) to load `auth_users.role` into the user object | MEDIUM (auth path) |
| 🟢 `tests/test_admin_role.py` | Verify admin/non-admin matrix for the 5+ admin endpoints | None |

**Cross-cutting effect**: any new admin who is promoted to `auth_users.role = 'admin'` via Settings → Auth & logins will now actually have admin privileges. (Today they do not.) This is the intended fix — but verify there are no unintended `role = 'admin'` rows currently in the DB before deployment.

## Phase 9 — Spellcheck (research only, no code in Phase 9)
**Impact**: zero. Research deliverable. Future Phase 9.5 if GO:

| Path | Change kind | Risk |
|---|---|---|
| 🟢 `infra/languagetool/Dockerfile` | New service | New infra |
| 🟢 `railway.json` | New service entry | Deploy |
| 🟢 `frontend/package.json` | Add `nspell` + Hunspell dictionary asset | Dep |
| 🟢 `frontend/src/composables/useSpellcheck.ts` | New composable | None |

## Cross-phase dependency footprint

| Dependency | Net-new in phase | Notes |
|---|---|---|
| `sortablejs` (frontend) | Phase 6 | ~30KB gzipped, ~6 yrs maintained |
| LanguageTool Docker service | Phase 9.5 (future) | New Railway service |
| `nspell` + Hunspell dict (frontend) | Phase 9.5 (future) | ~150KB dict, plus library |

**Phase 1+8+9 add zero new dependencies.**

## Permissions impact summary

| Phase | Permissions delta |
|---|---|
| Phase 2 (HelpCenter) | None — content is read-anyone |
| Phase 3 | TBD (premise unclear) |
| Phase 4 (timestamp sync) | None — same as existing segment edit |
| Phase 5 (formatting) | None — same as existing segment edit |
| Phase 6 (reorder) | None — same as existing chat/poll edit |
| Phase 7 quick-win | None — internal Celery call |
| Phase 7 broader | New: `/v1/queue/mine` returns only current user's items |
| Phase 8 | **Restores admin boundary to role-based** — non-broadening fix |
| Phase 9 (research) | None |

## Test impact summary

| Test surface | Phase | New tests required |
|---|---|---|
| `tests/test_segments_patch.py` | Phase 4 | time-edit happy path, overlap guard, audit ledger row |
| `tests/test_export_formats.py` | Phase 5 | snapshot per format (CMS/DOCX/SRT/VTT/TXT) |
| `tests/test_resource_reorder.py` | Phase 6 | reorder persistence + COALESCE fallback |
| `tests/test_admin_role.py` | Phase 8 | admin/non-admin matrix |
| `frontend/tests/parity-<view>.spec.ts` | All UI phases | pixel-diff baseline + post-impl comparison |
