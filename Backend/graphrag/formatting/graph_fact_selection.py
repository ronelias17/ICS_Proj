from __future__ import annotations

from typing import Any

from graphrag.lexicon import question_profile as qp
from graphrag.formatting import field_maps
from graphrag.formatting import value_display
from graphrag.lexicon import matching
from graphrag.lexicon.formatting_terms import FORMATTING_TERMS

LIST_FACT_CAP = 15
DEFAULT_FACT_CAP = 8
GRAPH_ROW_GROUP_SUBJECT_KEYS = (
    "program",
    "program_name",
    "owner",
    "housing",
    "parking",
    "service",
    "preparatory_program",
    "contact",
    "faculty",
    "institution",
    "name",
)
GRAPH_ROW_GROUP_OBJECT_KEYS = (
    "requirement",
    "fee",
    "policy",
    "scholarship",
    "document",
    "unit_type",
    "campus",
    "specialization",
    "course",
)


def normalize_row_aliases(row: dict) -> dict:
    """Normalize common generated Cypher aliases before prompt formatting."""
    normalized = {}
    for key, value in row.items():
        normalized[field_maps.ROW_ALIAS_KEYS.get(key, key)] = value
    return normalized


def select_graph_fact_rows(graph_rows: list[dict], question: str) -> list[dict]:
    """Choose the graph rows that should become prompt facts."""
    question_profile = qp.profile(question)
    rows = [row for row in graph_rows if should_keep_graph_row(row, question_profile)]
    rows = sorted(rows, key=lambda row: graph_row_priority(row, question_profile))
    cap = LIST_FACT_CAP if question_profile.has("list") else DEFAULT_FACT_CAP
    return rows[:cap]


def should_keep_graph_row(row: dict, question_profile: qp.QuestionProfile) -> bool:
    """Filter rows that are clearly off-answer for the question."""
    if question_profile.has("required_course") and str(nested_value(row, "required")).lower() in {"false", "no", "לא", "0"}:
        return False
    if question_profile.has("total_credits") and (row.get("course") or row.get("course_name")):
        return False
    if question_profile.has("payment_discount") and row.get("policy"):
        text = row_text(row)
        if not matching.contains_any(text, FORMATTING_TERMS["single_payment_policy"]):
            return False
    if question_profile.has("admission") and row.get("requirement"):
        text = row_text(row)
        if matching.contains_any(text, FORMATTING_TERMS["specialization_noise"]):
            return False
        if wrong_program_admission_row(row):
            return False
    if question_profile.has("degree_structure") and row_has_specialization_shape(row):
        return False
    return True


def wrong_program_admission_row(row: dict) -> bool:
    """Filter admission facts whose evidence/source clearly belongs to another program."""
    program = str(row.get("program") or row.get("program_name") or "")
    text = row_text(row)
    known_wrong_markers = [
        ("עבודה סוציאלית", ["עבודה סוציאלית", "faculties_ba_social_work"]),
    ]
    for owner_name, markers in known_wrong_markers:
        if owner_name in program:
            continue
        if any(marker in text for marker in markers):
            return True
    return False


def row_has_specialization_shape(row: dict) -> bool:
    """Detect specialization rows even when Cypher returned scalar aliases."""
    if row.get("specialization"):
        return True
    return any("specialization" in str(key).lower() for key in row)


def graph_row_priority(row: dict, question_profile: qp.QuestionProfile) -> tuple[int, int, str]:
    """Rank rows with answer-bearing values and obvious question fit first."""
    answer_value = int(not row_has_direct_answer(row))
    if question_profile.has("money_amount") and not row_has_any_key(row, {"display_amount", "amount_value", "monthly_rent", "monthly_total"}):
        answer_value += 2
    if (
        matching.contains_any(question_profile.question, FORMATTING_TERMS["studio"])
        and row.get("unit_type")
        and not matching.contains_any(str(row.get("unit_type")), FORMATTING_TERMS["studio"])
    ):
        answer_value += 2
    if question_profile.has("total_credits") and not (row.get("program") or row.get("program_name")):
        answer_value += 2
    return answer_value, len(str(row)), str(row)[:80]


