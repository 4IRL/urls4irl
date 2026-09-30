"""Endpoint registry audit helpers.

Pure — no app context, no DB. Every helper takes pre-built data (a live
registry dict from `build_registry(app)`, the committed JSON/markdown, the
`NO_JS_ENDPOINTS` / `INDIRECT_JS_ENDPOINTS` maps) and returns a sorted list of
findings. Used by both `tests/unit/test_endpoint_registry_audit.py` (unit
invariants) and the `flask endpoints audit` CLI (the registry-staleness CI
gate).

Five public helpers:
- `diff_registry()` — committed registry vs live app, field by field.
- `find_api_routes_without_js_linkage()` — `@api_route` rows with no JS channel.
- `find_stale_no_js_entries()` — `NO_JS_ENDPOINTS` keys that are dead or redundant.
- `find_stale_indirect_js_entries()` — `INDIRECT_JS_ENDPOINTS` keys that are
  dead, redundant, or also exempted by `NO_JS_ENDPOINTS`.
- `diff_markdown()` — committed markdown vs the markdown rendered from the committed JSON.

Each helper returns `[]` when its invariant holds. Non-empty lists are findings.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from backend.endpoint_registry.registry import (
    BLUEPRINT_WILDCARD_SUFFIX,
    render_markdown,
)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Endpoint placeholder for findings that concern a whole artifact, not a row.
WHOLE_REGISTRY = "*"

REGENERATE_REMEDY = "run make generate-endpoints"
JS_LINKAGE_REMEDY = (
    "add a JS_ROUTES/ADMIN_JS_ROUTES key, a template url_for reference, an "
    "INDIRECT_JS_ENDPOINTS source, or a NO_JS_ENDPOINTS reason in "
    "backend/utils/all_routes.py"
)

FindingKind = Literal[
    "missing_in_registry",
    "missing_in_app",
    "field_mismatch",
    "api_route_without_js_linkage",
    "no_js_entry_unknown",
    "no_js_entry_redundant",
    "indirect_entry_unknown",
    "indirect_entry_redundant",
    "indirect_entry_also_no_js",
    "markdown_stale",
]

Registry = dict[str, Any]


# ---------------------------------------------------------------------------
# Finding payload
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegistryFinding:
    """One audit finding: what kind, which endpoint (or `*`), and why."""

    kind: FindingKind
    endpoint: str
    detail: str


def _sorted_findings(findings: list[RegistryFinding]) -> list[RegistryFinding]:
    return sorted(
        findings, key=lambda finding: (finding.endpoint, finding.kind, finding.detail)
    )


def _rows_by_endpoint(registry: Registry) -> dict[str, list[dict[str, Any]]]:
    """Group rows per endpoint; an endpoint registered on several rules has several."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in registry["endpoints"]:
        grouped.setdefault(row["endpoint"], []).append(row)
    return grouped


def _sorted_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True))


def _field_mismatches(
    endpoint: str, live_row: dict[str, Any], committed_row: dict[str, Any]
) -> list[RegistryFinding]:
    return [
        RegistryFinding(
            "field_mismatch",
            endpoint,
            f"{field}: committed={committed_row.get(field)!r} "
            f"live={live_row.get(field)!r}",
        )
        for field in sorted(live_row.keys() | committed_row.keys())
        if live_row.get(field) != committed_row.get(field)
    ]


def _direct_linkage(endpoint_rows: list[dict[str, Any]]) -> list[str]:
    """Route keys + template refs of an endpoint (every rule's row shares `js`)."""
    js_linkage = endpoint_rows[0]["js"]
    return js_linkage["route_keys"] + js_linkage["template_url_for"]


def _no_js_key_covering(endpoint: str, no_js: Mapping[str, str]) -> str | None:
    """Return the `NO_JS_ENDPOINTS` key covering `endpoint`: exact, then `<bp>.*`."""
    if endpoint in no_js:
        return endpoint
    wildcard_key = endpoint.rpartition(".")[0] + BLUEPRINT_WILDCARD_SUFFIX
    return wildcard_key if wildcard_key in no_js else None


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def diff_registry(live: Registry, committed: Registry) -> list[RegistryFinding]:
    """Diff the committed registry against the live one, per endpoint and field.

    - `missing_in_registry` — endpoint is live but not committed.
    - `missing_in_app` — endpoint is committed but no longer live.
    - `field_mismatch` — for a single-rule endpoint, one finding per differing
      top-level row field; for an endpoint registered on several rules, one
      finding listing both sides' rows when they differ.
    """
    live_rows = _rows_by_endpoint(live)
    committed_rows = _rows_by_endpoint(committed)
    findings: list[RegistryFinding] = []

    for endpoint in live_rows.keys() - committed_rows.keys():
        findings.append(
            RegistryFinding(
                "missing_in_registry",
                endpoint,
                f"live endpoint not committed; {REGENERATE_REMEDY}",
            )
        )
    for endpoint in committed_rows.keys() - live_rows.keys():
        findings.append(
            RegistryFinding(
                "missing_in_app",
                endpoint,
                f"committed endpoint no longer live; {REGENERATE_REMEDY}",
            )
        )
    for endpoint in live_rows.keys() & committed_rows.keys():
        live_endpoint_rows = live_rows[endpoint]
        committed_endpoint_rows = committed_rows[endpoint]
        if len(live_endpoint_rows) == 1 and len(committed_endpoint_rows) == 1:
            findings.extend(
                _field_mismatches(
                    endpoint, live_endpoint_rows[0], committed_endpoint_rows[0]
                )
            )
            continue
        sorted_live = _sorted_rows(live_endpoint_rows)
        sorted_committed = _sorted_rows(committed_endpoint_rows)
        if sorted_live != sorted_committed:
            findings.append(
                RegistryFinding(
                    "field_mismatch",
                    endpoint,
                    f"rows: committed={sorted_committed!r} live={sorted_live!r}",
                )
            )
    return _sorted_findings(findings)


