from __future__ import annotations

import json
from pathlib import Path

import click
from flask import Flask, current_app
from flask.cli import AppGroup, with_appcontext

from backend.endpoint_registry.registry import (
    build_registry,
    dump_registry_json,
    render_markdown,
)

DEFAULT_REGISTRY_JSON_PATH = "docs/endpoints/endpoint-registry.json"
DEFAULT_REGISTRY_MARKDOWN_PATH = "docs/endpoints/ENDPOINT_REGISTRY.md"

endpoints_cli = AppGroup(
    "endpoints",
    help="Endpoint registry generation and audit for U4I.",
)


@endpoints_cli.command("generate")
@click.option(
    "--output",
    "-o",
    "output_path",
    default=DEFAULT_REGISTRY_JSON_PATH,
    help="Canonical JSON output path",
)
@click.option(
    "--markdown-output",
    "markdown_path",
    default=DEFAULT_REGISTRY_MARKDOWN_PATH,
    help="Rendered markdown output path",
)
@with_appcontext
def generate_endpoints_command(output_path: str, markdown_path: str) -> None:
    """Generate the endpoint registry JSON and its rendered markdown from the live url_map."""
    json_file = Path(output_path)
    markdown_file = Path(markdown_path)

    for output_file in (json_file, markdown_file):
        if not output_file.parent.exists():
            raise click.ClickException(
                f"Directory does not exist: {output_file.parent}"
            )
        if output_file.is_dir():
            raise click.ClickException(f"Output path is a directory: {output_file}")

    app = current_app._get_current_object()
    try:
        registry = build_registry(app)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    # Render the markdown from the JSON round-trip so both files come from the
    # same canonical data by construction; compute both before writing either.
    json_text = dump_registry_json(registry)
    markdown_text = render_markdown(json.loads(json_text))

    try:
        json_file.write_text(json_text, encoding="utf-8")
        markdown_file.write_text(markdown_text, encoding="utf-8")
    except OSError as exc:
        raise click.ClickException(f"Could not write endpoint registry: {exc}") from exc
    click.echo(
        f"endpoints: wrote {len(registry['endpoints'])} endpoints → "
        f"{json_file}, {markdown_file}"
    )


def register_endpoints_cli(app: Flask) -> None:
    app.cli.add_command(endpoints_cli)
