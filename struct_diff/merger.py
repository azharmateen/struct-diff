"""Deep merge for JSON/YAML structures."""

from enum import Enum
from typing import Any


class ConflictStrategy(Enum):
    FIRST_WINS = "first"      # Keep value from first (a)
    LAST_WINS = "last"        # Keep value from second (b)
    ARRAY_CONCAT = "concat"   # Concatenate arrays
    ARRAY_UNIQUE = "unique"   # Merge arrays, deduplicate


def deep_merge(a: Any, b: Any,
               strategy: ConflictStrategy = ConflictStrategy.LAST_WINS,
               array_strategy: ConflictStrategy = ConflictStrategy.LAST_WINS) -> Any:
    """Deep merge two structures.

    Args:
        a: First structure
        b: Second structure
        strategy: How to resolve scalar conflicts
        array_strategy: How to handle array merging

    Returns:
        Merged structure (new object, inputs not modified)
    """
    return _merge_recursive(a, b, strategy, array_strategy)


def _merge_recursive(a: Any, b: Any,
                     strategy: ConflictStrategy,
                     array_strategy: ConflictStrategy) -> Any:
    """Recursively merge two values."""
    # Both dicts: merge keys
    if isinstance(a, dict) and isinstance(b, dict):
        result = {}
        all_keys = set(a.keys()) | set(b.keys())

        for key in all_keys:
            if key in a and key in b:
                result[key] = _merge_recursive(a[key], b[key], strategy, array_strategy)
            elif key in a:
                result[key] = _deep_copy(a[key])
            else:
                result[key] = _deep_copy(b[key])

        return result

    # Both lists: use array strategy
    if isinstance(a, list) and isinstance(b, list):
        return _merge_arrays(a, b, array_strategy)

    # Scalar conflict: use strategy
    if strategy == ConflictStrategy.FIRST_WINS:
        return _deep_copy(a)
    else:
        return _deep_copy(b)


def _merge_arrays(a: list, b: list, strategy: ConflictStrategy) -> list:
    """Merge two arrays according to strategy."""
    if strategy == ConflictStrategy.ARRAY_CONCAT:
        return _deep_copy(a) + _deep_copy(b)

    if strategy == ConflictStrategy.ARRAY_UNIQUE:
        seen = set()
        result = []
        for item in a + b:
            key = _make_hashable(item)
            if key not in seen:
                seen.add(key)
                result.append(_deep_copy(item))
        return result

    if strategy == ConflictStrategy.FIRST_WINS:
        return _deep_copy(a)

    # LAST_WINS
    return _deep_copy(b)


def _deep_copy(value: Any) -> Any:
    """Simple deep copy for JSON-compatible structures."""
    if isinstance(value, dict):
        return {k: _deep_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_copy(v) for v in value]
    return value


def _make_hashable(value: Any) -> Any:
    """Make a value hashable for deduplication."""
    if isinstance(value, dict):
        return tuple(sorted((k, _make_hashable(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_make_hashable(v) for v in value)
    return value


def merge_files(paths: list[str],
                strategy: ConflictStrategy = ConflictStrategy.LAST_WINS,
                array_strategy: ConflictStrategy = ConflictStrategy.LAST_WINS) -> Any:
    """Merge multiple files sequentially."""
    from .converter import load_file

    if not paths:
        return {}

    result, _ = load_file(paths[0])
    for path in paths[1:]:
        data, _ = load_file(path)
        result = deep_merge(result, data, strategy, array_strategy)

    return result
