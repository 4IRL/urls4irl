from __future__ import annotations

from pathlib import Path

import click
from flask import Flask, current_app
from flask.cli import AppGroup, with_appcontext

from pydantic import ValidationError

from backend.extensions.metrics.buckets import previous_window, resolve_query_window
from backend.extensions.metrics.dim_types_generator import (
    generate_dim_types_ts,
    generate_dim_values_ts,
    generate_flows_ts,
    generate_resources_ts,
    generate_ui_events_ts,
)
from backend.extensions.metrics.middleware import _should_skip
from backend.extensions.metrics.registry_sync import sync_event_registry
from backend.metrics import query_service
from backend.metrics.audit import (
    diff_dimension_literals_vs_registry,
    diff_registry_vs_event_name,
    find_missing_dimension_model_entries,
    find_orphan_event_names,
    find_string_literal_record_event_callers,
)
from backend.metrics.events import EVENT_CATEGORY, EventCategory
from backend.metrics.gauges import GaugeName
from backend.metrics.resources import EVENT_NAME_TO_RESOURCE, Resource
from backend.schemas.requests.metrics import (
    GaugesTimeseriesQuerySchema,
    TopEventsQuerySchema,
)
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.config_strs import CONFIG_ENVS

EMPTY_TOP_EVENTS_OUTPUT = "No metrics rows in the requested window."
TOP_EVENTS_HEADER = "event_name\tcategory\tdescription\ttotal_count"

GAUGE_TIMESERIES_HEADER = "sampled_at\tvalue_int\tvalue_float"
EMPTY_GAUGE_TIMESERIES_OUTPUT = "No gauge samples in the requested window."
GAUGES_LATEST_HEADER = "gauge_name\tsampled_at\tvalue_int\tvalue_float"
EMPTY_GAUGES_LATEST_OUTPUT = "No gauge samples recorded yet."
GAUGES_LIST_HEADER = "gauge_name\tkind\tdescription"

# Sentinel rendered for a NULL value column (k-anon suppression or AVG/INT
# split) so a blank TSV cell never collapses two adjacent columns.
_GAUGE_NULL_CELL = ""

AUDIT_NONE_PLACEHOLDER: str = "(none)"
AUDIT_SECTION_ORPHANS: str = "# Orphan EventName members"
AUDIT_SECTION_STRING_LITERAL: str = "# String-literal record_event callers"
AUDIT_SECTION_MISSING_DIM: str = "# Missing DIMENSION_MODELS entries"
AUDIT_SECTION_DIM_DRIFT: str = (
    "# Dimension literal drift (EVENT_REGISTRY vs DIMENSION_MODELS Literals)"
)
AUDIT_SECTION_REGISTRY_DRIFT: str = "# EVENT_REGISTRY drift vs EventName enum"

# Coverage-summary TSV header. Three columns by design:
#   Domain   — display label for the row (e.g. "API (auto)" or a Resource name).
#   Category — one of "api" / "domain" / "ui" matching `EventCategory`.
#   Count    — distinct route handlers (API) or `EventName` members (Domain/UI).
COVERAGE_SUMMARY_HEADER: str = "Domain\tCategory\tCount"
COVERAGE_SUMMARY_API_LABEL: str = "API (auto)"

# Methods counted as "API hit"-emitting routes; mirrors the HTTP verbs the
# `API_HIT` middleware records via `@app.after_request`. Werkzeug auto-adds
# HEAD when GET is registered and OPTIONS for CORS — neither produces a
# distinct route handler, so both are excluded from the count.
_COVERAGE_SUMMARY_COUNTED_METHODS: frozenset[str] = frozenset(
    {"GET", "POST", "PATCH", "PUT", "DELETE"}
)

HELP_SUMMARY_METRICS = """Anonymous metrics CLI commands for U4I."""

metrics_cli = AppGroup(
    "metrics",
    context_settings={"ignore_unknown_options": True},
    help=HELP_SUMMARY_METRICS,
)


