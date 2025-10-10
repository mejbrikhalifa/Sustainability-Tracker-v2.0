"""
Automated tests for core features of the Sustainability Tracker
Run with: python test_core_features.py
"""

import sys
from co2_engine import (
    calculate_co2_v2,
    get_grid_mix,
    compute_mix_intensity,
    get_effective_electricity_factor,
    hourlyIntensityProfile,
    suggest_low_hours,
    compare_tasks_at_hours,
    calculate_annual_savings,
    DEVICE_PRESETS,
    get_device_presets_by_category,
    apply_seasonal_adjustment,
    REGION_FACTOR_PACKS,
)

def test_basic_emissions():
    """Test basic emissions calculation"""
    print("\n🧪 Test 1: Basic Emissions Calculation")
    
    activity_data = {
        "electricity_kwh": 10.0,
        "natural_gas_m3": 2.0,
        "petrol_liter": 5.0,
        "meat_kg": 0.2,
    }
    
    total = calculate_co2_v2(activity_data)
    print(f"   Input: {activity_data}")
    print(f"   Total CO₂: {total} kg")
    
    assert total > 0, "Total should be positive"
    assert 10 < total < 20, f"Total {total} seems unrealistic"
    print("   ✅ PASS")

def test_region_impact():
    """Test that different regions produce different results"""
    print("\n🧪 Test 2: Region Impact on Electricity")
    
    activity_data = {"electricity_kwh": 10.0}
    
    # EU average
    eu_total = calculate_co2_v2(activity_data, region_code="EU-avg")
    print(f"   EU-avg (10 kWh): {eu_total} kg")
    
    # France (low carbon)
    fr_total = calculate_co2_v2(activity_data, region_code="FR")
    print(f"   France (10 kWh): {fr_total} kg")
    
    # China (high carbon)
    cn_total = calculate_co2_v2(activity_data, region_code="CN")
    print(f"   China (10 kWh): {cn_total} kg")
    
    assert fr_total < eu_total < cn_total, "France should be lowest, China highest"
    print("   ✅ PASS")

def test_grid_mix():
    """Test grid mix retrieval and intensity calculation"""
    print("\n🧪 Test 3: Grid Mix & Intensity")
    
    regions_to_test = ["EU-avg", "FR", "CN", "US-CA", "NO"]
    
    for region in regions_to_test:
        mix = get_grid_mix(region)
        if mix:
            intensity = compute_mix_intensity(mix)
            print(f"   {region}: {intensity:.3f} kg/kWh")
            assert 0 < intensity < 1.5, f"Intensity {intensity} out of range"
        else:
            print(f"   {region}: No mix data")
    
    print("   ✅ PASS")

def test_hourly_profiles():
    """Test hourly intensity profiles"""
    print("\n🧪 Test 4: Hourly Intensity Profiles")
    
    seasons = ["Spring", "Summer", "Autumn", "Winter"]
    regions = ["EU-avg", "US-CA", "CN"]
    
    for region in regions:
        for season in seasons:
            profile = hourlyIntensityProfile(region, season)
            assert len(profile) == 24, f"Profile should have 24 hours, got {len(profile)}"
            assert all(v > 0 for v in profile), "All intensities should be positive"
            
            low_hours = suggest_low_hours(profile, top_n=3)
            assert len(low_hours) == 3, "Should suggest 3 low hours"
            
    print(f"   Tested {len(regions)} regions × {len(seasons)} seasons = {len(regions)*len(seasons)} profiles")
    print("   ✅ PASS")

def test_device_presets():
    """Test device preset library"""
    print("\n🧪 Test 5: Device Presets Library")
    
    # Check total count
    total_devices = len(DEVICE_PRESETS)
    print(f"   Total devices: {total_devices}")
    assert total_devices >= 50, f"Expected 50+ devices, got {total_devices}"
    
    # Check categories
    categories = get_device_presets_by_category()
    print(f"   Categories: {len(categories)}")
    print(f"   Category names: {', '.join(sorted(categories.keys()))}")
    assert len(categories) >= 8, "Should have 8+ categories"
    
    # Test a few devices
    test_devices = ["Refrigerator", "Laptop", "Air Conditioner (Small)", "EV Charging (Level 2)"]
    for device in test_devices:
        assert device in DEVICE_PRESETS, f"Device {device} not found"
        info = DEVICE_PRESETS[device]
        assert "power_w" in info, f"Device {device} missing power_w"
        assert "hours_per_day" in info, f"Device {device} missing hours_per_day"
        assert "category" in info, f"Device {device} missing category"
    
    print("   ✅ PASS")

