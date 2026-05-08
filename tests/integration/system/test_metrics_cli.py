from __future__ import annotations

import pytest
from flask import Flask

from backend.metrics.events import EventName
from backend.models.event_registry import Event_Registry
from backend.utils.strings.config_strs import CONFIG_ENVS

pytestmark = pytest.mark.cli

CLI_DISABLED_OUTPUT = "METRICS_ENABLED is false; skipping registry sync."
CLI_SUCCESS_OUTPUT = "metrics: synced event_registry from EventName enum."


def test_sync_registry_cli_with_metrics_disabled_is_noop(app: Flask):
    """
    GIVEN METRICS_ENABLED is false (the default for ConfigTest)
    WHEN the `flask metrics sync-registry` CLI command is invoked
    THEN ensure the command exits 0, prints the disabled message, and
        leaves EventRegistry empty
    """
    runner = app.test_cli_runner()
    result = runner.invoke(args=["metrics", "sync-registry"])

    assert result.exit_code == 0
    assert CLI_DISABLED_OUTPUT in result.output
    assert Event_Registry.query.count() == 0


def test_sync_registry_cli_populates_registry_when_enabled(app: Flask):
    """
    GIVEN METRICS_ENABLED is overridden to True for the test
    WHEN the `flask metrics sync-registry` CLI command is invoked
    THEN ensure the command exits 0, prints the success message, and
        every EventName member has a corresponding EventRegistry row
    """
    original_metrics_enabled = app.config.get(CONFIG_ENVS.METRICS_ENABLED, False)
    app.config[CONFIG_ENVS.METRICS_ENABLED] = True
    try:
        runner = app.test_cli_runner()
        result = runner.invoke(args=["metrics", "sync-registry"])

        assert result.exit_code == 0
        assert CLI_SUCCESS_OUTPUT in result.output

        registered_names = {row.name for row in Event_Registry.query.all()}
        for member in EventName:
            assert member.value in registered_names
    finally:
        app.config[CONFIG_ENVS.METRICS_ENABLED] = original_metrics_enabled
