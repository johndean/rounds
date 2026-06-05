# Phase 1 — Risk Report

**Generated**: 2026-06-04 against tip `6df4170` (post-F1.E)

Cross-phase risk register. Each risk has: severity, blast radius, current evidence, recommended mitigation. Ordered most-severe first.

## R1 — Phase 3 premise mismatch (HIGH)
**Risk**: The mandate says "Move Chat Count panel from Session List to Session Detail." No such panel exists in `SessionsView.vue` today. Chat-count surfaces exist only in `EditorView.vue:952` (right-rail badge) and `ChatTab.vue:69`.
**Blast radius**: Wrong-scope implementation produces a UI element the stakeholder did not request → pixel-parity mandate violation by definition.
**Evidence**: Exhaustive grep across Vue source + React SSOT JSX returns zero `chat` hits in SessionsView. Sessions KPI strip is `In Workflow / Processing / Published / Total`.
**Mitigation**: HARD STOP on Phase 3 until stakeholder clarifies whether they meant (a) the EditorView badge, (b) net-new tile on SessionDetail, or (c) something else. Do not infer.

## R2 — Phase 6 migration + new client library (MEDIUM-HIGH)
**Risk**: Poll/Chat sibling reorder requires (a) a new `order_index` column on two tables, (b) a backend persistence endpoint, (c) a drag-reorder lib added to `frontend/package.json` (currently has only 4 prod deps: `lucide-vue-next`, `pinia`, `vue`, `vue-router`).
**Blast radius**: Migration is forward-only (schema), library choice locks future drag patterns. Mistakes here ripple.
**Evidence**: `migrations/008_chat_polls.sql` has no `order_index`. PollsTab/ChatTab today emit outward drag only (drop onto transcript pane) — no sibling reorder code anywhere.
**Mitigation**: (1) Make `order_index` nullable initially, fall back to `sent_at_ms`/`opened_at_ms` ordering when null (backwards-compat). (2) Recommend `Sortable.js` (no Vue wrapper required, smaller footprint than vue-draggable-next). (3) Ship migration + backend first, frontend drag handler in a second commit, so each is independently revertable.

## R3 — Phase 5 export-format regression (MEDIUM)
**Risk**: Preserving soft/hard returns + paragraph structure across 7 export formats. Today each format has DIFFERENT line-break handling: CMS preserves paragraphs + soft breaks, DOCX collapses to one paragraph per segment, SRT has a 42-char-per-line wrap macro, VTT does `.strip()` only, TXT/ZIP unknown.
**Blast radius**: Stakeholder-facing exports — any regression is immediately visible and likely irreversible after delivery.
**Evidence**: `app/engines/artifact_transformer.py` is 634 LOC with 7 export paths. The SRT 42-char cap (`apply_srt_transform` 197-227) is intentional broadcast spec; cannot be removed.
**Mitigation**: Add per-format snapshot tests in `tests/` BEFORE Phase 5 implementation. Each test: known segment text with soft+hard returns + paragraphs → expected output per format. Lock the baselines; reject Phase 5 diffs that change non-target formats.

## R4 — Phase 4 SegmentPatch extension touches edit pipeline (MEDIUM)
**Risk**: Extending `SegmentPatch` to accept `start_ms`/`end_ms` adds a new mutation surface to the segment editor. Correction ledger needs a `time_edit` kind.
**Blast radius**: Segment edit is the core editor flow. A bad edit could orphan an alignment / break a downstream export.
**Evidence**: `app/api/segments.py:37-42` defines SegmentPatch — currently text-only. Correction ledger has no `time_edit` kind today.
**Mitigation**: Add a server-side guard: reject `start_ms >= end_ms`, reject if overlapping siblings unless explicit `force=true` flag. Also: do NOT mutate `seq`; only adjust millisecond bounds.

