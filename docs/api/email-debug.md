# API Reference — Email Debug (`/v1/admin/email-debug`)

Admin-only SMTP diagnostics router. Source: [app/api/email_debug.py](../../app/api/email_debug.py). Registered in [app/main.py:228](../../app/main.py#L228) via `app.include_router(email_debug_router.router)`.

Router declaration: `APIRouter(prefix="/v1/admin/email-debug", tags=["email-debug"])` — [app/api/email_debug.py:44](../../app/api/email_debug.py#L44).

## Authentication & Authorization (router-wide)

- **Authentication:** Every endpoint depends on `CurrentUser` (the `_user: CurrentUser` parameter), which is `Annotated[User, Depends(get_current_user)]` ([app/auth.py:208](../../app/auth.py#L208)). A valid HS256 JWT bearer token (issued by `/v1/auth/login`) is required; `get_current_user` decodes the token and confirms the subject email is still active in `auth_users` (with an env-CSV fallback). No token → HTTP 401 "Could not validate credentials" ([app/auth.py:172](../../app/auth.py#L172)).
- **Authorization:** Every endpoint additionally calls `_require_email_debug_admin(_user)` ([app/api/email_debug.py:50](../../app/api/email_debug.py#L50)), a thin wrapper that delegates to `require_admin(user, message="Only admin can access email diagnostics")` ([app/security/roles.py:95](../../app/security/roles.py#L95)). `require_admin` raises HTTP 403 `{"code": "ADMIN_ONLY", "message": ...}` unless `is_admin` is true. With no `role` argument passed, `is_admin` falls back to a **case-sensitive exact match** of `user.email` against `LEGACY_ADMIN_EMAIL = "johndean@vin.com"` ([app/security/roles.py:54](../../app/security/roles.py#L54), [app/security/roles.py:88](../../app/security/roles.py#L88)). The `auth_users.role` column is **not** consulted here — `get_current_user` never loads a role, so authorization today reduces to "the JWT subject equals `johndean@vin.com`".

> Note: This router is the one place where the `require_admin` helper from `app/security/roles.py` is actually wired into endpoints (via `_require_email_debug_admin`). It is invoked inside each handler body, not as a FastAPI dependency.

## Shared request model — `SendRequest`

Used only by `POST /send`. Defined at [app/api/email_debug.py:56](../../app/api/email_debug.py#L56).

| Field | Type | Required | Default | Constraints |
|---|---|---|---|---|
| `to` | `str` | yes | — | `min_length=3`, `max_length=255` |
| `subject` | `str` | no | `"Rounds Test Email"` | `max_length=200` |
| `text_body` | `str` | no | `"This is a test."` | `max_length=8000` |
| `html_body` | `str \| null` | no | `null` | `max_length=32000` |

---

## `GET /v1/admin/email-debug/config`

- **Endpoint:** `GET /v1/admin/email-debug/config`
- **Method:** GET
- **Decorator:** `@router.get("/config")` — [app/api/email_debug.py:64](../../app/api/email_debug.py#L64)
- **Purpose:** Presence-only check on the `SMTP_*` environment variables. Returns the literal `HOST`/`PORT`/`FROM` values (non-secret) but only a boolean presence flag for `USERNAME`/`PASSWORD` (their values are never leaked — always returned as `null`).
- **Authentication:** JWT via `CurrentUser` (`_user`).
- **Authorization:** `_require_email_debug_admin` → `require_admin` → JWT subject must equal `LEGACY_ADMIN_EMAIL`.
- **Request Schema:** None (no path params, query params, or body).
- **Response Schema:** Plain `dict` (no `response_model`). Each value is `{"present": bool, "value": str | null}`:
  ```json
  {
    "host":         {"present": true,  "value": "smtp.example.com"},
    "port":         {"present": true,  "value": "587"},
    "from_address": {"present": true,  "value": "mic@design.veterinary.support"},
    "username":     {"present": true,  "value": null},
    "password":     {"present": true,  "value": null}
  }
  ```
  Values are read from `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_USERNAME`, `SMTP_PASSWORD` ([app/api/email_debug.py:69-78](../../app/api/email_debug.py#L69)). `value` is `null` whenever the env var is empty/unset.
- **Validation Rules:** None beyond the auth gate.
- **Errors:** `401` (no/invalid token), `403` (`ADMIN_ONLY`).
- **Example:**
  ```bash
  curl -s -H "Authorization: Bearer $TOKEN" \
    https://rounds.vin/v1/admin/email-debug/config
  ```
- **Related Screens:** Settings → Email Debug / Diagnostics surface. NOT VERIFIED IN CODE which Vue view consumes this (no frontend reference confirmed in this assignment's scope).
- **Related Tables:** none (reads environment only).

---

## `POST /v1/admin/email-debug/connectivity`

- **Endpoint:** `POST /v1/admin/email-debug/connectivity`
- **Method:** POST
- **Decorator:** `@router.post("/connectivity")` — [app/api/email_debug.py:82](../../app/api/email_debug.py#L82)
- **Purpose:** SMTP smoke test that runs Connect → STARTTLS → LOGIN → NOOP → QUIT against the configured server. **No email is sent.** Returns per-step `{ok, latency_ms, error}`. A step's `ok=null` means it was skipped because a prior step failed (or, for `login`, because no credentials are configured).
- **Authentication:** JWT via `CurrentUser` (`_user`).
- **Authorization:** `_require_email_debug_admin` → JWT subject must equal `LEGACY_ADMIN_EMAIL`.
- **Request Schema:** None (no body or params).
- **Response Schema:** Plain `dict` (no `response_model`) with fixed keys `connect`, `starttls`, `login`, `noop`, `quit`, each shaped `{"ok": bool|null, "latency_ms": int|null, "error": str|null}` ([app/api/email_debug.py:96-102](../../app/api/email_debug.py#L96)).
  ```json
  {
    "connect":  {"ok": true,  "latency_ms": 42,  "error": null},
    "starttls": {"ok": true,  "latency_ms": 88,  "error": null},
    "login":    {"ok": true,  "latency_ms": 130, "error": null},
    "noop":     {"ok": true,  "latency_ms": 5,   "error": null},
    "quit":     {"ok": true,  "latency_ms": 4,   "error": null}
  }
  ```
  Behavior: connection uses `smtplib.SMTP(host, port, timeout=10)` with `port` from `SMTP_PORT` (default `587`) ([app/api/email_debug.py:92](../../app/api/email_debug.py#L92)). If `connect` or `starttls` fail, the function returns early ([app/api/email_debug.py:111](../../app/api/email_debug.py#L111), [app/api/email_debug.py:121](../../app/api/email_debug.py#L121)). If `SMTP_USERNAME`/`SMTP_PASSWORD` are unset, `login` returns `{"ok": null, ..., "error": "skipped — no SMTP_USERNAME/PASSWORD set"}` ([app/api/email_debug.py:134](../../app/api/email_debug.py#L134)). On any caught exception the step's `error` is `"{ExceptionClassName}: {message}"`.
- **Validation Rules:** Requires `SMTP_HOST` to be set, else `400`.
- **Errors:**
  - `400` — `"SMTP_HOST not configured"` when `SMTP_HOST` is empty/unset ([app/api/email_debug.py:91](../../app/api/email_debug.py#L91)).
  - `401` — no/invalid token.
  - `403` — `ADMIN_ONLY`.
  - Per-step transport failures are NOT raised as HTTP errors — they are reported in the `200` body's `error` field.
- **Example:**
  ```bash
  curl -s -X POST -H "Authorization: Bearer $TOKEN" \
    https://rounds.vin/v1/admin/email-debug/connectivity
  ```
- **Related Screens:** Settings → Email Debug / Diagnostics. NOT VERIFIED IN CODE.
- **Related Tables:** none.

---

## `POST /v1/admin/email-debug/send`

- **Endpoint:** `POST /v1/admin/email-debug/send`
- **Method:** POST
- **Decorator:** `@router.post("/send")` — [app/api/email_debug.py:234](../../app/api/email_debug.py#L234)
- **Purpose:** Admin-only test send to an arbitrary address. Sends a real multipart (plain + HTML) email via `smtplib` with `debuglevel=1` and captures the **full raw SMTP wire exchange** into a string, then records the attempt (success or failure) in `email_attempts` with the wire log in `smtp_log`. No rate limit (admin needs to iterate templates).
- **Authentication:** JWT via `CurrentUser` (`_user`).
- **Authorization:** `_require_email_debug_admin` → JWT subject must equal `LEGACY_ADMIN_EMAIL`. The operator email recorded on the attempt is `_user.email` lowercased ([app/api/email_debug.py:240](../../app/api/email_debug.py#L240)).
- **Request Schema:** `SendRequest` body (see shared model above). `db: DbSession` and `_user: CurrentUser` are injected.
- **Response Schema:** Plain `dict` (no `response_model`):
  ```json
  {
    "sent":       true,
    "to":         "person@example.com",
    "subject":    "Rounds Test Email",
    "latency_ms": 742,
    "error":      null,
    "smtp_log":   "send: 'ehlo ...\\r\\n'\nreply: b'250 ...'\n..."
  }
  ```
  On failure, `sent` is `false` and `error` carries `"{ExceptionClassName}: {message}"` ([app/api/email_debug.py:279-286](../../app/api/email_debug.py#L279)). `smtp_log` is the captured wire chatter (may be partial on failure).
  Defaults applied server-side: `subject` falls back to `"Rounds Test Email"`, `text_body` to `"This is a test."`, and when `html_body` is omitted the body becomes `<pre style='font-family:monospace;font-size:13px'>{text_body}</pre>` ([app/api/email_debug.py:246-250](../../app/api/email_debug.py#L246)). `from_address` is `SMTP_FROM` (default `"rounds-noreply@vin.com"`), `port` is `SMTP_PORT` (default `587`) ([app/api/email_debug.py:256-257](../../app/api/email_debug.py#L256)).
- **Validation Rules:**
  - Pydantic: `to` length 3–255; `subject` ≤200; `text_body` ≤8000; `html_body` ≤32000.
  - The trimmed `to` value must match the email regex `^[^@\s]+@[^@\s]+\.[^@\s]+$` (`_EMAIL_RE`, [app/api/email_debug.py:47](../../app/api/email_debug.py#L47)) — else `400`.
  - `SMTP_HOST` must be configured — else `400`.
- **Errors:**
  - `422` — Pydantic validation (e.g. `to` shorter than 3 chars or fields over max length).
  - `400` — `"Invalid 'to' email address"` ([app/api/email_debug.py:244](../../app/api/email_debug.py#L244)).
  - `400` — `"SMTP_HOST not configured"` ([app/api/email_debug.py:254](../../app/api/email_debug.py#L254)).
  - `401` — no/invalid token.
  - `403` — `ADMIN_ONLY`.
  - SMTP transport failures do NOT raise — they return `200` with `sent: false` and the error in the body; a `failed` row is still written to `email_attempts`.
- **Side effects:** Inserts one row into `email_attempts` with `trigger='debug_test'` and `result` of `'sent'` or `'failed'` via `_record_attempt` ([app/api/email_debug.py:191](../../app/api/email_debug.py#L191)). That insert is best-effort and never raises (logs a warning on failure).
- **Example:**
  ```bash
  curl -s -X POST -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"to":"me@example.com","subject":"Hi","text_body":"hello"}' \
    https://rounds.vin/v1/admin/email-debug/send
  ```
- **Related Screens:** Settings → Email Debug "Send test" panel. NOT VERIFIED IN CODE.
- **Related Tables:** `email_attempts` (INSERT) — [migrations/030_email_attempts.sql](../../migrations/030_email_attempts.sql).

---

## `GET /v1/admin/email-debug/attempts`

- **Endpoint:** `GET /v1/admin/email-debug/attempts`
- **Method:** GET
- **Decorator:** `@router.get("/attempts")` — [app/api/email_debug.py:307](../../app/api/email_debug.py#L307)
- **Purpose:** Paginated audit trail of send attempts for the "Recent Attempts" panel. Newest first.
- **Authentication:** JWT via `CurrentUser` (`_user`).
- **Authorization:** `_require_email_debug_admin` → JWT subject must equal `LEGACY_ADMIN_EMAIL`.
- **Request Schema:** Query parameters only:

  | Param | Type | Default | Constraints | Effect |
  |---|---|---|---|---|
  | `limit` | int | `50` | `ge=1, le=500` | `LIMIT` on the result set |
  | `to` | str \| null | `null` | — | `to_address ILIKE %{to}%` filter |
  | `result` | str \| null | `null` | `pattern="^(sent\|failed)$"` | exact `result =` filter |
  | `since_hours` | int \| null | `null` | `ge=1, le=720` | `attempted_at >= now() - interval` filter |

- **Response Schema:** `list[dict]` (no `response_model`). Each item ([app/api/email_debug.py:339-356](../../app/api/email_debug.py#L339)):
  ```json
  [
    {
      "id":             "uuid",
      "attempted_at":   "2026-06-08T12:00:00+00:00",
      "from_address":   "rounds-noreply@vin.com",
      "to_address":     "me@example.com",
      "subject":        "Rounds Test Email",
      "trigger":        "debug_test",
      "sop_session_id": null,
      "stage":          null,
      "result":         "sent",
      "error_code":     null,
      "error_message":  null,
      "latency_ms":     742,
      "smtp_log":       "send: 'ehlo ...'",
      "operator_email": "johndean@vin.com"
    }
  ]
  ```
  Columns are selected directly from `email_attempts` ([app/api/email_debug.py:330-332](../../app/api/email_debug.py#L330)); `id`/`sop_session_id` are stringified and `attempted_at` is ISO-formatted.
- **Validation Rules:** Enforced by the `Query(...)` constraints above; `result` must be exactly `sent` or `failed`.
- **Errors:**
  - `422` — query param out of range (e.g. `limit=0`, `since_hours>720`, `result` not matching the pattern).
  - `401` — no/invalid token.
  - `403` — `ADMIN_ONLY`.
- **Example:**
  ```bash
  curl -s -H "Authorization: Bearer $TOKEN" \
    "https://rounds.vin/v1/admin/email-debug/attempts?limit=20&result=failed&since_hours=24"
  ```
- **Related Screens:** Settings → Email Debug "Recent Attempts" panel. NOT VERIFIED IN CODE.
- **Related Tables:** `email_attempts` (SELECT) — [migrations/030_email_attempts.sql](../../migrations/030_email_attempts.sql).

---

## Notes

- The router exposes exactly **4** endpoints (every `@router` decorator enumerated above): `GET /config`, `POST /connectivity`, `POST /send`, `GET /attempts`.
- The `email_attempts` table CHECK constraints allow `trigger IN ('stage_notification','debug_test','template_test')` and `result IN ('sent','failed')` ([migrations/030_email_attempts.sql:31-32](../../migrations/030_email_attempts.sql#L31)). This router only ever writes `trigger='debug_test'`; the `stage_notification`/`template_test` triggers are written elsewhere (not in this router). The module docstring states `EmailBuilder` + per-type templates ship in a follow-up — PARTIALLY IMPLEMENTED relative to that wider email subsystem; only the four debug endpoints exist here.

## Source Verification
- **Files Used:** app/api/email_debug.py, app/auth.py, app/security/roles.py, app/main.py, migrations/030_email_attempts.sql
- **Components Used:** none (frontend consumers NOT VERIFIED IN CODE)
- **APIs Used:** GET /v1/admin/email-debug/config, POST /v1/admin/email-debug/connectivity, POST /v1/admin/email-debug/send, GET /v1/admin/email-debug/attempts
- **Database Tables Used:** email_attempts (INSERT in /send via `_record_attempt`; SELECT in /attempts)
- **Permission Logic Used:** JWT (`get_current_user`) + `require_admin` gate resolving to `LEGACY_ADMIN_EMAIL` exact-email match (no role column read). Wired via `_require_email_debug_admin`.
- **Confidence Score:** High — all four endpoints, the `SendRequest` model, the auth/admin chain, and the table schema were read directly from source.
- **Evidence Links:** [app/api/email_debug.py:44](../../app/api/email_debug.py#L44), [app/api/email_debug.py:50](../../app/api/email_debug.py#L50), [app/api/email_debug.py:64](../../app/api/email_debug.py#L64), [app/api/email_debug.py:82](../../app/api/email_debug.py#L82), [app/api/email_debug.py:234](../../app/api/email_debug.py#L234), [app/api/email_debug.py:307](../../app/api/email_debug.py#L307), [app/security/roles.py:54](../../app/security/roles.py#L54), [app/security/roles.py:95](../../app/security/roles.py#L95), [app/auth.py:172](../../app/auth.py#L172), [app/main.py:228](../../app/main.py#L228)
