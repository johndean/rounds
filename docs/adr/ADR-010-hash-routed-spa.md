# ADR-010 — Hash-routed SPA

- **Status:** Accepted
- **Date:** 2026-05-17 (bootstrap), refined 2026-06-05
- **Deciders:** johndean@vin.com
- **Related:** [ADR-009](./ADR-009-editor-architecture.md)

## Context

The Rounds frontend is a Vue 3 SPA served from `frontend/dist/` and mounted at `app/main.py:210` behind the FastAPI app. Two routing models exist for Vue Router:

- **History mode** — clean URLs like `https://rounds.vin/sessions/abc-123`. Requires the server to fall back every unmatched path to `index.html` so client-side routing can take over.
- **Hash mode** — URLs like `https://rounds.vin/#/sessions/abc-123`. Server only ever serves `index.html`; everything after `#` is client-side.

The bootstrap deploy hit both Railway's static file serving + the FastAPI fallback, plus the Vue HTML prototype was already using hash routing.

## Decision

**We use hash routing (`/#/...`).** The Vue Router instantiates with `createWebHashHistory()`. Server-side, FastAPI mounts a SPA fallback at `app/main.py:221` that serves `index.html` for any unmatched path, but in practice the fallback is rarely hit because every link uses `/#/...`.

## Consequences

- **Positive.**
  - No server-side route table maintenance — `index.html` is the only frontend asset that needs to be served.
  - Direct deep links (paste a URL, hit Enter) work without server cooperation.
  - Matches the prototype's URL shape, so screenshots and Playwright specs port without adjustment.
  - Static-asset CDNs (Railway's, in this case) don't need fallback rules.
- **Negative.**
  - URLs are uglier (`#/sessions/abc` vs `/sessions/abc`). Some users care; most don't.
  - Server-side analytics that read the URL path see only the SPA root — fragment-based analytics requires the client to send the fragment explicitly.
  - SEO is irrelevant for this app (internal tool, auth-gated), so the SEO-friendliness of history mode isn't a draw.
- **Risks.**
  - If a future need for SSR or static-site generation appears, hash mode is incompatible — would require a routing-mode flip + every link update.

## Code locations

- `frontend/src/router/index.ts` — `createWebHashHistory()`
- `frontend/index.html` — entry HTML
- `app/main.py:221` — SPA fallback (still present as a safety net)
- `docs/port-source/Transcript Software v4 - Vue.html` — original prototype using hash mode

## Alternatives considered

1. **History mode with FastAPI SPA fallback** — viable. Rejected at bootstrap to avoid the fallback failure modes (e.g. a typo in a deep link returns `index.html` with a 200, which masks broken links during dev).
2. **History mode behind a dedicated frontend CDN** — overengineered for the current scale.
3. **No routing — single-page editor with no URL state** — rejected because the editor uses URL for `session_id` and the dashboard uses URL for filter state.

## When this ADR should be revisited

- If SSR / static-site generation becomes a goal.
- If clean URLs become a hard requirement (executive request, SEO need, link-sharing-with-non-tech-stakeholders).
