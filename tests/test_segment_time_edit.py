"""
Tests for Phase 4 — SegmentPatch start_ms / end_ms extension.

Pins the validation contract (start < end, both non-negative) plus the
time-only audit-kind dispatch (`segment.time_edit` vs. `segment.edit`).
DB-dependent tests are marked skip pending the project-wide fixture;
the import-time + Pydantic validation tests run in CI.
"""
import pytest

from app.api.segments import SegmentPatch


class TestSegmentPatchTimeFields:
    """Pure-Pydantic validation — no DB / FastAPI needed."""

    def test_both_fields_optional(self):
        # Existing callers that only edit text continue to work.
        p = SegmentPatch(text="new text")
        assert p.start_ms is None
        assert p.end_ms is None

    def test_start_ms_only(self):
        p = SegmentPatch(start_ms=1500)
        assert p.start_ms == 1500
        assert p.end_ms is None

    def test_end_ms_only(self):
        p = SegmentPatch(end_ms=5000)
        assert p.end_ms == 5000
        assert p.start_ms is None

    def test_both_supplied(self):
        p = SegmentPatch(start_ms=1000, end_ms=4500)
        assert p.start_ms == 1000
        assert p.end_ms == 4500

    def test_zero_is_valid_start_ms(self):
        # Sessions start at 0ms; the first segment's start_ms is often 0.
        p = SegmentPatch(start_ms=0, end_ms=1000)
        assert p.start_ms == 0

    def test_negative_start_ms_rejected(self):
        with pytest.raises(Exception):  # Pydantic ValidationError
            SegmentPatch(start_ms=-1)

    def test_negative_end_ms_rejected(self):
        with pytest.raises(Exception):
            SegmentPatch(end_ms=-1)

    def test_serializes_only_supplied_fields(self):
        # exclude_none=True is what the audit-events insert path uses;
        # confirm time fields appear in the details JSON when supplied.
        p = SegmentPatch(start_ms=2000, end_ms=5000)
        d = p.model_dump(exclude_none=True, mode="json")
        assert d == {"start_ms": 2000, "end_ms": 5000}

    def test_omitted_time_fields_not_in_dump(self):
        # Text-only edit must not accidentally carry time keys in the audit
        # details (would mislead operators reading the ledger).
        p = SegmentPatch(text="hello")
        d = p.model_dump(exclude_none=True, mode="json")
        assert "start_ms" not in d
        assert "end_ms" not in d


@pytest.mark.skip(reason="Needs DB fixture; see tests/test_auth.py skip pattern.")
def test_patch_endpoint_rejects_end_lte_start():
    """edit_segment must return 400 when end_ms <= start_ms.

    Reproduces the explicit guard in app/api/segments.py:106-122 which
    rejects an invalid open-ended interval before any DB write."""
    # PATCH /v1/sessions/{sid}/segments/{seg_id} with {start_ms:5000, end_ms:5000}
    # → expected: 400 INVALID_TIMESTAMP
    ...


@pytest.mark.skip(reason="Needs DB fixture.")
def test_time_only_edit_emits_segment_time_edit_audit_kind():
    """When the patch carries ONLY time fields (no text/slide/speaker/flags),
    audit_events row has kind='segment.time_edit', not the generic
    'segment.edit'. This lets SOP analytics filter time-correction events."""
    ...


@pytest.mark.skip(reason="Needs DB fixture.")
def test_mixed_edit_emits_segment_edit_audit_kind():
    """When the patch carries time + text together, audit kind stays
    'segment.edit' (the generic). Reserves 'segment.time_edit' for
    operator-driven timestamp fixes only."""
    ...