@metrics_cli.command(
    "sync-registry",
    help="Reconcile EventRegistry table from the EventName Python enum.",
)
@with_appcontext
def sync_registry_command():
    if not current_app.config.get(CONFIG_ENVS.METRICS_ENABLED, False):
        print("METRICS_ENABLED is false; skipping registry sync.")
        return
    # current_app is a LocalProxy; pass the underlying Flask object so the
    # function's `app: Flask` typed signature is satisfied without `# type: ignore`.
    sync_event_registry(current_app._get_current_object())  # type: ignore[attr-defined]
    print("metrics: synced event_registry from EventName enum.")


@metrics_cli.command(
    "generate-dim-types",
    help="Emit TypeScript per-event dimension types from DIMENSION_MODELS.",
)
@click.option(
    "--output",
    "output_path",
    required=True,
    type=click.Path(dir_okay=False, writable=True),
    help="Target path for the generated .ts file.",
)
def generate_dim_types_command(output_path: str):
    """Render `frontend/lib/metrics-dimensions.ts` from the backend Pydantic models.

    Intentionally does NOT require an app context: the codegen is a pure
    walk of `DIMENSION_MODELS` + `EVENT_CATEGORY` and does not touch the
    database, Redis, or app config. Skipping `@with_appcontext` lets the
    CLI run inside a fresh process without booting Flask extensions.
    """
    source = generate_dim_types_ts()
    target = Path(output_path)
    target.write_text(source, encoding="utf-8")
    click.echo(f"metrics: wrote dim types → {target}")


@metrics_cli.command(
    "generate-dim-values",
    help="Emit TypeScript runtime constants for every dim-value Literal alias from DIMENSION_MODELS.",
)
@click.option(
    "--output",
    "output_path",
    required=True,
    type=click.Path(dir_okay=False, writable=True),
    help="Target path for the generated .ts file.",
)
def generate_dim_values_command(output_path: str):
    """Render `frontend/types/metrics-dim-values.ts` from the backend Pydantic models.

    Companion to `generate-dim-types`: the type-only `.d.ts` ships compile-time
    narrowings, this `.ts` ships the matching runtime constants so every
    `emit({ … })` call site can reference a single source of truth. Pure walk
    of `DIMENSION_MODELS`; no app context needed.
    """
    source = generate_dim_values_ts()
    target = Path(output_path)
    target.write_text(source, encoding="utf-8")
    click.echo(f"metrics: wrote dim values → {target}")


@metrics_cli.command(
    "generate-events",
    help="Emit TypeScript UI_EVENTS const + UIEventName type from the EventName enum.",
)
@click.option(
    "--output",
    "output_path",
    required=True,
    type=click.Path(dir_okay=False, writable=True),
    help="Target path for the generated .ts file.",
)
def generate_events_command(output_path: str):
    """Render `frontend/types/metrics-events.ts` from the backend `EventName` enum.

    Walks `EventName` filtered to UI events; emits a `UI_EVENTS` `as const`
    object with a derived `UIEventName` type. Companion to `generate-dim-types`
    and `generate-dim-values` — together they keep the frontend metrics
    contract locked to the Python source of truth. Pure walk of `EventName` +
    `EVENT_CATEGORY`; no app context needed.
    """
    source = generate_ui_events_ts()
    target = Path(output_path)
    target.write_text(source, encoding="utf-8")
    click.echo(f"metrics: wrote ui events → {target}")


