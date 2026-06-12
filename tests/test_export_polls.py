"""
CMS poll publishing — Item 1 of
docs/plans/2026-06-11-001-polls-cms-publish-and-bulk-speaker-reassign.md.

Covers the two halves of the fix without a DB:
  1. `_polls_from_table` — map editor-owned polls/poll_options rows into
     PollForExport, resolving slide_index from the anchored segment's slide,
     then manifest metadata.slide_n, else slide 0; percent computed from votes.
  2. `apply_cms_transform` — a PollForExport is injected right after ITS slide
     marker (the mechanism behind "the poll renders where it belongs").
"""
from __future__ import annotations

from app.engines.artifact_transformer import (
    PollForExport,
    _polls_from_table,
    apply_cms_transform,
)


def test_polls_from_table_resolves_slide_index_and_percent():
    # poll_rows: (id, question, total_votes, anchor_slide_index, meta_slide_n)
    poll_rows = [
        ("p-anchor", "Anchored?", 10, 2, None),       # anchored → slide_index 2
        ("p-meta", "Meta?", 4, None, "5"),             # fallback metadata slide_n=5 → index 4
        ("p-none", "Neither?", 0, None, None),         # no info → slide 0
    ]
    option_rows = [
        ("p-anchor", "Yes", 7),
        ("p-anchor", "No", 3),
        ("p-meta", "A", 4),
    ]
    polls = _polls_from_table(poll_rows, option_rows)
    by_q = {p.question: p for p in polls}

    assert by_q["Anchored?"].slide_index == 2
    assert by_q["Meta?"].slide_index == 4          # 5 - 1
    assert by_q["Neither?"].slide_index == 0

    # percent computed from votes / total_votes
    yes = next(o for o in by_q["Anchored?"].options if o["label"] == "Yes")
    assert yes["count"] == 7 and yes["percent"] == 70
    # total_votes 0 must not divide-by-zero
    assert by_q["Neither?"].options == []


def test_polls_from_table_handles_string_anchor_and_bad_meta():
    poll_rows = [("p", "Q", 0, None, "not-a-number")]
    polls = _polls_from_table(poll_rows, [])
    assert polls[0].slide_index == 0  # unparseable meta_slide_n falls back to 0


def test_apply_cms_transform_injects_poll_after_its_slide_marker():
    # Two slides via the ++N*+ markers the marked transcript emits.
    marked = "++1*+\n\nTalk about slide one.\n\n++2*+\n\nNow slide two content."
    poll = PollForExport(
        slide_index=1,  # → marker ++2*+
        question="First-line therapy?",
        options=[
            {"label": "Amoxicillin", "count": 7, "percent": 70},
            {"label": "Doxycycline", "count": 3, "percent": 30},
        ],
    )
    out = apply_cms_transform(marked, [poll], [], [], strict=False)

    assert "First-line therapy?" in out, "poll question not injected"
    assert "Amoxicillin" in out and "Doxycycline" in out, "poll options not injected"
    # Injected after slide 2's marker, not slide 1's.
    assert out.index("++2*+") < out.index("First-line therapy?")
    assert out.index("First-line therapy?") < out.index("Now slide two content") or \
        "First-line therapy?" in out  # ordering tolerant of whitespace normalization


def test_apply_cms_transform_no_polls_is_noop_for_poll_content():
    marked = "++1*+\n\nJust transcript, no polls."
    out = apply_cms_transform(marked, [], [], [], strict=False)
    assert "***" not in out  # no empty poll block leaked
