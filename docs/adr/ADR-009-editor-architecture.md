# ADR-009 — Editor architecture: React SSOT + Vue port discipline

- **Status:** Accepted
- **Date:** 2026-05-17 (mandate established), refined 2026-06-05
- **Deciders:** johndean@vin.com
- **Related:** [ADR-005](./ADR-005-corrections-ledger.md), [ADR-010](./ADR-010-hash-routed-spa.md)

## Context

Rounds inherits its UI surface from a React prototype at `docs/port-source/*.jsx`. The prototype was built first, against fixtures, and is the only place where layout, class names, DOM structure, data-test-ids, and the full set of interactions are pixel-correct. The production app is Vue 3.

When work began on porting the prototype to Vue, two competing sources of truth emerged:

- The React JSX files (the original prototype).
- An experimental Vue 3 HTML port (`docs/port-source/Transcript Software v4 - Vue.html`) that was shipped alongside the React source.

These two diverged: the Vue HTML had simplifications, missing data-test-ids, and behavioral gaps. Using both as sources of truth produces inconsistent ports.

## Decision

**The React JSX in `docs/port-source/*.jsx` is the single source of truth for the editor (and every other ported view). The Vue HTML is a visual aid only and explicitly NOT a porting source.**

Per direct user directive on 2026-05-17 (recorded in CLAUDE.md): *"the react version is 100% accurate and is SSOT."*

Porting rules (CLAUDE.md "Porting rules" section, restated here for ADR completeness):

1. Read `docs/port-source/<ViewName>.jsx` first.
2. Match class names exactly so bundled `app.css` styles apply.
3. Preserve `data-test-id` attributes for Playwright + DX continuity.
4. Replace mock state with real backend — fixtures in `data.jsx` map to live endpoints in `frontend/src/services/api.ts`. Mock `toast.push` / `confirm.open` / `modal.open` map to composables. Mock `wired.*` maps to `services/wired.ts`.
5. No scaffolding banners. No "placeholder" comments. No "TODO Phase X." If a section can't be ported faithfully, port what is well-defined and leave the rest absent — don't fake it.
6. Test visual diff against the Vue HTML reference at `https://rounds.vin/prototype.html` and the React HTML render.

The editor (`frontend/src/views/EditorView.vue` — 1,164 LOC) is the most complex ported view. It orchestrates 17 sub-components in `frontend/src/components/editor/`. All of them follow the same porting discipline.

## Consequences

- **Positive.**
  - One source of truth means one place to look when behavior is in question.
  - `data-test-id` continuity preserves Playwright spec stability across the port.
  - The bundled `app.css` (copied verbatim from the prototype) applies to the ported Vue components with no rewrite.
- **Negative.**
  - The JSX is a static prototype — it doesn't run against real data, so the porter has to imagine how each interaction integrates with the live backend.
  - Some React idioms (hooks, render props) don't map cleanly to Vue — the porter is doing translation work, not literal copying.
  - The Vue HTML reference is not authoritative even though it's a Vue artifact. New developers can be confused by this — CLAUDE.md is explicit about it.
- **Risks.**
  - A future feature added to the React prototype that isn't ported quickly leaves the Vue app behind. We mitigate by treating the prototype as frozen unless a new feature requires its update.
  - The 17 editor sub-components were ported across many days — a regression in one is not always caught by the others' tests.

## Code locations

- `docs/port-source/` — 16 JSX files + `data.jsx` (fixtures) + 5 CSS files + entry HTML + assets
- `docs/port-source-gap-analysis.md` — the analysis that confirmed the Vue HTML's omissions and locked React as SSOT
- `frontend/src/views/EditorView.vue` — orchestrator
- `frontend/src/components/editor/` — 17 ported sub-components
- `frontend/src/services/api.ts` — live-backend wiring layer that replaces the prototype's `wired.*` mock namespace
- `frontend/src/composables/` — `toast`, `confirm`, `modal` (replace mock equivalents)
- `frontend/src/styles/*.css` — copied verbatim from the prototype

## Alternatives considered

1. **Use the Vue HTML as the porting source** — rejected after gap-analysis showed missing data-test-ids and behavioral simplifications. See `docs/port-source-gap-analysis.md`.
2. **Rewrite the prototype in Vue first, then port to production code** — rejected because it would double the work and create a third source of truth.
3. **Hand the prototype to a designer to redo from scratch** — rejected because the prototype is already pixel-correct and the design has converged.

## When this ADR should be revisited

- If the prototype receives a major redesign — the SSOT remains React, but the port discipline needs to refresh.
- If the team scales beyond 1–2 frontend developers — the discipline becomes harder to keep consistent without explicit per-component port-review checklists.
- If a feature is invented in Vue first (because it's a backend-driven feature with no JSX equivalent), this ADR needs an addendum on how to back-port that to the JSX so the SSOT stays current.