@metrics_cli.command(
    "generate-resources",
    help="Emit TypeScript RESOURCES const + ResourceName type + RESOURCES_BY_CATEGORY from the Resource enum.",
)
@click.option(
    "--output",
    "output_path",
    required=True,
    type=click.Path(dir_okay=False, writable=True),
    help="Target path for the generated .ts file.",
)
def generate_resources_command(output_path: str):
    """Render `frontend/types/metrics-resources.ts` from `backend/metrics/resources.py`.

    Walks the `Resource` enum + `RESOURCE_BY_CATEGORY` mapping; emits the
    canonical resource list plus per-category subsets used by the admin
    dashboard's top-events filter dropdown. Pure walk; no app context needed.
    """
    source = generate_resources_ts()
    target = Path(output_path)
    target.write_text(source, encoding="utf-8")
    click.echo(f"metrics: wrote resources → {target}")


@metrics_cli.command(
    "generate-flows",
    help="Emit TypeScript FLOW_IDS const + FlowId type + FLOW_METADATA from the FLOWS registry.",
)
@click.option(
    "--output",
    "output_path",
    required=True,
    type=click.Path(dir_okay=False, writable=True),
    help="Target path for the generated .ts file.",
)
def generate_flows_command(output_path: str):
    """Render `frontend/types/metrics-flows.ts` from `backend/metrics/flows.py`.

    Walks the `FlowId` enum + `FLOWS` registry; emits the flow id list plus
    per-flow display metadata (display name + ordered, variable-length
    `stepLabels`) consumed by the admin dashboard's funnel-card renderer.
    Pure walk of `FLOWS`/`FlowId`; no app context needed (no database or
    Redis access), so it runs in `event-coverage-staleness.yml` where
    `METRICS_ENABLED=false` and no Flask extensions are initialized.
    """
    source = generate_flows_ts()
    target = Path(output_path)
    target.write_text(source, encoding="utf-8")
    click.echo(f"metrics: wrote flows → {target}")


@metrics_cli.command("top", help="Show top events by count for a time window.")
@click.option(
    "--window",
    type=str,
    default=None,
    help="day | week | month | year | Nh | Nd (mutually exclusive with --start/--end)",
)
@click.option(
    "--start",
    type=str,
    default=None,
    help="ISO-8601 with timezone (e.g., 2026-06-06T00:00:00Z); pair with --end",
)
@click.option(
    "--end",
    type=str,
    default=None,
    help="ISO-8601 with timezone (e.g., 2026-06-06T00:00:00Z); pair with --start",
)
@click.option(
    "--category",
    type=click.Choice(["api", "domain", "ui"]),
    default=None,
)
@click.option("--limit", type=click.IntRange(1, 100), default=10)
@with_appcontext
def top_command(
    window: str | None,
    start: str | None,
    end: str | None,
    category: str | None,
    limit: int,
) -> None:
    """Parity CLI for the `/api/metrics/query/top` endpoint.

    Validates input through the same `TopEventsQuerySchema` the HTTP route
    uses, so window/range XOR enforcement and `AwareDatetime` naive-rejection
    behave identically in terminal and dashboard contexts.
    """
    try:
        parsed = TopEventsQuerySchema.model_validate(
            {
                "window": window,
                "start": start,
                "end": end,
                "category": category,
                "limit": limit,
            }
        )
    except ValidationError as schema_validation_error:
        for error in schema_validation_error.errors():
            field_path = ".".join(str(part) for part in error["loc"]) or "__root__"
            click.echo(f"{field_path}: {error['msg']}", err=True)
        raise SystemExit(1)

    try:
        window_start, window_end = resolve_query_window(
            window=parsed.window,
            start=parsed.start,
            end=parsed.end,
            now=utc_now(),
        )
    except ValueError as range_resolution_error:
        click.echo(str(range_resolution_error), err=True)
        raise SystemExit(1)

    bounds_label = f"window: {parsed.window}" if parsed.window is not None else "range:"
    click.echo(
        f"{bounds_label} [{window_start.isoformat()} .. {window_end.isoformat()}]"
    )

    category_enum: EventCategory | None = (
        EventCategory(parsed.category) if parsed.category is not None else None
    )
    previous_window_start, previous_window_end = previous_window(
        window_start, window_end
    )
    rows = query_service.top_events(
        window_start=window_start,
        window_end=window_end,
        previous_window_start=previous_window_start,
        previous_window_end=previous_window_end,
        category=category_enum,
        limit=parsed.limit,
    )

    if not rows:
        click.echo(EMPTY_TOP_EVENTS_OUTPUT)
        return

    click.echo(TOP_EVENTS_HEADER)
    for row in rows:
        click.echo(
            "\t".join(
                [row.event_name, row.category, row.description, str(row.total_count)]
            )
        )


