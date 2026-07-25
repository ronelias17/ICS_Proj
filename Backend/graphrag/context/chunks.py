from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from graphrag.lexicon import question_profile as qp
from graphrag.clients.neo4j import Neo4jReadClient
from graphrag.lexicon import matching
from graphrag.lexicon.evidence_terms import EVIDENCE_TERMS
from graphrag.lexicon.question_terms import QUESTION_TERMS

BASE_REASON_SCORES = {"graph_provenance": 3.0, "anchor_mentions": 2.0, "next_chunk_neighbor": 1.7, "rrf_fill": 0.5}


@dataclass(frozen=True)
class ChunkSelectionContext:
    """Shared state for one chunk selection pass."""

    question: str
    profile: qp.QuestionProfile
    selected_program_names: tuple[str, ...]
    rrf_by_id: dict[str, dict]
    limit: int


@dataclass(frozen=True)
class ChunkSource:
    """Rows from one chunk source with the reason they were selected."""

    reason: str
    rows: list[dict]


def select_source_chunks(
    neo4j_client: Neo4jReadClient,
    question: str,
    graph_rows: list[dict],
    selected_entities: list[dict],
    rrf_chunks: list[dict],
) -> list[dict]:
    """Select provenance, anchor-mentioned, then RRF-fill chunks."""
    context = build_chunk_selection_context(question, graph_rows, selected_entities, rrf_chunks)
    sources = fetch_chunk_sources(neo4j_client, graph_rows, selected_entities, rrf_chunks)
    merged = merge_chunk_sources(sources, context)
    if should_expand_neighbor_chunks(context):
        neighbor_chunks = fetch_neighbor_chunks(neo4j_client, top_seed_chunk_ids(merged))
        merge_chunk_source(merged, ChunkSource("next_chunk_neighbor", neighbor_chunks), context)
    return rank_and_limit_chunks(merged, context)


def build_chunk_selection_context(
    question: str,
    graph_rows: list[dict],
    selected_entities: list[dict],
    rrf_chunks: list[dict],
) -> ChunkSelectionContext:
    """Build shared selection state once per question."""
    return ChunkSelectionContext(
        question=question,
        profile=qp.profile(question),
        selected_program_names=selected_program_names(selected_entities),
        rrf_by_id={chunk.get("id"): chunk for chunk in rrf_chunks if chunk.get("id")},
        limit=4 if not graph_rows else 3,
    )


def selected_program_names(selected_entities: list[dict]) -> tuple[str, ...]:
    """Return selected program names for wrong-program chunk filtering."""
    return tuple(
        str(entity.get("properties", {}).get("name") or "")
        for entity in selected_entities
        if entity.get("label") == "Program"
    )


def fetch_chunk_sources(
    neo4j_client: Neo4jReadClient,
    graph_rows: list[dict],
    selected_entities: list[dict],
    rrf_chunks: list[dict],
) -> list[ChunkSource]:
    """Fetch primary chunk sources before optional neighbor expansion."""
    return [
        ChunkSource("graph_provenance", fetch_chunks_by_ids(neo4j_client, chunk_ids_from_graph_rows(graph_rows))),
        ChunkSource("anchor_mentions", fetch_anchor_chunks(neo4j_client, [entity["id"] for entity in selected_entities if entity.get("id")])),
        ChunkSource("rrf_fill", rrf_chunks),
    ]


def merge_chunk_sources(sources: list[ChunkSource], context: ChunkSelectionContext) -> dict[str, dict]:
    """Merge all chunk sources into one ID-keyed map."""
    merged: dict[str, dict] = {}
    for source in sources:
        merge_chunk_source(merged, source, context)
    return merged


def top_seed_chunk_ids(merged: dict[str, dict]) -> list[str]:
    """Return top merged chunk IDs used for neighbor expansion."""
    return [
        chunk.get("id")
        for chunk in sorted_chunks(merged.values())[:4]
        if chunk.get("id")
    ]


