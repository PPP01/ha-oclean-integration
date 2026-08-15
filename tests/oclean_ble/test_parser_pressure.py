"""Regression tests for the 0308-simple running-data pressure field.

Bytes 16-17 are a little-endian uint16 divided by 300 to yield the pressure
value. When the device has no pressure data it leaves the field at its
all-ones sentinel (0xFFFF), which naively yields a bogus 218.45. That sentinel
must be treated as "not available" and the pressure field omitted. See review
finding P2.5.
"""

from oclean_ble.const import DATA_LAST_BRUSH_PRESSURE
from oclean_ble.parser import _parse_running_data_record


def _record(pressure_raw: int) -> bytes:
    """Build a minimal valid 18-byte 0308-simple record with a given raw pressure."""
    return bytes(
        [
            26,  # byte 0: year_base -> 2026
            7,  # byte 1: month
            5,  # byte 2: day
            12,  # byte 3: hour
            30,  # byte 4: minute
            0,  # byte 5: second
            8,  # byte 6: tz offset (+2h in quarter-hours)
            2,  # byte 7: week
            1,  # byte 8: pNum
            0,
            0,
            0,
            0,
            0,  # bytes 9-13: unknown
            0,
            0,  # bytes 14-15: blunt-teeth (LE uint16)
            pressure_raw & 0xFF,  # byte 16: pressure low
            (pressure_raw >> 8) & 0xFF,  # byte 17: pressure high
        ]
    )


def test_real_pressure_is_reported():
    # 600 / 300 = 2.0 – a plausible reading must pass through unchanged.
    result = _parse_running_data_record(_record(600))
    assert result[DATA_LAST_BRUSH_PRESSURE] == 2.0


def test_all_ones_sentinel_pressure_is_omitted():
    # 0xFFFF is the device's "field not populated" sentinel and must NOT be
    # reported as 218.45.
    result = _parse_running_data_record(_record(0xFFFF))
    assert DATA_LAST_BRUSH_PRESSURE not in result
    # The rest of the record (timestamp, brush-head usage) must still parse.
    assert result != {}
