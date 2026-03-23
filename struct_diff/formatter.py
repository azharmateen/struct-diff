"""Output formatters for diff results."""

import json
from typing import Any

from .differ import Change, ChangeType, DiffResult


def format_colored_terminal(result: DiffResult) -> str:
    """Format diff with ANSI color codes for terminal output."""
    if not result.has_changes:
        return "\033[32mNo differences found.\033[0m"

    lines = []
    lines.append(f"\033[1mFound {len(result.changes)} change(s):\033[0m")
    lines.append("")

    for change in result.changes:
        if change.change_type in (ChangeType.ADDED, ChangeType.ARRAY_ADDED):
            lines.append(f"\033[32m  + {change.path}: {_format_value(change.new_value)}\033[0m")
        elif change.change_type in (ChangeType.REMOVED, ChangeType.ARRAY_REMOVED):
            lines.append(f"\033[31m  - {change.path}: {_format_value(change.old_value)}\033[0m")
        elif change.change_type == ChangeType.CHANGED:
            lines.append(f"\033[33m  ~ {change.path}:\033[0m")
            lines.append(f"\033[31m      - {_format_value(change.old_value)}\033[0m")
            lines.append(f"\033[32m      + {_format_value(change.new_value)}\033[0m")
        elif change.change_type == ChangeType.TYPE_CHANGED:
            lines.append(f"\033[35m  ! {change.path}: type {change.old_type} -> {change.new_type}\033[0m")

    lines.append("")
    summary = result.summary
    parts = []
    if "added" in summary:
        parts.append(f"\033[32m+{summary['added']}\033[0m")
    if "removed" in summary:
        parts.append(f"\033[31m-{summary['removed']}\033[0m")
    if "changed" in summary:
        parts.append(f"\033[33m~{summary['changed']}\033[0m")
    if "type_changed" in summary:
        parts.append(f"\033[35m!{summary['type_changed']}\033[0m")

    lines.append(f"Summary: {', '.join(parts)}")
    return "\n".join(lines)


def format_json_patch(result: DiffResult) -> list[dict]:
    """Generate RFC 6902 JSON Patch operations."""
    ops = []

    for change in result.changes:
        # Convert dot-path to JSON Pointer
        pointer = _path_to_pointer(change.path)

        if change.change_type == ChangeType.ADDED:
            ops.append({"op": "add", "path": pointer, "value": change.new_value})
        elif change.change_type == ChangeType.REMOVED:
            ops.append({"op": "remove", "path": pointer})
        elif change.change_type in (ChangeType.CHANGED, ChangeType.TYPE_CHANGED):
            ops.append({"op": "replace", "path": pointer, "value": change.new_value})
        elif change.change_type == ChangeType.ARRAY_ADDED:
            ops.append({"op": "add", "path": pointer + "/-", "value": change.new_value})
        elif change.change_type == ChangeType.ARRAY_REMOVED:
            ops.append({"op": "remove", "path": pointer + "/0",
                         "value": change.old_value})  # Note: index approximate

    return ops


def format_markdown_table(result: DiffResult) -> str:
    """Format diff as a markdown table."""
    if not result.has_changes:
        return "No differences found."

    lines = []
    lines.append("| Path | Change | Old Value | New Value |")
    lines.append("|------|--------|-----------|-----------|")

    for change in result.changes:
        change_type = change.change_type.value.replace("_", " ").title()
        old = _escape_md(_format_value(change.old_value)) if change.old_value is not None else ""
        new = _escape_md(_format_value(change.new_value)) if change.new_value is not None else ""
        path = f"`{change.path}`"
        lines.append(f"| {path} | {change_type} | {old} | {new} |")

    return "\n".join(lines)


def format_html_side_by_side(result: DiffResult, a: Any, b: Any) -> str:
    """Generate HTML side-by-side diff view."""
    a_json = json.dumps(a, indent=2, ensure_ascii=False, default=str)
    b_json = json.dumps(b, indent=2, ensure_ascii=False, default=str)

    # Build change index by line
    changed_paths = {c.path for c in result.changes}

    html = """<!DOCTYPE html>
<html>
<head>
<style>
body { font-family: monospace; margin: 0; padding: 16px; background: #1e1e1e; color: #d4d4d4; }
.container { display: flex; gap: 16px; }
.panel { flex: 1; background: #252526; border-radius: 8px; overflow: hidden; }
.panel-header { padding: 8px 16px; background: #333; font-weight: bold; font-size: 14px; }
.panel-header.left { color: #f85149; }
.panel-header.right { color: #3fb950; }
pre { padding: 16px; margin: 0; white-space: pre-wrap; font-size: 13px; line-height: 1.5; overflow-x: auto; }
.added { background: #0d2818; }
.removed { background: #2d0f0f; }
.changed { background: #2d2000; }
.summary { padding: 16px; background: #252526; border-radius: 8px; margin-top: 16px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; margin: 0 4px; font-size: 12px; }
.badge-add { background: #0d2818; color: #3fb950; }
.badge-remove { background: #2d0f0f; color: #f85149; }
.badge-change { background: #2d2000; color: #d29922; }
</style>
</head>
<body>
<div class="container">
  <div class="panel">
    <div class="panel-header left">Original (A)</div>
    <pre>""" + _escape_html(a_json) + """</pre>
  </div>
  <div class="panel">
    <div class="panel-header right">Modified (B)</div>
    <pre>""" + _escape_html(b_json) + """</pre>
  </div>
</div>
<div class="summary">
  <strong>Changes:</strong> """

    summary = result.summary
    badges = []
    if "added" in summary:
        badges.append(f'<span class="badge badge-add">+{summary["added"]} added</span>')
    if "removed" in summary:
        badges.append(f'<span class="badge badge-remove">-{summary["removed"]} removed</span>')
    changed_count = summary.get("changed", 0) + summary.get("type_changed", 0)
    if changed_count:
        badges.append(f'<span class="badge badge-change">~{changed_count} changed</span>')

    html += " ".join(badges)
    html += """
</div>
</body>
</html>"""

    return html


def _path_to_pointer(path: str) -> str:
    """Convert dot-notation path to JSON Pointer (RFC 6901)."""
    # Remove $ prefix
    if path.startswith("$"):
        path = path[1:]
    if not path:
        return ""

    # Convert dots to slashes, handle array indices
    parts = []
    for segment in path.split("."):
        if not segment:
            continue
        # Handle array indices like [0] or [id=abc]
        if "[" in segment:
            base, _, idx = segment.partition("[")
            if base:
                parts.append(base)
            idx = idx.rstrip("]")
            parts.append(idx)
        else:
            parts.append(segment)

    return "/" + "/".join(p.replace("~", "~0").replace("/", "~1") for p in parts)


def _format_value(v: Any) -> str:
    """Format a value for display."""
    if v is None:
        return "null"
    if isinstance(v, str):
        if len(v) > 80:
            return f'"{v[:77]}..."'
        return f'"{v}"'
    if isinstance(v, dict):
        s = json.dumps(v, ensure_ascii=False, default=str)
        if len(s) > 80:
            return s[:77] + "..."
        return s
    if isinstance(v, list):
        s = json.dumps(v, ensure_ascii=False, default=str)
        if len(s) > 80:
            return s[:77] + "..."
        return s
    return str(v)


def _escape_md(s: str) -> str:
    """Escape markdown special characters."""
    return s.replace("|", "\\|").replace("\n", " ")


def _escape_html(s: str) -> str:
    """Escape HTML special characters."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