@metrics_cli.command(
    "audit",
    help="Audit EventName / DIMENSION_MODELS / record_event coverage.",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Exit non-zero if any finding category is non-empty.",
)
def audit_command(strict: bool) -> None:
    """Run all five coverage-audit helpers and print findings as TSV.

    Intentionally does NOT require an app context: every helper is a pure
    AST + enum/dict walk against code-located state (no markdown, no DB,
    no Redis). The `event-coverage-staleness.yml` CI workflow invokes this
    command with `--strict` to gate PRs.

    Output is grouped into five sections, each headed by `# <Section>`.
    Empty sections print `(none)` so the format is stable and grep-able.
    """
    orphans = find_orphan_event_names()
    string_literal_callers = find_string_literal_record_event_callers()
    missing_dimension_entries = find_missing_dimension_model_entries()
    dimension_literal_findings = diff_dimension_literals_vs_registry()
    registry_drift_findings = diff_registry_vs_event_name()

    click.echo(AUDIT_SECTION_ORPHANS)
    if orphans:
        for orphan_event_name in orphans:
            click.echo(orphan_event_name.name)
    else:
        click.echo(AUDIT_NONE_PLACEHOLDER)

    click.echo(AUDIT_SECTION_STRING_LITERAL)
    if string_literal_callers:
        for caller in string_literal_callers:
            click.echo(f"{caller.file}:{caller.line}\trecord_event({caller.literal!r})")
    else:
        click.echo(AUDIT_NONE_PLACEHOLDER)

    click.echo(AUDIT_SECTION_MISSING_DIM)
    if missing_dimension_entries:
        for missing_event_name in missing_dimension_entries:
            click.echo(missing_event_name.name)
    else:
        click.echo(AUDIT_NONE_PLACEHOLDER)

    click.echo(AUDIT_SECTION_DIM_DRIFT)
    if dimension_literal_findings:
        for dimension_finding in dimension_literal_findings:
            click.echo(
                f"{dimension_finding.event.name}\tfield={dimension_finding.field}\t"
                f"code={dimension_finding.code_values}\t"
                f"registry={dimension_finding.registry_values}"
            )
    else:
        click.echo(AUDIT_NONE_PLACEHOLDER)

    click.echo(AUDIT_SECTION_REGISTRY_DRIFT)
    if registry_drift_findings:
        for registry_finding in registry_drift_findings:
            click.echo(
                f"{registry_finding.kind}\t{registry_finding.event}\t"
                f"{registry_finding.detail}"
            )
    else:
        click.echo(AUDIT_NONE_PLACEHOLDER)

    any_findings_present = bool(
        orphans
        or string_literal_callers
        or missing_dimension_entries
        or dimension_literal_findings
        or registry_drift_findings
    )
    if strict and any_findings_present:
        raise SystemExit(1)


