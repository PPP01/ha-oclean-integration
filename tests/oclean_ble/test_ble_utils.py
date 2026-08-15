"""Unit tests for the HA-free BLE helper utilities.

Covers the spurious-vs-genuine CancelledError decision shared by the coordinator
poll path and the write-action connection wrapper (review finding P1.2).
"""

from oclean_ble.ble_utils import is_genuine_cancellation


def test_zero_cancelling_count_is_spurious():
    # asyncio.Task.cancelling() == 0 -> proxy-leaked spurious cancel: translate.
    assert is_genuine_cancellation(0) is False


def test_positive_cancelling_count_is_genuine():
    # cancelling() > 0 -> real HA shutdown / reload cancel: must re-raise.
    assert is_genuine_cancellation(1) is True


def test_higher_cancelling_count_is_genuine():
    assert is_genuine_cancellation(3) is True
