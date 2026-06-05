# Zero-Risk Plan — Closing the Remaining Enterprise Gaps

- **Date:** 2026-06-05
- **Author:** johndean@vin.com (+ Claude Opus 4.7)
- **Predecessor:** [`docs/UPLIFT_REPORT_2026-06-05.md`](../UPLIFT_REPORT_2026-06-05.md) §8 (acknowledged remaining gaps)
- **Constraint (locked):** every item in this plan must be **truly zero-risk** — additive only, no behavioral change, no semantic change, no schema change, no settings change that affects a running deploy. Anything that cannot meet that bar is moved to **§5 Phase X** with the gate that would unblock it.

---

## 1. Context — what we are closing, what we are not

The documentation uplift (PR `56eb009..ef48a31`) raised the codebase from "well-maintained single-developer system" to "enterprise-maintainable multi-developer system." It deliberately left 8 acknowledged gaps open because closing them would require behavior changes that fell outside that uplift's no-code-change promise.

This plan revisits those 8 gaps and asks: **for each, is there a zero-risk slice we can ship today, and what remains genuinely Phase-X?**

The 8 gaps:

1. Bus factor = 1
2. 0/10 largest files have tests (Tier 5)
3. Targeted renames (Tier 4)
4. CODEOWNERS / branch protection / second-reviewer (Tier 6)
5. `sessions.status` CHECK constraint
6. `frontend/src/services/api.ts` monolith split
7. `app/tasks/ai_process.py::_process_direct()` refactor
8. `AUTH_USERS` plaintext-in-env debt

The Phase 8 admin-gate adoption (`auth_users.role` wired into `get_current_user`) is acknowledged at the bottom of this plan but is **not** zero-risk and is logged in §5.

---

## 2. What "zero-risk" means in this plan

A change is zero-risk if and only if ALL of the following hold:

1. **No mutation of existing executable code paths.** Every Python expression, SQL clause, Vue template binding, and TypeScript expression remains byte-identical (except for additive comments / docstrings already shipped in the uplift).
2. **No new runtime branch.** A new file is fine only if nothing in the existing codebase imports or executes it.
3. **No deploy-time semantic change.** No env var renames, no Railway settings, no GitHub branch-protection rules that would block the single existing maintainer.
4. **No schema mutation.** No migrations. No data writes. Verifier scripts read only and run out-of-band.
5. **No CI/CD gate addition.** A new GitHub Action that fails on existing behavior is not zero-risk; one that only LOGS observations is.
6. **Reversible in seconds.** `git revert` of a single commit returns the codebase to the prior state with no residual effect.

A change that requires "we'll just be careful" is **not** zero-risk; it's careful-risk. Careful-risk goes to Phase X.

---

## 3. Per-gap analysis — what can land, what can't

For each gap: a) is there a zero-risk slice, b) what does it deliver, c) what would Phase X unlock.

### 3.1 Gap — Bus factor = 1

**Zero-risk slice available: YES** — narrowly.

The fundamental fix (invite a second maintainer) is organizational and out of scope for any code/docs plan. But there ARE zero-risk MITIGATIONS that close the *information-loss* axis of bus-factor risk:

- **`docs/RUNBOOK.md`** — operator playbook for every common production-incident shape. Inputs to write today:
  - The 13 `/v1/diag/*` operator routes (already enumerated in `CLAUDE.md` — promote to a dedicated runbook with step-by-step + when-to-use).
  - Railway-deploy recovery procedure (stuck deploy, failed migration, rollback).
  - Postgres recovery (lost connection, migration backfill, ID conflict).
  - Redis recovery (lost connection → WS bridge dead, idempotency cache reset).
  - GCS scope errors (R7 invariant failures, signed URL expiry).
  - Gemini quota / rate-limit / token-budget exhaustion.
