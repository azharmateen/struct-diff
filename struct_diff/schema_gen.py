"""Auto-generate JSON Schema from sample data."""

import re
from typing import Any, Optional


# Pattern detectors
PATTERNS = {
    "email": re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
    "uri": re.compile(r"^https?://[^\s]+$"),
    "uuid": re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I),
    "date": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "date-time": re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"),
    "ipv4": re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"),
    "hostname": re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$"),
}

# Enum detection threshold
ENUM_MAX_UNIQUE = 10
ENUM_MIN_SAMPLES = 3


def generate_schema(data: Any, title: str = "Generated Schema",
                    detect_patterns: bool = True,
                    detect_enums: bool = True,
                    infer_required: bool = True) -> dict:
    """Generate a JSON Schema from sample data.

    If data is a list, analyzes all items to build a comprehensive schema.
    If data is a dict, generates schema for that single object.
    """
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": title,
    }

    if isinstance(data, list) and data:
        # Analyze all items in array
        items_schema = _merge_schemas(
            [_infer_type(item, detect_patterns) for item in data],
            detect_enums=detect_enums,
        )
        if infer_required and isinstance(data[0], dict):
            items_schema = _add_required(items_schema, data)

        schema["type"] = "array"
        schema["items"] = items_schema
    else:
        schema.update(_infer_type(data, detect_patterns))
        if infer_required and isinstance(data, dict):
            schema = _add_required(schema, [data])

    return schema


def _infer_type(value: Any, detect_patterns: bool = True) -> dict:
    """Infer JSON Schema type for a single value."""
    if value is None:
        return {"type": "null"}

    if isinstance(value, bool):
        return {"type": "boolean"}

    if isinstance(value, int):
        return {"type": "integer"}

    if isinstance(value, float):
        return {"type": "number"}

    if isinstance(value, str):
        schema = {"type": "string"}
        if detect_patterns:
            fmt = _detect_format(value)
            if fmt:
                schema["format"] = fmt
        if len(value) > 0:
            # Add example for documentation
            schema["examples"] = [value]
        return schema

    if isinstance(value, list):
        if not value:
            return {"type": "array", "items": {}}

        item_schemas = [_infer_type(item, detect_patterns) for item in value]
        merged = _merge_schemas(item_schemas)
        return {"type": "array", "items": merged}

    if isinstance(value, dict):
        properties = {}
        for key, val in value.items():
            properties[key] = _infer_type(val, detect_patterns)

        return {
            "type": "object",
            "properties": properties,
        }

    return {}


def _detect_format(value: str) -> Optional[str]:
    """Detect string format from value."""
    for fmt, pattern in PATTERNS.items():
        if pattern.match(value):
            return fmt
    return None


def _merge_schemas(schemas: list[dict], detect_enums: bool = False) -> dict:
    """Merge multiple schemas into one that accepts all variants."""
    if not schemas:
        return {}

    if len(schemas) == 1:
        return schemas[0]

    # Group by type
    types = set()
    all_properties = {}
    all_formats = set()
    all_examples = []
    array_items = []

    for schema in schemas:
        t = schema.get("type")
        if t:
            types.add(t)

        if "format" in schema:
            all_formats.add(schema["format"])

        if "examples" in schema:
            all_examples.extend(schema["examples"])

        if "properties" in schema:
            for key, prop_schema in schema["properties"].items():
                if key not in all_properties:
                    all_properties[key] = []
                all_properties[key].append(prop_schema)

        if "items" in schema:
            array_items.append(schema["items"])

    # Build merged schema
    merged = {}

    if len(types) == 1:
        merged["type"] = types.pop()
    elif len(types) > 1:
        # Nullable handling
        if "null" in types and len(types) == 2:
            other = (types - {"null"}).pop()
            merged["type"] = [other, "null"]
        else:
            merged["type"] = sorted(types)

    if len(all_formats) == 1:
        merged["format"] = all_formats.pop()

    if all_properties:
        merged["properties"] = {}
        for key, prop_schemas in all_properties.items():
            merged["properties"][key] = _merge_schemas(prop_schemas, detect_enums)

    if array_items:
        merged["items"] = _merge_schemas(array_items, detect_enums)

    # Enum detection
    if detect_enums and all_examples:
        unique = list(set(all_examples))
        if (len(unique) <= ENUM_MAX_UNIQUE and
            len(all_examples) >= ENUM_MIN_SAMPLES and
            all(isinstance(v, str) for v in unique)):
            merged["enum"] = sorted(unique)
            merged.pop("examples", None)
        else:
            # Keep a few examples
            merged["examples"] = unique[:3]

    return merged


def _add_required(schema: dict, samples: list[dict]) -> dict:
    """Determine required fields based on presence across samples."""
    if "properties" not in schema:
        return schema

    all_keys = set(schema["properties"].keys())
    required = []

    for key in all_keys:
        # Required if present in all samples and never None
        if all(key in sample and sample[key] is not None
               for sample in samples if isinstance(sample, dict)):
            required.append(key)

    if required:
        schema["required"] = sorted(required)

    return schema


def schema_to_markdown(schema: dict, indent: int = 0) -> str:
    """Convert JSON Schema to readable markdown documentation."""
    lines = []
    prefix = "  " * indent

    if "title" in schema:
        lines.append(f"{'#' * min(indent + 1, 4)} {schema['title']}")
        lines.append("")

    schema_type = schema.get("type", "any")
    if isinstance(schema_type, list):
        schema_type = " | ".join(schema_type)

    if schema_type == "object" and "properties" in schema:
        required = set(schema.get("required", []))
        lines.append(f"{prefix}| Field | Type | Required | Format |")
        lines.append(f"{prefix}|-------|------|----------|--------|")

        for key, prop in schema["properties"].items():
            ptype = prop.get("type", "any")
            if isinstance(ptype, list):
                ptype = " | ".join(ptype)
            fmt = prop.get("format", "")
            req = "Yes" if key in required else "No"
            lines.append(f"{prefix}| `{key}` | {ptype} | {req} | {fmt} |")

    elif schema_type == "array" and "items" in schema:
        lines.append(f"{prefix}Array of:")
        lines.append(schema_to_markdown(schema["items"], indent + 1))

    if "enum" in schema:
        values = ", ".join(f"`{v}`" for v in schema["enum"])
        lines.append(f"{prefix}Enum values: {values}")

    return "\n".join(lines)
