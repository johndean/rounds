# VIN Transcript Software — Implementation Reference (Zero-Gap)

**Date:** 2026-05-17
**Build:** v4.0.0-ssot-r2
**Entry:** `Transcript Software v4.html`
**Scope:** Comprehensive implementation reference for the design system. Every surface, token, component, interaction, and state transition documented so a developer can rebuild the prototype with zero ambiguity.

---

## 1. Layout philosophy

Full-width canvas. No `max-width` on body or page wrappers. Every page is three vertical bands:
- TopBar (sticky chrome, 50px)
- Optional page-specific strips (filters, stage stepper, breadcrumbs)
- Full-width content area

`scrollbar-gutter: stable` + `overflow-y: scroll` on `<html>` to prevent horizontal jump when navigating between sections of different heights.

## 2. Six layout patterns

| Pattern | Surfaces | Structure |
|---|---|---|
| A — Hero + dense grid | Upload | Centered intent block (max 680-900px) + grid below |
| B — Single dense table | Sessions, Improvements | Header strip → tabs → CSS-grid table with fixed pixel columns |
| C — 2-column split | Improvements detail, Discrepancies | Master list scrolls; detail `position: sticky` |
| D — 3-column workspace | Editor (all 4 tabs) | leftCol + resizer + center + resizer + rightCol; widths persist to localStorage |
| E — Sidebar + content | Settings | 240px fixed sidebar + content fills the rest |
| F — Operator dashboard | Dashboard | Stacked zones: KPI strip → Queue → Pipeline → Recent → SLA → 3-col widgets × 2 rows |

## 3. Site chrome

