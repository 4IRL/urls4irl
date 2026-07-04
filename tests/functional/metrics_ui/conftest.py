# Folder-local conftest for `metrics_ui` Playwright tests.
#
# Session/parametrized fixtures (`browser`, `provide_app`, `runner`, etc.)
# are inherited from `tests/functional/conftest.py` and `tests/conftest.py`.
#
# The `seeded_metrics` autouse fixture lives here so every test in this
# folder picks it up automatically — duplicating the fixture in individual
# test modules would double-seed the database (each autouse-decorated copy
# would fire once per test).
from __future__ import annotations

from typing import Tuple

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner
from playwright.sync_api import Page


def _seed_metrics_via_cli(runner: Tuple[Flask, FlaskCliRunner]) -> None:
    """Invoke `flask addmock seed-uniform-test-data` through the test
    runner so the seeded rows live inside the test worker's DB.

    Using `subprocess.run(['flask', ...])` would escape the worker DB
    isolation, and `app.test_cli_runner().invoke(...)` would build a
    runner outside the fixture transaction scope. The `runner` fixture
    already wires both.
    """
    _, cli_runner = runner
    result = cli_runner.invoke(args=["addmock", "seed-uniform-test-data"])
    assert (
        result.exit_code == 0
    ), f"Metrics seed CLI failed: exit={result.exit_code} output={result.output}"


@pytest.fixture(autouse=True)
def seeded_metrics(
    runner: Tuple[Flask, FlaskCliRunner],
    page: Page,
) -> None:
    """Seed the test DB with uniform metrics data before each test.

    Depends on ``page`` to guarantee ordering: ``page``'s setup (via
    ``page_without_cookie_banner_cookie``) calls ``clear_db``, which wipes
    every table including ``AnonymousMetrics``.  Listing ``page`` as a
    dependency ensures this fixture always seeds AFTER that wipe, so the
    dashboard has data to render when the test body executes.

    Uses function scope (the default) to match the ``runner`` fixture,
    which clears the DB in its own teardown after every test. A broader
    scope would attempt to read rows that were already wiped.
    """
    _seed_metrics_via_cli(runner)
