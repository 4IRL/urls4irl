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

    Why this is needed — the shared-live-Redis constraint (same class of leak
    the ``settings_ui`` conftest fixes for the change-username/email counters):

    UI tests run the Flask app **in-process** (``run_app(worker_config)``) and
    isolate their *session* store to a per-worker Redis DB. But the add-member
    daily-cap counter (``create_utub_member``) writes to the shared
    **enforcement** ``REDIS_URI`` (``redis://redis:6379/0`` in the local ``web``
    container), which ``ConfigTestUI`` never overrides. That DB 0 keyspace is
    shared by every parallel worker AND persists across whole test-suite runs
    (the counter carries a 24h TTL). Without a flush, a full/repeated
    ``members_ui`` run accumulates ``member-add-lookup:1`` past
    ``MEMBER_ADD_DAILY_CAP`` (100) and trips the cap mid-suite, producing
    spurious add-member UI failures.

    Reuses ``flush_member_add_lookup_keys`` (the same helper the integration
    ``utubmembers``/``mobile_api`` conftests use), which deletes only matching
    keys — never ``flushdb()`` — since that DB is shared with other enforcement
    counters. ``provide_app`` carries the same enforcement ``REDIS_URI`` as the
    in-process app under test, so flushing through it reaches the same keyspace
    (identical mechanism to the ``settings_ui`` reset). Fails open (no-op) when
    the enforcement Redis is the in-memory stub, exactly like the service does.
    """
    flush_member_add_lookup_keys(provide_app)
    yield
    flush_member_add_lookup_keys(provide_app)
