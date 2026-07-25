from __future__ import annotations

import re
from dataclasses import dataclass

from graphrag.clients.neo4j import Neo4jReadClient


@dataclass(frozen=True)
class SearchTarget:
    """Configuration for one Neo4j node-search target."""

    label: str
    vector_index: str
    fulltext_index: str
    top_k: int
    projection: str


def vector_search(
    neo4j_client: Neo4jReadClient,
    target: SearchTarget,
    embedding: list[float] | None,
) -> tuple[list[dict], str]:
    """Run one vector index search for a configured node target."""
    if not embedding:
        return [], ""
    try:
        rows = neo4j_client.run_rows(
            f"""
            CALL db.index.vector.queryNodes($index_name, $top_k, $embedding)
            YIELD node, score
            WHERE node:{target.label}
            RETURN {target.projection},
                   score AS vector_score
            ORDER BY score DESC, id ASC
            LIMIT $top_k
            """,
            {
                "index_name": target.vector_index,
                "top_k": target.top_k,
                "embedding": embedding,
            },
        )
        return rows, ""
    except Exception as exc:
        return [], f"vector:{type(exc).__name__}: {exc}"


def lexical_search(
    neo4j_client: Neo4jReadClient,
    target: SearchTarget,
    question: str,
) -> tuple[list[dict], str]:
    """Run one full-text index search for a configured node target."""
    query = fulltext_query(question)
    if not query:
        return [], ""
    try:
        rows = neo4j_client.run_rows(
            f"""
            CALL db.index.fulltext.queryNodes($index_name, $query)
            YIELD node, score
            WHERE node:{target.label}
            RETURN {target.projection},
                   score AS lexical_score
            ORDER BY lexical_score DESC, id ASC
            LIMIT $top_k
            """,
            {
                "index_name": target.fulltext_index,
                "query": query,
                "top_k": target.top_k,
            },
        )
        return rows, ""
    except Exception as exc:
        return [], f"lexical:{type(exc).__name__}: {exc}"


def merge_ranked_rows(vector_rows: list[dict], lexical_rows: list[dict], top_k: int) -> list[dict]:
    """Merge vector and lexical hits with reciprocal-rank fusion."""
    merged: dict[str, dict] = {}
    rrf_k = 60
    for source, rows, score_key, rank_key in [
        ("vector", vector_rows, "vector_score", "vector_rank"),
        ("lexical", lexical_rows, "lexical_score", "lexical_rank"),
    ]:
        for rank, row in enumerate(rows, start=1):
            row_id = row.get("id")
            if not row_id:
                continue
            item = merged.setdefault(
                row_id,
                {
                    **row,
                    "id": row_id,
                    "vector_score": 0.0,
                    "lexical_score": 0.0,
                    "vector_rank": None,
                    "lexical_rank": None,
                    "rrf_score": 0.0,
                    "retrieval_sources": [],
                },
            )
            for key, value in row.items():
                if item.get(key) in (None, "", []):
                    item[key] = value
            item[score_key] = max(float(item.get(score_key) or 0.0), float(row.get(score_key) or 0.0))
            item[rank_key] = min(rank, item[rank_key]) if item.get(rank_key) else rank
            item["rrf_score"] += 1.0 / (rrf_k + rank)
            if source not in item["retrieval_sources"]:
                item["retrieval_sources"].append(source)
    for item in merged.values():
        item["score"] = item["rrf_score"]
    return sorted(
        merged.values(),
        key=lambda row: (-float(row.get("rrf_score") or 0.0), str(row.get("id") or "")),
    )[:top_k]


def fulltext_query(question: str) -> str:
    """Return a conservative Lucene query for Neo4j full-text search."""
    tokens = re.findall(r"[\w\u0590-\u05ff]+", question or "")
    terms = [token for token in tokens if len(token) > 1]
    return " ".join(terms[:12])
