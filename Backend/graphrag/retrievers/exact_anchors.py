from __future__ import annotations

from dataclasses import dataclass

from graphrag.lexicon import question_profile as qp
from graphrag.lexicon.question_terms import QUESTION_TERMS


@dataclass(frozen=True)
class ExactAnchor:
    """Small local entity anchor used when the question names a known concept."""

    entity_id: str
    label: str
    name: str
    aliases: tuple[str, ...]
    description: str = ""
    required_intent: str = ""


EXACT_ANCHORS = [
    ExactAnchor("program_ba_computer_science", "Program", "מדעי המחשב", ("מדעי המחשב", "תואר ראשון במדעי המחשב", "computer science")),
    ExactAnchor("program_ba_computer_engineering", "Program", "הנדסת מחשבים", ("הנדסת מחשבים", "תואר ראשון בהנדסת מחשבים", "computer engineering")),
    ExactAnchor("program_ba_electrical_and_electronics_engineering", "Program", "הנדסת חשמל ואלקטרוניקה", ("הנדסת חשמל", "הנדסת חשמל ואלקטרוניקה")),
    ExactAnchor("program_ba_industrial_and_management_engineering", "Program", "הנדסת תעשייה וניהול", ("הנדסת תעשייה וניהול",)),
    ExactAnchor("program_ba_nursing", "Program", "מדעי האחיות", ("מדעי האחיות", "סיעוד", "אחיות", "nursing", "bsn")),
    ExactAnchor("program_ba_economics_and_accounting", "Program", "כלכלה וחשבונאות", ("כלכלה וחשבונאות",)),
    ExactAnchor("program_ma_clinical_psychology", "Program", "פסיכולוגיה קלינית", ("פסיכולוגיה קלינית", "תואר שני בפסיכולוגיה קלינית")),
    ExactAnchor("program_ma_clinical_psychology_of_aging", "Program", "פסיכולוגיה קלינית של הבגרות והזקנה", ("פסיכולוגיה קלינית של הבגרות", "פסיכולוגיה קלינית של הזקנה")),
    ExactAnchor("program_ma_marine_sciences", "Program", "מדעי הים עם תזה", ("מדעי הים עם תזה", "תואר שני במדעי הים עם תזה", "ma marine sciences with thesis")),
    ExactAnchor("program_ma_business_administration", "Program", "מנהל עסקים", ("mba", "MBA", "מנהל עסקים", "מוסמך במנהל עסקים")),
    ExactAnchor("fee_tuition_deposit", "Fee", "מקדמת שכר לימוד", ("מקדמה", "מקדמת שכר לימוד")),
    ExactAnchor("faculty_engineering", "Faculty", "הפקולטה להנדסה", ("הנדסה", "פקולטה להנדסה"), required_intent="scholarship"),
    ExactAnchor("housing_ruppin_dormitory", "Housing", "מעונות המרכז האקדמי רופין", ("מעונות", "המעונות", "דיור", "מגורים")),
    ExactAnchor("parking_student_parking_lot", "Parking", "חניון סטודנטים", QUESTION_TERMS["parking"] + ("חניה לסטודנטים", "חנייה לסטודנטים")),
    ExactAnchor("contact_tuition_department", "ContactPoint", "מחלקת שכר לימוד", ("מחלקת שכר לימוד",), required_intent="contact"),
    ExactAnchor("contact_registration_advising_center", "ContactPoint", "מרכז ייעוץ והרשמה", ("מרכז ייעוץ והרשמה", "ייעוץ והרשמה", "מרכז הרישום", "בדיקת נתוני קבלה")),
    ExactAnchor("preparatory_program_engineering_and_sciences", "PreparatoryProgram", "מכינה להנדסה ומדעים", ("מכינה להנדסה ומדעים", "מכינה להנדסה", "מכינה מדעים")),
    ExactAnchor("preparatory_program_engineering_and_sciences_semester", "PreparatoryProgram", "מכינה סמסטריאלית להנדסה ומדעים", ("מכינה סמסטריאלית להנדסה",)),
    ExactAnchor("student_service_sports_unit", "StudentService", "היחידה לספורט", ("היחידה לספורט", "מתקני ספורט", "ספורט")),
    ExactAnchor("student_service_sports_teams", "StudentService", "נבחרות ספורט", ("נבחרות ספורט", "אסא", "אס\"א")),
]


def boost_exact_entity_anchors(question: str, rows: list[dict], top_k: int) -> list[dict]:
    """Inject local exact entity anchors above weak vector/full-text hits."""
    matched = [anchor for anchor in EXACT_ANCHORS if anchor_matches_question(anchor, question)]
    if not matched:
        return rows[:top_k]
    merged = {row.get("id"): dict(row) for row in rows if row.get("id")}
    for index, anchor in enumerate(matched):
        existing = merged.get(anchor.entity_id, {})
        sources = list(existing.get("retrieval_sources") or [])
        if "exact_anchor" not in sources:
            sources.insert(0, "exact_anchor")
        merged[anchor.entity_id] = {
            **existing,
            "id": anchor.entity_id,
            "labels": existing.get("labels") or ["Entity", anchor.label],
            "name": existing.get("name") or anchor.name,
            "description": existing.get("description") or anchor.description,
            "vector_score": float(existing.get("vector_score") or 0.0),
            "lexical_score": float(existing.get("lexical_score") or 0.0),
            "vector_rank": existing.get("vector_rank"),
            "lexical_rank": existing.get("lexical_rank"),
            "rrf_score": max(float(existing.get("rrf_score") or 0.0), 10.0 - (index * 0.01)),
            "score": max(float(existing.get("score") or 0.0), 10.0 - (index * 0.01)),
            "exact_anchor_rank": index + 1,
            "retrieval_sources": sources,
        }
    return sorted(
        merged.values(),
        key=lambda row: (
            0 if "exact_anchor" in (row.get("retrieval_sources") or []) else 1,
            int(row.get("exact_anchor_rank") or 999),
            -float(row.get("rrf_score") or 0.0),
            str(row.get("id") or ""),
        ),
    )[:top_k]


def anchor_matches_question(anchor: ExactAnchor, question: str) -> bool:
    """Return true when one configured alias appears in the question."""
    text = normalize(question)
    question_profile = qp.profile(question)
    if anchor.required_intent == "contact" and not (
        question_profile.has("contact") or any(normalize(term) in text for term in QUESTION_TERMS["tuition_department"])
    ):
        return False
    if anchor.required_intent == "scholarship" and not question_profile.has("scholarship"):
        return False
    return any(normalize(alias) in text for alias in anchor.aliases if alias)


def normalize(value: str) -> str:
    """Normalize local exact-anchor text for phrase containment."""
    return " ".join(str(value or "").casefold().replace("־", "-").split())
