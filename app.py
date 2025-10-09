# app.py
import pandas as pd
import datetime as dt
import streamlit as st
st.set_page_config(
    page_title="Sustainability Tracker",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """
    <style>
    /* Reduce outer padding/margins */
    .block-container { padding-top: 0.5rem; padding-bottom: 0.5rem; padding-left: 1rem; padding-right: 1rem; }
    /* Tighten spacing between widgets */
    .stMarkdown p { margin-bottom: 0.35rem; }
    .stCaption, .st-emotion-cache-6qob1r, .st-emotion-cache-1kyxreq { font-size: 0.85rem !important; }
    /* Code blocks smaller */
    pre[class*="language-"], code { font-size: 0.85rem !important; }
    /* Buttons/inputs paddings smaller */
    .stButton>button { padding: 0.3rem 0.6rem; }
    .stDownloadButton>button { padding: 0.3rem 0.6rem; }
    .stNumberInput input, .stTextInput input { padding-top: 0.25rem; padding-bottom: 0.25rem; }
    /* Dataframe header height and cell padding tighter */
    .stDataFrame [data-testid="stDataFrame"] { font-size: 0.9rem; }
    /* Reduce expander header font/padding */
    summary { padding-top: 0.25rem !important; padding-bottom: 0.25rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

import io
import ai_tips
from co2_engine import (
    calculate_co2,
    CO2_FACTORS,
    calculate_co2_breakdown,
    calculate_co2_v2,
    calculate_co2_breakdown_v2,
    REGION_FACTOR_PACKS,
    get_engine_meta,
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
    efficiency_score,
    estimate_offsets,
    simple_forecast_next7,
    weekly_goal_plan,
)
from utils import (
    format_emissions as fmt_emissions,
    friendly_message as status_message,
    percentage_change,
)
from ai_tips import (
    generate_ai_summary,
    generate_eco_tip_with_prompt,
    classify_input_type,
    set_extreme_thresholds,
    clean_tip,
    set_llm_params,
)
from app_helpers import (
    _coerce_float,
    has_meaningful_input,
    find_invalid_fields,
    should_generate_tip,
)
import time
import concurrent.futures
import csv
import json
import os
import random
import zipfile
import altair as alt
try:
    from altair_saver import save as alt_save
except Exception:
    alt_save = None
import tempfile

ENABLE_LATE_PDF = False

# =========================
# Category Mapping & Storage
# =========================
CATEGORY_MAP = {
    "Energy": [
        "electricity_kwh",
        "natural_gas_m3",
        "hot_water_liter",
        "cold_water_liter",
        "district_heating_kwh",
        "propane_liter",
        "fuel_oil_liter",
    ],
    "Transport": [
        "petrol_liter",
        "diesel_liter",
        "bus_km",
        "train_km",
        "bicycle_km",
        "flight_short_km",
        "flight_long_km",
    ],
    "Meals": [
        "meat_kg",
        "chicken_kg",
        "eggs_kg",
        "dairy_kg",
        "vegetarian_kg",
        "vegan_kg",
    ],
}
ALL_KEYS = [k for keys in CATEGORY_MAP.values() for k in keys]

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "history.csv")
PREFS_PATH = os.path.join(os.path.dirname(__file__), ".user_prefs.json")


# =========================
# --- Minimal PDF builder for Eco Tips (quick) ---
# =========================
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

def build_eco_tips_pdf(
    summary_text: str,
    tip_text: str,
    ai_summary_text: str,          # may be None
    emissions_today: float,
    date_str: str,
    src_label: str,
    per_activity: dict,
    category_breakdown: dict,
    ctx: dict,
    logo_bytes: bytes = None,
    title_text: str = "Eco Tips Report",
    primary_color: str = "#2563EB",
    include_pie: bool = True,      # ignored in minimal version
    include_sparklines: bool = False,  # ignored
    spark_data=None,               # ignored
    footer_text: str = None,
    margins_cm: dict = None,
    text_hex: str = "#111827",
    chart_bg_hex: str = "#FFFFFF",
    experiments_appendix=None      # ignored
):
    if not REPORTLAB_AVAILABLE:
        return None, "reportlab not installed. Try: pip install reportlab"

    try:
        from io import BytesIO
        buf = BytesIO()
        page_w, page_h = A4
        c = canvas.Canvas(buf, pagesize=A4)

        # Margins
        m_side = float(margins_cm.get("side", 1.5)) if isinstance(margins_cm, dict) else 1.5
        m_top = float(margins_cm.get("top", 1.5)) if isinstance(margins_cm, dict) else 1.5
        m_bottom = float(margins_cm.get("bottom", 1.5)) if isinstance(margins_cm, dict) else 1.5
        x = m_side * cm
        y = page_h - m_top * cm

        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(x, y, title_text)
        y -= 16 + 8

        # Date and source
        c.setFont("Helvetica", 10)
        c.drawString(x, y, f"Date: {date_str} • Source: {src_label}")
        y -= 12 + 4

        # Optional logo (top-right)
        if logo_bytes:
            try:
                from reportlab.lib.utils import ImageReader
                img = ImageReader(BytesIO(logo_bytes))
                img_w = 3.0 * cm
                c.drawImage(img, page_w - m_side * cm - img_w, page_h - m_top * cm - img_w, width=img_w, height=img_w, preserveAspectRatio=True, mask='auto')
            except Exception:
                pass

        # Today total and context
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x, y, f"Today's total: {ctx.get('today_total','')}")
        y -= 14
        c.setFont("Helvetica", 10)
        c.drawString(x, y, f"Yesterday: {ctx.get('yesterday_total','')} • Δ: {ctx.get('delta_pct','')} • Streak: {ctx.get('streak_days','')}")
        y -= 12 + 4

        # Summary
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x, y, "Summary")
        y -= 14
        c.setFont("Helvetica", 10)
        for line in summary_text.splitlines() or ["(none)"]:
            c.drawString(x, y, line[:110])
            y -= 12
            if y < m_bottom * cm + 36:
                c.showPage(); y = page_h - m_top * cm

        # Tip
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x, y, "Eco Tip")
        y -= 14
        c.setFont("Helvetica", 10)
        tip_lines = (tip_text or "").splitlines() or ["(none)"]
        for line in tip_lines:
            c.drawString(x, y, line[:110])
            y -= 12
            if y < m_bottom * cm + 36:
                c.showPage(); y = page_h - m_top * cm

        # AI Summary (optional)
        if ai_summary_text:
            c.setFont("Helvetica-Bold", 12)
            c.drawString(x, y, "AI Summary")
            y -= 14
            c.setFont("Helvetica", 10)
            for line in ai_summary_text.splitlines():
                c.drawString(x, y, line[:110])
                y -= 12
                if y < m_bottom * cm + 36:
                    c.showPage(); y = page_h - m_top * cm

        # Per-activity table (compact)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x, y, "Per‑activity (kg CO₂)")
        y -= 14
        c.setFont("Helvetica", 10)
        if per_activity:
            for k, v in sorted(per_activity.items(), key=lambda kv: -float(kv[1] or 0.0)):
                c.drawString(x, y, f"{k}: {v:.2f}")
                y -= 12
                if y < m_bottom * cm + 36:
                    c.showPage(); y = page_h - m_top * cm
        else:
            c.drawString(x, y, "(none)")
            y -= 12

        # Category breakdown
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x, y, "Category breakdown (kg CO₂)")
        y -= 14
        c.setFont("Helvetica", 10)
        if category_breakdown:
            for k, v in sorted(category_breakdown.items(), key=lambda kv: -float(kv[1] or 0.0)):
                c.drawString(x, y, f"{k}: {v:.2f}")
                y -= 12
                if y < m_bottom * cm + 36:
                    c.showPage(); y = page_h - m_top * cm
        else:
            c.drawString(x, y, "(none)")
            y -= 12

        # Footer
        if footer_text:
            c.setFont("Helvetica-Oblique", 9)
            c.drawString(x, m_bottom * cm, footer_text)

        c.showPage()
        c.save()
        return buf.getvalue(), None
    except Exception as e:
        return None, f"PDF build failed: {e}"

# =========================
# Preferences (persisted across sessions)
# =========================
def load_user_prefs() -> dict:
    try:
        if os.path.exists(PREFS_PATH):
            with open(PREFS_PATH, "r", encoding="utf-8") as f:
                prefs = json.load(f) or {}
                # Surface a small toast/banner once per session to show prefs applied
                if not st.session_state.get("_prefs_loaded_banner_shown"):
                    st.toast("Loaded saved preferences from .user_prefs.json", icon="✅")
                    st.session_state["_prefs_loaded_banner_shown"] = True
                return prefs
    except Exception:
        pass
    return {}


def save_user_prefs(prefs: dict):
    try:
        with open(PREFS_PATH, "w", encoding="utf-8") as f:
            json.dump(prefs or {}, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_pref(key: str, default=None):
    prefs = st.session_state.get("user_prefs")
    if prefs is None:
        prefs = load_user_prefs()
        st.session_state["user_prefs"] = prefs
    return prefs.get(key, default)


def set_pref(key: str, value):
    prefs = st.session_state.get("user_prefs")
    if prefs is None:
        prefs = load_user_prefs()
        st.session_state["user_prefs"] = prefs
    prefs[key] = value
    save_user_prefs(prefs)


# =========================
# Cached tip generation wrapper
# =========================
@st.cache_data(show_spinner=False)
def cached_generate_tip(norm_key: str, emissions: float, cache_salt: int = 0) -> str:
    """Cache tip generation using a normalized JSON key of user_data.
    norm_key: JSON string of sorted numeric values.
    """
    try:
        ud = json.loads(norm_key)
    except Exception:
        ud = {}
    return generate_tip(ud, float(emissions or 0))

def compute_category_emissions(activity_data: dict) -> dict:
    """Compute per-category emission subtotals from raw activity inputs."""
    result: dict = {}
    for cat, keys in CATEGORY_MAP.items():
        subtotal = 0.0
        for k in keys:
            try:
                amt = float(activity_data.get(k, 0) or 0)
            except Exception:
                amt = 0.0
            factor = CO2_FACTORS.get(k)
            if factor is not None:
                subtotal += amt * factor
        result[cat] = round(subtotal, 2)
    return result

@st.cache_data(show_spinner=False)
def get_cached_mix(region_code):
    try:
        return get_grid_mix(region_code)
    except Exception:
        return {}

@st.cache_data(show_spinner=False)
def get_cached_implied_intensity(region_code):
    mix = get_cached_mix(region_code)
    if not mix:
        return None
    try:
        return compute_mix_intensity(mix)
    except Exception:
        return None

def load_history() -> pd.DataFrame:
    cols = ["date", "total_kg"] + ALL_KEYS
    if os.path.exists(HISTORY_FILE):
        try:
            df = pd.read_csv(HISTORY_FILE)
        except Exception:
            return pd.DataFrame(columns=cols)

        # Coerce types
        df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
        if "total_kg" not in df.columns:
            df["total_kg"] = 0.0
        df["total_kg"] = pd.to_numeric(df["total_kg"], errors="coerce").fillna(0.0)

        # Ensure all activity columns exist (used by charts/summary)
        for k in ALL_KEYS:
            if k not in df.columns:
                df[k] = 0.0
            else:
                df[k] = pd.to_numeric(df[k], errors="coerce").fillna(0.0)

        return df
    return pd.DataFrame(columns=cols)


def save_entry(date_val: dt.date, activity_data: dict, total: float):
    df = load_history()
    row = {"date": pd.to_datetime(date_val)}
    for k in ALL_KEYS:
        row[k] = float(activity_data.get(k, 0) or 0)
    row["total_kg"] = float(total)

    if df.empty:
        df = pd.DataFrame([row])
    else:
        mask = df["date"].dt.date == date_val
        if mask.any():
            # Upsert
            df.loc[mask, list(row.keys())] = list(row.values())
        else:
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

    df = df.sort_values("date")
    df.to_csv(HISTORY_FILE, index=False)


def get_yesterday_total(df: pd.DataFrame, date_val: dt.date) -> float:
    if df.empty:
        return 0.0
    yesterday = pd.to_datetime(date_val) - pd.Timedelta(days=1)
    mask = df["date"].dt.date == yesterday.date()
    if mask.any():
        return float(df.loc[mask, "total_kg"].iloc[0])
    return 0.0


def compute_streak(df: pd.DataFrame, date_val: dt.date) -> int:
    """Compute the current streak of consecutive days up to date_val."""
    if df.empty:
        return 0

    # Ensure all dates are datetime.date
    df_dates = df["date"].dt.date if pd.api.types.is_datetime64_any_dtype(df["date"]) else df["date"]
    dayset = set(df_dates)

    streak = 0
    current = date_val
    while current in dayset:
        streak += 1
        current -= dt.timedelta(days=1)

    return streak


def award_badges(today_total: float, streak: int, df: pd.DataFrame) -> list:
    badges = []
    if not df.empty:
        badges.append("📅 Consistency: Entries logged!")
    if today_total < 20:
        badges.append("🌿 Low Impact Day (< 20 kg)")
    if streak >= 3:
        badges.append("🔥 3-Day Streak")
    if streak >= 7:
        badges.append("🏆 7-Day Streak")
    if not df.empty:
        recent = df.tail(7)
        avg7 = float(recent["total_kg"].mean()) if not recent.empty else 0.0
        if avg7 and today_total < 0.9 * avg7:
            badges.append("📈 10% Better than 7-day avg")
    return badges


# =========================
# Helper formatters
# =========================
def format_summary(user_data: dict) -> str:
    """Return a compact, human-friendly summary of today's inputs.
    Only include fields that are present and > 0 where numeric.
    """
    parts: list[str] = []
    def _num(v):
        try:
            return float(v)
        except Exception:
            return v

    # Transport
    if (val := _num(user_data.get("petrol_liter"))) and isinstance(val, float) and val > 0:
        parts.append(f"🚗 Petrol: {val:.1f} L")
    if (val := _num(user_data.get("diesel_liter"))) and isinstance(val, float) and val > 0:
        parts.append(f"🚙 Diesel: {val:.1f} L")
    if (val := _num(user_data.get("bus_km"))) and isinstance(val, float) and val > 0:
        parts.append(f"🚌 Bus: {val:.0f} km")
    if (val := _num(user_data.get("train_km"))) and isinstance(val, float) and val > 0:
        parts.append(f"🚆 Train: {val:.0f} km")
    if (val := _num(user_data.get("bicycle_km"))) and isinstance(val, float) and val > 0:
        parts.append(f"🚴 Bike: {val:.0f} km")

    # Energy
    if (val := _num(user_data.get("electricity_kwh"))) and isinstance(val, float) and val > 0:
        parts.append(f"⚡ Electricity: {val:.1f} kWh")
    if (val := _num(user_data.get("district_heating_kwh"))) and isinstance(val, float) and val > 0:
        parts.append(f"🔥 District heat: {val:.1f} kWh")
    if (val := _num(user_data.get("natural_gas_m3"))) and isinstance(val, float) and val > 0:
        parts.append(f"🏠 Gas: {val:.1f} m³")
    if (val := _num(user_data.get("hot_water_liter"))) and isinstance(val, float) and val > 0:
        parts.append(f"🚿 Hot water: {val:.0f} L")

    # Meals
    meal_bits = []
    for key, label in [
        ("meat_kg", "🥩 Meat"),
        ("chicken_kg", "🍗 Chicken"),
        ("dairy_kg", "🥛 Dairy"),
        ("eggs_kg", "🥚 Eggs"),
        ("vegetarian_kg", "🥗 Veg"),
        ("vegan_kg", "🌱 Vegan"),
    ]:
        val = _num(user_data.get(key))
        if isinstance(val, float) and val > 0:
            meal_bits.append(f"{label}: {val:.2f} kg")
    if meal_bits:
        parts.append(" | ".join(meal_bits))

    return " | ".join(parts) if parts else "No activities logged yet."


def format_summary_html(user_data: dict) -> str:
    """Return an HTML-formatted summary with colored tags. Safe for st.markdown(..., unsafe_allow_html=True)."""
    # Color groups
    def tag(label: str, color: str) -> str:
        return (
            f"<span style='display:inline-block;margin:2px 6px 2px 0;padding:2px 8px;"
            f"border-radius:12px;background:{color};color:#112;border:1px solid rgba(0,0,0,0.1);font-size:0.92em;'>"
            f"{label}</span>"
        )
    html_parts: list[str] = []
    # Transport (green-ish)
    trans_color = "#e6f4ea"  # light green
    for key, icon, unit, fmt in [
        ("petrol_liter", "🚗 Petrol", "L", "{:.1f}"),
        ("diesel_liter", "🚙 Diesel", "L", "{:.1f}"),
        ("bus_km", "🚌 Bus", "km", "{:.0f}"),
        ("train_km", "🚆 Train", "km", "{:.0f}"),
        ("bicycle_km", "🚴 Bike", "km", "{:.0f}"),
    ]:
        val = user_data.get(key)
        try:
            fv = float(val)
        except Exception:
            fv = 0.0
        if fv > 0:
            html_parts.append(tag(f"{icon}: {fmt.format(fv)} {unit}", trans_color))

    # Energy (blue-ish)
    energy_color = "#e8f0fe"  # light blue
    for key, icon, unit, fmt in [
        ("electricity_kwh", "⚡ Electricity", "kWh", "{:.1f}"),
        ("district_heating_kwh", "🔥 District heat", "kWh", "{:.1f}"),
        ("natural_gas_m3", "🏠 Gas", "m³", "{:.1f}"),
        ("hot_water_liter", "🚿 Hot water", "L", "{:.0f}"),
    ]:
        val = user_data.get(key)
        try:
            fv = float(val)
        except Exception:
            fv = 0.0
        if fv > 0:
            html_parts.append(tag(f"{icon}: {fmt.format(fv)} {unit}", energy_color))

    # Meals (orange-ish)
    meal_color = "#fff4e5"  # light orange
    for key, icon in [
        ("meat_kg", "🥩 Meat"),
        ("chicken_kg", "🍗 Chicken"),
        ("dairy_kg", "🥛 Dairy"),
        ("eggs_kg", "🥚 Eggs"),
        ("vegetarian_kg", "🥗 Veg"),
        ("vegan_kg", "🌱 Vegan"),
    ]:
        val = user_data.get(key)
        try:
            fv = float(val)
        except Exception:
            fv = 0.0
        if fv > 0:
            html_parts.append(tag(f"{icon}: {fv:.2f} kg", meal_color))

    if not html_parts:
        return "<em>No activities logged yet.</em>"
    return "\n".join(html_parts)


def dominant_category_icon(user_data: dict) -> tuple[str, str]:
    """Return (icon, category_label) for the dominant emitting category.
    Defaults to neutral if nothing is logged.
    """
    try:
        cat = compute_category_emissions(user_data)
    except Exception:
        cat = {}
    if not cat:
        return ("💡", "Tip")
    dom = max(cat.items(), key=lambda x: x[1])[0]
    icon_map = {"Energy": "⚡", "Transport": "🚗", "Meals": "🥗"}
    return (icon_map.get(dom, "💡"), dom)


# =========================
# Validation helpers
# =========================
def show_input_warnings(user_data: dict):
    """Render inline warnings grouped by category for any invalid fields.
    This is shown immediately after inputs so users can correct quickly.
    """
    invalid = find_invalid_fields(user_data)
    if not invalid:
        return
    # Group invalid keys by category using CATEGORY_MAP
    grouped = {cat: [] for cat in CATEGORY_MAP.keys()}
    for cat, keys in CATEGORY_MAP.items():
        grouped[cat] = [k for k in invalid if k in keys]
    # Render per-category messages if any
    has_any = any(grouped[cat] for cat in grouped)
    if has_any:
        st.markdown("<div style='color:#b00020;font-weight:600;'>Input issues detected:</div>", unsafe_allow_html=True)
        for cat in ["Energy", "Transport", "Meals"]:
            if grouped.get(cat):
                issues = ", ".join(grouped[cat])
                st.markdown(f"- <span style='color:#b00020;'>[{cat}] Invalid: {issues}</span>", unsafe_allow_html=True)


# =========================
# Streamlit App
# =========================
def main():
    # Density + header
    # Initialize persisted UI density in session state
    if "density" not in st.session_state:
        st.session_state["density"] = "Compact"

    # Read density from URL query params if present (new API)
    try:
        qp_density = st.query_params.get("density")
        if qp_density in ("Compact", "Comfy") and qp_density != st.session_state["density"]:
            st.session_state["_pending_density"] = qp_density
    except Exception:
        pass

    # Density toggle: Compact vs Comfy
    def _apply_pending_density_if_any():
        """Apply queued density (Compact/Comfy) before the density radio is instantiated."""
        pdn = st.session_state.get("_pending_density")
        if isinstance(pdn, str) and pdn:
            st.session_state["density"] = pdn
            st.session_state.pop("_pending_density", None)

    def _apply_pending_demo_toggle_if_any():
        """Apply a queued request to turn demo_mode off before the checkbox exists."""
        if st.session_state.get("_pending_demo_off"):
            # Safely set the widget-bound key before checkbox is created in this run
            st.session_state["demo_mode"] = False
            st.session_state.pop("_pending_demo_off", None)

    _apply_pending_density_if_any()
    _apply_pending_demo_toggle_if_any()

    # Defaults for regionalization (in case sidebar doesn't execute later)
    region_code = None
    try:
        default_pct = int(get_pref("renewable_pct", 0))
    except Exception:
        default_pct = 0
    renewable_adjust = float(default_pct) / 100.0

    dens_col1, dens_col2 = st.columns([3, 1])
    with dens_col1:
        st.markdown("#### Sustainability Tracker 🌍")
        st.caption("Track daily CO₂ emissions and get actionable tips • **38 global regions** • **50+ device presets** • **AI-powered insights**")
        st.divider()
    with dens_col2:
        _apply_pending_density_if_any()
        # Persist density across sessions using user prefs
        default_density = get_pref("ui_density", st.session_state.get("density", "Compact"))
        if "density" not in st.session_state:
            st.session_state["density"] = default_density

        prev_density = st.session_state.get("density", default_density)
        st.radio(
            "Density",
            ["Compact", "Comfy"],
            horizontal=True,
            key="density",
        )

        # Persist only when user changes it
        if st.session_state["density"] != prev_density:
            set_pref("ui_density", st.session_state["density"])
            try:
                st.query_params["density"] = st.session_state["density"]
            except Exception:
                pass
        
        # Quick settings: reset to defaults
        if st.button("↩️ Reset preferences to defaults"):
            try:
                if os.path.exists(PREFS_PATH):
                    os.remove(PREFS_PATH)
                # Clear cached prefs and some session flags
                st.session_state.pop("user_prefs", None)
                # Also clear remembered UI toggles so defaults take effect
                for k in [
                    "prompt_len_chart_type", "prompt_time_bin", "pdf_auto_clear_experiments",
                    "pdf_title", "pdf_primary_color", "pdf_text_color", "pdf_chart_bg",
                    "pdf_side_margin", "pdf_top_margin", "pdf_bottom_margin",
                    "pdf_include_pie", "pdf_include_spark", "pdf_include_ai_summary",
                    "pdf_include_prompt_appendix", "pdf_include_footer", "pdf_footer_text",
                    "prompt_mode", "prompt_category_opt", "density",
                    "exp_ai_summary_open_toggle", "exp_prompt_experiments_open_toggle",
                    "exp_prompt_log_open_toggle", "exp_pdf_options_open_toggle",
                ]:
                    st.session_state.pop(k, None)
                st.success("Preferences reset. Reload the page to see defaults applied.")
            except Exception as e:
                st.error(f"Could not reset preferences: {e}")
        # Help popover with a short FAQ
        # Help popover/expander with a short FAQ
        HelpContainer = st.popover if hasattr(st, "popover") else st.expander
        with HelpContainer("Help"):
            st.markdown(
                """
                - **How are emissions calculated?** Using standard factors per activity (kg CO₂ per unit).
                - **Why is bicycle 0?** Cycling has negligible direct CO₂ emissions in this model.
                - **How do I save/export?** Click "Calculate & Save" then download the CSV in Dashboard.
                - **Tips to reduce CO₂?** See the Eco tip card and focus on your biggest source first.

                <br/>
                <a href="#secrets" style="text-decoration:none;">
                  <span style="display:inline-block;padding:2px 8px;border-radius:12px;background:#eef;border:1px solid #ccd;color:#223;">🔐 Secrets (README)</span>
                </a>
                <div style="font-size:0.9em;color:#555;">
                  Configure your OPENAI_API_KEY via <code>.env</code>. See README → Secrets.
                </div>
                """,
                unsafe_allow_html=True,
            )
        # Demo mode: force Compact, load demo values, auto-generate tip
        demo_mode = st.checkbox(
            "Demo mode",
            value=st.session_state.get("demo_mode", False),
            help="Force Compact density, load demo values, and auto-generate a tip.",
            key="demo_mode",
        )
        # Subtle status line about snapshot (for demo debugging)
        if demo_mode:
            _snap = st.session_state.get("demo_snapshot")
            if isinstance(_snap, dict) and _snap.get("ts"):
                st.caption(f"Demo snapshot captured at {_snap['ts']}")
                with st.popover("View snapshot detail"):
                    st.caption(f"Density before demo: {_snap.get('density', 'Comfy')}")
                    inputs = _snap.get("inputs", {})
                    if inputs:
                        st.json(inputs)
                    else:
                        st.write("No inputs captured in snapshot.")
            else:
                st.caption("Demo snapshot: none yet")
        if demo_mode and not st.session_state.get("demo_mode_applied", False):
            # Snapshot current density and inputs to allow restore on exit
            input_keys = [
                # Energy
                "electricity_kwh",
                "natural_gas_m3",
                "hot_water_liter",
                "cold_water_liter",
                "district_heating_kwh",
                "propane_liter",
                "fuel_oil_liter",
                # Transport
                "bus_km",
                "train_km",
                "bicycle_km",
                "petrol_liter",
                "diesel_liter",
                "flight_short_km",
                "flight_long_km",
                # Meals
                "meat_kg",
                "chicken_kg",
                "eggs_kg",
                "dairy_kg",
                "vegetarian_kg",
                "vegan_kg",
            ]
            st.session_state["demo_snapshot"] = {
                "density": st.session_state.get("density", "Comfy"),
                "inputs": {f"in_{k}": st.session_state.get(f"in_{k}", 0.0) for k in input_keys},
                "ts": dt.datetime.now().isoformat(),
            }
            # Queue density to Compact
            st.session_state["_pending_density"] = "Compact"
            # Load representative demo values
            demo_vals = {
                # Energy
                "electricity_kwh": 6.0,
                "natural_gas_m3": 1.2,
                "hot_water_liter": 60,
                # Transport
                "bus_km": 10,
                "train_km": 0,
                "petrol_liter": 2.5,
                # Meals
                "meat_kg": 0.15,
                "dairy_kg": 0.3,
                "vegetarian_kg": 0.2,
            }
            st.session_state["_pending_values"] = demo_vals
            # Auto-generate in Eco Tips on next run
            st.session_state["tips_autogen"] = True
            st.session_state["demo_mode_applied"] = True
            try:
                st.rerun()
            except Exception:
                pass
        # Exit Demo Mode helper: resets inputs and layout back to defaults
        if demo_mode:
            demo_keys = [
                # Energy
                "electricity_kwh",
                "natural_gas_m3",
                "hot_water_liter",
                "cold_water_liter",
                "district_heating_kwh",
                "propane_liter",
                "fuel_oil_liter",
                # Transport
                "bus_km",
                "train_km",
                "bicycle_km",
                "petrol_liter",
                "diesel_liter",
                "flight_short_km",
                "flight_long_km",
                # Meals
                "meat_kg",
                "eggs_kg",
                "dairy_kg",
                "vegetarian_kg",
                "chicken_kg",
                "vegan_kg",
            ]
            if st.button("Exit Demo Mode"):
                # Restore from snapshot if available; otherwise clear to zeros and comfy
                snap = st.session_state.get("demo_snapshot")
                if snap and isinstance(snap, dict):
                    # Convert stored 'in_*' keys back to canonical field keys
                    restored = {}
                    for key, val in snap.get("inputs", {}).items():
                        if key.startswith("in_"):
                            restored[key[3:]] = val
                    st.session_state["_pending_values"] = restored
                    st.session_state["_pending_density"] = snap.get("density", "Comfy")
                else:
                    st.session_state["_pending_values"] = {k: 0.0 for k in demo_keys}
                    st.session_state["_pending_density"] = "Comfy"
                st.session_state["tips_autogen"] = False
                st.session_state["demo_mode_applied"] = False
                # Do NOT set the widget key directly here; queue an off toggle instead
                st.session_state["_pending_demo_off"] = True
                st.session_state.pop("demo_snapshot", None)
                try:
                    st.rerun()
                except Exception:
                    pass

        # Hidden debug controls
        with st.sidebar:
            st.header("⚙️ Settings & Tools")
            
            # Quick actions section
            with st.expander("⚡ Quick Actions", expanded=False):
                col_qa1, col_qa2 = st.columns(2)
                with col_qa1:
                    if st.button("🔄 Reset Today", key="qa_reset_today", help="Clear all today's inputs"):
                        for key in ALL_KEYS:
                            if f"in_{key}" in st.session_state:
                                st.session_state[f"in_{key}"] = 0.0
                        st.success("Inputs reset")
                        try:
                            st.rerun()
                        except Exception:
                            pass
                
                with col_qa2:
                    if st.button("📋 Copy Total", key="qa_copy_total", help="Copy today's total to clipboard"):
                        try:
                            em = st.session_state.get("emissions_today", 0.0)
                            st.code(f"{em:.2f} kg CO₂")
                            st.caption("Total displayed above")
                        except Exception:
                            st.warning("No total yet")
                
                # Quick navigation
                st.caption("**Quick Navigate:**")
                nav_cols = st.columns(3)
                with nav_cols[0]:
                    st.caption("📊 Dashboard")
                with nav_cols[1]:
                    st.caption("⚡ Energy Mix")
                with nav_cols[2]:
                    st.caption("🔌 Estimator")
            
            st.divider()
            # Regionalization controls
            with st.container():
                st.markdown("### Regionalization")
                try:
                    available_regions = ["(default)"] + sorted(list(REGION_FACTOR_PACKS.keys()))
                except Exception:
                    available_regions = ["(default)"]

                # Default to EU-avg if available, otherwise (default)
                try:
                    default_idx = available_regions.index("EU-avg") if "EU-avg" in available_regions else 0
                except Exception:
                    default_idx = 0

                # Default to EU-avg if available, otherwise (default)
                try:
                    default_idx = available_regions.index("EU-avg") if "EU-avg" in available_regions else 0
                except Exception:
                    default_idx = 0

                region_choice = st.selectbox(
                    "Region / subregion",
                    available_regions,
                    index=default_idx,
                    help="Override grid electricity factor (illustrative examples).",
                    key="ui_region_choice",
                )

                region_code = None if region_choice == "(default)" else region_choice

                # Renewable adjustment used only when region is (default)
                try:
                    default_pct = int(get_pref("renewable_pct", 0))
                except Exception:
                    default_pct = 0
                # Synced slider + number input for renewable percentage
                if "ui_renewable_pct_slider" not in st.session_state:
                    st.session_state["ui_renewable_pct_slider"] = int(default_pct)
                if "ui_renewable_pct_box" not in st.session_state:
                    st.session_state["ui_renewable_pct_box"] = int(default_pct)

                def _sync_from_box():
                    val = int(st.session_state["ui_renewable_pct_box"])
                    st.session_state["ui_renewable_pct_slider"] = val

                def _sync_from_slider():
                    val = int(st.session_state["ui_renewable_pct_slider"])
                    st.session_state["ui_renewable_pct_box"] = val

                c1, c2 = st.columns([2, 1])
                with c1:
                    st.slider(
                        "Renewable adjustment (%)",
                        min_value=0, max_value=80,
                        key="ui_renewable_pct_slider",
                        help="Reduces default electricity factor when no region override is selected.",
                        on_change=_sync_from_slider,
                    )
                with c2:
                    st.number_input(
                        " ",  # compact label
                        min_value=0, max_value=80, step=1, format="%d",
                        key="ui_renewable_pct_box",
                        on_change=_sync_from_box,
                        help="Type the percentage; the slider updates automatically.",
                    )

                renewable_pct = int(st.session_state["ui_renewable_pct_box"])
                if renewable_pct != default_pct:
                    try:
                        set_pref("renewable_pct", int(renewable_pct))
                    except Exception:
                        pass
                renewable_adjust = float(renewable_pct) / 100.0
                # Grid mix visualization (if available)
                try:
                    mix = get_cached_mix(region_code)
                except Exception:
                    mix = {}

                if mix:
                    st.markdown("Grid mix by source")
                    df_mix = pd.DataFrame(
                        [{"source": k.title(), "share": float(v)} for k, v in mix.items()]
                    )

                    # Pie chart via Altair
                    try:
                        import altair as alt
                        pie = alt.Chart(df_mix).mark_arc().encode(
                            theta=alt.Theta(field="share", type="quantitative", stack=True),
                            color=alt.Color(field="source", type="nominal", legend=alt.Legend(title="Source")),
                            tooltip=[alt.Tooltip("source:N"), alt.Tooltip("share:Q", format=".0%")],
                        ).properties(height=160)

                        st.altair_chart(pie, use_container_width=True)
                    except Exception:
                        # Fallback: simple bar if Altair fails
                        st.bar_chart(df_mix.set_index("source")["share"])

                    # Implied intensity (illustrative)
                    try:
                        implied = get_cached_implied_intensity(region_code)
                        if implied is not None:
                            st.caption(f"Implied intensity (mix-based): {implied:.3f} kg CO₂/kWh")
                    except Exception:
                        pass
                else:
                    st.caption("No grid mix data for this region.")
                # Factors source
                try:
                    meta = get_engine_meta(region_code)
                    st.caption(f"Factors: {meta.get('source','Default')} {meta.get('version','')}")
                except Exception:
                    pass
            
            st.markdown("#### Regions pack (Import/Export)")
            col_exp, col_imp = st.columns(2)

            with col_exp:
                try:
                   data_path = os.path.join(os.path.dirname(__file__), "data", "regions.json")
                   if os.path.exists(data_path):
                      with open(data_path, "r", encoding="utf-8") as f:
                          st.download_button(
                              "Export regions.json",
                              data=f.read(),
                              file_name="regions.json",
                              mime="application/json",
                              key="btn_export_regions_json",
                          )
                except Exception:
                    pass

            with col_imp:
                uploaded = st.file_uploader("Import regions.json", type=["json"], key="uploader_regions_json")
                if uploaded is not None:
                    try:
                        content = uploaded.read().decode("utf-8")
                        # Basic validation
                        obj = json.loads(content)
                        if isinstance(obj, dict) and obj:
                            data_dir = os.path.join(os.path.dirname(__file__), "data")
                            os.makedirs(data_dir, exist_ok=True)
                            out_path = os.path.join(data_dir, "regions.json")
                            with open(out_path, "w", encoding="utf-8") as f:
                                f.write(content)
                            st.success("Imported regions.json. Reloading…")
                            st.rerun()
                        else:
                             st.error("Invalid JSON format. Expected a non-empty object at top level.")
                    except Exception as e:
                        st.error(f"Failed to import regions.json: {e}")

            # move the same debug content here (no expander needed)
            default_th = st.session_state.get("spinner_threshold", 0.3)
            th = st.slider("Spinner threshold (seconds)", 0.0, 2.0, float(default_th), 0.05)
            st.session_state["spinner_threshold"] = float(th)

            # LLM settings (inside Debug expander as a container, not an expander)
            with st.container():
                st.markdown("### LLM settings")
                c1, c2 = st.columns(2)

                def_tip_temp = float(get_pref("tip_temperature", 0.7))
                def_tip_max = int(get_pref("tip_max_tokens", 160))
                def_sum_temp = float(get_pref("summary_temperature", 0.5))
                def_sum_max = int(get_pref("summary_max_tokens", 220))

                with c1:
                    tip_temperature = st.slider(
                        "Tip temperature", 0.0, 1.2, value=def_tip_temp, step=0.05, key="ui_tip_temperature"
                    )
                    tip_max_tokens = st.number_input(
                        "Tip max_tokens", min_value=64, max_value=1000, value=def_tip_max, step=10, key="ui_tip_max_tokens"
                    )
                with c2:
                    summary_temperature = st.slider(
                        "Summary temperature", 0.0, 1.2, value=def_sum_temp, step=0.05, key="ui_summary_temperature"
                    )
                    summary_max_tokens = st.number_input(
                        "Summary max_tokens", min_value=64, max_value=1200, value=def_sum_max, step=10, key="ui_summary_max_tokens"
                    )

                if st.button("Apply LLM settings", key="btn_apply_llm_settings"):
                    set_llm_params(
                        tip_temperature=float(tip_temperature),
                        tip_max_tokens=int(tip_max_tokens),
                        summary_temperature=float(summary_temperature),
                        summary_max_tokens=int(summary_max_tokens),
                )
                set_pref("tip_temperature", float(tip_temperature))
                set_pref("tip_max_tokens", int(tip_max_tokens))
                set_pref("summary_temperature", float(summary_temperature))
                set_pref("summary_max_tokens", int(summary_max_tokens))

                st.session_state["tip_cache_salt"] = int(st.session_state.get("tip_cache_salt", 0)) + 1
                st.success("Applied LLM settings. Tip cache invalidated for new generations.")            
            
            st.checkbox(
                "Enable performance logging (perf_log.csv)",
                value=st.session_state.get("perf_logging", False),
                key="perf_logging",
                help="Append eco-tip generation timings to perf_log.csv",
            )
            st.markdown(
                """
                <a href="#secrets" style="text-decoration:none;">
                  <span style="display:inline-block;padding:2px 8px;border-radius:12px;background:#eef;border:1px solid #ccd;color:#223;">🔐 Secrets (README)</span>
                </a>
                <div style="font-size:0.9em;color:#555;">Configure your OPENAI_API_KEY via <code>.env</code>. See README → Secrets.</div>
                """,
                unsafe_allow_html=True,
            )
            # Note on caching behavior
            st.info(
                "Tips are cached via st.cache_data using a normalized input key. Very fast times usually indicate a cache hit. Disabling cache requires code changes.",
                icon="ℹ️",
            )
            # Stress tests (simulation)
            st.divider()
            st.caption("Stress tests (simulated)")

            col_st1, col_st2, col_st3 = st.columns([1, 1, 1])
            with col_st1:
                burst_n = st.number_input("Burst size (tips)", min_value=1, max_value=200, value=25, step=1, key="stress_burst_n")
            with col_st2:
                delay_ms = st.number_input("Delay between tips (ms)", min_value=0, max_value=500, value=20, step=5, key="stress_delay_ms")
            with col_st3:
                long_text = st.checkbox(
                    "Simulate long inputs",
                    value=False,
                    key="stress_long_inputs",
                    help="Adds long strings to internal inputs to test prompt/summary stability.",
                )

            if st.button("▶️ Run stress tip burst"):
                prog = st.progress(0)
                errs = 0
                elapsed_total = 0.0

                def _mk_inputs(i: int) -> dict:
                    base = {
                        "electricity_kwh": max(0.0, random.uniform(0, 12)),
                        "natural_gas_m3": max(0.0, random.uniform(0, 3)),
                        "hot_water_liter": max(0.0, random.uniform(0, 120)),
                        "bus_km": max(0.0, random.uniform(0, 20)),
                        "train_km": max(0.0, random.uniform(0, 30)),
                        "petrol_liter": max(0.0, random.uniform(0, 4)),
                        "meat_kg": max(0.0, random.uniform(0, 0.5)),
                        "dairy_kg": max(0.0, random.uniform(0, 0.8)),
                        "vegetarian_kg": max(0.0, random.uniform(0, 0.8)),
                    }
                    if long_text:
                        base["note"] = ("x" * 2000) + f"_{i}"
                    return base

                for i in range(int(burst_n)):
                    try:
                        ud_i = _mk_inputs(i)
                        nd = {}
                        for k in sorted(ALL_KEYS):
                            try:
                                v = float(ud_i.get(k, 0) or 0)
                            except Exception:
                                v = 0.0
                            nd[k] = v
                        norm_key_i = json.dumps(nd, sort_keys=True)
                        em_i = 0.0
                        for k, v in nd.items():
                            em_i += v * CO2_FACTORS.get(k, 0.0)
                        t0 = time.time()
                        _ = cached_generate_tip(
                            norm_key_i,
                            float(em_i or 0),
                            int(st.session_state.get("tip_cache_salt", 0)),
                        )
                        elapsed_total += (time.time() - t0)
                        time.sleep(float(delay_ms) / 1000.0)
                    except Exception:
                        errs += 1
                    finally:
                        prog.progress(int((i + 1) / float(burst_n) * 100))

                st.success(
                    f"Stress run complete. Tips: {burst_n}, errors: {errs}, avg latency: {(elapsed_total / max(1, burst_n)):.3f}s"
                )
            # Simulate API failures toggle (forces fallbacks)
            simulate_fail = st.checkbox(
                "Simulate API failures (force fallbacks)",
                value=bool(os.environ.get("SIMULATE_API_FAILURES")),
                key="simulate_api_failures",
                help="When ON, GPT calls will be short-circuited to exercise local fallback paths.",
            )
            try:
                if simulate_fail:
                    os.environ["SIMULATE_API_FAILURES"] = "1"
                else:
                    os.environ.pop("SIMULATE_API_FAILURES", None)
            except Exception:
                pass
            # Scoped tip cache clear via salt bump
            if "tip_cache_salt" not in st.session_state:
                st.session_state["tip_cache_salt"] = 0
            if st.button("🧹 Clear tip cache (scoped)"):
                st.session_state["tip_cache_salt"] = int(st.session_state.get("tip_cache_salt", 0)) + 1
                st.success(
                    f"Tip cache cleared (salt={st.session_state['tip_cache_salt']}). New requests will bypass previous cache entries."
                ) 
                                       
        # Copy shareable link button (copies current URL with density param)
        st.markdown(
            """
            <button id=\"copy-link-btn\" style=\"margin-top:0.25rem;\">Copy shareable link</button>
            <script>
            const btn = document.getElementById('copy-link-btn');
            if (btn) {
              btn.addEventListener('click', async () => {
                try {
                  await navigator.clipboard.writeText(window.location.href);
                  const old = btn.textContent;
                  btn.textContent = 'Copied!';
                  setTimeout(() => { btn.textContent = old; }, 1500);
                } catch (e) {
                  btn.textContent = 'Copy failed';
                  setTimeout(() => { btn.textContent = 'Copy shareable link'; }, 1500);
                }
              });
            }
            </script>
            """,
            unsafe_allow_html=True,
        )
        # Reset layout button: revert to Compact density and update URL
        if st.button("Reset layout", type="secondary"):
            st.session_state["_pending_density"] = "Compact"
            try:
                st.query_params["density"] = "Compact"
            except Exception:
                pass
            st.success("Layout reset to Compact. Collapse expanders for best PDF.")
            try:
                st.rerun()
            except Exception:
                pass
        # Clear inputs button: zero all input fields
        if st.button("Clear inputs", help="Reset all fields to zero for today’s entry."):
            try:
                for _k in ALL_KEYS:
                    _sk = f"in_{_k}"
                    if _sk in st.session_state:
                        st.session_state[_sk] = 0.0
            except Exception:
                pass
            st.success("Inputs cleared.")
        # Demo and preset fillers
        with st.popover("Prefill demos/presets"):
            st.markdown("Pick a scenario to quickly populate inputs for demos.")
            c_demo, c_p1, c_p2 = st.columns(3)
            def _apply_values(vals: dict):
                # Queue values to apply before widgets are instantiated, then rerun
                st.session_state["_pending_values"] = {k: float(v) for k, v in vals.items()}
                try:
                    st.rerun()
                except Exception:
                    pass
            with c_demo:
                if st.button("Demo values"):
                    _apply_values({
                        # Energy
                        "electricity_kwh": 8,
                        "natural_gas_m3": 1.2,
                        "hot_water_liter": 60,
                        # Transport
                        "bus_km": 10,
                        "train_km": 0,
                        "petrol_liter": 2.5,
                        # Meals
                        "meat_kg": 0.15,
                        "dairy_kg": 0.3,
                        "vegetarian_kg": 0.2,
                    })
            with c_p1:
                if st.button("No car day"):
                    _apply_values({
                        "petrol_liter": 0,
                        "diesel_liter": 0,
                        "bus_km": 12,
                        "train_km": 6,
                        "bicycle_km": 5,
                    })
            with c_p2:
                if st.button("Vegetarian day"):
                    _apply_values({
                        "meat_kg": 0,
                        "chicken_kg": 0,
                        "vegetarian_kg": 0.6,
                        "vegan_kg": 0.2,
                        "dairy_kg": 0.25,
                    })
            c_p3, _, _ = st.columns(3)
            with c_p3:
                if st.button("Business trip"):
                    _apply_values({
                        "flight_short_km": 600,
                        "train_km": 20,
                        "electricity_kwh": 6,
                        "meat_kg": 0.25,
                    })
   
    # Initialize session state defaults (safe idempotent)
    if "density" not in st.session_state:
        # Use your persisted preference if available, else default to "Compact"
        try:
            default_density = get_pref("density", "Compact")
        except Exception:
            default_density = "Compact"
        st.session_state["density"] = default_density

    # Commonly used keys in this app; safe defaults
    st.session_state.setdefault("tip_cache_salt", 0)
    st.session_state.setdefault("demo_mode", False)
    st.session_state.setdefault("_pending_values", None)
    st.session_state.setdefault("_pending_density", None)
    st.session_state.setdefault("_pending_demo_off", False)

    # NOW define density safely
    density = st.session_state.get("density", get_pref("density", "Compact"))

    # Update URL query param to reflect current density (new API)
    try:
        st.query_params["density"] = density
    except Exception:
        pass
    
    expander_default = (st.session_state.get("density", "Compact") == "Comfy")
    # Heights and paddings based on density
    if density == "Compact":
        pad_top, pad_bottom = "1rem", "1rem"
        table_height = 150
        trend_height = 180
        bar_height = 180
        per_activity_height = 260
        expander_default = False
    else:
        pad_top, pad_bottom = "2rem", "2rem"
        table_height = 220
        trend_height = 260
        bar_height = 260
        per_activity_height = 360
        expander_default = True

    # Hide Streamlit default menu, footer, and header for cleaner PDF export
    st.markdown(
        f"""
        <style>
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}
        .block-container {{padding-top: {pad_top}; padding-bottom: {pad_bottom};}}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Top row: date and action area
    top_c1, top_c2 = st.columns([1, 2])
    with top_c1:
        selected_date = st.date_input("Date", value=dt.date.today())
    with top_c2:
        st.write("")

    def _apply_pending_values_if_any():
        """Apply any queued preset/demo values before widgets are created."""
        pending = st.session_state.get("_pending_values")
        if isinstance(pending, dict) and pending:
            for k, v in pending.items():
                st.session_state[f"in_{k}"] = float(v)
            st.session_state.pop("_pending_values", None)

    _apply_pending_values_if_any()

    with st.form("daily_input"):
        # Inputs grouped in compact expanders (density controlled)
        with st.expander("Energy inputs", expanded=expander_default):
            e1, e2, e3 = st.columns(3)
            with e1:
                # Provide a default only if the state was not prefilled (e.g., by _apply_pending_values_if_any)
                val_param = {} if "in_electricity_kwh" in st.session_state else {"value": 0.0}
                electricity = st.number_input("Electricity (kWh)", min_value=0.0, step=0.1, key="in_electricity_kwh", help="Enter a number ≥ 0", **val_param,)
                _e = _coerce_float(electricity)
                if _e is None or (_e is not None and _e < 0):
                    st.markdown("<div style='color:#b00020;font-size:0.9em;'>Enter a number ≥ 0</div>", unsafe_allow_html=True)
                # Natural Gas (m³)
                val_param = {} if "in_natural_gas_m3" in st.session_state else {"value": 0.0}
                natural_gas = st.number_input("Natural Gas (m³)", min_value=0.0, step=0.1, key="in_natural_gas_m3", help="Enter a number ≥ 0", **val_param,)
            with e2:
                # Hot Water (L)
                val_param = {} if "in_hot_water_liter" in st.session_state else {"value": 0.0}
                hot_water = st.number_input("Hot Water (L)", min_value=0.0, step=1.0, key="in_hot_water_liter", help="Enter a number ≥ 0", **val_param,)
                # Cold/Chilled Water (L)
                val_param = {} if "in_cold_water_liter" in st.session_state else {"value": 0.0}
                cold_water = st.number_input("Cold/Chilled Water (L)", min_value=0.0, step=1.0, key="in_cold_water_liter", help="Enter a number ≥ 0", **val_param,)        
            with e3:
                # District Heating (kWh)
                val_param = {} if "in_district_heating_kwh" in st.session_state else {"value": 0.0}
                district_heating = st.number_input("District Heating (kWh)", min_value=0.0, step=0.1, key="in_district_heating_kwh", help="Enter a number ≥ 0", **val_param,)
                # Propane (L)
                val_param = {} if "in_propane_liter" in st.session_state else {"value": 0.0}
                propane = st.number_input("Propane (L)", min_value=0.0, step=0.1, key="in_propane_liter", help="Enter a number ≥ 0", **val_param,)
                # Fuel Oil (L)
                val_param = {} if "in_fuel_oil_liter" in st.session_state else {"value": 0.0}
                fuel_oil = st.number_input("Fuel Oil (L)", min_value=0.0, step=0.1, key="in_fuel_oil_liter", help="Enter a number ≥ 0", **val_param,)
        
        with st.expander("Transport inputs", expanded=expander_default):
            t1, t2, t3 = st.columns(3)
            with t1:
                # Car Petrol (L)
                val_param = {} if "in_petrol_liter" in st.session_state else {"value": 0.0}
                petrol = st.number_input("Car Petrol (L)", min_value=0.0, step=0.1, key="in_petrol_liter", help="Enter a number ≥ 0", **val_param,)
                _p = _coerce_float(petrol)
                if _p is None or (_p is not None and _p < 0):
                    st.markdown("<div style='color:#b00020;font-size:0.9em;'>Enter a number ≥ 0</div>", unsafe_allow_html=True)
                # Car Diesel (L)
                val_param = {} if "in_diesel_liter" in st.session_state else {"value": 0.0}
                diesel = st.number_input("Car Diesel (L)", min_value=0.0, step=0.1, key="in_diesel_liter", help="Enter a number ≥ 0", **val_param,)
            with t2:
                # Bus (km)
                val_param = {} if "in_bus_km" in st.session_state else {"value": 0.0}
                bus = st.number_input("Bus (km)", min_value=0.0, step=1.0, key="in_bus_km", help="Enter a number ≥ 0", **val_param,)
                # Train (km)
                val_param = {} if "in_train_km" in st.session_state else {"value": 0.0}
                train = st.number_input("Train (km)", min_value=0.0, step=1.0, key="in_train_km", help="Enter a number ≥ 0", **val_param,)
                # Bicycle (km)
                val_param = {} if "in_bicycle_km" in st.session_state else {"value": 0.0}
                bicycle = st.number_input("Bicycle (km)", min_value=0.0, step=1.0, key="in_bicycle_km", help="Enter a number ≥ 0", **val_param,)
            with t3:
                # Flight Short (km)
                val_param = {} if "in_flight_short_km" in st.session_state else {"value": 0.0}
                flight_short = st.number_input("Flight Short (km)", min_value=0.0, step=1.0, key="in_flight_short_km", help="Enter a number ≥ 0", **val_param,)

                # Flight Long (km)
                val_param = {} if "in_flight_long_km" in st.session_state else {"value": 0.0}
                flight_long = st.number_input("Flight Long (km)", min_value=0.0, step=1.0, key="in_flight_long_km", help="Enter a number ≥ 0", **val_param,)

        with st.expander("Meals inputs", expanded=expander_default):
            m1, m2, m3 = st.columns(3)
            with m1:
                # Meat (kg)
                val_param = {} if "in_meat_kg" in st.session_state else {"value": 0.0}
                meat = st.number_input("Meat (kg)", min_value=0.0, step=0.1, key="in_meat_kg", help="Enter a number ≥ 0", **val_param,)
                _m = _coerce_float(meat)
                if _m is None or (_m is not None and _m < 0):
                    st.markdown("<div style='color:#b00020;font-size:0.9em;'>Enter a number ≥ 0</div>", unsafe_allow_html=True)
                # Chicken (kg)
                val_param = {} if "in_chicken_kg" in st.session_state else {"value": 0.0}
                chicken = st.number_input("Chicken (kg)", min_value=0.0, step=0.1, key="in_chicken_kg", help="Enter a number ≥ 0", **val_param,)
            with m2:
                # Eggs (kg)
                val_param = {} if "in_eggs_kg" in st.session_state else {"value": 0.0}
                eggs = st.number_input("Eggs (kg)", min_value=0.0, step=0.1, key="in_eggs_kg", help="Enter a number ≥ 0", **val_param,)
                # Dairy (kg)
                val_param = {} if "in_dairy_kg" in st.session_state else {"value": 0.0}
                dairy = st.number_input("Dairy (kg)", min_value=0.0, step=0.1, key="in_dairy_kg", help="Enter a number ≥ 0", **val_param,)
            with m3:
                # Vegetarian (kg)
                val_param = {} if "in_vegetarian_kg" in st.session_state else {"value": 0.0}
                vegetarian = st.number_input("Vegetarian (kg)", min_value=0.0, step=0.1, key="in_vegetarian_kg", help="Enter a number ≥ 0", **val_param,)
                # Vegan (kg)
                val_param = {} if "in_vegan_kg" in st.session_state else {"value": 0.0}
                vegan = st.number_input("Vegan (kg)", min_value=0.0, step=0.1, key="in_vegan_kg", help="Enter a number ≥ 0", **val_param,)
        submitted = st.form_submit_button("Calculate & Save")

    # Gather input into a dict compatible with CO2_FACTORS
    user_data = {
        "electricity_kwh": electricity,
        "natural_gas_m3": natural_gas,
        "hot_water_liter": hot_water,
        "cold_water_liter": cold_water,
        "district_heating_kwh": district_heating,
        "propane_liter": propane,
        "fuel_oil_liter": fuel_oil,
        "petrol_liter": petrol,
        "diesel_liter": diesel,
        "bus_km": bus,
        "train_km": train,
        "bicycle_km": bicycle,
        "flight_short_km": flight_short,
        "flight_long_km": flight_long,
        "meat_kg": meat,
        "chicken_kg": chicken,
        "eggs_kg": eggs,
        "dairy_kg": dairy,
        "vegetarian_kg": vegetarian,
        "vegan_kg": vegan,
    }

    # Global input hint (tooltip-style note)
    st.markdown("<div style='color:#5f6368;font-size:0.9em;'>Hint: All numeric inputs should be <b>≥ 0</b>. Enter whole numbers or decimals as needed.</div>", unsafe_allow_html=True)

    # Inline warnings near inputs (if any invalid fields)
    show_input_warnings(user_data)

    # Calculate total emissions
    emissions = calculate_co2_v2(
        user_data,
        region_code=region_code if 'region_code' in locals() else None,
        renewable_adjust=renewable_adjust if 'renewable_adjust' in locals() else None,
    )
    # Store for cross-tab visibility (Eco Tips tab)
    st.session_state["emissions_today"] = float(emissions)

    # Compute per-activity once for optional breakdown tab
    per_activity = calculate_co2_breakdown_v2(
        user_data,
        region_code=region_code if 'region_code' in locals() else None,
        renewable_adjust=renewable_adjust if 'renewable_adjust' in locals() else None,
    )

    # Load history for KPIs and visuals
    history_df = load_history()
    yesterday_total = get_yesterday_total(history_df, selected_date)
    delta_pct = percentage_change(yesterday_total, emissions)
    streak = compute_streak(history_df, selected_date)

    # KPIs (compact)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total", fmt_emissions(emissions))
    c2.metric("Δ vs. Yesterday", f"{delta_pct:.2f}%")
    c3.metric("Streak", f"{streak} day(s)")

    # Tabs for Dashboard and Breakdown
    tab_dashboard, tab_history, tab_breakdown, tab_energy_mix, tab_intensity, tab_score, tab_compare, tab_offsets, tab_planner, tab_renewables, tab_leaderboard, tab_estimator, tab_tips = st.tabs(
        ["📊 Dashboard", "📜 History", "📉 Breakdown", "⚡ Energy Mix", "⏱️ Intensity", "🏅 Score", "📈 Comparisons", "🌿 Offsets", "📅 Planner", "🌱 Renewables", "🏁 Leaderboard", "🔌 Estimator", "💡 Eco Tips"])

    with tab_dashboard:
        # Two-column layout for compact one-page UI
        left_col, right_col = st.columns([2, 1])

        with left_col:
            # Category-wise table
            cat_emissions = compute_category_emissions(user_data)
            st.caption("Category totals (kg CO₂)")
            st.markdown('<div style="max-width:1100px;margin:0 auto;">', unsafe_allow_html=True)
            st.dataframe(
                pd.DataFrame.from_dict(cat_emissions, orient="index", columns=["kg CO₂"]),
                use_container_width=True,
                height=table_height,  # keep your computed height or set ~220
            )
            st.markdown('</div>', unsafe_allow_html=True)
            st.caption("Today's category breakdown")
            st.bar_chart(pd.Series(cat_emissions, name="kg CO₂"), height=bar_height)

        with right_col:
            # Save after calculation
            if submitted:
                invalid = find_invalid_fields(user_data)
                if invalid:
                    bad_list = ", ".join(invalid)
                    st.warning(f"Some inputs look invalid (negative or non-numeric): {bad_list}. Please correct them before saving.")
                    # Optional logging
                    if st.session_state.get("perf_logging", False):
                        log_path = os.path.join(os.getcwd(), "perf_log.csv")
                        file_exists = os.path.exists(log_path)
                        try:
                            with open(log_path, mode="a", newline="", encoding="utf-8") as f:
                                writer = csv.writer(f)
                                if not file_exists:
                                    writer.writerow(["timestamp", "elapsed_s", "emissions_kg"])  # header
                                writer.writerow([dt.datetime.now().isoformat(), "warning:invalid_inputs", f"{emissions:.4f}"])
                        except Exception:
                            pass
                elif not has_meaningful_input(user_data):
                    st.warning("No valid input detected – please log at least one activity before saving.")
                    if st.session_state.get("perf_logging", False):
                        log_path = os.path.join(os.getcwd(), "perf_log.csv")
                        file_exists = os.path.exists(log_path)
                        try:
                            with open(log_path, mode="a", newline="", encoding="utf-8") as f:
                                writer = csv.writer(f)
                                if not file_exists:
                                    writer.writerow(["timestamp", "elapsed_s", "emissions_kg"])  # header
                                writer.writerow([dt.datetime.now().isoformat(), "warning:no_inputs", f"{emissions:.4f}"])
                        except Exception:
                            pass
                else:
                    save_entry(selected_date, user_data, emissions)
                    st.success("Saved.")

            # Visualizations (reduced height)
            history_df = load_history()  # reload after potential save
            if not history_df.empty:
                st.caption("Trend (Total kg CO₂)")               
                history_df_display = history_df.copy()
                history_df_display = history_df_display.dropna(subset=["date"])
                history_df_display["date"] = history_df_display["date"].dt.date
                st.line_chart(history_df_display.set_index("date")["total_kg"], height=trend_height)

                # CSV export button
                csv_buf = io.StringIO()
                history_df.to_csv(csv_buf, index=False)
                st.download_button(
                    label="⬇️ Download history CSV",
                    data=csv_buf.getvalue(),
                    file_name="history.csv",
                    mime="text/csv",
                    key="download_history_csv_dashboard",
                )

            # Eco tip and status (compact) — cached + robust
            st.caption("Eco tip & status")
            placeholder = st.empty()
            with placeholder.container():
                st.markdown("<div style='opacity:0.6'>Preparing tip…</div>", unsafe_allow_html=True)

            # Build normalized cache key from numeric inputs
            def _norm_key(d: dict) -> str:
                nd = {}
                for k in sorted(ALL_KEYS):
                    try:
                        v = float(d.get(k, 0) or 0)
                    except Exception:
                        v = 0.0
                    nd[k] = v
                return json.dumps(nd, sort_keys=True)

            norm_key = _norm_key(user_data)
            threshold = float(st.session_state.get("spinner_threshold", 0.3))
            start_time = time.time()
            tip_text = ""
            label = "tip_fresh"

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(
                    cached_generate_tip,
                    norm_key,
                    float(emissions or 0),
                    int(st.session_state.get("tip_cache_salt", 0)),
                )
                spinner_shown = False
                try:
                    while True:
                        if fut.done():
                            tip_text = fut.result()
                            break
                        elapsed_loop = time.time() - start_time
                        if not spinner_shown and elapsed_loop > threshold:
                            with placeholder.container():
                                 with st.spinner("Generating eco-tip..."):
                                    tip_text = fut.result()
                            spinner_shown = True
                            break
                        time.sleep(0.05)
                except Exception:
                    # Graceful fallback: call ai_tips.generate_tip so LAST_TIP_SOURCE updates too
                    try:
                        tip_text = ai_tips.generate_tip(user_data, emissions)
                        # Persist readable source in session for badges
                        try:
                            src_raw = getattr(ai_tips, "LAST_TIP_SOURCE", "unknown")
                            st.session_state["last_tip_source"] = (
                                "GPT" if src_raw == "gpt"
                                else ("Fallback" if src_raw == "fallback" else "Unknown")
                            )
                        except Exception:
                            pass
                    except Exception:
                        tip_text = ""

            elapsed = time.time() - start_time
            if elapsed < 0.06:
                label = "tip_cached"

            icon, dom_cat = dominant_category_icon(user_data)
            if not tip_text:
                tip_text = f"Focus on {dom_cat}: take one small action today (e.g., switch off idle devices, choose bus/train, or try a plant-based meal)."
            short_tip = clean_tip(tip_text)

            st.session_state["last_tip_full"] = tip_text
            st.session_state["last_tip"] = short_tip
            st.session_state["last_tip_icon"] = icon
            try:
                src_raw = getattr(ai_tips, "LAST_TIP_SOURCE", "unknown")
                st.session_state["last_tip_source"] = (
                    "GPT" if src_raw == "gpt"
                    else ("Fallback" if src_raw == "fallback" else "Unknown")
                )
            except Exception:
                pass

            placeholder.empty()
            st.success(f"{icon} {short_tip}")
            st.caption(f"Tip generated in {elapsed:.2f}s • {label}")
            st.caption(f"AI source: {st.session_state.get('last_tip_source', 'Unknown')}")

            # Optional perf logging with cached/fresh label
            if st.session_state.get("perf_logging", False):
                log_path = os.path.join(os.getcwd(), "perf_log.csv")
                file_exists = os.path.exists(log_path)
                try:
                    with open(log_path, mode="a", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        if not file_exists:
                            writer.writerow(["timestamp", "elapsed_s", "emissions_kg", "label"])  # header
                        writer.writerow([dt.datetime.now().isoformat(), f"{elapsed:.4f}", f"{emissions:.4f}", label])
                except Exception:
                    pass

            st.success(status_message(emissions))

            # Badges (compact list)
            summary_str = format_summary(user_data)
            st.download_button(
                label="⬇️ Download summary (.txt)",
                data=summary_str,
                file_name="summary.txt",
                mime="text/plain",
                key="download_summary_txt",
            )
            st.caption("Badges")
            badges = award_badges(emissions, streak, history_df)
            if badges:
                for b in badges:
                    st.markdown(f"- {b}")
            else:
                st.write("Log entries to start earning badges!")

        # Second row: mini sparklines by category
        if not history_df.empty:
            st.divider()
            st.caption("Mini trends by category")

            def _category_series(df: pd.DataFrame, keys: list[str]) -> pd.Series | None:
                present = [k for k in keys if k in df.columns]
                if not present:
                    return None
                s = pd.Series(0.0, index=df.index)
                for k in present:
                    factor = CO2_FACTORS.get(k)
                    s = s + df[k].fillna(0).astype(float) * factor
                return s

            def _seven_day_delta(s: pd.Series):
                if s is None or s.empty:
                    return None, None
                s = s.dropna()
                if len(s) < 2:
                    return None, None
                last7 = float(s.iloc[-7:].sum())
                prev7 = float(s.iloc[-14:-7].sum()) if len(s) >= 14 else 0.0
                return last7, percentage_change(prev7, last7)

            df_sorted = history_df.sort_values("date").copy()
            df_sorted_indexed = df_sorted.set_index("date")

            energy_s = _category_series(df_sorted, CATEGORY_MAP["Energy"]) 
            energy_s = energy_s if (energy_s is not None and not energy_s.empty) else pd.Series(dtype=float)
            transport_s = _category_series(df_sorted, CATEGORY_MAP["Transport"]) 
            transport_s = transport_s if (transport_s is not None and not transport_s.empty) else pd.Series(dtype=float)
            meals_s = _category_series(df_sorted, CATEGORY_MAP["Meals"]) 
            meals_s = meals_s if (meals_s is not None and not meals_s.empty) else pd.Series(dtype=float)

            mini_height = 120 if density == "Compact" else 160
            c_en, c_tr, c_me = st.columns(3)
            with c_en:
                st.markdown("**Energy**")
                if not energy_s.empty:
                    st.line_chart(energy_s.set_axis(df_sorted_indexed.index), height=mini_height)
                    en_last7, en_pct = _seven_day_delta(energy_s)
                    if en_last7 is not None:
                        st.metric("7d total", f"{en_last7:.2f} kg", f"{en_pct:.1f}%", delta_color="inverse")
                    else:
                        st.caption("Not enough data yet")
                else:
                    st.write("No data yet")
            with c_tr:
                st.markdown("**Transport**")
                if not transport_s.empty:
                    st.line_chart(transport_s.set_axis(df_sorted_indexed.index), height=mini_height)
                    tr_last7, tr_pct = _seven_day_delta(transport_s)
                    if tr_last7 is not None:
                        st.metric("7d total", f"{tr_last7:.2f} kg", f"{tr_pct:.1f}%", delta_color="inverse")
                    else:
                        st.caption("Not enough data yet")
                else:
                    st.write("No data yet")
            with c_me:
                st.markdown("**Meals**")
                if not meals_s.empty:
                    st.line_chart(meals_s.set_axis(df_sorted_indexed.index), height=mini_height)
                    me_last7, me_pct = _seven_day_delta(meals_s)
                    if me_last7 is not None:
                        st.metric("7d total", f"{me_last7:.2f} kg", f"{me_pct:.1f}%", delta_color="inverse")
                    else:
                        st.caption("Not enough data yet")
                else:
                    st.write("No data yet")

    with tab_history:
        st.header("Saved History")
        history_all = load_history()
        if history_all.empty:
            st.info("No entries yet. Click Calculate & Save on the Dashboard to start your history.")
        else:
            st.caption("All logged entries (most recent shown first)")
            display_df = history_all.copy()
            display_df["date"] = display_df["date"].dt.date

            # Constrain width and reduce height for compact view
            st.markdown('<div style="max-width:1100px;margin:0 auto;">', unsafe_allow_html=True)
            st.dataframe(
                display_df.sort_values("date", ascending=False),
                use_container_width=True,
                height=220  # or keep per_activity_height if it already adapts by density
            )
            st.markdown('</div>', unsafe_allow_html=True)

            # CSV export
            csv_buf = io.StringIO()
            history_all.to_csv(csv_buf, index=False)
            st.download_button(
                label="⬇️ Download history CSV",
                data=csv_buf.getvalue(),
                file_name="history.csv",
                mime="text/csv",
                key="download_history_csv_history_tab",
            )

    with tab_breakdown:
        st.caption("Per-activity emissions (kg CO₂)")
        if per_activity:
            st.markdown('<div style="max-width:1100px;margin:0 auto;">', unsafe_allow_html=True)
            st.dataframe(
                pd.Series(per_activity, name="kg CO₂").sort_values(ascending=False).to_frame(),
                use_container_width=True,
                height=220  # or keep per_activity_height if you prefer density-aware sizing
            )
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No per-activity data to show yet.")
    
    with tab_energy_mix:
        st.subheader("Electricity Breakdown by Source")
        st.caption("Visualize your selected region's grid mix and how it affects electricity emissions.")

        # Region guidance
        if not region_code:
            st.info("Pick a Region in the sidebar (Regionalization) to view a real grid mix. Otherwise, defaults apply.")

        # Load grid mix for the current region (cached)
        try:
            mix = get_cached_mix(region_code)
        except Exception:
            mix = {}

        if mix:
            df_mix = pd.DataFrame([{"source": k.title(), "share": float(v)} for k, v in mix.items()])

            # Charts: pie + stacked bar (Altair) with fallback
            col_chart1, col_chart2 = st.columns([1, 1])
            
            with col_chart1:
                st.markdown("**Pie Chart**")
                try:
                    pie = alt.Chart(df_mix).mark_arc().encode(
                        theta=alt.Theta(field="share", type="quantitative", stack=True),
                        color=alt.Color(field="source", type="nominal", legend=alt.Legend(title="Source")),
                        tooltip=[alt.Tooltip("source:N"), alt.Tooltip("share:Q", format=".0%")],
                    ).properties(height=240)
                    st.altair_chart(pie, use_container_width=True)
                    
                    # Download button for pie chart (if altair_saver available)
                    if alt_save:
                        try:
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                                alt_save(pie, tmp.name, method="selenium")
                                with open(tmp.name, "rb") as f:
                                    st.download_button(
                                        "💾 Download Pie",
                                        data=f.read(),
                                        file_name=f"grid_mix_pie_{region_code or 'default'}.png",
                                        mime="image/png",
                                        key="btn_download_pie",
                                    )
                                os.unlink(tmp.name)
                        except Exception:
                            pass
                except Exception:
                    st.bar_chart(df_mix.set_index("source")["share"], height=240)
            
            with col_chart2:
                st.markdown("**Stacked Bar (Exact Shares)**")
                try:
                    # Stacked horizontal bar showing exact percentages
                    bar = alt.Chart(df_mix).mark_bar().encode(
                        x=alt.X("share:Q", stack="normalize", axis=alt.Axis(format=".0%", title="Share")),
                        color=alt.Color("source:N", legend=alt.Legend(title="Source")),
                        tooltip=[alt.Tooltip("source:N"), alt.Tooltip("share:Q", format=".2%")],
                    ).properties(height=240)
                    st.altair_chart(bar, use_container_width=True)
                    
                    # Download button for stacked bar (if altair_saver available)
                    if alt_save:
                        try:
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                                alt_save(bar, tmp.name, method="selenium")
                                with open(tmp.name, "rb") as f:
                                    st.download_button(
                                        "💾 Download Bar",
                                        data=f.read(),
                                        file_name=f"grid_mix_bar_{region_code or 'default'}.png",
                                        mime="image/png",
                                        key="btn_download_bar",
                                    )
                                os.unlink(tmp.name)
                        except Exception:
                            pass
                except Exception:
                    # Fallback: simple bar chart
                    st.bar_chart(df_mix.set_index("source")["share"], height=240)

            # Implied grid intensity (mix-based) and factor currently used by the engine
            implied = get_cached_implied_intensity(region_code)
            try:
                effective_ef = get_effective_electricity_factor(
                    region_code if 'region_code' in locals() else None,
                    renewable_adjust if 'renewable_adjust' in locals() else None,
                )
            except Exception:
                effective_ef = CO2_FACTORS.get("electricity_kwh", 0.233)

            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                st.metric("Implied mix intensity", f"{implied:.3f} kg/kWh" if implied is not None else "n/a")
            with c2:
                st.metric("Factor in use", f"{effective_ef:.3f} kg/kWh")
            with c3:
                try:
                    elec_kwh = float(user_data.get("electricity_kwh", 0) or 0)
                except Exception:
                    elec_kwh = 0.0
                elec_kg = elec_kwh * float(effective_ef)
                st.metric("Today's electricity CO₂", f"{elec_kg:.2f} kg")

            # Share of total emissions
            try:
                share_pct = (elec_kg / emissions * 100.0) if emissions and emissions > 0 else 0.0
            except Exception:
                share_pct = 0.0
            st.caption(f"Electricity share of today's total: {share_pct:.1f}% (Total: {fmt_emissions(emissions)})")

            # Factors source metadata
            try:
                meta = get_engine_meta(region_code)
                st.caption(f"Factors: {meta.get('source','Default')} {meta.get('version','')} {meta.get('url','')}")
            except Exception:
                pass
        else:
            st.info("No grid mix data available for the selected region.")
    
    with tab_intensity:
        st.subheader("Hourly Carbon Intensity")
        st.caption("See how grid carbon intensity varies over 24 hours, and plan high-load activities at low-intensity times.")

        # Controls
        col_s1, col_s2 = st.columns([2, 1])
        with col_s1:
            season = st.selectbox("Season", ["Spring", "Summer", "Autumn", "Winter"], index=0, key="intensity_season")
        with col_s2:
            st.caption("Profile adapts to your region's grid mix")

        # Get 24h profile (kg CO₂/kWh)
        profile = hourlyIntensityProfile(region_code if 'region_code' in locals() else None, season)

        # Chart with color-coded zones
        try:
            df_profile = pd.DataFrame({
                "Hour": list(range(24)),
                "Intensity": profile,
            })
            
            # Create Altair chart with color zones
            try:
                # Calculate thresholds for color zones
                min_val = min(profile)
                max_val = max(profile)
                range_val = max_val - min_val
                low_threshold = min_val + range_val * 0.33
                high_threshold = min_val + range_val * 0.67
                
                # Color by intensity level
                df_profile["Zone"] = df_profile["Intensity"].apply(
                    lambda x: "Low" if x < low_threshold else ("Medium" if x < high_threshold else "High")
                )
                
                chart = alt.Chart(df_profile).mark_area(
                    line={"color": "#1f77b4"},
                    color=alt.Gradient(
                        gradient="linear",
                        stops=[
                            alt.GradientStop(color="#10b981", offset=0),
                            alt.GradientStop(color="#fbbf24", offset=0.5),
                            alt.GradientStop(color="#ef4444", offset=1)
                        ],
                        x1=1, x2=1, y1=1, y2=0
                    )
                ).encode(
                    x=alt.X("Hour:Q", axis=alt.Axis(title="Hour of Day", format="02d")),
                    y=alt.Y("Intensity:Q", axis=alt.Axis(title="kg CO₂/kWh")),
                    tooltip=[
                        alt.Tooltip("Hour:Q", format="02d", title="Hour"),
                        alt.Tooltip("Intensity:Q", format=".4f", title="Intensity"),
                        alt.Tooltip("Zone:N", title="Zone")
                    ]
                ).properties(height=240, width=600)
                
                st.altair_chart(chart, use_container_width=True)
                
                # Download button
                if alt_save:
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                            alt_save(chart, tmp.name, method="selenium")
                            with open(tmp.name, "rb") as f:
                                st.download_button(
                                    "💾 Download Chart",
                                    data=f.read(),
                                    file_name=f"hourly_intensity_{region_code or 'default'}_{season}.png",
                                    mime="image/png",
                                    key="btn_download_intensity",
                                )
                            os.unlink(tmp.name)
                    except Exception:
                        pass
            except Exception:
                # Fallback to simple line chart
                idx = list(range(24))
                st.line_chart(pd.Series(profile, index=idx, name="kg CO₂/kWh"), height=220)
        except Exception:
            st.warning("Unable to render chart.")

        # Suggested low-intensity hours
        try:
            low_hours = suggest_low_hours(profile, top_n=3)
            low_hours_str = ", ".join([f"{h:02d}:00" for h in sorted(low_hours)])
            st.caption(f"Best low-carbon hours today: {low_hours_str}")
        except Exception:
            st.caption("Best low-carbon hours: n/a")

        st.divider()
        st.markdown("### What-if: shift a task to a better hour")

        # Activity presets + custom
        activity = st.selectbox("Activity", ["Laundry", "Air Conditioning", "Dishwasher", "Custom"], index=0, key="whatif_activity")
        default_kwh = 2.0 if activity in ["Laundry", "Dishwasher"] else (3.5 if activity == "Air Conditioning" else 1.0)
        task_kwh = st.number_input("Task energy (kWh)", min_value=0.0, step=0.1, value=default_kwh, key="whatif_kwh")
        hour = st.slider("Operating hour", min_value=0, max_value=23, value=20, format="%02d:00", key="whatif_hour")

        # Impact at chosen hour
        try:
            intensity_at_hour = float(profile[int(hour)])
        except Exception:
            intensity_at_hour = 0.0
        co2_kg = task_kwh * intensity_at_hour

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Intensity at selected hour", f"{intensity_at_hour:.3f} kg/kWh")
        with c2:
            st.metric("Estimated CO₂ for this task", f"{co2_kg:.2f} kg")

        # Optional: show comparison vs best hour
        try:
            best_hr = min(range(24), key=lambda h: profile[h])
            best_intensity = profile[best_hr]
            co2_best = task_kwh * best_intensity
            delta = co2_kg - co2_best
            tip_color = "green" if delta > 0 else "blue"
            st.caption(f"Suggestion: Run at {best_hr:02d}:00 for ~{co2_best:.2f} kg (Δ {delta:+.2f} kg).")
        except Exception:
            pass

        
        st.divider()
        st.markdown("### 💰 Annual Savings Calculator")
        st.caption("Calculate yearly CO₂ and cost savings from shifting a recurring task to the optimal hour.")
        
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            recurring_kwh = st.number_input("Daily energy use (kWh)", min_value=0.0, step=0.5, value=2.0, key="recurring_kwh")
        with col_a2:
            recurring_hour = st.slider("Current operating hour", min_value=0, max_value=23, value=20, format="%02d:00", key="recurring_hour")
        
        try:
            savings_data = calculate_annual_savings(recurring_kwh, recurring_hour, profile)
            
            col_s1, col_s2, col_s3, col_s4 = st.columns(4)
            with col_s1:
                st.metric("Best hour", f"{savings_data['best_hour']:02d}:00")
            with col_s2:
                st.metric("Daily savings", f"{savings_data['daily_savings_kg']:.2f} kg")
            with col_s3:
                st.metric("Yearly savings", f"{savings_data['yearly_savings_kg']:.1f} kg")
            with col_s4:
                st.metric("Cost savings/year", f"${savings_data['yearly_cost_savings_usd']:.2f}")
            
            st.caption(f"💡 Shifting from {recurring_hour:02d}:00 to {savings_data['best_hour']:02d}:00 saves {savings_data['savings_pct']:.1f}% CO₂ per day.")
        except Exception:
            st.warning("Unable to calculate savings.")
        
        st.divider()
        st.markdown("### 📊 Multi-Task Comparison")
        st.caption("Compare multiple household tasks and see which ones benefit most from load shifting.")
        
        # Initialize session state for tasks
        if "intensity_tasks" not in st.session_state:
            st.session_state["intensity_tasks"] = [
                {"name": "Laundry", "kwh": 2.0, "hour": 20},
                {"name": "Dishwasher", "kwh": 1.8, "hour": 21},
                {"name": "EV Charging", "kwh": 15.0, "hour": 18},
            ]
        
        # Editable task table
        df_tasks = pd.DataFrame(st.session_state["intensity_tasks"])
        edited_tasks = st.data_editor(
            df_tasks,
            num_rows="dynamic",
            use_container_width=True,
            key="intensity_tasks_editor",
            column_config={
                "name": st.column_config.TextColumn("Task Name"),
                "kwh": st.column_config.NumberColumn("Energy (kWh)", min_value=0.0, step=0.1),
                "hour": st.column_config.NumberColumn("Current Hour", min_value=0, max_value=23, step=1),
            },
        )
        
        # Update session state
        try:
            st.session_state["intensity_tasks"] = edited_tasks.to_dict("records")
        except Exception:
            pass
        
        # Compare button
        if st.button("🔍 Compare Tasks", key="btn_compare_tasks"):
            try:
                comparison = compare_tasks_at_hours(profile, st.session_state["intensity_tasks"])
                
                if comparison:
                    df_comparison = pd.DataFrame(comparison)
                    
                    # Show summary metrics
                    total_current = df_comparison["current_co2_kg"].sum()
                    total_optimal = df_comparison["optimal_co2_kg"].sum()
                    total_savings = total_current - total_optimal
                    
                    col_t1, col_t2, col_t3 = st.columns(3)
                    with col_t1:
                        st.metric("Current total CO₂", f"{total_current:.2f} kg")
                    with col_t2:
                        st.metric("Optimal total CO₂", f"{total_optimal:.2f} kg")
                    with col_t3:
                        st.metric("Total savings", f"{total_savings:.2f} kg", delta=f"-{(total_savings/total_current*100):.1f}%")
                    
                    # Detailed table
                    st.dataframe(
                        df_comparison[[
                            "name", "kwh", "current_hour", "current_co2_kg",
                            "optimal_hour", "optimal_co2_kg", "savings_kg", "savings_pct"
                        ]],
                        use_container_width=True,
                        height=300,
                    )
                    
                    # Highlight best opportunities
                    best_task = max(comparison, key=lambda t: t["savings_kg"])
                    st.success(f"🎯 Best opportunity: **{best_task['name']}** - shift from {best_task['current_hour']:02d}:00 to {best_task['optimal_hour']:02d}:00 to save {best_task['savings_kg']:.2f} kg CO₂ ({best_task['savings_pct']:.1f}%)")
                else:
                    st.info("No tasks to compare. Add tasks above.")
            except Exception as e:
                st.error(f"Comparison failed: {e}")

    # Score tab content
    with tab_score:
        st.subheader("Energy Efficiency Score")
        st.caption("A simple 0–100 score based on today’s per‑category emissions vs typical baselines.")

        # Compute score
        try:
            sc = efficiency_score(user_data)
        except Exception:
            sc = {"score": 50, "category_scores": {}, "badges": ["⚠️"], "notes": ["Scoring unavailable."]}

        score_val = int(sc.get("score", 50))
        cat_scores = sc.get("category_scores", {})
        badges = sc.get("badges", [])
        notes = sc.get("notes", [])

        # Big score metric
        c1, c2 = st.columns([1, 2])
        with c1:
            st.metric("Score", f"{score_val}/100")
            if badges:
                for b in badges:
                    st.caption(b)
        with c2:
            # Category bars
            try:
                df_cs = pd.DataFrame([
                    {"category": k, "score": v} for k, v in cat_scores.items()
                ])
                if not df_cs.empty:
                    st.bar_chart(df_cs.set_index("category")["score"], height=200)
            except Exception:
                pass

        # Notes
        if notes:
            st.markdown("**Guidance**")
            for n in notes:
                st.caption(f"- {n}")

    # Comparisons tab content
    with tab_compare:
        st.subheader("Comparisons and Trends")
        st.caption("Today vs yesterday and 7‑day average, plus per‑category trends.")

        # Today vs Yesterday
        try:
            df_hist = load_history()
        except Exception:
            df_hist = pd.DataFrame()

        try:
            y_total = get_yesterday_total(df_hist, selected_date if isinstance(selected_date, (dt.date, dt.datetime)) else dt.date.today())
        except Exception:
            y_total = 0.0

        # Basic metrics
        colA, colB, colC = st.columns(3)
        with colA:
            st.metric("Today", fmt_emissions(emissions))
        with colB:
            st.metric("Yesterday", fmt_emissions(y_total))
        with colC:
            try:
                pct = percentage_change(y_total, emissions)
                st.metric("Change vs yesterday", f"{pct:+.1f}%")
            except Exception:
                st.metric("Change vs yesterday", "n/a")

        # 7‑day average and sparkline
        try:
            if not df_hist.empty:
                dfx = df_hist.copy()
                dfx["date"] = pd.to_datetime(dfx["date"]).dt.date
                last7 = dfx.sort_values("date").tail(7)
                avg7 = float(last7["total_kg"].mean()) if not last7.empty else 0.0
            else:
                avg7 = 0.0
        except Exception:
            avg7 = 0.0

        colD, colE = st.columns([1, 2])
        with colD:
            st.metric("7‑day average", f"{avg7:.2f} kg")
        with colE:
            try:
                if not df_hist.empty:
                    d7 = df_hist.copy()
                    d7["date"] = pd.to_datetime(d7["date"]).dt.date
                    last7 = d7.sort_values("date").tail(7)
                    st.line_chart(last7.set_index("date")["total_kg"], height=180)
            except Exception:
                pass

        # Per‑category sparklines (derived from last 7 rows if available)
        try:
            if not df_hist.empty:
                d7 = df_hist.copy()
                d7["date"] = pd.to_datetime(d7["date"]).dt.date
                last7 = d7.sort_values("date").tail(7)
                # compute per‑category from existing columns per day
                cat_series = {}
                for _, row in last7.iterrows():
                    rdict = {k: float(row.get(k, 0) or 0) for k in ALL_KEYS}
                    cats = compute_category_emissions(rdict)
                    for c, v in cats.items():
                        cat_series.setdefault(c, []).append(float(v))
                if cat_series:
                    st.markdown("**Per‑category trends (last 7 entries)**")
                    cc1, cc2, cc3 = st.columns(3)
                    cols = [cc1, cc2, cc3]
                    i = 0
                    for c, vals in cat_series.items():
                        with cols[i % 3]:
                            try:
                                idx = list(range(len(vals)))
                                st.line_chart(pd.Series(vals, index=idx, name=c), height=140)
                                st.caption(c)
                            except Exception:
                                pass
                        i += 1
        except Exception:
            pass
    
    # Offsets tab content
    with tab_offsets:
        st.subheader("Offset Suggestions")
        st.caption("Estimate the cost to offset today or this week. Prices and mix are illustrative (no API).")

        # Inputs
        price = st.slider("Offset price (USD per tCO₂e)", min_value=5, max_value=200, value=15, step=1, key="offset_price")

        # Compute last 7 sum to represent "this week"
        try:
            df_hist = load_history()
        except Exception:
            df_hist = pd.DataFrame()

        week_sum = 0.0
        try:
            if not df_hist.empty:
                dfx = df_hist.copy()
                dfx["date"] = pd.to_datetime(dfx["date"]).dt.date
                last7 = dfx.sort_values("date").tail(7)
                week_sum = float(last7["total_kg"].sum()) if not last7.empty else float(emissions or 0.0)
            else:
                week_sum = float(emissions or 0.0)
        except Exception:
            week_sum = float(emissions or 0.0)

        offs = estimate_offsets(float(emissions or 0.0), float(week_sum or 0.0), float(price))

        c1, c2 = st.columns(2)
        with c1:
            t = offs["today"]
            st.markdown("**Today**")
            st.metric("Tonnes CO₂e", f"{t['tonnes']:.3f} t")
            st.metric("Estimated cost", f"${t['cost_usd']:.2f}")
            st.caption(f"Price: ${t['price_per_tonne']:.0f}/tCO₂e")
            st.caption("Suggested mix:")
            try:
                df_mix = pd.DataFrame(t["mix"])
                st.bar_chart(df_mix.set_index("project")["share"], height=160)
            except Exception:
                pass
        with c2:
            w = offs.get("week")
            st.markdown("**This week**")
            if w:
                st.metric("Tonnes CO₂e", f"{w['tonnes']:.3f} t")
                st.metric("Estimated cost", f"${w['cost_usd']:.2f}")
                st.caption(f"Price: ${w['price_per_tonne']:.0f}/tCO₂e")
                st.caption("Suggested mix:")
                try:
                    df_mix_w = pd.DataFrame(w["mix"])
                    st.bar_chart(df_mix_w.set_index("project")["share"], height=160)
                except Exception:
                    pass
            else:
                st.info("Not enough data to build a weekly sum.")
    
    # Planner tab content
    with tab_planner:
        st.subheader("7‑Day Forecast & Weekly Goal")
        st.caption("Simple forecast from your history, plus a weekly target planner.")

        # Prepare last N totals
        try:
            df_hist = load_history()
        except Exception:
            df_hist = pd.DataFrame()

        last_totals = []
        try:
            if not df_hist.empty:
                dfx = df_hist.copy()
                dfx["date"] = pd.to_datetime(dfx["date"]).dt.date
                dfx = dfx.sort_values("date")
                last_totals = dfx["total_kg"].tail(14).astype(float).tolist()
            else:
                last_totals = [float(emissions or 0.0)]
        except Exception:
            last_totals = [float(emissions or 0.0)]

        # Forecast
        fc = simple_forecast_next7(last_totals)
        try:
            idx = [f"D+{i+1}" for i in range(7)]
            st.line_chart(pd.Series(fc, index=idx, name="Forecast (kg CO₂)"), height=220)
        except Exception:
            st.warning("Unable to render forecast.")

        # Weekly goal planner
        st.markdown("### Weekly goal")
        # Compute current week sum (last 7 entries)
        try:
            current_week_sum = 0.0
            remaining_days = 7
            if not df_hist.empty:
                dfx = df_hist.copy()
                dfx["date"] = pd.to_datetime(dfx["date"]).dt.date
                last7 = dfx.sort_values("date").tail(7)
                current_week_sum = float(last7["total_kg"].sum()) if not last7.empty else float(emissions or 0.0)
                remaining_days = int(7 - len(last7)) if not last7.empty else 6
                remaining_days = max(1, min(7, remaining_days))
            else:
                current_week_sum = float(emissions or 0.0)
                remaining_days = 6
        except Exception:
            current_week_sum = float(emissions or 0.0)
            remaining_days = 6

        target = st.number_input("Weekly target (kg CO₂)", min_value=0.0, value=max(0.0, round(current_week_sum + sum(fc), 1)), step=1.0)
        plan = weekly_goal_plan(current_week_sum, remaining_days, float(target))

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Required per remaining day", f"{plan['required_per_day']:.2f} kg/day")
        with c2:
            st.metric("Delta vs current daily avg", f"{plan['delta_vs_current_avg']:+.2f} kg/day")

        st.markdown("### What‑if reductions")
        colA, colB, colC = st.columns(3)
        with colA:
            r_energy = st.slider("Energy reduction (%)", 0, 50, 10, help="Apply to electricity/gas inputs.")
        with colB:
            r_transport = st.slider("Transport reduction (%)", 0, 50, 10)
        with colC:
            r_meals = st.slider("Meals reduction (%)", 0, 50, 10)

        # Rough what‑if: scale today's inputs by category and recompute total
        try:
            tmp = dict(user_data or {})
            for k in CATEGORY_MAP["Energy"]:
                if k in tmp and isinstance(tmp[k], (int, float)):
                    tmp[k] = float(tmp[k]) * (1.0 - r_energy/100.0)
            for k in CATEGORY_MAP["Transport"]:
                if k in tmp and isinstance(tmp[k], (int, float)):
                    tmp[k] = float(tmp[k]) * (1.0 - r_transport/100.0)
            for k in CATEGORY_MAP["Meals"]:
                if k in tmp and isinstance(tmp[k], (int, float)):
                    tmp[k] = float(tmp[k]) * (1.0 - r_meals/100.0)
            # Re-estimate emissions locally
            em_whatif = 0.0
            for k, v in tmp.items():
                try:
                    em_whatif += float(v or 0) * CO2_FACTORS.get(k, 0.0)
                except Exception:
                    pass
        except Exception:
            em_whatif = float(emissions or 0.0)

        st.caption(f"What‑if estimated total today: {em_whatif:.2f} kg (current: {fmt_emissions(emissions)})")

    # renewables tab content    
    with tab_renewables:
        st.subheader("Renewables Tracker")
        st.caption("See how your renewable percentage affects electricity emissions. Uses your current sidebar setting when no region is selected.")

        # Current renewable settings (from sidebar)
        try:
            renewable_pct = int(st.session_state.get("ui_renewable_pct_box", 0))
        except Exception:
            renewable_pct = 0
        st.metric("Renewable adjustment", f"{renewable_pct}%")

        # Base vs adjusted electricity factor
        try:
            base_ef = float(CO2_FACTORS.get("electricity_kwh", 0.233))
            # If a region is selected, factor is governed by that region and not the renewable slider.
            if region_code:
                # Factor in use via region
                ef_use = float(get_effective_electricity_factor(region_code, None))
                note = "Region override active. Renewable slider does not apply."
            else:
                ef_use = float(get_effective_electricity_factor(None, renewable_pct / 100.0))
                note = "Default region. Renewable slider applies."
        except Exception:
            ef_use = base_ef
            note = "Factor unavailable, using defaults."

        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            st.metric("Base factor", f"{base_ef:.3f} kg/kWh")
        with c2:
            st.metric("Factor in use", f"{ef_use:.3f} kg/kWh")
        with c3:
            delta = base_ef - ef_use
            st.metric("Delta vs base", f"{delta:+.3f} kg/kWh")
            st.caption(note)

        # Estimated savings for today from renewable adjustment (only when default region)
        try:
            elec_kwh_today = float(user_data.get("electricity_kwh", 0) or 0)
        except Exception:
            elec_kwh_today = 0.0
        savings_today = elec_kwh_today * max(0.0, base_ef - (ef_use if not region_code else base_ef))
        st.caption(f"Estimated savings today: {savings_today:.2f} kg CO₂")

        # Weekly (last 7 entries) savings estimate, only when default region
        try:
            df_hist = load_history()
        except Exception:
            df_hist = pd.DataFrame()

        try:
            if not df_hist.empty:
                dfx = df_hist.copy()
                dfx["date"] = pd.to_datetime(dfx["date"]).dt.date
                last7 = dfx.sort_values("date").tail(7)
                if not last7.empty:
                    kwh7 = float(last7.get("electricity_kwh", pd.Series(dtype=float)).fillna(0.0).sum())
                else:
                    kwh7 = float(elec_kwh_today)
            else:
                kwh7 = float(elec_kwh_today)
        except Exception:
            kwh7 = float(elec_kwh_today)

        savings_week = kwh7 * max(0.0, base_ef - (ef_use if not region_code else base_ef))
        st.caption(f"Estimated savings (last 7 entries): {savings_week:.2f} kg CO₂")

        # Simple visualization: base vs adjusted factor bar
        try:
            df_f = pd.DataFrame({"factor": ["Base", "In use"], "kg_per_kwh": [base_ef, ef_use]})
            st.bar_chart(df_f.set_index("factor")["kg_per_kwh"], height=180)
        except Exception:
            pass
    
    # leaderboard tab content
    with tab_leaderboard:
        st.subheader("Local Leaderboard")
        st.caption("Your best streaks and days from local history.")

        try:
            df_hist = load_history()
        except Exception:
            df_hist = pd.DataFrame()

        # Cards: best (lowest) day, highest day, best 7-day average, longest streak
        low_day, high_day, best_avg7, longest_streak = None, None, None, 0
        try:
            if not df_hist.empty:
                dfx = df_hist.copy()
                dfx["date"] = pd.to_datetime(dfx["date"]).dt.date
                dfx = dfx.sort_values("date")

                # Lowest and highest single days
                low_idx = dfx["total_kg"].idxmin()
                high_idx = dfx["total_kg"].idxmax()
                if pd.notna(low_idx):
                    low_day = (dfx.loc[low_idx, "date"], float(dfx.loc[low_idx, "total_kg"]))
                if pd.notna(high_idx):
                    high_day = (dfx.loc[high_idx, "date"], float(dfx.loc[high_idx, "total_kg"]))

                # Best 7-day rolling average
                if len(dfx) >= 7:
                    roll = dfx["total_kg"].rolling(7).mean()
                    ridx = roll.idxmin()
                    if pd.notna(ridx):
                        best_avg7 = float(roll.loc[ridx])

                # Longest streak
                # Recompute streaks by scanning consecutive dates
                dates = sorted(dfx["date"].unique())
                max_streak, cur = 0, 1 if dates else 0
                for i in range(1, len(dates)):
                    if dates[i] == dates[i-1] + dt.timedelta(days=1):
                        cur += 1
                    else:
                        max_streak = max(max_streak, cur)
                        cur = 1
                longest_streak = max(max_streak, cur)
        except Exception:
            pass

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if low_day:
                st.metric("Lowest day", f"{low_day[1]:.2f} kg", delta=None, help=str(low_day[0]))
            else:
                st.metric("Lowest day", "n/a")
        with c2:
            if high_day:
                st.metric("Highest day", f"{high_day[1]:.2f} kg", delta=None, help=str(high_day[0]))
            else:
                st.metric("Highest day", "n/a")
        with c3:
            st.metric("Best 7-day avg", f"{(best_avg7 if best_avg7 is not None else 0.0):.2f} kg")
        with c4:
            st.metric("Longest streak", f"{int(longest_streak)} days")

        # Top 5 lowest days table
        try:
            if not df_hist.empty:
                dfx2 = df_hist.copy()
                dfx2["date"] = pd.to_datetime(dfx2["date"]).dt.date
                top5 = dfx2.sort_values("total_kg").head(5)[["date", "total_kg"]]
                st.markdown("**Top 5 lowest days**")
                st.dataframe(top5.set_index("date"), use_container_width=True, height=180)
        except Exception:
            pass

        # Last 30 days chart
        try:
            if not df_hist.empty:
                d30 = df_hist.copy()
                d30["date"] = pd.to_datetime(d30["date"]).dt.date
                d30 = d30.sort_values("date").tail(30)
                st.markdown("**Last 30 entries**")
                st.bar_chart(d30.set_index("date")["total_kg"], height=200)
        except Exception:
            pass

    # estimators tab content
    with tab_estimator:
        st.subheader("Smart Home Energy Estimator")
        st.caption("Estimate daily electricity use from appliances, then apply it to your inputs.")

        # Default table rows + persistence + controls
        default_rows = [
            {"Appliance": "Fridge", "Power_W": 150, "Hours_per_day": 24.0},
            {"Appliance": "AC", "Power_W": 1200, "Hours_per_day": 4.0},
            {"Appliance": "Lights", "Power_W": 60, "Hours_per_day": 6.0},
        ]
        if "appliance_estimator_df" not in st.session_state:
            st.session_state["appliance_estimator_df"] = pd.DataFrame(
                default_rows, columns=["Appliance", "Power_W", "Hours_per_day"]
            )

        # Controls: CSV import/export, period toggle, quick presets
        ctop1, ctop2, ctop3, ctop4 = st.columns([1, 1, 1, 2])
        with ctop1:
            uploaded = st.file_uploader("Import CSV", type=["csv"], key="appliance_csv_upl")
        with ctop2:
            try:
                st.download_button(
                    label="Export CSV",
                    data=st.session_state["appliance_estimator_df"].to_csv(index=False).encode("utf-8"),
                    file_name="appliances.csv",
                    mime="text/csv",
                    key="appliance_csv_dl",
                )
            except Exception:
                st.warning("Unable to prepare CSV right now.")
        with ctop3:
            period = st.selectbox("Period", ["Daily", "Monthly", "Yearly"], index=0, key="appliance_period")
        with ctop4:
            # Enhanced device browser with categories
            with st.popover("📚 Device Library (50+ presets)"):
                # Season selector for automatic adjustments
                season_est = st.selectbox(
                    "Season (for climate devices)",
                    ["Spring", "Summer", "Autumn", "Winter"],
                    index=1,
                    key="estimator_season",
                    help="Automatically adjusts AC/heating usage based on season"
                )
                
                st.caption("Click any device to add it to your list")
                
                # Get devices by category
                try:
                    categories = get_device_presets_by_category()
                except Exception:
                    categories = {}
                
                # Display by category with expanders
                for category in sorted(categories.keys()):
                    with st.expander(f"{category} ({len(categories[category])} devices)"):
                        for device_name in sorted(categories[category]):
                            if st.button(f"➕ {device_name}", key=f"add_preset_{device_name}"):
                                try:
                                    device_info = DEVICE_PRESETS[device_name]
                                    base_hours = device_info["hours_per_day"]
                                    
                                    # Apply seasonal adjustment
                                    adjusted_hours = apply_seasonal_adjustment(device_name, season_est, base_hours)
                                    
                                    new_row = {
                                        "Appliance": device_name,
                                        "Power_W": device_info["power_w"],
                                        "Hours_per_day": adjusted_hours,
                                    }
                                    
                                    st.session_state["appliance_estimator_df"] = pd.concat(
                                        [st.session_state["appliance_estimator_df"], pd.DataFrame([new_row])],
                                        ignore_index=True,
                                    )
                                    st.success(f"Added {device_name}")
                                except Exception as e:
                                    st.warning(f"Could not add {device_name}: {e}")
            
            # Quick household profiles
            with st.popover("🏠 Quick Profiles"):
                st.caption("Load common household setups")
                
                if st.button("🏢 Small Apartment", key="profile_small_apt"):
                    try:
                        profile_devices = [
                            {"Appliance": "Refrigerator", "Power_W": 150, "Hours_per_day": 24.0},
                            {"Appliance": "Laptop", "Power_W": 65, "Hours_per_day": 6.0},
                            {"Appliance": "TV (LED 40-50\")", "Power_W": 90, "Hours_per_day": 4.0},
                            {"Appliance": "LED Bulb (10W)", "Power_W": 10, "Hours_per_day": 5.0},
                            {"Appliance": "Washing Machine", "Power_W": 500, "Hours_per_day": 0.7},
                            {"Appliance": "Microwave", "Power_W": 1200, "Hours_per_day": 0.3},
                        ]
                        st.session_state["appliance_estimator_df"] = pd.DataFrame(profile_devices)
                        st.success("Loaded Small Apartment profile")
                    except Exception:
                        st.warning("Could not load profile")
                
                if st.button("🏡 Family Home", key="profile_family_home"):
                    try:
                        profile_devices = [
                            {"Appliance": "Refrigerator", "Power_W": 150, "Hours_per_day": 24.0},
                            {"Appliance": "Freezer", "Power_W": 100, "Hours_per_day": 24.0},
                            {"Appliance": "Dishwasher", "Power_W": 1800, "Hours_per_day": 1.0},
                            {"Appliance": "Washing Machine", "Power_W": 500, "Hours_per_day": 0.7},
                            {"Appliance": "Dryer", "Power_W": 3000, "Hours_per_day": 0.8},
                            {"Appliance": "TV (OLED 55-65\")", "Power_W": 150, "Hours_per_day": 5.0},
                            {"Appliance": "Desktop PC", "Power_W": 200, "Hours_per_day": 4.0},
                            {"Appliance": "Laptop", "Power_W": 65, "Hours_per_day": 4.0},
                            {"Appliance": "Air Conditioner (Large)", "Power_W": 1800, "Hours_per_day": 6.0},
                            {"Appliance": "Electric Water Heater", "Power_W": 4000, "Hours_per_day": 2.0},
                        ]
                        st.session_state["appliance_estimator_df"] = pd.DataFrame(profile_devices)
                        st.success("Loaded Family Home profile")
                    except Exception:
                        st.warning("Could not load profile")
                
                if st.button("⚡ High-Tech Home", key="profile_hightech"):
                    try:
                        profile_devices = [
                            {"Appliance": "Refrigerator", "Power_W": 150, "Hours_per_day": 24.0},
                            {"Appliance": "Desktop PC", "Power_W": 200, "Hours_per_day": 8.0},
                            {"Appliance": "Gaming Console", "Power_W": 150, "Hours_per_day": 4.0},
                            {"Appliance": "TV (OLED 55-65\")", "Power_W": 150, "Hours_per_day": 6.0},
                            {"Appliance": "Monitor", "Power_W": 30, "Hours_per_day": 10.0},
                            {"Appliance": "Router/Modem", "Power_W": 10, "Hours_per_day": 24.0},
                            {"Appliance": "Smart Speaker", "Power_W": 3, "Hours_per_day": 24.0},
                            {"Appliance": "Security Camera", "Power_W": 5, "Hours_per_day": 24.0},
                            {"Appliance": "EV Charging (Level 2)", "Power_W": 7200, "Hours_per_day": 4.0},
                            {"Appliance": "Central AC", "Power_W": 3500, "Hours_per_day": 8.0},
                        ]
                        st.session_state["appliance_estimator_df"] = pd.DataFrame(profile_devices)
                        st.success("Loaded High-Tech Home profile")
                    except Exception:
                        st.warning("Could not load profile")

        # Handle CSV import
        if uploaded is not None:
            try:
                imp = pd.read_csv(uploaded)
                needed = {"Appliance", "Power_W", "Hours_per_day"}
                if not needed.issubset(set(imp.columns)):
                    st.error("CSV must contain columns: Appliance, Power_W, Hours_per_day")
                else:
                    st.session_state["appliance_estimator_df"] = imp[list(needed)]
                    st.success("Imported.")
            except Exception as e:
                st.error(f"Failed to import CSV: {e}")

        st.caption("💡 **Tip:** Use the Device Library to quickly add appliances, or edit the table directly. kWh/day and CO₂/day are computed automatically.")
        
        # Show device count and total power
        try:
            device_count = len(st.session_state["appliance_estimator_df"])
            total_power = st.session_state["appliance_estimator_df"]["Power_W"].sum()
            st.caption(f"📊 **{device_count} devices** | Total rated power: **{total_power:,.0f} W**")
        except Exception:
            pass
        df = st.data_editor(
            st.session_state["appliance_estimator_df"],
            num_rows="dynamic",
            use_container_width=True,
            key="appliance_estimator_table",
            column_config={
                "Appliance": st.column_config.TextColumn("Appliance"),
                "Power_W": st.column_config.NumberColumn("Power (W)", min_value=0, step=10),
                "Hours_per_day": st.column_config.NumberColumn("Hours/day", min_value=0.0, step=0.25),
            },
        )
        # Persist editor changes
        try:
            st.session_state["appliance_estimator_df"] = df.copy()
        except Exception:
            pass

        # Compute per-row and total kWh/day
        def _row_kwh(w, h):
            try:
                wv = max(0.0, float(w))
                hv = max(0.0, float(h))
                return (wv * hv) / 1000.0
            except Exception:
                return 0.0

        df_calc = df.copy()
        df_calc["kWh_day"] = df_calc.apply(
            lambda r: _row_kwh(r.get("Power_W", 0), r.get("Hours_per_day", 0)), axis=1
        )
        
        # Determine effective electricity factor consistent with v2 rules
        try:
            effective_ef = get_effective_electricity_factor(
                region_code if 'region_code' in locals() else None,
                renewable_adjust if 'renewable_adjust' in locals() else None,
            )
        except Exception:
            effective_ef = CO2_FACTORS.get("electricity_kwh", 0.233)

        # Per-row CO2/day and totals
        df_calc["CO2_kg_day"] = df_calc["kWh_day"] * float(effective_ef)
        total_kwh_day = float(df_calc["kWh_day"].sum() if "kWh_day" in df_calc.columns else 0.0)
        total_co2_day = float(df_calc["CO2_kg_day"].sum() if "CO2_kg_day" in df_calc.columns else 0.0)

        # Period scaling
        mult = 1.0
        unit_energy = "kWh/day"
        unit_co2 = "kg/day"
        if period == "Monthly":
            mult = 30.0
            unit_energy = "kWh/month"
            unit_co2 = "kg/month"
        elif period == "Yearly":
            mult = 365.0
            unit_energy = "kWh/year"
            unit_co2 = "kg/year"

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            st.metric("Total energy", f"{total_kwh_day*mult:.2f} {unit_energy}")
        with c2:
            st.metric("Factor used", f"{effective_ef:.3f} kg/kWh")
        with c3:
            st.metric("Estimated CO₂", f"{total_co2_day*mult:.2f} {unit_co2}")

        st.caption("Tip: This estimate uses your current Regionalization settings (region and renewable %).")

        # Show table with computed kWh/day and CO2/day
        st.dataframe(
            df_calc["Appliance Power_W Hours_per_day kWh_day CO2_kg_day".split()],
            use_container_width=True,
            height=260,
        )

        # Apply into main inputs (prefill electricity_kwh)
        if st.button("↪️ Apply to Energy inputs (electricity_kwh)"):
            try:
                st.session_state["_pending_values"] = {"electricity_kwh": float(total_kwh_day)}
                st.success("Applied. The Electricity (kWh) field will be prefilled on reload.")
                try:
                    st.rerun()
                except Exception:
                    pass
            except Exception as e:
                st.error(f"Could not apply: {e}")

    with tab_tips:
        icon_hdr, dom_hdr = dominant_category_icon(user_data)
        st.subheader(f"{icon_hdr} Personalized Eco Tips")
        st.caption(f"Get a personalized tip based on today’s inputs and total emissions. Dominant today: {dom_hdr}.")

        # API source badge (GPT vs Fallback)
        src_raw = getattr(ai_tips, "LAST_TIP_SOURCE", "unknown")
        source = st.session_state.get("last_tip_source") or (
            "GPT" if src_raw == "gpt" else ("Fallback" if src_raw == "fallback" else "Unknown")
        )
        badge_color = "#16a34a" if source == "GPT" else ("#6b7280" if source == "Fallback" else "#9ca3af")
        st.markdown(f"<div style='display:inline-block;padding:2px 8px;border-radius:12px;background:{badge_color};color:white;font-size:0.85em;'>AI source: {source}</div>", unsafe_allow_html=True)

        # Compact summary of today's inputs for context
        st.markdown("**Summary of today’s activities**")
        summary_str = format_summary(user_data)
        # Colored tag summary (HTML)
        st.markdown(format_summary_html(user_data), unsafe_allow_html=True)
        # Explicitly show today's total emissions coming from backend/session
        em_today = float(st.session_state.get("emissions_today", emissions))
        st.metric("Today's total (backend)", fmt_emissions(em_today))
        # Copy-ready block using Streamlit's built-in copy icon on code blocks
        st.caption("Copy-ready summary (use the copy icon on the right):")
        st.code(summary_str)
        
        # --- Quick PDF export (early) ---
        try:
            # Basics
            tip_for_pdf = st.session_state.get("last_tip_full") or st.session_state.get("last_tip") or ""
            date_str = (selected_date.isoformat() if isinstance(selected_date, (dt.date, dt.datetime)) else str(selected_date))
            src_label = st.session_state.get("last_tip_source", "Unknown")

            # Build data for PDF
            per_activity_local = calculate_co2_breakdown_v2(
                user_data,
                region_code=region_code if 'region_code' in locals() else None,
                renewable_adjust=renewable_adjust if 'renewable_adjust' in locals() else None,
            )
            cat_breakdown = compute_category_emissions(user_data)

            # Optional logo
            logo_bytes = None
            try:
                logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
                if os.path.exists(logo_path):
                    with open(logo_path, "rb") as lf:
                        logo_bytes = lf.read()
            except Exception:
                logo_bytes = None

            # Safe defaults for PDF options (in case controls render later in the tab)
            pdf_title = st.session_state.get("pdf_title", "Eco Tips Report")
            pdf_primary_color = st.session_state.get("pdf_primary_color", "#2563EB")
            pdf_text_color = st.session_state.get("pdf_text_color", "#111827")
            pdf_chart_bg = st.session_state.get("pdf_chart_bg", "#FFFFFF")
            pdf_side_margin = float(st.session_state.get("pdf_side_margin", 1.5))
            pdf_top_margin = float(st.session_state.get("pdf_top_margin", 1.5))
            pdf_bottom_margin = float(st.session_state.get("pdf_bottom_margin", 1.5))
            pdf_include_pie = bool(st.session_state.get("pdf_include_pie", True))
            pdf_include_spark = bool(st.session_state.get("pdf_include_spark", False))
            pdf_include_footer = bool(st.session_state.get("pdf_include_footer", False))
            pdf_footer_text = st.session_state.get("pdf_footer_text", "")

            # Current emissions and context
            em_today = float(st.session_state.get("emissions_today", emissions))
            ctx = {
                "today_total": fmt_emissions(em_today),
                "yesterday_total": fmt_emissions(yesterday_total) if 'yesterday_total' in locals() else "",
                "delta_pct": f"{percentage_change(yesterday_total, em_today):.2f}%" if 'yesterday_total' in locals() else "",
                "streak_days": f"{streak} days" if 'streak' in locals() else "",
            }

            pdf_bytes, err = build_eco_tips_pdf(
                summary_str,
                tip_for_pdf,
                st.session_state.get("ai_summary_text"),  # may be None
                em_today,
                date_str,
                src_label,
                per_activity_local,
                cat_breakdown,
                ctx,
                logo_bytes=logo_bytes,
                title_text=pdf_title,
                primary_color=pdf_primary_color,
                include_pie=pdf_include_pie,
                include_sparklines=pdf_include_spark,
                spark_data=None,
                footer_text=pdf_footer_text if pdf_include_footer else None,
                margins_cm={"side": pdf_side_margin, "top": pdf_top_margin, "bottom": pdf_bottom_margin},
                text_hex=pdf_text_color,
                chart_bg_hex=pdf_chart_bg,
                experiments_appendix=None,
            )

            if pdf_bytes:
                st.download_button(
                    label=" Download Eco Tips PDF (Quick)",
                    data=pdf_bytes,
                    file_name=f"eco_tips_{date_str}.pdf",
                    mime="application/pdf",
                    key="download_eco_tips_pdf_quick",
                )
                st.caption("Includes summary, tip, optional AI summary, per‑activity and category tables. Charts omitted in quick export.")
            else:
                if err:
                    st.info(f"PDF not ready: {err}")
        except Exception as e:
            st.warning(f"Quick PDF export unavailable: {e}")

        # Optional AI-powered summary alongside the rule-based one
        ai_open_default = bool(get_pref("exp_ai_summary_open", False))
        with st.expander("AI Summary (beta)", expanded=ai_open_default):
            ai_col1, ai_col2 = st.columns([1, 2])
            with ai_col1:
                default_show_ai = bool(get_pref("default_show_ai_summary", st.session_state.get("use_ai_summary", False)))
                use_ai_summary = st.checkbox(
                    "Show AI summary",
                    value=default_show_ai,
                    key="use_ai_summary",
                )
                pers_toggle = st.checkbox(
                    "Use AI summary by default",
                    value=default_show_ai,
                    key="use_ai_summary_default_toggle",
                    help="Save this as the default for future sessions",
                )
                if pers_toggle != default_show_ai:
                    set_pref("default_show_ai_summary", bool(pers_toggle))
            with ai_col2:
                regen_ai = st.button("🔁 Regenerate AI summary", disabled=not st.session_state.get("use_ai_summary", False))

            ai_open_toggle = st.checkbox("Open this section by default", value=ai_open_default, key="exp_ai_summary_open_toggle")
            if ai_open_toggle != ai_open_default:
                set_pref("exp_ai_summary_open", bool(ai_open_toggle))

        # Prompt experiments (choose structure and optional category)
        exp_open_default = bool(get_pref("exp_prompt_experiments_open", False))
        with st.expander("Prompt experiments", expanded=exp_open_default):
            exp_col1, exp_col2, exp_col3, exp_col4 = st.columns([1.2, 1.2, 1, 1])
            with exp_col1:
                default_mode = get_pref("default_prompt_mode", st.session_state.get("prompt_mode", "Contextualized"))
                prompt_mode = st.selectbox(
                    "Prompt mode",
                    options=["Contextualized", "Directive", "Persona"],
                    index=["Contextualized", "Directive", "Persona"].index(default_mode if default_mode in ["Contextualized", "Directive", "Persona"] else "Contextualized"),
                    key="prompt_mode",
                    help="Switch between different prompt structures",
                )
                if prompt_mode != default_mode:
                    set_pref("default_prompt_mode", prompt_mode)
            with exp_col2:
                default_cat = get_pref("default_prompt_category", st.session_state.get("prompt_category_opt", "Auto/None"))
                category_opt = st.selectbox(
                    "Category (optional)",
                    options=["Auto/None", "Energy", "Transport", "Meals"],
                    index=( ["Auto/None", "Energy", "Transport", "Meals"].index(default_cat) if (isinstance(default_cat, str) and default_cat in ["Auto/None", "Energy", "Transport", "Meals"]) else 0 ),
                    key="prompt_category_opt",
                    help="Adds a focus hint to the prompt if selected",
                )
                if category_opt != default_cat:
                    set_pref("default_prompt_category", category_opt)
            with exp_col3:
                default_quick = int(get_pref("d6_varN", st.session_state.get("d6_varN", 1)))
                varN_quick = st.number_input(
                    "Randomized variations (N)",
                    min_value=1, max_value=10,
                    value=default_quick,
                    step=1,
                    key="d6_varN_quick",
                    help="Run each scenario N times with small random perturbations to stress-test diversity."
                )
                if int(varN_quick) != default_quick:
                    st.session_state["d6_varN"] = int(varN_quick)
                    set_pref("d6_varN", int(varN_quick))
            with exp_col4:
                run_exp = st.button("🧪 Run prompt experiment")

            exp_open_toggle = st.checkbox("Open this section by default", value=exp_open_default, key="exp_prompt_experiments_open_toggle")
            if exp_open_toggle != exp_open_default:
                set_pref("exp_prompt_experiments_open", bool(exp_open_toggle))

        # Prompt log analysis
        log_open_default = bool(get_pref("exp_prompt_log_open", False))
        with st.expander("Prompt log analysis", expanded=log_open_default):
            log_path = os.path.join(os.getcwd(), "prompt_log.csv")
            if not os.path.exists(log_path):
                st.info("No prompt_log.csv found yet. Run a prompt experiment to create it.")
            else:
                try:
                    df_log = pd.read_csv(log_path)
                except Exception as e:
                    st.error(f"Could not read prompt_log.csv: {e}.")
                    df_log = None

                if df_log is not None and not df_log.empty:
                    # Basic hygiene
                    df_log["tip"] = df_log.get("tip", "").astype(str)
                    df_log["prompt"] = df_log.get("prompt", "").astype(str)
                    # Parse timestamp if present
                    if "timestamp" in df_log.columns:
                        with pd.option_context('mode.copy_on_write', False):
                            try:
                                df_log["timestamp"] = pd.to_datetime(df_log["timestamp"], errors="coerce")
                            except Exception:
                                pass

                    # Category filter
                    cats = sorted([c for c in df_log.get("category", pd.Series(dtype=str)).dropna().unique().tolist() if str(c).strip()])
                    chosen_cat = st.selectbox("Filter by category", options=["All"] + cats, index=0)
                    dfv = df_log if chosen_cat == "All" else df_log[df_log["category"].astype(str) == chosen_cat]
                    # Mode filter
                    modes = sorted([m for m in df_log.get("mode", pd.Series(dtype=str)).dropna().unique().tolist() if str(m).strip()])
                    chosen_mode = st.selectbox("Filter by mode", options=["All"] + modes, index=0)
                    if chosen_mode != "All":
                        dfv = dfv[dfv["mode"].astype(str) == chosen_mode]
                    if dfv.empty:
                        st.info("No rows match the current filter.")
                        st.stop()

                    total = len(dfv)
                    tip_words = dfv["tip"].fillna("").apply(lambda s: len(str(s).split()))
                    tip_chars = dfv["tip"].fillna("").apply(lambda s: len(str(s)))
                    avg_words = float(tip_words.mean()) if total else 0.0
                    avg_chars = float(tip_chars.mean()) if total else 0.0
                    uniq_tips = dfv["tip"].fillna("").str.strip().str.lower().nunique()
                    uniq_pct = (uniq_tips / total * 100.0) if total else 0.0
                    fallback_mask = dfv["prompt"].fillna("").str.contains("Fallback used", case=False, na=False)
                    fallback_count = int(fallback_mask.sum())

                    cA, cB, cC, cD = st.columns(4)
                    with cA:
                        st.metric("Samples", f"{total}")
                    with cB:
                        st.metric("Avg tip length (words)", f"{avg_words:.1f}")
                    with cC:
                        st.metric("Unique tips", f"{uniq_tips} ({uniq_pct:.1f}%)")
                    with cD:
                        st.metric("Fallback count", f"{fallback_count}")

                    # Tip length over time chart grouped by mode
                    st.caption("Tip length over time by mode")
                    chart_cols = st.columns([1,1])
                    with chart_cols[0]:
                        # Persist chart type in-session and to disk
                        default_chart_type = get_pref("prompt_len_chart_type", st.session_state.get("prompt_len_chart_type", "Line"))
                        chart_choice = st.radio(
                            "Chart type",
                            ["Line", "Bar"],
                            horizontal=True,
                            index=(0 if default_chart_type == "Line" else 1),
                            key="prompt_len_chart_type",
                        )
                        # Save any change
                        if chart_choice != default_chart_type:
                            set_pref("prompt_len_chart_type", chart_choice)
                    with chart_cols[1]:
                        # Persist binning choice in-session and to disk
                        default_bin = get_pref("prompt_time_bin", st.session_state.get("prompt_time_bin", "Hourly"))
                        bin_choice = st.radio(
                            "Time binning",
                            ["Hourly", "Daily"],
                            horizontal=True,
                            index=(0 if default_bin == "Hourly" else 1),
                            key="prompt_time_bin",
                        )
                        if bin_choice != default_bin:
                            set_pref("prompt_time_bin", bin_choice)
                    bin_freq = "H" if bin_choice == "Hourly" else "D"
                    try:
                        df_plot = dfv.copy()
                        df_plot["words"] = df_plot["tip"].fillna("").apply(lambda s: len(str(s).split()))
                        df_plot["chars"] = df_plot["tip"].fillna("").apply(lambda s: len(str(s)))
                        if "timestamp" in df_plot.columns and df_plot["timestamp"].notna().any() and "mode" in df_plot.columns:
                            piv = (df_plot
                                   .dropna(subset=["timestamp"]) 
                                   .groupby([pd.Grouper(key="timestamp", freq=bin_freq), "mode"])  # time bins
                                   .agg(words=("words", "mean"))
                                   .reset_index())
                            chart_df = piv.pivot(index="timestamp", columns="mode", values="words").sort_index()
                            if chart_choice == "Line":
                                st.line_chart(chart_df, height=220)
                            else:
                                st.bar_chart(chart_df, height=220)
                            # Characters chart
                            piv_c = (df_plot
                                     .dropna(subset=["timestamp"]) 
                                     .groupby([pd.Grouper(key="timestamp", freq=bin_freq), "mode"])  # time bins
                                     .agg(chars=("chars", "mean"))
                                     .reset_index())
                            chart_df_c = piv_c.pivot(index="timestamp", columns="mode", values="chars").sort_index()
                            st.caption("Characters over time by mode")
                            if chart_choice == "Line":
                                st.line_chart(chart_df_c, height=200)
                            else:
                                st.bar_chart(chart_df_c, height=200)
                        else:
                            st.info("Not enough timestamp/mode data to build the chart.")
                    except Exception as e:
                        st.caption(f"Chart unavailable: {e}")

                    # OK-rate over time chart grouped by mode with 95% CI using Altair
                    st.caption("OK-rate over time by mode (with 95% CI)")
                    show_ok_ci = st.checkbox("Show OK-rate with CIs", value=False, key="prompt_okrate_ci_toggle")
                    bootN = st.number_input("Bootstraps", min_value=100, max_value=2000, value=300, step=50, key="prompt_okrate_bootN") if show_ok_ci else 300
                    if show_ok_ci:
                        def _score_flags_row(row):
                            t = str(row.get("tip", "")).lower()
                            words = len(t.split())
                            verbs = ["try", "switch", "take", "bike", "walk", "reduce", "set", "lower", "replace", "unplug", "turn off", "plan", "use", "install", "carpool"]
                            actionable = any(v in t for v in verbs)
                            cat = str(row.get("category", "")).strip()
                            cat_hints = {
                                "Energy": ["electric", "heating", "thermostat", "kwh", "standby", "plug"],
                                "Transport": ["car", "bus", "train", "bike", "walk", "commute", "drive"],
                                "Meals": ["meal", "meat", "plant", "vegan", "vegetarian", "dairy"],
                            }
                            hints = cat_hints.get(cat, [])
                            relevant = True if (cat == "" or cat == "Mixed" or cat == "Ambiguous") else any(h in t for h in hints)
                            simple = (words <= 35) and (t.count('.') <= 2)
                            return bool(relevant and actionable and simple)

                        df_ok = dfv.copy()
                        df_ok["ok"] = df_ok.apply(_score_flags_row, axis=1)
                        agg = (
                            df_ok.dropna(subset=["timestamp"]) 
                                .groupby([pd.Grouper(key="timestamp", freq=bin_freq), "mode"]) 
                                .agg(ok_rate=("ok", lambda s: float(s.mean())*100.0), n=("ok","size"))
                                .reset_index()
                        )
                        # Bootstrap CIs per bin/mode
                        rows_ok = []
                        for (ts, md_), ggrp in agg.groupby(["timestamp", "mode"], dropna=False):
                            ok_rate = float(ggrp["ok_rate"].iloc[0]); n = int(ggrp["n"].iloc[0])
                            samples = []
                            for _ in range(int(bootN)):
                                p = max(0.0, min(1.0, ok_rate/100.0))
                                ones = sum(1 for __ in range(n) if random.random() < p)
                                samples.append((ones/n)*100.0 if n>0 else 0.0)
                            samples.sort()
                            lo = samples[int(0.025*(len(samples)-1))] if samples else 0.0
                            hi = samples[int(0.975*(len(samples)-1))] if samples else 0.0
                            rows_ok.append({"timestamp": ts, "mode": md_, "ok_rate": ok_rate, "ok_ci_low": lo, "ok_ci_high": hi, "n": n})
                        df_ok_ci = pd.DataFrame(rows_ok)

                        try:
                            if not df_ok_ci.empty:
                                ch = alt.Chart(df_ok_ci).encode(
                                x=alt.X("timestamp:T", title="Time"),
                                y=alt.Y("ok_rate:Q", title="OK rate (%)"),
                                color="mode:N",
                                tooltip=["mode:N", "timestamp:T", "n:Q", "ok_rate:Q", "ok_ci_low:Q", "ok_ci_high:Q"],
                            )
                            lines = ch.mark_line()
                            errs = ch.mark_errorband(opacity=0.3).encode(
                                y="ok_ci_low:Q", y2="ok_ci_high:Q"
                            )
                            ok_time_chart = errs + lines
                            st.altair_chart(ok_time_chart, use_container_width=True)

                            # Save PNG to session for ZIP export if altair_saver available
                            if alt_save is not None:
                                try:
                                    import tempfile
                                    tmpf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                                    alt_save(ok_time_chart, tmpf.name, fmt="png")
                                    with open(tmpf.name, "rb") as _f:
                                        st.session_state["ok_rate_time_png"] = _f.read()
                                    os.unlink(tmpf.name)
                                except Exception:
                                    st.session_state["ok_rate_time_png"] = None

                                # Save CSV of over-time data to session for ZIP export
                                try:
                                   st.session_state["ok_rate_time_csv"] = df_ok_ci.to_csv(index=False)
                                except Exception:
                                    st.session_state["ok_rate_time_csv"] = None

                                # Save chart spec for HTML embedding
                                try:
                                    st.session_state["ok_rate_time_spec"] = ok_time_chart.to_dict()
                                except Exception:
                                    st.session_state["ok_rate_time_spec"] = None

                        except Exception as e:
                            st.caption(f"Altair error bar chart unavailable: {e}")
                        
                        # Per-mode stats if available
                        if "mode" in dfv.columns:
                            try:
                                grp = dfv.groupby("mode", dropna=False)
                                rows = []
                                for mode_name, g in grp:
                                    tips_norm = g["tip"].fillna("").str.strip().str.lower().tolist()
                                    # Unique tips (case-insensitive)
                                    uniq = len(set(tips_norm))
                                    uniq_ratio = (uniq/len(g)*100.0) if len(g) else 0.0
                                    # Bigram distinctiveness
                                    def bigrams_of(s: str):
                                        toks = [t for t in s.split() if t]
                                        return list(zip(toks, toks[1:])) if len(toks) > 1 else []
                                    all_bigrams = []
                                    for t in tips_norm:
                                        all_bigrams.extend(bigrams_of(t.lower().strip()))
                                    total_bi = len(all_bigrams)
                                    uniq_bi = len(set(all_bigrams))
                                    uniq_bi_ratio = (uniq_bi/total_bi*100.0) if total_bi else 0.0
                                    avg_w = float(g["tip"].fillna("").apply(lambda s: len(str(s).split())).mean()) if len(g)>0 else 0.0
                                    fallbacks = int(g["prompt"].fillna("").str.contains("Fallback used", case=False, na=False).sum())
                                    rows.append({
                                        "mode": mode_name,
                                        "samples": len(g),
                                        "avg_words": avg_w,
                                        "unique_tips": uniq,
                                        "unique_tips_%": uniq_ratio,
                                        "unique_bigrams": uniq_bi,
                                        "unique_bigrams_%": uniq_bi_ratio,
                                        "fallbacks": fallbacks,
                                    })
                                per_mode = pd.DataFrame(rows).sort_values("mode")
                                st.caption("Per‑mode summary")
                                st.markdown('<div style="max-width:1100px;margin:0 auto;">', unsafe_allow_html=True)
                                st.dataframe(per_mode, use_container_width=True, height=220)
                                st.markdown('</div>', unsafe_allow_html=True)
                            except Exception:
                                pass

                            # Optional: boxplot per mode for tip lengths
                            show_box = st.checkbox("Show boxplot per mode (tip length in words)", value=False, key="prompt_boxplot_toggle")
                            if show_box:
                                try:
                                    import matplotlib.pyplot as plt
                                    fig, ax = plt.subplots(figsize=(6, 3))
                                    df_box = dfv.copy()
                                    if "mode" in df_box.columns:
                                        df_box["words"] = df_box["tip"].fillna("").apply(lambda s: len(str(s).split()))
                                        modes_order = sorted(df_box["mode"].dropna().unique().tolist())
                                        data = [df_box[df_box["mode"] == m]["words"].tolist() for m in modes_order]
                                        ax.boxplot(data, labels=modes_order, showfliers=True)
                                        ax.set_ylabel("Words")
                                        ax.set_title("Tip length distribution by mode")
                                        st.pyplot(fig, clear_figure=True)
                                except Exception:
                                    st.caption("Boxplot unavailable (matplotlib not installed)")
                        st.divider()
                        c1, c2 = st.columns([1,1])
                        with c1:
                            st.caption("Last 10 runs")
                            st.markdown('<div style="max-width:1100px;margin:0 auto;">', unsafe_allow_html=True)
                            st.dataframe(dfv.tail(10), use_container_width=True, height=220)
                            st.markdown('</div>', unsafe_allow_html=True)
                        with c2:
                            try:
                                with open(log_path, "r", encoding="utf-8") as fh:
                                    st.download_button("⬇️ Download prompt_log.csv", data=fh.read(), file_name="prompt_log.csv", mime="text/csv")
                            except Exception:
                                pass
                            if st.button("🗑️ Clear log (prompt_log.csv)"):
                                try:
                                    os.remove(log_path)
                                    st.success("Cleared prompt_log.csv. Refresh or run a new experiment to recreate.")
                                except Exception as e:
                                    st.error(f"Could not delete log: {e}")
                            if st.button("🧹 Clear experiments (session)"):
                                st.session_state["prompt_experiments"] = []
                                st.success("Cleared in-session prompt experiments. New runs will populate the appendix.")

        # Prompt testing suite
        with st.expander("Prompt testing suite", expanded=False):
            st.caption("Run predefined scenarios across modes (incl. ambiguous) and score tips for relevance, actionability, and simplicity.")
            colA, colB, colC, colD, colE, colF = st.columns([1.2, 1, 1, 1, 1, 1.4])
            with colA:
                default_amb = bool(get_pref("d6_include_ambig", st.session_state.get("d6_include_ambig", True)))
                include_ambiguous = st.checkbox("Include ambiguous cases", value=default_amb, key="d6_include_ambig")
                if include_ambiguous != default_amb:
                    set_pref("d6_include_ambig", bool(include_ambiguous))
            with colB:
                default_modes = get_pref("d6_modes", st.session_state.get("d6_modes", ["Contextualized", "Directive", "Persona"]))
                if not isinstance(default_modes, list) or not default_modes:
                    default_modes = ["Contextualized", "Directive", "Persona"]
                d6_modes = st.multiselect(
                    "Modes to test",
                    options=["Contextualized", "Directive", "Persona"],
                    default=default_modes,
                    key="d6_modes",
                )
                if sorted(d6_modes) != sorted(default_modes):
                    set_pref("d6_modes", d6_modes)
            with colC:
                default_varN = int(get_pref("d6_varN", st.session_state.get("d6_varN", 1)))
                varN = st.number_input("Randomized variations (N)", min_value=1, max_value=10, value=default_varN, step=1, key="d6_varN", help="Run each scenario N times with small random perturbations to stress-test diversity.")
                if int(varN) != default_varN:
                    set_pref("d6_varN", int(varN))
            with colD:
                run_suite = st.button("▶️ Run 10+ test scenarios")
            with colE:
                default_boot = int(get_pref("d6_bootN", st.session_state.get("d6_bootN", 300)))
                bootN = st.number_input("Bootstraps", min_value=100, max_value=2000, value=default_boot, step=50, key="d6_bootN", help="Resamples per mode to compute 95% CIs for OK rate and diversity metrics.")
                if int(bootN) != default_boot:
                    set_pref("d6_bootN", int(bootN))
            with colF:
                default_always = bool(get_pref("d6_always_ok_time", st.session_state.get("d6_always_ok_time", True)))
                always_ok_time = st.checkbox("Always include OK-rate over time", value=default_always, key="d6_always_ok_time", help="Generate the OK-rate over-time chart/spec as part of the Day 6 run so it's guaranteed in the HTML/ZIP.")
                if always_ok_time != default_always:
                    set_pref("d6_always_ok_time", bool(always_ok_time))
            # Quick toggle: Force edge-case visuals in report.html
            force_ec_default = bool(get_pref("d6_force_ec_visuals", st.session_state.get("d6_force_ec_visuals", False)))
            force_ec = st.checkbox("Force edge-case visuals in report.html", value=force_ec_default, help="Embed the edge-case distribution chart in the HTML report even if no edge-case rows are present.", key="d6_force_ec_visuals")
            if bool(force_ec) != bool(force_ec_default):
                set_pref("d6_force_ec_visuals", bool(force_ec))

            # Advanced: Tunable edge-case thresholds
            if hasattr(st, "popover"):
               with st.popover("Advanced: Edge-case thresholds (extreme values)"):
                   st.caption("Adjust per-activity numeric limits used to classify 'extreme' inputs. Saved across sessions.")
                   default_thr = get_pref("d6_thresholds", st.session_state.get("d6_thresholds", {
                       "electricity_kwh": 200.0,
                       "natural_gas_m3": 100.0,
                       "hot_water_liter": 2000.0,
                       "petrol_liter": 100.0,
                       "diesel_liter": 100.0,
                       "bus_km": 500.0,
                       "rail_km": 1000.0,
                       "meat_kg": 10.0,
                       "dairy_kg": 15.0,
                       "vegetarian_kg": 20.0,
                    }))
            else:
                st.markdown("#### Advanced: Edge-case thresholds (extreme values)")
                adv_box = st.container(border=True)
                with adv_box:
                    st.caption("Adjust per-activity numeric limits used to classify 'extreme' inputs. Saved across sessions.")
                    default_thr = get_pref("d6_thresholds", st.session_state.get("d6_thresholds", {
                        "electricity_kwh": 200.0,
                        "natural_gas_m3": 100.0,
                        "hot_water_liter": 2000.0,
                        "petrol_liter": 100.0,
                        "diesel_liter": 100.0,
                        "bus_km": 500.0,
                        "rail_km": 1000.0,
                        "meat_kg": 10.0,
                        "dairy_kg": 15.0,
                        "vegetarian_kg": 20.0,
                    }))
                last_upd = get_pref("d6_thresholds_updated_at", "")
                if last_upd:
                    st.caption(f"Last updated: {last_upd}")
                c1, c2, c3 = st.columns(3)
                with c1:
                    th_elec = st.number_input("electricity_kwh", min_value=1.0, max_value=10000.0,
                                  value=float(default_thr.get("electricity_kwh", 200.0)), step=1.0)
                    th_gas = st.number_input("natural_gas_m3", min_value=1.0, max_value=10000.0,
                                 value=float(default_thr.get("natural_gas_m3", 100.0)), step=1.0)
                    th_hot = st.number_input("hot_water_liter", min_value=10.0, max_value=100000.0,
                                 value=float(default_thr.get("hot_water_liter", 2000.0)), step=10.0)
                with c2:
                    th_pet = st.number_input("petrol_liter", min_value=1.0, max_value=10000.0,
                                 value=float(default_thr.get("petrol_liter", 100.0)), step=1.0)
                    th_dsl = st.number_input("diesel_liter", min_value=1.0, max_value=10000.0,
                                 value=float(default_thr.get("diesel_liter", 100.0)), step=1.0)
                    th_bus = st.number_input("bus_km", min_value=1.0, max_value=100000.0,
                                 value=float(default_thr.get("bus_km", 500.0)), step=5.0)
                with c3:
                    th_rail = st.number_input("rail_km", min_value=1.0, max_value=100000.0,
                                  value=float(default_thr.get("rail_km", 1000.0)), step=10.0)
                    th_meat = st.number_input("meat_kg", min_value=0.1, max_value=1000.0,
                                  value=float(default_thr.get("meat_kg", 10.0)), step=0.1, format="%0.1f")
                    th_dairy = st.number_input("dairy_kg", min_value=0.1, max_value=1000.0,
                                   value=float(default_thr.get("dairy_kg", 15.0)), step=0.1, format="%0.1f")
                    th_veg = st.number_input("vegetarian_kg", min_value=0.1, max_value=1000.0,
                                 value=float(default_thr.get("vegetarian_kg", 20.0)), step=0.1, format="%0.1f")

                new_thr = {
                    "electricity_kwh": float(th_elec),
                    "natural_gas_m3": float(th_gas),
                    "hot_water_liter": float(th_hot),
                    "petrol_liter": float(th_pet),
                    "diesel_liter": float(th_dsl),
                    "bus_km": float(th_bus),
                    "rail_km": float(th_rail),
                    "meat_kg": float(th_meat),
                    "dairy_kg": float(th_dairy),
                    "vegetarian_kg": float(th_veg),
                }

                # Apply and persist thresholds
                if new_thr != default_thr:
                    set_pref("d6_thresholds", new_thr)
                    set_pref("d6_thresholds_updated_at", dt.datetime.now().isoformat())

                # Always apply current thresholds to the classifier
                try:
                    set_extreme_thresholds(get_pref("d6_thresholds", new_thr))
                except Exception:
                    pass

                # Controls row: Reset to defaults and Export JSON
                rc1, rc2 = st.columns([1, 1])
                with rc1:
                    if st.button("Reset thresholds to defaults", key="btn_reset_thresholds"):
                        defaults = {
                            "electricity_kwh": 200.0,
                            "natural_gas_m3": 100.0,
                            "hot_water_liter": 2000.0,
                            "petrol_liter": 100.0,
                            "diesel_liter": 100.0,
                            "bus_km": 500.0,
                            "rail_km": 1000.0,
                            "meat_kg": 10.0,
                            "dairy_kg": 15.0,
                            "vegetarian_kg": 20.0,
                        }
                        set_pref("d6_thresholds", defaults)
                        set_pref("d6_thresholds_updated_at", dt.datetime.now().isoformat())
                        try:
                            set_extreme_thresholds(defaults)
                        except Exception:
                            pass
                        st.success("Thresholds reset to defaults. Collapse/expand to refresh controls if values don't immediately reflect.")

                with rc2:
                    try:
                        thr_json = json.dumps(get_pref("d6_thresholds", new_thr), indent=2)
                        st.download_button("⬇️ Export thresholds JSON", data=thr_json,
                               file_name="edge_case_thresholds.json", mime="application/json",
                               key="btn_export_thresholds")
                    except Exception:
                        pass

            # Import thresholds JSON
            upl = st.file_uploader("Import thresholds JSON", type=["json"], key="upl_thresholds_json")
            if upl is not None:
                try:
                    data = json.loads(upl.getvalue().decode("utf-8"))
                    if isinstance(data, dict) and data:
                        set_pref("d6_thresholds", data)
                        set_pref("d6_thresholds_updated_at", dt.datetime.now().isoformat())
                        try:
                            set_extreme_thresholds(data)
                        except Exception:
                            pass
                        st.success("Imported thresholds applied.")
                    else:
                        st.warning("Uploaded JSON is not a non-empty object. No changes applied.")
                except Exception as e:
                    st.error(f"Could not parse JSON: {e}")

            def _scenario_inputs():
                # Build at least 10 scenarios touching energy, transport, meals, plus ambiguous
                scenarios = []
                # Energy-focused
                scenarios.append(("Energy", {"electricity_kwh": 9.5}))
                scenarios.append(("Energy", {"natural_gas_m3": 4.0}))
                # Transport-focused
                scenarios.append(("Transport", {"petrol_liter": 6.0}))
                scenarios.append(("Transport", {"diesel_liter": 5.0}))
                scenarios.append(("Transport", {"bus_km": 20.0}))
                # Meals-focused
                scenarios.append(("Meals", {"meat_kg": 0.35}))
                scenarios.append(("Meals", {"dairy_kg": 0.6}))
                scenarios.append(("Meals", {"vegetarian_kg": 0.8}))
                # Mixed day
                scenarios.append(("Mixed", {"electricity_kwh": 3.0, "petrol_liter": 2.0, "meat_kg": 0.2}))
                # Ambiguous / unclear
                if include_ambiguous:
                    scenarios.append(("Ambiguous", {}))
                    scenarios.append(("Ambiguous", {"unknown_key": "help"}))
                    # Richer edge cases
                    scenarios.append(("Ambiguous", {"note": "🚗🍔💡"}))          # emojis
                    scenarios.append(("Ambiguous", {"note": "asdf123"}))         # nonsense
                    scenarios.append(("Ambiguous", {"note": "help"}))            # help request
                    scenarios.append(("Ambiguous", {"electricity_kwh": -5}))     # negative
                    scenarios.append(("Ambiguous", {"electricity_kwh": 50000}))  # extreme
                return scenarios

            def _perturb_inputs(inputs: dict) -> dict:
                # Apply small random multiplicative noise to numeric fields
                if not inputs:
                    return inputs
                out = {}
                for k, v in inputs.items():
                    try:
                        f = float(v)
                        noise = 1.0 + random.uniform(-0.15, 0.15)
                        out[k] = max(0.0, f * noise)
                    except Exception:
                        out[k] = v
                return out

            def _score_tip(tip: str, category: str) -> dict:
                t = (tip or "").lower()
                words = len(t.split())
                # Heuristic action verbs
                verbs = ["try", "switch", "take", "bike", "walk", "reduce", "set", "lower", "replace", "unplug", "turn off", "plan", "use", "install", "carpool"]
                actionable = any(v in t for v in verbs)
                # Relevance by category keyword hints
                cat_hints = {
                    "Energy": ["electric", "heating", "thermostat", "kwh", "standby", "plug"],
                    "Transport": ["car", "bus", "train", "bike", "walk", "commute", "drive"],
                    "Meals": ["meal", "meat", "plant", "vegan", "vegetarian", "dairy"],
                    "Mixed": [],
                    "Ambiguous": [],
                }
                hints = cat_hints.get(category, [])
                relevant = True if category in ("Mixed", "Ambiguous") else any(h in t for h in hints)
                simple = (words <= 35) and (t.count('.') <= 2)
                flags = {
                    "relevant": relevant,
                    "actionable": actionable,
                    "simple": simple,
                }
                flags["ok"] = all(flags.values())
                return flags

            if run_suite:
                scenarios = _scenario_inputs()
                results_rows = []
                for (cat, base_inputs) in scenarios:
                    for _ in range(int(varN)):
                        user_inputs = _perturb_inputs(base_inputs)
                        # Estimate emissions locally (simple sum using CO2_FACTORS)
                        em_est = 0.0
                        for k, v in (user_inputs or {}).items():
                            try:
                                em_est += float(v or 0) * CO2_FACTORS.get(k, 0.0)
                            except Exception:
                                pass
                        for m in d6_modes:
                            tip_i, prompt_i = generate_eco_tip_with_prompt(user_inputs, float(em_est), mode=m, category=(None if cat in ("Ambiguous", "Mixed") else cat))
                            flags = _score_tip(tip_i, cat)
                            results_rows.append({
                                "timestamp": dt.datetime.now().isoformat(),
                                "category": cat,
                                "mode": m,
                                "emissions_est_kg": f"{em_est:.2f}",
                                "tip": tip_i,
                                "relevant": flags["relevant"],
                                "actionable": flags["actionable"],
                                "simple": flags["simple"],
                                "ok": flags["ok"],
                                "prompt": prompt_i,
                                "input_type": classify_input_type(user_inputs),
                                "EC": "⚠️" if classify_input_type(user_inputs) != "valid" else "",
                            })
                # Convert and show table
                try:
                    df_cmp = pd.DataFrame(results_rows)
                    st.markdown("**Prompt Comparison Table (Day 6)**")
                    view_cols = ["timestamp", "category", "mode", "emissions_est_kg", "ok", "relevant", "actionable", "simple", "fallback_used", "input_type", "EC", "tip"]
                    # Edge-case filter UI
                    df_to_show = df_cmp
                    if "input_type" in df_cmp.columns:
                        unique_types = sorted([str(x) for x in df_cmp["input_type"].dropna().unique().tolist()])
                        default_filter = get_pref("d6_filter_input_type", unique_types)
                        # Ensure default matches available set
                        if not isinstance(default_filter, list) or not default_filter:
                            default_filter = unique_types
                        default_filter = [t for t in default_filter if t in unique_types]
                        sel_types = st.multiselect("Filter by input_type (edge-case)", options=unique_types, default=default_filter, key="d6_filter_input_type")
                        if sel_types != default_filter:
                            set_pref("d6_filter_input_type", sel_types)
                        if sel_types and len(sel_types) < len(unique_types):
                            df_to_show = df_cmp[df_cmp["input_type"].astype(str).isin(sel_types)]
                    st.markdown('<div style="max-width:1100px;margin:0 auto;">', unsafe_allow_html=True)
                    st.dataframe(df_to_show[view_cols], use_container_width=True, height=240)  # reduce from 380
                    st.markdown('</div>', unsafe_allow_html=True)
                    # Per-mode diversity and OK-rate metrics
                    try:
                        rows = []
                        # Helpers for bootstrap CIs
                        def _quantile(vals, q):
                            if not vals:
                                return 0.0
                            s = sorted(vals)
                            idx = max(0, min(len(s)-1, int(q * (len(s)-1))))
                            return float(s[idx])
                        def _bigrams_of(s: str):
                            toks = [t for t in s.split() if t]
                            return list(zip(toks, toks[1:])) if len(toks) > 1 else []
                        def _bootstrap_metrics(mode_df: pd.DataFrame, n_boot: int = 300):
                            tips = mode_df["tip"].fillna("").astype(str).tolist()
                            oks = mode_df["ok"].astype(bool).tolist()
                            n = len(tips)
                            if n == 0:
                                return {"ok_ci": (0.0, 0.0), "uniq_tips_ci": (0.0, 0.0), "uniq_bi_ci": (0.0, 0.0)}
                            ok_samples = []
                            utip_samples = []
                            ubi_samples = []
                            for _ in range(int(bootN)):
                                idxs = [random.randrange(0, n) for _ in range(n)]
                                tips_s = [tips[i] for i in idxs]
                                oks_s = [oks[i] for i in idxs]
                                # OK rate
                                ok_rate = (sum(oks_s)/len(oks_s))*100.0
                                ok_samples.append(ok_rate)
                                # Unique tips %
                                utip = (len(set(t.strip().lower() for t in tips_s))/len(tips_s))*100.0
                                utip_samples.append(utip)
                                # Unique bigrams %
                                bigs = []
                                for t in tips_s:
                                    bigs.extend(_bigrams_of(t.lower().strip()))
                                total_b = len(bigs)
                                ubi = ((len(set(bigs))/total_b)*100.0) if total_b else 0.0
                                ubi_samples.append(ubi)
                            return {
                                "ok_ci": (_quantile(ok_samples, 0.025), _quantile(ok_samples, 0.975)),
                                "uniq_tips_ci": (_quantile(utip_samples, 0.025), _quantile(utip_samples, 0.975)),
                                "uniq_bi_ci": (_quantile(ubi_samples, 0.025), _quantile(ubi_samples, 0.975)),
                            }
                        for mode_name, g in df_cmp.groupby("mode", dropna=False):
                            tips_norm = g["tip"].fillna("").str.strip().str.lower().tolist()
                            uniq = len(set(tips_norm))
                            uniq_ratio = (uniq/len(g)*100.0) if len(g) else 0.0
                            # Bigram distinctiveness
                            all_bigrams = []
                            for t in tips_norm:
                                all_bigrams.extend(_bigrams_of(t))
                            total_bi = len(all_bigrams)
                            uniq_bi = len(set(all_bigrams))
                            uniq_bi_ratio = (uniq_bi/total_bi*100.0) if total_bi else 0.0
                            ok_rate = float(g["ok"].mean()) * 100.0 if len(g)>0 else 0.0
                            cis = _bootstrap_metrics(g, n_boot=int(bootN))
                            ok_ci_low, ok_ci_high = cis['ok_ci']
                            ut_ci_low, ut_ci_high = cis['uniq_tips_ci']
                            ub_ci_low, ub_ci_high = cis['uniq_bi_ci']
                            rows.append({
                                "mode": mode_name,
                                "samples": len(g),
                                "ok_rate_%": ok_rate,
                                "ok_rate_ci_low": float(ok_ci_low),
                                "ok_rate_ci_high": float(ok_ci_high),
                                "unique_tips": uniq,
                                "unique_tips_%": uniq_ratio,
                                "unique_tips_ci_low": float(ut_ci_low),
                                "unique_tips_ci_high": float(ut_ci_high),
                                "unique_bigrams": uniq_bi,
                                "unique_bigrams_%": uniq_bi_ratio,
                                "unique_bigrams_ci_low": float(ub_ci_low),
                                "unique_bigrams_ci_high": float(ub_ci_high),
                            })
                        per_mode_metrics = pd.DataFrame(rows).sort_values("mode")
                        st.caption("Per‑mode diversity and OK‑rate")
                        st.markdown('<div style="max-width:1100px;margin:0 auto;">', unsafe_allow_html=True)
                        st.dataframe(per_mode_metrics, use_container_width=True, height=220)
                        st.markdown('</div>', unsafe_allow_html=True)
                        # Altair charts with error bars
                        try:
                            base_ok = alt.Chart(per_mode_metrics).encode(x=alt.X('mode:N', title='Mode'))
                            bars_ok = base_ok.mark_bar(color='#4F46E5').encode(
                                y=alt.Y('ok_rate_%:Q', title='OK rate (%)'),
                                tooltip=['mode:N','samples:Q','ok_rate_%:Q','ok_rate_ci_low:Q','ok_rate_ci_high:Q']
                            )
                            error_ok = base_ok.mark_errorband(opacity=0.3).encode(y='ok_rate_ci_low:Q', y2='ok_rate_ci_high:Q')
                            st.altair_chart(bars_ok + error_ok, use_container_width=True)

                            cols = st.columns(2)
                            with cols[0]:
                                st.caption("Unique tips % by mode (with CI)")
                                base_ut = alt.Chart(per_mode_metrics).encode(x=alt.X('mode:N', title='Mode'))
                                bars_ut = base_ut.mark_bar(color='#059669').encode(
                                    y=alt.Y('unique_tips_%:Q', title='Unique tips (%)'),
                                    tooltip=['mode:N','samples:Q','unique_tips_%:Q','unique_tips_ci_low:Q','unique_tips_ci_high:Q']
                                )
                                error_ut = base_ut.mark_errorband().encode(y='unique_tips_ci_low:Q', y2='unique_tips_ci_high:Q')
                                st.altair_chart(bars_ut + error_ut, use_container_width=True)
                            with cols[1]:
                                st.caption("Unique bigrams % by mode (with CI)")
                                base_ub = alt.Chart(per_mode_metrics).encode(x=alt.X('mode:N', title='Mode'))
                                bars_ub = base_ub.mark_bar(color='#2563EB').encode(
                                    y=alt.Y('unique_bigrams_%:Q', title='Unique bigrams (%)'),
                                    tooltip=['mode:N','samples:Q','unique_bigrams_%:Q','unique_bigrams_ci_low:Q','unique_bigrams_ci_high:Q']
                                )
                                error_ub = base_ub.mark_errorband().encode(y='unique_bigrams_ci_low:Q', y2='unique_bigrams_ci_high:Q')
                                st.altair_chart(bars_ub + error_ub, use_container_width=True)
                        except Exception as e:
                            st.caption(f"Altair error bar charts unavailable: {e}")
                    except Exception:
                        df_cmp = None
                    # Findings summary for HTML
                    try:
                        best_row = per_mode_metrics.sort_values('ok_rate_%', ascending=False).iloc[0]
                        findings = [
                            f"Best mode: {best_row['mode']} (OK rate {best_row['ok_rate_%']:.1f}% | 95% CI [{best_row['ok_rate_ci_low']:.1f}, {best_row['ok_rate_ci_high']:.1f}])",
                            f"Diversity (unique tips %): {best_row['unique_tips_%']:.1f}% | 95% CI [{best_row['unique_tips_ci_low']:.1f}, {best_row['unique_tips_ci_high']:.1f}]",
                            f"Diversity (unique bigrams %): {best_row['unique_bigrams_%']:.1f}% | 95% CI [{best_row['unique_bigrams_ci_low']:.1f}, {best_row['unique_bigrams_ci_high']:.1f}]",
                        ]
                    except Exception:
                        findings = []
                    # Top 3 deltas across modes (OK rate) and CI overlap flag
                    try:
                        pm = per_mode_metrics[["mode","ok_rate_%","ok_rate_ci_low","ok_rate_ci_high"]].copy()
                        pairs = []
                        for i in range(len(pm)):
                            for j in range(i+1, len(pm)):
                                a = pm.iloc[i]; b = pm.iloc[j]
                                delta = float(a["ok_rate_%"] - b["ok_rate_%"])  # a minus b
                                # CI overlap: if intervals intersect
                                overlap = not (a["ok_rate_ci_high"] < b["ok_rate_ci_low"] or b["ok_rate_ci_high"] < a["ok_rate_ci_low"])
                                pairs.append({
                                    "pair": f"{a['mode']} vs {b['mode']}",
                                    "delta": delta,
                                    "overlap": overlap,
                                })
                        pairs_sorted = sorted(pairs, key=lambda x: abs(x["delta"]), reverse=True)[:3]
                        top3 = [f"{p['pair']}: ΔOK {p['delta']:+.1f} pts (CIs overlap: {'yes' if p['overlap'] else 'no'})" for p in pairs_sorted]
                    except Exception:
                        top3 = []
                    # Always include OK-rate over time
                    if bool(get_pref("d6_always_ok_time", st.session_state.get("d6_always_ok_time", True))):
                        try:
                            # Build ok over-time from df_cmp directly (hourly)
                            df_tmp = df_cmp.copy()
                            df_tmp['timestamp'] = pd.to_datetime(df_tmp['timestamp'], errors='coerce')
                            df_tmp = df_tmp.dropna(subset=['timestamp'])
                            agg = (
                                df_tmp.groupby([pd.Grouper(key='timestamp', freq='H'), 'mode'])
                                    .agg(ok_rate=('ok', lambda s: float(s.mean())*100.0), n=('ok','size'))
                                    .reset_index()
                            )
                            # Bootstrap
                            rows_ok = []
                            for (ts, md_), ggrp in agg.groupby(['timestamp','mode'], dropna=False):
                                ok_rate = float(ggrp['ok_rate'].iloc[0]); n = int(ggrp['n'].iloc[0])
                                samples = []
                                for _ in range(int(bootN)):
                                    p = max(0.0, min(1.0, ok_rate/100.0))
                                    ones = sum(1 for __ in range(n) if random.random() < p)
                                    samples.append((ones/n)*100.0 if n>0 else 0.0)
                                samples.sort()
                                lo = samples[int(0.025*(len(samples)-1))] if samples else 0.0
                                hi = samples[int(0.975*(len(samples)-1))] if samples else 0.0
                                rows_ok.append({'timestamp': ts, 'mode': md_, 'ok_rate': ok_rate, 'ok_ci_low': lo, 'ok_ci_high': hi, 'n': n})
                            df_ok_ci = pd.DataFrame(rows_ok)
                            if not df_ok_ci.empty:
                                ch = alt.Chart(df_ok_ci).encode(
                                    x=alt.X('timestamp:T', title='Time'), y=alt.Y('ok_rate:Q', title='OK rate (%)'), color='mode:N',
                                    tooltip=['mode:N','timestamp:T','n:Q','ok_rate:Q','ok_ci_low:Q','ok_ci_high:Q']
                                )
                                ok_time_chart = ch.mark_errorband(opacity=0.3).encode(y='ok_ci_low:Q', y2='ok_ci_high:Q') + ch.mark_line()
                                # Save assets into session
                                st.session_state['ok_rate_time_spec'] = ok_time_chart.to_dict()
                                try:
                                    st.session_state['ok_rate_time_csv'] = df_ok_ci.to_csv(index=False)
                                except Exception:
                                    pass
                                if alt_save is not None:
                                    import tempfile
                                    tmpf = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                                    alt_save(ok_time_chart, tmpf.name, fmt='png')
                                    with open(tmpf.name, 'rb') as _f:
                                        st.session_state['ok_rate_time_png'] = _f.read()
                                    os.unlink(tmpf.name)
                        except Exception:
                            pass
                    # Markdown export (compact table)
                    def _to_markdown_table(df: pd.DataFrame) -> str:
                        headers = " | ".join(view_cols)
                        sep = " | ".join(["---"] * len(view_cols))
                        lines = [f"| {headers} |", f"| {sep} |"]
                        for _, row in df.iterrows():
                            vals = [str(row[c]) for c in view_cols]
                            lines.append("| " + " | ".join(vals) + " |")
                        return "\n".join(lines)
                    # Summary section (top-line findings)
                    try:
                        best_row = per_mode_metrics.sort_values('ok_rate_%', ascending=False).iloc[0]
                        summary_lines = [
                            "# Prompt Comparison Table (Day 6)",
                            "",
                            "## Summary Findings",
                            f"- **Best mode**: {best_row['mode']} (OK rate: {best_row['ok_rate_%']:.1f}% | 95% CI [{best_row['ok_rate_ci_low']:.1f}, {best_row['ok_rate_ci_high']:.1f}])",
                            f"- **Diversity (unique tips %)**: {best_row['unique_tips_%']:.1f}% | 95% CI [{best_row['unique_tips_ci_low']:.1f}, {best_row['unique_tips_ci_high']:.1f}]",
                            f"- **Diversity (unique bigrams %)**: {best_row['unique_bigrams_%']:.1f}% | 95% CI [{best_row['unique_bigrams_ci_low']:.1f}, {best_row['unique_bigrams_ci_high']:.1f}]",
                            "",
                            "## Full Table",
                        ]
                        md_header = "\n".join(summary_lines)
                    except Exception:
                        md_header = "# Prompt Comparison Table (Day 6)\n\n## Full Table"
                    md_table = _to_markdown_table(df_cmp[view_cols])
                    md = md_header + "\n\n" + md_table
                    st.markdown("**Markdown preview**")
                    st.code(md, language="markdown")
                    st.download_button(
                        label="⬇️ Save comparison as Markdown",
                        data=md,
                        file_name="prompt_compare.md",
                        mime="text/markdown",
                        key="download_prompt_compare_md",
                    )
                    # ZIP export (CSV + MD + per-mode metrics)
                    try:
                        buf = io.BytesIO()
                        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                            # README.md with quick guide
                            readme = []
                            readme.append("# Day 6 Report Package")
                            readme.append("")
                            readme.append("## Files")
                            readme.append("- prompt_compare.csv — All test rows (mode/category/ok flags/tip/prompt)")
                            readme.append("- prompt_compare.md — Summary + full table in Markdown")
                            readme.append("- per_mode_metrics.csv — Per-mode OK rate and diversity with 95% CIs")
                            readme.append("- per_mode_metrics.md — Per-mode metrics in Markdown")
                            readme.append("- ok_rate.png — OK rate bar chart with error bars")
                            readme.append("- unique_tips.png — Unique tips % bar chart with error bars")
                            readme.append("- unique_bigrams.png — Unique bigrams % bar chart with error bars")
                            readme.append("- ok_rate_over_time.png — OK rate over time with 95% CI (if generated)")
                            readme.append("- ok_rate_over_time.csv — Data for over-time chart (if generated)")
                            readme.append("- report.html — Interactive HTML report (if charts available)")
                            readme.append("")
                            readme.append("## How to interpret")
                            readme.append("- OK rate: percent of tips that are Relevant, Actionable, and Simple.")
                            readme.append("- Unique tips %: lexical uniqueness across tips (case-insensitive).")
                            readme.append("- Unique bigrams %: n-gram diversity proxy (higher means more varied phrasing).")
                            readme.append("- 95% CI: uncertainty from bootstrap resampling.")
                            readme.append("")
                            readme.append("## input_type taxonomy (heuristics)")
                            readme.append("- empty: no usable numeric or text inputs provided")
                            readme.append("- help: explicit request for help (e.g., 'help', '?', 'what should I do?')")
                            readme.append("- emoji: text dominated by emojis/symbols (very low alphanumeric ratio)")
                            readme.append("- nonsense: symbol-heavy/gibberish without clear meaning")
                            readme.append("- negative: any numeric input is negative (per field)")
                            readme.append("- extreme: numeric input exceeds per-activity sanity thresholds (heuristics)")
                            readme.append("- valid: inputs pass the above checks")
                            zf.writestr('README.md', "\n".join(readme))
                            # Combined HTML (embed Altair specs)
                            try:
                                html_parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'><title>Day 6 Report</title>"]
                                html_parts.append("<script src='https://cdn.jsdelivr.net/npm//vega@5'></script>")
                                html_parts.append("<script src='https://cdn.jsdelivr.net/npm/vega-lite@5'></script>")
                                html_parts.append("<script src='https://cdn.jsdelivr.net/npm/vega-embed@6'></script>")
                                html_parts.append("</head><body><h1>Day 6 Interactive Report</h1>")
                                def _embed_div(spec, div_id):
                                    return f"<div id='{div_id}'></div><script>vegaEmbed('#{div_id}', {json.dumps(spec)});</script>"
                                # Build specs for the three per-mode charts
                                try:
                                    spec_ok = (bars_ok + error_ok).to_dict()
                                    spec_ut = (bars_ut + error_ut).to_dict()
                                    spec_ub = (bars_ub + error_ub).to_dict()
                                    # Findings block
                                    if findings:
                                        html_parts.append("<h2>Findings</h2><ul>" + "".join([f"<li>{f}</li>" for f in findings]) + "</ul>")
                                    if top3:
                                        html_parts.append("<h3>Top 3 deltas (OK rate)</h3><ul>" + "".join([f"<li>{t}</li>" for t in top3]) + "</ul>")
                                    html_parts.append("<h2>OK rate by mode</h2>")
                                    html_parts.append(_embed_div(spec_ok, "ok_rate"))
                                    html_parts.append("<h2>Unique tips % by mode</h2>")
                                    html_parts.append(_embed_div(spec_ut, "unique_tips"))
                                    html_parts.append("<h2>Unique bigrams % by mode</h2>")
                                    html_parts.append(_embed_div(spec_ub, "unique_bigrams"))
                                except Exception:
                                    pass
                                # Over-time chart if present
                                if st.session_state.get('ok_rate_time_spec'):
                                    html_parts.append("<h2>OK rate over time</h2>")
                                    html_parts.append(_embed_div(st.session_state.get('ok_rate_time_spec'), "ok_rate_time"))
                                # Edge-case distribution chart (optional force)
                                try:
                                    force_ec = bool(get_pref("d6_force_ec_visuals", st.session_state.get("d6_force_ec_visuals", False)))
                                    show_ec = force_ec
                                    spec_ec = None
                                    no_edge_cases = False
                                    if "input_type" in df_cmp.columns:
                                        df_e = df_cmp.copy()
                                        e_counts = df_e.groupby(["mode", "input_type"], dropna=False).size().reset_index(name="count")
                                        import altair as alt
                                        ec_chart = alt.Chart(e_counts).mark_bar().encode(
                                            x=alt.X('mode:N', title='Mode'),
                                            y=alt.Y('count:Q', stack='normalize', title='Edge-case proportion'),
                                            color=alt.Color('input_type:N', title='input_type')
                                        )
                                        spec_ec = ec_chart.to_dict()
                                        show_ec = True
                                        try:
                                            no_edge_cases = df_e["input_type"].astype(str).apply(lambda s: s.strip().lower() == 'valid').all()
                                        except Exception:
                                            no_edge_cases = False
                                    if show_ec and spec_ec is not None:
                                        html_parts.append("<h2>Edge-case distribution by mode</h2>")
                                        html_parts.append(_embed_div(spec_ec, "edge_cases"))
                                        if force_ec and no_edge_cases:
                                            html_parts.append("<div style='font-size:0.9em;color:#64748B;font-style:italic;margin-top:4px;'>⚠️ Edge-case chart displayed due to forced rendering; no edge-case inputs were present in this run.</div>")
                                except Exception:
                                    pass
                                html_parts.append("</body></html>")
                                zf.writestr('report.html', "".join(html_parts))
                            except Exception:
                                pass
                            zf_bytes = buf.getvalue()
                            st.download_button(
                                label="⬇️ Save all (CSV + MD) as ZIP",
                                data=zf_bytes,
                                file_name="day6_results.zip",
                                mime="application/zip",
                                key="download_day6_zip",
                            )
                    except Exception as e:
                        st.caption(f"ZIP export unavailable: {e}")
                except Exception:
                    df_cmp = None
                # Determine AI summary to include in PDF if requested
                ai_summary_for_pdf = None
                try:
                    if bool(st.session_state.get("pdf_include_ai_summary", False)):
                        # Prefer any cached AI summary from the UI
                        ai_summary_for_pdf = st.session_state.get("ai_summary_text")
                        if not ai_summary_for_pdf:
                            # Generate on-demand for PDF context
                            df_hist = load_history()
                            ref_date = selected_date if isinstance(selected_date, (dt.date, dt.datetime)) else dt.date.today()
                            y_total = get_yesterday_total(df_hist, ref_date if isinstance(ref_date, dt.date) else ref_date.date())
                            cmp = percentage_change(y_total, em_today)
                            if y_total > 0:
                                comparison_text = f"{abs(cmp):.1f}% {'lower' if cmp < 0 else 'higher'} than yesterday ({fmt_emissions(y_total)})"
                            else:
                                comparison_text = "No data for yesterday"
                            # Weekly context (simple 7-day average)
                            weekly_context = None
                            try:
                                if not df_hist.empty:
                                    dfx = df_hist.copy()
                                    dfx["date"] = pd.to_datetime(dfx["date"]).dt.date
                                    last7 = dfx.sort_values("date").tail(7)
                                    if not last7.empty:
                                        avg7 = float(last7["total_kg"].mean())
                                        weekly_context = f"7-day average: {avg7:.2f} kg CO₂"
                            except Exception:
                                weekly_context = None
                            ai_summary_for_pdf = generate_ai_summary(
                                user_data=user_data,
                                emissions=em_today,
                                date=(ref_date.isoformat() if isinstance(ref_date, (dt.date, dt.datetime)) else str(ref_date)),
                                comparison_text=comparison_text,
                                streak_days=int(st.session_state.get("streak_days", 0)) if isinstance(st.session_state.get("streak_days", 0), (int, float)) else 0,
                                weekly_context=weekly_context,
                            )
                except Exception:
                    ai_summary_for_pdf = None
                # Prepare 7-day per-category sparkline data from history
                spark = {}
                try:
                    _hist = load_history()
                    if not _hist.empty:
                        dfh = _hist.copy()
                        dfh["date"] = pd.to_datetime(dfh["date"]).dt.date
                        last_dates = sorted(dfh["date"].unique())[-7:]
                        for d in last_dates:
                            row = dfh[dfh["date"] == d]
                            if row.empty:
                                continue
                            rdict = {k: float(row.iloc[-1].get(k, 0) or 0) for k in ALL_KEYS if k in row.columns}
                            cat_vals = compute_category_emissions(rdict)
                            for cat, val in cat_vals.items():
                                spark.setdefault(cat, []).append(float(val))
                except Exception:
                    spark = {}
                # Prefer uploaded logo; fallback to project's logo.png path if present
                logo_bytes = None
                if logo_file is None:
                    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
                    if os.path.exists(logo_path):
                        try:
                            with open(logo_path, "rb") as lf:
                                logo_bytes = lf.read()
                        except Exception:
                            logo_bytes = None
                
                # Ensure these are defined before the PDF build block
                tip_for_pdf = st.session_state.get("last_tip_full") or st.session_state.get("last_tip") or ""
                date_str = (selected_date.isoformat() if isinstance(selected_date, (dt.date, dt.datetime)) else str(selected_date))
                src_label = st.session_state.get("last_tip_source", "Unknown")
                st.caption("Reached PDF section")
                
                
                if ENABLE_LATE_PDF:
                    # Guards: ensure required values exist before PDF
                    missing = []
                    try:
                        _summary_ok = bool(summary_str and isinstance(summary_str, str))
                    except Exception:
                            _summary_ok = False
                    try:
                        _tip_ok = bool(tip_for_pdf and isinstance(tip_for_pdf, str))
                    except Exception:
                        _tip_ok = False
                    try:
                        _date_ok = bool(date_str and isinstance(date_str, str))
                    except Exception:
                        _date_ok = False
                    
                    try:
                        _src_ok = bool(src_label and isinstance(src_label, str))
                    except Exception:
                        _src_ok = False

                    if not _summary_ok:
                        missing.append("summary")
                    if not _tip_ok:
                        missing.append("tip")
                    if not _date_ok:
                        missing.append("date")
                    if not _src_ok:
                        missing.append("source")

                    try:
                        _pa_ok = isinstance(per_activity, dict) and len(per_activity) > 0
                    except Exception:
                        _pa_ok = False
                    if not _pa_ok:
                        missing.append("per_activity")

                    try:
                        cat_breakdown = compute_category_emissions(user_data)
                        _cb_ok = isinstance(cat_breakdown, dict) and len(cat_breakdown) > 0
                    except Exception:
                        _cb_ok = False
                    if not _cb_ok:
                        missing.append("category_breakdown")


                    if missing:
                        st.info(
                            f"PDF not ready: missing {', '.join(missing)}. Please fill inputs and generate tip/summary first."
                        )
                        pdf_bytes, err = None, "Missing inputs for PDF"
                    else:
                        pdf_bytes, err = build_eco_tips_pdf(
                            summary_str,
                            tip_for_pdf,
                            ai_summary_for_pdf,
                            em_today,
                            date_str,
                            src_label,
                            per_activity,
                            cat_breakdown,
                            {
                                "today_total": fmt_emissions(em_today),
                                "yesterday_total": fmt_emissions(yesterday_total) if 'yesterday_total' in locals() else "",
                                "delta_pct": f"{percentage_change(yesterday_total, em_today):.2f}%" if 'yesterday_total' in locals() else "",
                                "streak_days": f"{streak} days" if 'streak' in locals() else "",
                            },
                            logo_bytes=logo_bytes,
                            title_text=pdf_title,
                            primary_color=pdf_primary_color,
                            include_pie=bool(pdf_include_pie),
                            include_sparklines=bool(pdf_include_spark),
                            spark_data=spark,
                            footer_text=pdf_footer_text if pdf_include_footer else None,
                            margins_cm={
                                "side": float(pdf_side_margin),
                                "top": float(pdf_top_margin),
                                "bottom": float(pdf_bottom_margin),
                            },
                            text_hex=pdf_text_color,
                            chart_bg_hex=pdf_chart_bg,
                            experiments_appendix=(
                                st.session_state.get("prompt_experiments")
                                if bool(st.session_state.get("pdf_include_prompt_appendix", False))
                                else None
                            ),
                        )
                    
                    if pdf_bytes:
                        st.download_button(
                            label=" Download Eco Tips PDF",
                            data=pdf_bytes,
                            file_name=f"eco_tips_{date_str}.pdf",
                            mime="application/pdf",
                            key="download_eco_tips_pdf",
                        )
                    # After export, auto-clear experiments if enabled
                    if bool(get_pref("pdf_auto_clear_experiments", st.session_state.get("pdf_auto_clear_experiments", False))):
                        st.session_state["prompt_experiments"] = []
                        st.caption("Auto-cleared in-session prompt experiments after export.")
                    else:
                        st.error(err or "PDF generation failed.")
                    
                
        # Save all (CSV + MD) as ZIP
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            # README.md with quick guide
            readme = []
            readme.append("# Day 6 Report Package")
            readme.append("")
            readme.append("## Files")
            readme.append("- prompt_compare.csv — All test rows (mode/category/ok flags/tip/prompt)")
            readme.append("- prompt_compare.md — Summary + full table in Markdown")
            readme.append("- per_mode_metrics.csv — Per-mode OK rate and diversity with 95% CIs")
            readme.append("- per_mode_metrics.md — Per-mode metrics in Markdown")
            readme.append("- ok_rate.png — OK rate bar chart with error bars")
            readme.append("- unique_tips.png — Unique tips % bar chart with error bars")
            readme.append("- unique_bigrams.png — Unique bigrams % bar chart with error bars")
            readme.append("- ok_rate_over_time.png — OK rate over time with 95% CI (if generated)")
            readme.append("- ok_rate_over_time.csv — Data for over-time chart (if generated)")
            readme.append("- report.html — Interactive HTML report (if charts available)")
            readme.append("")
            readme.append("## How to interpret")
            readme.append("- OK rate: percent of tips that are Relevant, Actionable, and Simple.")
            readme.append("- Unique tips %: lexical uniqueness across tips (case-insensitive).")
            readme.append("- Unique bigrams %: n-gram diversity proxy (higher means more varied phrasing).")
            readme.append("- 95% CI: uncertainty from bootstrap resampling.")
            readme.append("")
            readme.append("## input_type taxonomy (heuristics)")
            readme.append("- empty: no usable numeric or text inputs provided")
            readme.append("- help: explicit request for help (e.g., 'help', '?', 'what should I do?')")
            readme.append("- emoji: text dominated by emojis/symbols (very low alphanumeric ratio)")
            readme.append("- nonsense: symbol-heavy/gibberish without clear meaning")
            readme.append("- negative: any numeric input is negative (per field)")
            readme.append("- extreme: numeric input exceeds per-activity sanity thresholds (heuristics)")
            readme.append("- valid: inputs pass the above checks")
            zf.writestr('README.md', "\n".join(readme))
            # Charts as PNG (if altair_saver available)
            if alt_save is not None:
                try:
                    # Save OK-rate bar with CIs
                    ok_tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                    alt_save(bars_ok + error_ok, ok_tmp.name, fmt='png')
                    with open(ok_tmp.name, 'rb') as _f:
                        zf.writestr('ok_rate.png', _f.read())
                    os.unlink(ok_tmp.name)
                except Exception:
                    pass
            # Include active thresholds JSON for provenance
            try:
                thr_json = json.dumps(get_pref("d6_thresholds", {
                    "electricity_kwh": 200.0,
                    "natural_gas_m3": 100.0,
                    "hot_water_liter": 2000.0,
                    "petrol_liter": 100.0,
                    "diesel_liter": 100.0,
                    "bus_km": 500.0,
                    "rail_km": 1000.0,
                    "meat_kg": 10.0,
                    "dairy_kg": 15.0,
                    "vegetarian_kg": 20.0,
                }), indent=2)
                zf.writestr('edge_case_thresholds.json', thr_json)
            except Exception:
                pass
            zf_bytes = buf.getvalue()
            st.download_button(
                label="⬇️ Save all (CSV + MD) as ZIP",
                data=zf_bytes,
                file_name="day6_results.zip",
                mime="application/zip",
                key="download_day6_zip",
            )

if __name__ == "__main__":
    main()