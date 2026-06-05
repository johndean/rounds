# Phase 1 Baseline — Help Center (Phase 2 scope)

Generated 2026-06-04 against tip `6df4170` (`6df4170d22fd27127cdd413e0765e1c57ef8eb37`).

**Scope:** read-only inventory for the rounds.vin stakeholder remediation **Phase 2 — Help Center** (context-sensitive Help Center, per-page FAQ, search, context filtering, plus a feature-flagged "Ask AI" surface). Mandate is pixel-parity / zero-unrequested-change. No edits in this pass.

> Note on overloaded "Phase 2" terminology: the in-repo plan `docs/plans/2026-05-18-002-parity-remediation-phases.md` already uses "Phase 2" for **Settings persistence**. The stakeholder remediation track this audit serves is a *separate* numbering. Future plan docs should disambiguate (e.g. `Phase 2 (stakeholder) — Help Center`) to avoid collision with the audit-remediation plan's phases.

---

## Existing Help / FAQ / Docs surface today

**None.** Rounds has no HelpCenter, FAQ, Docs, or Help drawer/modal/panel component anywhere in the codebase. Verified:

- `frontend/src/components/` — no `Help*.vue`, no `FAQ*.vue`, no `Docs*.vue`.
- `frontend/src/views/` — 14 views total, none named or referencing help/FAQ/docs surface.
- `frontend/src/components/shared/Icon.vue` — ~40 inline-SVG icons; **no `help-circle`, `question-mark`, or `info` icon** exists today. Adding a "?" button requires either adding an icon to the set or using a text glyph (`?`) the way `A−` / `A+` do.
- `app/api/` — 18 routers; **no help / faq / docs / content endpoints**. (The grep matches in `settings.py`, `corrections.py`, `email_debug.py`, `add_to_session.py` are all keyword-arg `help=...` strings or unrelated function names.)
- `docs/` — has `IMPLEMENTATION.md`, `SPEC.md`, `plans/`, `port-source/`, `audits/`, `parity-audits/` (the dirs `audits/` and `parity-audits/` are currently empty until this file lands). **No user-facing FAQ/help content authored anywhere.** No `frontend/src/content/` directory exists.
- `frontend/public/` — only CSS, fonts, prototype HTML, and a `process-test.html` / `upload-test.html`. No `/help` static content.

False-positive matches worth knowing about:

- `frontend/src/views/UploadView.vue` line 250-254, 403-446: uses CSS class `upload-field__help` and a `help:` keyword on `AI_MODES` options. That is **form-field hint text only**, not a Help Center surface.
- `frontend/src/components/improvements/ImprovDetail.vue` line 61, 78: literal string `"update Help Center articles"` appears inside a **fixture/seed Improvement card body** describing a hypothetical operator follow-up. No code wires to a Help Center.
- The various editor/settings component matches for "help" all refer to local helper/util identifiers (e.g. `editorHelpers.ts`), not user-facing help UI.

Bottom line: **building Help Center for rounds is greenfield.** The expense.vin lesson (upgrade an existing `HelpCenter.vue` in place to 3 tabs) does **NOT** apply — there is nothing to upgrade.

---

## Full route inventory

Source: `frontend/src/router/index.ts` (hash-routed, 14 named routes plus `/` redirect and catchAll).

