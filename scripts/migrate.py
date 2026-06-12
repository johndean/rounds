#!/usr/bin/env python3
"""
Rounds migration runner. Ports MIC's scripts/migrate.py:32-80; adds a
schema_migrations ledger as of 2026-06-05.

Globs ``migrations/[0-9][0-9][0-9]_*.sql``, applies each that has not
yet been recorded in the ``schema_migrations`` ledger. Excludes
``migrations/schema.sql`` if present (bootstrap-only).

**Why the ledger** (2026-06-05): the original no-ledger runner re-ran
every numbered .sql file on every deploy under an advisory lock and
relied on each statement being idempotent (``IF EXISTS`` /
``IF NOT EXISTS`` / ``ON CONFLICT``). That assumption broke for
``048_email_templates.sql``, which begins with
``DROP TABLE IF EXISTS email_templates CASCADE`` and re-seeds the
table — so every deploy silently destroyed operator-edited email
templates. The ledger ensures each migration applies exactly once.

**Bootstrap path** for the FIRST run of this ledger-aware script
against an already-migrated production DB: if any non-``schema_migrations``
table exists in the ``public`` schema AND the ledger is empty, mark every
existing migration file as already-applied. This prevents 048's DROP
from firing again on prod, where the post-migration state is already
correct. Fresh dev DBs (no other tables) run every file from scratch
and the ledger records each as it lands.

Railway pre-deploy command: ``python scripts/migrate.py``.
"""
from __future__ import annotations

import os
import re
import sys
from glob import glob
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations"

# Advisory lock serializes concurrent migrate.py processes (Railway runs
# the pre-deploy command once per service; api + worker share one
# railway.json, so two concurrent runs hit the same DB). 0x524F554E =
# ASCII 'ROUN'. The lock is held for the entire run.
_LOCK_KEY = 0x524F554E


def _normalize_dsn(dsn: str) -> str:
    """psycopg2 needs ``postgresql://`` — Railway / app code uses ``postgresql+asyncpg://``."""
    return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


