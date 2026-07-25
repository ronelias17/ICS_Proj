from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from collections.abc import Iterable

from graphrag.lexicon import matching
from graphrag.lexicon.question_terms import QUESTION_TERMS


DIRECT_INTENT_NAMES = {
    "admission",
    "program_fact",
    "contact",
    "refund_policy",
    "document_submission",
    "deadline",
    "payment_discount",
    "fee_or_policy",
    "course",
    "specialization",
    "housing",
    "parking",
    "campus_location",
    "faculty",
    "scholarship",
    "sports_service",
    "sports_facility",
    "service_facility",
    "preparatory",
    "prep_route",
    "list",
    "degree_structure",
}

HELPER_TERM_NAMES = {
    "policy",
    "explicit_amount",
    "no_refund_or_rejection",
    "payment_method",
    "name_answer",
    "admission_criteria",
    "housing_unit",
    "fee_or_policy_trigger",
}


@dataclass(frozen=True)
class DerivedIntentRule:
    """Describe an intent inferred from other intents or term groups."""

    name: str
    required_intents: tuple[str, ...] = ()
    any_terms: str = ""
    all_terms: tuple[str, ...] = ()
    not_terms: str = ""

    def matches(self, question: str, intents: set[str]) -> bool:
        """Return true when this derived rule applies."""
        if self.required_intents and not all(intent in intents for intent in self.required_intents):
            return False
        if self.any_terms and not matching.contains_any(question, QUESTION_TERMS[self.any_terms]):
            return False
        if self.all_terms and not all(term in question for term in self.all_terms):
            return False
        if self.not_terms and matching.contains_any(question, QUESTION_TERMS[self.not_terms]):
            return False
        return True


DERIVED_INTENT_RULES = (
    DerivedIntentRule("document_deadline", required_intents=("document_submission", "deadline")),
    DerivedIntentRule("housing_location", required_intents=("housing",), any_terms="housing_location"),
    DerivedIntentRule("housing_price", required_intents=("housing",), any_terms="housing_price"),
    DerivedIntentRule("parking_location", required_intents=("parking",), any_terms="parking_location"),
    DerivedIntentRule("parking_fee_or_policy", required_intents=("parking",), any_terms="parking_fee_or_policy"),
    DerivedIntentRule("money_amount", any_terms="money_amount"),
    DerivedIntentRule("money_amount", all_terms=("כמה",), any_terms="money_amount_with_kama"),
    DerivedIntentRule("required_course", all_terms=QUESTION_TERMS["required_course_all"]),
    DerivedIntentRule("total_credits", any_terms="total_credits", not_terms="course"),
)

PRIMARY_INTENT_PRIORITY = (
    ("scholarship", ("scholarship",)),
    ("service_facility", ("sports_facility", "sports_service")),
    ("document_deadline", ("document_deadline",)),
    ("contact", ("contact",)),
    ("document", ("document_submission",)),
    ("payment_discount", ("payment_discount",)),
    ("fee_or_policy", ("refund_policy", "fee_or_policy_trigger")),
    ("program_fact", ("program_fact",)),
    ("parking_fee_or_policy", ("parking_fee_or_policy",)),
    ("parking_location", ("parking_location",)),
    ("housing", ("housing",)),
    ("campus_location", ("campus_location",)),
    ("faculty", ("faculty",)),
    ("admission", ("admission",)),
    ("course", ("course",)),
    ("specialization", ("specialization",)),
    ("fee_or_policy", ("fee_or_policy",)),
)


@dataclass(frozen=True)
class QuestionProfile:
    """Reusable lightweight interpretation of a visitor question."""

    question: str
    intents: frozenset[str]
    primary: str

    def has(self, intent_name: str) -> bool:
        """Return true when this question matched the named intent."""
        return intent_name in self.intents

    def has_any(self, names: Iterable[str]) -> bool:
        """Return true when this question matched at least one named intent."""
        return any(name in self.intents for name in names)


@lru_cache(maxsize=512)
def profile(question: str) -> QuestionProfile:
    """Return the cached question profile used across retrieval and formatting."""
    intents = detect_intents(question)
    return QuestionProfile(question=question, intents=frozenset(intents), primary=detect_primary_intent(intents))


def detect_intents(question: str) -> set[str]:
    """Return all lightweight rule intents matched by the question."""
    intents = {
        name
        for name in DIRECT_INTENT_NAMES
        if matching.contains_any(question, QUESTION_TERMS[name])
    }
    intents.update(
        name
        for name in HELPER_TERM_NAMES
        if matching.contains_any(question, QUESTION_TERMS[name])
    )
    for rule in DERIVED_INTENT_RULES:
        if rule.matches(question, intents):
            intents.add(rule.name)
    return intents


def detect_primary_intent(intents: set[str]) -> str:
    """Return the schema/routing intent for a set of detected intents."""
    for result, candidates in PRIMARY_INTENT_PRIORITY:
        if any(candidate in intents for candidate in candidates):
            return result
    return "generic"


def detect_question_intent(question: str) -> str:
    """Return the primary schema/routing intent for one question."""
    return profile(question).primary