def rank_and_limit_chunks(merged: dict[str, dict], context: ChunkSelectionContext) -> list[dict]:
    """Return final chunks ordered by score and capped by context limit."""
    return sorted_chunks(merged.values())[: context.limit]


def sorted_chunks(chunks: Iterable[dict]) -> list[dict]:
    """Sort chunks by evidence score and stable ID."""
    return sorted(chunks, key=lambda chunk: (-float(chunk.get("evidence_score") or 0.0), str(chunk.get("id") or "")))


@dataclass(frozen=True)
class NodeFetchSpec:
    """Cypher fragments for one chunk-source fetch."""

    match: str
    where: str
    return_alias: str
    limit: int
    extra_return: str = ""
    order_by: str = "id"


FETCH_CHUNKS_BY_ID = NodeFetchSpec(
    match="MATCH (c:Chunk)",
    where="c.id IN $ids",
    return_alias="c",
    limit=40,
)
FETCH_ANCHOR_CHUNKS = NodeFetchSpec(
    match="MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)",
    where="e.id IN $ids",
    return_alias="c",
    limit=60,
    extra_return="collect(e.id) AS mentioned_entity_ids",
)
FETCH_NEIGHBOR_CHUNKS = NodeFetchSpec(
    match="MATCH (c:Chunk)-[:NEXT_CHUNK]-(n:Chunk)",
    where="c.id IN $ids",
    return_alias="n",
    limit=20,
)


def fetch_chunks_by_ids(neo4j_client: Neo4jReadClient, chunk_ids: list[str]) -> list[dict]:
    """Fetch Chunk rows by internal chunk IDs."""
    return fetch_nodes(neo4j_client, FETCH_CHUNKS_BY_ID, chunk_ids)


def fetch_anchor_chunks(neo4j_client: Neo4jReadClient, entity_ids: list[str]) -> list[dict]:
    """Fetch chunks that mention selected anchor entities."""
    return fetch_nodes(neo4j_client, FETCH_ANCHOR_CHUNKS, entity_ids)


def fetch_neighbor_chunks(neo4j_client: Neo4jReadClient, chunk_ids: list[str]) -> list[dict]:
    """Fetch one-hop NEXT_CHUNK neighbors for document/submission context."""
    return fetch_nodes(neo4j_client, FETCH_NEIGHBOR_CHUNKS, chunk_ids)


def chunk_ids_from_graph_rows(graph_rows: list[dict]) -> list[str]:
    """Extract chunk IDs from nested graph row relationship properties."""
    ids = []
    for chunk_id in iter_chunk_ids(graph_rows):
        ids.append(chunk_id)
        if not chunk_id.startswith("chunk_"):
            ids.append(f"chunk_{chunk_id}")
    return list(dict.fromkeys(ids))


