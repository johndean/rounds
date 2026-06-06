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

Lock SCOPE (two helpers, two scopes):
    - `try_advisory_lock` (SYNC, ingest workers): SESSION-scoped
      (pg_try_advisory_lock) released explicitly at exit. Used by the
      long-running ai_process / slide_extract Celery tasks — these hold
      the lock across many statements without a single commit boundary,
      so xact-scope would either neutralize the worker-concurrency win
      or release prematurely at the first internal commit.
    - `try_advisory_lock_async` (ASYNC, FastAPI handlers): TRANSACTION-
      scoped (pg_try_advisory_xact_lock), auto-released at COMMIT or
      ROLLBACK. The correction-ledger handlers (split/merge apply, undo,
      redo) acquire → short DB work → commit → exit; xact-scope is the
      right fit because SQLAlchemy's async pool returns the connection
      after commit, which makes explicit pg_advisory_unlock unsafe (it
      runs on a different pooled connection, silently returns false,
      leaks the original lock until pool_recycle). See the
      `try_advisory_lock_async` docstring for the full rationale.

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

    `db` is an AsyncSession; uses sqlalchemy.text. The lock is acquired
    with the TRANSACTION-scoped variant (pg_try_advisory_xact_lock) and
    auto-releases when the surrounding transaction COMMITs or ROLLBACKs.
    There is NO explicit unlock in finally — that would be a no-op (the
    lock is already gone) and, worse, would run on whatever connection
    the AsyncSession lazily checks out next (post-commit the connection
    has been returned to the pool).

    Why xact_lock and not session_lock here:
        The FastAPI correction handlers (split/merge apply, undo, redo)
        follow the pattern: acquire → short DB work → commit → exit.
        With the session-scoped variant, COMMIT returns the underlying
        connection to the SQLAlchemy pool *while the advisory lock is
        still held on that backend*. The unlock-in-finally then ran on a
        potentially different connection, silently returned false, and
        the original lock leaked until pool_recycle (30 min) or
        connection close — effectively bypassing serialization for
        subsequent requests that landed on the still-locked backend
        (because session-scoped locks are reentrant within the same
        backend). pg_try_advisory_xact_lock auto-releases at COMMIT, so
        the connection returns to the pool clean.

    Caller contract:
        - The caller MUST `await db.commit()` (or let an exception
          trigger ROLLBACK) inside the `async with` block — the lock
          lives only as long as the open transaction.
        - Do NOT use this helper to hold a lock across multiple
          transactions or across an async boundary that begins a new
          transaction; for that, see the sync `try_advisory_lock` (long-
          running ingest pipeline) or refactor to acquire xact_lock per
          stage.

    Yields True if the lock was acquired, False if it was already held
    (by any other connection, transaction- or session-scoped — both
    variants contend on the same Postgres advisory-lock namespace).
    Caller decides what to do on contention (typically 409).
    """
    from sqlalchemy import text as sql_text

    k1, k2 = _stage_keys(session_id, stage)
    acquired_row = (await db.execute(
        sql_text("SELECT pg_try_advisory_xact_lock(:k1, :k2) AS got"),
        {"k1": k1, "k2": k2},
    )).mappings().first()
    acquired = bool(acquired_row["got"]) if acquired_row else False

    # No try/finally with pg_advisory_unlock: the xact-scoped lock auto-
    # releases on COMMIT or ROLLBACK of the surrounding transaction. An
    # explicit unlock here would either no-op (lock already released) or
    # run on the wrong pooled connection (see docstring).
    yield acquired
