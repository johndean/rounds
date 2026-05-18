# Playwright suite

Three specs, single chromium project, single config.

| Spec | What it verifies | Count |
|---|---|---|
| `smoke.spec.ts` | Every hash route loads, key surface classes render, no console errors, all 12 settings sections render, all 4 editor tabs swap correctly, localStorage persistence works | 16 |
| `interactions.spec.ts` | Modals open/close, ⌘K palette has 12 entries, ⌘. tweaks toggle, brand-toggle flips CSS variable, inline Edit toolbar has 14 buttons, Reassign shows 24 tiles, Speaker picker shows 3 tiles, Download menu has 4 options, Suggest Improvement submits and prepends, Email Builder drill, GCS QA 14 rows, Email Debug 5 sections, Types matrix 8 rows, Prompt Templates New form opens | 18 |
| `visual.spec.ts` | Full-page screenshot diffs for every route + state + overlay. Baselines committed under `visual.spec.ts-snapshots/`. Tolerance: `maxDiffPixelRatio: 0.005` (0.5% of pixels can differ before failing) | 43 |

**Total: 77 tests.**

## Commands

```bash
npm run test               # all three specs (smoke + interactions + visual)
npm run test:smoke         # just route smoke
npm run test:interactions  # just interactions
npm run test:visual        # just visual diff against baselines
npm run test:visual:update # refresh visual baselines after intentional UI change
npm run test:report        # open the last HTML report
```

The Vite dev server is auto-started by `webServer` in `playwright.config.ts`.

## Auth bypass

Tests don't hit the live backend. `helpers.ts::bypassAuth(page)` plants a fake
JWT + persisted email in localStorage and intercepts `/v1/auth/me` + every other
`/v1/*` call with `200 / []` so fixture-driven views render unaltered.

## Baselines are platform-specific

Snapshot filenames include the platform (`-chromium-win32.png`). Linux CI runs
the same specs but the visual job is marked `continue-on-error: true` until
matching Linux baselines are committed — capture them on a Linux runner via
`npm run test:visual:update` and commit the resulting `*-chromium-linux.png`
files.
