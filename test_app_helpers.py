import pytest

from app_helpers import _coerce_float, has_meaningful_input, find_invalid_fields, should_generate_tip


def test__coerce_float_basic():
    assert _coerce_float(1) == 1.0
    assert _coerce_float("2.5") == 2.5
    assert _coerce_float("abc") is None


def test_has_meaningful_input_true_when_any_positive():
    assert has_meaningful_input({"a": 0, "b": 1}) is True
    assert has_meaningful_input({"a": "0", "b": "3.2"}) is True


def test_has_meaningful_input_false_when_all_zero_or_invalid():
    assert has_meaningful_input({"a": 0, "b": 0}) is False
    assert has_meaningful_input({"a": "x", "b": None}) is False


def test_find_invalid_fields_flags_negative_and_non_numeric():
    inv = find_invalid_fields({"x": -1, "y": "abc", "z": 0})
    assert set(inv) == {"x", "y"}


def test_should_generate_tip_false_on_invalid():
    data = {"x": -1, "y": 2}
    assert should_generate_tip(data) is False


def test_should_generate_tip_true_on_valid_and_meaningful():
    data = {"x": 0, "y": 1.5}
    assert should_generate_tip(data) is True
