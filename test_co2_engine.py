import math
import json
import os
import pytest

from co2_engine import (
    calculate_co2_v2,
    calculate_co2_breakdown_v2,
    get_effective_electricity_factor,
    get_grid_mix,
    compute_mix_intensity,
    REGION_FACTOR_PACKS,
)


def test_calculate_co2_v2_basic_default_factor():
    data = {"electricity_kwh": 10.0, "bus_km": 5.0}
    # default electricity: 0.233, bus: 0.12
    expected = round(10.0 * 0.233 + 5.0 * 0.12, 2)
    assert calculate_co2_v2(data) == expected


def test_calculate_co2_v2_region_override_fr():
    data = {"electricity_kwh": 10.0}
    # FR override: 0.07
    assert calculate_co2_v2(data, region_code="FR") == round(10.0 * 0.07, 2)


def test_calculate_co2_breakdown_v2_keys():
    data = {"electricity_kwh": 2.0, "meat_kg": 0.1}
    br = calculate_co2_breakdown_v2(data)
    # normalized keys
    assert "electricity_kwh" in br and "meat_kg" in br
    assert br["electricity_kwh"] > 0 and br["meat_kg"] > 0


def test_get_effective_electricity_factor_default_with_adjust():
    ef = get_effective_electricity_factor(region_code=None, renewable_adjust=0.5)
    # default 0.233 * (1-0.5) = 0.1165
    assert abs(ef - 0.1165) < 1e-6


def test_get_grid_mix_and_normalization():
    mix = get_grid_mix("EU-avg")
    assert isinstance(mix, dict)
    if mix:
        total = sum(mix.values())
        assert abs(total - 1.0) < 1e-6


def test_compute_mix_intensity_numeric():
    mix = {"coal": 0.5, "wind": 0.5}
    val = compute_mix_intensity(mix)
    assert isinstance(val, float)
    assert val > 0


def test_region_packs_loaded_from_json_or_default():
    # Ensure dict present with at least one region
    assert isinstance(REGION_FACTOR_PACKS, dict)
    assert len(REGION_FACTOR_PACKS) > 0
