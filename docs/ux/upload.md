# Upload

Route: `#/upload` ([frontend/src/router/index.ts:33](../../frontend/src/router/index.ts#L33)) → [frontend/src/views/UploadView.vue](../../frontend/src/views/UploadView.vue)

## Purpose

Single-page intake for new sessions. The operator attaches one or more media/document files, configures the AI processing pipeline, and clicks **Process**. On submit the view creates a session row, uploads each file directly to GCS via a signed URL, calls upload-complete, and navigates to the processing page. See the file header at [UploadView.vue:1-25](../../frontend/src/views/UploadView.vue#L1).

## User Types

Any authenticated user. The route has no `meta.public` and no `meta.adminOnly`, so the global guard only requires `auth.isAuthenticated` ([frontend/src/router/index.ts:53-67](../../frontend/src/router/index.ts#L53)). There is no role check on this screen — see Permissions.

## Entry Points

- Direct hash navigation to `#/upload`.
- Any in-app link/button that routes to the `upload` named route. (No in-view back-link is rendered by `UploadView.vue` itself; inbound links live in the app chrome — NOT VERIFIED IN CODE from this view.)

## Navigation Paths

- On a successful batch, `processBatch()` calls `router.push('/p/<session_id>')` ([UploadView.vue:248](../../frontend/src/views/UploadView.vue#L248)) — the Processing view.
- No other `router.push` / `RouterLink` exists in this view.

## Components

- [`Icon`](../../frontend/src/components/shared/Icon.vue) — used throughout for field icons, the dropzone glyph, chevrons, remove buttons ([UploadView.vue:28](../../frontend/src/views/UploadView.vue#L28)).
- A hidden `<input type="file" multiple>` (`pickerRef`, `data-test-id="upload-picker"`) ([UploadView.vue:330-337](../../frontend/src/views/UploadView.vue#L330)).
- Dropzone (`.upload-dropzone`, `data-test-id="upload-dropzone"`) with click-to-pick + drag/drop handlers ([UploadView.vue:352](../../frontend/src/views/UploadView.vue#L352)).
- Attachment list rows (`.upload-attach`) with per-file remove button `data-test-id="upload-remove-<i>"` ([UploadView.vue:380-398](../../frontend/src/views/UploadView.vue#L380)).
- Form sections, all native `<select>`/`<textarea>` (no separate child components): Processing Pipeline, AI Processing Mode, AI Model, Custom Prompt (conditional), STT, Processing Style card, IIL card ([UploadView.vue:402-578](../../frontend/src/views/UploadView.vue#L402)).
- Process button (`.upload-process`, `data-test-id="upload-process"`) ([UploadView.vue:580](../../frontend/src/views/UploadView.vue#L580)).

## Actions

- **Pick / drop files** → `onPick` / `onDrop` → `ingestFiles()` dedupes by `name::size` and builds an `Attached` record per file with a filename-inferred role (video/audio/slide/manifest/chat/other) via `inferRole()` ([UploadView.vue:86-144](../../frontend/src/views/UploadView.vue#L86)).
- **Remove attachment** → `removeAttachment(idx)` splices the list and pushes a warn toast ([UploadView.vue:146-150](../../frontend/src/views/UploadView.vue#L146)).
- **Change pipeline / AI mode / model / style / STT / IIL tiers** → local refs only; consumed by `buildPipelineConfig()` at submit ([UploadView.vue:167-197](../../frontend/src/views/UploadView.vue#L167)).
- **Toggle Processing Style / IIL panels** → local `styleOpen` / `iilOpen` / per-tier `tier1..3` refs.
- **Process** → `processBatch()` ([UploadView.vue:199-255](../../frontend/src/views/UploadView.vue#L199)):
  1. Generates a session code (`genCode()`, `MMDDYY_<stem>_<4charRandom>`).
  2. `sessionsApi.create(...)` with `pipeline_config` from `buildPipelineConfig()`.
  3. Per file: `gcsApi.signedUrl(sessionId, name, role)` then a raw `fetch(signed_url, { method: 'PUT', body: file })`.
  4. `gcsApi.uploadComplete(sessionId, completeFiles)`.
  5. `router.push('/p/<sessionId>')`.

## States

- **Idle / no files:** dropzone shows "Drop your files here"; Process button is `disabled` (`!filesAttached`) ([UploadView.vue:367-373](../../frontend/src/views/UploadView.vue#L367), [583](../../frontend/src/views/UploadView.vue#L583)).
- **Files attached:** dropzone flips to "N file(s) selected · Ready to process"; attachment list + role labels render ([UploadView.vue:360-399](../../frontend/src/views/UploadView.vue#L360)).
- **Custom-prompt mode:** when `aiMode === 'custom-prompt'` (`isCustom`) the saved-template picker + custom-prompt textarea appear ([UploadView.vue:312](../../frontend/src/views/UploadView.vue#L312), [439-468](../../frontend/src/views/UploadView.vue#L439)).
- **STT field disabled** unless `pipeline === 'enhanced'` ([UploadView.vue:471-482](../../frontend/src/views/UploadView.vue#L471)).
- **Uploading:** `uploading` ref true → Process button label becomes `Uploading {done}/{total}…` and per-file remove buttons are disabled ([UploadView.vue:586-588](../../frontend/src/views/UploadView.vue#L586), [394](../../frontend/src/views/UploadView.vue#L394)). Footer text switches to "Streaming bytes to GCS — do not close this tab" ([UploadView.vue:593-595](../../frontend/src/views/UploadView.vue#L593)).

## Empty States

The page itself is the empty/initial state for a new session — no list to be empty. With zero attachments the dropzone renders its prompt copy and the Process button is disabled. There is no separate "no data" panel.

## Error States

- **No files on Process:** `processBatch()` early-returns with toast "Add at least one file" (warn) ([UploadView.vue:200-203](../../frontend/src/views/UploadView.vue#L200)).
- **GCS PUT failure:** non-2xx PUT throws `GCS PUT failed (<status>) for <name>`, caught and shown as an error toast (8s) ([UploadView.vue:232](../../frontend/src/views/UploadView.vue#L232), [249-251](../../frontend/src/views/UploadView.vue#L249)).
- **API error (create / signed-url / upload-complete):** `ApiError` surfaces as `"<status>: <message>"`; other errors show their message; fallback "Upload failed" ([UploadView.vue:250-251](../../frontend/src/views/UploadView.vue#L250)).
- **Settings prefill failure on mount:** swallowed silently — falls back to local defaults ([UploadView.vue:50-52](../../frontend/src/views/UploadView.vue#L50)).
- There is no inline error banner; all errors are toast-only.

## Loading States

- **On mount**, `settingsApi.list()` prefills defaults; no spinner is rendered for this (silent, non-fatal) ([UploadView.vue:37-53](../../frontend/src/views/UploadView.vue#L37)).
- **During upload**, the Process button doubles as the progress indicator (`Uploading {done}/{total}…`); `progress` is updated after each file completes ([UploadView.vue:240](../../frontend/src/views/UploadView.vue#L240)). No separate progress bar element.

## Permissions

JWT presence only. The route is gated solely by `auth.isAuthenticated` in the global `beforeEach` guard ([frontend/src/router/index.ts:59-62](../../frontend/src/router/index.ts#L59)). There is no `adminOnly` meta on this route and no `LEGACY_ADMIN_EMAIL` check in `UploadView.vue`. Role-based authorization is scaffold-only repo-wide and not consulted here.

## Connected APIs

Traced through `@/services/api` and a raw `fetch` for the GCS PUT:

- `settingsApi.list()` → `GET /v1/settings` ([api.ts:780](../../frontend/src/services/api.ts#L780)) — mount prefill.
- `sessionsApi.create(...)` → `POST /v1/sessions` ([api.ts:141-142](../../frontend/src/services/api.ts#L141)).
- `gcsApi.signedUrl(sessionId, filename, role)` → `POST /v1/gcs/upload-url` ([api.ts:950-954](../../frontend/src/services/api.ts#L950)).
- Raw `fetch(signed_url, { method: 'PUT', body: file })` — direct-to-GCS, not through `http()` ([UploadView.vue:227-231](../../frontend/src/views/UploadView.vue#L227)).
- `gcsApi.uploadComplete(sessionId, files)` → `POST /v1/gcs/upload-complete` ([api.ts:955-959](../../frontend/src/services/api.ts#L955)).

## Data Sources

- `AI_MODELS` fixture for the AI Model `<select>` options ([UploadView.vue:32](../../frontend/src/views/UploadView.vue#L32), [434](../../frontend/src/views/UploadView.vue#L434)).
- Local static arrays: `aiModeOptions`, `styleCategories`, `styleChips`, `tiers`, `savedTemplates`, `customPromptDefault` ([UploadView.vue:258-325](../../frontend/src/views/UploadView.vue#L258)). The saved-template picker options are static and "Load Saved Prompt Template" does not fetch — selecting a template sets `savedTpl` only (the textarea is bound to `customPromptDefault`, not to a fetched template). PARTIALLY IMPLEMENTED.
- Org-level defaults from `GET /v1/settings` (`default_ai_model`, `default_pipeline`, `default_style`) used to prefill `model` / `pipeline` / `style` ([UploadView.vue:41-49](../../frontend/src/views/UploadView.vue#L41)).
- Attached file metadata is derived entirely client-side from `File` objects (no server read before submit).

## Source Verification
- **Files Used:** frontend/src/views/UploadView.vue, frontend/src/services/api.ts, frontend/src/router/index.ts
- **Components Used:** Icon (shared)
- **APIs Used:** GET /v1/settings, POST /v1/sessions, POST /v1/gcs/upload-url, raw PUT to signed GCS URL, POST /v1/gcs/upload-complete
- **Database Tables Used:** none read directly by the view; writes are server-side (sessions, source rows via upload-complete) — not asserted from frontend code
- **Permission Logic Used:** JWT presence only (router beforeEach `auth.isAuthenticated`); no role/admin gate on this route
- **Confidence Score:** High — every claim traced to view + api.ts + router source.
- **Evidence Links:** [UploadView.vue:199-255](../../frontend/src/views/UploadView.vue#L199), [api.ts:949-960](../../frontend/src/services/api.ts#L949), [router/index.ts:33](../../frontend/src/router/index.ts#L33)
