"""Unit tests for the HA-free custom-programme helpers."""

import pytest

from custom_components.oclean_ble.program_utils import (
    MAX_CUSTOM_PNUM,
    MAX_CUSTOM_STEPS,
    MIN_CUSTOM_PNUM,
    next_free_pnum,
    validate_program_steps,
)


def test_next_free_pnum_empty_returns_min():
    assert next_free_pnum([]) == MIN_CUSTOM_PNUM


def test_next_free_pnum_skips_used():
    assert next_free_pnum([120, 121, 123]) == 122


def test_next_free_pnum_ignores_preset_range():
    # presets (0, 72-104) never occupy the custom range
    assert next_free_pnum([0, 72, 90, 104]) == MIN_CUSTOM_PNUM


def test_next_free_pnum_accepts_str_keys():
    # store keys are strings (JSON); allocation must coerce
    assert next_free_pnum(["120", "121"]) == 122


def test_next_free_pnum_exhausted_raises():
    full = list(range(MIN_CUSTOM_PNUM, MAX_CUSTOM_PNUM + 1))
    with pytest.raises(ValueError):
        next_free_pnum(full)


def test_validate_ok():
    validate_program_steps([(8, 30), (20, 30), (33, 30)])  # no raise


def test_validate_max_steps_ok():
    validate_program_steps([(2, 30)] * MAX_CUSTOM_STEPS)  # exactly the max


def test_validate_empty_raises():
    with pytest.raises(ValueError):
        validate_program_steps([])


def test_validate_too_many_steps_raises():
    with pytest.raises(ValueError):
        validate_program_steps([(2, 30)] * (MAX_CUSTOM_STEPS + 1))


@pytest.mark.parametrize("gear", [0, 42, -1, 100])
def test_validate_bad_gear_raises(gear):
    with pytest.raises(ValueError):
        validate_program_steps([(gear, 30)])


@pytest.mark.parametrize("dur", [0, 256, -5])
def test_validate_bad_duration_raises(dur):
    with pytest.raises(ValueError):
        validate_program_steps([(8, dur)])
