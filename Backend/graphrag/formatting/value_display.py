from __future__ import annotations

import re
from typing import Any


def normalize_display_value(key: str, value: Any) -> str:
    """Normalize small display-only values for the final answer prompt."""
    if key == "exemption_type" and value == "בח":
        return "בחינת פטור"
    if key in {"monthly_rent", "monthly_total"}:
        return shekel_value(value)
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        parts = [normalize_display_value(key, item) for item in value if item not in (None, "")]
        return ", ".join(dict.fromkeys(part for part in parts if part))
    return str(value)


def shekel_value(value: Any) -> str:
    """Format numeric shekel values for prompt readability."""
    try:
        number = float(str(value).replace(",", ""))
    except ValueError:
        return str(value)
    if number.is_integer():
        return f"{int(number):,} ₪"
    return f"{number:,.2f} ₪"


def comparable_display_value(value: Any) -> str:
    """Return a loose comparable value for suppressing repeated fact text."""
    text = str(value or "").lower()
    text = re.sub(r"[*_`]+", " ", text)
    text = re.sub(r"[^\w\u0590-\u05ff]+", " ", text)
    tokens = [strip_generic_prefix(token) for token in text.split()]
    generic = {"תוכנית", "תכנית", "התוכנית", "התכנית", "התמחות", "מסלול", "ב", "ל", "של"}
    while tokens and tokens[0] in generic:
        tokens.pop(0)
    return " ".join(token for token in tokens if token).strip()


def strip_generic_prefix(token: str) -> str:
    """Remove only obvious Hebrew one-letter prepositions from the first word."""
    if token.startswith("בב") or token.startswith("לל"):
        return token[1:]
    if token.startswith(("לת", "לה", "למ")) and len(token) > 3:
        return token[1:]
    return token


def value_repeats_seen(value: Any, seen_values: list[str]) -> bool:
    """Return true when a value is duplicate or near-contained in this fact."""
    comparable = comparable_display_value(value)
    if len(comparable) < 3:
        return False
    for seen in seen_values:
        if comparable == seen:
            return True
        if min(len(comparable), len(seen)) >= 10 and (comparable in seen or seen in comparable):
            return True
    return False


def readable_amount(value: dict) -> str:
    """Prefer display_amount, then amount_value plus currency/unit."""
    if value.get("display_amount") not in (None, ""):
        return str(value.get("display_amount"))
    if value.get("amount_value") in (None, ""):
        return ""
    amount = str(value.get("amount_value"))
    suffix = value.get("currency") or value.get("amount_unit") or ""
    return f"{amount} {suffix}".strip()


def any_amount_value(value: dict) -> bool:
    """Return true when a dict has fields that collapse into one amount display."""
    return bool(readable_amount(value))
