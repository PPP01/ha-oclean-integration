"""Regression tests: session duration must be the REAL brushing time.

Real 42-byte C3385w0 records captured live from an OCLEANY3MH brush
(2026-07-03, debug log). Byte layout: bytes 7-8 hold the SCHEDULED programme
length (constant per pnum), bytes 9-10 the actually-brushed seconds
(validDuration). The user aborted a 180 s programme after ~31 s -> the sensor
must report 31, not 180.
"""

import pytest

from oclean_ble.const import (
    DATA_LAST_BRUSH_DURATION,
    DATA_LAST_BRUSH_DURATION_SCHEDULED,
    DATA_LAST_BRUSH_PNUM,
    DATA_LAST_BRUSH_SCORE,
)
from oclean_ble.parser import _real_duration_s, parse_t1_c3385w0_record

# 03.07.2026 10:25:48, pnum 2, scheduled 180 s (0x00b4), real 31 s (0x001f), score 29
REC_ABORTED_31S = bytes.fromhex(
    "1a07030a19300200b4001f05144b000000100000000000000100001202090000001d030300ffffffffff"
)
# 02.07.2026 21:01:02, pnum 123 ("Intensiv"), scheduled 306 s, real 306 s (full run), score 100
REC_FULL_306S = bytes.fromhex(
    "1a07021501027b0132013205144b0000001000000000000f1d2a2911342d37000064030300ffffffffff"
)
# 03.07.2026 00:19:58, pnum 123, scheduled 306 s, real 14 s (aborted), score 14
REC_ABORTED_14S = bytes.fromhex(
    "1a070300133a7b0132000e0a1446000000100000000000010b00000000000000000e030300ffffffffff"
)


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
