from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from graphrag.config import value_keys
from graphrag.lexicon import question_profile as qp
from graphrag.lexicon import matching
from graphrag.lexicon.question_terms import QUESTION_TERMS

VALUE_TEXT_PATTERNS = {
    "amount": re.compile(r"(₪|ש\"ח|שח|אחוז|%)"),
    "date": re.compile(r"\b\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?\b|\b20\d{2}\b"),
    "threshold": re.compile(r"\b(?:[1-9]\d|[1-7]\d{2})(?:\+| ומעלה)?\b"),
}
ANSWER_VALUE_MARKERS = ("@", "טלפון", "תנאי", "₪")
DIRECT_ANSWER_VALUE_KEYS = (
    value_keys.PROGRAM_FACT_VALUE_KEYS
    | value_keys.AMOUNT_VALUE_KEYS
    | value_keys.CONTACT_VALUE_KEYS
    | value_keys.DEADLINE_VALUE_KEYS
    | value_keys.THRESHOLD_VALUE_KEYS
    | value_keys.CRITERIA_VALUE_KEYS
    | {
        "focus",
        "location",
        "address",
        "required",
        "occupants",
        "course_category",
        "semester",
        "year",
        "weekly_hours",
    }
)
POLICY_NAME_ONLY_RETRY_HINT = (
    "The previous query returned only a Policy name. "
    "For policy/rule/payment/refund/cancellation/deadline questions, "
    "return policy.description, policy.rule_text, policy.conditions, and policy.deadline when available."
)
THIN_ROW_RETRY_HINT = (
    "The previous query returned rows, but they did not contain the answer value requested by the question.\n"
    "Return the target node name/description and bind answer-bearing relationships as r.\n"
    "For relationship-scoped facts, return properties(r) AS relationship."
)
ALIAS_RETRY_HINT = "Use lowercase snake_case aliases only, and use properties(r) AS relationship for relationship-scoped facts."
ZERO_ROWS_RETRY_HINT = (
    "The previous query matched no rows. Check relationship direction against the provided schema. "
    "Do not connect candidate IDs unless the schema shows that exact relationship direction."
)


@dataclass(frozen=True)
class RequiredValueRule:
    """Describe one value category rows must contain for a question type."""

    name: str
    applies: Callable[[str], bool]
    keys: set[str]
    allow_amount_text: bool = False
    allow_date_text: bool = False
    allow_threshold_text: bool = False


@dataclass(frozen=True)
class ValueRequirement:
    """Describe the primary concrete answer value requested by a question."""

    name: str
    applies: Callable[[qp.QuestionProfile], bool]


VALUE_REQUIREMENT_PRECEDENCE = (
    ValueRequirement("contact", lambda profile: profile.has("contact")),
    ValueRequirement("deadline", lambda profile: profile.has("deadline") or profile.has("document_deadline")),
    ValueRequirement("program_fact", lambda profile: profile.has("program_fact")),
    ValueRequirement("threshold", lambda profile: profile.has("admission") and profile.has("admission_criteria")),
    ValueRequirement("criteria", lambda profile: profile.has("scholarship")),
    ValueRequirement("amount", lambda profile: money_amount_is_primary_requirement(profile)),
)


def schema_terms_outside_attempt(cypher: str, generation: dict) -> dict:
    """Find generated labels/relationships not shown in this attempt's schema."""
    allowed_labels = set(generation.get("schema_labels") or [])
    allowed_relationships = set(generation.get("schema_relationships") or [])
    labels, relationships = cypher_schema_terms(cypher)
    return {
        "labels": sorted(label for label in labels if allowed_labels and label not in allowed_labels),
        "relationships": sorted(rel for rel in relationships if allowed_relationships and rel not in allowed_relationships),
    }


def cypher_schema_terms(cypher: str) -> tuple[set[str], set[str]]:
    """Extract labels and relationship types from generated Cypher."""
    labels = set(re.findall(r"\(\s*(?:[A-Za-z_][\w]*\s*)?:\s*([A-Za-z][A-Za-z0-9_]*)", cypher or ""))
    relationships = set(re.findall(r"\[\s*(?:[A-Za-z_][\w]*\s*)?:\s*([A-Z_][A-Z0-9_]*)", cypher or ""))
    return labels, relationships


def missing_required_answer_value(question: str, rows: list[dict]) -> str:
    """Return a retry reason when rows lack the value category requested."""
    if qp.profile(question).has("total_credits") and not rows_have_nonzero_credit_value(rows):
        return "missing_required_answer_value:credits"
    for rule in required_value_rules():
        if rule.applies(question) and not rows_have_answer_value(
            rows,
            rule.keys,
            allow_amount_text=rule.allow_amount_text,
            allow_date_text=rule.allow_date_text,
            allow_threshold_text=rule.allow_threshold_text,
        ):
            return f"missing_required_answer_value:{rule.name}"
    return ""


