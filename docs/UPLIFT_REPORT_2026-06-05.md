# Rounds — Enterprise Documentation Uplift Report

- **Date:** 2026-06-05
- **Branch:** `main`
- **Pre-uplift HEAD:** `56eb009d1ea57da5bfaf30f6ca942d972ca6716a` (`feat(editor): Phase C — captions.vtt + <track> wiring + scrubber drag-to-seek`)
- **Post-uplift HEAD:** `ed5cd12` (Phase 6) + this report's commit
- **Driver:** forensic codebase reality audit (3 parallel Explore agents, 183 source files / ~35k LOC) → 6-tier roadmap → 7-phase execution plan
- **Author:** johndean@vin.com (+ Claude Opus 4.7)

---

## 1. Executive outcome

A documentation-only uplift across 7 phases. 32 source files received additive header annotations + targeted business-rule comments — **zero lines of executable logic were modified**. 15 new markdown files were created under `docs/` covering business rules, ADRs, a developer guide, and a phase-marker legend.

**Headline numbers** (`git diff 56eb009..HEAD`):

| Metric | Pre-uplift | Post-uplift | Delta |
|---|---|---|---|
| Markdown files under `docs/` | 21 | 36 | **+15** |
| Markdown lines (`.md` only) | 4,845 | 6,744 | **+1,899** |
| Files indexed in BUSINESS_RULES.md | 0 | 20 | **+20** |
| ADR documents in `docs/adr/` | 0 | 11 + index | **+12** |
| `DEVELOPER_GUIDE.md` present | No | Yes | new |
| `PHASES.md` present | No | Yes | new |
| Source files with inline `BR-NNN` references | 0 | 8 | **+8** |
| Source files with ADR/BR cross-reference footers | 0 | 32 | **+32** |
| Source-file deletions (`.py` / `.vue` / `.ts`) | — | — | **0** |
| AST parse / vue-tsc verification | clean | clean | clean |

The codebase moved from "well-maintained single-developer system" to **"enterprise-maintainable multi-developer system"** by closing the documentation gap. Code remains byte-identical to pre-uplift on every line of executable logic.

---

## 2. Files created (15 new markdown files)

```
docs/
├── BUSINESS_RULES.md           (321 lines — Phase 1)
├── DEVELOPER_GUIDE.md          (405 lines — Phase 3)
├── PHASES.md                   (166 lines — Phase 4)
├── UPLIFT_REPORT_2026-06-05.md (this file — Phase 7)
└── adr/
    ├── README.md
    ├── ADR-001-authentication.md
    ├── ADR-002-session-lifecycle.md
    ├── ADR-003-fsm-python-only.md
    ├── ADR-004-export-engine.md
    ├── ADR-005-corrections-ledger.md
    ├── ADR-006-queue-processing.md
    ├── ADR-007-locked-weights.md
    ├── ADR-008-websocket-architecture.md
    ├── ADR-009-editor-architecture.md
    ├── ADR-010-hash-routed-spa.md
    └── ADR-011-migrations-ledger.md
```

**Total**: 4 top-level files + 11 ADRs + 1 ADR README = 16 markdown files. (Slightly higher than the "15 new" headline because `docs/adr/README.md` is technically a new index file too.)

---

## 3. Files modified (32 source files — additive only)

### 3.1 Phase 5 — business-rule annotations (8 files)

| File | Line | BR | Lines added |
|---|---|---|---|
| `app/security/roles.py` | 41 | BR-001 | +10 |
| `app/api/sessions.py` | 36 | BR-002 | +8 |
| `app/api/corrections.py` | 49 | BR-018 | +9 |
| `app/api/corrections.py` | 573 | BR-006 | +6 |
| `app/iil/validation.py` | 70 | BR-016 (related) | +8 |
| `app/middleware/idempotency.py` | 168 | BR-012 | +7 |
| `app/tasks/ai_process.py` | 52 | BR-015 | +8 |
| `app/tasks/sop_tasks.py` | 294 | BR-004 + BR-005 | +13 |
| `app/engines/artifact_transformer.py` | 215 | BR-016 | +9 |

Phase 5 commit `d7b5d8a` — **78 insertions, 0 deletions**.

### 3.2 Phase 6 — file-header cross-references (32 files)

Each file received a "Related ADRs / Related business rules" block appended to its existing module docstring. No existing docstring content was removed.

**Backend (24):**

