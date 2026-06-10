# Settings (`#/settings/:section?`)

The settings shell: a left nav of 13 sections plus a content pane that swaps in one `Section*` component per selection. Implemented in [frontend/src/views/SettingsView.vue](../../frontend/src/views/SettingsView.vue). The view's docstring calls it a verbatim port of `improvements.jsx::SettingsRoute` + `settings-pages.jsx::SettingsRouterPane` ([SettingsView.vue:1-17](../../frontend/src/views/SettingsView.vue#L1)).

Each section component is documented in detail in [settings-sections.md](./settings-sections.md). This page covers the shell only.

## Purpose

Provide a single deep-linkable home for workspace configuration: org identity, team/roles, session types & stage-assignee matrix, AI model defaults, upload transport, discrepancy-classifier config, export options, prompt templates, session manifest reference, email templates, auth/login management, operational diagnostics, and deleted-session recovery ([SettingsView.vue:38-52](../../frontend/src/views/SettingsView.vue#L38)).

## User Types

Any authenticated user can reach the shell. Individual sections degrade based on the backend: several sections (Auth & Logins, Deleted sessions, the email/GCS diagnostics) are admin-gated **server-side** and render a 403 banner or error toast for non-admins — see [settings-sections.md](./settings-sections.md). The shell itself applies no client-side gate.

## Entry Points

- Hash route `#/settings/:section?`, registered as the `settings` named route with `props: true` so the `:section` param is passed to the component ([frontend/src/router/index.ts:40](../../frontend/src/router/index.ts#L40)).
- The optional `:section` param deep-links a section; absent, it defaults to `general` ([SettingsView.vue:54](../../frontend/src/views/SettingsView.vue#L54)).

## Navigation Paths

- **Section switch** — clicking a nav button calls `pick(id)` → `router.push('/settings/<id>')` ([SettingsView.vue:56-58](../../frontend/src/views/SettingsView.vue#L56)). The active section is driven by the route param, not local state ([SettingsView.vue:54](../../frontend/src/views/SettingsView.vue#L54)).
- Several child sections push to their own internal sub-views via local refs (e.g. Email → builder, Diagnostics → test/gcs, Prompt templates → new/edit) — those are in-component, not route changes. The Prompt-templates "← Settings" back button uses `history.back()` ([frontend/src/components/settings/SectionPromptTemplates.vue:88-91](../../frontend/src/components/settings/SectionPromptTemplates.vue#L88)).

## Components

- `main.settings-page[data-screen-label="Settings"]` — two-pane layout ([SettingsView.vue:62](../../frontend/src/views/SettingsView.vue#L62)).
- `aside.settings-nav` — `h2.page-title` "Settings" + a `<ul>` of `button.settings-nav__item`, one per section; the active one gets `is-active` ([SettingsView.vue:63-73](../../frontend/src/views/SettingsView.vue#L63)).
- `section.settings-content` — renders exactly one `Section*` via a `v-if`/`v-else-if` chain keyed on `active`, with `SectionGeneral` as the final `v-else` fallback ([SettingsView.vue:74-89](../../frontend/src/views/SettingsView.vue#L74)).

The 13 sections (id → label → component), all imported at [SettingsView.vue:20-32](../../frontend/src/views/SettingsView.vue#L20) and mapped at [SettingsView.vue:38-52](../../frontend/src/views/SettingsView.vue#L38):

| id | label | component |
|---|---|---|
| `general` | General | SectionGeneral |
| `team` | Team & roles | SectionTeam |
| `types` | Types & stage defaults | SectionTypes |
| `ai-models` | AI models | SectionAIModels |
| `upload` | Upload & storage | SectionUpload |
| `discrepancy` | Discrepancy classification | SectionDiscrepancy |
| `export` | Export | SectionExport |
| `prompts` | Prompt templates | SectionPromptTemplates |
| `manifest` | Session manifest | SectionManifest |
| `email` | Email | SectionEmail |
| `auth-users` | Auth & logins | SectionAuthUsers |
| `diagnostics` | Diagnostics | SectionDiagnostics |
| `deleted` | Deleted sessions | SectionDeleted |

Note the section-list label for `prompts` is "Prompt templates" and for `manifest` is "Session manifest" ([SettingsView.vue:46-47](../../frontend/src/views/SettingsView.vue#L46)).

## Actions

The shell's only action is section selection (`pick`). All data-mutating actions live in the child sections — see [settings-sections.md](./settings-sections.md).

## States

- `active` is a computed off `props.section ?? 'general'` ([SettingsView.vue:54](../../frontend/src/views/SettingsView.vue#L54)).
- The section list is `Object.freeze`-d so it is immutable at runtime ([SettingsView.vue:38](../../frontend/src/views/SettingsView.vue#L38)).
- An unknown `:section` value falls through the `v-else-if` chain to the `SectionGeneral` `v-else`, so a bad deep-link silently shows General ([SettingsView.vue:88](../../frontend/src/views/SettingsView.vue#L88)).

## Empty States

Not applicable at the shell level — exactly one section always renders. Per-section empty states are documented in [settings-sections.md](./settings-sections.md).

## Error States

IMPLEMENTATION NOT FOUND at the shell level — the shell has no async work, so no error branch. Per-section error handling (toasts, 403 banners, error text) is documented in [settings-sections.md](./settings-sections.md).

## Loading States

IMPLEMENTATION NOT FOUND at the shell level — section components are statically imported (not lazy/async), so there is no shell-level loading branch. Each section manages its own `loading` ref and "Loading…" markup.

## Permissions

JWT presence only at the shell. The global router guard requires authentication for `#/settings/...` (no `public` meta) ([frontend/src/router/index.ts:53-62](../../frontend/src/router/index.ts#L53)). The shell has no `adminOnly` meta and applies no `johndean@vin.com` client gate. Admin restrictions on individual sections are enforced **server-side** — child sections surface a 403 as an error banner/toast (e.g. SectionDeleted's `forbidden` banner, SectionAuthUsers' and EmailDebug's 403 toasts). Role tiers are not active in the client; the real gate is JWT plus the backend's hardcoded admin-email check on those routes.

## Connected APIs

None directly from the shell. Every API call originates inside a child section — enumerated in [settings-sections.md](./settings-sections.md).

## Data Sources

The `sections` array is the only data the shell owns — a frozen literal of 13 `{ id, label }` items ([SettingsView.vue:38-52](../../frontend/src/views/SettingsView.vue#L38)). Section data sources are in [settings-sections.md](./settings-sections.md).

## Source Verification
- **Files Used:** frontend/src/views/SettingsView.vue; frontend/src/router/index.ts; frontend/src/components/settings/SectionPromptTemplates.vue (back-button reference)
- **Components Used:** SectionGeneral, SectionTeam, SectionTypes, SectionAIModels, SectionUpload, SectionDiscrepancy, SectionExport, SectionPromptTemplates, SectionManifest, SectionEmail, SectionAuthUsers, SectionDiagnostics, SectionDeleted
- **APIs Used:** none (shell); see settings-sections.md
- **Database Tables Used:** none (shell)
- **Permission Logic Used:** JWT presence (router guard); per-section admin gating is server-side
- **Confidence Score:** High — shell read in full; the section→component mapping and routing are unambiguous.
- **Evidence Links:** [SettingsView.vue:38](../../frontend/src/views/SettingsView.vue#L38), [SettingsView.vue:54](../../frontend/src/views/SettingsView.vue#L54), [SettingsView.vue:75-89](../../frontend/src/views/SettingsView.vue#L75), [router/index.ts:40](../../frontend/src/router/index.ts#L40)
