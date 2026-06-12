"""Anonymous-metrics event coverage audit helpers.

Pure AST + enum/dict introspection. No Flask app context, no DB, no Redis.
Used by both `tests/unit/test_event_coverage.py` (unit invariants) and the
`flask metrics audit` CLI (Step 2 of the coverage-audit plan, Step 9 CI gate).

Five public helpers:
- `find_orphan_event_names()` — EventName members with zero external references.
- `find_string_literal_record_event_callers()` — record_event("foo", ...) callers.
- `find_missing_dimension_model_entries()` — EventName members absent from DIMENSION_MODELS.
- `diff_dimension_literals_vs_registry_markdown(path)` — Pydantic Literal vs documented set.
- `diff_registry_markdown_vs_event_name(path)` — bidirectional registry/enum drift.

Each helper returns `[]` when its invariant holds. Non-empty lists are findings.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args, get_origin

from backend.metrics.dimension_models import DIMENSION_MODELS
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
# a real coverage gap). Each entry is paired with the master plan line that
# records the deferral so the next maintainer can verify the decision still
# holds. `URL_ACCESSED` is deferred per master plan line 363 in favour of
# the UI-side `UI_URL_ACCESS` event.
_INTENTIONALLY_UNTRACKED_EVENTS: frozenset[EventName] = frozenset(
    {EventName.URL_ACCESSED}
)


# Markdown Event Registry section heading (master plan).
_REGISTRY_SECTION_HEADING: str = "## Event Registry"


# Sub-section headings inside `## Event Registry` — each maps to one
# EventCategory. The category mapping is what `diff_registry_markdown_vs_event_name`
# uses to cross-check `EVENT_CATEGORY[member]`.
_REGISTRY_SUBSECTION_HEADING_PREFIX: str = "### "
_REGISTRY_CATEGORY_BY_SUBSECTION: dict[str, EventCategory] = {
    "API": EventCategory.API,
    "Domain": EventCategory.DOMAIN,
    "UI": EventCategory.UI,
}


# Pattern for a registry table row: `| EventName | Description | Dimensions | Phase |`
# Sub-group separator rows like `| **UTubs** | | | |` are excluded by requiring
# the first cell to look like an UPPER_SNAKE_CASE identifier.
_REGISTRY_ROW_PATTERN: re.Pattern[str] = re.compile(
    r"^\|\s*(?P<event>[A-Z][A-Z0-9_]+)\s*\|"
    r"\s*(?P<description>[^|]*?)\s*\|"
    r"\s*(?P<dimensions>[^|]*?)\s*\|"
    r"\s*(?P<phase>[^|]*?)\s*\|"
    r"\s*$"
)


# Pattern for a dim cell entry: backtick-quoted field name followed by a
# colon-separated list of backtick-quoted values, e.g.:
#   `trigger`: `pencil_icon` / `keyboard`
# A trailing free-form description (e.g. `active_tag_count`: N) is captured
# as the value list "N" so the helper can skip non-Literal fields.
_REGISTRY_DIM_FIELD_PATTERN: re.Pattern[str] = re.compile(
    r"`(?P<field>[a-zA-Z_][a-zA-Z0-9_]*)`\s*:\s*(?P<values>[^,]+)"
)
_REGISTRY_DIM_VALUE_PATTERN: re.Pattern[str] = re.compile(r"`([^`]+)`")


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
    """A drift between the markdown registry's documented dim values and the code-side Literal[...]."""

    event: EventName
    field: str
    code_values: tuple[str, ...]
    registry_values: tuple[str, ...]


@dataclass(frozen=True)
class RegistryDriftFinding:
    """A drift between the markdown registry and the EventName enum."""

    kind: Literal[
        "missing_in_markdown",
        "missing_in_code",
        "description_mismatch",
        "category_mismatch",
    ]
    event: str
    detail: str


@dataclass(frozen=True)
class _ParsedMarkdownRow:
    """One row of the markdown Event Registry table.

    Internal — emitted by `_parse_registry_markdown` and consumed by the two
    `diff_*` helpers. Not part of the public API.
    """

    description: str
    dimensions: dict[str, tuple[str, ...]]
    category: EventCategory


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
      explicit design decision; see master plan line 363 for URL_ACCESSED).
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


