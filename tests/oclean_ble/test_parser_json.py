"""Regression tests for the JSON brush-session fallback parser.

A malformed-but-valid JSON notification from the device (or BLE proxy) must
never raise out of ``parse_notification`` — an unparsable field must be skipped,
not crash the coordinator poll. See review finding P1.3.
"""

from oclean_ble.parser import _map_json_brush_data, parse_notification


def test_map_json_skips_non_numeric_int_field():
    # A non-numeric string in an int-cast field must be skipped, not raise.
    result = _map_json_brush_data({"score": "err"})
    assert result == {}


def test_map_json_keeps_valid_fields_when_one_is_bad():
    # One bad int field must not drop the other, well-formed fields.
    result = _map_json_brush_data({"score": "err", "duration": 120})
    assert 120 in result.values()


def test_map_json_none_value_does_not_raise():
    # ``None`` (JSON null) in an int-cast field: TypeError must be handled.
    result = _map_json_brush_data({"pressure": None})
    assert result == {}


def test_map_json_list_value_does_not_raise():
    # A structured value (list/dict) in an int-cast field must be skipped.
    result = _map_json_brush_data({"score": [1, 2, 3]})
    assert result == {}


def test_map_json_numeric_string_is_still_cast():
    # A well-formed numeric string must still be accepted and cast to int.
    result = _map_json_brush_data({"score": "58"})
    assert 58 in result.values()


def test_parse_notification_json_bad_value_returns_dict():
    # End-to-end via the real entry point: a bad value must not propagate.
    payload = b'{"score": "err", "duration": 120}'
    result = parse_notification(payload)
    assert isinstance(result, dict)
    assert 120 in result.values()
