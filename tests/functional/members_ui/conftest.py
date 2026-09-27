# Folder-local conftest for `members_ui` Playwright tests.
#
# Session/parametrized fixtures (`browser`, `provide_app`, `runner`, etc.)
# are inherited from `tests/functional/conftest.py` and `tests/conftest.py`.
#
# The add-member UI tests in this folder (create-member, members-metrics,
# and the member-search filter-reapply-after-add flow) all add members as
# user 1, incrementing the SAME per-user daily-cap counter the integration
# tests already flush. This autouse fixture applies that flush to the
# functional harness so the counter never accumulates across tests/runs.
from __future__ import annotations

from typing import Generator

import pytest
from flask import Flask

from tests.integration.utils import flush_member_add_lookup_keys


@pytest.fixture(autouse=True)
def _flush_member_add_lookup_counter(provide_app: Flask) -> Generator[None, None, None]:
    """Clear the per-user ``member-add-lookup:*`` daily-counter keys before and
    after every ``members_ui`` test in this folder.

    Why this is needed — the counter outlives a single test (same class of leak
    the ``settings_ui`` conftest fixes for the change-username/email counters):

    UI tests run the Flask app **in-process** (``run_app(worker_config)``).
    ``worker_config`` points both the session store and the **enforcement**
    ``REDIS_URI`` at the worker's leased Redis DB, so the add-member daily-cap
    counter (``create_utub_member``) is isolated per worker and per run. But
    that leased DB lives for the whole session and the counter carries a 24h
    TTL, so without a flush a full ``members_ui`` run accumulates
    ``member-add-lookup:1`` past ``MEMBER_ADD_DAILY_CAP`` (100) and trips the
    cap mid-suite, producing spurious add-member UI failures.

    Reuses ``flush_member_add_lookup_keys`` (the same helper the integration
    ``utubmembers``/``mobile_api`` conftests use), which deletes only matching
    keys — never ``flushdb()`` — since the leased DB also holds the worker's
    sessions and other enforcement counters. ``provide_app`` carries the same
    enforcement ``REDIS_URI`` as the in-process app under test, so flushing
    through it reaches the same keyspace (identical mechanism to the
    ``settings_ui`` reset). Fails open (no-op) when the enforcement Redis is
    the in-memory stub, exactly like the service does.
    """
    flush_member_add_lookup_keys(provide_app)
    yield
    flush_member_add_lookup_keys(provide_app)
