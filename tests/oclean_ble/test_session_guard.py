"""Regression tests for the session plausibility guard.

Real-world incident (2026-08-15, Oclean X "Paul", 70:28:45:77:F4:9D): a
mis-parsed record delivered a session timestamp in the year 2240. The
coordinator keeps a single monotonic high-water mark (``_last_session_ts``)
and treats every session with ``ts <= high-water mark`` as already known, so
one implausible record silently blocked ALL further session imports — four
weeks of brushing data were dropped before anyone noticed.

The timestamps below are the actual values recovered from the store.
"""

import pytest

from oclean_ble.session_guard import (
    filter_plausible_history,
    is_plausible_session_ts,
    sanitize_last_session_ts,
)

# Recovered from .storage/oclean_ble.70_28_45_77_f4_9d on 2026-08-15.
NOW = 1786809600  # 2026-08-15 ~18:00 UTC+2
LAST_GOOD_TS = 1784317079  # 2026-07-17 21:37:59 – last correctly parsed session
CORRUPT_TS = (
    1797163989,  # 2026-12-11
    1817626109,  # 2027-08-06
    1952345472,  # 2031-11-13
    8542671190,  # 2240-09-15 – the record that locked the brush
)


def test_recent_timestamp_is_plausible():
    assert is_plausible_session_ts(LAST_GOOD_TS, NOW) is True


def test_timestamp_far_in_the_future_is_implausible():
    assert is_plausible_session_ts(8542671190, NOW) is False


def test_timestamp_months_ahead_is_implausible():
    """The first corrupt record was only ~4 months ahead – still must be caught."""
    assert is_plausible_session_ts(1797163989, NOW) is False


def test_small_clock_drift_is_tolerated():
    """Brush clocks drift; an hour ahead is not corruption."""
    assert is_plausible_session_ts(NOW + 3600, NOW) is True


def test_zero_timestamp_is_implausible():
    assert is_plausible_session_ts(0, NOW) is False


def test_sanitize_keeps_a_plausible_stored_value():
    assert sanitize_last_session_ts(LAST_GOOD_TS, NOW, []) == LAST_GOOD_TS


def test_sanitize_falls_back_to_newest_plausible_known_timestamp():
    """Paul's case: the mark is poisoned, the zone history still holds the anchor."""
    known = [1783194164, LAST_GOOD_TS, 1797163989, 8542671190]

    assert sanitize_last_session_ts(8542671190, NOW, known) == LAST_GOOD_TS


def test_sanitize_returns_zero_when_no_plausible_anchor_exists():
    """Without an anchor a full re-import is preferable to a permanent lock."""
    assert sanitize_last_session_ts(8542671190, NOW, [8542671190]) == 0


def test_filter_drops_every_implausible_history_entry():
    history = [{"ts": LAST_GOOD_TS}] + [{"ts": ts} for ts in CORRUPT_TS]

    kept = filter_plausible_history(history, NOW)

    assert kept == [{"ts": LAST_GOOD_TS}]


def test_filter_is_idempotent_on_clean_history():
    history = [{"ts": 1783194164}, {"ts": LAST_GOOD_TS}]

    assert filter_plausible_history(history, NOW) == history


def test_filter_tolerates_entries_without_timestamp():
    """A malformed store entry must not crash the coordinator on load."""
    history = [{"ts": LAST_GOOD_TS}, {"zones": [1, 2]}]

    assert filter_plausible_history(history, NOW) == [{"ts": LAST_GOOD_TS}]
