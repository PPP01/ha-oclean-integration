"""Unit tests for the *B# reassembly source-binding helpers.

While a *B# multi-packet reassembly is open, only further packets from the SAME
source characteristic may be treated as continuation data. A READ-fallback frame
from a *different* characteristic must not be appended into the open buffer,
which would silently corrupt the reassembled records. See review finding P2.4.
"""

from oclean_ble.ble_utils import is_reassembly_continuation, normalize_char_source


class _FakeChar:
    """Minimal stand-in for a bleak GATT characteristic (has a .uuid)."""

    def __init__(self, uuid: str) -> None:
        self.uuid = uuid


def test_normalize_char_from_object_uuid():
    assert normalize_char_source(_FakeChar("0000FBB9-0000-1000-8000-00805F9B34FB")) == (
        "0000fbb9-0000-1000-8000-00805f9b34fb"
    )


def test_normalize_char_from_string():
    assert normalize_char_source("FBB9") == "fbb9"


def test_normalize_char_none():
    assert normalize_char_source(None) is None


def test_continuation_matches_same_source():
    # In progress + same source -> genuine continuation.
    assert is_reassembly_continuation(True, "fbb90", "fbb90") is True


def test_continuation_rejects_other_source():
    # In progress but a frame from a different characteristic is NOT continuation.
    assert is_reassembly_continuation(True, "fbb90", "fbb86") is False


def test_not_in_progress_is_never_continuation():
    assert is_reassembly_continuation(False, "fbb90", "fbb90") is False