def nested_value(value: Any, key: str) -> Any:
    """Find one nested property value by key."""
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for child in value.values():
            found = nested_value(child, key)
            if found not in (None, ""):
                return found
    if isinstance(value, list):
        for child in value:
            found = nested_value(child, key)
            if found not in (None, ""):
                return found
    return None


def row_has_any_key(value: Any, keys: set[str]) -> bool:
    """Return true when a row has one of the requested nested keys."""
    if isinstance(value, dict):
        return any(key in keys or row_has_any_key(child, keys) for key, child in value.items())
    if isinstance(value, list):
        return any(row_has_any_key(child, keys) for child in value)
    return False


def row_text(row: dict) -> str:
    """Return a compact text representation for lightweight gates."""
    return str(row)


def group_graph_rows(graph_rows: list[dict]) -> list[dict]:
    """Merge repeated rows that describe the same subject/object answer fact."""
    grouped: dict[tuple[str, ...], dict] = {}
    ordered_keys: list[tuple[str, ...]] = []
    for index, row in enumerate(graph_rows):
        key = graph_row_group_key(row, index)
        if key not in grouped:
            grouped[key] = {}
            ordered_keys.append(key)
        merge_row_values(grouped[key], row)
    return [grouped[key] for key in ordered_keys]


def graph_row_group_key(row: dict, index: int) -> tuple[str, ...]:
    """Choose a stable grouping key from common subject/object answer fields."""
    subject = first_present_value(row, GRAPH_ROW_GROUP_SUBJECT_KEYS)
    obj = first_present_value(row, GRAPH_ROW_GROUP_OBJECT_KEYS)
    if subject and obj:
        return ("pair", value_display.comparable_display_value(subject), value_display.comparable_display_value(obj))
    if subject:
        return ("subject", value_display.comparable_display_value(subject))
    value_key = scalar_row_group_key(row)
    if value_key:
        return ("values", *value_key)
    return ("row", str(index))


def scalar_row_group_key(row: dict) -> tuple[str, ...]:
    """Group rows that only differ by hidden graph path but display the same values."""
    values = []
    for key, value in row.items():
        if key in field_maps.INTERNAL_KEYS or value in (None, "", [], {}):
            continue
        comparable = value_display.comparable_display_value(value)
        if comparable:
            values.append(f"{key}:{comparable}")
    return tuple(sorted(values))


def first_present_value(row: dict, keys: list[str]) -> str:
    """Return the first scalar value found for common grouping fields."""
    for key in keys:
        value = row.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value)
    return ""


def merge_row_values(target: dict, source: dict) -> None:
    """Merge repeated graph row values while preserving distinct answer values."""
    for key, value in source.items():
        if key in field_maps.INTERNAL_KEYS or value in (None, "", [], {}):
            continue
        if key not in target:
            target[key] = value
            continue
        target[key] = merge_value(target[key], value)


def merge_value(existing: Any, new_value: Any) -> Any:
    """Merge scalar/list/dict values without creating duplicate display values."""
    if existing == new_value or new_value in (None, "", [], {}):
        return existing
    if isinstance(existing, dict) and isinstance(new_value, dict):
        merged = dict(existing)
        merge_row_values(merged, new_value)
        return merged
    values = existing if isinstance(existing, list) else [existing]
    additions = new_value if isinstance(new_value, list) else [new_value]
    for addition in additions:
        if addition in (None, ""):
            continue
        if not any(values_equivalent(addition, value) for value in values):
            values.append(addition)
    return values[0] if len(values) == 1 else values


def values_equivalent(left: Any, right: Any) -> bool:
    """Compare values by exact equality and normalized display similarity."""
    if left == right:
        return True
    left_text = value_display.comparable_display_value(left)
    right_text = value_display.comparable_display_value(right)
    return bool(left_text and left_text == right_text)


def row_has_direct_answer(value: Any) -> bool:
    """Detect graph rows that already contain answer-bearing fields."""
    if isinstance(value, dict):
        return any(key in field_maps.DIRECT_ANSWER_KEYS or row_has_direct_answer(child) for key, child in value.items())
    if isinstance(value, list):
        return any(row_has_direct_answer(item) for item in value)
    return False
