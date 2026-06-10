# Session Locks API — `/v1/sessions/{id}/lock/*`

Concurrent-edit lock for the session editor. One lock row per session keeps two operators from silently overwriting each other's autosaves. The lock is **advisory at the DB layer** (it never blocks `INSERT`/`UPDATE`) but the frontend gates the editor's read/write mode on it. TTL is **90 seconds** = 3 missed 30-second heartbeats.

Router declaration: [app/api/locks.py:40](../../app/api/locks.py#L40) — `APIRouter(prefix="/v1/sessions", tags=["session-locks"])`. TTL constant `LOCK_TTL_SECONDS = 90` at [app/api/locks.py:44](../../app/api/locks.py#L44).

The router defines **five** endpoints: acquire, heartbeat, release, holder, force-take.

---

## Shared response shape — `LockState`

Returned by acquire, heartbeat, holder, and force-take. Defined at [app/api/locks.py:57](../../app/api/locks.py#L57):

| Field | Type | Notes |
|---|---|---|
| `acquired` | `bool` | Did the caller end up holding the lock? |
| `is_self` | `bool` | Is the current holder the calling user? |
| `holder` | `LockHolder \| null` | `null` when there is no lock row. |

`LockHolder` ([app/api/locks.py:50](../../app/api/locks.py#L50)) — all ISO-8601 strings:

| Field | Type |
|---|---|
| `user_email` | `str` |
| `acquired_at` | `str` |
| `heartbeat_at` | `str` |
| `expires_at` | `str` |

A lock row is considered **stale** when `expires_at < now()` — `_is_stale` at [app/api/locks.py:89](../../app/api/locks.py#L89).

**Authentication (all five endpoints):** JWT bearer token via the `CurrentUser` dependency (`get_current_user`, [app/auth.py:172](../../app/auth.py#L172)). Missing/invalid token → `401`. The `session_id` path parameter is typed `UUID`, so a non-UUID value yields a FastAPI `422` before the handler runs.

---

## `POST /v1/sessions/{session_id}/lock/acquire`

- **Decorator:** [app/api/locks.py:99](../../app/api/locks.py#L99) — `@router.post("/{session_id}/lock/acquire", response_model=LockState)`
- **Handler:** `acquire` ([app/api/locks.py:100](../../app/api/locks.py#L100))
- **Purpose:** Acquire or refresh the lock for this session, stealing it if the existing holder's lock is stale.
- **Authorization:** JWT only — no admin gate.
- **Request Schema:** path `session_id: UUID`; no body.
- **Response Schema:** `200` `LockState`.

### Behavior ([app/api/locks.py:112](../../app/api/locks.py#L112))

- If no row exists, OR the existing holder's email equals the caller, OR the row is stale → upsert to the caller via `INSERT ... ON CONFLICT (session_id) DO UPDATE` ([app/api/locks.py:115](../../app/api/locks.py#L115)) with `expires_at = now() + 90s`. Returns `{acquired: true, is_self: true, holder: <caller>}`. The upsert preserves the original `acquired_at` when the caller already held the lock; otherwise it resets it (CASE at [app/api/locks.py:121](../../app/api/locks.py#L121)).
- If the row is held by **someone else** and is **fresh** → returns `{acquired: false, is_self: false, holder: <other user>}` ([app/api/locks.py:135](../../app/api/locks.py#L135)). No steal.

### Errors

| Status | Cause |
|---|---|
| `401` | Missing/invalid JWT. |
| `422` | `session_id` is not a valid UUID. |

### Example

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  https://rounds.vin/v1/sessions/3f2c.../lock/acquire
```

---

## `POST /v1/sessions/{session_id}/lock/heartbeat`

- **Decorator:** [app/api/locks.py:142](../../app/api/locks.py#L142) — `@router.post("/{session_id}/lock/heartbeat", response_model=LockState)`
- **Handler:** `heartbeat` ([app/api/locks.py:143](../../app/api/locks.py#L143))
- **Purpose:** Extend the caller's lock by another TTL window.
- **Authorization:** JWT only — no admin gate.
- **Request Schema:** path `session_id: UUID`; no body.
- **Response Schema:** `200` `LockState`.

### Behavior ([app/api/locks.py:155](../../app/api/locks.py#L155))

- No row exists → `{acquired: false, is_self: false, holder: null}` (idempotent; caller can re-acquire) ([app/api/locks.py:157](../../app/api/locks.py#L157)).
- Row held by someone else → `{acquired: false, is_self: false, holder: <other user>}` ([app/api/locks.py:162](../../app/api/locks.py#L162)). The frontend uses this to drop to read-only.
- Caller is the holder → `UPDATE ... SET heartbeat_at = now(), expires_at = now() + 90s` and returns `{acquired: true, is_self: true, holder: <caller>}` ([app/api/locks.py:169](../../app/api/locks.py#L169)).

> Despite the docstring at [app/api/locks.py:144](../../app/api/locks.py#L144) mentioning a `409`, the handler **never raises** — contention is surfaced via `acquired=false`, not an HTTP error. PARTIALLY IMPLEMENTED: the "409 only when actively stolen" behavior described in the docstring is not present in the code.

### Errors

| Status | Cause |
|---|---|
| `401` | Missing/invalid JWT. |
| `422` | `session_id` is not a valid UUID. |

---

## `POST /v1/sessions/{session_id}/lock/release`

- **Decorator:** [app/api/locks.py:188](../../app/api/locks.py#L188) — `@router.post("/{session_id}/lock/release", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)`
- **Handler:** `release` ([app/api/locks.py:189](../../app/api/locks.py#L189))
- **Purpose:** Release the lock if the caller holds it. No-op if the caller is not the holder.
- **Authorization:** JWT only — no admin gate.
- **Request Schema:** path `session_id: UUID`; no body.
- **Response Schema:** `204 No Content`, empty body (`response_class=Response`, returns `Response(status_code=204)`).

### Behavior ([app/api/locks.py:191](../../app/api/locks.py#L191))

Single `DELETE FROM session_locks WHERE session_id = :s AND user_email = :u`. The `user_email` predicate means another user's lock is never deleted. Always returns `204` regardless of whether a row was deleted.

### Errors

| Status | Cause |
|---|---|
| `401` | Missing/invalid JWT. |
| `422` | `session_id` is not a valid UUID. |

---

## `GET /v1/sessions/{session_id}/lock/holder`

- **Decorator:** [app/api/locks.py:204](../../app/api/locks.py#L204) — `@router.get("/{session_id}/lock/holder", response_model=LockState)`
- **Handler:** `holder` ([app/api/locks.py:205](../../app/api/locks.py#L205))
- **Purpose:** Read the current lock holder. Used by the banner on read-only tabs.
- **Authorization:** JWT only — no admin gate.
- **Request Schema:** path `session_id: UUID`; no body.
- **Response Schema:** `200` `LockState`.

### Behavior ([app/api/locks.py:208](../../app/api/locks.py#L208))

- No row → `{acquired: false, is_self: false, holder: null}`.
- Row exists → `acquired = (holder == caller AND not stale)`; `is_self = (holder == caller)`; `holder` populated ([app/api/locks.py:211](../../app/api/locks.py#L211)). Note this is the only endpoint where `acquired` factors in staleness for the caller's own lock.

### Errors

| Status | Cause |
|---|---|
| `401` | Missing/invalid JWT. |
| `422` | `session_id` is not a valid UUID. |

---

## `POST /v1/sessions/{session_id}/lock/force-take`

- **Decorator:** [app/api/locks.py:218](../../app/api/locks.py#L218) — `@router.post("/{session_id}/lock/force-take", response_model=LockState)`
- **Handler:** `force_take` ([app/api/locks.py:219](../../app/api/locks.py#L219))
- **Purpose:** Force-take the lock regardless of staleness — for when an operator's tab crashed and the 90-second TTL is too long to wait. Writes an `audit_events` row.
- **Request Schema:** path `session_id: UUID`; no body.
- **Response Schema:** `200` `LockState` — `{acquired: true, is_self: true, holder: <caller>}`.

### Authorization — admin-gated (the only gated route in this router)

The handler calls `is_admin(user)` and raises `403 "admin required"` when it returns `False` ([app/api/locks.py:225](../../app/api/locks.py#L225)). `is_admin` is imported at [app/api/locks.py:38](../../app/api/locks.py#L38).

Because the call passes **no `role` argument**, `is_admin` falls through to its legacy-email branch: `user.email == LEGACY_ADMIN_EMAIL`, a case- and whitespace-sensitive exact match against the literal `"johndean@vin.com"` ([app/security/roles.py:62](../../app/security/roles.py#L62), [app/security/roles.py:54](../../app/security/roles.py#L54)). The `auth_users.role` column is **not** consulted here — `get_current_user` never loads it into the `User` object ([app/auth.py:172](../../app/auth.py#L172)), so in practice this endpoint is gated on the single hardcoded admin email, not on a role tier.

> This is the one place in these three routers where `is_admin` is actually wired into an endpoint. Its effective behavior today is the `LEGACY_ADMIN_EMAIL` gate.

### Behavior ([app/api/locks.py:228](../../app/api/locks.py#L228))

1. Read the prior holder (may be `null`).
2. Upsert the lock to the caller via `INSERT ... ON CONFLICT DO UPDATE` ([app/api/locks.py:232](../../app/api/locks.py#L232)) — unlike `acquire`, this unconditionally resets `acquired_at` to `now()`.
3. Insert an `audit_events` row with `kind = 'session.lock_force_take'`, a summary naming the prior holder, and `details = {"prior_holder": <email|null>}` ([app/api/locks.py:247](../../app/api/locks.py#L247)).
4. Commit and return the new `LockState`.

### Errors

| Status | Cause |
|---|---|
| `401` | Missing/invalid JWT. |
| `403` | Caller is not the admin email (`{"detail": "admin required"}`) — [app/api/locks.py:226](../../app/api/locks.py#L226). |
| `422` | `session_id` is not a valid UUID. |

### Example

```bash
# Must be authenticated as johndean@vin.com
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  https://rounds.vin/v1/sessions/3f2c.../lock/force-take
```

---

## Related Screens

- **EditorView** (`/e/:id`, [frontend/src/router/index.ts:34](../../frontend/src/router/index.ts#L34)) consumes all five lock endpoints through the `useSessionLock` composable.
- **`useSessionLock.ts`** ([frontend/src/composables/useSessionLock.ts:2](../../frontend/src/composables/useSessionLock.ts#L2)) calls `/lock/acquire` on mount, runs a 30s heartbeat (paused while `document.hidden`), `/lock/release` on unmount/`beforeunload`/visibility-hidden, and exposes `forceTake`. It **fails closed**: when the lock service is unreachable, `isHolder` becomes false and a `lockError` banner renders. A `403` from force-take is interpreted as "tried force-take without admin" ([frontend/src/composables/useSessionLock.ts:68](../../frontend/src/composables/useSessionLock.ts#L68)).

## Related Tables

- **`session_locks`** — `session_id` (UUID PK), `user_email`, `acquired_at`, `heartbeat_at`, `expires_at`. Defined in [migrations/057_session_locks.sql:14](../../migrations/057_session_locks.sql#L14); default `expires_at = now() + INTERVAL '90 seconds'`; index `idx_session_locks_expires_at`.
- **`audit_events`** — written by `force-take` only. Columns `session_id`, `actor_email`, `kind`, `summary`, `details (jsonb)` from [migrations/004_audit.sql:3](../../migrations/004_audit.sql#L3).

---

## Source Verification
- **Files Used:** app/api/locks.py, app/auth.py, app/security/roles.py, migrations/057_session_locks.sql, migrations/004_audit.sql, frontend/src/composables/useSessionLock.ts, frontend/src/router/index.ts
- **Components Used:** EditorView.vue, useSessionLock.ts composable
- **APIs Used:** `POST .../lock/acquire`, `POST .../lock/heartbeat`, `POST .../lock/release`, `GET .../lock/holder`, `POST .../lock/force-take`
- **Database Tables Used:** session_locks, audit_events (sessions referenced via the session_id path param only)
- **Permission Logic Used:** acquire/heartbeat/release/holder = JWT only. force-take = JWT + `is_admin(user)` with no role arg → effectively the LEGACY_ADMIN_EMAIL (`johndean@vin.com`) gate; `auth_users.role` is not read.
- **Confidence Score:** High — all five handlers read in full; the force-take admin gate traced through is_admin to the LEGACY_ADMIN_EMAIL literal; the docstring's "409" claim flagged as not implemented.
- **Evidence Links:** [app/api/locks.py:99](../../app/api/locks.py#L99) (acquire), [app/api/locks.py:218](../../app/api/locks.py#L218) (force-take decorator), [app/api/locks.py:225](../../app/api/locks.py#L225) (is_admin call), [app/security/roles.py:62](../../app/security/roles.py#L62) (is_admin), [migrations/057_session_locks.sql:14](../../migrations/057_session_locks.sql#L14)