def iter_chunk_ids(value: Any) -> Iterable[str]:
    """Yield chunk_id values from nested graph row dictionaries."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "chunk_id" and isinstance(child, str):
                yield child
            else:
                yield from iter_chunk_ids(child)
    elif isinstance(value, list):
        for item in value:
            yield from iter_chunk_ids(item)


def node_projection(alias: str) -> str:
    """Return the shared Chunk projection for a Cypher variable."""
    return f"""
           {alias}.id AS id,
           coalesce({alias}.display_title, {alias}.page_title, {alias}.title, "") AS title,
           coalesce({alias}.section_heading, "") AS section_heading,
           coalesce({alias}.text, "") AS text
    """.strip()


def fetch_nodes(neo4j_client: Neo4jReadClient, spec: NodeFetchSpec, ids: list[str]) -> list[dict]:
    """Fetch chunks using a small Cypher fragment spec."""
    if not ids:
        return []
    extra_return = f",\n               {spec.extra_return}" if spec.extra_return else ""
    return neo4j_client.run_rows(
        f"""
        {spec.match}
        WHERE {spec.where}
        RETURN {node_projection(spec.return_alias)}{extra_return}
        ORDER BY {spec.order_by}
        LIMIT {spec.limit}
        """,
        {"ids": ids},
    )


def merge_chunk_source(
    merged: dict[str, dict],
    source: ChunkSource,
    context: ChunkSelectionContext,
) -> None:
    """Merge one chunk source into the ID-keyed map."""
    for chunk in source.rows:
        row_id = chunk.get("id")
        if not row_id:
            continue
        chunk_context = build_chunk_context(chunk, context)
        if should_skip_candidate(chunk_context, source.reason):
            continue
        existing = merged.get(row_id)
        score = score_chunk(chunk_context, source.reason)
        if existing:
            existing["evidence_score"] = max(float(existing.get("evidence_score") or 0.0), score)
            if source.reason not in existing["selection_reasons"]:
                existing["selection_reasons"].append(source.reason)
            continue
        merged[row_id] = chunk_with_selection_metadata(chunk, source.reason, score)


@dataclass(frozen=True)
class ChunkContext:
    """Inputs needed by chunk filtering and scoring rules."""

    chunk: dict
    question: str
    profile: qp.QuestionProfile
    text: str
    selected_program_names: tuple[str, ...]
    rrf_chunk: dict | None = None


def build_chunk_context(chunk: dict, context: ChunkSelectionContext) -> ChunkContext:
    """Build per-chunk state from shared selection context."""
    return ChunkContext(
        chunk=chunk,
        question=context.question,
        profile=context.profile,
        text=chunk_text(chunk),
        selected_program_names=context.selected_program_names,
        rrf_chunk=context.rrf_by_id.get(chunk.get("id")),
    )


def should_skip_candidate(context: ChunkContext, reason: str) -> bool:
    """Return true when a chunk should not enter the merged candidate set."""
    if should_skip_chunk_context(context):
        return True
    return reason == "rrf_fill" and chunk_mentions_other_program(context.chunk, context.selected_program_names)


def chunk_with_selection_metadata(chunk: dict, reason: str, score: float) -> dict:
    """Return one selected chunk row with score and source reason metadata."""
    return {
        **chunk,
        "selection_reason": reason,
        "selection_reasons": [reason],
        "evidence_score": score,
    }


@dataclass(frozen=True)
class ChunkFilterRule:
    """One chunk filter rule."""

    intent: str | None = None
    any_intents: tuple[str, ...] = ()
    not_intents: tuple[str, ...] = ()
    required_evidence_terms: str | None = None
    custom: Callable[[ChunkContext], bool] | None = None
    terminal: bool = False

    def applies(self, profile: qp.QuestionProfile) -> bool:
        """Return true when this filter applies to the question profile."""
        if self.intent and not profile.has(self.intent):
            return False
        if self.any_intents and not profile.has_any(self.any_intents):
            return False
        return not any(profile.has(intent) for intent in self.not_intents)

    def should_skip(self, context: ChunkContext) -> bool:
        """Return true when this filter should remove the chunk."""
        if self.required_evidence_terms:
            return not matching.contains_any(context.text, EVIDENCE_TERMS[self.required_evidence_terms])
        if self.custom:
            return self.custom(context)
        return False


def should_skip_chunk_context(context: ChunkContext) -> bool:
    """Drop chunks that are clearly off-intent for the final answer prompt."""
    for rule in CHUNK_FILTER_RULES:
        if not rule.applies(context.profile):
            continue
        if rule.should_skip(context):
            return True
        if rule.terminal:
            return False
    return False


def should_expand_neighbor_chunks(context: ChunkSelectionContext) -> bool:
    """Expand nearby chunks only for questions likely to span adjacent sections."""
    return context.profile.has("document_submission") or context.profile.has("document_deadline")


def skip_parking_only_chunk(context: ChunkContext) -> bool:
    """Skip parking-only chunks when the active question is not parking-centered."""
    return is_parking_only_chunk(context.chunk)


def skip_admission_noise_chunk(context: ChunkContext) -> bool:
    """Skip scholarship/specialization chunks in admission prompts."""
    if matching.contains_any(context.text, EVIDENCE_TERMS["scholarship_text"]) and not matching.contains_any(context.question, EVIDENCE_TERMS["scholarship_text"]):
        return True
    return matching.contains_any(context.text, EVIDENCE_TERMS["admission_specialization_noise"])


def skip_required_course_noise_chunk(context: ChunkContext) -> bool:
    """Skip chunks that are not useful required-course evidence."""
    if not matching.contains_any(context.text, EVIDENCE_TERMS["required_course_evidence"]):
        return True
    if matching.contains_any(context.text, EVIDENCE_TERMS["required_course_elective"]) and not matching.contains_any(
        context.text,
        EVIDENCE_TERMS["required_course_core"],
    ):
        return True
    if matching.contains_any(context.text, EVIDENCE_TERMS["payment_noise"]):
        return True
    if matching.contains_any(context.text, EVIDENCE_TERMS["admission_chunk_noise"]):
        return True
    return matching.contains_any(context.text, EVIDENCE_TERMS["admission_specialization_noise"])


def skip_degree_structure_noise_chunk(context: ChunkContext) -> bool:
    """Skip admission/payment chunks in degree-structure comparison prompts."""
    return matching.contains_any(context.text, EVIDENCE_TERMS["admission_title_marker"]) or matching.contains_any(
        context.text,
        EVIDENCE_TERMS["degree_structure_payment_noise"],
    )


def skip_non_location_parking_chunk(context: ChunkContext) -> bool:
    """Keep only parking chunks that carry location evidence."""
    if not matching.contains_any(context.text, EVIDENCE_TERMS["parking_entity_text"]):
        return True
    if not matching.contains_any(context.text, EVIDENCE_TERMS["parking_location_text"]):
        return True
    return matching.contains_any(context.text, EVIDENCE_TERMS["parking_price_text"]) and not matching.contains_any(
        context.text,
        EVIDENCE_TERMS["parking_location_context"],
    )


def is_parking_only_chunk(chunk: dict) -> bool:
    """Detect parking support chunks that are not dorm unit price-list chunks."""
    text = chunk_text(chunk)
    title = str(chunk.get("title") or "")
    has_parking = matching.contains_any(text, EVIDENCE_TERMS["parking_chunk"])
    if not has_parking:
        return False
    if matching.contains_any(title, QUESTION_TERMS["parking"]):
        return True
    if matching.contains_any(text, EVIDENCE_TERMS["parking_policy"]):
        return True
    has_housing_price = matching.contains_any(text, EVIDENCE_TERMS["housing_price_table"])
    return not has_housing_price


def chunk_mentions_other_program(chunk: dict, selected_program_names: Iterable[str]) -> bool:
    """Skip obvious other-program admission chunks when a selected Program exists."""
    if not selected_program_names:
        return False
    text = chunk_text(chunk)
    if any(name and name in text for name in selected_program_names):
        return False
    title = str(chunk.get("title") or "")
    return bool(
        matching.contains_any(title, EVIDENCE_TERMS["admission_title_marker"])
        and not matching.contains_any(title, EVIDENCE_TERMS["general_criteria_title"])
    )


CHUNK_FILTER_RULES = (
    ChunkFilterRule(intent="scholarship", required_evidence_terms="scholarship_text", terminal=True),
    ChunkFilterRule(any_intents=("sports_service", "sports_facility"), required_evidence_terms="sports_text", terminal=True),
    ChunkFilterRule(intent="housing_location", not_intents=("parking",), custom=skip_parking_only_chunk),
    ChunkFilterRule(intent="admission", custom=skip_admission_noise_chunk),
    ChunkFilterRule(intent="required_course", custom=skip_required_course_noise_chunk),
    ChunkFilterRule(intent="degree_structure", custom=skip_degree_structure_noise_chunk),
    ChunkFilterRule(intent="housing_price", not_intents=("parking",), custom=skip_parking_only_chunk),
    ChunkFilterRule(intent="parking_location", custom=skip_non_location_parking_chunk),
    ChunkFilterRule(intent="total_credits", required_evidence_terms="total_credits_text"),
)


@dataclass(frozen=True)
class ChunkScoreRule:
    """One additive chunk scoring rule."""

    intent: str
    delta: float
    evidence_terms: str | None = None
    question_terms: str | None = None
    custom: Callable[[ChunkContext], bool] | None = None

    def applies(self, profile: qp.QuestionProfile) -> bool:
        """Return true when this rule applies to the question profile."""
        return profile.has(self.intent)

    def matches(self, context: ChunkContext) -> bool:
        """Return true when the chunk text matches this scoring rule."""
        if self.custom:
            return self.custom(context)
        if self.evidence_terms:
            return matching.contains_any(context.text, EVIDENCE_TERMS[self.evidence_terms])
        if self.question_terms:
            return matching.contains_any(context.text, QUESTION_TERMS[self.question_terms])
        return False


def score_chunk(context: ChunkContext, reason: str) -> float:
    """Score a chunk by source, RRF, selected program match, rules, and lexical overlap."""
    score = BASE_REASON_SCORES.get(reason, 0.0)
    if context.rrf_chunk:
        score += 1.0 + float(context.rrf_chunk.get("rrf_score") or 0.0)
    if context.selected_program_names and any(name and name in context.text for name in context.selected_program_names):
        score += 1.0
    for rule in CHUNK_SCORE_RULES:
        if rule.applies(context.profile) and rule.matches(context):
            score += rule.delta
    return score + lexical_overlap(context.question, context.text)


def has_required_course_core(context: ChunkContext) -> bool:
    """Return true when chunk text looks like required-course core evidence."""
    return matching.contains_any(context.text, EVIDENCE_TERMS["required_course_core"]) or (
        matching.contains_any(context.text, EVIDENCE_TERMS["total_credits_text"]) and context.text.count("-") >= 4
    )


def has_required_course_elective_noise(context: ChunkContext) -> bool:
    """Return true when elective chunks should be penalized for required-course questions."""
    return matching.contains_any(context.text, EVIDENCE_TERMS["required_course_elective"]) and not matching.contains_any(
        context.text,
        EVIDENCE_TERMS["required_course_core"],
    )


CHUNK_SCORE_RULES = (
    ChunkScoreRule("course", 2.0, evidence_terms="course_curriculum"),
    ChunkScoreRule("scholarship", 3.0, evidence_terms="scholarship_text"),
    ChunkScoreRule("scholarship", 1.5, evidence_terms="scholarship_criteria_text"),
    ChunkScoreRule("document_submission", 3.5, evidence_terms="document_evidence"),
    ChunkScoreRule("document_submission", 1.0, evidence_terms="document_context"),
    ChunkScoreRule("required_course", 2.0, custom=has_required_course_core),
    ChunkScoreRule("required_course", -2.0, custom=has_required_course_elective_noise),
    ChunkScoreRule("degree_structure", 4.0, question_terms="degree_structure"),
    ChunkScoreRule("degree_structure", -1.5, evidence_terms="degree_structure_payment_noise"),
)


def lexical_overlap(question: str, text: str) -> float:
    """Return a tiny lexical-overlap score for chunk ordering."""
    query_terms = {term for term in re.findall(r"[\w\u0590-\u05ff]+", question or "") if len(term) > 2}
    text_terms = set(re.findall(r"[\w\u0590-\u05ff]+", text or ""))
    return min(len(query_terms & text_terms) * 0.1, 1.0)


def chunk_text(chunk: dict) -> str:
    """Return the searchable chunk title and text."""
    return " ".join(str(chunk.get(key) or "") for key in ["title", "section_heading", "text"])
