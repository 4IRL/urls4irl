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
from redis import Redis

from backend.utils.strings.config_strs import CONFIG_ENVS

# Rate-limit / lockout counters written by the change-username, change-password,
# change-email, and account delete services
# (`account_service.apply_username_change` / `apply_email_change` /
# `apply_account_deletion`, `reauth_throttle.record_reauth_failure`). All are
# per-user Redis keys on the shared ENFORCEMENT Redis (`CONFIG_ENVS.REDIS_URI`,
# DB 0 in the local `web` container) — NOT the per-worker session Redis DB the UI
# tests otherwise isolate. See `_reset_rate_limit_state` for why they must be
# cleared between UI tests. `email-change:*` is the per-day send cap the
# change-email happy-path test would otherwise trip after 3 runs. Only
# `apply_account_deletion`'s re-auth path remains relevant to the shared
# `reauth-fail:*` prefix (via `record_reauth_failure`) — the logout-everywhere
# flow has no re-auth (D-1) — so no new prefix is needed for the danger-zone tests.
_RATE_LIMIT_KEY_PATTERNS: tuple[str, ...] = (
    "username-change:*",
    "reauth-fail:*",
    "email-change:*",
)
_MEMORY_URI: str = "memory://"


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


@pytest.fixture(autouse=True)
def _reset_rate_limit_state(provide_app: Flask) -> None:
    """Clear the change-username / change-email / re-auth rate-limit counters on
    the shared enforcement Redis before every settings UI test (the change-email
    per-day send cap, ``email-change:*``, would otherwise trip the happy-path
    test after 3 runs — same class of leak as the change-username counter below).

    Why this is needed — the shared-live-Redis constraint:

    UI tests run the Flask app **in-process** (``run_app(worker_config)``) and
    isolate their *session* store to a per-worker Redis DB (``TEST_REDIS_URI``
    base + worker index). But the change-username rate limiter and the
    change-password re-auth lockout read the **enforcement** ``REDIS_URI``
    (``Config.REDIS_URI`` — ``redis://redis:6379/0`` in the local ``web``
    container), which ``ConfigTest``/``ConfigTestUI`` never override. That DB 0
    keyspace is therefore shared by every parallel worker AND persists across
    whole test-suite runs (the counters carry a 24h TTL).

    ``apply_username_change`` checks the per-user cap (3/24h) BEFORE the
    uniqueness check, so once user 1's ``username-change:1`` counter reaches the
    cap — e.g. ``test_change_username_happy_path_updates_in_place`` renames user
    1 and burns a slot on every run —
    ``test_change_username_duplicate_name_shows_field_error`` renders the 429
    rate-limit message instead of the expected ``USERNAME_TAKEN`` field error,
    a non-deterministic, order-/history-dependent failure in the full suite.

    Deleting ``username-change:*`` and ``reauth-fail:*`` on the enforcement
    Redis before each test gives every change-username/password test a clean
    counter regardless of prior tests or prior runs. Fails open (no-op) when the
    enforcement Redis is the in-memory stub, exactly like the services do.
    """
    redis_uri: str | None = provide_app.config.get(CONFIG_ENVS.REDIS_URI)
    if not redis_uri or redis_uri == _MEMORY_URI:
        return

    redis_client = Redis.from_url(redis_uri)
    try:
        for key_pattern in _RATE_LIMIT_KEY_PATTERNS:
            stale_keys = list(redis_client.scan_iter(match=key_pattern))
            if stale_keys:
                redis_client.unlink(*stale_keys)
    finally:
        redis_client.close()
