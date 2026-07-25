from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

from graphrag.config.settings import GraphRagSettings


BACKEND_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = BACKEND_ROOT.parent


def env_int(name: str, default: int) -> int:
    """Read an integer environment variable."""
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def mongo_uri_from_env() -> str:
    """Build the internal MongoDB connection URI from shared Docker settings."""
    configured_uri = os.getenv("MONGO_URI")
    if configured_uri:
        return configured_uri

    username = quote_plus(os.getenv("MONGO_ROOT_USERNAME", "admin"))
    password = quote_plus(os.getenv("MONGO_ROOT_PASSWORD", ""))
    return f"mongodb://{username}:{password}@mongodb:27017/?authSource=admin"


@dataclass(frozen=True)
class AppSettings:
    """FastAPI backend runtime settings."""

    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str
    mongo_uri: str
    mongo_db: str
    question_records_collection: str
    suggestions_collection: str
    llm_endpoint: str
    llm_model: str
    embedding_endpoint: str
    embedding_model: str
    graphrag_cypher_max_tokens: int
    graphrag_answer_max_tokens: int
    graphrag_request_timeout: int
    graphrag_answer_retries: int
    graphrag_top_k_chunks: int
    graphrag_top_k_entities: int
    graphrag_max_concurrent_questions: int

    @classmethod
    def from_env(cls) -> "AppSettings":
        """Load shared app settings from the project .env and process environment."""
        load_dotenv(APP_ROOT / ".env", override=False)
        return cls(
            neo4j_uri=os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
            neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
            neo4j_password=os.getenv("NEO4J_PASSWORD", "neo4j"),
            neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
            mongo_uri=mongo_uri_from_env(),
            mongo_db=os.getenv("MONGO_DB", "ics"),
            question_records_collection=os.getenv("MONGO_QUESTION_RECORDS_COLLECTION", "question_records"),
            suggestions_collection=os.getenv("MONGO_SUGGESTIONS_COLLECTION", "suggestions"),
            llm_endpoint=os.getenv("LLM_ENDPOINT", "http://llama-chat:8080/v1/chat/completions"),
            llm_model=os.getenv("LLM_MODEL", "local-model"),
            embedding_endpoint=os.getenv("EMBEDDING_ENDPOINT", "http://llama-embed:8080/v1/embeddings"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "embeddinggemma-300M-Q8_0"),
            graphrag_cypher_max_tokens=env_int("GRAPHRAG_CYPHER_MAX_TOKENS", 250),
            graphrag_answer_max_tokens=env_int("GRAPHRAG_ANSWER_MAX_TOKENS", 350),
            graphrag_request_timeout=env_int("GRAPHRAG_REQUEST_TIMEOUT", 90),
            graphrag_answer_retries=env_int("GRAPHRAG_ANSWER_RETRIES", 2),
            graphrag_top_k_chunks=env_int("GRAPHRAG_TOP_K_CHUNKS", 5),
            graphrag_top_k_entities=env_int("GRAPHRAG_TOP_K_ENTITIES", 8),
            graphrag_max_concurrent_questions=max(1, env_int("GRAPHRAG_MAX_CONCURRENT_QUESTIONS", 1)),
        )

    def to_graphrag_settings(self) -> GraphRagSettings:
        """Convert backend settings into GraphRAG engine settings."""
        return GraphRagSettings(
            neo4j_uri=self.neo4j_uri,
            neo4j_user=self.neo4j_user,
            neo4j_password=self.neo4j_password,
            neo4j_database=self.neo4j_database,
            embedding_url=self.embedding_endpoint,
            embedding_model=self.embedding_model,
            answer_llm_url=self.llm_endpoint,
            answer_model=self.llm_model,
            cypher_max_tokens=self.graphrag_cypher_max_tokens,
            answer_max_tokens=self.graphrag_answer_max_tokens,
            request_timeout=self.graphrag_request_timeout,
            answer_retries=self.graphrag_answer_retries,
            top_k_chunks=self.graphrag_top_k_chunks,
            top_k_entities=self.graphrag_top_k_entities,
        )
