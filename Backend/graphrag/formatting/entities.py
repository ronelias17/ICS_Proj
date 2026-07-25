from __future__ import annotations

from graphrag.formatting import field_maps
from graphrag.formatting import value_display


def format_selected_entities(entities: list[dict]) -> list[str]:
    """Format selected entity summaries for the final answer prompt."""
    formatted = []
    for index, entity in enumerate(entities[:3], start=1):
        label = entity.get("label") or "Entity"
        properties = entity.get("properties") or {}
        fields = field_maps.ENTITY_PUBLIC_FIELDS.get(label) or list(properties)
        lines = []
        name = properties.get("name") or ""
        if name:
            lines.append(f"{label}: {name}")
        else:
            lines.append(label)
        for key in fields:
            if key == "name":
                continue
            value = properties.get(key)
            if value in (None, "", [], {}):
                continue
            if key == "description" and len(str(value)) > 220:
                continue
            label_text = field_maps.DISPLAY_KEYS.get(key, key)
            lines.append(f"{label_text}: {value_display.normalize_display_value(key, value)}")
        formatted.append(f"{index}. " + "\n   ".join(lines))
    return formatted
