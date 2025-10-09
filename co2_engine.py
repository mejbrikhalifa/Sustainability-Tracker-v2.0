"""
co2_engine.py

A small engine to estimate CO₂ emissions from daily activities.

- CO2_FACTORS contains emission factors (kg CO₂ per unit) for supported activities.
- calculate_co2(activity_data) returns the total emissions in kilograms of CO₂.
- calculate_co2_breakdown(activity_data) (optional) returns per-activity emissions
  for deeper insights and debugging.

Notes for readers:
- Keys in activity_data should match the factor keys (e.g., "electricity_kWh").
- We normalize input keys (lowercase, underscores) so "Electricity (kWh)" → "electricity_kWh" still matches.
- Factors are illustrative and can be adapted to local datasets (EPA/IPCC, supplier-specific, etc.).
"""

from typing import Dict, Mapping, Optional, List
import os
import json
from utils import normalize_activity_name

# Emission factors in kg CO₂ per unit.
# You can adjust these values based on your country/utility factors or published datasets.
CO2_FACTORS: Dict[str, float] = {
    # Energy
    "electricity_kwh": 0.233,        # per kWh
    "natural_gas_m3": 2.03,          # per cubic meter
    "hot_water_liter": 0.25,         # per liter (includes energy for heating water)
    "cold_water_liter": 0.075,       # per liter (pumping/treatment, if desired)
    "district_heating_kwh": 0.15,    # per kWh
    "propane_liter": 1.51,           # per liter
    "fuel_oil_liter": 2.52,          # per liter

    # Transport
    "petrol_liter": 0.235,           # per liter gasoline
    "diesel_liter": 0.268,           # per liter diesel
    "bus_km": 0.12,                  # per km
    "train_km": 0.14,                # per km (very rough average)
    "bicycle_km": 0.0,               # cycling assumed zero direct emissions
    "flight_short_km": 0.275,        # per km (short-haul average)
    "flight_long_km": 0.175,         # per km (long-haul average)

    # Meals (food mass consumed in kg)
    "meat_kg": 27.0,
    "chicken_kg": 6.9,
    "eggs_kg": 4.8,
    "dairy_kg": 13.0,
    "vegetarian_kg": 2.0,
    "vegan_kg": 1.5,
}


def _get_factor(activity_key: str) -> Optional[float]:
    """
    Return the emission factor for an activity, after normalizing its key.

    We accept flexible keys (e.g., "Electricity (kWh)") by normalizing them into
    the canonical format used by CO2_FACTORS.
    """
    normalized = normalize_activity_name(activity_key)
    return CO2_FACTORS.get(normalized)


def calculate_co2(activity_data: Mapping[str, float]) -> float:
    """
    Calculate total CO₂ emissions for a set of activities.

    Parameters
    - activity_data: mapping of activity key to amount used/done for the day.
      Example:
          {"electricity_kWh": 4.2, "bus_km": 12, "meat_kg": 0.15}

    Returns
    - Total emissions (kg CO₂) rounded to 2 decimals.

    Behavior
    - Non-numeric or negative amounts are ignored with a warning.
    - Unknown activity keys are ignored with a warning.
    """
    total_emissions = 0.0

    for activity, amount in activity_data.items():
        factor = _get_factor(activity)
        if factor is None:
            print(f"⚠️ Warning: '{activity}' not found in CO2_FACTORS")
            continue

        # Coerce amount to float and guard against negatives
        try:
            amt_val = float(amount)
        except (TypeError, ValueError):
            print(f"⚠️ Warning: amount for '{activity}' is not numeric; skipping.")
            continue

        if amt_val < 0:
            print(f"⚠️ Warning: negative amount for '{activity}' ({amt_val}); treating as 0.")
            amt_val = 0.0

        total_emissions += factor * amt_val

    return round(total_emissions, 2)


def calculate_co2_breakdown(activity_data: Mapping[str, float]) -> Dict[str, float]:
    """
    Return per-activity emissions (kg CO₂) for insight and debugging.

    Unknown or invalid entries are skipped.
    Keys are returned in their normalized form.
    """
    breakdown: Dict[str, float] = {}

    for activity, amount in activity_data.items():
        normalized = normalize_activity_name(activity)
        factor = CO2_FACTORS.get(normalized)
        if factor is None:
            continue

        try:
            amt_val = float(amount)
        except (TypeError, ValueError):
            continue

        if amt_val < 0:
            amt_val = 0.0

        kg = factor * amt_val
        if kg:
            # more precision here to help users debug contributions
            breakdown[normalized] = round(kg, 4)

    return breakdown