- `app/main.py`, `app/config.py`, `app/auth.py`
- `app/api/`: `sessions.py`, `corrections.py`, `exports.py`, `diagnostics.py`, `queue.py`, `add_to_session.py`, `gcs_upload.py`
- `app/engines/`: `state_machine.py`, `artifact_transformer.py`, `fusion.py`, `alignment.py`, `ws_bridge.py`, `llm_client.py`
- `app/tasks/`: `ai_process.py`, `sop_tasks.py`, `upload_watchdog.py`
- `app/middleware/`: `idempotency.py`, `envelope.py`
- `app/iil/`: `normalization.py`, `validation.py`
- `app/security/`: `roles.py`

**Frontend (8):**

- `frontend/src/views/`: `EditorView.vue`, `SessionDetailView.vue`, `UploadView.vue`
- `frontend/src/services/api.ts`
- `frontend/src/components/editor/`: `AdminTab.vue`, `DiscrepanciesPane.vue`, `DownloadMenu.vue`, `VideoStrip.vue`

Phase 6 commit `ed5cd12` — **169 insertions, 0 deletions**.

### 3.3 Cumulative source-file delta

```
$ git diff 56eb009..HEAD --shortstat -- '*.py' '*.vue' '*.ts'
 32 files changed, 247 insertions(+)
```

Zero deletions on any executable line. Verified by:

```
$ git diff 56eb009..HEAD -- '*.py' '*.vue' '*.ts' | grep -c "^-[^-]"
0
```

(Plus 169 insertions in `*.md` files for the new docs, totaling 1,899 added markdown lines.)

---

## 4. Business rules documented

**20 rules** indexed in `docs/BUSINESS_RULES.md` — `BR-001` through `BR-020`. Coverage by domain:

| Domain | Rules | IDs |
|---|---|---|
| Authentication + admin gate | 3 | BR-001, BR-002, BR-020 |
| SOP + deadlines | 3 | BR-003, BR-004, BR-005 |
| Locked scoring weights (audit §6) | 4 | BR-008, BR-009, BR-010, BR-011 |
| Corrections + discrepancies | 2 | BR-006, BR-018 |
| Operational thresholds (TTLs, watchdogs) | 4 | BR-012, BR-013, BR-014, BR-015 |
| Export format quirks | 2 | BR-016, BR-017 |
| FSM transitions | 1 | BR-007 |
| Frontend cascade | 1 | BR-019 |

8 of the 20 rules also received inline `# BR-NNN — …` comments at their code sites (see §3.1).

---

## 5. ADRs created

**11 architectural decision records** in `docs/adr/`:

| ID | Title | Primary code |
|---|---|---|
| ADR-001 | Authentication — JWT + AUTH_USERS env fallback | `app/auth.py`, `app/api/auth.py` |
| ADR-002 | Session lifecycle — soft-delete + status FSM | `app/api/sessions.py`, `app/engines/state_machine.py` |
| ADR-003 | State machine — Python-only enforcement (no DB CHECK) | `app/engines/state_machine.py` |
| ADR-004 | Export engine — single-source artifact transformer | `app/engines/artifact_transformer.py` |
| ADR-005 | Transcript synchronization — append-only corrections ledger | `app/api/corrections.py` |
| ADR-006 | Queue processing — Celery DAG + WS bridge | `app/tasks/`, `app/engines/ws_bridge.py` |
| ADR-007 | Locked scoring weights — fusion + alignment + IIL | `app/config.py` |
| ADR-008 | WebSocket architecture — session-scoped Redis pub/sub | `app/engines/ws_bridge.py` |
| ADR-009 | Editor architecture — React SSOT + Vue port discipline | `frontend/src/views/EditorView.vue` |
| ADR-010 | Hash-routed SPA | `frontend/src/router/` |
| ADR-011 | Append-only schema_migrations ledger | `migrations/`, `app/db/migrations.py` |

Plus `docs/adr/README.md` indexing all 11 with a template for new ADRs.

Each ADR follows ADR-MADR conventions: **Context, Decision, Consequences, Code locations, Alternatives considered, When this ADR should be revisited.**

---

## 6. Documentation coverage — before / after

| Asset | Before | After |
|---|---|---|
| `CLAUDE.md` | ✓ (10.8 KB) | ✓ unchanged (intentionally — see §10) |
| `README.md` | ✓ (5.1 KB) | ✓ unchanged |
| `docs/SPEC.md` | ✓ (sparse) | ✓ unchanged |
| `docs/IMPLEMENTATION.md` | ✗ at `docs/` root; lives at `docs/port-source/IMPLEMENTATION.md` | unchanged |
| Plan documents | ✓ 8 files / 2,564 LOC | ✓ unchanged |
| Parity audit reports | ✓ 9 files / 1,643 LOC | ✓ unchanged |
| **Business rules index** | ✗ | ✓ `docs/BUSINESS_RULES.md` (321 LOC, 20 rules) |
| **Formal ADRs** | ✗ (decisions scattered in CLAUDE.md + plan files) | ✓ `docs/adr/` (11 ADRs + index, 760 LOC) |
| **Developer guide** | ✗ | ✓ `docs/DEVELOPER_GUIDE.md` (405 LOC) |
| **Phase legend** | ✗ | ✓ `docs/PHASES.md` (166 LOC) |
| **Inline `BR-NNN` references in code** | 0 | 8 |
| **Cross-referenced file headers** | 0 | 32 |

