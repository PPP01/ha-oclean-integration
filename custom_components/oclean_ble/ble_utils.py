"""HA-free BLE helper utilities.

Pure decision logic shared by the coordinator poll path and the write-action
connection wrapper. Kept free of Home Assistant / bleak imports so it can be
unit-tested with plain pytest (see tests/oclean_ble/test_ble_utils.py).
"""

from __future__ import annotations


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
