"""Tests for the host-independent timestamp helpers (review P2.1).

The parser must not depend on the host process timezone (``time.mktime``).
Instead it emits a *device-local* epoch (wall-clock digits interpreted as UTC)
via ``_local_epoch``; the coordinator then resolves that to true UTC with
``resolve_session_utc`` — using the frame's TZ offset when the record carries
one (0308 paths), else the HA-configured timezone (DST-aware).
"""

import datetime
from zoneinfo import ZoneInfo

from oclean_ble.parser import _local_epoch, resolve_session_utc

_BERLIN = ZoneInfo("Europe/Berlin")
_UTC = datetime.timezone.utc


def _utc_epoch(y, mo, d, h, mi, s=0) -> int:
    return int(datetime.datetime(y, mo, d, h, mi, s, tzinfo=_UTC).timestamp())


def test_local_epoch_treats_wallclock_as_utc():
    # The wall-clock digits are interpreted as if they were UTC.
    dt = datetime.datetime(2026, 7, 5, 12, 30, 0)
    assert _local_epoch(dt) == _utc_epoch(2026, 7, 5, 12, 30, 0)


def test_resolve_with_frame_offset_subtracts_offset():
    # 0308 path: the record carries a real signed offset (here +2h = 7200 s).
    le = _local_epoch(datetime.datetime(2026, 7, 5, 12, 0, 0))
    assert resolve_session_utc(le, 7200, _BERLIN) == le - 7200


def test_resolve_offset_ignores_timezone_argument():
    # When a frame offset is present the HA timezone must NOT be consulted.
    le = _local_epoch(datetime.datetime(2026, 1, 15, 12, 0, 0))
    assert resolve_session_utc(le, 3600, _BERLIN) == le - 3600


def test_resolve_ha_tz_summer_is_dst_aware():
    # Offset-less path in July: Berlin is UTC+2 (CEST).
    le = _local_epoch(datetime.datetime(2026, 7, 5, 12, 0, 0))
    assert resolve_session_utc(le, None, _BERLIN) == le - 7200


def test_resolve_ha_tz_winter_is_dst_aware():
    # Offset-less path in January: Berlin is UTC+1 (CET).
    le = _local_epoch(datetime.datetime(2026, 1, 15, 12, 0, 0))
    assert resolve_session_utc(le, None, _BERLIN) == le - 3600


def test_resolve_ha_tz_utc_is_noop():
    le = _local_epoch(datetime.datetime(2026, 7, 5, 12, 0, 0))
    assert resolve_session_utc(le, None, _UTC) == le


def test_offset_and_ha_tz_agree_when_device_matches_ha_zone():
    # Consistency: a summer session whose device offset (+2h) equals Berlin's
    # current offset must resolve identically via both paths.
    le = _local_epoch(datetime.datetime(2026, 7, 5, 8, 15, 0))
    assert resolve_session_utc(le, 7200, _BERLIN) == resolve_session_utc(le, None, _BERLIN)
