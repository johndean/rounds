# Phase 1 — Dependency Report

**Generated**: 2026-06-04 against tip `6df4170` (post-F1.E)

Cross-phase dependency map for the stakeholder remediation. "Depends on" means the named artifact must exist or be modified before the phase can land cleanly.

## Phase-to-phase dependencies

```
Phase 1 (Inventory — DONE) ──► Gates everything else (per mandate)

Phase 2 (HelpCenter)
  └─ Depends on: AppHeader.vue tools cluster + App.vue global host slot. Both exist.
  └─ Independent of all other phases. Can ship first.

Phase 3 (Chat Count panel move)
  ├─ BLOCKED on stakeholder clarification (premise mismatch — see Phase 3 baseline)
  └─ If re-scoped to "add to SessionDetail":
      └─ Depends on: either (a) a chat-count field on SessionSummary
                        or (b) a 9th fetch in SessionDetailView.load() — already 8 parallel fetches today
      └─ Independent of other phases once scoped.

Phase 4 (Video ↔ Segment timestamp sync)
  └─ Depends on:
      ├─ Extending SegmentPatch (app/api/segments.py:37-42) to accept start_ms/end_ms
      ├─ Adding a "time_edit" kind to the correction ledger (migration delta)
      └─ EditorView.vue shared time ref (already exists at L320-323)
  └─ Independent of Phases 5, 6, 7 (different surfaces inside EditorView).

Phase 5 (Segment formatting — soft/hard returns)
  └─ Depends on:
      ├─ Segment.text data type supporting embedded \n (already a TEXT column; verify Vue editor preserves them)
      ├─ artifact_transformer.py (634 LOC) — per-format line-break logic differs across CMS/DOCX/SRT/VTT/TXT
      └─ Today: CMS preserves paragraphs; DOCX collapses to one paragraph per segment; SRT wraps at 42 chars
  └─ Touches same EditorView shell as Phases 4, 6, but no logic overlap.

Phase 6 (Poll & Chat reordering)
  └─ Depends on:
      ├─ NEW order_index column on chat_messages + polls tables (migration required)
      ├─ NEW backend endpoint to persist reorder
      ├─ NEW client drag-reorder lib (Sortable.js, vue-draggable-next, or hand-rolled) — none present today
      └─ Today: outward drag exists (drop onto transcript pane); sibling drag-reorder does NOT
  └─ Independent of other phases.

Phase 7 (Workflow automation)
  └─ Depends on (STRONGLY):
      ├─ app/api/email_templates.py (already exists — 287 LOC, CRUD, /resolve endpoint)
      ├─ app/tasks/sop_tasks.py::_maybe_send_deadline_email (just shipped F1.E with inline f-strings)
      └─ Quick-win: replace inline f-strings with a call to email_templates_resolve_internal()
  └─ Additional surfaces for "ownership/status/queue visibility":
      ├─ SopView.vue palette → sop_state.assignees wire-up (pre-existing bug — flagged separately)
      └─ New per-user queue view (no /mine, /inbox, /queue route today)

Phase 8 (Open Builder permissions)
  └─ Depends on: shared role helper (does NOT exist today) — auth_users.role column exists (migration 045)
                  but get_current_user does not load it. Fix shape: load role into CurrentUser; replace 5
                  email-literal checks with role-based require_admin().
  └─ Independent of all other phases. Can ship before any UX work.

Phase 9 (Spellcheck research) — research only, no implementation
  └─ Future Phase 9.5 (if GO): LanguageTool Docker service + Hunspell dictionary asset bundle.
      Independent of other phases.

Phase 10 (Validation) — gates EVERY prior phase. Cannot land before its parent phase ships.
```

## Cross-cutting shared surfaces

| Surface | Touched by phases | Conflict risk |
|---|---|---|
| `app/tasks/sop_tasks.py` | F1.E (shipped), Phase 7 | LOW — Phase 7 is additive (resolver call). Same function, one block insertion. |
| `EditorView.vue` shell | Phases 4, 5, 6 | LOW — different sub-components per phase. |
| `app/api/email_templates.py` | Phase 8 (admin gate fix) | LOW — single helper extraction. |
| `app/security/roles.py` (new file) | Phase 8 | Net new. Adopted by `email_templates.py`, `settings.py`, `email_debug.py`. |
| `frontend/src/components/AppHeader.vue` | Phase 2 (one button) | LOW — adds one icon-button to existing tools cluster. |
| `frontend/src/App.vue` | Phase 2 (one mount) | LOW — one `<HelpCenterDrawer />` host alongside existing `<TweaksPanel />`. |

## Recommended ordering (lowest-risk first)

1. **Phase 8** — single-helper fix, root cause known, smallest diff (likely ~30 LOC across 4 files). Ship first.
2. **Phase 2** — greenfield, no shared-surface risk, easy rollback.
3. **Phase 7 quick-win** — wire F1.E through `email_templates_resolve_internal()`. ~50 LOC. Resolver already exists.
4. **Phase 4** — extend `SegmentPatch`, add `time_edit` ledger kind, wire EditorView click→seek + time→highlight.
5. **Phase 5** — preserve segment text newlines through editor + adjust DOCX line-break logic.
6. **Phase 6** — migration + reorder lib + drag handler. Largest net-new surface.
7. **Phase 3** — only after stakeholder clarifies the premise.
8. **Phase 9** — defer until stakeholder decisions land (BAA, license, UX, latency).

Phases 4, 5, 6 share EditorView but no logic overlap — can be parallelized across separate commits with no conflict.
