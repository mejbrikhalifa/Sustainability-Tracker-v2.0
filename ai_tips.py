# ai_tips.py
import os
from dotenv import load_dotenv
import time
from functools import lru_cache
from openai import OpenAIError

import random
import re
from types import SimpleNamespace

# Optional .env loading and Streamlit secrets; create client lazily to avoid import-time failures
try:
    load_dotenv()
except Exception:
    pass
import streamlit as st

def get_openai_key() -> str | None:
    """Return OpenAI key from env or Streamlit secrets (if set).
    Never raises if secrets.toml is absent; returns None instead.
    """
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key
    try:
        return st.secrets.get("OPENAI_API_KEY")
    except Exception:
        return None

_client = None
# Public client object used by tests for monkeypatching. We initialize a minimal
# placeholder that has the expected attribute path so patching
# ai_tips.client.chat.completions.create works even before a real client exists.
class _DummyCompletions:
    def create(self, **kwargs):  # pragma: no cover - replaced in tests
        raise OpenAIError("No OpenAI client initialized")

class _DummyChat:
    def __init__(self):
        self.completions = _DummyCompletions()

# Exposed symbol
client = SimpleNamespace(chat=_DummyChat())
def get_openai_client():
    """Create and cache the OpenAI client lazily. Returns None if no key."""
    global _client
    if _client is not None:
        return _client
    key = get_openai_key()
    if not key:
        return None
    # Local import to avoid hard failure if package missing until actually needed
    from openai import OpenAI
    _client = OpenAI(api_key=key)
    # Keep public alias in sync so external patches to ai_tips.client still work
    try:
        # Only replace the exposed client if it still looks like the dummy
        # to avoid stomping on test patches that attached to the dummy object.
        if isinstance(getattr(client, "chat", None), _DummyChat):
            globals()["client"] = _client
    except Exception:
        globals()["client"] = _client
    return _client

# Public flag for UI to inspect last tip source: "gpt" | "fallback" | "unknown"
LAST_TIP_SOURCE = "unknown"

# Configurable LLM parameters (set by the app via set_llm_params)
_TIP_TEMPERATURE: float = 0.7
_TIP_MAX_TOKENS: int = 160
_SUM_TEMPERATURE: float = 0.5
_SUM_MAX_TOKENS: int = 220

def set_llm_params(
    tip_temperature: float | None = None,
    tip_max_tokens: int | None = None,
    summary_temperature: float | None = None,
    summary_max_tokens: int | None = None,
):
    """Allow the UI to tune LLM parameters at runtime.
    Any None values are ignored (leave current setting).
    """
    global _TIP_TEMPERATURE, _TIP_MAX_TOKENS, _SUM_TEMPERATURE, _SUM_MAX_TOKENS
    if isinstance(tip_temperature, (int, float)):
        _TIP_TEMPERATURE = float(tip_temperature)
    if isinstance(tip_max_tokens, (int, float)):
        _TIP_MAX_TOKENS = int(tip_max_tokens)
    if isinstance(summary_temperature, (int, float)):
        _SUM_TEMPERATURE = float(summary_temperature)
    if isinstance(summary_max_tokens, (int, float)):
        _SUM_MAX_TOKENS = int(summary_max_tokens)


# Short-lived negative cache for failing GPT calls to prevent repeated hits
_NEG_CACHE: dict[str, float] = {}
_NEG_TTL_SECONDS = 60.0
# Local factors used only for rules-based fallback logic.
# These mirror typical factors used elsewhere in the app, but are intentionally local
# so this module stays self-contained and never crashes due to imports.
LOCAL_CO2_FACTORS = {
    "electricity_kwh": 0.233,
    "natural_gas_m3": 2.03,
    "hot_water_liter": 0.25,
    "cold_water_liter": 0.075,
    "district_heating_kwh": 0.15,
    "propane_liter": 1.51,
    "fuel_oil_liter": 2.52,
    "petrol_liter": 0.235,
    "diesel_liter": 0.268,
    "bus_km": 0.12,
    "train_km": 0.14,
    "bicycle_km": 0.0,
    "flight_short_km": 0.275,
    "flight_long_km": 0.175,
    "meat_kg": 27.0,
    "chicken_kg": 6.9,
    "eggs_kg": 4.8,
    "dairy_kg": 13.0,
    "vegetarian_kg": 2.0,
    "vegan_kg": 1.5,
}

