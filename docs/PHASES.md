# Rounds — Phase Marker Legend

> **Why this exists.** The codebase carries 100+ inline `Phase X` markers across docstrings + comments. Some refer to the bootstrap port plan (Phase 1–10). Some refer to remediation sub-passes (Phase 6n / Phase 7i / Phase 8 step-3 / Phase 7-broader). Some refer to the editor zero-gap work (Phase A1–A7 / B1–B5 / C1–C3). Without a decoder, a maintainer reading `# Phase 7b — pre-ready gate` has no way to recover what "Phase 7b" means or when it shipped.
>
> This document is the **phase decoder**. Each row tells you what the initiative was, what was in scope, when it shipped, and where to find the plan document that drove it.
>
> **Status.** Created 2026-06-05 as Phase 4 of the documentation uplift. Indexes every phase marker observed in source as of HEAD `56eb009`.
>
> **Reading rule.** When you see a `Phase X` marker in code and want context: ctrl-F it here. If it isn't here, it was added after this document was last revised — please append it.

---

## Index of initiatives

| Initiative | Phase prefix | Time range | Status |
|---|---|---|---|
| [Bootstrap port](#bootstrap-port) | `Phase 1` – `Phase 10` | 2026-05-17 – 2026-05-22 | Shipped |
| [MIC parity audit remediation](#mic-parity-audit-remediation) | `Phase 6X` / `Phase 7X` / `parity-N` | 2026-05-19 – 2026-05-26 | Shipped |
| [SOP + queue + admin (2026-06-04 stakeholder pass)](#sop--queue--admin-2026-06-04-stakeholder-pass) | `Phase 7-broader-N` / `Phase 8 step-N` / `Phase 7.1`–`7.4` | 2026-06-04 – 2026-06-05 | Shipped |
| [Upload watchdog (Phase H')](#upload-watchdog-phase-h) | `Phase H'` | 2026-05-25 | Shipped (default off) |
| [Editor zero-gap remediation](#editor-zero-gap-remediation) | `Phase A1`–`A7` / `B1`–`B5` / `C1`–`C3` | 2026-06-05 | Shipped |

---

## Bootstrap port

**Plan document:** [`docs/plans/2026-05-17-001-feat-rounds-bootstrap-plan.md`](./plans/2026-05-17-001-feat-rounds-bootstrap-plan.md).

The 1:1 port from MIC. Each phase added a slice of the runtime: scaffolding → ingest pipeline → editor → SOP → exports.

| Phase | Goal | Status | Where to look |
|---|---|---|---|
| **Phase 1** | Scaffold — `/v1/health`, FastAPI app skeleton, dependency wiring | Shipped | `app/main.py:4` ("Phase 1 scaffold") |
| **Phase 2** | Auth + JWT + AUTH_USERS seed | Shipped | `app/auth.py`, `app/services/auth_users.py` |
| **Phase 3** | Sessions + soft-delete + state machine | Shipped | `app/api/sessions.py:249` ("Phase 3 — port from MIC") |
| **Phase 4** | Corrections ledger (append-only) | Shipped | `app/api/corrections.py:2` ("Phase 4"), `migrations/044_*.sql`, [ADR-005](./adr/ADR-005-corrections-ledger.md) |
| **Phase 5** | Key Points engine | Shipped | `app/iil/key_points.py:2` ("Phase 5 / MIC §25") |
| **Phase 6** | Ingest + transcribe + frame-sample + anchor + fusion + finalize pipeline | Shipped | `app/tasks/ingest.py`, `app/tasks/transcribe.py`, `app/tasks/fusion.py`, `app/tasks/finalize.py` |
| **Phase 7** | SOP control layer + WS bridge + envelope middleware + idempotency | Shipped | `app/tasks/sop_tasks.py:15` ("Phase 7g"), `app/middleware/envelope.py:17` ("Phase 7i / parity-3") |
| **Phase 8** | Audit + improvements + diagnostics surfaces | Shipped | `app/api/audit.py`, `app/api/improvements.py`, `app/api/diagnostics.py` |
| **Phase 9** | Speaker management + segment-level edits | Shipped | `app/api/session_resources.py:232` ("Phase 9: add a speaker") |
| **Phase 10** | Captions burn-in + template auto-detect classifier | Shipped (burn deferred per [project_rounds_no_caption_burn](../) — burn_captions code retained but not wired) | `app/tasks/ai_process.py:863` ("Phase 10.3"), `app/api/session_resources.py:74` ("Phase 10.1") |

### Phase 6 sub-marker glossary (bootstrap-internal)

The bootstrap plan broke Phase 6 into ~20 named sub-phases by implementation unit (U-numbers). Examples seen in source:

| Sub-marker | What | Source |
|---|---|---|
| `Phase 6e` | Anchor task | `app/tasks/anchor_task.py:3` |
| `Phase 6f` | Chat + extras parsing | `app/engines/chat_parser.py:13`, `app/services/extras2_parser.py:7` |
| `Phase 6g` | Normalize task | `app/tasks/normalize.py:16` |
| `Phase 6h` | Fusion task | `app/tasks/fusion.py:5` |
| `Phase 6i` | Align task | `app/tasks/align.py:4` |
| `Phase 6k` | Slide extract (PyMuPDF replacement for pdftoppm) | `app/tasks/slide_extract.py:4` |
| `Phase 6l` | Classify + LCS discrepancies | `app/tasks/classify_task.py`, `app/tasks/lcs_discrepancies.py` |
| `Phase 6n` | WS bridge | `app/engines/ws_bridge.py:10` |
| `Phase 6o` | Idempotency + rate-limit middlewares | `app/middleware/idempotency.py`, `app/middleware/rate_limit.py` |
| `Phase 6p` | Export engine + artifact transformer | `app/engines/artifact_transformer.py:8`, `app/api/exports.py:8` |
| `Phase 6q` | Key Points task | `app/tasks/kp_task.py:11` |

The `U`-numbers (U94, U105, etc.) in those comments are the **implementation-unit IDs** from the bootstrap plan document.

### Phase 7 sub-marker glossary

| Sub-marker | What | Source |
|---|---|---|
| `Phase 7a` | Segmenter engine | `app/engines/segmenter.py:15` |
| `Phase 7b` | Pre-ready gate (5 named gates) | `app/engines/pre_ready_gate.py:16` |
| `Phase 7c` | Normalize hardening (Tier 1/2) | `app/iil/normalization.py:22` |
| `Phase 7f` | Key Points engine feature extraction | `app/tasks/kp_task.py:184` |
| `Phase 7g` | SOP auto-init + deadline emails | `app/tasks/sop_tasks.py:15`, `app/tasks/finalize.py:100` |
| `Phase 7h` | Request-ID middleware + PDF re-extract per page | `app/middleware/request_id.py:6`, `app/tasks/slide_extract.py:39` |
| `Phase 7i` | Envelope middleware + alignment drift gaps + anchor phrase list | `app/middleware/envelope.py:17`, `app/engines/alignment.py:13`, `app/engines/anchor.py:10` |
| `Phase 7j` | Fusion verbatim re-port + validation invariants | `app/engines/fusion.py:19`, `app/iil/validation.py:35` |

---

## MIC parity audit remediation

**Plan documents:** [`docs/plans/2026-05-18-001-feat-full-mic-parity.md`](./plans/2026-05-18-001-feat-full-mic-parity.md), [`docs/plans/2026-05-18-002-parity-remediation-phases.md`](./plans/2026-05-18-002-parity-remediation-phases.md).

Sequential passes that closed numbered audit gaps. Each gap was color-coded by severity:

- 🔴 — blocker / data-loss / fundamental missing
- 🟠 — significant divergence
- 🟡 — quality-of-life / nice-to-have

The `parity-N` markers in code refer to these gap-closing passes:

| Pass | Scope | Source examples |
|---|---|---|
| `parity-1` | Bootstrap closes (audit gaps #1–#10) | (most are in the bootstrap-phase commits) |
| `parity-2` | Engine + task closes (gaps #11–#20) | `app/engines/artifact_transformer.py:8` ("closes 🟠 #11") |
| `parity-3` | Envelope + idempotency + alignment drift (gaps #19, #8, #9) | `app/middleware/envelope.py:17`, `app/middleware/idempotency.py:14`, `app/engines/alignment.py:13` |
| `parity-4` | Validation invariants (zero-gap) | `app/iil/validation.py:35` |

The audit gap numbers (#11, #14, #17, etc.) are positions in [`docs/plans/2026-05-18-001-feat-full-mic-parity.md`](./plans/2026-05-18-001-feat-full-mic-parity.md). Cross-referencing a marker like "closes 🔴 #5" is a one-grep operation.

---

## SOP + queue + admin (2026-06-04 stakeholder pass)

**Plan documents:** [`docs/audits/permissions-open-builder-2026-06-04.md`](./audits/permissions-open-builder-2026-06-04.md) and sibling `parity-audits/` baselines.

A multi-day remediation that closed concrete stakeholder asks from the 2026-06-04 audit. Sub-phases:

| Phase marker | Goal | Source |
|---|---|---|
| `Phase 7-broader-1` | Settings BUILD remediation (auth_users + email templates) | `app/api/email_templates.py:4` ("Phase 5 of the 2026-05-23 Settings BUILD remediation plan"), `app/api/diagnostics.py:569` ("Phase 2 of the 2026-05-23 Settings BUILD remediation plan") |
| `Phase 7-broader-2` | Queue visibility surface | `app/api/queue.py:9` |
| `Phase 7.1` | EmailBuilder extraction + per-type templates | `app/api/email_templates.py:396` |
| `Phase 7.2` | Deadline-specific template variants (migration 051) | `app/api/email_templates.py:122` |
| `Phase 7.3` | Roles helper byte-identical tightening | `app/security/roles.py:21` |
| `Phase 7.4` | Roles helper variant after fix | `app/api/email_templates.py:91` |
| `Phase 8` | Roles + permissions audit + admin gate scaffolding | `app/security/__init__.py:4`, `app/security/roles.py:8` (note: gate scaffolded but not yet wired everywhere — see [BR-001](./BUSINESS_RULES.md#br-001), [ADR-001](./adr/ADR-001-authentication.md)) |
| `Phase 8 step-3` | `require_admin` dependency + envelope error code `ADMIN_ONLY` (403) | `app/middleware/envelope.py:46`, `app/api/sessions.py:29` |

---

## Upload watchdog (Phase H')

**Plan document:** noted inline in `app/config.py:90` — *"See the plan in C:\\Users\\JohnDean\\.claude\\plans\\lets-start-a-new-streamed-creek.md"* (that plan file was used by an earlier iteration of this work).

A standalone safety pass. Recovers sessions stuck on `status='uploading'` after the silent `enqueue_ingest` failure path. Disabled by default ([BR-014](./BUSINESS_RULES.md#br-014)) — flip `UPLOAD_WATCHDOG_ENABLED=true` in Railway worker env to activate.

| Phase marker | Source |
|---|---|
| `Phase H' 2026-05-25` | `app/config.py:83–93`, `app/tasks/upload_watchdog.py` |

---

## Editor zero-gap remediation

**Plan document:** internal to this session (not in `docs/plans/`). Shipped 2026-06-05 across three commits:

- `2955e01` — Phase A batch (loading bar + keyboard shortcuts + flag filter)
- `168588e` — Phase B batch (chat/disc edit + Mark OK + drag-to-re-anchor)
- `56eb009` — Phase C batch (captions.vtt + `<track>` + scrubber drag-to-seek)

| Phase marker | What shipped | Source |
|---|---|---|
| `Phase A1` | Wire DownloadMenu to `/v1/sessions/{id}/exports/{format}` with Blob URL | `frontend/src/services/api.ts:385`, `frontend/src/components/editor/DownloadMenu.vue:6` |
| `Phase A2` | Keyboard shortcuts (Cmd+Z, Cmd+Y, Cmd+F) with input-focus guard | `frontend/src/views/EditorView.vue:870` |
| `Phase A4` | Filter visible segments when a flag chip is active | `frontend/src/views/EditorView.vue:683` |
| `Phase A5` | Operator rescue (`/v1/diag/*`) admin panel in AdminTab | `frontend/src/services/api.ts:1003`, `frontend/src/components/editor/AdminTab.vue:10` |
| `Phase A7` | Per-stage loading progress strip | `frontend/src/views/EditorView.vue:83`, `frontend/src/styles/app.css:831` |
| `Phase B1` | DiscrepanciesPane handlers (Mark OK, Dismiss, jump-to-segment) | `frontend/src/components/editor/DiscrepanciesPane.vue:53` |
| `Phase B2` | Inline chat edit (optimistic) | `frontend/src/views/EditorView.vue:590`, `frontend/src/components/editor/ChatTab.vue:34` |
| `Phase B5` | Drag-to-re-anchor inline chat/poll anchors | `frontend/src/components/editor/AnchorBlock.vue:56` |
| `Phase C1` | `captions.vtt` route with ETag + Cache-Control | `app/api/exports.py:8`, `app/api/exports.py:108` |
| `Phase C2` | `<track>` element wired via authenticated fetch + Blob URL | `frontend/src/services/api.ts:420`, `frontend/src/components/editor/VideoStrip.vue:59` |
| `Phase C3` | Pointer-based scrubber drag-to-seek with `requestAnimationFrame` throttle | `frontend/src/components/editor/VideoStrip.vue:92` |

---

## Adding a new phase marker

When a new initiative is started:

1. Pick a fresh prefix that does not collide with the table above (`D1`–`D7`, `Phase 9-broader-N`, etc.).
2. Document the initiative here under a new section before merging the first commit that uses the prefix.
3. Inside the commit's docstring / comment, use the prefix consistently: `Phase D2 — <one-line goal>`.
4. When the initiative ships, mark its row "Shipped" in this document.

Markers without an entry here will surface in the next audit pass as undecodable phase markers.
