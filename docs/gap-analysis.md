# Gap Analysis — Critical Validation Pass (rounds.vin)

Phase: the framework's **Critical Validation Pass + Gap Analysis Report**, run
against the actual rounds.vin codebase as of `HEAD` 2026-06-09. Every item below
is code-verified; nothing is inferred. Inspection/EHS framework categories that
do not apply to a transcript product are marked **N/A (domain mismatch)** rather
than padded.

> Companion to the documentation package generated in `docs/`, `help-center/`,
> and `ai-demo-knowledge/`. This is the honest "what's broken / missing / unwired"
> ledger.

---

## 1. Documentation discrepancies (HIGH — fix these first)

| # | Discrepancy | Reality (code) | Where the wrong claim appears |
|---|---|---|---|
| D1 | **Session lifecycle was mis-documented** (✅ corrected 2026-06-09). | Real FSM: `uploading → transcribing → normalizing → fusing → aligning → ready → complete` (+ `failed`; `failed`/`complete` terminal). `processing`/`published`/`archived` were never statuses; `ingesting` is a **legacy** alias normalized to `uploading` by migration 010 (still referenced by a dead frontend routing branch). [state_machine.py:40](../app/engines/state_machine.py#L40), [010_state_machine.sql:21](../migrations/010_state_machine.sql#L21) | **Source of the error:** `BUSINESS_RULES.md` BR-007 (wrong transition map + "failed escape-hatch"), `ADR-002`, `ADR-003`/`DEVELOPER_GUIDE.md` ("no CHECK"). Propagated into the two seed specs + product docs. **Not** CLAUDE.md (it is clean — only says reingest "resets status to 'uploading'"). All corrected this session. |
| D2 | **"Published" / "Archived" are not statuses.** | "Complete" is the terminal success state. "Archive" is a UI notion backed by `sessions.deleted_at` (soft-delete), not an FSM status. | Same files as D1; help-center copy mentions "archive". |
| D3 | **Route count.** | The API has ~20 routers / ~142 endpoints. | `CLAUDE.md` still says "32 routes live." (Already corrected in `docs/api/README.md`.) |
| D4 | **Permission framing drift.** | `require_admin`/`is_admin` ARE wired into endpoints now; only the *role-reading* half is scaffold. | `app/security/roles.py:10` docstring still says "not yet wired into any endpoint"; some lighter Phase-1 docs echo it. The authoritative `docs/security/permission-matrix.md` is correct. |

**Recommendation:** reconcile D1/D2 first — they are the highest-impact factual
errors and they propagate into help content and demo answers. A single
find-and-correct sweep across `CLAUDE.md` + the named seed specs resolves it.

---

## 2. Orphaned pages & unused routes

| Route | View | Finding |
|---|---|---|
| `#/queue` | `QueueView.vue` | **Orphaned.** No nav link anywhere in `AppHeader.vue`; reachable only by typing the URL. [AppHeader.vue:149-155](../frontend/src/components/AppHeader.vue#L149) |
| `#/gcs` | `GcsView.vue` | **Deep-link only.** No anchor; the nav's "Settings" link merely highlights when the path starts with `/gcs`. Operator/diagnostic surface. |
| `#/audit` | `AuditView.vue` | **Deep-link only.** Same pattern — `is-active` grouping under Settings, but no clickable link. |
| `#/admin/help` | `admin/HelpEditor.vue` | **Admin deep-link.** No nav link; guarded by `meta.adminOnly` ([router/index.ts:44](../frontend/src/router/index.ts#L44)). Expected for an admin tool, but undiscoverable via UI. |

Contextual routes (`#/s/:id`, `#/e/:id`, `#/e/:id/sop`, `#/e/:id/audit`,
`#/v/:id`, `#/p/:id`) are **not** orphaned — they are reached from session rows
and grouped under the "Sessions" nav active-state. No action needed.

---

## 3. Dead UI / unwired features

| Feature | State | Evidence |
|---|---|---|
| **Split / merge segment** | UI hidden + executor returns **503 `SPLIT_MERGE_DISABLED`** when flag off (default). | `app/config.py:134`; `AppHeader.vue:62` |
| **Ask AI (Help)** | Tab hidden unless `HELP_ASK_AI_ENABLED` (default off). | `app/config.py:121`; `AppHeader.vue:58` |
| **Upload watchdog** | Recovery Beat task default-off; no manual "resume" button exists. | `app/config.py:100` |
| **SOP deadline email** | Hourly scan runs but sends nothing unless `SOP_DEADLINE_EMAIL_ENABLED` (default off). | `app/config.py:110` |
| **Vertex AI classification** | Route exists; disabled by default. | `app/config.py:86` |
| **Video speed control** | Player is fixed at 1× — control not wired (`PARTIALLY IMPLEMENTED`). | `docs/product/video-sync.md` (player components) |

These are deliberate kill-switches, not bugs — but a demo or QA pass will see
"missing" UI. Document defaults; flip env vars to demo them.

---

## 4. Data-layer gaps (from the verified data dictionary) — ✅ Resolved 2026-06-10 (zero-risk)

| # | Finding | Evidence |
|---|---|---|
| G1 | **`sop_approvals` is orphaned** — table created, zero read/write references in `app/`. | migration 003; `IMPLEMENTATION NOT FOUND` |
| G2 | **`session_locks.session_id` has no FK to `sessions`** (PK only). | migration 057 |
| G3 | **Migration `007` does not exist** — sequence jumps 006 → 008. | migrations/ |
| G4 | **Dead legacy schemas** — `prompt_templates` & `email_templates` 006 definitions were DROP+CREATE-reshaped by 047/048; the 006 versions are dead. | migrations 006/047/048 |
| G5 | **Parallel tables (confusion risk)** — `corrections` (002) vs `correction_ledger` (029); `discrepancies` (002) vs `transcription_discrepancies` (017); `speakers` (001) vs `session_speakers` (011). | data-dictionary.md |
| G6 | **`validation_results` ambiguity** — exists as a table (014) AND a JSONB column on `normalization_results` (012); string matches not disambiguated. | data-dictionary.md |

> ✅ **Resolved 2026-06-10 (zero-risk, Tracks A+B+C1).** G3/G4/G5/G6 closed by
> documentation (see [data-dictionary "Migration numbering & resolved gaps"](data/data-dictionary.md)).
> G1 (`sop_approvals`) labeled RESERVED/UNUSED; G2 (`session_locks` FK)
> accepted-with-rationale (ephemeral, TTL-swept). DB-side mirror: migration
> [`058_schema_comments.sql`](../migrations/058_schema_comments.sql) (COMMENT-only,
> metadata, reversible). Optional structural hardening — FK add (C2), table drop
> (C3) — **deferred, not applied.** Plan:
> [2026-06-10-001-zero-risk-gap-remediation.md](plans/2026-06-10-001-zero-risk-gap-remediation.md).

---

## 5. RBAC gaps

- **No role tiers in the running system.** `auth_users.role` (migration 045) is
  stored but **never read** by `get_current_user`; the `User` object has no
  `role`. All admin power = `email == "johndean@vin.com"`. **PARTIALLY IMPLEMENTED.**
  [app/security/roles.py:62](../app/security/roles.py#L62)
- **Single point of admin.** Every admin-gated surface depends on one hardcoded
  email. Changing the operator requires a code/constant change (BR-001).
- **Client guard is advisory.** `#/admin/help` is gated client-side by email; the
  server re-checks on `/v1/help/articles*` mutations (correct), but other admin
  routes rely on the same single gate.

---

## 6. Framework categories that are N/A here (domain mismatch)

The originating framework assumes an inspection/EHS platform. These categories
have **no implementation** in rounds.vin and are not gaps — they are out of scope:

- Assignment **escalation** engine (regional/HSE/compliance escalation) — only
  flat SOP stage-assignees + SLA reminder emails exist. **N/A.**
- **Compliance rule engine** (mandatory inspections, photo/GPS validation,
  severity routing, compliance scoring) — **N/A.** The only "rules" are the
  domain business rules (BR-001..020) + locked scoring weights.
- **Inspection / Checklist / Observation / Corrective-Action** workflows — **N/A.**
- **Mobile workflow gaps** — there is **no mobile app**; single Vue SPA. **N/A.**
- **CMMS / ERP / GIS / mapping / camera / SMS** integrations — **N/A.** Real
  integrations: GCS, Google STT, Gemini, Vertex (off), SMTP, Railway.

---

## 7. Areas requiring human verification

- **D1/D2 blast radius:** confirm which exact files repeat the fictional status
  chain before the correction sweep (grep `ingesting|published|archived`).
- **`session_audit` vs `audit_events`:** two audit surfaces exist (`session_audit`
  processing_log written by the FSM; `audit_events` for edits). Confirm intended
  separation vs. consolidation.
- **`corrections` vs `correction_ledger` (G5):** confirm both are live by design
  (the 029 header says MIC-parity) vs. one being deprecated.
- **Orphaned `#/queue`:** confirm whether it is intentionally retired or should be
  re-linked (it duplicates dashboard "Your Queue").

---

## Source Verification
- **Files Used:** app/engines/state_machine.py, app/tasks/sop_tasks.py, frontend/src/components/AppHeader.vue, frontend/src/router/index.ts, app/security/roles.py, app/config.py, app/api/sessions.py; data-dictionary.md + workflow run flags for §4.
- **Components Used:** AppHeader.vue, QueueView.vue, GcsView.vue, AuditView.vue, admin/HelpEditor.vue
- **APIs Used:** routing config only
- **Database Tables Used:** sop_approvals, session_locks, prompt_templates, email_templates, corrections/correction_ledger, discrepancies/transcription_discrepancies, speakers/session_speakers, validation_results, normalization_results, auth_users
- **Permission Logic Used:** JWT + LEGACY_ADMIN_EMAIL gate; auth_users.role unread
- **Confidence Score:** High — §1–§5 traced to file:line read this session; §4 cross-checked against the prior data-dictionary run.
- **Evidence Links:** [state_machine.py:40](../app/engines/state_machine.py#L40), [router/index.ts:43](../frontend/src/router/index.ts#L43), [AppHeader.vue:149](../frontend/src/components/AppHeader.vue#L149), [config.py:134](../app/config.py#L134), [roles.py:62](../app/security/roles.py#L62)
