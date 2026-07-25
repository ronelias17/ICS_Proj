from __future__ import annotations

from graphrag.formatting import field_maps
from graphrag.formatting import graph_fact_rendering as fact_rendering
from graphrag.formatting import graph_fact_selection as fact_selection
from graphrag.formatting import value_display


def format_graph_facts(graph_rows: list[dict], question: str = "") -> list[str]:
    """Convert graph result rows into readable answer facts without debug fields."""
    facts = []
    normalized_rows = [fact_selection.normalize_row_aliases(row) for row in graph_rows]
    selected_rows = fact_selection.select_graph_fact_rows(normalized_rows, question)
    for index, row in enumerate(fact_selection.group_graph_rows(selected_rows), start=1):
        lines = render_graph_fact_lines(row)
        if lines:
            facts.append(f"{index}. " + "\n   ".join(lines))
    return facts


def render_graph_fact_lines(row: dict) -> list[str]:
    """Render one graph row into fact lines."""
    lines: list[str] = []
    seen: set[str] = set()
    seen_values: list[str] = []
    edge = fact_rendering.edge_shape_for_row(row)
    if edge:
        fact_rendering.append_edge_lines(lines, row, edge, seen=seen, seen_values=seen_values)
        return lines
    fact_rendering.append_amount_line(lines, row, indent="", seen=seen, seen_values=seen_values)
    relation = fact_rendering.relation_label_for_row(row)
    relation_inserted = False
    for key, value in row.items():
        if key in field_maps.AMOUNT_KEYS and value_display.any_amount_value(row):
            continue
        fact_rendering.append_value_lines(lines, key, value, indent="", seen=seen, seen_values=seen_values)
        if not relation_inserted and relation and key in {"program", "program_name", "owner", "housing", "parking", "name"}:
            fact_rendering.append_value_lines(lines, "relation", relation, indent="", seen=seen, seen_values=seen_values)
            relation_inserted = True
    return lines
