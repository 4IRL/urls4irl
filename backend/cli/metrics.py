from __future__ import annotations

from flask import Flask, current_app
from flask.cli import AppGroup, with_appcontext

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


def register_metrics_cli(app: Flask):
    app.cli.add_command(metrics_cli)
