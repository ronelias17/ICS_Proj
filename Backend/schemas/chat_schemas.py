from __future__ import annotations

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """Question request from the frontend."""

    question: str = Field(
        min_length=1,
        max_length=1000,
        description="Visitor question",
    )


class AskResponse(BaseModel):
    """Question response returned to the frontend."""

    id: str
    answer: str


class FeedbackRequest(BaseModel):
    """Feedback update request."""

    id: str
    feedback_positive: bool


class FeedbackResponse(BaseModel):
    """Feedback update response."""

    ok: bool


class SuggestionQuestion(BaseModel):
    """One suggested question."""

    id: str
    question: str


class SuggestionsResponse(BaseModel):
    """Suggested questions response."""

    suggestions: list[SuggestionQuestion]


class HealthError(BaseModel):
    """One dependency health error."""

    service: str
    message: str


class HealthResponse(BaseModel):
    """Backend dependency health response."""

    ok: bool
    mongo: bool
    neo4j: bool
    llama_chat: bool
    llama_embed: bool
    errors: list[HealthError] = Field(default_factory=list)