| Route | View file | Workflow page? | Notes |
|---|---|---|---|
| `#/login` | `LoginView.vue` | No (public auth) | Instrument-Serif aesthetic, no AppHeader rendered (`App.vue:96`). Out of scope for Help Center. |
| `#/dashboard` | `DashboardView.vue` | **Yes (landing/orientation)** | Top-of-funnel surface, KPIs + recent activity. Borderline workflow but heavily used as the user's first stop — strong candidate for an "intro to Rounds" / quickstart help context. |
| `#/sessions` | `SessionsView.vue` | **Yes** | List of all transcript sessions, filter/sort/triage. First step of the day-to-day workflow. |
| `#/s/:id` | `SessionDetailView.vue` | **Yes** | Per-session hub: metadata, stage badges, file list, links into editor/sop/audit/viewer. Multi-step navigation pivot. |
| `#/upload` | `UploadView.vue` | **Yes (heavy)** | The Upload form: file picker, AI-mode selector, prompt config, GCS/Railway backend choice. High help density (already has `upload-field__help` inline hint text). **C2-locked — do not touch.** |
| `#/e/:id` | `EditorView.vue` | **Yes (heavy)** | Main editor: transcript pane, slide rail, discrepancies, decisions, anchors. Long-tail of QWERTY shortcuts. |
| `#/e/:id/sop` | `SopView.vue` | **Yes** | SOP workflow / stage assignment view. Multi-stage gating logic the user needs to understand. |
| `#/e/:id/audit` | `EditorAuditView.vue` | **Yes** | Word Track Changes per-session. Delegates to AuditView. |
| `#/v/:id` | `ViewerView.vue` | Partial (read-only preview) | Preview of final transcript. Workflow-tail; help less critical here. |
| `#/p/:id` | `ProcessingView.vue` | **Yes** | 4-stage processing progress. Users frequently confused about stages — strong help target. |
| `#/improvements` | `ImprovementsView.vue` | **Yes** | Improvements queue / triage. Operator-facing workflow. |
| `#/audit` | `AuditView.vue` | Mixed (system audit log) | Standalone audit-events log; more diagnostic than workflow. Help here would be "what does each event type mean." |
| `#/settings/:section?` | `SettingsView.vue` | **No (settings)** | 12+ sections (Team, Types, Email, Manifest, Diagnostics, PromptTemplates, Deleted, AIModels, AuthUsers, Discrepancy, Export, General, Upload). Settings — not a workflow page — but per-section inline help is highly applicable. |
| `#/gcs` | `GcsView.vue` | No (admin/QA tool) | GCS QA panel. Operator diagnostic tool. |

### Workflow-page classification summary

Recommended **Help Center insertion set** (the "applicable workflow pages"):

1. `/dashboard` — orient/quickstart
2. `/sessions` — list mechanics, filters, triage
3. `/s/:id` — session lifecycle, stages, file mgmt
4. `/upload` — upload backend choice, AI modes, prompt templates *(C2-locked: any Help Center button must be additive to the AppHeader, not embedded in the page body)*
5. `/e/:id` — editor core: keys, discrepancies, decisions
6. `/e/:id/sop` — SOP stage assignment / deadlines
7. `/e/:id/audit` — Word Track Changes
8. `/p/:id` — processing stages and recovery
9. `/improvements` — triage flow

**Excluded:**
- `/login` — public, no header.
- `/v/:id` — read-only; can defer to Phase 3 if requested.
- `/settings/:section?` — settings, not workflow. Per-section inline help is in scope IF the integration pattern supports it without page-body edits.
- `/audit` — diagnostic log; defer.
- `/gcs` — operator tool; defer.

---

## Integration pattern candidates (with tradeoffs)

### 1. Floating "?" button in topbar (per-page, dynamic context) — **RECOMMENDED**

- **File to touch:** `frontend/src/components/AppHeader.vue` (one file), plus a new `frontend/src/components/HelpCenter/` directory for the drawer panel + content.
- **Insertion point:** inside the existing `<div class="app-header__tools">` (currently holds Search, divider, A−, A+). A new `<button class="app-header__icon-btn" data-test-id="topbar-help">?</button>` slots in between the divider and the A− / A+ pair, reusing the **existing `.app-header__icon-btn` class so zero new CSS is required**.
- **Visual delta:** one additional 30px-wide icon button in the topbar tools cluster. No layout changes — `app-header__tools` is flex with `gap: 6px` and right-aligned via `margin-left: auto`.
- **Pixel-parity risk:** **Low.** The topbar is not specced pixel-for-pixel against `port-source/components.jsx::AppHeader` *content* — it's specced against the *class structure*. The React prototype's AppHeader has the same tools cluster but currently shows Search + A−/A+; adding a "?" is the same kind of additive operator-affordance as the build-SHA chip already added at line 105-110. Risk: if MIC's AppHeader has a different button order, we should match MIC's slot ordering, not invent our own.
- **Context source:** read `route.name` from `useRoute()` and key Help Center content off it.
- **Wins:** single point of control; context-sensitive without per-page edits; cleanest rollback (revert one file).

