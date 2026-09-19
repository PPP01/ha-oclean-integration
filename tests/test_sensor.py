"""Tests for sensor.py – all four sensor entity classes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# conftest.py stubs HA + bleak before these imports
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription

from custom_components.oclean_ble.const import (
    DATA_LAST_BRUSH_AREAS,
    DATA_LAST_BRUSH_COVERAGE,
    DATA_LAST_BRUSH_DURATION,
    DATA_LAST_BRUSH_GESTURE_ARRAY,
    DATA_LAST_BRUSH_GESTURE_CODE,
    DATA_LAST_BRUSH_PNUM,
    DATA_LAST_BRUSH_POWER_ARRAY,
    DATA_LAST_BRUSH_PRESSURE_RATIO,
    DATA_LAST_BRUSH_SCORE,
    DATA_LAST_BRUSH_TIME,
    SCHEME_NAMES,
    TOOTH_AREA_NAMES,
)
from custom_components.oclean_ble.sensor import (
    SENSOR_DESCRIPTIONS,
    OcleanBrushAreasSensor,
    OcleanDurationRatingSensor,
    OcleanPowerDistributionSensor,
    OcleanPressureDetailSensor,
    OcleanSchemeSensor,
    OcleanSensor,
    OcleanToothAreaSensor,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_coordinator(data=None, last_update_success=True):
    coord = MagicMock()
    coord.data = data
    coord.last_update_success = last_update_success
    return coord


def _make_sensor(key, device_class=None, data=None, last_update_success=True):
    coord = _make_coordinator(data=data, last_update_success=last_update_success)
    desc = SensorEntityDescription(key=key, device_class=device_class)
    return OcleanSensor(coord, desc, "AA:BB:CC:DD:EE:FF", "Oclean")


def _make_areas_sensor(data=None, last_update_success=True):
    coord = _make_coordinator(data=data, last_update_success=last_update_success)
    return OcleanBrushAreasSensor(coord, "AA:BB:CC:DD:EE:FF", "Oclean")


def _make_scheme_sensor(data=None, last_update_success=True):
    coord = _make_coordinator(data=data, last_update_success=last_update_success)
    return OcleanSchemeSensor(coord, "AA:BB:CC:DD:EE:FF", "Oclean")


def _make_tooth_sensor(zone_name, data=None, last_update_success=True):
    coord = _make_coordinator(data=data, last_update_success=last_update_success)
    return OcleanToothAreaSensor(coord, "AA:BB:CC:DD:EE:FF", "Oclean", zone_name)


# ---------------------------------------------------------------------------
# OcleanSensor.native_value
# ---------------------------------------------------------------------------


class TestOcleanSensorNativeValue:
    def test_returns_none_when_data_is_none(self):
        sensor = _make_sensor("battery", data=None)
        assert sensor.native_value is None

    def test_returns_none_when_value_is_none(self):
        sensor = _make_sensor("battery", data={"battery": None})
        assert sensor.native_value is None

    def test_returns_raw_value_for_non_timestamp(self):
        sensor = _make_sensor("battery", data={"battery": 80})
        assert sensor.native_value == 80

    def test_timestamp_class_converts_to_datetime(self):
        from datetime import datetime

        sensor = _make_sensor(
            DATA_LAST_BRUSH_TIME,
            device_class=SensorDeviceClass.TIMESTAMP,
            data={DATA_LAST_BRUSH_TIME: 1_700_000_000},
        )
        result = sensor.native_value
        assert isinstance(result, datetime)

    def test_timestamp_invalid_value_returns_none(self):
        sensor = _make_sensor(
            DATA_LAST_BRUSH_TIME,
            device_class=SensorDeviceClass.TIMESTAMP,
            data={DATA_LAST_BRUSH_TIME: "not-a-timestamp"},
        )
        assert sensor.native_value is None

    def test_timestamp_out_of_range_returns_none(self):
        """OSError on platforms with limited timestamp range."""
        sensor = _make_sensor(
            DATA_LAST_BRUSH_TIME,
            device_class=SensorDeviceClass.TIMESTAMP,
            data={DATA_LAST_BRUSH_TIME: 99_999_999_999_999},
        )
        # May return None (OSError) or a datetime depending on the platform
        result = sensor.native_value
        assert result is None or hasattr(result, "year")


# ---------------------------------------------------------------------------
# OcleanSensor.available
# ---------------------------------------------------------------------------


class TestOcleanSensorAvailable:
    def test_stale_data_with_value_is_available(self):
        sensor = _make_sensor("battery", data={"battery": 50}, last_update_success=False)
        assert sensor.available is True

    def test_stale_data_without_value_is_unavailable(self):
        sensor = _make_sensor("battery", data={"battery": None}, last_update_success=False)
        assert sensor.available is False

    def test_stale_data_no_data_dict_is_unavailable(self):
        sensor = _make_sensor("battery", data=None, last_update_success=False)
        assert sensor.available is False

    def test_score_available_even_when_no_score_received_yet(self):
        """Score must stay available when session exists but no score push was received yet.

        DATA_LAST_BRUSH_SCORE is NOT in _SESSION_DERIVED_KEYS: the score arrives via
        a real-time 0000 push only during/after brushing and is absent from historical
        session data. Marking it 'unavailable' would permanently hide it on devices
        like OCLEANY3MH that do support it (issue #19).
        """
        sensor = _make_sensor(
            DATA_LAST_BRUSH_SCORE,
            data={DATA_LAST_BRUSH_TIME: 1_700_000_000, DATA_LAST_BRUSH_SCORE: None},
        )
        assert sensor.available is True

    def test_session_key_before_first_session_is_available(self):
        """No session yet → can't declare field unsupported."""
        sensor = _make_sensor(
            DATA_LAST_BRUSH_SCORE,
            data={DATA_LAST_BRUSH_TIME: None, DATA_LAST_BRUSH_SCORE: None},
        )
        assert sensor.available is True

    def test_session_key_with_value_is_available(self):
        sensor = _make_sensor(
            DATA_LAST_BRUSH_SCORE,
            data={DATA_LAST_BRUSH_TIME: 1_700_000_000, DATA_LAST_BRUSH_SCORE: 85},
        )
        assert sensor.available is True

    def test_non_session_key_always_available(self):
        sensor = _make_sensor("battery", data={"battery": None, DATA_LAST_BRUSH_TIME: 123})
        assert sensor.available is True


# ---------------------------------------------------------------------------
# OcleanBrushAreasSensor
# ---------------------------------------------------------------------------


class TestOcleanBrushAreasSensor:
    def test_native_value_none_when_no_data(self):
        sensor = _make_areas_sensor(data=None)
        assert sensor.native_value is None

    def test_native_value_none_when_areas_missing(self):
        sensor = _make_areas_sensor(data={DATA_LAST_BRUSH_AREAS: None})
        assert sensor.native_value is None

    def test_native_value_counts_nonzero_zones(self):
        areas = {
            "upper_left_out": 100,
            "upper_left_in": 0,
            "lower_left_out": 80,
            "lower_left_in": 0,
        }
        sensor = _make_areas_sensor(data={DATA_LAST_BRUSH_AREAS: areas})
        assert sensor.native_value == 2

    def test_native_value_all_zeros_returns_zero(self):
        areas = dict.fromkeys(TOOTH_AREA_NAMES, 0)
        sensor = _make_areas_sensor(data={DATA_LAST_BRUSH_AREAS: areas})
        assert sensor.native_value == 0

    def test_extra_state_attributes_returns_areas_dict(self):
        areas = {"upper_left_out": 120, "lower_right_in": 50}
        sensor = _make_areas_sensor(data={DATA_LAST_BRUSH_AREAS: areas})
        assert sensor.extra_state_attributes == areas

    def test_extra_state_attributes_none_when_no_data(self):
        sensor = _make_areas_sensor(data=None)
        assert sensor.extra_state_attributes is None

    def test_available_returns_false_when_session_exists_but_areas_none(self):
        sensor = _make_areas_sensor(data={DATA_LAST_BRUSH_TIME: 1_700_000_000, DATA_LAST_BRUSH_AREAS: None})
        assert sensor.available is False

    def test_available_true_when_areas_present(self):
        areas = {"zone": 100}
        sensor = _make_areas_sensor(data={DATA_LAST_BRUSH_TIME: 1_700_000_000, DATA_LAST_BRUSH_AREAS: areas})
        assert sensor.available is True

    def test_available_stale_data_with_areas_returns_true(self):
        areas = {"zone": 50}
        sensor = _make_areas_sensor(data={DATA_LAST_BRUSH_AREAS: areas}, last_update_success=False)
        assert sensor.available is True

    def test_available_stale_data_no_areas_returns_false(self):
        sensor = _make_areas_sensor(data={DATA_LAST_BRUSH_AREAS: None}, last_update_success=False)
        assert sensor.available is False


# ---------------------------------------------------------------------------
# OcleanSchemeSensor
# ---------------------------------------------------------------------------


class TestOcleanSchemeSensor:
    def test_native_value_none_when_no_data(self):
        sensor = _make_scheme_sensor(data=None)
        assert sensor.native_value is None

    def test_native_value_none_when_pnum_missing(self):
        sensor = _make_scheme_sensor(data={DATA_LAST_BRUSH_PNUM: None})
        assert sensor.native_value is None

    def test_native_value_known_pnum_returns_name(self):
        pnum, name = next(iter(SCHEME_NAMES.items()))
        sensor = _make_scheme_sensor(data={DATA_LAST_BRUSH_PNUM: pnum})
        assert sensor.native_value == name

    def test_native_value_unknown_pnum_returns_string(self):
        unknown_pnum = 9999
        assert unknown_pnum not in SCHEME_NAMES
        sensor = _make_scheme_sensor(data={DATA_LAST_BRUSH_PNUM: unknown_pnum})
        assert sensor.native_value == str(unknown_pnum)

    def test_available_false_when_session_exists_pnum_none(self):
        sensor = _make_scheme_sensor(data={DATA_LAST_BRUSH_TIME: 1_700_000_000, DATA_LAST_BRUSH_PNUM: None})
        assert sensor.available is False

    def test_available_true_when_pnum_present(self):
        sensor = _make_scheme_sensor(data={DATA_LAST_BRUSH_TIME: 1_700_000_000, DATA_LAST_BRUSH_PNUM: 21})
        assert sensor.available is True

    def test_available_stale_with_value_returns_true(self):
        sensor = _make_scheme_sensor(data={DATA_LAST_BRUSH_PNUM: 21}, last_update_success=False)
        assert sensor.available is True

    def test_available_stale_no_value_returns_false(self):
        sensor = _make_scheme_sensor(data={DATA_LAST_BRUSH_PNUM: None}, last_update_success=False)
        assert sensor.available is False


# ---------------------------------------------------------------------------
# OcleanToothAreaSensor
# ---------------------------------------------------------------------------


class TestOcleanToothAreaSensor:
    _zone = TOOTH_AREA_NAMES[0]  # "upper_left_out"

    def test_native_value_none_when_no_data(self):
        sensor = _make_tooth_sensor(self._zone, data=None)
        assert sensor.native_value is None

    def test_native_value_none_when_areas_missing(self):
        sensor = _make_tooth_sensor(self._zone, data={DATA_LAST_BRUSH_AREAS: None})
        assert sensor.native_value is None

    def test_native_value_returns_zone_pressure(self):
        areas = {self._zone: 120}
        sensor = _make_tooth_sensor(self._zone, data={DATA_LAST_BRUSH_AREAS: areas})
        assert sensor.native_value == 120

    def test_native_value_none_when_zone_absent(self):
        # Areas dict present but this zone key missing
        sensor = _make_tooth_sensor(self._zone, data={DATA_LAST_BRUSH_AREAS: {}})
        assert sensor.native_value is None

    def test_translation_key_derived_from_zone(self):
        sensor = _make_tooth_sensor("upper_left_out", data=None)
        assert sensor._attr_translation_key == "zone_upper_left_out"

    def test_available_false_when_session_exists_no_areas(self):
        sensor = _make_tooth_sensor(
            self._zone,
            data={DATA_LAST_BRUSH_TIME: 1_700_000_000, DATA_LAST_BRUSH_AREAS: None},
        )
        assert sensor.available is False

    def test_available_true_when_areas_present(self):
        areas = {self._zone: 50}
        sensor = _make_tooth_sensor(
            self._zone,
            data={DATA_LAST_BRUSH_TIME: 1_700_000_000, DATA_LAST_BRUSH_AREAS: areas},
        )
        assert sensor.available is True

    def test_all_tooth_area_zones_instantiate(self):
        for zone in TOOTH_AREA_NAMES:
            sensor = _make_tooth_sensor(zone, data=None)
            assert sensor._zone_name == zone


# ---------------------------------------------------------------------------
# Helpers for new sensor classes
# ---------------------------------------------------------------------------


def _make_duration_rating_sensor(data=None, last_update_success=True):
    coord = _make_coordinator(data=data, last_update_success=last_update_success)
    return OcleanDurationRatingSensor(coord, "AA:BB:CC:DD:EE:FF", "Oclean")


def _make_pressure_detail_sensor(data=None, last_update_success=True):
    coord = _make_coordinator(data=data, last_update_success=last_update_success)
    return OcleanPressureDetailSensor(coord, "AA:BB:CC:DD:EE:FF", "Oclean")


def _make_power_distribution_sensor(data=None, last_update_success=True):
    coord = _make_coordinator(data=data, last_update_success=last_update_success)
    return OcleanPowerDistributionSensor(coord, "AA:BB:CC:DD:EE:FF", "Oclean")


class TestDiagnosticBlockTidyUp:
    """Diagnostic-block cleanup: meaningless raw fields hidden, coverage promoted."""

    def _desc(self, key):
        return next(d for d in SENSOR_DESCRIPTIONS if d.key == key)

    def test_coverage_is_primary_sensor(self):
        """Coverage is a meaningful brushing-quality metric → primary, not diagnostic."""
        assert self._desc(DATA_LAST_BRUSH_COVERAGE).entity_category is None

    def test_gesture_code_disabled_by_default(self):
        """gestureCode (0-3) has no confirmed meaning → hidden by default."""
        assert self._desc(DATA_LAST_BRUSH_GESTURE_CODE).entity_registry_enabled_default is False

    def test_pressure_detail_disabled_by_default(self):
        """Raw 5-bucket pressureRatio is superseded by the Pressure Level sensor."""
        assert OcleanPressureDetailSensor._attr_entity_registry_enabled_default is False

    def test_power_distribution_disabled_by_default(self):
        """powerArray (12x 0-3) meaning unconfirmed → hidden by default."""
        assert OcleanPowerDistributionSensor._attr_entity_registry_enabled_default is False


# ---------------------------------------------------------------------------
# OcleanDurationRatingSensor
# ---------------------------------------------------------------------------


class TestOcleanDurationRatingSensor:
    def test_none_when_no_data(self):
        sensor = _make_duration_rating_sensor(data=None)
        assert sensor.native_value is None

    def test_none_when_duration_missing(self):
        sensor = _make_duration_rating_sensor(data={DATA_LAST_BRUSH_DURATION: None})
        assert sensor.native_value is None

    def test_full_duration_returns_100(self):
        sensor = _make_duration_rating_sensor(data={DATA_LAST_BRUSH_DURATION: 240})
        assert sensor.native_value == 100

    def test_half_duration_returns_50(self):
        sensor = _make_duration_rating_sensor(data={DATA_LAST_BRUSH_DURATION: 120})
        assert sensor.native_value == 50

    def test_over_target_capped_at_100(self):
        sensor = _make_duration_rating_sensor(data={DATA_LAST_BRUSH_DURATION: 480})
        assert sensor.native_value == 100

    def test_zero_duration_returns_0(self):
        sensor = _make_duration_rating_sensor(data={DATA_LAST_BRUSH_DURATION: 0})
        assert sensor.native_value == 0

    def test_short_duration_rounds(self):
        # 60 / 240 * 100 = 25
        sensor = _make_duration_rating_sensor(data={DATA_LAST_BRUSH_DURATION: 60})
        assert sensor.native_value == 25

    def test_available_false_when_session_exists_no_duration(self):
        sensor = _make_duration_rating_sensor(
            data={DATA_LAST_BRUSH_TIME: 1_700_000_000, DATA_LAST_BRUSH_DURATION: None}
        )
        assert sensor.available is False

    def test_available_true_when_duration_present(self):
        sensor = _make_duration_rating_sensor(data={DATA_LAST_BRUSH_TIME: 1_700_000_000, DATA_LAST_BRUSH_DURATION: 120})
        assert sensor.available is True


# ---------------------------------------------------------------------------
# OcleanPressureDetailSensor
# ---------------------------------------------------------------------------


class TestOcleanPressureDetailSensor:
    _ratio = [10, 20, 30, 40, 50]

    def test_none_when_no_data(self):
        sensor = _make_pressure_detail_sensor(data=None)
        assert sensor.native_value is None

    def test_none_when_ratio_missing(self):
        sensor = _make_pressure_detail_sensor(data={DATA_LAST_BRUSH_PRESSURE_RATIO: None})
        assert sensor.native_value is None

    def test_none_when_ratio_wrong_length(self):
        sensor = _make_pressure_detail_sensor(data={DATA_LAST_BRUSH_PRESSURE_RATIO: [1, 2, 3]})
        assert sensor.native_value is None

    def test_returns_average(self):
        sensor = _make_pressure_detail_sensor(data={DATA_LAST_BRUSH_PRESSURE_RATIO: self._ratio})
        assert sensor.native_value == 30  # (10+20+30+40+50)/5

    def test_extra_state_attributes(self):
        sensor = _make_pressure_detail_sensor(data={DATA_LAST_BRUSH_PRESSURE_RATIO: self._ratio})
        attrs = sensor.extra_state_attributes
        assert attrs == {"segment_1": 10, "segment_2": 20, "segment_3": 30, "segment_4": 40, "segment_5": 50}

    def test_attributes_none_when_no_data(self):
        sensor = _make_pressure_detail_sensor(data=None)
        assert sensor.extra_state_attributes is None

    def test_available_false_when_session_exists_no_ratio(self):
        sensor = _make_pressure_detail_sensor(
            data={DATA_LAST_BRUSH_TIME: 1_700_000_000, DATA_LAST_BRUSH_PRESSURE_RATIO: None}
        )
        assert sensor.available is False

    def test_available_true_when_ratio_present(self):
        sensor = _make_pressure_detail_sensor(
            data={DATA_LAST_BRUSH_TIME: 1_700_000_000, DATA_LAST_BRUSH_PRESSURE_RATIO: self._ratio}
        )
        assert sensor.available is True


# ---------------------------------------------------------------------------
# OcleanPowerDistributionSensor
# ---------------------------------------------------------------------------


class TestOcleanPowerDistributionSensor:
    # 12 values: 8 matching TOOTH_AREA_NAMES + 4 extra
    _power = [3, 2, 0, 1, 3, 0, 2, 1, 0, 3, 1, 2]

    def test_none_when_no_data(self):
        sensor = _make_power_distribution_sensor(data=None)
        assert sensor.native_value is None

    def test_none_when_power_missing(self):
        sensor = _make_power_distribution_sensor(data={DATA_LAST_BRUSH_POWER_ARRAY: None})
        assert sensor.native_value is None

    def test_counts_nonzero_zones(self):
        sensor = _make_power_distribution_sensor(data={DATA_LAST_BRUSH_POWER_ARRAY: self._power})
        # [3,2,0,1,3,0,2,1,0,3,1,2] → 9 nonzero
        assert sensor.native_value == 9

    def test_extra_state_attributes_maps_zones(self):
        sensor = _make_power_distribution_sensor(
            data={DATA_LAST_BRUSH_POWER_ARRAY: self._power, DATA_LAST_BRUSH_GESTURE_ARRAY: [1, 2, 3]}
        )
        attrs = sensor.extra_state_attributes
        # First 8 values mapped to TOOTH_AREA_NAMES
        assert attrs[TOOTH_AREA_NAMES[0]] == 3
        assert attrs[TOOTH_AREA_NAMES[2]] == 0
        # Extra values indexed
        assert attrs["zone_9"] == 0
        assert attrs["zone_12"] == 2
        # Gesture array included
        assert attrs["gesture_array"] == [1, 2, 3]

    def test_attributes_without_gesture(self):
        sensor = _make_power_distribution_sensor(data={DATA_LAST_BRUSH_POWER_ARRAY: self._power})
        attrs = sensor.extra_state_attributes
        assert "gesture_array" not in attrs

    def test_attributes_none_when_no_data(self):
        sensor = _make_power_distribution_sensor(data=None)
        assert sensor.extra_state_attributes is None

    def test_available_false_when_session_exists_no_power(self):
        sensor = _make_power_distribution_sensor(
            data={DATA_LAST_BRUSH_TIME: 1_700_000_000, DATA_LAST_BRUSH_POWER_ARRAY: None}
        )
        assert sensor.available is False

    def test_available_true_when_power_present(self):
        sensor = _make_power_distribution_sensor(
            data={DATA_LAST_BRUSH_TIME: 1_700_000_000, DATA_LAST_BRUSH_POWER_ARRAY: self._power}
        )
        assert sensor.available is True

    def test_gesture_code_in_session_derived_keys(self):
        """Gesture code sensor should become unavailable when session exists but no gesture data."""
        sensor = _make_sensor(
            DATA_LAST_BRUSH_GESTURE_CODE,
            data={DATA_LAST_BRUSH_TIME: 1_700_000_000, DATA_LAST_BRUSH_GESTURE_CODE: None},
        )
        assert sensor.available is False


# ---------------------------------------------------------------------------
# OcleanDurationSensor – real brushed time + scheduled length as attribute
# ---------------------------------------------------------------------------


def _make_duration_sensor(data=None):
    from custom_components.oclean_ble.sensor import OcleanDurationSensor

    return OcleanDurationSensor(_make_coordinator(data=data), "AA:BB:CC:DD:EE:FF", "Oclean")


class TestOcleanDurationSensor:
    def test_state_is_the_real_brushed_time(self):
        from custom_components.oclean_ble.const import (
            DATA_LAST_BRUSH_DURATION_SCHEDULED,
        )

        sensor = _make_duration_sensor({DATA_LAST_BRUSH_DURATION: 31, DATA_LAST_BRUSH_DURATION_SCHEDULED: 180})
        assert sensor.native_value == 31

    def test_scheduled_length_exposed_as_attribute(self):
        from custom_components.oclean_ble.const import (
            DATA_LAST_BRUSH_DURATION_SCHEDULED,
        )

        sensor = _make_duration_sensor({DATA_LAST_BRUSH_DURATION: 31, DATA_LAST_BRUSH_DURATION_SCHEDULED: 180})
        assert sensor.extra_state_attributes == {"scheduled_duration_s": 180}

    def test_no_attribute_when_scheduled_unknown(self):
        # Layouts that do not expose validDuration report no scheduled length.
        sensor = _make_duration_sensor({DATA_LAST_BRUSH_DURATION: 120})
        assert sensor.extra_state_attributes is None

    def test_no_attribute_without_coordinator_data(self):
        sensor = _make_duration_sensor(None)
        assert sensor.extra_state_attributes is None

    def test_keeps_the_duration_entity_key(self):
        # Same key/unique_id as the previous description-driven sensor, so
        # existing entity history is preserved.
        sensor = _make_duration_sensor({})
        assert sensor.entity_description.key == DATA_LAST_BRUSH_DURATION
        assert sensor.entity_description.device_class == SensorDeviceClass.DURATION

    def test_duration_not_also_in_description_tuple(self):
        # Guard against the sensor being created twice (duplicate unique_id).
        assert all(d.key != DATA_LAST_BRUSH_DURATION for d in SENSOR_DESCRIPTIONS)


# -------------------------------------------------------------------------
# OcleanRssiSensor – advertisement RSSI, read from HA's Bluetooth registry
# ---------------------------------------------------------------------------


def _make_rssi_sensor():
    from custom_components.oclean_ble.sensor import OcleanRssiSensor

    coord = _make_coordinator(data={})
    sensor = OcleanRssiSensor(coord, "AA:BB:CC:DD:EE:FF", "Oclean")
    sensor.hass = MagicMock()
    return sensor


def _service_info(rssi=-70, source="proxy-kitchen"):
    info = MagicMock()
    info.rssi = rssi
    info.source = source
    return info


def _scanner_device(rssi, name):
    device = MagicMock()
    device.advertisement.rssi = rssi
    device.scanner.name = name
    return device


class TestOcleanRssiSensor:
    """The value comes from the Bluetooth registry, not from a BLE poll, so it
    stays meaningful while the brush is asleep and between polls."""

    def test_native_value_is_last_advertisement_rssi(self, monkeypatch):
        from homeassistant.components import bluetooth

        sensor = _make_rssi_sensor()
        monkeypatch.setattr(bluetooth, "async_last_service_info", MagicMock(return_value=_service_info(rssi=-83)))
        assert sensor.native_value == -83

    def test_native_value_none_when_never_seen(self, monkeypatch):
        from homeassistant.components import bluetooth

        sensor = _make_rssi_sensor()
        monkeypatch.setattr(bluetooth, "async_last_service_info", MagicMock(return_value=None))
        assert sensor.native_value is None

    def test_unavailable_when_never_seen(self, monkeypatch):
        from homeassistant.components import bluetooth

        sensor = _make_rssi_sensor()
        monkeypatch.setattr(bluetooth, "async_last_service_info", MagicMock(return_value=None))
        assert sensor.available is False

    def test_available_even_when_poll_failed(self, monkeypatch):
        # The advertisement is passive: a failed GATT poll must not make the
        # signal-strength sensor unavailable.
        from homeassistant.components import bluetooth

        from custom_components.oclean_ble.sensor import OcleanRssiSensor

        coord = _make_coordinator(data=None, last_update_success=False)
        sensor = OcleanRssiSensor(coord, "AA:BB:CC:DD:EE:FF", "Oclean")
        sensor.hass = MagicMock()
        monkeypatch.setattr(bluetooth, "async_last_service_info", MagicMock(return_value=_service_info()))
        assert sensor.available is True

    def test_attributes_expose_source_and_per_scanner_rssi(self, monkeypatch):
        from homeassistant.components import bluetooth

        sensor = _make_rssi_sensor()
        monkeypatch.setattr(
            bluetooth,
            "async_last_service_info",
            MagicMock(return_value=_service_info(rssi=-70, source="proxy-kitchen")),
        )
        monkeypatch.setattr(
            bluetooth,
            "async_scanner_devices_by_address",
            MagicMock(
                return_value=[
                    _scanner_device(-70, "proxy-kitchen"),
                    _scanner_device(-91, "proxy-bath"),
                ]
            ),
        )
        attrs = sensor.extra_state_attributes
        assert attrs["source"] == "proxy-kitchen"
        assert attrs["by_scanner"] == {"proxy-kitchen": -70, "proxy-bath": -91}

    def test_attributes_none_when_nothing_known(self, monkeypatch):
        from homeassistant.components import bluetooth

        sensor = _make_rssi_sensor()
        monkeypatch.setattr(bluetooth, "async_last_service_info", MagicMock(return_value=None))
        monkeypatch.setattr(bluetooth, "async_scanner_devices_by_address", MagicMock(return_value=[]))
        assert sensor.extra_state_attributes is None

    def test_scanner_without_advertisement_is_skipped(self, monkeypatch):
        from homeassistant.components import bluetooth

        sensor = _make_rssi_sensor()
        stale = MagicMock()
        stale.advertisement = None
        monkeypatch.setattr(bluetooth, "async_last_service_info", MagicMock(return_value=_service_info()))
        monkeypatch.setattr(
            bluetooth,
            "async_scanner_devices_by_address",
            MagicMock(return_value=[stale, _scanner_device(-77, "proxy-hall")]),
        )
        assert sensor.extra_state_attributes["by_scanner"] == {"proxy-hall": -77}

    def test_entity_metadata(self):
        from homeassistant.components.sensor import SensorStateClass
        from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory

        sensor = _make_rssi_sensor()
        assert sensor._attr_device_class == SensorDeviceClass.SIGNAL_STRENGTH
        assert sensor._attr_state_class == SensorStateClass.MEASUREMENT
        assert sensor._attr_native_unit_of_measurement == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
        assert sensor._attr_entity_category == EntityCategory.DIAGNOSTIC
        assert sensor._attr_translation_key == "rssi"

    @pytest.mark.asyncio
    async def test_registers_passive_advertisement_callback(self, monkeypatch):
        from homeassistant.components import bluetooth

        sensor = _make_rssi_sensor()
        register = MagicMock(return_value=lambda: None)
        monkeypatch.setattr(bluetooth, "async_register_callback", register)

        await sensor.async_added_to_hass()

        register.assert_called_once()
        matcher = register.call_args[0][2]
        assert matcher.address == "AA:BB:CC:DD:EE:FF"
        assert matcher.connectable is False
        assert register.call_args[0][3] == bluetooth.BluetoothScanningMode.PASSIVE
        # The unsubscribe callable is registered for teardown.
        assert len(sensor._on_remove_callbacks) == 1

    def test_advertisement_callback_pushes_state(self):
        sensor = _make_rssi_sensor()
        sensor.async_write_ha_state = MagicMock()
        sensor._advertisement_callback(MagicMock(), MagicMock())
        sensor.async_write_ha_state.assert_called_once()


class TestOcleanRssiSensorScannerNames:
    def test_scanner_without_name_falls_back_to_source(self, monkeypatch):
        from homeassistant.components import bluetooth

        sensor = _make_rssi_sensor()
        device = MagicMock()
        device.advertisement.rssi = -66
        device.scanner = MagicMock(spec=["source"])
        device.scanner.source = "AA:BB:CC:00:11:22"
        monkeypatch.setattr(bluetooth, "async_last_service_info", MagicMock(return_value=_service_info()))
        monkeypatch.setattr(bluetooth, "async_scanner_devices_by_address", MagicMock(return_value=[device]))

        assert sensor.extra_state_attributes["by_scanner"] == {"AA:BB:CC:00:11:22": -66}

    def test_scanner_without_name_or_source_uses_placeholder(self, monkeypatch):
        from homeassistant.components import bluetooth

        sensor = _make_rssi_sensor()
        device = MagicMock()
        device.advertisement.rssi = -66
        device.scanner = MagicMock(spec=[])
        monkeypatch.setattr(bluetooth, "async_last_service_info", MagicMock(return_value=_service_info()))
        monkeypatch.setattr(bluetooth, "async_scanner_devices_by_address", MagicMock(return_value=[device]))

        assert sensor.extra_state_attributes["by_scanner"] == {"?": -66}
