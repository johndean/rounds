"""
tests/test_segment_split.py — Phase 3.5/4 split executor coverage.

Plan ref: docs/plans/2026-06-06-002-phase-3.5-split-merge-executor-v2.md §5.1.

The 14 tests below exercise app/services/segment_split.execute_split via
the public POST /v1/sessions/{sid}/corrections endpoint (correction_type
= "split"). Each test inserts minimal session + segment + word_alignment
fixtures, posts the request, and asserts both the HTTP envelope AND the
post-state of segments / word_alignment / key_points_annotations rows.

Conventions:
  • SPLIT_MERGE_ENABLED is force-set True via monkeypatch_settings fixture.
  • CurrentUser auth dep is overridden with a synthetic User so tests
    don't need to drive the login flow.
  • Each test cleans up its session via ON DELETE CASCADE on sessions(id).
  • Every test is `async def` and pytest-asyncio (mode=auto) drives it.

Requires a reachable Postgres on settings.DATABASE_URL with migrations
applied. Skipped at module level if the DB isn't reachable.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

# ─── Module-level guard: skip whole file if DB isn't reachable ───────────
_DB_AVAILABLE = True
try:
    from app.db import SessionLocal

    async def _probe() -> None:
        async with SessionLocal() as s:
            await s.execute(text("SELECT 1"))

    _loop = asyncio.new_event_loop()
    try:
        _loop.run_until_complete(_probe())
    finally:
        _loop.close()
except Exception:  # noqa: BLE001
    _DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _DB_AVAILABLE,
    reason="Postgres on DATABASE_URL is not reachable; skipping DB-integration tests.",
)


# ─── Helpers ─────────────────────────────────────────────────────────────
def _new_app_with_overrides():
    """Build the FastAPI app with auth + SPLIT_MERGE_ENABLED stubs.

    `_fake_user` is async because FastAPI dependencies awaited by the
    framework expect the coroutine protocol; the helper itself is sync.
    """
    from app import auth as auth_mod
    from app.config import settings as _settings
    from app.main import app

    # Force the flag on for the duration of the test.
    _settings.SPLIT_MERGE_ENABLED = True

    # Override CurrentUser dep so we don't need a JWT.
    async def _fake_user() -> auth_mod.User:  # noqa: S7503 (await req. by FastAPI)
        return auth_mod.User(email="test@vin.com")

    app.dependency_overrides[auth_mod.get_current_user] = _fake_user
    return app


def _auth_header() -> dict[str, str]:
    """A real Bearer token for an AUTH_USERS email. The dependency_overrides
    path proved unreliable here, so we exercise the genuine auth path instead:
    get_current_user decodes the JWT and, when auth_users has no row (this
    harness doesn't run lifespan, so the seed never fires), falls back to the
    AUTH_USERS env CSV — which contains this email. Robust in both local and CI
    (CI sets AUTH_USERS=ci@vin.com)."""
    from app.auth import _ENV_FALLBACK_DB, create_access_token
    email = next(iter(_ENV_FALLBACK_DB), "test@vin.com")
    return {"Authorization": f"Bearer {create_access_token(email).access_token}"}


def _hash(session_id: str, ms: int) -> str:
    """Match app/services/segment_split.py recipe: sha256(session_id||split_ms)."""
    payload = f"{session_id}{ms}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def _insert_session(db) -> str:
    sid = str(uuid.uuid4())
    code = f"TEST-{uuid.uuid4().hex[:8]}"
    await db.execute(
        text(
            """
            INSERT INTO sessions (id, code, title, status)
            VALUES (CAST(:sid AS uuid), :code, 'split-test session', 'ready')
            """
        ),
        {"sid": sid, "code": code},
    )
    await db.execute(
        text(
            """
            INSERT INTO ledger_pointers (session_id, current_pointer)
            VALUES (CAST(:sid AS uuid), -1)
            ON CONFLICT (session_id) DO NOTHING
            """
        ),
        {"sid": sid},
    )
    return sid


async def _insert_segment(
    db,
    session_id: str,
    *,
    text_value: str,
    seq: int = 0,
    start_ms: int = 0,
    end_ms: int = 4000,
    is_anchor: bool = False,
    anchor_kind: str | None = None,
    flags: list | None = None,
    metadata: dict | None = None,
    slide_id: str | None = None,
    speaker_id: str | None = None,
) -> str:
    seg_id = str(uuid.uuid4())
    content_hash = _hash(session_id, start_ms)
    await db.execute(
        text(
            """
            INSERT INTO segments (
                id, session_id, slide_id, speaker_id, seq,
                start_ms, end_ms, text, confidence,
                flags, is_anchor, anchor_kind,
                metadata, content_hash
            ) VALUES (
                CAST(:id AS uuid),
                CAST(:sid AS uuid),
                CAST(:slide AS uuid),
                CAST(:speaker AS uuid),
                :seq, :start_ms, :end_ms, :t, 0.9,
                CAST(:flags AS jsonb), :is_anchor, :anchor_kind,
                CAST(:meta AS jsonb), :content_hash
            )
            """
        ),
        {
            "id": seg_id,
            "sid": session_id,
            "slide": slide_id,
            "speaker": speaker_id,
            "seq": seq,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "t": text_value,
            "flags": json.dumps(flags if flags is not None else []),
            "is_anchor": is_anchor,
            "anchor_kind": anchor_kind,
            "meta": json.dumps(metadata if metadata is not None else {}),
            "content_hash": content_hash,
        },
    )
    return seg_id


async def _insert_word_alignment(
    db,
    segment_id: str,
    n_words: int,
    *,
    start_ms: int = 0,
    end_ms: int = 4000,
) -> None:
    if n_words <= 0:
        return
    span = max(end_ms - start_ms, n_words)  # avoid 0-width
    step = span // n_words
    for idx in range(n_words):
        ws = start_ms + idx * step
        we = ws + step
        await db.execute(
            text(
                """
                INSERT INTO word_alignment (
                    segment_id, gemini_idx, stt_word_id,
                    stt_start_ms, stt_end_ms, match_kind
                ) VALUES (
                    CAST(:seg AS uuid), :idx, NULL,
                    :ws, :we, 'exact'
                )
                """
            ),
            {"seg": segment_id, "idx": idx, "ws": ws, "we": we},
        )


async def _cleanup_session(db, session_id: str) -> None:
    """CASCADE wipes segments / word_alignment / correction_ledger / pointers."""
    await db.execute(
        text("DELETE FROM sessions WHERE id = CAST(:sid AS uuid)"),
        {"sid": session_id},
    )
    await db.commit()


async def _post_split(
    client: AsyncClient,
    session_id: str,
    segment_id: str,
    after_word_index: int,
    *,
    action_id: str | None = None,
) -> Any:
    body: dict[str, Any] = {
        "segment_id": segment_id,
        "correction_type": "split",
        "after_word_index": after_word_index,
    }
    if action_id:
        body["action_id"] = action_id
    return await client.post(
        f"/v1/sessions/{session_id}/corrections",
        json=body,
        headers=_auth_header(),
    )


# ─── Tests ───────────────────────────────────────────────────────────────


async def test_split_happy_path_4_word_after_1():
    """Test 1 — 4-word segment, after_word_index=1 → 2 segs, gemini_idx 0..1 / 0..1."""
    app = _new_app_with_overrides()
    async with SessionLocal() as db:
        sid = await _insert_session(db)
        seg_id = await _insert_segment(
            db, sid, text_value="one two three four", start_ms=0, end_ms=4000
        )
        await _insert_word_alignment(db, seg_id, 4, start_ms=0, end_ms=4000)
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await _post_split(client, sid, seg_id, after_word_index=1)
        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]  # unwrap MIC §9.1 envelope
        assert body["correction_type"] == "split"
        assert len(body["affected_segment_ids"]) == 2
        new_seg_ids = body["affected_segment_ids"]

        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    text(
                        "SELECT id::text AS id, text, start_ms, end_ms FROM segments "
                        "WHERE session_id = CAST(:sid AS uuid) ORDER BY start_ms"
                    ),
                    {"sid": sid},
                )
            ).mappings().all()
            assert len(rows) == 2
            left, right = rows[0], rows[1]
            assert left["text"] == "one two"
            assert right["text"] == "three four"

            # gemini_idx 0..1 on each
            left_wa = (
                await db.execute(
                    text(
                        "SELECT gemini_idx FROM word_alignment "
                        "WHERE segment_id = CAST(:s AS uuid) ORDER BY gemini_idx"
                    ),
                    {"s": left["id"]},
                )
            ).mappings().all()
            right_wa = (
                await db.execute(
                    text(
                        "SELECT gemini_idx FROM word_alignment "
                        "WHERE segment_id = CAST(:s AS uuid) ORDER BY gemini_idx"
                    ),
                    {"s": right["id"]},
                )
            ).mappings().all()
            assert [r["gemini_idx"] for r in left_wa] == [0, 1]
            assert [r["gemini_idx"] for r in right_wa] == [0, 1]
            assert set(new_seg_ids) == {left["id"], right["id"]}
    finally:
        async with SessionLocal() as db:
            await _cleanup_session(db, sid)


async def test_split_after_word_index_zero():
    """Test 2 — after_word_index=0 → left 1 word, right 3 words."""
    app = _new_app_with_overrides()
    async with SessionLocal() as db:
        sid = await _insert_session(db)
        seg_id = await _insert_segment(
            db, sid, text_value="alpha beta gamma delta", start_ms=0, end_ms=4000
        )
        await _insert_word_alignment(db, seg_id, 4, start_ms=0, end_ms=4000)
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await _post_split(client, sid, seg_id, after_word_index=0)
        assert resp.status_code == 200, resp.text

        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    text(
                        "SELECT id::text AS id, text FROM segments "
                        "WHERE session_id = CAST(:sid AS uuid) ORDER BY start_ms"
                    ),
                    {"sid": sid},
                )
            ).mappings().all()
            assert len(rows) == 2
            assert rows[0]["text"] == "alpha"
            assert rows[1]["text"] == "beta gamma delta"

            left_wa = (
                await db.execute(
                    text(
                        "SELECT gemini_idx FROM word_alignment "
                        "WHERE segment_id = CAST(:s AS uuid) ORDER BY gemini_idx"
                    ),
                    {"s": rows[0]["id"]},
                )
            ).mappings().all()
            right_wa = (
                await db.execute(
                    text(
                        "SELECT gemini_idx FROM word_alignment "
                        "WHERE segment_id = CAST(:s AS uuid) ORDER BY gemini_idx"
                    ),
                    {"s": rows[1]["id"]},
                )
            ).mappings().all()
            assert [r["gemini_idx"] for r in left_wa] == [0]
            assert [r["gemini_idx"] for r in right_wa] == [0, 1, 2]
    finally:
        async with SessionLocal() as db:
            await _cleanup_session(db, sid)


async def test_split_after_word_index_n_minus_1_rejected():
    """Test 3 — after_word_index = n-1 (would leave 0 words on right) → 400."""
    app = _new_app_with_overrides()
    async with SessionLocal() as db:
        sid = await _insert_session(db)
        seg_id = await _insert_segment(
            db, sid, text_value="one two three four", start_ms=0, end_ms=4000
        )
        await _insert_word_alignment(db, seg_id, 4, start_ms=0, end_ms=4000)
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # n=4 words, after_word_index=3 leaves right with 0 words.
            resp = await _post_split(client, sid, seg_id, after_word_index=3)
        assert resp.status_code == 400, resp.text
        assert resp.json()["error"]["details"]["code"] == "SPLIT_INVALID_WORD_INDEX"

        async with SessionLocal() as db:
            count = (
                await db.execute(
                    text(
                        "SELECT COUNT(*) AS c FROM segments "
                        "WHERE session_id = CAST(:sid AS uuid)"
                    ),
                    {"sid": sid},
                )
            ).mappings().first()
            assert count["c"] == 1  # no insert happened
    finally:
        async with SessionLocal() as db:
            await _cleanup_session(db, sid)


async def test_split_after_word_index_negative_rejected():
    """Test 4 — after_word_index < 0 → 400."""
    app = _new_app_with_overrides()
    async with SessionLocal() as db:
        sid = await _insert_session(db)
        seg_id = await _insert_segment(
            db, sid, text_value="one two three four", start_ms=0, end_ms=4000
        )
        await _insert_word_alignment(db, seg_id, 4, start_ms=0, end_ms=4000)
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await _post_split(client, sid, seg_id, after_word_index=-1)
        # FastAPI/Pydantic may also reject the body with 422; either is
        # acceptable so long as it's a client-error and no row was inserted.
        assert resp.status_code in (400, 422), resp.text
        if resp.status_code == 400:
            assert resp.json()["error"]["details"]["code"] == "SPLIT_INVALID_WORD_INDEX"

        async with SessionLocal() as db:
            count = (
                await db.execute(
                    text(
                        "SELECT COUNT(*) AS c FROM segments "
                        "WHERE session_id = CAST(:sid AS uuid)"
                    ),
                    {"sid": sid},
                )
            ).mappings().first()
            assert count["c"] == 1
    finally:
        async with SessionLocal() as db:
            await _cleanup_session(db, sid)


async def test_split_after_word_index_way_past_end_rejected():
    """Test 5 — after_word_index well past n_words-1 → 400 SPLIT_INVALID_WORD_INDEX.

    Differs from test 3 (which sits exactly at n-1, the boundary case);
    this one drives the same branch from far outside the valid range so
    a future implementation that splits the boundary check into two
    inequalities keeps both branches covered.
    """
    app = _new_app_with_overrides()
    async with SessionLocal() as db:
        sid = await _insert_session(db)
        seg_id = await _insert_segment(
            db, sid, text_value="one two three four", start_ms=0, end_ms=4000
        )
        await _insert_word_alignment(db, seg_id, 4, start_ms=0, end_ms=4000)
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await _post_split(client, sid, seg_id, after_word_index=99)
        assert resp.status_code == 400, resp.text
        assert resp.json()["error"]["details"]["code"] == "SPLIT_INVALID_WORD_INDEX"
    finally:
        async with SessionLocal() as db:
            await _cleanup_session(db, sid)


async def test_split_anchor_segment_rejected():
    """Test 6 — is_anchor=TRUE segment → 400 SPLIT_ANCHOR_SEGMENT."""
    app = _new_app_with_overrides()
    async with SessionLocal() as db:
        sid = await _insert_session(db)
        seg_id = await _insert_segment(
            db,
            sid,
            text_value="poll a b c",
            start_ms=0,
            end_ms=4000,
            is_anchor=True,
            anchor_kind="poll",
        )
        await _insert_word_alignment(db, seg_id, 4, start_ms=0, end_ms=4000)
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await _post_split(client, sid, seg_id, after_word_index=1)
        assert resp.status_code == 400, resp.text
        assert resp.json()["error"]["details"]["code"] == "SPLIT_ANCHOR_SEGMENT"

        async with SessionLocal() as db:
            count = (
                await db.execute(
                    text(
                        "SELECT COUNT(*) AS c FROM segments "
                        "WHERE session_id = CAST(:sid AS uuid)"
                    ),
                    {"sid": sid},
                )
            ).mappings().first()
            assert count["c"] == 1
    finally:
        async with SessionLocal() as db:
            await _cleanup_session(db, sid)


async def test_split_no_word_alignment_rejected():
    """Test 7 — segment with no word_alignment rows → 422 SPLIT_NO_WORD_ALIGNMENT."""
    app = _new_app_with_overrides()
    async with SessionLocal() as db:
        sid = await _insert_session(db)
        seg_id = await _insert_segment(
            db, sid, text_value="legacy text no alignment", start_ms=0, end_ms=4000
        )
        # Intentionally NO word_alignment rows.
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await _post_split(client, sid, seg_id, after_word_index=1)
        assert resp.status_code == 422, resp.text
        assert resp.json()["error"]["details"]["code"] == "SPLIT_NO_WORD_ALIGNMENT"
    finally:
        async with SessionLocal() as db:
            await _cleanup_session(db, sid)


async def test_split_key_points_annotations_cloned():
    """Test 8 — key_points_annotations row present → cloned to new segment."""
    app = _new_app_with_overrides()
    async with SessionLocal() as db:
        sid = await _insert_session(db)
        seg_id = await _insert_segment(
            db, sid, text_value="one two three four", start_ms=0, end_ms=4000
        )
        await _insert_word_alignment(db, seg_id, 4, start_ms=0, end_ms=4000)
        # Seed a kp row on the original segment.
        await db.execute(
            text(
                """
                INSERT INTO key_points_annotations (
                    id, session_id, segment_id, label, score, metadata,
                    key_points, explanation, available, extraction_confidence
                ) VALUES (
                    gen_random_uuid(), CAST(:sid AS uuid), CAST(:seg AS uuid),
                    'kp', 0.5, '{}'::jsonb,
                    CAST(:kps AS jsonb), 'because reasons', TRUE, 0.85
                )
                """
            ),
            {"sid": sid, "seg": seg_id, "kps": json.dumps(["a", "b", "c"])},
        )
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await _post_split(client, sid, seg_id, after_word_index=1)
        assert resp.status_code == 200, resp.text

        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    text(
                        """
                        SELECT segment_id::text AS sid_seg, key_points, explanation,
                               available, extraction_confidence
                          FROM key_points_annotations
                         WHERE session_id = CAST(:sid AS uuid)
                         ORDER BY segment_id
                        """
                    ),
                    {"sid": sid},
                )
            ).mappings().all()
            assert len(rows) == 2  # original kept, new clone inserted
            kps_arrays = [r["key_points"] for r in rows]
            # Both halves carry the SAME key_points array (kp_task will refine later).
            assert kps_arrays[0] == kps_arrays[1] == ["a", "b", "c"]
            # Same supporting fields on the clone.
            assert {r["explanation"] for r in rows} == {"because reasons"}
            assert all(r["available"] for r in rows)
            assert all(abs(r["extraction_confidence"] - 0.85) < 1e-6 for r in rows)
    finally:
        async with SessionLocal() as db:
            await _cleanup_session(db, sid)


async def test_split_flags_inherited():
    """Test 9 — flags JSONB inherited by new segment."""
    app = _new_app_with_overrides()
    async with SessionLocal() as db:
        sid = await _insert_session(db)
        seg_id = await _insert_segment(
            db,
            sid,
            text_value="one two three four",
            flags=["medication", "filler"],
        )
        await _insert_word_alignment(db, seg_id, 4)
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await _post_split(client, sid, seg_id, after_word_index=1)
        assert resp.status_code == 200, resp.text

        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    text(
                        "SELECT id::text AS id, flags FROM segments "
                        "WHERE session_id = CAST(:sid AS uuid) ORDER BY start_ms"
                    ),
                    {"sid": sid},
                )
            ).mappings().all()
            assert len(rows) == 2
            for r in rows:
                # JSONB comes back as list[str].
                assert sorted(r["flags"]) == ["filler", "medication"]
    finally:
        async with SessionLocal() as db:
            await _cleanup_session(db, sid)


async def test_split_metadata_has_split_breadcrumb():
    """Test 10 — new segment's metadata has split_from + split_at_ms breadcrumb."""
    app = _new_app_with_overrides()
    async with SessionLocal() as db:
        sid = await _insert_session(db)
        seg_id = await _insert_segment(
            db,
            sid,
            text_value="one two three four",
            start_ms=0,
            end_ms=4000,
            metadata={"kind": "ai", "origin": "ingest"},
        )
        await _insert_word_alignment(db, seg_id, 4, start_ms=0, end_ms=4000)
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await _post_split(client, sid, seg_id, after_word_index=1)
        assert resp.status_code == 200, resp.text

        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    text(
                        """
                        SELECT id::text AS id, metadata, start_ms
                          FROM segments
                         WHERE session_id = CAST(:sid AS uuid)
                         ORDER BY start_ms
                        """
                    ),
                    {"sid": sid},
                )
            ).mappings().all()
            assert len(rows) == 2
            # Original (start_ms = 0) — metadata unchanged.
            assert "split_from" not in rows[0]["metadata"]
            # New right half — breadcrumb present, inherited keys preserved.
            new_meta = rows[1]["metadata"]
            assert new_meta.get("split_from") == seg_id
            assert "split_at_ms" in new_meta
            assert isinstance(new_meta["split_at_ms"], int)
            # Inherited keys still present.
            assert new_meta.get("kind") == "ai"
            assert new_meta.get("origin") == "ingest"
    finally:
        async with SessionLocal() as db:
            await _cleanup_session(db, sid)


