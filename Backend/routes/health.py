from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

from fastapi import APIRouter, Request
import requests

from schemas.chat_schemas import HealthError, HealthResponse


router = APIRouter(prefix="/api", tags=["health"])
HTTP_HEALTH_TIMEOUT_SECONDS = 2.0


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Check backend dependencies used by GraphRAG."""
    checks: dict[str, bool] = {}
    errors: list[HealthError] = []

    try:
        await request.app.state.mongo.ping()
        checks["mongo"] = True
    except Exception as exc:
        checks["mongo"] = False
        errors.append(HealthError(service="mongo", message=f"{type(exc).__name__}: {exc}"))

    try:
        rows = await asyncio.to_thread(request.app.state.graphrag_service.neo4j.run_rows, "RETURN 1 AS ok")
        checks["neo4j"] = bool(rows and rows[0].get("ok") == 1)
        if not checks["neo4j"]:
            errors.append(HealthError(service="neo4j", message="Unexpected Neo4j health response."))
    except Exception as exc:
        checks["neo4j"] = False
        errors.append(HealthError(service="neo4j", message=f"{type(exc).__name__}: {exc}"))

    settings = request.app.state.settings
    checks["llama_chat"] = await check_llama_health("llama_chat", settings.llm_endpoint, errors)
    checks["llama_embed"] = await check_llama_health("llama_embed", settings.embedding_endpoint, errors)

    return HealthResponse(
        ok=all(checks.values()),
        mongo=checks.get("mongo", False),
        neo4j=checks.get("neo4j", False),
        llama_chat=checks.get("llama_chat", False),
        llama_embed=checks.get("llama_embed", False),
        errors=errors,
    )


async def check_llama_health(service: str, endpoint: str, errors: list[HealthError]) -> bool:
    """Return true when a llama.cpp server health endpoint is reachable."""
    health_url = llama_health_url(endpoint)
    try:
        response = await asyncio.to_thread(requests.get, health_url, timeout=HTTP_HEALTH_TIMEOUT_SECONDS)
    except Exception as exc:
        errors.append(HealthError(service=service, message=f"{type(exc).__name__}: {exc}"))
        return False
    if 200 <= response.status_code < 300:
        return True
    message = response.text.strip()[:200] or f"HTTP {response.status_code}"
    errors.append(HealthError(service=service, message=message))
    return False


def llama_health_url(endpoint: str) -> str:
    """Build the llama.cpp /health URL from an OpenAI-compatible API endpoint."""
    parsed = urlsplit(endpoint)
    return f"{parsed.scheme}://{parsed.netloc}/health"
