from __future__ import annotations


CYPHER_CANDIDATE_LABEL_PRIORITY = (
    "Program",
    "Faculty",
    "PreparatoryProgram",
    "ContactPoint",
    "StudentService",
    "Fee",
    "Policy",
    "AdmissionRequirement",
    "Scholarship",
    "Housing",
    "HousingUnitType",
    "Parking",
    "Campus",
    "Specialization",
    "Course",
)

SELECTED_ANCHOR_LABEL_PRIORITY = (
    "Program",
    "PreparatoryProgram",
    "Housing",
    "HousingUnitType",
    "Parking",
    "Campus",
    "ContactPoint",
    "Fee",
    "Policy",
    "AdmissionRequirement",
    "Scholarship",
    "Specialization",
    "Course",
)


def primary_label(labels: list[str]) -> str:
    """Return the first domain label from a Neo4j label list."""
    return next((label for label in labels if label != "Entity"), "Entity")


def label_rank(label: str, priority: tuple[str, ...]) -> int:
    """Return label rank according to one explicit priority list."""
    return priority.index(label) if label in priority else len(priority)


def best_label_rank(labels: list[str], priority: tuple[str, ...]) -> int:
    """Return the best rank among all domain labels."""
    ranks = [label_rank(label, priority) for label in labels if label != "Entity"]
    return min(ranks, default=len(priority))


def candidate_score(candidate: dict) -> float:
    """Return the merged retrieval score used for stable candidate ordering."""
    return float(candidate.get("rrf_score") or candidate.get("score") or 0.0)


def selected_anchor_candidate_sort_key(candidate: dict) -> tuple[int, float, str]:
    """Sort entity candidates for selected evidence anchors."""
    label = primary_label(candidate.get("labels") or [])
    return label_rank(label, SELECTED_ANCHOR_LABEL_PRIORITY), -candidate_score(candidate), str(candidate.get("id") or "")


def cypher_candidate_sort_key(candidate: dict) -> tuple[int, float, str]:
    """Sort entity candidates for Cypher prompt hints."""
    labels = candidate.get("labels") or []
    return best_label_rank(labels, CYPHER_CANDIDATE_LABEL_PRIORITY), -candidate_score(candidate), str(candidate.get("id") or "")