def _clamp_fraction(x: Optional[float]) -> float:
    try:
        xf = float(x) if x is not None else 0.0
    except Exception:
        return 0.0
    return max(0.0, min(1.0, xf))

def _region_overlay(region_code: Optional[str]) -> Dict[str, float]:
    if not region_code:
        return {}
    pack = REGION_FACTOR_PACKS.get(str(region_code).strip())
    if not pack:
        return {}
    return dict(pack.get("factors", {}))  # shallow copy

def get_engine_meta(region_code: Optional[str]) -> Dict[str, str]:
    """Expose factor source metadata for UI captions."""
    meta = {
        "source": "Default factors",
        "version": "n/a",
        "url": "",
        "region_code": str(region_code or "default"),
    }
    pack = REGION_FACTOR_PACKS.get(str(region_code).strip()) if region_code else None
    if pack and "__meta__" in pack:
        meta.update({k: str(v) for k, v in pack["__meta__"].items()})
    return meta

def calculate_co2_v2(
    activity_data: Mapping[str, float],
    *,
    region_code: Optional[str] = None,
    renewable_adjust: Optional[float] = None,
) -> float:
    """
    Total kg CO₂ with optional regional overlay and renewable adjustment for electricity.
    - region_code: if provided and known, overrides electricity factor.
    - renewable_adjust: fraction [0..1] that reduces the electricity factor when no region overlay applies.
    """
    overlay = _region_overlay(region_code)
    adj = _clamp_fraction(renewable_adjust)
    total = 0.0
    for activity, amount in activity_data.items():
        norm = normalize_activity_name(activity)
        factor = CO2_FACTORS.get(norm)
        if factor is None:
            continue
        try:
            amt = float(amount)
        except Exception:
            continue
        if amt < 0:
            amt = 0.0

        if norm == "electricity_kwh":
            ef = overlay.get("electricity_kwh", factor)
            if "electricity_kwh" not in overlay and adj > 0.0:
                ef = ef * (1.0 - adj)
            total += ef * amt
        else:
            total += factor * amt
    return round(total, 2)


def calculate_co2_breakdown_v2(
    activity_data: Mapping[str, float],
    *,
    region_code: Optional[str] = None,
    renewable_adjust: Optional[float] = None,
) -> Dict[str, float]:
    """
    Per-activity kg CO₂ with same rules as calculate_co2_v2.
    """
    overlay = _region_overlay(region_code)
    adj = _clamp_fraction(renewable_adjust)
    out: Dict[str, float] = {}
    for activity, amount in activity_data.items():
        norm = normalize_activity_name(activity)
        factor = CO2_FACTORS.get(norm)
        if factor is None:
            continue
        try:
            amt = float(amount)
        except Exception:
            continue
        if amt < 0:
            amt = 0.0

        ef = factor
        if norm == "electricity_kwh":
            ef = overlay.get("electricity_kwh", factor)
            if "electricity_kwh" not in overlay and adj > 0.0:
                ef = ef * (1.0 - adj)

        kg = ef * amt
        if kg:
            out[norm] = round(kg, 4)
    return out


# ------------------------------
# Regional packs and grid mixes
# ------------------------------
# Default illustrative regional overlays. Each pack may provide an electricity
# factor override and an optional generation mix breakdown (shares sum to ~1.0).
DEFAULT_REGION_PACKS: Dict[str, dict] = {
    "EU-avg": {
        "__meta__": {"source": "Illustrative EU avg", "version": "2024.1", "url": ""},
        "factors": {"electricity_kwh": 0.28},
        "grid_mix": {"coal": 0.15, "gas": 0.20, "nuclear": 0.25, "hydro": 0.15, "wind": 0.18, "solar": 0.07},
    },
    "US-avg": {
        "__meta__": {"source": "Illustrative US avg", "version": "2024.1", "url": ""},
        "factors": {"electricity_kwh": 0.40},
        "grid_mix": {"coal": 0.20, "gas": 0.38, "nuclear": 0.19, "hydro": 0.07, "wind": 0.11, "solar": 0.05},
    },
    "FR": {
        "__meta__": {"source": "Illustrative France", "version": "2024.1", "url": ""},
        "factors": {"electricity_kwh": 0.07},
        "grid_mix": {"nuclear": 0.66, "hydro": 0.12, "wind": 0.10, "solar": 0.06, "gas": 0.04, "coal": 0.02},
    },
}

