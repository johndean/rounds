# API Reference — `auth`

Router source: [app/api/auth.py](../../app/api/auth.py)

Mounted in [app/main.py:212](../../app/main.py#L212) via `app.include_router(auth_router.router)`.

Router prefix: `/v1/auth` (declared at [app/api/auth.py:12](../../app/api/auth.py#L12)). Tag: `auth`.

This router has **2 endpoints**: one public login that issues a JWT, and one authenticated identity probe. Both are defined entirely in `auth.py`; the token machinery (`authenticate`, `create_access_token`, `TokenResponse`, `CurrentUser`/`get_current_user`) lives in [app/auth.py](../../app/auth.py).

## Authentication & authorization model (verified)

- **Authentication** = a valid HS256 JWT bearer token. `get_current_user` ([app/auth.py:172](../../app/auth.py#L172)) decodes the token with `API_SECRET_KEY`, reads the `sub` claim, then confirms the user is still active via the `auth_users` table with an env-CSV fallback. The bearer scheme is `OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=False)` ([app/auth.py:161](../../app/auth.py#L161)); a missing/invalid token raises `401 Could not validate credentials`.
- **Authorization** for both endpoints in this router is JWT-presence only. There is no `require_admin` / `LEGACY_ADMIN_EMAIL` gate anywhere in `auth.py`.
- Role-based authorization is **scaffold-only** repo-wide: `auth_users.role` exists (migration 045) but `get_current_user` never reads it, and `app/security/roles.py` is not wired into these endpoints (see the docstring at [app/security/roles.py:10-19](../../app/security/roles.py#L10)).
- Token shape: payload is `{"sub": <email lowercased>, "exp": <utc expiry>}`, signed HS256 with `API_SECRET_KEY`. Lifetime = `ACCESS_TOKEN_EXPIRE_MINUTES` (default 480 minutes / 8 hours per the module docstring) ([app/auth.py:153-158](../../app/auth.py#L153)).

> **Response envelope:** every JSON response is wrapped by `EnvelopeMiddleware` ([app/middleware/envelope.py:196](../../app/middleware/envelope.py#L196)) into `{success, data, error, meta}`. The schemas below describe the **`data`** payload. On success, the documented body is nested under `data`; on error it appears under `error` (`{code, message, details, retryable}`). The `/docs`, `/redoc`, `/openapi*` paths are exempt ([app/middleware/envelope.py:179-193](../../app/middleware/envelope.py#L179)).

---

## POST `/v1/auth/login`

- **Decorator:** [app/api/auth.py:15](../../app/api/auth.py#L15) — `@router.post("/login", response_model=TokenResponse)`
- **Method:** POST
- **Purpose:** Username/password login. `form.username` is treated as the email address; returns a bearer access token on success ([app/api/auth.py:16-28](../../app/api/auth.py#L16)).
- **Authentication:** None — this is the token-minting entry point. No `CurrentUser` dependency.
- **Authorization:** None (public). It is the only route in this router with no auth dependency.
- **Request Schema:** `application/x-www-form-urlencoded` via FastAPI's `OAuth2PasswordRequestForm` ([app/api/auth.py:16](../../app/api/auth.py#L16)):
  - `username` (string, required) — the user's email.
  - `password` (string, required).
  - (`grant_type`, `scope`, `client_id`, `client_secret` are accepted by the OAuth2 form but unused here.)
- **Response Schema:** `TokenResponse` ([app/auth.py:147-150](../../app/auth.py#L147)):

  | Field | Type | Notes |
  |---|---|---|
  | `access_token` | string | HS256 JWT |
  | `token_type` | string | constant `"bearer"` |
  | `expires_in` | int | token lifetime in **seconds** |

- **Validation Rules:**
  - Credentials verified by `authenticate(email, password)` ([app/auth.py:100-143](../../app/auth.py#L100)). Precedence: (1) `auth_users` row found + bcrypt verify succeeds → success; (2) row found + bcrypt fails → fail without fallthrough; (3) row missing OR DB error → try the `AUTH_USERS` env-CSV fallback (constant-time compare); (4) otherwise fail.
  - An inactive `auth_users` row (`is_active = false`) fails login ([app/auth.py:123-124](../../app/auth.py#L123)).
  - Email is lowercased into the token `sub` ([app/auth.py:156](../../app/auth.py#L156)).
- **Errors:**
  - `401 UNAUTHORIZED` — `detail="Incorrect email or password"`, header `WWW-Authenticate: Bearer`, when `authenticate` returns `None` ([app/api/auth.py:22-27](../../app/api/auth.py#L22)).
- **Example:**
  ```bash
  curl -s -X POST https://rounds.vin/v1/auth/login \
    -d "username=johndean@vin.com&password=<PW>"
  # data: {"access_token":"<jwt>","token_type":"bearer","expires_in":28800}
  ```
- **Related Screens:** Login view — `frontend/src/services/api.ts:29` calls `http('/v1/auth/login', …)`.
- **Related Tables:** `auth_users` (primary credential store; bcrypt hashes). `AUTH_USERS` env CSV is a non-table fallback source.

---

## GET `/v1/auth/me`

- **Decorator:** [app/api/auth.py:31](../../app/api/auth.py#L31) — `@router.get("/me")`
- **Method:** GET
- **Purpose:** Returns the currently-authenticated principal ([app/api/auth.py:32-34](../../app/api/auth.py#L32)).
- **Authentication:** Required — `user: CurrentUser` dependency ([app/api/auth.py:32](../../app/api/auth.py#L32)) resolves through `get_current_user`. A missing/invalid token yields `401`.
- **Authorization:** JWT-only. No admin gate.
- **Request Schema:** None (no path params, query params, or body).
- **Response Schema:** `dict[str, str]` — `{"email": "<user email>"}` ([app/api/auth.py:34](../../app/api/auth.py#L34)). No declared `response_model`.
- **Validation Rules:** None beyond the JWT decode/active-user check in `get_current_user`.
- **Errors:**
  - `401 UNAUTHORIZED` — `detail="Could not validate credentials"` when the token is absent, malformed, expired, or the `sub` user is no longer present/active in `auth_users` and not in the env fallback ([app/auth.py:164-205](../../app/auth.py#L164)).
- **Example:**
  ```bash
  curl -s -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/auth/me
  # data: {"email":"johndean@vin.com"}
  ```
- **Related Screens:** Used by `api.auth.me()` ([frontend/src/services/api.ts:33](../../frontend/src/services/api.ts#L33)) — typically the auth-store bootstrap / session-restore path.
- **Related Tables:** `auth_users` (active-user check inside `get_current_user`); env-CSV fallback otherwise.

---

## Source Verification
- **Files Used:** app/api/auth.py, app/auth.py, app/security/roles.py, app/middleware/envelope.py, app/main.py, frontend/src/services/api.ts
- **Components Used:** none (login + auth-store bootstrap consume these; no component file inspected directly)
- **APIs Used:** POST /v1/auth/login, GET /v1/auth/me
- **Database Tables Used:** auth_users (plus AUTH_USERS env-CSV fallback — not a table)
- **Permission Logic Used:** JWT presence only (no LEGACY_ADMIN_EMAIL / require_admin gate in this router); `/login` is public
- **Confidence Score:** High — both endpoints and the full token/auth path were read in source; no inferred behavior.
- **Evidence Links:** [app/api/auth.py:15](../../app/api/auth.py#L15), [app/api/auth.py:31](../../app/api/auth.py#L31), [app/auth.py:100](../../app/auth.py#L100), [app/auth.py:172](../../app/auth.py#L172), [app/main.py:212](../../app/main.py#L212)