def find_api_routes_without_js_linkage(live: Registry) -> list[RegistryFinding]:
    """Flag `@api_route` rows (non-null `schemas`) reachable through no JS channel."""
    findings = [
        RegistryFinding(
            "api_route_without_js_linkage", row["endpoint"], JS_LINKAGE_REMEDY
        )
        for row in live["endpoints"]
        if row["schemas"] is not None
        and not row["js"]["route_keys"]
        and not row["js"]["template_url_for"]
        and row["js"]["indirect"] is None
        and row["js"]["no_js"] is None
    ]
    return _sorted_findings(findings)


def find_stale_no_js_entries(
    no_js: Mapping[str, str], live: Registry
) -> list[RegistryFinding]:
    """Flag `NO_JS_ENDPOINTS` keys that name nothing live, or a linked endpoint.

    - `no_js_entry_unknown` — an exact key matches no live endpoint, or a
      `<blueprint>.*` key matches no live blueprint.
    - `no_js_entry_redundant` — an exactly-keyed endpoint also has a route key
      or a template `url_for` reference, so the exemption is not needed.
    """
    live_rows = _rows_by_endpoint(live)
    live_blueprints = {row["blueprint"] for row in live["endpoints"]}
    findings: list[RegistryFinding] = []

    for key in no_js:
        if key.endswith(BLUEPRINT_WILDCARD_SUFFIX):
            blueprint = key.removesuffix(BLUEPRINT_WILDCARD_SUFFIX)
            if blueprint not in live_blueprints:
                findings.append(
                    RegistryFinding(
                        "no_js_entry_unknown", key, f"no live blueprint {blueprint!r}"
                    )
                )
            continue
        endpoint_rows = live_rows.get(key)
        if endpoint_rows is None:
            findings.append(
                RegistryFinding("no_js_entry_unknown", key, "no live endpoint")
            )
            continue
        linkage = _direct_linkage(endpoint_rows)
        if linkage:
            findings.append(
                RegistryFinding(
                    "no_js_entry_redundant",
                    key,
                    f"already linked via {', '.join(linkage)}; remove the NO_JS_ENDPOINTS entry",
                )
            )
    return _sorted_findings(findings)


def find_stale_indirect_js_entries(
    indirect_js: Mapping[str, str], no_js: Mapping[str, str], live: Registry
) -> list[RegistryFinding]:
    """Flag `INDIRECT_JS_ENDPOINTS` keys that are dead, redundant or contradicted.

    - `indirect_entry_unknown` — the key matches no live endpoint.
    - `indirect_entry_redundant` — the endpoint also has a route key or a
      template `url_for` reference, so the indirect source is not needed.
    - `indirect_entry_also_no_js` — a `NO_JS_ENDPOINTS` key (exact or
      `<blueprint>.*`) also covers the endpoint: it cannot both be called by
      the frontend and have no frontend caller.
    """
    live_rows = _rows_by_endpoint(live)
    findings: list[RegistryFinding] = []

    for key in indirect_js:
        no_js_key = _no_js_key_covering(key, no_js)
        if no_js_key is not None:
            findings.append(
                RegistryFinding(
                    "indirect_entry_also_no_js",
                    key,
                    f"also covered by NO_JS_ENDPOINTS key {no_js_key!r}; keep only one",
                )
            )
        endpoint_rows = live_rows.get(key)
        if endpoint_rows is None:
            findings.append(
                RegistryFinding("indirect_entry_unknown", key, "no live endpoint")
            )
            continue
        linkage = _direct_linkage(endpoint_rows)
        if linkage:
            findings.append(
                RegistryFinding(
                    "indirect_entry_redundant",
                    key,
                    f"already linked via {', '.join(linkage)}; "
                    "remove the INDIRECT_JS_ENDPOINTS entry",
                )
            )
    return _sorted_findings(findings)


def diff_markdown(
    committed_json: Registry, committed_markdown: str
) -> list[RegistryFinding]:
    """Flag committed markdown that is not the rendering of the committed JSON."""
    if render_markdown(committed_json) == committed_markdown:
        return []
    return [RegistryFinding("markdown_stale", WHOLE_REGISTRY, REGENERATE_REMEDY)]


__all__ = [
    "JS_LINKAGE_REMEDY",
    "REGENERATE_REMEDY",
    "WHOLE_REGISTRY",
    "RegistryFinding",
    "diff_markdown",
    "diff_registry",
    "find_api_routes_without_js_linkage",
    "find_stale_indirect_js_entries",
    "find_stale_no_js_entries",
]
