# Workflow: Session Soft-Delete / Restore / Permanent Purge

Three-stage session trash lifecycle: soft-delete (sets `deleted_at`, data preserved 30 days), restore (clears `deleted_at`), and permanent delete (hard-deletes the row + cascaded children, irreversible). All three are admin-gated.

Endpoints in [app/api/sessions.py](../../app/api/sessions.py): `DELETE /{session_id}` ([:621](../../app/api/sessions.py#L621)), `POST /{session_id}/restore` ([:668](../../app/api/sessions.py#L668)), `DELETE /{session_id}/permanent` ([:697](../../app/api/sessions.py#L697)), and the listing `GET /deleted` ([:266](../../app/api/sessions.py#L266)). The router prefix makes these `/v1/sessions/...`.

## Trigger

- **Soft-delete:** `DELETE /v1/sessions/{session_id}` ([app/api/sessions.py:621](../../app/api/sessions.py#L621)).
- **Restore:** `POST /v1/sessions/{session_id}/restore` ([app/api/sessions.py:668](../../app/api/sessions.py#L668)).
- **Permanent purge:** `DELETE /v1/sessions/{session_id}/permanent` ([app/api/sessions.py:697](../../app/api/sessions.py#L697)).
- **List trash:** `GET /v1/sessions/deleted` ([app/api/sessions.py:266](../../app/api/sessions.py#L266)) — must be declared before `GET /{session_id}` so the literal path wins.

## Inputs

- `session_id` (path, UUID) for the three mutation endpoints.
- `GET /deleted` takes no parameters; it returns sessions with `deleted_at IS NOT NULL AND deleted_at >= now() - interval '30 days'`, fields `session_id, code, title, presenter, status, created_at, deleted_at` ([app/api/sessions.py:282-302](../../app/api/sessions.py#L282)). Rows older than 30 days are hidden from this view but the DB row survives until purge so the audit ledger can still join ([app/api/sessions.py:270-273](../../app/api/sessions.py#L270)).

## Validations

- **Soft-delete:** 404 if the session does not exist; `ConflictError` ("Session is already deleted") if `deleted_at` is already set ([app/api/sessions.py:635-645](../../app/api/sessions.py#L635)).
- **Restore:** 404 if not found; `ConflictError` ("Session is not deleted") if `deleted_at IS NULL` ([app/api/sessions.py:677-687](../../app/api/sessions.py#L677)).
- **Permanent:** 404 if not found; `ConflictError` ("Session must be soft-deleted before permanent deletion") if `deleted_at IS NULL` — a session must be soft-deleted first ([app/api/sessions.py:710-720](../../app/api/sessions.py#L710)).

## Approvals

None in the workflow sense (no multi-party sign-off). Authorization is the admin gate only:

- **Soft-delete** is gated by the `SESSION_TRASH_ALLOWED` set: `{ADMIN_EMAIL, "carlab@vin.com"}`, where `ADMIN_EMAIL` is `LEGACY_ADMIN_EMAIL = "johndean@vin.com"` ([app/api/sessions.py:52](../../app/api/sessions.py#L52), [app/security/roles.py:54](../../app/security/roles.py#L54)). Caller email not in the set → 403 "Only admin can delete sessions" ([app/api/sessions.py:630-631](../../app/api/sessions.py#L630)).
- **Restore, Permanent, and List-deleted** call `require_admin(...)` ([app/api/sessions.py:276](../../app/api/sessions.py#L276), [:674](../../app/api/sessions.py#L674), [:707](../../app/api/sessions.py#L707)). With no `role` argument passed, `require_admin` resolves through the hardcoded `user.email == LEGACY_ADMIN_EMAIL` comparison ("johndean@vin.com") and raises 403 `{"code": "ADMIN_ONLY", ...}` otherwise ([app/security/roles.py:88-117](../../app/security/roles.py#L88)).

**Authorization reality:** `app/security/roles.py` is documented as Phase-8 scaffold that is *not* wired to read `auth_users.role` — `get_current_user` never loads the role, so the `role=` path is never exercised; every caller hits the legacy email comparison ([app/security/roles.py:10-19](../../app/security/roles.py#L10)). So restore/permanent/list-deleted are effectively single-admin (`johndean@vin.com`), and soft-delete additionally admits `carlab@vin.com` via `SESSION_TRASH_ALLOWED`.

## Notifications

None. No WS event, no email is emitted by any of the three handlers. (Soft-delete and permanent both call `release_slot` — a Redis rate-limit cleanup, not a notification; see Outputs.)

## Outputs

- **Soft-delete:** `{"session_id": ..., "deleted": True}` ([app/api/sessions.py:665](../../app/api/sessions.py#L665)). Sets `deleted_at = now(), updated_at = now()` ([app/api/sessions.py:647-650](../../app/api/sessions.py#L647)), then releases the Redis rate-limit slot via `release_slot` so the soft-deleted session stops counting against `MAX_CONCURRENT_SESSIONS` ([app/api/sessions.py:653-663](../../app/api/sessions.py#L653)).
- **Restore:** `{"session_id": ..., "restored": True}` ([app/api/sessions.py:694](../../app/api/sessions.py#L694)). Sets `deleted_at = NULL, updated_at = now()` ([app/api/sessions.py:689-692](../../app/api/sessions.py#L689)).
- **Permanent:** `{"session_id": ..., "permanently_deleted": True}` ([app/api/sessions.py:750](../../app/api/sessions.py#L750)). A single `DELETE FROM sessions WHERE id = :sid` reaps the whole dependency tree — the Rounds schema declares `ON DELETE CASCADE` on every child FK referencing `sessions(id)` (segments → words also cascade). `audit_events.session_id` is `ON DELETE SET NULL` (migration 004), so historical audit events survive purge for forensic queries ([app/api/sessions.py:722-733](../../app/api/sessions.py#L722)). Also calls `release_slot` as a safety net ([app/api/sessions.py:742-748](../../app/api/sessions.py#L742)).

## Status Changes

None of these touch the `sessions.status` enum (`uploading/ingesting/ready/failed/...`). Lifecycle is expressed via the `deleted_at` column only:

| Action | `deleted_at` | `updated_at` |
|---|---|---|
| Soft-delete | `NULL → now()` | `now()` |
| Restore | `now() → NULL` | `now()` |
| Permanent | row deleted | n/a |

## Audit Events

**None written by these handlers.** Soft-delete, restore, and permanent-delete do not insert `audit_events` or `session_audit` rows ([app/api/sessions.py:621-750](../../app/api/sessions.py#L621)). For permanent purge, the comment notes `audit_events.session_id` is preserved via `ON DELETE SET NULL` so pre-existing audit rows survive — but no new audit row is created for the delete itself ([app/api/sessions.py:726-727](../../app/api/sessions.py#L726)).

## Exception Handling

- **Soft-delete / permanent — `release_slot` failure:** wrapped in try/except, logged as a warning, non-fatal (the DB mutation already committed) ([app/api/sessions.py:657-663](../../app/api/sessions.py#L657), [:743-748](../../app/api/sessions.py#L743)).
- **Permanent — cascade failure:** the `DELETE` is wrapped in try/except; on error it rolls back, logs with traceback, and raises `HTTPException(500, "Cascade delete failed: <ExcClass>")` ([app/api/sessions.py:728-740](../../app/api/sessions.py#L728)).
- **Conflict states** raise `ConflictError` from `app.middleware.envelope` (already-deleted, not-deleted, not-yet-soft-deleted) ([app/api/sessions.py:644-645](../../app/api/sessions.py#L644), [:686-687](../../app/api/sessions.py#L686), [:719-720](../../app/api/sessions.py#L719)).
- **Missing session** raises `HTTPException(404, "Session not found")` in all three ([app/api/sessions.py:642](../../app/api/sessions.py#L642), [:684](../../app/api/sessions.py#L684), [:717](../../app/api/sessions.py#L717)).

## Source Verification
- **Files Used:** app/api/sessions.py, app/security/roles.py
- **Components Used:** none (backend-only; the client-side trash UI is not in scope of these files)
- **APIs Used:** DELETE /v1/sessions/{id}, POST /v1/sessions/{id}/restore, DELETE /v1/sessions/{id}/permanent, GET /v1/sessions/deleted
- **Database Tables Used:** sessions (deleted_at, updated_at); cascaded children on purge; audit_events (preserved via ON DELETE SET NULL, not written)
- **Permission Logic Used:** JWT + hardcoded LEGACY_ADMIN_EMAIL gate. Soft-delete via the SESSION_TRASH_ALLOWED set ({johndean@vin.com, carlab@vin.com}); restore/permanent/list-deleted via require_admin, which (with no role arg loaded) resolves to the email==LEGACY_ADMIN_EMAIL comparison.
- **Confidence Score:** High — every gate, validation, status field, and output traced to source; permission reality (scaffold not wired to auth_users.role) confirmed in app/security/roles.py.
- **Evidence Links:** [app/api/sessions.py:621](../../app/api/sessions.py#L621), [app/api/sessions.py:668](../../app/api/sessions.py#L668), [app/api/sessions.py:697](../../app/api/sessions.py#L697), [app/api/sessions.py:52](../../app/api/sessions.py#L52), [app/security/roles.py:88](../../app/security/roles.py#L88)
