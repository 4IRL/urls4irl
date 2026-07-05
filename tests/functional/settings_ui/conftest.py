# Folder-local conftest for `settings_ui` Playwright tests.
#
# Session/parametrized fixtures (`browser`, `provide_app`, `runner`, etc.)
# are inherited from `tests/functional/conftest.py` and `tests/conftest.py`.
#
# The `seeded_users` autouse fixture lives here so every test in this
# folder picks it up automatically — duplicating the fixture in individual
# test modules would double-seed the database (each autouse-decorated copy
# would fire once per test).
from __future__ import annotations

from typing import Tuple

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner
from playwright.sync_api import Page


def _seed_users_via_cli(runner: Tuple[Flask, FlaskCliRunner]) -> None:
    """Invoke `flask addmock users` through the test runner so the seeded
    rows live inside the test worker's DB.

    Using `subprocess.run(['flask', ...])` would escape the worker DB
    isolation, and `app.test_cli_runner().invoke(...)` would build a
    runner outside the fixture transaction scope. The `runner` fixture
    already wires both. `flask addmock users` seeds users with
    `email_validated=True`, so the settings page (gated by
    `email_validation_required`) loads directly — no post-seed patch needed.
    """
    _, cli_runner = runner
    result = cli_runner.invoke(args=["addmock", "users"])
    assert (
        result.exit_code == 0
    ), f"addmock users failed: exit={result.exit_code} output={result.output}"


@pytest.fixture(autouse=True)
def seeded_users(
    runner: Tuple[Flask, FlaskCliRunner],
    page: Page,
) -> None:
    """Seed the test DB with mock users before each test.

    Depends on ``page`` to guarantee ordering: ``page``'s setup (via
    ``page_without_cookie_banner_cookie``) calls ``clear_db``, which wipes
    every table. Listing ``page`` as a dependency ensures this fixture
    always seeds AFTER that wipe, so the settings page can be reached by a
    logged-in user when the test body executes.

    Uses function scope (the default) to match the ``runner`` fixture,
    which clears the DB in its own teardown after every test.
    """
    _seed_users_via_cli(runner)
