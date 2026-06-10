# Viewer / Preview Screen

Route: `#/v/:id` — registered in [frontend/src/router/index.ts:37](../../frontend/src/router/index.ts#L37) as the `viewer` route (`props: true`, so `:id` is passed to the view as the `id` prop). Implemented by [frontend/src/views/ViewerView.vue](../../frontend/src/views/ViewerView.vue).

## Purpose

Read-only "Export Preview" of a finished session. It renders the per-slide transcript (speaker label + segment text grouped under each slide), a list of export-format cards (Word / Captions / Plain Text / Word Macro), a publishing checklist, and an optional "Key Points" section. The page exists to let an operator review the assembled transcript before exporting/publishing.

Important: the export buttons and publishing links are **not wired to real downloads or navigation**. See Actions / States below.

## User Types

Any authenticated user. There is no role gate on this route. The router only enforces (a) `meta.public` bypass and (b) auth presence; everything not marked public requires `auth.isAuthenticated` ([frontend/src/router/index.ts:53-67](../../frontend/src/router/index.ts#L53)). The `adminOnly` guard is applied only to `/admin/help`, not to this route. NOT VERIFIED IN CODE: any per-session ownership or read permission check on the viewer.

## Entry Points

- The Editor links to the Viewer. The Viewer itself links back to the Editor via `RouterLink :to="`/e/${session.id}`"` ([frontend/src/views/ViewerView.vue:126](../../frontend/src/views/ViewerView.vue#L126)).
- Direct hash navigation to `#/v/:id`.

NOT VERIFIED IN CODE: an explicit "open preview / viewer" link from the Sessions list or Dashboard (this view file does not declare its inbound links; only its outbound Editor link is present in the template).

## Navigation Paths

- Outbound: "Editor" button → `/e/{session.id}` (only rendered when `session` is non-null) ([frontend/src/views/ViewerView.vue:126](../../frontend/src/views/ViewerView.vue#L126)).
- The publishing-checklist rows are anchors with `href="#"` whose click handler calls `e.preventDefault()` and shows a toast — they do not navigate ([frontend/src/views/ViewerView.vue:97-103](../../frontend/src/views/ViewerView.vue#L97), [151](../../frontend/src/views/ViewerView.vue#L151)).

## Components

- `<main class="preview-page" data-screen-label="Viewer / Preview">` root ([frontend/src/views/ViewerView.vue:107](../../frontend/src/views/ViewerView.vue#L107)).
- `Icon` shared component ([frontend/src/components/shared/Icon.vue](../../frontend/src/components/shared/Icon.vue)), used for `chevron-left` and `download` glyphs.
- Identity header `.preview-id` — code, title, presenter "interim" line, and taxonomy chips ([frontend/src/views/ViewerView.vue:110-117](../../frontend/src/views/ViewerView.vue#L110)).
- Toolbar `.preview-toolbar` — section title, an "Include key points section" checkbox bound to `includeKeyPoints`, and the Editor link ([frontend/src/views/ViewerView.vue:119-128](../../frontend/src/views/ViewerView.vue#L119)).
- Export-format cards `.preview-formats` / `.preview-format` — rendered from the hardcoded `downloads` array (4 entries: `.docx`, `.srt`, `.txt`, `.zip`) ([frontend/src/views/ViewerView.vue:71-76](../../frontend/src/views/ViewerView.vue#L71), [130-145](../../frontend/src/views/ViewerView.vue#L130)). Each card has `data-test-id="preview-{ext}"`.
- Publishing checklist `.preview-checklist` — rendered from the hardcoded `publishing` array (7 rows: Zoom recording, Slides, Podbean, VINcast, Intranet, Message board, Session page), each with `href: '#'` ([frontend/src/views/ViewerView.vue:78-86](../../frontend/src/views/ViewerView.vue#L78), [147-155](../../frontend/src/views/ViewerView.vue#L147)).
- Slide blocks `.preview-slides` / `.preview-slide` — one `<article>` per slide, titled "Slide {index+1}", with segments grouped under it ([frontend/src/views/ViewerView.vue:157-175](../../frontend/src/views/ViewerView.vue#L157)). Segment paragraphs print `**{speakerLabel}:** {text}` with literal markdown asterisks in a `<strong>` ([frontend/src/views/ViewerView.vue:168](../../frontend/src/views/ViewerView.vue#L168)).
- Key Points block `.preview-keypoints` — only shown when `includeKeyPoints` is checked ([frontend/src/views/ViewerView.vue:177-182](../../frontend/src/views/ViewerView.vue#L177)).
- Footer line — "End of preview · {N} segments · {N} slides · build {sha}" ([frontend/src/views/ViewerView.vue:184-186](../../frontend/src/views/ViewerView.vue#L184)).

This view has **no route-specific child component files** — only the shared `Icon`. The `downloads` and `publishing` lists are static literals in the script.

## Actions

- **Toggle "Include key points section"** — `v-model="includeKeyPoints"` checkbox; toggles visibility of the Key Points block. Local state only ([frontend/src/views/ViewerView.vue:122-125](../../frontend/src/views/ViewerView.vue#L122), [177](../../frontend/src/views/ViewerView.vue#L177)).
- **Click an export-format card** → `downloadFile(ext)` ([frontend/src/views/ViewerView.vue:91-96](../../frontend/src/views/ViewerView.vue#L91)). This does **not** download anything; it pushes a warn toast: "`{EXT}` export not yet wired — ships with Phase 10 exports endpoint." Marked in code as PARTIALLY IMPLEMENTED (the comment at [88-90](../../frontend/src/views/ViewerView.vue#L88) states the real export endpoint is deferred to Phase 10).
- **Click a publishing-checklist label** → `openPub(p, $event)` ([frontend/src/views/ViewerView.vue:97-103](../../frontend/src/views/ViewerView.vue#L97)). Prevents default and pushes a warn toast: "`{label}` link not yet wired — publishing links land with Phase 10." PARTIALLY IMPLEMENTED.
- **Click "Editor"** → navigates to `/e/{session.id}` (real navigation).

Toasts are pushed via the `toast` composable ([frontend/src/composables/useToast.ts](../../frontend/src/composables/useToast.ts)).

## States

- **Loading** — while `loading` is true a centered "Loading preview…" div is shown; the rest of the page is in a `<template v-else>` ([frontend/src/views/ViewerView.vue:108-109](../../frontend/src/views/ViewerView.vue#L108)).
- **Loaded with data** — identity header + export cards + checklist + slide blocks render.
- **Session not found** — `sessionsApi.get` is wrapped in `.catch(() => null)`, so on failure `session` stays null and the title falls back to "Session not found"; the code falls back to `props.id` ([frontend/src/views/ViewerView.vue:37](../../frontend/src/views/ViewerView.vue#L37), [111-112](../../frontend/src/views/ViewerView.vue#L111)). The Editor link is hidden when `session` is null ([126](../../frontend/src/views/ViewerView.vue#L126)).
- **Key Points expanded** — `includeKeyPoints === true` reveals a static explanatory paragraph (no real extracted key points are fetched) ([frontend/src/views/ViewerView.vue:177-182](../../frontend/src/views/ViewerView.vue#L177)).

## Empty States

- **No slides** — when `slides.length === 0`, a centered message "No slides yet — ingest pipeline pending." renders inside `.preview-slides` ([frontend/src/views/ViewerView.vue:172-174](../../frontend/src/views/ViewerView.vue#L172)).
- **Slide with no audio** — for each slide whose `segmentsBySlide` list is empty, the body shows "( no audio )" ([frontend/src/views/ViewerView.vue:166](../../frontend/src/views/ViewerView.vue#L166)).
- **Key Points** — the Key Points body text itself states it is "Empty until the session is processed." ([frontend/src/views/ViewerView.vue:179-181](../../frontend/src/views/ViewerView.vue#L179)).

## Error States

IMPLEMENTATION NOT FOUND — there is no dedicated error branch in the template. Every fetch in `onMounted` is individually wrapped in `.catch()` returning a benign fallback (`null` / `[]`), so failures degrade silently into the empty/not-found states above rather than surfacing an error message ([frontend/src/views/ViewerView.vue:36-41](../../frontend/src/views/ViewerView.vue#L36)). There is no toast or banner on fetch failure.

## Loading States

Single boolean `loading` (initialized true, set false in the `finally` of `onMounted`) gates the whole page behind the "Loading preview…" placeholder ([frontend/src/views/ViewerView.vue:30](../../frontend/src/views/ViewerView.vue#L30), [48-50](../../frontend/src/views/ViewerView.vue#L48)). There is no per-section skeleton; all four fetches resolve via `Promise.all` before the page paints ([frontend/src/views/ViewerView.vue:36-41](../../frontend/src/views/ViewerView.vue#L36)).

## Permissions

JWT presence only. The global `router.beforeEach` redirects unauthenticated users to `/login` ([frontend/src/router/index.ts:59-62](../../frontend/src/router/index.ts#L59)). This route is **not** flagged `adminOnly` and has no `LEGACY_ADMIN_EMAIL` gate. Per repo reality, role-based authorization is scaffold-only and not wired into this screen. NOT VERIFIED IN CODE: any per-session access control.

## Connected APIs

All issued once in `onMounted` via `Promise.all` ([frontend/src/views/ViewerView.vue:34-51](../../frontend/src/views/ViewerView.vue#L34)):

- `GET /v1/sessions/{id}` via `sessionsApi.get` ([frontend/src/services/api.ts:139-140](../../frontend/src/services/api.ts#L139)) → `SessionSummary` ([frontend/src/services/api.ts:37](../../frontend/src/services/api.ts#L37)).
- `GET /v1/sessions/{id}/slides` via raw `http<SlideRow[]>` (no wrapper in `api.ts`; the local `SlideRow` interface is declared in the view at [frontend/src/views/ViewerView.vue:23](../../frontend/src/views/ViewerView.vue#L23)) ([frontend/src/views/ViewerView.vue:38](../../frontend/src/views/ViewerView.vue#L38)).
- `GET /v1/sessions/{id}/segments` via `segmentsApi.list` ([frontend/src/services/api.ts:618-620](../../frontend/src/services/api.ts#L618)) → `SegmentRow[]` ([frontend/src/services/api.ts:604](../../frontend/src/services/api.ts#L604)).
- `GET /v1/sessions/{id}/speakers` via raw `http<SpeakerRow[]>` (no wrapper in `api.ts`; local `SpeakerRow` interface at [frontend/src/views/ViewerView.vue:24](../../frontend/src/views/ViewerView.vue#L24)) ([frontend/src/views/ViewerView.vue:40](../../frontend/src/views/ViewerView.vue#L40)).

No write/POST endpoints are called by this view. The export and publishing handlers call no API.

## Data Sources

- Live: `session`, `slides`, `segments`, `speakers` refs hydrated from the four GETs above ([frontend/src/views/ViewerView.vue:26-29](../../frontend/src/views/ViewerView.vue#L26)).
- Derived: `segmentsBySlide` — a `Map<slide_id, SegmentRow[]>` built by grouping segments under their `slide_id` ([frontend/src/views/ViewerView.vue:53-63](../../frontend/src/views/ViewerView.vue#L53)). `speakerLabel()` resolves a speaker id to `short || name` with a leading "Dr. " stripped ([frontend/src/views/ViewerView.vue:65-69](../../frontend/src/views/ViewerView.vue#L65)).
- Static literals: `downloads` (4 export formats) and `publishing` (7 checklist rows) are hardcoded in the script, not fetched ([frontend/src/views/ViewerView.vue:71-86](../../frontend/src/views/ViewerView.vue#L71)).
- `bundleSha` from `import.meta.env.VITE_BUILD_SHA` for the footer build stamp ([frontend/src/views/ViewerView.vue:18-19](../../frontend/src/views/ViewerView.vue#L18)).

## Source Verification
- **Files Used:** frontend/src/views/ViewerView.vue, frontend/src/services/api.ts, frontend/src/router/index.ts, frontend/src/components/shared/Icon.vue (referenced), frontend/src/composables/useToast.ts (referenced)
- **Components Used:** Icon (shared)
- **APIs Used:** GET /v1/sessions/{id}, GET /v1/sessions/{id}/slides, GET /v1/sessions/{id}/segments, GET /v1/sessions/{id}/speakers
- **Database Tables Used:** none directly (frontend view; tables reached via the four GET endpoints — sessions, slides, segments, speakers — not verified at the DB layer from this file)
- **Permission Logic Used:** JWT presence (global router beforeEach); no adminOnly / LEGACY_ADMIN_EMAIL gate on this route
- **Confidence Score:** High — every claim traced to the view template/script and the api.ts wrappers it imports.
- **Evidence Links:** [ViewerView.vue:34-51](../../frontend/src/views/ViewerView.vue#L34), [ViewerView.vue:91-103](../../frontend/src/views/ViewerView.vue#L91), [api.ts:618-620](../../frontend/src/services/api.ts#L618), [router/index.ts:37](../../frontend/src/router/index.ts#L37)
