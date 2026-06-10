# Authentication & Access — Demo Questions

> Code-verified Q&A for rounds.vin authentication. Every answer is traceable to source. Paths are relative to this file (`ai-demo-knowledge/demo-questions/`). Unproven items are tagged `IMPLEMENTATION NOT FOUND` / `NOT VERIFIED IN CODE` / `PARTIALLY IMPLEMENTED`.

## User

### Q: How do I sign in?
- **Verified Answer:** Go to `#/login`, enter your VIN email and password, and click "Sign in". A successful login takes you to the dashboard (or back to the page you were trying to reach). Empty email or password is rejected client-side with an "Email and password required" toast.
- **Supporting Evidence:** `signIn()` validates non-empty inputs, calls `auth.login`, then routes to `route.query.next || '/dashboard'`.
- **Source Files:** [frontend/src/views/LoginView.vue:26](../../frontend/src/views/LoginView.vue#L26)
- **API References:** POST /v1/auth/login
- **Database References:** auth_users

### Q: How long does my session last before I have to sign in again?
- **Verified Answer:** 8 hours. The token expiry is `ACCESS_TOKEN_EXPIRE_MINUTES`, default 480 minutes. The "Keep me signed in for 8 hours" checkbox on the login screen is a static label reflecting this fixed lifetime — it doesn't change behavior.
- **Supporting Evidence:** Token `exp` is `now + ACCESS_TOKEN_EXPIRE_MINUTES`; default is 480.
- **Source Files:** [app/auth.py:154](../../app/auth.py#L154), [app/config.py:43](../../app/config.py#L43), [frontend/src/views/LoginView.vue:88](../../frontend/src/views/LoginView.vue#L88)
- **API References:** POST /v1/auth/login
- **Database References:** none

### Q: What happens if I enter the wrong password?
- **Verified Answer:** Login fails with a 401 and you see "Incorrect email or password". You stay on the login screen — no redirect loop.
- **Supporting Evidence:** Backend raises 401 `Incorrect email or password`; the client maps a 401 on the login path to that message and suppresses the auto-redirect when already on `#/login`.
- **Source Files:** [app/api/auth.py:22](../../app/api/auth.py#L22), [frontend/src/stores/auth.ts:55](../../frontend/src/stores/auth.ts#L55), [frontend/src/services/http.ts:79](../../frontend/src/services/http.ts#L79)
- **API References:** POST /v1/auth/login
- **Database References:** auth_users

### Q: What happens when my session expires while I'm working?
- **Verified Answer:** The next API call returns 401; the app clears your stored token and sends you back to the login screen automatically.
- **Supporting Evidence:** On a non-anonymous 401 the HTTP wrapper clears the token and `window.location.replace('/#/login')`.
- **Source Files:** [frontend/src/services/http.ts:71](../../frontend/src/services/http.ts#L71), [app/auth.py:194](../../app/auth.py#L194)
- **API References:** any Bearer-protected endpoint
- **Database References:** auth_users

### Q: Does staying signed in survive a page refresh?
- **Verified Answer:** Yes. The token and your email are stored in the browser; on reload the app re-confirms the token against `/v1/auth/me`, and the saved email lets the route guard pass without flashing the login screen.
- **Supporting Evidence:** `bootstrap()` calls `authApi.me()`; email is persisted to `rounds_user_email_v1`, token to `rounds_jwt_v1`.
- **Source Files:** [frontend/src/stores/auth.ts:30](../../frontend/src/stores/auth.ts#L30), [frontend/src/services/http.ts:19](../../frontend/src/services/http.ts#L19)
- **API References:** GET /v1/auth/me
- **Database References:** auth_users

### Q: How do I sign out?
- **Verified Answer:** Logout clears the token and saved email from your browser. There is no server-side session to revoke — the token simply stops being sent.
- **Supporting Evidence:** `logout()` sets token null and clears persisted email; `IMPLEMENTATION NOT FOUND` for any `/v1/auth/logout` route.
- **Source Files:** [frontend/src/stores/auth.ts:66](../../frontend/src/stores/auth.ts#L66)
- **API References:** none
- **Database References:** none

## Operations

### Q: How are user accounts created — is there self-signup?
- **Verified Answer:** No self-signup. An admin creates a login via `POST /v1/settings/auth-users` (email, password, role). On first boot the table is also seeded once from the `AUTH_USERS` env CSV if empty.
- **Supporting Evidence:** Create endpoint is admin-gated; `seed_from_env_if_empty` populates from env only when the table is empty.
- **Source Files:** [app/api/settings.py:536](../../app/api/settings.py#L536), [app/services/auth_users.py:176](../../app/services/auth_users.py#L176), [app/main.py:73](../../app/main.py#L73)
- **API References:** POST /v1/settings/auth-users
- **Database References:** auth_users

### Q: A user is locked out — how do I reset their password?
- **Verified Answer:** An admin calls `POST /v1/settings/auth-users/{id}/reset-password` with the new plaintext (10–256 chars). It bcrypt-hashes the new password, sets `password_reset_at`, and writes an audit row. Passwords cannot be changed via PUT.
- **Supporting Evidence:** Reset endpoint hashes + sets `password_reset_at`; PATCH model only carries `role`/`is_active`.
- **Source Files:** [app/api/settings.py:613](../../app/api/settings.py#L613), [app/api/settings.py:488](../../app/api/settings.py#L488)
- **API References:** POST /v1/settings/auth-users/{id}/reset-password
- **Database References:** auth_users, audit_events

### Q: How do I disable a user without deleting them?
- **Verified Answer:** Set `is_active = false` via `PUT /v1/settings/auth-users/{id}`. Inactive users can't log in and fail the per-request active check. (You cannot disable the only active admin — see last-admin protection.)
- **Supporting Evidence:** Login rejects `is_active=FALSE`; `user_is_active` filters on `is_active = TRUE`.
- **Source Files:** [app/auth.py:123](../../app/auth.py#L123), [app/services/auth_users.py:136](../../app/services/auth_users.py#L136), [app/api/settings.py:569](../../app/api/settings.py#L569)
- **API References:** PUT /v1/settings/auth-users/{id}
- **Database References:** auth_users

### Q: Login is failing right after a deploy — what's the recovery path?
- **Verified Answer:** If the `auth_users` table is empty (seed failed mid-deploy), the operator can call `POST /v1/diag/reseed-auth-users` to re-run the seed against the live DB without a redeploy. It's idempotent (no-op if rows exist). Meanwhile, known users in the `AUTH_USERS` env CSV can still log in via the fallback path.
- **Supporting Evidence:** Reseed endpoint exists and re-invokes `seed_from_env_if_empty`; `authenticate` falls back to the env CSV on missing row / DB error.
- **Source Files:** [app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534), [app/auth.py:132](../../app/auth.py#L132)
- **API References:** POST /v1/diag/reseed-auth-users, POST /v1/auth/login
- **Database References:** auth_users

### Q: If Postgres is briefly down, can people still log in?
- **Verified Answer:** Yes, for users present in the `AUTH_USERS` env CSV. The DB error is logged and authentication falls back to a constant-time compare against the env registry. Users only in the DB (not in env) cannot log in during the outage.
- **Supporting Evidence:** `authenticate` wraps the DB path in try/except and falls through to `_ENV_FALLBACK_DB`; `get_current_user` does the same for the active-check.
- **Source Files:** [app/auth.py:129](../../app/auth.py#L129), [app/auth.py:197](../../app/auth.py#L197)
- **API References:** POST /v1/auth/login, GET /v1/auth/me
- **Database References:** auth_users

### Q: How do I see who last logged in?
- **Verified Answer:** `GET /v1/settings/auth-users` returns each login's `last_login_at` and `password_reset_at` (admin only). `last_login_at` is updated on each successful DB-path login.
- **Supporting Evidence:** Projection includes both timestamps; `touch_last_login` updates `last_login_at`.
- **Source Files:** [app/api/settings.py:476](../../app/api/settings.py#L476), [app/services/auth_users.py:154](../../app/services/auth_users.py#L154)
- **API References:** GET /v1/settings/auth-users
- **Database References:** auth_users

## Finance

### Q: Does authentication call any paid/metered external service per login?
- **Verified Answer:** No. Login uses local bcrypt verification and local JWT signing against Postgres only — no external identity provider, no per-login metered API. (Gemini/STT/GCS costs are in the processing pipeline, not auth.)
- **Supporting Evidence:** `authenticate` queries `auth_users` + bcrypt; token is signed locally with `API_SECRET_KEY`. No external auth integration found.
- **Source Files:** [app/auth.py:100](../../app/auth.py#L100), [app/auth.py:153](../../app/auth.py#L153)
- **API References:** POST /v1/auth/login
- **Database References:** auth_users

## Compliance

### Q: How are passwords stored?
- **Verified Answer:** As bcrypt hashes (`$2b$…`) with a per-hash salt, never in plaintext at rest in the DB. Passwords are never returned by any API. The legacy `AUTH_USERS` env CSV still holds plaintext as a seed/fallback source (acknowledged debt).
- **Supporting Evidence:** `hash_password` uses `bcrypt.hashpw(secret, bcrypt.gensalt())`; the auth-user projection whitelists columns excluding `password_hash`; env CSV is plaintext.
- **Source Files:** [app/services/auth_users.py:72](../../app/services/auth_users.py#L72), [app/api/settings.py:499](../../app/api/settings.py#L499), [app/auth.py:1](../../app/auth.py#L1)
- **API References:** GET /v1/settings/auth-users (password_hash omitted)
- **Database References:** auth_users.password_hash

### Q: Are account management actions audited?
- **Verified Answer:** Yes — creating, updating, resetting a password, or deleting a login each writes an `audit_events` row with the acting admin's email (`actor_email`) and a `kind` such as `settings.auth_user.reset_password`. Login and logout events themselves are NOT written to the audit ledger.
- **Supporting Evidence:** Each settings auth-user write inserts into `audit_events`; `IMPLEMENTATION NOT FOUND` for login-event audit rows.
- **Source Files:** [app/api/settings.py:561](../../app/api/settings.py#L561), [app/api/settings.py:627](../../app/api/settings.py#L627)
- **API References:** POST/PUT/DELETE /v1/settings/auth-users, .../reset-password
- **Database References:** audit_events

### Q: Can you ever remove the last administrator?
- **Verified Answer:** No. The system refuses to demote, deactivate, or delete the only remaining active admin and returns 409 `LAST_ADMIN_PROTECTED`.
- **Supporting Evidence:** Update and delete handlers check `_count_active_admins() <= 1` before applying a demotion/disable/delete.
- **Source Files:** [app/api/settings.py:580](../../app/api/settings.py#L580), [app/api/settings.py:651](../../app/api/settings.py#L651)
- **API References:** PUT /v1/settings/auth-users/{id}, DELETE /v1/settings/auth-users/{id}
- **Database References:** auth_users

### Q: How are credentials protected in transit and what algorithm signs the token?
- **Verified Answer:** Tokens are HS256 JWTs signed with `API_SECRET_KEY`. CORS limits browser origins to `https://rounds.vin` plus localhost dev. The token + email are stored in browser `localStorage` (an acknowledged XSS-reachable surface). `NOT VERIFIED IN CODE`: TLS termination is infrastructure-level, not in this repo.
- **Supporting Evidence:** `jwt.encode(payload, API_SECRET_KEY, algorithm=ALGORITHM)` with `ALGORITHM="HS256"`; CORS allow-list in `main.py`; token in `localStorage`.
- **Source Files:** [app/auth.py:157](../../app/auth.py#L157), [app/config.py:42](../../app/config.py#L42), [app/main.py:115](../../app/main.py#L115), [frontend/src/services/http.ts:21](../../frontend/src/services/http.ts#L21)
- **API References:** POST /v1/auth/login
- **Database References:** none

### Q: Is there multi-factor auth or SSO?
- **Verified Answer:** No. There is no MFA, no SSO/OAuth provider, and no email-verification flow in this repo. Authentication is single-factor email+password.
- **Supporting Evidence:** `IMPLEMENTATION NOT FOUND` for any MFA/SSO/OAuth provider integration; only the username/password login exists.
- **Source Files:** [app/api/auth.py:15](../../app/api/auth.py#L15)
- **API References:** POST /v1/auth/login
- **Database References:** auth_users

## Administrator

### Q: Who counts as an admin in the system today?
- **Verified Answer:** Effectively one identity: the email `johndean@vin.com` (`LEGACY_ADMIN_EMAIL`). Admin-gated routes call `require_admin(user)`, which checks `user.email == "johndean@vin.com"`. The `auth_users.role` column exists and stores `admin`/`user`, but the request principal does not read it, so `role='admin'` on any other account does not currently grant admin power.
- **Supporting Evidence:** `is_admin` with no `role` arg compares email to `LEGACY_ADMIN_EMAIL`; no callsite passes `role=`; `get_current_user` builds `User` with only `email`.
- **Source Files:** [app/security/roles.py:62](../../app/security/roles.py#L62), [app/auth.py:172](../../app/auth.py#L172)
- **API References:** all `require_admin`-gated routes (e.g. /v1/settings/auth-users)
- **Database References:** auth_users.role (stored, not used for authz)

### Q: Which screens/endpoints are admin-gated?
- **Verified Answer:** Settings auth-users CRUD, Settings session types, email templates, email diagnostics, help-article admin routes, session trash/restore/permanent-delete, lock override, and the two inline-gated diagnostics reseed/clear endpoints. On the client, only `/admin/help` carries an `adminOnly` route guard.
- **Supporting Evidence:** `require_admin`/`is_admin` callsites across settings.py, sessions.py, help.py, email_templates.py, email_debug.py, locks.py; inline email checks in diagnostics.py; `meta: { adminOnly: true }` only on `/admin/help`.
- **Source Files:** [app/api/settings.py:322](../../app/api/settings.py#L322), [app/api/sessions.py:276](../../app/api/sessions.py#L276), [app/api/locks.py:225](../../app/api/locks.py#L225), [app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534), [frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63)
- **API References:** /v1/settings/*, /v1/sessions/* (trash/restore/permanent), /v1/help/* admin, /v1/diag/*
- **Database References:** auth_users, audit_events

### Q: Is the role-based permission system live?
- **Verified Answer:** `PARTIALLY IMPLEMENTED`. The helper `app/security/roles.py` is now imported and called by real endpoints, and migration 045 stores `role`. But authorization still resolves to the single hardcoded admin email because `get_current_user` does not load `auth_users.role` and no caller passes `role=user.role`. The role-based code path (`is_admin(..., role="admin")`) is unit-tested but unreachable in production request flow.
- **Supporting Evidence:** `require_admin` callsites omit `role=`; `User` dataclass has only `email`; helper docstring describes the future wiring as not-yet-done.
- **Source Files:** [app/security/roles.py:88](../../app/security/roles.py#L88), [app/auth.py:36](../../app/auth.py#L36), [migrations/045_auth_users.sql:15](../../migrations/045_auth_users.sql#L15)
- **API References:** none (model-level)
- **Database References:** auth_users.role

### Q: How do I add a second admin so I can safely rotate the first?
- **Verified Answer:** Create or update a login with `role='admin'` via Settings auth-users. This satisfies the last-admin guard (`_count_active_admins > 1`) for DB-level operations. Caveat: because authz still resolves to the `johndean@vin.com` email gate, a second `role='admin'` row is recorded and protected in the DB but does not yet confer admin authority at the API gate. Plan the rotation accordingly.
- **Supporting Evidence:** Create/update accept `role='admin'`; `_count_active_admins` counts `role='admin' AND is_active`; authz gate is still email-based.
- **Source Files:** [app/api/settings.py:536](../../app/api/settings.py#L536), [app/api/settings.py:513](../../app/api/settings.py#L513), [app/security/roles.py:88](../../app/security/roles.py#L88)
- **API References:** POST/PUT /v1/settings/auth-users
- **Database References:** auth_users

### Q: What does the `AUTH_USERS` env var do now that there's a DB table?
- **Verified Answer:** Two roles: (1) one-time seed source on first boot when the table is empty, and (2) live fallback registry when the DB has no matching row or errors. After a successful seed it can be cleared for normal operation, but keeping it preserves the outage fallback.
- **Supporting Evidence:** `seed_from_env_if_empty` reads it on empty table; `_ENV_FALLBACK_DB` is parsed from it at module load and used on DB miss/error.
- **Source Files:** [app/services/auth_users.py:176](../../app/services/auth_users.py#L176), [app/auth.py:86](../../app/auth.py#L86), [app/config.py:39](../../app/config.py#L39)
- **API References:** POST /v1/auth/login
- **Database References:** auth_users

## Power User

### Q: How do I authenticate API calls directly (curl/Postman)?
- **Verified Answer:** POST form-encoded `username` + `password` to `/v1/auth/login`, read `access_token` from the response, then send `Authorization: Bearer <token>` on subsequent calls. `GET /v1/auth/me` confirms the token resolves to your email.
- **Supporting Evidence:** Login uses `OAuth2PasswordRequestForm` (form body); the client sends `Authorization: Bearer`; `/me` returns `{email}`.
- **Source Files:** [app/api/auth.py:16](../../app/api/auth.py#L16), [frontend/src/services/api.ts:28](../../frontend/src/services/api.ts#L28), [frontend/src/services/http.ts:43](../../frontend/src/services/http.ts#L43)
- **API References:** POST /v1/auth/login, GET /v1/auth/me
- **Database References:** auth_users

### Q: What's inside the JWT?
- **Verified Answer:** A `sub` claim (your lowercased email) and an `exp` claim (issue time + 8 hours), signed HS256 with `API_SECRET_KEY`. No roles or scopes are embedded.
- **Supporting Evidence:** `payload = {"sub": email.lower(), "exp": expire}`; HS256.
- **Source Files:** [app/auth.py:156](../../app/auth.py#L156)
- **API References:** POST /v1/auth/login
- **Database References:** none

### Q: Is email case-sensitive at login?
- **Verified Answer:** No. Lookups compare `lower(email)`, and a unique index on `lower(email)` ensures only one row per case-folded email. The JWT subject is stored lowercased.
- **Supporting Evidence:** `lookup_user`/`user_is_active` use `lower(email) = lower(:e)`; unique index `auth_users_email_lower_uq`; token `sub` lowercased.
- **Source Files:** [app/services/auth_users.py:112](../../app/services/auth_users.py#L112), [migrations/045_auth_users.sql:26](../../migrations/045_auth_users.sql#L26), [app/auth.py:156](../../app/auth.py#L156)
- **API References:** POST /v1/auth/login
- **Database References:** auth_users

### Q: What happens with a very long password (>72 bytes)?
- **Verified Answer:** It is truncated to the first 72 bytes at a codepoint boundary, applied identically on hash and verify, so round-trips are stable. Two passwords sharing their first 72 bytes would collide.
- **Supporting Evidence:** `_truncate_to_bcrypt_limit` cuts at 72 bytes and is called in both `hash_password` and `verify_password`.
- **Source Files:** [app/services/auth_users.py:57](../../app/services/auth_users.py#L57)
- **API References:** POST /v1/auth/login, POST /v1/settings/auth-users
- **Database References:** auth_users.password_hash

### Q: If I have a DB account with a new password but the env CSV has the old one, which wins?
- **Verified Answer:** The DB wins. If a matching `auth_users` row exists and the bcrypt check fails, authentication fails immediately — it does NOT fall through to the env CSV. The env fallback only applies when there's no DB row or the DB errors.
- **Supporting Evidence:** On a found row with failing verify, `authenticate` returns None without falling through; comment "known user, wrong password — do NOT fall through".
- **Source Files:** [app/auth.py:125](../../app/auth.py#L125)
- **API References:** POST /v1/auth/login
- **Database References:** auth_users

## Source Verification
- **Files Used:** app/api/auth.py, app/auth.py, app/security/roles.py, app/services/auth_users.py, app/api/settings.py, app/api/diagnostics.py, app/config.py, app/main.py, migrations/045_auth_users.sql, frontend/src/views/LoginView.vue, frontend/src/stores/auth.ts, frontend/src/router/index.ts, frontend/src/services/http.ts, frontend/src/services/api.ts
- **Components Used:** LoginView.vue, auth Pinia store, vue-router guard, http.ts wrapper
- **APIs Used:** POST /v1/auth/login, GET /v1/auth/me, /v1/settings/auth-users (GET/POST/PUT/DELETE + reset-password), POST /v1/diag/reseed-auth-users
- **Database Tables Used:** auth_users, audit_events
- **Permission Logic Used:** JWT (get_current_user) + LEGACY_ADMIN_EMAIL gate via require_admin/is_admin (role kwarg unused) + client adminOnly guard
- **Confidence Score:** High — every answer traced to code; the one infra item (TLS) and the unverified Settings sub-component are flagged inline.
- **Evidence Links:** [app/auth.py:100](../../app/auth.py#L100), [app/auth.py:125](../../app/auth.py#L125), [app/auth.py:156](../../app/auth.py#L156), [app/security/roles.py:62](../../app/security/roles.py#L62), [app/api/settings.py:580](../../app/api/settings.py#L580), [app/services/auth_users.py:176](../../app/services/auth_users.py#L176), [frontend/src/services/http.ts:71](../../frontend/src/services/http.ts#L71)