def _ensure_ledger(cur) -> None:
    """Create ``schema_migrations`` if it doesn't exist."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name        TEXT        PRIMARY KEY,
            applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def _bootstrap_from_existing_db(cur, files: list[str]) -> int:
    """
    First-run bootstrap for an already-migrated DB.

    If the ledger is empty AND the public schema contains tables OTHER
    than schema_migrations (i.e. prior no-ledger runs already applied
    everything), record every current migration filename as
    already-applied so subsequent runs skip them.

    Returns the count of files marked as bootstrapped (0 on a fresh DB).
    """
    cur.execute("SELECT count(*) FROM schema_migrations")
    ledger_rows = cur.fetchone()[0]
    if ledger_rows > 0:
        return 0

    cur.execute(
        """
        SELECT count(*) FROM information_schema.tables
         WHERE table_schema = 'public'
           AND table_name  != 'schema_migrations'
        """
    )
    other_tables = cur.fetchone()[0]
    if other_tables == 0:
        return 0

    names = [Path(p).name for p in files]
    cur.executemany(
        "INSERT INTO schema_migrations (name) VALUES (%s) ON CONFLICT DO NOTHING",
        [(n,) for n in names],
    )
    # Operator-visible log: the bootstrap assumes the existing DB is
    # ALREADY fully migrated through the most recent file in
    # migrations/. On prod (fully-migrated through 051 as of
    # 2026-06-05), that assumption holds. On partially-migrated dev /
    # staging DBs, it silently marks unapplied files as applied —
    # operator must spot-check the list. Default behavior is preserved
    # for the prod cutover; a future Phase could replace this with
    # per-migration sentinel detection.
    print(
        f"Bootstrap detail: ledger populated with {len(names)} file(s). "
        f"Marked-applied list (verify against your DB state if non-prod):"
    )
    for n in names:
        print(f"    - {n}")
    return len(names)


def _strip_sql_comments(sql: str) -> str:
    """Remove ``--`` line comments and ``/* */`` block comments. Only used to
    scan for keywords (e.g. CONCURRENTLY) — NOT for execution."""
    no_block = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", "", no_block)


def _needs_no_transaction(sql: str) -> bool:
    """True if the migration must run OUTSIDE a transaction. CREATE/DROP INDEX
    CONCURRENTLY is the only such statement Postgres has; it raises "cannot run
    inside a transaction block" otherwise. The connection is autocommit, but a
    multi-statement execute() is sent as one simple query, which Postgres wraps
    in an IMPLICIT transaction — so such files must be executed one statement at
    a time. (This is the fresh-DB failure that kept CI's pytest job from ever
    running; prod was unaffected because 052 was already in the ledger.)"""
    return "CONCURRENTLY" in _strip_sql_comments(sql).upper()


def _split_statements(sql: str) -> list[str]:
    """Split SQL into top-level statements on semicolons, respecting line/block
    comments, single/double-quoted strings, and dollar-quoted bodies ($$...$$ /
    $tag$...$tag$). Used only for the no-transaction path so each statement is
    sent to Postgres separately (no implicit multi-statement transaction)."""
    stmts: list[str] = []
    buf: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        two = sql[i:i + 2]
        if two == "--":                                   # line comment
            j = sql.find("\n", i)
            i = n if j == -1 else j + 1
            continue
        if two == "/*":                                   # block comment
            j = sql.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        if ch in ("'", '"'):                              # quoted string
            buf.append(ch)
            i += 1
            while i < n:
                buf.append(sql[i])
                if sql[i] == ch:
                    if i + 1 < n and sql[i + 1] == ch:    # doubled-quote escape
                        buf.append(sql[i + 1])
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        if ch == "$":                                     # dollar-quoted body
            m = re.match(r"\$[A-Za-z0-9_]*\$", sql[i:])
            if m:
                tag = m.group(0)
                end = sql.find(tag, i + len(tag))
                if end == -1:
                    buf.append(sql[i:])
                    i = n
                else:
                    buf.append(sql[i:end + len(tag)])
                    i = end + len(tag)
                continue
        if ch == ";":                                     # statement boundary
            stmt = "".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def _apply_one(cur, path: str) -> bool:
    """Apply a single migration if not yet recorded. Returns True if
    applied, False if skipped."""
    name = Path(path).name
    cur.execute("SELECT 1 FROM schema_migrations WHERE name = %s", (name,))
    if cur.fetchone():
        print(f"  ✓ {name} (already applied)")
        return False
    print(f"  → {name}")
    with open(path, encoding="utf-8") as fh:
        sql = fh.read()
    if _needs_no_transaction(sql):
        # Run statement-by-statement so CONCURRENTLY isn't trapped in the
        # implicit transaction a multi-statement simple query creates. The
        # connection is autocommit, so each statement commits on its own. These
        # files are expected to be idempotent (IF [NOT] EXISTS) since a mid-file
        # failure can't roll back the statements already committed.
        for stmt in _split_statements(sql):
            cur.execute(stmt)
    else:
        cur.execute(sql)
    cur.execute(
        "INSERT INTO schema_migrations (name) VALUES (%s) ON CONFLICT DO NOTHING",
        (name,),
    )
    return True


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL not set; aborting.", file=sys.stderr)
        return 2

    files = sorted(glob(str(MIGRATIONS_DIR / "[0-9][0-9][0-9]_*.sql")))
    if not files:
        print(f"No migrations found in {MIGRATIONS_DIR}; nothing to do.")
        return 0

    print(f"Found {len(files)} migration file(s) in {MIGRATIONS_DIR}")
    conn = psycopg2.connect(_normalize_dsn(dsn))
    conn.set_session(autocommit=True)
    applied = 0
    skipped = 0
    try:
        with conn.cursor() as cur:
            print(f"Acquiring advisory lock 0x{_LOCK_KEY:X} (serializes concurrent migration runs)...")
            cur.execute("SELECT pg_advisory_lock(%s)", (_LOCK_KEY,))
            print("Lock acquired.")
            try:
                _ensure_ledger(cur)
                bootstrapped = _bootstrap_from_existing_db(cur, files)
                if bootstrapped:
                    print(
                        f"Bootstrap: existing tables detected with empty ledger; "
                        f"marked {bootstrapped} migration file(s) as already-applied. "
                        f"(This run will be a no-op except for ledger population.)"
                    )
                for path in files:
                    try:
                        if _apply_one(cur, path):
                            applied += 1
                        else:
                            skipped += 1
                    except Exception as exc:
                        print(f"    FAILED: {exc}", file=sys.stderr)
                        return 1
            finally:
                cur.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_KEY,))
                print("Lock released.")
    finally:
        conn.close()

    print(f"Migrations complete: {applied} applied, {skipped} skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
