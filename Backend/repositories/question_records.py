from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from graphrag.config.answer_messages import NO_EVIDENCE_FALLBACK_ANSWER
from graphrag.config.answer_messages import SERVICE_UNAVAILABLE_ANSWER


FALLBACK_ANSWER = NO_EVIDENCE_FALLBACK_ANSWER


class QuestionRecordsRepository:
    """Mongo persistence for asked questions and their answers."""

    def __init__(self, database: AsyncIOMotorDatabase, collection_name: str):
        self.collection = database[collection_name]

    async def create_running_record(self, question: str) -> str:
        """Create the initial question record and return its Mongo id."""
        now = datetime.now(timezone.utc)
        result = await self.collection.insert_one(
            {
                "question": question,
                "answer": None,
                "status": "running",
                "feedback_positive": None,
                "created_at": now,
                "completed_at": None,
                "elapsed_ms": None,
                "retrieval_elapsed_ms": None,
                "answer_elapsed_ms": None,
                "error": None,
                "evidence": None,
                "debug": None,
            }
        )
        return str(result.inserted_id)

    async def complete_record(self, record_id: str, record: dict[str, Any]) -> None:
        """Save the finished GraphRAG record."""
        status = "completed" if record.get("status") == "ok" else "failed"
        await self.collection.update_one(
            {"_id": ObjectId(record_id)},
            {
                "$set": {
                    "answer": record.get("answer", ""),
                    "status": status,
                    "completed_at": datetime.now(timezone.utc),
                    "elapsed_ms": record.get("elapsed_ms"),
                    "retrieval_elapsed_ms": record.get("retrieval_elapsed_ms"),
                    "answer_elapsed_ms": record.get("answer_elapsed_ms"),
                    "error": record.get("error"),
                    "evidence": record.get("evidence"),
                    "debug": record.get("debug"),
                }
            },
        )

    async def fail_record(self, record_id: str, error: str, answer: str = SERVICE_UNAVAILABLE_ANSWER) -> None:
        """Mark a question record as failed."""
        await self.collection.update_one(
            {"_id": ObjectId(record_id)},
            {
                "$set": {
                    "answer": answer,
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc),
                    "error": error,
                }
            },
        )

    async def set_feedback(self, record_id: str, feedback_positive: bool) -> bool:
        """Update answer feedback."""
        result = await self.collection.update_one(
            {"_id": ObjectId(record_id)},
            {
                "$set": {
                    "feedback_positive": feedback_positive,
                    "feedback_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.matched_count == 1