def _load_region_packs_from_json() -> Dict[str, dict]:
    """Load region factor packs from data/regions.json if available.
    Returns DEFAULT_REGION_PACKS on any error.
    """
    try:
        data_path = os.path.join(os.path.dirname(__file__), "data", "regions.json")
        if os.path.exists(data_path):
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data:
                    return data  # trust JSON structure
    except Exception:
        pass
    return DEFAULT_REGION_PACKS

# Public pack variable used by the engine and UI
REGION_FACTOR_PACKS: Dict[str, dict] = _load_region_packs_from_json()

# Approximate source intensities in kg CO2 per kWh, for illustrative implied intensity.
SOURCE_INTENSITIES: Dict[str, float] = {
    "coal": 0.9,
    "gas": 0.45,
    "oil": 0.7,
    "nuclear": 0.012,
    "hydro": 0.01,
    "wind": 0.01,
    "solar": 0.05,
    "biomass": 0.10,
}

def get_grid_mix(region_code: Optional[str]) -> Dict[str, float]:
    """Return generation mix shares for a region if available.
    Keys are lowercase source names; values are fractions [0..1].
    """
    if not region_code:
        return {}
    pack = REGION_FACTOR_PACKS.get(str(region_code).strip())
    if not pack:
        return {}
    mix = pack.get("grid_mix", {})
    # Validate and normalize
    out: Dict[str, float] = {}
    for k, v in mix.items():
        try:
            out[str(k).lower()] = max(0.0, float(v))
        except Exception:
            continue
    total = sum(out.values())
    if total > 0:
        return {k: v / total for k, v in out.items()}
    return out

def compute_mix_intensity(mix: Dict[str, float]) -> float:
    """Compute implied kg CO2/kWh from a generation mix using SOURCE_INTENSITIES.
    Unknown sources are ignored. Returns a rounded value with 3 decimals.
    """
    total = 0.0
    for src, share in mix.items():
        try:
            s = float(share)
        except Exception:
            continue
        if s <= 0:
            continue
        intensity = SOURCE_INTENSITIES.get(str(src).lower())
        if intensity is None:
            continue
        total += s * float(intensity)
    return round(total, 3)


def get_effective_electricity_factor(
    region_code: Optional[str],
    renewable_adjust: Optional[float],
) -> float:
    """Return the effective kg CO₂/kWh for electricity given UI settings.

    Rules:
    - If a known region overlay exists, return its electricity factor.
    - Otherwise, apply a fractional reduction [0..1] to the default electricity factor.
    - All inputs are clamped/validated; always returns a non-negative float.
    """
    base_ef = float(CO2_FACTORS.get("electricity_kwh", 0.233))
    overlay = _region_overlay(region_code)
    if "electricity_kwh" in overlay:
        try:
            return float(overlay.get("electricity_kwh", base_ef))
        except Exception:
            return base_ef
    # No overlay; apply renewable adjustment
    adj = _clamp_fraction(renewable_adjust)
    try:
        return max(0.0, base_ef * (1.0 - float(adj)))
    except Exception:
        return base_ef


