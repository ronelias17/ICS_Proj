from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class RelationshipSchema:
    """Structured graph relationship schema row."""

    source: str
    rel_type: str
    target: str
    description: str
    properties: tuple[str, ...] = ()

    @property
    def pattern(self) -> str:
        """Render this row as the Cypher pattern shown to the LLM."""
        return f"(:{self.source})-[:{self.rel_type}]->(:{self.target})"

    def endpoints(self) -> tuple[str, str]:
        """Return source and target labels."""
        return self.source, self.target

    def touches(self, labels: set[str]) -> bool:
        """Return true when either endpoint is in the selected labels."""
        return self.source in labels or self.target in labels


def rel(source: str, rel_type: str, target: str, description: str, properties: Sequence[str] = ()) -> RelationshipSchema:
    """Create a relationship schema row with normalized properties."""
    return RelationshipSchema(source, rel_type, target, description, tuple(properties))


NODE_SCHEMA = {
    "Institution": {
        "description": "The Ruppin Academic Center institution as a whole.",
        "properties": ["id", "name", "description"],
    },
    "Faculty": {
        "description": "Academic faculty or school that owns programs, policies, contacts, or fees.",
        "properties": ["id", "name", "description"],
    },
    "Program": {
        "description": "Degree-granting study program such as BA, BSc, BSN, MA, or MBA.",
        "properties": [
            "id",
            "name",
            "english_name",
            "degree_type",
            "duration",
            "credits",
            "study_days",
            "study_format",
            "tuition_type",
            "career_fields",
            "description",
        ],
    },
    "PreparatoryProgram": {
        "description": "Pre-academic or preparatory program that can prepare for later degree admission; not a degree program.",
        "properties": ["id", "name", "duration", "description"],
    },
    "AdmissionRequirement": {
        "description": "Requirement, eligibility route, threshold, or condition for being accepted into a program.",
        "properties": ["id", "name", "requirement_text", "description"],
    },
    "Fee": {
        "description": "Payment item such as tuition, deposit, registration fee, housing rent, or parking fee.",
        "properties": ["id", "name", "description"],
    },
    "Policy": {
        "description": "Rule, deadline, refund/cancellation condition, registration rule, payment rule, or document/submission rule.",
        "properties": ["id", "name", "rule_text", "deadline", "conditions", "covers", "description"],
    },
    "Scholarship": {
        "description": "Scholarship, grant, tuition benefit, or scholarship eligibility item.",
        "properties": ["id", "name", "condition", "description"],
    },
    "Specialization": {
        "description": "Official study track, concentration, or specialization within a program.",
        "properties": ["id", "name", "focus", "description"],
    },
    "Course": {
        "description": "Individual curriculum course or class.",
        "properties": ["id", "name", "description"],
    },
    "ContactPoint": {
        "description": "Office or named contact point with direct contact fields such as phone, email, WhatsApp, fax, or office hours.",
        "properties": [
            "id",
            "name",
            "purpose",
            "phone",
            "email",
            "whatsapp",
            "fax",
            "office_hours",
            "department",
            "description",
        ],
    },
    "Housing": {
        "description": "Student housing or dormitory as a whole.",
        "properties": ["id", "name", "location", "description"],
    },
    "HousingUnitType": {
        "description": "Specific dormitory apartment or unit type, such as studio, shared room, accessible apartment, or couple apartment.",
        "properties": ["id", "name", "occupants", "description"],
    },
    "Parking": {
        "description": "Parking facility, parking option, or parking arrangement.",
        "properties": ["id", "name", "location", "description"],
    },
    "Campus": {
        "description": "Campus or physical location.",
        "properties": ["id", "name", "address", "description"],
    },
    "StudentService": {
        "description": "Student service, support unit, sports activity, or campus-life service. Not a physical facility unless the graph evidence says so.",
        "properties": ["id", "name", "description"],
    },
}

ADMISSION_PROPS = [
    "requirement_type",
    "criteria_logic",
    "conditions",
    "deadline",
    "bagrut_average_min",
    "psychometric_min",
    "combined_score_min",
    "math_units",
    "math_grade_min",
    "physics_units",
    "physics_grade_min",
    "hebrew_score_min",
    "english_exam",
    "mimd_score_min",
    "matam_score_min",
    "gre_psychology_min",
    "engineer_exam_avg_min",
    "engineer_studies_avg_min",
    "degree_avg_min",
    "open_university_credits_min",
    "rule_text",
]

FEE_PROPS = [
    "amount_value",
    "display_amount",
    "currency",
    "amount_unit",
    "payment_context",
    "payment_condition",
    "discount_percent",
    "valid_until",
    "deadline",
    "conditions",
    "academic_year",
    "refund_fraction",
    "rule_text",
]

COURSE_PROPS = ["credits", "weekly_hours", "semester", "year", "required", "course_category", "course_type"]
HOUSING_PROPS = ["occupants", "monthly_rent", "monthly_total", "amount_value", "display_amount", "currency", "conditions"]
SCHOLARSHIP_PROPS = ["condition", "psychometric_min", "bagrut_min", "target_audience", "conditions", "rule_text"]
CONTACT_PROPS: list[str] = []
LOCATION_PROPS: list[str] = []

