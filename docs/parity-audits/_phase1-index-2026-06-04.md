# Phase 1 Index — Stakeholder Remediation Baseline

**Generated**: 2026-06-04 against tip `6df4170` (post-F1.E)
**Anchor tag**: `stakeholder-remediation-baseline-2026-06-04` (pushed to both `origin` and `production`)

Phase 1 of the stakeholder remediation mandate requires four cross-cutting reports plus per-surface baseline inventories. Per the mandate: *"No code changes until all reports are complete."* This index links them all.

## Mandate reports (cross-cutting synthesis)
- [Dependency report](./phase1-dependency-report-2026-06-04.md) — which phases depend on which artifacts; ordering constraints
- [Risk report](./phase1-risk-report-2026-06-04.md) — top risks across all 10 phases, ranked
- [Impact report](./phase1-impact-report-2026-06-04.md) — files, components, APIs, migrations touched per phase
- [Rollback report](./phase1-rollback-report-2026-06-04.md) — per-phase rollback procedures

## Per-surface baseline inventories
- [SessionsView + SessionDetailView](./phase1-sessionsview-sessiondetail-baseline-2026-06-04.md) — Phase 3 scope
- [EditorView + sub-components](./phase1-editorview-baseline-2026-06-04.md) — Phases 4 / 5 / 6 scope
- [SopView + DashboardView](./phase1-sop-dashboard-baseline-2026-06-04.md) — Phase 7 scope
- [HelpCenter integration surface](./phase1-helpcenter-baseline-2026-06-04.md) — Phase 2 scope

## Adjacent investigations (run in parallel with Phase 1)
- [Open Builder permissions audit](../audits/permissions-open-builder-2026-06-04.md) — Phase 8 root cause
- [Spellcheck feasibility research](../research/spellcheck-grammarly-2026-06-04.md) — Phase 9 GO/NO-GO

## Decision points surfaced (require stakeholder input before Phase 2+ implementation)
1. **Phase 3 premise mismatch** — there is no Chat Count panel in SessionsView today. Clarification needed: does "move chat count" mean (a) move the EditorView right-rail chat-count badge to SessionDetail, (b) add a new chat-count tile to SessionDetail with no source-side removal, or (c) re-confirm with stakeholder?
2. **Phase 7 quick-win**: existing `email_templates` API (`app/api/email_templates.py`) is 80% of the configurable-template requirement. F1.E's SMTP path uses inline f-strings instead — wiring it through `POST /v1/email-templates/resolve` is the smallest correct Phase 7 win. Authorize?
3. **Phase 8 fix scope**: Open Builder issue is a hardcoded `user.email != "johndean@vin.com"` admin gate at `app/api/email_templates.py:39-44` (and 4 sibling places). `auth_users.role` column already exists (migration 045) but is never consulted. Fix is a single-helper extraction. Authorize?
4. **Phase 9 stakeholder decisions** — Grammarly Embedded SDK is dead (shutdown 2024-01-10). Recommended replacement is self-hosted LanguageTool + Hunspell medical dictionary + optional Claude Haiku polish button. Decisions deferred:
   - BAA status with Anthropic/Google (gates the LLM "polish" layer)
   - GPLv3 medical-dictionary license sign-off
   - UX target: inline squiggles vs. sidebar list
   - Latency budget: <200ms (client-side) vs. 500-800ms (server roundtrip)
   - Scale assumption (~10 editors, ~50M chars/mo) — confirm or correct

## What did NOT change in Phase 1
- No source code modified anywhere.
- No production deploy beyond F1 (already shipped before mandate landed; reconciled as in-scope per user direction).
- No third-party services added or configured.
- No new dependencies introduced.
