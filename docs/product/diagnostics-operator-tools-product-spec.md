# Diagnostics & Operator Tools — Product Spec

> Module key: `diagnostics-operator-tools`
> Scope: the `/v1/diag/*` backend endpoints and the frontend surfaces that call them (Settings → Diagnostics, the editor's Admin-tab Rescue panel, Settings → Auth & Logins reseed). All claims below are verified against the source files listed in **Source Verification**.

## Overview

The Diagnostics & Operator Tools module is a set of backend HTTP endpoints under the `/v1/diag` prefix plus the thin frontend panels that invoke a subset of them. The endpoints fall into four families that mirror the catalog in `CLAUDE.md`:

1. **Read-only probes** — GCS credential/bucket alignment (`/gcs`), classification-backend route (`/classify-route`), and the 14-row GCS QA suite (`/gcs-checks`).
2. **Per-session manual rescue** — reingest, realign, init SOP stages, autoplace polls, abort.
3. **Queue + task surgery** — flush the Celery broker queue, revoke a task, run the SOP deadline check inline.
4. **Rate-limit + auth recovery** — clear leaked Redis rate-limit slots, reseed `auth_users` from the env CSV.

All routes are registered on the FastAPI app via `app.include_router(diag_router.router)` in [app/main.py:227](../../app/main.py#L227) with prefix `/v1/diag` and tag `diagnostics` ([app/api/diagnostics.py:24](../../app/api/diagnostics.py#L24)).

## Purpose

These are operator tools, not test endpoints. They exist so an operator can probe infrastructure health and manually rescue a session or the queue when the automated pipeline has gone sideways — without a redeploy. The module docstring states they are "production operator tools" ([app/api/diagnostics.py:1-13](../../app/api/diagnostics.py#L1)). Most of the rescue routes are the explicit escape hatch around the session state machine: reingest and abort deliberately bypass `ALLOWED_TRANSITIONS` to push a `failed`/`ready`/`uploading` session back into a workable state ([app/api/diagnostics.py:114-125](../../app/api/diagnostics.py#L114), [app/api/diagnostics.py:438-471](../../app/api/diagnostics.py#L438)).

## User Value

- **Operator can spot-check infrastructure** (GCS bucket reachability, signed-URL generation, PUT round-trip, lifecycle/CORS/ACL, classification backend) from a UI panel or curl.
- **Operator can self-rescue a stuck session** (re-run ingest, re-run word alignment, backfill SOP stages, backfill poll placement, force-abort).
- **Operator can recover from queue stampedes** (purge the broker, revoke a specific task).
- **A user blocked by a 429 rate-limit can self-clear leaked Redis slots** — this is the only `/v1/diag/*` action surfaced to any logged-in user, not just the admin (see Permissions).
- **Recovery from an empty `auth_users` table without a redeploy** via reseed.

## Navigation

There are three distinct entry points in the frontend; the `/v1/diag/gcs`, `/v1/diag/classify-route`, and `/v1/diag/health` client methods exist in the API client but have **no UI caller** (verified — see Known Constraints).

| Surface | Route / location | Endpoints used |
|---|---|---|
| Settings → Diagnostics | `#/settings/diagnostics` ([frontend/src/views/SettingsView.vue:86](../../frontend/src/views/SettingsView.vue#L86)) → `SectionDiagnostics.vue` | `clear-rate-limit-slots`, drills into GCS QA |
| Settings → Diagnostics → GCS Pipeline QA | drill-in within `SectionDiagnostics` → `GCSDebug.vue` | `gcs-checks` |
| Editor right rail → Admin tab → Rescue | `AdminTab.vue`, visible only when `isAdmin` | `reingest`, `realign`, `init-session-stages`, `autoplace-polls`, `abort-session` |
| Settings → Auth & Logins recovery panel | `SectionAuthUsers.vue:242` | `reseed-auth-users` |

The top-nav "Settings" link is active for `/settings`, `/audit`, and `/gcs` ([frontend/src/components/AppHeader.vue:154](../../frontend/src/components/AppHeader.vue#L154)). The `/gcs` route ([frontend/src/router/index.ts:42](../../frontend/src/router/index.ts#L42)) renders `GcsView.vue`, which is a **static-fixture page** that does not call any diagnostics endpoint (see Known Constraints).

## Screens

### 1. GcsView (`/gcs`) — static fixture, NOT a live probe surface

`GcsView.vue` renders a hardcoded array of 14 `Check` rows with fixed `ok`/`ms`/`note` values ([frontend/src/views/GcsView.vue:11-26](../../frontend/src/views/GcsView.vue#L11)). It is a faithful port of `processing.jsx::GcsRoute`. The KPI row ("Checks Passing 13/14", "Last Sweep 00:01:42", "7-Day Uptime 99.98%", "Open Pages 0") and the "5-minute cadence … PagerDuty after two consecutive misses" copy are all static fixture text — there is no backend call, no cadence job, and no PagerDuty integration in this view. **PARTIALLY IMPLEMENTED** as a real diagnostics surface: it is purely a visual port.

### 2. SectionDiagnostics (Settings → Diagnostics home)

`SectionDiagnostics.vue` is the operator landing card stack. It contains ([frontend/src/components/settings/SectionDiagnostics.vue:43-126](../../frontend/src/components/settings/SectionDiagnostics.vue#L43)):

- A **Phase 0 counters** card whose values (`longtasks/min: 1`, `heap: 108 MB`, `WS RTT: 18ms`, `autosave: 2s ago`) are **static text, not live telemetry** ([SectionDiagnostics.vue:51-53](../../frontend/src/components/settings/SectionDiagnostics.vue#L51)). **NOT VERIFIED IN CODE** that any counter is wired.
- A button to open the **test email page** (EmailDebug — a separate module).
- A **GCS Pipeline QA** card that drills into `GCSDebug.vue`. Its summary copy ("14 GCS-side checks running on a 5-minute cadence. 7-day uptime 99.98%. Failing G13 …") is static text.
- Two links to standalone DevTools HTML pages: `/upload-test.html` and `/process-test.html` (static assets opened in a new tab).
- A **Reset rate-limit slots** card with a live button that calls `/v1/diag/clear-rate-limit-slots`.

### 3. GCSDebug (Settings → Diagnostics → GCS Pipeline QA) — live

`GCSDebug.vue` calls `GET /v1/diag/gcs-checks` on mount and on the "Re-run checks" button ([frontend/src/components/settings/GCSDebug.vue:31-46](../../frontend/src/components/settings/GCSDebug.vue#L31)). It renders the 14 returned rows: G1–G6 are real probes (green `pass` / amber `fail`), G7–G14 are deferred stubs rendered with a neutral `deferred` chip so they cannot be mistaken for healthy ([GCSDebug.vue:113-123](../../frontend/src/components/settings/GCSDebug.vue#L113)). KPI tiles show "Real probes passing", "Real probes failing", "Deferred", and "Total checks" computed from the live response ([GCSDebug.vue:26-29](../../frontend/src/components/settings/GCSDebug.vue#L26)). This is the honest replacement for the old all-green fixture.

### 4. AdminTab Rescue panel (editor right rail) — live, admin-gated UI

`AdminTab.vue` renders a "Rescue · operator actions" section only when `isAdmin` is true. It exposes five buttons that call the per-session rescue endpoints with a native `window.confirm()` prompt before dispatch ([frontend/src/components/editor/AdminTab.vue:58-82](../../frontend/src/components/editor/AdminTab.vue#L58), [AdminTab.vue:178-199](../../frontend/src/components/editor/AdminTab.vue#L178)). Two are styled destructive (reingest, abort).

### 5. SectionAuthUsers reseed (Settings → Auth & Logins) — live

`SectionAuthUsers.vue:242` calls `diag.reseedAuthUsers()` from a recovery panel.

## User Flows

### Reset my stale rate-limit slots (any logged-in user)
1. User hits `429 RATE_LIMIT_USER` after a create+delete cycle leaked a Redis slot.
2. User opens Settings → Diagnostics and clicks "Reset my stale slots".
3. Frontend calls `POST /v1/diag/clear-rate-limit-slots` ([SectionDiagnostics.vue:26](../../frontend/src/components/settings/SectionDiagnostics.vue#L26)).
4. Backend sweeps the Redis set `sessions:active:{email}` for the calling user, removes any slot whose session is soft-deleted (`deleted_at IS NOT NULL`) or no longer in the DB, and also removes it from `sessions:queue` ([app/api/diagnostics.py:304-319](../../app/api/diagnostics.py#L304)).
5. Toast shows removed count and `remaining/cap` ([SectionDiagnostics.vue:28-33](../../frontend/src/components/settings/SectionDiagnostics.vue#L28)).

### Run GCS QA probe suite (admin)
1. Operator opens Settings → Diagnostics → GCS Pipeline QA (or clicks Re-run).
2. Frontend calls `GET /v1/diag/gcs-checks`.
3. Backend admin-gates on `user.email == 'johndean@vin.com'`, builds one GCS client, runs G1–G6, appends G7–G14 deferred stubs, writes an `audit_events` row, returns 14 rows ([app/api/diagnostics.py:624-724](../../app/api/diagnostics.py#L624)).

### Rescue a stuck session (admin, in the editor)
1. Operator opens a session in the editor, switches the right rail to the Admin tab.
2. Rescue panel is visible only because `isAdmin` is true.
3. Operator clicks e.g. "Re-ingest pipeline"; a `window.confirm()` prompt appears.
4. On confirm, frontend calls `POST /v1/diag/reingest/{sessionId}`.
5. Backend resets status → `uploading`, deletes prior segments, appends a `session_audit` log entry, commits, then enqueues `ingest_task` ([app/api/diagnostics.py:104-171](../../app/api/diagnostics.py#L104)).

### Reseed auth users (admin)
1. After a Railway env update or a seed failure that left `auth_users` empty, operator opens Settings → Auth & Logins recovery panel.
2. Frontend calls `POST /v1/diag/reseed-auth-users`.
3. Backend admin-gates, re-runs `seed_from_env_if_empty`, writes an `audit_events` row, returns `{seeded, total, skipped_count}` ([app/api/diagnostics.py:521-572](../../app/api/diagnostics.py#L521)).

## Business Rules

- **BR-001 (LEGACY_ADMIN_EMAIL gate).** The admin-gated diagnostics routes compare `user.email` to the literal `"johndean@vin.com"` ([app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534), [app/api/diagnostics.py:632](../../app/api/diagnostics.py#L632)). The same literal is the `LEGACY_ADMIN_EMAIL` constant in [app/security/roles.py:54](../../app/security/roles.py#L54) and is mirrored client-side ([AdminTab.vue:45](../../frontend/src/components/editor/AdminTab.vue#L45), [frontend/src/router/index.ts:51](../../frontend/src/router/index.ts#L51)).
- **Reingest is the explicit state-machine escape hatch.** It pushes a session to `uploading` regardless of current status and wipes `segments` so transcribe doesn't no-op via its check-before-execute guard ([app/api/diagnostics.py:114-131](../../app/api/diagnostics.py#L114)).
- **Abort bypasses ALLOWED_TRANSITIONS** to force `failed`; it is a no-op if already `failed` ([app/api/diagnostics.py:457-461](../../app/api/diagnostics.py#L457)).
- **Reseed is idempotent** — `seed_from_env_if_empty` returns 0 with no writes if `auth_users` already has rows ([app/services/auth_users.py:199-203](../../app/services/auth_users.py#L199)).
- **Rate-limit sweep preserves live slots** — only slots for missing or soft-deleted sessions are released ([app/api/diagnostics.py:314-318](../../app/api/diagnostics.py#L314)).
- **GCS PUT probe honors the R7 invariant** — the round-trip writes to `gs://<bucket>/_diag/`, never `sessions/`, and immediately deletes the probe blob ([app/api/diagnostics.py:727-736](../../app/api/diagnostics.py#L727)).
- **init-session-stages and autoplace-polls are idempotent** — only stages without an assignee / polls with `anchor_segment IS NULL` are written ([app/api/diagnostics.py:224](../../app/api/diagnostics.py#L224), [app/api/diagnostics.py:260](../../app/api/diagnostics.py#L260)).

## Validation Rules

- **Session existence.** `reingest` and `abort-session` first `SELECT status FROM sessions`; if no row, they raise `404 session {id} not found` ([app/api/diagnostics.py:110-111](../../app/api/diagnostics.py#L110), [app/api/diagnostics.py:453-454](../../app/api/diagnostics.py#L453)). `realign`, `init-session-stages`, and `autoplace-polls` do **not** pre-check existence — they pass the id straight to a Celery task or service and surface any error in the `detail` field.
- **Admin identity.** `reseed-auth-users` and `gcs-checks` require `hasattr(user,'email')` and `user.email == 'johndean@vin.com'`, else `403 ADMIN_ONLY` ([app/api/diagnostics.py:534-538](../../app/api/diagnostics.py#L534), [app/api/diagnostics.py:632-636](../../app/api/diagnostics.py#L632)).
- **`init-session-stages` type override.** Optional `?type_id=<uuid>` query param; omitted falls back to the session's existing type, then the org default Type ([app/api/diagnostics.py:213-214](../../app/api/diagnostics.py#L213), [app/services/session_init.py:39-41](../../app/services/session_init.py#L39)).
- **`revoke-task` terminate flag.** Optional `terminate: bool = True` query param ([app/api/diagnostics.py:399](../../app/api/diagnostics.py#L399)).

## States

- **Session status transitions driven by this module:** `reingest` → `uploading`; `abort-session` → `failed`. Both write a `session_audit.processing_log` entry recording `{ts, prev, next, actor, reason}` ([app/api/diagnostics.py:135-153](../../app/api/diagnostics.py#L135), [app/api/diagnostics.py:475-493](../../app/api/diagnostics.py#L475)).
- **GCS check states:** each `GcsCheckRow.ok` is `true` (pass), `false` (fail), or `null` (deferred stub) ([app/api/diagnostics.py:590-596](../../app/api/diagnostics.py#L590)).
- **Frontend rescue button state:** `rescuing` ref holds the in-flight action id; all rescue buttons disable while any action is running ([AdminTab.vue:48](../../frontend/src/components/editor/AdminTab.vue#L48), [AdminTab.vue:188](../../frontend/src/components/editor/AdminTab.vue#L188)).
- **GCSDebug loading state:** `loading` ref drives the "Running…" button label and a "Running probes…" placeholder row ([GCSDebug.vue:31-44](../../frontend/src/components/settings/GCSDebug.vue#L31)).

## Dependencies

- **Postgres** — `sessions`, `segments`, `session_audit`, `auth_users`, `audit_events` tables.
- **Redis** — active-sessions sets (`sessions:active:{email}`) and `sessions:queue` list, read via `settings.REDIS_URL` ([app/api/diagnostics.py:301-302](../../app/api/diagnostics.py#L301)).
- **Google Cloud Storage** — `google.cloud.storage` client built with `settings.GCP_PROJECT_ID` / `settings.GCS_BUCKET` ([app/api/diagnostics.py:42-46](../../app/api/diagnostics.py#L42), [app/api/diagnostics.py:645-647](../../app/api/diagnostics.py#L645)).
- **Celery** — `celery_app.control.purge()` / `.revoke()` for queue surgery; `enqueue_ingest`, `lcs_discrepancies_task`, `sop_check_deadlines_task` for rescue/inline runs ([app/api/diagnostics.py:373-417](../../app/api/diagnostics.py#L373)).
- **Backend services** — `init_session_stages` ([app/services/session_init.py:27](../../app/services/session_init.py#L27)), `auto_place_polls` ([app/services/poll_autoplace.py:84](../../app/services/poll_autoplace.py#L84)), `seed_from_env_if_empty` ([app/services/auth_users.py:176](../../app/services/auth_users.py#L176)).
- **WS bridge** — `publish_ws_event_sync` so abort flips open SessionDetail/Processing tabs out of the "Preparing files" loop ([app/api/diagnostics.py:500-506](../../app/api/diagnostics.py#L500)).

## Error Handling

- **Probe isolation in `gcs-checks`:** each probe is wrapped by `_gcs_time_probe`, which catches any exception and returns `ok=False` with `"{ExceptionClass}: {message[:160]}"` in the note, so one failing probe can never 500 the suite ([app/api/diagnostics.py:598-621](../../app/api/diagnostics.py#L598)). If the GCS client itself fails to construct, G1 is marked failed and G2–G6 are emitted as "(skipped — client unavailable)" ([app/api/diagnostics.py:648-659](../../app/api/diagnostics.py#L648)).
- **Best-effort audit:** the `gcs-checks` audit insert is wrapped in try/except so a failed audit row never fails the probe call ([app/api/diagnostics.py:719-722](../../app/api/diagnostics.py#L719)).
- **Enqueue/dispatch failures** in `reingest`, `realign`, `init-session-stages`, `autoplace-polls`, `revoke-task`, `flush-celery-queue`, and `sop-check` are caught and returned as a `detail`/`error` string with `enqueued=false` / `ok=false` rather than raising ([app/api/diagnostics.py:158-164](../../app/api/diagnostics.py#L158), [app/api/diagnostics.py:338-346](../../app/api/diagnostics.py#L338)).
- **`flush-celery-queue` no-worker case:** if `control.purge()` returns `None`, the response reports `purged=0` with detail "no workers responded — queue may still hold messages" ([app/api/diagnostics.py:384-386](../../app/api/diagnostics.py#L384)).
- **Frontend:** `GCSDebug` and `SectionDiagnostics` surface `ApiError` as `"{status} — {message}"` toasts; `AdminTab` shows `"{label} failed — {message}"` ([GCSDebug.vue:36-42](../../frontend/src/components/settings/GCSDebug.vue#L36), [AdminTab.vue:76-78](../../frontend/src/components/editor/AdminTab.vue#L76)).

## Permissions

PERMISSION REALITY (verified): role-based auth is scaffold-only. `app/security/roles.py` (`is_admin`/`require_admin`) is **NOT wired into any diagnostics endpoint** — `diagnostics.py` never imports it (verified: the only match for "require_admin" in the file is a docstring line). `auth_users.role` (migration 045) is **not** read by `get_current_user`, which only decodes the JWT and checks the user is active ([app/auth.py:172-205](../../app/auth.py#L172)). Real authorization today is:

- **JWT presence (every route).** All 13 `/v1/diag/*` routes depend on `CurrentUser` ([app/auth.py:208](../../app/auth.py#L208)), so any logged-in user can call most of them — including the per-session rescue routes and the queue-surgery routes. There is **no server-side admin check** on `reingest`, `realign`, `init-session-stages`, `autoplace-polls`, `abort-session`, `clear-rate-limit-slots`, `flush-celery-queue`, `revoke-task`, `sop-check`, `gcs`, or `classify-route`.
- **Hardcoded email gate (2 diagnostics routes only).** `reseed-auth-users` and `gcs-checks` raise `403 ADMIN_ONLY` unless `user.email == "johndean@vin.com"` ([app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534), [app/api/diagnostics.py:632](../../app/api/diagnostics.py#L632)).
- **Client-side UX guard only (not enforcement).** The editor Rescue panel renders only when `auth.email` equals the legacy admin email ([AdminTab.vue:46](../../frontend/src/components/editor/AdminTab.vue#L46)). This is a v-if, not a security boundary — the backend rescue routes do not enforce it. The one `adminOnly` router guard in the app is on `/admin/help`, not on any diagnostics route ([frontend/src/router/index.ts:44](../../frontend/src/router/index.ts#L44), [frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63)).

> Discrepancy: the `diagnostics.py` module docstring claims "admin-gated routes additionally enforce LEGACY_ADMIN_EMAIL via require_admin" ([app/api/diagnostics.py:8](../../app/api/diagnostics.py#L8)). This is inaccurate — the gating is done by inline `user.email != "johndean@vin.com"` checks, not the `require_admin` helper, and only two routes are gated at all.

## Reporting Impacts

- Two diagnostics actions write to the global `audit_events` ledger: `gcs-checks` (`kind='diag.gcs_checks'`, summary `real_passed=N/M bucket=…`) and `reseed-auth-users` (`kind='diag.reseed_auth_users'`, summary `before=… seeded=… after=…`) ([app/api/diagnostics.py:711-717](../../app/api/diagnostics.py#L711), [app/api/diagnostics.py:558-564](../../app/api/diagnostics.py#L558)). These rows surface wherever `audit_events` is read (Audit views).
- `reingest` and `abort-session` append to the per-session `session_audit.processing_log` JSONB array, which is the session's processing timeline ([app/api/diagnostics.py:142-153](../../app/api/diagnostics.py#L142)).
- No diagnostics route emits Finance or revenue data. **No reporting integration beyond the two audit tables is implemented.**

## Audit Requirements

| Action | Audit table | Actor recorded | Verified |
|---|---|---|---|
| reingest | `session_audit.processing_log` | `actor: "diag/reingest"` | [app/api/diagnostics.py:139](../../app/api/diagnostics.py#L139) |
| abort-session | `session_audit.processing_log` | `actor: "diag/abort-session"` | [app/api/diagnostics.py:479](../../app/api/diagnostics.py#L479) |
| init-session-stages | (via service) | `actor="diag/init-session-stages"` passed to `init_session_stages` | [app/api/diagnostics.py:234](../../app/api/diagnostics.py#L234) |
| gcs-checks | `audit_events` | `actor_email=user.email` | [app/api/diagnostics.py:714](../../app/api/diagnostics.py#L714) |
| reseed-auth-users | `audit_events` | `actor_email=user.email` | [app/api/diagnostics.py:562](../../app/api/diagnostics.py#L562) |

`realign`, `autoplace-polls`, `clear-rate-limit-slots`, `flush-celery-queue`, `revoke-task`, `sop-check`, `gcs`, and `classify-route` write **no audit row** of their own (the `init-session-stages` and `autoplace-polls` services may log internally, but the diag endpoints do not add a diag-specific audit row). **PARTIALLY IMPLEMENTED**: audit coverage of operator actions is not uniform.

## Data Relationships

- `session_audit.session_id` is a PK FK to `sessions(id)` with `ON DELETE CASCADE`; `processing_log` is a JSONB array appended via `||` on conflict ([migrations/010_state_machine.sql:31-35](../../migrations/010_state_machine.sql#L31)).
- `audit_events.session_id` is a nullable FK to `sessions(id)` `ON DELETE SET NULL`; diagnostics rows leave it NULL and identify the actor by `actor_email` ([migrations/004_audit.sql:3-11](../../migrations/004_audit.sql#L3)).
- `reingest` deletes `segments WHERE session_id = ...` before re-enqueue ([app/api/diagnostics.py:128-131](../../app/api/diagnostics.py#L128)).
- Redis keys `sessions:active:{email}` (set) and `sessions:queue` (list) relate to the per-user concurrency cap `settings.MAX_CONCURRENT_SESSIONS` reported as `cap` ([app/api/diagnostics.py:323-324](../../app/api/diagnostics.py#L323)).

## Known Constraints

- **Three client methods have no UI caller.** `diag.gcs()`, `diag.classifyRoute()`, and `diag.health()` are defined in [frontend/src/services/api.ts:1039-1041](../../frontend/src/services/api.ts#L1039) but no `.vue` component calls them (verified — only `gcsChecks`, `clearRateLimitSlots`, `reseedAuthUsers`, and the five per-session rescue methods have callers). The read-only `/gcs` and `/classify-route` endpoints are curl-only.
- **`GcsView.vue` (`/gcs`) is a static fixture**, not a live diagnostics surface. Its 14 rows, KPIs, "5-minute cadence", "PagerDuty after two consecutive misses", and "99.98% uptime" are hardcoded and do not reflect any backend probe ([frontend/src/views/GcsView.vue:11-26](../../frontend/src/views/GcsView.vue#L11)).
- **`SectionDiagnostics` Phase 0 counters and GCS summary copy are static text** — not wired to live telemetry. **NOT VERIFIED IN CODE** that any counter is live.
- **`abort-session` does not revoke a Celery task.** The UI button description says "Set status → failed and kill any in-flight Celery task" ([AdminTab.vue:63](../../frontend/src/components/editor/AdminTab.vue#L63)), and the CLAUDE.md catalog says "kills any in-flight task", but the endpoint only updates status and publishes a WS event — it does **not** call `revoke()` ([app/api/diagnostics.py:463-508](../../app/api/diagnostics.py#L463)). To revoke a task you must call `/revoke-task/{task_id}` separately. This is a UI-copy vs backend discrepancy.
- **G7–G14 GCS checks are deferred stubs**, returning `ok=None`; they are not implemented probes ([app/api/diagnostics.py:690-704](../../app/api/diagnostics.py#L690)).
- **No CSRF / confirmation token on destructive routes.** Rescue confirmation is a client-side `window.confirm()` only; the backend has no confirmation-token requirement (CLAUDE.md notes this is a future hardening item).
- **`flush-celery-queue` is global** — there is no per-session filter; it purges the entire Rounds queue ([app/api/diagnostics.py:367-370](../../app/api/diagnostics.py#L367)).

## Source Verification
- **Files Used:** app/api/diagnostics.py; app/auth.py; app/security/roles.py; app/main.py; app/services/auth_users.py; app/services/session_init.py; app/services/poll_autoplace.py; migrations/004_audit.sql; migrations/010_state_machine.sql; frontend/src/views/GcsView.vue; frontend/src/components/settings/SectionDiagnostics.vue; frontend/src/components/settings/GCSDebug.vue; frontend/src/components/editor/AdminTab.vue; frontend/src/services/api.ts; frontend/src/router/index.ts; frontend/src/components/AppHeader.vue; frontend/src/views/SettingsView.vue; frontend/src/components/settings/SectionAuthUsers.vue
- **Components Used:** GcsView.vue, SectionDiagnostics.vue, GCSDebug.vue, AdminTab.vue (Rescue panel), SectionAuthUsers.vue (reseed caller)
- **APIs Used:** GET /v1/diag/gcs, GET /v1/diag/classify-route, GET /v1/diag/gcs-checks, POST /v1/diag/reingest/{id}, POST /v1/diag/realign/{id}, POST /v1/diag/init-session-stages/{id}, POST /v1/diag/autoplace-polls/{id}, POST /v1/diag/clear-rate-limit-slots, POST /v1/diag/sop-check, POST /v1/diag/flush-celery-queue, POST /v1/diag/revoke-task/{task_id}, POST /v1/diag/abort-session/{id}, POST /v1/diag/reseed-auth-users
- **Database Tables Used:** sessions, segments, session_audit, auth_users, audit_events (plus Redis keys sessions:active:{email}, sessions:queue)
- **Permission Logic Used:** JWT presence (CurrentUser) on all routes; hardcoded `user.email == "johndean@vin.com"` (LEGACY_ADMIN_EMAIL) gate on reseed-auth-users + gcs-checks only; client-side isAdmin v-if UX guard on AdminTab. roles.py require_admin is NOT wired.
- **Confidence Score:** High — every route, gate, and UI caller was read directly from source; discrepancies (docstring vs inline gate, abort copy vs behavior, static fixtures) are flagged.
- **Evidence Links:** [app/api/diagnostics.py:24](../../app/api/diagnostics.py#L24), [app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534), [app/api/diagnostics.py:632](../../app/api/diagnostics.py#L632), [app/auth.py:172](../../app/auth.py#L172), [app/security/roles.py:54](../../app/security/roles.py#L54), [frontend/src/components/editor/AdminTab.vue:178](../../frontend/src/components/editor/AdminTab.vue#L178), [frontend/src/components/settings/GCSDebug.vue:31](../../frontend/src/components/settings/GCSDebug.vue#L31)
