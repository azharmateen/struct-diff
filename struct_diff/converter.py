"""Convert between JSON, YAML, and TOML formats."""

import json
from pathlib import Path
from typing import Any, Optional

import yaml


def load_file(filepath: str) -> tuple[Any, str]:
    """Load a JSON, YAML, or TOML file. Returns (data, format)."""
    path = Path(filepath)
    ext = path.suffix.lower()
    content = path.read_text(encoding="utf-8")

    if ext in (".json",):
        return json.loads(content), "json"
    elif ext in (".yaml", ".yml"):
        return yaml.safe_load(content), "yaml"
    elif ext in (".toml",):
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                raise ImportError("Install tomli for TOML support: pip install tomli")
        return tomllib.loads(content), "toml"
    else:
        # Try JSON first, then YAML
        try:
            return json.loads(content), "json"
        except json.JSONDecodeError:
            return yaml.safe_load(content), "yaml"


def dump_data(data: Any, fmt: str, indent: int = 2) -> str:
    """Serialize data to a format string."""
    if fmt == "json":
        return json.dumps(data, indent=indent, ensure_ascii=False, default=str)
    elif fmt == "yaml":
        return yaml.dump(data, default_flow_style=False, allow_unicode=True,
                         sort_keys=False)
    elif fmt == "toml":
        try:
            import tomli_w
        except ImportError:
            raise ImportError("Install tomli-w for TOML output: pip install tomli-w")
        return tomli_w.dumps(data)
    else:
        raise ValueError(f"Unsupported format: {fmt}. Use json, yaml, or toml.")


def convert(input_path: str, output_format: str, output_path: Optional[str] = None) -> str:
    """Convert a file between formats.

    Args:
        input_path: Path to input file
        output_format: Target format (json, yaml, toml)
        output_path: Optional output path (default: input with new extension)

    Returns:
        The output file path
    """
    data, source_format = load_file(input_path)
    result = dump_data(data, output_format)

    if output_path is None:
        ext_map = {"json": ".json", "yaml": ".yaml", "toml": ".toml"}
        stem = Path(input_path).stem
        parent = Path(input_path).parent
        output_path = str(parent / f"{stem}{ext_map[output_format]}")

    Path(output_path).write_text(result, encoding="utf-8")
    return output_path


def detect_format(filepath: str) -> str:
    """Detect file format from extension."""
    ext = Path(filepath).suffix.lower()
    format_map = {
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
    }
    return format_map.get(ext, "json")
