"""Unit tests for the HA-free statistics helpers.

Covers:
  * P2.2 – statistic units mirror the SensorEntityDescription units: score is
    dimensionless (NOT "%"), duration is presented in the sensor's displayed
    unit (minutes), pressure is dimensionless.
  * P2.3 – multiple sessions that fall in the same UTC hour are aggregated by
    mean into one bucket instead of emitting duplicate-start rows (which HA
    would collapse, silently dropping all but one).
"""

from oclean_ble.const import (
    DATA_LAST_BRUSH_DURATION,
    DATA_LAST_BRUSH_PRESSURE,
    DATA_LAST_BRUSH_SCORE,
)
from oclean_ble.statistics import aggregate_hourly, statistic_unit, statistic_value


# --- P2.2: units derived from the sensor descriptions -----------------------


def test_score_unit_is_dimensionless():
    # The score live-sensor has no native_unit_of_measurement -> statistic None.
    assert statistic_unit(DATA_LAST_BRUSH_SCORE) is None


def test_duration_unit_is_minutes():
    # The duration live-sensor is displayed in minutes (suggested_unit).
    assert statistic_unit(DATA_LAST_BRUSH_DURATION) == "min"


def test_pressure_unit_is_dimensionless():
    assert statistic_unit(DATA_LAST_BRUSH_PRESSURE) is None


def test_score_value_passthrough():
    assert statistic_value(DATA_LAST_BRUSH_SCORE, 80) == 80


def test_duration_value_converted_to_minutes():
    # Raw seconds must be presented in the declared unit (minutes).
    assert statistic_value(DATA_LAST_BRUSH_DURATION, 120) == 2.0


def test_pressure_value_passthrough():
    assert statistic_value(DATA_LAST_BRUSH_PRESSURE, 2.5) == 2.5


# --- P2.3: hourly aggregation ------------------------------------------------


def test_aggregate_hourly_merges_same_hour_by_mean():
    # Two sessions in the 01:00 UTC hour must merge to their mean; the 02:00
    # session stays separate.
    result = aggregate_hourly([(3600, 10.0), (3601, 20.0), (7200, 5.0)])
    assert result == [(3600, 15.0), (7200, 5.0)]


def test_aggregate_hourly_single_per_hour_preserves_values():
    result = aggregate_hourly([(3600, 42.0), (7200, 7.0)])
    assert result == [(3600, 42.0), (7200, 7.0)]


def test_aggregate_hourly_floors_to_hour_boundary():
    # A timestamp mid-hour must be floored to the top of its UTC hour.
    result = aggregate_hourly([(3600 + 1800, 9.0)])
    assert result == [(3600, 9.0)]


def test_aggregate_hourly_empty():
    assert aggregate_hourly([]) == []


def test_aggregate_hourly_sorted_by_hour():
    result = aggregate_hourly([(7200, 1.0), (3600, 2.0)])
    assert [hour for hour, _ in result] == [3600, 7200]