# -----------------------------------------
# Hourly/Seasonal carbon intensity profiles
# -----------------------------------------
# Simple illustrative 24h shapes (not real-time). Values are relative and will
# be normalized to average 1.0 and then scaled to the region's implied intensity.
HOURLY_PROFILE_SHAPES: Dict[str, List[float]] = {
    # Nearly flat day
    "flat": [
        1.0, 0.99, 0.98, 0.98, 0.97, 0.98, 1.0, 1.02, 1.05, 1.08, 1.10, 1.08,
        1.05, 1.02, 1.00, 0.98, 0.97, 0.98, 1.00, 1.03, 1.06, 1.08, 1.05, 1.02,
    ],
    # Summer-like: evening peak (AC usage)
    "evening_peak": [
        0.85, 0.83, 0.82, 0.82, 0.83, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15,
        1.20, 1.25, 1.28, 1.30, 1.25, 1.20, 1.15, 1.10, 1.05, 1.00, 0.95, 0.90,
    ],
    # Winter-like: morning + evening peaks (heating)
    "winter_dual_peak": [
        0.90, 0.88, 0.86, 0.85, 0.88, 0.95, 1.05, 1.15, 1.10, 1.00, 0.95, 0.92,
        0.95, 1.05, 1.20, 1.30, 1.25, 1.15, 1.05, 1.00, 0.95, 0.93, 0.92, 0.91,
    ],
    # Spring: renewable-heavy with low midday (solar peak)
    "spring_solar": [
        0.95, 0.93, 0.91, 0.90, 0.92, 0.98, 1.05, 1.08, 1.02, 0.88, 0.75, 0.70,
        0.68, 0.72, 0.80, 0.92, 1.05, 1.12, 1.15, 1.10, 1.05, 1.02, 1.00, 0.98,
    ],
    # Autumn: transition period with moderate variation
    "autumn_transition": [
        0.92, 0.90, 0.88, 0.87, 0.89, 0.94, 1.00, 1.08, 1.10, 1.05, 1.00, 0.96,
        0.95, 1.00, 1.08, 1.15, 1.18, 1.12, 1.05, 1.00, 0.98, 0.96, 0.94, 0.93,
    ],
    # Solar-heavy regions (CA, AU): low midday, high evening
    "solar_heavy": [
        1.05, 1.03, 1.01, 1.00, 1.02, 1.08, 1.12, 1.15, 1.08, 0.85, 0.65, 0.55,
        0.52, 0.58, 0.72, 0.95, 1.15, 1.28, 1.35, 1.30, 1.20, 1.15, 1.12, 1.08,
    ],
    # Wind-heavy regions (NO, UK, DE): variable with night lows
    "wind_heavy": [
        0.88, 0.85, 0.83, 0.82, 0.85, 0.92, 1.00, 1.10, 1.15, 1.12, 1.08, 1.05,
        1.03, 1.08, 1.15, 1.20, 1.18, 1.12, 1.05, 1.00, 0.98, 0.95, 0.92, 0.90,
    ],
    # Coal-heavy regions (PL, IN, CN): flatter with modest peaks
    "coal_heavy": [
        0.98, 0.97, 0.96, 0.95, 0.96, 0.98, 1.00, 1.05, 1.08, 1.10, 1.12, 1.10,
        1.08, 1.10, 1.12, 1.15, 1.12, 1.08, 1.05, 1.03, 1.02, 1.01, 1.00, 0.99,
    ],
}


def _normalize_shape_to_avg_one(shape: List[float]) -> List[float]:
    vals = [max(0.0, float(x)) for x in shape]
    avg = sum(vals) / len(vals) if vals else 1.0
    if avg <= 0:
        return [1.0 for _ in range(24)]
    return [x / avg for x in vals]

def _get_region_profile_type(region_code: Optional[str]) -> str:
    """Determine the best hourly profile type based on region's grid mix characteristics."""
    if not region_code:
        return "default"
    
    mix = get_grid_mix(region_code)
    if not mix:
        return "default"
    
    # Calculate renewable shares
    solar_share = mix.get("solar", 0.0)
    wind_share = mix.get("wind", 0.0)
    coal_share = mix.get("coal", 0.0)
    
    # Solar-heavy: >15% solar
    if solar_share > 0.15:
        return "solar_heavy"
    
    # Wind-heavy: >20% wind
    if wind_share > 0.20:
        return "wind_heavy"
    
    # Coal-heavy: >50% coal
    if coal_share > 0.50:
        return "coal_heavy"
    
    return "default"

def hourlyIntensityProfile(regionCode: Optional[str], season: str) -> List[float]:
    """Return a 24-element list of kg CO2/kWh for the given region and season.

    - Uses region grid mix (if available) to compute implied base intensity via
      compute_mix_intensity(). Falls back to effective factor if mix missing.
    - Applies a simple season-specific shape and scales to the base intensity.
    """
    # Base intensity from mix if available; else from effective factor.
    mix = get_grid_mix(regionCode)
    implied = compute_mix_intensity(mix) if mix else None
    if implied is None:
        try:
            implied = float(
                get_effective_electricity_factor(regionCode, None)  # already in kg/kWh
            )
        except Exception:
            implied = float(CO2_FACTORS.get("electricity_kwh", 0.233))

    # Choose shape by season and region characteristics
    season_key = str(season or "").lower()
    region_type = _get_region_profile_type(regionCode)
    
    # Priority 1: Region-specific patterns override seasonal defaults
    if region_type == "solar_heavy":
        raw_shape = HOURLY_PROFILE_SHAPES["solar_heavy"]
    elif region_type == "wind_heavy":
        raw_shape = HOURLY_PROFILE_SHAPES["wind_heavy"]
    elif region_type == "coal_heavy":
        raw_shape = HOURLY_PROFILE_SHAPES["coal_heavy"]
    # Priority 2: Seasonal patterns for default regions
    elif "winter" in season_key:
        raw_shape = HOURLY_PROFILE_SHAPES["winter_dual_peak"]
    elif "summer" in season_key:
        raw_shape = HOURLY_PROFILE_SHAPES["evening_peak"]
    elif "spring" in season_key:
        raw_shape = HOURLY_PROFILE_SHAPES["spring_solar"]
    elif "autumn" in season_key or "fall" in season_key:
        raw_shape = HOURLY_PROFILE_SHAPES["autumn_transition"]
    else:
        raw_shape = HOURLY_PROFILE_SHAPES["flat"]

    norm_shape = _normalize_shape_to_avg_one(raw_shape)
    profile = [round(implied * x, 5) for x in norm_shape]
    # Ensure 24 values
    if len(profile) != 24:
        # pad or trim as needed
        if len(profile) < 24:
            profile = profile + [profile[-1]] * (24 - len(profile))
        else:
            profile = profile[:24]
    return profile