def missing_policy_node_value(question: str, rows: list[dict]) -> str:
    """Reject policy-like rows that only name a Policy without policy content."""
    if not is_policy_like_question(question):
        return ""
    if not rows_contain_policy_name(rows):
        return ""
    if rows_have_answer_value(rows, value_keys.POLICY_VALUE_KEYS | value_keys.AMOUNT_VALUE_KEYS | {"relationship"}, allow_date_text=True):
        return ""
    return "missing_policy_node_value"


def rows_are_answer_empty(question: str, rows: list[dict]) -> bool:
    """Detect rows that contain only subject/name fields and no answer values."""
    if not rows:
        return True
    saw_subject = False
    for row in rows:
        for key_path, value in iter_leaf_values(row):
            if not value_is_present(value):
                continue
            key = key_path[-1]
            if key in value_keys.IGNORED_ANSWER_VALUE_KEYS:
                continue
            if key in DIRECT_ANSWER_VALUE_KEYS:
                return False
            if key in value_keys.SUBJECT_ONLY_KEYS:
                saw_subject = True
                continue
            if isinstance(value, (int, float, bool)):
                return False
            text = str(value).strip()
            if len(text) > 80 or has_answer_like_text(text):
                return False
    if saw_subject and allows_name_only_answer(question, rows):
        return False
    return saw_subject


def allows_name_only_answer(question: str, rows: list[dict]) -> bool:
    """Allow name-shaped rows when names/categories are the requested answer."""
    if question_requires_concrete_value(question):
        return False
    if not qp.profile(question).has("name_answer"):
        return False
    return rows_have_answer_key(rows, value_keys.NAME_ONLY_ANSWER_KEYS)


def question_requires_concrete_value(question: str) -> bool:
    """Return true when name-only rows are not enough for this question."""
    return bool(active_value_requirement(question))


def requires_money_answer_value(question: str) -> bool:
    """Return true when graph rows must include an amount-like value."""
    return active_value_requirement(question) == "amount"


def active_value_requirement(question: str) -> str:
    """Return the concrete value type this question primarily asks for."""
    question_profile = qp.profile(question)
    for requirement in VALUE_REQUIREMENT_PRECEDENCE:
        if requirement.applies(question_profile):
            return requirement.name
    return ""


def money_amount_is_primary_requirement(question_profile: qp.QuestionProfile) -> bool:
    """Return true when money terms ask for an amount rather than another value type."""
    if not question_profile.has("money_amount"):
        return False
    if question_profile.has("payment_method"):
        return False
    if question_profile.has("deadline"):
        return question_profile.has("explicit_amount")
    if question_profile.has("refund_policy") or question_profile.has("no_refund_or_rejection"):
        return question_profile.has("explicit_amount")
    return True


def required_value_rules() -> tuple[RequiredValueRule, ...]:
    """Return ordered required-value rules for graph row quality checks."""
    return (
        RequiredValueRule("amount", requires_money_answer_value, value_keys.AMOUNT_VALUE_KEYS, allow_amount_text=True),
        RequiredValueRule("contact", profile_has("contact"), value_keys.CONTACT_VALUE_KEYS),
        RequiredValueRule("deadline", profile_has("deadline"), value_keys.DEADLINE_VALUE_KEYS, allow_date_text=True),
        RequiredValueRule(
            "threshold",
            profile_has_all("admission", "admission_criteria"),
            value_keys.THRESHOLD_VALUE_KEYS | {"requirement_text", "rule_text", "criteria_logic", "conditions", "description"},
        ),
        RequiredValueRule("criteria", profile_has("scholarship"), value_keys.CRITERIA_VALUE_KEYS, allow_threshold_text=True),
    )


def profile_has(name: str) -> Callable[[str], bool]:
    """Return a question predicate backed by QuestionProfile."""
    return lambda question: qp.profile(question).has(name)


def profile_has_all(*names: str) -> Callable[[str], bool]:
    """Return a question predicate that requires all named profile flags."""
    return lambda question: all(qp.profile(question).has(name) for name in names)


def rows_have_answer_key(rows: list[dict], keys: set[str]) -> bool:
    """Return true when rows contain one of the requested answer-role keys."""
    for row in rows:
        for key_path, value in iter_leaf_values(row):
            key = key_path[-1] if key_path else ""
            normalized_key = key.removesuffix("_name")
            if value_is_present(value) and normalized_key in keys:
                return True
    return False


def rows_have_nonzero_credit_value(rows: list[dict]) -> bool:
    """Return true when rows contain a positive credit value."""
    for row in rows:
        for key_path, value in iter_leaf_values(row):
            key = key_path[-1] if key_path else ""
            if key in value_keys.CREDIT_VALUE_KEYS and numeric_value(value) > 0:
                return True
    return False


