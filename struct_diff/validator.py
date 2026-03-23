"""Validate JSON/YAML against JSON Schema with human-readable errors."""

import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ValidationError:
    path: str
    message: str
    expected: Optional[str] = None
    got: Optional[str] = None

    def __str__(self):
        parts = [f"  {self.path}: {self.message}"]
        if self.expected:
            parts.append(f"    expected: {self.expected}")
        if self.got:
            parts.append(f"    got: {self.got}")
        return "\n".join(parts)


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    def summary(self) -> str:
        if self.valid:
            return "Valid"
        return f"Invalid: {self.error_count} error(s)\n" + "\n".join(str(e) for e in self.errors)


def validate(data: Any, schema: dict, path: str = "$") -> ValidationResult:
    """Validate data against a JSON Schema.

    Supports: type, required, properties, items, enum, format,
    minimum, maximum, minLength, maxLength, pattern, minItems, maxItems.
    """
    errors = []
    _validate_recursive(data, schema, path, errors)
    return ValidationResult(valid=len(errors) == 0, errors=errors)


def _validate_recursive(data: Any, schema: dict, path: str, errors: list):
    """Recursively validate data against schema."""
    if not schema:
        return

    # Type validation
    expected_type = schema.get("type")
    if expected_type:
        if not _check_type(data, expected_type):
            errors.append(ValidationError(
                path=path,
                message="Type mismatch",
                expected=str(expected_type),
                got=type(data).__name__,
            ))
            return  # Stop checking if type is wrong

    # Enum validation
    if "enum" in schema:
        if data not in schema["enum"]:
            errors.append(ValidationError(
                path=path,
                message="Value not in enum",
                expected=f"one of {schema['enum']}",
                got=str(data),
            ))

    # String validations
    if isinstance(data, str):
        if "minLength" in schema and len(data) < schema["minLength"]:
            errors.append(ValidationError(
                path=path,
                message=f"String too short (min {schema['minLength']})",
                expected=f">= {schema['minLength']} chars",
                got=f"{len(data)} chars",
            ))
        if "maxLength" in schema and len(data) > schema["maxLength"]:
            errors.append(ValidationError(
                path=path,
                message=f"String too long (max {schema['maxLength']})",
                expected=f"<= {schema['maxLength']} chars",
                got=f"{len(data)} chars",
            ))
        if "pattern" in schema:
            if not re.match(schema["pattern"], data):
                errors.append(ValidationError(
                    path=path,
                    message="Pattern mismatch",
                    expected=f"matches /{schema['pattern']}/",
                    got=f'"{data}"',
                ))
        if "format" in schema:
            _validate_format(data, schema["format"], path, errors)

    # Number validations
    if isinstance(data, (int, float)) and not isinstance(data, bool):
        if "minimum" in schema and data < schema["minimum"]:
            errors.append(ValidationError(
                path=path,
                message=f"Value below minimum",
                expected=f">= {schema['minimum']}",
                got=str(data),
            ))
        if "maximum" in schema and data > schema["maximum"]:
            errors.append(ValidationError(
                path=path,
                message=f"Value above maximum",
                expected=f"<= {schema['maximum']}",
                got=str(data),
            ))

    # Object validations
    if isinstance(data, dict):
        # Required fields
        required = schema.get("required", [])
        for field in required:
            if field not in data:
                errors.append(ValidationError(
                    path=f"{path}.{field}",
                    message="Required field missing",
                ))

        # Properties
        properties = schema.get("properties", {})
        for key, prop_schema in properties.items():
            if key in data:
                _validate_recursive(data[key], prop_schema, f"{path}.{key}", errors)

        # Additional properties
        if schema.get("additionalProperties") is False:
            extra = set(data.keys()) - set(properties.keys())
            for key in extra:
                errors.append(ValidationError(
                    path=f"{path}.{key}",
                    message="Additional property not allowed",
                ))

    # Array validations
    if isinstance(data, list):
        if "minItems" in schema and len(data) < schema["minItems"]:
            errors.append(ValidationError(
                path=path,
                message=f"Array too short",
                expected=f">= {schema['minItems']} items",
                got=f"{len(data)} items",
            ))
        if "maxItems" in schema and len(data) > schema["maxItems"]:
            errors.append(ValidationError(
                path=path,
                message=f"Array too long",
                expected=f"<= {schema['maxItems']} items",
                got=f"{len(data)} items",
            ))

        items_schema = schema.get("items", {})
        if items_schema:
            for i, item in enumerate(data):
                _validate_recursive(item, items_schema, f"{path}[{i}]", errors)


def _check_type(value: Any, expected: Any) -> bool:
    """Check if value matches expected JSON Schema type(s)."""
    if isinstance(expected, list):
        return any(_check_type(value, t) for t in expected)

    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }

    if expected not in type_map:
        return True  # Unknown type, allow

    expected_types = type_map[expected]

    # Special case: booleans should not match integer/number
    if expected in ("integer", "number") and isinstance(value, bool):
        return False

    return isinstance(value, expected_types)


def _validate_format(value: str, fmt: str, path: str, errors: list):
    """Validate string format."""
    format_patterns = {
        "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        "uri": r"^https?://",
        "uuid": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        "date": r"^\d{4}-\d{2}-\d{2}$",
        "date-time": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
        "ipv4": r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",
    }

    pattern = format_patterns.get(fmt)
    if pattern and not re.match(pattern, value, re.I):
        errors.append(ValidationError(
            path=path,
            message=f"Invalid {fmt} format",
            expected=fmt,
            got=f'"{value}"',
        ))
