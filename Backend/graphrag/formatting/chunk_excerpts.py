from __future__ import annotations

import re

from graphrag.lexicon import question_profile as qp
from graphrag.formatting import field_maps
from graphrag.lexicon.formatting_terms import FORMATTING_TERMS
from graphrag.lexicon.matching import contains_any


CHUNK_EXCERPT_CHAR_LIMITS = (550, 450, 350, 300)


def chunk_prompt_limit(graph_rows: list[dict]) -> int:
    """Return the number of support chunks to send with graph facts."""
    if not graph_rows:
        return 4
    return 3


def format_chunk_excerpt_records(
    chunks: list[dict],
    *,
    limit: int,
    question: str = "",
    selected_entities: list[dict] | None = None,
) -> list[dict]:
    """Format chunk excerpts with source IDs for app records."""
    records = []
    selected_program_names = program_names(selected_entities or [])
    chunk_index = 0
    for topic_index, (topic, topic_chunks) in enumerate(group_chunks_by_topic(chunks[:limit]).items(), start=1):
        lines = [f"Topic: {topic or 'Source'}"]
        chunk_ids = []
        for chunk_position, chunk in enumerate(topic_chunks, start=1):
            raw_text = trim_off_scope_admission_rows(
                chunk.get("text") or "",
                question=question,
                selected_program_names=selected_program_names,
            )
            text = compact_text(raw_text, chunk_excerpt_char_limit(chunk_index))
            chunk_index += 1
            if not text:
                continue
            chunk_id = chunk.get("id") or chunk.get("chunk_id")
            if chunk_id:
                chunk_ids.append(str(chunk_id))
            chunk_label = chunk_display_index(chunk, chunk_position)
            lines.append(f"Chunk: {chunk_label}")
            lines.append(f"Text: {text}")
        if len(lines) > 1:
            records.append(
                {
                    "ids": list(dict.fromkeys(chunk_ids)),
                    "display_text": f"{topic_index}. " + "\n   ".join(lines),
                }
            )
    return records


def chunk_excerpt_char_limit(index: int) -> int:
    """Return the text budget for one selected source chunk."""
    return CHUNK_EXCERPT_CHAR_LIMITS[min(index, len(CHUNK_EXCERPT_CHAR_LIMITS) - 1)]


def group_chunks_by_topic(chunks: list[dict]) -> dict[str, list[dict]]:
    """Group selected chunks by display title while preserving order."""
    grouped: dict[str, list[dict]] = {}
    for chunk in chunks:
        topic = display_topic_title(chunk.get("title") or "")
        grouped.setdefault(topic, []).append(chunk)
    return grouped


def display_topic_title(title: str) -> str:
    """Normalize raw chunk titles for final prompt display only."""
    raw = clean_excerpt_text(title)
    if raw in field_maps.TITLE_DISPLAY_OVERRIDES:
        return field_maps.TITLE_DISPLAY_OVERRIDES[raw]
    display = raw.replace("_", " ")
    display = re.sub(r"\bתשפז\b", 'תשפ"ז', display)
    display = re.sub(r"\bתשפו\b", 'תשפ"ו', display)
    display = re.sub(r"\s+", " ", display).strip()
    return display


def chunk_display_index(chunk: dict, fallback: int) -> str:
    """Derive a human chunk index from a chunk ID without exposing the ID."""
    row_id = str(chunk.get("id") or "")
    match = re.search(r"(?:^|__)chunk_0*([0-9]+)$", row_id)
    if match:
        return match.group(1)
    return str(fallback)


def compact_text(text: str, max_chars: int) -> str:
    """Collapse whitespace and trim long source excerpts."""
    clean = clean_excerpt_text(text)
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 3].rstrip() + "..."


def clean_excerpt_text(text: str) -> str:
    """Remove simple Markdown markup from final chunk excerpts."""
    lines = []
    for line in str(text or "").splitlines():
        line = re.sub(r"^\s*#{1,6}\s*", "", line)
        lines.append(line)
    clean = "\n".join(lines)
    clean = re.sub(r"(?<!\w)#{2,6}\s*", " ", clean)
    clean = clean.replace("**", "").replace("__", "")
    return " ".join(clean.split())


def program_names(selected_entities: list[dict]) -> list[str]:
    """Extract selected Program names for prompt-only scope trimming."""
    names = []
    for entity in selected_entities:
        if entity.get("label") != "Program":
            continue
        properties = entity.get("properties") or {}
        name = str(properties.get("name") or "").strip()
        if name:
            names.append(name)
    return names


def trim_off_scope_admission_rows(text: str, *, question: str, selected_program_names: list[str]) -> str:
    """Remove separate admission table rows that clearly name a different program."""
    if not text or not selected_program_names or not qp.profile(question).has("admission"):
        return text
    row_pattern = re.compile(
        r"(?P<row>\s*[-•]\s*(?:לימודי|ללימודי|לתוכנית|לתכנית)[\s\S]*?)"
        r"(?=\s*[-•]\s*(?:לימודי|ללימודי|לתוכנית|לתכנית)|\n\s*\n|$)"
    )

    def replace_row(match: re.Match[str]) -> str:
        row = match.group("row")
        if keep_admission_fragment(row, question, selected_program_names):
            return row
        return " "

    trimmed = row_pattern.sub(replace_row, text)
    return re.sub(r"\s+", " ", trimmed).strip() or text


def keep_admission_fragment(fragment: str, question: str, selected_program_names: list[str]) -> bool:
    """Keep generic or selected-program admission fragments, drop obvious other-program rows."""
    clean = fragment.strip()
    if not clean:
        return False
    if not re.search(r"[-•]\s*(?:לימודי|ללימודי|לתוכנית|לתכנית)", clean):
        return True
    if any(name and name in clean for name in selected_program_names):
        return True
    question_terms = []
    for term in re.findall(r"[\u0590-\u05ff]{4,}", question):
        normalized = re.sub(r"^[לוובמהכ]+", "", term)
        if normalized and normalized not in FORMATTING_TERMS["admission_generic"]:
            question_terms.append(normalized)
    if any(term in clean for term in question_terms):
        return True
    return not contains_any(clean, FORMATTING_TERMS["other_program_admission"])
