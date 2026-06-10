# 2026-06-10-001 — Zero-Risk Gap Remediation

**Status:** Proposed
**Author:** johndean@vin.com (with Claude)
**Scope:** Clear the six data-layer findings from [`docs/gap-analysis.md`](../gap-analysis.md) §4 with **zero production risk**.

## Context

The documentation-factory run surfaced six schema/code findings. This plan
**verifies** each against source (done — see "Verified facts" per item) and
resolves it by the **lowest-risk means that actually closes the finding**.

Guiding rule: **migrations are forward-only and applied-by-slug** (ADR-011) — we
**never** edit an applied migration, never renumber, and never drop data that the
app writes. Five of six findings are therefore resolved by **documentation +
optional DB `COMMENT` metadata** (both zero-risk). The sixth (`session_locks` FK)
is a genuine structural omission; it is split into "document the accepted
behavior" (zero-risk) and an **optional** hardening migration (low-risk, gated).

## Risk tiers used below

- **Tier 0 (zero-risk):** Markdown edits, and `COMMENT ON` statements (metadata
  only — instant, no lock, no data/structure change, trivially reversible).
- **Tier 1 (low-risk, opt-in):** A forward migration that adds a constraint or
  drops a provably-empty table. Includes pre-checks + rollback. Requires explicit
  approval — **not** part of the zero-risk baseline.

---

## Track A — Documentation (Tier 0, clears 5 of 6)

All edits land in [`docs/data/data-dictionary.md`](../data/data-dictionary.md) and
[`docs/gap-analysis.md`](../gap-analysis.md) (flip §4 rows to "Resolved 2026-06-10").

### A1 — Migration `007` gap → **document, never renumber**
- **Verified:** no `007_*.sql`; sequence is 006 → 008. Renumbering would break the
  `schema_migrations` ledger (applied-by-slug). The gap is cosmetic.
- **Resolution:** one line in the data-dictionary "Migrations" note: *"`007` was
  never authored; numbering is non-contiguous by design — the ledger keys on slug,
  not ordinal."* No file change to migrations.

### A2 — Dead `006` `prompt_templates` / `email_templates` → **document supersession**
- **Verified:** `006` still **runs on a fresh DB**, then `047`/`048` DROP+CREATE
  the reshaped tables. Editing `006` would break bootstrap and the ledger.
- **Resolution:** data-dictionary note on both tables: *"Created in 006, reshaped
  (DROP+CREATE) by 047/048 — the 006 column set is transient on fresh bootstrap and
  superseded at rest. Read the 047/048 schema as authoritative."* Leave migrations
  untouched.

### A3 — Parallel tables → **disambiguate (all are live)**
- **Verified live in `app/`:** `correction_ledger` (22 refs) — the live edit
  ledger; `session_speakers` (7) — manifest-derived; `transcription_discrepancies`
  (12) — STT-diff. Their twins (`corrections` 002, `speakers` 001,
  `discrepancies` 002) serve distinct runtime roles.
- **Resolution:** a "Twin tables — which is which" subsection in the data-dictionary
  stating each table's owner/purpose and that **none is a duplicate to be dropped.**
  Verification step before publishing: `grep -rn "FROM corrections\b" app/` etc. to
  confirm the legacy twins still have at least one reader; tag any with zero readers
  as `VESTIGIAL (no code reader)` — **document only, do not drop.**

### A4 — `validation_results` ambiguity → **disambiguate (both are real)**
- **Verified both used:** a `validation_results` **table** keyed by `alignment_id`
  (`app/tasks/align.py:315`, `app/engines/pre_ready_gate.py`) **and** a
  `normalization_results.validation_results` **JSONB column**
  (`app/tasks/normalize.py:188/195`, `app/tasks/kp_task.py:235`).
- **Resolution:** data-dictionary note disambiguating the two by full path
  (`validation_results` table = alignment validation; `normalization_results.
  validation_results` column = IIL normalization validation). Naming collision only.

### A5 — `sop_approvals` orphan → **document as reserved/unused**
- **Verified:** **0** references in `app/api`, `app/tasks`, `app/services`. Created
  by `003` with `FK → sessions ON DELETE CASCADE`; never written, so it holds no
  data.
- **Resolution (Tier 0):** data-dictionary + gap-analysis entry: *"`sop_approvals`
  (003) is a reserved append-only signature table with no current reader/writer —
  `IMPLEMENTATION NOT FOUND`. Retained for the planned per-stage sign-off feature;
  empty in all environments."* (Optional physical drop → Track B2.)

---

## Track B — Optional DB metadata `COMMENT`s (Tier 0)

Embed the Track-A clarifications **in the database** so they survive outside the
repo. One forward migration, `058_schema_comments.sql`, containing only
`COMMENT ON TABLE/COLUMN` statements. Metadata-only ⇒ zero-risk, instant,
reversible (`COMMENT ... IS NULL`).

