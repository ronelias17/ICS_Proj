from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from repositories.question_records import FALLBACK_ANSWER
from graphrag.config.answer_messages import SERVICE_UNAVAILABLE_ANSWER
from schemas.chat_schemas import AskRequest, AskResponse


router = APIRouter(prefix="/api", tags=["questions"])
LOGGER = logging.getLogger("ics.backend.ask")


@router.post("/ask", response_model=AskResponse)
async def ask_question(payload: AskRequest, request: Request) -> AskResponse:
    """Run GraphRAG for one visitor question."""
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    records = request.app.state.question_records
    graphrag = request.app.state.graphrag_service

    insert_task = asyncio.create_task(records.create_running_record(question))
    record_id = ""

    try:
        record_id = await insert_task
        async with request.app.state.graphrag_semaphore:
            record = await asyncio.to_thread(graphrag.ask, question)
        await records.complete_record(record_id, record)
        if record.get("error"):
            return JSONResponse(
                status_code=503,
                content={
                    "id": record_id,
                    "answer": record.get("answer") or SERVICE_UNAVAILABLE_ANSWER,
                },
            )
        return AskResponse(id=record_id, answer=record.get("answer", FALLBACK_ANSWER))
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        if record_id:
            await records.fail_record(record_id, error)
            return JSONResponse(
                status_code=503,
                content={
                    "id": record_id,
                    "answer": SERVICE_UNAVAILABLE_ANSWER,
                },
            )
        LOGGER.exception("Could not create a question record.")
        raise HTTPException(
            status_code=500,
            detail="Service is temporarily unavailable.",
        ) from exc