**TopBar** (`components.jsx` AppHeader):
- Navy (#002855) sticky band, 50px tall
- Brand: VIN logo (light variant) + `TRANSCRIPT.SOFTWARE` mono uppercase
- Build pill: `v4.0.0-ssot-r2` mono decorative
- Primary nav (5 links, 12px uppercase, .06em letter-spacing): Dashboard · Sessions · Upload · Improvements · Settings
- Right cluster: ⌘K Search (opens command palette modal) · A−/A+ font controls · `nominal` status pill
- User: avatar gold (KS) + name + Logout (confirm dialog → toast)

**StatusBar** (editor only, sticky bottom 30px navy):
- WS connected indicator · autosave timestamp · longtasks/min · heap · build version
- Toggleable via Tweaks panel

## 4. Token system (`colors_and_type.css`)

**Surface tokens** (light + dark variants via `[data-theme]`):
`--surface-bg`, `--surface-card`, `--surface-muted`, `--surface-nav`, `--fg1`, `--fg2`, `--fg-on-dark`, `--fg-link`, `--border-subtle`

**Brand palette:**
`--color-navy` #002855, `--color-steel` #4D6995, `--color-green` #007D61, `--color-teal` #0097A9, `--color-blue` #0861CE, `--color-red` #C54644, `--color-amber` #B75D04, `--color-gold` #B9975B, `--color-light-steel` #DDE5ED, `--color-warm-light` #E8E3D2

**Slide-accent palette** (`SLIDE_PALETTE` JS array, `i % 10` indexed, O(1) Map lookup):
`#2563eb · #7c3aed · #059669 · #d97706 · #dc2626 · #0891b2 · #6366f1 · #ea580c · #0d9488 · #be185d`

Applied to: slide rail row tints, segment 3px left stripe, slide-chip dots, AI/STT/Discrepancies/Audit segment chrome, minimap rects, ActiveSlide card border + gradient, Session Detail timeline strip + slide-assignment list + per-segment confidence dots.

**Typography:**
- `--font-family` 'ProximaNova', Helvetica Neue, Arial
- `--font-mono` 'Courier New', ui-monospace
- Weights: 300 / 400 / 500 / 800
- Scale: 0.64rem → 3.815rem at 1.25 ratio

**Spacing:** 1.5× ratio, `--space-1` (4px) through `--space-9` (81px)
**Radii:** sm 4px · md 8px · lg 16px · pill 999px
**Shadows:** 4-tier `--shadow-sm/md/lg/xl`
**Motion:** 150ms / 300ms / 500ms; easing `cubic-bezier(0.16, 1, 0.3, 1)`

## 5. Routes (13 total, hash-based)

| Hash | File | Pattern | Purpose |
|---|---|---|---|
| `#/dashboard` | dashboard.jsx | F | Operator overview |
| `#/sessions` | sessions.jsx | B | Sessions list (supports `?stage=<id>` + `?ai=<id>` + `?f=<filter>` query params) |
| `#/s/:id` | session-detail.jsx | mixed | Session detail (homepage for one session) |
| `#/upload` | upload.jsx | A | New-session upload |
| `#/e/:id` | editor.jsx | D | Editor (4 tabs: AI · STT · Discrepancies · Audit) |
| `#/e/:id/sop` | sop.jsx | mixed | SOP workflow with KPIs + stepper + stage detail + approvals |
| `#/e/:id/audit` | audit.jsx | mixed | Word Track Changes ledger |
| `#/v/:id` | viewer.jsx | mixed | Export preview document |
| `#/p/:id` | processing.jsx | mixed | 8-hop ingestion pipeline trace |
| `#/improvements` | improvements.jsx | C | Master/detail with 5-step wizard |
| `#/settings` | improvements.jsx + settings-pages.jsx | E | 12-section settings |
| `#/audit` | audit.jsx | mixed | Standalone audit ledger |
| `#/gcs` | processing.jsx | mixed | GCS QA G1-G14 |

## 6. Editor (the heaviest surface)

**Topbar stack:**
1. Breadcrumb: `Sessions / {code} / Editor`
2. Mini SOP stepper: 8 stages (dot + name) with current/done/pending color states + AI-ready chip
3. Big title row: mono session code (22px/800) + Result · Undo · Redo · Preview buttons (Preview → `/v/:id`)
4. Sub-row: `{n}/{n} aligned` (green) · Find & Replace (opens modal) · current stage chip · Workflow · Audit · Download (dropdown menu with 4 formats)
5. FLAGGED row: 12 chip filters (Medication/Name/Number/Date/Terminology/Filler/Punctuation/Style/Other · Uncertain/Drift/Low-conf) with counts

**Tabs:** AI Transcript · STT Reference · Discrepancies · Audit (each with numeric count badge + flag-color legend at right)

**3-column body grid** (`grid-template-columns: {leftW}px 6px minmax(0,1fr) 6px {rightW}px`):
- Resizers: 6px hover-navy, drag-active class on `<body>` switches cursor globally
- Widths persist to localStorage keys `mic_left_w` / `mic_right_w`

**Left column:**
- VideoStrip (16:9 poster, navy gradient, slide metadata, scan-line overlay, center play button when paused, HUD with action icons + timecode)
- Mini audio bar (38px): ▶ · 1× speed · green CC toggle · scrubber with chapter ticks · timecode
- Slide rail head: title + Focus/Filter segmented control (centered, navy pill on active) + Clear focus/Show all button when `focusedSlideId` set
- Slide cards: 40×30 accent-gradient thumbnail + 2-line clamped title + segment count badge
- 3-branch nav style: active (full accent bg + 100% border + 3px inset stripe) / empty (0.55 opacity + 33% stripe) / normal (12% bg + 44% border + 100% stripe)

**Center pane — AI Transcript:**
- Segment cards with slide-chip header (accent dot + slide number + title) + Edit / Reassign / Speaker inline actions
- Body row with 86px gutter (time + speaker pill) + main text with karaoke
- Inline edit replaces segment body: full-width textarea + Tiptap toolbar (B I U • 1. ↩ ↪ S 🟡 🟢 🔵 🌸 link bar-chart) + Cancel/Save; history stack via state; toolbar `onMouseDown preventDefault` so textarea focus + selection preserved across button clicks
- Inline reassign: grid of pill tiles for every slide (accent dots, current slide highlighted green)
- Inline speaker: card grid (avatar/name/role) for all speakers
- Inline poll/chat anchor blocks (green/gold-bordered cards) with their own Edit/Remove

**Center pane — STT Reference:**
- Same shell + same per-slide accent stripes
- Mono lowercase text, token-time superscripts, drift wavy underlines, filler chips
- Read-only banner with §9/L2 invariant citation

**Center pane — Discrepancies:**
- Synced 2-column grid (single shared scrollbar; paired AI+STT rows align via grid)
- All / Flagged / Meaningful filter pills (counts derived after focus-mode filter applies)
- Focus-mode banner appears when slide focused
- Each AI side row has full segment chrome; STT side hides header via `visibility: hidden` to preserve row height

**Center pane — Audit:**
- Decisions/Ledger toggle on toolbar
- Decisions: per-correction cards with time range + edited / inserted-chat / slide-reassigned / speaker-change / annotation pills + actor + WAS/NOW panels (red strike + green highlight)
- Ledger: flat correction-lineage table

**Right rail:**
- ActiveSlide card: 4px left border (slide accent), accent gradient slide preview, segment count, mini SVG timeline
- Rail tabs: Admin · Chat · Polls
- Admin: Timeline minimap (single SVG, N rects) + segments-on-this-slide list (accent border-left) + Instructor card + IIL signals
- Chat: per-slide dividers, draggable rows for unplaced messages, "PLACED · Slide N" pill + strike-through for placed
- Polls: drag-or-click placement; placed polls render inline in transcript as green-bordered anchor segments with full bar charts

## 7. Session Detail (`/s/:id`)

- Breadcrumb: Sessions / code
- Header strip: Content-ready chip + code chip + mono title + INTERIM line + right side: to-review chip + alignment chip + Workflow / Audit / Open Editor buttons
- 3-column grid (280 / 1fr / 320):
  - **Left** — session meta card: code, mono title, taxonomy chips, 4 compact Downloads buttons (.docx/.srt/.txt/.zip)
  - **Center** — 5-KPI grid (Segments / Avg Confidence / Words / Coverage / Duration), 2-card row (Alignment 95% + AI Mode card), Session Files attention card (4 rows with PRESENT/MISSING pills + Update/Add)
  - **Right** — Stage Assignments card (per-stage row with reassign pencil) + Publishing Links chips (6 destinations)
- Full-width Timeline card: SVG strip with per-slide accent rectangles + 0:00-duration axis
- 3-widget row: Segment Confidence list (1-31) + Slide Assignment list + Review Queue

## 8. SOP Workflow (`/e/:id/sop`)

- Breadcrumb + session identity header (mono code, title, presenter/recorded/duration/segments/words/attendees)
- 5-KPI strip: Current Stage badge · Assigned to (avatar+name+role) · Dwell in stage (amber if > 48h) · Acceptance checks N/M (blocker count) · Pipeline progress %
- 8-stage stepper with stage-owner avatar on each step
- 2-pane grid (1.6/1):
  - **Stage detail card** — title + CURRENT/COMPLETE/PENDING pill + Prev/Next paging · check rows with by-actor footnote · advance-row (green is-ready / amber is-blocked) with confirm dialog
  - **Side rail** — Stage owner card (40px avatar + name + role + Reassign/Ping + Notify-on-entry/SLA/Status meta) · Approvals card (append-only signatures) · Quick actions card
- 2-pane footer (1.4/1): Stage Transition History (timestamp + from→to badges + note + actor card per row) + SOP Invariants card (L5 / §18.14 / §15.6 / ADR)

## 9. Dashboard (`/dashboard`)

- Date eyebrow + greeting + dual-pipeline lead
- 6-KPI strip with inline SVG sparklines: AI Sessions / SOP Sessions / Segments / Artifacts / CMS Published / Improvement RQs
- Your Queue: 3 cards (code + stage badge + title + segs/aligned/due + status + Open ›)
- Pipeline: 2 horizontal rails
  - **Pipeline 1 — AI Processing** 7 stages (`upload/transcribe/normalize/align/fuse/ready/failed`) — each circle is a `<button>` → `navigate("/sessions?ai=<id>")`
  - **Pipeline 2 — SOP Control Layer** 8 stages (`prep/copy_draft/medical/copy_final/cms/captions/qa/complete`) with ATTN indicator on Medical Review — each circle → `navigate("/sessions?stage=<id>")`
- System overview: 7d/30d/90d/All tabs + 6-KPI strip with sparklines + SLA-by-stage grid (8 cells, dwell-vs-target bars, breach in red, on-target in green)
- 3-column widget row: SOP Age Alerts / Correction Hotspots (bar rows) / Storage Top Sessions (bar rows)
- Bottom 3-column row: Jobs Queue (5 task types, ok/err counts) / Storage Breakdown (5 categories with size bars) / Assignment Coverage (3 ops with load/cap bars + Unassigned pool with claim → link)

Sessions list reads `?stage` / `?ai` / `?f` query params and shows an active-filter chip (`SOP: Medical review ×`) which clears via the × to return to unfiltered view.

## 10. Settings (12 sections via E pattern)

240px sidebar + content. Every section uses `<SettingsHeader title lead headerCta>` + inline content. Drill-into sub-routes return via `← Settings` link.

| Section | Behavior |
|---|---|
| **General** | Org name input · Default locale select · Time zone select · Save |
| **Team & roles** | 2-pane: People list (10) with Edit/Delete + Add prompt · Groups list (5) with removable member chips + Add member dropdown + new-group input |
| **Types & stage defaults** | 2-pane: Type list (17) clickable + Remove · Right: Stage Assignees Matrix for selected Type (8 stage rows × assignee dropdown × Email checkbox) + Save matrix |
| **AI models** | Default model select (8 Gemini variants) |
| **Upload & storage** | Upload method select (Railway / GCS) with paragraph |
| **Discrepancy classification** | Backend select (Gemini Dev / Vertex AI) + Classification model select + callout |
| **Export** | Include key points toggle + Word Macro download card (real .zip blob) |
| **Prompt templates** | Drill: Catalog (5 categories) + AI Prompt Templates section · "+ New Template" form with Type/Name/Icon/Description/Category + IIL Configuration block (Filler/Tone/Terminology/Rewrite + Structure/Key-points toggles) + System Prompt textarea |
| **Session manifest** | Documentation: 8-row Expected Fields table + filename conventions |
| **Email** | Drill: Email Template Builder · 8 stage tabs · per-Type EDITING select · Subject + HTML Body (full width) + Plain Text · Variables palette (6 categories) · Live preview with VIN Transcript Software branding (navy header + body card + footer) · Save/Revert/Send test |
| **Diagnostics** | Two drill cards: Phase 0 telemetry → Test Email · Diagnostics (5 sections: SMTP Config / Connectivity Test / Send Test Email / Copy diagnostic bundle / Recent Attempts / Event Log) · G1-G14 → GCS Pipeline QA (drilled inline) |
| **Deleted sessions** | Recovery list (code / title / deleted-date / actor / N-of-30 days) + Restore + Purge per row |

## 11. Email templates — VIN Transcript Software branding

All 8 stage defaults rebranded from "Media Intelligence Console" / `[MIC]` to "VIN Transcript Software" / `[VIN]`:

- Header bar: navy (#002855) + "VIN TRANSCRIPT SOFTWARE" uppercase eyebrow (#B1C9E8) + stage subject (white, 18px/800)
- Body card: white bg + 14px ProximaNova + greeting + body + WHAT TO DO list + navy CTA button
- Footer: muted bg + "Sent by VIN Transcript Software · Reply to this email with questions"

Each stage has unique body content per workflow purpose (Prep / Copy edit draft / Medical review / Copy edit final / CMS publish / Captions upload / QA / Published).

## 12. Wiring infrastructure (`wiring.jsx` + `wiring.css`)

- **Toast** — `toast.push(msg, {tone, action, duration})`, 4 tones, bottom-right stack
- **Confirm** — `confirm.open({title, body, danger, confirmLabel}) → Promise<bool>`
- **Modal** — `modal.open(<Content />)` for Find&Replace, Suggest Improvement, Segment Edit, Command Palette
- **Mock API** — `api.*` stubs return `Promise.resolve(mock)` so swap-to-real is one-line
- **Audit log** — `auditLog.log(actor, kind, summary, details)` writes a real event
- **`wired` namespace** — `exportCSV / download / logout / fontSize / openCmdK / openFind / openSuggestImprovement / openSegmentEdit / advanceStage / deleteRow / saveSetting / testEmail / openGCS / cancelIngestion / resolveCheck / reassignStage / reassignSegment / toastInfo`
- **`data-test-id`** on every wired button

**Global keyboard shortcuts:** ⌘K opens command palette · ⌘F opens Find&Replace when in editor

## 13. Improvements (`/improvements`)

- Status tabs: All / Pending / Under Review / Approved / In Progress / Rolled Out / Declined / Archived
- Master table: checkbox · TITLE+url · STATUS pill · RISK pill · PRIORITY · SUBMITTED · Del action
- Search + Suggest Improvement primary
- 5-step wizard (Overview / Requirements / Implementation / Testing / Review):
  - **Overview** — 2-col metadata grid + Description
  - **Requirements / Implementation / Testing** — eyebrow + Regenerate button + monospace `<pre>` markdown
  - **Review** — Expand All · Copy to Clipboard · Export (.md) + 3 collapsible accordions + ADMIN CONTROLS (Status / Risk / Target Version / Admin Notes) + Save Changes
- Suggest Improvement modal: Title / Description / Type / Priority / Area / Security checkbox / Submit (blue #2563eb)

## 14. Tweaks panel

- **Appearance** — Theme (light/dark) · Brand (VIN/VSPN) · Density (comfortable/compact)
- **Editor** — Slide-rail mode (focus/filter) · AI flag overlays toggle · Debug status bar toggle
- **Quick navigate** — 11 buttons for every route

## 15. Closures: F1 / F2 / F3 (Section 11/12 audit)

| # | Closure |
|---|---|
| F1 | Focus mode "Clear focus" / "Show all" button added to slide-rail header |
| F2 | Mode-switch clears `focusedSlideId` on every transition, wired across all 4 editor tabs |
| F3 | Timeline minimap renders in both Active Slide card AND Admin tab |

## 16. Slide-accent color rollout — 18 production gaps closed

P1 palette as token system · P2 3-branch nav logic · P3-P4 AI tab stripe + chip dot · P6-P8 cross-tab consistency · P9 right-panel + minimap accent · P10 Active Slide card border/tint · P13 slide-rail 3-branch tint · P17 minimap perf (single SVG) · P18 precomputed Map lookup. All closed.

## 17. All 78 functional buttons wired

Every previously-non-functional button now fires confirm/toast/modal/audit:
- TopBar (4): search/⌘K · A−/A+ · Logout
- Sessions list (3): Export CSV · row delete (undo) · sort
- Session Detail (20): file actions · stage reassign · publishing chips · download formats
- Editor topbar (6): Result · Undo · Redo · Preview · Find&Replace · Download dropdown
- Editor segments (3 × N): Edit (inline) · Reassign (inline) · Speaker (inline)
- Audit (3): Export ledger · Full WTC · Export JSONL
- Upload (6): × Remove per attachment · Process →
- SOP (3+N): Resolve · Advance (confirm) · Prev/Next
- Improvements (6+N): Suggest · Del · wizard steps · Back/Next · Save
- Settings (~24): every section + card CTA
- Processing (3): Open GCS · Download raw STT · Cancel ingestion
- Dashboard (5+15): Filters · +5 overflow · time tabs · claim → · **pipeline circles (15 → filtered sessions)**
- Viewer (2): Download SRT · Edit

## 18. File map

| File | LOC | Purpose |
|---|---|---|
| `Transcript Software v4.html` | ~35 | Entry — loads pinned React + Babel + all scripts |
| `colors_and_type.css` | ~175 | Foundation tokens |
| `app.css` | ~3,000 | Structural styles for all surfaces |
| `wiring.css` | ~100 | Toast / confirm / modal chrome |
| `settings.css` | ~280 | Settings inline forms + sub-pages |
| `components.jsx` | ~600 | AppHeader / Icon / StageBadge / Avatar / Link / SegmentText / SLIDE_PALETTE |
| `wiring.jsx` | ~600 | Toast / Confirm / Modal / mock API / auditLog / FindReplaceModal / SuggestImprovementModal / SegmentEditModal / CommandPalette / wired namespace |
| `data.jsx` | ~900 | Fixtures: SPEAKERS / SLIDES / SEGMENTS / CHAT / POLLS / SOP_STAGES / SESSIONS / DISCREPANCIES / CORRECTIONS / IMPROVEMENTS |
| `tweaks-panel.jsx` | ~570 | Tweaks shell + host protocol |
| `dashboard.jsx` | ~450 | Dashboard |
| `sessions.jsx` | ~180 | Sessions list with `?stage` / `?ai` / `?f` query params |
| `session-detail.jsx` | ~320 | Session detail |
| `upload.jsx` | ~370 | Upload flow |
| `editor.jsx` | ~1,500 | Editor (4 tabs + VideoStrip + SlideRail + TranscriptPane + AnchorBlock + STTPane + DownloadMenu) |
| `audit.jsx` | ~420 | DiscrepanciesPane / DecisionCard / AuditLedger / standalone audit |
| `sop.jsx` | ~270 | SOP workflow |
| `viewer.jsx` | ~170 | Preview/export document mock |
| `processing.jsx` | ~140 | Processing trace + standalone GCS QA |
| `improvements.jsx` | ~650 | Improvements list + 5-step wizard · Settings router |
| `settings-pages.jsx` | ~860 | All 12 Settings sections + EmailBuilder + EmailDebug + GCSDebug + prompt-templates catalog + new-template form |
| `app.jsx` | ~150 | Hash router + theme/brand wiring + global keyboard handlers |

**Total: ~12,000 LOC across 20 files** (16 JS modules + 4 CSS files + 1 HTML).

## 19. Boundary — what this build does NOT do

- No real backend (all api calls mock)
- No real WebSocket (status bar decorative)
- No real audio playback (video poster static)
- No real Tiptap (segment edit is textarea + toolbar)
- No real LLM calls
- No real GCS uploads
- No real file exports (downloads emit text blobs with right extension)
- No real auth (Logout toasts)
- No real i18n (English-only)
- No real virtualization (all segments inline)

This is design fidelity, not production. Every UX surface is shipped. Every interaction wires to toast/confirm/modal/audit primitives so swapping in real backends is mechanical.

## 20. Implementation checklist

1. Build `colors_and_type.css` tokens first
2. Build TopBar (AppHeader) — once it's done every screen has chrome
3. Build wiring infrastructure (toast/confirm/modal/api/auditLog)
4. Build primitives (.btn, .chip, .card, .mono)
5. Build editor (heaviest surface — 3-column resizable + 4 tabs + inline editing)
6. Build Settings sidebar + 12 sections (E pattern)
7. Build Session Detail (mixed) and Sessions list (B pattern)
8. Build Dashboard (F pattern) and wire pipeline circles to sessions filters
9. Build SOP workflow + Audit ledger
10. Build Improvements wizard (C pattern)
11. Build Upload (A pattern), Viewer (export mock), Processing (8-hop trace), GCS QA

## 21. Net status

**Zero-gap against operator-facing requirements.** Every screen shipped. Every wired button works. Every inline edit functional. Slide-accent system rolled out everywhere. Filter/Focus mode wired across AI / STT / Discrepancies / Audit tabs. Email templates VIN-branded. Dashboard pipeline circles navigate to filtered Sessions list. Settings sub-routes (Email Builder, Test Email Diagnostics, GCS QA, Prompt Templates) all drill in-place via `← Settings` back navigation.

Backend / perf items (original Sections 1-7, 10, 14.A.D-14.G.D from the source audit) remain backend execution work and are unaffected by the design layer.

This document is the single source of truth for rebuilding the prototype.
