# Known Limitations — rounds.vin (honest, code-grounded gap list)

This is the "do not oversell" reference for a demo AI. Every limitation below is
traced to code. If a capability is not provable from code, it is tagged
"NOT VERIFIED IN CODE" or "IMPLEMENTATION NOT FOUND" rather than asserted either
way.

---

## 1. Authorization is JWT-presence + a hardcoded admin email — not roles

This is the single most important thing to be honest about.

- Every `/v1/*` route (except `POST /v1/auth/login`) requires only a valid JWT
  via `CurrentUser` → `get_current_user`
  ([app/auth.py:172-205](../app/auth.py#L172)).
- "Admin" everywhere means a hardcoded literal:
  `LEGACY_ADMIN_EMAIL = "johndean@vin.com"`
  ([app/security/roles.py:54](../app/security/roles.py#L54)).
- `app/security/roles.py` (`is_admin` / `require_admin`) is explicitly described
  in its own docstring as **"Phase 8 scaffold only — not yet wired into any
  endpoint"** beyond the legacy gate, and `auth_users.role` (migration 045) is
  **never consulted by `get_current_user`**
  ([app/security/roles.py:10-19](../app/security/roles.py#L10)).
- The only role-ish runtime gates that actually fire:
  - `require_admin(...)` (which resolves to the `LEGACY_ADMIN_EMAIL` email
    check) on `GET /v1/sessions/deleted`, `POST .../restore`,
    `DELETE .../permanent`
    ([app/api/sessions.py:276](../app/api/sessions.py#L276),
    [app/api/sessions.py:674](../app/api/sessions.py#L674),
    [app/api/sessions.py:707](../app/api/sessions.py#L707)).
  - `SESSION_TRASH_ALLOWED = {johndean@vin.com, carlab@vin.com}` for soft-delete
    ([app/api/sessions.py:52](../app/api/sessions.py#L52)).
  - `is_admin(user)` on `POST .../lock/force-take`
    ([app/api/locks.py:225](../app/api/locks.py#L225)).
  - One **client-side** route guard: `meta.adminOnly` on `#/admin/help`,
    compared to the same email in the browser
    ([frontend/src/router/index.ts:63](../frontend/src/router/index.ts#L63)).
    This is UI-only; the server is the authoritative check on `/v1/help/articles*`.

**Implication:** any authenticated user can hit almost every mutating endpoint.
There are no per-stage permissions (e.g. "only a Medical reviewer can advance the
`medical` stage") — the SOP advance route checks only forward-ordering and the
blocked flag, not the caller's role ([app/api/sop.py:113-142](../app/api/sop.py#L113)).

---

## 2. Plaintext credential bootstrap (known debt)

`AUTH_USERS` is a plaintext `email:password` CSV in env. It seeds the bcrypt
`auth_users` table on first boot and remains the live fallback when the DB path
returns nothing or errors ([app/auth.py:81-86](../app/auth.py#L81),
[app/auth.py:132-143](../app/auth.py#L132)). CLAUDE.md flags this as the same
posture as the MIC audit finding #7; hashed-at-rest-only is a future plan.

There is **no account lockout / failed-attempt throttle** in the login path
despite help-center copy claiming one
([app/auth.py:100-143](../app/auth.py#L100); claim at
[app/data/help_content.py:250](../app/data/help_content.py#L250)).

---

## 3. Default-OFF feature flags (do not demo without flipping them)

All four default to `False` in [`app/config.py`](../app/config.py):

| Flag | Default | Effect when off | Evidence |
|---|---|---|---|
| `SPLIT_MERGE_ENABLED` | `False` | split/merge corrections return `503 SPLIT_MERGE_DISABLED`; UI hides controls | [app/config.py:134](../app/config.py#L134), [app/api/corrections.py:362](../app/api/corrections.py#L362) |
| `HELP_ASK_AI_ENABLED` | `False` | `/v1/help/ask` returns 404; "Ask AI" tab hidden | [app/config.py:121](../app/config.py#L121), [app/api/help.py:174](../app/api/help.py#L174) |
| `SOP_DEADLINE_EMAIL_ENABLED` | `False` | overdue stages are counted but no email is sent | [app/config.py:110](../app/config.py#L110) |
| `UPLOAD_WATCHDOG_ENABLED` | `False` | stuck `uploading` sessions are not auto-recovered (manual `/v1/diag/reingest`) | [app/config.py:100](../app/config.py#L100) |

The frontend reads `help_ask_ai_enabled` and `split_merge_enabled` from
`/v1/version` at mount ([app/main.py:183-188](../app/main.py#L183)).

---

## 4. Single-editor locking (no real-time collaboration)

Editing is single-writer. The lock is a single `session_locks` row per session
with a 90-second TTL (3 missed 30s heartbeats)
([app/api/locks.py:42-44](../app/api/locks.py#L42)). A second editor is bounced
to read-only and shown the holder; there is no operational-transform /
concurrent merge. A stale lock auto-steals; a live lock requires admin
`force-take` ([app/api/locks.py:99-139](../app/api/locks.py#L99),
[app/api/locks.py:218-262](../app/api/locks.py#L218)). The module docstring notes
the lock is advisory at the DB layer and enforced at the API layer on autosave.

---

## 5. Reporting is current-state only — no time series

Per [`docs/product/reporting.md`](../docs/product/reporting.md) (consistent with
the code): the Dashboard shows live counts and the SOP `dashboard-summary`
computes `count` + `overdue_count` per stage on the fly
([app/api/sop.py:279-325](../app/api/sop.py#L279)). Documented gaps:

- No historical trend charts (no time-series store behind the metric cards).
- No SLA dwell-time history (you see "overdue", not average time-in-stage).
- No per-operator productivity metrics.
- No AI/storage cost tracking.
- No exportable reports (screenshot / print-to-PDF only).

---

## 6. No mobile app and no separate admin portal

- The frontend is a single hash-routed Vue SPA
  ([frontend/src/router/index.ts:22-47](../frontend/src/router/index.ts#L22)).
  There is no native mobile client in this repo, and no dedicated
  admin-portal application — admin actions are the same SPA plus the
  `#/admin/help` route and curl-only `/v1/diag/*` tools.
- Responsive / mobile-optimized layout: **NOT VERIFIED IN CODE** — the views
  exist but no breakpoint/mobile-layout audit was performed here.

---

## 7. Operator diagnostics have no UI

The 13 `/v1/diag/*` rescue endpoints (reingest, realign, abort-session,
flush-celery-queue, clear-rate-limit-slots, reseed-auth-users, etc.) are
curl/Postman-only operator tools, all gated by `CurrentUser` only
([app/api/diagnostics.py](../app/api/diagnostics.py); enumerated in CLAUDE.md).
They are not surfaced in any view.

---

## 8. Two parallel correction/audit systems coexist

There is legacy debt in the edit-history layer:

- `corrections` (migration 002) — the legacy append-only edit log, still written
  by `segments.py`/`audit.py`.
- `correction_ledger` + `ledger_pointers` (migration 029) — the Phase-4
  append-only ledger that backs undo/redo and is the source for the captions
  ETag fingerprint ([app/api/exports.py:129-147](../app/api/exports.py#L129)).
- `audit_events` (migration 004) — the global UI-action log.

Both correction tables are live at once; a demo should not claim a single
unified audit store.

---

## 9. Two discrepancy tables — only one is wired

- `transcription_discrepancies` (migration 017) is what the Discrepancies
  endpoint actually reads ([app/api/discrepancies.py:72-78](../app/api/discrepancies.py#L72)).
- The older `discrepancies` table (migration 002) was what the endpoint used to
  point at; it "always returned []" and is no longer the source
  ([app/api/discrepancies.py:4-9](../app/api/discrepancies.py#L4)).

---

## 10. Created-but-unused schema (no read/write path found)

Per the data dictionary's own verification, some tables are created by a
migration but have **no source reference** in `app/`:

- `sop_approvals` — "no `api/`, `tasks/`, or `services/` file references this
  table … Used By APIs: IMPLEMENTATION NOT FOUND"
  (see [data-model-reference.md](data-model-reference.md) and
  `docs/data/data-dictionary.md` → `sop_approvals`).
- `slide_time_ranges` / `replay_log` are backend fusion artifacts with **no UI
  read path** (NOT VERIFIED IN CODE that any view reads them).

Do not present these as user-facing features.

---

## 11. Help Center content has two sources of truth (drift risk)

In-app help is seeded from `app/data/help_content.py` /
`frontend/src/constants/help-content.ts`, while `docs/help-center/faq.md` is the
offline mirror. The README says to keep them in sync, but they have already
drifted (the file-type and lockout claims in the FAQ do not match code — see
[frequently-asked-questions.md](frequently-asked-questions.md)). A Phase-3
`help_articles` table (migration 053) is intended to eventually own this content
but is not yet the single source.

---

## 12. Shared production data plane with MIC (per CLAUDE.md)

Uploads land in MIC's GCS bucket (`video-pipeline-uploads-mic`), Gemini bills
MIC's quota, and SMTP sends as `mic@design.veterinary.support`. Only Postgres +
Redis are isolated to Rounds. This is documented infrastructure debt, not a
product feature — relevant if a demo touches real uploads or email.

---

## Source Verification
- **Files Used:** `app/auth.py`, `app/security/roles.py`, `app/api/sessions.py`, `app/api/locks.py`, `app/api/sop.py`, `app/api/corrections.py`, `app/api/discrepancies.py`, `app/api/exports.py`, `app/api/help.py`, `app/api/diagnostics.py`, `app/config.py`, `app/main.py`, `app/data/help_content.py`, `frontend/src/router/index.ts`, `docs/product/reporting.md`, `docs/data/data-dictionary.md`, `CLAUDE.md`
- **Components Used:** Vue SPA router (`router/index.ts`) — confirms single SPA + `adminOnly` client guard
- **APIs Used:** `POST /v1/auth/login`, `POST /v1/sessions/{id}/corrections`, `GET /v1/sessions/{id}/discrepancies`, `POST /v1/sessions/{id}/sop/advance`, `POST /v1/sessions/{id}/lock/force-take`, `GET /v1/sessions/deleted`, `POST /v1/sessions/{id}/restore`, `DELETE /v1/sessions/{id}/permanent`, `POST /v1/help/ask`, `/v1/diag/*`
- **Database Tables Used:** `auth_users`, `session_locks`, `corrections`, `correction_ledger`, `ledger_pointers`, `audit_events`, `transcription_discrepancies`, `discrepancies`, `sop_state`, `sop_approvals`, `slide_time_ranges`, `replay_log`, `help_articles`
- **Permission Logic Used:** JWT presence + `LEGACY_ADMIN_EMAIL`/`SESSION_TRASH_ALLOWED` gate + client-side `adminOnly` route guard (scaffold-only role helper NOT wired)
- **Confidence Score:** High — every limitation is line-linked; items that genuinely can't be confirmed (mobile/responsive layout) are tagged NOT VERIFIED IN CODE rather than asserted.
- **Evidence Links:** [app/security/roles.py:10](../app/security/roles.py#L10), [app/config.py:100](../app/config.py#L100), [app/api/locks.py:42](../app/api/locks.py#L42), [app/api/discrepancies.py:4](../app/api/discrepancies.py#L4), [frontend/src/router/index.ts:63](../frontend/src/router/index.ts#L63)