### 2. Side drawer (right-edge slide-in)

- **File to touch:** `frontend/src/App.vue` (mount a new global host like the existing `ToastHost` / `ConfirmHost` / `ModalHost` / `CommandPalette` / `TweaksPanel`), plus the drawer component itself.
- **Visual delta:** zero in default state; full-height right rail when opened (~400px). Modeled after `TweaksPanel.vue`.
- **Pixel-parity risk:** Low when closed (drawer is `display: none` until invoked). The trigger still has to live somewhere — see option 1 for the trigger. So option 2 ≈ option 1's UI shell.
- **Wins:** more screen real estate for long FAQ entries + search results. The `TweaksPanel` is already a proven precedent (same drawer shape) so styling can mirror it (or `.twk-panel` BEM scheme can be reused).

### 3. Modal

- **File to touch:** `App.vue` already mounts `ModalHost.vue`. A new "Help" modal type registered with the modal composable.
- **Visual delta:** zero in default state.
- **Pixel-parity risk:** Low. But modals block the page; for FAQ browsing while keeping the workflow visible, the drawer (option 2) is better UX.
- **Verdict:** acceptable for "Ask AI" if it's invoked as a discrete one-shot interaction, less good for the FAQ browse loop.

### 4. Inline section per page

- **File to touch:** every workflow view file (9 views).
- **Visual delta:** non-zero on every page. Adds a help section to each view body.
- **Pixel-parity risk:** **HIGH — REJECTED.** Violates the zero-unrequested-change mandate. Also UploadView is C2-locked. Listed only for completeness.

### Recommendation

**Option 1 (topbar "?") + Option 2 (drawer)**, combined: the "?" in the AppHeader opens a right-side drawer modeled on `TweaksPanel.vue`. This is the lowest-risk path that is also the most useful: one trigger file (`AppHeader.vue`), one new component tree (`components/HelpCenter/`), zero per-view edits, and a clean revert.

---

## Topbar component analysis

- **File:** `frontend/src/components/AppHeader.vue`
- **Mounted by:** `frontend/src/App.vue:96` — `<AppHeader v-if="!isLogin" />` (rendered on every authenticated route).
- **Current structure** (left→right):
  1. `.app-header__brand` — VIN logo + `transcript.software` wordmark (RouterLink to `/sessions`).
  2. `.app-header__build` — bundle SHA chip (clickable to copy).
  3. Conditional `.app-header__build` amber chip — version-mismatch reload button.
  4. `.app-header__nav` — Primary nav: Dashboard / Sessions / Upload / Improvements / Settings.
  5. `.app-header__tools` (where a Help button would safely go):
     - `.app-header__icon-btn` `topbar-search` — Search (⌘K), uses `Icon name="search"`.
     - `.app-header__divider`.
     - `.app-header__icon-btn--mono` `topbar-font-decrease` — `A−`.
     - `.app-header__icon-btn--mono` `topbar-font-increase` — `A+`.
  6. `.app-header__user` — avatar + name + Logout.

**Safe insertion slot:** inside `.app-header__tools`, between the existing `.app-header__divider` (after Search) and the font-size pair. A `<button class="app-header__icon-btn" data-test-id="topbar-help" title="Help (?)" @click="helpCenter.toggle">?</button>` reuses the existing button class (CSS already exists in `frontend/public/app.css:70-83`) with **zero new styling**. Optionally followed by a second `.app-header__divider` if visual grouping is needed.

**Icon glyph:** the Icon set has no help/question-mark SVG. Two options:
- Use a literal `?` text node (matches `A−` / `A+` mono treatment via `.app-header__icon-btn--mono` — most parity-safe).
- Add a `help-circle` template to `Icon.vue` (single template line, used only here).

**Data-test-id:** `topbar-help` (matches existing convention `topbar-search`, `topbar-font-*`, `topbar-logout`).

---

## Backend content delivery options

