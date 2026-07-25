from __future__ import annotations

from datetime import datetime
from datetime import timezone


def build_question_record(
    *,
    question: str,
    retrieval: dict,
    answer_result: dict,
    elapsed_seconds: float,
    created_at: datetime | None = None,
) -> dict:
    """Build the app/Mongo-style record for one answered question."""
    timestamp = created_at or datetime.now(timezone.utc)
    graph = retrieval.get("graph") or {}
    error = top_level_error(answer_result)
    selected_entities = (retrieval.get("selected_entities") or {}).get("rows") or []
    return {
        "question": question,
        "answer": answer_result.get("answer", ""),
        "created_at": timestamp.isoformat(),
        "elapsed_ms": seconds_to_ms(elapsed_seconds),
        "retrieval_elapsed_ms": seconds_to_ms(retrieval.get("elapsed_seconds")),
        "answer_elapsed_ms": seconds_to_ms(answer_result.get("elapsed_seconds")),
        "status": "error" if error else "ok",
        "error": error,
        "feedback_positive": None,
        "evidence": {
            "selected_entities": entity_evidence_items(selected_entities, answer_result.get("clean_selected_entities") or []),
            "graph_facts": graph_fact_evidence_items(answer_result.get("clean_graph_facts") or []),
            "source_excerpts": answer_result.get("clean_chunk_excerpt_records") or [],
        },
        "debug": {
            "exact_anchors": exact_anchor_records((retrieval.get("entities") or {}).get("rows") or []),
            "final_cypher": graph.get("generated_cypher", ""),
            "retry_count": graph.get("retry_count", 0),
            "failure_reason": graph.get("error", ""),
            "guard_reason": (graph.get("guard") or {}).get("reason", ""),
        },
    }


def seconds_to_ms(seconds: float | int | str | None) -> int:
    """Convert elapsed seconds to whole milliseconds."""
    try:
        return round(float(seconds or 0.0) * 1000)
    except (TypeError, ValueError):
        return 0


def top_level_error(answer_result: dict) -> str | None:
    """Return the compact app-level error string, if any."""
    if answer_result.get("error"):
        return str(answer_result["error"])
    return None


def exact_anchor_records(entity_rows: list[dict]) -> list[dict]:
    """Return compact exact-anchor records for app debug logs."""
    anchors = []
    for row in entity_rows:
        if "exact_anchor" not in (row.get("retrieval_sources") or []):
            continue
        anchors.append(
            {
                "label": primary_label(row),
                "id": row.get("id", ""),
                "name": row.get("name", ""),
            }
        )
    return anchors


def entity_evidence_items(entity_rows: list[dict], display_texts: list[str]) -> list[dict]:
    """Return compact selected-entity evidence records."""
    items = []
    for index, display_text in enumerate(display_texts):
        row = entity_rows[index] if index < len(entity_rows) else {}
        items.append(
            {
                "id": row.get("id", ""),
                "display_text": display_text,
            }
        )
    return items


def graph_fact_evidence_items(display_texts: list[str]) -> list[dict]:
    """Return compact graph-fact records."""
    return [{"display_text": display_text} for display_text in display_texts]


def primary_label(row: dict) -> str:
    """Return the first non-base graph label for one entity row."""
    return next((label for label in row.get("labels", []) if label != "Entity"), "Entity")
