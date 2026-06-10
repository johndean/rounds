# rounds.vin — Product Overview

> Code-verified knowledge asset for a demo AI. Every claim is traceable to a
> source file in this repository. Unproven claims are tagged
> `NOT VERIFIED IN CODE`, `IMPLEMENTATION NOT FOUND`, or `PARTIALLY IMPLEMENTED`.
> Links are relative to this file's location (`ai-demo-knowledge/`).

## What rounds.vin is

rounds.vin is transcript software for VIN (Veterinary Information Network). An
operator uploads a recorded lecture/session; an AI pipeline produces a
first-pass transcript with speaker labels and slide alignment; then a human
workflow walks the transcript through editorial and medical review before it is
exported to a downstream CMS. The product README states this verbatim
([docs/product/README.md:3-4](../docs/product/README.md#L3)).

The domain is `rounds.vin`; the FastAPI app is titled "Rounds API"
([app/main.py:110](../app/main.py#L110)).

> The originating brief mentioned "CE.VIN" and modules like
> Organizations/Sites/Vendors/Projects. **None of those exist in this repo.**
> There is no org/site/vendor/project model in the codebase. The session list is
> a single shared backlog with no per-tenant scoping
> ([docs/product/improvements-product-spec.md:7](../docs/product/improvements-product-spec.md#L7)).

## Who uses it

There is exactly one user concept in code: an authenticated principal identified
by email (`User` dataclass with a single `email` field,
[app/auth.py:36-38](../app/auth.py#L36)). The product docs refer to these users
as operators, copy editors, medical reviewers, and clinicians, but the **code
does not model these as distinct roles** — see "Permission reality" below.
Login is username (treated as email) + password
([app/api/auth.py:15-28](../app/api/auth.py#L15)).

## The core flow (end to end, code-true)

1. **Upload.** An operator picks pipeline settings and uploads media to Google
   Cloud Storage via a signed PUT URL
   ([app/api/gcs_upload.py:69](../app/api/gcs_upload.py#L69)), then calls
   upload-complete, which registers sources, enforces the R7 scope invariant,
   reserves a rate-limit slot, and enqueues ingest
   ([app/api/gcs_upload.py:110](../app/api/gcs_upload.py#L110)).
2. **AI processing.** A Celery DAG drives the session from `uploading` to
   `ready`. The session status moves through a locked state machine:
   `uploading → transcribing → normalizing → fusing → aligning → ready`, with an
   AI-direct shortcut `uploading → ready` and a final `ready → complete`
   promotion ([app/engines/state_machine.py:40-47](../app/engines/state_machine.py#L40)).
   The pipeline produces segments, words, slides, speaker labels, segment→slide
   alignments, and AI↔STT discrepancies
   ([docs/technical/processing-pipeline-technical-spec.md:11-31](../docs/technical/processing-pipeline-technical-spec.md#L11)).
3. **Editing.** In the Editor (`#/e/:id`) an operator reviews and corrects the
   transcript. All edits go through an append-only correction ledger; undo/redo
   is a pointer move, never a row deletion
   ([app/api/corrections.py:883](../app/api/corrections.py#L883),
   [app/api/corrections.py:928](../app/api/corrections.py#L928)).
4. **SOP workflow.** A separate 8-stage "Standard Operating Procedure" workflow
   tracks editorial/medical/CMS progress after the transcript is `ready`:
   `prep → copy_draft → medical → copy_final → cms → captions → qa → complete`,
   forward-only ([app/api/sop.py:24](../app/api/sop.py#L24),
   [app/api/sop.py:80-90](../app/api/sop.py#L80)).
5. **Export.** Finished transcripts are exported on demand as txt / srt / vtt /
   docx / html / zip ([app/api/exports.py:41](../app/api/exports.py#L41)), plus a
   cache-friendly WebVTT caption track for the in-app player
   ([app/api/exports.py:120](../app/api/exports.py#L120)).

## What the backend is

FastAPI + SQLAlchemy (async) + Celery workers, integrating Google Cloud Storage,
Google Speech-to-Text, and Google Gemini. The API exposes routes under `/v1/*`
mounted from ~24 routers ([app/main.py:212-233](../app/main.py#L212)). Background
work runs on a single Celery queue with Celery Beat embedded
([docs/technical/processing-pipeline-technical-spec.md:41-42](../docs/technical/processing-pipeline-technical-spec.md#L41)).

## What the frontend is

A Vue 3 single-page app, hash-routed, that is a pixel-by-pixel port of a React
prototype. Routes mirror the backend resource shape: `#/dashboard`,
`#/sessions`, `#/s/:id`, `#/upload`, `#/e/:id` (+ `/sop`, `/audit`), `#/v/:id`,
`#/p/:id`, `#/improvements`, `#/settings/:section?`, `#/audit`, `#/gcs`,
`#/queue`, and admin `#/admin/help`
([frontend/src/router/index.ts:27-45](../frontend/src/router/index.ts#L27)).

## Permission reality (important — do not overstate)

Role-based authorization is **scaffold-only**. The demo AI must not present role
tiers (admin/editor/reviewer) as an active access-control system. The verified
facts:

- **Real authorization today = JWT presence.** Every protected endpoint requires
  a valid bearer token via the `CurrentUser` dependency; that is the only check
  on most routes ([app/auth.py:172-208](../app/auth.py#L172)).
- **A single hardcoded admin gate.** Admin-only routes call `require_admin(user)`
  with no `role=` argument, so the helper falls back to comparing
  `user.email == "johndean@vin.com"` (the `LEGACY_ADMIN_EMAIL` constant)
  ([app/security/roles.py:54](../app/security/roles.py#L54),
  [app/security/roles.py:88-92](../app/security/roles.py#L88)). Two diagnostics
  routes inline the same literal email check directly
  ([app/api/diagnostics.py:534](../app/api/diagnostics.py#L534),
  [app/api/diagnostics.py:632](../app/api/diagnostics.py#L632)).
- **`auth_users.role` exists but is not read.** Migration 045 added a `role`
  column and the seed writes `"admin"`/`"user"`
  ([app/services/auth_users.py:206](../app/services/auth_users.py#L206)), but
  `get_current_user` never loads it — it only checks `user_is_active`
  ([app/auth.py:179-205](../app/auth.py#L179)). The `roles.py` helper documents
  this migration path as future work
  ([app/security/roles.py:10-19](../app/security/roles.py#L10)).
- **One client-side route guard.** `#/admin/help` carries `meta.adminOnly` and a
  `beforeEach` guard redirects anyone whose email ≠ `johndean@vin.com` to the
  dashboard ([frontend/src/router/index.ts:44](../frontend/src/router/index.ts#L44),
  [frontend/src/router/index.ts:63](../frontend/src/router/index.ts#L63)). This
  is UI-only; the server re-checks on every `/v1/help/articles*` write.

So: there is one bootstrap superadmin (a hardcoded email), and everyone else is
"a logged-in user." Anything finer-grained is not enforced.

## Known security debt (verified, stated by code)

- `AUTH_USERS` is a plaintext email:password CSV in env, used to seed the
  `auth_users` table (bcrypt-hashed) on first boot and as a login fallback if the
  DB path fails ([app/auth.py:100-143](../app/auth.py#L100),
  [app/config.py:39](../app/config.py#L39)).
- The `/v1/diag/*` rescue endpoints require only a JWT — the pipeline-recovery
  ones (reingest/realign/abort) are **not** behind the admin gate
  ([docs/technical/processing-pipeline-technical-spec.md:251](../docs/technical/processing-pipeline-technical-spec.md#L251)).

## What this product is NOT

- Not multi-tenant. No organizations, sites, vendors, or projects.
- Not a real-time meeting/transcription product — it processes **uploaded
  recordings**, not live audio.
- Not a generic CMS — it exports to a downstream CMS; it does not host published
  content itself.

## Source Verification
- **Files Used:** docs/product/README.md, app/main.py, app/auth.py, app/api/auth.py, app/api/gcs_upload.py, app/engines/state_machine.py, app/api/corrections.py, app/api/sop.py, app/api/exports.py, app/api/sessions.py, app/api/diagnostics.py, app/security/roles.py, app/services/auth_users.py, app/config.py, frontend/src/router/index.ts, docs/technical/processing-pipeline-technical-spec.md, docs/product/improvements-product-spec.md
- **Components Used:** EditorView (`#/e/:id`), HelpEditor (`#/admin/help`) — referenced, not opened in full here
- **APIs Used:** POST /v1/auth/login, POST /v1/gcs/upload-url, POST /v1/gcs/upload-complete, GET /v1/sessions, /v1/sessions/{id}/sop, /v1/sessions/{id}/exports/{format}, /v1/sessions/{id}/captions.vtt, /v1/diag/*
- **Database Tables Used:** auth_users, sessions, session_templates (referenced); full set documented in module-catalog.md
- **Permission Logic Used:** JWT presence (CurrentUser) + LEGACY_ADMIN_EMAIL hardcoded gate via require_admin; one client-side adminOnly route guard
- **Confidence Score:** High — every flow claim traced to current source; permission reality cross-checked against auth.py, roles.py, and router/index.ts.
- **Evidence Links:** [app/engines/state_machine.py:40-47](../app/engines/state_machine.py#L40), [app/security/roles.py:54-92](../app/security/roles.py#L54), [app/auth.py:172-208](../app/auth.py#L172), [frontend/src/router/index.ts:44-67](../frontend/src/router/index.ts#L44)
