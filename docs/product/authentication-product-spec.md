# Authentication & Access — Product Spec

> Module key: `authentication`. This document describes only what is implemented in this repository (rounds.vin). Every claim is traceable to a source file. Items that could not be proven from code are tagged `NOT VERIFIED IN CODE`, `IMPLEMENTATION NOT FOUND`, or `PARTIALLY IMPLEMENTED`.

## Overview

Rounds authenticates operators with a username/password login that issues a JWT bearer token. The "username" is an email address. Credentials are checked against a database table (`auth_users`) of bcrypt-hashed passwords, with a fallback to a plaintext `AUTH_USERS` environment CSV when the database has no matching row or errors. See [app/api/auth.py:15](../../app/api/auth.py#L15) and [app/auth.py:100](../../app/auth.py#L100).

The token is an HS256 JWT signed with `API_SECRET_KEY`, carrying the user email in the `sub` claim, expiring after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 480 minutes = 8 hours). See [app/auth.py:153](../../app/auth.py#L153) and [app/config.py:42](../../app/config.py#L42).

Every protected route depends on `get_current_user`, which decodes the JWT and re-checks that the user is still active before each request. See [app/auth.py:172](../../app/auth.py#L172).

There is no self-service signup, no password-self-reset flow, and no email-verification flow in this repo. New logins and password resets are created by an admin via Settings → Auth & Logins. See [app/api/settings.py:536](../../app/api/settings.py#L536) and [app/api/settings.py:613](../../app/api/settings.py#L613).

## Purpose

- Gate access to the transcript operations console so only known VIN operators can view or act on sessions.
- Identify the acting principal (by email) so that mutating actions can be attributed in the audit ledger (e.g. `actor_email` rows written on auth-user changes). See [app/api/settings.py:561](../../app/api/settings.py#L561).
- Provide a single bootstrap administrator gate (`johndean@vin.com`) for the small number of operator-only / admin-only surfaces that exist today. See [app/security/roles.py:54](../../app/security/roles.py#L54).

## User Value

- An operator signs in once and stays signed in for 8 hours (token lifetime), across page refreshes, without re-entering credentials. The email and token are persisted client-side. See [frontend/src/stores/auth.ts:24](../../frontend/src/stores/auth.ts#L24) and [frontend/src/services/http.ts:21](../../frontend/src/services/http.ts#L21).
- Wrong credentials produce a clear "Incorrect email or password" message rather than a generic failure. See [frontend/src/stores/auth.ts:55](../../frontend/src/stores/auth.ts#L55) and [app/api/auth.py:22](../../app/api/auth.py#L22).
- An expired or revoked token automatically routes the user back to login instead of leaving them on a broken screen. See [frontend/src/services/http.ts:71](../../frontend/src/services/http.ts#L71).

## Navigation

- `#/login` — the public Login route. It is the only route flagged `meta: { public: true }`. See [frontend/src/router/index.ts:29](../../frontend/src/router/index.ts#L29).
- `/` redirects to `#/dashboard`. See [frontend/src/router/index.ts:28](../../frontend/src/router/index.ts#L28).
- Any non-public route, when accessed without authentication, redirects to `#/login` with a `?next=<originalPath>` query so the user returns to where they were after signing in. See [frontend/src/router/index.ts:59](../../frontend/src/router/index.ts#L59).
- On a successful login the app navigates to the `next` query param if present, else `#/dashboard`. See [frontend/src/views/LoginView.vue:40](../../frontend/src/views/LoginView.vue#L40).
- The login form is reached again automatically on any 401 from the API (except while already on `#/login`). See [frontend/src/services/http.ts:79](../../frontend/src/services/http.ts#L79).
- Account management (creating logins, resetting passwords, deactivating users) lives under the Settings view; the auth-user CRUD endpoints are mounted at `/v1/settings/auth-users`. See [app/api/settings.py:529](../../app/api/settings.py#L529). The specific Settings sub-screen component is `PARTIALLY IMPLEMENTED` / `NOT VERIFIED IN CODE` here — the API and client service exist ([frontend/src/services/api.ts:764](../../frontend/src/services/api.ts#L764)) but this assignment did not verify the Settings auth-and-logins Vue sub-component.

## Screens

### Login screen (`#/login`)

Source: [frontend/src/views/LoginView.vue](../../frontend/src/views/LoginView.vue).

Fields and controls:

- Email input (`type="email"`, placeholder `you@vin.com`, autofocus, `data-test-id="login-email"`). See [frontend/src/views/LoginView.vue:66](../../frontend/src/views/LoginView.vue#L66).
- Password input (`type="password"`, `data-test-id="login-password"`). See [frontend/src/views/LoginView.vue:78](../../frontend/src/views/LoginView.vue#L78).
- A "Keep me signed in for 8 hours" checkbox, rendered `checked`. It has no `v-model` binding and is not read by the submit handler — it is a static label that reflects the fixed 8-hour token lifetime. See [frontend/src/views/LoginView.vue:88](../../frontend/src/views/LoginView.vue#L88). `NOT VERIFIED IN CODE` that this checkbox changes any behavior.
- Submit button labeled "Sign in" / "Signing in…" while busy, disabled while busy (`data-test-id="login-submit"`). See [frontend/src/views/LoginView.vue:93](../../frontend/src/views/LoginView.vue#L93).
- A build-SHA pill and footer showing the bundle build identifier (`VITE_BUILD_SHA`, defaulting to `dev`). See [frontend/src/views/LoginView.vue:15](../../frontend/src/views/LoginView.vue#L15).

The screen is branded "TRANSCRIPT.SOFTWARE — VIN Transcript Operations Console". See [frontend/src/views/LoginView.vue:53](../../frontend/src/views/LoginView.vue#L53).

### Settings → Auth & Logins (account management surface)

The backend exposes the management API for this surface (list / add / update / reset-password / delete logins). See [app/api/settings.py:529-668](../../app/api/settings.py#L529). The client service wrapper types `AuthUser` and `AuthUserPatch`. See [frontend/src/services/api.ts:764](../../frontend/src/services/api.ts#L764). The dedicated Vue sub-component rendering this screen is `NOT VERIFIED IN CODE` in this assignment.

## User Flows

### Sign in

1. User enters email + password and submits. If either is empty, a "Email and password required" toast is shown and submission stops. See [frontend/src/views/LoginView.vue:28](../../frontend/src/views/LoginView.vue#L28).
2. The store calls `POST /v1/auth/login` with the email lowercased and trimmed, sent as form-encoded `username`/`password`. See [frontend/src/stores/auth.ts:48](../../frontend/src/stores/auth.ts#L48) and [frontend/src/services/api.ts:28](../../frontend/src/services/api.ts#L28).
3. The backend authenticates against `auth_users` (bcrypt), falling back to the env CSV if no row / DB error. On success it returns an access token. See [app/auth.py:100](../../app/auth.py#L100) and [app/api/auth.py:21](../../app/api/auth.py#L21).
4. The client stores the token in `localStorage` (`rounds_jwt_v1`), then calls `GET /v1/auth/me` to confirm and capture the principal email, persisting it (`rounds_user_email_v1`). See [frontend/src/services/http.ts:19](../../frontend/src/services/http.ts#L19) and [frontend/src/stores/auth.ts:48](../../frontend/src/stores/auth.ts#L48).
5. A "Welcome back, <name>" toast is shown and the app navigates to `next` or `#/dashboard`. See [frontend/src/views/LoginView.vue:39](../../frontend/src/views/LoginView.vue#L39).

### Session bootstrap on refresh

On app load, if a token exists, `bootstrap()` calls `GET /v1/auth/me`; on failure the token is cleared and the user is treated as logged out. The persisted email lets the route guard pass synchronously so there is no flash of `/login`. See [frontend/src/stores/auth.ts:30](../../frontend/src/stores/auth.ts#L30).

### Token expiry / revocation

Any API 401 (other than on the login form itself) clears the stored token and redirects the browser to `/#/login`. See [frontend/src/services/http.ts:71](../../frontend/src/services/http.ts#L71).

### Logout

`logout()` clears the token and persisted email locally. There is no server-side token revocation endpoint — logout is purely client-side token disposal. See [frontend/src/stores/auth.ts:66](../../frontend/src/stores/auth.ts#L66). `IMPLEMENTATION NOT FOUND` for any `/v1/auth/logout` route.

### Admin creates a login / resets a password

An admin (the `johndean@vin.com` gate) can create a login (`POST /v1/settings/auth-users`), change its role/active flag (`PUT`), reset its password (`POST .../reset-password`), or delete it (`DELETE`). Each write inserts an `audit_events` row. See [app/api/settings.py:536](../../app/api/settings.py#L536), [:569](../../app/api/settings.py#L569), [:613](../../app/api/settings.py#L613), [:645](../../app/api/settings.py#L645).

## Business Rules

- **Token lifetime is 8 hours.** `ACCESS_TOKEN_EXPIRE_MINUTES` defaults to 480. See [app/config.py:43](../../app/config.py#L43) and [app/auth.py:154](../../app/auth.py#L154).
- **Token algorithm is HS256, signed with `API_SECRET_KEY`.** See [app/config.py:42](../../app/config.py#L42) and [app/auth.py:157](../../app/auth.py#L157).
- **Bootstrap admin gate (BR-001).** Admin-gated surfaces resolve to a single hardcoded email `johndean@vin.com` until `auth_users.role` is consulted by the request principal. See [app/security/roles.py:54](../../app/security/roles.py#L54).
- **DB-first authentication with env-CSV fallback (BR-020).** A matching `auth_users` row with a passing bcrypt check wins; a matching row with a wrong password fails without falling through; a missing row or DB error falls back to the `AUTH_USERS` env CSV. See [app/auth.py:104-143](../../app/auth.py#L104).
- **Inactive users cannot authenticate.** A matching row with `is_active = FALSE` returns failure at login, and `get_current_user` requires an active row on the DB path. See [app/auth.py:123](../../app/auth.py#L123) and [app/services/auth_users.py:136](../../app/services/auth_users.py#L136).
- **Email matching is case-insensitive at lookup.** Lookups use `lower(email)`; a unique index on `lower(email)` collapses casing to one row. See [app/services/auth_users.py:101](../../app/services/auth_users.py#L101) and [migrations/045_auth_users.sql:26](../../migrations/045_auth_users.sql#L26).
- **One-shot seed from env on first boot.** `seed_from_env_if_empty` populates `auth_users` from the `AUTH_USERS` CSV only when the table is empty; the seeded role is `admin` only for `johndean@vin.com`, else `user`. See [app/services/auth_users.py:176](../../app/services/auth_users.py#L176) and [app/main.py:73](../../app/main.py#L73).
- **Passwords are never returned by the API.** Every auth-user projection whitelists columns and omits `password_hash`. See [app/api/settings.py:499](../../app/api/settings.py#L499) and [frontend/src/services/api.ts:762](../../frontend/src/services/api.ts#L762).
- **Reset-only password model.** The only way to set a new password is the admin reset endpoint; PATCH cannot change a password. See [app/api/settings.py:488](../../app/api/settings.py#L488) and [app/api/settings.py:613](../../app/api/settings.py#L613).
- **Last-admin protection.** The system refuses to demote, disable, or delete the only remaining active admin (409 `LAST_ADMIN_PROTECTED`). See [app/api/settings.py:580](../../app/api/settings.py#L580) and [app/api/settings.py:651](../../app/api/settings.py#L651).
- **bcrypt 72-byte truncation.** Passwords longer than 72 bytes are truncated at a codepoint boundary, identically on hash and verify. See [app/services/auth_users.py:57](../../app/services/auth_users.py#L57).

## Validation Rules

- **Login:** both email and password must be non-empty client-side before the request is made. See [frontend/src/views/LoginView.vue:28](../../frontend/src/views/LoginView.vue#L28). Server-side, the form fields come through `OAuth2PasswordRequestForm`. See [app/api/auth.py:16](../../app/api/auth.py#L16).
- **Create login:** `email` 3–255 chars, `password` 10–256 chars, `role` defaults to `user` and must be `admin` or `user` (else 400 `BAD_ROLE`). See [app/api/settings.py:482](../../app/api/settings.py#L482) and [app/api/settings.py:539](../../app/api/settings.py#L539).
- **Update login:** at least one updatable field required (else 400); role must be `admin`/`user` if present. See [app/api/settings.py:574](../../app/api/settings.py#L574).
- **Reset password:** new password 10–256 chars. See [app/api/settings.py:495](../../app/api/settings.py#L495).
- **Duplicate email on create:** 409 `DUPLICATE_EMAIL`. See [app/api/settings.py:554](../../app/api/settings.py#L554).

## States

- **Unauthenticated:** no valid token; any protected route redirects to `#/login`. `isAuthenticated` is `email && getToken()`. See [frontend/src/stores/auth.ts:28](../../frontend/src/stores/auth.ts#L28).
- **Authenticated:** valid, unexpired token present; `get_current_user` resolves a `User(email=...)`. See [app/auth.py:172](../../app/auth.py#L172).
- **Expired / revoked:** token decode fails or the user is no longer active → 401 → client clears token and redirects to login. See [app/auth.py:184](../../app/auth.py#L184) and [frontend/src/services/http.ts:71](../../frontend/src/services/http.ts#L71).
- **Auth-user record states:** `is_active` TRUE/FALSE; `role` `admin`/`user`; `last_login_at` updated on successful DB-path login; `password_reset_at` set on admin reset. See [migrations/045_auth_users.sql:11](../../migrations/045_auth_users.sql#L11) and [app/services/auth_users.py:154](../../app/services/auth_users.py#L154).

## Dependencies

- **Postgres** — `auth_users` table is the credential store. See [migrations/045_auth_users.sql](../../migrations/045_auth_users.sql).
- **Redis** — used by the rate-limit and idempotency middleware, not by login itself. Login does not require Redis. See [app/middleware/rate_limit.py:27](../../app/middleware/rate_limit.py#L27) and [app/middleware/idempotency.py:49](../../app/middleware/idempotency.py#L49).
- **`API_SECRET_KEY`** — required setting; JWT signing key. See [app/config.py:38](../../app/config.py#L38).
- **`AUTH_USERS`** — required setting; bootstrap seed source + fallback registry. See [app/config.py:39](../../app/config.py#L39).
- **bcrypt** — password hashing (direct, not passlib). See [app/services/auth_users.py:20](../../app/services/auth_users.py#L20).
- **python-jose (`jose`)** — JWT encode/decode. See [app/auth.py:25](../../app/auth.py#L25).

## Error Handling

- **Wrong credentials:** `POST /v1/auth/login` returns 401 `Incorrect email or password`. See [app/api/auth.py:22](../../app/api/auth.py#L22). The client maps a 401 on the login path to a friendly message and does not redirect-loop. See [frontend/src/stores/auth.ts:55](../../frontend/src/stores/auth.ts#L55) and [frontend/src/services/http.ts:79](../../frontend/src/services/http.ts#L79).
- **Missing / invalid token on a protected route:** 401 `Could not validate credentials`. See [app/auth.py:164](../../app/auth.py#L164).
- **Admin-gate failure:** 403 with body `{"code": "ADMIN_ONLY", "message": ...}` from `require_admin`. See [app/security/roles.py:113](../../app/security/roles.py#L113). The diagnostics endpoints use an inline equivalent 403 `ADMIN_ONLY`. See [app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534).
- **DB outage at login:** logged, then env-CSV fallback attempted; login still succeeds for known env users. See [app/auth.py:129](../../app/auth.py#L129).
- **`touch_last_login` failure:** logged as a warning; never blocks login. See [app/services/auth_users.py:154](../../app/services/auth_users.py#L154).
- **All API errors** are wrapped in the `{success, data, error, meta}` envelope by middleware; the locked error-code → HTTP map includes `UNAUTHORIZED` (401), `FORBIDDEN` (403), `ADMIN_ONLY` (403). See [app/middleware/envelope.py:41](../../app/middleware/envelope.py#L41).

## Permissions

The repository's effective authorization model today is:

1. **JWT presence + validity** — every protected route depends on `get_current_user`. A valid, unexpired, active-user token is required. See [app/auth.py:172](../../app/auth.py#L172).
2. **A single hardcoded bootstrap-admin email gate** — `johndean@vin.com`. Admin-gated routes call `require_admin(user)` / `is_admin(user)` which, with no `role` argument supplied, compares `user.email` against `LEGACY_ADMIN_EMAIL`. See [app/security/roles.py:62](../../app/security/roles.py#L62). Two diagnostics endpoints inline the same `user.email != "johndean@vin.com"` check. See [app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534) and [app/api/diagnostics.py:632](../../app/api/diagnostics.py#L632).
3. **One client-side route guard** — the only `adminOnly` route is `/admin/help`; the guard compares `auth.email` to a UI mirror of the same email. This is a UX convenience, not a security boundary; the server is authoritative. See [frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63).

`PARTIALLY IMPLEMENTED` — role tiers are NOT active as an authorization mechanism. The `auth_users.role` column exists (migration 045) and is populated/managed, but `get_current_user` does NOT read it into the principal, and no `require_admin` callsite passes `role=user.role`. The `is_admin(..., role=...)` parameter exists but is unused by callers, so a row with `role='admin'` confers no admin power unless its email is the hardcoded legacy admin. See [app/security/roles.py:88](../../app/security/roles.py#L88) and [app/auth.py:172](../../app/auth.py#L172). Treat all admin power as resolving to the single `johndean@vin.com` identity.

Admin-gated surfaces that currently call the gate: Settings auth-users CRUD ([app/api/settings.py:531](../../app/api/settings.py#L531)), Settings types ([app/api/settings.py:322](../../app/api/settings.py#L322)), email templates ([app/api/email_templates.py:223](../../app/api/email_templates.py#L223)), email debug ([app/api/email_debug.py:53](../../app/api/email_debug.py#L53)), help-article admin routes ([app/api/help.py:461](../../app/api/help.py#L461)), session trash/restore/permanent-delete ([app/api/sessions.py:276](../../app/api/sessions.py#L276)), and lock override ([app/api/locks.py:225](../../app/api/locks.py#L225)).

## Reporting Impacts

- Successful DB-path logins update `auth_users.last_login_at`, which is surfaced in the auth-user listing. See [app/services/auth_users.py:154](../../app/services/auth_users.py#L154) and [app/api/settings.py:476](../../app/api/settings.py#L476).
- `last_login_at` and `password_reset_at` are exposed via `GET /v1/settings/auth-users` for an admin operator to review login recency and last reset. See [app/api/settings.py:506](../../app/api/settings.py#L506).
- No login-event analytics table, dashboard, or aggregate login report was found. `IMPLEMENTATION NOT FOUND`.

## Audit Requirements

- **Auth-user lifecycle changes are audited.** Add / update / reset-password / delete each insert an `audit_events` row with `actor_email`, a `kind` (`settings.auth_user.add` / `.update` / `.reset_password` / `.delete`), and a human summary. See [app/api/settings.py:561](../../app/api/settings.py#L561), [:605](../../app/api/settings.py#L605), [:627](../../app/api/settings.py#L627), [:663](../../app/api/settings.py#L663).
- **Login events themselves are NOT written to `audit_events`.** A successful login updates `last_login_at` but does not append an audit row. `IMPLEMENTATION NOT FOUND` for login/logout audit-event rows.
- **Request correlation:** every response carries an `x-request-id` (minted or echoed from inbound). This supports support-ticket / log correlation but is not a login audit record. See [app/middleware/request_id.py:16](../../app/middleware/request_id.py#L16).

## Data Relationships

- `auth_users` is the authentication identity store, keyed by `id` (UUID) with a unique index on `lower(email)`. See [migrations/045_auth_users.sql:11](../../migrations/045_auth_users.sql#L11).
- The JWT `sub` claim carries the lowercased email — the link between a token and an `auth_users` row is the email, not the UUID. See [app/auth.py:156](../../app/auth.py#L156).
- `audit_events.actor_email` records the acting principal's email for auth-user management writes — relating an action back to the logged-in identity. See [app/api/settings.py:562](../../app/api/settings.py#L562).
- `auth_users` is distinct from the `people` directory table also managed under Settings (people have `name`, `avatar_color`, etc. and are a separate concept from login credentials). See [app/api/settings.py:95](../../app/api/settings.py#L95). `NOT VERIFIED IN CODE` that `auth_users` and `people` are joined anywhere.

## Known Constraints

- **Single bootstrap admin.** All admin authority resolves to `johndean@vin.com`; the role column is not yet an authorization input. See [app/security/roles.py:54](../../app/security/roles.py#L54) and [app/auth.py:172](../../app/auth.py#L172).
- **Plaintext `AUTH_USERS` env CSV remains.** It is the seed source and a live fallback registry; this is acknowledged debt. See [app/auth.py:1-14](../../app/auth.py#L1) and [migrations/045_auth_users.sql:3](../../migrations/045_auth_users.sql#L3).
- **No token revocation / refresh.** Tokens are stateless HS256 with an 8-hour expiry; logout is client-side disposal only. See [app/auth.py:153](../../app/auth.py#L153) and [frontend/src/stores/auth.ts:66](../../frontend/src/stores/auth.ts#L66).
- **No multi-factor auth, no SSO/OAuth provider, no password complexity beyond min-length.** `IMPLEMENTATION NOT FOUND`.
- **Token + email stored in `localStorage`.** Accessible to same-origin JS. See [frontend/src/services/http.ts:21](../../frontend/src/services/http.ts#L21) and [frontend/src/stores/auth.ts:12](../../frontend/src/stores/auth.ts#L12).
- **bcrypt 72-byte limit:** two passwords sharing their first 72 bytes collide. See [app/services/auth_users.py:49](../../app/services/auth_users.py#L49).

## Source Verification
- **Files Used:** app/api/auth.py, app/auth.py, app/security/roles.py, app/services/auth_users.py, app/api/settings.py, app/api/diagnostics.py, app/middleware/request_id.py, app/middleware/envelope.py, app/config.py, app/main.py, migrations/045_auth_users.sql, frontend/src/views/LoginView.vue, frontend/src/stores/auth.ts, frontend/src/router/index.ts, frontend/src/services/http.ts, frontend/src/services/api.ts
- **Components Used:** LoginView.vue (login screen); auth Pinia store; vue-router guard
- **APIs Used:** POST /v1/auth/login, GET /v1/auth/me, GET/POST/PUT/DELETE /v1/settings/auth-users, POST /v1/settings/auth-users/{id}/reset-password
- **Database Tables Used:** auth_users, audit_events (write-only for auth-user changes)
- **Permission Logic Used:** JWT presence/validity (get_current_user) + LEGACY_ADMIN_EMAIL (`johndean@vin.com`) gate via require_admin/is_admin + one client-side adminOnly route guard
- **Confidence Score:** High — all behaviors traced to source; the only unverified item is the Settings auth-and-logins Vue sub-component, flagged inline.
- **Evidence Links:** [app/auth.py:100](../../app/auth.py#L100), [app/auth.py:153](../../app/auth.py#L153), [app/api/auth.py:15](../../app/api/auth.py#L15), [app/security/roles.py:62](../../app/security/roles.py#L62), [app/config.py:42](../../app/config.py#L42), [frontend/src/router/index.ts:53](../../frontend/src/router/index.ts#L53), [frontend/src/stores/auth.ts:44](../../frontend/src/stores/auth.ts#L44), [app/api/settings.py:529](../../app/api/settings.py#L529)
