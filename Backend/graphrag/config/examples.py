from __future__ import annotations

from graphrag.lexicon.matching import contains_any


EXAMPLE_QUESTION_TAG_TERMS = {
    "admission": ("קבלה", "תנאי קבלה", "פסיכומטרי", "בגרות"),
    "deposit_amount": ("מקדמה", "כמה עולה המקדמה", "עלות המקדמה"),
    "refund_policy": ("החזר", "מוחזר", "מוחזרים", "לא מוחזר", "ביטול הרשמה", "דמי הרשמה"),
    "payment_discount": ("הנחה", "תשלום אחד", "יתרת שכר לימוד"),
    "payment_method": ("איך משלמים", "אפשר לשלם", "ניתן לשלם", "במזומן", "אשראי", "צ'ק"),
    "housing_price": ("כמה עולה דירה", "כמה עולה דירת", "מחיר דירה", "מה העלות דירה", "שכר דירה"),
    "program_fact": ("כמה שנים", "נקודות זכות", "משך הלימודים"),
    "contact": ("קשר", "טלפון", "אימייל", "מייל", "וואטסאפ"),
    "faculty": ("פקולטה", "פקולטות", "הפקולטות", "faculty", "faculties"),
    "housing": ("מעונות", "דירה", "דירות", "דיור", "מגורים"),
    "parking": ("חניה", "חנייה", "חניון", "חניה לסטודנטים"),
    "course": ("קורס", "קורסי חובה", "סילבוס"),
    "specialization": ("מסלול", "התמחות", "התמחויות"),
    "scholarship": ("מלגה", "מלגות", "מצטיינים", "הצטיינות"),
    "prep_route": ("מכינה", "קדם אקדמית", "הנדסה ומדעים"),
}