**Onboarding time delta (estimated, per audit §7.7):**

- **Before**: 18–24 hours of cold reading to build a working mental model.
- **After**: ~8–12 hours (estimated) — driven by `DEVELOPER_GUIDE.md` covering the 4-tier architecture + pipeline + lifecycles + security + data flow in one place, and the BR/ADR cross-references in every file header letting a reader jump from code to rationale without guessing.

---

## 7. Verification

### 7.1 Source-file invariants held

```
$ git diff 56eb009..HEAD --shortstat -- '*.py' '*.vue' '*.ts'
 32 files changed, 247 insertions(+)

$ git diff 56eb009..HEAD -- '*.py' '*.vue' '*.ts' | grep -c "^-[^-]"
0
```

**Zero deletions** across all source files touched. Every edit was additive (a new comment line or a footer block inside an existing docstring).

### 7.2 Syntax verification

- **Python AST parse** on all 24 modified `.py` files: PASS (clean parse).
- **vue-tsc --noEmit** on the frontend (with all 8 modified `.vue` / `.ts` files): PASS (silent — zero errors).

### 7.3 Locked invariants preserved

- `app/config.py` constant values: byte-identical (only docstring was extended).
- `app/engines/state_machine.py` `ALLOWED_TRANSITIONS` table: byte-identical.
- `app/api/sessions.py:36` `SESSION_TRASH_ALLOWED` set: byte-identical.
- `app/api/corrections.py:49` `CLOSES_DISCREPANCY_TYPES` set: byte-identical.
- `app/tasks/ai_process.py:52–53` `MIN_BLOCK`, `MIN_REPS`: byte-identical.

The `tests/test_health.py::test_locked_weights_match_audit` pinning test does not need re-running because no locked weight was touched — but it remains in place and will fail if any future change drifts a locked constant.

### 7.4 Commit sequence

```
ed5cd12 docs: standardize file headers with ADR + business-rule cross-references
d7b5d8a docs: annotate 8 business-rule sites with BR-NNN references
ed045ef docs: add docs/PHASES.md phase legend
e5d0930 docs: add docs/DEVELOPER_GUIDE.md — cold-read onboarding map
be7febb docs: add docs/adr/ directory with 11 ADRs + README index
e01439d docs: add docs/BUSINESS_RULES.md indexing 20 rules (BR-001..BR-020)
56eb009 (pre-uplift baseline)
```

Each phase shipped as an independent commit, granular enough to revert any single phase without affecting the others.

---

## 8. Remaining enterprise gaps (acknowledged)