**Existing endpoints (any help-related):** none in `app/api/`. The 18 routers cover sessions, upload, audit, sop, segments, corrections, discrepancies, exports, settings, improvements, diagnostics, etc. No content / docs / faq / help router.

### Option A — Static JSON manifest in the bundle

- Ship `frontend/src/content/help/manifest.json` (or `.ts` exporting typed records).
- Schema: `{ routeName: string, entries: [{ id, title, body_md, tags[] }] }`.
- Pros: zero backend work; deploys atomically with the frontend; offline; easy review in PR diff.
- Cons: authors must redeploy to update; not editable by ops via API.
- **Recommended for v1.**

### Option B — Static Markdown bundled via Vite

- Add `frontend/src/content/help/*.md` with frontmatter; use a Vite Markdown plugin.
- Pros: nicer authoring than JSON; supports headings/lists/code.
- Cons: new build dep (Vite Markdown plugin) — small but non-zero.
- **Recommended if FAQ entries are long-form. Likely needed for some entries.**

### Option C — New `/v1/help/*` API serving DB-backed content

- Mirrors expense.vin's rejected `vue-help` TS package + po.vin RAG model decision. **Defer.**
- Only revisit if ops requests editable-without-deploy authoring.

### Option D — Hybrid: bundled markdown + a small `/v1/help/search` endpoint

- Search runs server-side over the same content, useful if entries grow large.
- **Defer to Phase 2.5 or v2.**

### Recommendation

**Option A or B for v1.** Pick B (markdown) if any FAQ entry exceeds a paragraph; A (JSON) if entries are all short. Either way, content lives at `frontend/src/content/help/`. No backend changes in Phase 2 scope.

---

## "Ask AI" surface today

**Existing AI assistant in rounds:** None user-facing. The "AI" surfaces in this codebase are:

- `EditorView.vue` AI flag overlays (a CSS overlay rendering existing flag data, not a chat).
- `UploadView.vue` AI mode selector for processing (`transcript` / `summary` / `key-moments` / `structured-notes` / `custom-prompt`) — this is the pipeline AI, not a help/chat assistant.
- `SectionAIModels.vue` settings page — admin config for which Gemini model is the default.
- Backend `GEMINI_API_KEY` / `gemini-2.5-flash` / `gemini-2.5-pro` are pipeline-processing only (`app/tasks/ai_process.py`, etc.).

No chat assistant, no chatbot widget, no `askAi` route or endpoint. Grep for `askAi|ask_ai|AskAI|assistant|chatgpt|claude|openai` returned 15 files — all are either pipeline AI code, doc files, or migration SQL. None is a user-facing assistant surface.

### Feature flag candidate

- **Name:** `HELP_ASK_AI_ENABLED: bool = False` in `app/config.py` (Pydantic Settings).
- **Pattern match:** mirrors existing default-off flags like `UPLOAD_WATCHDOG_ENABLED` and `SOP_DEADLINE_EMAIL_ENABLED` (both default `False`, both Boolean env-driven).
- **Frontend exposure:** add a single field to whichever endpoint surfaces other public flags (or, if none exists yet, fetch it via the same `/v1/version`-style unauthenticated probe pattern AppHeader already uses). For minimum surface, the flag can be `import.meta.env.VITE_HELP_ASK_AI_ENABLED` and read at bundle time — cheapest and zero backend.
- **Default state:** **disabled, no UI changes**. The Help Center drawer renders FAQ + search; the "Ask AI" tab/section only appears when the flag is on.
- **Naming:** `HELP_ASK_AI_ENABLED` if backend-checked; `VITE_HELP_ASK_AI_ENABLED` if frontend-only. Recommend the frontend-only env-var path for v1 — no backend, no risk.

---

## Risk notes for Phase 2

