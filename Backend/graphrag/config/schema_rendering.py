from __future__ import annotations

from graphrag.config.schema_catalog import NODE_SCHEMA
from graphrag.config.schema_selection import select_schema_subset


DISPLAY_RELATIONSHIP_PROPERTIES = {
    "HAS_ADMISSION_REQUIREMENT": (
        "requirement_type",
        "criteria_logic",
        "conditions",
        "deadline",
        "bagrut_average_min",
        "psychometric_min",
        "combined_score_min",
        "math_units",
        "math_grade_min",
        "rule_text",
    ),
    "HAS_FEE": (
        "amount_value",
        "display_amount",
        "currency",
        "amount_unit",
        "deadline",
        "discount_percent",
        "refund_fraction",
        "payment_context",
        "conditions",
        "rule_text",
    ),
    "HAS_POLICY": (
        "deadline",
        "conditions",
        "amount_value",
        "display_amount",
        "discount_percent",
        "refund_fraction",
        "payment_context",
        "rule_text",
    ),
    "HAS_SCHOLARSHIP": ("condition", "psychometric_min", "bagrut_min", "target_audience", "conditions"),
    "HAS_COURSE": ("credits", "weekly_hours", "semester", "year", "required", "course_category"),
    "HAS_HOUSING_UNIT_TYPE": ("occupants", "monthly_rent", "monthly_total", "display_amount", "conditions"),
    "RECOGNIZES_COURSE_FOR_EXEMPTION": ("credits", "semester", "year", "course_category"),
}


def build_schema_payload(
    candidate_labels: list[str] | set[str] | None = None,
    question: str = "",
) -> dict:
    """Render schema text and metadata for one Cypher attempt."""
    labels, relationships = select_schema_subset(
        candidate_labels or [],
        question,
    )
    common_props = {"id", "name", "description"}
    parts = ["Common node properties: id, name, description."]
    node_parts = []
    for label, schema in NODE_SCHEMA.items():
        if label not in labels:
            continue
        props = [prop for prop in schema["properties"] if prop not in common_props]
        extra_props = ", ".join(props) if props else "none"
        node_parts.append(f"{label}({schema['description']} Extra properties: {extra_props})")
    parts.append("Nodes: " + "; ".join(node_parts) + ".")
    rel_parts = []
    for rel in relationships:
        props = ", ".join(display_relationship_properties(rel)) or "none"
        rel_parts.append(f"{rel.pattern}({rel.description} Relationship properties: {props})")
    parts.append("Allowed relationships: " + "; ".join(rel_parts) + ".")
    return {
        "text": " ".join(parts),
        "labels": sorted(labels),
        "relationships": [rel.rel_type for rel in relationships],
    }


def display_relationship_properties(rel) -> tuple[str, ...]:
    """Return the compact relationship-property list shown to the Cypher LLM."""
    configured = DISPLAY_RELATIONSHIP_PROPERTIES.get(rel.rel_type, rel.properties)
    visible = tuple(prop for prop in configured if prop in rel.properties)
    return visible or rel.properties
