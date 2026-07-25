from __future__ import annotations

AMOUNT_VALUE_KEYS = {
    "amount",
    "display_amount",
    "amount_value",
    "monthly_rent",
    "monthly_total",
    "currency",
    "amount_unit",
    "discount_percent",
    "refund_fraction",
    "payment_condition",
    "valid_until",
}

CONTACT_VALUE_KEYS = {"phone", "email", "whatsapp", "fax", "office_hours"}
DEADLINE_VALUE_KEYS = {"deadline", "valid_until", "date", "exam_date"}
THRESHOLD_VALUE_KEYS = {
    "bagrut_average_min",
    "psychometric_min",
    "combined_score_min",
    "math_grade_min",
    "math_units",
    "hebrew_score_min",
    "matam_score_min",
    "gre_psychology_min",
    "degree_avg_min",
    "engineer_exam_avg_min",
    "engineer_studies_avg_min",
}
CRITERIA_VALUE_KEYS = {
    "condition",
    "conditions",
    "rule_text",
    "description",
    "psychometric_min",
    "bagrut_min",
    "criteria_logic",
}
POLICY_VALUE_KEYS = {"description", "rule_text", "conditions", "deadline", "valid_until"}
CREDIT_VALUE_KEYS = {"credits", "total_credits"}
PROGRAM_FACT_VALUE_KEYS = {"duration", "credits", "study_days", "study_format", "degree_type", "career_fields"}
SUBJECT_ONLY_KEYS = {
    "program",
    "program_name",
    "scholarship",
    "requirement",
    "fee",
    "policy",
    "housing",
    "unit_type",
    "parking",
    "campus",
    "contact",
    "course",
    "specialization",
    "faculty",
    "institution",
    "name",
}
IGNORED_ANSWER_VALUE_KEYS = {"id", "source_id", "chunk_id", "import_key", "evidence", "aliases"}
NAME_ONLY_ANSWER_KEYS = {
    "specialization",
    "course",
    "unit_type",
    "parking",
    "campus",
    "faculty",
    "location",
    "address",
    "preparatory_program",
    "service",
    "housing",
}