1. **Pixel-parity vs the React SSOT:** the AppHeader is a port of `docs/port-source/components.jsx::AppHeader`. Adding a "?" button is *additive*. To maintain SSOT fidelity, the change should be mirrored in the React prototype OR explicitly documented as "rounds-only additive operator affordance" in the parity log — same pattern as the build-SHA chip (`app-header__build`) already on lines 105-110.
2. **No new CSS classes:** reuse `.app-header__icon-btn` (and `--mono` if using text glyph) so no `app.css` edits are needed. Zero risk of breaking other surfaces.
3. **Drawer overlap with TweaksPanel:** `TweaksPanel.vue` already sits as a right-side drawer with the `.twk-*` BEM scheme. Help drawer should follow the same shape and z-index ordering to avoid collision. Verify open-state mutual exclusivity (closing Tweaks before opening Help, or stacked but offset).
4. **C1 / C2 locks:** UploadView (C2) and pipeline files (C1) must not be edited. The topbar-button + drawer pattern already satisfies this — no per-view edits. Avoid any temptation to "add a help link inline in UploadView."
5. **Content delivery is greenfield:** there is no existing `frontend/src/content/` directory. Creating it for help content is fine; just keep it under `src/content/help/` to avoid colliding with future feature content directories.
6. **Search scope creep:** "search" + "context filtering" are easy to over-engineer. For v1, a simple substring filter over the bundled manifest (or markdown frontmatter `tags`) is sufficient. Defer fuzzy/embedding search to a future phase.
7. **"Ask AI" must not regress without the flag:** the default-off path must render *exactly* the same UI as if the feature didn't exist. Verify with a visual diff against the no-flag bundle before shipping.

---

## Rollback procedure

The Help Center is designed to be a **single-feature additive change**. Rollback is mechanical:

1. **Revert the AppHeader button:** delete the new `<button data-test-id="topbar-help">` element in `frontend/src/components/AppHeader.vue` (and its handler import). The button reuses existing CSS so no style cleanup is needed.
2. **Unmount the drawer:** delete the `<HelpCenterDrawer />` line in `frontend/src/App.vue` (alongside the existing `<ToastHost />` etc.). Remove the import.
3. **Delete the component tree:** `rm -rf frontend/src/components/HelpCenter/`.
4. **Delete the content tree:** `rm -rf frontend/src/content/help/`.
5. **Delete the feature flag (if used):** remove `HELP_ASK_AI_ENABLED` from `app/config.py` (or the `VITE_HELP_ASK_AI_ENABLED` Railway env var). No migration to revert — the flag has no DB state.
6. **No backend rollback needed** — Phase 2 adds zero backend routes.
7. **CSS rollback:** none. No CSS was added.
8. **Verify:** `npm run build` clean, `/dashboard` renders identical to pre-Phase-2 bundle (visual diff), data-test-id `topbar-help` no longer in DOM.

Estimated rollback time: **< 10 minutes** (one PR revert if the change shipped as a single commit; faster if reverting only the `AppHeader.vue` + `App.vue` mounts and leaving the unused component tree in place until a follow-up cleanup).

---

## Files referenced (absolute paths)

- `C:\Users\JohnDean\rounds\frontend\src\App.vue`
- `C:\Users\JohnDean\rounds\frontend\src\components\AppHeader.vue`
- `C:\Users\JohnDean\rounds\frontend\src\components\TweaksPanel.vue`
- `C:\Users\JohnDean\rounds\frontend\src\components\shared\Icon.vue`
- `C:\Users\JohnDean\rounds\frontend\src\router\index.ts`
- `C:\Users\JohnDean\rounds\frontend\src\views\*.vue` (14 files)
- `C:\Users\JohnDean\rounds\frontend\public\app.css` (esp. `.app-header__*` rules around lines 60-95)
- `C:\Users\JohnDean\rounds\app\config.py` (feature-flag location pattern: `UPLOAD_WATCHDOG_ENABLED`, `SOP_DEADLINE_EMAIL_ENABLED`)
- `C:\Users\JohnDean\rounds\app\api\` (18 routers — none help-related)
- `C:\Users\JohnDean\rounds\docs\port-source\components.jsx` (React SSOT for AppHeader)
- `C:\Users\JohnDean\rounds\docs\plans\2026-05-18-002-parity-remediation-phases.md` (existing in-repo "Phase 2 — Settings persistence"; note the naming collision)