async def test_split_slide_and_speaker_inherited():
    """Test 11 — slide_id + speaker_id inherited by new segment."""
    app = _new_app_with_overrides()
    async with SessionLocal() as db:
        sid = await _insert_session(db)
        # Seed slide + speaker so the FKs resolve.
        slide_id = str(uuid.uuid4())
        speaker_id = str(uuid.uuid4())
        await db.execute(
            text(
                """
                INSERT INTO slides (id, session_id, slide_index)
                VALUES (CAST(:id AS uuid), CAST(:sid AS uuid), 0)
                """
            ),
            {"id": slide_id, "sid": sid},
        )
        await db.execute(
            text(
                """
                INSERT INTO speakers (id, session_id, name, role)
                VALUES (CAST(:id AS uuid), CAST(:sid AS uuid), 'Dr. Test', 'Instructor')
                """
            ),
            {"id": speaker_id, "sid": sid},
        )
        seg_id = await _insert_segment(
            db,
            sid,
            text_value="one two three four",
            slide_id=slide_id,
            speaker_id=speaker_id,
        )
        await _insert_word_alignment(db, seg_id, 4)
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await _post_split(client, sid, seg_id, after_word_index=1)
        assert resp.status_code == 200, resp.text

        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    text(
                        """
                        SELECT slide_id::text AS slide_id, speaker_id::text AS speaker_id
                          FROM segments
                         WHERE session_id = CAST(:sid AS uuid)
                         ORDER BY start_ms
                        """
                    ),
                    {"sid": sid},
                )
            ).mappings().all()
            assert len(rows) == 2
            for r in rows:
                assert r["slide_id"] == slide_id
                assert r["speaker_id"] == speaker_id
    finally:
        async with SessionLocal() as db:
            await _cleanup_session(db, sid)


