from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
import time

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.settings import AppSettings
from db.mongo import MongoClientProvider
from repositories.question_records import QuestionRecordsRepository
from repositories.suggestions import SuggestionsRepository
from routes.ask import router as ask_router
from routes.feedback import router as feedback_router
from routes.health import router as health_router
from routes.suggestions import router as suggestions_router
from services.graphrag_service import GraphRagService


LOGGER = logging.getLogger("ics.backend")
GRAPHRAG_STARTUP_TIMEOUT_SECONDS = 90
GRAPHRAG_STARTUP_RETRY_SECONDS = 2


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create shared backend resources."""
    settings = AppSettings.from_env()
    mongo = MongoClientProvider(settings)
    await mongo.ping()

    app.state.settings = settings
    app.state.mongo = mongo
    app.state.question_records = QuestionRecordsRepository(
        mongo.database,
        settings.question_records_collection,
    )
    app.state.suggestions = SuggestionsRepository(
        mongo.database,
        settings.suggestions_collection,
    )
    app.state.graphrag_semaphore = asyncio.Semaphore(settings.graphrag_max_concurrent_questions)
    app.state.graphrag_service = await asyncio.to_thread(create_graphrag_service_with_retry, settings)

    try:
        yield
    finally:
        mongo.close()


def create_graphrag_service_with_retry(settings: AppSettings) -> GraphRagService:
    """Create GraphRAG once Neo4j is ready to accept Bolt connections."""
    deadline = time.monotonic() + GRAPHRAG_STARTUP_TIMEOUT_SECONDS
    attempt = 0
    while True:
        attempt += 1
        try:
            return GraphRagService(settings)
        except Exception:
            if time.monotonic() >= deadline:
                LOGGER.exception("GraphRAG startup failed after %s attempts.", attempt)
                raise
            LOGGER.info(
                "GraphRAG startup waiting for dependencies; retrying in %s seconds. attempt=%s",
                GRAPHRAG_STARTUP_RETRY_SECONDS,
                attempt,
            )
            time.sleep(GRAPHRAG_STARTUP_RETRY_SECONDS)


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ask_router)
app.include_router(feedback_router)
app.include_router(health_router)
app.include_router(suggestions_router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3033)
