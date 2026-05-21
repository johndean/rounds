# Plan — Units 5 & 6: Typed Stage Assignees + Session Auto-Init

**Status:** awaiting approval 2026-05-20
**Pre-reqs:** Units 1–4 shipped (commit TBD). DB has `is_default` on `session_types`, 17 seeded types, full `/v1/settings/{people,groups,types}/...` CRUD.
**Scope:** Close the last two gaps from the MIC parity audit — convert `stage_assignees` from `assignee_email TEXT` to typed FKs, then auto-populate per-session stage assignees from the chosen Type on upload.

---

## Unit 5 — Typed stage assignees (`person_id` / `group_id` FK)

### Why this matters

Today `stage_assignees.assignee_email` is a free-text column. The value can be a person's email (`carlab@vin.com`) or a synthetic group label (`Group: Content Team`). Two consequences:

1. **No referential integrity.** Deleting a person from `Settings → Team` leaves orphan rows in `stage_assignees` that still reference their old email. The Type matrix continues to show that ghost assignee until somebody overwrites the row.
2. **Group identity is positional.** Renaming "Content Team" → "Editorial Team" breaks every stage assignment that references it because the matrix stored the literal string `Group: Content Team`. MIC sidesteps this with `person_id` / `group_id` UUID FKs.

MIC's [`sop_type_stage_defaults`](https://github.com/.../mic/migrations/012_sop_types_and_type_stage_defaults.sql) constrains exactly one of `person_id` or `group_id` to be NOT NULL, and both are `ON DELETE SET NULL`. That's the target.

### Strategy — additive, no destructive migration