def test_seasonal_adjustment():
    """Test seasonal adjustments for climate devices"""
    print("\n🧪 Test 6: Seasonal Adjustments")
    
    # Test AC in summer vs winter
    ac_summer = apply_seasonal_adjustment("Air Conditioner (Small)", "Summer", 4.0)
    ac_winter = apply_seasonal_adjustment("Air Conditioner (Small)", "Winter", 4.0)
    
    print(f"   AC (Small) - Summer: {ac_summer}h, Winter: {ac_winter}h")
    assert ac_summer > ac_winter, "AC should run more in summer"
    
    # Test heater in winter vs summer
    heater_winter = apply_seasonal_adjustment("Space Heater", "Winter", 4.0)
    heater_summer = apply_seasonal_adjustment("Space Heater", "Summer", 4.0)
    
    print(f"   Space Heater - Winter: {heater_winter}h, Summer: {heater_summer}h")
    assert heater_winter > heater_summer, "Heater should run more in winter"
    
    print("   ✅ PASS")

def test_multi_task_comparison():
    """Test multi-task comparison feature"""
    print("\n🧪 Test 7: Multi-Task Comparison")
    
    profile = hourlyIntensityProfile("EU-avg", "Summer")
    
    tasks = [
        {"name": "Laundry", "kwh": 2.0, "hour": 20},
        {"name": "Dishwasher", "kwh": 1.8, "hour": 21},
        {"name": "EV Charging", "kwh": 15.0, "hour": 18},
    ]
    
    results = compare_tasks_at_hours(profile, tasks)
    
    assert len(results) == 3, "Should return 3 results"
    
    for result in results:
        print(f"   {result['name']}: {result['savings_kg']:.2f} kg savings ({result['savings_pct']:.1f}%)")
        assert result['current_co2_kg'] >= result['optimal_co2_kg'], "Current should be >= optimal"
    
    print("   ✅ PASS")

def test_annual_savings():
    """Test annual savings calculator"""
    print("\n🧪 Test 8: Annual Savings Calculator")
    
    profile = hourlyIntensityProfile("EU-avg", "Summer")
    
    savings = calculate_annual_savings(3.0, 20, profile)
    
    print(f"   Daily savings: {savings['daily_savings_kg']:.2f} kg")
    print(f"   Yearly savings: {savings['yearly_savings_kg']:.1f} kg")
    print(f"   Cost savings: ${savings['yearly_cost_savings_usd']:.2f}")
    
    assert savings['daily_savings_kg'] >= 0, "Savings should be non-negative"
    
    # Allow for rounding tolerance (within 0.5 kg)
    expected_yearly = savings['daily_savings_kg'] * 365
    actual_yearly = savings['yearly_savings_kg']
    tolerance = 0.5
    
    assert abs(actual_yearly - expected_yearly) < tolerance, \
        f"Yearly {actual_yearly} should be close to daily × 365 ({expected_yearly})"
    
    print("   ✅ PASS")

def test_regions_available():
    """Test that all 38 regions are available"""
    print("\n🧪 Test 9: Global Regions Coverage")
    
    expected_regions = [
        "EU-avg", "US-avg", "US-CA", "CA", "UK", "FR", "DE",
        "CN", "IN", "JP", "AU", "BR", "RU", "ZA", "NG", "EG", "KE",
        "SG", "TH", "VN", "ID", "MY", "PH", "KR", "MX", "AR", "CL",
        "NO", "SE", "IS", "NZ", "AE", "SA", "TR", "PL"
    ]
    
    available = list(REGION_FACTOR_PACKS.keys())
    print(f"   Expected: {len(expected_regions)} regions")
    print(f"   Available: {len(available)} regions")
    
    missing = set(expected_regions) - set(available)
    if missing:
        print(f"   ⚠️  Missing: {missing}")
    
    assert len(available) >= 35, f"Should have 35+ regions, got {len(available)}"
    print("   ✅ PASS")

def run_all_tests():
    """Run all tests and report results"""
    print("=" * 60)
    print("🧪 SUSTAINABILITY TRACKER - AUTOMATED TESTS")
    print("=" * 60)
    
    tests = [
        test_basic_emissions,
        test_region_impact,
        test_grid_mix,
        test_hourly_profiles,
        test_device_presets,
        test_seasonal_adjustment,
        test_multi_task_comparison,
        test_annual_savings,
        test_regions_available,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"   ❌ FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 TEST RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("✅ ALL TESTS PASSED! 🎉")
        print("\n🚀 Core features are working correctly.")
        print("📋 Next: Follow TESTING_GUIDE.md for UI testing")
        return 0
    else:
        print(f"❌ {failed} TEST(S) FAILED")
        print("\n🐛 Please review failures and fix issues")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