def suggest_low_hours(profile: List[float], top_n: int = 3) -> List[int]:
    """Return the indices (hours) of the top_n lowest-intensity hours."""
    pairs = sorted(((v, i) for i, v in enumerate(profile)), key=lambda t: t[0])
    return [i for _, i in pairs[: max(1, int(top_n))]]

def compare_tasks_at_hours(profile: List[float], tasks: List[dict]) -> List[dict]:
    """
    Compare multiple tasks across different hours.
    
    Args:
        profile: 24-hour intensity profile (kg CO2/kWh)
        tasks: List of dicts with keys: 'name', 'kwh', 'hour'
    
    Returns:
        List of dicts with task details, CO2 emissions, and optimal hour suggestion
    """
    results = []
    best_hour = min(range(24), key=lambda h: profile[h])
    best_intensity = profile[best_hour]
    
    for task in tasks:
        try:
            name = str(task.get("name", "Unknown"))
            kwh = float(task.get("kwh", 0))
            hour = int(task.get("hour", 0)) % 24
            
            intensity_at_hour = profile[hour]
            co2_current = kwh * intensity_at_hour
            co2_optimal = kwh * best_intensity
            savings = co2_current - co2_optimal
            savings_pct = (savings / co2_current * 100) if co2_current > 0 else 0.0
            
            results.append({
                "name": name,
                "kwh": kwh,
                "current_hour": hour,
                "current_intensity": round(intensity_at_hour, 4),
                "current_co2_kg": round(co2_current, 3),
                "optimal_hour": best_hour,
                "optimal_intensity": round(best_intensity, 4),
                "optimal_co2_kg": round(co2_optimal, 3),
                "savings_kg": round(savings, 3),
                "savings_pct": round(savings_pct, 1),
            })
        except Exception:
            continue
    
    return results

