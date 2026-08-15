"""Pure session-grouping logic for back-to-back brushing runs (no HA imports).

Users often start a second programme right after the first because one run is
too short. The brush firmware scores each run separately (two half-brushings
score ~50 % each), so the integration offers an OWN combined value per group of
back-to-back sessions: the capped sum of the firmware scores
(``min(100, sum)`` — 60 % + 80 % = 100 %, 50 % + 60 % = 100 %).

Kept free of Home Assistant imports so it is unit-testable with plain pytest;
the coordinator persists the group state and exposes it to sensors.
"""

from __future__ import annotations

from typing import Any

# Selectable merge windows (minutes) in the options flow; 0 = feature off.
MERGE_WINDOW_CHOICES = (0, 1, 2, 3, 4, 5)


def is_group_continuation(prev_end_ts: int, new_ts: int, window_s: int) -> bool:
    """Return True when a session starting at *new_ts* continues the group.

    *prev_end_ts* is the previous session's start + real duration. The gap
    between the previous end and the new start must be <= *window_s*. Negative
    gaps (overlapping timestamps from device clock drift) also merge — the
    sessions are adjacent by definition. window_s <= 0 disables merging.
    """
    if window_s <= 0 or prev_end_ts <= 0 or new_ts <= 0:
        return False
    return (new_ts - prev_end_ts) <= window_s


def combined_score(scores: list[int | None]) -> int | None:
    """Return the integration score of a group: min(100, sum of firmware scores).

    Sessions without a score are ignored; returns None when no score exists.
    """
    vals = [int(s) for s in scores if s is not None]
    if not vals:
        return None
    return min(100, sum(vals))


def new_group(ts: int, duration: int, score: int | None) -> dict[str, Any]:
    """Start a fresh group from one session."""
    return {
        "start_ts": ts,
        "end_ts": ts + max(0, int(duration or 0)),
        "scores": [score],
        "durations": [int(duration or 0)],
    }


def extend_group(group: dict[str, Any], ts: int, duration: int, score: int | None) -> dict[str, Any]:
    """Append a continuation session to *group* (returns the same dict)."""
    group["end_ts"] = ts + max(0, int(duration or 0))
    group["scores"].append(score)
    group["durations"].append(int(duration or 0))
    return group