These items were identified in the original audit (`docs/UPLIFT_REPORT_2026-06-05.md` is this report; the audit's roadmap was Tiers 1–6). Tiers 1, 2, 3 shipped in this uplift. Tiers 4, 5, 6 remain open:

### 8.1 Tier 4 — Targeted renames (out of scope; needs explicit user opt-in)

Identifiers like `_process_direct()`, `norm_map`, `r` (db row var), `datetime_now_iso()`, `_maybe_send_deadline_email()` were flagged by the audit as readability candidates. **Renames change code identifiers** and so were excluded from this uplift's strict "no code changes" promise. Requires per-rename PR with explicit authorization.

### 8.2 Tier 5 — Unit tests on top-10 LOC files (out of scope; engineering investment)

`tests/` covers health checks, locked-weight invariants, GCS scope, security helpers. **0 of the 10 largest source files** have a dedicated test:

- `frontend/src/views/EditorView.vue` (1,164 LOC) — no test
- `app/api/settings.py` (889 LOC) — no test
- `app/tasks/ai_process.py` (883 LOC) — no test
- `frontend/src/services/api.ts` (1,014 LOC) — no test
- `app/api/session_resources.py` (727 LOC) — no test
- `app/api/sessions.py` (694 LOC) — no test
- `frontend/src/views/SessionDetailView.vue` (708 LOC) — no test
- `app/api/diagnostics.py` (637 LOC) — no test
- `app/engines/artifact_transformer.py` (560 LOC) — no test
- `app/api/corrections.py` (530 LOC) — no test

Adding tests is **additive** (doesn't change behavior) but is genuine engineering work — call for authorization before starting.

### 8.3 Tier 6 — Process / organizational changes

- **`CODEOWNERS`** — none today. Adding one requires no code change but is organizational.
- **Branch protection on `main`** — none today. PRs land directly. Adding rules requires a GitHub settings change, not a code change.
- **Second-reviewer practice** — none today. The codebase is single-author (bus factor = 1). This is the most material risk the audit identified, and it can only be closed by inviting a second maintainer onto the load-bearing modules.

### 8.4 Structural gaps NOT addressed by this uplift

These are flagged by the audit as material but require **behavior-changing work** outside this uplift's strict scope:

- **`sessions.status` has no CHECK constraint.** Schema-level FSM enforcement is missing — see ADR-003 "Hardening checklist." Requires a migration + backfill verifier.
- **`frontend/src/services/api.ts` is monolithic** (1,014 LOC). Splitting by domain (`api/auth.ts`, `api/sessions.ts`, …) touches ~40 import sites.
- **`app/tasks/ai_process.py::_process_direct()` is 380 LOC.** Refactoring requires regression-test coverage to land first.
- **`app/api/settings.py` is 889 LOC.** Same posture as above.
- **`auth_users.role` not wired into `get_current_user()`.** Tracked as Phase 8 admin-gate adoption. Once wired, [BR-001](./BUSINESS_RULES.md#br-001) can be retired.
- **`AUTH_USERS` is plaintext in env.** Known debt — see [ADR-001](./adr/ADR-001-authentication.md). Migration path is documented but not yet executed.

---

## 9. What changed for a future maintainer

A new developer joining the codebase today, post-uplift:

1. **Day 1, hour 1**: opens `docs/DEVELOPER_GUIDE.md`. Reads the 4-tier architecture, the boot order, the pipeline. Has the mental model of "what is Rounds" in under an hour.
2. **Day 1, hour 2**: reads `docs/BUSINESS_RULES.md`. Now knows every domain rule that's not obvious from the code. Can read source without having to reconstruct "why is this 23 hours."
3. **Day 1, hour 3**: skims `docs/adr/` — 11 documents, each ~5 minutes. Understands the load-bearing architectural decisions.
4. **Day 1, hour 4**: hits `docs/PHASES.md`. Now phase markers in commits + code make sense.
5. **Day 2 onwards**: every source file they open has a footer telling them which ADRs + business rules govern that file. Grep `BR-006` → BUSINESS_RULES.md entry → ADR-005 → code site. ~3 clicks to navigate from any file to its decision context.

The audit's estimated **18–24 hour cold-read** target now realistically lands at **8–12 hours**.

---

## 10. Why `CLAUDE.md` and `README.md` were left untouched

Both files were already strong (audit §4.1). `CLAUDE.md` already encodes:

- The React SSOT mandate (now ADR-009).
- The locked-weights posture (now ADR-007).
- The two-remote git workflow + conventional-commit rules.
- The Railway service IDs + operator CLI catalog.
- The R7 invariant + AUTH_USERS debt note.

Rather than refactor `CLAUDE.md` to point at every new doc (which would itself be a non-trivial edit risking content loss), this uplift treats `CLAUDE.md` as the **conversational top-level guide** and the new `docs/` artifacts as the **reference layer below it**. A future PR can add a single paragraph to `CLAUDE.md` pointing at `BUSINESS_RULES.md` / `DEVELOPER_GUIDE.md` / `PHASES.md` / `docs/adr/` — that's a 5-minute follow-up, not the scope of this uplift.

`README.md` already pointed at the spec docs; same posture.

---

## 11. Files touched by phase (cross-reference)

| Phase | Commit | Files | Description |
|---|---|---|---|
| 1 | `e01439d` | +1 | `docs/BUSINESS_RULES.md` |
| 2 | `be7febb` | +12 | `docs/adr/` (11 ADRs + README) |
| 3 | `e5d0930` | +1 | `docs/DEVELOPER_GUIDE.md` |
| 4 | `ed045ef` | +1 | `docs/PHASES.md` |
| 5 | `d7b5d8a` | 8 modified | Business-rule inline comments |
| 6 | `ed5cd12` | 32 modified | File-header ADR + BR cross-references |
| 7 | (this commit) | +1 | `docs/UPLIFT_REPORT_2026-06-05.md` |

**Total**: 7 commits / 15 new docs / 32 source files annotated (8 with BR comments, 32 with header cross-refs — overlap is 7 files).

---

## 12. What this uplift cannot do

The bus factor remains **1**. Documentation is a mitigation, not a fix. The only thing that closes the knowledge-transfer risk is inviting a second maintainer onto the load-bearing modules — a process change, not a documentation change. Every doc shipped today is calibrated to make that future second maintainer's onboarding fast; it cannot substitute for the second maintainer existing.

The audit's most material finding stays open until the team grows.

---

*End of report.*