def diff_dimension_literals_vs_registry_markdown(
    registry_md: Path,
) -> list[DimensionLiteralFinding]:
    """Diff documented dim values (markdown) vs code-side Pydantic `Literal[...]` args.

    For every (event_name, dim_field) pair where the code-side annotation is a
    `Literal[...]`, compare the literal arg set against the markdown registry's
    documented value set. Fields whose code-side annotation is non-Literal
    (int, str, bool, IntEnum) are skipped — both sides agree there is no
    closed-set constraint.
    """
    markdown_rows: dict[str, _ParsedMarkdownRow] = _parse_registry_markdown(registry_md)

    findings: list[DimensionLiteralFinding] = []
    for event_name, dim_model in DIMENSION_MODELS.items():
        if dim_model is None:
            continue
        markdown_row = markdown_rows.get(event_name.name)
        if markdown_row is None:
            continue

        for field_name, field_info in dim_model.model_fields.items():
            annotation = field_info.annotation
            if get_origin(annotation) is not Literal:
                continue
            code_values = tuple(str(value) for value in get_args(annotation))
            registry_values = markdown_row.dimensions.get(field_name)
            if registry_values is None:
                # Markdown does not document this field at all — distinct from
                # the "documented but unenumerated" case below. This typically
                # arises when the markdown row uses a free-form descriptor
                # (e.g., "(top-level columns)" for API_HIT) instead of an
                # enumerated `field: value1 / value2` clause. Code is the
                # authoritative source for the Literal; skip silently rather
                # than flag a drift the registry cannot meaningfully express.
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


