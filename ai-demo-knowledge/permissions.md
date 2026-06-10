# Permissions — rounds.vin (scaffold-only reality)

> Mirror of [`docs/security/permission-matrix.md`](../docs/security/permission-matrix.md),
> re-verified against source. This describes ONLY the authorization that exists in
> the repo today. There is no active role tier. Where the code contains scaffolding
> for a future role system, it is marked **PARTIALLY IMPLEMENTED**.

## TL;DR — the authorization reality

Authorization in Rounds is **NOT role-based.** It reduces to exactly three mechanisms:

1. **JWT presence.** Every non-public endpoint depends on `CurrentUser` →
   `get_current_user` ([app/auth.py:172](../app/auth.py#L172)). It decodes the JWT,
   confirms the subject email is an *active* user (DB `auth_users` row, or env-CSV
   fallback), and returns a `User` object whose **only field is `email`**
   ([app/auth.py:36](../app/auth.py#L36)).
2. **A single hardcoded bootstrap-admin email gate.** Admin power = `user.email ==
   "johndean@vin.com"` (`LEGACY_ADMIN_EMAIL`, [app/security/roles.py:54](../app/security/roles.py#L54)),
   checked via `require_admin`/`is_admin` or, in two diagnostics routes, an inline
   `user.email != "johndean@vin.com"` comparison.
3. **One client-side route guard.** The Vue router redirects away from `/admin/help`
   unless `auth.email === 'johndean@vin.com'` ([frontend/src/router/index.ts:63](../frontend/src/router/index.ts#L63)).
   UI convenience only; the server re-checks every `/v1/help/articles*` mutation.

**`auth_users.role` exists but is never read.** Migration 045 defines
`role TEXT NOT NULL DEFAULT 'user'`, and the auth-user CRUD surface validates/writes
`'admin' | 'user'` (with a last-admin guard), but `get_current_user` never selects
the column, the `User` object has no `role`, and **no callsite passes `role=user.role`**.
Creating a second `role='admin'` row grants that user **no** admin power in any
endpoint. The role-based path is **PARTIALLY IMPLEMENTED** scaffolding.

> Stale-doc note: `app/security/roles.py`'s own docstring still calls the helpers
> "scaffold only — not wired into any endpoint." That is out of date — `require_admin`/
> `is_admin` ARE now called from `settings.py`, `email_templates.py`, `email_debug.py`,
> `help.py`, `sessions.py`, and `locks.py`. What remains scaffold is the *role-reading*
> half: with no role supplied, the helpers fall through to the email comparison, so net
> behavior is unchanged — admin == `johndean@vin.com`.

## The two real principals

| Principal | Identified by | Can do |
|---|---|---|
| **Authenticated user** | Any active email in `auth_users` (or the `AUTH_USERS` env-CSV) holding a valid JWT. `User` carries only `.email`. | Everything gated by `CurrentUser` alone — the large majority of routes. |
| **Bootstrap admin** | The literal `"johndean@vin.com"`. Case- and whitespace-sensitive string equality. | Everything an auth user can, **plus** the admin-gated surfaces below. |

One narrow carve-out that is neither tier: `SESSION_TRASH_ALLOWED`
([app/api/sessions.py:52](../app/api/sessions.py#L52)) adds `"carlab@vin.com"` to the
**soft-delete action only** — not a general admin grant.

## Screen guards (frontend router)

The router enforces only authentication (any non-`public` route → `/login` when
unauthenticated) and one `adminOnly` guard:

| Screen | Auth User | Bootstrap Admin | Enforcement |
|---|---|---|---|
| `#/login` | allowed (public) | allowed | `meta.public` |
| dashboard, sessions, s/:id, upload, e/:id, e/:id/sop, e/:id/audit, v/:id, p/:id, improvements, settings, audit, gcs, queue | allowed | allowed | auth-required only |
| `#/admin/help` (Help editor) | blocked → `/dashboard` | allowed | `meta.adminOnly` + `auth.email !== LEGACY_ADMIN_EMAIL` ([router:63](../frontend/src/router/index.ts#L63)) |

The `adminOnly` guard is client-side UX only; the underlying `/v1/help/articles*`
mutations are still blocked server-side by `require_admin`.

## Action / API gates (verified)

Legend: allowed · blocked (403) · ⚠ allowed via a special-case allowlist (not the admin gate).

| Capability | Route(s) | Auth User | Admin | Gate |
|---|---|---|---|---|
| Log in | `POST /v1/auth/login` | allowed (public) | allowed | credential check; no auth dep |
| Identify self | `GET /v1/auth/me` | allowed | allowed | `CurrentUser`; returns `{email}` only |
| List/read/create/edit sessions | `GET/POST/PATCH /v1/sessions*` | allowed | allowed | `CurrentUser` (+ rate-limit on create) |
| **Soft-delete session** | `DELETE /v1/sessions/{id}` | ⚠ only if email ∈ `SESSION_TRASH_ALLOWED` | allowed | inline set membership, **not** `require_admin` |
| List deleted / restore / permanent-delete | `GET /v1/sessions/deleted`, `POST .../restore`, `DELETE .../permanent` | blocked | allowed | `require_admin` |
| Force-take editor lock | `POST /v1/sessions/{id}/lock/force-take` | blocked | allowed | `is_admin(user)` → 403 |
| Read org settings | `GET /v1/settings*` reads | allowed | allowed | `CurrentUser` |
| Set org setting / People / Groups | `PUT /v1/settings/{key}`, `/people*`, `/groups*` | allowed | allowed | `CurrentUser` only — **no admin gate** |
| Add/remove session Type; set assignee matrix | `POST/DELETE /v1/settings/types*`, `PUT .../assignees` | blocked | allowed | `require_admin` |
| Auth-user CRUD + reset | `GET/POST/PUT/DELETE /v1/settings/auth-users*` | blocked | allowed | `require_admin` |
| Prompt-template write | `POST/PUT/DELETE /v1/settings/templates*` | blocked | allowed | `require_admin` |
| Email-template write | `POST/PUT/DELETE /v1/email-templates*` | blocked | allowed | `require_admin` |
| Email diagnostics | `GET/POST /v1/admin/email-debug/*` | blocked | allowed | `_require_email_debug_admin` → `require_admin` |
| Help: read articles | `GET /v1/help/articles*` | allowed (published + audience='users' only) | allowed (all incl. drafts) | `CurrentUser` + `is_admin` audience filter |
| Help: write/publish/delete + bulk-AI | `POST/PUT/DELETE /v1/help/articles*`, `/v1/help/admin/*` | blocked | allowed | `require_admin` |
| Diagnostics: read-only probes | `GET /v1/diag/gcs`, `/classify-route` | allowed | allowed | `CurrentUser` only — **not** admin-gated |
| Diagnostics: `gcs-checks`, `reseed-auth-users` | those two routes | blocked | allowed | **inline** `user.email != "johndean@vin.com"` (bypasses the helper) |
| Diagnostics: other rescue/queue routes | `reingest`, `realign`, `abort-session`, `flush-celery-queue`, `revoke-task`, `clear-rate-limit-slots`, `autoplace-polls`, `sop-check`, etc. | allowed | allowed | `CurrentUser` only — **PARTIALLY IMPLEMENTED**: module docstring claims admin-gating but only the two routes above carry a gate. Verify per-route. |

> **Inconsistency flagged:** `reseed-auth-users` and `gcs-checks` duplicate the admin
> literal inline instead of calling `require_admin`, so a future change to
> `LEGACY_ADMIN_EMAIL` would not propagate to them.

> **No general "Approve" permission exists.** The transcript workflow
> (Copy Edit → Medical Review → Publish / SOP advance) is governed by the SOP FSM,
> not by role gates — `/sop/advance` requires only JWT, any authenticated user can
> advance one stage. NOT VERIFIED IN CODE: any approval-role gate on stage transitions.

## How a request is actually authorized

1. Client sends `Authorization: Bearer <jwt>`.
2. `CurrentUser` → `get_current_user` decodes the JWT (HS256, `API_SECRET_KEY`),
   extracts `sub` (email), confirms active via `user_is_active` (env-CSV fallback on
   miss). Returns `User(email=...)`. **No role loaded.**
3. Admin routes call `require_admin(user)`/`is_admin(user)` — or two diag routes use an
   inline email comparison.
4. With no `role=` passed, the helper compares `user.email == LEGACY_ADMIN_EMAIL`;
   403 `{"code": "ADMIN_ONLY"}` (HTTP 403 via the envelope) on failure.

## Rate limiting (a separate, non-role guard)

Per-user-email quota on upload, independent of role ([app/middleware/rate_limit.py](../app/middleware/rate_limit.py)):
- 429 `RATE_LIMIT_USER` when the user already has `MAX_CONCURRENT_SESSIONS` (3) active.
- 429 `RATE_LIMIT_QUEUE` when the global ingest queue exceeds `MAX_QUEUE_LENGTH` (10).
- Redis unreachable → check skipped (fail-open).
- The bootstrap admin gets **no** rate-limit exemption.

## Known gaps & scaffolding (do not treat as active)

- **Role tier is not active (PARTIALLY IMPLEMENTED).** `auth_users.role` is written/validated and the seed assigns `role='admin'` to `johndean@vin.com`, but the column is never consulted at request time.
- **Frontend has no role concept.** The auth store exposes only `email` + `isAuthenticated` ([frontend/src/stores/auth.ts](../frontend/src/stores/auth.ts)).
- **Several Settings write surfaces are ungated:** `PUT /v1/settings/{key}`, all People endpoints, all Groups endpoints accept any authenticated user.
- **`AUTH_USERS` env-CSV fallback** remains a live login path; a user present only in the CSV can authenticate (and would be admin if their email equals `johndean@vin.com`).

## Source Verification
- **Files Used:** docs/security/permission-matrix.md, app/security/roles.py, app/auth.py, app/api/sessions.py, app/api/settings.py, app/api/email_templates.py, app/api/email_debug.py, app/api/help.py, app/api/locks.py, app/api/diagnostics.py, app/middleware/rate_limit.py, frontend/src/router/index.ts, frontend/src/stores/auth.ts, migrations/045_auth_users.sql
- **Components Used:** frontend/src/router/index.ts (router guard), frontend/src/stores/auth.ts (auth store)
- **APIs Used:** /v1/auth/login, /v1/auth/me, /v1/sessions* (incl. deleted/restore/permanent/lock/force-take), /v1/settings* (k/v, people, groups, types, auth-users, templates), /v1/email-templates*, /v1/admin/email-debug/*, /v1/help/articles*, /v1/help/admin/*, /v1/diag/*
- **Database Tables Used:** auth_users (incl. role, never read at request time), sessions (deleted_at), people, groups, session_types, stage_assignees, prompt_templates, email_templates, org_settings, audit_events
- **Permission Logic Used:** JWT (`CurrentUser` → `get_current_user`) + hardcoded `LEGACY_ADMIN_EMAIL` ("johndean@vin.com") gate via `require_admin`/`is_admin`, plus two inline `user.email != "johndean@vin.com"` diag checks, plus the `SESSION_TRASH_ALLOWED` soft-delete carve-out, plus one client-side `adminOnly` router guard. `auth_users.role` exists but is NOT read.
- **Confidence Score:** High — mirrors the source matrix, with `LEGACY_ADMIN_EMAIL` line 54 and `SESSION_TRASH_ALLOWED` line 52 re-confirmed by grep at HEAD.
- **Evidence Links:** [app/security/roles.py:54](../app/security/roles.py#L54), [app/auth.py:36](../app/auth.py#L36), [app/auth.py:172](../app/auth.py#L172), [app/api/sessions.py:52](../app/api/sessions.py#L52), [frontend/src/router/index.ts:63](../frontend/src/router/index.ts#L63), [migrations/045_auth_users.sql](../migrations/045_auth_users.sql)