async def test_split_content_hash_recomputed_for_new_segment():
    """Test 12 — new segment hash = sha256(session_id||split_ms); original unchanged."""
    app = _new_app_with_overrides()
    async with SessionLocal() as db:
        sid = await _insert_session(db)
        seg_id = await _insert_segment(
            db, sid, text_value="one two three four", start_ms=0, end_ms=4000
        )
        await _insert_word_alignment(db, seg_id, 4, start_ms=0, end_ms=4000)
        # Snapshot the original hash before splitting.
        orig_hash_before = (
            await db.execute(
                text(
                    "SELECT content_hash FROM segments WHERE id = CAST(:seg AS uuid)"
                ),
                {"seg": seg_id},
            )
        ).mappings().first()["content_hash"]
        await db.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await _post_split(client, sid, seg_id, after_word_index=1)
        assert resp.status_code == 200, resp.text

        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    text(
                        """
                        SELECT id::text AS id, content_hash, start_ms
                          FROM segments
                         WHERE session_id = CAST(:sid AS uuid)
                         ORDER BY start_ms
                        """
                    ),
                    {"sid": sid},
                )
            ).mappings().all()
            assert len(rows) == 2
            left, right = rows[0], rows[1]
            # Original (start_ms=0) hash unchanged.
            assert left["id"] == seg_id
            assert left["content_hash"] == orig_hash_before
            # New segment's hash = sha256(session_id || split_ms || new_seg_id)
            # hex. The H2 fix (2026-06-06) mixes the new row's UUID into the
            # recipe so a repeated split_ms can't collide on the UNIQUE
            # (session_id, content_hash) constraint (mig 020). split_ms equals
            # the new segment's start_ms.
            expected_new = hashlib.sha256(
                f"{sid}{right['start_ms']}{right['id']}".encode("utf-8")
            ).hexdigest()
            assert right["content_hash"] == expected_new
            assert right["content_hash"] != orig_hash_before
    finally:
        async with SessionLocal() as db:
            await _cleanup_session(db, sid)


