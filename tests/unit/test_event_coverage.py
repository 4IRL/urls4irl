"""Unit-scope coverage audit for the anonymous-metrics EventName surface.

Asserts the invariants the `flask metrics audit` CLI enforces, but at unit scope
so the staleness CI workflow does not need Postgres/Redis. All invariants are
pure AST walks + enum/dict introspection — no Flask app context required.

Each test wraps one helper from `backend.metrics.audit`; the helper returns the
list of findings (`[]` means clean). When CI sees `[]` for every category the
event-coverage gate is green.
"""

from __future__ import annotations

import pytest

from backend.metrics.audit import (
    diff_dimension_literals_vs_registry,
    diff_registry_vs_event_name,
    find_missing_dimension_model_entries,
    find_orphan_event_names,
    find_string_literal_record_event_callers,
)
from backend.metrics.event_registry import EVENT_REGISTRY
from backend.metrics.events import EventName

pytestmark = pytest.mark.unit


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


def test_event_registry_keys_match_event_name_enum() -> None:
    """`EVENT_REGISTRY.keys()` and `set(EventName)` must be identical.

    Catches drift in either direction: an enum member added without a registry
    entry (description/category undefined) or a registry entry whose enum
    member has been removed.
    """
    registry_keys = set(EVENT_REGISTRY.keys())
    enum_members = set(EventName)
    missing_in_registry = enum_members - registry_keys
    extra_in_registry = registry_keys - enum_members
    assert missing_in_registry == set() and extra_in_registry == set(), (
        f"EVENT_REGISTRY drift vs EventName enum: "
        f"missing_in_registry={[member.name for member in missing_in_registry]}, "
        f"extra_in_registry={[member.name for member in extra_in_registry]}. "
        "Add or remove the corresponding entry in backend/metrics/event_registry.py."
    )


def test_dimension_literals_match_event_registry() -> None:
    """`EVENT_REGISTRY[event].dimensions` must match the code-side Pydantic Literals.

    Two-way diff: (a) the registry's documented value tuples, (b) the
    `Literal[...]` args of the Pydantic field in
    `DIMENSION_MODELS[event].model_fields[field]`. Fields whose code-side
    annotation is non-Literal (int, str, bool) are skipped — both sides agree
    there is no closed-set constraint.
    """
    findings = diff_dimension_literals_vs_registry()
    assert findings == [], (
        f"Found {len(findings)} dimension literal drift finding(s): "
        f"{[(finding.event.name, finding.field, finding.code_values, finding.registry_values) for finding in findings]}. "
        "Reconcile EVENT_REGISTRY against the code-side Literal[...] type."
    )


def test_no_registry_drift_against_event_name_enum() -> None:
    """`EVENT_REGISTRY` entries must align with `EventName` + EVENT_CATEGORY + EVENT_DESCRIPTIONS.

    Bidirectional: every `EventName` member has a registry entry; every
    registry key maps to an enum member; description matches
    `EVENT_DESCRIPTIONS[member]`; category matches `EVENT_CATEGORY[member]`.
    The description / category arms are guard rails — both EVENT_CATEGORY and
    EVENT_DESCRIPTIONS are derived projections of EVENT_REGISTRY today, so
    these arms only fire if a future refactor breaks the derivation.
    """
    findings = diff_registry_vs_event_name()
    assert findings == [], (
        f"Found {len(findings)} registry drift finding(s): "
        f"{[(finding.kind, finding.event, finding.detail) for finding in findings]}. "
        "Reconcile EVENT_REGISTRY against the EventName enum."
    )
