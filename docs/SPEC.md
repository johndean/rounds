# Spec sources & open dependencies

This file tracks the authoritative spec inputs for Rounds and any unresolved retrieval gaps.

## Authoritative inputs

| Input | Status | Where it lives |
|---|---|---|
| **Frontend design (`IMPLEMENTATION.md` — Transcript Software v4 zero-gap reference, v4.0.0-ssot-r2)** | Pinned in planning conversation | Paste into `docs/IMPLEMENTATION.md` when convenient — currently referenced from the build plan. |
| **Backend audit (MIC GCS / Railway / AI services duplication reference, 2026-05-17)** | Pinned in planning conversation | Paste into `docs/MIC-AUDIT.md` when convenient — currently referenced from the build plan. |
| **Build plan** | Repo-local | [`docs/plans/2026-05-17-001-feat-rounds-bootstrap-plan.md`](./plans/2026-05-17-001-feat-rounds-bootstrap-plan.md) |

## Open retrieval gap — prototype CSS bundle

The pixel-by-pixel target is the original `Transcript Software v4.html` bundle hosted at:

> `https://api.anthropic.com/v1/design/h/S_rIYpJehhJHtk_vXKpUbQ?open_file=Transcript+Software+v4.html`

Programmatic fetch via `WebFetch` failed with `maxContentLength size of 10485760 exceeded` (the bundle exceeds the 10 MB fetch ceiling).

The bundle contains 4 CSS files we need verbatim per the build plan (Key Technical Decisions §4):

| File | LOC (approx) | Reconstructed in scaffold? | Status |
|---|---|---|---|
| `colors_and_type.css` | ~175 | **Yes** — reconstructed from IMPLEMENTATION.md §4 documented tokens. May still differ from the prototype byte-for-byte. | needs prototype verification |
| `app.css` | ~3000 | **No** — placeholder only. Minimum styles for scaffold to render. | **blocks Phase 10** |
| `wiring.css` | ~100 | **No** — minimal placeholder. | **blocks Phase 10** |
| `settings.css` | ~280 | **No** — minimal placeholder. | **blocks Phase 10** |

The 16 JSX files in the bundle (`components.jsx`, `wiring.jsx`, `data.jsx`, `editor.jsx`, etc.) are the **port source** for Vue SFCs in Phases 2-4. Without the bundle we are inferring behavior from `IMPLEMENTATION.md` prose alone, which works for structure but not for exact CSS class names, exact JSX prop shapes, or exact fixture values in `data.jsx`.

### Retrieval attempts (2026-05-17)

| Approach | URL | Result |
|---|---|---|
| Base bundle fetch | `…/h/S_rIYpJehhJHtk_vXKpUbQ?open_file=Transcript+Software+v4.html` | **HTTP 200 but exceeds 10 MB Claude-side limit** — body discarded. |
| Per-file query param | `…/h/S_rIYpJehhJHtk_vXKpUbQ?open_file=app.css` (and `wiring.css`, `settings.css`, `colors_and_type.css`) | **HTTP 404** — `?open_file=` is a viewer UI hint, not a file router. |
| Path-based | `…/h/S_rIYpJehhJHtk_vXKpUbQ/app.css` (and `/`) | **HTTP 404** — viewer SPA, no static path serving. |

Conclusion: the design URL serves a JS-rendered viewer; raw file contents are not directly reachable via WebFetch. **Agent-driven retrieval blocked.**

### Manual retrieval (recommended)

1. Open the design URL in a browser: <https://api.anthropic.com/v1/design/h/S_rIYpJehhJHtk_vXKpUbQ?open_file=Transcript+Software+v4.html>
2. Use the design viewer's built-in download / export, OR view each file in the viewer's file picker (sidebar lists every file in the bundle) and copy the contents out one file at a time, OR open browser DevTools → Network tab while the viewer loads, capture the raw responses for each `.css` / `.jsx` / `.html` file.
3. Drop the recovered files into a tmp folder, then:
   - `cp tmp/colors_and_type.css frontend/src/styles/colors_and_type.css`  (replaces the reconstructed version)
   - `cp tmp/app.css frontend/src/styles/app.css`  (replaces placeholder)
   - `cp tmp/wiring.css frontend/src/styles/wiring.css`  (replaces placeholder)
   - `cp tmp/settings.css frontend/src/styles/settings.css`  (replaces placeholder)
   - Save JSX modules to `tmp/port-source/*.jsx` — they are **read-only references** for Phase 2-4 Vue SFC port work (do not import them; they're the source we're porting from).

Until the bundle is in-repo, Phase 10 pixel-diff verification will not pass. The plan's other phases can proceed independently.

## Other open items

- **Login screen design** — out of scope for IMPLEMENTATION.md (which documents the internal app surface only). Per memory `feedback_cevin_internal_design.md`, internal pages use the MIC-aesthetic (dark topbar + sans-serif); the Login screen uses Instrument Serif. Rounds inherits this — Login design TBD before Phase 8 wiring (U55).
- **Backend audit verbatim copy** — same paste-from-conversation approach as IMPLEMENTATION.md.
- **VIN logo asset** — referenced in IMPLEMENTATION.md §3 ("VIN logo (light variant)"). Needs asset retrieval from VIN brand resources. Placeholder text used in `AppHeader.vue` until then.