# Simple mapping of activities to categories (kept local to avoid cross-module deps)
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


# Allowed activity keys for sanitization
ALLOWED_KEYS = {k for keys in CATEGORY_MAP.values() for k in keys}

def _sanitize_inputs_for_prompt(user_data: dict) -> dict:
    """Sanitize raw user activity inputs for prompt/context use.

    What this does:
    - Keeps only allowed activity keys from `CATEGORY_MAP`.
    - Coerces values to floats where possible; drops non-numeric.
    - Normalizes negatives to 0 and clamps extremes using heuristic thresholds.
    - Returns a new dict safe for model prompts, summaries, and caching keys.

    Notes:
    - This function prevents prompt-injection via unexpected keys or strings.
    - Extremes are capped to reduce accidental outliers from dominating context.
    """
    if not isinstance(user_data, dict):
        return {}
    out = {}
    for k, v in user_data.items():
        if k not in ALLOWED_KEYS:
            continue
        try:
            f = float(v or 0)
        except Exception:
            continue
        if f < 0:
            f = 0.0
        thr = EXTREME_THRESHOLDS.get(k)
        if isinstance(thr, (int, float)) and f > float(thr):
            f = float(thr)
        out[k] = f
    return out


def sanitize_inputs_for_prompt(user_data: dict) -> dict:
    """Public alias for `_sanitize_inputs_for_prompt` for external callers.

    See `_sanitize_inputs_for_prompt` for details on clamping and key filtering.
    """
    return _sanitize_inputs_for_prompt(user_data)

# Per-activity numeric sanity thresholds (heuristics). Values above these are considered 'extreme'.
EXTREME_THRESHOLDS = {
    # Energy
    "electricity_kwh": 200.0,        # kWh/day (very high household day)
    "natural_gas_m3": 100.0,         # m^3/day
    "hot_water_liter": 2000.0,       # liters/day
    # Transport
    "petrol_liter": 100.0,           # liters/day
    "diesel_liter": 100.0,
    "bus_km": 500.0,                 # km/day
    "train_km": 1000.0,
    # Meals (by mass consumed)
    "meat_kg": 10.0,                 # kg/day
    "dairy_kg": 15.0,
    "vegetarian_kg": 20.0,
}

def set_extreme_thresholds(new_thresholds: dict | None):
    """Override the default EXTREME_THRESHOLDS with values from the app.
    Pass a dict of {key: float}. Invalid entries are ignored.
    """
    global EXTREME_THRESHOLDS
    if not isinstance(new_thresholds, dict):
        return
    updated = EXTREME_THRESHOLDS.copy()
    for k, v in new_thresholds.items():
        try:
            updated[k] = float(v)
        except Exception:
            continue
    EXTREME_THRESHOLDS = updated

# -------- Ambiguity & input checks --------
def _has_meaningful_inputs(user_data: dict) -> bool:
    if not isinstance(user_data, dict) or not user_data:
        return False
    for v in user_data.values():
        try:
            if float(v or 0) > 0:
                return True
        except Exception:
            continue
    return False

def _generic_tip_or_clarify() -> str:
    # Provide a concise general tip and a clarifying follow‑up
    return (
        "💡 Turn off unused lights, unplug idle chargers, and take a short walk instead of a 1–2 km drive. "
        "Would you like a tip about Transport, Meals, or Energy?"
    )

