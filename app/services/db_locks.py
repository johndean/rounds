"""
app/services/db_locks.py — Postgres advisory lock helpers (per-stage scope).

Plan ref: docs/plans/2026-06-05-010-zero-gap-parity-plan.md §Phase 1.5.
Audit IDs prep-closed: U7 (slide-extract race), TR2 (idempotent retries).
Formally closed in Phase 9b.

Why advisory locks (not table locks):
    Concurrent autosaves on the same segment + parallel ingest tasks on
    the same session both need serialization, but neither benefits from
    table-level locking (rebuilds the query planner state every time,
    contends with read traffic). Postgres pg_try_advisory_lock keys the
    lock on a (key1, key2) int pair and is RAM-cheap (~50µs acquire).

Lock-key derivation:
    The (session_id, stage_name) pair is hashed to two int32 values
    (deterministic, collision-cheap given the cardinality is small).
    Each call MUST use the same stage_name; otherwise sibling stages
    will collide pointlessly.

Lock SCOPE (per the perf reviewer):
    We use the SESSION-scoped lock (pg_try_advisory_lock) released
    explicitly at exit, NOT the transaction-scoped variant
    (pg_try_advisory_xact_lock). xact-scoped locks held across a long
    ai_process pipeline would serialize all concurrent re-ingests on
    the same session and neutralize the worker-concurrency win.

Usage:

    from app.db.locks import try_advisory_lock

    with try_advisory_lock(sync_conn, session_id="abc", stage="slide_extract") as acquired:
        if not acquired:
            return  # someone else is already running this stage
        do_work()
"""
from __future__ import annotations

import contextlib
import hashlib
from typing import Iterator


def _stage_keys(session_id: str, stage: str) -> tuple[int, int]:
    """
    Deterministically derive a (key1, key2) int32 pair from
    (session_id, stage). Postgres advisory locks take two int4 keys; we
    hash both fields together so a typo in stage name produces a
    different key (no accidental cross-stage collision).

    Returns signed int32s in (-2^31, 2^31-1). Postgres rejects values
    outside that range.
    """
    h = hashlib.blake2s(f"{session_id}|{stage}".encode("utf-8"), digest_size=8).digest()
    k1 = int.from_bytes(h[0:4], "big", signed=True)
    k2 = int.from_bytes(h[4:8], "big", signed=True)
    return k1, k2


@contextlib.contextmanager
def try_advisory_lock(conn, *, session_id: str, stage: str) -> Iterator[bool]:
    """
    Context manager around pg_try_advisory_lock / pg_advisory_unlock.

    Yields True if the lock was acquired, False if it was already held by
    another connection. Caller decides what to do on contention (skip,
    requeue, etc.). The lock is released in finally so a raised exception
    inside the with-block does NOT leak the lock.

    `conn` is a psycopg2-style connection (synchronous). For async usage
    in FastAPI handlers, use `try_advisory_lock_async` below.
    """
    k1, k2 = _stage_keys(session_id, stage)
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s, %s)", (k1, k2))
        acquired = bool(cur.fetchone()[0])
        try:
            yield acquired
        finally:
            if acquired:
                cur.execute("SELECT pg_advisory_unlock(%s, %s)", (k1, k2))


@contextlib.asynccontextmanager
async def try_advisory_lock_async(db, *, session_id: str, stage: str):
    """
    Async variant for SQLAlchemy AsyncSession (used inside FastAPI routes).

    `db` is an AsyncSession; uses sqlalchemy.text. Releases on exit; safe
    for use across awaits because the lock is bound to the underlying
    Postgres SESSION (the connection-pool connection), not the
    transaction.
    """
    from sqlalchemy import text as sql_text

    k1, k2 = _stage_keys(session_id, stage)
    acquired_row = (await db.execute(
        sql_text("SELECT pg_try_advisory_lock(:k1, :k2) AS got"),
        {"k1": k1, "k2": k2},
    )).mappings().first()
    acquired = bool(acquired_row["got"]) if acquired_row else False

    try:
        yield acquired
    finally:
        if acquired:
            await db.execute(
                sql_text("SELECT pg_advisory_unlock(:k1, :k2)"),
                {"k1": k1, "k2": k2},
            )