async def test_split_idempotent_with_action_id():
    """Test 13 — duplicate action_id → idempotent (one new seg across 2 POSTs)."""
    app = _new_app_with_overrides()
    async with SessionLocal() as db:
        sid = await _insert_session(db)
        seg_id = await _insert_segment(
            db, sid, text_value="one two three four", start_ms=0, end_ms=4000
        )
        await _insert_word_alignment(db, seg_id, 4, start_ms=0, end_ms=4000)
        await db.commit()

    action_id = str(uuid.uuid4())
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r1 = await _post_split(
                client, sid, seg_id, after_word_index=1, action_id=action_id
            )
            assert r1.status_code == 200, r1.text
            r2 = await _post_split(
                client, sid, seg_id, after_word_index=1, action_id=action_id
            )
            assert r2.status_code == 200, r2.text
            assert r2.json()["data"].get("deduped") is True  # unwrap envelope

        async with SessionLocal() as db:
            # Still exactly 2 segments (1 original split into 2) — not 3.
            count = (
                await db.execute(
                    text(
                        "SELECT COUNT(*) AS c FROM segments "
                        "WHERE session_id = CAST(:sid AS uuid)"
                    ),
                    {"sid": sid},
                )
            ).mappings().first()
            assert count["c"] == 2
            # One ledger row for this action_id.
            ledger = (
                await db.execute(
                    text(
                        """
                        SELECT COUNT(*) AS c
                          FROM correction_ledger
                         WHERE session_id = CAST(:sid AS uuid)
                           AND action_id  = CAST(:aid AS uuid)
                        """
                    ),
                    {"sid": sid, "aid": action_id},
                )
            ).mappings().first()
            assert ledger["c"] == 1
    finally:
        async with SessionLocal() as db:
            await _cleanup_session(db, sid)


