# Exports API

Router source: [app/api/exports.py](../../app/api/exports.py)

Produces downloadable transcript artifacts (`docx` / `srt` / `vtt` / `txt` / `html` / `zip`) and a cache-friendly WebVTT caption file for the editor's HTML5 `<track>` element. The artifact bytes are streamed back; a row is recorded in the `artifacts` table on successful generation (idempotent via `ON CONFLICT (session_id, kind)`) ([exports.py:84-98](../../app/api/exports.py#L84)).

This file defines **two** `APIRouter`s:
- `router` — prefix `/v1/sessions/{session_id}/exports`, tag `exports` ([exports.py:27](../../app/api/exports.py#L27)).
- `captions_router` — prefix `/v1/sessions/{session_id}`, tag `exports` ([exports.py:28](../../app/api/exports.py#L28)).

Two `@router`/`@captions_router` decorators are defined:

| # | Method | Path | Handler | Decorator line |
|---|--------|------|---------|----------------|
| 1 | GET | `/v1/sessions/{session_id}/exports/{format}` | `export_session` | [exports.py:41](../../app/api/exports.py#L41) |
| 2 | GET | `/v1/sessions/{session_id}/captions.vtt` | `get_captions_vtt` | [exports.py:120](../../app/api/exports.py#L120) |

## Authentication & authorization (applies to both endpoints below)

- **Authentication:** Endpoint 1 depends on `user: CurrentUser`; endpoint 2 on `_user: CurrentUser` ([exports.py:24](../../app/api/exports.py#L24), [exports.py:46](../../app/api/exports.py#L46), [exports.py:125](../../app/api/exports.py#L125)). Both require a valid HS256 JWT bearer token via `get_current_user`; missing/invalid token → 401 ([app/auth.py:172](../../app/auth.py#L172)).
- **Authorization:** No `LEGACY_ADMIN_EMAIL` / `require_admin` / role check in this router (grep-confirmed: no matches). **Both routes are JWT-only.** Any authenticated user may call them. The artifact write records the caller's `user.email` in `generated_by` ([exports.py:96](../../app/api/exports.py#L96)).

## Supported formats

`_KIND_TO_MIME` ([exports.py:31-38](../../app/api/exports.py#L31)):

| `format` | MIME type |
|----------|-----------|
| `txt` | `text/plain; charset=utf-8` |
| `srt` | `application/x-subrip; charset=utf-8` |
| `vtt` | `text/vtt; charset=utf-8` |
| `docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| `html` | `text/html; charset=utf-8` |
| `zip` | `application/zip` |

---

## 1. GET `/v1/sessions/{session_id}/exports/{format}`

**Endpoint** [exports.py:41](../../app/api/exports.py#L41)
**Method:** GET
**Purpose:** Generate and stream the requested transcript artifact, attaching a `Content-Disposition: attachment` header so the browser downloads it. On success, upserts the artifact metadata row ([exports.py:48-108](../../app/api/exports.py#L48)).
**Authentication:** JWT required (`user: CurrentUser`).
**Authorization:** JWT-only. No admin gate.

**Request Schema**
- Path parameters: `session_id: UUID`, `format: str` (case-insensitive — lowercased before lookup, [exports.py:48](../../app/api/exports.py#L48)).
- No request body.

**Response Schema**
- A binary/text `Response` whose `media_type` is the matching MIME from `_KIND_TO_MIME` and whose `Content-Disposition` is `attachment; filename="<session.code>.<fmt>"` ([exports.py:103-108](../../app/api/exports.py#L103)).
- Body produced by the matching transformer from `app/engines/artifact_transformer`: `to_txt`, `to_srt`, `to_vtt`, `to_docx`, `to_cms_html` (for `html`), or `to_zip` ([exports.py:55-81](../../app/api/exports.py#L55)).

**Validation Rules**
- `format` must be one of the `_KIND_TO_MIME` keys after lowercasing, else 400 ([exports.py:49-53](../../app/api/exports.py#L49)).
- The session is loaded via `load_session_for_export`; a `RuntimeError` is mapped to 404 ([exports.py:65-68](../../app/api/exports.py#L65)).

**Side effects**
- Upserts `artifacts (session_id, kind, bytes, generated_by)` with `ON CONFLICT (session_id, kind) DO UPDATE`. This block is best-effort: any exception is swallowed and rolled back (treated as "schema not migrated / transient DB error") and does **not** fail the download ([exports.py:84-101](../../app/api/exports.py#L84)).

**Errors**

| Status | Condition | Detail |
|--------|-----------|--------|
| 401 | missing/invalid JWT | "Could not validate credentials" |
| 400 | unsupported `format` | `{"code": "INVALID_FORMAT", "supported": ["txt","srt","vtt","docx","html","zip"]}` ([exports.py:50-53](../../app/api/exports.py#L50)) |
| 404 | session not loadable | message from the underlying `RuntimeError` ([exports.py:67-68](../../app/api/exports.py#L67)) |

**Example**
```bash
curl -s -OJ -H "Authorization: Bearer $TOKEN" \
  https://rounds.vin/v1/sessions/<SESSION_ID>/exports/docx
```

**Related Screens:** Session detail / editor export-download actions; CMS export flow (the `html` format uses `to_cms_html`).
**Related Tables:** `artifacts` (best-effort upsert). Session/segment data is loaded by `app/engines/artifact_transformer.load_session_for_export`.

---

## 2. GET `/v1/sessions/{session_id}/captions.vtt`

**Endpoint** [exports.py:120](../../app/api/exports.py#L120) (on `captions_router`)
**Method:** GET
**Purpose:** Serve WebVTT captions for the video `<track>` element, with `ETag` + `Cache-Control` so the editor doesn't re-fetch on every mount. The ETag fingerprints `(session_id, max correction_ledger.sequence_number)` so the cache invalidates the moment any correction lands ([exports.py:111-128](../../app/api/exports.py#L111)).
**Authentication:** JWT required (`_user: CurrentUser`). The editor fetches this via authenticated `fetch()` and wraps the body in a Blob URL, sidestepping `<track>`'s inability to send `Authorization` headers ([exports.py:112-115](../../app/api/exports.py#L112)).
**Authorization:** JWT-only. No admin gate.

**Request Schema**
- Path parameter: `session_id: UUID`.
- Request header (optional): `If-None-Match` — when it equals the computed ETag, the server returns 304 with no body ([exports.py:150-157](../../app/api/exports.py#L150)).
- No request body.

**Response Schema**
- **200:** body = `to_vtt(sess)`; `media_type = text/vtt; charset=utf-8`; headers `ETag`, `Cache-Control: private, max-age=60`, `Content-Disposition: inline` ([exports.py:165-176](../../app/api/exports.py#L165)).
- **304:** empty body; headers `ETag`, `Cache-Control: private, max-age=60` ([exports.py:150-157](../../app/api/exports.py#L150)).
- ETag format: `W/"<session_id>-<max_seq>"`, where `max_seq` is `COALESCE(MAX(sequence_number), -1)` over `correction_ledger` for the session ([exports.py:138-148](../../app/api/exports.py#L138)).

**Validation Rules**
- The ETag is computed from `correction_ledger` (the Phase-4 append-only ledger), **not** the legacy `corrections` audit table. The code comment documents this as a 2026-06-06 bug fix — `corrections` has no `sequence_number` column ([exports.py:133-137](../../app/api/exports.py#L133)).
- Session loaded via `load_session_for_export`; `RuntimeError` → 404 ([exports.py:160-163](../../app/api/exports.py#L160)).

**Errors**

| Status | Condition | Detail |
|--------|-----------|--------|
| 401 | missing/invalid JWT | "Could not validate credentials" |
| 304 | `If-None-Match` matches current ETag | no body (this is the cache-hit path, not an error) |
| 404 | session not loadable | message from the underlying `RuntimeError` ([exports.py:162-163](../../app/api/exports.py#L162)) |

**Example**
```bash
# Conditional request — returns 304 when the ETag is unchanged
curl -s -H "Authorization: Bearer $TOKEN" \
  -H 'If-None-Match: W/"<SESSION_ID>-<MAX_SEQ>"' \
  https://rounds.vin/v1/sessions/<SESSION_ID>/captions.vtt
```

**Related Screens:** Editor video player `<track>` captions.
**Related Tables:** `correction_ledger` (ETag fingerprint only). VTT body produced by `app/engines/artifact_transformer.to_vtt`.

---

## Source Verification
- **Files Used:** [app/api/exports.py](../../app/api/exports.py), [app/auth.py](../../app/auth.py)
- **Components Used:** none (frontend `<track>` / editor referenced only in code comments, not read)
- **APIs Used:** `GET /v1/sessions/{session_id}/exports/{format}`, `GET /v1/sessions/{session_id}/captions.vtt`
- **Database Tables Used:** `artifacts` (upsert in endpoint 1), `correction_ledger` (ETag fingerprint in endpoint 2)
- **Permission Logic Used:** JWT presence only (`CurrentUser` → `get_current_user`). No `LEGACY_ADMIN_EMAIL` / `require_admin` gate in this router (grep-confirmed: no matches).
- **Confidence Score:** High — formats, headers, ETag derivation, and error codes all read directly from the router source. The transformer functions (`to_*`, `load_session_for_export`) are referenced by import but their internals were not opened; their existence and call sites are verified.
- **Evidence Links:** decorators at [exports.py:41](../../app/api/exports.py#L41), [exports.py:120](../../app/api/exports.py#L120); format map at [exports.py:31](../../app/api/exports.py#L31); ETag at [exports.py:138](../../app/api/exports.py#L138); auth at [app/auth.py:172](../../app/auth.py#L172).
