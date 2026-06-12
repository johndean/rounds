"""
DB-backed integration test for the segment drag-drop reorder + undo round-trip.

tests/test_segment_reorder.py pins the pure `_reorder_changes` helper. THIS test
exercises the actual SQL against a real Postgres: the jsonb_to_recordset seq
rewrite and the snapshot-undo. It is the test that would have caught the
shipped 500 — "column seq is of type integer but expression is of type text":
the original bare-VALUES rewrite (untyped binds → text) throws here; the
declared-type jsonb_to_recordset version passes.

Runs in CI (the Quality workflow provisions Postgres + runs migrations before
pytest). Skips cleanly when no database is reachable locally, matching the
project's existing DB-test posture (see tests/test_chat_polls_reorder.py).
"""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth import User
from app.config import settings


async def _engine_or_skip():
    """A dedicated async engine (isolated from the app's module engine so we
    own its lifecycle across pytest-asyncio's per-test loop). Skips the test if
    no database answers."""
    eng = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with eng.connect() as conn:
            await conn.execute(sa.text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — no local DB → skip, don't fail
        await eng.dispose()
        pytest.skip(f"no database reachable for integration test: {exc}")
    return eng


async def test_reorder_and_undo_roundtrip(monkeypatch):
    from app.api.session_resources import (
        SegmentReorderRequest,
        reorder_segments,
        undo_bulk_reassign,
    )

    # The endpoint is flag-gated (default off); enable it for the test.
    monkeypatch.setattr(settings, "SEGMENT_REORDER_ENABLED", True, raising=False)

    eng = await _engine_or_skip()
    sm = async_sessionmaker(eng, expire_on_commit=False, autoflush=False)
    user = User(email="ci@vin.com")
    code = f"REORDER-IT-{uuid.uuid4().hex[:8]}"
    session_id = None
    try:
        # ── setup: one session + 5 segments with NON-contiguous seq. The gaps
        #    matter — they mirror the production session whose first drag hit the
        #    500, and they make undo's "restore the exact prior seq" assertion
        #    meaningful (a contiguous 0..N-1 restore would be indistinguishable
        #    from the rewrite). ──
        seqs = [1, 2, 9, 10, 11]
        async with sm() as db:
            session_id = (await db.execute(
                sa.text("INSERT INTO sessions (code, title) VALUES (:c, :t) RETURNING id"),
                {"c": code, "t": "reorder integration test"},
            )).scalar_one()
            ids = []
            for s in seqs:
                seg_id = (await db.execute(
                    sa.text(
                        "INSERT INTO segments (session_id, seq, start_ms, end_ms, text) "
                        "VALUES (:sid, :seq, :a, :b, :txt) RETURNING id"
                    ),
                    {"sid": session_id, "seq": s, "a": s * 1000, "b": s * 1000 + 500, "txt": f"seg {s}"},
                )).scalar_one()
                ids.append(str(seg_id))
            await db.commit()

        original_order = ids[:]                  # ascending seq == insertion order
        original_seqs = dict(zip(ids, seqs))     # id -> original (gapped) seq

        # ── reorder: full reverse so EVERY row's seq changes (max coverage of
        #    the rewrite SQL). ──
        new_order = list(reversed(original_order))
        async with sm() as db:
            resp = await reorder_segments(
                uuid.UUID(str(session_id)),
                SegmentReorderRequest(ordered_segment_ids=[uuid.UUID(x) for x in new_order]),
                db, user,
            )
        assert resp["kind"] == "reorder"
        assert resp["undoable"] is True
        assert resp["reordered"] == len(seqs)    # every row changed
        batch_id = resp["batch_id"]
        assert batch_id

        # ── verify: order matches the request, seqs are a clean 0..N-1. ──
        async with sm() as db:
            rows = (await db.execute(
                sa.text("SELECT id, seq FROM segments WHERE session_id = :sid ORDER BY seq"),
                {"sid": session_id},
            )).all()
        assert [str(r[0]) for r in rows] == new_order, "segments did not land in requested order"
        assert [r[1] for r in rows] == list(range(len(seqs))), "seq not rewritten to clean 0..N-1"

        # ── undo: restores the EXACT prior seq values, gaps and all. ──
        async with sm() as db:
            undo = await undo_bulk_reassign(
                uuid.UUID(str(session_id)), uuid.UUID(batch_id), db, user,
            )
        assert undo["restored"] == resp["reordered"]

        async with sm() as db:
            rows = (await db.execute(
                sa.text("SELECT id, seq FROM segments WHERE session_id = :sid ORDER BY seq"),
                {"sid": session_id},
            )).all()
        assert [str(r[0]) for r in rows] == original_order, "undo did not restore original order"
        assert {str(r[0]): r[1] for r in rows} == original_seqs, \
            "undo did not restore the exact prior seq values"
    finally:
        # session delete cascades to segments + bulk_reassign_batches (FKs are
        # ON DELETE CASCADE); audit_events is cleared explicitly.
        if session_id is not None:
            async with sm() as db:
                await db.execute(sa.text("DELETE FROM audit_events WHERE session_id = :sid"), {"sid": session_id})
                await db.execute(sa.text("DELETE FROM sessions WHERE id = :sid"), {"sid": session_id})
                await db.commit()
        await eng.dispose()