def _count_auto_counted_api_routes(app: Flask) -> int:
    """Return the number of distinct (endpoint, method) pairs that the API_HIT
    middleware would record — i.e., routes not filtered by `_should_skip`.

    Walks Flask's URL map and applies the same skip predicate the middleware
    uses at request time (`backend/extensions/metrics/middleware.py`). One
    counted hit is logged per (endpoint, method) pair because the middleware's
    counter key includes `method`, so `GET /utubs` and `POST /utubs` are two
    distinct counted routes even though they share an endpoint.

    Examples:
        >>> # current route count (update as routes are added/removed)
        >>> _count_auto_counted_api_routes(app)
        34
    """
    counted_pairs: set[tuple[str, str]] = set()
    for rule in app.url_map.iter_rules():
        if rule.methods is None:
            continue
        if app.view_functions.get(rule.endpoint) is None:
            continue
        blueprint_name: str | None = (
            rule.endpoint.rsplit(".", 1)[0] if "." in rule.endpoint else None
        )
        if _should_skip(rule.endpoint, blueprint_name):
            continue
        for method_name in rule.methods:
            if method_name in _COVERAGE_SUMMARY_COUNTED_METHODS:
                counted_pairs.add((rule.endpoint, method_name))
    return len(counted_pairs)


def _count_events_per_resource(category: EventCategory) -> list[tuple[Resource, int]]:
    """Return an ordered list of (Resource, count) tuples for `EventName`
    members in `category`, grouped by `EVENT_NAME_TO_RESOURCE`.

    Order is the iteration order of `Resource`, which is the canonical
    declaration order in `backend/metrics/resources.py`. Resources with zero
    matching members are omitted so the TSV stays compact.

    Examples:
        >>> # current per-resource counts for the DOMAIN category:
        >>> _count_events_per_resource(EventCategory.DOMAIN)
        [(Resource.UTUB, 5), (Resource.URL, 5), (Resource.TAG, 4), ...]
    """
    counts_by_resource: dict[Resource, int] = {resource: 0 for resource in Resource}
    for event_name, resource in EVENT_NAME_TO_RESOURCE.items():
        if EVENT_CATEGORY[event_name] is category:
            counts_by_resource[resource] += 1
    return [
        (resource, count) for resource, count in counts_by_resource.items() if count > 0
    ]


@metrics_cli.command(
    "coverage-summary",
    help="Emit a TSV count of API/Domain/UI events grouped by resource.",
)
@with_appcontext
def coverage_summary_command() -> None:
    """Emit machine-readable counts so the master plan's Coverage Summary
    table can be regenerated from CLI output instead of hand-counted.

    Output format: tab-separated values, three columns:
        Domain   — display label (e.g. "API (auto)" or a Resource name)
        Category — `api` / `domain` / `ui`
        Count    — distinct route handlers (API) or `EventName` members

    Sources:
        - API (auto): `app.url_map` minus `_should_skip` filtered routes,
          counted as distinct (endpoint, method) pairs.
        - Domain per Resource: `EventName` members in `EventCategory.DOMAIN`
          grouped by `EVENT_NAME_TO_RESOURCE`.
        - UI per Resource: `EventName` members in `EventCategory.UI` grouped
          by `EVENT_NAME_TO_RESOURCE` (the "surface").

    The CI staleness workflow does NOT run this command; it is intended for
    human reviewers regenerating the master plan's `## Coverage Summary`
    table after `EventName` changes.
    """
    flask_app: Flask = current_app._get_current_object()  # type: ignore[attr-defined]

    click.echo(COVERAGE_SUMMARY_HEADER)
    click.echo(
        "\t".join(
            [
                COVERAGE_SUMMARY_API_LABEL,
                EventCategory.API.value,
                str(_count_auto_counted_api_routes(flask_app)),
            ]
        )
    )
    for resource, count in _count_events_per_resource(EventCategory.DOMAIN):
        click.echo("\t".join([resource.value, EventCategory.DOMAIN.value, str(count)]))
    for resource, count in _count_events_per_resource(EventCategory.UI):
        click.echo("\t".join([resource.value, EventCategory.UI.value, str(count)]))


def _gauge_value_cell(value: int | float | None) -> str:
    """Render a gauge value column for TSV, mapping `None` to the null sentinel.

    Examples:
        _gauge_value_cell(6)    -> "6"
        _gauge_value_cell(4.0)  -> "4.0"
        _gauge_value_cell(None) -> ""
    """
    return _GAUGE_NULL_CELL if value is None else str(value)