# -------------------------------
# Smart Home Device Presets
# -------------------------------
# Comprehensive library of common household appliances with typical power ratings and usage patterns
DEVICE_PRESETS: Dict[str, dict] = {
    # Kitchen Appliances
    "Refrigerator": {"power_w": 150, "hours_per_day": 24.0, "category": "Kitchen"},
    "Freezer": {"power_w": 100, "hours_per_day": 24.0, "category": "Kitchen"},
    "Dishwasher": {"power_w": 1800, "hours_per_day": 1.0, "category": "Kitchen"},
    "Microwave": {"power_w": 1200, "hours_per_day": 0.3, "category": "Kitchen"},
    "Electric Oven": {"power_w": 2400, "hours_per_day": 1.0, "category": "Kitchen"},
    "Electric Stove": {"power_w": 2000, "hours_per_day": 1.5, "category": "Kitchen"},
    "Coffee Maker": {"power_w": 1000, "hours_per_day": 0.5, "category": "Kitchen"},
    "Toaster": {"power_w": 1200, "hours_per_day": 0.2, "category": "Kitchen"},
    "Kettle": {"power_w": 1500, "hours_per_day": 0.3, "category": "Kitchen"},
    
    # Laundry & Cleaning
    "Washing Machine": {"power_w": 500, "hours_per_day": 0.7, "category": "Laundry"},
    "Dryer": {"power_w": 3000, "hours_per_day": 0.8, "category": "Laundry"},
    "Vacuum Cleaner": {"power_w": 1400, "hours_per_day": 0.3, "category": "Cleaning"},
    "Iron": {"power_w": 1200, "hours_per_day": 0.5, "category": "Laundry"},
    
    # Climate Control
    "Air Conditioner (Small)": {"power_w": 900, "hours_per_day": 4.0, "category": "Climate"},
    "Air Conditioner (Large)": {"power_w": 1800, "hours_per_day": 6.0, "category": "Climate"},
    "Central AC": {"power_w": 3500, "hours_per_day": 8.0, "category": "Climate"},
    "Space Heater": {"power_w": 1500, "hours_per_day": 4.0, "category": "Climate"},
    "Electric Radiator": {"power_w": 2000, "hours_per_day": 6.0, "category": "Climate"},
    "Ceiling Fan": {"power_w": 75, "hours_per_day": 8.0, "category": "Climate"},
    "Dehumidifier": {"power_w": 300, "hours_per_day": 8.0, "category": "Climate"},
    
    # Electronics & Entertainment
    "TV (LED 40-50\")": {"power_w": 90, "hours_per_day": 4.0, "category": "Entertainment"},
    "TV (OLED 55-65\")": {"power_w": 150, "hours_per_day": 4.0, "category": "Entertainment"},
    "Gaming Console": {"power_w": 150, "hours_per_day": 3.0, "category": "Entertainment"},
    "Desktop PC": {"power_w": 200, "hours_per_day": 6.0, "category": "Electronics"},
    "Laptop": {"power_w": 65, "hours_per_day": 6.0, "category": "Electronics"},
    "Monitor": {"power_w": 30, "hours_per_day": 8.0, "category": "Electronics"},
    "Router/Modem": {"power_w": 10, "hours_per_day": 24.0, "category": "Electronics"},
    "Printer": {"power_w": 50, "hours_per_day": 1.0, "category": "Electronics"},
    "Sound System": {"power_w": 100, "hours_per_day": 3.0, "category": "Entertainment"},
    
    # Lighting
    "LED Bulb (10W)": {"power_w": 10, "hours_per_day": 5.0, "category": "Lighting"},
    "LED Bulb (15W)": {"power_w": 15, "hours_per_day": 5.0, "category": "Lighting"},
    "CFL Bulb (20W)": {"power_w": 20, "hours_per_day": 5.0, "category": "Lighting"},
    "Halogen Bulb (50W)": {"power_w": 50, "hours_per_day": 4.0, "category": "Lighting"},
    "LED Strip Lights": {"power_w": 25, "hours_per_day": 6.0, "category": "Lighting"},
    
    # Electric Vehicles & Mobility
    "EV Charging (Level 1)": {"power_w": 1400, "hours_per_day": 8.0, "category": "EV"},
    "EV Charging (Level 2)": {"power_w": 7200, "hours_per_day": 4.0, "category": "EV"},
    "E-Bike Charging": {"power_w": 100, "hours_per_day": 3.0, "category": "EV"},
    "E-Scooter Charging": {"power_w": 150, "hours_per_day": 2.0, "category": "EV"},
    
    # Water Heating
    "Electric Water Heater": {"power_w": 4000, "hours_per_day": 2.0, "category": "Water"},
    "Tankless Water Heater": {"power_w": 3000, "hours_per_day": 1.5, "category": "Water"},
    
    # Pool & Outdoor
    "Pool Pump": {"power_w": 1500, "hours_per_day": 6.0, "category": "Outdoor"},
    "Hot Tub": {"power_w": 1500, "hours_per_day": 2.0, "category": "Outdoor"},
    "Outdoor Lighting": {"power_w": 100, "hours_per_day": 6.0, "category": "Outdoor"},
    
    # Miscellaneous
    "Hair Dryer": {"power_w": 1500, "hours_per_day": 0.3, "category": "Personal Care"},
    "Electric Shaver": {"power_w": 15, "hours_per_day": 0.2, "category": "Personal Care"},
    "Phone Charger": {"power_w": 5, "hours_per_day": 2.0, "category": "Electronics"},
    "Tablet Charger": {"power_w": 10, "hours_per_day": 2.0, "category": "Electronics"},
    "Smart Speaker": {"power_w": 3, "hours_per_day": 24.0, "category": "Electronics"},
    "Security Camera": {"power_w": 5, "hours_per_day": 24.0, "category": "Security"},
    "Doorbell Camera": {"power_w": 4, "hours_per_day": 24.0, "category": "Security"},
}

