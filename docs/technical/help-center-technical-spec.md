# Help Center — Technical Spec

> Code-verified against the rounds.vin repository. Uncertainty tags used where applicable: **NOT VERIFIED IN CODE**, **IMPLEMENTATION NOT FOUND**, **PARTIALLY IMPLEMENTED**.

## Architecture

The Help Center spans backend (FastAPI + SQLAlchemy core SQL + Celery) and frontend (Vue 3 + Pinia). It has two backend "eras" living in one router:

- **Ask AI (in-process RAG)**: `POST /v1/help/ask` retrieves from an in-memory Python corpus ([`app/data/help_content.py`](../../app/data/help_content.py)) and synthesizes via Gemini, with an extractive fallback. No DB read on this path.
- **Article CMS (DB-backed)**: CRUD + versions + coverage + search over the `help_articles` / `help_article_versions` tables, plus admin bulk-AI Celery tasks.

Backend module: [`app/api/help.py`](../../app/api/help.py) — router prefix `/v1/help`, tag `help` ([`app/api/help.py:58`](../../app/api/help.py#L58)), included at [`app/main.py:233`](../../app/main.py#L233). Bulk tasks: [`app/tasks/help_tasks.py`](../../app/tasks/help_tasks.py). Compliance SSOT: [`app/utils/help_compliance.py`](../../app/utils/help_compliance.py) (mirrored on the frontend at [`frontend/src/utils/helpCompliance.ts`](../../frontend/src/utils/helpCompliance.ts)).

Frontend: a Pinia store ([`frontend/src/stores/help.ts`](../../frontend/src/stores/help.ts)) drives the inline drawer; two typed service files wrap the backend ([`helpApi.ts`](../../frontend/src/services/helpApi.ts) for Ask; [`helpArticlesApi.ts`](../../frontend/src/services/helpArticlesApi.ts) for the CMS). The admin CMS view is [`HelpEditor.vue`](../../frontend/src/views/admin/HelpEditor.vue).

## Frontend Components

| Component | Role | Evidence |
|---|---|---|
| `HelpPanel.vue` | Inline drawer shell: search, 3 tabs, FAQ hybrid load, footer | [`HelpPanel.vue`](../../frontend/src/components/help/HelpPanel.vue) |
| `HelpItem.vue` | Accordion q/a card (props `q`, `a`, `defaultOpen`) | [`HelpItem.vue`](../../frontend/src/components/help/HelpItem.vue) |
| `HelpFaqAccordion.vue` | API-backed FAQ article (title + summary + steps + related chips) | [`HelpFaqAccordion.vue`](../../frontend/src/components/help/HelpFaqAccordion.vue) |
| `HelpAskComposer.vue` | Ask AI thread + composer; Cmd/Ctrl+Enter submit | [`HelpAskComposer.vue`](../../frontend/src/components/help/HelpAskComposer.vue) |
| `HelpStepList.vue` | Read-only numbered steps render | [`HelpStepList.vue`](../../frontend/src/components/help/HelpStepList.vue) |
| `HelpRelatedLinks.vue` | Fetches up to 5 related articles, renders chips, emits `select` | [`HelpRelatedLinks.vue`](../../frontend/src/components/help/HelpRelatedLinks.vue) |
| `HelpEditor.vue` (view) | Admin CMS page at `/admin/help` | [`HelpEditor.vue`](../../frontend/src/views/admin/HelpEditor.vue) |
| `HelpAdminToolbar.vue` | Bulk action buttons (publish-all + 4 AI tasks + refresh) | [`HelpAdminToolbar.vue`](../../frontend/src/components/help/HelpAdminToolbar.vue) |
| `HelpCoverageReport.vue` | Published count per domain; <2 red; `defineExpose({refresh})` | [`HelpCoverageReport.vue`](../../frontend/src/components/help/HelpCoverageReport.vue) |
| `HelpArticleEditorDialog.vue` | Create/edit modal with live compliance preview | [`HelpArticleEditorDialog.vue`](../../frontend/src/components/help/HelpArticleEditorDialog.vue) |
| `HelpVersionHistoryDialog.vue` | Version list + restore-via-PATCH | [`HelpVersionHistoryDialog.vue`](../../frontend/src/components/help/HelpVersionHistoryDialog.vue) |
| `HelpComplianceMeter.vue` | Compact 3-dot or detailed CC-Rounds meter | [`HelpComplianceMeter.vue`](../../frontend/src/components/help/HelpComplianceMeter.vue) |

Composables / stores: `useHelpStore` ([`stores/help.ts`](../../frontend/src/stores/help.ts)), `useIsAdmin` ([`composables/useIsAdmin.ts`](../../frontend/src/composables/useIsAdmin.ts)).

## Backend Services

- **`app/api/help.py`** — all routes. Uses raw `sqlalchemy.text` SQL with bind params and explicit `CAST(... AS uuid|jsonb)`. Row serialization via `_row_to_article` / `_row_to_version` ([`app/api/help.py:249-282`](../../app/api/help.py#L249)).
  - Retrieval scoring `_score_article` / `_retrieve_top`: term overlap on title+summary, +2 for page_key match, +1 for role match; top-5; cold fallback to first 3 ([`app/api/help.py:86-108`](../../app/api/help.py#L86)).
  - `_rate_limit_check`: Redis INCR keyed `rounds:help:ask:{email}:{epoch_hour}` with 3600s expire; soft-fails open ([`app/api/help.py:114-135`](../../app/api/help.py#L114)).
  - `_slugify`: NFKD→ASCII, lowercase, hyphenate, strip non-`[a-z0-9-]`, ≤64 ([`app/api/help.py:288-294`](../../app/api/help.py#L288)).
- **`app/tasks/help_tasks.py`** — four Celery tasks (below). Uses its own sync engine (`DATABASE_URL` with `+asyncpg` stripped) ([`app/tasks/help_tasks.py:64-68`](../../app/tasks/help_tasks.py#L64)).
- **`app/utils/help_compliance.py`** — pure `compute_compliance` + `is_faq_category` ([`app/utils/help_compliance.py:58-138`](../../app/utils/help_compliance.py#L58)).
- **`app/engines/llm_client.py`** — `call_gemini_text(system_prompt, user_payload, model_id='gemini-2.5-pro', max_retries=2, max_output_tokens=...)` ([`app/engines/llm_client.py:217-242`](../../app/engines/llm_client.py#L217)).

## APIs

All under prefix `/v1/help`; all require `CurrentUser` (JWT). Admin-gated endpoints call `require_admin(user)`.

| Method & Path | Auth | Purpose | Evidence |
|---|---|---|---|
| `POST /ask` | JWT; gated by `HELP_ASK_AI_ENABLED` | Grounded Q&A → `{answer, sources[], used_llm}` | [`app/api/help.py:164-230`](../../app/api/help.py#L164) |
| `GET /articles` | JWT (audience-filtered) | List; query `feature_tag`, `audience`, `content_domain`, `limit` | [`app/api/help.py:370-419`](../../app/api/help.py#L370) |
| `GET /articles/{id}` | JWT (audience-filtered) | One article; 404 if hidden | [`app/api/help.py:425-449`](../../app/api/help.py#L425) |
| `POST /articles` | admin | Create (201); auto-slug; 409 on slug collision | [`app/api/help.py:455-516`](../../app/api/help.py#L455) |
| `PATCH /articles/{id}` | admin | Versioned partial update | [`app/api/help.py:522-618`](../../app/api/help.py#L522) |
| `PATCH /articles/{id}/archive` | admin | Soft-archive (`is_published=FALSE`) | [`app/api/help.py:624-668`](../../app/api/help.py#L624) |
| `PATCH /articles/reorder` | admin | Bulk `display_order` set (not versioned) | [`app/api/help.py:674-701`](../../app/api/help.py#L674) |
| `GET /articles/{id}/versions` | admin | All versions newest-first | [`app/api/help.py:707-723`](../../app/api/help.py#L707) |
| `GET /articles/{id}/versions/{version}` | admin | Single version | [`app/api/help.py:726-744`](../../app/api/help.py#L726) |
| `GET /coverage` | admin | Counts per domain + totals | [`app/api/help.py:750-780`](../../app/api/help.py#L750) |
| `GET /search` | JWT (audience-filtered) | Substring on title+summary, title-rank | [`app/api/help.py:786-821`](../../app/api/help.py#L786) |
| `POST /admin/bulk-publish` | admin | Inline CC-Rounds-gated publish | [`app/api/help.py:829-894`](../../app/api/help.py#L829) |
| `POST /admin/fix-summaries` | admin | Enqueue `rounds.tasks.help.fix_summaries` | [`app/api/help.py:916-922`](../../app/api/help.py#L916) |
| `POST /admin/expand-steps` | admin | Enqueue `rounds.tasks.help.expand_steps` | [`app/api/help.py:925-928`](../../app/api/help.py#L925) |
| `POST /admin/expand-faqs` | admin | Enqueue `rounds.tasks.help.expand_faqs` | [`app/api/help.py:931-934`](../../app/api/help.py#L931) |
| `POST /admin/generate-faq-corpus` | admin | Enqueue `rounds.tasks.help.generate_faq_corpus` | [`app/api/help.py:937-948`](../../app/api/help.py#L937) |

Ask request/response models: `HelpAskRequest{question, page_key?, role?}`, `HelpAskResponse{answer, sources[HelpAskSource{id,title,summary}], used_llm}` ([`app/api/help.py:64-79`](../../app/api/help.py#L64)). Frontend mirror: [`helpApi.ts:19-53`](../../frontend/src/services/helpApi.ts#L19). The `/v1/version` flag `help_ask_ai_enabled` toggles the Ask tab ([`app/main.py:159-189`](../../app/main.py#L159), [`AppHeader.vue:53-59`](../../frontend/src/components/AppHeader.vue#L53)).

## Data Models

### `help_articles` ([`migrations/053_help_articles.sql:20-38`](../../migrations/053_help_articles.sql#L20))
`id UUID PK (gen_random_uuid)`, `slug TEXT NOT NULL UNIQUE`, `title TEXT NOT NULL`, `summary TEXT NOT NULL DEFAULT ''`, `category TEXT DEFAULT 'general'`, `audience TEXT DEFAULT 'users'`, `feature_tags JSONB DEFAULT '[]'`, `steps JSONB DEFAULT '[]'`, `related_article_ids JSONB DEFAULT '[]'`, `display_order INT DEFAULT 0`, `is_published BOOL DEFAULT FALSE`, `content_domain TEXT DEFAULT 'general'`, `workflow_slug TEXT NULL`, `version INT DEFAULT 1`, `last_edited_by TEXT DEFAULT ''`, `created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ`.
Indexes: `is_published`, `content_domain`, `audience`, GIN on `feature_tags`, composite `(content_domain, display_order)` ([`migrations/053_help_articles.sql:41-51`](../../migrations/053_help_articles.sql#L41)). Table is `CREATE TABLE IF NOT EXISTS` — not dropped on re-run.

### `help_article_versions` ([`migrations/054_help_article_versions.sql:22-30`](../../migrations/054_help_article_versions.sql#L22))
`id UUID PK`, `article_id UUID NOT NULL REFERENCES help_articles(id) ON DELETE CASCADE`, `version INT NOT NULL`, `snapshot JSONB NOT NULL`, `edited_by TEXT DEFAULT ''`, `edited_at TIMESTAMPTZ`, `UNIQUE (article_id, version)`. Append-only; index `(article_id, edited_at DESC)`.

### Seeds
- `055` seeds ~70 published articles from the hardcoded corpus (slug `<page_key>-<role>-<idx>` / `faq-<idx>`), `ON CONFLICT (slug) DO NOTHING` ([`migrations/055_help_articles_seed.sql`](../../migrations/055_help_articles_seed.sql)).
- `056` UPDATEs each seeded row with hand-authored `steps[]` (3 for Help, 2 for FAQ) and some summaries to clear CC-Rounds; wrapped in `BEGIN;`, matches on slug, bumps `version` ([`migrations/056_help_articles_steps_content.sql:46-95`](../../migrations/056_help_articles_steps_content.sql#L46)).

### In-process Ask corpus ([`app/data/help_content.py`](../../app/data/help_content.py))
`HELP_CONTENT` dict (`pages` × roles + `faq` + `contact`). `flatten_corpus()` yields `HelpArticle{id, page_key, role, title, summary}` with ids `<page_key>:<role>:<idx>` or `faq:<idx>` ([`app/data/help_content.py:288-316`](../../app/data/help_content.py#L288)). This is a hand-mirror of [`frontend/src/constants/help-content.ts`](../../frontend/src/constants/help-content.ts).

### Frontend DTOs ([`helpArticlesApi.ts:14-76`](../../frontend/src/services/helpArticlesApi.ts#L14))
`HelpStep{title,body}`, `HelpArticleDTO` (full row), `HelpArticleVersion{...,snapshot:HelpArticleDTO}`, `HelpCoverageResponse{by_domain, total_published, total_drafts}`, create/update payloads, list filters.

## Events

- **No WebSocket / pub-sub events** are emitted for the Help Center. Bulk Celery tasks are fire-and-forget; the toolbar tells the admin to refresh manually in ~30s ([`HelpAdminToolbar.vue:18-20`, `72`](../../frontend/src/components/help/HelpAdminToolbar.vue#L18)). A WS auto-refresh is explicitly noted as future work in the component header. **IMPLEMENTATION NOT FOUND** for any live event channel.
- **Audit events** (`audit_events` rows) are emitted only by the AI bulk tasks (`kind='help.ai_rewrite'`) — see Background Jobs. These are persisted rows, not a message bus.

## State Management

- **Pinia `useHelpStore`** ([`stores/help.ts:89-232`](../../frontend/src/stores/help.ts#L89)):
  - Panel: `open`, `pageKey`, `setPageKey/toggle/show/hide`.
  - Search: `searchQuery`, computed `searchResults` (substring + title rank), unused `semanticLoading`/`semanticError`.
  - `resolved` = passthrough of `HELP_CONTENT` (Phase-1 posture; no override layer) ([`stores/help.ts:131-132`](../../frontend/src/stores/help.ts#L131)).
  - Ask: `askThread[AskTurn]`, `isStreaming`, `askEnabled` (+`setAskEnabled`), `startAsk`/`abortAsk`/`clearAskThread`. `startAsk` rejects when a turn is in flight or question < 2 chars; creates an `AbortController`, calls `askHelp`, mutates the matching turn on resolve/error ([`stores/help.ts:149-219`](../../frontend/src/stores/help.ts#L149)).
- **HelpPanel local state**: `activeTab`, debounced `query`, `faqArticles`/`faqLoading`/`faqLoaded`. FAQ cache invalidates when `auth.email` changes ([`HelpPanel.vue:128-134`](../../frontend/src/components/help/HelpPanel.vue#L128)).
- **HelpEditor local state**: `articles[]`, filters, dialog open flags, `coverageRef` (calls child `refresh()` after saves/archives) ([`HelpEditor.vue:38-130`](../../frontend/src/views/admin/HelpEditor.vue#L38)).

## Validation

- Pydantic models enforce all create/update/ask/reorder/query constraints server-side (see Product Spec → Validation Rules; [`app/api/help.py:64-343`, `374-377`, `790-791`](../../app/api/help.py#L64)).
- Audience is constrained to `users|admin` by regex at the schema and query layers ([`app/api/help.py:311`, `327`, `375`](../../app/api/help.py#L311)).
- CC-Rounds validation (`compute_compliance`) gates `bulk-publish` and is mirrored client-side for the live meter ([`app/utils/help_compliance.py:79-138`](../../app/utils/help_compliance.py#L79), [`HelpComplianceMeter.vue:18-27`](../../frontend/src/components/help/HelpComplianceMeter.vue#L18)). Threshold drift between Python and TS is pinned by `tests/test_help_compliance.py` per the module header ([`app/utils/help_compliance.py:5-8`](../../app/utils/help_compliance.py#L5)) — test existence **NOT VERIFIED IN CODE** (not opened in this review).
- The FAQ-corpus generator does strict `isinstance` validation on the LLM JSON (rejects non-string title/summary, too-few steps, out-of-range summary length, and invalid related ids) ([`app/tasks/help_tasks.py:644-693`](../../app/tasks/help_tasks.py#L644)).

## Security

- **AuthN**: every endpoint takes `CurrentUser` (JWT) ([`app/api/help.py:50`](../../app/api/help.py#L50)). No anonymous access, including read endpoints.
- **AuthZ**: `require_admin(user)` on all writes/admin reads — currently the single hardcoded `LEGACY_ADMIN_EMAIL` email check ([`app/security/roles.py:62-117`](../../app/security/roles.py#L62)). `auth_users.role` (migration 045) is NOT consulted; the role helper is scaffold-only and unwired ([`app/security/roles.py:11-19`](../../app/security/roles.py#L11)).
- **Audience masking** is enforced in SQL for non-admins on list/get/search (defense in depth beyond the gate) ([`app/api/help.py:388-390`, `445-448`, `799-801`](../../app/api/help.py#L388)).
- **SQL injection**: all queries use bind params; the FAQ generator's literal/regex blacklist (`_DEVSPEAK_BLACKLIST`/`_DEVSPEAK_REGEXES`) is a content-quality guard against LLM leaking dev terms into user-facing text, not a SQL guard ([`app/tasks/help_tasks.py:465-514`](../../app/tasks/help_tasks.py#L465)).
- **LLM trust boundary**: the Ask AI system prompt restricts the model to the provided articles and demands strict JSON; output is parsed with a fence-tolerant parser and falls back to extractive on any failure ([`app/api/help.py:202-228`](../../app/api/help.py#L202)).
- **Rate limit** guards LLM cost surface, soft cap only ([`app/api/help.py:114-135`](../../app/api/help.py#L114)).
- **Client-side guard** for `/admin/help` is cosmetic; server is authoritative ([`router/index.ts:63-66`](../../frontend/src/router/index.ts#L63)).

## Permissions

See Security + the Product Spec Permissions section. Summary of effective gates:
- JWT presence — all 17 endpoints.
- `require_admin` (email gate) — POST/PATCH articles, archive, reorder, versions list/get, coverage, all `/admin/*` ([`app/api/help.py:461`, `529`, `632`, `683`, `713`, `733`, `751`, `832`, `921-947`](../../app/api/help.py#L461)).
- SQL audience masking — `GET /articles`, `GET /articles/{id}`, `GET /search` for non-admins.
- Client route guard `meta.adminOnly` + `useIsAdmin` — UX only.

No editor/reviewer/role-tier authorization exists in this module.

## Integrations

| Integration | Use | Evidence |
|---|---|---|
| Gemini (`call_gemini_text`) | Ask AI synthesis; all 4 bulk tasks | [`app/api/help.py:200-211`](../../app/api/help.py#L200), [`app/tasks/help_tasks.py:149-156`](../../app/tasks/help_tasks.py#L149) |
| Redis | Ask rate-limit counter; per-article + per-task idempotency keys | [`app/api/help.py:124-132`](../../app/api/help.py#L124), [`app/tasks/help_tasks.py:79-89`](../../app/tasks/help_tasks.py#L79) |
| Celery (`celery_app.send_task`) | Enqueue bulk tasks (returns `task_id`) | [`app/api/help.py:900-913`](../../app/api/help.py#L900) |
| Postgres (asyncpg async; sync engine in tasks) | help_articles / versions / audit_events | [`app/api/help.py:53`](../../app/api/help.py#L53), [`app/tasks/help_tasks.py:64-68`](../../app/tasks/help_tasks.py#L64) |
| `/v1/version` | Ships `help_ask_ai_enabled` to gate the Ask tab | [`app/main.py:183`](../../app/main.py#L183) |

## Background Jobs

All inherit `RoundsTask` (retries with backoff), use Redis idempotency, snapshot prior state before mutating, and emit an `audit_events` row on success.

1. **`fix_help_summaries_task`** (`rounds.tasks.help.fix_summaries`, max_retries=2) — for every article failing `summaryOk`, ask Gemini (max 512 tokens) to rewrite the summary into the FAQ/Help target range; save as draft (`is_published=FALSE`), bump version, snapshot prior, audit. Idempotency key `rounds:help:task:fix_summaries:{id}` (24h). Returns `{rewritten, skipped, failed, article_ids}` ([`app/tasks/help_tasks.py:182-279`](../../app/tasks/help_tasks.py#L182)).
2. **`expand_help_steps_task`** (`rounds.tasks.help.expand_steps`) — non-FAQ articles below `HELP_MIN_STEPS=3`; draft additional steps via Gemini (max 1024), append, draft+version+snapshot+audit ([`app/tasks/help_tasks.py:287-410`](../../app/tasks/help_tasks.py#L287)).
3. **`expand_faq_steps_task`** (`rounds.tasks.help.expand_faqs`) — same for FAQ-category articles below `FAQ_MIN_STEPS=2` ([`app/tasks/help_tasks.py:418-421`](../../app/tasks/help_tasks.py#L418)).
4. **`generate_faq_corpus_task`** (`rounds.tasks.help.generate_faq_corpus`, max_retries=1) — one-time seed: for each of 12 routes in `_FAQ_GENERATOR_ROUTES`, draft a FAQ article, validate shape + CC-Rounds FAQ thresholds + dev-speak blacklist, insert as draft with slug `faq-ai-{page_key}` (`ON CONFLICT DO NOTHING`). Task-level Redis guard `rounds:help:task:generate_faq_corpus:global` (24h via `_idem_seen`) short-circuits concurrent runs. Re-raises `OperationalError`/`DisconnectionError` to Celery retry. Returns `{created, skipped_existing, devspeak_rejected, failed, article_ids}` ([`app/tasks/help_tasks.py:517-777`](../../app/tasks/help_tasks.py#L517)).

Audit rows from all four: `INSERT INTO audit_events (session_id, actor_email, kind, summary, details) VALUES (NULL, 'ai:{task}', 'help.ai_rewrite', ...)` ([`app/tasks/help_tasks.py:129-146`](../../app/tasks/help_tasks.py#L129)).

`POST /admin/bulk-publish` runs **inline** (not Celery) — iterate drafts, `compute_compliance`, publish only `allPass`, commit once if any published ([`app/api/help.py:829-894`](../../app/api/help.py#L829)).

## Error Handling

- **Ask path**: 404 (disabled) / 400 (empty) / 429 (`HELP_ASK_RATE_LIMIT`) / 200 with extractive fallback on Gemini failure ([`app/api/help.py:174-228`](../../app/api/help.py#L174)). Frontend maps statuses to codes ([`stores/help.ts:65-87`](../../frontend/src/stores/help.ts#L65)).
- **CRUD**: 409 `SLUG_CONFLICT`, 503 `TABLE_NOT_MIGRATED`, 404 `NOT_FOUND`, 500 `INTERNAL` (always rollback before raising) ([`app/api/help.py:500-514`, `611-616`](../../app/api/help.py#L500)).
- **List/search resilience**: a missing table returns an empty list rather than 500 ([`app/api/help.py:413-417`, `815-819`](../../app/api/help.py#L413)).
- **Enqueue**: broker failure → 503 `QUEUE_UNAVAILABLE` ([`app/api/help.py:908-913`](../../app/api/help.py#L908)).
- **Tasks**: per-article failures are caught, counted (`failed`), and the loop continues; DB connection errors in the FAQ generator bubble to Celery retry ([`app/tasks/help_tasks.py:272-274`, `756-766`](../../app/tasks/help_tasks.py#L272)).
- **Redis down**: rate-limit allows the request; task idempotency proceeds (logged warnings) ([`app/api/help.py:133-135`](../../app/api/help.py#L133), [`app/tasks/help_tasks.py:87-89`](../../app/tasks/help_tasks.py#L87)).
- **Frontend**: dialogs surface errors via `toast.push(..., {tone:'error'})` and keep the dialog open on failure ([`HelpArticleEditorDialog`](../../frontend/src/components/help/HelpArticleEditorDialog.vue), [`HelpVersionHistoryDialog.vue:62-64`](../../frontend/src/components/help/HelpVersionHistoryDialog.vue#L62)).

## Performance Considerations

- **Ask retrieval** is O(n) over the in-process corpus (~80 entries) — trivial; no DB hit ([`app/api/help.py:97-108`](../../app/api/help.py#L97)).
- **LLM cost bounding**: Ask caps output at 1024 tokens; summary rewrites at 512; the FAQ-generator's task-level Redis guard prevents a double-clicked button from making 12 duplicate Gemini calls ([`app/tasks/help_tasks.py:548-561`](../../app/tasks/help_tasks.py#L548)).
- **List queries** are indexed on `is_published`, `audience`, `content_domain`, and `(content_domain, display_order)`; `feature_tag` filters use a GIN index on `feature_tags` with `@>` containment ([`app/api/help.py:395-397`](../../app/api/help.py#L395), [`migrations/053_help_articles.sql:41-51`](../../migrations/053_help_articles.sql#L41)). `limit` capped at 500.
- **Search** uses `LOWER(...) LIKE '%q%'` — a leading-wildcard scan, not index-assisted; bounded by `limit` ≤ 50 ([`app/api/help.py:797-813`](../../app/api/help.py#L797)).
- **FAQ tab** fetches once per panel session and caches (`faqLoaded`), invalidated on user change ([`HelpPanel.vue:90-134`](../../frontend/src/components/help/HelpPanel.vue#L90)).
- **`HelpRelatedLinks`** fetches related articles individually via `Promise.all`, capped at 5 ([`HelpRelatedLinks.vue:33-37`](../../frontend/src/components/help/HelpRelatedLinks.vue#L33)).
- **PATCH** locks the row (`SELECT ... FOR UPDATE`) before snapshot+update to keep versioning consistent under concurrency ([`app/api/help.py:537`](../../app/api/help.py#L537)).

## Source Verification
- **Files Used:** app/api/help.py, app/tasks/help_tasks.py, app/data/help_content.py, app/utils/help_compliance.py, app/security/roles.py, app/config.py, app/main.py, app/engines/llm_client.py, migrations/053_help_articles.sql, migrations/054_help_article_versions.sql, migrations/055_help_articles_seed.sql, migrations/056_help_articles_steps_content.sql, frontend/src/stores/help.ts, frontend/src/services/helpApi.ts, frontend/src/services/helpArticlesApi.ts, frontend/src/router/index.ts, frontend/src/composables/useIsAdmin.ts, frontend/src/constants/help-content.ts, frontend/src/views/admin/HelpEditor.vue, frontend/src/components/help/*, frontend/src/components/AppHeader.vue
- **Components Used:** HelpPanel, HelpAskComposer, HelpItem, HelpFaqAccordion, HelpStepList, HelpRelatedLinks, HelpEditor, HelpAdminToolbar, HelpCoverageReport, HelpArticleEditorDialog, HelpVersionHistoryDialog, HelpComplianceMeter, AppHeader
- **APIs Used:** POST /v1/help/ask; GET/POST /v1/help/articles; GET/PATCH /v1/help/articles/{id}; PATCH /v1/help/articles/{id}/archive; PATCH /v1/help/articles/reorder; GET /v1/help/articles/{id}/versions[/{version}]; GET /v1/help/coverage; GET /v1/help/search; POST /v1/help/admin/{bulk-publish,fix-summaries,expand-steps,expand-faqs,generate-faq-corpus}; GET /v1/version
- **Database Tables Used:** help_articles, help_article_versions, audit_events
- **Permission Logic Used:** JWT (CurrentUser) + LEGACY_ADMIN_EMAIL gate (require_admin) + SQL audience masking + client adminOnly guard
- **Confidence Score:** High — every claim is line-traced; the one unopened artifact (test file) is tagged.
- **Evidence Links:** [app/api/help.py:58](../../app/api/help.py#L58), [app/tasks/help_tasks.py:517](../../app/tasks/help_tasks.py#L517), [migrations/054_help_article_versions.sql:22](../../migrations/054_help_article_versions.sql#L22), [app/utils/help_compliance.py:79](../../app/utils/help_compliance.py#L79), [frontend/src/stores/help.ts:149](../../frontend/src/stores/help.ts#L149)
