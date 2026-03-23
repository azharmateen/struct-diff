"""Semantic diff engine: compare JSON/YAML structures ignoring key order."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ChangeType(Enum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    TYPE_CHANGED = "type_changed"
    ARRAY_ADDED = "array_item_added"
    ARRAY_REMOVED = "array_item_removed"


@dataclass
class Change:
    path: str
    change_type: ChangeType
    old_value: Any = None
    new_value: Any = None
    old_type: Optional[str] = None
    new_type: Optional[str] = None

    def __str__(self):
        if self.change_type == ChangeType.ADDED:
            return f"+ {self.path}: {_format_value(self.new_value)}"
        elif self.change_type == ChangeType.REMOVED:
            return f"- {self.path}: {_format_value(self.old_value)}"
        elif self.change_type == ChangeType.CHANGED:
            return f"~ {self.path}: {_format_value(self.old_value)} -> {_format_value(self.new_value)}"
        elif self.change_type == ChangeType.TYPE_CHANGED:
            return f"! {self.path}: type {self.old_type} -> {self.new_type}"
        elif self.change_type == ChangeType.ARRAY_ADDED:
            return f"+ {self.path}[]: {_format_value(self.new_value)}"
        elif self.change_type == ChangeType.ARRAY_REMOVED:
            return f"- {self.path}[]: {_format_value(self.old_value)}"
        return f"? {self.path}"


@dataclass
class DiffResult:
    changes: list[Change] = field(default_factory=list)

    @property
    def added(self) -> list[Change]:
        return [c for c in self.changes if c.change_type == ChangeType.ADDED]

    @property
    def removed(self) -> list[Change]:
        return [c for c in self.changes if c.change_type == ChangeType.REMOVED]

    @property
    def changed(self) -> list[Change]:
        return [c for c in self.changes if c.change_type in (ChangeType.CHANGED, ChangeType.TYPE_CHANGED)]

    @property
    def array_changes(self) -> list[Change]:
        return [c for c in self.changes if c.change_type in (ChangeType.ARRAY_ADDED, ChangeType.ARRAY_REMOVED)]

    @property
    def has_changes(self) -> bool:
        return len(self.changes) > 0

    @property
    def summary(self) -> dict[str, int]:
        result = {}
        for c in self.changes:
            key = c.change_type.value
            result[key] = result.get(key, 0) + 1
        return result


def semantic_diff(a: Any, b: Any, path: str = "$") -> DiffResult:
    """Compare two structures semantically, ignoring key ordering.

    Returns a DiffResult with all detected changes.
    """
    result = DiffResult()
    _diff_recursive(a, b, path, result)
    return result


def _diff_recursive(a: Any, b: Any, path: str, result: DiffResult):
    """Recursively compare two values."""
    # Type mismatch
    if type(a) != type(b):
        # Special case: int vs float comparison
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if a != b:
                result.changes.append(Change(
                    path=path, change_type=ChangeType.CHANGED,
                    old_value=a, new_value=b,
                ))
            return

        result.changes.append(Change(
            path=path, change_type=ChangeType.TYPE_CHANGED,
            old_value=a, new_value=b,
            old_type=type(a).__name__, new_type=type(b).__name__,
        ))
        return

    # Dict comparison (order-independent)
    if isinstance(a, dict):
        all_keys = set(a.keys()) | set(b.keys())
        for key in sorted(all_keys):
            child_path = f"{path}.{key}"
            if key not in a:
                result.changes.append(Change(
                    path=child_path, change_type=ChangeType.ADDED,
                    new_value=b[key],
                ))
            elif key not in b:
                result.changes.append(Change(
                    path=child_path, change_type=ChangeType.REMOVED,
                    old_value=a[key],
                ))
            else:
                _diff_recursive(a[key], b[key], child_path, result)
        return

    # Array comparison (by value matching, not index)
    if isinstance(a, list):
        _diff_arrays(a, b, path, result)
        return

    # Scalar comparison
    if a != b:
        result.changes.append(Change(
            path=path, change_type=ChangeType.CHANGED,
            old_value=a, new_value=b,
        ))


def _diff_arrays(a: list, b: list, path: str, result: DiffResult):
    """Compare arrays by value matching."""
    # For simple arrays of scalars, use set-like comparison
    if all(_is_scalar(x) for x in a) and all(_is_scalar(x) for x in b):
        a_set = set(_hashable(x) for x in a)
        b_set = set(_hashable(x) for x in b)

        for item in sorted(a_set - b_set, key=str):
            result.changes.append(Change(
                path=path, change_type=ChangeType.ARRAY_REMOVED,
                old_value=_unhashable(item),
            ))
        for item in sorted(b_set - a_set, key=str):
            result.changes.append(Change(
                path=path, change_type=ChangeType.ARRAY_ADDED,
                new_value=_unhashable(item),
            ))
        return

    # For arrays of objects, try to match by common identifier fields
    id_field = _find_id_field(a + b)

    if id_field:
        a_by_id = {item.get(id_field): item for item in a if isinstance(item, dict)}
        b_by_id = {item.get(id_field): item for item in b if isinstance(item, dict)}

        for key in sorted(set(a_by_id) | set(b_by_id), key=str):
            if key not in a_by_id:
                result.changes.append(Change(
                    path=f"{path}[{id_field}={key}]",
                    change_type=ChangeType.ARRAY_ADDED,
                    new_value=b_by_id[key],
                ))
            elif key not in b_by_id:
                result.changes.append(Change(
                    path=f"{path}[{id_field}={key}]",
                    change_type=ChangeType.ARRAY_REMOVED,
                    old_value=a_by_id[key],
                ))
            else:
                _diff_recursive(a_by_id[key], b_by_id[key],
                                f"{path}[{id_field}={key}]", result)
        return

    # Fallback: index-based comparison
    max_len = max(len(a), len(b))
    for i in range(max_len):
        child_path = f"{path}[{i}]"
        if i >= len(a):
            result.changes.append(Change(
                path=child_path, change_type=ChangeType.ARRAY_ADDED,
                new_value=b[i],
            ))
        elif i >= len(b):
            result.changes.append(Change(
                path=child_path, change_type=ChangeType.ARRAY_REMOVED,
                old_value=a[i],
            ))
        else:
            _diff_recursive(a[i], b[i], child_path, result)


def _find_id_field(items: list) -> Optional[str]:
    """Find a common identifier field in a list of dicts."""
    id_candidates = ["id", "_id", "name", "key", "slug", "code", "uuid"]
    dicts = [item for item in items if isinstance(item, dict)]
    if not dicts:
        return None

    for field in id_candidates:
        if all(field in d for d in dicts):
            values = [d[field] for d in dicts]
            # Check uniqueness within each source
            if len(values) == len(set(str(v) for v in values)):
                return field
    return None


def _is_scalar(v: Any) -> bool:
    return isinstance(v, (str, int, float, bool, type(None)))


def _hashable(v: Any) -> Any:
    if isinstance(v, (list, dict)):
        return str(v)
    return v


def _unhashable(v: Any) -> Any:
    return v


def _format_value(v: Any) -> str:
    if isinstance(v, str):
        if len(v) > 60:
            return f'"{v[:57]}..."'
        return f'"{v}"'
    if isinstance(v, dict):
        return f"{{{len(v)} keys}}"
    if isinstance(v, list):
        return f"[{len(v)} items]"
    return str(v)
