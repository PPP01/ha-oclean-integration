"""Regression tests: session duration must be the REAL brushing time.

Real 42-byte C3385w0 records captured live from an OCLEANY3MH brush
(2026-07-03, debug log). Byte layout: bytes 7-8 hold the SCHEDULED programme
length (constant per pnum), bytes 9-10 the actually-brushed seconds
(validDuration). The user aborted a 180 s programme after ~31 s -> the sensor
must report 31, not 180.
"""

import pytest

from custom_components.oclean_ble.const import (
    DATA_LAST_BRUSH_DURATION,
    DATA_LAST_BRUSH_DURATION_SCHEDULED,
    DATA_LAST_BRUSH_PNUM,
    DATA_LAST_BRUSH_SCORE,
)
from custom_components.oclean_ble.parser import _real_duration_s, parse_t1_c3385w0_record

# 03.07.2026 10:25:48, pnum 2, scheduled 180 s (0x00b4), real 31 s (0x001f), score 29
REC_ABORTED_31S = bytes.fromhex("1a07030a19300200b4001f05144b000000100000000000000100001202090000001d030300ffffffffff")
# 02.07.2026 21:01:02, pnum 123 ("Intensiv"), scheduled 306 s, real 306 s (full run), score 100
REC_FULL_306S = bytes.fromhex("1a07021501027b0132013205144b0000001000000000000f1d2a2911342d37000064030300ffffffffff")
# 03.07.2026 00:19:58, pnum 123, scheduled 306 s, real 14 s (aborted), score 14
REC_ABORTED_14S = bytes.fromhex("1a070300133a7b0132000e0a1446000000100000000000010b00000000000000000e030300ffffffffff")


def test_aborted_session_reports_real_31s_not_programme_180s():
    result = parse_t1_c3385w0_record(REC_ABORTED_31S)
    assert result[DATA_LAST_BRUSH_PNUM] == 2
    assert result[DATA_LAST_BRUSH_SCORE] == 29
    assert result[DATA_LAST_BRUSH_DURATION] == 31  # NOT 180
    assert result[DATA_LAST_BRUSH_DURATION_SCHEDULED] == 180


def test_full_run_reports_full_duration():
    result = parse_t1_c3385w0_record(REC_FULL_306S)
    assert result[DATA_LAST_BRUSH_PNUM] == 123
    assert result[DATA_LAST_BRUSH_SCORE] == 100
    assert result[DATA_LAST_BRUSH_DURATION] == 306
    assert result[DATA_LAST_BRUSH_DURATION_SCHEDULED] == 306


def test_aborted_intensiv_reports_14s():
    result = parse_t1_c3385w0_record(REC_ABORTED_14S)
    assert result[DATA_LAST_BRUSH_DURATION] == 14  # NOT 306
    assert result[DATA_LAST_BRUSH_DURATION_SCHEDULED] == 306


@pytest.mark.parametrize(
    ("scheduled", "valid", "expected"),
    [
        (180, 31, 31),  # normal abort: real time wins
        (306, 306, 306),  # full run: identical
        (180, 0, 180),  # device leaves validDuration empty -> fallback
        (31, 180, 31),  # swapped-field safety: smaller nonzero value wins
        (0, 45, 45),  # only valid present
        (0, 0, None),  # nothing usable
    ],
)
def test_real_duration_helper(scheduled, valid, expected):
    assert _real_duration_s(scheduled, valid) == expected


# ---------------------------------------------------------------------------
# Scope guard: the other record layouts keep bytes 7-8 / 9-10 as-is
# ---------------------------------------------------------------------------


def test_area_sum_corroborates_valid_duration_on_c3385w0():
    """The gestureArray holds per-zone seconds, so it sums to roughly the REAL
    brushing time — the independent cross-check that bytes 9-10 are right on
    this layout: 0+1+0+0+18+2+9+0 = 30 against valid=31, not scheduled=180."""
    assert sum(REC_ABORTED_31S[23:31]) == 30


def test_y3p_layout_not_switched_to_valid_duration():
    """Real OCLEANY3P record (issue #49 comment12): bytes 7-8 = 120, bytes
    9-10 = 11, but the gestureArray sums to 97 — consistent with 120, not 11.
    The field order is not confirmed on this layout, so it must keep bytes
    7-8 and expose no scheduled attribute."""
    from custom_components.oclean_ble.parser import parse_t1_c3352g_record

    record = bytes.fromhex("1a03120d2109000078000b6400000000000f001d38010e0f0d261001000d0100000100ffffffffffffff")
    result = parse_t1_c3352g_record(record)

    assert sum(record[23:31]) == 97
    assert result[DATA_LAST_BRUSH_DURATION] == 120
    assert DATA_LAST_BRUSH_DURATION_SCHEDULED not in result


def test_extended_record_not_switched_to_valid_duration():
    from custom_components.oclean_ble.parser import _parse_extended_running_data_record

    record = bytearray(32)
    record[1] = 32
    record[2:8] = bytes((26, 7, 3, 10, 25, 48))  # 2026-07-03 10:25:48
    record[8] = 2  # pNum
    record[9:11] = (180).to_bytes(2, "big")  # duration
    record[11:13] = (31).to_bytes(2, "big")  # NOT treated as validDuration here
    record[19] = 8  # tz offset quarters

    result = _parse_extended_running_data_record(bytes(record))

    assert result[DATA_LAST_BRUSH_DURATION] == 180
    assert DATA_LAST_BRUSH_DURATION_SCHEDULED not in result
