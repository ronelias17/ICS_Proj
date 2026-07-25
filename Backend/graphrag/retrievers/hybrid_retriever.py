from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from graphrag.clients.embeddings import EmbeddingResult
from graphrag.context.chunks import select_source_chunks
from graphrag.context.entities import fetch_selected_entities
from graphrag.retrievers import neo4j_search
from graphrag.retrievers.exact_anchors import boost_exact_entity_anchors
from graphrag.retrievers.cypher_retriever import CypherRetriever
from graphrag.retrievers.node_retriever import NodeRetriever


class HybridRetriever:
    """Run entity hints, graph retrieval, and chunk retrieval in a compact flow."""

    def __init__(self, cypher_retriever: CypherRetriever, chunk_retriever: NodeRetriever, entity_retriever: NodeRetriever):
        """Create the hybrid retriever."""
        self.cypher_retriever = cypher_retriever
        self.chunk_retriever = chunk_retriever
        self.entity_retriever = entity_retriever
        self.embeddings = entity_retriever.embeddings

    def retrieve(self, question: str) -> dict:
        """Return entity candidates, graph rows, and chunk support rows."""
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=5) as executor:
            embedding_future = executor.submit(self.embeddings.embed, [question])
            entity_lexical_future = executor.submit(self.entity_retriever.lexical_search, question)
            chunk_lexical_future = executor.submit(self.chunk_retriever.lexical_search, question)

            embedding_result = embedding_result_or_empty(embedding_future)
            embedding = embedding_result.embeddings[0] if embedding_result.embeddings else None
            entity_vector_future = executor.submit(self.entity_retriever.vector_search, embedding)
            chunk_vector_future = executor.submit(self.chunk_retriever.vector_search, embedding)

            entity_vector_rows, entity_vector_error = lane_result(entity_vector_future)
            entity_lexical_rows, entity_lexical_error = lane_result(entity_lexical_future)
            entity_errors = [error for error in [embedding_result.error, entity_vector_error, entity_lexical_error] if error]
            entity_rows = boost_exact_entity_anchors(
                question,
                neo4j_search.merge_ranked_rows(entity_vector_rows, entity_lexical_rows, self.entity_retriever.settings.top_k_entities),
                self.entity_retriever.settings.top_k_entities,
            )
            entities = {
                "rows": entity_rows,
                "error": " | ".join(entity_errors),
            }

            graph_future = executor.submit(
                self.cypher_retriever.retrieve,
                question,
                entity_candidates=entities.get("rows") or [],
            )

            chunk_vector_rows, chunk_vector_error = lane_result(chunk_vector_future)
            chunk_lexical_rows, chunk_lexical_error = lane_result(chunk_lexical_future)
            chunk_errors = [error for error in [embedding_result.error, chunk_vector_error, chunk_lexical_error] if error]
            chunks = {
                "rows": neo4j_search.merge_ranked_rows(chunk_vector_rows, chunk_lexical_rows, self.chunk_retriever.settings.top_k_chunks),
                "error": " | ".join(chunk_errors),
            }

            try:
                graph = graph_future.result()
            except Exception as exc:
                graph = {
                    "generated_cypher": "",
                    "guard": {"ok": False, "reason": "graph_retrieval_exception"},
                    "rows": [],
                    "error": f"{type(exc).__name__}: {exc}",
                }

        try:
            selected_entities = fetch_selected_entities(
                self.cypher_retriever.neo4j_client,
                question,
                graph.get("rows") or [],
                entities.get("rows") or [],
            )
            chunks["selected_rows"] = select_source_chunks(
                self.cypher_retriever.neo4j_client,
                question,
                graph.get("rows") or [],
                selected_entities,
                chunks.get("rows") or [],
            )
        except Exception as exc:
            chunks["selected_rows"] = chunks.get("rows") or []
            chunks["selection_error"] = f"{type(exc).__name__}: {exc}"
            selected_entities = []
        return {
            "entities": entities,
            "graph": graph,
            "chunks": chunks,
            "selected_entities": {"rows": selected_entities},
            "elapsed_seconds": time.perf_counter() - started,
        }


def lane_result(future) -> tuple[list[dict], str]:
    """Return parallel search rows/errors without crashing retrieval."""
    try:
        return future.result()
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


def embedding_result_or_empty(future) -> EmbeddingResult:
    """Return an embedding result, or an empty result if the future failed."""
    try:
        return future.result()
    except Exception as exc:
        return EmbeddingResult(
            embeddings=[],
            error=f"embedding:{type(exc).__name__}: {exc}",
        )
