from __future__ import annotations

from graphrag.config.schema_catalog import (
    ADMISSION_PROPS,
    CONTACT_PROPS,
    COURSE_PROPS,
    FEE_PROPS,
    HOUSING_PROPS,
    LOCATION_PROPS,
    NODE_SCHEMA,
    RELATIONSHIP_SCHEMA,
    SCHOLARSHIP_PROPS,
    RelationshipSchema,
    rel,
)
from graphrag.config.schema_rendering import build_schema_payload
from graphrag.config.schema_selection import (
    INTENT_LABELS,
    INTENT_RELATIONSHIP_TYPES,
    allowed_candidate_labels_for_intent,
    dedupe_relationships,
    detect_question_intent,
    one_hop_relationships,
    select_schema_subset,
    valid_labels,
    valid_relationship_types,
)

__all__ = [
    "ADMISSION_PROPS",
    "CONTACT_PROPS",
    "COURSE_PROPS",
    "FEE_PROPS",
    "HOUSING_PROPS",
    "INTENT_LABELS",
    "INTENT_RELATIONSHIP_TYPES",
    "LOCATION_PROPS",
    "NODE_SCHEMA",
    "RELATIONSHIP_SCHEMA",
    "SCHOLARSHIP_PROPS",
    "RelationshipSchema",
    "allowed_candidate_labels_for_intent",
    "build_schema_payload",
    "dedupe_relationships",
    "detect_question_intent",
    "one_hop_relationships",
    "rel",
    "select_schema_subset",
    "valid_labels",
    "valid_relationship_types",
]