# Seasonal device profiles (adjust usage patterns by season)
SEASONAL_ADJUSTMENTS: Dict[str, Dict[str, float]] = {
    "Summer": {
        "Air Conditioner (Small)": 8.0,
        "Air Conditioner (Large)": 10.0,
        "Central AC": 12.0,
        "Ceiling Fan": 12.0,
        "Dehumidifier": 10.0,
        "Space Heater": 0.0,
        "Electric Radiator": 0.0,
    },
    "Winter": {
        "Air Conditioner (Small)": 0.0,
        "Air Conditioner (Large)": 0.0,
        "Central AC": 0.0,
        "Space Heater": 8.0,
        "Electric Radiator": 10.0,
        "Electric Water Heater": 3.0,
        "Ceiling Fan": 2.0,
    },
    "Spring": {
        "Air Conditioner (Small)": 2.0,
        "Space Heater": 2.0,
        "Ceiling Fan": 6.0,
    },
    "Autumn": {
        "Air Conditioner (Small)": 1.0,
        "Space Heater": 3.0,
        "Ceiling Fan": 4.0,
    },
}

def get_device_presets_by_category() -> Dict[str, List[str]]:
    """Return device presets grouped by category."""
    categories: Dict[str, List[str]] = {}
    for device, info in DEVICE_PRESETS.items():
        cat = info.get("category", "Other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(device)
    return categories

def apply_seasonal_adjustment(device_name: str, season: str, base_hours: float) -> float:
    """Apply seasonal adjustment to device usage hours."""
    adjustments = SEASONAL_ADJUSTMENTS.get(season, {})
    if device_name in adjustments:
        return adjustments[device_name]
    return base_hours

def calculate_annual_savings(daily_kwh: float, current_hour: int, profile: List[float]) -> dict:
    """
    Calculate annual CO2 savings from shifting a recurring task to optimal hour.
    
    Args:
        daily_kwh: Energy consumption per day (kWh)
        current_hour: Current operating hour (0-23)
        profile: 24-hour intensity profile (kg CO2/kWh)
    
    Returns:
        Dict with daily, monthly, yearly savings and cost estimates
    """
    try:
        best_hour = min(range(24), key=lambda h: profile[h])
        current_intensity = profile[int(current_hour) % 24]
        best_intensity = profile[best_hour]
        
        daily_savings_kg = daily_kwh * (current_intensity - best_intensity)
        monthly_savings_kg = daily_savings_kg * 30
        yearly_savings_kg = daily_savings_kg * 365
        
        # Rough cost estimate: $15/tonne CO2
        cost_per_kg = 0.015  # USD
        yearly_cost_savings = yearly_savings_kg * cost_per_kg
        
        return {
            "best_hour": best_hour,
            "current_intensity": round(current_intensity, 4),
            "best_intensity": round(best_intensity, 4),
            "daily_savings_kg": round(daily_savings_kg, 3),
            "monthly_savings_kg": round(monthly_savings_kg, 2),
            "yearly_savings_kg": round(yearly_savings_kg, 2),
            "yearly_cost_savings_usd": round(yearly_cost_savings, 2),
            "savings_pct": round((daily_savings_kg / (daily_kwh * current_intensity) * 100) if current_intensity > 0 else 0, 1),
        }
    except Exception:
        return {
            "best_hour": 0,
            "current_intensity": 0.0,
            "best_intensity": 0.0,
            "daily_savings_kg": 0.0,
            "monthly_savings_kg": 0.0,
            "yearly_savings_kg": 0.0,
            "yearly_cost_savings_usd": 0.0,
            "savings_pct": 0.0,
        }

# -------------------------------
# Energy efficiency score (0–100)
# -------------------------------
def efficiency_score(activity_data: Mapping[str, float]) -> dict:
    """
    Return {'score': int, 'category_scores': dict, 'badges': list[str], 'notes': list[str]}.

    Heuristic: compare per-category emissions vs simple daily baselines.
    Score 100 = very low emissions vs baseline. Weighted average across categories.
    """
    try:
        # Simple daily baselines (kg CO2) – illustrative
        baselines = {
            "Energy": 8.0,
            "Transport": 6.0,
            "Meals": 5.0,
        }
        weights = {
            "Energy": 0.45,
            "Transport": 0.35,
            "Meals": 0.20,
        }
        # Compute per-category emissions from activity_data
        cat = {}
        # Local import to avoid circulars
        from co2_engine import CO2_FACTORS as EF  # noqa

        def _sum(keys):
            s = 0.0
            for k in keys:
                try:
                    amt = float(activity_data.get(k, 0) or 0)
                except Exception:
                    amt = 0.0
                s += amt * EF.get(k, 0.0)
            return s

        cat["Energy"] = _sum([
            "electricity_kwh", "natural_gas_m3", "district_heating_kwh", "propane_liter", "fuel_oil_liter", "hot_water_liter"
        ])
        cat["Transport"] = _sum([
            "petrol_liter", "diesel_liter", "bus_km", "train_km", "bicycle_km", "flight_short_km", "flight_long_km"
        ])
        cat["Meals"] = _sum([
            "meat_kg", "chicken_kg", "eggs_kg", "dairy_kg", "vegetarian_kg", "vegan_kg"
        ])

        # Category scores (0-100) – lower than baseline -> higher score
        cat_scores = {}
        for c, val in cat.items():
            base = max(0.1, float(baselines.get(c, 5.0)))
            ratio = float(val) / base
            # piecewise: penalize more strongly over baseline
            if ratio <= 1.0:
                s = 100.0 - (ratio * 50.0)  # 50–100 within/under baseline
            else:
                s = max(0.0, 50.0 - ((ratio - 1.0) * 70.0))  # drops below 50 when over baseline
            cat_scores[c] = round(max(0.0, min(100.0, s)))

        overall = 0.0
        for c, w in weights.items():
            overall += w * cat_scores.get(c, 50.0)
        score = int(round(max(0.0, min(100.0, overall))))

        # Badges and notes
        badges, notes = [], []
        if score >= 85:
            badges.append("🏅 Excellent")
        elif score >= 70:
            badges.append("✅ Good")
        elif score >= 50:
            badges.append("⚠️ Moderate")
        else:
            badges.append("🚧 Needs improvement")

        # Guidance note per dominant category
        worst_cat = min(cat_scores.items(), key=lambda kv: kv[1])[0]
        if worst_cat == "Energy":
            notes.append("Focus on electricity/gas usage (standby power, thermostat setpoints, efficient appliances).")
        elif worst_cat == "Transport":
            notes.append("Shift trips to lower-carbon modes (walk/bike/transit) or consolidate car journeys.")
        else:
            notes.append("Try more plant-forward meals and reduce high-impact ingredients on heavy days.")

        return {"score": score, "category_scores": cat_scores, "badges": badges, "notes": notes}
    except Exception:
        return {"score": 50, "category_scores": {}, "badges": ["⚠️"], "notes": ["Scoring unavailable."]}

# --------------------------
# Offset suggestions (local)
# --------------------------
def estimate_offsets(kg_today: float, kg_week: float | None = None, price_per_tonne_usd: float = 15.0) -> dict:
    """
    Return {'today': {...}, 'week': {...}} with tonnes and costs.
    - price_per_tonne_usd: user-adjustable price in USD per tCO2e.
    """
    t_today = max(0.0, float(kg_today or 0.0)) / 1000.0
    t_week = max(0.0, float(kg_week or 0.0)) / 1000.0 if kg_week is not None else None
    def _calc(t):
        return {
            "tonnes": round(t, 3),
            "price_per_tonne": float(price_per_tonne_usd),
            "cost_usd": round(t * float(price_per_tonne_usd), 2),
            # simple illustrative mix
            "mix": [
                {"project": "Reforestation", "share": 0.4},
                {"project": "Renewable Energy", "share": 0.35},
                {"project": "Cookstoves", "share": 0.25},
            ],
        }
    out = {"today": _calc(t_today)}
    if t_week is not None:
        out["week"] = _calc(t_week)
    return out

# ------------------------
# Simple 7-day forecasting
# ------------------------
def simple_forecast_next7(daily_totals: list[float]) -> list[float]:
    """
    Very simple forecast:
    - If enough history (>=7), use the average of the last 7 entries as a flat projection.
    - Else, use the average of all provided.
    Returns 7 values (kg CO2).
    """
    vals = [max(0.0, float(x)) for x in (daily_totals or []) if x is not None]
    if not vals:
        base = 0.0
    else:
        base = sum(vals[-7:]) / min(7, len(vals))
    return [round(base, 2) for _ in range(7)]

# ------------------------
# Weekly goal plan
# ------------------------
def weekly_goal_plan(current_week_sum: float, remaining_days: int, target_week_sum: float) -> dict:
    """
    Given current accumulated kg for this week and remaining days, compute
    required average per remaining day to hit target_week_sum.
    Returns {'required_per_day': float, 'delta_vs_current_avg': float}
    """
    remain = max(0, int(remaining_days))
    if remain == 0:
        return {"required_per_day": 0.0, "delta_vs_current_avg": 0.0}
    needed = max(0.0, float(target_week_sum) - float(current_week_sum))
    req = needed / remain
    cur_avg = (float(current_week_sum) / (7 - remain)) if (7 - remain) > 0 else req
    return {"required_per_day": round(req, 2), "delta_vs_current_avg": round(req - cur_avg, 2)}



