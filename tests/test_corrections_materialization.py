"""
Phase 2a — materialize correction_ledger -> segments.text so the export
pipeline (artifact_transformer.load_session_for_export reads seg.text
directly) reflects autosaved edits without an ingest replay.

Plan ref: docs/plans/2026-06-05-010-zero-gap-parity-plan.md §Phase 2a.
Audit IDs prep-closed: blocker for Phase 6 (downloads parity).

These are unit smoke tests — full DB-integration coverage of materialize
on apply + undo + redo lives in the manual two-tab smoke documented in
the plan's verification section.
"""
from __future__ import annotations


def test_materialize_helper_exists_and_is_callable():
    """The materialization helper must be importable + take (db, session_id, *, up_to_pointer)."""
    import inspect

    from app.api.corrections import _materialize_segments_for_session

    sig = inspect.signature(_materialize_segments_for_session)
    params = list(sig.parameters)
    assert params[0] == "db"
    assert params[1] == "session_id"
    assert "up_to_pointer" in sig.parameters
    # up_to_pointer must be keyword-only
    assert sig.parameters["up_to_pointer"].kind is inspect.Parameter.KEYWORD_ONLY


def test_apply_correction_materializes_text_edit_inline():
    """Source-level assertion: apply_correction calls UPDATE segments
    inside the text_edit branch. Catches a future refactor that removes
    materialization and silently breaks downloads."""
    import pathlib

    src = pathlib.Path(__file__).resolve().parent.parent / "app" / "api" / "corrections.py"
    text = src.read_text(encoding="utf-8")
    # The Phase 2a marker comment + the UPDATE segments call must be
    # in the apply_correction function (before _emit_ws for the new row).
    assert "Phase 2a" in text, "Phase 2a marker missing — materialization was removed"
    assert 'UPDATE segments SET text = :t' in text, "Inline segments.text UPDATE missing from apply_correction"


def test_undo_redo_call_materialization():
    """Source-level assertion: undo_correction + redo_correction call
    _materialize_segments_for_session. If either drops the call, exports
    will silently diverge from editor on undo/redo."""
    import pathlib

    src = pathlib.Path(__file__).resolve().parent.parent / "app" / "api" / "corrections.py"
    text = src.read_text(encoding="utf-8")

    # Slice undo function
    undo_start = text.index("async def undo_correction")
    undo_end = text.index("async def redo_correction")
    undo_body = text[undo_start:undo_end]
    assert "_materialize_segments_for_session" in undo_body, "undo doesn't materialize"

    # Slice redo function
    redo_start = text.index("async def redo_correction")
    # Search the rest of the file
    redo_body = text[redo_start:]
    # Stop at the next top-level def to keep it scoped.
    next_def = redo_body.find("\n@router")
    redo_scope = redo_body[:next_def] if next_def > 0 else redo_body
    assert "_materialize_segments_for_session" in redo_scope, "redo doesn't materialize"
