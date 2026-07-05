"""Tests for zone_utils – HA-free zone rating helpers.

Ratings are SHARE-based: target per zone is sum(zones)/8, NOT duration/8.
Rationale: some devices (OCLEANY3MD/Oclean X) report zone values in a
different unit than seconds – Paul's 4:00 session sums to 96, not 240.
Rating against the session's own total is unit-invariant.
"""

from custom_components.oclean_ble.zone_utils import (
    LOWER_DISPLAY,
    RATING_EMOJI,
    UPPER_DISPLAY,
    zone_emoji_signature,
    zone_ratings,
    zones_to_seconds,
)

# Purple live session 2026-07-04: sum 293 (duration 306 s – values ARE seconds)
PURPLE = [21, 40, 48, 29, 17, 38, 55, 45]

# Paul live session 2026-07-04: sum 96 at 240 s duration (values NOT seconds!)
PAUL = [9, 12, 10, 16, 14, 9, 11, 15]


def test_ratings_real_purple_session() -> None:
    # total 293 → target 36.6 → good ≥ 27.5, ok ≥ 14.65
    assert zone_ratings(PURPLE) == [
        "ok",  # 21
        "good",  # 40
        "good",  # 48
        "good",  # 29
        "ok",  # 17
        "good",  # 38
        "good",  # 55
        "good",  # 45
    ]


def test_ratings_real_paul_session_unit_invariant() -> None:
    # total 96 → target 12 → good ≥ 9, ok ≥ 4.8: gleichmäßig geputzt → alles good.
    # Mit dem alten duration/8-Soll (240/8=30) wäre alles poor/ok gewesen.
    assert zone_ratings(PAUL) == ["good"] * 8


def test_ratings_thresholds_exact() -> None:
    # total 80 → target 10 → good ≥ 7.5, ok ≥ 4.0
    zones = [8, 7, 4, 3, 1, 0, 10, 47]
    assert zone_ratings(zones) == [
        "good",
        "ok",
        "ok",
        "poor",
        "poor",
        "missed",
        "good",
        "good",
    ]


def test_ratings_all_zero() -> None:
    assert zone_ratings([0] * 8) == ["missed"] * 8


def test_ratings_invalid_input() -> None:
    assert zone_ratings(None) is None
    assert zone_ratings([1, 2, 3]) is None


def test_emoji_signature_display_order() -> None:
    # index:      0    1   2  3  4   5   6   7
    zones = [40, 20, 0, 3, 1, 38, 55, 45]
    # total 202 → target 25.25 → good ≥ 18.94, ok ≥ 10.1
    # oben  [0,1,5,4] → good(40), good(20), good(38), poor(1)  → 🟩🟩🟩🟥
    # unten [2,3,7,6] → missed(0), poor(3), good(45), good(55) → ⬜🟥🟩🟩
    assert zone_emoji_signature(zones) == "🟩🟩🟩🟥/⬜🟥🟩🟩"


def test_emoji_signature_none() -> None:
    assert zone_emoji_signature(None) is None


def test_zones_to_seconds_paul_96_scheme() -> None:
    # OCLEANY3MD: 96 Slots à 2,5 s bei 240 s → v × 2,5, kaufmännisch gerundet
    assert zones_to_seconds([12, 9, 14, 13, 13, 12, 9, 14], 240) == [
        30,
        23,
        35,
        33,
        33,
        30,
        23,
        35,
    ]


def test_zones_to_seconds_preserves_shares() -> None:
    # Ampel-Bewertung muss vor und nach der Umrechnung identisch sein
    raw = [13, 11, 14, 13, 9, 13, 9, 14]
    assert zone_ratings(zones_to_seconds(raw, 240)) == zone_ratings(raw)


def test_zones_to_seconds_seconds_stay_roughly_identity() -> None:
    # Purple-Werte sind schon Sekunden (Summe 293 ≈ 306): Skalierung wäre fast
    # Identität – hier nur dokumentiert, angewendet wird sie modellbasiert nie.
    out = zones_to_seconds([21, 40, 48, 29, 17, 38, 55, 45], 306)
    assert out[1] == 42  # 40/293*306 = 41.77 → 42


def test_zones_to_seconds_edge_cases() -> None:
    assert zones_to_seconds(None, 240) is None
    assert zones_to_seconds([1, 2, 3], 240) is None
    assert zones_to_seconds([0] * 8, 240) == [0] * 8
    assert zones_to_seconds([12, 9, 14, 13, 13, 12, 9, 14], 0) == [12, 9, 14, 13, 13, 12, 9, 14]


def test_display_constants() -> None:
    assert UPPER_DISPLAY == (0, 1, 5, 4)
    assert LOWER_DISPLAY == (2, 3, 7, 6)
    assert set(RATING_EMOJI) == {"good", "ok", "poor", "missed"}
