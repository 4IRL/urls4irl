"""Unit-scope invariants for the generated endpoint registry.

Asserts what `flask endpoints audit --strict` enforces, against the real repo:
the committed `docs/endpoints/` artifacts match the live app, every
`@api_route` endpoint has JS linkage, `NO_JS_ENDPOINTS` and
`INDIRECT_JS_ENDPOINTS` hold only live and needed entries, and the markdown is
the rendering of the committed JSON.
The negative probes below feed hand-built dicts to the pure helpers in
`backend.endpoint_registry.audit`, one per finding kind.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.config import ConfigTest
from backend.endpoint_registry.audit import (
    JS_LINKAGE_REMEDY,
    REGENERATE_REMEDY,
    WHOLE_REGISTRY,
    RegistryFinding,
    diff_markdown,
    diff_registry,
    find_api_routes_without_js_linkage,
    find_stale_indirect_js_entries,
    find_stale_no_js_entries,
)
from backend.endpoint_registry.registry import build_registry, render_markdown
from backend.utils.all_routes import INDIRECT_JS_ENDPOINTS, NO_JS_ENDPOINTS
from tests.utils_for_test import create_secondary_app

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_COMMITTED_JSON = _REPO_ROOT / "docs" / "endpoints" / "endpoint-registry.json"
_COMMITTED_MARKDOWN = _REPO_ROOT / "docs" / "endpoints" / "ENDPOINT_REGISTRY.md"

GENERATE_REMEDY = "Run 'make generate-endpoints' and commit docs/endpoints/."
NO_JS_REMEDY = (
    "Fix backend/utils/all_routes.py: give the endpoint a JS_ROUTES/ADMIN_JS_ROUTES "
    "key or template url_for, an INDIRECT_JS_ENDPOINTS source, or a "
    "NO_JS_ENDPOINTS reason; drop dead/redundant/conflicting "
    "INDIRECT_JS_ENDPOINTS and NO_JS_ENDPOINTS entries."
)

Registry = dict[str, Any]


def _finding_tuples(findings: list[RegistryFinding]) -> list[tuple[str, str]]:
    return [(finding.endpoint, finding.detail) for finding in findings]


# ---------------------------------------------------------------------------
# Real-repo invariants
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def live_registry() -> Registry:
    # Pass the class, not an instance, so Config.__init__ env validation is skipped.
    return build_registry(create_secondary_app(ConfigTest))


@pytest.fixture(scope="module")
def committed_registry() -> Registry:
    return json.loads(_COMMITTED_JSON.read_text(encoding="utf-8"))


def test_committed_registry_matches_live_app(
    live_registry: Registry, committed_registry: Registry
) -> None:
    """
    GIVEN the live app's registry and the committed docs/endpoints JSON
    WHEN they are diffed field by field
    THEN there is no drift
    """
    findings = diff_registry(live_registry, committed_registry)
    assert findings == [], f"{_finding_tuples(findings)}. {GENERATE_REMEDY}"


def test_every_api_route_has_js_linkage(live_registry: Registry) -> None:
    """
    GIVEN the live app's registry
    WHEN @api_route rows are checked for a route key, template ref or no-js reason
    THEN every one has at least one
    """
    findings = find_api_routes_without_js_linkage(live_registry)
    assert findings == [], f"{_finding_tuples(findings)}. {NO_JS_REMEDY}"


def test_no_js_entries_are_live_and_needed(live_registry: Registry) -> None:
    """
    GIVEN NO_JS_ENDPOINTS and the live app's registry
    WHEN each entry is checked against the live endpoints and blueprints
    THEN none is dead and none shadows an endpoint that is already linked
    """
    findings = find_stale_no_js_entries(NO_JS_ENDPOINTS, live_registry)
    assert findings == [], f"{_finding_tuples(findings)}. {NO_JS_REMEDY}"


def test_indirect_js_entries_are_live_needed_and_unique(
    live_registry: Registry,
) -> None:
    """
    GIVEN INDIRECT_JS_ENDPOINTS, NO_JS_ENDPOINTS and the live app's registry
    WHEN each indirect entry is checked
    THEN none is dead, none shadows an already-linked endpoint, and none is
        also exempted by NO_JS_ENDPOINTS
    """
    findings = find_stale_indirect_js_entries(
        INDIRECT_JS_ENDPOINTS, NO_JS_ENDPOINTS, live_registry
    )
    assert findings == [], f"{_finding_tuples(findings)}. {NO_JS_REMEDY}"


def test_markdown_rendered_from_committed_json(committed_registry: Registry) -> None:
    """
    GIVEN the committed JSON and the committed markdown
    WHEN the JSON is rendered to markdown
    THEN it is byte-identical to the committed markdown
    """
    findings = diff_markdown(
        committed_registry, _COMMITTED_MARKDOWN.read_text(encoding="utf-8")
    )
    assert findings == [], f"{_finding_tuples(findings)}. {GENERATE_REMEDY}"


# ---------------------------------------------------------------------------
# Negative probes — one per finding kind
# ---------------------------------------------------------------------------


def _row(
    endpoint: str,
    *,
    is_api_route: bool = True,
    route_keys: list[str] | None = None,
    template_url_for: list[str] | None = None,
    indirect: str | None = None,
    no_js: str | None = None,
    services: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "endpoint": endpoint,
        "blueprint": endpoint.rpartition(".")[0],
        "rule": f"/{endpoint.replace('.', '/')}",
        "methods": ["GET"],
        "handler": f"backend/probe.py:{endpoint.rpartition('.')[2]}",
        "decorators": ["api_route"] if is_api_route else [],
        "services": services or [],
        "schemas": (
            {"request": None, "query": None, "response": None, "status_codes": {}}
            if is_api_route
            else None
        ),
        "templates": [],
        "js": {
            "route_keys": route_keys or [],
            "template_url_for": template_url_for or [],
            "indirect": indirect,
            "no_js": no_js,
        },
    }


def _registry(*rows: dict[str, Any]) -> Registry:
    return {
        "generated_by": "probe",
        "source_of_truth": "probe",
        "endpoints": list(rows),
    }


def test_route_added_live_is_missing_in_registry() -> None:
    """
    GIVEN a live registry with an endpoint the committed one lacks
    WHEN diff_registry runs
    THEN exactly one missing_in_registry finding names it
    """
    shared = _row("probe.shared", route_keys=["shared"])
    added = _row("probe.added", route_keys=["added"])

    findings = diff_registry(_registry(shared, added), _registry(shared))

    assert findings == [
        RegistryFinding(
            "missing_in_registry",
            "probe.added",
            f"live endpoint not committed; {REGENERATE_REMEDY}",
        )
    ]


def test_route_removed_from_app_is_missing_in_app() -> None:
    """
    GIVEN a committed registry with an endpoint the live app no longer has
    WHEN diff_registry runs
    THEN exactly one missing_in_app finding names it
    """
    shared = _row("probe.shared", route_keys=["shared"])
    removed = _row("probe.removed", route_keys=["removed"])

    findings = diff_registry(_registry(shared), _registry(shared, removed))

    assert [(finding.kind, finding.endpoint) for finding in findings] == [
        ("missing_in_app", "probe.removed")
    ]


def test_changed_service_is_field_mismatch() -> None:
    """
    GIVEN the same endpoint with a different service live vs committed
    WHEN diff_registry runs
    THEN one field_mismatch finding names the services field and both values
    """
    committed = _row("probe.page", route_keys=["page"], services=["backend.old:fn"])
    live = _row("probe.page", route_keys=["page"], services=["backend.new:fn"])

    findings = diff_registry(_registry(live), _registry(committed))

    assert findings == [
        RegistryFinding(
            "field_mismatch",
            "probe.page",
            "services: committed=['backend.old:fn'] live=['backend.new:fn']",
        )
    ]


def _with_rule(row: dict[str, Any], rule: str) -> dict[str, Any]:
    return {**row, "rule": rule}


def test_changed_secondary_rule_is_field_mismatch() -> None:
    """
    GIVEN an endpoint registered on two rules whose secondary rule changed live
    WHEN diff_registry runs
    THEN one field_mismatch finding names the endpoint and lists both sides' rows
    """
    primary = _row("probe.page", route_keys=["page"])
    committed_secondary = _with_rule(primary, "/probe/page/old")
    live_secondary = _with_rule(primary, "/probe/page/new")

    findings = diff_registry(
        _registry(primary, live_secondary), _registry(primary, committed_secondary)
    )

    assert [(finding.kind, finding.endpoint) for finding in findings] == [
        ("field_mismatch", "probe.page")
    ]
    assert findings[0].detail.startswith("rows: committed=")
    assert "/probe/page/old" in findings[0].detail
    assert "/probe/page/new" in findings[0].detail


def test_identical_multi_rule_endpoint_has_no_finding() -> None:
    """
    GIVEN an endpoint registered on two rules, identical live and committed
        but listed in a different order
    WHEN diff_registry runs
    THEN there is no finding
    """
    primary = _row("probe.page", route_keys=["page"])
    secondary = _with_rule(primary, "/probe/page/alt")

    findings = diff_registry(
        _registry(primary, secondary), _registry(secondary, primary)
    )

    assert findings == []


def test_unlinked_api_route_is_flagged() -> None:
    """
    GIVEN an @api_route row with no route key, template ref, indirect source
        or no-js reason, beside linked, indirect-only, exempt and non-api rows
    WHEN find_api_routes_without_js_linkage runs
    THEN only the unlinked @api_route row is flagged, with the remedy text
    """
    live = _registry(
        _row("probe.unlinked"),
        _row("probe.keyed", route_keys=["keyed"]),
        _row("probe.templated", template_url_for=["pages/probe.html"]),
        _row("probe.indirect", indirect="server-built-url"),
        _row("probe.exempt", no_js="infra-probe"),
        _row("probe.page", is_api_route=False),
    )

    findings = find_api_routes_without_js_linkage(live)

    assert findings == [
        RegistryFinding(
            "api_route_without_js_linkage", "probe.unlinked", JS_LINKAGE_REMEDY
        )
    ]


def test_no_js_entry_for_dead_endpoint_or_blueprint_is_unknown() -> None:
    """
    GIVEN NO_JS entries naming a dead endpoint and a dead blueprint, plus live ones
    WHEN find_stale_no_js_entries runs
    THEN only the two dead entries are flagged no_js_entry_unknown
    """
    live = _registry(_row("probe.live", no_js="infra-probe"))
    no_js = {
        "probe.live": "infra-probe",
        "probe.*": "mobile-api",
        "probe.gone": "infra-probe",
        "ghost.*": "mobile-api",
    }

    findings = find_stale_no_js_entries(no_js, live)

    assert findings == [
        RegistryFinding("no_js_entry_unknown", "ghost.*", "no live blueprint 'ghost'"),
        RegistryFinding("no_js_entry_unknown", "probe.gone", "no live endpoint"),
    ]


def test_no_js_entry_for_linked_endpoint_is_redundant() -> None:
    """
    GIVEN NO_JS entries for an endpoint with a route key and one with a template ref
    WHEN find_stale_no_js_entries runs
    THEN both are flagged no_js_entry_redundant, naming the linkage
    """
    live = _registry(
        _row("probe.keyed", route_keys=["keyed"], no_js="infra-probe"),
        _row(
            "probe.templated",
            template_url_for=["pages/probe.html"],
            no_js="infra-probe",
        ),
    )
    no_js = {"probe.keyed": "infra-probe", "probe.templated": "infra-probe"}

    findings = find_stale_no_js_entries(no_js, live)

    assert [(finding.kind, finding.endpoint) for finding in findings] == [
        ("no_js_entry_redundant", "probe.keyed"),
        ("no_js_entry_redundant", "probe.templated"),
    ]
    assert "keyed" in findings[0].detail
    assert "pages/probe.html" in findings[1].detail


def test_indirect_entry_for_dead_endpoint_is_unknown() -> None:
    """
    GIVEN INDIRECT_JS entries naming a live endpoint and a dead one
    WHEN find_stale_indirect_js_entries runs
    THEN only the dead entry is flagged indirect_entry_unknown
    """
    live = _registry(_row("probe.live", indirect="page-self-url"))
    indirect_js = {"probe.live": "page-self-url", "probe.gone": "server-built-url"}

    findings = find_stale_indirect_js_entries(indirect_js, {}, live)

    assert findings == [
        RegistryFinding("indirect_entry_unknown", "probe.gone", "no live endpoint")
    ]


def test_indirect_entry_for_linked_endpoint_is_redundant() -> None:
    """
    GIVEN INDIRECT_JS entries for an endpoint with a route key and one with a
        template ref
    WHEN find_stale_indirect_js_entries runs
    THEN both are flagged indirect_entry_redundant, naming the linkage
    """
    live = _registry(
        _row("probe.keyed", route_keys=["keyed"], indirect="page-self-url"),
        _row(
            "probe.templated",
            template_url_for=["pages/probe.html"],
            indirect="server-built-url",
        ),
    )
    indirect_js = {
        "probe.keyed": "page-self-url",
        "probe.templated": "server-built-url",
    }

    findings = find_stale_indirect_js_entries(indirect_js, {}, live)

    assert [(finding.kind, finding.endpoint) for finding in findings] == [
        ("indirect_entry_redundant", "probe.keyed"),
        ("indirect_entry_redundant", "probe.templated"),
    ]
    assert "keyed" in findings[0].detail
    assert "INDIRECT_JS_ENDPOINTS" in findings[0].detail
    assert "pages/probe.html" in findings[1].detail


def test_indirect_entry_also_in_no_js_is_flagged() -> None:
    """
    GIVEN INDIRECT_JS entries also covered by NO_JS_ENDPOINTS, one by an exact
        key and one by a `<blueprint>.*` key, plus an uncovered entry
    WHEN find_stale_indirect_js_entries runs
    THEN the two covered entries are flagged indirect_entry_also_no_js, naming
        the covering NO_JS key
    """
    live = _registry(
        _row("probe.exact", indirect="page-self-url", no_js="infra-probe"),
        _row("mobile.call", indirect="server-built-url", no_js="mobile-api"),
        _row("probe.clean", indirect="page-self-url"),
    )
    indirect_js = {
        "probe.exact": "page-self-url",
        "mobile.call": "server-built-url",
        "probe.clean": "page-self-url",
    }
    no_js = {"probe.exact": "infra-probe", "mobile.*": "mobile-api"}

    findings = find_stale_indirect_js_entries(indirect_js, no_js, live)

    assert findings == [
        RegistryFinding(
            "indirect_entry_also_no_js",
            "mobile.call",
            "also covered by NO_JS_ENDPOINTS key 'mobile.*'; keep only one",
        ),
        RegistryFinding(
            "indirect_entry_also_no_js",
            "probe.exact",
            "also covered by NO_JS_ENDPOINTS key 'probe.exact'; keep only one",
        ),
    ]


def test_edited_markdown_is_stale() -> None:
    """
    GIVEN a registry dict and its markdown, then a hand-edited copy
    WHEN diff_markdown runs on each
    THEN the pristine rendering is clean and the edited one is markdown_stale
    """
    registry = _registry(_row("probe.page", route_keys=["page"]))
    rendered = render_markdown(registry)

    assert diff_markdown(registry, rendered) == []
    assert diff_markdown(registry, rendered + "hand edit\n") == [
        RegistryFinding("markdown_stale", WHOLE_REGISTRY, REGENERATE_REMEDY)
    ]
