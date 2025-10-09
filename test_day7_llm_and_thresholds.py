import importlib
import types

import pytest

# Import the module under test
import ai_tips as tips


def test_set_llm_params_updates_globals():
    # Pre-conditions: capture originals
    orig_tip_temp = getattr(tips, "_TIP_TEMPERATURE", None)
    orig_tip_max = getattr(tips, "_TIP_MAX_TOKENS", None)
    orig_sum_temp = getattr(tips, "_SUM_TEMPERATURE", None)
    orig_sum_max = getattr(tips, "_SUM_MAX_TOKENS", None)

    try:
        # Act
        tips.set_llm_params(tip_temperature=0.33, tip_max_tokens=123, summary_temperature=0.77, summary_max_tokens=456)

        # Assert
        assert tips._TIP_TEMPERATURE == pytest.approx(0.33)
        assert tips._TIP_MAX_TOKENS == 123
        assert tips._SUM_TEMPERATURE == pytest.approx(0.77)
        assert tips._SUM_MAX_TOKENS == 456
    finally:
        # Restore
        if orig_tip_temp is not None:
            tips._TIP_TEMPERATURE = orig_tip_temp
        if orig_tip_max is not None:
            tips._TIP_MAX_TOKENS = orig_tip_max
        if orig_sum_temp is not None:
            tips._SUM_TEMPERATURE = orig_sum_temp
        if orig_sum_max is not None:
            tips._SUM_MAX_TOKENS = orig_sum_max


def test_thresholds_update_and_clamp_train_km():
    # Ensure thresholds contain train_km and set a specific value
    new_thr = {"train_km": 1000.0}
    tips.set_extreme_thresholds(new_thr)

    # The internal EXTREME_THRESHOLDS should now reflect the value
    assert float(tips.EXTREME_THRESHOLDS.get("train_km")) == 1000.0

    # Inputs beyond the limit should be clamped by sanitize_inputs_for_prompt
    raw = {"train_km": 50000.0, "bus_km": 10.0}
    safe = tips.sanitize_inputs_for_prompt(raw)

    assert safe["train_km"] == 1000.0  # clamped
    assert safe["bus_km"] == 10.0      # unchanged


def test_sanitize_filters_unexpected_keys_and_negatives():
    raw = {
        "electricity_kwh": -5,   # negative -> coerced to 0
        "unknown_key": 123,      # dropped
        "note": "🚗🍔💡",         # dropped (non-allowed)
        "meat_kg": 0.25,         # kept
    }
    safe = tips.sanitize_inputs_for_prompt(raw)

    assert "unknown_key" not in safe
    assert "note" not in safe
    assert safe["electricity_kwh"] == 0.0
    assert safe["meat_kg"] == pytest.approx(0.25)
