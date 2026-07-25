from __future__ import annotations

from dataclasses import dataclass

import requests

from graphrag.config.settings import GraphRagSettings


@dataclass
class EmbeddingResult:
    """Embedding result from the local embedding server."""

    embeddings: list[list[float]]
    error: str = ""


class EmbeddingClient:
    """OpenAI-compatible embedding client for the local embedding server."""

    def __init__(self, settings: GraphRagSettings):
        """Create an embedding client from runtime settings."""
        self.settings = settings

    def embed(self, texts: list[str]) -> EmbeddingResult:
        """Embed a batch of texts and validate response shape."""
        try:
            response = requests.post(
                self.settings.embedding_url,
                json={"model": self.settings.embedding_model, "input": texts},
                timeout=self.settings.request_timeout,
            )
            response.raise_for_status()
            raw = response.json()
            data = sorted(raw.get("data", []), key=lambda item: item.get("index", 0))
            embeddings = [item.get("embedding") for item in data]
            if len(embeddings) != len(texts):
                raise RuntimeError(f"Embedding count mismatch: expected {len(texts)}, got {len(embeddings)}.")
            return EmbeddingResult(embeddings=embeddings)
        except Exception as exc:  # pragma: no cover - depends on local services.
            return EmbeddingResult(embeddings=[], error=str(exc))