@metrics_cli.command(
    "gauge-timeseries",
    help="Show one gauge's sampled values over a time window.",
)
@click.option(
    "--name",
    type=click.Choice([member.value for member in GaugeName]),
    required=True,
    help="Which gauge to chart (a GaugeName value, e.g. total_users).",
)
@click.option(
    "--window",
    type=str,
    default=None,
    help="day | week | month | year | Nh | Nd (mutually exclusive with --start/--end)",
)
@click.option(
    "--start",
    type=str,
    default=None,
    help="ISO-8601 with timezone (e.g., 2026-06-06T00:00:00Z); pair with --end",
)
@click.option(
    "--end",
    type=str,
    default=None,
    help="ISO-8601 with timezone (e.g., 2026-06-06T00:00:00Z); pair with --start",
)
@with_appcontext
def gauge_timeseries_command(
    name: str,
    window: str | None,
    start: str | None,
    end: str | None,
) -> None:
    """Parity CLI for one gauge's timeseries (per-name; the HTTP endpoint is batched).

    `--name` is validated by `click.Choice` (the batched
    `GaugesTimeseriesQuerySchema` carries no `name` field), and the
    window/range XOR is enforced by the same `GaugesTimeseriesQuerySchema` the
    HTTP route uses so terminal and dashboard behave identically.
    """
    try:
        parsed = GaugesTimeseriesQuerySchema.model_validate(
            {"window": window, "start": start, "end": end}
        )
    except ValidationError as schema_validation_error:
        for error in schema_validation_error.errors():
            field_path = ".".join(str(part) for part in error["loc"]) or "__root__"
            click.echo(f"{field_path}: {error['msg']}", err=True)
        raise SystemExit(1)

    try:
        window_start, window_end = resolve_query_window(
            window=parsed.window,
            start=parsed.start,
            end=parsed.end,
            now=utc_now(),
        )
    except ValueError as range_resolution_error:
        click.echo(str(range_resolution_error), err=True)
        raise SystemExit(1)

    samples = query_service.gauge_timeseries_one(
        gauge_name=GaugeName(name),
        window_start=window_start,
        window_end=window_end,
    )

    if not samples:
        click.echo(EMPTY_GAUGE_TIMESERIES_OUTPUT)
        return

    click.echo(GAUGE_TIMESERIES_HEADER)
    for sample in samples:
        click.echo(
            "\t".join(
                [
                    sample.sampled_at.isoformat(),
                    _gauge_value_cell(sample.value_int),
                    _gauge_value_cell(sample.value_float),
                ]
            )
        )


@metrics_cli.command(
    "gauges-latest",
    help="Show the most-recent sample for every gauge that has rows.",
)
@with_appcontext
def gauges_latest_command() -> None:
    """Parity CLI for the `/api/metrics/query/gauges/latest` endpoint."""
    rows = query_service.latest_gauge_snapshot()

    if not rows:
        click.echo(EMPTY_GAUGES_LATEST_OUTPUT)
        return

    click.echo(GAUGES_LATEST_HEADER)
    for row in rows:
        click.echo(
            "\t".join(
                [
                    row.gauge_name,
                    row.sampled_at.isoformat(),
                    _gauge_value_cell(row.value_int),
                    _gauge_value_cell(row.value_float),
                ]
            )
        )


@metrics_cli.command(
    "gauges-list",
    help="Show static metadata (name, kind, description) for every gauge.",
)
@with_appcontext
def gauges_list_command() -> None:
    """Parity CLI for the `/api/metrics/query/gauges/list` endpoint (pure registry walk)."""
    click.echo(GAUGES_LIST_HEADER)
    for row in query_service.list_gauges():
        click.echo("\t".join([row.gauge_name, row.kind, row.description]))


def register_metrics_cli(app: Flask):
    app.cli.add_command(metrics_cli)
