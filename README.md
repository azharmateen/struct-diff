# struct-diff

[![Built with Claude Code](https://img.shields.io/badge/Built%20with-Claude%20Code-blue?logo=anthropic&logoColor=white)](https://claude.ai/code)


**Semantic JSON/YAML differ that ignores key ordering + auto-generates schemas.**

Compare configurations without false positives from key reordering. Generate schemas from samples. Merge configs with conflict resolution.

```
pip install struct-diff
struct-diff diff config-v1.yaml config-v2.yaml
```

> Finds real changes. Ignores noise. Exits non-zero for CI pipelines.

## Why struct-diff?

- **Semantic diff** - Compares structure, not text. Key ordering never triggers a diff
- **Array intelligence** - Matches array items by value or ID field, not index
- **Schema generation** - Auto-infer JSON Schema from sample data with format detection
- **Format conversion** - JSON, YAML, TOML interconversion
- **Validation** - Human-readable schema validation errors
- **Deep merge** - Merge configs with first-wins, last-wins, array concat strategies
- **Multiple outputs** - Terminal colors, JSON Patch (RFC 6902), markdown, HTML

## Quick Start

```bash
# Semantic diff (ignores key ordering)
struct-diff diff old-config.json new-config.json

# Diff with JSON Patch output (RFC 6902)
struct-diff diff a.yaml b.yaml --format json-patch

# Generate schema from sample data
struct-diff schema users.json --title "User Schema"

# Validate data against schema
struct-diff validate data.json --schema schema.json

# Convert between formats
struct-diff convert config.yaml --to json
struct-diff convert settings.json --to yaml

# Deep merge with conflict resolution
struct-diff merge base.yaml overrides.yaml --strategy last --arrays unique
```

## Diff Output Formats

| Format | Flag | Description |
|--------|------|-------------|
| Terminal | `--format terminal` | Colored diff (default) |
| JSON Patch | `--format json-patch` | RFC 6902 operations |
| Markdown | `--format markdown` | Table for docs/PRs |
| HTML | `--format html` | Side-by-side visual diff |

## Schema Generation

Auto-detects from sample data:
- Types (string, integer, number, boolean, array, object, null)
- Formats (email, URI, UUID, date, datetime, IPv4)
- Required vs optional fields
- Enum values (small sets of repeated strings)

```bash
# From a single object
struct-diff schema user.json

# From an array of objects (analyzes all items)
struct-diff schema users.json --title "User List Schema"
```

## Merge Strategies

| Strategy | Scalars | Arrays |
|----------|---------|--------|
| `first` | Keep A's value | Keep A's array |
| `last` | Keep B's value | Keep B's array |
| `concat` | Last wins | Concatenate A + B |
| `unique` | Last wins | Merge + deduplicate |

## CI Integration

`struct-diff diff` exits with code 1 when differences are found:

```yaml
- name: Check config drift
  run: struct-diff diff expected.yaml actual.yaml --format markdown > diff.md
```

## License

MIT
