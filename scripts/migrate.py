#!/usr/bin/env python3
"""
Rounds migration runner. Ports MIC's scripts/migrate.py:32-80.

Globs `migrations/[0-9][0-9][0-9]_*.sql`, applies each in autocommit transaction
order. Excludes `migrations/schema.sql` if present (bootstrap).

Railway pre-deploy command: `python scripts/migrate.py`.
"""
from __future__ import annotations

import os
import sys
from glob import glob
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations"


def _normalize_dsn(dsn: str) -> str:
    """psycopg2 needs `postgresql://` — Railway / app code uses `postgresql+asyncpg://`."""
    return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL not set; aborting.", file=sys.stderr)
        return 2

    files = sorted(glob(str(MIGRATIONS_DIR / "[0-9][0-9][0-9]_*.sql")))
    if not files:
        print(f"No migrations found in {MIGRATIONS_DIR}; nothing to do.")
        return 0

    print(f"Applying {len(files)} migration(s) from {MIGRATIONS_DIR}:")
    conn = psycopg2.connect(_normalize_dsn(dsn))
    conn.set_session(autocommit=True)
    try:
        with conn.cursor() as cur:
            # Serialize concurrent migration runs via a Postgres session-level
            # advisory lock. Railway's pre-deploy command runs once per
            # service (api + worker share one railway.json), so every deploy
            # triggers TWO concurrent migrate.py processes against the same
            # database. Destructive DDL (DROP TABLE CASCADE in 047/048)
            # races between them and one side fails with no log output
            # (Railway-diagnosed root cause of deploy 2c0151eb).
            #
            # pg_advisory_lock blocks until the lock is free; the second
            # runner waits behind the first and then runs migrations
            # against the post-migrated schema (every statement is
            # IF EXISTS / IF NOT EXISTS / ON CONFLICT, so re-running is
            # a no-op for already-applied state).
            #
            # Lock key 0x524F554E = ASCII 'ROUN' (Rounds) — arbitrary but
            # collision-free with any other advisory locks in the app.
            _LOCK_KEY = 0x524F554E
            print(f"Acquiring advisory lock 0x{_LOCK_KEY:X} (serializes concurrent migration runs)...")
            cur.execute("SELECT pg_advisory_lock(%s)", (_LOCK_KEY,))
            print("Lock acquired.")
            try:
                for path in files:
                    name = Path(path).name
                    print(f"  → {name}")
                    with open(path, encoding="utf-8") as fh:
                        sql = fh.read()
                    try:
                        cur.execute(sql)
                    except Exception as exc:
                        print(f"    FAILED: {exc}", file=sys.stderr)
                        return 1
            finally:
                cur.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_KEY,))
                print("Lock released.")
    finally:
        conn.close()

    print("Migrations complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