RELATIONSHIP_SCHEMA = (
    rel("Program", "BELONGS_TO_FACULTY", "Faculty", "Program ownership by an academic faculty."),
    rel("Program", "HAS_ADMISSION_REQUIREMENT", "AdmissionRequirement", "Admission requirement, eligibility route, threshold, or condition for program acceptance.", ADMISSION_PROPS),
    rel("Program", "HAS_FEE", "Fee", "Program-scoped payment, tuition, deposit, registration, or other fee.", FEE_PROPS),
    rel("Program", "HAS_POLICY", "Policy", "Program-scoped rule, deadline, refund/cancellation policy, payment rule, registration rule, or document/submission rule.", FEE_PROPS),
    rel("Program", "HAS_SCHOLARSHIP", "Scholarship", "Scholarship or tuition benefit available for a program.", SCHOLARSHIP_PROPS),
    rel("Program", "HAS_SPECIALIZATION", "Specialization", "Official tracks or specializations offered by a program."),
    rel("Program", "HAS_COURSE", "Course", "Individual courses in a program curriculum.", COURSE_PROPS),
    rel("Program", "HAS_CONTACT", "ContactPoint", "Program contact office or contact person/department.", CONTACT_PROPS),
    rel("Program", "LOCATED_AT", "Campus", "Program campus or physical study location.", LOCATION_PROPS),
    rel("Faculty", "HAS_FEE", "Fee", "Faculty-scoped payment or fee.", FEE_PROPS),
    rel("Faculty", "HAS_POLICY", "Policy", "Faculty-scoped rule, deadline, or policy.", FEE_PROPS),
    rel("Faculty", "HAS_CONTACT", "ContactPoint", "Faculty contact office or department.", CONTACT_PROPS),
    rel("Faculty", "LOCATED_AT", "Campus", "Faculty campus or physical location.", LOCATION_PROPS),
    rel("Institution", "HAS_FACULTY", "Faculty", "Academic faculty belonging to the institution."),
    rel("Institution", "HAS_CAMPUS", "Campus", "Campus belonging to the institution.", LOCATION_PROPS),
    rel("Institution", "HAS_CONTACT", "ContactPoint", "Institution-wide contact office or contact point.", CONTACT_PROPS),
    rel("Institution", "HAS_FEE", "Fee", "Institution-wide or generic payment/fee, such as general tuition, registration, or basic fee.", FEE_PROPS),
    rel("Institution", "HAS_POLICY", "Policy", "Institution-wide rule, deadline, payment/refund policy, registration policy, or document policy.", FEE_PROPS),
    rel("Institution", "HAS_SERVICE", "StudentService", "Student service or activity offered by the institution."),
    rel("Institution", "HAS_HOUSING", "Housing", "Student housing or dormitory offered by the institution."),
    rel("Institution", "HAS_PARKING", "Parking", "Parking option offered by the institution."),
    rel("Housing", "HAS_HOUSING_UNIT_TYPE", "HousingUnitType", "Apartment or room type offered in student housing.", HOUSING_PROPS),
    rel("Housing", "HAS_FEE", "Fee", "Housing-scoped payment or fee.", FEE_PROPS),
    rel("Housing", "HAS_CONTACT", "ContactPoint", "Housing office or housing contact point.", CONTACT_PROPS),
    rel("Housing", "HAS_PARKING", "Parking", "Parking option available for dormitory residents."),
    rel("Housing", "LOCATED_AT", "Campus", "Housing campus or physical location.", LOCATION_PROPS),
    rel("HousingUnitType", "HAS_POLICY", "Policy", "Rule or condition specific to a housing unit type.", FEE_PROPS),
    rel("Parking", "HAS_FEE", "Fee", "Parking price, subscription, or payment.", FEE_PROPS),
    rel("Parking", "HAS_POLICY", "Policy", "Parking rule, subscription rule, or parking condition.", FEE_PROPS),
    rel("Parking", "LOCATED_AT", "Campus", "Physical location of a parking facility.", LOCATION_PROPS),
    rel("Parking", "HAS_CONTACT", "ContactPoint", "Parking contact point or operator contact.", CONTACT_PROPS),
    rel("PreparatoryProgram", "HAS_ADMISSION_REQUIREMENT", "AdmissionRequirement", "Admission, completion, or continuation requirement for a preparatory program.", ADMISSION_PROPS),
    rel("PreparatoryProgram", "HAS_FEE", "Fee", "Preparatory-program payment, tuition, deposit, or fee.", FEE_PROPS),
    rel("PreparatoryProgram", "HAS_POLICY", "Policy", "Preparatory-program rule, deadline, registration rule, or payment/refund policy.", FEE_PROPS),
    rel("PreparatoryProgram", "HAS_CONTACT", "ContactPoint", "Preparatory-program contact office or contact point.", CONTACT_PROPS),
    rel("PreparatoryProgram", "HAS_SCHOLARSHIP", "Scholarship", "Scholarship or benefit for a preparatory program.", SCHOLARSHIP_PROPS),
    rel("PreparatoryProgram", "PREPARES_FOR", "Program", "Degree program that a preparatory program can prepare students for."),
    rel("Program", "RECOGNIZES_COURSE_FOR_EXEMPTION", "Course", "Course recognized for exemption, prior-study credit, or an alternative admission/exemption route; not a normal curriculum listing.", COURSE_PROPS),
)
