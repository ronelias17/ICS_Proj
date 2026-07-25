from __future__ import annotations

from graphrag.lexicon import question_profile as qp
from graphrag.config.schema_catalog import NODE_SCHEMA
from graphrag.config.schema_catalog import RELATIONSHIP_SCHEMA
from graphrag.config.schema_catalog import RelationshipSchema


INTENT_LABELS = {
    "admission": {"Program", "AdmissionRequirement"},
    "program_fact": {"Program"},
    "document": {"Program", "Policy"},
    "document_deadline": {"Program", "Policy"},
    "payment_discount": {"Program", "Institution", "Policy"},
    "fee_or_policy": {"Program", "Institution", "Fee", "Policy"},
    "course": {"Program", "Course", "Specialization"},
    "specialization": {"Program", "Specialization", "Course"},
    "contact": {"ContactPoint", "Program", "Institution", "Faculty", "StudentService"},
    "housing": {"Housing", "HousingUnitType", "Fee", "Policy", "Campus", "Institution"},
    "parking_location": {"Parking", "Campus", "Institution"},
    "parking_fee_or_policy": {"Parking", "Fee", "Policy", "Institution", "Campus"},
    "campus_location": {"Campus", "Institution", "Housing", "Program", "Faculty", "Parking"},
    "faculty": {"Faculty", "Institution", "Program"},
    "scholarship": {"Program", "Faculty", "Scholarship", "Institution", "PreparatoryProgram"},
    "service_facility": {"Institution", "StudentService", "ContactPoint"},
    "generic": {"Program", "Institution", "Faculty"},
}

INTENT_RELATIONSHIP_TYPES = {
    "admission": {"HAS_ADMISSION_REQUIREMENT"},
    "program_fact": set(),
    "document": {"HAS_POLICY"},
    "document_deadline": {"HAS_POLICY"},
    "payment_discount": {"HAS_POLICY"},
    "fee_or_policy": {"HAS_FEE", "HAS_POLICY"},
    "course": {"HAS_COURSE", "RECOGNIZES_COURSE_FOR_EXEMPTION"},
    "specialization": {"HAS_SPECIALIZATION"},
    "contact": {"HAS_CONTACT"},
    "housing": {"HAS_HOUSING", "HAS_HOUSING_UNIT_TYPE", "HAS_FEE", "HAS_POLICY", "LOCATED_AT"},
    "parking_location": {"HAS_PARKING", "HAS_CAMPUS", "LOCATED_AT"},
    "parking_fee_or_policy": {"HAS_PARKING", "LOCATED_AT", "HAS_FEE", "HAS_POLICY", "HAS_CONTACT"},
    "campus_location": {"HAS_PARKING", "HAS_CAMPUS", "LOCATED_AT"},
    "faculty": {"HAS_FACULTY", "BELONGS_TO_FACULTY"},
    "scholarship": {"HAS_SCHOLARSHIP", "BELONGS_TO_FACULTY"},
    "service_facility": {"HAS_SERVICE", "HAS_CONTACT"},
    "generic": {"BELONGS_TO_FACULTY", "HAS_CAMPUS", "LOCATED_AT"},
}


def select_schema_subset(
    candidate_labels: list[str] | set[str],
    question: str,
) -> tuple[set[str], list[RelationshipSchema]]:
    """Choose schema from question intent and top candidate labels."""
    primary_intent = detect_question_intent(question)
    question_profile = qp.profile(question)
    candidate_label_set = set(label for label in candidate_labels if label in NODE_SCHEMA)
    labels = set(candidate_label_set)
    if not labels:
        labels.update(INTENT_LABELS[primary_intent])
    if primary_intent == "admission" and question_profile.has("prep_route"):
        labels.add("PreparatoryProgram")
    seed_labels = set(labels)
    relationships = relationships_for_intent(primary_intent, seed_labels)
    if primary_intent == "program_fact":
        return labels, []
    labels.update(endpoint for rel in relationships for endpoint in rel.endpoints() if endpoint)
    if not relationships:
        fallback = [rel for rel in RELATIONSHIP_SCHEMA if rel.rel_type in INTENT_RELATIONSHIP_TYPES["generic"]]
        labels.update({"Program", "Institution", "Faculty", "Campus"})
        return labels, fallback
    return labels, dedupe_relationships(relationships)

def valid_labels() -> set[str]:
    """Return labels allowed in generated Cypher."""
    return set(NODE_SCHEMA)


def valid_relationship_types() -> set[str]:
    """Return relationship types allowed in generated Cypher."""
    return {rel.rel_type for rel in RELATIONSHIP_SCHEMA}


def detect_question_intent(question: str) -> str:
    """Detect the schema intent used for Cypher prompt trimming."""
    return qp.detect_question_intent(question)


def allowed_candidate_labels_for_intent(intent_name: str, question: str = "") -> set[str]:
    """Return candidate labels that may expand the schema for one intent."""
    allowed = set(INTENT_LABELS.get(intent_name, INTENT_LABELS["generic"]))
    if intent_name == "admission" and qp.profile(question).has("prep_route"):
        allowed.add("PreparatoryProgram")
    return allowed


def one_hop_relationships(labels: set[str]) -> list[RelationshipSchema]:
    """Return one-hop relationship patterns around selected labels."""
    return [rel for rel in RELATIONSHIP_SCHEMA if rel.touches(labels)]


def relationships_for_intent(intent_name: str, labels: set[str]) -> list[RelationshipSchema]:
    """Prefer intent-relevant relationships while keeping one-hop schema as fallback."""
    relationships = one_hop_relationships(labels)
    wanted_types = INTENT_RELATIONSHIP_TYPES.get(intent_name, set())
    if not wanted_types:
        return relationships
    focused = [rel for rel in relationships if rel.rel_type in wanted_types]
    return focused or relationships


def dedupe_relationships(relationships: list[RelationshipSchema]) -> list[RelationshipSchema]:
    """Keep relationship schema rows in original order without duplicate patterns."""
    seen = set()
    result = []
    for rel in relationships:
        pattern = rel.pattern
        if pattern in seen:
            continue
        seen.add(pattern)
        result.append(rel)
    return result
