"""Plausibility guard for session timestamps (no HA imports).

The coordinator tracks imported sessions with a single monotonic high-water
mark (``_last_session_ts``): anything at or below it counts as already known.
That makes the mark a one-way ratchet — a single mis-parsed record with a
timestamp in the future raises it beyond every real session and permanently
blocks all further imports, silently.

This module keeps that from happening (and heals a mark already poisoned by
one). Kept free of Home Assistant imports so it is unit-testable with plain
pytest (see tests/oclean_ble/test_session_guard.py).
"""

from __future__ import annotations

from typing import Any

# Brush clocks drift and are only re-synced on demand, so a session may
# legitimately be stamped slightly ahead of host time. A full day of slack
# absorbs that while still catching the corruption seen in practice, where
# the smallest bogus timestamp was already ~4 months out.
FUTURE_TOLERANCE_S = 86400


def is_plausible_session_ts(ts: int, now: int) -> bool:
    """Return True when *ts* can be a real brushing session at host time *now*.

    Rejects the empty/zero timestamp of an unparsed record and anything more
    than :data:`FUTURE_TOLERANCE_S` ahead of *now*. Old timestamps are always
    plausible — backfilled sessions are the normal case.
    """
    if not ts or ts <= 0:
        return False
    return ts <= now + FUTURE_TOLERANCE_S


def sanitize_last_session_ts(stored_ts: int, now: int, known_ts: list[int]) -> int:
    """Return a usable high-water mark, repairing a poisoned *stored_ts*.

    A plausible mark is returned unchanged. An implausible one is replaced by
    the newest plausible timestamp among *known_ts* (the retained session
    history), which resumes importing exactly where the good data ended and
    therefore re-imports nothing that already exists. With no plausible anchor
    the mark drops to 0: a full re-import may duplicate entries, but that is
    recoverable whereas a permanent import lock is not.
    """
    if is_plausible_session_ts(stored_ts, now):
        return stored_ts
    plausible = [ts for ts in known_ts if is_plausible_session_ts(ts, now)]
    return max(plausible) if plausible else 0


def filter_plausible_history(entries: list[dict[str, Any]], now: int) -> list[dict[str, Any]]:
    """Drop history entries whose timestamp cannot be real.

    Entries without a usable ``ts`` are dropped as well, so a malformed store
    cannot crash the coordinator during load.
    """
    return [entry for entry in entries if is_plausible_session_ts(entry.get("ts", 0), now)]
