"""
Neo4j graph population.

Imports the local graph.json file into Neo4j and optionally stores llama.cpp
embeddings for Chunk and Entity nodes.

The importer is intentionally idempotent:
- nodes are upserted by stable id
- relationships are merged by (from, type, to)
- no existing data is deleted
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests


SCRIPT_DIR = Path(__file__).resolve().parent

# Quick-edit defaults for portable use. CLI arguments can still override these.
DEFAULT_GRAPH_FILE = SCRIPT_DIR / "graph.json"
DEFAULT_CACHE_FILE = SCRIPT_DIR / "index_cache.jsonl"

# Leave empty to use http://localhost:7474/db/{DEFAULT_NEO4J_DB}/tx/commit.
# For a remote Neo4j HTTP port, set the full endpoint here.
DEFAULT_NEO4J_HTTP_URL = "http://localhost:7474/db/neo4j/tx/commit"
DEFAULT_NEO4J_DB = "neo4j"
DEFAULT_NEO4J_USER = "neo4j"
DEFAULT_NEO4J_PASSWORD = ""

DEFAULT_EMBEDDING_URL = "http://localhost:8081/v1/embeddings"
DEFAULT_EMBEDDING_MODEL = "embeddinggemma-300M-Q8_0"
DEFAULT_EMBEDDING_DIMENSIONS = 768
DEFAULT_EMBED_TARGETS = "chunks,entities"

DEFAULT_BATCH_SIZE = 500
DEFAULT_EMBEDDING_BATCH_SIZE = 100
DEFAULT_EMBEDDING_MAX_CHARS = 600
DEFAULT_EMBEDDING_RETRIES = 2
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120

DEFAULT_DRY_RUN = False
DEFAULT_SKIP_EMBEDDINGS = False
DEFAULT_EMBEDDINGS_ONLY = False
DEFAULT_TEST_EMBEDDING = False
DEFAULT_TEST_NEO4J = False

SUPPORTED_EMBED_TARGETS = {"chunks", "entities"}


@dataclass(frozen=True)
class PopulateSettings:
    graph_file: Path
    neo4j_http_url: str
    neo4j_db: str
    neo4j_user: str
    neo4j_password: str
    embedding_url: str
    embedding_model: str
    embedding_dimensions: int
    embed_targets: str
    batch_size: int
    embedding_batch_size: int
    embedding_max_chars: int
    embedding_retries: int
    embedding_cache_file: Path
    request_timeout: int
    dry_run: bool
    skip_embeddings: bool
    embeddings_only: bool
    test_embedding: bool
    test_neo4j: bool


def parse_args() -> PopulateSettings:
    parser = argparse.ArgumentParser(description="Populate Neo4j from the portable GraphRAG graph folder.")
    parser.add_argument("--graph-file", default=str(DEFAULT_GRAPH_FILE))
    parser.add_argument("--neo4j-http-url", default=DEFAULT_NEO4J_HTTP_URL)
    parser.add_argument("--neo4j-db", default=DEFAULT_NEO4J_DB)
    parser.add_argument("--neo4j-user", default=DEFAULT_NEO4J_USER)
    parser.add_argument("--neo4j-password", default=DEFAULT_NEO4J_PASSWORD)
    parser.add_argument("--embedding-url", default=DEFAULT_EMBEDDING_URL)
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--embedding-dimensions", type=int, default=DEFAULT_EMBEDDING_DIMENSIONS)
    parser.add_argument("--embed-targets", default=DEFAULT_EMBED_TARGETS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--embedding-batch-size", type=int, default=DEFAULT_EMBEDDING_BATCH_SIZE)
    parser.add_argument("--embedding-max-chars", type=int, default=DEFAULT_EMBEDDING_MAX_CHARS)
    parser.add_argument("--embedding-retries", type=int, default=DEFAULT_EMBEDDING_RETRIES)
    parser.add_argument("--embedding-cache-file", default=str(DEFAULT_CACHE_FILE))
    parser.add_argument("--request-timeout", type=int, default=DEFAULT_REQUEST_TIMEOUT_SECONDS)
    parser.add_argument("--dry-run", action="store_true", default=DEFAULT_DRY_RUN, help="Validate graph and print plan without writing to Neo4j.")
    parser.add_argument("--skip-embeddings", action="store_true", default=DEFAULT_SKIP_EMBEDDINGS, help="Import graph structure without embeddings/vector indexes.")
    parser.add_argument("--embeddings-only", action="store_true", default=DEFAULT_EMBEDDINGS_ONLY, help="Only create vector indexes and populate embeddings.")
    parser.add_argument("--test-embedding", action="store_true", default=DEFAULT_TEST_EMBEDDING, help="Call the embedding endpoint once and exit.")
    parser.add_argument("--test-neo4j", action="store_true", default=DEFAULT_TEST_NEO4J, help="Run RETURN 1 against Neo4j and exit.")
    args = parser.parse_args()
    return PopulateSettings(
        graph_file=Path(args.graph_file),
        neo4j_http_url=args.neo4j_http_url,
        neo4j_db=args.neo4j_db,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        embedding_url=args.embedding_url,
        embedding_model=args.embedding_model,
        embedding_dimensions=args.embedding_dimensions,
        embed_targets=args.embed_targets,
        batch_size=args.batch_size,
        embedding_batch_size=args.embedding_batch_size,
        embedding_max_chars=args.embedding_max_chars,
        embedding_retries=args.embedding_retries,
        embedding_cache_file=Path(args.embedding_cache_file),
        request_timeout=args.request_timeout,
        dry_run=args.dry_run,
        skip_embeddings=args.skip_embeddings,
        embeddings_only=args.embeddings_only,
        test_embedding=args.test_embedding,
        test_neo4j=args.test_neo4j,
    )


def batched(items: list[dict], size: int) -> Iterable[list[dict]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def stable_hash(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def text_hash(text: str, model: str) -> str:
    return hashlib.sha256(f"{model}\n{text}".encode("utf-8")).hexdigest()


def normalize_embedding_text(text: str, max_chars: int) -> tuple[str, bool]:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if max_chars <= 0 or len(normalized) <= max_chars:
        return normalized, False
    truncated = normalized[:max_chars].rsplit(" ", 1)[0].strip()
    return (truncated or normalized[:max_chars].strip()), True


def sanitize_token(token: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]", "_", str(token or ""))
    token = re.sub(r"_+", "_", token).strip("_")
    if not token:
        return "Unknown"
    if token[0].isdigit():
        token = f"_{token}"
    return token


def sanitize_label(label: str) -> str:
    return sanitize_token(label)


def sanitize_rel_type(rel_type: str) -> str:
    return sanitize_token(rel_type).upper()


def sanitize_property_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        clean_values = []
        for item in value:
            clean_item = sanitize_property_value(item)
            if clean_item is None:
                continue
            if isinstance(clean_item, (str, int, float, bool)):
                clean_values.append(clean_item)
            else:
                clean_values.append(json.dumps(clean_item, ensure_ascii=False, sort_keys=True))
        return clean_values
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def sanitize_properties(props: dict) -> dict:
    clean = {}
    for key, value in (props or {}).items():
        clean_key = sanitize_token(key)
        clean_value = sanitize_property_value(value)
        if clean_value in (None, "", [], {}):
            continue
        clean[clean_key] = clean_value
    return clean


def load_graph(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Graph file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def entity_rows(nodes: list[dict]) -> dict[tuple[str, ...], list[dict]]:
    grouped: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    for node in nodes:
        labels = tuple(sorted({"Entity"} | {sanitize_label(label) for label in node.get("labels", [])}))
        props = sanitize_properties(node.get("properties", {}))
        if node.get("embedding_text"):
            props.update(sanitize_properties({"embedding_text": node.get("embedding_text", "")}))
        grouped[labels].append({"id": node["id"], "props": props})
    return grouped


def document_rows(documents: list[dict]) -> list[dict]:
    rows = []
    for document in documents:
        props = sanitize_properties(document.get("properties", {}))
        rows.append({"id": document["id"], "props": props})
    return rows


def chunk_rows(chunks: list[dict]) -> list[dict]:
    rows = []
    for chunk in chunks:
        props = sanitize_properties(
            {
                key: value
                for key, value in chunk.items()
                if key not in {"id"}
            }
        )
        rows.append({"id": chunk["id"], "props": props})
    return rows


def relationship_import_key(source_id: str, rel_type: str, target_id: str, props: dict) -> str:
    """Return a stable key so parallel scoped relationships are preserved."""
    payload = {
        "from": source_id,
        "type": rel_type,
        "to": target_id,
        "props": props,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return stable_hash(encoded, 16)


def relationship_rows(relationships: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for rel in relationships:
        rel_type = sanitize_rel_type(rel.get("type", ""))
        props = sanitize_properties(rel.get("properties", {}))
        grouped[rel_type].append(
            {
                "from": rel["from"],
                "to": rel["to"],
                "props": props,
                "import_key": relationship_import_key(rel["from"], rel_type, rel["to"], props),
            }
        )
    return grouped


def semantic_endpoint_collapse_risk(graph: dict) -> dict:
    """Summarize parallel semantic edges that endpoint-only MERGE would collapse."""
    endpoint_counts = Counter(
        (rel.get("from"), rel.get("type"), rel.get("to"))
        for rel in graph.get("relationships", [])
    )
    duplicate_groups = {key: count for key, count in endpoint_counts.items() if count > 1}
    duplicate_type_extras = Counter()
    for (_source_id, rel_type, _target_id), count in duplicate_groups.items():
        duplicate_type_extras[rel_type] += count - 1
    return {
        "semantic_relationships": len(graph.get("relationships", [])),
        "unique_endpoint_groups": len(endpoint_counts),
        "duplicate_endpoint_extra_relationships": sum(count - 1 for count in duplicate_groups.values()),
        "top_duplicate_relationship_types": [
            {"type": rel_type, "extra_relationships": count}
            for rel_type, count in duplicate_type_extras.most_common(10)
        ],
    }


def validate_graph(graph: dict) -> dict:
    documents = graph.get("documents", [])
    chunks = graph.get("chunks", [])
    nodes = graph.get("nodes", [])
    relationships = graph.get("relationships", [])
    provenance = graph.get("provenance_relationships", [])
    ids = {item["id"] for item in documents + chunks + nodes}
    bad_edges = [
        rel
        for rel in relationships + provenance
        if rel.get("from") not in ids or rel.get("to") not in ids
    ]
    self_loops = [
        rel
        for rel in relationships + provenance
        if rel.get("from") == rel.get("to")
    ]
    duplicate_ids = [node_id for node_id, count in Counter(item["id"] for item in documents + chunks + nodes).items() if count > 1]
    return {
        "documents": len(documents),
        "chunks": len(chunks),
        "entities": len(nodes),
        "semantic_relationships": len(relationships),
        "provenance_relationships": len(provenance),
        "bad_edges": len(bad_edges),
        "self_loops": len(self_loops),
        "duplicate_ids": len(duplicate_ids),
    }


class Neo4jHttpClient:
    def __init__(self, url: str, user: str, password: str, timeout: int = 120):
        self.url = url
        self.auth = (user, password)
        self.timeout = timeout
        self.session = requests.Session()

    def run(self, statement: str, parameters: dict | None = None) -> dict:
        payload = {"statements": [{"statement": statement, "parameters": parameters or {}}]}
        response = self.session.post(self.url, json=payload, auth=self.auth, timeout=self.timeout)
        if response.status_code == 401:
            raise RuntimeError(
                "Neo4j authentication failed. Pass --neo4j-password or configure "
                "NEO4J_PASSWORD for the Docker population job."
            )
        if response.status_code == 404:
            raise RuntimeError(
                f"Neo4j HTTP endpoint was reached, but the database path was not found: {self.url}. "
                "In Neo4j Desktop, the instance name is not the database name. Your screenshot shows "
                "databases named 'neo4j' and 'system', so pass --neo4j-db neo4j or set "
                "DEFAULT_NEO4J_DB."
            )
        response.raise_for_status()
        data = response.json()
        if data.get("errors"):
            raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False, indent=2))
        return data


def neo4j_http_url(settings: PopulateSettings) -> str:
    if settings.neo4j_http_url:
        return settings.neo4j_http_url
    return f"http://localhost:7474/db/{settings.neo4j_db}/tx/commit"


def create_constraints(client: Neo4jHttpClient, dimensions: int, embed_targets: set[str], skip_embeddings: bool) -> None:
    statements = [
        "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (n:Document) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.id IS UNIQUE",
        "CREATE INDEX entity_name IF NOT EXISTS FOR (n:Entity) ON (n.name)",
        "CREATE INDEX document_source_file IF NOT EXISTS FOR (n:Document) ON (n.source_file)",
        "CREATE FULLTEXT INDEX chunk_text_fulltext IF NOT EXISTS "
        "FOR (n:Chunk) ON EACH [n.text, n.title, n.section_heading]",
        "CREATE FULLTEXT INDEX entity_text_fulltext IF NOT EXISTS "
        "FOR (n:Entity) ON EACH [n.name, n.description, n.embedding_text]",
    ]
    if not skip_embeddings:
        if "chunks" in embed_targets:
            statements.append(
                "CREATE VECTOR INDEX chunk_embedding_index IF NOT EXISTS "
                "FOR (c:Chunk) ON (c.embedding) "
                f"OPTIONS {{indexConfig: {{`vector.dimensions`: {dimensions}, `vector.similarity_function`: 'cosine'}}}}"
            )
        if "entities" in embed_targets:
            statements.append(
                "CREATE VECTOR INDEX entity_embedding_index IF NOT EXISTS "
                "FOR (e:Entity) ON (e.embedding) "
                f"OPTIONS {{indexConfig: {{`vector.dimensions`: {dimensions}, `vector.similarity_function`: 'cosine'}}}}"
            )
    for statement in statements:
        client.run(statement)


def upsert_nodes(client: Neo4jHttpClient, label_clause: str, rows: list[dict], batch_size: int, label: str) -> None:
    statement = f"""
    UNWIND $rows AS row
    MERGE (n:{label_clause} {{id: row.id}})
    SET n += row.props
    """
    total = len(rows)
    for index, batch in enumerate(batched(rows, batch_size), start=1):
        client.run(statement, {"rows": batch})
        print(f"  {label}: {min(index * batch_size, total)}/{total}")


def upsert_relationships(client: Neo4jHttpClient, rel_type: str, rows: list[dict], batch_size: int, label: str) -> None:
    statement = f"""
    UNWIND $rows AS row
    MATCH (a {{id: row.from}})
    MATCH (b {{id: row.to}})
    MERGE (a)-[r:{rel_type} {{import_key: row.import_key}}]->(b)
    SET r += row.props
    SET r.import_key = row.import_key
    """
    total = len(rows)
    for index, batch in enumerate(batched(rows, batch_size), start=1):
        client.run(statement, {"rows": batch})
        print(f"  {label} {rel_type}: {min(index * batch_size, total)}/{total}")


def load_embedding_cache(path: Path) -> dict[tuple[str, str], list[float]]:
    cache = {}
    if not path.exists():
        return cache
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        cache[(item["key"], item["hash"])] = item["embedding"]
    return cache


def append_embedding_cache(path: Path, items: list[dict]) -> None:
    if not items:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def embed_batch(url: str, model: str, texts: list[str], timeout: int) -> list[list[float]]:
    response = requests.post(url, json={"model": model, "input": texts}, timeout=timeout)
    if not response.ok:
        body = response.text.strip()
        if len(body) > 1000:
            body = body[:1000] + "..."
        raise RuntimeError(f"Embedding request failed HTTP {response.status_code}: {body}")
    data = response.json()
    embeddings = [item["embedding"] for item in sorted(data.get("data", []), key=lambda item: item.get("index", 0))]
    if len(embeddings) != len(texts):
        raise RuntimeError(f"Embedding endpoint returned {len(embeddings)} embeddings for {len(texts)} texts")
    return embeddings


def embedding_items(graph: dict, targets: set[str], max_chars: int) -> list[dict]:
    items = []
    if "chunks" in targets:
        for chunk in graph.get("chunks", []):
            text, truncated = normalize_embedding_text(str(chunk.get("text", "") or ""), max_chars)
            if text:
                items.append({"id": chunk["id"], "label": "Chunk", "text": text, "truncated": truncated})
    if "entities" in targets:
        for node in graph.get("nodes", []):
            text, truncated = normalize_embedding_text(str(node.get("embedding_text", "") or ""), max_chars)
            if text:
                items.append({"id": node["id"], "label": "Entity", "text": text, "truncated": truncated})
    return items


def embed_batch_with_fallback(
    url: str,
    model: str,
    batch: list[tuple[dict, tuple[str, str], str]],
    timeout: int,
    retries: int,
) -> list[list[float]]:
    texts = [item["text"] for item, _, _ in batch]
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return embed_batch(url, model, texts, timeout)
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1 + attempt)

    if len(batch) > 1:
        midpoint = max(1, len(batch) // 2)
        return embed_batch_with_fallback(url, model, batch[:midpoint], timeout, retries) + embed_batch_with_fallback(
            url,
            model,
            batch[midpoint:],
            timeout,
            retries,
        )

    item = batch[0][0]
    raise RuntimeError(
        f"Embedding failed for {item['label']} {item['id']} after retries and fallback "
        f"(chars={len(item['text'])}, truncated={item.get('truncated', False)}): {last_error}"
    ) from last_error


def store_embedding_rows(client: Neo4jHttpClient, rows: list[dict], batch_size: int) -> None:
    rows_by_label: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        rows_by_label[row["label"]].append({"id": row["id"], "embedding": row["embedding"]})

    for label, label_rows in rows_by_label.items():
        statement = f"""
        UNWIND $rows AS row
        MATCH (n:{label} {{id: row.id}})
        SET n.embedding = row.embedding
        """
        for batch in batched(label_rows, batch_size):
            client.run(statement, {"rows": batch})
        print(f"  stored {label} embeddings: {len(label_rows)}")


def embed_and_store(
    client: Neo4jHttpClient,
    graph: dict,
    settings: PopulateSettings,
    targets: set[str],
) -> None:
    items = embedding_items(graph, targets, settings.embedding_max_chars)
    cache_path = settings.embedding_cache_file
    cache = load_embedding_cache(cache_path)
    new_cache_items = []
    missing = []
    truncated_count = sum(1 for item in items if item.get("truncated"))
    cached_rows = []

    for item in items:
        item_hash = text_hash(item["text"], settings.embedding_model)
        cache_key = (f"{item['label']}:{item['id']}", item_hash)
        embedding = cache.get(cache_key)
        if embedding is None:
            missing.append((item, cache_key, item_hash))
        else:
            cached_rows.append({"id": item["id"], "label": item["label"], "embedding": embedding})

    print(
        f"Embedding cache: {len(cached_rows)} cached, {len(missing)} missing "
        f"(max_chars={settings.embedding_max_chars}, truncated={truncated_count})"
    )
    if cached_rows:
        print("Storing cached vectors...")
        store_embedding_rows(client, cached_rows, settings.batch_size)

    for index, batch in enumerate(batched(missing, settings.embedding_batch_size), start=1):
        embeddings = embed_batch_with_fallback(
            settings.embedding_url,
            settings.embedding_model,
            batch,
            settings.request_timeout,
            settings.embedding_retries,
        )
        batch_rows = []
        for (item, cache_key, item_hash), embedding in zip(batch, embeddings):
            if len(embedding) != settings.embedding_dimensions:
                raise RuntimeError(
                    f"Embedding dimension mismatch for {item['id']}: "
                    f"got {len(embedding)}, expected {settings.embedding_dimensions}"
                )
            row = {"id": item["id"], "label": item["label"], "embedding": embedding}
            batch_rows.append(row)
            new_cache_items.append(
                {
                    "key": cache_key[0],
                    "hash": item_hash,
                    "embedding": embedding,
                }
            )
        store_embedding_rows(client, batch_rows, settings.batch_size)
        append_embedding_cache(cache_path, new_cache_items)
        new_cache_items.clear()
        print(f"  embedded: {min(index * settings.embedding_batch_size, len(missing))}/{len(missing)}")


def parse_embed_targets(value: str) -> set[str]:
    targets = {item.strip().lower() for item in value.split(",") if item.strip()}
    unknown = targets - SUPPORTED_EMBED_TARGETS
    if unknown:
        raise ValueError(f"Unknown embed targets: {sorted(unknown)}")
    return targets


def dry_run(graph: dict, settings: PopulateSettings, targets: set[str]) -> None:
    summary = validate_graph(graph)
    collapse_risk = semantic_endpoint_collapse_risk(graph)
    print("Graph import dry run")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("Semantic endpoint collapse risk")
    print(json.dumps(collapse_risk, ensure_ascii=False, indent=2))
    print(f"Neo4j HTTP URL: {neo4j_http_url(settings)}")
    print(f"Embedding URL: {settings.embedding_url}")
    print(f"Embedding model: {settings.embedding_model}")
    print(f"Embedding dimensions: {settings.embedding_dimensions}")
    print(f"Embedding targets: {sorted(targets)}")
    if settings.skip_embeddings:
        print("Embedding items: 0")
    else:
        items = embedding_items(graph, targets, settings.embedding_max_chars)
        print(f"Embedding items: {len(items)}")
        print(f"Embedding max chars: {settings.embedding_max_chars}")
        print(f"Embedding truncated items: {sum(1 for item in items if item.get('truncated'))}")


def populate(graph: dict, settings: PopulateSettings) -> None:
    targets = parse_embed_targets(settings.embed_targets)
    if settings.skip_embeddings and settings.embeddings_only:
        raise RuntimeError("--skip-embeddings and --embeddings-only cannot be used together")
    if settings.skip_embeddings:
        targets = set()

    if settings.test_embedding:
        embeddings = embed_batch(settings.embedding_url, settings.embedding_model, ["בדיקת embedding קצרה"], settings.request_timeout)
        print(f"Embedding test OK: dimension={len(embeddings[0])}")
        return

    if settings.dry_run:
        dry_run(graph, settings, targets)
        return

    client = Neo4jHttpClient(neo4j_http_url(settings), settings.neo4j_user, settings.neo4j_password, settings.request_timeout)
    if settings.test_neo4j:
        client.run("RETURN 1 AS ok")
        print("Neo4j test OK")
        return

    summary = validate_graph(graph)
    if summary["bad_edges"] or summary["self_loops"] or summary["duplicate_ids"]:
        raise RuntimeError(f"Graph failed validation: {json.dumps(summary, ensure_ascii=False)}")

    start = time.perf_counter()
    print("Creating constraints/indexes...")
    create_constraints(client, settings.embedding_dimensions, targets, settings.skip_embeddings)

    if settings.embeddings_only:
        if not targets:
            raise RuntimeError("--embeddings-only requires at least one embed target")
        print("Embedding-only mode: skipping node and relationship upserts.")
        embed_and_store(client, graph, settings, targets)
        elapsed = time.perf_counter() - start
        print(f"Graph embeddings complete in {elapsed:.1f}s")
        return

    print("Upserting documents...")
    upsert_nodes(client, "Document", document_rows(graph.get("documents", [])), settings.batch_size, "documents")

    print("Upserting chunks...")
    upsert_nodes(client, "Chunk", chunk_rows(graph.get("chunks", [])), settings.batch_size, "chunks")

    print("Upserting entities...")
    for labels, rows in sorted(entity_rows(graph.get("nodes", [])).items()):
        label_clause = ":".join(labels)
        upsert_nodes(client, label_clause, rows, settings.batch_size, f"entities {label_clause}")

    print("Upserting semantic relationships...")
    for rel_type, rows in sorted(relationship_rows(graph.get("relationships", [])).items()):
        upsert_relationships(client, rel_type, rows, settings.batch_size, "semantic")

    print("Upserting provenance relationships...")
    for rel_type, rows in sorted(relationship_rows(graph.get("provenance_relationships", [])).items()):
        upsert_relationships(client, rel_type, rows, settings.batch_size, "provenance")

    if targets:
        print("Embedding and storing vectors...")
        embed_and_store(client, graph, settings, targets)

    elapsed = time.perf_counter() - start
    print(f"Graph import complete in {elapsed:.1f}s")


def main() -> None:
    settings = parse_args()
    graph = load_graph(settings.graph_file)
    populate(graph, settings)


if __name__ == "__main__":
    main()
