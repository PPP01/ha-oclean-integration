"""HA-free BLE helper utilities.

Pure decision logic shared by the coordinator poll path and the write-action
connection wrapper. Kept free of Home Assistant / bleak imports so it can be
unit-tested with plain pytest (see tests/oclean_ble/test_ble_utils.py).
"""

from __future__ import annotations

from typing import Any


def normalize_char_source(sender: Any) -> str | None:
    """Normalise a notification sender to a lowercase characteristic-UUID string.

    ``sender`` may be a bleak ``BleakGATTCharacteristic`` (has ``.uuid``), an
    explicit UUID string passed by the READ-fallback paths, or ``None``. The
    result is used purely as an identity key to bind *B# reassembly
    continuation packets to the characteristic that started the reassembly.
    """
    if sender is None:
        return None
    uuid = getattr(sender, "uuid", None)
    if uuid is not None:
        return str(uuid).lower()
    return str(sender).lower()


def is_reassembly_continuation(
    in_progress: bool, active_source: str | None, incoming_source: str | None
) -> bool:
    """Decide whether an incoming packet is a *B# reassembly continuation.

    A packet only continues an open reassembly when a reassembly is in progress
    AND the packet arrived on the SAME source characteristic that delivered the
    *B# header. A frame from a different characteristic (e.g. a READ fallback on
    another UUID) must be dispatched normally, never appended to the open buffer
    — otherwise a standalone frame is misread as continuation data and silently
    corrupts the reassembled records (review P2.4).
    """
    return in_progress and incoming_source == active_source


def is_genuine_cancellation(cancelling_count: int) -> bool:
    """Decide whether a caught CancelledError is a *genuine* task cancellation.

    The ESPHome BLE-proxy connect path leaks a *spurious* CancelledError when a
    connection to a sleeping device times out (its internal disconnect-guard
    cancels an await). A genuine cancellation (HA shutdown / entry reload)
    marks the current task via ``asyncio.Task.cancelling() > 0`` and MUST
    propagate; only the spurious proxy cancellation may be translated into a
    retryable error.

    Args:
        cancelling_count: ``asyncio.current_task().cancelling()`` at catch time.

    Returns:
        True if the CancelledError must be re-raised, False if it is the
        proxy-leaked spurious variant and may be translated.
    """
    return cancelling_count > 0