def numeric_value(value) -> float:
    """Return a numeric scalar when safely parseable, otherwise zero."""
    if isinstance(value, bool) or value in (None, "", [], {}):
        return 0.0
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return 0.0


def is_policy_like_question(question: str) -> bool:
    """Detect policy/rule/payment/refund/deadline/permission questions."""
    question_profile = qp.profile(question)
    return (
        question_profile.has("policy")
        or question_profile.has("refund_policy")
        or matching.contains_any(question, QUESTION_TERMS["policy_permission"])
    )


def rows_contain_policy_name(rows: list[dict]) -> bool:
    """Return true when rows include a Policy role/name field."""
    for row in rows:
        if row.get("policy") not in (None, "", [], {}) or row.get("policy_name") not in (None, "", [], {}) or row.get("name") not in (None, "", [], {}):
            return True
    return False


def rows_have_answer_value(
    rows: list[dict],
    keys: set[str],
    *,
    allow_amount_text: bool = False,
    allow_date_text: bool = False,
    allow_threshold_text: bool = False,
) -> bool:
    """Return true when any row has a non-empty nested answer value."""
    for row in rows:
        for key_path, value in iter_leaf_values(row):
            if not value_is_present(value):
                continue
            key = key_path[-1]
            if key in value_keys.IGNORED_ANSWER_VALUE_KEYS:
                continue
            if leaf_matches_answer_value(
                key,
                value,
                keys,
                allow_amount_text=allow_amount_text,
                allow_date_text=allow_date_text,
                allow_threshold_text=allow_threshold_text,
            ):
                return True
    return False


def leaf_matches_answer_value(
    key: str,
    value,
    keys: set[str],
    *,
    allow_amount_text: bool = False,
    allow_date_text: bool = False,
    allow_threshold_text: bool = False,
) -> bool:
    """Return true when one leaf value satisfies an answer-value requirement."""
    if key in keys:
        return True
    text = str(value)
    return (
        allow_amount_text and matching.matches_pattern(text, VALUE_TEXT_PATTERNS["amount"])
        or allow_date_text and matching.matches_pattern(text, VALUE_TEXT_PATTERNS["date"])
        or allow_threshold_text and matching.matches_pattern(text, VALUE_TEXT_PATTERNS["threshold"])
    )


def iter_leaf_values(value, path: tuple[str, ...] = ()):
    """Yield nested scalar values with their key path."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield from iter_leaf_values(child, (*path, str(key)))
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_leaf_values(child, (*path, str(index)))
        return
    yield path, value


def value_is_present(value) -> bool:
    """Return true for values that can carry answer content."""
    return value not in (None, "", [], {})


def has_answer_like_text(text: str) -> bool:
    """Detect scalar text that carries a value rather than only a name."""
    return (
        any(matching.matches_pattern(text, pattern) for pattern in VALUE_TEXT_PATTERNS.values())
        or matching.contains_any(text, ANSWER_VALUE_MARKERS)
    )


def retry_feedback_for_attempt(guard, generation: dict, error: str) -> str:
    """Build compact feedback for the next Cypher generation attempt."""
    cypher = guard.cypher if getattr(guard, "ok", False) else generation.get("cypher", "")
    parts = []
    if cypher:
        parts.append(f"Previous Cypher:\n{cypher}")
    if error:
        parts.append(f"Failure reason: {error}")
        if error == "zero_rows":
            parts.append(ZERO_ROWS_RETRY_HINT)
        if error == "empty_answer_rows" or error.startswith("missing_required_answer_value:"):
            parts.append(THIN_ROW_RETRY_HINT)
            if error == "empty_answer_rows" and cypher_returns_only_policy_name(cypher):
                parts.append(POLICY_NAME_ONLY_RETRY_HINT)
        if error == "missing_policy_node_value":
            parts.append(POLICY_NAME_ONLY_RETRY_HINT)
        if error == "invalid_return_alias_style":
            parts.append(ALIAS_RETRY_HINT)
    elif generation.get("error"):
        parts.append(f"Generation error: {generation.get('error')}")
    return "\n".join(parts).strip()


def cypher_returns_only_policy_name(cypher: str) -> bool:
    """Detect RETURN policy.name AS policy without other answer fields."""
    match = re.search(r"\bRETURN\b(.+?)(?:\bORDER\s+BY\b|\bLIMIT\b|$)", cypher or "", flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return False
    body = match.group(1)
    if not re.search(r"\b[A-Za-z_][\w]*\.name\s+AS\s+(?:policy|policy_name|name)\b", body, flags=re.IGNORECASE):
        return False
    return not re.search(r"\.(?:description|rule_text|conditions|deadline|valid_until)\b|properties\s*\(", body, flags=re.IGNORECASE)
