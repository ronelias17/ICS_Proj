from __future__ import annotations

import re
from typing import Any, Protocol

from graphrag.config.settings import GraphRagSettings

try:
    from neo4j import GraphDatabase
except Exception:  # pragma: no cover - optional runtime dependency.
    GraphDatabase = None


WRITE_TOKENS = {"CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "DROP", "LOAD"}


class Neo4jReadClient(Protocol):
    """Shared read-client interface used by retrievers."""

    def run_rows(self, statement: str, parameters: dict | None = None) -> list[dict]:
        """Run a read query and return dictionaries."""
        ...


class Neo4jClient:
    """Read-only Neo4j Bolt client with connection pooling."""

    _drivers: dict[tuple[str, str, str], Any] = {}

    def __init__(self, settings: GraphRagSettings):
        """Create a Neo4j driver client from settings."""
        if GraphDatabase is None:
            raise RuntimeError("neo4j Python driver is not installed.")
        self.settings = settings
        key = (settings.neo4j_uri, settings.neo4j_user, settings.neo4j_database)
        driver = self._drivers.get(key)
        if driver is None:
            driver_kwargs = {
                "auth": (settings.neo4j_user, settings.neo4j_password),
                "max_connection_pool_size": 10,
            }
            try:
                driver = GraphDatabase.driver(settings.neo4j_uri, notifications_min_severity="OFF", **driver_kwargs)
            except TypeError:
                driver = GraphDatabase.driver(settings.neo4j_uri, **driver_kwargs)
            driver.verify_connectivity()
            self._drivers[key] = driver
        self.driver = driver

    def run_rows(self, statement: str, parameters: dict | None = None) -> list[dict]:
        """Run a read-only Cypher query and return plain dictionaries."""
        if looks_like_write(statement):
            raise ValueError("Neo4jClient is read-only for GraphRAG.")
        with self.driver.session(database=self.settings.neo4j_database) as session:
            result = session.run(statement, parameters or {})
            keys = result.keys()
            return [{key: plain_value(record.get(key)) for key in keys} for record in result]


def looks_like_write(statement: str) -> bool:
    """Return true if a Cypher statement appears to mutate the graph."""
    tokens = re.findall(r"[A-Za-z_]+", statement.upper())
    if "CALL" in tokens and ("DBMS" in tokens or "APOC" in tokens):
        return True
    return any(token in WRITE_TOKENS for token in tokens)


def plain_value(value):
    """Convert Neo4j values into JSON-serializable Python values."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [plain_value(item) for item in value]
    if hasattr(value, "items"):
        return {key: plain_value(child) for key, child in value.items()}
    return str(value)
