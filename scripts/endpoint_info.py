"""Answer "what touches this route" from the committed endpoint registry.

Run by `make endpoint-info e=<route>` on the host, with no stack: it reads
`docs/endpoints/endpoint-registry.json` (written by `make generate-endpoints`)
and prints each matching entry in about 7 lines, using the same labels and
value rendering as `docs/endpoints/ENDPOINT_REGISTRY.md` (see
`backend/endpoint_registry/registry.py:render_markdown`).

A query resolves against the first tier that matches anything:
1. an exact endpoint (`utubs.get_single_utub`);
2. an exact rule, every method on that path (`/utubs/<int:utub_id>`);
3. `METHOD /rule` (`DELETE /utubs/<int:utub_id>`; the rule may omit converters);
4. a converter-stripped rule (`/utubs/<utub_id>` matches `/utubs/<int:utub_id>`);
5. a case-insensitive substring of an endpoint or rule (candidates).

More than MAX_FULL_ENTRIES matches print one `endpoint  METHOD rule` line each
instead of full entries. No match exits 1. Stdlib only: it runs on the host
under bare mise python.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT: Path = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY: Path = REPO_ROOT / "docs" / "endpoints" / "endpoint-registry.json"
MAX_FULL_ENTRIES: int = 5
EMPTY_VALUE: str = "—"
_CONVERTER_PATTERN: re.Pattern[str] = re.compile(r"<(?:[^<>:]+:)?([^<>:]+)>")
_METHOD_QUERY_PATTERN: re.Pattern[str] = re.compile(r"^([A-Za-z]+)\s+(/\S*)$")


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def _strip_converters(rule: str) -> str:
    """`/utubs/<int:utub_id>` -> `/utubs/<utub_id>`; converter-less rules pass through."""
    return _CONVERTER_PATTERN.sub(r"<\1>", rule)


def _rule_matches(query_rule: str, row_rule: str) -> bool:
    return _strip_converters(query_rule) == _strip_converters(row_rule)


def resolve(registry: dict[str, Any], query: str) -> list[dict[str, Any]]:
    """Rows matching `query` from the first precedence tier that matches, in registry order."""
    rows: list[dict[str, Any]] = registry["endpoints"]
    query = query.strip()
    if not query:
        return []

    exact_endpoint = [row for row in rows if row["endpoint"] == query]
    if exact_endpoint:
        return exact_endpoint

    exact_rule = [row for row in rows if row["rule"] == query]
    if exact_rule:
        return exact_rule

    method_match = _METHOD_QUERY_PATTERN.match(query)
    if method_match:
        method = method_match.group(1).upper()
        query_rule = method_match.group(2)
        method_rows = [
            row
            for row in rows
            if method in row["methods"] and _rule_matches(query_rule, row["rule"])
        ]
        if method_rows:
            return method_rows

    stripped_query = _strip_converters(query)
    stripped_rule = [
        row for row in rows if _strip_converters(row["rule"]) == stripped_query
    ]
    if stripped_rule:
        return stripped_rule

    lowered_query = query.lower()
    return [
        row
        for row in rows
        if lowered_query in row["endpoint"].lower()
        or lowered_query in row["rule"].lower()
    ]


# ---------------------------------------------------------------------------
# Formatting (mirrors registry.py's markdown value rendering)
# ---------------------------------------------------------------------------
# `_code`, `_code_list`, `_render_schemas` and `_render_js` deliberately mirror
# the same helpers in backend/endpoint_registry/registry.py: this script stays
# stdlib-only and host-native, so it must not import `backend`. Make any
# formatting change in both places. tests/unit/test_endpoint_info.py
# cross-checks `format_entry()` against `render_markdown()` to catch drift.


def _code(value: str) -> str:
    return f"`{value}`"


def _code_list(values: list[str]) -> str:
    return ", ".join(_code(value) for value in values) or EMPTY_VALUE


def _render_schemas(schemas: dict[str, Any] | None) -> str:
    if schemas is None:
        return EMPTY_VALUE
    parts = [
        f"{part}: {_code(schemas[part])}"
        for part in ("request", "query", "response")
        if schemas.get(part) is not None
    ]
    status_codes = schemas.get("status_codes") or {}
    if status_codes:
        rendered_codes = ", ".join(
            f"{code} {_code(schema_name)}" if schema_name else code
            for code, schema_name in status_codes.items()
        )
        parts.append(f"status: {rendered_codes}")
    return "; ".join(parts) or EMPTY_VALUE


def _render_js(js: dict[str, Any]) -> str:
    parts: list[str] = []
    if js["route_keys"]:
        parts.append(f"keys: {_code_list(js['route_keys'])}")
    if js["template_url_for"]:
        parts.append(f"template url_for: {_code_list(js['template_url_for'])}")
    if js["indirect"]:
        parts.append(f"indirect: {js['indirect']}")
    if js["no_js"]:
        parts.append(f"no-js: {js['no_js']}")
    return "; ".join(parts) or EMPTY_VALUE


def _summary_line(row: dict[str, Any]) -> str:
    return f"{','.join(row['methods'])} {row['rule']}"


def format_entry(row: dict[str, Any]) -> str:
    """One registry row as a short text block, labelled like the markdown bullets."""
    return "\n".join(
        [
            f"{_summary_line(row)} — {row['endpoint']}",
            f"  Handler: {_code(row['handler'])}",
            f"  Decorators: {_code_list(row['decorators'])}",
            f"  Service: {_code_list(row['services'])}",
            f"  Schema: {_render_schemas(row['schemas'])}",
            f"  Template: {_code_list(row['templates'])}",
            f"  JS: {_render_js(row['js'])}",
        ]
    )


def format_candidates(rows: list[dict[str, Any]]) -> str:
    """One `endpoint  METHOD rule` line per row, for a query too broad to print in full."""
    width = max(len(row["endpoint"]) for row in rows)
    return "\n".join(
        f"{row['endpoint'].ljust(width)}  {_summary_line(row)}" for row in rows
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="endpoint_info",
        description="Show what touches a route, from the committed endpoint registry.",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help="registry JSON (default: docs/endpoints/endpoint-registry.json)",
    )
    parser.add_argument(
        "query", help="an endpoint, a rule, or 'METHOD /rule' (converters optional)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(
            f"endpoint registry not found: {args.registry} — run make generate-endpoints",
            file=sys.stderr,
        )
        return 1
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as read_error:
        print(
            f"endpoint registry unreadable: {args.registry} — {read_error}",
            file=sys.stderr,
        )
        return 1

    try:
        matches = resolve(registry, args.query)
        if not matches:
            print(f"no endpoint matches '{args.query}'", file=sys.stderr)
            return 1
        if len(matches) > MAX_FULL_ENTRIES:
            header = (
                f"{len(matches)} endpoints match '{args.query}' — narrow the query:"
            )
            output = f"{header}\n{format_candidates(matches)}"
        else:
            output = "\n\n".join(format_entry(row) for row in matches)
    except (KeyError, TypeError, AttributeError) as shape_error:
        print(
            f"endpoint registry unreadable: {args.registry} — {shape_error!r}",
            file=sys.stderr,
        )
        return 1
    print(output)
    return 0


__all__ = ["format_candidates", "format_entry", "main", "resolve"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
