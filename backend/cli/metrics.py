from __future__ import annotations

from pathlib import Path

import click
from flask import Flask, current_app
from flask.cli import AppGroup, with_appcontext

from backend.extensions.metrics.dim_types_generator import (
    generate_dim_types_ts,
    generate_dim_values_ts,
)
from backend.extensions.metrics.registry_sync import sync_event_registry
from backend.utils.strings.config_strs import CONFIG_ENVS

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


def register_metrics_cli(app: Flask):
    app.cli.add_command(metrics_cli)
