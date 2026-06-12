"""
Segment drag-drop reorder — pure logic for the seq rewrite.

Plan: docs/plans/2026-06-12-001-segment-drag-drop-reorder.md.
Covers `_reorder_changes` (which (segment_id, new_seq) pairs change for a given
desired full order) without a DB. The endpoint validates the permutation; this
test pins the change-computation that drives both the seq UPDATE and the undo
snapshot.
"""
from __future__ import annotations

from app.api.session_resources import _reorder_changes


def _current(ids):
    return {sid: i for i, sid in enumerate(ids)}


def test_identity_order_changes_nothing():
    ids = ["a", "b", "c", "d"]
    assert _reorder_changes(_current(ids), ids) == []


def test_full_reverse_keeps_only_odd_middle_fixed():
    ids = ["a", "b", "c", "d", "e"]
    reversed_ids = ["e", "d", "c", "b", "a"]
    changed = dict(_reorder_changes(_current(ids), reversed_ids))
    # 5-element reverse: only the middle ("c", index 2) is a fixed point;
    # everything else changes index.
    assert changed == {"e": 0, "d": 1, "b": 3, "a": 4}
    assert "c" not in changed


def test_single_move_to_front_shifts_the_span():
    ids = ["a", "b", "c", "d", "e"]
    # move "d" to the front
    new = ["d", "a", "b", "c", "e"]
    changed = dict(_reorder_changes(_current(ids), new))
    # d:0, a:1, b:2, c:3 change; e stays at 4
    assert changed == {"d": 0, "a": 1, "b": 2, "c": 3}
    assert "e" not in changed


def test_changes_yield_a_clean_permutation():
    ids = [f"s{i}" for i in range(10)]
    new = ids[3:] + ids[:3]  # rotate
    cur = _current(ids)
    changed = _reorder_changes(cur, new)
    # Apply the changes on top of current, assert final seqs are 0..9 unique.
    final = dict(cur)
    for sid, seq in changed:
        final[sid] = seq
    assert sorted(final.values()) == list(range(10))
    # And the final order matches the requested order.
    assert [sid for sid, _ in sorted(final.items(), key=lambda kv: kv[1])] == new
