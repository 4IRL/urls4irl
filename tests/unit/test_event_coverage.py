"""Unit-scope coverage audit for the anonymous-metrics EventName surface.

Asserts the invariants the `flask metrics audit` CLI enforces, but at unit scope
so the staleness CI workflow does not need Postgres/Redis. All invariants are
pure AST walks + enum/dict introspection — no Flask app context required.

Each test wraps one helper from `backend.metrics.audit`; the helper returns the
list of findings (`[]` means clean). When CI sees `[]` for every category the
event-coverage gate is green.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.metrics.audit import (
    diff_dimension_literals_vs_registry_markdown,
    diff_registry_markdown_vs_event_name,
    find_missing_dimension_model_entries,
    find_orphan_event_names,
    find_string_literal_record_event_callers,
)

pytestmark = pytest.mark.unit


REGISTRY_MARKDOWN: Path = Path("plans/anonymous-metrics/anonymous-metrics-master.md")


def test_no_orphan_event_name_members() -> None:
    """Every `EventName` member must be referenced outside the metrics module.

    An orphan is an enum member that has zero `EventName.<MEMBER>` references
    in any file under `backend/` that is NOT one of the metrics-internal
    files (events.py, dimension_models.py, resources.py, registry_sync.py,
    dim_types_generator.py, cli/metrics.py, audit.py itself).
    """
    orphans = find_orphan_event_names()
    assert orphans == [], (
        f"Found {len(orphans)} orphan EventName member(s): "
        f"{[orphan.name for orphan in orphans]}. "
        "Either wire the member into a record_event() call or remove it."
    )


def test_no_string_literal_record_event_callers() -> None:
    """No caller may pass a bare string literal as `record_event(...)`'s first arg.

    The enum-typed first positional argument is what gives the metrics writer
    its Pydantic-validated dimension shape. A string-literal caller silently
    bypasses validation.
    """
    callers = find_string_literal_record_event_callers()
    assert callers == [], (
        f"Found {len(callers)} string-literal record_event caller(s): "
        f"{[(str(caller.file), caller.line, caller.literal) for caller in callers]}. "
        "Convert each to EventName.<MEMBER>."
    )


def test_every_event_name_has_dimension_model_entry() -> None:
    """Every `EventName` member must appear as a key in `DIMENSION_MODELS`.

    Mirrors the integration-scope assertion in
    `tests/integration/system/test_dimension_models.py`, but lives at unit
    scope so the staleness workflow does not need Postgres/Redis.
    """
    missing = find_missing_dimension_model_entries()
    assert missing == [], (
        f"Found {len(missing)} EventName member(s) missing from DIMENSION_MODELS: "
        f"{[event_name.name for event_name in missing]}. "
        "Add a `_Dim<EventName>` entry or use `_DimDeviceOnly` for no-dim events."
    )


def test_dimension_literals_match_registry_markdown() -> None:
    """Markdown registry's documented `Dimensions` cells must match the code-side Pydantic Literals.

    Three-way diff: (a) markdown documented value set, (b) the `Literal[...]`
    args of the Pydantic field in `DIMENSION_MODELS[event].model_fields[field]`.
    Fields whose code-side annotation is non-Literal (int, str, bool) are
    skipped — both sides agree there is no closed-set constraint.
    """
    findings = diff_dimension_literals_vs_registry_markdown(REGISTRY_MARKDOWN)
    assert findings == [], (
        f"Found {len(findings)} dimension literal drift finding(s): "
        f"{[(finding.event.name, finding.field, finding.code_values, finding.registry_values) for finding in findings]}. "
        "Reconcile the markdown registry against the code-side Literal[...] type."
    )


def test_no_registry_drift_against_event_name_enum() -> None:
    """Markdown Event Registry rows must match the `EventName` + EVENT_CATEGORY + EVENT_DESCRIPTIONS state.

    Bidirectional: every `EventName` member has a registry row; every registry
    row maps to an enum member; the description column matches
    `EVENT_DESCRIPTIONS[member]`; the category row groups match
    `EVENT_CATEGORY[member]`.
    """
    findings = diff_registry_markdown_vs_event_name(REGISTRY_MARKDOWN)
    assert findings == [], (
        f"Found {len(findings)} registry drift finding(s): "
        f"{[(finding.kind, finding.event, finding.detail) for finding in findings]}. "
        "Reconcile the master plan markdown registry against the EventName enum."
    )
