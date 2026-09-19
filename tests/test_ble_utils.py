"""Unit tests for the HA-free ble_utils helpers."""

from __future__ import annotations

from custom_components.oclean_ble.ble_utils import is_genuine_cancellation


def test_zero_cancelling_count_is_spurious():
    # cancelling() == 0 → proxy-leaked spurious cancel: translate, don't re-raise
    assert is_genuine_cancellation(0) is False


def test_positive_cancelling_count_is_genuine():
    # cancelling() > 0 → real HA shutdown / reload cancel: must re-raise
    assert is_genuine_cancellation(1) is True


def test_higher_cancelling_count_is_genuine():
    assert is_genuine_cancellation(3) is True
