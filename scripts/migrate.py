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
        conn.close()

    print("Migrations complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
