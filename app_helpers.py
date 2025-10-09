"""Pure helpers extracted from app.py for unit testing without Streamlit.

Functions:
- _coerce_float(v)
- has_meaningful_input(user_data)
- find_invalid_fields(user_data)
- should_generate_tip(user_data)
"""
from typing import Any, Dict, List, Optional

__all__ = [
    "_coerce_float",
    "has_meaningful_input",
    "find_invalid_fields",
    "should_generate_tip",
]


def _coerce_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except Exception:
        return None


def has_meaningful_input(user_data: Dict[str, Any]) -> bool:
    """True if at least one numeric input is > 0."""
    for v in user_data.values():
        fv = _coerce_float(v)
        if (fv is not None) and (fv > 0):
            return True
    return False


def find_invalid_fields(user_data: Dict[str, Any]) -> List[str]:
    """Return keys that are non-numeric or negative."""
    bad: List[str] = []
    for k, v in user_data.items():
        fv = _coerce_float(v)
        if fv is None:
            bad.append(k)
        elif fv < 0:
            bad.append(k)
    return bad


def should_generate_tip(user_data: Dict[str, Any]) -> bool:
    """Return True if inputs are valid and meaningful, else False."""
    invalid = find_invalid_fields(user_data)
    if invalid:
        return False
    return has_meaningful_input(user_data)
