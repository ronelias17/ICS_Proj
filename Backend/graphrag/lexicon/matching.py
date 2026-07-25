from __future__ import annotations

import re
from collections.abc import Iterable


def contains_any(text: str, terms: Iterable[str]) -> bool:
    """Return true when text contains at least one term."""
    haystack = text or ""
    return any(term in haystack for term in terms)


def matches_pattern(text: str, pattern: re.Pattern[str]) -> bool:
    """Return true when text matches a compiled pattern."""
    return bool(pattern.search(text or ""))
