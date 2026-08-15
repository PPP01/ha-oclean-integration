"""Unit tests for the back-to-back session grouping logic."""

import pytest

from session_group import combined_score, extend_group, is_group_continuation, new_group


# ---------------------------------------------------------------- combined_score
@pytest.mark.parametrize(
    ("scores", "expected"),
    [
        ([60, 80], 100),  # user-specified: 60 % + 80 % = 100 %
        ([50, 60], 100),  # user-specified: 50 % + 60 % = 100 %
        ([50, 40], 90),
        ([12], 12),
        ([50, None], 50),  # scoreless run ignored
        ([None, None], None),
        ([], None),
        ([100, 100], 100),  # hard cap
        ([30, 30, 30], 90),  # three runs
    ],
)
def test_combined_score(scores, expected):
    assert combined_score(scores) == expected


# ---------------------------------------------------------- is_group_continuation
def test_within_window_merges():
    # previous ended at t=1000, new starts 120 s later, window 3 min
    assert is_group_continuation(1000, 1120, 180) is True


def test_exactly_window_merges():
    assert is_group_continuation(1000, 1180, 180) is True


def test_beyond_window_no_merge():
    assert is_group_continuation(1000, 1181, 180) is False


def test_overlap_merges():
    # device clock drift: new start before previous end -> still adjacent
    assert is_group_continuation(1000, 990, 180) is True


def test_window_zero_disables():
    assert is_group_continuation(1000, 1010, 0) is False


def test_no_previous_session():
    assert is_group_continuation(0, 1000, 180) is False


# ------------------------------------------------------------------ group builders
def test_group_lifecycle():
    g = new_group(1000, 60, 50)
    assert g["end_ts"] == 1060
    g = extend_group(g, 1100, 120, 60)
    assert g["end_ts"] == 1220
    assert combined_score(g["scores"]) == 100  # 50 + 60 capped
    assert sum(g["durations"]) == 180
    assert len(g["scores"]) == 2