## R5 — F1.E + Phase 7 share `sop_tasks.py` (MEDIUM)
**Risk**: F1.E shipped 7 minutes ago. Phase 7 will edit the same function (`_maybe_send_deadline_email`) to wire through the existing `email_templates_resolve_internal()`. If Phase 7 ships before a Phase 1 reread, the existing inline-f-string path may end up dead-code.
**Blast radius**: Function-local. Easy to keep clean if Phase 7's first action is to read the current state.
**Mitigation**: Document the wire-up in the Phase 7 commit message. Delete the inline f-strings as part of the same commit (don't leave dead-code).

## R6 — Pre-existing assignee display bug surfaces during Phase 7 (LOW-MEDIUM)
**Risk**: SopView renders assignees from a STATIC palette array at `SopView.vue:66-75`, NOT from `sop_state.assignees` JSONB. Reassign endpoint writes data nobody reads. If Phase 7's "ownership visibility" requirement implicitly assumes the display is wired, the work item changes from "add status indicator" to "fix display + add status indicator."
**Blast radius**: Phase 7 scope creep.
**Evidence**: Three render sites (KPI L325, stepper L375, side card L453) all reference `palette`, never `sop_state.assignees`.
**Mitigation**: Flag this to stakeholder BEFORE Phase 7 implementation. Either scope-in (palette → assignees swap) or scope-out (status indicator only).

## R7 — Phase 8 fix risks broadening admin boundary if done sloppily (LOW)
**Risk**: Replacing `user.email != "johndean@vin.com"` with a role check needs care: must keep the boundary at `role == 'admin'`, not loosen to "any authenticated user." 5 sites to change (`email_templates.py`, `settings.py`, `email_debug.py` were called out by the agent).
**Blast radius**: Admin endpoints become accessible to unintended roles if the helper is wrong.
**Mitigation**: Extract a `app/security/roles.py::require_admin(user)` helper. Single function with one explicit `role == 'admin'` check. Apply it everywhere. Reject the PR if any direct email-literal compares remain.

## R8 — Phase 2 HelpCenter drawer collides with existing TweaksPanel (LOW)
**Risk**: A right-side drawer for Help Center may conflict with the existing `<TweaksPanel>` mount. If both can open simultaneously they could overlap or fight z-index.
**Blast radius**: Visual glitch on a small subset of routes.
**Evidence**: HelpCenter agent recommends mounting `<HelpCenterDrawer />` "next to TweaksPanel" in App.vue.
**Mitigation**: Mutex behavior — opening one closes the other. State a single "rightDrawer" pinia store, value in {`none`, `help`, `tweaks`}.

## R9 — Phase 9 future LanguageTool service introduces a new prod dependency (LOW, future)
**Risk**: Self-hosting LanguageTool requires a Docker service on Railway. New service = new failure surface, monitoring, deployment story.
**Blast radius**: Spellcheck degrades to browser-native if LanguageTool is down — graceful, not catastrophic.
**Mitigation**: Ship LanguageTool integration with a feature flag (`SPELLCHECK_LT_ENABLED`). Disabled default. Health check + fallback to browser-native on timeout.

## R10 — Phase 10 (validation) is mandate-required but ambiguously scoped (LOW)
**Risk**: Mandate says "evidence-based validation" with 9 categories (functional, workflow, permission, export, navigation, sync, regression, UI, pixel-parity). No criteria for "evidence sufficient."
**Mitigation**: Per affected phase, deliver: (a) screenshots before/after, (b) pixel-diff output via `pixelmatch` or similar, (c) Playwright test pass count, (d) one-line manual smoke confirmation. Document in the per-phase PR description.

## Pixel-parity protection mechanism (cross-cutting)

Per the mandate: *"Any visual difference not explicitly required must be treated as a defect."*

**Pre-implementation**: per affected view, capture a baseline screenshot at 1440×900 and 1024×768 on `https://rounds.vin/<route>` BEFORE the phase begins. Store in `docs/parity-audits/screenshots/<phase>-baseline/`.

**Post-implementation**: re-capture at the same viewports. Run `pixelmatch` (or equivalent) against the baseline. Diff > N pixels in any region NOT specified as the change target = defect.

**Tooling**: Playwright has native screenshot + diff support. Add a `parity-<view>.spec.ts` test per affected view.