CYPHER_EXAMPLES = [
    {
        "tags": {"Program", "AdmissionRequirement", "HAS_ADMISSION_REQUIREMENT", "admission"},
        "question": "מה תנאי הקבלה למדעי המחשב?",
        "cypher": """
MATCH (p:Program {id: "program_ba_computer_science"})-[r:HAS_ADMISSION_REQUIREMENT]->(a:AdmissionRequirement)
RETURN p.name AS program, a.name AS requirement, a.description AS description, properties(r) AS relationship
LIMIT 10
""".strip(),
    },
    {
        "tags": {"Program", "Fee", "HAS_FEE", "Policy", "deposit_amount"},
        "question": "כמה עולה המקדמה לפסיכולוגיה קלינית?",
        "cypher": """
MATCH (p:Program {id: "program_ma_clinical_psychology"})-[r:HAS_FEE]->(f:Fee {id: "fee_tuition_deposit"})
WHERE r.amount_value IS NOT NULL OR r.display_amount IS NOT NULL
RETURN p.name AS program, f.name AS fee, properties(r) AS relationship
LIMIT 10
""".strip(),
    },
    {
        "tags": {"Policy", "refund_policy"},
        "question": "האם דמי הרשמה מוחזרים במקרה של ביטול הרשמה?",
        "cypher": """
MATCH (policy:Policy {id: "policy_registration_fee_non_refundable"})
RETURN policy.name AS policy,
       policy.description AS description,
       policy.rule_text AS rule_text,
       policy.conditions AS conditions,
       policy.deadline AS deadline
LIMIT 10
""".strip(),
    },
    {
        "tags": {"Policy", "payment_discount"},
        "question": "האם יש הנחה על תשלום יתרת שכר לימוד בתשלום אחד?",
        "cypher": """
MATCH (policy:Policy {id: "policy_single_payment_discount"})
RETURN policy.name AS policy,
       policy.description AS description,
       policy.rule_text AS rule_text,
       policy.conditions AS conditions,
       policy.deadline AS deadline
LIMIT 10
""".strip(),
    },
    {
        "tags": {"Policy", "payment_method"},
        "question": "האם אפשר לשלם שכר לימוד במזומן?",
        "cypher": """
MATCH (policy:Policy {id: "policy_cash_payment_limit"})
RETURN policy.name AS policy,
       policy.description AS description,
       policy.rule_text AS rule_text,
       policy.conditions AS conditions
LIMIT 10
""".strip(),
    },
    {
        "tags": {"ContactPoint", "contact"},
        "question": "איך יוצרים קשר עם מחלקת שכר לימוד?",
        "cypher": """
MATCH (contact:ContactPoint {id: "contact_tuition_department"})
RETURN contact.name AS contact,
       contact.phone AS phone,
       contact.email AS email,
       contact.office_hours AS office_hours
LIMIT 10
""".strip(),
    },
    {
        "tags": {"Institution", "Faculty", "HAS_FACULTY", "faculty"},
        "question": "איזה פקולטות יש ברופין?",
        "cypher": """
MATCH (i:Institution)-[:HAS_FACULTY]->(f:Faculty)
RETURN f.name AS faculty
LIMIT 10
""".strip(),
    },
    {
        "tags": {"Fee", "HAS_FEE", "payment_method", "fee_or_policy"},
        "question": "מה אפשרויות התשלום של יתרת שכר הלימוד?",
        "cypher": """
MATCH (owner)-[r:HAS_FEE]->(f:Fee {id: "fee_tuition_balance"})
RETURN f.name AS fee,
       properties(r) AS relationship
LIMIT 10
""".strip(),
    },
    {
        "tags": {"Program", "Specialization", "HAS_SPECIALIZATION", "specialization"},
        "question": "איזה מסלולים יש במדעי המחשב?",
        "cypher": """
MATCH (p:Program {id: "program_ba_computer_science"})-[:HAS_SPECIALIZATION]->(s:Specialization)
RETURN p.name AS program, s.name AS specialization, s.focus AS focus, s.description AS description
LIMIT 10
""".strip(),
    },
    {
        "tags": {"Program", "Scholarship", "HAS_SCHOLARSHIP", "scholarship"},
        "question": "מה התנאים למלגת מצטיינים בהנדסת תעשייה וניהול?",
        "cypher": """
MATCH (p:Program {id: "program_ba_industrial_and_management_engineering"})-[r:HAS_SCHOLARSHIP]->(s:Scholarship)
RETURN p.name AS program,
       s.name AS scholarship,
       s.condition AS condition,
       s.description AS description,
       properties(r) AS relationship
LIMIT 10
""".strip(),
    },
    {
        "tags": {"Housing", "HousingUnitType", "HAS_HOUSING_UNIT_TYPE", "housing", "housing_price"},
        "question": "כמה עולה דירת סטודיו במעונות?",
        "cypher": """
MATCH (h:Housing)-[r:HAS_HOUSING_UNIT_TYPE]->(u:HousingUnitType)
WHERE r.monthly_total IS NOT NULL OR r.monthly_rent IS NOT NULL
RETURN h.name AS housing,
       u.name AS unit_type,
       properties(r) AS relationship
LIMIT 10
""".strip(),
    },
    {
        "tags": {"Parking", "Campus", "HAS_PARKING", "LOCATED_AT", "parking"},
        "question": "האם יש חניה לסטודנטים?",
        "cypher": """
MATCH (i:Institution)-[:HAS_PARKING]->(p:Parking)
OPTIONAL MATCH (p)-[r:LOCATED_AT]->(c:Campus)
RETURN p.name AS parking, p.location AS location,
       c.name AS campus, c.address AS address,
       properties(r) AS relationship
LIMIT 10
""".strip(),
    },
    {
        "tags": {"Program", "Course", "HAS_COURSE", "course"},
        "question": "אילו קורסי חובה יש במדעי המחשב?",
        "cypher": """
MATCH (p:Program {id: "program_ba_computer_science"})-[r:HAS_COURSE]->(c:Course)
RETURN p.name AS program, c.name AS course, properties(r) AS relationship
LIMIT 10
""".strip(),
    },
    {
        "tags": {"PreparatoryProgram", "AdmissionRequirement", "HAS_ADMISSION_REQUIREMENT", "admission", "prep_route"},
        "question": "מה תנאי הקבלה למכינה להנדסה ומדעים?",
        "cypher": """
MATCH (prep:PreparatoryProgram)-[r:HAS_ADMISSION_REQUIREMENT]->(a:AdmissionRequirement)
RETURN prep.name AS preparatory_program,
       prep.duration AS duration,
       a.name AS requirement,
       a.description AS description,
       properties(r) AS relationship
LIMIT 10
""".strip(),
    },
]

def examples_text(question: str = "", intent: str | None = None) -> str:
    """Render up to two intent-relevant Cypher examples."""
    wanted = ({intent} if intent and intent != "generic" else set()) | example_tags_for_question(question)
    scored = [(score_example(example, wanted), example) for example in CYPHER_EXAMPLES]
    selected = [
        example
        for score, example in sorted(scored, key=lambda item: item[0], reverse=True)
        if score > 0 and "generic" not in example["tags"]
    ][:2]
    return "\n\n".join(f"Question: {example['question']}\nCypher:\n{example['cypher']}" for example in selected[:2])


def score_example(example: dict, wanted: set[str]) -> int:
    """Score one Cypher example by tag overlap."""
    return len((example.get("tags") or set()) & wanted)


def example_tags_for_question(question: str) -> set[str]:
    """Infer lightweight tags used only for selecting Cypher examples."""
    return {
        tag
        for tag, terms in EXAMPLE_QUESTION_TAG_TERMS.items()
        if contains_any(question, terms)
    }
