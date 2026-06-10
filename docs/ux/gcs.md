# GCS Pipeline QA (`#/gcs`)

A read-only dashboard for the GCS-side ingestion plane. Implemented in [frontend/src/views/GcsView.vue](../../frontend/src/views/GcsView.vue), described in its own docstring as a "Faithful 1:1 port of docs/port-source/processing.jsx::GcsRoute" ([GcsView.vue:1-5](../../frontend/src/views/GcsView.vue#L1)).

> IMPORTANT — this route's view renders a **hardcoded static fixture**, not live data. The 14 checks, their pass/fail flags, latencies, the KPI numbers ("00:01:42", "99.98%", "0 open pages"), and the note text are all literal constants in the component ([GcsView.vue:11-26](../../frontend/src/views/GcsView.vue#L11), [GcsView.vue:41-59](../../frontend/src/views/GcsView.vue#L41)). It makes no API calls. A separate, live-probing GCS QA surface exists under Settings → Diagnostics → GCS ([frontend/src/components/settings/GCSDebug.vue](../../frontend/src/components/settings/GCSDebug.vue)), which calls `GET /v1/diag/gcs-checks`; that is documented in [settings-sections.md](./settings-sections.md). The `#/gcs` route view itself is static.

## Purpose

Present a static "14 checks across the GCS-side ingestion plane" ledger with KPI tiles. Copy states each check runs on a 5-minute cadence, results stream into the audit ledger, and failures trigger PagerDuty after two consecutive misses ([GcsView.vue:37-40](../../frontend/src/views/GcsView.vue#L37)). PARTIALLY IMPLEMENTED: the descriptive copy describes a live system, but the view does not fetch or stream anything — the data is a fixture array.

## User Types

Any authenticated user. No role gating in the view or on the route.

## Entry Points

- Hash route `#/gcs`, registered as the `gcs` named route ([frontend/src/router/index.ts:42](../../frontend/src/router/index.ts#L42)).
- Settings → Diagnostics has a button "Open GCS QA →" but it navigates to the embedded `GCSDebug` sub-view (`view = 'gcs'`), NOT to the `#/gcs` route ([frontend/src/components/settings/SectionDiagnostics.vue:62](../../frontend/src/components/settings/SectionDiagnostics.vue#L62)). NOT VERIFIED IN CODE: any nav-chrome link that targets `#/gcs` directly.

## Navigation Paths

None. The view has no router calls, no links, and no buttons.

## Components

- `Icon` from `@/components/shared/Icon.vue` — used inside the status chips (`name="check"` for pass, `name="alert"` for retrying) ([GcsView.vue:7](../../frontend/src/views/GcsView.vue#L7), [GcsView.vue:73-74](../../frontend/src/views/GcsView.vue#L73)).

DOM structure (all static markup):
- `main.page[data-screen-label="GCS QA"]` ([GcsView.vue:32](../../frontend/src/views/GcsView.vue#L32)).
- `div.page-eyebrow` breadcrumb "Operations / GCS Pipeline QA" ([GcsView.vue:33-35](../../frontend/src/views/GcsView.vue#L33)).
- `h1.page-title` + `p.page-desc` ([GcsView.vue:36-40](../../frontend/src/views/GcsView.vue#L36)).
- `div.kpi-row` with four `div.kpi` tiles: Checks Passing (`{{ okCount }}/14`), Last Sweep ("00:01:42", "cadence 5 min"), 7-Day Uptime ("99.98%"), Open Pages ("0") ([GcsView.vue:41-59](../../frontend/src/views/GcsView.vue#L41)).
- `div.audit-ledger` — a head row (`audit-row audit-row--head`) plus one `audit-row` per check, columns ID / Check / Status / Latency / Note via inline `gridTemplateColumns` ([GcsView.vue:60-79](../../frontend/src/views/GcsView.vue#L60)).

## Actions

None. There are no interactive elements — no buttons, inputs, or links.

## States

- The only reactive value is `okCount`, a computed count of checks where `ok === true` ([GcsView.vue:28](../../frontend/src/views/GcsView.vue#L28)). For the fixture, 13 of 14 pass; G13 ("PII redaction sentinel") is `ok: false` and renders the amber "retrying" chip ([GcsView.vue:24](../../frontend/src/views/GcsView.vue#L24), [GcsView.vue:73-75](../../frontend/src/views/GcsView.vue#L73)).
- Per-row status: `v-if="c.ok"` → green "pass" chip; `v-else` → amber "retrying" chip ([GcsView.vue:72-75](../../frontend/src/views/GcsView.vue#L72)).
- Note column shows `c.note` or "—" ([GcsView.vue:77](../../frontend/src/views/GcsView.vue#L77)).

## Empty States

IMPLEMENTATION NOT FOUND. The check list is a non-empty hardcoded array of 14 entries; there is no empty branch.

## Error States

IMPLEMENTATION NOT FOUND. No fetch occurs, so there is no error path. (A per-check "fail" visual exists as the amber chip, but it reflects fixture data, not a runtime error.)

## Loading States

IMPLEMENTATION NOT FOUND. No async load occurs; the data is rendered synchronously from a constant.

## Permissions

JWT presence only. The global router guard requires authentication for `#/gcs` (no `public` meta), redirecting unauthenticated users to login ([frontend/src/router/index.ts:53-62](../../frontend/src/router/index.ts#L53)). No `adminOnly` meta on this route and no `johndean@vin.com` gate in the view. Role tiers are not active here.

## Connected APIs

None. The view imports no API module and makes no HTTP calls.

## Data Sources

Hardcoded in-component:
- `checks: Check[]` — 14 literal entries (G1–G14) with `id`, `name`, `ok`, `ms`, optional `note` ([GcsView.vue:9-26](../../frontend/src/views/GcsView.vue#L9)).
- KPI tile values are literal strings/computed-from-fixture ([GcsView.vue:42-58](../../frontend/src/views/GcsView.vue#L42)).

## Source Verification
- **Files Used:** frontend/src/views/GcsView.vue; frontend/src/router/index.ts; frontend/src/components/settings/SectionDiagnostics.vue; frontend/src/components/settings/GCSDebug.vue; frontend/src/components/shared/Icon.vue (referenced)
- **Components Used:** Icon
- **APIs Used:** none (route view); the live probe `GET /v1/diag/gcs-checks` lives in the separate Settings GCSDebug surface
- **Database Tables Used:** none
- **Permission Logic Used:** JWT presence (global router guard); no role gate
- **Confidence Score:** High — the view was read in full; it is unambiguously a static fixture with no API, loading, empty, or error branches.
- **Evidence Links:** [GcsView.vue:11](../../frontend/src/views/GcsView.vue#L11), [GcsView.vue:28](../../frontend/src/views/GcsView.vue#L28), [router/index.ts:42](../../frontend/src/router/index.ts#L42)
