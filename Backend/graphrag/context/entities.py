from __future__ import annotations

from typing import Any

from graphrag.lexicon import question_profile as qp
from graphrag.clients.neo4j import Neo4jReadClient
from graphrag.retrievers import candidate_ranking

GRAPH_FIELD_LABELS = {
    "program": "Program",
    "program_name": "Program",
    "housing": "Housing",
    "unit_type": "HousingUnitType",
    "parking": "Parking",
    "campus": "Campus",
    "contact": "ContactPoint",
    "faculty": "Faculty",
    "institution": "Institution",
    "service": "StudentService",
    "preparatory_program": "PreparatoryProgram",
    "document": "Policy",
    "name": "ContactPoint",
    "fee": "Fee",
    "policy": "Policy",
    "requirement": "AdmissionRequirement",
    "scholarship": "Scholarship",
    "specialization": "Specialization",
    "course": "Course",
}


def fetch_selected_entities(
    neo4j_client: Neo4jReadClient,
    question: str,
    graph_rows: list[dict],
    entity_candidates: list[dict],
) -> list[dict]:
    """Fetch public properties for up to three selected anchor entities."""
    anchors = selected_anchor_specs(question, graph_rows, entity_candidates)
    ids = [anchor["id"] for anchor in anchors if anchor.get("id")]
    names = [anchor["name"] for anchor in anchors if anchor.get("name")]
    if not ids and not names:
        return []
    rows = neo4j_client.run_rows(
        """
        MATCH (e:Entity)
        WHERE e.id IN $ids OR e.name IN $names
        RETURN e.id AS id, labels(e) AS labels, properties(e) AS properties
        LIMIT 30
        """,
        {"ids": ids, "names": names},
    )
    indexed = {row.get("id"): row for row in rows if row.get("id")}
    by_name = {row.get("properties", {}).get("name"): row for row in rows if row.get("properties", {}).get("name")}
    selected = []
    seen = set()
    for anchor in anchors:
        row = indexed.get(anchor.get("id")) or by_name.get(anchor.get("name"))
        if not row or row.get("id") in seen:
            continue
        selected.append(clean_entity_row(row))
        seen.add(row.get("id"))
        if len(selected) >= 3:
            break
    return selected


def selected_anchor_specs(question: str, graph_rows: list[dict], entity_candidates: list[dict]) -> list[dict]:
    """Select anchor specs from graph rows first, then retrieved candidates."""
    question_profile = qp.profile(question)
    graph_anchors: list[dict] = []
    for row in graph_rows:
        for field, label in GRAPH_FIELD_LABELS.items():
            value = row.get(field)
            if isinstance(value, str) and value.strip():
                graph_anchors.append({"label": label, "name": value.strip(), "id": "", "source": "graph"})
    if any(anchor.get("label") == "Program" for anchor in graph_anchors):
        return dedupe_anchors([anchor for anchor in graph_anchors if anchor.get("label") == "Program"])
    if graph_anchors:
        return dedupe_anchors(graph_anchors)
    if question_profile.primary in {"document", "scholarship"}:
        program_candidates = [
            candidate
            for candidate in sorted(entity_candidates, key=candidate_ranking.selected_anchor_candidate_sort_key)
            if candidate_ranking.primary_label(candidate.get("labels") or []) == "Program"
        ]
        if program_candidates:
            return dedupe_anchors(
                [
                    {
                        "label": "Program",
                        "name": program_candidates[0].get("name") or "",
                        "id": program_candidates[0].get("id") or "",
                        "source": "candidate",
                    }
                ]
            )
    if question_profile.has_any(("admission", "required_course", "degree_structure")):
        program_candidates = [
            candidate
            for candidate in sorted(entity_candidates, key=candidate_ranking.selected_anchor_candidate_sort_key)
            if candidate_ranking.primary_label(candidate.get("labels") or []) == "Program"
        ]
        if program_candidates:
            return dedupe_anchors(
                [
                    {
                        "label": "Program",
                        "name": candidate.get("name") or "",
                        "id": candidate.get("id") or "",
                        "source": "candidate",
                    }
                    for candidate in program_candidates[:2]
                ]
            )
    anchors = list(graph_anchors)
    for candidate in sorted(entity_candidates, key=candidate_ranking.selected_anchor_candidate_sort_key):
        anchors.append(
            {
                "label": candidate_ranking.primary_label(candidate.get("labels") or []),
                "name": candidate.get("name") or "",
                "id": candidate.get("id") or "",
                "source": "candidate",
            }
        )
    return dedupe_anchors(anchors)


def dedupe_anchors(anchors: list[dict]) -> list[dict]:
    """Dedupe anchors while preserving priority order."""
    seen = set()
    result = []
    for anchor in anchors:
        key = anchor.get("id") or f"{anchor.get('label')}:{anchor.get('name')}"
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(anchor)
    return result


def label_rank(label: str) -> int:
    """Rank labels for selected anchors."""
    return candidate_ranking.label_rank(label, candidate_ranking.SELECTED_ANCHOR_LABEL_PRIORITY)


def clean_entity_row(row: dict) -> dict:
    """Strip internal fields from a fetched entity row."""
    properties = row.get("properties") or {}
    labels = [label for label in row.get("labels") or [] if label != "Entity"]
    return {
        "id": row.get("id"),
        "label": labels[0] if labels else "Entity",
        "properties": {
            key: value
            for key, value in properties.items()
            if is_public_entity_property(key, value, properties.get("name"))
        },
    }


def is_public_entity_property(key: str, value: Any, name: str | None) -> bool:
    """Return true for useful public entity properties."""
    if key in {"id", "embedding", "embedding_text", "source_id", "chunk_id", "import_key", "aliases"}:
        return False
    if key.startswith("_") or key.endswith("_score") or "rank" in key:
        return False
    if value in (None, "", [], {}):
        return False
    if key == "description" and name and str(value).strip() == str(name).strip():
        return False
    if isinstance(value, str) and len(value) > 380:
        return False
    return isinstance(value, (str, int, float, bool, list))
