from __future__ import annotations

from fastapi import APIRouter, Request

from schemas.chat_schemas import SuggestionsResponse


router = APIRouter(prefix="/api", tags=["suggestions"])


@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_suggestions(request: Request) -> SuggestionsResponse:
    """Return suggested questions."""
    suggestions = await request.app.state.suggestions.list_active()
    return SuggestionsResponse(suggestions=suggestions)
