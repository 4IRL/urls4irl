from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator
from unittest import mock

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from backend import db
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.utubs import UtubPinUpdatedResponseSchema
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.utub_strs import UTUB_FAILURE, UTUB_ID
from backend.utubs.constants import MAX_PINNED_UTUBS, UTubErrorCodes
from tests.conftest import AjaxFlaskLoginClient
from tests.integration.utils import assert_response_conforms_to_schema
from tests.utils_for_test import (
    get_csrf_token,
    lock_utub,
    remove_member,
    trash_utub,
)

pytestmark = pytest.mark.utubs

UTUB_ID_VALUE = 1
CREATOR_ID = 1
CO_OWNER_ID = 2
PLAIN_MEMBER_ID = 3


@contextmanager
def _client_for(
    app: Flask, user_id: int
) -> Generator[tuple[FlaskClient, str], None, None]:
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        user = Users.query.get(user_id)
    with app.test_client(user=user) as client:
        csrf_token = get_csrf_token(client.get("/home").get_data(), meta_tag=True)
        yield client, csrf_token


def _patch(
    app: Flask,
    client: FlaskClient,
    csrf_token: str,
    body: Any,
    utub_id: int = UTUB_ID_VALUE,
) -> TestResponse:
    with app.app_context():
        url = url_for(ROUTES.UTUBS.UPDATE_UTUB_PIN, utub_id=utub_id)
    return client.patch(url, json=body, headers={"X-CSRFToken": csrf_token})


def _add_owned_utubs(app: Flask, user_id: int, count: int) -> list[int]:
    """Commit ``count`` extra UTubs created by ``user_id`` (a member of each)."""
    utub_ids: list[int] = []
    with app.app_context():
        for index in range(count):
            new_utub = Utubs(
                name=f"Pin UTub {index}", utub_creator=user_id, utub_description=""
            )
            db.session.add(new_utub)
            db.session.commit()
            membership = Utub_Members(member_role=Member_Role.CREATOR)
            membership.utub_id = new_utub.id
            membership.user_id = user_id
            db.session.add(membership)
            db.session.commit()
            utub_ids.append(new_utub.id)
    return utub_ids


def _set_pinned(app: Flask, utub_id: int, user_id: int, pinned: bool) -> None:
    with app.app_context():
        membership: Utub_Members = Utub_Members.query.get((utub_id, user_id))
        membership.pinned_at = utc_now() if pinned else None
        db.session.commit()


def _is_pinned(app: Flask, utub_id: int, user_id: int) -> bool:
    with app.app_context():
        db.session.expire_all()
        return Utub_Members.query.get((utub_id, user_id)).pinned_at is not None


def _pinned_total(app: Flask, user_id: int) -> int:
    with app.app_context():
        db.session.expire_all()
        return Utub_Members.query.filter(
            Utub_Members.user_id == user_id, Utub_Members.pinned_at.is_not(None)
        ).count()


def _seed_pins(app: Flask, user_id: int, count: int) -> list[int]:
    """Create ``count`` extra UTubs for the user and pin each of them."""
    utub_ids = _add_owned_utubs(app, user_id, count)
    for utub_id in utub_ids:
        _set_pinned(app, utub_id, user_id, True)
    return utub_ids


def _count_commits(app: Flask, action: Any) -> int:
    real_commit = db.session.commit
    with mock.patch.object(db.session, "commit", wraps=real_commit) as commit_spy:
        action()
    return commit_spy.call_count


# --------------------------------------------------------------------------
# Success paths
# --------------------------------------------------------------------------


