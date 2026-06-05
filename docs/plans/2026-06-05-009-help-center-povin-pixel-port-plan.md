# rounds.vin Help Center — Pixel-Perfect po.vin Port (Inline Panel) + X1–X8

> **This plan supersedes** the earlier `docs/plans/2026-06-05-008-help-center-full-port-plan.md` (which mirrored MIC). The user has provided three pixel-reference screenshots showing the po.vin Help Center; the design + layout must now match po.vin **byte-for-byte**, not MIC. The X1–X8 feature decisions (Ask AI, CC-Rounds thresholds, bulk AI, version history, FAQ corpus, cross-links, numbered steps; X5 out) carry forward and land **inside** the po.vin-style panel.

- **Date:** 2026-06-05
- **Author:** johndean@vin.com (+ Claude Opus 4.7)
- **Working directory:** `C:\Users\JohnDean\rounds\`
- **Pixel-perfect SSOT:** `C:\Users\JohnDean\po-vin\` (confirmed exists; Help Center implementation fully inventoried)
- **Reference screenshots:** three images attached in-session showing "This page" / "FAQ" / "Ask AI" tabs of the po.vin Help Center, including the inline-under-banner layout, "Still stuck?" yellow callout, semantic+lexical search box, and chat composer.

---

## 1. Context — why this plan exists

The audit (workflow `waqecj0sd`) and subsequent X1–X8 decisions produced a plan to port a help-center CMS from MIC. The user has now provided pixel-perfect reference screenshots showing a different SSOT — **po.vin** — and has stated two non-negotiable constraints:

1. **The Help Center must be inline under the banner header** (a third grid column in the main app layout), not a teleport drawer overlay.
2. **The design must match pixel-by-pixel** to the three reference screenshots (search placeholder, tab pills with sparkle icons, amber section labels, yellow "Still stuck?" callout, footer keyboard hints, "Ask the Help Center AI" chat composer, etc.).

The current rounds.vin Help Center (`HelpCenterDrawer.vue`, 299 LOC, teleport-to-body, z-index 840) cannot be incrementally tuned to match — it has the wrong architecture. The right move is **a full replace** sourced from `C:\Users\JohnDean\po-vin\` with rounds-specific content + the X1–X8 features layered on.

The X1–X8 features the user previously approved still apply:
- **X1** Ask AI with MIC's Gemini wiring (shared `GEMINI_API_KEY` already in Railway env)
- **X2** New rounds-specific compliance thresholds ("CC-Rounds")
- **X3** Bulk AI Celery tasks (fix-summaries / expand-steps / expand-faqs)
- **X4** Version history for help edits (`help_article_versions` table)
- **X5** *Read-tracking — declined, stays out*
- **X6** AI-generated FAQ corpus + accordion render
- **X7** Cross-linked articles (`related_article_ids[]`)
- **X8** Numbered JSONB steps

These features land **inside the po.vin-style panel**, not on top of a separate MIC-style design.

---

## 2. po.vin Help Center — verified component map (SSOT for the pixel port)

Located at `C:\Users\JohnDean\po-vin\`:

| Layer | po.vin file | What rounds will mirror |
|---|---|---|
| Inline panel root | `src/components/HelpPanel.vue` | Replaces `HelpCenterDrawer.vue` |
| Accordion item | `src/components/HelpItem.vue` | New `HelpItem.vue` in rounds |
| Article card (search results, related) | `src/components/help/HelpArticleCard.vue` | New `HelpArticleCard.vue` |
| Chat composer | `src/components/help/HelpAskComposer.vue` | New `HelpAskComposer.vue` (Phase 2) |
| Admin override editor | `src/views/admin/HelpEditor.vue` | New `HelpEditor.vue` (Phase 3) |
| Pinia store | `src/stores/help.ts` | Replace `stores/helpCenter.ts` |
| Hardcoded content | `src/constants/help-content.ts` | New `frontend/src/constants/help-content.ts` |
| API client | `src/lib/helpApi.ts` | New `frontend/src/services/helpApi.ts` |
| Backend route (Hono) | `src/server/routes/help.ts` | FastAPI port at `app/api/help.py` (Phase 2+) |
| Styles | `src/styles/help.css` | New `frontend/src/styles/help.css` |
| Mount in shell | `src/App.vue:92` (3rd grid column) | Modify `frontend/src/App.vue` + minor `app.css` changes |

**Architecture pattern from po.vin (`help.css:6-14`)** — the key layout move:

```css
.layout {
  display: grid;
  grid-template-columns: 232px minmax(0, 1fr) 0;     /* sidebar | main | (hidden help) */
  transition: grid-template-columns 300ms ease-out;
}
.layout[data-help-open="true"] {
  grid-template-columns: 232px minmax(0, 1fr) 420px; /* sidebar | main | help */
}
.help-drawer {
  position: sticky;
  top: 60px;                  /* under the topbar */
  height: calc(100vh - 60px);
}
```

The third column animates from `0` to `420px`. The middle column uses `minmax(0, 1fr)` so it reclaims/yields space automatically. **No JS layout math**, CSS Grid handles the push. On screens narrower than 900 px, the panel reverts to a `position: fixed` right-side overlay (po.vin's responsive fallback — we mirror this).

---

## 3. rounds.vin current state — what gets replaced

From the survey (Agent B, 2026-06-05):

- `frontend/src/components/HelpCenterDrawer.vue` (299 LOC, **REPLACE**) — teleports to `<body>`, `position: fixed`, `z-index: 840`, `width: 360px`.
- `frontend/src/stores/helpCenter.ts` (25 LOC, **REPLACE** with po.vin-style store).
- `frontend/src/App.vue:107` — mount point. Move out of the global-overlays cluster; render as a grid sibling.
- `frontend/src/components/AppHeader.vue:148` — trigger button (`?` icon). **KEEP unchanged** — still calls `help.toggle()`.
- `frontend/src/content/help/*.md` (5 files, 145 lines total) — **RETAIN as fallback** during Phase 1 cutover; **DELETE in Phase 3** after backend CMS lands.
- `frontend/src/styles/app.css` lines for `.help-drawer.*` and `.help-md` — **DELETE the overlay rules** (`position: fixed`, `z-index`, `transform` transitions); keep the markdown rendering rules as reference for the new component.

**`.app` shell grid** (`frontend/src/styles/app.css:19-23`) currently `grid-template-rows: auto 1fr`. Phase 1 changes this to a 2-area layout:

```css
.app {
  display: grid;
  grid-template-areas:
    "header header"
    "main   help";
  grid-template-rows: auto 1fr;
  grid-template-columns: minmax(0, 1fr) 0;
  transition: grid-template-columns 300ms ease-out;
}
.app[data-help-open="true"] {
  grid-template-columns: minmax(0, 1fr) 420px;
}
.app__header { grid-area: header; }
.app__main   { grid-area: main; min-width: 0; }
.app__help   { grid-area: help; min-width: 0; }
```

`AppHeader` wears the `app__header` class; the routed view wears `app__main`; the new `HelpPanel` wears `app__help`. Editor's `.editor__grid` already uses `minmax(0, 1fr)` for its center column — it reflows naturally when the help panel opens.

---

## 4. Pixel-perfect visual spec (from po.vin `help.css`, verbatim values)

Captured by Agent A (po.vin source read). These are the exact values rounds.vin will copy:

**Header (`help.css:40-81`):**
- Padding `18px 20px 14px`; gap `12px`
- Help icon `32×32px`, navy background, gold `?` glyph, `border-radius: 8px`
- Overline ("HELP CENTER") `10px / 800 / 0.12em letter-spacing / uppercase / steel`
- Title ("Need a hand?") `17px / 800 / navy`
- Close (X) `28×28px`, subtle border, hover transition

**Search (`help.css:84-112`):**
- Margin `14px 20px 10px`
- Padding `8px 10px`
- Background `var(--color-off-white)`; border `1px var(--border-subtle)`; `border-radius: 8px`
- Input `13px / inherit-font / navy text / steel placeholder`
- Placeholder text: **"Search help — semantic + lexical"**
- Clear button `20×20px` round
- Spinner animation `help-spin 0.9s linear infinite`

**Tabs / pills (`help.css:114-137`):**
- Container flex, gap `6px`, padding `4px 20px 0`
- Inactive: `off-white bg / 1px subtle border / 11px 800 / steel text / border-radius 999px / padding 6px 12px`
- Active: `navy bg / white text / navy border`
- Icons: ✦ "This page", 📖 "FAQ", ✦ "Ask AI" — the sparkle icons are rendered via inline SVG inside the button

**Accordion (`help.css:172-216`):**
- Item: `1px subtle border / border-radius 8px / white bg`
- Question button: `13px / 800 / navy / padding 10px / flex with chevron`
- Expanded question: bg becomes `off-white`; chevron rotates `180deg`
- Answer: `13px / steel / padding 10px / line-height 1.55`

**Yellow "Still stuck?" callout (`help.css:227-238`):**
- Padding `12px 14px`; bg `var(--color-warm-light)`; border `1px var(--color-gold)`; `border-radius: 8px`
- Font `12px / navy`; strong label `13px / bold`
- Body links navy + `font-weight: 800`; `<code>` tags monospace with light-gray background

**Chat composer ("Ask AI" tab, `help.css:412-596`):**
- Thread container `flex column / gap 16px / overflow-y auto`
- User message: `light-steel bg / 12px / navy / padding 8px / border-radius 8px`
- AI answer: `off-white bg / subtle border / 13px navy / line-height 1.55`
- Typing cursor: `7×14px / blue bg / animation: help-cursor 1s steps`
- Citations: ordered list with numbered links + external-link icons + top border separator
- Input textarea: `off-white bg / subtle border / 13px / focus → blue border + white bg / rows="2" min-height 48px max 140px`
- Submit button: dark navy `btn--primary` with paper-plane icon, disabled while streaming

**Footer (`help.css:241-264`):**
- Padding `12px 20px`; gap `10px`; border-top `1px subtle`
- `.kbd` badge: `light-steel bg / navy / monospace / 10px / border-radius 4px`
- Doc link: `blue / 800 / external-link icon / underline on hover`
- Text: **"Press `?` to open · `Esc` to close"** + right-aligned **"Full docs ↗"**

**Responsive (`help.css:267-281`):**
- Below `900px`: panel reverts to `position: fixed; top: 60px; right: 0; max-width: 360px; z-index: 30`
- Slide transition `translateX(100%)` ↔ `translateX(0)`
- Shadow `-8px 0 32px rgba(0, 40, 85, 0.18)`

**Section labels (amber/gold uppercase):**
- "FOR ADMINS · DASHBOARD" / "FREQUENTLY ASKED" / "✦ ASK THE HELP CENTER AI"
- `10px / 800 / 0.12em letter-spacing / uppercase / gold color`
- Dot separator between role + page in "This page" tab

---

## 5. Five-phase rollout

| Phase | Days | Risk | What ships |
|---|---|---|---|
| 1 | 3–4 | Low–Moderate | Inline panel + pixel-perfect po.vin port + hardcoded HELP_CONTENT (drafted in rounds voice) |
| 2 | 3–4 | Moderate | Ask AI tab wired to backend `/v1/help/ask` (MIC Gemini pattern) + rate limit (X1) |
| 3 | 5–7 | Moderate | Backend CMS — `help_articles` + `help_article_versions` + admin CRUD + version history + cross-links + numbered steps (X4 + X7 + X8) |
| 4 | 4–5 | Moderate | CC-Rounds compliance + 3 bulk-AI Celery tasks (X2 + X3) |
| 5 | 2–3 | Low | AI-generated FAQ corpus seed + accordion render (X6) |

**Total: ~17–23 working days.** Each phase is independently shippable + revertible.

---

## 6. Phase 1 — Inline panel + pixel-perfect po.vin port

### 6.1 New + modified files

**New:**
- `frontend/src/components/help/HelpPanel.vue` — port of po.vin's `HelpPanel.vue`. Three tabs, search input, footer, "Still stuck?" callout. Renders inside the new `app__help` grid area.
- `frontend/src/components/help/HelpItem.vue` — port of po.vin's `HelpItem.vue`. Accordion question/answer with chevron rotation.
- `frontend/src/components/help/HelpArticleCard.vue` — port of po.vin's `HelpArticleCard.vue`. Used for search results + related-article chips (X7 hooks in Phase 3).
- `frontend/src/stores/help.ts` — replaces `helpCenter.ts`. Adds: `pageKey` ref, `role` ref, `currentEntry` computed (lookup by `pageKey + role` in HELP_CONTENT), `faq` computed, `searchQuery` ref, `searchResults` computed (substring + title-rank for Phase 1; semantic in Phase 2), placeholders for `startAsk()` / `cancelAsk()` (wired in Phase 2).
- `frontend/src/constants/help-content.ts` — hardcoded `HELP_CONTENT` object. Shape mirrors po.vin's: `{ pages: { [routeKey]: { [role]: { title, intro, topics: [{q, a}] } } }, faq: [{q, a}] }`. Content draft below in §6.4.
- `frontend/src/styles/help.css` — port of po.vin's `help.css` verbatim, with `--color-*` and `--border-subtle` resolved to rounds' existing CSS variables (mapped in §6.3).
- `frontend/src/utils/routeToPageKey.ts` — single-source `ROUTE_TAG_MAP` (route.name → pageKey). Mirror of po.vin's pattern.

**Modified:**
- `frontend/src/App.vue` — swap `<HelpCenterDrawer />` (at line 107) with new `<HelpPanel class="app__help" />`. Add `:data-help-open="help.isOpen"` on the root `.app` element.
- `frontend/src/components/AppHeader.vue` — no functional change; the `?` button at line 148 still calls `help.toggle()`. The store is renamed (`useHelpCenterStore` → `useHelpStore`); update the import.
- `frontend/src/styles/app.css:19-23` — change `.app` grid to the named-areas pattern shown in §3.
- `frontend/src/main.ts` — register the new help store (no real change; Pinia auto-registers).

**Deleted (end of Phase 1, after verification):**
- `frontend/src/components/HelpCenterDrawer.vue`
- `frontend/src/stores/helpCenter.ts`
- All `.help-drawer.*` overlay rules in `app.css` (replaced by `help.css`)
- (Defer the 5 `.md` files in `frontend/src/content/help/` until Phase 3 CMS lands — they're a fallback safety net.)

### 6.2 Routing + pageKey resolution

`stores/help.ts` watches `route.name` and maps to a `pageKey`:

```ts
const ROUTE_TAG_MAP: Record<string, string> = {
  Dashboard:      'dashboard',
  Sessions:       'sessions',
  SessionDetail:  'session-detail',
  Editor:         'editor',
  Sop:            'sop',
  Upload:         'upload',
  Improvements:   'improvements',
  Settings:       'settings',
  Audit:          'audit',
  Help:           'help',
};
const pageKey = computed(() => ROUTE_TAG_MAP[String(route.name)] || 'dashboard');
```

The current role for rounds is resolved from the auth store. rounds is single-tenant today and only has the `LEGACY_ADMIN_EMAIL` admin gate (BR-001) — so the role resolution simplifies to `'admin' | 'user'`. The HELP_CONTENT table is structured so `'user'` is the always-present default; `'admin'` is an optional override per page.

### 6.3 CSS variable mapping

po.vin's `help.css` uses these variables — rounds already has equivalents in `frontend/src/styles/colors_and_type.css`:

| po.vin variable | rounds equivalent | Notes |
|---|---|---|
| `--color-navy` | `--surface-nav` or new `--color-navy` (`#002055`) | Topbar bg + active pill bg |
| `--color-gold` | `--color-gold` (already present from Phase 7-broader work) | Section label color |
| `--color-steel` | `--text-muted` / new `--color-steel` | Body paragraph color |
| `--color-light-steel` | `--surface-elevated` / new `--color-light-steel` | Inactive pill bg, user msg bg |
| `--color-off-white` | `--surface-card` / new `--color-off-white` | Search input bg, AI answer bg |
| `--color-warm-light` | new `--color-warm-light` (`#fff7e0` or similar) | "Still stuck?" callout bg |
| `--color-blue` | `--color-link` or new `--color-blue` | Search-input focus border + link color |
| `--border-subtle` | `--border-subtle` (already present) | Card / pill borders |
| `--duration-normal` / `--duration-fast` | new constants `250ms` / `120ms` | Panel + tab transitions |
| `--easing-out` | new `cubic-bezier(0.16, 1, 0.3, 1)` | Smooth grid-template-columns animation |

Any missing variables get added to `colors_and_type.css` in Phase 1 with rounds-appropriate values. **No locked-weight or pipeline file is touched.**

### 6.4 Initial HELP_CONTENT — rounds-specific draft (Phase 1 ships this)

Phase 1 ships **hand-authored / AI-drafted** content for the 10 rounds routes × 2 roles (`admin`, `user`). Each entry follows po.vin's structure: `title`, `intro` (1–2 sentences, second person, plain product voice), `topics` (3–5 accordion items per page+role). The `faq` corpus seeds with ~10 cross-cutting questions.

**Worked example — Editor page, `user` role:**

```ts
editor: {
  user: {
    title: 'Editor',
    intro:
      'The Editor is where you review and correct a transcript. Three panes — slides on the left, ' +
      'transcript in the middle, audit details on the right.',
    topics: [
      {
        q: 'How do I edit a transcript segment?',
        a: 'Click on the segment text in the middle pane to start editing. Type your change, then ' +
          'click Save. Use Cancel to discard. Every save is reversible — open the Audit tab to see ' +
          'your edit history and undo any change.',
      },
      {
        q: 'How do I move a chat or poll to a different time?',
        a: 'Drag the chat or poll card from the right rail onto the transcript segment where it ' +
          'should appear. The card snaps to the segment\'s start time. You can drag again to ' +
          'reanchor at any point.',
      },
      {
        q: 'How do I change who said a segment?',
        a: 'Use the Speakers panel on the top right to rename, merge, or reassign speakers across ' +
          'the whole session. Changes apply to every segment that references the speaker.',
      },
      {
        q: 'How do I export the finished transcript?',
        a: 'Click the Export menu at the top of the Editor. Pick docx, srt, vtt, txt, or zip. ' +
          'Filler words like "um" and "uh" are removed from docx and txt; srt/vtt keep them so ' +
          'captions stay aligned to the audio.',
      },
    ],
  },
  admin: {
    title: 'Editor',
    intro:
      'You see everything the editor user sees plus a Rescue section. Use Rescue only when a ' +
      'session is stuck or needs to be re-processed from scratch.',
    topics: [
      {
        q: 'What does the Admin tab\'s Rescue section do?',
        a: 'Five operator buttons that re-run pipeline stages on a stuck session. Re-ingest ' +
          'restarts the whole pipeline; Re-align rebuilds slide-to-segment matches; the other ' +
          'three handle stage init, poll placement, and a hard abort.',
      },
      {
        q: 'When should I retry vs abort a session?',
        a: 'Retry when the failure was transient (network, Gemini quota). Abort when the source ' +
          'media is bad and the session should not continue. Aborted sessions can be deleted from ' +
          'the Sessions list.',
      },
    ],
  },
},
```

**Page coverage targets for Phase 1:** Dashboard, Sessions, SessionDetail, Editor, SOP, Upload, Improvements, Settings, Audit, Help (about-help). The full content draft lives in `frontend/src/constants/help-content.ts` (~600 lines).

**FAQ corpus (Phase 1 hardcoded — replaced by AI-generated articles in Phase 5):**
```ts
faq: [
  { q: 'I forgot my password — what do I do?', a: '...' },
  { q: 'How long do sessions last?',          a: '...' },
  { q: 'What is the difference between AI Mode and Default Mode?', a: '...' },
  { q: 'Why does the pipeline sometimes say "rate-limited"?', a: '...' },
  { q: 'Can I retry a failed session safely?', a: '...' },
  { q: 'Where can I see who edited a transcript?', a: '...' },
  { q: 'How do I use this help panel?', a: '...' },
  { q: 'Where do exports come from?', a: '...' },
  { q: 'What happens when I archive a session?', a: '...' },
  { q: 'Where can I learn more?', a: '...' },
],
```

### 6.5 Phase 1 verification

- **Pixel match**: side-by-side screenshot diff against the 3 reference images for each tab. Tolerance: `≤ 2px` on any padding/margin; **exact** for color tokens.
- `vue-tsc --noEmit` clean.
- `npm run build` produces a bundle. Bundle-size delta vs current Help Center: expected `+10 – +15 KB` gzipped (new component + content table).
- Playwright spec: open drawer on every route, switch tabs, confirm route-keyed content renders, confirm yellow callout visible, confirm footer hints render.
- Manual: open on every route at desktop + at 768px (responsive overlay fallback) + at 360px (mobile width).
- `?` button still toggles (AppHeader.vue:148 unchanged).
- `Esc` still closes.

### 6.6 Phase 1 commit shape

Single PR (or two PRs split as `layout-pivot` + `pixel-port`):
1. `feat(help): inline grid layout + pixel-perfect po.vin port + rounds HELP_CONTENT`
2. (squash-acceptable) delete obsolete `HelpCenterDrawer.vue` + `helpCenter.ts` + overlay CSS

Push to both remotes per CLAUDE.md convention.

---

## 7. Phase 2 — Ask AI with MIC's Gemini wiring (X1)

Builds on Phase 1. The Ask AI tab placeholder becomes a real chat.

### 7.1 Backend

`app/api/help.py` (new, ~250 LOC). Port the MIC `app/api/help.py::ask_ai` pattern verbatim (lines 168–229 of MIC) with rounds wiring:

```python
@router.post("/ask")
async def ask_ai(body, user, db):
    if not settings.HELP_ASK_AI_ENABLED:
        raise HTTPException(404, "Ask AI is not enabled")
    # 1) Retrieve published help articles (Phase 3 — for Phase 2 we read from
    #    a temporary in-memory copy of frontend/src/constants/help-content.ts
    #    converted into a Python dict at module import time)
    # 2) Score by question-term hits + workflow_slug bias
    # 3) Top 5 → context block
    # 4) call_gemini_text(sys_prompt, payload, max_output_tokens=1024)
    # 5) JSON-parse {answer: string}; fall back to extractive on any failure
    # 6) Return {answer, sources: [{id,title,summary}], used_llm: bool}
```

Settings additions (`app/config.py`):

```python
HELP_ASK_AI_ENABLED: bool = False                # backend kill-switch (default off)
HELP_ASK_AI_RATE_LIMIT_PER_HOUR: int = 30        # per-user soft cap (Redis-backed)
```

`GEMINI_API_KEY` is already provisioned (Railway env, shared MIC quota per `CLAUDE.md`). No new Railway access setup required.

Rate limit: Redis key `rounds:help:ask:{user_email}:{epoch_hour}` INCR + EXPIRE 3600. At cap, return 429 with envelope `{error: {code: 'HELP_ASK_RATE_LIMIT', retryable: true}}`.

### 7.2 Frontend

- `frontend/src/components/help/HelpAskComposer.vue` (new, ~180 LOC) — pixel-port of po.vin's `HelpAskComposer.vue`. Streaming SSE message list; user bubble (light-steel bg) above; AI answer bubble (off-white bg + sources list) below; textarea + paper-plane button at the bottom.
- `frontend/src/services/helpApi.ts` (new) — `askHelp(question, signal)` returns an SSE reader. Mirrors po.vin's `helpApi.ts`.
- `frontend/src/components/help/HelpPanel.vue` — Ask AI tab swaps from "coming soon" copy to `<HelpAskComposer />`.
- `app/main.py` — wire `from app.api import help as help_router` + `app.include_router(help_router.router)`.
- `/v1/version` — extend the response envelope to include `help_ask_ai_enabled: bool`. The frontend reads this at app mount; the broken build-time `VITE_HELP_ASK_AI_ENABLED` flag is **deleted**.

### 7.3 Phase 2 verification

- `tests/test_help_ask.py` — flag-off → 404; empty question → 400; valid question → 200 with `used_llm=true` when Gemini key is set, `used_llm=false` extractive fallback when not; 30 calls/hr → 429.
- Manual: ask "How do I edit a transcript segment?" with the flag on; verify grounded answer + sources panel + paper-plane button disables while streaming.

---

## 8. Phase 3 — Backend CMS + version history + cross-links + numbered steps (X4 + X7 + X8)

### 8.1 Migrations

`migrations/053_help_articles.sql`:

```sql
CREATE TABLE IF NOT EXISTS help_articles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    summary         TEXT NOT NULL DEFAULT '',
    category        TEXT NOT NULL,           -- 'general' | 'faq:*' | 'page:dashboard' | ...
    audience        TEXT NOT NULL DEFAULT 'users',   -- 'users' | 'admin'
    feature_tags    JSONB NOT NULL DEFAULT '[]',    -- per-page filter
    steps           JSONB NOT NULL DEFAULT '[]',    -- X8 — [{title, body}, ...]
    related_article_ids JSONB NOT NULL DEFAULT '[]',-- X7
    display_order   INTEGER NOT NULL DEFAULT 0,
    is_published    BOOLEAN NOT NULL DEFAULT FALSE,
    content_domain  TEXT NOT NULL DEFAULT 'general',
    workflow_slug   TEXT,
    version         INTEGER NOT NULL DEFAULT 1,
    last_edited_by  TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_help_articles_published ON help_articles(is_published);
CREATE INDEX IF NOT EXISTS idx_help_articles_content_domain ON help_articles(content_domain);
CREATE INDEX IF NOT EXISTS idx_help_articles_feature_tags ON help_articles USING GIN (feature_tags);
```

`migrations/054_help_article_versions.sql`:

```sql
CREATE TABLE IF NOT EXISTS help_article_versions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id  UUID NOT NULL REFERENCES help_articles(id) ON DELETE CASCADE,
    version     INTEGER NOT NULL,
    snapshot    JSONB NOT NULL,
    edited_by   TEXT NOT NULL,
    edited_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(article_id, version)
);
CREATE INDEX IF NOT EXISTS idx_help_article_versions_article ON help_article_versions(article_id);
```

`migrations/055_help_articles_seed.sql` — idempotent seed inserting the Phase-1 hardcoded HELP_CONTENT topics + FAQ as `is_published=TRUE` articles. After seeding succeeds, Phase 1's hardcoded `help-content.ts` becomes a fallback only.

### 8.2 Backend routes (`app/api/help.py` additions)

| Method + Path | Purpose | Auth |
|---|---|---|
| `GET /v1/help/articles?feature_tag=&audience=` | List | Any authed user |
| `GET /v1/help/articles/{id}` | Detail | Any authed user |
| `GET /v1/help/articles/{id}/versions` | Version list (X4) | Admin |
| `GET /v1/help/articles/{id}/versions/{n}` | Version snapshot (X4) | Admin |
| `POST /v1/help/articles` | Create | Admin |
| `PATCH /v1/help/articles/{id}` | Update (auto-snapshots prior version, bumps `version`) | Admin |
| `PATCH /v1/help/articles/{id}/archive` | Sets `is_published=false` | Admin |
| `PATCH /v1/help/articles/reorder` | Bulk display_order | Admin |
| `GET /v1/help/coverage` | Domain count grid | Admin |
| `GET /v1/help/search?q=` | Server-side search (substring + title-rank for v1) | Any authed user |

Admin gate uses existing `require_admin(_user)` from `app/security/roles.py` (BR-001 — `LEGACY_ADMIN_EMAIL`). PATCH handler snapshots prior state to `help_article_versions` BEFORE applying.

### 8.3 Frontend admin overlay

- `frontend/src/views/admin/HelpEditor.vue` (new, ~400 LOC) — port of po.vin's `HelpEditor.vue`. Lists articles, opens create/edit modal, manages publish/archive.
- `frontend/src/components/help/HelpArticleEditorDialog.vue` — create/edit modal. Fields: title, summary, category, content_domain, feature_tags (multi-select chips), audience toggle, **numbered steps editor (X8)** with drag-reorder, **related articles picker (X7)** with multi-select against the article list.
- `frontend/src/components/help/HelpStepList.vue` — read-only numbered render of `steps[]` (used in panel detail view).
- `frontend/src/components/help/HelpVersionHistoryDialog.vue` — opens from "View history" in HelpEditor; lists versions chronologically with diff-vs-current toggle.
- `frontend/src/components/help/HelpRelatedLinks.vue` — at the bottom of an article body, renders `related_article_ids[]` as chip links that swap the open article in-place.
- `frontend/src/components/help/HelpCoverageReport.vue` — admin-only panel-top stat block; renders the coverage grid (`<2` per domain shows a red dot). Same component pattern as MIC's `HelpCoverageReport.vue`.

### 8.4 Phase 3 verification

- `tests/test_help_api.py` — CRUD + version snapshot + audience filter; non-admin gets 403 on admin routes.
- Manual: admin creates an article with 3 steps + 2 related links; edits twice; opens version history; sees 3 versions with diff highlights; non-admin user sees published-only articles in the panel.

---

## 9. Phase 4 — CC-Rounds compliance + bulk-AI Celery tasks (X2 + X3)

### 9.1 New rounds-specific thresholds ("CC-Rounds")

Designed for rounds' smaller starting corpus (looser than MIC's CC5.2):

| Threshold | Help (rounds) | FAQ (rounds) | MIC reference | Rationale |
|---|---|---|---|---|
| `MIN_STEPS` | **3** | **2** | 5 / 3 | rounds articles run tighter; 3-step minimum is enough for a procedure |
| `MIN_WORDS` | **200** | **80** | 300 / 150 | floor lets early articles publish without artificial padding |
| `SUMMARY_MIN` (chars) | **180** | **60** | 351 / 100 | summaries that fit in a card preview |
| `SUMMARY_MAX` (chars) | none | **300** | none / 400 | FAQ caps keep accordion neat |
| `WORD_CEILING` | **1000** | **1000** | 1500 | tighter target |
| `SUMMARY_TARGET` (AI rewrite range) | `(180, 400)` | `(120, 280)` | `(351,600)` / `(200,350)` | drives Fix-CC bulk task |

SSOT lives in **two** byte-identical files:
- `app/utils/help_compliance.py` (backend)
- `frontend/src/utils/helpCompliance.ts` (frontend mirror)

A test `tests/test_help_compliance.py::test_thresholds_match_audit` pins both sides to a hardcoded expected table — drift fails CI. Label "CC-Rounds" replaces "CC5.2" everywhere.

### 9.2 Celery tasks

`app/tasks/help_tasks.py` (new, ~300 LOC). Each task inherits `RoundsTask`, with idempotency via Redis (`rounds:help:task:{name}:{article_id}`, 24h TTL):

| Task | Trigger | Behavior |
|---|---|---|
| `fix_help_summaries_task` | `POST /v1/help/admin/fix-summaries` | Articles failing `summaryOk` → Gemini rewrites summary into target. Saved as `is_published=False`, `last_edited_by='ai:fix_summaries'`, version bumped. |
| `expand_help_steps_task` | `POST /v1/help/admin/expand-steps` | Non-FAQ articles with `stepCount < 3` → Gemini drafts additional steps. Same review-gate. |
| `expand_faq_steps_task` | `POST /v1/help/admin/expand-faqs` | FAQ-category articles with `stepCount < 2` → Gemini drafts steps. |
| `bulk_publish_drafts_task` (inline, not Celery) | `POST /v1/help/admin/bulk-publish` | Per-row `compute_compliance` gate; only `allPass=True` drafts publish. Returns `{published, skipped:[{reason, wordsOk, summaryOk, stepsOk}], total_attempted}`. |

**Audit hook:** every AI rewrite emits an `audit_events` row with `kind='help.ai_rewrite'`, `actor='ai:{task-name}'`, `details={article_id, version_before, version_after, threshold_failures}`.

### 9.3 Frontend

- `HelpAdminToolbar.vue` (new) — `+ New Article` / `Publish All Drafts` / `Fix CC-Rounds` / `Expand Steps` / `Expand FAQs` / `Coverage Report` buttons. Toast on enqueue. Disabled while task in-flight.
- `HelpComplianceMeter.vue` (new) — small inline meter on each article card + edit dialog. Three checks (words / summary / steps) with red/green dots + overall percent.

### 9.4 Phase 4 verification

- `tests/test_help_compliance.py` + `tests/test_help_tasks.py`.
- Manual: admin clicks Fix CC-Rounds; N articles enqueued; appear as new drafts authored by `ai:fix_summaries`; admin reviews + publishes.

---

## 10. Phase 5 — AI-generated FAQ corpus + accordion render (X6)

### 10.1 One-time seed task

`generate_faq_corpus_task` (`app/tasks/help_tasks.py`, additional task). Admin-invoked. Reads the existing published articles + the rounds.vin route inventory and asks Gemini to draft a starter FAQ article per route. Schema:

```json
{
  "title": "How do I edit a transcript segment?",
  "summary": "Two-sentence answer in plain product voice.",
  "category": "faq:editor",
  "steps": [
    { "title": "Open the segment", "body": "..." },
    { "title": "Make the change", "body": "..." },
    { "title": "Save it", "body": "..." }
  ],
  "feature_tags": ["editor"],
  "content_domain": "editor"
}
```

**Quality contract** (baked into the system prompt):
- Product voice — second person, end-user nouns, **no Vue component names, no DB schema terms, no phase markers, no HTTP routes, no env var names**
- 3-step structure (open / do / verify)
- Summary 60–280 chars (CC-Rounds FAQ target)
- Gemini receives the existing article list and picks 0–3 IDs for `related_article_ids` (X7 wiring)

All AI-generated FAQs land `is_published=False`. Admin reviews + publishes via Phase 3 UI.

### 10.2 FAQ render

`HelpFaqAccordion.vue` (new) — when `is_faq_category(category)` returns true, the article renders as an expandable accordion (question = title, answer = summary + steps inline). For non-FAQ categories, the existing card render is used. Switch logic in `HelpPanel.vue` mirroring po.vin.

`is_faq_category(category) → "faq" in (category or "").lower()` — SSOT predicate, mirrored in `app/utils/help_compliance.py` and `frontend/src/utils/helpCompliance.ts`.

### 10.3 Cross-link rendering (X7 finalized)

`HelpRelatedLinks.vue` already added in Phase 3 — Phase 5 just verifies the AI seed task populates `related_article_ids` correctly.

### 10.4 Phase 5 verification

- After running seed task: ~10 FAQ drafts appear (one per route). Each passes CC-Rounds FAQ thresholds.
- Admin publishes them. User opens drawer, switches to FAQ tab, sees accordion render. Cross-link chips at the bottom of each article navigate within the panel.

---

## 11. Out of scope (acknowledged)

| # | Item | Why out |
|---|---|---|
| X5 | Read-tracking / analytics | Explicitly declined by user (2026-06-05) |
| — | Migration off `LEGACY_ADMIN_EMAIL` to `auth_users.role` | Independent Phase X |
| — | Real-time collaborative article editing | Single-author authoring sufficient at current scale |
| — | i18n / localization | Single-locale (English) only |
| — | Image / video embeds in articles | Markdown body + numbered steps cover ~95% of needs |
| — | Bidirectional cross-link enforcement | Admin discretion suffices |
| — | Streaming Ask AI for arbitrary length | Cap at 1024 output tokens; request/response with simulated streaming via SSE |
| — | Public (unauthed) help surface | All endpoints require auth (matches current rounds posture) |

---

## 12. Verification matrix

| Phase | Backend test | Frontend test | Manual smoke |
|---|---|---|---|
| 1 | — | `vue-tsc` clean; Playwright opens panel on every route + switches tabs | Pixel diff vs 3 reference screenshots (≤2px tolerance) |
| 2 | `tests/test_help_ask.py` (flag, extractive fallback, rate-limit) | Composer renders sources panel + paper-plane button | Real Gemini call returns grounded answer |
| 3 | `tests/test_help_api.py` (CRUD + version + audience) | vue-tsc + Playwright admin CRUD | Admin creates article + edits twice + opens version history |
| 4 | `tests/test_help_compliance.py` + `tests/test_help_tasks.py` | Compliance meter flags accurate | Admin runs Fix CC-Rounds; drafts appear `ai:fix_summaries` |
| 5 | `tests/test_generate_faq_corpus.py` (Gemini mocked) | Accordion render + cross-link navigation | Seed task generates 10 FAQ drafts; admin publishes |

**Final invariant across all phases:** `git diff <pre-phase-1-sha>..HEAD` shows **zero deletions** in `app/api/{auth,sessions,corrections,exports,segments,session_resources,sop,settings}.py`, `app/engines/*`, `app/middleware/*`, `frontend/src/router/`, `frontend/src/stores/auth.ts`, `frontend/src/views/{Editor,Upload,SessionDetail,Sop,Audit,Improvements,Settings}View.vue`. The only deletions allowed are the deprecated overlay-drawer files at the end of Phase 1 + their CSS rules in `app.css`.

---

## 13. Order of operations + rollback

1. **Phase 1 first** — ships the visible pixel-perfect change. Independent of any backend.
2. **Phase 2** after Phase 1 stabilizes (≥ 2 days soak) — needs Gemini wiring + rate-limit policy in place. Backend flag default OFF until staging soak passes.
3. **Phase 3** as a single PR (migrations + auth-gated routes + admin UI). Cutover keeps the Phase 1 hardcoded HELP_CONTENT as fallback for 1 week before deletion.
4. **Phase 4** depends on Phase 3 (article CRUD) + Phase 2 (Gemini wiring).
5. **Phase 5** seeds using Phase 4's compliance + AI infrastructure.

**Rollback per phase**: each phase ships its own commits. `git revert <phase-N-merge-sha>` reverts to the prior stable state. Migrations 053 / 054 / 055 are forward-only but the table is `IF NOT EXISTS` and the data is admin-edited content (no user data lost on revert if the table is dropped).

---

## 14. Success criteria

This plan is successful when:

1. **Phase 1**: rounds.vin Help Center renders pixel-identical to the three reference screenshots (search placeholder text, tab pill style, accordion expand/collapse animation, yellow callout, footer hints) — verified by side-by-side image diff with ≤ 2 px tolerance on padding/margin and exact match on color tokens.
2. **Phase 1**: opening the panel pushes the main content left (CSS Grid 3rd column animates `0 → 420px`), does not overlay; on screens narrower than 900 px, it reverts to a fixed-right overlay drawer with the same content.
3. **Phase 2**: Ask AI tab returns grounded answers with cited sources when the backend flag is on; extractive fallback when Gemini is unavailable; rate-limit returns 429 after 30 calls/hour.
4. **Phase 3**: admin can CRUD articles + open version history; non-admin gets 403 on admin routes; the 5 obsolete `.md` files are deleted; coverage report shows the domain grid with `<2`-red flag.
5. **Phase 4**: CC-Rounds compliance meter accurate on every article; bulk AI rewrites land as drafts; admin review-gate enforced.
6. **Phase 5**: FAQ corpus seeded; accordion renders; cross-links navigate within the panel.
7. **Whole**: zero dev-speak instances remaining in any user-facing copy (verified by the grep used in the original audit).

---

## 15. Notes on the prior `docs/plans/2026-06-05-008-help-center-full-port-plan.md`

The earlier plan committed at `60f74da` (rounds repo) mirrored MIC. The user's pixel-perfect po.vin requirement supersedes that plan. After ExitPlanMode + approval, I will:

1. Mark the prior plan superseded by appending a header note at the top, and
2. Add a one-line cross-reference from `CLAUDE.md` to **this** plan as the active source of truth.

Both repo writes happen post-approval; nothing changes in the repo while plan mode is active.

---

*End of plan.*
