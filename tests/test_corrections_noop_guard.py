"""
Phase 1.5 — anti-no-op guard on the corrections append path.

Plan ref: docs/plans/2026-06-05-010-zero-gap-parity-plan.md §Phase 1.5.
Audit IDs prep-closed: protects E24 (autosave) from silently destroying
redo history when a blur fires without an actual edit.
"""
from __future__ import annotations

import uuid


def _req(**kw):
    from app.api.corrections import CorrectionRequest
    base = {
        "segment_id":      uuid.uuid4(),
        "correction_type": "text_edit",
        "old_text":        "hello world",
        "new_text":        "hello world",
    }
    base.update(kw)
    return CorrectionRequest(**base)


def test_text_edit_unchanged_is_noop():
    from app.api.corrections import _is_noop_correction
    assert _is_noop_correction(_req()) is True


def test_text_edit_changed_is_not_noop():
    from app.api.corrections import _is_noop_correction
    assert _is_noop_correction(_req(new_text="hello WORLD")) is False


def test_text_edit_missing_old_text_not_noop():
    """Malformed payload should fall through to the existing validation path."""
    from app.api.corrections import _is_noop_correction
    assert _is_noop_correction(_req(old_text=None)) is False


def test_slide_reassign_to_same_id_is_noop():
    from app.api.corrections import _is_noop_correction
    sid = uuid.uuid4()
    req = _req(
        correction_type="slide_reassignment",
        old_text=None,
        new_text=None,
        old_slide_id=sid,
        new_slide_id=sid,
    )
    assert _is_noop_correction(req) is True


def test_slide_reassign_to_different_id_not_noop():
    from app.api.corrections import _is_noop_correction
    req = _req(
        correction_type="slide_reassignment",
        old_text=None,
        new_text=None,
        old_slide_id=uuid.uuid4(),
        new_slide_id=uuid.uuid4(),
    )
    assert _is_noop_correction(req) is False


def test_speaker_reassign_never_noop():
    """Speaker reassignment has render-side effects; treat as never-noop."""
    from app.api.corrections import _is_noop_correction
    req = _req(
        correction_type="speaker_reassignment",
        old_text=None,
        new_text=None,
    )
    assert _is_noop_correction(req) is False


def test_mark_ok_never_noop():
    """mark_ok writes a discrepancy resolution; never a noop."""
    from app.api.corrections import _is_noop_correction
    req = _req(correction_type="mark_ok")
    assert _is_noop_correction(req) is False


def test_advisory_lock_keys_deterministic_and_in_int32_range():
    from app.services.db_locks import _stage_keys
    k1, k2 = _stage_keys("session-abc", "slide_extract")
    assert -(2 ** 31) <= k1 < 2 ** 31
    assert -(2 ** 31) <= k2 < 2 ** 31
    # Deterministic
    assert (k1, k2) == _stage_keys("session-abc", "slide_extract")
    # Different stage -> different keys (collision possible but vanishingly likely)
    other = _stage_keys("session-abc", "transcribe")
    assert (k1, k2) != other
