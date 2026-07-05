"""HA-free helpers rating per-zone brushing values against the session total.

Traffic-light thresholds (single source of truth, mirrored by the
button-card SVG renderer in the dashboard): target per zone is
sum(zones)/8 – the zone's SHARE of the whole session. A zone rates
good at >= 75 % of target, ok at >= 40 %, poor above 0 and missed at
exactly 0.

Why share-based instead of duration/8: the zone values are seconds on
OCLEANX3-class devices (sum ~= duration) but use a different unit on
OCLEANY3MD/Oclean X (e.g. sum 96 for a 240 s session). Normalising to
the session's own total keeps the rating unit-invariant and always
"relative to the actual total brushing time".
"""

from __future__ import annotations

GOOD_SHARE = 0.75
OK_SHARE = 0.40

RATING_EMOJI = {"good": "🟩", "ok": "🟨", "poor": "🟥", "missed": "⬜"}

# Display order (patient view, left→right) over TOOTH_AREA_NAMES indices:
# upper: UL_out, UL_in, UR_in, UR_out – lower: LL_out, LL_in, LR_in, LR_out
UPPER_DISPLAY = (0, 1, 5, 4)
LOWER_DISPLAY = (2, 3, 7, 6)


def zone_ratings(zones: list[int] | None) -> list[str] | None:
    """Rate 8 per-zone values as good/ok/poor/missed (TOOTH_AREA_NAMES order)."""
    if zones is None or len(zones) != 8:
        return None
    total = sum(v for v in zones if v > 0)
    if total <= 0:
        return ["missed"] * 8
    target = total / 8
    ratings: list[str] = []
    for v in zones:
        if v <= 0:
            ratings.append("missed")
        elif v >= target * GOOD_SHARE:
            ratings.append("good")
        elif v >= target * OK_SHARE:
            ratings.append("ok")
        else:
            ratings.append("poor")
    return ratings


def zones_to_seconds(zones: list[int] | None, duration_s: int) -> list[int] | None:
    """Scale raw per-zone values to seconds of the real session duration.

    For slot-scheme firmwares (e.g. OCLEANY3MD: fixed total of 96 slots à
    2.5 s in a 4-min programme) the raw values are meaningless to users –
    seconds = value / total * duration, half-up rounded. Ratings are share
    based, so scaling never changes the traffic-light result. Callers decide
    per model whether to scale; with an unusable total/duration the input is
    returned unchanged.
    """
    if zones is None or len(zones) != 8:
        return None
    total = sum(v for v in zones if v > 0)
    if total <= 0 or duration_s <= 0:
        return list(zones)
    return [int(max(0, v) / total * duration_s + 0.5) for v in zones]


def zone_emoji_signature(zones: list[int] | None) -> str | None:
    """Compact emoji signature '<upper>/<lower>' in display order."""
    ratings = zone_ratings(zones)
    if ratings is None:
        return None
    upper = "".join(RATING_EMOJI[ratings[i]] for i in UPPER_DISPLAY)
    lower = "".join(RATING_EMOJI[ratings[i]] for i in LOWER_DISPLAY)
    return f"{upper}/{lower}"
