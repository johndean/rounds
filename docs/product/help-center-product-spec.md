# Help Center — Product Spec

> Code-verified against the rounds.vin repository. Every claim below is traceable to a source file and line. Tags used where code could not confirm a claim: **NOT VERIFIED IN CODE**, **IMPLEMENTATION NOT FOUND**, **PARTIALLY IMPLEMENTED**.

## Overview

The Help Center is rounds.vin's in-app help surface plus its admin-authored help-article CMS. It has two distinct faces:

1. **The inline Help drawer** ([`frontend/src/components/help/HelpPanel.vue`](../../frontend/src/components/help/HelpPanel.vue)) — a right-side panel any signed-in user can open. It has three tabs: **This page**, **FAQ**, and **Ask AI**, plus a search box.
2. **The admin Help Editor** ([`frontend/src/views/admin/HelpEditor.vue`](../../frontend/src/views/admin/HelpEditor.vue)) — a CMS at route `/admin/help` where the bootstrap admin authors, edits, publishes, archives, version-controls, and AI-bulk-edits help articles.

Help content is stored in the `help_articles` table ([`migrations/053_help_articles.sql`](../../migrations/053_help_articles.sql)), seeded from a hand-authored corpus ([`migrations/055_help_articles_seed.sql`](../../migrations/055_help_articles_seed.sql), [`migrations/056_help_articles_steps_content.sql`](../../migrations/056_help_articles_steps_content.sql)). The Ask AI tab grounds questions against an in-process Python mirror of the same corpus ([`app/data/help_content.py`](../../app/data/help_content.py)) and synthesizes an answer with Gemini ([`app/api/help.py:198-230`](../../app/api/help.py#L198)).

The backend router is mounted at prefix `/v1/help` ([`app/api/help.py:58`](../../app/api/help.py#L58)) and included into the FastAPI app at [`app/main.py:233`](../../app/main.py#L233).

## Purpose

- Give end users (clinicians, copy editors, operators) contextual, page-aware help without leaving the app.
- Provide a grounded **Ask AI** Q&A surface that answers only from the help corpus and never hallucinates outside it ([`app/api/help.py:202-209`](../../app/api/help.py#L202) — system prompt restricts the model to the provided articles).
- Give the bootstrap admin a CMS to author and maintain help articles with versioned edits, a compliance meter ("CC-Rounds"), coverage reporting, and AI-assisted bulk content cleanup.

## User Value

| Audience | Value (code-verified) |
|---|---|
| Any signed-in user | Open the drawer on any page; the **This page** tab shows tips for the current route, resolved from `pageKey` ([`HelpPanel.vue:52-74`](../../frontend/src/components/help/HelpPanel.vue#L52)). Search across all topics + FAQ (client-side substring + title rank, [`stores/help.ts:104-129`](../../frontend/src/stores/help.ts#L104)). |
| Any signed-in user | **Ask AI** tab (when enabled): ask a free-text question; get a concise grounded answer with inline citations ([`HelpAskComposer.vue`](../../frontend/src/components/help/HelpAskComposer.vue)). When disabled, a "Coming soon" notice renders ([`HelpPanel.vue:346-363`](../../frontend/src/components/help/HelpPanel.vue#L346)). |
| Bootstrap admin only | Author/edit/publish/archive articles, view + restore version history, see CC-Rounds compliance per article, run a coverage report, and trigger AI bulk operations ([`HelpEditor.vue`](../../frontend/src/views/admin/HelpEditor.vue), [`HelpAdminToolbar.vue`](../../frontend/src/components/help/HelpAdminToolbar.vue)). |

## Navigation

- **Inline drawer:** opened by user action only — the panel state is driven exclusively by `help.toggle()` / `help.show()` / `help.hide()` ([`stores/help.ts:95-97`](../../frontend/src/stores/help.ts#L95)). Routes never auto-open it ([`stores/help.ts:29-31`](../../frontend/src/stores/help.ts#L29) documents this invariant). **Esc** closes the panel ([`HelpPanel.vue:163-166`](../../frontend/src/components/help/HelpPanel.vue#L163)).
  - The "press `?` to open" / "Esc to close" hint is rendered in the footer ([`HelpPanel.vue:367-369`](../../frontend/src/components/help/HelpPanel.vue#L367)). The `?`-to-open keyboard binding itself is **NOT VERIFIED IN CODE** within the files reviewed — `HelpPanel.vue` registers only an `Escape` handler; the open trigger lives elsewhere (header button). **PARTIALLY IMPLEMENTED** as documented here.
- **Admin Help Editor:** route `/admin/help`, name `admin-help`, lazy-loaded, `meta.adminOnly: true` ([`router/index.ts:44`](../../frontend/src/router/index.ts#L44)). A `beforeEach` guard redirects non-admins to `/dashboard` ([`router/index.ts:53-68`](../../frontend/src/router/index.ts#L63)).
- The page key for the drawer is derived from the active route name via `resolvePageKey(route.name)` ([`HelpPanel.vue:52-56`](../../frontend/src/components/help/HelpPanel.vue#L52)).

## Screens

### 1. Inline Help Drawer ([`HelpPanel.vue`](../../frontend/src/components/help/HelpPanel.vue))

- **Header:** "Help Center / Need a hand?" with a close button (`data-test-id="help-close"`).
- **Search box:** placeholder `"Search help — semantic + lexical"`, `data-test-id="help-search-input"`. Typing 2+ chars switches the body to search results and hides the tabs ([`HelpPanel.vue:76`, `233`](../../frontend/src/components/help/HelpPanel.vue#L76)). Query is debounced 250ms before hitting the store ([`HelpPanel.vue:59-66`](../../frontend/src/components/help/HelpPanel.vue#L59)).
- **Tabs** (hidden during search): `This page` (`help-tab-page`), `FAQ` (`help-tab-faq`), `Ask AI` (`help-tab-ask`).
- **This page tab:** renders the role-resolved entry for the current `pageKey`: `pageContent[role] ?? pageContent.all` ([`HelpPanel.vue:68-73`](../../frontend/src/components/help/HelpPanel.vue#L68)). Topics render as accordion `HelpItem` cards; the first opens by default ([`HelpPanel.vue:302-310`](../../frontend/src/components/help/HelpPanel.vue#L302)).
- **FAQ tab:** **PARTIALLY IMPLEMENTED hybrid.** On first open it fetches published articles via `listArticles({limit:200})` and filters to `category === 'faq'` or `category` starts with `faq:` and `is_published` ([`HelpPanel.vue:90-115`](../../frontend/src/components/help/HelpPanel.vue#L90)). If any match, they render as `HelpFaqAccordion` (title + summary + steps + related-link chips). If the API errors or returns empty, it falls back to the hardcoded `HELP_CONTENT.faq` array rendered via `HelpItem` ([`HelpPanel.vue:316-341`](../../frontend/src/components/help/HelpPanel.vue#L316)).
- **Ask AI tab:** renders `HelpAskComposer` when `help.askEnabled` is true, otherwise a "Coming soon" notice ([`HelpPanel.vue:346-363`](../../frontend/src/components/help/HelpPanel.vue#L346)). `askEnabled` is set from the backend `/v1/version` flag `help_ask_ai_enabled` by the header on mount ([`AppHeader.vue:58-59`](../../frontend/src/components/AppHeader.vue#L58)).
- **Footer:** keyboard hints + a "Full docs" link to `https://{contact.docs}` where `contact.docs = "rounds.vin/docs"` ([`HelpPanel.vue:371-378`](../../frontend/src/components/help/HelpPanel.vue#L371), [`app/data/help_content.py:261-265`](../../app/data/help_content.py#L261)).

### 2. Ask AI composer ([`HelpAskComposer.vue`](../../frontend/src/components/help/HelpAskComposer.vue))

- Textarea (`help-ask-input`); **Cmd/Ctrl+Enter** submits ([`HelpAskComposer.vue:49-54`](../../frontend/src/components/help/HelpAskComposer.vue#L49)). Submit disabled until the trimmed question is ≥ 2 chars and no request is in flight ([`HelpAskComposer.vue:38-40`](../../frontend/src/components/help/HelpAskComposer.vue#L38)).
- Each turn shows the user question, the AI answer, an inline error chip on failure, and a numbered citation list ([`HelpAskComposer.vue:98-128`](../../frontend/src/components/help/HelpAskComposer.vue#L98)).
- A **Cancel** button shows while streaming; **Clear thread** appears once there is at least one turn.

### 3. Admin Help Editor ([`HelpEditor.vue`](../../frontend/src/views/admin/HelpEditor.vue))

- Header "Admin / Help Editor".
- **Admin toolbar** ([`HelpAdminToolbar.vue`](../../frontend/src/components/help/HelpAdminToolbar.vue)): `+ New article`, `Publish all drafts`, `Fix CC-Rounds`, `Expand Steps`, `Expand FAQs`, `Generate FAQ corpus`, `Refresh`.
- **Coverage report** ([`HelpCoverageReport.vue`](../../frontend/src/components/help/HelpCoverageReport.vue)): a 2-column grid of published-article counts per content domain; any domain below 2 published is flagged red ([`HelpCoverageReport.vue:17`, `46-60`](../../frontend/src/components/help/HelpCoverageReport.vue#L17)).
- **Filters:** Audience (`all`/`users`/`admin`), Domain (dynamic from loaded articles), Status (`all`/`published`/`drafts`), and a client-side text search over title/summary/slug ([`HelpEditor.vue:42-89`](../../frontend/src/views/admin/HelpEditor.vue#L42)).
- **Article list rows:** title, published/draft pill, audience pill, domain pill, `v{version}` pill, inline CC-Rounds compliance meter, summary, slug, last-edited-by, updated-at, and per-row actions **Edit / History / Archive** (Archive shows only on published rows) ([`HelpEditor.vue:204-235`](../../frontend/src/views/admin/HelpEditor.vue#L204)).
- **Editor dialog** ([`HelpArticleEditorDialog.vue`](../../frontend/src/components/help/HelpArticleEditorDialog.vue)): title, summary, category, content_domain, audience, feature_tags (chips), is_published toggle, steps[] (numbered cards with move-up/down), related_article_ids (max 5), with a live CC-Rounds preview meter.
- **Version history dialog** ([`HelpVersionHistoryDialog.vue`](../../frontend/src/components/help/HelpVersionHistoryDialog.vue)): lists prior versions newest-first; "Restore" re-applies a snapshot as a fresh PATCH.

## User Flows

### Flow A — User reads page-specific help
1. User opens the drawer; `pageKey` is already set from the route ([`HelpPanel.vue:52-56`](../../frontend/src/components/help/HelpPanel.vue#L52)).
2. **This page** tab renders the role entry (admin email gets `admin` content, everyone else gets `user`) ([`HelpPanel.vue:46-48`](../../frontend/src/components/help/HelpPanel.vue#L46)).
3. User clicks a topic to expand its answer ([`HelpItem.vue`](../../frontend/src/components/help/HelpItem.vue)).

### Flow B — User asks the AI a question
1. Ask AI tab → type question → Cmd/Ctrl+Enter.
2. `startAsk()` appends a turn and calls `askHelp({question, page_key})` → `POST /v1/help/ask` ([`stores/help.ts:149-207`](../../frontend/src/stores/help.ts#L149), [`helpApi.ts:43-53`](../../frontend/src/services/helpApi.ts#L43)).
3. Backend feature-gates on `HELP_ASK_AI_ENABLED` (404 if off), rate-limits per user, retrieves top-5 corpus articles, calls Gemini, and returns `{answer, sources, used_llm}` ([`app/api/help.py:164-230`](../../app/api/help.py#L164)).
4. If Gemini is unavailable/misconfigured/returns unparseable output, the route degrades to an **extractive** answer built from the top hits and never raises 5xx ([`app/api/help.py:194-228`](../../app/api/help.py#L194)).

### Flow C — Admin authors / edits an article
1. `/admin/help` → toolbar "+ New article" or row "Edit" → dialog.
2. Save calls `createArticle` (`POST /v1/help/articles`, 201) or `updateArticle` (`PATCH /v1/help/articles/{id}`) ([`helpArticlesApi.ts:95-108`](../../frontend/src/services/helpArticlesApi.ts#L95)).
3. On PATCH the backend snapshots the prior row into `help_article_versions` **before** applying the change and bumps `version` ([`app/api/help.py:594-610`](../../app/api/help.py#L594)).

### Flow D — Admin versioning / restore
1. Row "History" → dialog lists versions ([`GET /v1/help/articles/{id}/versions`](../../app/api/help.py#L707)).
2. "Restore" sends the chosen snapshot as a PATCH body; the restore itself appends a new version row ([`HelpVersionHistoryDialog.vue:42-67`](../../frontend/src/components/help/HelpVersionHistoryDialog.vue#L42), [`migrations/054_help_article_versions.sql:9-13`](../../migrations/054_help_article_versions.sql#L9)).

### Flow E — Admin bulk publish / AI cleanup
1. **Publish all drafts** → inline `POST /v1/help/admin/bulk-publish`: runs CC-Rounds on every draft, publishes only `allPass` rows, returns counts + a skipped list with per-check failure reasons ([`app/api/help.py:829-894`](../../app/api/help.py#L829)).
2. **Fix CC-Rounds / Expand Steps / Expand FAQs / Generate FAQ corpus** → enqueue Celery tasks; each returns a `task_id` and is fire-and-forget; AI output lands as drafts pending admin review ([`app/api/help.py:916-948`](../../app/api/help.py#L916), [`app/tasks/help_tasks.py`](../../app/tasks/help_tasks.py)).

## Business Rules

| Rule | Statement | Evidence |
|---|---|---|
| BR-001 (admin gate) | "Admin" everywhere in this module = the single hardcoded `LEGACY_ADMIN_EMAIL = "johndean@vin.com"`. There is no role-tier system in effect. | [`app/security/roles.py:54`, `62-92`](../../app/security/roles.py#L54) |
| Feature gate | Ask AI is OFF by default; enabling it is an intentional env change (`HELP_ASK_AI_ENABLED`). When off, `/v1/help/ask` returns 404. | [`app/config.py:121`](../../app/config.py#L121), [`app/api/help.py:174-175`](../../app/api/help.py#L174) |
| Rate limit | Per-user hourly cap on Ask AI = `HELP_ASK_AI_RATE_LIMIT_PER_HOUR` (default 30); 0 disables. Over-cap → 429 with code `HELP_ASK_RATE_LIMIT`. | [`app/config.py:123`](../../app/config.py#L123), [`app/api/help.py:114-135`, `181-190`](../../app/api/help.py#L114) |
| Never-5xx Ask AI | The enabled Ask path always returns a usable answer (LLM or extractive); a Gemini failure degrades, never errors. | [`app/api/help.py:24-29`, `226-228`](../../app/api/help.py#L24) |
| Review-gate for AI edits | Every AI rewrite/draft lands as `is_published = FALSE` — admins must manually publish. | [`app/tasks/help_tasks.py:18-21`, `252`, `378`, `718`](../../app/tasks/help_tasks.py#L18) |
| Versioning on PATCH | Every PATCH (and archive, and AI rewrite) snapshots the prior state before mutating; version-table rows are never updated/deleted. | [`app/api/help.py:594-610`](../../app/api/help.py#L594), [`migrations/054_help_article_versions.sql:9-13`](../../migrations/054_help_article_versions.sql#L9) |
| Archive = unpublish | "Archive" sets `is_published = FALSE`; there is no separate `archived` flag and no hard-delete in the UI. | [`app/api/help.py:624-668`](../../app/api/help.py#L624) |
| Reorder is not versioned | Bulk reorder updates `display_order` only and does NOT snapshot (cosmetic change). | [`app/api/help.py:674-701`](../../app/api/help.py#L674) |
| CC-Rounds thresholds | Help: ≥3 steps, ≥200 step-body words, summary ≥180 chars (no max). FAQ: ≥2 steps, ≥80 words, summary 60–300 chars. FAQ vs Help is decided by substring "faq" in `category`. | [`app/utils/help_compliance.py:39-63`](../../app/utils/help_compliance.py#L39) |
| Coverage red threshold | A content domain with fewer than 2 published articles is flagged red. | [`HelpCoverageReport.vue:17`](../../frontend/src/components/help/HelpCoverageReport.vue#L17) |
| FAQ-corpus idempotency | The generator inserts one draft per route with slug `faq-ai-{page_key}` and `ON CONFLICT (slug) DO NOTHING`; safe to re-run. A task-level Redis guard short-circuits concurrent runs. | [`app/tasks/help_tasks.py:517-561`, `707-739`](../../app/tasks/help_tasks.py#L517) |
| Dev-speak blacklist | AI-generated FAQ drafts are post-filtered against a literal + regex dev-speak blacklist; any hit rejects the draft. | [`app/tasks/help_tasks.py:465-514`, `695-705`](../../app/tasks/help_tasks.py#L465) |

## Validation Rules

Backend (Pydantic) — [`app/api/help.py`](../../app/api/help.py):
- Ask request: `question` length 1–2000; `page_key` ≤ 64; `role` ≤ 16 ([`app/api/help.py:64-68`](../../app/api/help.py#L64)).
- Article create: `title` 1–200; `summary` ≤ 4000; `category` ≤ 64; `audience` must match `^(users|admin)$`; `feature_tags`/`steps`/`related_article_ids` max length 20; `display_order` ≥ 0 ([`app/api/help.py:306-319`](../../app/api/help.py#L306)).
- Step: `title` 1–200, `body` 1–4000 ([`app/api/help.py:300-303`](../../app/api/help.py#L300)).
- Update: all fields optional, same per-field constraints ([`app/api/help.py:322-334`](../../app/api/help.py#L322)).
- Reorder: 1–200 items, each `display_order` ≥ 0 ([`app/api/help.py:337-343`](../../app/api/help.py#L337)).
- List query: `audience` regex `^(users|admin)$`, `limit` 1–500 (default 200) ([`app/api/help.py:374-377`](../../app/api/help.py#L374)).
- Search query: `q` length 2–200, `limit` 1–50 ([`app/api/help.py:790-791`](../../app/api/help.py#L790)).

Frontend:
- Ask submit disabled until question ≥ 2 chars ([`HelpAskComposer.vue:38-40`](../../frontend/src/components/help/HelpAskComposer.vue#L38)); `startAsk` also rejects < 2 chars ([`stores/help.ts:150-152`](../../frontend/src/stores/help.ts#L150)).
- Editor dialog Save disabled until title is non-empty ([`HelpArticleEditorDialog.vue:58`](../../frontend/src/components/help/HelpArticleEditorDialog.vue#L58)); related-article picker caps at 5 ([`HelpArticleEditorDialog.vue:121-129`](../../frontend/src/components/help/HelpArticleEditorDialog.vue#L121)).
- Search activates at ≥ 2 chars ([`HelpPanel.vue:76`](../../frontend/src/components/help/HelpPanel.vue#L76), [`stores/help.ts:106`](../../frontend/src/stores/help.ts#L106)).

## States

**Ask AI turn** ([`stores/help.ts:48-58`](../../frontend/src/stores/help.ts#L48)): `streaming`, `done`, `errorCode`/`errorMessage`. Mapped error codes: `HELP_ASK_RATE_LIMIT` (429), `NOT_ENABLED` (404), `BAD_REQUEST` (400), `ABORTED`, generic `HTTP_{status}` ([`stores/help.ts:65-87`](../../frontend/src/stores/help.ts#L65)).

**Article**: `is_published` true (Published) / false (Draft) — surfaced as a pill ([`HelpEditor.vue:209-211`](../../frontend/src/views/admin/HelpEditor.vue#L209)). `version` integer, starts at 1, increments per edit ([`migrations/053_help_articles.sql:34`](../../migrations/053_help_articles.sql#L34)).

**FAQ tab load**: `faqLoading` / `faqLoaded` / fallback. `faqLoaded` is set true only on success so a transient error retries on next open ([`HelpPanel.vue:86-115`](../../frontend/src/components/help/HelpPanel.vue#L86)).

**CC-Rounds**: per article computes `wordsOk` / `summaryOk` / `stepsOk` / `allPass` / `pct` ([`app/utils/help_compliance.py:79-138`](../../app/utils/help_compliance.py#L79)).

## Dependencies

- **Gemini** via `app.engines.llm_client.call_gemini_text` (default model `gemini-2.5-pro`, temperature 0.1) for Ask AI and all bulk tasks ([`app/api/help.py:200-211`](../../app/api/help.py#L200), [`app/engines/llm_client.py:217-242`](../../app/engines/llm_client.py#L217)). Requires `GEMINI_API_KEY`.
- **Redis** for the Ask rate limit and Celery task idempotency keys ([`app/api/help.py:124-132`](../../app/api/help.py#L124), [`app/tasks/help_tasks.py:71-89`](../../app/tasks/help_tasks.py#L71)). Both soft-fail if Redis is down.
- **Celery** (`celery_app`) for the four admin bulk tasks ([`app/tasks/help_tasks.py:182`, `407`, `418`, `517`](../../app/tasks/help_tasks.py#L182)).
- **Postgres** tables `help_articles`, `help_article_versions`, `audit_events`.
- **Auth:** every endpoint requires a logged-in user (`CurrentUser` dependency) ([`app/api/help.py:50`](../../app/api/help.py#L50)).
- The in-process Ask corpus is a hand-mirror of the frontend `help-content.ts`; a test pins them in sync ([`app/data/help_content.py:25-28`](../../app/data/help_content.py#L25)).

## Error Handling

| Surface | Error | Code / status | Evidence |
|---|---|---|---|
| Ask AI | Feature disabled | 404 "Ask AI is not enabled" | [`app/api/help.py:174-175`](../../app/api/help.py#L174) |
| Ask AI | Empty question | 400 (Pydantic 422 on body; explicit 400 fallback) | [`app/api/help.py:177-179`](../../app/api/help.py#L177) |
| Ask AI | Over rate cap | 429 `HELP_ASK_RATE_LIMIT` (`retryable: true`) | [`app/api/help.py:181-190`](../../app/api/help.py#L181) |
| Ask AI | Gemini failure | (no error) degrade to extractive, log warning | [`app/api/help.py:226-228`](../../app/api/help.py#L226) |
| Article CRUD | Slug collision | 409 `SLUG_CONFLICT` | [`app/api/help.py:503-507`](../../app/api/help.py#L503) |
| Article CRUD | Table not migrated | 503 `TABLE_NOT_MIGRATED` | [`app/api/help.py:508-512`](../../app/api/help.py#L508) |
| Article CRUD | Not found / hidden from non-admin | 404 `NOT_FOUND` (existence not leaked) | [`app/api/help.py:441-448`](../../app/api/help.py#L441) |
| List/Search | Table missing | graceful empty list (logged warning) | [`app/api/help.py:415-417`, `817-819`](../../app/api/help.py#L415) |
| Admin actions | Non-admin | 403 `ADMIN_ONLY` | [`app/security/roles.py:95-117`](../../app/security/roles.py#L95) |
| Celery enqueue | Broker unreachable | 503 `QUEUE_UNAVAILABLE` | [`app/api/help.py:900-913`](../../app/api/help.py#L900) |
| Internal | Unhandled DB error | 500 `INTERNAL` (rollback first) | [`app/api/help.py:513-514`, `613-616`](../../app/api/help.py#L513) |

## Permissions

**PERMISSION REALITY (verified):** role-based authorization is scaffold-only across rounds.vin. The role helper [`app/security/roles.py`](../../app/security/roles.py) is **not** wired into `get_current_user`, and `auth_users.role` (migration 045) is **not** read into the user object. Effective authorization for the Help Center:

1. **Every** `/v1/help/*` endpoint requires a valid JWT (`CurrentUser`) — read endpoints included ([`app/api/help.py:50`, `165`, `371`, `426`](../../app/api/help.py#L50)).
2. **Write/admin endpoints** call `require_admin(user)`, which today is a single hardcoded `user.email == "johndean@vin.com"` check ([`app/api/help.py:461`, `529`, `632`, `683`, `713`, `733`, `751`, `832`, `921-947`](../../app/api/help.py#L461); gate at [`app/security/roles.py:62-92`](../../app/security/roles.py#L62)).
3. **Audience masking** (defense in depth): `list_articles`, `get_article`, and `search` mask drafts and `audience='admin'` rows for non-admins — non-admins see only `is_published=TRUE AND audience='users'` ([`app/api/help.py:388-390`, `445-448`, `799-801`](../../app/api/help.py#L388), filter at [`app/api/help.py:349-354`](../../app/api/help.py#L349)). The non-admin path determines "admin" via the same email gate ([`app/api/help.py:357-364`](../../app/api/help.py#L357)).
4. **Client-side route guard**: `/admin/help` has `meta.adminOnly`; the router redirects non-admins to `/dashboard`, comparing `auth.email !== 'johndean@vin.com'` ([`router/index.ts:51`, `63-66`](../../frontend/src/router/index.ts#L63)). `useIsAdmin` mirrors the same email comparison for UI visibility ([`composables/useIsAdmin.ts:22-27`](../../frontend/src/composables/useIsAdmin.ts#L22)). This is cosmetic only — the server is authoritative.

Do not present role tiers (e.g. editor/reviewer) as active for this module — they are not.

## Reporting Impacts

- **Coverage report** is the only reporting surface: published-article counts per `content_domain` plus totals (`total_published`, `total_drafts`), with a <2-published red flag ([`app/api/help.py:750-780`](../../app/api/help.py#L750), [`HelpCoverageReport.vue`](../../frontend/src/components/help/HelpCoverageReport.vue)).
- **Bulk-publish** returns per-run reporting: `total_attempted`, `published`, `published_ids`, and a `skipped[]` list carrying each failed row's CC-Rounds breakdown ([`app/api/help.py:889-894`](../../app/api/help.py#L889)).
- No other dashboards, exports, or analytics for help articles were found. **IMPLEMENTATION NOT FOUND** for any usage analytics (e.g. Ask AI query logging beyond a non-persistent best-effort log id at [`app/api/help.py:154-158`](../../app/api/help.py#L154)).

## Audit Requirements

- **AI rewrites/seed only**: every AI bulk operation emits an `audit_events` row with `kind='help.ai_rewrite'`, `actor='ai:{task-name}'`, `session_id=NULL`, and details capturing version-before/after, lengths, and which checks failed ([`app/tasks/help_tasks.py:129-146`, `257-269`, `383-395`, `741-753`](../../app/tasks/help_tasks.py#L129)).
- **Human edits via the API are NOT audited into `audit_events`.** They are versioned into `help_article_versions` (which stores the full prior snapshot + `edited_by` + `edited_at`) but no `audit_events` row is written by `create_article` / `update_article` / `archive_article` / `bulk_publish` ([`app/api/help.py:455-701`, `829-894`](../../app/api/help.py#L455) — no `audit_events` insert in these paths). **PARTIALLY IMPLEMENTED**: the audit trail for human article edits is the version table, not the global audit log.
- `audit_events.session_id` is nullable by design so help-article audit rows (which are not session-scoped) are valid ([`app/tasks/help_tasks.py:129-132`](../../app/tasks/help_tasks.py#L129)).

## Data Relationships

- `help_articles` (1) → `help_article_versions` (many), FK `article_id` with `ON DELETE CASCADE`; unique `(article_id, version)` ([`migrations/054_help_article_versions.sql:22-30`](../../migrations/054_help_article_versions.sql#L22)).
- `help_articles.related_article_ids` is a JSONB array of other article UUIDs (no FK enforcement; validated against existing rows only in the FAQ generator) ([`migrations/053_help_articles.sql:29`](../../migrations/053_help_articles.sql#L29), [`app/tasks/help_tasks.py:687-693`](../../app/tasks/help_tasks.py#L687)).
- `audit_events` rows for AI rewrites reference an article by `article_id` inside the JSONB `details` (not a column FK); `session_id` is NULL ([`app/tasks/help_tasks.py:129-146`](../../app/tasks/help_tasks.py#L129)).
- The seed slug schemes link content to source: page topics use `<page_key>-<role>-<idx>`, FAQ items `faq-<idx>`, AI-generated FAQ `faq-ai-<page_key>` ([`migrations/055_help_articles_seed.sql:10-13`](../../migrations/055_help_articles_seed.sql#L10), [`app/tasks/help_tasks.py:583`](../../app/tasks/help_tasks.py#L583)).

## Known Constraints

- **Ask AI corpus is the in-process Python mirror, not the DB.** `/v1/help/ask` retrieves from [`app/data/help_content.py`](../../app/data/help_content.py), which is a hand-maintained copy of the frontend constants — NOT from the `help_articles` table. Article CMS edits do not change Ask AI answers ([`app/data/help_content.py:13-15`](../../app/data/help_content.py#L13)). **PARTIALLY IMPLEMENTED** relative to the file's own "Phase 3 will replace this with a DB read" note ([`app/data/help_content.py:14-15`](../../app/data/help_content.py#L14)).
- **No streaming.** `helpApi.ts` is request/response only; the composer's "Cancel" sets a soft flag but the underlying fetch is not aborted via signal in this path ([`HelpAskComposer.vue:18-24`](../../frontend/src/components/help/HelpAskComposer.vue#L18)). (The store does create an `AbortController` and pass `signal`, [`stores/help.ts:167-175`](../../frontend/src/stores/help.ts#L167).)
- **Search is lexical, not semantic** despite the placeholder text. Drawer search is client-side substring + title rank ([`stores/help.ts:104-129`](../../frontend/src/stores/help.ts#L104)); `semanticLoading`/`semanticError` are unused placeholders.
- **`max_output_tokens` hard cap = 1024** for Ask AI; bulk summary rewrites cap at 512 ([`app/api/help.py:211`](../../app/api/help.py#L211), [`app/tasks/help_tasks.py:237`](../../app/tasks/help_tasks.py#L237)).
- **No bulk reorder UI surfaced**: `reorderArticles` exists in the service and a `PATCH /v1/help/articles/reorder` endpoint exists, but no drag-reorder control was found in `HelpEditor.vue`. **IMPLEMENTATION NOT FOUND** for the reorder UI ([`helpArticlesApi.ts:118-123`](../../frontend/src/services/helpArticlesApi.ts#L118)).
- **The `?`-to-open keyboard shortcut** advertised in the footer is **NOT VERIFIED IN CODE** in the reviewed files (only Esc-to-close is handled in the panel).

## Source Verification
- **Files Used:** app/api/help.py, app/tasks/help_tasks.py, app/data/help_content.py, app/utils/help_compliance.py, app/security/roles.py, app/config.py, app/main.py, app/engines/llm_client.py, migrations/053_help_articles.sql, migrations/054_help_article_versions.sql, migrations/055_help_articles_seed.sql, migrations/056_help_articles_steps_content.sql, frontend/src/stores/help.ts, frontend/src/services/helpApi.ts, frontend/src/services/helpArticlesApi.ts, frontend/src/router/index.ts, frontend/src/composables/useIsAdmin.ts, frontend/src/constants/help-content.ts, frontend/src/views/admin/HelpEditor.vue, frontend/src/components/help/* (HelpPanel, HelpItem, HelpFaqAccordion, HelpAskComposer, HelpStepList, HelpRelatedLinks, HelpCoverageReport, HelpVersionHistoryDialog, HelpComplianceMeter, HelpArticleEditorDialog, HelpAdminToolbar), frontend/src/components/AppHeader.vue
- **Components Used:** HelpPanel.vue, HelpAskComposer.vue, HelpItem.vue, HelpFaqAccordion.vue, HelpStepList.vue, HelpRelatedLinks.vue, HelpEditor.vue, HelpAdminToolbar.vue, HelpCoverageReport.vue, HelpArticleEditorDialog.vue, HelpVersionHistoryDialog.vue, HelpComplianceMeter.vue, AppHeader.vue
- **APIs Used:** POST /v1/help/ask, GET /v1/help/articles, GET /v1/help/articles/{id}, POST /v1/help/articles, PATCH /v1/help/articles/{id}, PATCH /v1/help/articles/{id}/archive, PATCH /v1/help/articles/reorder, GET /v1/help/articles/{id}/versions, GET /v1/help/articles/{id}/versions/{version}, GET /v1/help/coverage, GET /v1/help/search, POST /v1/help/admin/bulk-publish, POST /v1/help/admin/fix-summaries, POST /v1/help/admin/expand-steps, POST /v1/help/admin/expand-faqs, POST /v1/help/admin/generate-faq-corpus, GET /v1/version
- **Database Tables Used:** help_articles, help_article_versions, audit_events
- **Permission Logic Used:** JWT (CurrentUser) on all endpoints + LEGACY_ADMIN_EMAIL gate (require_admin) on writes/admin + server-side audience masking + client-side adminOnly route guard
- **Confidence Score:** High — all behaviors traced to specific source lines; uncertain items explicitly tagged.
- **Evidence Links:** [app/api/help.py:164](../../app/api/help.py#L164), [app/api/help.py:455](../../app/api/help.py#L455), [app/utils/help_compliance.py:39](../../app/utils/help_compliance.py#L39), [app/security/roles.py:62](../../app/security/roles.py#L62), [migrations/053_help_articles.sql:20](../../migrations/053_help_articles.sql#L20), [frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63)
