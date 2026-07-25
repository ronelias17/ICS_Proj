from __future__ import annotations

import time
from datetime import datetime, timezone

from core.settings import AppSettings
from graphrag.clients.embeddings import EmbeddingClient
from graphrag.clients.llm import LocalChatClient
from graphrag.clients.neo4j import Neo4jClient
from graphrag.llm_tasks.answer_generator import AnswerGenerator
from graphrag.llm_tasks.cypher_generator import CypherGenerator
from graphrag.retrievers.cypher_retriever import CypherRetriever
from graphrag.retrievers.hybrid_retriever import HybridRetriever
from graphrag.retrievers.node_retriever import NodeRetriever
from graphrag.retrievers.node_retriever import chunk_search_target
from graphrag.retrievers.node_retriever import entity_search_target
from services.question_record_builder import build_question_record


class GraphRagService:
    """App-facing wrapper around the GraphRAG engine."""

    def __init__(self, settings: AppSettings):
        graph_settings = settings.to_graphrag_settings()
        neo4j = Neo4jClient(graph_settings)
        llm = LocalChatClient(graph_settings)
        embeddings = EmbeddingClient(graph_settings)
        cypher_generator = CypherGenerator(graph_settings, llm)
        graph = CypherRetriever(neo4j, cypher_generator)
        chunks = NodeRetriever(graph_settings, neo4j, embeddings, chunk_search_target(graph_settings))
        entities = NodeRetriever(graph_settings, neo4j, embeddings, entity_search_target(graph_settings))
        self.neo4j = neo4j
        self.retriever = HybridRetriever(graph, chunks, entities)
        self.answer_generator = AnswerGenerator(graph_settings, llm)

    def ask(self, question: str) -> dict:
        """Run GraphRAG for one question and return an app/Mongo record."""
        started = time.perf_counter()
        retrieval = self.retriever.retrieve(question)
        graph_rows = retrieval.get("graph", {}).get("rows") or []
        chunk_rows = retrieval.get("chunks", {}).get("selected_rows") or retrieval.get("chunks", {}).get("rows") or []
        selected_entities = retrieval.get("selected_entities", {}).get("rows") or []
        answer_result = self.answer_generator.answer(
            question,
            graph_rows,
            chunk_rows,
            selected_entities=selected_entities,
        )
        return build_question_record(
            question=question,
            retrieval=retrieval,
            answer_result=answer_result,
            elapsed_seconds=time.perf_counter() - started,
            created_at=datetime.now(timezone.utc),
        )
