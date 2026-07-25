from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

from graphrag.config.settings import GraphRagSettings


@dataclass
class LlmResponse:
    """Structured result returned by the local chat-completions client."""

    content: str
    error: str = ""
    finish_reason: str = ""


def chat_messages(system_prompt: str, user_prompt: str) -> list[dict[str, str]]:
    """Build the chat message shape expected by the local LLM endpoint."""
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


class LocalChatClient:
    """Small OpenAI-compatible client for llama.cpp chat completions."""

    def __init__(self, settings: GraphRagSettings):
        """Create a chat client from runtime settings."""
        self.settings = settings

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float = 0.0,
        llm_request_attempts: int | None = None,
    ) -> LlmResponse:
        """Call the local LLM and return generated content."""
        attempts = llm_request_attempts if llm_request_attempts is not None else self.settings.answer_retries
        attempts = max(1, attempts)
        last_error = ""
        for attempt in range(1, attempts + 1):
            try:
                payload = self.build_payload(messages, max_tokens=max_tokens, temperature=temperature)
                response = requests.post(
                    self.settings.answer_llm_url,
                    json=payload,
                    timeout=self.settings.request_timeout,
                )
                return self.parse_response(response)
            except Exception as exc:  # pragma: no cover - depends on local services.
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < attempts:
                    time.sleep(1.0)
        return LlmResponse(
            content="",
            error=last_error,
        )

    def build_payload(self, messages: list[dict[str, str]], *, max_tokens: int, temperature: float) -> dict[str, Any]:
        """Build the OpenAI-compatible chat-completions payload."""
        return {
            "model": self.settings.answer_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "reasoning_budget": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }

    def parse_response(self, response: requests.Response) -> LlmResponse:
        """Parse a local chat-completions response."""
        raw = response.json() if response.content else {}
        response.raise_for_status()
        choice = (raw.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = (message.get("content") or "").strip()
        return LlmResponse(
            content=content,
            finish_reason=str(choice.get("finish_reason") or ""),
        )
