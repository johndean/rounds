# Authentication & Access — Technical Spec

> Module key: `authentication`. Every claim is traceable to source. Unproven items are tagged `NOT VERIFIED IN CODE`, `IMPLEMENTATION NOT FOUND`, or `PARTIALLY IMPLEMENTED`. Paths are relative to this file (`docs/technical/`).

## Architecture

Stateless JWT bearer auth. The FastAPI backend issues an HS256 token on `POST /v1/auth/login` and validates it on every protected route via a `get_current_user` dependency. The Vue 3 + Pinia frontend stores the token in `localStorage`, injects it as an `Authorization: Bearer` header on every request, and gates routes with a `vue-router` `beforeEach` guard.

Request lifecycle (server, outermost first): `RequestIdMiddleware` → `EnvelopeMiddleware` → `IdempotencyMiddleware` → CORS → route handler. The auth dependency runs inside the handler resolution. See the mount order in [app/main.py:115-150](../../app/main.py#L115) (note: `add_middleware` registers in reverse, so the last-added `RequestIdMiddleware` is outermost — see the lifespan docstring at [app/main.py:11](../../app/main.py#L11)).

Credential store: Postgres `auth_users` (bcrypt). A plaintext `AUTH_USERS` env CSV is both the one-time seed source and a runtime fallback. See [app/auth.py:1-14](../../app/auth.py#L1).

## Frontend Components

- **`LoginView.vue`** ([frontend/src/views/LoginView.vue](../../frontend/src/views/LoginView.vue)) — the `#/login` screen. Local refs `email`, `pw`, `busy`; `signIn()` validates non-empty inputs, calls `auth.login`, toasts the result, and `router.replace`s to `route.query.next` or `/dashboard`. Test ids: `login-email`, `login-password`, `login-submit`.
- **`auth` store** ([frontend/src/stores/auth.ts](../../frontend/src/stores/auth.ts)) — Pinia setup store. State: `email`, `isLoading`, `error`. Getter `isAuthenticated = Boolean(email && getToken())`. Actions `bootstrap()`, `login()`, `logout()`. Persists email to `localStorage` key `rounds_user_email_v1` so the guard passes synchronously on refresh.
- **Router guard** ([frontend/src/router/index.ts:53](../../frontend/src/router/index.ts#L53)) — `beforeEach`: public routes pass; unauthenticated → `login` with `?next`; `meta.adminOnly` routes require `auth.email === LEGACY_ADMIN_EMAIL` (UI mirror of `johndean@vin.com`) else redirect to `dashboard`. The only `adminOnly` route is `/admin/help`. See [frontend/src/router/index.ts:44](../../frontend/src/router/index.ts#L44).
- **HTTP wrapper** ([frontend/src/services/http.ts](../../frontend/src/services/http.ts)) — `http<T>()` injects `Authorization: Bearer <token>` unless `opts.anonymous`; `setToken`/`getToken` manage `localStorage` key `rounds_jwt_v1`; on a non-login 401 it clears the token and `window.location.replace('/#/login')`; auto-unwraps the `{success,data,error,meta}` envelope.
- **API service** ([frontend/src/services/api.ts:27](../../frontend/src/services/api.ts#L27)) — `auth.login(email, password)` posts form-body `{username, password}` with `anonymous: true`; `auth.me()` GETs `/v1/auth/me`. `AuthUser`/`AuthUserPatch` types and `settingsApi` auth-user methods are defined here ([frontend/src/services/api.ts:764](../../frontend/src/services/api.ts#L764)).

The Settings auth-and-logins Vue sub-component is `NOT VERIFIED IN CODE` in this assignment (the API + service layer are verified).

## Backend Services

- **`app/api/auth.py`** — router `prefix="/v1/auth"`. `POST /login` (OAuth2 form) → `authenticate` → `create_access_token`. `GET /me` → returns `{"email": user.email}` for the `CurrentUser` principal. See [app/api/auth.py:15](../../app/api/auth.py#L15).
- **`app/auth.py`** — `authenticate(email, password)` (DB-first, env-CSV fallback), `create_access_token(email)` (HS256, `sub`+`exp`), `oauth2_scheme` (`OAuth2PasswordBearer(auto_error=False)`), `get_current_user` (decode + active check + env fallback), and `CurrentUser = Annotated[User, Depends(get_current_user)]`. A lazy module-scoped sync `Engine` (`pool_pre_ping=True`, `pool_size=5`, `max_overflow=2`) serves auth queries. See [app/auth.py:73](../../app/auth.py#L73).
- **`app/services/auth_users.py`** — pure functions over `auth_users`: `hash_password`, `verify_password` (both bcrypt with 72-byte truncation), `lookup_user`, `user_is_active`, `touch_last_login`, `seed_from_env_if_empty`. Uses `bcrypt` directly (not passlib — passlib 1.7.x self-test breaks under bcrypt 4.x; see comment at [app/services/auth_users.py:25](../../app/services/auth_users.py#L25)).
- **`app/security/roles.py`** — `LEGACY_ADMIN_EMAIL = "johndean@vin.com"`, `is_admin(user, *, role=None)`, `require_admin(user, *, role=None, message)`. See [app/security/roles.py:54](../../app/security/roles.py#L54).
- **`app/api/settings.py`** — auth-user CRUD (`/v1/settings/auth-users`), each guarded by `require_admin`. See [app/api/settings.py:529](../../app/api/settings.py#L529).

## APIs

| Method | Path | Auth | Body / params | Success | Notes |
|---|---|---|---|---|---|
| POST | `/v1/auth/login` | none (public) | form `username`, `password` | `{access_token, token_type:"bearer", expires_in}` | 401 on bad creds. [app/api/auth.py:15](../../app/api/auth.py#L15) |
| GET | `/v1/auth/me` | Bearer | — | `{email}` | 401 if token invalid/inactive. [app/api/auth.py:31](../../app/api/auth.py#L31) |
| GET | `/v1/settings/auth-users` | Bearer + admin | — | `AuthUser[]` (no `password_hash`) | [app/api/settings.py:529](../../app/api/settings.py#L529) |
| POST | `/v1/settings/auth-users` | Bearer + admin | `{email, password, role?}` | 201 `AuthUser` | 409 `DUPLICATE_EMAIL`. [app/api/settings.py:536](../../app/api/settings.py#L536) |
| PUT | `/v1/settings/auth-users/{id}` | Bearer + admin | `{role?, is_active?}` | `AuthUser` | 409 `LAST_ADMIN_PROTECTED`. [app/api/settings.py:569](../../app/api/settings.py#L569) |
| POST | `/v1/settings/auth-users/{id}/reset-password` | Bearer + admin | `{password}` | `{email, password_reset_at}` | [app/api/settings.py:613](../../app/api/settings.py#L613) |
| DELETE | `/v1/settings/auth-users/{id}` | Bearer + admin | — | 204 | 409 `LAST_ADMIN_PROTECTED`. [app/api/settings.py:645](../../app/api/settings.py#L645) |

"admin" = `require_admin(user)` → resolves to the `johndean@vin.com` email gate (see Permissions). The login form is sent as `application/x-www-form-urlencoded` (`OAuth2PasswordRequestForm`), not JSON. See [app/api/auth.py:16](../../app/api/auth.py#L16) and [frontend/src/services/api.ts:29](../../frontend/src/services/api.ts#L29).

## Data Models

### `auth_users` (migration 045)

Source: [migrations/045_auth_users.sql](../../migrations/045_auth_users.sql).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `email` | TEXT NOT NULL | unique on `lower(email)` |
| `password_hash` | TEXT NOT NULL | bcrypt `$2b$…` |
| `role` | TEXT NOT NULL DEFAULT 'user' | `'admin'` \| `'user'` (see note below) |
| `is_active` | BOOLEAN NOT NULL DEFAULT TRUE | inactive rows cannot authenticate |
| `last_login_at` | TIMESTAMPTZ NULL | set by `touch_last_login` on DB-path login |
| `password_reset_at` | TIMESTAMPTZ NULL | set on admin reset |
| `created_at` / `updated_at` | TIMESTAMPTZ NOT NULL | `now()` defaults |

Indexes: unique `auth_users_email_lower_uq` on `lower(email)` ([migrations/045_auth_users.sql:26](../../migrations/045_auth_users.sql#L26)); partial `auth_users_active_idx` on `is_active` where TRUE ([migrations/045_auth_users.sql:30](../../migrations/045_auth_users.sql#L30)).

`PARTIALLY IMPLEMENTED`: `role` is stored, managed, and validated (`admin`/`user`), but it is NOT read into the request principal by `get_current_user` and is not used as an authorization input by any `require_admin` callsite. See "Permissions". The migration comment also lists `password_reset_at` as the only schema column beyond what login uses.

### Python types

- `User` (frozen dataclass, only field `email`). See [app/auth.py:36](../../app/auth.py#L36).
- `AuthUserRow` (frozen, slots: `id, email, password_hash, role, is_active, last_login_at`). See [app/services/auth_users.py:39](../../app/services/auth_users.py#L39).
- `TokenResponse` (Pydantic: `access_token`, `token_type="bearer"`, `expires_in`). See [app/auth.py:147](../../app/auth.py#L147).
- `AuthUserCreate` / `AuthUserPatch` / `AuthUserResetPassword` (Pydantic, Settings). See [app/api/settings.py:482](../../app/api/settings.py#L482).

### JWT payload

`{"sub": <email.lower()>, "exp": <utc-now + ACCESS_TOKEN_EXPIRE_MINUTES>}`, HS256 over `API_SECRET_KEY`. See [app/auth.py:156](../../app/auth.py#L156).

## Events

- **Audit events on auth-user mutations:** `audit_events` rows with `kind` ∈ {`settings.auth_user.add`, `settings.auth_user.update`, `settings.auth_user.reset_password`, `settings.auth_user.delete`} and `actor_email`. See [app/api/settings.py:561](../../app/api/settings.py#L561).
- **No domain event is emitted on login/logout.** `IMPLEMENTATION NOT FOUND` for any auth event publish. (Login only updates `last_login_at`.)
- The repo has a Redis pub/sub WS bridge, but it is unrelated to auth and started in the lifespan after the auth-users seed. See [app/main.py:93](../../app/main.py#L93).

## State Management

- **Server: stateless.** No session table; the JWT is the entire session. Re-validation on each request re-queries `auth_users.is_active` (DB) with env-CSV fallback. See [app/auth.py:192](../../app/auth.py#L192).
- **Client: Pinia + localStorage.** `rounds_jwt_v1` holds the token; `rounds_user_email_v1` holds the email for synchronous guard evaluation on reload. `isAuthenticated` requires both. See [frontend/src/services/http.ts:19](../../frontend/src/services/http.ts#L19) and [frontend/src/stores/auth.ts:12](../../frontend/src/stores/auth.ts#L12).
- **`bootstrap()`** re-confirms the token against `/v1/auth/me` on load, clearing it on failure. See [frontend/src/stores/auth.ts:30](../../frontend/src/stores/auth.ts#L30).

## Validation

- **Login:** client requires non-empty email+password ([frontend/src/views/LoginView.vue:28](../../frontend/src/views/LoginView.vue#L28)); server parses via `OAuth2PasswordRequestForm`.
- **JWT decode:** `JWTError` → 401; non-string `sub` → 401. See [app/auth.py:184](../../app/auth.py#L184).
- **Auth-user create:** `email` 3–255, `password` 10–256, `role` in {`admin`,`user`}. See [app/api/settings.py:482](../../app/api/settings.py#L482) and [:539](../../app/api/settings.py#L539).
- **Auth-user update:** ≥1 field; role enum check; last-admin guard. See [app/api/settings.py:573](../../app/api/settings.py#L573).
- **Reset password:** 10–256 chars. See [app/api/settings.py:495](../../app/api/settings.py#L495).
- **Email normalization:** lowercased+trimmed on create; lookups compare `lower(email)`. See [app/api/settings.py:551](../../app/api/settings.py#L551) and [app/services/auth_users.py:112](../../app/services/auth_users.py#L112).

## Security

- **Password hashing:** bcrypt with per-hash salt (`gensalt`), ~50ms by design, 72-byte codepoint-safe truncation applied symmetrically on hash + verify. `verify_password` catches all exceptions and returns False (no exception leaks as success). See [app/services/auth_users.py:72-98](../../app/services/auth_users.py#L72).
- **Token signing:** HS256 with `API_SECRET_KEY`; 8-hour expiry. See [app/auth.py:153](../../app/auth.py#L153) and [app/config.py:42](../../app/config.py#L42).
- **Env-CSV constant-time compare:** the fallback path uses a non-short-circuiting byte compare. See [app/auth.py:89](../../app/auth.py#L89).
- **`auto_error=False`** on `OAuth2PasswordBearer` lets `get_current_user` raise a consistent `_credentials_exception` (401, `WWW-Authenticate: Bearer`). See [app/auth.py:161](../../app/auth.py#L161).
- **Password never serialized:** the auth-user projection whitelists columns; `AuthUserRow.password_hash` is held server-side only. See [app/api/settings.py:500](../../app/api/settings.py#L500).
- **Known-user wrong-password does not fall through to env.** Prevents a rotated DB password from being bypassed by a stale env entry. See [app/auth.py:128](../../app/auth.py#L128).
- **CORS** is restricted to `https://rounds.vin` + localhost dev origins, `allow_credentials=True`. See [app/main.py:115](../../app/main.py#L115).
- **Known posture risks:** token + email in `localStorage` (XSS-reachable); plaintext `AUTH_USERS` env retained as seed + fallback; no token revocation/refresh; no MFA/SSO. See [frontend/src/services/http.ts:21](../../frontend/src/services/http.ts#L21) and [app/auth.py:81](../../app/auth.py#L81).

## Permissions

Two enforced layers plus one UI guard:

1. **Authentication** — `CurrentUser` dependency requires a valid, unexpired token whose `sub` resolves to an active user (DB active-check, env fallback). See [app/auth.py:172](../../app/auth.py#L172).
2. **Bootstrap-admin authorization** — `require_admin(user)` raises 403 `ADMIN_ONLY` unless `is_admin(user)` is True. With no `role` kwarg passed (no callsite passes one), `is_admin` falls to `user.email == LEGACY_ADMIN_EMAIL` (`johndean@vin.com`). See [app/security/roles.py:88](../../app/security/roles.py#L88). Two diagnostics routes inline the same check. See [app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534), [:632](../../app/api/diagnostics.py#L632).
3. **Client `adminOnly` guard** — `/admin/help` only; UI convenience, server is authoritative. See [frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63).

`PARTIALLY IMPLEMENTED` — discrepancy with prior internal notes: `app/security/roles.py` is no longer "scaffold-only / not wired." It IS imported and called by `settings.py`, `sessions.py`, `help.py`, `email_templates.py`, `email_debug.py` (`require_admin`) and `locks.py` (`is_admin`). However, the *effective authorization is unchanged* from the legacy single-email gate, because (a) `get_current_user` still does not load `auth_users.role` into `User`, and (b) no callsite supplies `role=user.role`. The role-based branch (`is_admin(..., role="admin")`) exists and is unit-tested but is dead in production paths. See [app/auth.py:172](../../app/auth.py#L172) and [app/security/roles.py:88](../../app/security/roles.py#L88).

## Integrations

- **Postgres** — credential store; via SQLAlchemy sync `Engine` for auth queries and the async `DbSession` for Settings CRUD. See [app/auth.py:73](../../app/auth.py#L73).
- **bcrypt** library — hashing. See [app/services/auth_users.py:20](../../app/services/auth_users.py#L20).
- **python-jose** — JWT. See [app/auth.py:25](../../app/auth.py#L25).
- No external identity provider, OAuth, LDAP, or SSO integration. `IMPLEMENTATION NOT FOUND`.

## Background Jobs

- **Boot-time seed** — `seed_from_env_if_empty` runs in the FastAPI lifespan, idempotently inserting `auth_users` from `AUTH_USERS` only when the table is empty; per-row try/except so one bad row doesn't abort; `ON CONFLICT ((lower(email))) DO NOTHING` for the multi-instance race; seeded role is `admin` only for `johndean@vin.com`. See [app/main.py:73](../../app/main.py#L73) and [app/services/auth_users.py:176](../../app/services/auth_users.py#L176).
- **Operator rescue** — `POST /v1/diag/reseed-auth-users` re-runs the seed against the live DB (admin-gated, inline email check). See [app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534).
- No scheduled/Celery-Beat auth job (e.g. token cleanup) exists. `IMPLEMENTATION NOT FOUND`.

## Error Handling

- **Login 401:** `Incorrect email or password` (`HTTPException`). See [app/api/auth.py:22](../../app/api/auth.py#L22).
- **Protected-route 401:** `Could not validate credentials`, `WWW-Authenticate: Bearer`. See [app/auth.py:164](../../app/auth.py#L164).
- **Admin 403:** `{"code":"ADMIN_ONLY","message":...}`. See [app/security/roles.py:113](../../app/security/roles.py#L113).
- **Envelope mapping:** the `EnvelopeMiddleware` maps `HTTPException` `{detail}` bodies into `{success,data,error,meta}`; the locked code→status map includes `UNAUTHORIZED`(401), `FORBIDDEN`(403), `ADMIN_ONLY`(403). A `{detail:{code,message}}` body is preserved into the error envelope. See [app/middleware/envelope.py:41](../../app/middleware/envelope.py#L41) and [:261](../../app/middleware/envelope.py#L261).
- **DB failures at auth** are logged and fall through to env CSV (fail-open for known env users); they do not 500. See [app/auth.py:129](../../app/auth.py#L129) and [app/auth.py:197](../../app/auth.py#L197).
- **Client 401 handling:** clears token, redirects to `/#/login` unless already there. See [frontend/src/services/http.ts:71](../../frontend/src/services/http.ts#L71).

## Performance Considerations

- **bcrypt verify is ~50ms by design and only runs on `POST /v1/auth/login`.** See [app/auth.py:113](../../app/auth.py#L113).
- **Per-request check is a single indexed `SELECT 1 ... WHERE lower(email)=... AND is_active`, ~1ms warm.** Uses the lower(email) unique index + active partial index. See [app/services/auth_users.py:136](../../app/services/auth_users.py#L136).
- **Connection reuse:** module-scoped sync engine, `pool_pre_ping=True`, `pool_size=5`, `max_overflow=2` survives Postgres restarts. See [app/auth.py:77](../../app/auth.py#L77).
- **`touch_last_login`** is best-effort and wrapped in try/except; a failure logs a warning and does not slow or fail login. See [app/services/auth_users.py:154](../../app/services/auth_users.py#L154).
- **JWT validation is local crypto** — no network/DB call for decode; the only DB touch per protected request is the active-check. See [app/auth.py:183](../../app/auth.py#L183).
- The idempotency/rate-limit middleware (Redis) does not run on the auth routes (`/v1/auth/*` is not in `_PROTECTED_PATHS`, and rate-limit is an explicit dependency only on upload routes). See [app/middleware/idempotency.py:32](../../app/middleware/idempotency.py#L32) and [app/middleware/rate_limit.py:33](../../app/middleware/rate_limit.py#L33).

## Source Verification
- **Files Used:** app/api/auth.py, app/auth.py, app/security/roles.py, app/services/auth_users.py, app/api/settings.py, app/api/diagnostics.py, app/middleware/idempotency.py, app/middleware/rate_limit.py, app/middleware/request_id.py, app/middleware/envelope.py, app/config.py, app/main.py, migrations/045_auth_users.sql, frontend/src/views/LoginView.vue, frontend/src/stores/auth.ts, frontend/src/router/index.ts, frontend/src/services/http.ts, frontend/src/services/api.ts
- **Components Used:** LoginView.vue, auth Pinia store, vue-router beforeEach guard, http.ts fetch wrapper
- **APIs Used:** POST /v1/auth/login, GET /v1/auth/me, /v1/settings/auth-users (GET/POST/PUT/DELETE + reset-password), POST /v1/diag/reseed-auth-users
- **Database Tables Used:** auth_users; audit_events (write-only)
- **Permission Logic Used:** JWT (get_current_user) + LEGACY_ADMIN_EMAIL gate via require_admin/is_admin (role kwarg unused) + client adminOnly guard
- **Confidence Score:** High — every claim traced to code; the roles.py wiring discrepancy vs. prior notes is documented in Permissions and flagged.
- **Evidence Links:** [app/auth.py:172](../../app/auth.py#L172), [app/auth.py:100](../../app/auth.py#L100), [app/security/roles.py:88](../../app/security/roles.py#L88), [app/services/auth_users.py:176](../../app/services/auth_users.py#L176), [app/main.py:73](../../app/main.py#L73), [migrations/045_auth_users.sql:11](../../migrations/045_auth_users.sql#L11), [frontend/src/services/http.ts:71](../../frontend/src/services/http.ts#L71)
