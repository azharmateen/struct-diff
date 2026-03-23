"""CLI for struct-diff: semantic JSON/YAML differ."""

import json
import sys
from pathlib import Path

import click
from rich.console import Console

from .converter import load_file, dump_data, convert, detect_format
from .differ import semantic_diff
from .formatter import (format_colored_terminal, format_json_patch,
                        format_markdown_table, format_html_side_by_side)
from .merger import deep_merge, ConflictStrategy
from .schema_gen import generate_schema
from .validator import validate

console = Console()


@click.group()
def cli():
    """struct-diff: Semantic JSON/YAML differ, schema generator, and more."""
    pass


@cli.command()
@click.argument("file_a", type=click.Path(exists=True))
@click.argument("file_b", type=click.Path(exists=True))
@click.option("--format", "-f", "fmt", default="terminal",
              type=click.Choice(["terminal", "json-patch", "markdown", "html"]),
              help="Output format")
@click.option("--output", "-o", default=None, help="Write output to file")
def diff(file_a, file_b, fmt, output):
    """Semantic diff between two JSON/YAML files (ignores key ordering)."""
    a, _ = load_file(file_a)
    b, _ = load_file(file_b)

    result = semantic_diff(a, b)

    if fmt == "terminal":
        text = format_colored_terminal(result)
        if output:
            # Strip ANSI for file output
            import re
            text = re.sub(r'\033\[[0-9;]*m', '', text)
            Path(output).write_text(text, encoding="utf-8")
            console.print(f"[green]Diff written to {output}[/green]")
        else:
            click.echo(text)
    elif fmt == "json-patch":
        patch = format_json_patch(result)
        text = json.dumps(patch, indent=2)
        if output:
            Path(output).write_text(text, encoding="utf-8")
            console.print(f"[green]JSON Patch written to {output}[/green]")
        else:
            click.echo(text)
    elif fmt == "markdown":
        text = format_markdown_table(result)
        if output:
            Path(output).write_text(text, encoding="utf-8")
            console.print(f"[green]Markdown diff written to {output}[/green]")
        else:
            click.echo(text)
    elif fmt == "html":
        text = format_html_side_by_side(result, a, b)
        out = output or "diff.html"
        Path(out).write_text(text, encoding="utf-8")
        console.print(f"[green]HTML diff written to {out}[/green]")

    if result.has_changes:
        sys.exit(1)  # Non-zero exit when differences found (useful in CI)


@cli.command()
@click.argument("sample_file", type=click.Path(exists=True))
@click.option("--title", "-t", default=None, help="Schema title")
@click.option("--output", "-o", default=None, help="Output file")
@click.option("--no-patterns", is_flag=True, help="Disable format pattern detection")
@click.option("--no-enums", is_flag=True, help="Disable enum detection")
def schema(sample_file, title, output, no_patterns, no_enums):
    """Auto-generate JSON Schema from sample data."""
    data, _ = load_file(sample_file)

    if title is None:
        title = Path(sample_file).stem.replace("-", " ").replace("_", " ").title()

    result = generate_schema(
        data,
        title=title,
        detect_patterns=not no_patterns,
        detect_enums=not no_enums,
    )

    text = json.dumps(result, indent=2)

    if output:
        Path(output).write_text(text, encoding="utf-8")
        console.print(f"[green]Schema written to {output}[/green]")
    else:
        click.echo(text)


@cli.command("validate")
@click.argument("data_file", type=click.Path(exists=True))
@click.option("--schema", "-s", "schema_file", required=True,
              type=click.Path(exists=True), help="JSON Schema file")
def validate_cmd(data_file, schema_file):
    """Validate a JSON/YAML file against a JSON Schema."""
    data, _ = load_file(data_file)
    schema_data, _ = load_file(schema_file)

    result = validate(data, schema_data)

    if result.valid:
        console.print(f"[green]Valid![/green] {data_file} conforms to schema.")
    else:
        console.print(f"[red]Invalid![/red] {result.error_count} error(s) found:\n")
        for error in result.errors:
            console.print(f"  [red]{error.path}[/red]: {error.message}")
            if error.expected:
                console.print(f"    expected: [green]{error.expected}[/green]")
            if error.got:
                console.print(f"    got:      [red]{error.got}[/red]")
            console.print()

        sys.exit(1)


@cli.command("convert")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--to", "-t", "target_format", required=True,
              type=click.Choice(["json", "yaml", "toml"]),
              help="Target format")
@click.option("--output", "-o", default=None, help="Output file path")
def convert_cmd(input_file, target_format, output):
    """Convert between JSON, YAML, and TOML."""
    out_path = convert(input_file, target_format, output)
    source_fmt = detect_format(input_file)
    console.print(f"[green]Converted[/green] {source_fmt} -> {target_format}: {out_path}")


@cli.command()
@click.argument("file_a", type=click.Path(exists=True))
@click.argument("file_b", type=click.Path(exists=True))
@click.option("--strategy", "-s", default="last",
              type=click.Choice(["first", "last"]),
              help="Conflict resolution strategy")
@click.option("--arrays", "-a", default="last",
              type=click.Choice(["first", "last", "concat", "unique"]),
              help="Array merge strategy")
@click.option("--output", "-o", default=None, help="Output file")
@click.option("--format", "-f", "fmt", default=None,
              type=click.Choice(["json", "yaml"]),
              help="Output format (default: same as first file)")
def merge(file_a, file_b, strategy, arrays, output, fmt):
    """Deep merge two JSON/YAML files."""
    a, a_fmt = load_file(file_a)
    b, _ = load_file(file_b)

    strategy_map = {
        "first": ConflictStrategy.FIRST_WINS,
        "last": ConflictStrategy.LAST_WINS,
        "concat": ConflictStrategy.ARRAY_CONCAT,
        "unique": ConflictStrategy.ARRAY_UNIQUE,
    }

    result = deep_merge(a, b,
                        strategy=strategy_map[strategy],
                        array_strategy=strategy_map[arrays])

    out_fmt = fmt or a_fmt
    text = dump_data(result, out_fmt)

    if output:
        Path(output).write_text(text, encoding="utf-8")
        console.print(f"[green]Merged result written to {output}[/green]")
    else:
        click.echo(text)


if __name__ == "__main__":
    cli()
