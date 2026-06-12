"""Anonymous-metrics event coverage audit helpers.

Pure AST + enum/dict introspection. No Flask app context, no DB, no Redis.
Used by both `tests/unit/test_event_coverage.py` (unit invariants) and the
`flask metrics audit` CLI (the event-coverage-staleness CI gate).

Five public helpers:
- `find_orphan_event_names()` — EventName members with zero external references.
- `find_string_literal_record_event_callers()` — record_event("foo", ...) callers.
- `find_missing_dimension_model_entries()` — EventName members absent from DIMENSION_MODELS.
- `diff_dimension_literals_vs_registry()` — Pydantic Literal vs EVENT_REGISTRY dim values.
- `diff_registry_vs_event_name()` — bidirectional EVENT_REGISTRY/EventName drift.

Each helper returns `[]` when its invariant holds. Non-empty lists are findings.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args, get_origin

from backend.metrics.dimension_models import DIMENSION_MODELS
from backend.metrics.event_registry import EVENT_REGISTRY
from backend.metrics.events import (
    EVENT_CATEGORY,
    EVENT_DESCRIPTIONS,
    EventCategory,
    EventName,
)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


# Files excluded from orphan-detection — these are the metrics-module
# definitions themselves, so EventName.<MEMBER> references inside them must
# NOT count as "external usage". The audit module itself is included so its
# own EventName import does not register references. Paths are anchored to
# the on-disk location of `backend/` (computed from `__file__`) so the
# exclusion match works whether the caller passes a relative or absolute
# `backend_root` to `find_orphan_event_names`.
_BACKEND_DIR: Path = Path(__file__).resolve().parent.parent
_METRICS_INTERNAL_FILES: frozenset[Path] = frozenset(
    {
        _BACKEND_DIR / "metrics" / "audit.py",
        _BACKEND_DIR / "metrics" / "events.py",
        _BACKEND_DIR / "metrics" / "dimension_models.py",
        _BACKEND_DIR / "metrics" / "resources.py",
        _BACKEND_DIR / "extensions" / "metrics" / "registry_sync.py",
        _BACKEND_DIR / "extensions" / "metrics" / "dim_types_generator.py",
        _BACKEND_DIR / "cli" / "metrics.py",
    }
)


# UI events are wired via the dim_types_generator codegen pipeline — their
# only "reference" in code is in dim_types_generator.py (which iterates every
# EventCategory.UI member by construction). They appear in frontend TS via
# the generated `UI_EVENTS` constant, not via Python attribute access. Treat
# them as wired-by-codegen and skip the AST orphan check; the wiring proof
# lives in the TS test surface (e.g., `metrics-client.ts`), not in `backend/`.
_ORPHAN_CHECK_CATEGORIES: frozenset[EventCategory] = frozenset(
    {EventCategory.API, EventCategory.DOMAIN}
)


# Allowlist of EventName members deferred by explicit design decision (not
# a real coverage gap). `URL_ACCESSED` is intentionally deferred in favour of
# the UI-side `UI_URL_ACCESS` event, which captures the same user behaviour
# with richer dimensions and without any backend service-layer overhead.
_INTENTIONALLY_UNTRACKED_EVENTS: frozenset[EventName] = frozenset(
    {EventName.URL_ACCESSED}
)


# ---------------------------------------------------------------------------
# Dataclasses for finding payloads
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StringLiteralFinding:
    """A record_event(...) caller whose first positional arg is a bare string literal."""

    file: Path
    line: int
    literal: str


@dataclass(frozen=True)
class DimensionLiteralFinding:
    """A drift between the EVENT_REGISTRY documented dim values and the code-side Literal[...]."""

    event: EventName
    field: str
    code_values: tuple[str, ...]
    registry_values: tuple[str, ...]


@dataclass(frozen=True)
class RegistryDriftFinding:
    """A drift between EVENT_REGISTRY and the EventName enum / derived dicts."""

    kind: Literal[
        "missing_in_registry",
        "missing_in_code",
        "description_mismatch",
        "category_mismatch",
    ]
    event: str
    detail: str


# ---------------------------------------------------------------------------
# AST walkers — shared helpers
# ---------------------------------------------------------------------------


def _iter_python_files(backend_root: Path) -> list[Path]:
    """Yield every `.py` file under `backend_root`, sorted for determinism."""
    return sorted(backend_root.rglob("*.py"))


def _parse_python_file(file_path: Path) -> ast.AST | None:
    """Parse a Python file to AST. Returns `None` on syntax errors (skip silently)."""
    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        return ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return None


def _collect_event_name_attribute_references(tree: ast.AST) -> set[str]:
    """Return every `MEMBER` referenced as `EventName.MEMBER` in the AST."""
    references: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "EventName"
        ):
            references.add(node.attr)
    return references


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def find_orphan_event_names(
    backend_root: Path = Path("backend"),
) -> list[EventName]:
    """Return `EventName` members with zero external references.

    Walks every `.py` file under `backend_root`, collects all
    `EventName.<MEMBER>` attribute references, then returns the set of
    EventName members that have:
    - zero references outside the metrics-module internals AND
    - a category in `_ORPHAN_CHECK_CATEGORIES` (API + DOMAIN — UI events
      are wired via codegen, not via Python attribute access) AND
    - membership NOT in `_INTENTIONALLY_UNTRACKED_EVENTS` (deferred by
      explicit design decision — see the comment on that constant).
    """
    referenced_externally: set[str] = set()
    for python_file in _iter_python_files(backend_root):
        # `_METRICS_INTERNAL_FILES` holds absolute paths anchored at the on-disk
        # `backend/` directory, so we resolve the candidate file to absolute
        # before comparing. Probe trees under `tmp_path/backend/...` will never
        # match any entry, which is the intended behaviour.
        if python_file.resolve() in _METRICS_INTERNAL_FILES:
            continue
        tree = _parse_python_file(python_file)
        if tree is None:
            continue
        referenced_externally.update(_collect_event_name_attribute_references(tree))

    return [
        event_name
        for event_name in EventName
        if (
            event_name.name not in referenced_externally
            and EVENT_CATEGORY[event_name] in _ORPHAN_CHECK_CATEGORIES
            and event_name not in _INTENTIONALLY_UNTRACKED_EVENTS
        )
    ]


def find_string_literal_record_event_callers(
    backend_root: Path = Path("backend"),
) -> list[StringLiteralFinding]:
    """Return every `record_event("foo", ...)` style caller.

    Walks every `.py` file under `backend_root` for `Call` nodes whose `func`
    is either `Name(id='record_event')` or `Attribute(attr='record_event')`,
    and whose positional arg 0 is a `Constant(value=<str>)`.
    """
    findings: list[StringLiteralFinding] = []
    for python_file in _iter_python_files(backend_root):
        tree = _parse_python_file(python_file)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not _is_record_event_call(node):
                continue
            if not node.args:
                continue
            first_positional_arg = node.args[0]
            if isinstance(first_positional_arg, ast.Constant) and isinstance(
                first_positional_arg.value, str
            ):
                findings.append(
                    StringLiteralFinding(
                        file=python_file,
                        line=node.lineno,
                        literal=first_positional_arg.value,
                    )
                )
    return findings


def _is_record_event_call(call_node: ast.Call) -> bool:
    """Return True if the Call node targets a function named `record_event`.

    Handles both `record_event(...)` (Name) and `module.record_event(...)`
    (Attribute) shapes.
    """
    if isinstance(call_node.func, ast.Name):
        return call_node.func.id == "record_event"
    if isinstance(call_node.func, ast.Attribute):
        return call_node.func.attr == "record_event"
    return False


def find_missing_dimension_model_entries() -> list[EventName]:
    """Return `EventName` members absent from `DIMENSION_MODELS`."""
    registered_events: set[EventName] = set(DIMENSION_MODELS.keys())
    return [
        event_name for event_name in EventName if event_name not in registered_events
    ]


def diff_dimension_literals_vs_registry() -> list[DimensionLiteralFinding]:
    """Diff EVENT_REGISTRY-documented dim values vs code-side Pydantic `Literal[...]` args.

    For every (event_name, dim_field) pair where the code-side annotation is a
    `Literal[...]`, compare the literal arg set against the `dimensions` mapping
    in `EVENT_REGISTRY[event]`. Fields whose code-side annotation is non-Literal
    (int, str, bool, IntEnum) are skipped — both sides agree there is no
    closed-set constraint.
    """
    findings: list[DimensionLiteralFinding] = []
    for event_name, dim_model in DIMENSION_MODELS.items():
        if dim_model is None:
            continue
        registry_entry = EVENT_REGISTRY.get(event_name)
        if registry_entry is None:
            continue

        for field_name, field_info in dim_model.model_fields.items():
            annotation = field_info.annotation
            if get_origin(annotation) is not Literal:
                continue
            code_values = tuple(str(value) for value in get_args(annotation))
            registry_values = registry_entry.dimensions.get(field_name)
            if registry_values is None:
                # EVENT_REGISTRY does not document this field. Two legitimate
                # reasons: the field is a closed-set Literal that the registry
                # author chose to leave out (e.g. API_HIT's top-level
                # endpoint/method/status_code columns), or the registry uses a
                # free-form descriptor for a non-Literal field. Code is the
                # authoritative source for the Literal; skip silently.
                continue
            if set(code_values) != set(registry_values):
                findings.append(
                    DimensionLiteralFinding(
                        event=event_name,
                        field=field_name,
                        code_values=code_values,
                        registry_values=registry_values,
                    )
                )
    return findings


def diff_registry_vs_event_name() -> list[RegistryDriftFinding]:
    """Bidirectional drift between `EVENT_REGISTRY` and the `EventName` enum.

    Findings:
    - `missing_in_registry` — `EventName` member has no `EVENT_REGISTRY` entry.
    - `missing_in_code` — `EVENT_REGISTRY` key has no matching `EventName` member.
    - `description_mismatch` — entry description != `EVENT_DESCRIPTIONS[member]`.
    - `category_mismatch` — entry category != `EVENT_CATEGORY[member]`.

    In the current architecture `EVENT_DESCRIPTIONS` / `EVENT_CATEGORY` are
    derived projections of `EVENT_REGISTRY`, so description/category mismatches
    are reachable only if a future refactor breaks that derivation. The bidir
    keys-vs-enum check remains the primary drift signal.
    """
    findings: list[RegistryDriftFinding] = []
    code_event_names: set[str] = {event_name.name for event_name in EventName}

    for event_name in EventName:
        registry_entry = EVENT_REGISTRY.get(event_name)
        if registry_entry is None:
            findings.append(
                RegistryDriftFinding(
                    kind="missing_in_registry",
                    event=event_name.name,
                    detail="no EVENT_REGISTRY entry",
                )
            )
            continue

        expected_description = EVENT_DESCRIPTIONS[event_name]
        if registry_entry.description != expected_description:
            findings.append(
                RegistryDriftFinding(
                    kind="description_mismatch",
                    event=event_name.name,
                    detail=(
                        f"registry={registry_entry.description!r} vs "
                        f"code={expected_description!r}"
                    ),
                )
            )

        expected_category = EVENT_CATEGORY[event_name]
        if registry_entry.category != expected_category:
            findings.append(
                RegistryDriftFinding(
                    kind="category_mismatch",
                    event=event_name.name,
                    detail=(
                        f"registry={registry_entry.category.value!r} vs "
                        f"code={expected_category.value!r}"
                    ),
                )
            )

    for registry_event in EVENT_REGISTRY:
        if registry_event.name not in code_event_names:
            findings.append(
                RegistryDriftFinding(
                    kind="missing_in_code",
                    event=registry_event.name,
                    detail="EVENT_REGISTRY entry has no matching EventName member",
                )
            )

    return findings


__all__ = [
    "DimensionLiteralFinding",
    "RegistryDriftFinding",
    "StringLiteralFinding",
    "diff_dimension_literals_vs_registry",
    "diff_registry_vs_event_name",
    "find_missing_dimension_model_entries",
    "find_orphan_event_names",
    "find_string_literal_record_event_callers",
]
