# API endpoint index

Complete catalog of every HTTP route registered on the Rounds FastAPI app, extracted directly from the `@router` / `@captions_router` / `@global_router` decorators in [`app/api/*.py`](../../app/api/). Each router is mounted in [`app/main.py:212`](../../app/main.py#L212) onward via `app.include_router(...)`.

## Total route count

**144 routes** across 20 router-object files (22 router objects — `exports.py` and `sop.py` each register a second router).

> This supersedes the "32 routes live" figure in [`CLAUDE.md`](../../CLAUDE.md). The real count verified from `@router`/`@captions_router`/`@global_router` decorators is **144**. The "32" figure is stale.

## How auth works (verified)

- **Auth = JWT presence.** Every route except `POST /v1/auth/login` depends on `CurrentUser` ([`app/auth.py:208`](../../app/auth.py#L208)), which decodes the HS256 bearer token and confirms the principal is still active (DB lookup with env-CSV fallback). The `User` object carries only `email` ([`app/auth.py:36`](../../app/auth.py#L36)) — `auth_users.role` is **not** loaded by `get_current_user` ([`app/auth.py:172`](../../app/auth.py#L172)).
- **Admin gate = the LEGACY_ADMIN_EMAIL gate.** Admin-only routes call `require_admin(user)` / `is_admin(user)` from [`app/security/roles.py`](../../app/security/roles.py). With no `role` passed, that helper reduces to `user.email == "johndean@vin.com"` ([`app/security/roles.py:92`](../../app/security/roles.py#L92)). Two diagnostics routes inline the same literal check directly ([`app/api/diagnostics.py:534`](../../app/api/diagnostics.py#L534), [`app/api/diagnostics.py:632`](../../app/api/diagnostics.py#L632)).
- **Role tiers are not active.** `auth_users.role` (migration 045) exists but is never read at request time, so there is exactly one admin (`johndean@vin.com`) and one non-admin tier (everyone else with a valid token). Routes in the table marked "Audience filter" are **not** access-gated — they return rows to any authenticated user but narrow the result set for non-admins (see [`app/api/help.py:388`](../../app/api/help.py#L388)).

> **Discrepancy with the originating brief.** The brief stated `require_admin`/`is_admin` are "NOT wired into endpoints." That is **no longer true in the current code** — `require_admin`/`is_admin` are wired into ~38 endpoints across `settings.py`, `help.py`, `email_templates.py`, `email_debug.py`, `sessions.py`, and `locks.py`. The brief's other claims hold: the gate is still the hardcoded `johndean@vin.com` email (now centralized in `app/security/roles.py` instead of inline), `auth_users.role` is still not consulted by `get_current_user`, and the client-side `adminOnly` guard at [`frontend/src/router/index.ts:63`](../../frontend/src/router/index.ts#L63) is unverified by this assignment. NOT VERIFIED IN CODE: the frontend router guard (out of scope of this index).

## Route table

Auth column legend: **JWT** = requires a valid bearer token (`CurrentUser`); **Public** = no auth dependency.
Admin-gated column: **Yes** = `require_admin`/`is_admin`/inline email check enforces `johndean@vin.com`; **Audience filter** = not gated, but result set narrows for non-admins; **No** = any authenticated user.

| Method | Path | Router file | Auth | Admin-gated? | Doc |
|---|---|---|---|---|---|
| POST | `/v1/auth/login` | auth.py | Public | No | [auth](./auth.md) |
| GET | `/v1/auth/me` | auth.py | JWT | No | [auth](./auth.md) |
| POST | `/v1/gcs/upload-url` | gcs_upload.py | JWT | No | [gcs-upload](./gcs-upload.md) |
| POST | `/v1/gcs/upload-complete` | gcs_upload.py | JWT | No | [gcs-upload](./gcs-upload.md) |
| GET | `/v1/sessions` | sessions.py | JWT | No | [sessions](./sessions.md) |
| POST | `/v1/sessions` | sessions.py | JWT | No | [sessions](./sessions.md) |
| GET | `/v1/sessions/deleted` | sessions.py | JWT | Yes | [sessions](./sessions.md) |
| GET | `/v1/sessions/{session_id}/audit-log` | sessions.py | JWT | No | [sessions](./sessions.md) |
| GET | `/v1/sessions/{session_id}/pipeline-config` | sessions.py | JWT | No | [sessions](./sessions.md) |
| GET | `/v1/sessions/{session_id}/stage-assignees` | sessions.py | JWT | No | [sessions](./sessions.md) |
| PUT | `/v1/sessions/{session_id}/stage-assignees/{stage}` | sessions.py | JWT | No | [sessions](./sessions.md) |
| POST | `/v1/sessions/{session_id}/stage-assignees/apply-type-defaults` | sessions.py | JWT | No | [sessions](./sessions.md) |
| GET | `/v1/sessions/{session_id}` | sessions.py | JWT | No | [sessions](./sessions.md) |
| PATCH | `/v1/sessions/{session_id}` | sessions.py | JWT | No | [sessions](./sessions.md) |
| DELETE | `/v1/sessions/{session_id}` | sessions.py | JWT | No | [sessions](./sessions.md) |
| POST | `/v1/sessions/{session_id}/restore` | sessions.py | JWT | Yes | [sessions](./sessions.md) |
| DELETE | `/v1/sessions/{session_id}/permanent` | sessions.py | JWT | Yes | [sessions](./sessions.md) |
| GET | `/v1/sessions/{session_id}/failure-reason` | sessions.py | JWT | No | [sessions](./sessions.md) |
| POST | `/v1/sessions/{session_id}/lock/acquire` | locks.py | JWT | No | [locks](./locks.md) |
| POST | `/v1/sessions/{session_id}/lock/heartbeat` | locks.py | JWT | No | [locks](./locks.md) |
| POST | `/v1/sessions/{session_id}/lock/release` | locks.py | JWT | No | [locks](./locks.md) |
| GET | `/v1/sessions/{session_id}/lock/holder` | locks.py | JWT | No | [locks](./locks.md) |
| POST | `/v1/sessions/{session_id}/lock/force-take` | locks.py | JWT | Yes | [locks](./locks.md) |
| GET | `/v1/sessions/{session_id}/missing` | add_to_session.py | JWT | No | [add-to-session](./add-to-session.md) |
| POST | `/v1/sessions/{session_id}/add/signed-url` | add_to_session.py | JWT | No | [add-to-session](./add-to-session.md) |
| POST | `/v1/sessions/{session_id}/add/slides` | add_to_session.py | JWT | No | [add-to-session](./add-to-session.md) |
| POST | `/v1/sessions/{session_id}/add/chat` | add_to_session.py | JWT | No | [add-to-session](./add-to-session.md) |
| POST | `/v1/sessions/{session_id}/add/manifest` | add_to_session.py | JWT | No | [add-to-session](./add-to-session.md) |
| POST | `/v1/sessions/{session_id}/slides/re-extract` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| GET | `/v1/sessions/{session_id}/slides` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| POST | `/v1/sessions/{session_id}/captions/burn` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| GET | `/v1/sessions/{session_id}/captioned-video` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| GET | `/v1/sessions/{session_id}/speakers` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| POST | `/v1/sessions/{session_id}/speakers` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| PATCH | `/v1/sessions/{session_id}/speakers/{speaker_id}` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| DELETE | `/v1/sessions/{session_id}/speakers/{speaker_id}` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| POST | `/v1/sessions/{session_id}/segments/{segment_id}/speaker-reassign` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| GET | `/v1/sessions/{session_id}/sources` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| GET | `/v1/sessions/{session_id}/media-url` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| GET | `/v1/sessions/{session_id}/words` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| GET | `/v1/sessions/{session_id}/chat` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| PATCH | `/v1/sessions/{session_id}/chat/order` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| PATCH | `/v1/sessions/{session_id}/chat/{message_id}` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| GET | `/v1/sessions/{session_id}/chat-participants` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| GET | `/v1/sessions/{session_id}/polls` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| PATCH | `/v1/sessions/{session_id}/polls/order` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| PATCH | `/v1/sessions/{session_id}/polls/{poll_id}/anchor` | session_resources.py | JWT | No | [session-resources](./session-resources.md) |
| POST | `/v1/sessions/{session_id}/corrections` | corrections.py | JWT | No | [corrections](./corrections.md) |
| POST | `/v1/sessions/{session_id}/find-replace` | corrections.py | JWT | No | [corrections](./corrections.md) |
| GET | `/v1/sessions/{session_id}/corrections` | corrections.py | JWT | No | [corrections](./corrections.md) |
| POST | `/v1/sessions/{session_id}/corrections/undo` | corrections.py | JWT | No | [corrections](./corrections.md) |
| POST | `/v1/sessions/{session_id}/corrections/redo` | corrections.py | JWT | No | [corrections](./corrections.md) |
| GET | `/v1/sessions/{session_id}/review-queue` | corrections.py | JWT | No | [corrections](./corrections.md) |
| GET | `/v1/sessions/{session_id}/segments` | segments.py | JWT | No | [segments](./segments.md) |
| PATCH | `/v1/sessions/{session_id}/segments/{segment_id}` | segments.py | JWT | No | [segments](./segments.md) |
| POST | `/v1/sessions/{session_id}/segments/{segment_id}/reassign` | segments.py | JWT | No | [segments](./segments.md) |
| GET | `/v1/sessions/{session_id}/discrepancies` | discrepancies.py | JWT | No | [discrepancies](./discrepancies.md) |
| GET | `/v1/sessions/{session_id}/word-alignment` | word_alignment.py | JWT | No | [word-alignment](./word-alignment.md) |
| GET | `/v1/sessions/{session_id}/sop` | sop.py | JWT | No | [sop](./sop.md) |
| POST | `/v1/sessions/{session_id}/sop/advance` | sop.py | JWT | No | [sop](./sop.md) |
| POST | `/v1/sessions/{session_id}/sop/assign` | sop.py | JWT | No | [sop](./sop.md) |
| PATCH | `/v1/sessions/{session_id}/sop/annotations` | sop.py | JWT | No | [sop](./sop.md) |
| POST | `/v1/sessions/{session_id}/sop/checks/resolve` | sop.py | JWT | No | [sop](./sop.md) |
| GET | `/v1/sop/dashboard-summary` | sop.py (`global_router`) | JWT | No | [sop](./sop.md) |
| GET | `/v1/sessions/{session_id}/exports/{format}` | exports.py | JWT | No | [exports](./exports.md) |
| GET | `/v1/sessions/{session_id}/captions.vtt` | exports.py (`captions_router`) | JWT | No | [exports](./exports.md) |
| GET | `/v1/audit` | audit.py | JWT | No | [audit](./audit.md) |
| GET | `/v1/audit/sessions/{session_id}/corrections` | audit.py | JWT | No | [audit](./audit.md) |
| GET | `/v1/improvements` | improvements.py | JWT | No | [improvements](./improvements.md) |
| POST | `/v1/improvements` | improvements.py | JWT | No | [improvements](./improvements.md) |
| GET | `/v1/improvements/{improvement_id}` | improvements.py | JWT | No | [improvements](./improvements.md) |
| PUT | `/v1/improvements/{improvement_id}/wizard/{step}` | improvements.py | JWT | No | [improvements](./improvements.md) |
| PATCH | `/v1/improvements/{improvement_id}` | improvements.py | JWT | No | [improvements](./improvements.md) |
| DELETE | `/v1/improvements/{improvement_id}` | improvements.py | JWT | No | [improvements](./improvements.md) |
| GET | `/v1/queue/mine` | queue.py | JWT | No | [queue](./queue.md) |
| GET | `/v1/settings` | settings.py | JWT | No | [settings](./settings.md) |
| PUT | `/v1/settings/{key}` | settings.py | JWT | No | [settings](./settings.md) |
| GET | `/v1/settings/people` | settings.py | JWT | No | [settings](./settings.md) |
| POST | `/v1/settings/people` | settings.py | JWT | No | [settings](./settings.md) |
| DELETE | `/v1/settings/people/{person_id}` | settings.py | JWT | No | [settings](./settings.md) |
| PUT | `/v1/settings/people/{person_id}` | settings.py | JWT | No | [settings](./settings.md) |
| GET | `/v1/settings/groups` | settings.py | JWT | No | [settings](./settings.md) |
| POST | `/v1/settings/groups` | settings.py | JWT | No | [settings](./settings.md) |
| PUT | `/v1/settings/groups/{group_id}` | settings.py | JWT | No | [settings](./settings.md) |
| DELETE | `/v1/settings/groups/{group_id}` | settings.py | JWT | No | [settings](./settings.md) |
| GET | `/v1/settings/groups/{group_id}/members` | settings.py | JWT | No | [settings](./settings.md) |
| GET | `/v1/settings/groups-members` | settings.py | JWT | No | [settings](./settings.md) |
| POST | `/v1/settings/groups/{group_id}/members/{person_id}` | settings.py | JWT | No | [settings](./settings.md) |
| DELETE | `/v1/settings/groups/{group_id}/members/{person_id}` | settings.py | JWT | No | [settings](./settings.md) |
| GET | `/v1/settings/types` | settings.py | JWT | No | [settings](./settings.md) |
| POST | `/v1/settings/types` | settings.py | JWT | Yes | [settings](./settings.md) |
| DELETE | `/v1/settings/types/{type_id}` | settings.py | JWT | Yes | [settings](./settings.md) |
| GET | `/v1/settings/types/{type_id}/assignees` | settings.py | JWT | No | [settings](./settings.md) |
| PUT | `/v1/settings/types/{type_id}/assignees` | settings.py | JWT | Yes | [settings](./settings.md) |
| GET | `/v1/settings/auth-users` | settings.py | JWT | Yes | [settings](./settings.md) |
| POST | `/v1/settings/auth-users` | settings.py | JWT | Yes | [settings](./settings.md) |
| PUT | `/v1/settings/auth-users/{user_id}` | settings.py | JWT | Yes | [settings](./settings.md) |
| POST | `/v1/settings/auth-users/{user_id}/reset-password` | settings.py | JWT | Yes | [settings](./settings.md) |
| DELETE | `/v1/settings/auth-users/{user_id}` | settings.py | JWT | Yes | [settings](./settings.md) |
| GET | `/v1/settings/export/macro` | settings.py | JWT | No | [settings](./settings.md) |
| GET | `/v1/settings/templates` | settings.py | JWT | No | [settings](./settings.md) |
| GET | `/v1/settings/templates/{template_id}` | settings.py | JWT | No | [settings](./settings.md) |
| POST | `/v1/settings/templates` | settings.py | JWT | Yes | [settings](./settings.md) |
| PUT | `/v1/settings/templates/{template_id}` | settings.py | JWT | Yes | [settings](./settings.md) |
| DELETE | `/v1/settings/templates/{template_id}` | settings.py | JWT | Yes | [settings](./settings.md) |
| GET | `/v1/email-templates` | email_templates.py | JWT | No | [email-templates](./email-templates.md) |
| GET | `/v1/email-templates/{template_id}` | email_templates.py | JWT | No | [email-templates](./email-templates.md) |
| POST | `/v1/email-templates` | email_templates.py | JWT | Yes | [email-templates](./email-templates.md) |
| PUT | `/v1/email-templates/{template_id}` | email_templates.py | JWT | Yes | [email-templates](./email-templates.md) |
| DELETE | `/v1/email-templates/{template_id}` | email_templates.py | JWT | Yes | [email-templates](./email-templates.md) |
| POST | `/v1/email-templates/resolve` | email_templates.py | JWT | No | [email-templates](./email-templates.md) |
| GET | `/v1/admin/email-debug/config` | email_debug.py | JWT | Yes | [email-debug](./email-debug.md) |
| POST | `/v1/admin/email-debug/connectivity` | email_debug.py | JWT | Yes | [email-debug](./email-debug.md) |
| POST | `/v1/admin/email-debug/send` | email_debug.py | JWT | Yes | [email-debug](./email-debug.md) |
| GET | `/v1/admin/email-debug/attempts` | email_debug.py | JWT | Yes | [email-debug](./email-debug.md) |
| POST | `/v1/help/ask` | help.py | JWT | No | [help](./help.md) |
| GET | `/v1/help/articles` | help.py | JWT | Audience filter | [help](./help.md) |
| GET | `/v1/help/articles/{article_id}` | help.py | JWT | Audience filter | [help](./help.md) |
| POST | `/v1/help/articles` | help.py | JWT | Yes | [help](./help.md) |
| PATCH | `/v1/help/articles/{article_id}` | help.py | JWT | Yes | [help](./help.md) |
| PATCH | `/v1/help/articles/{article_id}/archive` | help.py | JWT | Yes | [help](./help.md) |
| PATCH | `/v1/help/articles/reorder` | help.py | JWT | Yes | [help](./help.md) |
| GET | `/v1/help/articles/{article_id}/versions` | help.py | JWT | Yes | [help](./help.md) |
| GET | `/v1/help/articles/{article_id}/versions/{version}` | help.py | JWT | Yes | [help](./help.md) |
| GET | `/v1/help/coverage` | help.py | JWT | Yes | [help](./help.md) |
| GET | `/v1/help/search` | help.py | JWT | Audience filter | [help](./help.md) |
| POST | `/v1/help/admin/bulk-publish` | help.py | JWT | Yes | [help](./help.md) |
| POST | `/v1/help/admin/fix-summaries` | help.py | JWT | Yes | [help](./help.md) |
| POST | `/v1/help/admin/expand-steps` | help.py | JWT | Yes | [help](./help.md) |
| POST | `/v1/help/admin/expand-faqs` | help.py | JWT | Yes | [help](./help.md) |
| POST | `/v1/help/admin/generate-faq-corpus` | help.py | JWT | Yes | [help](./help.md) |
| GET | `/v1/diag/gcs` | diagnostics.py | JWT | No | [diagnostics](./diagnostics.md) |
| GET | `/v1/diag/classify-route` | diagnostics.py | JWT | No | [diagnostics](./diagnostics.md) |
| POST | `/v1/diag/reingest/{session_id}` | diagnostics.py | JWT | No | [diagnostics](./diagnostics.md) |
| POST | `/v1/diag/realign/{session_id}` | diagnostics.py | JWT | No | [diagnostics](./diagnostics.md) |
| POST | `/v1/diag/init-session-stages/{session_id}` | diagnostics.py | JWT | No | [diagnostics](./diagnostics.md) |
| POST | `/v1/diag/autoplace-polls/{session_id}` | diagnostics.py | JWT | No | [diagnostics](./diagnostics.md) |
| POST | `/v1/diag/clear-rate-limit-slots` | diagnostics.py | JWT | No | [diagnostics](./diagnostics.md) |
| POST | `/v1/diag/sop-check` | diagnostics.py | JWT | No | [diagnostics](./diagnostics.md) |
| POST | `/v1/diag/flush-celery-queue` | diagnostics.py | JWT | No | [diagnostics](./diagnostics.md) |
| POST | `/v1/diag/revoke-task/{task_id}` | diagnostics.py | JWT | No | [diagnostics](./diagnostics.md) |
| POST | `/v1/diag/abort-session/{session_id}` | diagnostics.py | JWT | No | [diagnostics](./diagnostics.md) |
| POST | `/v1/diag/reseed-auth-users` | diagnostics.py | JWT | Yes | [diagnostics](./diagnostics.md) |
| GET | `/v1/diag/gcs-checks` | diagnostics.py | JWT | Yes | [diagnostics](./diagnostics.md) |

### Per-router subtotals

| Router file | Router object(s) | Routes |
|---|---|---|
| auth.py | `router` | 2 |
| gcs_upload.py | `router` | 2 |
| sessions.py | `router` | 14 |
| locks.py | `router` | 5 |
| add_to_session.py | `router` | 5 |
| session_resources.py | `router` | 19 |
| corrections.py | `router` | 6 |
| segments.py | `router` | 3 |
| discrepancies.py | `router` | 1 |
| word_alignment.py | `router` | 1 |
| sop.py | `router` + `global_router` | 6 |
| exports.py | `router` + `captions_router` | 2 |
| audit.py | `router` | 2 |
| improvements.py | `router` | 6 |
| queue.py | `router` | 1 |
| settings.py | `router` | 30 |
| email_templates.py | `router` | 6 |
| email_debug.py | `router` | 4 |
| help.py | `router` | 16 |
| diagnostics.py | `router` | 13 |
| **Total** | **22 router objects / 20 files** | **144** |

> The `__init__.py` in `app/api/` is empty (1 line); routers are imported and mounted in [`app/main.py`](../../app/main.py#L212).

## Admin-gated routes (the full list)

These 36 routes enforce the `johndean@vin.com` gate (`require_admin` / `is_admin` / inline email check). Everything else is reachable by any authenticated user.

- **sessions.py (3):** `GET /v1/sessions/deleted` ([:276](../../app/api/sessions.py#L276)), `POST /v1/sessions/{id}/restore` ([:674](../../app/api/sessions.py#L674)), `DELETE /v1/sessions/{id}/permanent` ([:707](../../app/api/sessions.py#L707)).
- **locks.py (1):** `POST /v1/sessions/{id}/lock/force-take` ([:225](../../app/api/locks.py#L225)).
- **settings.py (11):** `POST/DELETE /types`, `PUT /types/{id}/assignees`, all five `/auth-users` routes, and `POST/PUT/DELETE /templates` (see [settings.py](../../app/api/settings.py)).
- **email_templates.py (3):** `POST` / `PUT /{id}` / `DELETE /{id}` (`require_admin` at [:223](../../app/api/email_templates.py#L223), [:266](../../app/api/email_templates.py#L266), [:298](../../app/api/email_templates.py#L298)).
- **email_debug.py (4):** all four routes (module-level `_require_admin` → `require_admin` at [:53](../../app/api/email_debug.py#L53)).
- **help.py (12):** create/patch/archive/reorder/versions(x2)/coverage + the four `/admin/*` AI/bulk actions (8 + 4).
- **diagnostics.py (2):** `POST /v1/diag/reseed-auth-users` ([:534](../../app/api/diagnostics.py#L534)) and `GET /v1/diag/gcs-checks` ([:632](../../app/api/diagnostics.py#L632)). The other 11 `/v1/diag/*` routes are JWT-only — they use `_u: CurrentUser` with no admin check, despite the CLAUDE.md note implying all diag routes require admin. PARTIALLY IMPLEMENTED: 11 of 13 `/v1/diag/*` operator routes have no admin gate.

## Source Verification
- **Files Used:** `app/api/auth.py`, `app/api/gcs_upload.py`, `app/api/sessions.py`, `app/api/locks.py`, `app/api/add_to_session.py`, `app/api/session_resources.py`, `app/api/corrections.py`, `app/api/segments.py`, `app/api/discrepancies.py`, `app/api/word_alignment.py`, `app/api/sop.py`, `app/api/exports.py`, `app/api/audit.py`, `app/api/improvements.py`, `app/api/queue.py`, `app/api/settings.py`, `app/api/email_templates.py`, `app/api/email_debug.py`, `app/api/help.py`, `app/api/diagnostics.py`, `app/api/__init__.py`, `app/main.py`, `app/auth.py`, `app/security/roles.py`
- **Components Used:** none
- **APIs Used:** all 144 routes enumerated above (the 22 router objects across 20 files)
- **Database Tables Used:** none (this is a route index; tables referenced only incidentally in handler bodies: `sessions`, `correction_ledger`, `artifacts`, `help_articles`, `session_locks`, `auth_users`)
- **Permission Logic Used:** JWT presence (`CurrentUser`, `app/auth.py:208`) for all routes except `POST /v1/auth/login`; admin gate = `require_admin`/`is_admin` from `app/security/roles.py` reducing to `user.email == "johndean@vin.com"` (LEGACY_ADMIN_EMAIL), plus two inline email checks in `diagnostics.py`. `auth_users.role` is not read at request time.
- **Confidence Score:** High — every row derived from a verbatim `@router`/`@captions_router`/`@global_router` decorator, the router-prefix definitions, the `app/main.py` mount order, and the actual `require_admin`/`is_admin`/inline-email-check callsites. Count cross-checked by ripgrep (144 occurrences).
- **Evidence Links:** [app/main.py:212](../../app/main.py#L212), [app/auth.py:172](../../app/auth.py#L172), [app/auth.py:208](../../app/auth.py#L208), [app/security/roles.py:92](../../app/security/roles.py#L92), [app/api/diagnostics.py:534](../../app/api/diagnostics.py#L534), [app/api/help.py:388](../../app/api/help.py#L388), [app/api/settings.py:431](../../app/api/settings.py#L431), [app/api/locks.py:225](../../app/api/locks.py#L225)