async def test_split_concurrent_same_session_returns_busy():
    """Test 14 — concurrent splits on same session → second returns 409 SPLIT_MERGE_BUSY."""
    app = _new_app_with_overrides()
    async with SessionLocal() as db:
        sid = await _insert_session(db)
        # Two independent segments in the same session so a second request
        # has its own valid target. The advisory lock is keyed on
        # (session_id, "split_merge") — it should block the second call
        # regardless of which segment is being split.
        seg1 = await _insert_segment(
            db,
            sid,
            text_value="one two three four",
            seq=0,
            start_ms=0,
            end_ms=4000,
        )
        await _insert_word_alignment(db, seg1, 4, start_ms=0, end_ms=4000)
        seg2 = await _insert_segment(
            db,
            sid,
            text_value="five six seven eight",
            seq=1,
            start_ms=5000,
            end_ms=9000,
        )
        await _insert_word_alignment(db, seg2, 4, start_ms=5000, end_ms=9000)
        await db.commit()

    # Hold the (session_id, "split_merge") advisory lock from outside the
    # request to deterministically force the dispatcher's
    # try_advisory_lock_async to return acquired=False -> 409.
    from app.services.db_locks import _stage_keys

    k1, k2 = _stage_keys(sid, "split_merge")
    holder = SessionLocal()
    holder_db = await holder.__aenter__()
    try:
        got = (
            await holder_db.execute(
                text("SELECT pg_try_advisory_lock(:k1, :k2) AS got"),
                {"k1": k1, "k2": k2},
            )
        ).mappings().first()
        assert got and got["got"] is True, "lock holder failed to acquire"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await _post_split(client, sid, seg2, after_word_index=1)
        assert resp.status_code == 409, resp.text
        assert resp.json()["error"]["details"]["code"] == "SPLIT_MERGE_BUSY"

        async with SessionLocal() as db:
            count = (
                await db.execute(
                    text(
                        "SELECT COUNT(*) AS c FROM segments "
                        "WHERE session_id = CAST(:sid AS uuid)"
                    ),
                    {"sid": sid},
                )
            ).mappings().first()
            assert count["c"] == 2  # no split occurred on the busy attempt
    finally:
        # Release the holder's advisory lock and clean up.
        try:
            await holder_db.execute(
                text("SELECT pg_advisory_unlock(:k1, :k2)"),
                {"k1": k1, "k2": k2},
            )
            await holder_db.commit()
        except Exception:  # noqa: BLE001
            pass
        await holder.__aexit__(None, None, None)
        async with SessionLocal() as db:
            await _cleanup_session(db, sid)
