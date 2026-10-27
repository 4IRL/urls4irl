"""Real two-connection proof for ``PATCH /utubs/<id>/member-settings``.

Runs on ``build_app`` (real commits, one connection per request thread), not the
SAVEPOINT harness, so row locks are genuine. Proves that two concurrent writes by
the same member to different keys both persist (the caller's membership row is
locked ``FOR UPDATE`` before the merge reads it).
"""

from __future__ import annotations

import time
from typing import Any, Tuple
from unittest import mock

import pytest
from flask import Flask, url_for

from backend.models.utub_members import Utub_Members
from backend.schemas.utub_member_settings import merge_member_settings
from backend.utils.all_routes import ROUTES
from tests.integration.utubmembers.test_owner_mutation_concurrency import (
    OWNER_USER_ID,
    _request_as_owner,
    _run_concurrently,
    committed_owner_utub,  # noqa: F401  (fixture reused as a base seed)
)

pytestmark = pytest.mark.utubs

MERGE_PATH = "backend.utubs.services.update_member_settings.merge_member_settings"
HOLD_SECONDS = 0.5
SeedType = Tuple[Flask, int, list[int]]


def _slow_merge(raw: dict | None, patch: dict[str, Any]) -> dict | None:
    """Hold the (already read) stored value for a moment before merging, so an
    unlocked second writer would read the same stale value and lose an update."""
    time.sleep(HOLD_SECONDS)
    return merge_member_settings(raw, patch)


def _stored(app: Flask, utub_id: int, user_id: int) -> Any:
    with app.app_context():
        return Utub_Members.query.get((utub_id, user_id)).settings


def test_concurrent_patches_to_different_keys_both_persist(
    committed_owner_utub: SeedType,  # noqa: F811
) -> None:
    """
    GIVEN one member and a merge slowed down after the stored value is read
    WHEN two requests of that member patch different keys at the same time
    THEN both get 200 and both keys are stored (the membership row lock
        serializes the read-merge-write, so neither update is lost)
    """
    app, utub_id, _ = committed_owner_utub
    with app.test_request_context():
        url = url_for(ROUTES.UTUBS.UPDATE_MEMBER_SETTINGS, utub_id=utub_id)

    with mock.patch(MERGE_PATH, _slow_merge):
        results = _run_concurrently(
            {
                "copy": lambda: _request_as_owner(
                    app,
                    OWNER_USER_ID,
                    "patch",
                    url,
                    {"urls": {"hide_copy_button": True}},
                ),
                "density": lambda: _request_as_owner(
                    app, OWNER_USER_ID, "patch", url, {"urls": {"density": "compact"}}
                ),
            }
        )

    assert {label: status for label, (status, _) in results.items()} == {
        "copy": 200,
        "density": 200,
    }
    assert _stored(app, utub_id, OWNER_USER_ID) == {
        "urls": {"hide_copy_button": True, "density": "compact"}
    }
