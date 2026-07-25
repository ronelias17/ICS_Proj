from __future__ import annotations

import re

from graphrag.clients.llm import LocalChatClient
from graphrag.clients.llm import chat_messages
from graphrag.config.examples import examples_text
from graphrag.config.prompts import CYPHER_SYSTEM_PROMPT, CYPHER_USER_TEMPLATE
from graphrag.config import schema
from graphrag.config.settings import GraphRagSettings
from graphrag.retrievers import candidate_ranking


class CypherGenerator:
    """Generate a read-only Cypher query from a question and curated schema."""

    def __init__(self, settings: GraphRagSettings, llm: LocalChatClient | None = None):
        """Create the Cypher generator with a local chat client."""
        self.settings = settings
        self.llm = llm or LocalChatClient(settings)

    def generate(
        self,
        question: str,
        entity_candidates: list[dict] | None = None,
        *,
        retry_feedback: str = "",
        include_examples: bool = True,
    ) -> dict:
        """Return generated Cypher and the schema terms shown for this attempt."""
        candidates = entity_candidates or []
        intent = schema.detect_question_intent(question)
        schema_labels = candidate_schema_labels(question, candidates)
        schema_payload = schema.build_schema_payload(
            candidate_labels=schema_labels,
            question=question,
        )
        examples = examples_text(question=question, intent=intent) if include_examples else ""
        candidates_text = format_entity_candidates(
            question,
            candidates,
            allowed_labels=set(schema_payload["labels"]),
            limit=5,
        )
        user_prompt = CYPHER_USER_TEMPLATE.format(
            schema=schema_payload["text"],
            examples=examples,
            entity_candidates=candidates_text,
            question=question,
            retry_feedback=retry_feedback_text(retry_feedback),
        )
        messages = chat_messages(CYPHER_SYSTEM_PROMPT, user_prompt)
        response = self.llm.complete(messages, max_tokens=self.settings.cypher_max_tokens, temperature=0.0, llm_request_attempts=1)
        cypher = extract_cypher(response.content)
        return {
            "cypher": cypher,
            "error": response.error,
            "schema_labels": schema_payload["labels"],
            "schema_relationships": schema_payload["relationships"],
            "include_examples": include_examples,
        }

def extract_cypher(text: str) -> str:
    """Extract the first Cypher-looking query from LLM output."""
    if not text:
        return ""
    cleaned = re.sub(r"```(?:cypher)?", "", text, flags=re.IGNORECASE).replace("```", "").strip()
    match = re.search(r"(?is)\b(MATCH|OPTIONAL MATCH|WITH|RETURN|UNWIND)\b.*", cleaned)
    if not match:
        return ""
    cypher = match.group(0).strip()
    return re.split(r"\n\s*(?:Explanation|הסבר)\s*:", cypher, maxsplit=1)[0].strip()


def retry_feedback_text(feedback: str) -> str:
    """Render retry feedback only when a previous attempt failed."""
    if not feedback:
        return ""
    return (
        "Previous attempt failed:\n"
        f"{feedback}\n"
        "Generate a corrected query. Prefer the candidate IDs above and bind answer-bearing relationships as r."
    )


def unknown_schema_terms(cypher: str) -> dict:
    """Return labels/relationship types in Cypher that are not in the clean schema."""
    labels = set(re.findall(r":\s*([A-Za-z][A-Za-z0-9_]*)", cypher or ""))
    relationships = set(re.findall(r"\[\s*(?:[A-Za-z_][\w]*\s*)?:\s*([A-Z_][A-Z0-9_]*)", cypher or ""))
    return {
        "labels": sorted(label for label in labels if label not in schema.valid_labels() and not label.isupper()),
        "relationships": sorted(rel for rel in relationships if rel not in schema.valid_relationship_types()),
    }


def exact_anchor_ids(entity_candidates: list[dict]) -> list[str]:
    """Return exact-anchor candidate IDs that generated Cypher should prefer."""
    ids = []
    for item in entity_candidates:
        sources = item.get("retrieval_sources") or []
        if "exact_anchor" in sources and item.get("id"):
            ids.append(item["id"])
    return ids


def format_entity_candidates(
    question: str,
    entity_candidates: list[dict],
    *,
    allowed_labels: set[str] | None = None,
    limit: int = 8,
) -> str:
    """Render compact candidate hints for the Cypher prompt."""
    if not entity_candidates:
        return "- none"
    allowed = allowed_labels or candidate_display_labels(question, entity_candidates)
    lines = []
    for item in sorted(entity_candidates, key=candidate_ranking.cypher_candidate_sort_key)[:limit]:
        labels = [label for label in item.get("labels", []) if label != "Entity"]
        label = labels[0] if labels else "Entity"
        if label not in allowed:
            continue
        variable = variable_for_label(label)
        lines.append(f'- ({variable}:{label} {{id: "{escape_cypher_string(item.get("id", ""))}", name: "{escape_cypher_string(item.get("name", ""))}"}})')
    return "\n".join(lines) if lines else "- none"


def candidate_schema_labels(question: str, entity_candidates: list[dict]) -> set[str]:
    """Collect intent-compatible labels from top sorted candidates."""
    intent = schema.detect_question_intent(question)
    exact_labels = exact_anchor_labels(entity_candidates)
    allowed = schema.allowed_candidate_labels_for_intent(intent, question) | exact_labels
    labels = set()
    for item in sorted(entity_candidates, key=candidate_ranking.cypher_candidate_sort_key)[:8]:
        labels.update(label for label in item.get("labels", []) if label in allowed)
    return labels


def candidate_display_labels(question: str, entity_candidates: list[dict]) -> set[str]:
    """Allow exact-anchor and current-intent labels in candidate hints."""
    intent = schema.detect_question_intent(question)
    return exact_anchor_labels(entity_candidates) | schema.allowed_candidate_labels_for_intent(intent, question)


def exact_anchor_labels(entity_candidates: list[dict]) -> set[str]:
    """Return domain labels for candidates injected by exact-anchor matching."""
    labels = set()
    for item in entity_candidates:
        if "exact_anchor" not in (item.get("retrieval_sources") or []):
            continue
        labels.update(label for label in item.get("labels", []) if label != "Entity")
    return labels


def variable_for_label(label: str) -> str:
    """Return readable Cypher variables for candidate hints."""
    return {
        "Program": "p",
        "AdmissionRequirement": "a",
        "Fee": "f",
        "Policy": "policy",
        "Course": "course",
        "Specialization": "s",
        "Parking": "parking",
        "Campus": "campus",
        "Housing": "housing",
        "HousingUnitType": "unit_type",
        "ContactPoint": "contact",
        "Faculty": "faculty",
        "Institution": "institution",
        "PreparatoryProgram": "prep",
        "Scholarship": "scholarship",
        "StudentService": "service",
    }.get(label, "e")


def escape_cypher_string(value: object) -> str:
    """Escape a value for display inside a Cypher-like candidate hint."""
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')