```sql
-- 058_schema_comments.sql — metadata only, no structural change.
COMMENT ON TABLE  sop_approvals IS 'RESERVED/UNUSED as of 2026-06-10: no app reader/writer. Planned per-stage sign-off. Empty in all envs.';
COMMENT ON TABLE  validation_results IS 'Alignment validation rows, keyed by alignment_id (app/tasks/align.py). NOT the normalization_results.validation_results JSONB column.';
COMMENT ON COLUMN normalization_results.validation_results IS 'IIL normalization validation (JSONB). Distinct from the validation_results TABLE.';
COMMENT ON TABLE  correction_ledger IS 'LIVE edit ledger (029). Twin of legacy corrections (002).';
COMMENT ON TABLE  session_speakers IS 'Manifest-derived speakers (011). Twin of runtime speakers (001).';
COMMENT ON TABLE  transcription_discrepancies IS 'STT-diff discrepancies (017). Twin of editor discrepancies (002).';
```

**Risk:** none (comments). **Rollback:** re-set the comments to `NULL`.

---

## Track C — `session_locks` FK (the only structural finding)

`session_locks.session_id` is a bare `UUID PRIMARY KEY` with **no** `REFERENCES
sessions(id)`, unlike every sibling (`sop_state`, `sop_transitions`, `sop_checks`,
`sop_approvals` all cascade). Two ways to "clear" it:

### C1 — Accept-with-rationale (Tier 0, recommended default)
Document why the omission is low-impact: lock rows are **ephemeral** (90s TTL,
swept), the app only ever writes a `session_id` that exists, and the worst case is
a stale lock row for a deleted session that ages out on its own. Add a
data-dictionary note: *"No FK by current design; rows are TTL-ephemeral. Hardening
tracked in Track C2."* This closes the finding at zero risk.

### C2 — Harden with an FK (Tier 1, opt-in, requires approval)
If we want the FK for real, the safe forward-only migration:

```sql
-- 059_session_locks_fk.sql — forward-only; pre-checked + non-blocking validate.
-- 1) Remove any orphan locks (safe: rows are ephemeral, TTL 90s).
DELETE FROM session_locks sl
 WHERE NOT EXISTS (SELECT 1 FROM sessions s WHERE s.id = sl.session_id);
-- 2) Add the FK as NOT VALID first (no full-table scan / no blocking lock).
ALTER TABLE session_locks
  ADD CONSTRAINT session_locks_session_id_fkey
  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE NOT VALID;
-- 3) Validate separately (takes only a SHARE UPDATE lock, not ACCESS EXCLUSIVE).
ALTER TABLE session_locks VALIDATE CONSTRAINT session_locks_session_id_fkey;
```

- **Pre-check (run first, expect 0):**
  `SELECT count(*) FROM session_locks sl WHERE NOT EXISTS (SELECT 1 FROM sessions s WHERE s.id = sl.session_id);`
- **Risk:** low. The `DELETE` only touches already-stale ephemeral rows; `NOT VALID`
  + separate `VALIDATE` avoids an `ACCESS EXCLUSIVE` table lock. `ON DELETE CASCADE`
  matches sibling tables.
- **Rollback:** `ALTER TABLE session_locks DROP CONSTRAINT session_locks_session_id_fkey;`
- **Not zero-risk** (it is a schema change), so it is explicitly opt-in.

### C3 — `sop_approvals` physical drop (Tier 1, opt-in, only if abandoned)
If product confirms the sign-off feature is abandoned (not merely unbuilt):
```sql
-- 060_drop_sop_approvals.sql
DROP TABLE IF EXISTS sop_approvals;
```
Risk minimal (table is provably empty — never written), but it is still a
destructive schema change. **Default recommendation: keep + COMMENT (A5/B), do not
drop.**

---

## Recommended execution order

1. **Track A** (A1–A5) — Markdown only. Clears 5 findings. Zero risk.
2. **Track B** — `058_schema_comments.sql`. Zero risk. Clears the same 5 in-DB.
3. **Track C1** — document `session_locks` acceptance. Zero risk; closes the 6th at
   the documentation level.
4. **Track C2 / C3** — **only on explicit approval.** These are the sole non-zero-
   risk items and are optional hardening, not required to clear the findings.

After Tracks A–C1, all six gap-analysis §4 rows flip to **Resolved (2026-06-10)**
with zero production risk.

## Verification

- **Docs:** `grep -rn "Resolved 2026-06-10" docs/` shows all six rows updated;
  re-run the §4 grep set (`sop_approvals`, `validation_results`, etc.) to confirm
  notes match code.
- **Track B:** `\d+ sop_approvals` (psql) shows the new table comment; no row-count
  or structural diff.
- **Track C2 (if run):** pre-check returns 0; after migrate,
  `SELECT conname FROM pg_constraint WHERE conrelid = 'session_locks'::regclass;`
  lists `session_locks_session_id_fkey`; app smoke test of acquire/heartbeat/release
  (`/v1/sessions/{id}/locks/*`) unaffected.
- **No app/test changes** are required by Tracks A, B, or C1.

## Files touched

- `docs/data/data-dictionary.md` (A1–A5, C1 notes)
- `docs/gap-analysis.md` (flip §4 rows to Resolved)
- `migrations/058_schema_comments.sql` (Track B — new, metadata only)
- `migrations/059_session_locks_fk.sql` (Track C2 — **only if approved**)
- `migrations/060_drop_sop_approvals.sql` (Track C3 — **only if approved**)
