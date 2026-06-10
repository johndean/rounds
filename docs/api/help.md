# API Reference — `help` router (`/v1/help`)

Help Center backend: a grounded Ask-AI Q&A endpoint over an in-process corpus, plus a help-article CMS (CRUD, version history, coverage, search) and admin bulk/AI-trigger actions.

- **Source file:** [`app/api/help.py`](../../app/api/help.py)
- **Router prefix / tag:** `prefix="/v1/help"`, `tags=["help"]` — [app/api/help.py:58](../../app/api/help.py#L58)

## Authentication & authorization model (read this first)

Every endpoint depends on `CurrentUser` = `Annotated[User, Depends(get_current_user)]` ([app/auth.py:208](../../app/auth.py#L208)). `get_current_user` validates the JWT bearer token and confirms the email is an active user; it does **not** load a role onto the `User` object ([app/auth.py:172](../../app/auth.py#L172), [app/auth.py:37](../../app/auth.py#L37)). So baseline auth = a valid JWT.

Write/admin endpoints call `require_admin(user)` ([app/security/roles.py:95](../../app/security/roles.py#L95)). With no `role=` argument passed, this resolves to `is_admin`'s legacy branch: a **case-sensitive exact-string compare of `user.email` against `LEGACY_ADMIN_EMAIL = "johndean@vin.com"`** ([app/security/roles.py:62](../../app/security/roles.py#L62), [app/security/roles.py:54](../../app/security/roles.py#L54)). Failure → `403 {"code":"ADMIN_ONLY","message":"admin only"}`.

The read endpoints (`GET /articles`, `GET /articles/{id}`, `GET /search`) add a second layer: an **audience filter**. `_is_user_admin(user)` calls the same `is_admin` helper ([help.py:357](../../app/api/help.py#L357)); for non-admins the SQL restricts rows to `is_published = TRUE AND audience = 'users'` ([help.py:349](../../app/api/help.py#L349)). This is the same `johndean@vin.com` gate, used as a content filter rather than a hard 403.

> The module header at [help.py:236](../../app/api/help.py#L236) states this explicitly: "BR-001 — single LEGACY_ADMIN_EMAIL gate until auth_users.role lands." The `role` field accepted on `POST /ask` is a retrieval-bias hint only — it is NOT an authorization input.

Authorization legend:
- **JWT-only** — any authenticated user.
- **JWT + audience filter** — JWT required; non-admins see only published `audience='users'` rows.
- **JWT + LEGACY_ADMIN_EMAIL gate** — `require_admin(user)`; effectively only `johndean@vin.com`.

---

## Pydantic models

| Model | Fields | Source |
|---|---|---|
| `HelpAskRequest` | `question: str` (1–2000), `page_key: str\|None` (≤64), `role: str\|None` (≤16) | [help.py:64](../../app/api/help.py#L64) |
| `HelpAskSource` | `id: str`, `title: str`, `summary: str` | [help.py:71](../../app/api/help.py#L71) |
| `HelpAskResponse` | `answer: str`, `sources: list[HelpAskSource]`, `used_llm: bool` | [help.py:77](../../app/api/help.py#L77) |
| `HelpStep` | `title: str` (1–200), `body: str` (1–4000) | [help.py:300](../../app/api/help.py#L300) |
| `HelpArticleCreate` | `title` (1–200), `summary` (≤4000, default ""), `category` (≤64, default "general"), `audience` (regex `^(users\|admin)$`, default "users"), `feature_tags: list[str]` (≤20), `steps: list[HelpStep]` (≤20), `related_article_ids: list[UUID]` (≤20), `display_order: int≥0`, `is_published: bool=False`, `content_domain` (≤64, default "general"), `workflow_slug: str\|None` (≤64), `slug: str\|None` (≤64) | [help.py:306](../../app/api/help.py#L306) |
| `HelpArticleUpdate` | all of the above except `slug`, every field Optional (PATCH) | [help.py:322](../../app/api/help.py#L322) |
| `HelpReorderItem` | `id: UUID`, `display_order: int≥0` | [help.py:337](../../app/api/help.py#L337) |
| `HelpReorderRequest` | `items: list[HelpReorderItem]` (1–200) | [help.py:342](../../app/api/help.py#L342) |

Article response serializer `_row_to_article` ([help.py:249](../../app/api/help.py#L249)) → `{id, slug, title, summary, category, audience, feature_tags, steps, related_article_ids, display_order, is_published, content_domain, workflow_slug, version, last_edited_by, created_at, updated_at}`. Version serializer `_row_to_version` ([help.py:274](../../app/api/help.py#L274)) → `{id, article_id, version, snapshot, edited_by, edited_at}`.

---

## Endpoints

### 1. `POST /v1/help/ask` — grounded Ask-AI Q&A
- **Decorator:** [help.py:164](../../app/api/help.py#L164) — `@router.post("/ask", response_model=HelpAskResponse)`
- **Purpose:** Retrieve top-N articles from the in-process corpus (`flatten_corpus()` over `app/data/help_content.py`), synthesize a grounded answer via Gemini, and degrade to an extractive summary of the top hits if Gemini is unavailable/mis-configured/fails JSON parsing. The enabled path never raises 5xx for an LLM failure.
- **Authentication:** JWT (`user: CurrentUser`). Note: this handler takes only `user` — it does NOT take `DbSession`; it touches no database.
- **Authorization:** JWT-only (no `require_admin`).
- **Request Schema:** `HelpAskRequest` `{question, page_key?, role?}`. `role` biases retrieval scoring only ([help.py:86](../../app/api/help.py#L86)); it is not an auth field.
- **Response Schema:** `HelpAskResponse` `{answer: str, sources: [{id,title,summary}], used_llm: bool}`.
- **Validation Rules:**
  - Feature flag: if `settings.HELP_ASK_AI_ENABLED` is false → **404 "Ask AI is not enabled"** ([help.py:174](../../app/api/help.py#L174)).
  - `question` min_length=1 (Pydantic) → 422; an all-whitespace question also → **400 "question is required"** after `.strip()` ([help.py:178](../../app/api/help.py#L178)).
  - Per-user hourly cap via Redis (`HELP_ASK_AI_RATE_LIMIT_PER_HOUR`); over cap → **429 `{"code":"HELP_ASK_RATE_LIMIT","retryable":true}`** ([help.py:186](../../app/api/help.py#L186)). Redis errors soft-fail (request allowed) ([help.py:133](../../app/api/help.py#L133)).
  - LLM path only runs when `settings.GEMINI_API_KEY` is set AND there are hits; `max_output_tokens` hard cap = 1024 ([help.py:211](../../app/api/help.py#L211)).
- **Errors:** 404 (feature off); 400 (empty question); 429 (rate limit); 401. Never 5xx for a Gemini failure (degrades to extractive).
- **Example:** `POST /v1/help/ask` body `{"question":"How do I merge two segments?","page_key":"editor"}` → `{"answer":"...[1]...","sources":[{"id":"...","title":"...","summary":"..."}],"used_llm":true}`.
- **Related Screens:** Help Center → Ask AI.
- **Related Tables:** none (corpus is the in-process `app/data/help_content.py`; no DB read/write).

### 2. `GET /v1/help/articles` — list articles
- **Decorator:** [help.py:370](../../app/api/help.py#L370) — `@router.get("/articles")`
- **Purpose:** List help articles ordered by `content_domain, display_order, created_at`. Audience-filtered for non-admins.
- **Authentication:** JWT (`user`).
- **Authorization:** **JWT + audience filter.** Admins see all (incl. drafts) and may pass `audience` to narrow; non-admins are forced to `is_published = TRUE AND audience = 'users'` ([help.py:388](../../app/api/help.py#L388)).
- **Request Schema:** query `feature_tag: str|None` (≤64), `audience: str|None` (regex `^(users|admin)$`), `content_domain: str|None` (≤64), `limit: int` (default 200, 1–500).
- **Response Schema:** `list[dict]` (`_row_to_article`).
- **Validation Rules:** `feature_tag` filter uses JSONB containment (`feature_tags @> [tag]`).
- **Errors:** 401; 422 (bad query). If the `help_articles` table is missing (pre-migration 053) the query failure is caught and an **empty list** is returned ([help.py:415](../../app/api/help.py#L415)).
- **Related Screens:** Help Center index; admin article list.
- **Related Tables:** `help_articles`.

### 3. `GET /v1/help/articles/{article_id}` — get one article
- **Decorator:** [help.py:425](../../app/api/help.py#L425) — `@router.get("/articles/{article_id}")`
- **Purpose:** Fetch a single article by id.
- **Authentication:** JWT (`user`).
- **Authorization:** **JWT + audience filter.** Non-admins requesting an unpublished/admin-only row get 404 (defense-in-depth, not 403) ([help.py:445](../../app/api/help.py#L445)).
- **Request Schema:** path `article_id: UUID`.
- **Response Schema:** `dict` (`_row_to_article`).
- **Validation Rules:** missing row → **404 `{"code":"NOT_FOUND"}`** ([help.py:442](../../app/api/help.py#L442)); audience-blocked → same 404.
- **Errors:** 404; 401; 422 (bad UUID).
- **Related Screens:** Help Center → article detail.
- **Related Tables:** `help_articles`.

### 4. `POST /v1/help/articles` — create article
- **Decorator:** [help.py:455](../../app/api/help.py#L455) — `@router.post("/articles", status_code=201)`
- **Purpose:** Create a help article (version starts at 1). Slug taken from `payload.slug` if given, else `_slugify(title)` ([help.py:288](../../app/api/help.py#L288)).
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([help.py:461](../../app/api/help.py#L461)).
- **Request Schema:** `HelpArticleCreate`.
- **Response Schema:** `dict` (`_row_to_article`), 201.
- **Validation Rules:** `audience` Pydantic pattern `^(users|admin)$`; list fields capped at 20 items.
- **Errors:** **409 `{"code":"SLUG_CONFLICT"}`** on `help_articles_slug_key`/duplicate ([help.py:503](../../app/api/help.py#L503)); **503 `{"code":"TABLE_NOT_MIGRATED"}`** if the table doesn't exist ([help.py:508](../../app/api/help.py#L508)); **500 `{"code":"INTERNAL"}`** otherwise ([help.py:513](../../app/api/help.py#L513)); 403; 401; 422.
- **Related Screens:** Help admin → new article.
- **Related Tables:** `help_articles`.

### 5. `PATCH /v1/help/articles/{article_id}` — update article (versioned)
- **Decorator:** [help.py:522](../../app/api/help.py#L522) — `@router.patch("/articles/{article_id}")`
- **Purpose:** Partial update. Snapshots the PRIOR row into `help_article_versions` first (under `FOR UPDATE`), then applies the patch and bumps `version`, sets `last_edited_by`.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([help.py:529](../../app/api/help.py#L529)).
- **Request Schema:** `HelpArticleUpdate` (all fields optional).
- **Response Schema:** `dict` (`_row_to_article`). An empty patch is a no-op that returns the current row ([help.py:586](../../app/api/help.py#L586)).
- **Validation Rules:** only non-None fields are written; `audience` pattern-validated by Pydantic.
- **Errors:** missing row → **404 `{"code":"NOT_FOUND"}`** ([help.py:543](../../app/api/help.py#L543)); **500 `{"code":"INTERNAL"}`** on DB failure (rolled back) ([help.py:616](../../app/api/help.py#L616)); 403; 401; 422.
- **Related Screens:** Help admin → edit article; version history feeds [versions endpoints].
- **Related Tables:** `help_articles`, `help_article_versions`.

### 6. `PATCH /v1/help/articles/{article_id}/archive` — soft-archive
- **Decorator:** [help.py:624](../../app/api/help.py#L624) — `@router.patch("/articles/{article_id}/archive")`
- **Purpose:** Soft-archive by setting `is_published = FALSE` (no separate `archived` flag). Snapshots the prior row into versions and bumps `version`.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([help.py:632](../../app/api/help.py#L632)).
- **Request Schema:** path `article_id: UUID`.
- **Response Schema:** `dict` (`_row_to_article`).
- **Validation Rules:** missing row → **404 `{"code":"NOT_FOUND"}`** ([help.py:639](../../app/api/help.py#L639)).
- **Errors:** 404; **500 `{"code":"INTERNAL"}`** (rolled back) ([help.py:666](../../app/api/help.py#L666)); 403; 401; 422.
- **Related Screens:** Help admin → archive.
- **Related Tables:** `help_articles`, `help_article_versions`.

### 7. `PATCH /v1/help/articles/reorder` — bulk reorder
- **Decorator:** [help.py:674](../../app/api/help.py#L674) — `@router.patch("/articles/reorder")`
- **Purpose:** Bulk-set `display_order` across many articles. Does NOT snapshot (reorder is cosmetic).
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([help.py:683](../../app/api/help.py#L683)).
- **Request Schema:** `HelpReorderRequest` `{items: [{id, display_order}, ...]}` (1–200 items).
- **Response Schema:** `dict` `{"updated": <count>}`.
- **Validation Rules:** Pydantic enforces 1–200 items, `display_order ≥ 0`.
- **Errors:** **500 `{"code":"INTERNAL"}`** (rolled back) ([help.py:699](../../app/api/help.py#L699)); 403; 401; 422.
- **Related Screens:** Help admin → drag-reorder.
- **Related Tables:** `help_articles`.

> Routing note: this `/articles/reorder` path is registered ([help.py:674](../../app/api/help.py#L674)) after the parameterized `PATCH /articles/{article_id}` ([help.py:522](../../app/api/help.py#L522)). FastAPI matches routes in declaration order, so a PATCH to `/articles/reorder` would match the `{article_id}` route first and fail UUID coercion (422). NOT VERIFIED IN CODE whether a workaround exists elsewhere (e.g. router include order); flagged as a discrepancy to confirm.

### 8. `GET /v1/help/articles/{article_id}/versions` — list versions
- **Decorator:** [help.py:707](../../app/api/help.py#L707) — `@router.get("/articles/{article_id}/versions")`
- **Purpose:** List all snapshot versions for an article, newest first.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([help.py:713](../../app/api/help.py#L713)).
- **Response Schema:** `list[dict]` (`_row_to_version`).
- **Errors:** 403; 401; 422.
- **Related Screens:** Help admin → version history.
- **Related Tables:** `help_article_versions`.

### 9. `GET /v1/help/articles/{article_id}/versions/{version}` — get one version
- **Decorator:** [help.py:726](../../app/api/help.py#L726) — `@router.get("/articles/{article_id}/versions/{version}")`
- **Purpose:** Fetch a single snapshot by `(article_id, version)`.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([help.py:733](../../app/api/help.py#L733)).
- **Request Schema:** path `article_id: UUID`, `version: int`.
- **Response Schema:** `dict` (`_row_to_version`).
- **Validation Rules:** missing → **404 `{"code":"NOT_FOUND"}`** ([help.py:743](../../app/api/help.py#L743)).
- **Errors:** 404; 403; 401; 422.
- **Related Screens:** Help admin → version detail / diff.
- **Related Tables:** `help_article_versions`.

### 10. `GET /v1/help/coverage` — coverage report
- **Decorator:** [help.py:750](../../app/api/help.py#L750) — `@router.get("/coverage")`
- **Purpose:** Count of published articles per `content_domain`, plus total published/draft counts. The frontend flags domains with <2 published articles.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([help.py:756](../../app/api/help.py#L756)).
- **Response Schema:** `dict` `{by_domain: {<domain>: n}, total_published: int, total_drafts: int}`.
- **Errors:** 403; 401.
- **Related Screens:** `HelpCoverageReport.vue` (named in source comment, [help.py:755](../../app/api/help.py#L755)).
- **Related Tables:** `help_articles`.

### 11. `GET /v1/help/search` — substring search
- **Decorator:** [help.py:786](../../app/api/help.py#L786) — `@router.get("/search")`
- **Purpose:** Server-side substring search across title+summary; title hits rank above summary-only hits. Audience-filtered for non-admins.
- **Authentication:** JWT (`user`).
- **Authorization:** **JWT + audience filter** (non-admins restricted to published `users` rows, [help.py:799](../../app/api/help.py#L799)).
- **Request Schema:** query `q: str` (2–200, required), `limit: int` (default 20, 1–50).
- **Response Schema:** `list[dict]` (`_row_to_article`).
- **Validation Rules:** `q` min_length=2 (Pydantic) → 422.
- **Errors:** 401; 422. Table-missing failure is caught → **empty list** ([help.py:817](../../app/api/help.py#L817)).
- **Related Screens:** Help Center → search box.
- **Related Tables:** `help_articles`.

### 12. `POST /v1/help/admin/bulk-publish` — compliance-gated bulk publish
- **Decorator:** [help.py:829](../../app/api/help.py#L829) — `@router.post("/admin/bulk-publish")`
- **Purpose:** Inline (not Celery) — iterate every draft, run `compute_compliance` (`app/utils/help_compliance.py`), publish only rows where `allPass` is True; return counts + a skipped list with per-row CC-Rounds failure reasons.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([help.py:834](../../app/api/help.py#L834)).
- **Request Schema:** none.
- **Response Schema:** `dict` `{total_attempted, published, published_ids, skipped: [{id, title, reason, ...cc fields}]}`.
- **Validation Rules:** publish gated on `cc["allPass"]`.
- **Errors:** **500 `{"code":"INTERNAL"}`** if the commit fails (rolled back) ([help.py:887](../../app/api/help.py#L887)); 403; 401.
- **Related Screens:** Help admin → compliance bulk publish.
- **Related Tables:** `help_articles`.

### 13. `POST /v1/help/admin/fix-summaries` — enqueue fix-summaries task
- **Decorator:** [help.py:916](../../app/api/help.py#L916) — `@router.post("/admin/fix-summaries")`
- **Purpose:** Enqueue Celery task `rounds.tasks.help.fix_summaries` (fire-and-forget). Handler takes only `user` — no `DbSession`.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([help.py:921](../../app/api/help.py#L921)).
- **Response Schema:** `dict` `{task_id, task, enqueued: true}` (via `_enqueue`, [help.py:900](../../app/api/help.py#L900)).
- **Errors:** **503 `{"code":"QUEUE_UNAVAILABLE"}`** if the broker is unreachable ([help.py:910](../../app/api/help.py#L910)); 403; 401.
- **Related Screens:** Help admin → AI actions.
- **Related Tables:** none directly (the Celery task touches `help_articles`).

### 14. `POST /v1/help/admin/expand-steps` — enqueue expand-steps task
- **Decorator:** [help.py:925](../../app/api/help.py#L925) — `@router.post("/admin/expand-steps")`
- **Purpose:** Enqueue Celery task `rounds.tasks.help.expand_steps`.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([help.py:927](../../app/api/help.py#L927)).
- **Response Schema:** `dict` `{task_id, task, enqueued: true}`.
- **Errors:** 503 `QUEUE_UNAVAILABLE`; 403; 401.
- **Related Screens:** Help admin → AI actions.
- **Related Tables:** none directly.

### 15. `POST /v1/help/admin/expand-faqs` — enqueue expand-faqs task
- **Decorator:** [help.py:931](../../app/api/help.py#L931) — `@router.post("/admin/expand-faqs")`
- **Purpose:** Enqueue Celery task `rounds.tasks.help.expand_faqs`.
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([help.py:933](../../app/api/help.py#L933)).
- **Response Schema:** `dict` `{task_id, task, enqueued: true}`.
- **Errors:** 503 `QUEUE_UNAVAILABLE`; 403; 401.
- **Related Screens:** Help admin → AI actions.
- **Related Tables:** none directly.

### 16. `POST /v1/help/admin/generate-faq-corpus` — enqueue FAQ-corpus seed task
- **Decorator:** [help.py:937](../../app/api/help.py#L937) — `@router.post("/admin/generate-faq-corpus")`
- **Purpose:** Enqueue Celery task `rounds.tasks.help.generate_faq_corpus` — drafts one FAQ article per registered route, validates against CC-Rounds + a dev-speak blacklist, inserts each as a draft. Re-invocation is safe (deterministic `faq-ai-{page_key}` slug with `ON CONFLICT DO NOTHING`, per docstring).
- **Authentication:** JWT.
- **Authorization:** **JWT + LEGACY_ADMIN_EMAIL gate** ([help.py:947](../../app/api/help.py#L947)).
- **Response Schema:** `dict` `{task_id, task, enqueued: true}`.
- **Errors:** 503 `QUEUE_UNAVAILABLE`; 403; 401.
- **Related Screens:** Help admin → AI actions (seed FAQ corpus).
- **Related Tables:** none directly (the task inserts into `help_articles`).

---

## Notes / discrepancies
- `POST /ask` and the four admin Celery-trigger endpoints (13–16) do NOT inject `DbSession`; they touch no database directly.
- IMPLEMENTATION NOT FOUND in this router: the Celery task bodies (`rounds.tasks.help.*`) and `compute_compliance` are referenced but defined elsewhere (`app/tasks/...`, `app/utils/help_compliance.py`) — not opened/verified here.
- See [help.py:7](../../app/api/help.py#L7): "Phase 2 ships the Ask AI route only … Phase 3 ships the rest" — both phases are present in the current file.

## Source Verification
- **Files Used:** `app/api/help.py`, `app/security/roles.py`, `app/auth.py`
- **Components Used:** none (Vue screens `HelpCoverageReport.vue` named only from an in-code comment, not opened/verified here)
- **APIs Used:** none (this IS the API surface); references `app/data/help_content.py` (corpus), `app/engines/llm_client.call_gemini_text`, `app/utils/help_compliance.compute_compliance`, `app/tasks/celery_app` — not opened here
- **Database Tables Used:** `help_articles`, `help_article_versions`
- **Permission Logic Used:** JWT presence (`CurrentUser`) on all routes; `require_admin(user)` → `LEGACY_ADMIN_EMAIL` gate on all write/admin/coverage/version routes; audience filter (`_is_user_admin` → same gate) on `GET /articles`, `GET /articles/{id}`, `GET /search`
- **Confidence Score:** High — every endpoint, decorator line, model, error code, and gate read directly from source. The reorder route-ordering item is flagged as NOT VERIFIED IN CODE.
- **Evidence Links:** [help.py:58](../../app/api/help.py#L58) (router), [help.py:164](../../app/api/help.py#L164) (POST /ask), [help.py:461](../../app/api/help.py#L461) (require_admin example), [help.py:349](../../app/api/help.py#L349) (audience filter), [roles.py:54](../../app/security/roles.py#L54) (LEGACY_ADMIN_EMAIL)
