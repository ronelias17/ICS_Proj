from __future__ import annotations

from graphrag.clients.embeddings import EmbeddingClient
from graphrag.clients.neo4j import Neo4jReadClient
from graphrag.config.settings import GraphRagSettings
from graphrag.retrievers import neo4j_search


class NodeRetriever:
    """Retrieve one configured node type with vector and full-text search."""

    def __init__(
        self,
        settings: GraphRagSettings,
        neo4j_client: Neo4jReadClient,
        embeddings: EmbeddingClient,
        search_target: neo4j_search.SearchTarget,
    ):
        """Create a node retriever from settings, clients, and a search target."""
        self.settings = settings
        self.neo4j_client = neo4j_client
        self.embeddings = embeddings
        self.search_target = search_target

    def vector_search(self, embedding: list[float] | None) -> tuple[list[dict], str]:
        """Search the configured vector index when an embedding is available."""
        return neo4j_search.vector_search(self.neo4j_client, self.search_target, embedding)

    def lexical_search(self, question: str) -> tuple[list[dict], str]:
        """Search the configured full-text index."""
        return neo4j_search.lexical_search(self.neo4j_client, self.search_target, question)


def chunk_search_target(settings: GraphRagSettings) -> neo4j_search.SearchTarget:
    """Build the Neo4j search target for chunk retrieval."""
    return neo4j_search.SearchTarget(
        label="Chunk",
        vector_index=settings.chunk_vector_index,
        fulltext_index="chunk_text_fulltext",
        top_k=settings.top_k_chunks,
        projection="""
            node.id AS id,
            coalesce(node.display_title, node.page_title, node.title, "") AS title,
            coalesce(node.section_heading, "") AS section_heading,
            coalesce(node.text, "") AS text
        """.strip(),
    )


def entity_search_target(settings: GraphRagSettings) -> neo4j_search.SearchTarget:
    """Build the Neo4j search target for entity retrieval."""
    return neo4j_search.SearchTarget(
        label="Entity",
        vector_index=settings.entity_vector_index,
        fulltext_index="entity_text_fulltext",
        top_k=settings.top_k_entities,
        projection="""
            node.id AS id,
            labels(node) AS labels,
            node.name AS name,
            node.description AS description
        """.strip(),
    )
