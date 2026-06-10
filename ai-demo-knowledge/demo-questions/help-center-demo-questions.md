# Help Center — Demo Questions

> Every answer below is code-verified. Paths are relative to this file (`ai-demo-knowledge/demo-questions/`), so repo root is `../../`. Personas with no code-true question are omitted.

---

## User

### Q1. How do I open help for the page I'm on, and what will it show?
**Verified Answer:** Open the Help drawer; the **This page** tab is selected by default and shows the help entry for the current route. The page is resolved from the route name via `resolvePageKey(route.name)`, and the content shown is the role-specific entry (`pageContent[role] ?? pageContent.all`). The first topic is expanded automatically. There is also a search box and FAQ / Ask AI tabs.
**Supporting Evidence:** `pageKey` is set by a route watcher ([`HelpPanel.vue:52-56`](../../frontend/src/components/help/HelpPanel.vue#L52)); the page entry and default-open first topic ([`HelpPanel.vue:68-73`, `302-310`](../../frontend/src/components/help/HelpPanel.vue#L68)).
**Source Files:** frontend/src/components/help/HelpPanel.vue, frontend/src/components/help/HelpItem.vue
**API References:** none (This page tab reads client-side `HELP_CONTENT`)
**Database References:** none

### Q2. How do I close the Help drawer?
**Verified Answer:** Press **Esc**, or click the close button in the drawer header. The panel registers a keydown handler that calls `help.hide()` on Escape.
**Supporting Evidence:** Esc handler ([`HelpPanel.vue:163-166`](../../frontend/src/components/help/HelpPanel.vue#L163)); close button `data-test-id="help-close"` ([`HelpPanel.vue:196-204`](../../frontend/src/components/help/HelpPanel.vue#L196)). The footer also advertises `?` to open / Esc to close, but only Esc-to-close is verified in this component.
**Source Files:** frontend/src/components/help/HelpPanel.vue
**API References:** none
**Database References:** none

### Q3. How does the search work — is it AI/semantic?
**Verified Answer:** Search activates at 2+ characters and is **lexical**, not semantic: it does a case-insensitive substring match over every topic's question+answer (and the FAQ), then ranks title hits first. The placeholder says "semantic + lexical" but the implementation is substring + title-rank.
**Supporting Evidence:** `searchResults` computed ([`stores/help.ts:104-129`](../../frontend/src/stores/help.ts#L104)); activates ≥2 chars ([`HelpPanel.vue:76`](../../frontend/src/components/help/HelpPanel.vue#L76)).
**Source Files:** frontend/src/stores/help.ts, frontend/src/components/help/HelpPanel.vue
**API References:** none
**Database References:** none

### Q4. What happens when I ask the AI a question and how do I submit it?
**Verified Answer:** In the Ask AI tab, type your question and press **Cmd/Ctrl+Enter** (or click Ask). The answer comes back grounded in the help articles, with a numbered citation list. The Ask button is disabled until the question is at least 2 characters. If the AI is unavailable, you still get a useful answer assembled from the top matching articles.
**Supporting Evidence:** Cmd/Ctrl+Enter submit + min-length ([`HelpAskComposer.vue:38-54`](../../frontend/src/components/help/HelpAskComposer.vue#L38)); request flow ([`stores/help.ts:149-207`](../../frontend/src/stores/help.ts#L149)); extractive fallback ([`app/api/help.py:194-228`](../../app/api/help.py#L194)).
**Source Files:** frontend/src/components/help/HelpAskComposer.vue, frontend/src/stores/help.ts, app/api/help.py
**API References:** POST /v1/help/ask
**Database References:** none (Ask reads the in-process corpus, not the DB)

### Q5. Why is the Ask AI tab sometimes just "Coming soon"?
**Verified Answer:** Ask AI is gated by a backend flag, `HELP_ASK_AI_ENABLED`, which is OFF by default. The frontend reads `help_ask_ai_enabled` from `/v1/version` on app mount; when false, the tab still renders but shows a "Coming soon" notice instead of the chat composer. When the flag is off, calling the endpoint returns 404.
**Supporting Evidence:** flag default OFF ([`app/config.py:121`](../../app/config.py#L121)); 404 when off ([`app/api/help.py:174-175`](../../app/api/help.py#L174)); flag plumbing ([`app/main.py:183`](../../app/main.py#L183), [`AppHeader.vue:58-59`](../../frontend/src/components/AppHeader.vue#L58)); coming-soon render ([`HelpPanel.vue:346-363`](../../frontend/src/components/help/HelpPanel.vue#L346)).
**Source Files:** app/config.py, app/main.py, frontend/src/components/AppHeader.vue, frontend/src/components/help/HelpPanel.vue
**API References:** POST /v1/help/ask, GET /v1/version
**Database References:** none

### Q6. The Ask AI tab said I hit a limit. What is that?
**Verified Answer:** There's a per-user hourly cap on Ask AI questions (default 30 per hour). Exceeding it returns a 429 with code `HELP_ASK_RATE_LIMIT`; the UI shows "Hourly Ask AI limit reached. Try again in a few minutes." Wait and retry.
**Supporting Evidence:** cap config ([`app/config.py:123`](../../app/config.py#L123)); rate-limit check + 429 ([`app/api/help.py:114-135`, `181-190`](../../app/api/help.py#L114)); UI mapping ([`stores/help.ts:69-73`](../../frontend/src/stores/help.ts#L69)).
**Source Files:** app/config.py, app/api/help.py, frontend/src/stores/help.ts
**API References:** POST /v1/help/ask
**Database References:** none (Redis-backed counter, not Postgres)

---

## Administrator

### Q1. Who can access the admin Help Editor?
**Verified Answer:** Only the bootstrap admin — the single hardcoded email `johndean@vin.com`. There is no role-tier system in effect: `auth_users.role` exists in the schema but is not read by auth, and the role helper is scaffold-only. The `/admin/help` route has a client-side `adminOnly` guard that redirects non-admins to `/dashboard`, and every write/admin API endpoint enforces the same email gate server-side via `require_admin`.
**Supporting Evidence:** `LEGACY_ADMIN_EMAIL` gate ([`app/security/roles.py:54`, `62-92`](../../app/security/roles.py#L54)); scaffold-only note ([`app/security/roles.py:11-19`](../../app/security/roles.py#L11)); route guard ([`router/index.ts:63-66`](../../frontend/src/router/index.ts#L63)); `require_admin` on writes ([`app/api/help.py:461`, `529`, `632`](../../app/api/help.py#L461)).
**Source Files:** app/security/roles.py, frontend/src/router/index.ts, app/api/help.py
**API References:** POST/PATCH /v1/help/articles, all /v1/help/admin/*
**Database References:** help_articles

### Q2. When I edit an article, is the old version kept?
**Verified Answer:** Yes. Every PATCH snapshots the prior full row into `help_article_versions` **before** applying the change, then bumps `version` and stamps `last_edited_by`. Archive does the same. The version table is append-only (never updated/deleted). You can view and restore prior versions from the History dialog; restoring sends the snapshot back as a PATCH (which itself appends a new version).
**Supporting Evidence:** PATCH snapshot-then-update ([`app/api/help.py:594-610`](../../app/api/help.py#L594)); table is append-only ([`migrations/054_help_article_versions.sql:9-13`](../../migrations/054_help_article_versions.sql#L9)); restore-via-PATCH ([`HelpVersionHistoryDialog.vue:42-67`](../../frontend/src/components/help/HelpVersionHistoryDialog.vue#L42)).
**Source Files:** app/api/help.py, migrations/054_help_article_versions.sql, frontend/src/components/help/HelpVersionHistoryDialog.vue
**API References:** PATCH /v1/help/articles/{id}, GET /v1/help/articles/{id}/versions
**Database References:** help_articles, help_article_versions

### Q3. What does "Archive" actually do — is the article deleted?
**Verified Answer:** No. Archive is a soft-unpublish: it sets `is_published = FALSE`, bumps the version, and preserves the article and its full version history. There is no separate `archived` flag and no hard-delete in the UI (hard purge is DB-intervention only, and would cascade-delete versions).
**Supporting Evidence:** archive endpoint ([`app/api/help.py:624-668`](../../app/api/help.py#L624)); cascade note ([`migrations/054_help_article_versions.sql:15-18`](../../migrations/054_help_article_versions.sql#L15)); UI confirm copy ([`HelpEditor.vue:113-114`](../../frontend/src/views/admin/HelpEditor.vue#L113)).
**Source Files:** app/api/help.py, migrations/054_help_article_versions.sql, frontend/src/views/admin/HelpEditor.vue
**API References:** PATCH /v1/help/articles/{id}/archive
**Database References:** help_articles, help_article_versions

### Q4. "Publish all drafts" — does it publish everything?
**Verified Answer:** No. It runs CC-Rounds compliance on every draft and publishes only the rows that pass all checks. It returns counts plus a `skipped[]` list with each failed draft's compliance breakdown (wordsOk/summaryOk/stepsOk + the actual counts) so you can target a fix. This runs inline (not via Celery).
**Supporting Evidence:** compliance-gated bulk publish ([`app/api/help.py:829-894`](../../app/api/help.py#L829)); UI toast logic ([`HelpAdminToolbar.vue:47-64`](../../frontend/src/components/help/HelpAdminToolbar.vue#L47)).
**Source Files:** app/api/help.py, app/utils/help_compliance.py, frontend/src/components/help/HelpAdminToolbar.vue
**API References:** POST /v1/help/admin/bulk-publish
**Database References:** help_articles

### Q5. What do the AI toolbar buttons (Fix CC-Rounds, Expand Steps, Expand FAQs, Generate FAQ corpus) do, and are changes published immediately?
**Verified Answer:** They enqueue Celery tasks that use Gemini to clean up content. Fix CC-Rounds rewrites non-compliant summaries; Expand Steps/FAQs draft additional steps for under-length Help/FAQ articles; Generate FAQ corpus drafts one FAQ article per route. **Nothing is auto-published** — every AI edit/draft lands as `is_published=FALSE` for your review. Each button shows a confirm, returns a `task_id`, and tells you to refresh in ~30s. Generate FAQ corpus is safe to re-run (slug-based idempotency + a concurrency guard).
**Supporting Evidence:** enqueue endpoints ([`app/api/help.py:916-948`](../../app/api/help.py#L916)); review-gate invariant ([`app/tasks/help_tasks.py:18-21`, `252`, `378`, `718`](../../app/tasks/help_tasks.py#L18)); idempotency + concurrency guard ([`app/tasks/help_tasks.py:548-561`, `583-591`](../../app/tasks/help_tasks.py#L548)).
**Source Files:** app/api/help.py, app/tasks/help_tasks.py, frontend/src/components/help/HelpAdminToolbar.vue
**API References:** POST /v1/help/admin/fix-summaries, /expand-steps, /expand-faqs, /generate-faq-corpus
**Database References:** help_articles, help_article_versions, audit_events

### Q6. Why did Generate FAQ corpus skip or reject some routes?
**Verified Answer:** Three reasons. (1) **Skipped existing** — a route already has its `faq-ai-{page_key}` draft (idempotency). (2) **Dev-speak rejected** — the AI output contained a forbidden term (component names, table names, HTTP routes, env vars, "Phase N", framework names, `.vue`, SCREAMING_SNAKE), caught by a literal + regex blacklist post-filter. (3) **Failed** — the JSON was malformed, too few steps, or the summary length was outside the FAQ range. Counts are returned as `{created, skipped_existing, devspeak_rejected, failed}`.
**Supporting Evidence:** blacklist + regexes ([`app/tasks/help_tasks.py:465-514`](../../app/tasks/help_tasks.py#L465)); validation + reject paths ([`app/tasks/help_tasks.py:644-705`](../../app/tasks/help_tasks.py#L644)); return shape ([`app/tasks/help_tasks.py:771-777`](../../app/tasks/help_tasks.py#L771)).
**Source Files:** app/tasks/help_tasks.py
**API References:** POST /v1/help/admin/generate-faq-corpus
**Database References:** help_articles, audit_events

### Q7. What is the CC-Rounds compliance meter checking?
**Verified Answer:** Three things per article: step-body **word count**, **summary length**, and **step count**. Help articles need ≥3 steps, ≥200 words, summary ≥180 chars (no max). FAQ articles need ≥2 steps, ≥80 words, summary 60–300 chars. An article is FAQ if its `category` contains the substring "faq". The meter shows pass/fail per dimension plus an overall percent. The thresholds are identical on backend and frontend (pinned by a test).
**Supporting Evidence:** thresholds + `is_faq_category` ([`app/utils/help_compliance.py:39-63`](../../app/utils/help_compliance.py#L39)); compute logic ([`app/utils/help_compliance.py:79-138`](../../app/utils/help_compliance.py#L79)); meter render ([`HelpComplianceMeter.vue:18-62`](../../frontend/src/components/help/HelpComplianceMeter.vue#L18)).
**Source Files:** app/utils/help_compliance.py, frontend/src/utils/helpCompliance.ts, frontend/src/components/help/HelpComplianceMeter.vue
**API References:** none (computed client-side; also used by bulk-publish server-side)
**Database References:** help_articles

---

## Operations

### Q1. Ask AI is enabled but failing silently — does it ever 500?
**Verified Answer:** No. When enabled, the Ask path is designed to never raise 5xx for an AI failure: if Gemini is unavailable, misconfigured, or returns unparseable JSON, it degrades to an extractive answer built from the top retrieved articles and logs a warning. It returns 4xx only for the disabled flag (404), empty question (400), or rate limit (429).
**Supporting Evidence:** never-5xx invariant ([`app/api/help.py:24-29`](../../app/api/help.py#L24)); degrade path ([`app/api/help.py:226-228`](../../app/api/help.py#L226)).
**Source Files:** app/api/help.py
**API References:** POST /v1/help/ask
**Database References:** none

### Q2. What happens if Redis is down — does Ask AI break?
**Verified Answer:** No. The rate-limit check soft-fails open: on any Redis error it logs a warning and allows the request. Similarly, the Celery tasks' idempotency keys soft-fail (the rewrite proceeds, just without dedupe protection). Redis is a cost/dedupe guard here, not a hard dependency for availability.
**Supporting Evidence:** rate-limit soft-fail ([`app/api/help.py:133-135`](../../app/api/help.py#L133)); task idempotency soft-fail ([`app/tasks/help_tasks.py:87-89`](../../app/tasks/help_tasks.py#L87)).
**Source Files:** app/api/help.py, app/tasks/help_tasks.py
**API References:** POST /v1/help/ask
**Database References:** none

### Q3. What happens if the help tables aren't migrated yet?
**Verified Answer:** Read endpoints degrade gracefully. `GET /articles` and `GET /search` catch a missing-table error and return an empty list (logged warning) instead of 500. Creating an article when the table is missing returns 503 `TABLE_NOT_MIGRATED`. The FAQ tab in the drawer falls back to the hardcoded corpus when the API returns empty or errors.
**Supporting Evidence:** list/search empty fallback ([`app/api/help.py:413-417`, `815-819`](../../app/api/help.py#L413)); create 503 ([`app/api/help.py:508-512`](../../app/api/help.py#L508)); FAQ fallback ([`HelpPanel.vue:316-341`](../../frontend/src/components/help/HelpPanel.vue#L316)).
**Source Files:** app/api/help.py, frontend/src/components/help/HelpPanel.vue
**API References:** GET /v1/help/articles, GET /v1/help/search, POST /v1/help/articles
**Database References:** help_articles

### Q4. How do I enqueue a bulk task by hand, and what does an unreachable broker return?
**Verified Answer:** POST to the relevant `/v1/help/admin/*` endpoint (with an admin JWT). Each calls `celery_app.send_task(task_name)` and returns `{task_id, task, enqueued:true}`. If the broker is unreachable, the endpoint returns 503 `QUEUE_UNAVAILABLE` rather than hanging.
**Supporting Evidence:** shared enqueue + 503 ([`app/api/help.py:900-948`](../../app/api/help.py#L900)).
**Source Files:** app/api/help.py
**API References:** POST /v1/help/admin/fix-summaries, /expand-steps, /expand-faqs, /generate-faq-corpus
**Database References:** none

### Q5. Is there an event/notification when a bulk task finishes?
**Verified Answer:** No live event today. Bulk tasks are fire-and-forget; the toolbar tells the admin to refresh the list in ~30s, and a WS auto-refresh is noted as future work. Completion is observable indirectly through the new drafts appearing on refresh and the `audit_events` rows the tasks write.
**Supporting Evidence:** fire-and-forget + manual-refresh note ([`HelpAdminToolbar.vue:18-20`](../../frontend/src/components/help/HelpAdminToolbar.vue#L18)); audit rows ([`app/tasks/help_tasks.py:129-146`](../../app/tasks/help_tasks.py#L129)).
**Source Files:** frontend/src/components/help/HelpAdminToolbar.vue, app/tasks/help_tasks.py
**API References:** none
**Database References:** audit_events

---

## Compliance

### Q1. Is there an audit trail for help-article changes?
**Verified Answer:** Partially. AI bulk operations write `audit_events` rows with `kind='help.ai_rewrite'`, actor `ai:{task-name}`, and details capturing version-before/after and what changed. **Human edits via the API are NOT written to `audit_events`** — they are captured in `help_article_versions` (full prior snapshot + `edited_by` + `edited_at`). So the human-edit trail is the version table; the global audit log only records AI rewrites.
**Supporting Evidence:** AI audit emit ([`app/tasks/help_tasks.py:129-146`, `257-269`](../../app/tasks/help_tasks.py#L129)); no `audit_events` insert in the human CRUD paths ([`app/api/help.py:455-701`](../../app/api/help.py#L455)); version table fields ([`migrations/054_help_article_versions.sql:22-30`](../../migrations/054_help_article_versions.sql#L22)).
**Source Files:** app/tasks/help_tasks.py, app/api/help.py, migrations/054_help_article_versions.sql
**API References:** PATCH /v1/help/articles/{id}, all /v1/help/admin/*
**Database References:** audit_events, help_article_versions

### Q2. Can non-admins see unpublished or admin-only help articles?
**Verified Answer:** No. The list, detail, and search endpoints mask content for non-admins in SQL: non-admins see only `is_published=TRUE AND audience='users'`. The detail endpoint returns 404 (not 403) for hidden rows so it does not even leak that the article exists.
**Supporting Evidence:** list/search masking ([`app/api/help.py:388-390`, `799-801`](../../app/api/help.py#L388)); detail existence not leaked ([`app/api/help.py:445-448`](../../app/api/help.py#L445)); filter helper ([`app/api/help.py:349-354`](../../app/api/help.py#L349)).
**Source Files:** app/api/help.py
**API References:** GET /v1/help/articles, GET /v1/help/articles/{id}, GET /v1/help/search
**Database References:** help_articles

### Q3. Does the AI invent features in user-facing help text?
**Verified Answer:** It is constrained against it. Ask AI's system prompt restricts the model to the provided articles and tells it to say so plainly if they don't cover the question. The bulk-content prompts forbid inventing features, component names, schema terms, routes, env vars, and phase markers. The FAQ-corpus generator additionally **post-filters** output against a literal + regex dev-speak blacklist and rejects any violating draft, as defense in depth beyond the prompt.
**Supporting Evidence:** Ask grounding prompt ([`app/api/help.py:202-209`](../../app/api/help.py#L202)); bulk prompt constraints ([`app/tasks/help_tasks.py:222-230`](../../app/tasks/help_tasks.py#L222)); blacklist post-filter ([`app/tasks/help_tasks.py:465-514`, `695-705`](../../app/tasks/help_tasks.py#L465)).
**Source Files:** app/api/help.py, app/tasks/help_tasks.py
**API References:** POST /v1/help/ask, POST /v1/help/admin/generate-faq-corpus
**Database References:** help_articles

### Q4. Are AI-generated help articles published without human review?
**Verified Answer:** No. Every AI rewrite or AI-generated draft is saved with `is_published=FALSE` and requires an admin to manually publish it (via Publish all drafts or the editor). This is an explicit invariant in the task module.
**Supporting Evidence:** review-gate invariant ([`app/tasks/help_tasks.py:18-21`](../../app/tasks/help_tasks.py#L18)); drafts on insert/update ([`app/tasks/help_tasks.py:252`, `378`, `718`](../../app/tasks/help_tasks.py#L252)).
**Source Files:** app/tasks/help_tasks.py
**API References:** POST /v1/help/admin/*
**Database References:** help_articles
**Flags:** Note that `require_admin` today resolves to a single hardcoded email gate, not a role system (see Administrator Q1).

---

## Power User

### Q1. How are search results ranked in the Ask AI retrieval vs. the drawer search?
**Verified Answer:** Two different mechanisms. The **drawer search** (client-side) is substring match over question+answer with title hits sorted first. The **Ask AI retrieval** (backend) scores each corpus article by term overlap on title+summary, adds +2 if the article's `page_key` matches the current page and +1 if the `role` matches, sorts descending, takes the top 5, and if nothing scores it falls back to the first 3 so it always cites something.
**Supporting Evidence:** drawer rank ([`stores/help.ts:122-128`](../../frontend/src/stores/help.ts#L122)); backend scoring ([`app/api/help.py:86-108`](../../app/api/help.py#L86)).
**Source Files:** frontend/src/stores/help.ts, app/api/help.py
**API References:** POST /v1/help/ask
**Database References:** none

### Q2. Does editing a help article in the CMS change what Ask AI answers?
**Verified Answer:** No. Ask AI retrieves from an in-process Python corpus (`app/data/help_content.py`), which is a hand-maintained mirror of the frontend constants — not from the `help_articles` table. CMS edits affect the drawer's FAQ tab and the article list, but not Ask AI answers, until/unless the corpus source is migrated to the DB (noted as future work in the file).
**Supporting Evidence:** Ask reads `flatten_corpus()` ([`app/api/help.py:100`, `192`](../../app/api/help.py#L100)); corpus is a hand-mirror, DB read is future ([`app/data/help_content.py:13-15`](../../app/data/help_content.py#L13)).
**Source Files:** app/api/help.py, app/data/help_content.py
**API References:** POST /v1/help/ask, GET /v1/help/articles
**Database References:** help_articles (CMS), none (Ask)

### Q3. How do related-article cross-links resolve, and is there a limit?
**Verified Answer:** An article's `related_article_ids` is a JSONB UUID array. `HelpRelatedLinks` fetches up to the first 5 via individual `GET /v1/help/articles/{id}` calls (each tolerant of failure), and renders them as clickable chips that emit a `select` event. In the editor dialog the related picker caps selection at 5. There's no DB foreign-key enforcement on these ids; the FAQ generator additionally validates ids against existing rows before storing.
**Supporting Evidence:** fetch capped at 5 ([`HelpRelatedLinks.vue:33-37`](../../frontend/src/components/help/HelpRelatedLinks.vue#L33)); editor cap ([`HelpArticleEditorDialog.vue:121-129`](../../frontend/src/components/help/HelpArticleEditorDialog.vue#L121)); generator id validation ([`app/tasks/help_tasks.py:687-693`](../../app/tasks/help_tasks.py#L687)).
**Source Files:** frontend/src/components/help/HelpRelatedLinks.vue, frontend/src/components/help/HelpArticleEditorDialog.vue, app/tasks/help_tasks.py
**API References:** GET /v1/help/articles/{id}
**Database References:** help_articles

### Q4. What's the difference between a Help article and a FAQ article internally?
**Verified Answer:** It's a single predicate on `category`: any category containing the substring "faq" (case-insensitive) is treated as FAQ. Seed FAQ rows use `category` like `faq:auth` / `faq:editor`; AI-generated FAQ rows use `faq:{page_key}`. This drives looser CC-Rounds thresholds (≥2 steps / ≥80 words / 60–300 char summary vs Help's ≥3 / ≥200 / ≥180), the FAQ-vs-Help routing of the Expand tasks, and which articles surface in the drawer's FAQ tab.
**Supporting Evidence:** predicate ([`app/utils/help_compliance.py:58-63`](../../app/utils/help_compliance.py#L58)); seed categories ([`migrations/055_help_articles_seed.sql:245-275`](../../migrations/055_help_articles_seed.sql#L245)); FAQ tab filter ([`HelpPanel.vue:100-105`](../../frontend/src/components/help/HelpPanel.vue#L100)).
**Source Files:** app/utils/help_compliance.py, migrations/055_help_articles_seed.sql, frontend/src/components/help/HelpPanel.vue
**API References:** GET /v1/help/articles
**Database References:** help_articles

### Q5. Is reordering articles versioned, and is there a UI for it?
**Verified Answer:** Reordering is intentionally NOT versioned — `PATCH /v1/help/articles/reorder` only updates `display_order` (and `last_edited_by`/`updated_at`) without snapshotting, because snapshotting a drag-reorder of many rows would bloat the version table. A typed `reorderArticles` service wrapper exists, but no drag-reorder control was found in the Help Editor view — the reorder UI is not implemented.
**Supporting Evidence:** reorder endpoint (no snapshot) ([`app/api/help.py:674-701`](../../app/api/help.py#L674)); service wrapper ([`helpArticlesApi.ts:118-123`](../../frontend/src/services/helpArticlesApi.ts#L118)).
**Source Files:** app/api/help.py, frontend/src/services/helpArticlesApi.ts
**API References:** PATCH /v1/help/articles/reorder
**Database References:** help_articles
**Flags:** Reorder UI — IMPLEMENTATION NOT FOUND in HelpEditor.vue.

---

## Source Verification
- **Files Used:** app/api/help.py, app/tasks/help_tasks.py, app/data/help_content.py, app/utils/help_compliance.py, app/security/roles.py, app/config.py, app/main.py, migrations/053_help_articles.sql, migrations/054_help_article_versions.sql, migrations/055_help_articles_seed.sql, migrations/056_help_articles_steps_content.sql, frontend/src/stores/help.ts, frontend/src/services/helpApi.ts, frontend/src/services/helpArticlesApi.ts, frontend/src/router/index.ts, frontend/src/composables/useIsAdmin.ts, frontend/src/views/admin/HelpEditor.vue, frontend/src/components/help/* , frontend/src/components/AppHeader.vue
- **Components Used:** HelpPanel, HelpItem, HelpAskComposer, HelpFaqAccordion, HelpRelatedLinks, HelpEditor, HelpAdminToolbar, HelpComplianceMeter, HelpVersionHistoryDialog, AppHeader
- **APIs Used:** POST /v1/help/ask; GET/POST /v1/help/articles; GET/PATCH /v1/help/articles/{id}; PATCH /v1/help/articles/{id}/archive; PATCH /v1/help/articles/reorder; GET /v1/help/articles/{id}/versions; GET /v1/help/coverage; GET /v1/help/search; POST /v1/help/admin/{bulk-publish,fix-summaries,expand-steps,expand-faqs,generate-faq-corpus}; GET /v1/version
- **Database Tables Used:** help_articles, help_article_versions, audit_events
- **Permission Logic Used:** JWT (CurrentUser) + LEGACY_ADMIN_EMAIL gate (require_admin) + SQL audience masking + client adminOnly route guard
- **Confidence Score:** High — every answer is line-traced to source; deviations from advertised behavior (lexical search, in-process Ask corpus, partial audit, missing reorder UI) are explicitly called out.
- **Evidence Links:** [app/api/help.py:164](../../app/api/help.py#L164), [app/api/help.py:829](../../app/api/help.py#L829), [app/utils/help_compliance.py:39](../../app/utils/help_compliance.py#L39), [app/tasks/help_tasks.py:517](../../app/tasks/help_tasks.py#L517), [app/security/roles.py:62](../../app/security/roles.py#L62), [frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63)
