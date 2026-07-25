from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GraphRagSettings:
    """Runtime settings for the GraphRAG sidecar."""

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j"
    neo4j_database: str = "neo4j"
    embedding_url: str = "http://localhost:8081/v1/embeddings"
    embedding_model: str = "embeddinggemma-300M-Q8_0"
    answer_llm_url: str = "http://localhost:8080/v1/chat/completions"
    answer_model: str = "local-model"
    cypher_max_tokens: int = 250
    answer_max_tokens: int = 350
    request_timeout: int = 60
    answer_retries: int = 2
    chunk_vector_index: str = "chunk_embedding_index"
    entity_vector_index: str = "entity_embedding_index"
    top_k_chunks: int = 5
    top_k_entities: int = 8
