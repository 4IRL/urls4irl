"""Real two-connection proofs for ``PATCH /utubs/<id>/settings``.

Runs on ``build_app`` (real commits, one connection per request thread), not the
SAVEPOINT harness, so row locks are genuine. Proves that (1) concurrent writes to
different sections lose no update and (2) a section's ``normalize`` hook runs on
the merged state, while the UTub row lock is held, before the 400 decision.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Generator, Self, Tuple
from unittest import mock

import pytest
from flask import Flask, url_for
from pydantic import Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from backend import db
from backend.models.utub_members import Member_Role
from backend.models.utubs import Utubs
from backend.schemas import utub_settings
from backend.schemas.utub_settings import (
    TagsSettings,
    UrlsSettings,
    UtubSettings,
)
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.utub_strs import UTUB_FAILURE
from backend.utubs.constants import UTubErrorCodes
from backend.utubs.guards import lock_and_reauthorize
from tests.integration.utubmembers.test_owner_mutation_concurrency import (
    BARRIER_TIMEOUT_SECONDS,
    OWNER_USER_ID,
    _request_as_owner,
    _run_concurrently,
    committed_owner_utub,  # noqa: F401  (fixture reused as a base seed)
)
from tests.utils_for_test import set_member_role

pytestmark = pytest.mark.utubs

CO_OWNER_USER_ID = 2
SERVICE_LOCK_PATH = "backend.utubs.services.update_utub_settings.lock_and_reauthorize"
SeedType = Tuple[Flask, int, list[int]]


# --------------------------------------------------------------------------
# Stub settings models (registered via the single seam, undone by monkeypatch)
# --------------------------------------------------------------------------


class _RaceUrlsSettings(UrlsSettings):
    stub_flag: bool = False


class _RaceTagsSettings(TagsSettings):
    stub_count: int = 0


class _RaceUtubSettings(UtubSettings):
    urls: _RaceUrlsSettings = Field(default_factory=_RaceUrlsSettings)
    tags: _RaceTagsSettings = Field(default_factory=_RaceTagsSettings)


# Filled by the hook-order stub's normalize: one dict per call.
_NORMALIZE_CALLS: list[dict[str, Any]] = []
_REJECT_ABOVE = 100


def _probe_utub_row_locked(utub_id: int) -> bool:
    """True when another connection holds a lock on the UTub row.

    Uses a separate connection and ``FOR UPDATE NOWAIT``, which fails at once
    when the request's ``FOR NO KEY UPDATE`` (or any row lock) is held.
    """
    # Closing the connection rolls back, releasing any lock the probe took.
    with db.engine.connect() as probe_connection:
        try:
            probe_connection.execute(
                text('SELECT id FROM "Utubs" WHERE id = :utub_id FOR UPDATE NOWAIT'),
                {"utub_id": utub_id},
            )
        except OperationalError:
            return True
    return False


class _HookUrlsSettings(UrlsSettings):
    """``high`` must be >= ``low``; normalize repairs it before the check."""

    low: int = 0
    high: int = 0

    def normalize(self, patched_keys: frozenset[str]) -> Self:
        utub_id = int(_UTUB_ID_UNDER_TEST[0])
        _NORMALIZE_CALLS.append(
            {
                "input": {"low": self.low, "high": self.high},
                "patched_keys": patched_keys,
                "locked": _probe_utub_row_locked(utub_id) if patched_keys else None,
            }
        )
        if self.low > _REJECT_ABOVE:
            raise ValueError("low is out of range")
        if self.high < self.low:
            self.high = self.low
        return self

    @model_validator(mode="after")
    def _check_high_not_below_low(self) -> Self:
        # Declared after the base normalize validator, so it sees the repair.
        if self.high < self.low:
            raise ValueError("high must not be below low")
        return self


class _HookUtubSettings(UtubSettings):
    urls: _HookUrlsSettings = Field(default_factory=_HookUrlsSettings)


_UTUB_ID_UNDER_TEST: list[int] = [0]


# --------------------------------------------------------------------------
# Fixtures and helpers
# --------------------------------------------------------------------------


@pytest.fixture
def committed_manager_utub(
    committed_owner_utub: SeedType,  # noqa: F811
) -> SeedType:
    """The committed seed (creator 1, plain members 2 and 3) with user 2
    promoted to CO_CREATOR, so users 1 and 2 are both managers."""
    app, utub_id, user_ids = committed_owner_utub
    set_member_role(app, utub_id, user_ids[1], Member_Role.CO_CREATOR)
    return app, utub_id, user_ids


@pytest.fixture
def race_settings_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(utub_settings, "get_settings_model", lambda: _RaceUtubSettings)


@pytest.fixture
def hook_settings_model(
    monkeypatch: pytest.MonkeyPatch, committed_manager_utub: SeedType
) -> Generator[None, None, None]:
    _, utub_id, _ = committed_manager_utub
    _NORMALIZE_CALLS.clear()
    _UTUB_ID_UNDER_TEST[0] = utub_id
    monkeypatch.setattr(utub_settings, "get_settings_model", lambda: _HookUtubSettings)
    yield
    _NORMALIZE_CALLS.clear()
    _UTUB_ID_UNDER_TEST[0] = 0


def _barriered_lock_and_reauthorize() -> Callable[..., Any]:
    """Both requests rendezvous BEFORE taking the row lock, so each has passed
    the route guard on unlocked state; the lock then serializes them."""
    barrier = threading.Barrier(2)

    def _wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            barrier.wait(timeout=BARRIER_TIMEOUT_SECONDS)
        except threading.BrokenBarrierError:
            pass
        return lock_and_reauthorize(*args, **kwargs)

    return _wrapper


def _settings_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.UTUBS.UPDATE_UTUB_SETTINGS, utub_id=utub_id)


def _stored_settings(app: Flask, utub_id: int) -> Any:
    with app.app_context():
        return Utubs.query.get(utub_id).settings


def _store_settings(app: Flask, utub_id: int, value: Any) -> None:
    with app.app_context():
        Utubs.query.get(utub_id).settings = value
        db.session.commit()


# --------------------------------------------------------------------------
# Concurrency: no lost update across sections
# --------------------------------------------------------------------------


def test_concurrent_patches_to_different_sections_both_persist(
    committed_manager_utub: SeedType, race_settings_model: None
) -> None:
    """
    GIVEN two managers (creator and co-creator) and a two-section settings model
    WHEN each PATCHes a different section and both pass the unlocked route guard
        before either takes the row lock
    THEN both get 200 and the stored overrides hold both sections' keys, so
        neither write was lost, whichever request won the lock
    """
    app, utub_id, _ = committed_manager_utub
    url = _settings_url(app, utub_id)

    with mock.patch(SERVICE_LOCK_PATH, _barriered_lock_and_reauthorize()):
        results = _run_concurrently(
            {
                "urls": lambda: _request_as_owner(
                    app, OWNER_USER_ID, "patch", url, {"urls": {"stub_flag": True}}
                ),
                "tags": lambda: _request_as_owner(
                    app, CO_OWNER_USER_ID, "patch", url, {"tags": {"stub_count": 3}}
                ),
            }
        )

    assert {label: status for label, (status, _) in results.items()} == {
        "urls": 200,
        "tags": 200,
    }
    assert _stored_settings(app, utub_id) == {
        "urls": {"stub_flag": True},
        "tags": {"stub_count": 3},
    }


# --------------------------------------------------------------------------
# Normalize-hook ordering: after merge, under the lock, before the 400 decision
# --------------------------------------------------------------------------


def test_probe_detects_unlocked_row(committed_manager_utub: SeedType) -> None:
    """
    GIVEN no request holds the UTub row lock
    WHEN the NOWAIT probe runs on a separate connection
    THEN it reports unlocked, so a True from the hook test is meaningful
    """
    app, utub_id, _ = committed_manager_utub
    with app.app_context():
        assert _probe_utub_row_locked(utub_id) is False


def test_normalize_sees_stored_plus_patch_under_lock_and_persists_adjustment(
    committed_manager_utub: SeedType, hook_settings_model: None
) -> None:
    """
    GIVEN stored urls overrides {"high": 1}
    WHEN a manager PATCHes {"urls": {"low": 5}}
    THEN normalize received stored + patch ({"low": 5, "high": 1}) with the patch's
        keys, ran while the row lock was held, and its adjustment (high raised to
        5) is persisted in a 200
    """
    app, utub_id, _ = committed_manager_utub
    _store_settings(app, utub_id, {"urls": {"high": 1}})
    _NORMALIZE_CALLS.clear()

    status, body = _request_as_owner(
        app,
        OWNER_USER_ID,
        "patch",
        _settings_url(app, utub_id),
        {"urls": {"low": 5}},
    )

    assert status == 200
    patched_calls = [call for call in _NORMALIZE_CALLS if call["locked"] is not None]
    assert len(patched_calls) == 1
    assert patched_calls[0]["input"] == {"low": 5, "high": 1}
    assert patched_calls[0]["patched_keys"] == frozenset({"low"})
    assert patched_calls[0]["locked"] is True
    assert body["settings"]["urls"]["high"] == 5
    assert _stored_settings(app, utub_id) == {"urls": {"low": 5, "high": 5}}


def test_normalize_repairs_state_invalid_before_normalize_instead_of_400(
    committed_manager_utub: SeedType, hook_settings_model: None
) -> None:
    """
    GIVEN a stored urls section that violates the high >= low invariant until
        normalize runs (low 7, high 2)
    WHEN a manager PATCHes an unrelated change to that section
    THEN the response is 200 (not 400) and the repaired value is persisted
    """
    app, utub_id, _ = committed_manager_utub
    _store_settings(app, utub_id, {"urls": {"low": 7, "high": 2}})

    status, body = _request_as_owner(
        app,
        OWNER_USER_ID,
        "patch",
        _settings_url(app, utub_id),
        {"urls": {"low": 7}},
    )

    assert status == 200
    assert body["settings"]["urls"] == {"low": 7, "high": 7}
    assert _stored_settings(app, utub_id) == {"urls": {"low": 7, "high": 7}}


def test_normalize_rejection_returns_400_and_leaves_db_unchanged(
    committed_manager_utub: SeedType, hook_settings_model: None
) -> None:
    """
    GIVEN stored urls overrides {"low": 1}
    WHEN a manager PATCHes a state normalize cannot fix (low above the limit)
    THEN normalize ran under the row lock, the response is the settings 400 keyed
        on the section, and the stored overrides are unchanged
    """
    app, utub_id, _ = committed_manager_utub
    _store_settings(app, utub_id, {"urls": {"low": 1}})
    _NORMALIZE_CALLS.clear()

    status, body = _request_as_owner(
        app,
        OWNER_USER_ID,
        "patch",
        _settings_url(app, utub_id),
        {"urls": {"low": _REJECT_ABOVE + 1}},
    )

    assert status == 400
    assert body[STD_JSON.MESSAGE] == UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_SETTINGS
    assert body[STD_JSON.ERROR_CODE] == UTubErrorCodes.INVALID_FORM_INPUT
    assert list(body[STD_JSON.ERRORS]) == ["urls"]
    patched_calls = [call for call in _NORMALIZE_CALLS if call["locked"] is not None]
    assert len(patched_calls) == 1
    assert patched_calls[0]["locked"] is True
    assert _stored_settings(app, utub_id) == {"urls": {"low": 1}}