def diff_registry_markdown_vs_event_name(
    registry_md: Path,
) -> list[RegistryDriftFinding]:
    """Bidirectional drift between markdown Event Registry and EventName + EVENT_* dicts.

    Findings:
    - `missing_in_markdown` — `EventName` member has no registry row.
    - `missing_in_code` — registry row's first cell does not match an enum member.
    - `description_mismatch` — registry Description column != `EVENT_DESCRIPTIONS[member]`.
    - `category_mismatch` — registry sub-section heading group != `EVENT_CATEGORY[member]`.
    """
    markdown_rows: dict[str, _ParsedMarkdownRow] = _parse_registry_markdown(registry_md)
    findings: list[RegistryDriftFinding] = []

    code_event_names: set[str] = {event_name.name for event_name in EventName}

    for event_name in EventName:
        markdown_row = markdown_rows.get(event_name.name)
        if markdown_row is None:
            findings.append(
                RegistryDriftFinding(
                    kind="missing_in_markdown",
                    event=event_name.name,
                    detail="no registry row in master plan",
                )
            )
            continue

        expected_description = EVENT_DESCRIPTIONS[event_name]
        if markdown_row.description != expected_description:
            findings.append(
                RegistryDriftFinding(
                    kind="description_mismatch",
                    event=event_name.name,
                    detail=(
                        f"markdown={markdown_row.description!r} vs "
                        f"code={expected_description!r}"
                    ),
                )
            )

        expected_category = EVENT_CATEGORY[event_name]
        if markdown_row.category != expected_category:
            findings.append(
                RegistryDriftFinding(
                    kind="category_mismatch",
                    event=event_name.name,
                    detail=(
                        f"markdown={markdown_row.category.value!r} vs "
                        f"code={expected_category.value!r}"
                    ),
                )
            )

    for markdown_event_name in markdown_rows:
        if markdown_event_name not in code_event_names:
            findings.append(
                RegistryDriftFinding(
                    kind="missing_in_code",
                    event=markdown_event_name,
                    detail="registry row has no matching EventName member",
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Markdown registry parser
# ---------------------------------------------------------------------------


def _parse_registry_markdown(registry_md: Path) -> dict[str, _ParsedMarkdownRow]:
    """Walk the master plan's `## Event Registry` section into a dict.

    State machine:
    - Outside `## Event Registry` → skip everything.
    - Inside `## Event Registry`, sub-section heading determines current category.
    - Table rows matching `_REGISTRY_ROW_PATTERN` populate the dict.
    """
    parsed_rows: dict[str, _ParsedMarkdownRow] = {}
    text = registry_md.read_text(encoding="utf-8")

    inside_registry_section: bool = False
    current_category: EventCategory | None = None

    for line in text.splitlines():
        stripped_line = line.strip()

        # Detect section / sub-section transitions.
        if stripped_line.startswith("## "):
            inside_registry_section = stripped_line == _REGISTRY_SECTION_HEADING
            current_category = None
            continue
        if not inside_registry_section:
            continue
        if stripped_line.startswith(_REGISTRY_SUBSECTION_HEADING_PREFIX):
            current_category = _classify_subsection_heading(stripped_line)
            continue
        if current_category is None:
            continue

        row_match = _REGISTRY_ROW_PATTERN.match(line)
        if row_match is None:
            continue

        event_name_cell = row_match.group("event")
        description_cell = row_match.group("description")
        dimensions_cell = row_match.group("dimensions")

        dimensions = _parse_dim_cell(dimensions_cell)
        parsed_rows[event_name_cell] = _ParsedMarkdownRow(
            description=description_cell,
            dimensions=dimensions,
            category=current_category,
        )

    return parsed_rows


def _classify_subsection_heading(heading_line: str) -> EventCategory | None:
    """Map `### API (...)`, `### Domain (...)`, `### UI (...)` to an EventCategory.

    Returns `None` for any other sub-heading (e.g., `### Coverage Summary`).
    """
    body_after_prefix = heading_line[len(_REGISTRY_SUBSECTION_HEADING_PREFIX) :].strip()
    first_word = body_after_prefix.split(" ", maxsplit=1)[0]
    return _REGISTRY_CATEGORY_BY_SUBSECTION.get(first_word)


def _parse_dim_cell(dimensions_cell: str) -> dict[str, tuple[str, ...]]:
    r"""Parse the `Dimensions` table cell into `{field_name: (value, value, ...)}`.

    Handles:
    - `—` (em-dash) or empty cell → returns {}.
    - `\`field\`: \`value1\` / \`value2\`` style closed-set Literals.
    - `\`field\`: N` style non-Literal placeholder → mapped to `("N",)` so callers can detect it.
    """
    # Em-dash + empty marker = no dimensions documented.
    if not dimensions_cell or dimensions_cell == "—":
        return {}

    parsed_fields: dict[str, tuple[str, ...]] = {}
    # Splitting by comma is too aggressive — values can themselves contain
    # spaces. We use the regex to find every `field: tail` pair greedily.
    for field_match in _REGISTRY_DIM_FIELD_PATTERN.finditer(dimensions_cell):
        field_name = field_match.group("field")
        values_section_start = field_match.end()
        # The values for this field run until the next `<comma><backtick>field<backtick>:`
        # boundary or the end of the cell.
        next_field_match = _REGISTRY_DIM_FIELD_PATTERN.search(
            dimensions_cell, values_section_start
        )
        if next_field_match is None:
            values_section = dimensions_cell[field_match.start("values") :]
        else:
            values_section = dimensions_cell[
                field_match.start("values") : next_field_match.start()
            ]
        # Strip a trailing comma if present (separates two field clauses).
        values_section = values_section.rstrip(",").strip()
        backtick_values = _REGISTRY_DIM_VALUE_PATTERN.findall(values_section)
        if backtick_values:
            parsed_fields[field_name] = tuple(backtick_values)
        else:
            # Non-Literal placeholder like `N` (active_tag_count). Mark as "open"
            # by recording the raw text so callers can detect and skip.
            parsed_fields[field_name] = (values_section,)

    return parsed_fields


__all__ = [
    "DimensionLiteralFinding",
    "RegistryDriftFinding",
    "StringLiteralFinding",
    "diff_dimension_literals_vs_registry_markdown",
    "diff_registry_markdown_vs_event_name",
    "find_missing_dimension_model_entries",
    "find_orphan_event_names",
    "find_string_literal_record_event_callers",
]