def classify_input_type(user_data: dict) -> str:
    """Classify input edge-case type for logging and analysis.
    Returns one of: empty, help, emoji, nonsense, negative, extreme, valid.
    """
    if not isinstance(user_data, dict) or not user_data:
        return "empty"
    texts = []
    nums = []
    # Per-key numeric scan (catch negative or extreme early)
    for k, v in user_data.items():
        if isinstance(v, str):
            texts.append(v.strip())
            continue
        try:
            fv = float(v)
            nums.append(fv)
            if fv < 0:
                return "negative"
            thr = EXTREME_THRESHOLDS.get(k)
            if isinstance(thr, (int, float)) and fv > float(thr):
                return "extreme"
        except Exception:
            # ignore non-numeric
            pass
    # Empty-ish
    if (not texts) and (not nums):
        return "empty"
    # Help or question
    if any(t.lower() in {"help", "?", "what should i do?", "what can i do?"} for t in texts if t):
        return "help"
    # Emoji or symbol-heavy (few alnum)
    import re
    if any(t and (len(re.findall(r"[A-Za-z0-9]", t)) <= max(1, len(t) // 5)) for t in texts):
        # If contains common emoji/symbols
        if any(ch for ch in "🚗🍔💡🔥✨🌱😊👍🏽⚡" if (ch in "".join(texts))):
            return "emoji"
        # Otherwise likely nonsense
        return "nonsense"
    return "valid"

def _compute_breakdowns(user_data: dict, emissions: float):
    """Compute per-activity kg, per-category totals, dominant category and labels.
    Returns a dict with keys: activity_lines, category_lines, dominant_cat, dominant_pct, emission_level.
    """
    # Per-activity
    activity_kg = {}
    for k, v in (user_data or {}).items():
        try:
            amt = float(v or 0)
        except Exception:
            amt = 0.0
        factor = LOCAL_CO2_FACTORS.get(k, 0.0)
        kg = amt * factor
        if kg > 0:
            activity_kg[k] = kg

    # Per-category totals
    cat_totals = {cat: 0.0 for cat in CATEGORY_MAP}
    for cat, keys in CATEGORY_MAP.items():
        for k in keys:
            try:
                amt = float((user_data or {}).get(k, 0) or 0)
            except Exception:
                amt = 0.0
            cat_totals[cat] += amt * LOCAL_CO2_FACTORS.get(k, 0.0)

    # Dominant category
    if cat_totals:
        dominant_cat = max(cat_totals.items(), key=lambda x: x[1])[0]
        dom_val = cat_totals[dominant_cat]
        dominant_pct = (dom_val / emissions * 100.0) if emissions and emissions > 0 else 0.0
    else:
        dominant_cat, dominant_pct = "", 0.0

    # Emission level bucket
    if emissions > 50:
        emission_level = "high"
    elif emissions > 25:
        emission_level = "moderate"
    else:
        emission_level = "low"

    # Human-friendly lines
    activity_lines = []
    for k, kg in sorted(activity_kg.items(), key=lambda x: x[1], reverse=True)[:5]:
        activity_lines.append(f"- {k.replace('_', ' ')}: {kg:.2f} kg CO₂")

    category_lines = []
    total = max(emissions, 0.0001)
    for cat, val in sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)[:5]:
        pct = (val / total) * 100.0
        category_lines.append(f"- {cat}: {val:.2f} kg ({pct:.1f}%)")

    return {
        "activity_lines": "\n".join(activity_lines) if activity_lines else "(no impactful activities logged)",
        "category_lines": "\n".join(category_lines) if category_lines else "(no categories)",
        "dominant_cat": dominant_cat,
        "dominant_pct": dominant_pct,
        "emission_level": emission_level,
    }

def generate_eco_tip(user_data: dict, emissions: float) -> str:
    """Public entry point used by the app. Tries GPT with caching and backoff;
    falls back to local rules if key missing or calls fail.
    """
    global LAST_TIP_SOURCE
    # Sanitize inputs for prompting/caching and handle ambiguous/noisy inputs up front
    safe_inputs = _sanitize_inputs_for_prompt(user_data)
    # Handle ambiguous/noisy inputs up front
    if not _has_meaningful_inputs(safe_inputs):
        LAST_TIP_SOURCE = "fallback"
        return clean_tip(_generic_tip_or_clarify())
    if not get_openai_key():
        print("⚠️ OPENAI_API_KEY not set. Using local tip generator.")
        LAST_TIP_SOURCE = "fallback"
        return clean_tip(local_tip(safe_inputs, emissions))

    # Build a deterministic, structured context string for better prompting + caching
    try:
        breakdown = _compute_breakdowns(safe_inputs, float(emissions or 0))
        context_str = (
            f"EMISSION LEVEL: {breakdown['emission_level']}\n"
            f"DOMINANT CATEGORY: {breakdown['dominant_cat']} ({breakdown['dominant_pct']:.1f}%)\n\n"
            f"ACTIVITY BREAKDOWN:\n{breakdown['activity_lines']}\n\n"
            f"CATEGORY BREAKDOWN:\n{breakdown['category_lines']}\n"
        )
    except Exception:
        # Fallback to simple key=value summary for cache key if something goes wrong
        try:
            context_str = ",".join(f"{k}={safe_inputs.get(k, 0)}" for k in sorted(safe_inputs.keys()))
        except Exception:
            context_str = str(sorted(safe_inputs.items()))

    tip = _generate_eco_tip_cached(context_str, float(emissions or 0))
    if tip:
        LAST_TIP_SOURCE = "gpt"
        return clean_tip(tip)
    LAST_TIP_SOURCE = "fallback"
    return clean_tip(local_tip(safe_inputs, emissions))

@lru_cache(maxsize=128)
def _generate_eco_tip_cached(user_data_key: str, emissions: float) -> str:
    """Cached GPT tip generator. Returns empty string on failure to signal fallback."""
    # Negative-cache gate: if we recently failed for this key, skip calling GPT
    now = time.time()
    exp = _NEG_CACHE.get(user_data_key)
    if isinstance(exp, (int, float)) and exp > now:
        return ""
    prompt = (
        """
        Provide 1 short, actionable eco-tip focused on the dominant category.
        - Use today's total: {emissions:.2f} kg
        - Context:
        {structured_context}
        Rules: specific and doable in 24–48h; max 2 short sentences; positive tone; use a matching emoji (⚡/🚗/🥗) if relevant.
        """.strip()
    ).format(structured_context=user_data_key, emissions=emissions)

    tip = _gpt_tip_from_prompt(prompt)
    if not tip:
        _NEG_CACHE[user_data_key] = time.time() + _NEG_TTL_SECONDS
    return tip

def _gpt_tip_from_prompt(prompt: str) -> str:
    """Helper: call OpenAI with a provided prompt and return text or empty on failure."""
    # Simulation flag (for stress/end-to-end testing): force fallbacks
    if os.environ.get("SIMULATE_API_FAILURES"):
        return ""    
    # Use the public client object so tests can patch it directly
    cli = globals().get("client")
    # If no key, or client doesn't expose the needed path, bail out
    if not get_openai_key():
        return ""
    try:
        create_fn = cli.chat.completions.create  # type: ignore[attr-defined]
    except Exception:
        return ""
    retries = 3
    base_delay = 1.0
    for attempt in range(retries):
        try:
            response = create_fn(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a sustainability assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=_TIP_MAX_TOKENS,
                temperature=_TIP_TEMPERATURE,
            )
            return (response.choices[0].message.content or "").strip()
        except OpenAIError as e:
            sleep_s = base_delay * (2 ** attempt) + random.random() * 0.5
            print(f"⚠️ GPT call failed (attempt {attempt+1}/{retries}): {e}. Retrying in {sleep_s:.1f}s...")
            time.sleep(sleep_s)
        except Exception as e:
            print(f"⚠️ Unexpected GPT error: {e}")
            break
    return ""

# --- Prompt experimentation API ---

def _build_prompt_variant(
    emissions: float,
    structured_context: str,
    mode: str = "Contextualized",
    category: str | None = None,
) -> str:
    """Return a prompt string for the chosen mode. Modes: Directive, Contextualized, Persona.
    Optional category ("Energy", "Transport", "Meals") adds an extra focus cue.
    """
    cat_hint = ""
    if isinstance(category, str) and category in ("Energy", "Transport", "Meals"):
        cat_hint = f"\nFocus category: {category}."

    if mode == "Directive":
        return (
            """
            Provide 1 concise, actionable eco-tip for the next 24–48h. Target the highest-impact activity today.
            {cat_hint}
            Total: {emissions:.2f} kg
            Context:
            {structured_context}
            """.strip()
        ).format(emissions=emissions, structured_context=structured_context, cat_hint=cat_hint)

    if mode == "Persona":
        return (
            """
            Friendly coach tone. Give ONE practical action (max 2 short sentences) for the next 24–48h. Include a relevant emoji.
            {cat_hint}
            Total: {emissions:.2f} kg
            Context:
            {structured_context}
            """.strip()
        ).format(emissions=emissions, structured_context=structured_context, cat_hint=cat_hint)

    # Default: Contextualized
    return (
        """
        Suggest ONE concrete action to cut the largest source today. 1–2 short sentences, positive tone.
        {cat_hint}
        Total: {emissions:.2f} kg
        Context:
        {structured_context}
        """.strip()
    ).format(emissions=emissions, structured_context=structured_context, cat_hint=cat_hint)

def generate_eco_tip_with_prompt(
    user_data: dict,
    emissions: float,
    mode: str = "Contextualized",
    category: str | None = None,
) -> tuple[str, str]:
    """Generate an eco tip for experimentation, returning (tip_text, prompt_text).
    Respects OPENAI_API_KEY and falls back to local rules; on fallback, returns the constructed prompt with a note.
    """
    # Sanitize inputs
    safe_inputs = _sanitize_inputs_for_prompt(user_data)

    # Ambiguity handling: if no meaningful inputs, return general tip + clarification
    if not _has_meaningful_inputs(safe_inputs):
        tip = _generic_tip_or_clarify()
        # Still return a synthetic prompt explaining ambiguity handling for logging
        prompt = (
            "Ambiguous inputs detected (no meaningful activity values). "
            "Returning general fallback + clarification question."
        )
        return clean_tip(tip), prompt
    # Build structured context
    breakdown = _compute_breakdowns(safe_inputs, float(emissions or 0))
    structured_context = (
        f"EMISSION LEVEL: {breakdown['emission_level']}\n"
        f"DOMINANT CATEGORY: {breakdown['dominant_cat']} ({breakdown['dominant_pct']:.1f}%)\n\n"
        f"ACTIVITY BREAKDOWN:\n{breakdown['activity_lines']}\n\n"
        f"CATEGORY BREAKDOWN:\n{breakdown['category_lines']}\n"
    )
    prompt = _build_prompt_variant(float(emissions or 0), structured_context, mode=mode, category=category)

    if not get_openai_key():
        tip = local_tip(safe_inputs, emissions)
        return clean_tip(tip), prompt + "\n\n(Note: Fallback used; no API key)"

    # Call GPT with the exact prompt
    tip_text = _gpt_tip_from_prompt(prompt)
    if not tip_text:
        tip_text = local_tip(safe_inputs, emissions)
    return clean_tip(tip_text), prompt

def local_tip(user_data: dict, emissions: float) -> str:
    """
    Simple rules-based fallback that never crashes and gives helpful, actionable tips.
    - Identifies the largest-emitting activity using LOCAL_CO2_FACTORS
    - Provides a targeted tip for that activity
    - Includes tiered guidance based on total emissions
    """
    # Largest emitter detection
    best_key = None
    best_kg = 0.0
    for k, amt in user_data.items():
        try:
            amt_f = float(amt or 0)
        except Exception:
            amt_f = 0.0
        factor = LOCAL_CO2_FACTORS.get(k)
        if factor is None:
            continue
        kg = amt_f * factor
        if kg > best_kg:
            best_kg = kg
            best_key = k

    # Tiered guidance based on total emissions
    if emissions > 60:
        preface = "🚨 High footprint today."
    elif emissions > 25:
        preface = "🌱 Moderate footprint today."
    else:
        preface = "🌍 Low footprint today—nice work!"

    # Targeted, practical suggestions
    tips_by_key = {
        # Energy
        "electricity_kwh": "Reduce standby power: switch devices fully off, use smart strips, and swap to LED bulbs.",
        "natural_gas_m3": "Lower heating setpoint by 1°C and seal drafts to cut gas use.",
        "hot_water_liter": "Take shorter showers and wash clothes on cold to cut hot water.",
        "cold_water_liter": "Fix leaks and install low‑flow faucets to save water and energy.",
        "district_heating_kwh": "Use a programmable thermostat and improve insulation to reduce heat demand.",
        "propane_liter": "Service your boiler and optimize thermostat schedules to trim propane use.",
        "fuel_oil_liter": "Schedule a boiler tune‑up and improve home insulation to cut oil use.",
        # Transport
        "petrol_liter": "Try car‑pooling or public transport 1–2 days/week; keep tires properly inflated.",
        "diesel_liter": "Combine errands into one trip and ease acceleration to save fuel.",
        "bus_km": "Great choice using the bus—consider a weekly pass to keep it going.",
        "train_km": "Nice! Train is low‑carbon—can you replace a short car trip with train?",
        "bicycle_km": "Awesome cycling—aim to replace one short car errand by bike this week.",
        "flight_short_km": "Consider rail for short trips, or bundle meetings to reduce flight frequency.",
        "flight_long_km": "Plan fewer long‑haul flights; if needed, choose non‑stop routes and economy seats.",
        # Meals
        "meat_kg": "Try a meat‑free day or swap red meat for chicken/plant‑based options.",
        "chicken_kg": "Balance meals with beans, lentils, and seasonal veggies a few times this week.",
        "eggs_kg": "Source from local farms and add plant‑based proteins to diversify.",
        "dairy_kg": "Switch to plant milk for coffee/tea and try dairy‑free snacks.",
        "vegetarian_kg": "Great! Add pulses and whole grains for protein and nutrition.",
        "vegan_kg": "Excellent! Keep variety with legumes, nuts, and B12‑fortified foods.",
    }

    if best_key and best_key in tips_by_key and best_kg > 0:
        return f"{preface} Biggest source: {best_key.replace('_', ' ')}. Tip: {tips_by_key[best_key]}"

    # Otherwise choose a general practical tip based on broad categories
    energy_load = sum((float(user_data.get(k, 0) or 0)) * LOCAL_CO2_FACTORS.get(k, 0) for k in [
        "electricity_kwh", "natural_gas_m3", "district_heating_kwh", "propane_liter", "fuel_oil_liter"
    ])
    transport_load = sum((float(user_data.get(k, 0) or 0)) * LOCAL_CO2_FACTORS.get(k, 0) for k in [
        "petrol_liter", "diesel_liter", "bus_km", "train_km", "flight_short_km", "flight_long_km"
    ])
    meals_load = sum((float(user_data.get(k, 0) or 0)) * LOCAL_CO2_FACTORS.get(k, 0) for k in [
        "meat_kg", "chicken_kg", "dairy_kg", "eggs_kg"
    ])

    if transport_load >= energy_load and transport_load >= meals_load and transport_load > 0:
        return f"{preface} Transport dominates—plan a no‑car day, try car‑pooling, or take the bus/train for one commute."
    if energy_load >= transport_load and energy_load >= meals_load and energy_load > 0:
        return f"{preface} Energy dominates—set heating 1–2°C lower and switch off devices fully at night."
    if meals_load > 0:
        return f"{preface} Diet is a big lever—try a meat‑free day and batch‑cook plant‑based meals this week."

    # Final generic tip
    return f"{preface} Start small: one meat‑free meal, one public‑transport trip, and switch devices fully off tonight."

def clean_tip(tip: str, max_sentences: int = 2) -> str:
    tip = _sanitize_tip_output(tip)
    if not tip:
        return ""
    # Limit to max_sentences
    parts = [p.strip() for p in tip.split('.') if p.strip()]
    if len(parts) > max_sentences:
        tip = '. '.join(parts[:max_sentences]).strip() + '.'
    # Nudge overly long outputs
    if len(tip) > 280:
        tip = tip[:277].rstrip() + '…'
    return tip

def generate_tip(user_data: dict, emissions: float) -> str:
    """Facade used by the UI.
    Always returns a tip string: on GPT failure/empty result, returns local fallback
    instead of surfacing a warning to the UI.
    """
    try:
        tip = generate_eco_tip(user_data, emissions)
        if isinstance(tip, str) and tip.strip():
            return tip
    except Exception:
        # Fall back below
        pass
    # Fallback path: never raise, always produce a helpful tip
    safe_inputs = _sanitize_inputs_for_prompt(user_data)
    try:
        tip = local_tip(safe_inputs, emissions)
    except Exception:
        tip = _generic_tip_or_clarify()
    globals()["LAST_TIP_SOURCE"] = "fallback"
    return clean_tip(tip)

# Optional: AI-powered daily summary generator with fallback

def generate_ai_summary(
    user_data: dict,
    emissions: float,
    date: str | None = None,
    comparison_text: str | None = None,
    streak_days: int = 0,
    weekly_context: str | None = None,
) -> str:
    """Generate a concise AI summary. Falls back to a rules-based summary if API is unavailable.
    This function is additive and does not change existing UI unless wired in.
    """
    safe_inputs = _sanitize_inputs_for_prompt(user_data)  # <-- add this line

    def _fallback_summary() -> str:
        b = _compute_breakdowns(safe_inputs, float(emissions or 0))
        parts = []
        if date:
            parts.append(f"Date: {date}.")
        parts.append(f"Total: {emissions:.2f} kg CO₂ ({b['emission_level']}).")
        if comparison_text:
            parts.append(comparison_text)
        if streak_days and streak_days > 0:
            parts.append(f"Streak: {streak_days} days.")
        if b["dominant_cat"]:
            parts.append(f"{b['dominant_cat']} led today ({b['dominant_pct']:.1f}%).")
        return " ".join(parts)

    if not get_openai_key():
        return _fallback_summary()

    b = _compute_breakdowns(safe_inputs, float(emissions or 0))
    structured = (
        f"DATE: {date or '(unknown)'}\n"
        f"TOTAL: {emissions:.2f} kg CO₂\n"
        f"COMPARISON: {comparison_text or 'n/a'}\n"
        f"STREAK: {streak_days} days\n"
        f"EMISSION LEVEL: {b['emission_level']}\n"
        f"DOMINANT: {b['dominant_cat']} ({b['dominant_pct']:.1f}%)\n\n"
        f"ACTIVITIES:\n{b['activity_lines']}\n\n"
        f"CATEGORIES:\n{b['category_lines']}\n\n"
        f"WEEKLY CONTEXT:\n{weekly_context or '(none)'}\n"
    )

    prompt = (
        """
        You are a sustainability data analyst providing an insightful daily summary.

        USER DATA (structured):
        {structured}

        Write a concise 3–4 sentence summary that includes:
        - Performance snapshot (low/moderate/high, key achievement/concern, streak acknowledgment if >0)
        - Impact analysis (top 1–2 contributors with rough percentages)
        - One actionable forward-looking suggestion
        - Conversational tone with 1–2 relevant emojis, end motivationally
        """.strip()
    ).format(structured=structured)

    # Use the public client object so tests can patch it directly
    cli = globals().get("client")
    if not get_openai_key():
        return _fallback_summary()
    try:
        create_fn = cli.chat.completions.create  # type: ignore[attr-defined]
    except Exception:
        return _fallback_summary()
    retries = 3
    base_delay = 1.0
    for attempt in range(retries):
        try:
            response = create_fn(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful, data-driven sustainability analyst."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=_SUM_MAX_TOKENS,
                temperature=_SUM_TEMPERATURE,
            )
            text = (response.choices[0].message.content or "").strip()
            return text or _fallback_summary()
        except OpenAIError as e:
            sleep_s = base_delay * (2 ** attempt) + random.random() * 0.5
            print(f"⚠️ GPT summary failed (attempt {attempt+1}/{retries}): {e}. Retrying in {sleep_s:.1f}s...")
            time.sleep(sleep_s)
        except Exception as e:
            print(f"⚠️ Unexpected GPT summary error: {e}")
            break
    return _fallback_summary()

def _sanitize_tip_output(t: str) -> str:
    """Collapse whitespace, strip risky content, enforce length for card display.
    Guardrails: no URLs/HTML/code blocks, no product endorsements, no medical/unsafe advice.
    Limit to ~220 chars.
    """
    if not isinstance(t, str):
        return ""
    t = t.strip()
    if not t:
        return ""
    # Strip code fences and HTML
    t = re.sub(r"```[\s\S]*?```", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    # Remove URLs
    t = re.sub(r"https?://\S+", "", t)
    # Basic content guardrails
    forbidden = [
        r"\b(doctor|medical|prescription|drug|supplement)\b",
        r"\b(buy|purchase|brand|discount|coupon|sponsor)\b",
    ]
    for pat in forbidden:
        if re.search(pat, t, flags=re.IGNORECASE):
            t = re.sub(pat, "", t, flags=re.IGNORECASE)
    # Normalize whitespace
    t = re.sub(r"\s+", " ", t).strip()
    # Enforce short length for card view
    if len(t) > 220:
        t = t[:217].rstrip() + "…"
    return t