def test_pin_then_unpin_echoes_state_and_count(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a member with no pins
    WHEN they pin a UTub and then unpin it
    THEN each 200 conforms to the schema and echoes isPinned and pinnedCount
    """
    client, csrf_token, _, app = login_first_user_without_register

    pin_response = _patch(app, client, csrf_token, {"pinned": True})

    assert pin_response.status_code == 200
    assert_response_conforms_to_schema(
        pin_response.json,
        UtubPinUpdatedResponseSchema,
        {
            STD_JSON.STATUS,
            STD_JSON.MESSAGE,
            UTUB_ID,
            MODELS.IS_PINNED,
            MODELS.PINNED_COUNT,
        },
    )
    assert pin_response.json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert pin_response.json[UTUB_ID] == UTUB_ID_VALUE
    assert pin_response.json[MODELS.IS_PINNED] is True
    assert pin_response.json[MODELS.PINNED_COUNT] == 1
    assert _is_pinned(app, UTUB_ID_VALUE, CREATOR_ID)

    unpin_response = _patch(app, client, csrf_token, {"pinned": False})

    assert unpin_response.status_code == 200
    assert unpin_response.json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert unpin_response.json[MODELS.IS_PINNED] is False
    assert unpin_response.json[MODELS.PINNED_COUNT] == 0
    assert not _is_pinned(app, UTUB_ID_VALUE, CREATOR_ID)


@pytest.mark.parametrize("pinned_already", [False, True])
def test_no_op_returns_no_change_without_commit(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    pinned_already,
):
    """
    GIVEN a UTub already in the requested pin state
    WHEN the same state is requested again
    THEN 200 No change is returned, the current count is echoed and nothing commits
    """
    client, csrf_token, _, app = login_first_user_without_register
    _set_pinned(app, UTUB_ID_VALUE, CREATOR_ID, pinned_already)

    responses: list[TestResponse] = []
    commits = _count_commits(
        app,
        lambda: responses.append(
            _patch(app, client, csrf_token, {"pinned": pinned_already})
        ),
    )

    assert commits == 0
    assert responses[0].status_code == 200
    assert responses[0].json[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert responses[0].json[MODELS.IS_PINNED] is pinned_already
    assert responses[0].json[MODELS.PINNED_COUNT] == (1 if pinned_already else 0)


def test_sixth_pin_returns_409_and_writes_nothing(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a member with 5 pins
    WHEN they pin a sixth UTub
    THEN 409 PIN_LIMIT_REACHED is returned and the UTub stays unpinned
    """
    client, csrf_token, _, app = login_first_user_without_register
    _seed_pins(app, CREATOR_ID, MAX_PINNED_UTUBS)

    response = _patch(app, client, csrf_token, {"pinned": True})

    assert response.status_code == 409
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response.json[STD_JSON.ERROR_CODE] == UTubErrorCodes.PIN_LIMIT_REACHED
    assert response.json[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_PINS_CAP_REACHED
    assert not _is_pinned(app, UTUB_ID_VALUE, CREATOR_ID)
    assert _pinned_total(app, CREATOR_ID) == MAX_PINNED_UTUBS


def test_re_pin_at_cap_is_no_change(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a member at the cap whose request targets an already pinned UTub
    WHEN they pin it again
    THEN 200 No change is returned (not 409)
    """
    client, csrf_token, _, app = login_first_user_without_register
    _seed_pins(app, CREATOR_ID, MAX_PINNED_UTUBS - 1)
    _set_pinned(app, UTUB_ID_VALUE, CREATOR_ID, True)

    response = _patch(app, client, csrf_token, {"pinned": True})

    assert response.status_code == 200
    assert response.json[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert response.json[MODELS.PINNED_COUNT] == MAX_PINNED_UTUBS


def test_unpin_at_cap_succeeds(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a member at the cap
    WHEN they unpin one of the pinned UTubs
    THEN 200 is returned with the reduced count
    """
    client, csrf_token, _, app = login_first_user_without_register
    _seed_pins(app, CREATOR_ID, MAX_PINNED_UTUBS - 1)
    _set_pinned(app, UTUB_ID_VALUE, CREATOR_ID, True)

    response = _patch(app, client, csrf_token, {"pinned": False})

    assert response.status_code == 200
    assert response.json[MODELS.IS_PINNED] is False
    assert response.json[MODELS.PINNED_COUNT] == MAX_PINNED_UTUBS - 1


def test_pin_in_trashed_utub_does_not_count_toward_cap(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a member with 5 pins, one of them on a trashed UTub
    WHEN they pin another UTub
    THEN 200 is returned and the live count is 5
    """
    client, csrf_token, _, app = login_first_user_without_register
    pinned_ids = _seed_pins(app, CREATOR_ID, MAX_PINNED_UTUBS)
    trash_utub(app, pinned_ids[0], deleted_by=CREATOR_ID)

    response = _patch(app, client, csrf_token, {"pinned": True})

    assert response.status_code == 200
    assert response.json[MODELS.PINNED_COUNT] == MAX_PINNED_UTUBS


def test_pin_and_unpin_succeed_in_locked_utub(
    add_multiple_users_to_utub_without_logging_in, app
):
    """
    GIVEN a locked UTub
    WHEN a plain member pins and then unpins it
    THEN both succeed (a pin is a private preference, not lock-gated)
    """
    lock_utub(app, UTUB_ID_VALUE)

    with _client_for(app, PLAIN_MEMBER_ID) as (client, csrf_token):
        pin_response = _patch(app, client, csrf_token, {"pinned": True})
        unpin_response = _patch(app, client, csrf_token, {"pinned": False})

    assert pin_response.status_code == 200
    assert unpin_response.status_code == 200
    assert not _is_pinned(app, UTUB_ID_VALUE, PLAIN_MEMBER_ID)


def test_over_cap_after_restore_blocks_pin_but_allows_unpin(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a member with 6 live pins (as after a restore)
    WHEN they pin a 7th, then unpin one
    THEN the pin is 409 PIN_LIMIT_REACHED, a no-op pin of a pinned UTub is
        No change with the live count, and the unpin is 200 with the live,
        unclamped counts
    """
    client, csrf_token, _, app = login_first_user_without_register
    pinned_ids = _seed_pins(app, CREATOR_ID, MAX_PINNED_UTUBS + 1)

    pin_response = _patch(app, client, csrf_token, {"pinned": True})
    no_op_response = _patch(
        app, client, csrf_token, {"pinned": True}, utub_id=pinned_ids[0]
    )
    unpin_response = _patch(
        app, client, csrf_token, {"pinned": False}, utub_id=pinned_ids[0]
    )

    assert pin_response.status_code == 409
    assert pin_response.json[STD_JSON.ERROR_CODE] == UTubErrorCodes.PIN_LIMIT_REACHED
    assert no_op_response.status_code == 200
    assert no_op_response.json[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert no_op_response.json[MODELS.PINNED_COUNT] == MAX_PINNED_UTUBS + 1
    assert unpin_response.status_code == 200
    assert unpin_response.json[MODELS.PINNED_COUNT] == MAX_PINNED_UTUBS


def test_one_members_pin_does_not_change_another_members(
    add_multiple_users_to_utub_without_logging_in, app
):
    """
    GIVEN a UTub the creator already has pinned
    WHEN the co-owner pins it
    THEN the co-owner's count is their own (1) and the creator's pin is untouched,
        then unpinning as the co-owner leaves the creator's pin in place
    """
    _set_pinned(app, UTUB_ID_VALUE, CREATOR_ID, True)

    with _client_for(app, CO_OWNER_ID) as (client, csrf_token):
        pin_response = _patch(app, client, csrf_token, {"pinned": True})
        unpin_response = _patch(app, client, csrf_token, {"pinned": False})

    assert pin_response.status_code == 200
    assert pin_response.json[MODELS.PINNED_COUNT] == 1
    assert unpin_response.status_code == 200
    assert unpin_response.json[MODELS.PINNED_COUNT] == 0
    assert _is_pinned(app, UTUB_ID_VALUE, CREATOR_ID)
    assert not _is_pinned(app, UTUB_ID_VALUE, PLAIN_MEMBER_ID)


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"pinned": None},
        {"pinned": "true"},
        {"pinned": 1},
        {"pinned": True, "extra": 1},
    ],
    ids=["missing_key", "null", "string", "integer", "extra_key"],
)
def test_invalid_body_returns_400(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    body,
):
    """
    GIVEN a member
    WHEN they PATCH an invalid body
    THEN 400 is returned and nothing is pinned
    """
    client, csrf_token, _, app = login_first_user_without_register

    response = _patch(app, client, csrf_token, body)

    assert response.status_code == 400
    assert response.json[STD_JSON.ERROR_CODE] == UTubErrorCodes.INVALID_FORM_INPUT
    assert not _is_pinned(app, UTUB_ID_VALUE, CREATOR_ID)


# --------------------------------------------------------------------------
# Not found / CSRF
# --------------------------------------------------------------------------


def test_removed_member_gets_404(add_multiple_users_to_utub_without_logging_in, app):
    """
    GIVEN a member removed from the UTub
    WHEN they pin it
    THEN 404 is returned
    """
    remove_member(app, UTUB_ID_VALUE, PLAIN_MEMBER_ID)

    with _client_for(app, PLAIN_MEMBER_ID) as (client, csrf_token):
        response = _patch(app, client, csrf_token, {"pinned": True})

    assert response.status_code == 404


def test_never_member_gets_404(add_single_user_to_utub_without_logging_in, app):
    """
    GIVEN an existing user who was never added to the UTub
    WHEN they pin it
    THEN 404 is returned and no membership row exists for them
    """
    with _client_for(app, PLAIN_MEMBER_ID) as (client, csrf_token):
        response = _patch(app, client, csrf_token, {"pinned": True})

    assert response.status_code == 404
    with app.app_context():
        assert Utub_Members.query.get((UTUB_ID_VALUE, PLAIN_MEMBER_ID)) is None


def test_trashed_utub_returns_404(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a trashed UTub
    WHEN a member pins it
    THEN 404 is returned
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, UTUB_ID_VALUE, deleted_by=CREATOR_ID)

    response = _patch(app, client, csrf_token, {"pinned": True})

    assert response.status_code == 404


def test_pinned_trashed_utub_cannot_be_unpinned(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a pinned UTub that was then trashed
    WHEN the member unpins it
    THEN 404 is returned and the pin is kept
    """
    client, csrf_token, _, app = login_first_user_without_register
    _set_pinned(app, UTUB_ID_VALUE, CREATOR_ID, True)
    trash_utub(app, UTUB_ID_VALUE, deleted_by=CREATOR_ID)

    response = _patch(app, client, csrf_token, {"pinned": False})

    assert response.status_code == 404
    assert _is_pinned(app, UTUB_ID_VALUE, CREATOR_ID)


def test_missing_utub_returns_404(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a UTub id that does not exist
    WHEN a member pins it
    THEN 404 is returned
    """
    client, csrf_token, _, app = login_first_user_without_register

    response = _patch(app, client, csrf_token, {"pinned": True}, utub_id=9999)

    assert response.status_code == 404


def test_missing_csrf_token_returns_403(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a logged in member
    WHEN they PATCH without a CSRF token
    THEN 403 is returned and nothing is pinned
    """
    client, _, _, app = login_first_user_without_register
    with app.app_context():
        url = url_for(ROUTES.UTUBS.UPDATE_UTUB_PIN, utub_id=UTUB_ID_VALUE)

    response = client.patch(url, json={"pinned": True})

    assert response.status_code == 403
    assert not _is_pinned(app, UTUB_ID_VALUE, CREATOR_ID)
