"""Unit tests for `scripts/endpoint_info.py` (`make endpoint-info e=<route>`).

Resolution and formatting run against a small inline registry; one test
cross-checks `format_entry` against `render_markdown` so the terminal view and
the committed markdown cannot drift, and one resolves the three documented
sample queries against the committed registry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.endpoint_registry.registry import render_markdown
from scripts.endpoint_info import (
    DEFAULT_REGISTRY,
    MAX_FULL_ENTRIES,
    format_entry,
    main,
    resolve,
)

pytestmark = pytest.mark.unit

MAX_ENTRY_LINES = 20
UTUB_RULE = "/utubs/<int:utub_id>"


def _row(
    *,
    endpoint: str,
    rule: str,
    methods: list[str],
    js: dict[str, Any] | None = None,
    schemas: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "blueprint": endpoint.split(".", 1)[0],
        "decorators": ["utub_membership_required", "api_route"],
        "endpoint": endpoint,
        "handler": f"backend/{endpoint.split('.', 1)[0]}/routes.py:{endpoint.split('.', 1)[1]}",
        "js": js
        or {"indirect": None, "no_js": None, "route_keys": [], "template_url_for": []},
        "methods": methods,
        "rule": rule,
        "schemas": schemas,
        "services": [],
        "templates": [],
    }


GET_UTUB_ROW = _row(
    endpoint="utubs.get_single_utub",
    rule=UTUB_RULE,
    methods=["GET"],
    js={
        "indirect": None,
        "no_js": None,
        "route_keys": ["getUTub"],
        "template_url_for": [],
    },
    schemas={
        "query": None,
        "request": None,
        "response": "backend.schemas.utubs.UtubDetailSchema",
        "status_codes": {
            "200": "backend.schemas.utubs.UtubDetailSchema",
            "404": "backend.schemas.errors.ErrorResponse",
        },
    },
)
DELETE_UTUB_ROW = _row(endpoint="utubs.delete_utub", rule=UTUB_RULE, methods=["DELETE"])
MEMBERS_ROW = _row(
    endpoint="members.remove_member",
    rule="/utubs/<int:utub_id>/members/<int:user_id>",
    methods=["DELETE"],
)
RESET_PASSWORD_ROW = _row(
    endpoint="splash.reset_password",
    rule="/reset-password/<token>",
    methods=["POST"],
    js={
        "indirect": "page-self-url",
        "no_js": None,
        "route_keys": [],
        "template_url_for": [],
    },
)
REGISTRY: dict[str, Any] = {
    "endpoints": [GET_UTUB_ROW, DELETE_UTUB_ROW, MEMBERS_ROW, RESET_PASSWORD_ROW]
}


def _endpoints(rows: list[dict[str, Any]]) -> list[str]:
    return [row["endpoint"] for row in rows]


def _write_registry(tmp_path: Path, registry: dict[str, Any]) -> Path:
    registry_path = tmp_path / "endpoint-registry.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    return registry_path


# ---------------------------------------------------------------------------
# resolve(): precedence tiers
# ---------------------------------------------------------------------------


def test_resolve_exact_endpoint_wins() -> None:
    """
    GIVEN an endpoint name
    WHEN resolve() runs
    THEN only that endpoint's row is returned (tier 1).
    """
    assert _endpoints(resolve(REGISTRY, "utubs.get_single_utub")) == [
        "utubs.get_single_utub"
    ]


def test_resolve_exact_rule_returns_every_method() -> None:
    """
    GIVEN a rule shared by GET and DELETE
    WHEN resolve() runs on the exact rule
    THEN both rows come back, and the longer members rule is not a match (tier 2).
    """
    assert _endpoints(resolve(REGISTRY, UTUB_RULE)) == [
        "utubs.get_single_utub",
        "utubs.delete_utub",
    ]


@pytest.mark.parametrize(
    "query",
    [
        pytest.param("DELETE /utubs/<int:utub_id>", id="exact-rule"),
        pytest.param("delete /utubs/<utub_id>", id="lowercase-stripped"),
    ],
)
def test_resolve_method_and_rule(query: str) -> None:
    """
    GIVEN a `METHOD /rule` query
    WHEN resolve() runs
    THEN only the row with that method on that path is returned (tier 3).
    """
    assert _endpoints(resolve(REGISTRY, query)) == ["utubs.delete_utub"]


def test_resolve_converter_stripped_rule() -> None:
    """
    GIVEN a rule written without its `int:` converter
    WHEN resolve() runs
    THEN it matches `/utubs/<int:utub_id>`, every method (tier 4).
    """
    assert _endpoints(resolve(REGISTRY, "/utubs/<utub_id>")) == [
        "utubs.get_single_utub",
        "utubs.delete_utub",
    ]


def test_resolve_substring_fallback_returns_candidates() -> None:
    """
    GIVEN a fragment matching no endpoint or rule exactly
    WHEN resolve() runs
    THEN every row whose endpoint or rule contains it (case-insensitively) is returned (tier 5).
    """
    assert _endpoints(resolve(REGISTRY, "MEMBER")) == ["members.remove_member"]
    assert _endpoints(resolve(REGISTRY, "utubs.")) == [
        "utubs.get_single_utub",
        "utubs.delete_utub",
    ]


def test_resolve_exact_endpoint_shadows_substring() -> None:
    """
    GIVEN an endpoint name that is also a substring of a longer endpoint name
    WHEN resolve() runs on it
    THEN only the exact endpoint is returned, not the substring candidate.
    """
    bulk_row = _row(
        endpoint="members.remove_member_bulk",
        rule="/utubs/<int:utub_id>/members",
        methods=["DELETE"],
    )
    registry = {"endpoints": [MEMBERS_ROW, bulk_row]}
    assert _endpoints(resolve(registry, "members.remove_member")) == [
        "members.remove_member"
    ]


@pytest.mark.parametrize(
    "query", ["no.such_endpoint", "", "   ", "PATCH /utubs/<int:utub_id>"]
)
def test_resolve_unknown_query_returns_empty(query: str) -> None:
    """
    GIVEN a query matching nothing (including a blank one, or a method the path lacks)
    WHEN resolve() runs
    THEN it returns an empty list.
    """
    assert resolve(REGISTRY, query) == []


# ---------------------------------------------------------------------------
# format_entry()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "row", REGISTRY["endpoints"], ids=_endpoints(REGISTRY["endpoints"])
)
def test_format_entry_is_at_most_20_lines(row: dict[str, Any]) -> None:
    """
    GIVEN any registry row
    WHEN format_entry() renders it
    THEN the block fits in 20 lines and names the method, rule and endpoint first.
    """
    entry_lines = format_entry(row).splitlines()
    assert len(entry_lines) <= MAX_ENTRY_LINES
    assert (
        entry_lines[0]
        == f"{','.join(row['methods'])} {row['rule']} — {row['endpoint']}"
    )


@pytest.mark.parametrize(
    "row", REGISTRY["endpoints"], ids=_endpoints(REGISTRY["endpoints"])
)
def test_format_entry_mirrors_markdown_bullets(row: dict[str, Any]) -> None:
    """
    GIVEN a registry row
    WHEN it is rendered by format_entry() and by render_markdown()
    THEN each `  Label: value` line equals the markdown's `- **Label:** value` bullet.
    """
    markdown_bullets = [
        line.replace("- **", "  ", 1).replace(":**", ":", 1)
        for line in render_markdown({"endpoints": [row]}).splitlines()
        if line.startswith("- **")
    ]
    assert format_entry(row).splitlines()[1:] == markdown_bullets


def test_format_entry_renders_indirect_js_source() -> None:
    """
    GIVEN a row linked through an indirect JS source
    WHEN format_entry() renders it
    THEN the JS line reads `indirect: <source>`.
    """
    assert "  JS: indirect: page-self-url" in format_entry(RESET_PASSWORD_ROW)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main_prints_full_entries(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    GIVEN a rule with two methods
    WHEN main() runs
    THEN it exits 0 and prints both full entries.
    """
    registry_path = _write_registry(tmp_path, REGISTRY)
    assert main(["--registry", str(registry_path), UTUB_RULE]) == 0
    output = capsys.readouterr().out
    assert format_entry(GET_UTUB_ROW) in output
    assert format_entry(DELETE_UTUB_ROW) in output