- **`docs/HANDOVER.md`** — a "if I disappeared tomorrow" document covering:
  - Who pays for what (Railway, Google Cloud, GitHub).
  - Where the production secrets live (Railway dashboard sections).
  - The on-call story (today: nobody — single-maintainer; document the **absence**).
  - External integrations (carlab partner contact, any Slack/email aliases).
- **`docs/INCIDENT_HISTORY.md`** — append-only log of the few incidents that have shaped the codebase (upload-watchdog rationale, BR-002 carlab carve-out origin, Phase 8 admin-gate driver). Captures institutional memory before it ages out.

**What this DOES NOT do:** it does not solve bus factor; bus factor is bottlenecked on a human. It DOES bound the damage if that human disappears.

**Phase X (organizational):** invite a second maintainer onto load-bearing modules. Once present, retire the `LEGACY_ADMIN_EMAIL` single-email gate (BR-001) and enable branch protection (§3.4).

### 3.2 Gap — 0/10 largest files have tests (Tier 5)

**Zero-risk slice available: YES** — via **characterization tests**.

A characterization test is a test that asserts *the current behavior*, not the *correct* behavior. It exists to pin the system in place: "today, when I call X with Y, I get Z." If the test fails in the future, the developer who made the change is forced to look at the failure and decide: did I intentionally change Z, or is this a regression?

Characterization tests are zero-risk because:

- They do not modify any production code path.
- They fail only when behavior changes — they do not assert "correctness," only "stability."
- They live entirely in `tests/` and `frontend/tests/`.
- They are reversible (revert deletes them with no production effect).

**What to ship today (zero-risk):**

For each of the top-10 largest source files, write **1–3 characterization tests** that exercise the most load-bearing path. Examples:

| File | Characterization target |
|---|---|
| `app/api/sessions.py` | Snapshot the JSON shape of `GET /v1/sessions` with a fixture session. Pin the field set. |
| `app/api/corrections.py` | Snapshot the result of `apply_correction(text_edit)` against a known input. Pin the ledger row shape. |
| `app/api/exports.py` | Snapshot the output bytes of `to_txt` / `to_srt` against a fixture session. Hash-compare. |
| `app/api/diagnostics.py` | Snapshot the JSON shape of `GET /v1/diag/gcs` (read-only probe). |
| `app/api/settings.py` | Snapshot the JSON shape of `GET /v1/settings/auth_users` for an admin. |
| `app/api/session_resources.py` | Snapshot the response of `GET /v1/sessions/{id}/sources`. |
| `app/tasks/ai_process.py` | Pure-function tests for `_detect_repetition_loop`, schema-transform helpers (no Gemini calls). |
| `app/engines/artifact_transformer.py` | Snapshot `to_docx` byte-length range against a fixture; the docx is a zip so exact equality is brittle. |
| `frontend/src/views/EditorView.vue` | Playwright spec that asserts the editor mounts + renders the empty state without errors. |
| `frontend/src/services/api.ts` | TS type-shape unit tests via `import type` and sample values. |

**Important constraint:** these tests are run only on local + CI; they DO NOT extend the CI run-time budget by more than ~30 seconds (per-file budget) or they become careful-risk (a slow CI that times out blocks the maintainer).

**What Phase X unlocks:**

- Tests that ASSERT CORRECTNESS (not just stability). Requires deciding what "correct" means for each function — that's behavior-defining work, not characterization. Move to Phase X with the gate "characterization tests have shipped + 1 month of green CI baseline."
- Refactoring the 380-LOC `_process_direct()` (§3.7) becomes safe **after** its characterization suite is in place.

### 3.3 Gap — Targeted renames (Tier 4)

**Zero-risk slice available: NO.**

Renames change identifiers. Even pure renames carry risk:

- **Reflection / string lookups.** Python's `getattr`, SQLAlchemy's `Column(name=...)`, and FastAPI's pydantic `Field(alias=...)` can be reference-by-string. A grep miss breaks a route quietly.
- **Operator scripts external to the repo.** A Bash one-liner that hits `/v1/diag/<route>` would not break on a Python rename, but a script that depends on a logged function name (e.g. log-grep for `_process_direct`) would.
- **Audit logs.** `audit_events.kind` and `audit_events.summary` strings may reference function names (in error tracebacks, especially). A rename changes the message strings going forward, fragmenting historical search.
- **Git blame / archeology.** A rename + reformat can muddy blame across the rename commit; while `--follow` mitigates, it doesn't undo it.

These risks are **small but nonzero**. They violate the bar in §2.

**Zero-risk slice we CAN ship today:**

- **`docs/RENAME_REGISTRY.md`** — a document that lists every rename the audit flagged + the new name + a one-line rationale + the explicit risk classification. Maintainer authorizes a batch when ready; the doc is the source of truth for "the list."

**What Phase X unlocks:**

- Actually renaming. Requires: rename PR per identifier (or small batches), CI green, manual smoke of the renamed surface, audit-log grep to confirm no historical search breaks, explicit user authorization at PR time.

### 3.4 Gap — CODEOWNERS / branch protection / second-reviewer (Tier 6)

**Zero-risk slice available: PARTIAL.**

Split into two parts:

**Part A — `.github/CODEOWNERS` file (ZERO-RISK):**

A `CODEOWNERS` file is a hint to GitHub's UI. Without an accompanying branch-protection rule that REQUIRES the owner's review, it does nothing operationally. Adding the file is therefore:

- **Zero-risk to deploy** (GitHub never rejects a PR for missing owner review unless a protection rule says so).
- **Forward-compatible** — if branch protection is later enabled, the file is already in place.
- **Documentation value** — a reviewer landing on a PR sees which files have implied stewardship, which itself improves review quality.

The file can name the existing single maintainer for the load-bearing modules:

```
# .github/CODEOWNERS
app/config.py                       @johndean
app/engines/state_machine.py        @johndean
app/engines/fusion.py               @johndean
app/engines/alignment.py            @johndean
app/security/                       @johndean
migrations/                         @johndean
.github/workflows/                  @johndean
```

When a second maintainer joins, that entry updates from `@johndean` to `@johndean @secondperson` — a one-line change.

**Part B — Enabling branch protection on `main` (NOT zero-risk for a single-author repo):**

Branch protection that REQUIRES a reviewing approval blocks the existing single maintainer from landing their own commits. That's not zero-risk; it's a deliberate workflow change. Even self-approval is forbidden by default.

Workarounds (none zero-risk):

- "Allow administrators to bypass" — defeats the purpose; the bus factor is the admin.
- "Require status checks to pass but not approvals" — zero-risk and worth doing IF the CI green-build signal is reliable. **Today we don't have a CI gate worth pinning** beyond local checks; that itself is Phase X.

**Zero-risk slice today:**

- Ship `.github/CODEOWNERS` (Part A).
- Document Part B in this plan as a Phase X with the gate "second maintainer is named OR CI gates beyond locked-weights become reliable."

### 3.5 Gap — `sessions.status` CHECK constraint

**Zero-risk slice available: PARTIAL.**

