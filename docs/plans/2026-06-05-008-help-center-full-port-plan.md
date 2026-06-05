# rounds.vin Help Center — Full CMS Port Plan (MIC-Sourced) — SUPERSEDED

> **⚠ SUPERSEDED 2026-06-05.** This plan mirrored the MIC Help Center. The user subsequently provided pixel-reference screenshots of the **po.vin** Help Center and required a pixel-perfect port with an inline-under-banner layout (not a teleport overlay). The X1–X8 feature decisions captured here still apply, but the visual + architectural source of truth has changed.
>
> **Active plan:** [`2026-06-05-009-help-center-povin-pixel-port-plan.md`](./2026-06-05-009-help-center-povin-pixel-port-plan.md)
>
> This file is retained for historical context only. Do not implement from it.

---

# rounds.vin Help Center — Full CMS Port Plan (MIC-Sourced)

- **Date:** 2026-06-05
- **Author:** johndean@vin.com (+ Claude Opus 4.7)
- **Predecessor:** audit synthesis in session transcript (workflow `waqecj0sd`, 2026-06-05).
- **Source of truth:** MIC repository at `C:\Users\JohnDean\Desktop\mic\` — the rounds.vin Help Center has no React-port SSOT, so MIC is the design anchor. Backend patterns, Pydantic shapes, Celery task structure, and frontend component partition are mirrored from MIC unless an explicit deviation is documented in this plan.
- **Scope decisions confirmed by user (2026-06-05):**
  - **X1** Ask AI — **YES**, use MIC's Gemini wiring + shared `GEMINI_API_KEY` (already in Railway env).
  - **X2** Content compliance — **YES**, with **new rounds-specific thresholds** (designed in §6.2).
  - **X3** Bulk AI actions (fix-summaries / expand-steps / expand-faqs) — **YES**.
  - **X4** Version history / audit ledger for help edits — **YES**.
  - **X5** Read-tracking / analytics — **NO** (explicitly declined).
  - **X6** FAQ separate render + AI-generated human-readable enterprise-standard corpus — **YES**.
  - **X7** Cross-linked articles — **YES**.
  - **X8** Numbered JSONB steps — **YES**.

---

## 1. Why this plan exists

The audit (workflow `waqecj0sd`) established that rounds.vin's Help Center is a 517-LOC build-time markdown viewer with 20 inventoried dev-speak instances in user-facing copy, no backend, no admin surface, and a non-functional "Ask AI" placeholder. The MIC source at `C:\Users\JohnDean\Desktop\mic\` ships a full CMS for the same surface — 13 Vue components + 8 backend files + 53 seeded articles in product voice. This plan ports the MIC implementation to rounds with the seven decisions the user made on Phase X items.

**What ships:** product-voice content rewrite (immediate) → structural drawer fixes → CMS skeleton with version-history + cross-links + numbered steps → Ask AI with Gemini RAG → compliance + bulk AI tasks → AI-generated FAQ corpus.

**What does NOT ship:** read-tracking / analytics (declined by user at X5).

---

## 2. Six-phase rollout

| Phase | Deliverable | Effort | Risk | Predecessor |
|---|---|---|---|---|
| A | Content rewrite — strip 20 dev-speak instances | ~1 day | **Zero** | — |
| B | Structural drawer fixes (mobile, search default, "Show all", keyboard shortcut, expanded corpus) | ~2 days | **Low** | A |
| C | Backend CMS skeleton + admin UI + version history + cross-links + numbered steps | ~5–7 days | **Moderate** (new auth-gated routes + new table) | B |
| D | Ask AI with Gemini RAG (mirror MIC `/v1/help/ask`) | ~3–4 days | **Moderate** (cost surface — rate-limit required) | C |
| E | Content compliance scoring (CC-Rounds) + bulk AI Celery tasks | ~4–5 days | **Moderate** (AI rewrites with review gate) | C, D |
| F | AI-generated FAQ corpus (one-time seed) + FAQ accordion render | ~2–3 days | **Low** (admin reviews every AI article before publish) | E |

**Total estimated effort:** 17–22 working days. Each phase is independently shippable + revertible.

---

## 3. Phase A — Content rewrite (~1 day, zero-risk)

Identical to the audit synthesis Tier 1. Edits only `frontend/src/content/help/*.md` (5 files) and 3 lines in `HelpCenterDrawer.vue`. No schema, no new files, no behavior change.

**Acceptance:** `grep -rEn 'text_edit|SpeakerEditPanel|Phase [0-9]|/v1/|browser local|correction ledger|re-enqueue|FastAPI Swagger|VITE_HELP_ASK_AI_ENABLED' frontend/src/content/help/ frontend/src/components/HelpCenterDrawer.vue` returns zero matches.

Single commit. Push both remotes.

---

## 4. Phase B — Structural drawer fixes (~2 days, low-risk)

Identical to the audit synthesis Tier 2. Adds 6 more `.md` files (one per uncovered route), fixes drawer width for mobile, adds empty-search default, adds "Show all" toggle, binds keyboard shortcut, adds friendly Ask-AI placeholder.

**Acceptance:** Playwright spec opens drawer on every route + asserts route-specific content + asserts "Show all" returns full corpus.

Single commit. Push both remotes.

---

## 5. Phase C — Backend CMS skeleton (~5–7 days, moderate-risk)

### 5.1 Migration

**`migrations/053_help_articles.sql`** — mirrors MIC `migrations/007_help_articles.sql` schema with rounds-specific column adjustments:

```sql
CREATE TABLE IF NOT EXISTS help_articles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    summary         TEXT NOT NULL DEFAULT '',
    category        TEXT NOT NULL,                    -- 'general' | 'getting_started' | 'editor' | 'sop' | 'faq:*'
    audience        TEXT NOT NULL DEFAULT 'users',    -- 'users' | 'admin'
    feature_tags    JSONB NOT NULL DEFAULT '[]',      -- ['editor','dashboard',...] — per-page filter
    steps           JSONB NOT NULL DEFAULT '[]',      -- [{title, body}, ...] — X8 numbered steps
    related_article_ids JSONB NOT NULL DEFAULT '[]',  -- X7 cross-links — list of UUID strings
    display_order   INTEGER NOT NULL DEFAULT 0,
    is_published    BOOLEAN NOT NULL DEFAULT FALSE,
    content_domain  TEXT NOT NULL DEFAULT 'general',  -- 'sessions' | 'editor' | 'sop' | 'processing' | etc.
    workflow_slug   TEXT,                              -- optional SOP-specific variant
    version         INTEGER NOT NULL DEFAULT 1,       -- X4 — bumps on every update
    last_edited_by  TEXT NOT NULL DEFAULT '',         -- email or 'ai:fix_summaries' etc.
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_help_articles_published ON help_articles(is_published);
CREATE INDEX IF NOT EXISTS idx_help_articles_content_domain ON help_articles(content_domain);
CREATE INDEX IF NOT EXISTS idx_help_articles_feature_tags ON help_articles USING GIN (feature_tags);
```

**`migrations/054_help_article_versions.sql`** — X4 version history:

```sql
CREATE TABLE IF NOT EXISTS help_article_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id      UUID NOT NULL REFERENCES help_articles(id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    snapshot        JSONB NOT NULL,         -- full article row at this version
    edited_by       TEXT NOT NULL,
    edited_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(article_id, version)
);

CREATE INDEX IF NOT EXISTS idx_help_article_versions_article ON help_article_versions(article_id);
```

A row is appended to `help_article_versions` on every successful PATCH. The frontend version-history dialog reads this table.

### 5.2 Backend (`app/api/help.py`, ~400 LOC)

Mirror MIC's structure, simplified. Endpoints:

| Method + Path | Purpose | Auth |
|---|---|---|
| `GET /v1/help/articles` | List with filters (`?feature_tag=editor&audience=users`) | Any authed user (audience-filtered) |
| `GET /v1/help/articles/{id}` | Single article detail | Any authed user |
| `GET /v1/help/articles/{id}/versions` | Version history list — **X4** | Admin |
| `GET /v1/help/articles/{id}/versions/{n}` | Single version snapshot — **X4** | Admin |
| `POST /v1/help/articles` | Create | Admin |
| `PATCH /v1/help/articles/{id}` | Update (auto-snapshots prior version) | Admin |
| `PATCH /v1/help/articles/{id}/archive` | Set `is_published=false` (no separate archive flag) | Admin |
| `PATCH /v1/help/articles/reorder` | Bulk `display_order` rewrite | Admin |
| `GET /v1/help/coverage` | Domain-count grid for the report panel | Admin |
| `GET /v1/help/search?q=...` | Server-side substring + title-rank | Any authed user |

Admin gate uses existing `require_admin(_user)` from `app/security/roles.py` (`LEGACY_ADMIN_EMAIL` — [BR-001](../BUSINESS_RULES.md#br-001)). Future migration to `auth_users.role` is an independent Phase X.

PATCH handler snapshots the article into `help_article_versions` BEFORE applying changes, bumps `version`, sets `last_edited_by`. Logic in `_snapshot_and_bump(article, editor_email) -> int`.

### 5.3 Pydantic schemas (`app/schemas/help_article.py`, ~100 LOC)

`HelpStep`, `HelpArticleCreate`, `HelpArticleUpdate`, `HelpArticleListItem`, `HelpArticleDetail`, `HelpArticleVersion`, `HelpCoverageResponse`. Mirror MIC `app/schemas/help_article.py`.

### 5.4 Frontend (Vue 3 / Pinia)

**New files:**
- `frontend/src/components/help/HelpAdminToolbar.vue` — `+ New Article` / `Publish All Drafts` / (X3 placeholders for `Fix CC` / `Expand Steps` / `Expand FAQs` — wired in Phase E) / `Coverage Report` toggle.
- `frontend/src/components/help/HelpCoverageReport.vue` — grid of content domains, count, red badge when `< 2`.
- `frontend/src/components/help/HelpArticleList.vue` — admin-mode cards with `Edit` / `Unpublish` / `Archive` per row.
- `frontend/src/components/help/HelpArticleEditorDialog.vue` — create/edit modal with title, summary, category, content_domain, feature_tags multi-select, **steps editor** (X8 — numbered card list with title + body per step), **related articles picker** (X7 — multi-select from article list), audience toggle.
- `frontend/src/components/help/HelpStepList.vue` — read-only numbered render of `steps[]` (X8).
- `frontend/src/components/help/HelpVersionHistoryDialog.vue` — list versions, click to view snapshot (X4).
- `frontend/src/components/help/HelpRelatedLinks.vue` — render `related_article_ids[]` as links inside article detail (X7).
- `frontend/src/stores/useHelpStore.js` → migrate the existing `helpCenter.ts` to fetch from `/v1/help/*` instead of `import.meta.glob`. Keep the `.md` fallback path active during cutover.
- `frontend/src/api/help.ts` — typed wrappers around the new routes.
- `frontend/src/constants/helpDomains.ts` — `CONTENT_DOMAINS` list (sessions / editor / sop / processing / artifacts / cms / improvements / settings / general) + `ROUTE_TAG_MAP` (route name → feature_tag).
- `frontend/src/composables/useIsAdmin.ts` — mirrors `LEGACY_ADMIN_EMAIL` server-side gate.

**Modified:**
- `frontend/src/components/HelpCenterDrawer.vue` — switch fetch source (API first, `.md` fallback), add Admin toolbar conditional render, add Coverage panel conditional render, add Step + Related rendering on article detail.

### 5.5 Seeding existing content

A one-time admin-invoked migration `055_help_articles_seed.sql` (idempotent via `DO ... IF EXISTS RETURN`) inserts the 5 currently-bundled markdown files as draft articles. Admin reviews + publishes them via the new UI. Once verified, the `.md` fallback can be deleted in a follow-up.

### 5.6 Acceptance

- `python -m pytest tests/test_help_api.py` passes (CRUD + version snapshot + audience filter).
- Manual smoke: admin creates article, edits it twice, opens version history, sees 3 versions. Non-admin gets 403 on admin routes.
- The 5 existing `.md` articles appear as drafts after seeding migration.

---

## 6. Phase D — Ask AI with Gemini RAG (~3–4 days, moderate-risk)

### 6.1 Backend: `POST /v1/help/ask`

Verbatim port from MIC `app/api/help.py:168` with rounds-specific adjustments:

```python
@router.post("/ask")
async def ask_ai(body, user, db):
    if not settings.HELP_ASK_AI_ENABLED:
        raise HTTPException(404, "Ask AI is not enabled")
    # 1. Read all published articles audience-filtered
    # 2. Score by question-term hits + workflow_slug bias
    # 3. Take top 5 as context
    # 4. Call call_gemini_text(sys_prompt, payload, max_output_tokens=1024)
    # 5. Parse JSON {answer: string}; fall back to extractive on any failure
    # 6. Return {answer, sources: [{id,title,summary}], used_llm: bool}
```

Mirrors MIC behavior including the extractive fallback — Ask AI **never hard-errors**. If Gemini quota / network / parse fails, the user gets a degraded but useful response built from the top article summaries.

### 6.2 Settings + Railway

Add to `app/config.py`:

```python
HELP_ASK_AI_ENABLED: bool = False         # backend kill-switch — SSOT
HELP_ASK_AI_RATE_LIMIT_PER_HOUR: int = 30 # per-user soft cap — see §6.4
```

Railway env to add (api + worker services):

```
HELP_ASK_AI_ENABLED=false                 # default off; flip to true to enable
```

**`GEMINI_API_KEY` is already in Railway env** (shared with MIC's quota per `CLAUDE.md` "Production infrastructure" section). No new key provisioning required. The wiring uses the existing `app/engines/llm_client.py::call_gemini_text` — already verified to work in the Rounds runtime.

### 6.3 Frontend wiring

- Update `frontend/src/components/HelpCenterDrawer.vue:65` — switch `askAiEnabled` from the broken `VITE_HELP_ASK_AI_ENABLED` build-flag path to a server-fetched flag at drawer mount (single `GET /v1/version` extension — add `help_ask_ai_enabled: bool` to the version envelope). Removes the dev-speak instruction + plumbs the backend kill-switch through cleanly.
- Build the chat UI: input box at the bottom, message list above, sources rendered as link chips under each answer. ~150 LOC.
- Streaming response — defer to a follow-up; v1 is request/response.

### 6.4 Rate limiting + cost ceiling

Per-user soft rate limit: `HELP_ASK_AI_RATE_LIMIT_PER_HOUR = 30` enforced via Redis (`mic:help:ask:{user_email}:{epoch_hour}` INCR with 3600s TTL). At limit, return 429 with envelope `{error: {code: 'HELP_ASK_RATE_LIMIT', retryable: true}}` — does NOT degrade to extractive (the user should know they're throttled).

Per-call output cap: `max_output_tokens=1024` (matches MIC). Per-call retrieval cap: top 5 articles. These two together give a hard upper bound on input+output token cost per call.

### 6.5 Acceptance

- `tests/test_help_ask.py` — flag-off returns 404; flag-on with empty question → 400; flag-on with question → 200 with `used_llm=true` when Gemini available, `used_llm=false` with extractive fallback when Gemini key is unset; rate-limit returns 429 after 30 calls.
- Manual: ask "How do I edit a segment?" in the drawer; verify a grounded answer + sources panel.

---

## 7. Phase E — Compliance scoring + bulk AI actions (~4–5 days, moderate-risk)

### 7.1 Rounds-specific compliance thresholds ("CC-Rounds")

MIC's CC5.2 thresholds were tuned to MIC's 53-article corpus. Rounds starts with 5 articles and grows from there; rigid thresholds would block the initial publish flow. Proposed rounds-specific defaults (rationale per row):

| Threshold | Help (rounds) | FAQ (rounds) | MIC reference | Rationale |
|---|---|---|---|---|
| `MIN_STEPS` | **3** | **2** | 5 / 3 | Rounds articles are tighter; 3-step is enough for short procedures |
| `MIN_WORDS` (across steps) | **200** | **80** | 300 / 150 | Lower floor lets early articles publish without artificial padding |
| `SUMMARY_MIN` (chars) | **180** | **60** | 351 / 100 | Summaries that fit in a card preview |
| `SUMMARY_MAX` (chars) | **null** (no max) | **300** | null / 400 | FAQ summaries cap to keep accordion neat |
| `WORD_CEILING` (for % progress) | **1000** | **1000** | 1500 | Tighter target — rounds articles run shorter than MIC's |
| `SUMMARY_TARGET` (AI rewrite range) | `(180, 400)` | `(120, 280)` | `(351,600)` / `(200,350)` | Drives the Fix-CC bulk task |

Both backend SSOT (`app/utils/help_compliance.py`) and frontend mirror (`frontend/src/utils/helpCompliance.ts`) hold these values byte-identically. A test `tests/test_help_compliance.py::test_thresholds_match_audit` pins both sides to a hardcoded expected table — drift fails CI.

The label "CC-Rounds" replaces "CC5.2" everywhere (button text, error codes, JSON keys). No reference to MIC's version number leaks into rounds.

### 7.2 `compute_compliance()` (SSOT predicate)

Pure function, ports MIC `compute_compliance` verbatim except thresholds:

```python
def compute_compliance(article: dict | Any) -> dict:
    # ... returns {isFaq, wordCount, summaryLen, stepCount,
    #              wordsOk, summaryOk, stepsOk, allPass, pct}
```

`is_faq_category(category)` predicate: `return "faq" in (category or "").lower()` — same SSOT as MIC.

### 7.3 Bulk AI Celery tasks (mirror MIC `app/tasks/help_tasks.py`)

Four tasks under `app/tasks/help_tasks.py`, each inheriting `RoundsTask` (rounds equivalent of MIC's `MICTask`):

| Task | Trigger | Behavior |
|---|---|---|
| `fix_help_summaries_task` | `POST /v1/help/admin/fix-summaries` | For every article failing `summaryOk`, call Gemini to rewrite summary into the target range. **Saves as `is_published=False`** (review gate). Sets `last_edited_by='ai:fix_summaries'`. Bumps `version` (snapshots prior). |
| `expand_help_steps_task` | `POST /v1/help/admin/expand-steps` | For every non-FAQ article with `stepCount < MIN_STEPS=3`, call Gemini to draft additional `{title, body}` steps consistent with existing content. Same review-gate + version-bump rules. |
| `expand_faq_steps_task` | `POST /v1/help/admin/expand-faqs` | Same as expand-help but for FAQ category articles, threshold = 2. |
| `bulk_publish_drafts_task` (immediate, not Celery) | `POST /v1/help/admin/bulk-publish` | Server-side runs `compute_compliance` on each draft; only sets `is_published=True` for articles where `allPass=True`. Returns `{published, skipped:[{reason, wordsOk, summaryOk, stepsOk}], total_attempted}`. |

**Idempotency:** Redis key `rounds:help:task:{name}:{article_id}` with 24h TTL (matches MIC pattern). Reruns of a same task on a same article within 24h skip rather than retry — prevents the AI from running an infinite improve-loop on a borderline article.

**Audit hook:** every AI rewrite emits an `audit_events` row with `kind='help.ai_rewrite'`, `actor='ai:{task-name}'`, `details={article_id, version_before, version_after, threshold_failures}`.

### 7.4 Frontend

- `HelpAdminToolbar.vue` — wire the three buttons + bulk-publish.
- `HelpComplianceMeter.vue` — small inline meter on each article card + edit dialog showing `wordsOk / summaryOk / stepsOk` + overall `pct`. Reads from the frontend `helpCompliance.ts` mirror.
- Toast on task enqueue + WS event on completion (use existing WS bridge — `session:{user_email}` or extend to `user:{email}` channel).

### 7.5 Acceptance

- `tests/test_help_compliance.py` — threshold pinning + Help/FAQ predicate.
- `tests/test_help_tasks.py` — each task picks the right articles + saves as draft + bumps version.
- Manual: admin clicks Fix CC, sees N articles enqueued + appearing as new drafts; admin reviews + publishes.

---

## 8. Phase F — AI-generated FAQ corpus + FAQ render (~2–3 days, low-risk)

### 8.1 One-time seed task

`generate_faq_corpus_task` Celery task — admin-invoked one-time. Reads the existing 5 markdown files + the rounds.vin route inventory (Dashboard / Sessions / SessionDetail / Editor / SOP / Upload / Improvements / Settings) and asks Gemini to draft a starter FAQ article per route. Output format per article:

```json
{
  "title": "How do I edit a transcript segment?",
  "summary": "Two-sentence answer in plain product voice.",
  "category": "faq:editor",
  "steps": [
    {"title": "Open the segment", "body": "..."},
    {"title": "Make the change", "body": "..."},
    {"title": "Save it", "body": "..."}
  ],
  "feature_tags": ["editor"],
  "content_domain": "editor"
}
```

**Quality contract** (enforced in the system prompt):
- Product voice — second person, end-user nouns, no Vue component names, no DB schema terms, no phase markers.
- 3-step structure: open / do / verify.
- Summary 60–280 chars (matches CC-Rounds FAQ target).
- Cross-link suggestions in `related_article_ids` — Gemini sees the existing article list and picks 0–3 IDs to link.

All AI-generated FAQs land as `is_published=False` (review gate). Admin reviews + publishes via the standard UI.

The task is run ONCE to seed the FAQ corpus. After that, FAQs are authored / edited like any other article.

### 8.2 FAQ render component

`HelpFaqAccordion.vue` — when `is_faq_category(category)` returns true, the article renders as an expandable accordion (question = title, answer = summary + steps inline). For non-FAQ categories, the existing card render is used. Switch logic in `HelpDrawer.vue` mirroring MIC.

### 8.3 Cross-link rendering

`HelpRelatedLinks.vue` — at the bottom of every article detail, render `related_article_ids[]` as link chips. Each chip is a `<router-link>` that opens the linked article inside the same drawer (replaces the current `currentArticle`). Bidirectionality is NOT enforced — A → B doesn't auto-add B → A; admin decides per link.

### 8.4 Acceptance

- After running the seed task: ~8 FAQ drafts appear in admin view, one per route. Each passes CC-Rounds FAQ thresholds.
- Admin publishes them. User opens drawer, navigates to FAQ category, sees accordion render.
- Cross-links: clicking a related-link chip on Article A loads Article B in the same drawer.

---

## 9. What this plan deliberately does NOT include

| # | Item | Why |
|---|---|---|
| X5 | Read-tracking / analytics | Explicitly declined by user (2026-06-05) |
| — | Migration off `LEGACY_ADMIN_EMAIL` to `auth_users.role` | Independent Phase X (see audit plan §5 X10) |
| — | Real-time collaborative editing of articles | Out of scope; single-author authoring is sufficient |
| — | Localization / i18n of help content | Single-locale (English) until user signals otherwise |
| — | Image/video embeds in articles | Markdown body + steps cover ~95% of needs; defer |
| — | Bidirectional cross-link enforcement | Admin discretion is enough at current scale |
| — | Streaming Ask AI responses | Request/response is fine for v1 |
| — | Public (unauthenticated) help surface | Every endpoint requires auth (matches current posture) |

---

## 10. Verification matrix

| Phase | Backend test | Frontend test | Manual smoke |
|---|---|---|---|
| A | — | `grep` returns zero dev-speak hits | Open drawer on each route + read |
| B | — | Playwright: drawer opens, search works, "Show all" toggles | Mobile resize check |
| C | `tests/test_help_api.py` (CRUD + version + audience) | vue-tsc clean; Playwright admin CRUD | Admin creates 1 article + edits twice; non-admin gets 403 |
| D | `tests/test_help_ask.py` (flag, fallback, rate-limit) | UI renders sources panel | Real Gemini call returns grounded answer |
| E | `tests/test_help_compliance.py` + `tests/test_help_tasks.py` | Compliance meter shows correct flags | Admin runs Fix CC; drafts appear with `ai:fix_summaries` author |
| F | `tests/test_generate_faq_corpus.py` (mock Gemini) | Accordion render + cross-link navigation | Seed task generates 8 FAQ drafts; admin publishes |

Final invariant check across all phases: `git diff <pre-phase-a-sha>..HEAD` shows zero deletions on existing app/api/, app/engines/, app/middleware/, frontend/src/router/, frontend/src/stores/ (everything is additive except the rewrites in Phase A markdown + the cutover edit in HelpCenterDrawer.vue).

---

## 11. Execution sequencing recommendation

1. **Today (Phase A)** — ship the content rewrite. One commit. Push both remotes. The user-visible experience improves immediately with zero risk.
2. **Within the week (Phase B)** — structural drawer fixes. Independent of any backend.
3. **Phase C** as the next major block — gate it as a single PR (auth-gated routes + migration + admin UI) for a focused review.
4. **Phase D** (Ask AI) after C is stable — needs Gemini wiring + rate-limit policy in place. Flag stays OFF until soak in staging.
5. **Phase E** after D — compliance + bulk AI tasks build on the article CRUD from C and the Gemini wiring from D.
6. **Phase F** last — seeds the FAQ corpus using the compliance + AI infrastructure from E.

Each phase is independently revertible. Phases C–F each carry their own migration (`053` / `054` / `055` / `056` / `057` if needed) — Phase A and B carry none.

---

## 12. Success criteria (whole-plan)

The plan is successful when:

1. **Phase A**: zero dev-speak hits in `frontend/src/content/help/`. Verified by grep.
2. **Phase B**: drawer renders correctly on every route + on mobile. Verified by Playwright.
3. **Phase C**: admin can create / edit / archive articles + view version history; non-admin sees published content only. Verified by `tests/test_help_api.py` + manual.
4. **Phase D**: Ask AI returns grounded answers with source citations when enabled; extractive fallback when Gemini unavailable; rate-limit returns 429 at threshold. Verified by `tests/test_help_ask.py` + manual.
5. **Phase E**: CC-Rounds compliance meter accurate on every article; bulk AI rewrites land as drafts; admin review-gate enforced. Verified by `tests/test_help_compliance.py` + `tests/test_help_tasks.py` + manual.
6. **Phase F**: seed task generates an FAQ draft per route; FAQ accordion renders; cross-links navigate within drawer. Verified by `tests/test_generate_faq_corpus.py` + manual.
7. **Whole**: rounds.vin Help Center matches the MIC legacy screenshot's feature surface on every row in the audit comparison table.

---

*End of plan.*
