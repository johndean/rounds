# Admin Help Editor (`#/admin/help`)

The Help Center CMS — where operators author, edit, publish, archive, and version the help articles end users see in-app. Implemented in [frontend/src/views/admin/HelpEditor.vue](../../frontend/src/views/admin/HelpEditor.vue).

## Purpose

Manage help-article content: a filterable list of all articles, a coverage report, an article editor dialog, version history with restore, and a bulk-AI admin toolbar (publish-all / Fix CC-Rounds / Expand Steps / Expand FAQs / Generate FAQ corpus). Edits are versioned automatically — every save snapshots the prior state ([HelpEditor.vue:1-22](../../frontend/src/views/admin/HelpEditor.vue#L1), [HelpEditor.vue:151-154](../../frontend/src/views/admin/HelpEditor.vue#L151)).

## User Types

Admin only — but "admin" here is the **single hardcoded email gate**, not a role tier. Both the router guard and an in-component `useIsAdmin` check require `auth.email === 'johndean@vin.com'` (see Permissions). Any other authenticated user is redirected to the dashboard before the page mounts, or sees an "Admin only." stub if they slip through.

## Entry Points

- Hash route `#/admin/help`, registered as the `admin-help` named route with `meta: { adminOnly: true }` ([frontend/src/router/index.ts:44](../../frontend/src/router/index.ts#L44)).
- NOT VERIFIED IN CODE: any nav-chrome link to this route (the view declares no inbound links; admin nav rendering lives elsewhere).

## Navigation Paths

- **Redirect on non-admin** — `onMounted` calls `router.replace('/dashboard')` if `isAdmin` is false ([HelpEditor.vue:132-140](../../frontend/src/views/admin/HelpEditor.vue#L132)).
- All other interactions are in-page dialogs (editor, version history) — no further route changes from this view.

## Components

- `HelpAdminToolbar` — the bulk-AI action toolbar; emits `@new` (open editor) and `@refresh` (reload) ([HelpEditor.vue:29,158](../../frontend/src/views/admin/HelpEditor.vue#L29)). See "Toolbar actions" below.
- `HelpCoverageReport` — published-article count per `content_domain`, flagging domains with `<2` published; exposes `refresh()` via a template ref, re-invoked after save/archive/restore ([HelpEditor.vue:30,160](../../frontend/src/views/admin/HelpEditor.vue#L30), [HelpEditor.vue:52,110,120,129](../../frontend/src/views/admin/HelpEditor.vue#L52); [HelpCoverageReport.vue:64-65](../../frontend/src/components/help/HelpCoverageReport.vue#L64)).
- `HelpComplianceMeter` — per-row CC-Rounds compliance indicator (`:article="a"`) ([HelpEditor.vue:33,215](../../frontend/src/views/admin/HelpEditor.vue#L33)).
- `HelpArticleEditorDialog` — create/edit dialog; props `:open`, `:article`, `:all-articles`; emits `@close`, `@saved` ([HelpEditor.vue:31,238-244](../../frontend/src/views/admin/HelpEditor.vue#L31)).
- `HelpVersionHistoryDialog` — version list + restore; props `:open`, `:article-id`; emits `@close`, `@restored` (rendered only when `historyTarget` is set) ([HelpEditor.vue:32,245-251](../../frontend/src/views/admin/HelpEditor.vue#L32)).
- `Icon` — used in row action buttons (edit / history / x) ([HelpEditor.vue:28,225-233](../../frontend/src/views/admin/HelpEditor.vue#L28)).

Page DOM:
- `div.hed` wrapper; `div.hed__forbidden` "Admin only." when `!isAdmin`, else a `<template v-else>` with header, toolbar, coverage, filters, and list ([HelpEditor.vue:144-253](../../frontend/src/views/admin/HelpEditor.vue#L144)).
- Filters row (`div.hed__filters`): Audience select (all/users/admin), Domain select (built from distinct `content_domain`s), Status select (all/published/drafts), and a free-text Search input ([HelpEditor.vue:163-196](../../frontend/src/views/admin/HelpEditor.vue#L163)).
- List (`ul.hed__list`): one `li.hed__row` per filtered article showing title, published/draft pill, audience, content_domain, `v{{version}}`, compliance meter, summary, slug, last-edited-by, updated_at, and Edit/History/Archive actions ([HelpEditor.vue:204-236](../../frontend/src/views/admin/HelpEditor.vue#L204)).

## Actions

- **New article** — toolbar `@new` → `openNew()` sets `editorTarget = null`, opens the editor dialog ([HelpEditor.vue:91-94](../../frontend/src/views/admin/HelpEditor.vue#L91)).
- **Edit** — row Edit button → `openEdit(a)` ([HelpEditor.vue:95-98,225](../../frontend/src/views/admin/HelpEditor.vue#L95)).
- **History** — row History button → `openHistory(a)` (sets `historyTarget`, opens dialog) ([HelpEditor.vue:99-102,228](../../frontend/src/views/admin/HelpEditor.vue#L99)).
- **Archive** — row Archive button (only when `a.is_published`) → native `confirm()` then `archiveArticle(a.id)`, success toast, coverage refresh ([HelpEditor.vue:113-124,231](../../frontend/src/views/admin/HelpEditor.vue#L113)).
- **Save (from dialog)** — `@saved` → `onSaved()` upserts the article into the local list and refreshes coverage ([HelpEditor.vue:104-111](../../frontend/src/views/admin/HelpEditor.vue#L104)).
- **Restore (from history)** — `@restored` → `onRestored()` patches the local list + refreshes coverage ([HelpEditor.vue:126-130](../../frontend/src/views/admin/HelpEditor.vue#L126)).
- **Refresh** — toolbar `@refresh` → `load()` (re-fetch with current filters) ([HelpEditor.vue:158](../../frontend/src/views/admin/HelpEditor.vue#L158)).
- **Filter changes** — Audience and Domain selects call `@change="load"` (server re-query); Status and Search filter the already-loaded list client-side via the `filtered` computed ([HelpEditor.vue:166,174,71-83](../../frontend/src/views/admin/HelpEditor.vue#L166)).

### Toolbar actions ([HelpAdminToolbar.vue](../../frontend/src/components/help/HelpAdminToolbar.vue))
Each is fire-and-forget with a native `confirm()` gate and a result toast:
- **Publish all drafts** → `bulkPublishDrafts()` `POST /v1/help/admin/bulk-publish` (inline, CC-Rounds gated) ([HelpAdminToolbar.vue:52](../../frontend/src/components/help/HelpAdminToolbar.vue#L52)).
- **Fix CC-Rounds** → `fixSummaries()` `POST /v1/help/admin/fix-summaries` (Celery enqueue) ([HelpAdminToolbar.vue:71](../../frontend/src/components/help/HelpAdminToolbar.vue#L71)).
- **Expand Steps** → `expandSteps()` `POST /v1/help/admin/expand-steps` ([HelpAdminToolbar.vue:85](../../frontend/src/components/help/HelpAdminToolbar.vue#L85)).
- **Expand FAQs** → `expandFaqs()` `POST /v1/help/admin/expand-faqs` ([HelpAdminToolbar.vue:99](../../frontend/src/components/help/HelpAdminToolbar.vue#L99)).
- **Generate FAQ corpus** → `generateFaqCorpus()` `POST /v1/help/admin/generate-faq-corpus` ([HelpAdminToolbar.vue:117](../../frontend/src/components/help/HelpAdminToolbar.vue#L117)).

(API wrappers: [helpArticlesApi.ts:173-200](../../frontend/src/services/helpArticlesApi.ts#L173).)

## States

- `filtered` computed applies Status + Search filters over the loaded `articles` ([HelpEditor.vue:71-83](../../frontend/src/views/admin/HelpEditor.vue#L71)).
- `domains` computed derives the Domain dropdown from distinct `content_domain` values ([HelpEditor.vue:85-89](../../frontend/src/views/admin/HelpEditor.vue#L85)).
- Save/archive/restore mutate `articles` in place (upsert/patch) without a full reload ([HelpEditor.vue:104-130](../../frontend/src/views/admin/HelpEditor.vue#L104)).
- Per-row pill: `is-published` vs `is-draft` driven by `a.is_published` ([HelpEditor.vue:209-211](../../frontend/src/views/admin/HelpEditor.vue#L209)).

## Empty States

Implemented. When `filtered.length === 0` (and not erroring / not initial-loading), the `v-else-if` at [HelpEditor.vue:201-203](../../frontend/src/views/admin/HelpEditor.vue#L201) renders `div.hed__empty` with "No articles match the current filters."

## Error States

Implemented. When `err` is set, `div.hed__err` renders the message (highest-priority branch) ([HelpEditor.vue:199](../../frontend/src/views/admin/HelpEditor.vue#L199)). `err` is `e.message` or "Failed to load articles" from the `load()` catch ([HelpEditor.vue:64-66](../../frontend/src/views/admin/HelpEditor.vue#L64)). Toolbar action failures push their own error toasts ([HelpAdminToolbar.vue:59-61](../../frontend/src/components/help/HelpAdminToolbar.vue#L59)). Archive failures toast via `e.message` ([HelpEditor.vue:121-122](../../frontend/src/views/admin/HelpEditor.vue#L121)).

## Loading States

Implemented. The `v-else-if="loading && articles.length === 0"` branch renders `div.hed__loading` "Loading…" — only on the first load while the list is still empty ([HelpEditor.vue:200](../../frontend/src/views/admin/HelpEditor.vue#L200)). Subsequent refreshes keep the existing list visible (no full-screen spinner). `loading` is toggled around `load()` ([HelpEditor.vue:54-69](../../frontend/src/views/admin/HelpEditor.vue#L54)).

## Permissions

This is the one screen with an active client-side admin gate, and it is the **legacy hardcoded-email gate**, not a role tier:

1. **Router guard** — `beforeEach` checks `to.meta.adminOnly && auth.email !== 'johndean@vin.com'` and redirects to `dashboard` ([frontend/src/router/index.ts:51,63-66](../../frontend/src/router/index.ts#L51)). The constant `LEGACY_ADMIN_EMAIL` is the literal email ([router/index.ts:51](../../frontend/src/router/index.ts#L51)).
2. **In-component check** — `useIsAdmin()` returns `auth.email === LEGACY_ADMIN_EMAIL_CLIENT` where that constant is also `'johndean@vin.com'` ([HelpEditor.vue:36](../../frontend/src/views/admin/HelpEditor.vue#L36); [useIsAdmin.ts:22-27](../../frontend/src/composables/useIsAdmin.ts#L22); [help-content.ts:43](../../frontend/src/constants/help-content.ts#L43)). When false, `onMounted` redirects and the template shows `div.hed__forbidden` "Admin only." ([HelpEditor.vue:133-138,145](../../frontend/src/views/admin/HelpEditor.vue#L133)).

`useIsAdmin`'s own docstring states the client check is UI-only and mirrors the backend `LEGACY_ADMIN_EMAIL` gate (`app/security/roles.py`), which is authoritative on every `/v1/help/articles*` route ([useIsAdmin.ts:5-14](../../frontend/src/composables/useIsAdmin.ts#L5)). There is no role-based gate active — `auth_users.role` is not read for this decision. This is the defense-in-depth pair described as "router guard AND the v-if check" ([HelpEditor.vue:8-10](../../frontend/src/views/admin/HelpEditor.vue#L8)).

## Connected APIs

From the view ([helpArticlesApi.ts](../../frontend/src/services/helpArticlesApi.ts)):
- `listArticles({ audience, content_domain, limit: 500 })` → `GET /v1/help/articles` (on mount + filter change + refresh) ([HelpEditor.vue:59-63](../../frontend/src/views/admin/HelpEditor.vue#L59); [helpArticlesApi.ts:79-87](../../frontend/src/services/helpArticlesApi.ts#L79)).
- `archiveArticle(id)` → `PATCH /v1/help/articles/{id}/archive` ([HelpEditor.vue:116](../../frontend/src/views/admin/HelpEditor.vue#L116); [helpArticlesApi.ts:111-115](../../frontend/src/services/helpArticlesApi.ts#L111)).

From `HelpCoverageReport`:
- `getCoverage()` → `GET /v1/help/coverage` (on mount + each `refresh()`) ([HelpCoverageReport.vue:38](../../frontend/src/components/help/HelpCoverageReport.vue#L38); [helpArticlesApi.ts:135-137](../../frontend/src/services/helpArticlesApi.ts#L135)).

From `HelpAdminToolbar` (see Actions): `POST /v1/help/admin/{bulk-publish, fix-summaries, expand-steps, expand-faqs, generate-faq-corpus}` ([helpArticlesApi.ts:173-200](../../frontend/src/services/helpArticlesApi.ts#L173)).

The editor/version dialogs (`HelpArticleEditorDialog`, `HelpVersionHistoryDialog`) call create/update and versions/restore endpoints internally (`POST/PATCH /v1/help/articles`, `GET /v1/help/articles/{id}/versions`, etc.) per the api wrappers ([helpArticlesApi.ts:95-132](../../frontend/src/services/helpArticlesApi.ts#L95)). NOT VERIFIED IN CODE for this doc: the exact internal calls of those two dialog components (their source was not read here).

## Data Sources

`HelpArticleDTO` shape consumed by the list ([helpArticlesApi.ts:19-37](../../frontend/src/services/helpArticlesApi.ts#L19)): `id, slug, title, summary, category, audience, feature_tags, steps, related_article_ids, display_order, is_published, content_domain, workflow_slug, version, last_edited_by, created_at, updated_at`. Coverage shape: `{ by_domain, total_published, total_drafts }` ([helpArticlesApi.ts:48-52](../../frontend/src/services/helpArticlesApi.ts#L48)). The backing tables (help_articles, help_article_versions) are not declared in the frontend; not verified from these files.

## Source Verification
- **Files Used:** frontend/src/views/admin/HelpEditor.vue; frontend/src/components/help/HelpAdminToolbar.vue; frontend/src/components/help/HelpCoverageReport.vue; frontend/src/services/helpArticlesApi.ts; frontend/src/composables/useIsAdmin.ts; frontend/src/constants/help-content.ts; frontend/src/router/index.ts; frontend/src/stores/auth.ts
- **Components Used:** HelpAdminToolbar, HelpCoverageReport, HelpComplianceMeter, HelpArticleEditorDialog, HelpVersionHistoryDialog, Icon
- **APIs Used:** GET /v1/help/articles; PATCH /v1/help/articles/{id}/archive; GET /v1/help/coverage; POST /v1/help/admin/{bulk-publish,fix-summaries,expand-steps,expand-faqs,generate-faq-corpus}; (dialogs also use create/update/versions/restore wrappers in helpArticlesApi.ts)
- **Database Tables Used:** not verified from the frontend (help-article tables referenced only by endpoint)
- **Permission Logic Used:** JWT + LEGACY_ADMIN_EMAIL gate (router `meta.adminOnly` guard at router/index.ts:63 AND in-component `useIsAdmin` email compare). No active role tier.
- **Confidence Score:** High for the view, toolbar, coverage, and gate (all read in full); Medium for the editor/version dialog internals (not read — their endpoints inferred from the api wrappers).
- **Evidence Links:** [HelpEditor.vue:59](../../frontend/src/views/admin/HelpEditor.vue#L59), [HelpEditor.vue:199-203](../../frontend/src/views/admin/HelpEditor.vue#L199), [useIsAdmin.ts:22](../../frontend/src/composables/useIsAdmin.ts#L22), [router/index.ts:63](../../frontend/src/router/index.ts#L63)