Adding a CHECK constraint is a schema change. It would fail at migration time if any historical row has a value outside the allowed set. Even after verification it remains a behavior-changing migration (future writes that violate the constraint get rejected at the DB level — that IS the point, but it's a new failure mode).

**Zero-risk slice we CAN ship today:**

A **verifier script** that:

- Reads `sessions.status` from production (read-only).
- Reports any value not in `ALLOWED_TRANSITIONS.keys() ∪ {"published", "archived"}`.
- Logs the count of rows per status value.
- Lives at `scripts/verify_sessions_status.py`.
- Runs OUT-OF-BAND (not in CI, not in the deploy pipeline) so it has zero impact on a running system.

The script's output is the prerequisite for the Phase X migration: it confirms the historical row set is clean BEFORE a CHECK migration is even drafted.

**What Phase X unlocks:**

- The actual CHECK migration (`migrations/053_sessions_status_check.sql`). Gate: the verifier has run cleanly on production AND on every staging environment.

### 3.6 Gap — `api.ts` monolith split

**Zero-risk slice available: NO** (for the split itself); **YES** (for the planning artifact).

`frontend/src/services/api.ts` is 1,014 LOC and exports 32 named entities. Splitting it by domain (`api/auth.ts`, `api/sessions.ts`, `api/corrections.ts`, …) and updating ~40 import sites is a non-trivial mechanical change. Even mechanical changes risk:

- A missed import site → TypeScript error → build fails.
- A circular import that didn't exist before (a sub-module imports from another sub-module).
- Tree-shaking / chunk-splitting changes that subtly alter bundle composition.

**Zero-risk slice we CAN ship today:**

- **`docs/plans/api-ts-split-plan.md`** — the migration plan: which exports go into which file, what re-export shim `api.ts` becomes (a barrel file: `export * from './api/auth'; …`), what the per-import-site grep looks like, what TypeScript settings need a `paths` entry, what bundle-size delta we expect.

**What Phase X unlocks:**

- Executing the split. Gate: explicit user authorization + a single PR that does the split + an automated test that asserts every old import path still resolves through the barrel.

### 3.7 Gap — `_process_direct()` refactor

**Zero-risk slice available: NO** (for the refactor itself); **YES** (for characterization tests covered in §3.2).

`_process_direct()` is 380 LOC. Splitting it into smaller functions changes the call shape, the traceback shape, the test surface, and potentially the logging surface. Even a "behaviorally identical" split:

- Changes traceback paths → operator log greps shift.
- Changes the function names that appear in `audit_events` if they're stringified anywhere.
- Risks one of the inner extracted functions being called from somewhere unexpected later (because it's now a public-ish name).

**Zero-risk slice today:**

- Ship the characterization tests from §3.2 first — specifically for `_process_direct()` and its helpers. These tests act as **the contract** the refactor will preserve.

**What Phase X unlocks:**

- The refactor. Gate: characterization suite green for ≥1 month + explicit user authorization.

### 3.8 Gap — `AUTH_USERS` plaintext debt

**Zero-risk slice available: PARTIAL.**

The fundamental migration (hash passwords at rest; retire the env-CSV fallback) is a behavior change. But individual prep steps are zero-risk:

- **Migration draft** that ADDS a `password_hash` column to `auth_users` with `IF NOT EXISTS`. NOT applied. Lives at `migrations/053_auth_users_password_hash.sql` as a *draft file* — not applied by the migration runner because it's not in the registered list (or it's gated behind a feature flag in `app/db/migrations.py`).
- **Helper function** at `app/services/auth_users.py` that, GIVEN a plaintext password, can hash it — not wired into the login path, just available. Zero-risk because it's an unused export until something calls it.
- **`docs/plans/auth-users-hashing-plan.md`** — the dual-path migration plan (lazy hash at next login, eventual flip of the default).

**Where the risk actually starts:**

- The moment `get_current_user` consults `password_hash` first and falls back to plaintext, that's a behavior change for every login.
- The moment the env-CSV fallback is removed, that's a behavior change.

**What Phase X unlocks:**

- Apply the migration (gate: explicit user authorization).
- Wire the helper into the login path (gate: lazy-hash strategy approved + tested in staging).
- Retire the env fallback (gate: every user's hash populated AND a one-week soak period elapsed).

---

## 4. Zero-risk roadmap — what to ship

In recommended order. Each item is its own commit; each is independently revertible.

### Step 1 — Bus-factor mitigation docs (1 day)

- `docs/RUNBOOK.md` — operator playbook (covers the 13 `/v1/diag/*` routes, Railway recovery, Postgres / Redis / GCS / Gemini failures).
- `docs/HANDOVER.md` — "if I disappeared tomorrow" document.
- `docs/INCIDENT_HISTORY.md` — append-only incident log capturing institutional memory.

Risk: **zero** (pure docs).

### Step 2 — `.github/CODEOWNERS` (15 min)

- Add `.github/CODEOWNERS` with `@johndean` as the steward for the locked-weight files, security, migrations, and CI workflows.
- **DO NOT** enable branch protection (Phase X).

Risk: **zero** (no protection rule without an enforcement bind).

### Step 3 — Verifier scripts (1 day)

- `scripts/verify_sessions_status.py` — read-only audit of `sessions.status` values vs `ALLOWED_TRANSITIONS`.
- `scripts/verify_locked_weights.py` — already exists as `tests/test_health.py::test_locked_weights_match_audit`; cross-link from the runbook.
- `scripts/verify_auth_users_consistency.py` — read-only audit comparing `AUTH_USERS` env CSV against the `auth_users` table.

All three are out-of-band (not in CI, not in the deploy pipeline) — manual operator invocation only.

Risk: **zero** (read-only, out-of-band).

### Step 4 — Characterization test suite (3–5 days)

For each of the 10 largest files: 1–3 characterization tests pinning current behavior.

- `tests/test_sessions_api_characterization.py`
- `tests/test_corrections_api_characterization.py`
- `tests/test_exports_api_characterization.py`
- `tests/test_diagnostics_api_characterization.py`
- `tests/test_settings_api_characterization.py`
- `tests/test_session_resources_api_characterization.py`
- `tests/test_ai_process_helpers_characterization.py` (pure helpers only — no Gemini calls)
- `tests/test_artifact_transformer_characterization.py`
- `frontend/tests/editor-view-mount.spec.ts`
- `frontend/tests/api-ts-type-shapes.spec.ts`

CI run-time budget: each test under 30s; total addition under 5min.

Risk: **zero** (additive only; tests document current state).

### Step 5 — Rename + split + refactor plans (1 day)

- `docs/plans/2026-06-05-003-rename-registry.md` — the rename list (Tier 4) with rationale + risk classification per rename.
- `docs/plans/2026-06-05-004-api-ts-split-plan.md` — the api.ts barrel-file plan.
- `docs/plans/2026-06-05-005-process-direct-refactor-plan.md` — the `_process_direct()` decomposition plan (cites the characterization suite as the contract).

Risk: **zero** (planning docs only).

### Step 6 — AUTH_USERS hashing prep (1 day)

- `docs/plans/2026-06-05-006-auth-users-hashing-plan.md` — dual-path migration plan.
- `migrations/053_auth_users_password_hash.sql.draft` — DRAFT migration (note the `.draft` extension so it is not picked up by the applier).
- `app/services/auth_users.py::hash_password(plain) -> str` — additive helper. Not consumed by the login path.

Risk: **zero** (draft migration not registered; helper unused).

### Step 7 — Schema CHECK migration prep (0.5 day)

- `docs/plans/2026-06-05-007-sessions-status-check-plan.md` — references the verifier (§3.5), drafts the migration, lists the rollback procedure.
- `migrations/053_sessions_status_check.sql.draft` — DRAFT migration (not applied).

Risk: **zero** (draft migration not registered).

### Total estimated effort: ~6–8 days of focused work, all zero-risk.

---

## 5. Phase X — what stays out of scope until authorization is granted

Each Phase X item has a **gate** — the precondition that would unblock it.

| # | Phase X item | Gate that would unblock it | Predecessor in this plan |
|---|---|---|---|
| X1 | Invite a second maintainer onto load-bearing modules | Organizational decision + person | (Step 1 prepares the docs the new maintainer needs) |
| X2 | Enable branch protection on `main` with required reviewing approval | X1 must complete OR self-approval workflow accepted | (Step 2 prepares the CODEOWNERS file) |
| X3 | Execute targeted renames (per registry) | Explicit user authorization per batch + characterization suite green | Step 4 + Step 5 |
| X4 | Apply `sessions.status` CHECK migration | Verifier (Step 3) green on production + 1 week stable | Step 3 + Step 7 |
| X5 | Execute `api.ts` split | Characterization suite green + explicit user authorization | Step 4 + Step 5 |
| X6 | Refactor `_process_direct()` | Characterization suite green ≥1 month + explicit user authorization | Step 4 + Step 5 |
| X7 | Apply `auth_users.password_hash` migration | Plan reviewed + staging deploy successful | Step 6 |
| X8 | Wire `password_hash` into `get_current_user` | X7 complete + lazy-hash strategy tested | X7 |
| X9 | Retire `AUTH_USERS` env CSV fallback (BR-020) | X8 complete + every user has a hash + 1-week soak | X8 |
| X10 | Wire `auth_users.role` into `get_current_user` and retire `LEGACY_ADMIN_EMAIL` (BR-001) | Phase 8 admin-gate adoption plan executed | (independent — see Phase 8 plan) |
| X11 | CI gates beyond locked-weights (e.g. characterization tests must pass before merge) | Characterization suite green + 1 month observation | Step 4 |

Each Phase X item is **flagged with a clear gate** so a future plan can pick it up without ambiguity about prerequisites.

---

## 6. Order of operations

The 7 zero-risk steps in §4 are independent and can be done in any order. Recommended order optimizes for early value:

1. **Step 1** (docs) — closes the most material risk (bus factor information loss) with the lowest effort.
2. **Step 2** (CODEOWNERS) — 15 minutes; opportunistic.
3. **Step 4** (characterization tests) — slowest, but is a prerequisite for Phase X items X3 / X5 / X6.
4. **Step 3** (verifier scripts) — runs in parallel with Step 4.
5. **Step 5, 6, 7** (planning docs + drafts) — can land in one batch.

After all 7 steps land, the codebase is in a **defensible posture** where every Phase X item has a documented path forward.

---

## 7. Verification

Each step ships as its own commit. Per-step verification:

| Step | Verification |
|---|---|
| 1 | `git diff` confirms only `docs/*.md` additions. |
| 2 | `git diff` confirms only `.github/CODEOWNERS` addition. **Do not modify any branch protection rule.** |
| 3 | Each verifier runs locally against a fresh Postgres / staging DB; output captured in the runbook. |
| 4 | `python -m pytest tests/test_*_characterization.py` passes locally. CI green. |
| 5, 6, 7 | `git diff` confirms only `docs/plans/*.md` + `*.sql.draft` + unconsumed helper additions. |

After all steps: `git diff <pre-plan-sha>..HEAD --shortstat -- '*.py' '*.vue' '*.ts'` should show **zero deletions** on source files (consistent with the uplift's zero-risk posture).

---

## 8. What this plan deliberately does NOT promise

- **It does not close the bus factor.** It mitigates information loss. The fix is human.
- **It does not enable branch protection.** Even with CODEOWNERS in place, enabling protection that requires a reviewer blocks the single maintainer.
- **It does not execute any rename, split, refactor, or schema change.** All of those land in Phase X with explicit gates.
- **It does not wire `auth_users.role` or remove `LEGACY_ADMIN_EMAIL`.** Those are Phase 8 admin-gate-adoption work (tracked separately).
- **It does not add a CI gate that would block the existing maintainer.** Any new gate added in Phase X must clear that single-author bar.

---

## 9. Success criteria

This plan is successful when:

1. The 7 zero-risk steps from §4 have shipped (each as a commit).
2. The bus-factor docs (§3.1) exist and are linked from `CLAUDE.md`.
3. The CODEOWNERS file (§3.4) is in place.
4. Characterization tests (§3.2) cover the top-10 largest files and are green in CI.
5. Verifier scripts (§3.5, §3.8) run cleanly against production read-only.
6. Each Phase X item (§5) has a documented gate that any future maintainer can read.
7. **Zero lines of executable logic have been modified.** Verified by `git diff --shortstat` showing only additive changes on source files (excluding `tests/` which are themselves additive).

---

*End of plan.*
