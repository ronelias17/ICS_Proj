from __future__ import annotations

import re
import time

from graphrag.clients.llm import LocalChatClient
from graphrag.clients.llm import chat_messages
from graphrag.config.answer_messages import NO_EVIDENCE_FALLBACK_ANSWER
from graphrag.config.answer_messages import SERVICE_UNAVAILABLE_ANSWER
from graphrag.config.prompts import ANSWER_SYSTEM_PROMPT, ANSWER_USER_TEMPLATE
from graphrag.config.settings import GraphRagSettings
from graphrag.formatting import chunk_excerpts
from graphrag.formatting import entities
from graphrag.formatting import graph_facts


LENGTH_RETRY_INSTRUCTION = (
    "Your previous answer was too long. Answer in no more than two short sentences. "
    "Do not list every item; summarize with examples only."
)
INCOMPLETE_RETRY_INSTRUCTION = (
    "Your previous answer looked incomplete. Answer again in no more than two short sentences and finish cleanly."
)
DANGLING_CONNECTORS = {"ו", "או", "של", "עם", "כמו", "ב", "ל", "מ", "על", "אל", "את"}
FINAL_PUNCTUATION = tuple(".!?…:;\"'׳״”’)")


class AnswerGenerator:
    """Build the final answer prompt and optionally call the local LLM."""

    def __init__(self, settings: GraphRagSettings, llm: LocalChatClient | None = None):
        """Create the answer generator."""
        self.settings = settings
        self.llm = llm or LocalChatClient(settings)

    def build_prompt(
        self,
        question: str,
        graph_rows: list[dict],
        chunks: list[dict],
        selected_entities: list[dict] | None = None,
    ) -> dict:
        """Return clean answer messages and app-record evidence text."""
        clean_selected_entities = entities.format_selected_entities(selected_entities or [])
        clean_graph_facts = graph_facts.format_graph_facts(graph_rows, question=question)
        chunk_limit = chunk_excerpts.chunk_prompt_limit(graph_rows)
        clean_chunk_excerpt_records = chunk_excerpts.format_chunk_excerpt_records(
            chunks,
            limit=chunk_limit,
            question=question,
            selected_entities=selected_entities or [],
        )
        clean_chunk_excerpts = [record["display_text"] for record in clean_chunk_excerpt_records]
        entities_text = "\n".join(clean_selected_entities) if clean_selected_entities else "אין ישויות נבחרות."
        graph_text = "\n".join(clean_graph_facts) if clean_graph_facts else "אין קשרי גרף או עובדות גרף ישירות."
        chunk_text = "\n".join(clean_chunk_excerpts) if clean_chunk_excerpts else "אין קטעי מקור תומכים."
        user_prompt = ANSWER_USER_TEMPLATE.format(
            question=question,
            selected_entities=entities_text,
            graph_rows=graph_text,
            chunks=chunk_text,
        )
        messages = chat_messages(ANSWER_SYSTEM_PROMPT, user_prompt)
        return {
            "messages": messages,
            "clean_selected_entities": clean_selected_entities,
            "clean_graph_facts": clean_graph_facts,
            "clean_chunk_excerpt_records": clean_chunk_excerpt_records,
        }

    def answer(
        self,
        question: str,
        graph_rows: list[dict],
        chunks: list[dict],
        selected_entities: list[dict] | None = None,
    ) -> dict:
        """Call the answer LLM and return app-record fields."""
        started = time.perf_counter()
        prompt = self.build_prompt(question, graph_rows, chunks, selected_entities=selected_entities)
        response = self.llm.complete(
            prompt["messages"],
            max_tokens=self.settings.answer_max_tokens,
            temperature=0.0,
            llm_request_attempts=self.settings.answer_retries,
        )
        incomplete_retry_reason = ""
        if response.finish_reason == "length":
            retry_messages = messages_with_extra_instruction(prompt["messages"], LENGTH_RETRY_INSTRUCTION)
            response = self.llm.complete(
                retry_messages,
                max_tokens=self.settings.answer_max_tokens,
                temperature=0.0,
                llm_request_attempts=self.settings.answer_retries,
            )
        else:
            incomplete_retry_reason = incomplete_answer_reason(response.content)
            if incomplete_retry_reason:
                retry_messages = messages_with_extra_instruction(prompt["messages"], INCOMPLETE_RETRY_INSTRUCTION)
                response = self.llm.complete(
                    retry_messages,
                    max_tokens=self.settings.answer_max_tokens,
                    temperature=0.0,
                    llm_request_attempts=self.settings.answer_retries,
                )
        answer_text = str(response.content or "").strip()
        if not answer_text:
            answer_text = SERVICE_UNAVAILABLE_ANSWER if response.error else NO_EVIDENCE_FALLBACK_ANSWER
        return {
            "answer": answer_text,
            "clean_selected_entities": prompt["clean_selected_entities"],
            "clean_graph_facts": prompt["clean_graph_facts"],
            "clean_chunk_excerpt_records": prompt["clean_chunk_excerpt_records"],
            "error": response.error,
            "elapsed_seconds": time.perf_counter() - started,
        }


def messages_with_extra_instruction(messages: list[dict[str, str]], instruction: str) -> list[dict[str, str]]:
    """Append one retry instruction to the final user message."""
    updated = [dict(message) for message in messages]
    for message in reversed(updated):
        if message.get("role") == "user":
            message["content"] = f"{message.get('content', '')}\n\n{instruction}"
            return updated
    updated.append({"role": "user", "content": instruction})
    return updated


def incomplete_answer_reason(answer: str) -> str:
    """Return a reason when an answer looks visibly cut off."""
    text = (answer or "").strip()
    if not text:
        return ""
    visible = text.rstrip(" \t\r\n\"'׳״”’)")
    if not visible:
        return ""
    tokens = re.findall(r"[\w\u0590-\u05ff]+", visible)
    last_token = tokens[-1] if tokens else ""
    if last_token in DANGLING_CONNECTORS:
        return f"dangling_connector:{last_token}"
    if visible.endswith(FINAL_PUNCTUATION):
        return ""
    if re.fullmatch(r"[A-Za-z\u0590-\u05ff]", last_token or ""):
        return "dangling_single_letter"
    if len(last_token) <= 2 and re.fullmatch(r"[A-Za-z\u0590-\u05ff]+", last_token or "") and len(visible) > 40:
        return f"short_incomplete_token:{last_token}"
    return ""