def test_main_unknown_query_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    GIVEN a query that matches nothing
    WHEN main() runs
    THEN it exits 1 with `no endpoint matches '<q>'` on stderr.
    """
    registry_path = _write_registry(tmp_path, REGISTRY)
    assert main(["--registry", str(registry_path), "nope"]) == 1
    captured = capsys.readouterr()
    assert "no endpoint matches 'nope'" in captured.err
    assert captured.out == ""


def test_main_many_candidates_prints_one_line_each(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    GIVEN more than MAX_FULL_ENTRIES substring matches
    WHEN main() runs
    THEN it prints one `endpoint  METHOD rule` line per candidate instead of full entries.
    """
    candidate_count = MAX_FULL_ENTRIES + 1
    many_rows = [
        _row(
            endpoint=f"widgets.widget_{index}",
            rule=f"/widgets/{index}",
            methods=["GET"],
        )
        for index in range(candidate_count)
    ]
    registry_path = _write_registry(tmp_path, {"endpoints": many_rows})
    assert main(["--registry", str(registry_path), "widget"]) == 0
    output_lines = capsys.readouterr().out.splitlines()
    assert len(output_lines) == 1 + candidate_count
    assert f"{candidate_count} endpoints match 'widget'" in output_lines[0]
    assert output_lines[1] == "widgets.widget_0  GET /widgets/0"
    assert not any("Handler:" in line for line in output_lines)


