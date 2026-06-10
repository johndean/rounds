# Workflow: Help Article Bulk Publish & Bulk-AI Rewrites

Admin tooling for the in-app Help Center CMS. Two surfaces:

1. **Bulk publish** — an inline (synchronous) endpoint that publishes every draft article that passes the CC-Rounds compliance check ([`app/api/help.py`](../../app/api/help.py), `POST /v1/help/admin/bulk-publish`).
2. **Bulk-AI rewrites** — four admin endpoints that enqueue Celery tasks ([`app/tasks/help_tasks.py`](../../app/tasks/help_tasks.py)) which use Gemini to fix non-compliant summaries, expand step counts, and seed a starter FAQ corpus. **Every AI-produced article lands as a draft (`is_published=False`)** and must be published — typically via the bulk-publish endpoint above.

These two surfaces form one loop: AI tasks create/rewrite drafts → admin reviews → bulk-publish promotes the compliant ones.

## Trigger

All five are admin-gated POST endpoints under `/v1/help/admin/`:

- `POST /v1/help/admin/bulk-publish` — inline, synchronous ([help.py:829-830](../../app/api/help.py#L829)).
- `POST /v1/help/admin/fix-summaries` → enqueues `rounds.tasks.help.fix_summaries` ([help.py:916-922](../../app/api/help.py#L916)).
- `POST /v1/help/admin/expand-steps` → enqueues `rounds.tasks.help.expand_steps` ([help.py:925-928](../../app/api/help.py#L925)).
- `POST /v1/help/admin/expand-faqs` → enqueues `rounds.tasks.help.expand_faqs` ([help.py:931-934](../../app/api/help.py#L931)).
- `POST /v1/help/admin/generate-faq-corpus` → enqueues `rounds.tasks.help.generate_faq_corpus` ([help.py:937-948](../../app/api/help.py#L937)).

The enqueue helper `_enqueue` calls `celery_app.send_task(name)` and returns `{task_id, task, enqueued:true}` ([help.py:900-913](../../app/api/help.py#L900)). The four AI tasks take no per-article argument — each scans the whole `help_articles` corpus itself.

## Inputs

- **bulk-publish** — no body. Reads all rows where `is_published = FALSE` ([help.py:838-845](../../app/api/help.py#L838)).
- **fix_summaries** — no input. Scans all articles, targets those failing `compute_compliance(...)['summaryOk']` ([help_tasks.py:198-213](../../app/tasks/help_tasks.py#L198)). Target length range is `FAQ_SUMMARY_TARGET` for FAQ categories else `HELP_SUMMARY_TARGET` ([help_tasks.py:221](../../app/tasks/help_tasks.py#L221)).
- **expand_help_steps** — non-FAQ articles with fewer than `HELP_MIN_STEPS=3` steps ([help_tasks.py:407-410](../../app/tasks/help_tasks.py#L407), [help_tasks.py:310-315](../../app/tasks/help_tasks.py#L310)).
- **expand_faq_steps** — FAQ-category articles with fewer than `FAQ_MIN_STEPS=2` steps ([help_tasks.py:418-421](../../app/tasks/help_tasks.py#L418)).
- **generate_faq_corpus** — iterates a hardcoded route table `_FAQ_GENERATOR_ROUTES` (12 entries: dashboard, sessions, editor, sop, upload, improvements, settings, audit, viewer, processing, help, session-detail) and drafts one FAQ per route ([help_tasks.py:436-449](../../app/tasks/help_tasks.py#L436)).

Compliance thresholds and `is_faq_category` come from [`app/utils/help_compliance.py`](../../app/utils/help_compliance.py) ([help_tasks.py:49-56](../../app/tasks/help_tasks.py#L49)). Gemini is reached via `call_gemini_text`; tasks raise `RuntimeError` if `GEMINI_API_KEY` is unset ([help_tasks.py:149-156](../../app/tasks/help_tasks.py#L149)).

## Validations

- **bulk-publish** — per draft, runs `compute_compliance(a)`; publishes only when `cc['allPass']`. Non-passing rows are returned in `skipped[]` with their `wordsOk/summaryOk/stepsOk` + measured counts and reason `"CC-Rounds fail"` ([help.py:850-879](../../app/api/help.py#L850)).
- **All AI tasks land as drafts** — every UPDATE/INSERT sets `is_published = FALSE` (the review-gate invariant) ([help_tasks.py:248-256](../../app/tasks/help_tasks.py#L248), [help_tasks.py:374-382](../../app/tasks/help_tasks.py#L374), [help_tasks.py:716-718](../../app/tasks/help_tasks.py#L716)).
- **Idempotency** — each AI task uses a Redis SETNX key `rounds:help:task:{name}:{article_id}` with 24h TTL; a re-run on the same article within the window is counted as `skipped`. Redis failure soft-fails (proceeds) ([help_tasks.py:79-89](../../app/tasks/help_tasks.py#L79), [help_tasks.py:217-219](../../app/tasks/help_tasks.py#L217)). `generate_faq_corpus` adds a task-level guard keyed on `"global"` to short-circuit a double-clicked Generate, and a per-route deterministic slug `faq-ai-{page_key}` with `ON CONFLICT (slug) DO NOTHING` ([help_tasks.py:556-561](../../app/tasks/help_tasks.py#L556), [help_tasks.py:582-592](../../app/tasks/help_tasks.py#L582), [help_tasks.py:719](../../app/tasks/help_tasks.py#L719)).
- **LLM response validation** — JSON is parsed tolerantly (fence-strip) ([help_tasks.py:159-174](../../app/tasks/help_tasks.py#L159)); summaries/steps must be the right type and non-empty or the article is counted `failed` ([help_tasks.py:239-242](../../app/tasks/help_tasks.py#L239), [help_tasks.py:352-367](../../app/tasks/help_tasks.py#L352)).
- **generate_faq_corpus** additionally enforces: strict string `title`/`summary`, summary length within `FAQ_SUMMARY_TARGET`, ≥ `FAQ_MIN_STEPS` clean steps, `related_ids` filtered to real existing article ids, and a **dev-speak blacklist + regex** post-filter (`_contains_devspeak`) that rejects component names, table names, HTTP routes, framework names, env vars, `Phase N` markers, and `*.vue` references; a hit makes the draft `devspeak_rejected` rather than seeded ([help_tasks.py:644-705](../../app/tasks/help_tasks.py#L644), [help_tasks.py:465-514](../../app/tasks/help_tasks.py#L465)).

## Approvals

- **The publish step IS the approval.** AI tasks never auto-publish; an admin must promote drafts (manually per article via the PATCH route, or in bulk via `bulk-publish` which still requires `allPass`). This human review gate is stated as the contract for all three rewrite tasks ([help_tasks.py:18-21](../../app/tasks/help_tasks.py#L18)) and `generate_faq_corpus` ([help_tasks.py:530-531](../../app/tasks/help_tasks.py#L530)).
- No multi-party / second-reviewer approval exists.

## Notifications

- **No email.** No SMTP send on this surface.
- The enqueue endpoints return `{task_id, ...}` for operator polling; tasks are otherwise fire-and-forget. The task docstrings reference a "WS event / admin toast" carrying the `{rewritten, skipped, failed}` counts ([help_tasks.py:31-32](../../app/tasks/help_tasks.py#L31)), but the WS publish call is NOT present in `help_tasks.py` itself. NOT VERIFIED IN CODE: the WS broadcast of task completion (no `publish_ws_event` call in the read file).
- The durable record of each AI rewrite is an `audit_events` row (see Audit Events), which the docstrings describe as the admin-inspectable result ([help.py:918-920](../../app/api/help.py#L918)).

## Outputs

- **bulk-publish** — UPDATEs passing drafts to `is_published=TRUE, version=version+1, last_edited_by=user.email`; returns `{total_attempted, published, published_ids[], skipped[]}` ([help.py:855-894](../../app/api/help.py#L855)).
- **fix_summaries** — UPDATEs `summary`, bumps `version`, sets `is_published=FALSE`, `last_edited_by='ai:fix_summaries'`; returns `{rewritten, skipped, failed, article_ids[]}` ([help_tasks.py:245-279](../../app/tasks/help_tasks.py#L245)).
- **expand_help_steps / expand_faq_steps** — appends AI-drafted steps to the existing `steps` JSONB, bumps `version`, `is_published=FALSE`, `last_edited_by='ai:{task_name}'`; same return shape ([help_tasks.py:369-404](../../app/tasks/help_tasks.py#L369)).
- **generate_faq_corpus** — INSERTs new draft rows (`slug='faq-ai-{page}'`, `category='faq:{page}'`, `audience='users'`, `is_published=FALSE`, `version=1`, `last_edited_by='ai:generate_faq_corpus'`); returns `{created, skipped_existing, devspeak_rejected, failed, article_ids[]}` ([help_tasks.py:708-777](../../app/tasks/help_tasks.py#L708)).
- **Version snapshots** — before any rewrite UPDATE, `_snapshot_prior` appends the prior article state to `help_article_versions` so admins can revert ([help_tasks.py:116-126](../../app/tasks/help_tasks.py#L116), [help_tasks.py:247](../../app/tasks/help_tasks.py#L247), [help_tasks.py:373](../../app/tasks/help_tasks.py#L373)). (INSERT-only `generate_faq_corpus` has no prior state to snapshot.)

## Status Changes

- Article publication state: **draft (`is_published=FALSE`) → published (`is_published=TRUE`)** only via bulk-publish (or the PATCH route). AI tasks always leave/insert articles in the draft state; they never flip `is_published` to TRUE.
- `version` increments on every rewrite UPDATE and on bulk-publish ([help.py:858](../../app/api/help.py#L858), [help_tasks.py:251](../../app/tasks/help_tasks.py#L251)).
- No session-pipeline status is involved (help articles are not session-scoped).

## Audit Events

- **Every AI rewrite/insert emits one `audit_events` row** via `_emit_audit`: `session_id = NULL`, `kind = 'help.ai_rewrite'`, `actor_email = 'ai:{task-name}'`, a human summary, and `details` carrying `article_id` + version before/after + the relevant length/step counts ([help_tasks.py:129-146](../../app/tasks/help_tasks.py#L129), [help_tasks.py:257-269](../../app/tasks/help_tasks.py#L257), [help_tasks.py:383-395](../../app/tasks/help_tasks.py#L383), [help_tasks.py:741-753](../../app/tasks/help_tasks.py#L741)). `_emit_audit` is best-effort — a failed audit insert is logged and the rewrite proceeds ([help_tasks.py:133-146](../../app/tasks/help_tasks.py#L133)).
- **bulk-publish writes NO audit row** — it records the change only via the `version` bump and `last_edited_by` ([help.py:855-863](../../app/api/help.py#L855)). NOT VERIFIED IN CODE: an audit event on publish.

## Exception Handling

- **bulk-publish** — per-row UPDATE failures are caught, logged, and added to `skipped[]` with reason `"DB update failed"`; the loop continues. A commit failure rolls back and raises HTTP 500 `{code:"INTERNAL"}` ([help.py:865-887](../../app/api/help.py#L865)).
- **AI tasks** — per-article failures are caught and counted as `failed`; the task continues to the next article ([help_tasks.py:272-274](../../app/tasks/help_tasks.py#L272), [help_tasks.py:398-400](../../app/tasks/help_tasks.py#L398)). All inherit `RoundsTask` retry policy; the three rewrite tasks declare `max_retries=2`, `generate_faq_corpus` `max_retries=1` ([help_tasks.py:182](../../app/tasks/help_tasks.py#L182), [help_tasks.py:517](../../app/tasks/help_tasks.py#L517)).
- **generate_faq_corpus** re-raises `OperationalError`/`DisconnectionError` so a full DB outage triggers Celery retry rather than 12 silent per-route failures + 12 wasted Gemini calls ([help_tasks.py:756-766](../../app/tasks/help_tasks.py#L756)).
- **enqueue endpoints** — if the broker is unreachable, `_enqueue` raises HTTP 503 `{code:"QUEUE_UNAVAILABLE"}` ([help.py:908-913](../../app/api/help.py#L908)).

### Feature flags

- This bulk-publish / bulk-AI surface is **not** behind a runtime feature flag in the read files (no env-gated `if not settings.X: 503` guard on these routes/tasks). The hard dependency is `GEMINI_API_KEY` being set, which the tasks check at AI-call time ([help_tasks.py:153-154](../../app/tasks/help_tasks.py#L153)). IMPLEMENTATION NOT FOUND: a `*_ENABLED` env flag gating these endpoints. (The dev-speak blacklist does reference `VITE_HELP_ASK_AI_ENABLED` / `SOP_DEADLINE_EMAIL_ENABLED` only as strings to forbid in generated copy — they do not gate this workflow, [help_tasks.py:483](../../app/tasks/help_tasks.py#L483).)

## Approvals — Permission Reality

Every endpoint calls `require_admin(user)` from [`app/security/roles.py`](../../app/security/roles.py) ([help.py:54](../../app/api/help.py#L54), [help.py:834](../../app/api/help.py#L834), [help.py:921/927/933/947](../../app/api/help.py#L921)). `require_admin` is invoked with **no `role` argument**, so `is_admin` falls through to the legacy email gate `user.email == LEGACY_ADMIN_EMAIL` where `LEGACY_ADMIN_EMAIL = "johndean@vin.com"` ([roles.py:54](../../app/security/roles.py#L54), [roles.py:88-92](../../app/security/roles.py#L88)). The `User` object carries only `email`; `get_current_user` never loads `auth_users.role` ([app/auth.py:37-38](../../app/auth.py#L37)). So in production the effective authorization for the entire Help admin surface = **JWT presence + the single hardcoded `johndean@vin.com` address**. NOT VERIFIED IN CODE: any active role-tier resolution. (The `roles.py` docstring still labels itself "scaffold only — not wired" — that is stale for this surface; these routes do call it, and it resolves to the email gate.)

## Source Verification
- **Files Used:** app/tasks/help_tasks.py, app/api/help.py, app/security/roles.py, app/auth.py, app/utils/help_compliance.py (imports only), migrations/004_audit.sql (column shape)
- **Components Used:** none (admin UI .vue not read; frontend router guard meta.adminOnly at frontend/src/router/index.ts:63 referenced from CLAUDE.md, not re-verified here)
- **APIs Used:** POST /v1/help/admin/bulk-publish, /admin/fix-summaries, /admin/expand-steps, /admin/expand-faqs, /admin/generate-faq-corpus; Celery tasks rounds.tasks.help.fix_summaries / expand_steps / expand_faqs / generate_faq_corpus
- **Database Tables Used:** help_articles, help_article_versions, audit_events
- **Permission Logic Used:** JWT + `require_admin(user)` resolving to the `LEGACY_ADMIN_EMAIL = "johndean@vin.com"` email gate (no role arg; `auth_users.role` not loaded)
- **Confidence Score:** High — endpoints and tasks fully traced; the only unverified items are the WS-completion broadcast (not in the read files) and any audit row on bulk-publish (none found).
- **Evidence Links:** [help.py:829-948](../../app/api/help.py#L829), [help_tasks.py:18-21](../../app/tasks/help_tasks.py#L18), [help_tasks.py:79-89](../../app/tasks/help_tasks.py#L79), [help_tasks.py:129-146](../../app/tasks/help_tasks.py#L129), [help_tasks.py:644-777](../../app/tasks/help_tasks.py#L644), [roles.py:54-92](../../app/security/roles.py#L54)
