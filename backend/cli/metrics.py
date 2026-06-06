from __future__ import annotations

from pathlib import Path

import click
from flask import Flask, current_app
from flask.cli import AppGroup, with_appcontext

from pydantic import ValidationError

from backend.extensions.metrics.buckets import resolve_query_window
from backend.extensions.metrics.dim_types_generator import (
    generate_dim_types_ts,
    generate_dim_values_ts,
    generate_ui_events_ts,
)
from backend.extensions.metrics.registry_sync import sync_event_registry
from backend.metrics import query_service
from backend.metrics.events import EventCategory
from backend.schemas.requests.metrics import TopEventsQuerySchema
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.config_strs import CONFIG_ENVS

EMPTY_TOP_EVENTS_OUTPUT = "No metrics rows in the requested window."
TOP_EVENTS_HEADER = "event_name\tcategory\tdescription\ttotal_count"

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
    rows = query_service.top_events(
        window_start=window_start,
        window_end=window_end,
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


def register_metrics_cli(app: Flask):
    app.cli.add_command(metrics_cli)
