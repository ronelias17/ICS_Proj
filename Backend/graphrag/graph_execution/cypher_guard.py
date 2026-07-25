from __future__ import annotations

import re
from dataclasses import dataclass


DISALLOWED_PATTERN_TEXTS = (
    r"\bCREATE\b",
    r"\bMERGE\b",
    r"\bDELETE\b",
    r"\bDETACH\b",
    r"\bSET\b",
    r"\bREMOVE\b",
    r"\bDROP\b",
    r"\bLOAD\s+CSV\b",
    r"\bCALL\s+DBMS\b",
    r"\bCALL\s+APOC\b",
)

ALLOWED_STARTS = ("MATCH", "OPTIONAL MATCH", "WITH", "RETURN", "UNWIND")
DISALLOWED_PATTERNS = tuple(re.compile(pattern, re.IGNORECASE) for pattern in DISALLOWED_PATTERN_TEXTS)
LIMIT_RE = re.compile(r"\bLIMIT\b", re.IGNORECASE)
PROPERTIES_R_RE = re.compile(r"properties\s*\(\s*r\s*\)", re.IGNORECASE)
R_FIELD_RE = re.compile(r"\br\.[A-Za-z_][A-Za-z0-9_]*")
RELATIONSHIP_R_BINDING_RE = re.compile(r"\[\s*r\s*(?::|\]|\{)", re.IGNORECASE)
NODE_R_BINDING_RE = re.compile(r"\(\s*r\s*(?::|\)|\{)", re.IGNORECASE)
ANONYMOUS_OUTGOING_REL_RE = re.compile(r"-\[\s*:(\w+)\s*\]->")
ANONYMOUS_INCOMING_REL_RE = re.compile(r"<-\[\s*:(\w+)\s*\]-")
PROPERTIES_FIELD_ACCESS_RE = re.compile(
    r"properties\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
RETURN_REPAIR_RE = re.compile(r"\bRETURN\b\s+(.+?)(\bORDER\s+BY\b.+|\bLIMIT\b.+|$)", re.IGNORECASE | re.DOTALL)
RETURN_COLUMNS_RE = re.compile(r"\bRETURN\b(.+?)(?:\bORDER\s+BY\b|\bLIMIT\b|$)", re.IGNORECASE | re.DOTALL)
RETURN_ALIAS_RE = re.compile(r"\bAS\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
RETURN_ALIAS_AT_END_RE = re.compile(r"\bAS\s+([A-Za-z_][\w]*)\s*$", re.IGNORECASE)
RAW_RETURN_ALIAS_AT_END_RE = re.compile(r"\bAS\s+[A-Za-z_][\w]*\s*$", re.IGNORECASE)
SIMPLE_PROPERTY_FIELD_RE = re.compile(r"([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)")
NODE_LABEL_RE = re.compile(r"\(([A-Za-z_][\w]*)\s*:\s*([A-Za-z][\w]*)")
UNION_RE = re.compile(r"\bUNION(?:\s+ALL)?\b", re.IGNORECASE)
SNAKE_CASE_ALIAS_RE = re.compile(r"[a-z][a-z0-9_]*")

LABEL_RETURN_ALIASES = {
    "Program": "program",
    "AdmissionRequirement": "requirement",
    "Fee": "fee",
    "Policy": "policy",
    "Course": "course",
    "Specialization": "specialization",
    "Housing": "housing",
    "HousingUnitType": "unit_type",
    "Parking": "parking",
    "Campus": "campus",
    "ContactPoint": "contact",
    "StudentService": "service",
    "Faculty": "faculty",
    "Institution": "institution",
}


@dataclass
class CypherGuardResult:
    """Safety check result for generated Cypher."""

    ok: bool
    cypher: str
    reason: str = ""
    repaired: bool = False


def ensure_limit(cypher: str, default_limit: int = 25) -> str:
    """Append a conservative LIMIT if the generated query omitted one."""
    if LIMIT_RE.search(cypher):
        return cypher.strip()
    return f"{cypher.strip()}\nLIMIT {default_limit}"


def validate_cypher(cypher: str) -> CypherGuardResult:
    """Reject write/admin Cypher and allow only read-style query starts."""
    cleaned = normalize_cypher(cypher)
    if not cleaned:
        return CypherGuardResult(False, "", "empty_cypher")
    if has_unquoted_semicolon(cleaned):
        return CypherGuardResult(False, cleaned, "multiple_statements_not_allowed")
    if has_invalid_union(cleaned):
        return CypherGuardResult(False, cleaned, "invalid_union_columns")
    cleaned, repaired, repair_error = apply_repairs(cleaned)
    if repair_error:
        return CypherGuardResult(False, cleaned, repair_error)
    if has_invalid_return_alias_style(cleaned):
        return CypherGuardResult(False, cleaned, "invalid_return_alias_style")
    upper = cleaned.upper()
    if not upper.startswith(ALLOWED_STARTS):
        return CypherGuardResult(False, cleaned, "query_must_start_with_read_clause")
    for pattern in DISALLOWED_PATTERNS:
        if pattern.search(cleaned):
            return CypherGuardResult(False, cleaned, f"disallowed_pattern:{pattern.pattern}")
    return CypherGuardResult(True, ensure_limit(cleaned), "", repaired=repaired)


def normalize_cypher(cypher: str) -> str:
    """Normalize model output before validation."""
    return cypher.strip().rstrip(";").strip()


def apply_repairs(cypher: str) -> tuple[str, bool, str]:
    """Apply safe repairs and return the repaired query plus an optional error."""
    repaired = False
    repaired_cypher = repair_properties_function_property_access(cypher)
    if repaired_cypher != cypher:
        cypher = repaired_cypher
        repaired = True
    if uses_properties_r_without_binding(cypher):
        repaired_cypher = repair_properties_r_relationship(cypher)
        if repaired_cypher == cypher:
            return cypher, repaired, "properties_r_without_relationship_binding"
        cypher = repaired_cypher
        repaired = True
    if uses_r_property_without_binding(cypher):
        repaired_cypher = repair_properties_r_relationship(cypher)
        if repaired_cypher == cypher:
            return cypher, repaired, "r_property_without_relationship_binding"
        cypher = repaired_cypher
        repaired = True
    repaired_cypher = repair_return_aliases(cypher)
    if repaired_cypher != cypher:
        cypher = repaired_cypher
        repaired = True
    return cypher, repaired, ""


def has_unquoted_semicolon(text: str) -> bool:
    """Return true when a semicolon appears outside quoted strings."""
    in_quote = False
    escape = False
    for char in text:
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_quote = not in_quote
            continue
        if char == ";" and not in_quote:
            return True
    return False


def uses_properties_r_without_binding(cypher: str) -> bool:
    """Detect properties(r) when no relationship variable named r is bound."""
    if not PROPERTIES_R_RE.search(cypher):
        return False
    return not RELATIONSHIP_R_BINDING_RE.search(cypher)


def uses_r_property_without_binding(cypher: str) -> bool:
    """Detect r.field usage when no relationship variable named r is bound."""
    if not R_FIELD_RE.search(cypher):
        return False
    if RELATIONSHIP_R_BINDING_RE.search(cypher):
        return False
    return not NODE_R_BINDING_RE.search(cypher)


def repair_properties_r_relationship(cypher: str) -> str:
    """Bind the first anonymous relationship as r when properties(r) is returned."""
    outgoing = ANONYMOUS_OUTGOING_REL_RE.sub(r"-[r:\1]->", cypher, count=1)
    if outgoing != cypher:
        return outgoing
    incoming = ANONYMOUS_INCOMING_REL_RE.sub(r"<-[r:\1]-", cypher, count=1)
    return incoming


def repair_properties_function_property_access(cypher: str) -> str:
    """Rewrite properties(r).field to r.field for ORDER BY / WHERE / CASE-safe property access."""
    return PROPERTIES_FIELD_ACCESS_RE.sub(r"\1.\2", cypher)


def repair_return_aliases(cypher: str) -> str:
    """Add semantic aliases for simple returned property expressions."""
    variable_aliases = inferred_variable_aliases(cypher)

    def repair_return(match: re.Match) -> str:
        return_body = match.group(1)
        suffix = match.group(2) or ""
        expressions = split_return_expressions(return_body)
        repaired = [repair_return_expression(expression, variable_aliases) for expression in expressions]
        return "RETURN " + ", ".join(repaired) + (" " + suffix.strip() if suffix.strip() else "")

    return RETURN_REPAIR_RE.sub(repair_return, cypher)


def has_invalid_return_alias_style(cypher: str) -> bool:
    """Reject RETURN aliases that are not lowercase snake_case."""
    aliases = RETURN_ALIAS_RE.findall(cypher or "")
    return any(not SNAKE_CASE_ALIAS_RE.fullmatch(alias) for alias in aliases)


def repair_return_expression(expression: str, variable_aliases: dict[str, str]) -> str:
    """Repair one RETURN expression when it is a simple variable.property field."""
    expression = expression.strip()
    alias_match = RETURN_ALIAS_AT_END_RE.search(expression)
    raw_expression = RAW_RETURN_ALIAS_AT_END_RE.sub("", expression).strip()
    field_match = SIMPLE_PROPERTY_FIELD_RE.fullmatch(raw_expression)
    if not field_match:
        return expression
    variable, field_name = field_match.groups()
    semantic_alias = variable_aliases.get(variable) if field_name == "name" else field_name
    if not semantic_alias:
        return expression
    current_alias = alias_match.group(1).lower() if alias_match else ""
    if current_alias == semantic_alias:
        return expression
    if field_name != "name" and current_alias:
        return expression
    if current_alias and current_alias not in {f"{semantic_alias}_name", "name"}:
        return expression
    return f"{raw_expression} AS {semantic_alias}"


def inferred_variable_aliases(cypher: str) -> dict[str, str]:
    """Infer semantic aliases from node labels in MATCH patterns."""
    aliases = {}
    for variable, label in NODE_LABEL_RE.findall(cypher):
        if label in LABEL_RETURN_ALIASES:
            aliases[variable] = LABEL_RETURN_ALIASES[label]
    return aliases


def has_invalid_union(cypher: str) -> bool:
    """Return true when UNION branches have different RETURN column names."""
    if not UNION_RE.search(cypher):
        return False
    branches = UNION_RE.split(cypher)
    returns = [return_columns(branch) for branch in branches]
    if any(not columns for columns in returns):
        return True
    return len({tuple(columns) for columns in returns}) > 1


def return_columns(branch: str) -> list[str]:
    """Extract rough RETURN column names from one Cypher branch."""
    match = RETURN_COLUMNS_RE.search(branch)
    if not match:
        return []
    columns = []
    for expression in split_return_expressions(match.group(1)):
        alias = RETURN_ALIAS_AT_END_RE.search(expression)
        if alias:
            columns.append(alias.group(1).lower())
            continue
        columns.append(expression.strip().lower())
    return columns


def split_return_expressions(text: str) -> list[str]:
    """Split RETURN expressions on top-level commas."""
    parts = []
    current = []
    depth = 0
    quote = ""
    for char in text:
        if quote:
            current.append(char)
            if char == quote:
                quote = ""
            continue
        if char in {"'", '"'}:
            quote = char
            current.append(char)
            continue
        if char == "(":
            depth += 1
        elif char == ")" and depth:
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current).strip())
    return [part for part in parts if part]
