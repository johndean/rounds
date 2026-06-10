# Permission Matrix — rounds.vin

> Scope: this document describes **only** the authorization that exists in this
> repository today, verified against source. It does not describe a planned,
> aspirational, or role-tiered model. Where the code contains scaffolding for a
> future role system, that is called out explicitly and marked
> **PARTIALLY IMPLEMENTED**.

## TL;DR — the authorization reality (read this first)

Authorization in Rounds today is **NOT role-based.** It reduces to exactly three
mechanisms:

1. **JWT presence.** Every non-public endpoint depends on `CurrentUser`, which
   resolves to `get_current_user` ([app/auth.py:172](../../app/auth.py#L172)).
   That function decodes the JWT, confirms the subject email is an *active* user
   (DB `auth_users` row, or env-CSV fallback), and returns a `User` object whose
   **only field is `email`** ([app/auth.py:36-38](../../app/auth.py#L36)).
2. **A single hardcoded bootstrap-admin email gate.** Admin power is granted by
   comparing `user.email` against the literal string `"johndean@vin.com"`
   (the constant `LEGACY_ADMIN_EMAIL`,
   [app/security/roles.py:54](../../app/security/roles.py#L54)). This is checked
   either through the helper `require_admin` / `is_admin`
   ([app/security/roles.py:62-117](../../app/security/roles.py#L62)) or, in two
   diagnostics routes, via a raw inline `user.email != "johndean@vin.com"`
   comparison.
3. **One client-side route guard.** The Vue router redirects away from
   `/admin/help` unless `auth.email === 'johndean@vin.com'`
   ([frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63)).
   This is UI convenience only; the server re-checks on every
   `/v1/help/articles*` mutation.

**There is no active role tier.** A `role` column exists in the database
(`auth_users.role`, migration 045) and helpers accept an optional `role=`
argument, but **`get_current_user` never reads that column**, the `User` object
has no `role` attribute, and **no callsite anywhere passes `role=user.role`**
(verified by grep — the only `role=` forwarding is internal to `require_admin`
itself). Therefore every admin check in the running system resolves through the
email branch. The role-based path is **PARTIALLY IMPLEMENTED** scaffolding.

### What changed vs. earlier audits

Earlier notes described `require_admin` / `is_admin` as "scaffold only — not yet
wired into any endpoint." That is **no longer accurate for the helper wiring**:
the Phase 8 step-3 commit replaced the scattered inline `user.email != ADMIN_EMAIL`
checks with `require_admin(...)` calls across `settings.py`, `email_templates.py`,
`email_debug.py`, `help.py`, `sessions.py`, and `is_admin(...)` in `locks.py`.
What is **still** scaffold-only is the *role-reading* half: the helpers fall back
to the `LEGACY_ADMIN_EMAIL` email comparison because no caller supplies a role and
`get_current_user` never loads one. So the net authorization behavior is
unchanged from the inline-gate era — admin == `johndean@vin.com`.

---

## Principals (the two real identities)

| Principal | How it is identified in code | What it can do |
|---|---|---|
| **Authenticated user** | Any email present (and `is_active`) in `auth_users`, or present in the `AUTH_USERS` env-CSV fallback, holding a valid JWT. The `User` object carries only `.email`. | Everything that is gated by `CurrentUser` alone (the large majority of routes). |
| **Bootstrap admin** | The single email literal `"johndean@vin.com"` (`LEGACY_ADMIN_EMAIL`). Identified purely by string equality on `user.email`; case-sensitive, whitespace-sensitive ([app/security/roles.py:88-92](../../app/security/roles.py#L88)). | Everything an authenticated user can do, **plus** the admin-gated surfaces below. |

There is one **narrow carve-out** that is neither tier: the
`SESSION_TRASH_ALLOWED` set ([app/api/sessions.py:52](../../app/api/sessions.py#L52))
adds `"carlab@vin.com"` to the *soft-delete* action only — not a general admin
grant. See the Sessions row in the action matrix.

> **`auth_users.role` exists but is not read.** Migration 045 defines
> `role TEXT NOT NULL DEFAULT 'user'` with intended values `'admin' | 'user'`
> ([migrations/045_auth_users.sql:15](../../migrations/045_auth_users.sql#L15)).
> `get_current_user` ([app/auth.py:172-205](../../app/auth.py#L172)) only checks
> active-status (`user_is_active`) and returns `User(email=...)` — it never
> selects or attaches `role`. Confirm: the `User` dataclass has a single field,
> `email` ([app/auth.py:36](../../app/auth.py#L36)). **PARTIALLY IMPLEMENTED.**

---

## Role × capability matrix

Two columns because there are two principals. "Auth User" = any authenticated
non-admin email. "Bootstrap Admin" = `johndean@vin.com`.

Legend: ✅ allowed · ❌ blocked (403) · ⚠️ allowed via a special-case
allowlist (not the admin gate).

### Screens (frontend route guards)

The router enforces only two things: authentication (any non-`public` route
redirects to `/login` when unauthenticated) and one `adminOnly` guard. There is
**no per-role screen gating beyond `/admin/help`.**

| Screen / route | Auth User | Bootstrap Admin | Enforcement |
|---|---|---|---|
| `#/login` | ✅ (public) | ✅ | `meta.public` ([router:54](../../frontend/src/router/index.ts#L54)) |
| `#/dashboard`, `#/sessions`, `#/s/:id`, `#/upload`, `#/e/:id`, `#/e/:id/sop`, `#/e/:id/audit`, `#/v/:id`, `#/p/:id`, `#/improvements`, `#/settings/:section?`, `#/audit`, `#/gcs`, `#/queue` | ✅ | ✅ | Auth-required only (`isAuthenticated` check, [router:59](../../frontend/src/router/index.ts#L59)) |
| `#/admin/help` (Help editor) | ❌ → redirected to `/dashboard` | ✅ | `meta.adminOnly` + `auth.email !== LEGACY_ADMIN_EMAIL` ([router:63](../../frontend/src/router/index.ts#L63)) |

> Note: the `adminOnly` guard is **client-side only**. It is a UX redirect, not a
> security boundary — a user who reaches the underlying `/v1/help/articles*`
> mutation routes directly is still blocked by the server-side `require_admin`
> calls. Every other Settings sub-section (People, Groups, Types, Auth & Logins,
> Email templates, Prompt templates, Diagnostics) renders for any authenticated
> user; the *write* actions inside them are what the server gates.

### Actions / APIs

Each row maps a capability to the exact server gate. "Gate" tells you precisely
which mechanism enforces it.

| Capability | API route(s) | Auth User | Bootstrap Admin | Gate (verified) |
|---|---|---|---|---|
| Log in | `POST /v1/auth/login` | ✅ (public) | ✅ | Credential check only; no auth dep ([app/api/auth.py:15](../../app/api/auth.py#L15)) |
| Identify self | `GET /v1/auth/me` | ✅ | ✅ | `CurrentUser`; returns `{email}` only ([app/api/auth.py:31](../../app/api/auth.py#L31)) |
| List / read sessions | `GET /v1/sessions`, `GET /v1/sessions/{id}` | ✅ | ✅ | `CurrentUser` |
| Create / upload session | `POST /v1/sessions`, `POST /v1/gcs/upload-url`, `/upload-complete` | ✅ | ✅ | `CurrentUser` + rate-limit dep (see below) |
| Edit session metadata | `PATCH /v1/sessions/{id}` | ✅ | ✅ | `CurrentUser` |
| **Soft-delete session** | `DELETE /v1/sessions/{id}` | ⚠️ only if email ∈ `SESSION_TRASH_ALLOWED` (`johndean@vin.com` or `carlab@vin.com`) | ✅ | Inline set-membership check, **not** `require_admin` ([app/api/sessions.py:630](../../app/api/sessions.py#L630)) |
| List deleted sessions | `GET /v1/sessions/deleted` | ❌ | ✅ | `require_admin` ([app/api/sessions.py:276](../../app/api/sessions.py#L276)) |
| **Restore session** | `POST /v1/sessions/{id}/restore` | ❌ | ✅ | `require_admin` ([app/api/sessions.py:674](../../app/api/sessions.py#L674)) |
| **Permanently delete session** | `DELETE /v1/sessions/{id}/permanent` | ❌ | ✅ | `require_admin`; requires prior soft-delete ([app/api/sessions.py:707](../../app/api/sessions.py#L707)) |
| Force-take editor lock | `POST /v1/sessions/{id}/lock/force-take` | ❌ | ✅ | `is_admin(user)` → 403 ([app/api/locks.py:225](../../app/api/locks.py#L225)) |
| Read org settings | `GET /v1/settings`, `GET /v1/settings/{...}` reads | ✅ | ✅ | `CurrentUser` |
| Set org setting k/v | `PUT /v1/settings/{key}` | ✅ | ✅ | `CurrentUser` only — **no admin gate** ([app/api/settings.py:73](../../app/api/settings.py#L73)) |
| Manage People | `GET/POST/PUT/DELETE /v1/settings/people*` | ✅ | ✅ | `CurrentUser` only — **no admin gate** ([app/api/settings.py:100](../../app/api/settings.py#L100), [115](../../app/api/settings.py#L115), [125](../../app/api/settings.py#L125)) |
| Manage Groups + members | `GET/POST/PUT/DELETE /v1/settings/groups*` | ✅ | ✅ | `CurrentUser` only — **no admin gate** ([app/api/settings.py:169](../../app/api/settings.py#L169)–[304](../../app/api/settings.py#L304)) |
| Read session Types | `GET /v1/settings/types`, `/types/{id}/assignees` | ✅ | ✅ | `CurrentUser` |
| Add / remove Type | `POST /v1/settings/types`, `DELETE /v1/settings/types/{id}` | ❌ | ✅ | `require_admin` ([app/api/settings.py:322](../../app/api/settings.py#L322), [337](../../app/api/settings.py#L337)) |
| Set Type stage-assignee matrix | `PUT /v1/settings/types/{id}/assignees` | ❌ | ✅ | `require_admin` ([app/api/settings.py:431](../../app/api/settings.py#L431)) |
| List auth users | `GET /v1/settings/auth-users` | ❌ | ✅ | `require_admin` ([app/api/settings.py:531](../../app/api/settings.py#L531)) |
| Create / update / reset / delete auth user | `POST/PUT/DELETE /v1/settings/auth-users*`, `.../reset-password` | ❌ | ✅ | `require_admin` ([app/api/settings.py:538](../../app/api/settings.py#L538), [571](../../app/api/settings.py#L571), [617](../../app/api/settings.py#L617), [647](../../app/api/settings.py#L647)) |
| Read prompt templates | `GET /v1/settings/templates*` | ✅ | ✅ | `CurrentUser` |
| Create / update / delete prompt template | `POST/PUT/DELETE /v1/settings/templates*` | ❌ | ✅ | `require_admin` ([app/api/settings.py:872](../../app/api/settings.py#L872), [938](../../app/api/settings.py#L938), [1016](../../app/api/settings.py#L1016)) |
| Download export macro bundle | `GET /v1/settings/export/macro` | ✅ | ✅ | `CurrentUser` only — comment explicitly states "No admin gate" ([app/api/settings.py:680](../../app/api/settings.py#L680)) |
| Read email templates / resolve | `GET /v1/email-templates*`, `POST /resolve` | ✅ | ✅ | `CurrentUser` |
| Create / update / delete email template | `POST/PUT/DELETE /v1/email-templates*` | ❌ | ✅ | `require_admin` ([app/api/email_templates.py:223](../../app/api/email_templates.py#L223), [266](../../app/api/email_templates.py#L266), [298](../../app/api/email_templates.py#L298)) |
| Email diagnostics (config / connectivity / send / attempts) | `GET/POST /v1/admin/email-debug/*` | ❌ | ✅ | `_require_email_debug_admin` → `require_admin` ([app/api/email_debug.py:50-53](../../app/api/email_debug.py#L50)) |
| Help: read articles | `GET /v1/help/articles*` | ✅ (sees only `is_published=TRUE AND audience='users'`) | ✅ (sees all rows incl. drafts) | `CurrentUser` + audience filter via `is_admin` ([app/api/help.py:384](../../app/api/help.py#L384), filter [349](../../app/api/help.py#L349)) |
| Help: create / edit / publish / delete articles | `POST/PUT/DELETE /v1/help/articles*` | ❌ | ✅ | `require_admin` (multiple sites, e.g. [app/api/help.py:461](../../app/api/help.py#L461), [529](../../app/api/help.py#L529), [632](../../app/api/help.py#L632)) |
| Diagnostics: read-only probes | `GET /v1/diag/gcs`, `/classify-route`, etc. | ✅ | ✅ | `CurrentUser` only — these probes are **not** admin-gated ([app/api/diagnostics.py:36](../../app/api/diagnostics.py#L36)) |
| Diagnostics: GCS checks ledger | `GET /v1/diag/gcs-checks` | ❌ | ✅ | **Inline** `user.email != "johndean@vin.com"` (not the helper) ([app/api/diagnostics.py:632](../../app/api/diagnostics.py#L632)) |
| Diagnostics: reseed auth users | `POST /v1/diag/reseed-auth-users` | ❌ | ✅ | **Inline** `user.email != "johndean@vin.com"` (not the helper) ([app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534)) |
| Diagnostics: other rescue/queue/auth-recovery routes | `POST /v1/diag/reingest/{id}`, `/realign/{id}`, `/abort-session/{id}`, `/flush-celery-queue`, `/revoke-task/{id}`, `/clear-rate-limit-slots`, etc. | ✅ | ✅ | `CurrentUser` only — **PARTIALLY IMPLEMENTED**: the module docstring claims admin-gating "via require_admin" ([app/api/diagnostics.py:6-8](../../app/api/diagnostics.py#L6)), but only the two routes above actually carry a gate; the remaining `/v1/diag/*` routes are reachable by any authenticated user. Verify per-route before relying on a gate. |

> **Inconsistency flagged:** two diagnostics routes
> (`reseed-auth-users`, `gcs-checks`) duplicate the admin literal inline
> (`user.email != "johndean@vin.com"`) instead of calling `require_admin`. They
> behave identically today but bypass the single-source-of-truth helper, so a
> future change to `LEGACY_ADMIN_EMAIL` would not propagate to them.

### Data-access summary (CRUD / Approve / Export / Administer)

This collapses the route table into the conventional access verbs. "Admin"
here means the single bootstrap admin email.

| Resource | Create | Read | Update | Delete | Approve | Export | Administer |
|---|---|---|---|---|---|---|---|
| Sessions | Any user | Any user | Any user | Soft-delete: trash-allowlist ⚠️ · Permanent: Admin | n/a (no approval action found — see note) | Macro bundle: any user | Restore / list-deleted / lock-force-take: Admin |
| People | Any user | Any user | Any user | Any user (soft) | n/a | n/a | n/a (no admin gate) |
| Groups | Any user | Any user | Any user | Any user (hard) | n/a | n/a | n/a (no admin gate) |
| Session Types | Admin | Any user | n/a | Admin | n/a | n/a | Assignee matrix: Admin |
| Prompt templates | Admin | Any user | Admin | Admin | n/a | n/a | Admin |
| Email templates | Admin | Any user | Admin | Admin | n/a | n/a | Admin |
| Auth users | Admin | Admin | Admin | Admin | n/a | n/a | Admin (incl. password reset, last-admin guard) |
| Help articles | Admin | Any user (filtered) / Admin (all) | Admin | Admin | Publish toggle: Admin | n/a | Admin |
| Org settings (k/v) | Any user | Any user | Any user | n/a | n/a | n/a | n/a (no admin gate) |
| Email diagnostics | n/a (send action) | Admin (attempts/config) | n/a | n/a | n/a | n/a | Admin |

> **No general "Approve" permission exists** as a distinct authorization concept.
> The transcript workflow (Copy Edit → Medical Review → Publish) is governed by
> the FSM state machine, not by role gates — stage transitions are not in scope
> of this permission document and were not verified here.
> **NOT VERIFIED IN CODE** for this matrix.

---

## How a request is actually authorized (control flow)

1. Client sends `Authorization: Bearer <jwt>`.
2. FastAPI dependency `CurrentUser` → `get_current_user`
   ([app/auth.py:172](../../app/auth.py#L172)) decodes the JWT (HS256,
   `API_SECRET_KEY`), extracts `sub` (email), and confirms the user is active
   via `user_is_active` against `auth_users` (env-CSV fallback on miss/DB error).
   Returns `User(email=...)`. **No role is loaded.**
3. If the route needs admin, it calls `require_admin(user)` /
   `is_admin(user)` — or, in two diagnostics routes, an inline
   `user.email != "johndean@vin.com"` check.
4. `require_admin` / `is_admin` ([app/security/roles.py:62-117](../../app/security/roles.py#L62)):
   since no caller passes `role=`, the `role` branch is skipped and the function
   compares `user.email == LEGACY_ADMIN_EMAIL` ("johndean@vin.com"). 403
   `{"code": "ADMIN_ONLY", ...}` on failure.

The `ADMIN_ONLY` code maps to HTTP 403 in the response envelope
([app/middleware/envelope.py:50](../../app/middleware/envelope.py#L50)).

---

## Rate limiting (a separate, non-role guard)

Rate limiting is enforced per-user-email on upload, independent of any role.
It is a `CurrentUser`-keyed quota, not an authorization tier
([app/middleware/rate_limit.py](../../app/middleware/rate_limit.py)):

- `check_user_quota` rejects with **429 `RATE_LIMIT_USER`** when the user already
  has `MAX_CONCURRENT_SESSIONS` active sessions
  ([rate_limit.py:43-50](../../app/middleware/rate_limit.py#L43)), keyed on
  `sessions:active:{email}` in Redis.
- **429 `RATE_LIMIT_QUEUE`** when the global ingest queue exceeds
  `MAX_QUEUE_LENGTH` ([rate_limit.py:51-59](../../app/middleware/rate_limit.py#L51)).
- If Redis is unreachable the check is skipped (warn, do not block) —
  fail-open by design ([rate_limit.py:64-66](../../app/middleware/rate_limit.py#L64)).
- The admin diagnostics route `POST /v1/diag/clear-rate-limit-slots` sweeps a
  user's active-session slots to clear an orphaned 429.

The bootstrap admin gets no rate-limit exemption — the quota applies to every
authenticated email equally.

---

## Known gaps & scaffolding (do not treat as active)

- **Role tier is not active. PARTIALLY IMPLEMENTED.** `auth_users.role` is
  written and validated on the auth-user CRUD surface (`'admin' | 'user'`,
  last-admin guard at [app/api/settings.py:580-593](../../app/api/settings.py#L580)),
  and the boot seed assigns `role='admin'` to `johndean@vin.com` and `'user'` to
  everyone else ([app/services/auth_users.py:206](../../app/services/auth_users.py#L206)).
  **But that column is never consulted at request time** — `get_current_user`
  does not load it, the `User` object has no `role`, and no callsite passes
  `role=user.role`. So creating a second `role='admin'` row in `auth_users` does
  **not** grant that user admin power in any endpoint; only the literal email
  `johndean@vin.com` is admin. The migration path to activate roles is documented
  in [app/security/roles.py:14-19](../../app/security/roles.py#L14).
- **Frontend has no role concept.** The auth store exposes only `email` and
  `isAuthenticated` (token presence); there is no role field
  ([frontend/src/stores/auth.ts:24-72](../../frontend/src/stores/auth.ts#L24)).
- **Several Settings write surfaces are ungated.** `PUT /v1/settings/{key}`,
  all People endpoints, and all Groups endpoints accept any authenticated user.
  This is the code as written, not a recommendation.
- **`AUTH_USERS` env-CSV fallback** remains a live login path
  ([app/auth.py:133-143](../../app/auth.py#L133)); a user present only in the env
  CSV (not the DB) can authenticate, and would be admin if their email equals
  `johndean@vin.com`.

---

## Source Verification
- **Files Used:** `app/security/roles.py`, `app/auth.py`, `app/api/auth.py`, `app/api/sessions.py`, `app/api/settings.py`, `app/api/email_templates.py`, `app/api/email_debug.py`, `app/api/help.py`, `app/api/locks.py`, `app/api/diagnostics.py`, `app/middleware/rate_limit.py`, `app/middleware/envelope.py`, `app/services/auth_users.py`, `frontend/src/router/index.ts`, `frontend/src/stores/auth.ts`, `migrations/045_auth_users.sql`
- **Components Used:** `frontend/src/router/index.ts` (router guard), `frontend/src/stores/auth.ts` (auth store)
- **APIs Used:** `/v1/auth/login`, `/v1/auth/me`, `/v1/sessions*` (incl. `/deleted`, `/{id}/restore`, `/{id}/permanent`, `/{id}/lock/force-take`), `/v1/settings*` (settings k/v, people, groups, types, auth-users, templates, export/macro), `/v1/email-templates*`, `/v1/admin/email-debug/*`, `/v1/help/articles*`, `/v1/diag/*`, `/v1/gcs/upload-url`, `/v1/gcs/upload-complete`
- **Database Tables Used:** `auth_users` (id, email, password_hash, role, is_active, last_login_at, password_reset_at), `sessions` (deleted_at), `people`, `groups`, `group_members`, `session_types`, `stage_assignees`, `prompt_templates`, `email_templates`, `email_attempts`, `org_settings`, `audit_events`
- **Permission Logic Used:** JWT presence (`CurrentUser` → `get_current_user`) + hardcoded `LEGACY_ADMIN_EMAIL` ("johndean@vin.com") gate via `require_admin`/`is_admin`, plus two inline `user.email != "johndean@vin.com"` checks in diagnostics, plus the `SESSION_TRASH_ALLOWED` set carve-out for soft-delete, plus one client-side `adminOnly` router guard. `auth_users.role` exists but is NOT read by `get_current_user`.
- **Confidence Score:** High — every gate was read in source and the negative claim (role never loaded) was confirmed by inspecting the `User` dataclass, `get_current_user`, and a repo-wide grep showing no `role=user.role` callsite.
- **Evidence Links:** [app/security/roles.py:54](../../app/security/roles.py#L54) (LEGACY_ADMIN_EMAIL), [app/security/roles.py:88-92](../../app/security/roles.py#L88) (email-branch fallback), [app/auth.py:36](../../app/auth.py#L36) (User has only `email`), [app/auth.py:172-205](../../app/auth.py#L172) (get_current_user does not load role), [migrations/045_auth_users.sql:15](../../migrations/045_auth_users.sql#L15) (role column exists), [frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63) (client adminOnly guard), [app/api/sessions.py:52](../../app/api/sessions.py#L52) (SESSION_TRASH_ALLOWED), [app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534) + [632](../../app/api/diagnostics.py#L632) (inline admin literals)