Option B from the audit: **keep `assignee_email TEXT` for backwards compat, add `person_id` + `group_id` nullable FKs in parallel.** Writes populate all three columns; reads prefer the typed FK and fall back to the email string. Deprecate `assignee_email` in a follow-up once every row has a typed FK and downstream consumers (exports, email templates, the Editor's stage strip) have migrated.

```sql
ALTER TABLE stage_assignees
  ADD COLUMN IF NOT EXISTS person_id UUID REFERENCES people(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS group_id  UUID REFERENCES groups(id) ON DELETE SET NULL;

-- Exactly one of person_id / group_id may be set; both NULL = unassigned.
ALTER TABLE stage_assignees
  ADD CONSTRAINT chk_stage_assignees_single_assignee
  CHECK ((person_id IS NULL) OR (group_id IS NULL));

-- Backfill the typed FKs from existing assignee_email strings.
-- Match person rows on lowered email (people.email is already canonicalised).
UPDATE stage_assignees sa
   SET person_id = p.id
  FROM people p
 WHERE sa.person_id IS NULL
   AND sa.group_id  IS NULL
   AND sa.assignee_email = p.email;

-- Match group rows on the "Group: <name>" prefix convention the frontend used.
UPDATE stage_assignees sa
   SET group_id = g.id
  FROM groups g
 WHERE sa.person_id IS NULL
   AND sa.group_id  IS NULL
   AND sa.assignee_email = 'Group: ' || g.name;
```

Unmatched rows (a deleted person, a typo, a hand-edited DB) keep `person_id` + `group_id` NULL and the text fallback wins on read.

### Write-path changes

`PUT /v1/settings/types/{id}/assignees` accepts the existing `StageAssigneeRow` shape:

```ts
{ stage: 'medical', assignee_email: 'carlab@vin.com', notify_email: true }
```

Backend resolves `assignee_email` to either `person_id` or `group_id` at write time:

```python
def _resolve_assignee(db, email: str) -> tuple[UUID | None, UUID | None]:
    if not email:
        return None, None
    if email.startswith("Group: "):
        row = db.execute(text("SELECT id FROM groups WHERE name = :n"), {"n": email[7:]}).first()
        return None, row[0] if row else None
    row = db.execute(text("SELECT id FROM people WHERE email = :e"), {"e": email.lower()}).first()
    return row[0] if row else None, None
```

INSERT stores all three columns. The text column stays for any consumer that hasn't migrated.

### Read-path changes

`GET /v1/settings/types/{id}/assignees` returns rows enriched with the joined display data:

```python
SELECT
    sa.id, sa.stage, sa.notify_email,
    -- Prefer typed FK display fields; fall back to the legacy email string.
    COALESCE(p.email, sa.assignee_email)                                 AS assignee_email,
    COALESCE(p.name,  CASE WHEN sa.assignee_email LIKE 'Group: %'
                           THEN sa.assignee_email ELSE NULL END,
             g.name)                                                     AS assignee_label,
    sa.person_id,
    sa.group_id
  FROM stage_assignees sa
  LEFT JOIN people p ON p.id = sa.person_id
  LEFT JOIN groups g ON g.id = sa.group_id
 WHERE sa.type_id = :t
 ORDER BY sa.stage;
```

The frontend already uses `assignee_email` for the picker value — no UI changes needed for the read path. `assignee_label` is the new display field that survives a rename.

### Risk

- **Medium**. Touches a hot read path (Type matrix render + every session ingest that reads stage assignees).
- **Mitigation 1**: write-path resolves at INSERT time, so reads only do the COALESCE — no per-request lookup.
- **Mitigation 2**: backfill is idempotent (`WHERE person_id IS NULL AND group_id IS NULL`).
- **Mitigation 3**: rollback is `DROP COLUMN person_id; DROP COLUMN group_id; DROP CONSTRAINT chk_stage_assignees_single_assignee` — additive only, no data loss.

### LOC estimate

| File | Change | LOC |
|---|---|---|
| `migrations/040_stage_assignees_typed_fk.sql` | `ALTER TABLE` + CHECK + backfill UPDATEs | ~35 |
| `app/api/settings.py` | `_resolve_assignee` helper + write-path resolver + read-path JOIN | ~50 |
| `frontend/src/services/api.ts` | Extend `StageAssigneeRow` with optional `person_id`/`group_id`/`assignee_label` | ~5 |

**Total: ~90 LOC, 1 migration.**

### Acceptance

1. Existing Type matrices render unchanged after deploy (read-path COALESCE preserves the email surface).
2. New stage assignments written via the matrix UI populate `person_id` or `group_id` in addition to `assignee_email`.
3. Deleting a person from `Settings → Team` now nulls their `person_id` references in `stage_assignees` and the matrix renders `(unassigned)` for those stages instead of a stale email.
4. Renaming a group propagates immediately to every Type matrix that referenced it (via the `g.name` join).

---

## Unit 6 — Per-session stage assignees auto-init from Type

### Why this matters

Today the Type matrix defines *what assignees a session should start with*, but no Rounds code actually reads it during ingest. Every session has the same blank stage state until a human manually wires assignees. MIC closes this loop two ways:

1. `sessions.session_type_id` FK (column added in migration 015) lets the operator (or auto-detect) pick a Type at upload time.
2. `sop_sessions` table holds per-session, mutable stage assignments seeded from `sop_type_stage_defaults` of the chosen Type.

Rounds needs both halves. The session→Type link is missing entirely, and there's no `session_stage_assignees` table.

### Schema additions

```sql
-- 041_session_type_link.sql
ALTER TABLE sessions
  ADD COLUMN IF NOT EXISTS session_type_id UUID REFERENCES session_types(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS sessions_session_type_id_idx ON sessions (session_type_id);

-- 042_session_stage_assignees.sql
CREATE TABLE IF NOT EXISTS session_stage_assignees (
    session_id     UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    stage          TEXT NOT NULL,
    person_id      UUID REFERENCES people(id) ON DELETE SET NULL,
    group_id       UUID REFERENCES groups(id) ON DELETE SET NULL,
    notify_email   BOOLEAN NOT NULL DEFAULT TRUE,
    source         TEXT NOT NULL DEFAULT 'manual',  -- 'default' | 'manual'
    assigned_by    TEXT,
    assigned_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, stage),
    CONSTRAINT chk_session_stage_assignees_single
      CHECK ((person_id IS NULL) OR (group_id IS NULL))
);
```

`PRIMARY KEY (session_id, stage)` enforces one assignee per stage per session. `source` distinguishes auto-populated defaults from operator overrides so the Editor can show "DEFAULT" vs "MANUAL" badges.

### Auto-init hook

The cleanest insertion point is the existing `gcs_upload.py` post-manifest path — the same place the manifest parse already runs. After parsing the manifest's `type:` field (or falling back to the default type), copy the Type's matrix rows into `session_stage_assignees`:

```python
# in app/services/session_init.py — new file
def init_session_stages(engine, session_id: str, session_type_id: str) -> int:
    """Copy stage_assignees rows for the given Type into the session's
    per-session stage_assignees table. Idempotent on (session_id, stage)."""
    with engine.begin() as conn:
        return conn.execute(text("""
            INSERT INTO session_stage_assignees
                (session_id, stage, person_id, group_id, notify_email, source)
            SELECT
                :sid, sa.stage, sa.person_id, sa.group_id, sa.notify_email, 'default'
              FROM stage_assignees sa
             WHERE sa.type_id = :tid
            ON CONFLICT (session_id, stage) DO NOTHING
        """), {"sid": session_id, "tid": session_type_id}).rowcount
```

Wired into `gcs_upload.py:upload_complete` right after the manifest parse + session_templates row is committed. Wrapped in try/except so a failure here logs a warning but doesn't block ingest — matches the poll auto-place hook's safety posture (commit `a409fdc`).

Manifest field resolution:
1. If manifest declares `type: AAFV` (or whatever code), look up that Type by `code` (case-insensitive).
2. Else use the org default Type (`is_default = TRUE`, guaranteed to exist by migration 038).
3. Set `sessions.session_type_id` accordingly.

### Read path / Editor wiring

A new endpoint `GET /v1/sessions/{id}/stage-assignees` returns the per-session matrix:

```python
SELECT
    ssa.stage, ssa.notify_email, ssa.source, ssa.assigned_at,
    p.id AS person_id, p.email, p.name,
    g.id AS group_id,  g.name AS group_name
  FROM session_stage_assignees ssa
  LEFT JOIN people p ON p.id = ssa.person_id
  LEFT JOIN groups g ON g.id = ssa.group_id
 WHERE ssa.session_id = :sid
 ORDER BY ssa.stage;
```

Editor's right-rail Admin tab + the SOP stepper render assignee chips from this. A future PATCH endpoint (out of scope for Unit 6 v1) lets the operator override per-stage.

### Backfill for existing sessions

```sql
-- 043_backfill_session_stage_assignees.sql
WITH default_type AS (SELECT id FROM session_types WHERE is_default = TRUE LIMIT 1)
INSERT INTO session_stage_assignees
    (session_id, stage, person_id, group_id, notify_email, source)
SELECT
    s.id, sa.stage, sa.person_id, sa.group_id, sa.notify_email, 'default'
  FROM sessions s
 CROSS JOIN stage_assignees sa
  JOIN default_type dt ON sa.type_id = COALESCE(s.session_type_id, dt.id)
 WHERE s.deleted_at IS NULL
   AND NOT EXISTS (
       SELECT 1 FROM session_stage_assignees ssa
        WHERE ssa.session_id = s.id AND ssa.stage = sa.stage
   );
```

Runs in api pre-deploy (`scripts/migrate.py`) so historical sessions populate their matrix at next deploy. Depends on Unit 5 having backfilled typed FKs.

### Risk

- **Medium**. New persistence layer + ingest path hook.
- **Mitigation 1**: hook is wrapped in try/except like `auto_place_polls` — failure logs WARNING, session still completes ingest.
- **Mitigation 2**: backfill is idempotent (`NOT EXISTS` guard).
- **Mitigation 3**: rollback is `DROP TABLE session_stage_assignees; ALTER TABLE sessions DROP COLUMN session_type_id` — no data loss in upstream tables.

### LOC estimate

| File | Change | LOC |
|---|---|---|
| `migrations/041_session_type_link.sql` | `ALTER TABLE sessions ADD COLUMN session_type_id` | ~10 |
| `migrations/042_session_stage_assignees.sql` | New table + CHECK + index | ~25 |
| `migrations/043_backfill_session_stage_assignees.sql` | Backfill historical sessions | ~25 |
| `app/services/session_init.py` (new) | `init_session_stages()` helper | ~40 |
| `app/api/gcs_upload.py` | Wire hook after manifest parse + Type lookup | ~30 |
| `app/api/sessions.py` (new endpoint) | `GET /v1/sessions/{id}/stage-assignees` | ~40 |
| `frontend/src/services/api.ts` | `sessionStageAssignees(id)` type + method | ~10 |
| `frontend/src/components/editor/AdminTab.vue` (or equivalent) | Render assignee chips from new endpoint | ~30 |

**Total: ~210 LOC, 3 migrations, 1 new service module.**

### Acceptance

1. New upload with manifest `type: AAFV` writes `sessions.session_type_id` to the AAFV Type's UUID.
2. `session_stage_assignees` for that session has 8 rows (one per stage) populated from the AAFV Type's matrix, all `source = 'default'`.
3. Renaming a group used by AAFV's matrix propagates to existing sessions' stage chips via the JOIN.
4. Deleting a person nulls their `person_id` in `session_stage_assignees` and the chip renders `(unassigned)`.
5. `/v1/diag/session-init/{id}` re-fires `init_session_stages()` for backfill/recovery.

---

## Sequencing

Ship in order: **Unit 5 first, then Unit 6**. Unit 6 depends on Unit 5's typed FK columns being present.

Each Unit is one commit, idempotent migrations, rollback-safe. Pre-deploy on Railway auto-applies each migration; both api and worker can run on the same SHA without coordination.

## What this plan deliberately does NOT do

- **No `assignee_email` removal.** It stays for back-compat until every read site has migrated.
- **No editor PATCH endpoint** for per-session stage overrides. Surface that in a follow-up (Unit 7).
- **No notification-on-entry email firing.** The `notify_email` flag is captured but unwiring it for actual email delivery is its own work item (SOP email templates already exist in `email_templates`; needs a Celery hook on stage transition).
- **No backfill of `sessions.session_type_id` from manifest re-parse.** Existing sessions' Type stays NULL unless an operator explicitly assigns one; their stage assignees default off the org's default Type via the JOIN.

## Open questions

1. Should manifest-declared Type be case-sensitive on `code` lookup? (Recommend case-insensitive with `LOWER()`.)
2. Should auto-init run even when the session has been manually edited? (Recommend no — `ON CONFLICT DO NOTHING` already protects.)
3. Should the Editor show a "Use Type defaults" reset button per stage? (Yes, but out of scope here — needs the PATCH endpoint.)
