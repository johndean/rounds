# Editor — Audit / Word Track Changes (per-session)

Route: `#/e/:id/audit` ([frontend/src/router/index.ts:36](../../frontend/src/router/index.ts#L36)) → [frontend/src/views/EditorAuditView.vue](../../frontend/src/views/EditorAuditView.vue), `props: true` (`id`).

## Purpose

The per-session correction ledger. `EditorAuditView.vue` is a thin wrapper that renders the shared `AuditView` with the session `id` prop, which switches `AuditView` into per-session mode (correction_ledger) and adds a session breadcrumb hop. See [EditorAuditView.vue:1-14](../../frontend/src/views/EditorAuditView.vue#L1). In this mode the screen shows the append-only edit history (text_edit, slide_reassignment, speaker_reassignment, chat/poll inserts, etc.) for one session, with KPIs, type filters, a JSONL export, and the L1 has_user_override invariant card.

## User Types

Any authenticated user. No `adminOnly` meta ([router/index.ts:36](../../frontend/src/router/index.ts#L36)); neither `EditorAuditView.vue` nor `AuditView.vue` contains a role or admin gate.

## Entry Points

- From the Editor: "Audit" button → `/e/:id/audit` ([EditorView.vue:1242](../../frontend/src/views/EditorView.vue#L1242)).
- From SOP view: "Full audit ledger" quick action → `/e/:id/audit` ([SopView.vue:529](../../frontend/src/views/SopView.vue#L529)).
- Direct hash navigation.

Note: the same `AuditView` component also backs the global `#/audit` route ([router/index.ts:41](../../frontend/src/router/index.ts#L41)); that global mode reads `audit_events` instead. This doc covers the per-session mode reached via `EditorAuditView`.

## Navigation Paths

`EditorAuditView.vue` renders no links of its own ([EditorAuditView.vue:12-14](../../frontend/src/views/EditorAuditView.vue#L12)); all navigation comes from the delegated `AuditView`:
- Breadcrumb: `/sessions`, and (per-session) `/e/:id` (session code link) ([AuditView.vue:143-148](../../frontend/src/views/AuditView.vue#L143)).
- No outbound buttons beyond the breadcrumb in per-session mode.

## Components

- `EditorAuditView.vue` imports and renders `AuditView` ([EditorAuditView.vue:7-13](../../frontend/src/views/EditorAuditView.vue#L7)).
- `AuditView` uses `Icon` (shared) and `AuditLedger` ([AuditView.vue:17-18](../../frontend/src/views/AuditView.vue#L17)).
- `AuditLedger` is a presentational table of correction rows; empty array → empty ledger ([AuditLedger.vue:1-8](../../frontend/src/components/audit/AuditLedger.vue#L1)).

## Actions

- **Filter by correction type** — chip row sets `filter` ref; per-session chips are a fixed set (all types, text_edit, chat_insert, chat_edit, poll_insert, slide_reassignment, speaker_reassignment, mark_reviewed, annotation_add) ([AuditView.vue:98-111](../../frontend/src/views/AuditView.vue#L98), [199-211](../../frontend/src/views/AuditView.vue#L199)).
- **Export JSONL** — `exportJsonl()` serializes the loaded corrections to NDJSON and triggers a client-side download named `audit.jsonl` (`data-test-id="audit-wtc-export-jsonl"`) ([AuditView.vue:125-137](../../frontend/src/views/AuditView.vue#L125), [212-214](../../frontend/src/views/AuditView.vue#L212)). No server call — purely a client Blob download.
- There are no edit/undo actions on this screen; the ledger is read-only display (edits happen in the Editor).

## States

- **Per-session vs global:** `globalMode = !props.id`. With the `id` prop present (this route), the title is "Word Track Changes", the eyebrow shows the session code link + "Audit · Word Track Changes (v7)", and the per-session KPIs (Total Corrections, Text Edits dirty, Non-dirty Corrections, Distinct Actors) + the L1 invariant card render ([AuditView.vue:46](../../frontend/src/views/AuditView.vue#L46), [150-196](../../frontend/src/views/AuditView.vue#L150), [223-248](../../frontend/src/views/AuditView.vue#L223)).
- **KPI math:** "Text Edits (dirty)" = `stats.text_edit`; "Non-dirty" = total − text_edit; "Distinct Actors" = unique `actor` count ([AuditView.vue:182-195](../../frontend/src/views/AuditView.vue#L182), [122](../../frontend/src/views/AuditView.vue#L122)).
- **Ledger rows** render newest-first (`[...corrections].reverse()`) and filter by selected type ([AuditLedger.vue:41-44](../../frontend/src/components/audit/AuditLedger.vue#L41)).

## Empty States

- **No corrections:** when not loading and `corrections.length === 0`, a centered message renders: "No corrections yet — audit events accumulate as you edit segments." ([AuditView.vue:218-220](../../frontend/src/views/AuditView.vue#L218)). `AuditLedger` is not rendered in this case.

## Error States

- `load()` wraps both fetches in `.catch(() => null)` / `.catch(() => [])`, so a failed fetch degrades to the empty-state message rather than an error banner ([AuditView.vue:57-60](../../frontend/src/views/AuditView.vue#L57)). There is no dedicated error UI — IMPLEMENTATION NOT FOUND.
- The JSONL export has no failure path beyond the browser's own download handling.

## Loading States

- `loading` ref true during `load()`; renders a centered "Loading audit log…" while in flight, replaced by the ledger or empty-state when settled ([AuditView.vue:217](../../frontend/src/views/AuditView.vue#L217)).

## Permissions

JWT presence only via the global router guard ([router/index.ts:53-67](../../frontend/src/router/index.ts#L53)). No `adminOnly` meta on `#/e/:id/audit` and no email/role gate in `EditorAuditView.vue` or `AuditView.vue`. Any authenticated user can view and export the ledger; the server is authoritative on the underlying endpoints (not asserted from these files).

## Connected APIs

In per-session mode (`props.id` set), `load()` issues ([AuditView.vue:55-62](../../frontend/src/views/AuditView.vue#L55)):
- `sessionsApi.get(id)` → `GET /v1/sessions/{id}` ([api.ts:139-140](../../frontend/src/services/api.ts#L139)) — for the breadcrumb code/title.
- `auditApi.corrections(id)` → `GET /v1/audit/sessions/{id}/corrections` ([api.ts:944-945](../../frontend/src/services/api.ts#L944)) — the correction_ledger rows.

(The global-mode branch would call `auditApi.list({ limit: 500 })` → `GET /v1/audit`, but that path is not taken when the `id` prop is present — [AuditView.vue:63-66](../../frontend/src/views/AuditView.vue#L63), [api.ts:942-943](../../frontend/src/services/api.ts#L942).)

## Data Sources

- **Live (backend):** the corrections list from `GET /v1/audit/sessions/{id}/corrections`; session meta from `GET /v1/sessions/{id}`.
- **Local/derived:** `stats` (per-type counts), `distinctActors`, `distinctKinds`, and the fixed per-session filter `types` list are all computed from the loaded `corrections` array ([AuditView.vue:89-123](../../frontend/src/views/AuditView.vue#L89)).
- **Static:** the L1 invariant card's `allTypes` list and the per-type chip metadata in `AuditLedger` (`correctionTypeLabel`) are static reference data ([AuditView.vue:120](../../frontend/src/views/AuditView.vue#L120), [AuditLedger.vue:26-39](../../frontend/src/components/audit/AuditLedger.vue#L26)).

## Source Verification
- **Files Used:** frontend/src/views/EditorAuditView.vue, frontend/src/views/AuditView.vue, frontend/src/components/audit/AuditLedger.vue, frontend/src/services/api.ts, frontend/src/router/index.ts
- **Components Used:** AuditView, Icon (shared), AuditLedger
- **APIs Used:** GET /v1/sessions/{id}, GET /v1/audit/sessions/{id}/corrections (per-session mode); GET /v1/audit only in the non-taken global branch
- **Database Tables Used:** none read directly by the view; server reads correction_ledger per api.ts/header comments (not asserted from frontend)
- **Permission Logic Used:** JWT presence only (route guard); no admin/role gate in the wrapper or AuditView
- **Confidence Score:** High — EditorAuditView is a thin delegate; per-session AuditView branch fully traced to api.ts.
- **Evidence Links:** [EditorAuditView.vue:1-14](../../frontend/src/views/EditorAuditView.vue#L1), [AuditView.vue:52-85](../../frontend/src/views/AuditView.vue#L52), [api.ts:940-946](../../frontend/src/services/api.ts#L940)