def test_main_missing_registry_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    GIVEN a registry path that does not exist
    WHEN main() runs
    THEN it exits 1 and points at make generate-endpoints, with no traceback.
    """
    missing_path = tmp_path / "absent.json"
    assert main(["--registry", str(missing_path), "utubs.get_single_utub"]) == 1
    assert "run make generate-endpoints" in capsys.readouterr().err


def test_main_malformed_registry_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    GIVEN a registry file that is not valid JSON
    WHEN main() runs
    THEN it exits 1 with an `unreadable` message, not a traceback.
    """
    registry_path = tmp_path / "endpoint-registry.json"
    registry_path.write_text("{not json", encoding="utf-8")
    assert main(["--registry", str(registry_path), "utubs.get_single_utub"]) == 1
    assert "endpoint registry unreadable" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("registry", "query"),
    [
        pytest.param([], "utubs.get_single_utub", id="top-level-list"),
        pytest.param({"rows": []}, "utubs.get_single_utub", id="missing-endpoints"),
        pytest.param({"endpoints": [{"endpoint": "x"}]}, "x", id="row-missing-keys"),
        pytest.param({"endpoints": [{"endpoint": "x"}]}, "zzz", id="row-missing-rule"),
    ],
)
def test_main_wrong_shape_registry_exits_1(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    registry: Any,
    query: str,
) -> None:
    """
    GIVEN a registry that is valid JSON but not the registry's shape
    WHEN main() runs a query that reaches the missing structure
    THEN it exits 1 with an `unreadable` message and prints nothing to stdout.
    """
    registry_path = tmp_path / "endpoint-registry.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    assert main(["--registry", str(registry_path), query]) == 1
    captured = capsys.readouterr()
    assert "endpoint registry unreadable" in captured.err
    assert captured.out == ""


def test_main_dash_leading_query_is_not_an_option(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    GIVEN a dash-leading query passed after `--`
    WHEN main() runs
    THEN it is treated as a query (no help output) and exits 1 as an unmatched route.
    """
    registry_path = _write_registry(tmp_path, REGISTRY)
    assert main(["--registry", str(registry_path), "--", "-h"]) == 1
    captured = capsys.readouterr()
    assert "no endpoint matches '-h'" in captured.err
    assert captured.out == ""


# ---------------------------------------------------------------------------
# Committed registry
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def committed_registry() -> dict[str, Any]:
    return json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("query", "expected_endpoints"),
    [
        pytest.param("utubs.get_single_utub", ["utubs.get_single_utub"], id="endpoint"),
        pytest.param(
            "/utubs/<utub_id>",
            ["utubs.delete_utub", "utubs.get_single_utub"],
            id="stripped-rule",
        ),
        pytest.param(
            "DELETE /utubs/<int:utub_id>", ["utubs.delete_utub"], id="method-rule"
        ),
    ],
)
def test_documented_queries_resolve_against_committed_registry(
    committed_registry: dict[str, Any], query: str, expected_endpoints: list[str]
) -> None:
    """
    GIVEN the committed docs/endpoints/endpoint-registry.json
    WHEN the documented sample queries resolve
    THEN each returns the expected rows, each formatted in at most 20 lines.
    """
    matches = resolve(committed_registry, query)
    assert _endpoints(matches) == expected_endpoints
    for row in matches:
        assert len(format_entry(row).splitlines()) <= MAX_ENTRY_LINES
