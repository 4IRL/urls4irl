from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
from flask import Flask, current_app
from flask.cli import AppGroup, with_appcontext

from backend.endpoint_registry.audit import (
    WHOLE_REGISTRY,
    RegistryFinding,
    diff_markdown,
    diff_registry,
    find_api_routes_without_js_linkage,
    find_stale_indirect_js_entries,
    find_stale_no_js_entries,
)
from backend.endpoint_registry.registry import (
    build_registry,
    dump_registry_json,
    render_markdown,
)
from backend.utils.all_routes import INDIRECT_JS_ENDPOINTS, NO_JS_ENDPOINTS

DEFAULT_REGISTRY_JSON_PATH = "docs/endpoints/endpoint-registry.json"
DEFAULT_REGISTRY_MARKDOWN_PATH = "docs/endpoints/ENDPOINT_REGISTRY.md"

AUDIT_NONE_PLACEHOLDER = "(none)"
AUDIT_SECTION_DRIFT = "# Registry drift (committed vs live)"
AUDIT_SECTION_JS = "# @api_route endpoints without JS linkage"
AUDIT_SECTION_NO_JS = "# Stale NO_JS_ENDPOINTS / INDIRECT_JS_ENDPOINTS entries"
AUDIT_SECTION_MARKDOWN = "# Markdown rendering"

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


def _load_committed_registry(
    registry_file: Path,
) -> tuple[dict[str, Any] | None, list[RegistryFinding]]:
    """Load the committed JSON, or return a single finding explaining why not."""
    try:
        committed = json.loads(registry_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        detail = f"committed registry not found: {registry_file}"
    except (OSError, ValueError) as exc:
        # ValueError covers json.JSONDecodeError and UnicodeDecodeError.
        detail = f"committed registry unreadable: {registry_file}: {exc}"
    else:
        if _has_registry_shape(committed):
            return committed, []
        detail = f"committed registry has an invalid shape: {registry_file}"
    return None, [RegistryFinding("missing_in_registry", WHOLE_REGISTRY, detail)]


def _is_registry_row(row: Any) -> bool:
    return (
        isinstance(row, dict)
        and isinstance(row.get("endpoint"), str)
        and isinstance(row.get("blueprint"), str)
        and isinstance(row.get("js"), dict)
    )


def _has_registry_shape(committed: Any) -> bool:
    """True when every row has the fields the audit helpers index into."""
    if not isinstance(committed, dict):
        return False
    rows = committed.get("endpoints")
    return isinstance(rows, list) and all(_is_registry_row(row) for row in rows)


def _markdown_findings(
    committed: dict[str, Any] | None, markdown_file: Path
) -> list[RegistryFinding]:
    if committed is None:
        # Nothing to render from; the drift section already reports why.
        return []
    try:
        committed_markdown = markdown_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        detail = f"committed markdown not found: {markdown_file}"
    except (OSError, ValueError) as exc:
        detail = f"committed markdown unreadable: {markdown_file}: {exc}"
    else:
        return diff_markdown(committed, committed_markdown)
    return [RegistryFinding("markdown_stale", WHOLE_REGISTRY, detail)]


def _echo_section(header: str, findings: list[RegistryFinding]) -> None:
    click.echo(header)
    if not findings:
        click.echo(AUDIT_NONE_PLACEHOLDER)
    for finding in findings:
        click.echo(f"{finding.kind}\t{finding.endpoint}\t{finding.detail}")


@endpoints_cli.command(
    "audit", help="Audit the committed endpoint registry against the live app."
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Exit non-zero if any finding is present.",
)
@click.option(
    "--registry",
    "registry_path",
    default=DEFAULT_REGISTRY_JSON_PATH,
    help="Committed registry JSON path",
)
@click.option(
    "--markdown",
    "markdown_path",
    default=DEFAULT_REGISTRY_MARKDOWN_PATH,
    help="Committed registry markdown path",
)
@with_appcontext
def audit_endpoints_command(
    strict: bool, registry_path: str, markdown_path: str
) -> None:
    """Diff the committed registry against the live app and check JS linkage.

    Output is grouped into four `# <Section>` blocks of TSV rows
    (`kind<TAB>endpoint<TAB>detail`); empty sections print `(none)`.
    """
    app = current_app._get_current_object()
    try:
        live = build_registry(app)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    committed, load_findings = _load_committed_registry(Path(registry_path))
    drift_findings = (
        load_findings if committed is None else diff_registry(live, committed)
    )
    js_findings = find_api_routes_without_js_linkage(live)
    stale_entry_findings = find_stale_no_js_entries(
        NO_JS_ENDPOINTS, live
    ) + find_stale_indirect_js_entries(INDIRECT_JS_ENDPOINTS, NO_JS_ENDPOINTS, live)
    markdown_findings = _markdown_findings(committed, Path(markdown_path))

    _echo_section(AUDIT_SECTION_DRIFT, drift_findings)
    _echo_section(AUDIT_SECTION_JS, js_findings)
    _echo_section(AUDIT_SECTION_NO_JS, stale_entry_findings)
    _echo_section(AUDIT_SECTION_MARKDOWN, markdown_findings)

    any_findings_present = bool(
        drift_findings or js_findings or stale_entry_findings or markdown_findings
    )
    if strict and any_findings_present:
        raise SystemExit(1)


def register_endpoints_cli(app: Flask) -> None:
    app.cli.add_command(endpoints_cli)
