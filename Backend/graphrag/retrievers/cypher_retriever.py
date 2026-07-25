from __future__ import annotations

from graphrag.clients.neo4j import Neo4jReadClient
from graphrag.graph_execution.cypher_guard import validate_cypher
from graphrag.graph_execution import cypher_result_quality
from graphrag.llm_tasks.cypher_generator import CypherGenerator
from graphrag.llm_tasks.cypher_generator import exact_anchor_ids
from graphrag.llm_tasks.cypher_generator import unknown_schema_terms


MAX_CYPHER_ATTEMPTS = 2
SOFT_ROW_ERRORS = (
    "zero_rows",
    "empty_answer_rows",
    "missing_policy_node_value",
    "missing_required_answer_value:",
)


class CypherRetriever:
    """Generate safe Cypher, run it on Neo4j, and return graph rows."""

    def __init__(self, neo4j_client: Neo4jReadClient, cypher_generator: CypherGenerator):
        """Create a graph retriever from a Neo4j client and Cypher generator."""
        self.neo4j_client = neo4j_client
        self.cypher_generator = cypher_generator

    def retrieve(self, question: str, entity_candidates: list[dict] | None = None) -> dict:
        """Run the text-to-Cypher graph retrieval stage."""
        candidates = entity_candidates or []
        attempt_count = 0
        rows: list[dict] = []
        error = ""
        generation: dict = {}
        guard = validate_cypher("")
        retry_feedback = ""
        for attempt_number in range(1, MAX_CYPHER_ATTEMPTS + 1):
            attempt_count = attempt_number
            generation = self.cypher_generator.generate(
                question,
                entity_candidates=candidates,
                retry_feedback=retry_feedback,
                include_examples=attempt_number == 1,
            )
            guard = validate_cypher(generation["cypher"])
            rows, error = self.try_run_attempt(question, guard, generation, candidates)
            if rows and not error:
                break
            if error and not should_retry_cypher_error(error):
                break
            retry_feedback = cypher_result_quality.retry_feedback_for_attempt(guard, generation, error)
        if not rows and not error:
            error = "zero_rows"
        if not error and generation.get("error") and not rows:
            error = generation.get("error", "")
        return {
            "generated_cypher": guard.cypher if guard.ok else generation["cypher"],
            "guard": {
                "ok": guard.ok,
                "reason": guard.reason,
            },
            "rows": rows,
            "error": error,
            "retry_count": max(0, attempt_count - 1),
        }

    def try_run_attempt(self, question: str, guard, generation: dict, candidates: list[dict]) -> tuple[list[dict], str]:
        """Validate schema terms, run one generated Cypher attempt, and return rows/error."""
        schema_error = validate_attempt_schema(guard, generation)
        if schema_error:
            return [], schema_error
        rows, run_error = self.run_guarded_cypher(guard.cypher)
        if run_error:
            return [], run_error
        row_error = reject_bad_attempt_rows(question, rows, guard.cypher, candidates)
        if row_error:
            return [], row_error
        return rows, ""

    def run_guarded_cypher(self, cypher: str) -> tuple[list[dict], str]:
        """Run validated Cypher and convert driver errors into retry reasons."""
        try:
            return self.neo4j_client.run_rows(cypher), ""
        except Exception as exc:
            return [], f"{type(exc).__name__}: {exc}"


def validate_attempt_schema(guard, generation: dict) -> str:
    """Return a retry reason when generated Cypher is unsafe or out of scope."""
    if not guard.ok:
        return guard.reason
    unknown = unknown_schema_terms(guard.cypher)
    if unknown["labels"] or unknown["relationships"]:
        return f"unknown_schema_terms:{unknown}"
    outside_attempt_schema = cypher_result_quality.schema_terms_outside_attempt(guard.cypher, generation)
    if outside_attempt_schema["labels"] or outside_attempt_schema["relationships"]:
        return f"schema_terms_outside_attempt_schema:{outside_attempt_schema}"
    return ""


def reject_bad_attempt_rows(question: str, rows: list[dict], cypher: str, candidates: list[dict]) -> str:
    """Return a retry reason when graph rows do not answer the question."""
    if not rows:
        return exact_anchor_failure_reason(cypher, candidates) or "zero_rows"
    if cypher_result_quality.rows_are_answer_empty(question, rows):
        return "empty_answer_rows"
    policy_value_reason = cypher_result_quality.missing_policy_node_value(question, rows)
    if policy_value_reason:
        return policy_value_reason
    missing_value_reason = cypher_result_quality.missing_required_answer_value(question, rows)
    if missing_value_reason:
        return missing_value_reason
    return ""


def exact_anchor_failure_reason(cypher: str, candidates: list[dict]) -> str:
    """Return a retry reason when generated Cypher ignored exact anchors."""
    required_ids = exact_anchor_ids(candidates)
    if required_ids and not any(entity_id in cypher for entity_id in required_ids):
        return "generated_cypher_ignored_exact_anchor_candidates"
    return ""


def should_retry_cypher_error(error: str) -> bool:
    """Return true for hard Cypher failures that are worth a second LLM attempt."""
    return bool(error) and not is_soft_row_quality_error(error)


def is_soft_row_quality_error(error: str) -> bool:
    """Return true when chunks/entities should take over instead of retrying Cypher."""
    return any(error == item or error.startswith(item) for item in SOFT_ROW_ERRORS)
