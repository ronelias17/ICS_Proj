from __future__ import annotations

from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Request

from schemas.chat_schemas import FeedbackRequest, FeedbackResponse


router = APIRouter(prefix="/api", tags=["feedback"])


@router.post("/feedback", response_model=FeedbackResponse)
async def update_feedback(payload: FeedbackRequest, request: Request) -> FeedbackResponse:
    """Save answer feedback."""
    records = request.app.state.question_records
    try:
        ok = await records.set_feedback(payload.id, payload.feedback_positive)
    except InvalidId as exc:
        raise HTTPException(status_code=400, detail="Invalid feedback id.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not save feedback: {type(exc).__name__}.") from exc
    if not ok:
        raise HTTPException(status_code=404, detail="Question record not found.")
    return FeedbackResponse(ok=True)
