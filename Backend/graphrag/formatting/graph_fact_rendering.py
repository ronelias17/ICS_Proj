from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from graphrag.formatting import field_maps
from graphrag.formatting import value_display


@dataclass(frozen=True)
class EdgeFactShape:
    """Describe one relationship-shaped graph fact row."""

    from_key: str
    to_key: str
    title: str
    relation: str

    def matches(self, row: dict) -> bool:
        """Return true when both edge endpoints are present in the row."""
        return bool(row.get(self.from_key) and row.get(self.to_key))

    def to_dict(self) -> dict:
        """Return the legacy edge shape dict used by append_edge_lines."""
        return {"title": self.title, "from_key": self.from_key, "to_key": self.to_key, "relation": self.relation}


OWNER_EDGE_LABELS = (("program", "Program"), ("owner", "Owner"), ("housing", "Housing"), ("parking", "Parking"))

EDGE_FACT_SHAPES = (
    EdgeFactShape("program", "requirement", "Program -> AdmissionRequirement", "תנאי קבלה"),
    EdgeFactShape("program", "course", "Program -> Course", "קורס בתוכנית"),
    EdgeFactShape("program", "specialization", "Program -> Specialization", "התמחות / מסלול"),
    EdgeFactShape("program", "scholarship", "Program -> Scholarship", "מלגה"),
    EdgeFactShape("program", "document", "Program -> Document", "מסמך"),
    EdgeFactShape("service", "contact", "StudentService -> ContactPoint", "פרטי קשר"),
    EdgeFactShape("housing", "unit_type", "Housing -> HousingUnitType", "סוג יחידת דיור"),
    EdgeFactShape("parking", "campus", "Parking -> Campus", "מיקום"),
    *(EdgeFactShape(owner_key, "fee", f"{owner_label} -> Fee", "תשלום / עלות") for owner_key, owner_label in OWNER_EDGE_LABELS),
    *(EdgeFactShape(owner_key, "policy", f"{owner_label} -> Policy", "מדיניות / כלל") for owner_key, owner_label in OWNER_EDGE_LABELS),
)

RELATION_LABEL_BY_KEY = (
    ("course", "קורס בתוכנית"),
    ("requirement", "תנאי קבלה"),
    ("fee", "תשלום / עלות"),
    ("policy", "מדיניות / כלל"),
    ("scholarship", "מלגה"),
    ("document", "מסמך נדרש"),
    ("contact", "פרטי קשר"),
    ("service", "שירות סטודנטים"),
    ("unit_type", "סוג יחידת דיור"),
    ("specialization", "התמחות / מסלול"),
)


def relation_label_for_row(row: dict) -> str:
    """Infer a readable relation label from common Cypher return columns."""
    edge = matching_edge_shape(row)
    if edge:
        return edge.relation
    for key, label in RELATION_LABEL_BY_KEY:
        if row.get(key):
            return label
    if row.get("campus") and row.get("parking"):
        return "מיקום"
    return ""


def edge_shape_for_row(row: dict) -> dict:
    """Return a readable edge shape for common relationship rows."""
    edge = matching_edge_shape(row)
    return edge.to_dict() if edge else {}


def matching_edge_shape(row: dict) -> EdgeFactShape | None:
    """Return the first known edge shape matched by a row."""
    for shape in EDGE_FACT_SHAPES:
        if shape.matches(row):
            return shape
    return None


def append_edge_lines(lines: list[str], row: dict, edge: dict, *, seen: set[str], seen_values: list[str]) -> None:
    """Append a relationship-shaped fact with From/Relation/To lines."""
    lines.append(edge["title"])
    append_value_lines(lines, "from", row.get(edge["from_key"]), indent="", seen=seen, seen_values=seen_values)
    append_value_lines(lines, "relation", edge["relation"], indent="", seen=seen, seen_values=seen_values)
    append_value_lines(lines, "to", row.get(edge["to_key"]), indent="", seen=seen, seen_values=seen_values)
    skip = {edge["from_key"], edge["to_key"], "relation"}
    append_amount_line(lines, row, indent="", seen=seen, seen_values=seen_values)
    for key, value in row.items():
        if key in skip or (key in field_maps.AMOUNT_KEYS and value_display.any_amount_value(row)):
            continue
        append_value_lines(lines, key, value, indent="", seen=seen, seen_values=seen_values)


def append_value_lines(lines: list[str], key: str, value: Any, *, indent: str, seen: set[str], seen_values: list[str]) -> None:
    """Append a clean display line for one row field or nested property dict."""
    if key in field_maps.INTERNAL_KEYS or value in (None, "", [], {}):
        return
    label = field_maps.DISPLAY_KEYS.get(key, key)
    if isinstance(value, dict):
        append_amount_line(lines, value, indent=indent, seen=seen, seen_values=seen_values)
        for child_key, child_value in value.items():
            if child_key in field_maps.AMOUNT_KEYS and value_display.any_amount_value(value):
                continue
            append_value_lines(lines, child_key, child_value, indent=indent, seen=seen, seen_values=seen_values)
        return
    normalized = value_display.normalize_display_value(key, value)
    if normalized in (None, ""):
        return
    if value_display.value_repeats_seen(normalized, seen_values):
        return
    line = f"{indent}{label}: {normalized}"
    if line in seen:
        return
    seen.add(line)
    comparable = value_display.comparable_display_value(normalized)
    if comparable:
        seen_values.append(comparable)
    lines.append(line)


def append_amount_line(lines: list[str], value: dict, *, indent: str, seen: set[str], seen_values: list[str]) -> None:
    """Display one clean amount line from amount/currency fields."""
    amount = value_display.readable_amount(value)
    if not amount:
        return
    if value_display.value_repeats_seen(amount, seen_values):
        return
    line = f"{indent}Amount: {amount}"
    if line not in seen:
        seen.add(line)
        comparable = value_display.comparable_display_value(amount)
        if comparable:
            seen_values.append(comparable)
        lines.append(line)
