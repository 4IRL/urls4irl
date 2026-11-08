"""
Integration tests for the bearer-token Member endpoints:
  POST   /api/v1/utubs/<utub_id>/members
  DELETE /api/v1/utubs/<utub_id>/members/<user_id>
  PATCH  /api/v1/utubs/<utub_id>/members/<user_id>  (grant/revoke co-owner)
  PATCH  /api/v1/utubs/<utub_id>/owner              (transfer ownership)

Conventions:
  - Uses api_client (plain FlaskClient, no session/CSRF).
  - URL built with url_for() inside app.test_request_context().
  - All JSON key constants imported from backend string modules.
  - pytestmark = pytest.mark.mobile_api
"""

import time

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from sqlalchemy import null

from backend import db, limiter
from backend.members.constants import MEMBER_ADD_RATE_LIMIT, UTubMembersErrorCodes
from backend.metrics.events import EventName
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import API_AUTH_FAILURE
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS
from backend.utils.strings.utub_strs import UTUB_FAILURE, UTUB_ID
from tests.integration.mobile_api.mobile_helpers import token_for_user
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
)
from tests.models_for_test import valid_users
from tests.utils_for_test import lock_utub, set_member_role, set_members_settings

pytestmark = pytest.mark.mobile_api

# ---------------------------------------------------------------------------
# Constants for request body field names
# ---------------------------------------------------------------------------

_USERNAME_FIELD = "username"
_MEMBER_KEY = MEMBER_SUCCESS.MEMBER


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def _create_member_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.CREATE_MEMBER, utub_id=utub_id)


def _remove_member_url(app: Flask, utub_id: int, user_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.REMOVE_MEMBER, utub_id=utub_id, user_id=user_id)


def _modify_member_role_url(app: Flask, utub_id: int, user_id: int) -> str:
    with app.test_request_context():
        return url_for(
            ROUTES.API_V1.MODIFY_MEMBER_ROLE, utub_id=utub_id, user_id=user_id
        )


def _transfer_ownership_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.TRANSFER_UTUB_OWNERSHIP, utub_id=utub_id)


# ===========================================================================
# POST /api/v1/utubs/<utub_id>/members — add member
# ===========================================================================


def test_add_member_happy_path(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    every_user_makes_a_unique_utub,
):
    """
    GIVEN three users each with their own UTub (ids 1, 2, 3)
    WHEN creator of UTub 1 (user 1) POSTs to add user 2 by username
    THEN 200 with member object and utubID; DB association created

    Note: bearer headers are minted after every_user_makes_a_unique_utub runs
    (which registers all 3 users) to avoid fixture conflict with register_first_user.
    """
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))
    user_2_username = valid_users[1]["username"]

    with app.app_context():
        initial_member_count = Utub_Members.query.filter_by(utub_id=1).count()

    assert initial_member_count == 1

    response = api_client.post(
        _create_member_url(app, utub_id=1),
        json={_USERNAME_FIELD: user_2_username},
        headers=user_1_headers,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.MEMBER_ADDED
    assert response_json[_MEMBER_KEY][MODELS.USERNAME] == user_2_username
    assert response_json[_MEMBER_KEY][MODELS.ID] == 2
    assert response_json[_MEMBER_KEY][MODELS.MEMBER_ROLE] == Member_Role.MEMBER.value
    assert response_json[_MEMBER_KEY][MODELS.JOINED_AT] is not None

    with app.app_context():
        assert (
            Utub_Members.query.filter_by(utub_id=1).count() == initial_member_count + 1
        )


def test_remove_then_readd_member_gets_new_joined_at(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    every_user_makes_a_unique_utub,
):
    """
    GIVEN creator (user 1) who added user 2 and then removed them
    WHEN user 2 is added again
    THEN the add response carries a joinedAt later than the first one
    """
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))
    user_2_username = valid_users[1]["username"]

    first = api_client.post(
        _create_member_url(app, utub_id=1),
        json={_USERNAME_FIELD: user_2_username},
        headers=user_1_headers,
    )
    assert first.status_code == 200
    first_joined_at = first.get_json()[_MEMBER_KEY][MODELS.JOINED_AT]

    removed = api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=2), headers=user_1_headers
    )
    assert removed.status_code == 200
    assert MODELS.JOINED_AT not in removed.get_json()[_MEMBER_KEY]

    # joinedAt has millisecond precision; ensure the re-add lands in a later ms.
    time.sleep(0.01)

    second = api_client.post(
        _create_member_url(app, utub_id=1),
        json={_USERNAME_FIELD: user_2_username},
        headers=user_1_headers,
    )
    assert second.status_code == 200
    second_joined_at = second.get_json()[_MEMBER_KEY][MODELS.JOINED_AT]
    assert second_joined_at is not None
    assert second_joined_at != first_joined_at
    assert second_joined_at > first_joined_at


def test_add_member_no_token_is_401(app: Flask, api_client: FlaskClient):
    """No Authorization header → 401 JSON failure."""
    response = api_client.post(
        _create_member_url(app, utub_id=1),
        json={_USERNAME_FIELD: "someuser"},
    )

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_add_member_not_creator_is_403(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN user 2 is a member (not creator) of UTub id=1
    WHEN user 2 tries to add another member
    THEN 403 with errorCode MEMBER_ADD_NOT_ALLOWED (adding is off by default)
    """
    user_2_token = token_for_user(app, user_id=2)
    user_3_username = valid_users[2]["username"]

    response = api_client.post(
        _create_member_url(app, utub_id=1),
        json={_USERNAME_FIELD: user_3_username},
        headers=make_bearer_headers(user_2_token),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        response_json[STD_JSON.ERROR_CODE]
        == UTubMembersErrorCodes.MEMBER_ADD_NOT_ALLOWED
    )


def test_add_member_missing_body_is_400(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    add_single_utub_as_user_without_logging_in,
):
    """Missing required username field → 400 (schema validation failure)."""
    response = api_client.post(
        _create_member_url(app, utub_id=1),
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_add_member_rejects_client_sent_invite_link_source(
    app: Flask,
    metrics_enabled_app,
    provide_metrics_redis,
    api_client: FlaskClient,
    make_bearer_headers,
    every_user_makes_a_unique_utub,
):
    """
    GIVEN metrics enabled and a UTub creator (user 1)
    WHEN they POST add-member with the server-only source='invite_link'
    THEN 400, no member is added and no MEMBER_ADDED metric is recorded
    """
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))

    with app.app_context():
        initial_member_count = Utub_Members.query.filter_by(utub_id=1).count()

    response = api_client.post(
        _create_member_url(app, utub_id=1),
        json={
            _USERNAME_FIELD: valid_users[1]["username"],
            "source": "invite_link",
        },
        headers=user_1_headers,
    )

    assert response.status_code == 400
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE
    with app.app_context():
        assert Utub_Members.query.filter_by(utub_id=1).count() == initial_member_count
    assert count_counter_keys(provide_metrics_redis, EventName.MEMBER_ADDED) == 0


@pytest.mark.parametrize(
    "body_source, expected_source",
    [
        ("search_result", "search_result"),
        (None, "exact_username"),
    ],
)
def test_add_member_records_source_dimension(
    app: Flask,
    metrics_enabled_app,
    provide_metrics_redis,
    api_client: FlaskClient,
    make_bearer_headers,
    every_user_makes_a_unique_utub,
    body_source: str | None,
    expected_source: str,
):
    """
    GIVEN metrics enabled and a UTub creator (user 1)
    WHEN they POST add-member with a client source (or none)
    THEN one MEMBER_ADDED counter exists whose source dimension is the converted value
    """
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))
    body = {_USERNAME_FIELD: valid_users[1]["username"]}
    if body_source is not None:
        body["source"] = body_source

    response = api_client.post(
        _create_member_url(app, utub_id=1),
        json=body,
        headers=user_1_headers,
    )

    assert response.status_code == 200
    keys = find_counter_keys(provide_metrics_redis, EventName.MEMBER_ADDED)
    assert len(keys) == 1
    assert parse_dims(keys[0])["source"] == expected_source


def test_add_member_nonexistent_user_is_400(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    add_single_utub_as_user_without_logging_in,
):
    """
    GIVEN a valid creator token for UTub id=1
    WHEN POST /api/v1/utubs/1/members with a username that does not exist
    THEN 400 (service rejects unknown username)
    """
    response = api_client.post(
        _create_member_url(app, utub_id=1),
        json={_USERNAME_FIELD: "NonExistentUser9999"},
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


# ===========================================================================
# DELETE /api/v1/utubs/<utub_id>/members/<user_id> — remove member
# ===========================================================================


def test_remove_member_creator_removes_member_happy_path(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    add_multiple_users_to_utub_without_logging_in,
):
    """
    GIVEN UTub id=1 with creator (user 1) and members (users 2, 3)
    WHEN creator sends DELETE /api/v1/utubs/1/members/2
    THEN 200 with member object; DB association removed

    Note: bearer headers are minted after the multi-user fixture runs
    to avoid fixture conflict with register_first_user.
    """
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))

    with app.app_context():
        initial_member_count = Utub_Members.query.filter_by(utub_id=1).count()

    assert initial_member_count == 3

    response = api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=2),
        headers=user_1_headers,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.MEMBER_REMOVED
    assert response_json[_MEMBER_KEY][MODELS.ID] == 2

    with app.app_context():
        assert (
            Utub_Members.query.filter_by(utub_id=1).count() == initial_member_count - 1
        )


def test_remove_member_self_removal_happy_path(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN UTub id=1 with creator (user 1) and members (users 2, 3)
    WHEN user 2 (non-creator member) removes themselves
    THEN 200
    """
    user_2_token = token_for_user(app, user_id=2)

    with app.app_context():
        initial_member_count = Utub_Members.query.filter_by(utub_id=1).count()

    assert initial_member_count == 3

    response = api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=2),
        headers=make_bearer_headers(user_2_token),
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS

    with app.app_context():
        assert (
            Utub_Members.query.filter_by(utub_id=1).count() == initial_member_count - 1
        )


def test_remove_member_no_token_is_401(app: Flask, api_client: FlaskClient):
    """No Authorization header → 401."""
    response = api_client.delete(_remove_member_url(app, utub_id=1, user_id=2))

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_remove_member_non_member_cannot_remove_other(
    app: Flask,
    api_client: FlaskClient,
    every_user_makes_a_unique_utub,
    make_bearer_headers,
):
    """
    GIVEN user 1 is not a member of UTub id=2 (owned by user 2)
    WHEN user 1 tries DELETE /api/v1/utubs/2/members/3
    THEN 404 (not a member of that UTub → utub_membership_required returns 404)
    """
    user_1_token = token_for_user(app, user_id=1)

    response = api_client.delete(
        _remove_member_url(app, utub_id=2, user_id=3),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 404
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_remove_member_member_cannot_remove_other_member(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN UTub id=1 with creator (user 1) and members (users 2, 3)
    WHEN user 2 tries to remove user 3
    THEN 403 (only creator may remove others)
    """
    user_2_token = token_for_user(app, user_id=2)

    response = api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=3),
        headers=make_bearer_headers(user_2_token),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.INVALID_PERMISSION_TO_REMOVE
    )


def test_remove_member_co_creator_can_remove_self(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN UTub id=1 where user 2 has been promoted to CO_CREATOR
    WHEN user 2 (co-owner) removes themselves (user_id=2)
    THEN 200 (co-creators may leave voluntarily — DD-5) and the row is gone
    """
    set_member_role(app, utub_id=1, user_id=2, role=Member_Role.CO_CREATOR)
    user_2_headers = make_bearer_headers(token_for_user(app, user_id=2))

    with app.app_context():
        initial_member_count = Utub_Members.query.filter_by(utub_id=1).count()

    response = api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=2),
        headers=user_2_headers,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.MEMBER_REMOVED

    with app.app_context():
        assert Utub_Members.query.get((1, 2)) is None
        assert (
            Utub_Members.query.filter_by(utub_id=1).count() == initial_member_count - 1
        )


def test_remove_member_creator_cannot_remove_self_with_co_creator_present(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN UTub id=1 where user 2 has been promoted to CO_CREATOR
    WHEN the literal creator (user 1) tries to remove themselves (user_id=1)
    THEN 400 — the true owner stays blocked even when a co-creator exists
    """
    set_member_role(app, utub_id=1, user_id=2, role=Member_Role.CO_CREATOR)
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))

    response = api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=1),
        headers=user_1_headers,
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.CREATOR_CANNOT_REMOVE_THEMSELF
    )

    with app.app_context():
        assert Utub_Members.query.get((1, 1)) is not None


def test_remove_member_co_creator_can_remove_another_member(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN UTub id=1 with creator (user 1) and members (users 2, 3), where user 2
        has been promoted to CO_CREATOR
    WHEN the co-creator (user 2) removes another member (user 3)
    THEN 200 — the co-owner's right to remove other members is preserved (DD-1)
    """
    set_member_role(app, utub_id=1, user_id=2, role=Member_Role.CO_CREATOR)
    set_members_settings(app, 1, {"co_owners_can_remove": True})
    user_2_headers = make_bearer_headers(token_for_user(app, user_id=2))

    with app.app_context():
        initial_member_count = Utub_Members.query.filter_by(utub_id=1).count()

    response = api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=3),
        headers=user_2_headers,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.MEMBER_REMOVED
    assert response_json[_MEMBER_KEY][MODELS.ID] == 3

    with app.app_context():
        assert Utub_Members.query.get((1, 3)) is None
        assert (
            Utub_Members.query.filter_by(utub_id=1).count() == initial_member_count - 1
        )


def _co_owner_delete(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    user_id: int,
):
    return api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=user_id),
        headers=make_bearer_headers(token_for_user(app, user_id=2)),
    )


def _assert_co_owner_switch_off_refusal(response) -> None:
    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.CO_OWNER_REMOVE_NOT_ALLOWED
    assert (
        int(response_json[STD_JSON.ERROR_CODE])
        == UTubMembersErrorCodes.CO_OWNER_REMOVE_NOT_ALLOWED
    )


def test_remove_member_co_creator_with_switch_off_is_refused(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN the default (off) co-owner removal switch and user 2 a co-owner
    WHEN user 2 removes plain member user 3, a co-owner user 3, or a non-member id
    THEN each is 403 with errorCode CO_OWNER_REMOVE_NOT_ALLOWED and the member stays
    """
    set_member_role(app, utub_id=1, user_id=2, role=Member_Role.CO_CREATOR)

    plain = _co_owner_delete(app, api_client, make_bearer_headers, user_id=3)
    _assert_co_owner_switch_off_refusal(plain)

    missing = _co_owner_delete(app, api_client, make_bearer_headers, user_id=9999)
    _assert_co_owner_switch_off_refusal(missing)

    set_member_role(app, utub_id=1, user_id=3, role=Member_Role.CO_CREATOR)
    co_owner = _co_owner_delete(app, api_client, make_bearer_headers, user_id=3)
    _assert_co_owner_switch_off_refusal(co_owner)

    with app.app_context():
        assert Utub_Members.query.get((1, 3)) is not None


def test_remove_member_co_creator_cannot_remove_co_creator_with_switch_on(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN the switch on and users 2 and 3 both co-owners
    WHEN co-owner 2 removes co-owner 3
    THEN 403 CO_OWNER_CANNOT_REMOVE_CO_OWNER with no errorCode; the target stays
    """
    set_member_role(app, utub_id=1, user_id=2, role=Member_Role.CO_CREATOR)
    set_member_role(app, utub_id=1, user_id=3, role=Member_Role.CO_CREATOR)
    set_members_settings(app, 1, {"co_owners_can_remove": True})

    response = _co_owner_delete(app, api_client, make_bearer_headers, user_id=3)

    assert response.status_code == 403
    response_json = response.get_json()
    assert (
        response_json[STD_JSON.MESSAGE]
        == MEMBER_FAILURE.CO_OWNER_CANNOT_REMOVE_CO_OWNER
    )
    assert response_json.get(STD_JSON.ERROR_CODE) is None
    with app.app_context():
        assert Utub_Members.query.get((1, 3)) is not None


@pytest.mark.parametrize("switch_on", [False, True])
def test_remove_member_co_creator_can_leave_and_cannot_remove_owner(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
    switch_on,
):
    """
    GIVEN a co-owner (user 2) and the switch off or on
    WHEN user 2 removes the owner
    THEN CANNOT_REMOVE_OWNER either way
    AND WHEN user 2 removes themself THEN 200 either way
    """
    set_member_role(app, utub_id=1, user_id=2, role=Member_Role.CO_CREATOR)
    set_members_settings(app, 1, {"co_owners_can_remove": switch_on})

    owner_response = _co_owner_delete(app, api_client, make_bearer_headers, user_id=1)
    assert owner_response.status_code == 403
    assert (
        owner_response.get_json()[STD_JSON.MESSAGE]
        == MEMBER_FAILURE.CANNOT_REMOVE_OWNER
    )

    self_response = _co_owner_delete(app, api_client, make_bearer_headers, user_id=2)
    assert self_response.status_code == 200
    with app.app_context():
        assert Utub_Members.query.get((1, 2)) is None


def test_remove_member_locked_utub_wins_over_switch_off(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN a locked UTub with the switch off and user 2 a co-owner
    WHEN user 2 removes plain member user 3
    THEN the locked response (UTUB_IS_LOCKED), not CO_OWNER_REMOVE_NOT_ALLOWED
    """
    set_member_role(app, utub_id=1, user_id=2, role=Member_Role.CO_CREATOR)
    lock_utub(app, 1)

    response = _co_owner_delete(app, api_client, make_bearer_headers, user_id=3)

    assert response.status_code == 403
    assert (
        int(response.get_json()[STD_JSON.ERROR_CODE])
        == UTubMembersErrorCodes.UTUB_IS_LOCKED
    )


def test_remove_member_plain_member_cannot_remove_with_switch_on(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN the switch on and user 2 a plain member
    WHEN user 2 removes user 3
    THEN 403 INVALID_PERMISSION_TO_REMOVE and user 3 stays
    """
    set_members_settings(app, 1, {"co_owners_can_remove": True})

    response = _co_owner_delete(app, api_client, make_bearer_headers, user_id=3)

    assert response.status_code == 403
    assert (
        response.get_json()[STD_JSON.MESSAGE]
        == MEMBER_FAILURE.INVALID_PERMISSION_TO_REMOVE
    )
    with app.app_context():
        assert Utub_Members.query.get((1, 3)) is not None


def test_remove_member_switch_turned_off_after_on_is_refused(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN the switch turned on, then off by the owner before the co-owner's request
    WHEN co-owner user 2 removes plain member user 3
    THEN 403 CO_OWNER_REMOVE_NOT_ALLOWED and user 3 stays
    """
    set_member_role(app, utub_id=1, user_id=2, role=Member_Role.CO_CREATOR)
    set_members_settings(app, 1, {"co_owners_can_remove": True})
    set_members_settings(app, 1, {"co_owners_can_remove": False})

    response = _co_owner_delete(app, api_client, make_bearer_headers, user_id=3)

    _assert_co_owner_switch_off_refusal(response)
    with app.app_context():
        assert Utub_Members.query.get((1, 3)) is not None


def test_remove_member_owner_removes_co_creator_regardless_of_switch(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN the switch off and user 3 a co-owner
    WHEN the owner removes user 3
    THEN 200
    """
    set_member_role(app, utub_id=1, user_id=3, role=Member_Role.CO_CREATOR)

    response = api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=3),
        headers=make_bearer_headers(token_for_user(app, user_id=1)),
    )

    assert response.status_code == 200
    with app.app_context():
        assert Utub_Members.query.get((1, 3)) is None


def test_remove_member_co_creator_cannot_remove_literal_owner(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN UTub id=1 with creator (user 1) and members (users 2, 3), where user 2
        has been promoted to CO_CREATOR
    WHEN the co-creator (user 2) tries to remove the literal owner (user 1)
    THEN 403 with MEMBER_FAILURE.CANNOT_REMOVE_OWNER — the integrity guard prevents
        an ownerless UTub, and the owner's membership row remains intact
    """
    set_member_role(app, utub_id=1, user_id=2, role=Member_Role.CO_CREATOR)
    user_2_headers = make_bearer_headers(token_for_user(app, user_id=2))

    with app.app_context():
        initial_member_count = Utub_Members.query.filter_by(utub_id=1).count()

    response = api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=1),
        headers=user_2_headers,
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.CANNOT_REMOVE_OWNER

    with app.app_context():
        assert Utub_Members.query.get((1, 1)) is not None
        assert Utub_Members.query.filter_by(utub_id=1).count() == initial_member_count


def test_remove_member_plain_member_cannot_remove_literal_owner(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN UTub id=1 with creator (user 1) and plain members (users 2, 3)
    WHEN a plain member (user 2) tries to remove the literal owner (user 1)
    THEN 403 with MEMBER_FAILURE.CANNOT_REMOVE_OWNER — the integrity guard runs before the
        generic "remove another member" check, yielding the specific owner-protection error,
        and the owner's membership row remains intact
    """
    user_2_headers = make_bearer_headers(token_for_user(app, user_id=2))

    with app.app_context():
        initial_member_count = Utub_Members.query.filter_by(utub_id=1).count()

    response = api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=1),
        headers=user_2_headers,
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.CANNOT_REMOVE_OWNER

    with app.app_context():
        assert Utub_Members.query.get((1, 1)) is not None
        assert Utub_Members.query.filter_by(utub_id=1).count() == initial_member_count


# ===========================================================================
# PATCH /api/v1/utubs/<utub_id>/members/<user_id> — grant/revoke co-owner
# ===========================================================================

_MEMBER_ROLE_FIELD = "member_role"
_ROLE_CO_CREATOR = "cocreator"
_ROLE_MEMBER = "member"


def _member_role(app: Flask, utub_id: int, user_id: int) -> Member_Role:
    with app.app_context():
        member: Utub_Members = Utub_Members.query.get((utub_id, user_id))
        return member.member_role


def test_modify_member_role_grant_happy_path(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN UTub id=1 with creator (user 1) and plain members (users 2, 3)
    WHEN the owner PATCHes user 2 with member_role=cocreator
    THEN 200, success envelope, and user 2's role flips to CO_CREATOR
    """
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))

    response = api_client.patch(
        _modify_member_role_url(app, utub_id=1, user_id=2),
        json={_MEMBER_ROLE_FIELD: _ROLE_CO_CREATOR},
        headers=user_1_headers,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.MEMBER_ROLE_MODIFIED
    assert _member_role(app, utub_id=1, user_id=2) == Member_Role.CO_CREATOR


def test_modify_member_role_revoke_happy_path(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN UTub id=1 where user 2 has been promoted to CO_CREATOR
    WHEN the owner PATCHes user 2 with member_role=member
    THEN 200 and user 2's role flips back to MEMBER
    """
    set_member_role(app, utub_id=1, user_id=2, role=Member_Role.CO_CREATOR)
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))

    response = api_client.patch(
        _modify_member_role_url(app, utub_id=1, user_id=2),
        json={_MEMBER_ROLE_FIELD: _ROLE_MEMBER},
        headers=user_1_headers,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert _member_role(app, utub_id=1, user_id=2) == Member_Role.MEMBER


def test_modify_member_role_no_token_is_401(app: Flask, api_client: FlaskClient):
    """No Authorization header → 401 JSON failure."""
    response = api_client.patch(
        _modify_member_role_url(app, utub_id=1, user_id=2),
        json={_MEMBER_ROLE_FIELD: _ROLE_CO_CREATOR},
    )

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_modify_member_role_co_creator_actor_is_403(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """A co-creator (not the literal owner) cannot change roles → 403."""
    set_member_role(app, utub_id=1, user_id=2, role=Member_Role.CO_CREATOR)
    user_2_headers = make_bearer_headers(token_for_user(app, user_id=2))

    response = api_client.patch(
        _modify_member_role_url(app, utub_id=1, user_id=3),
        json={_MEMBER_ROLE_FIELD: _ROLE_CO_CREATOR},
        headers=user_2_headers,
    )

    assert response.status_code == 403
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert _member_role(app, utub_id=1, user_id=3) == Member_Role.MEMBER


def test_modify_member_role_plain_member_actor_is_403(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """A plain member cannot change roles → 403."""
    user_3_headers = make_bearer_headers(token_for_user(app, user_id=3))

    response = api_client.patch(
        _modify_member_role_url(app, utub_id=1, user_id=2),
        json={_MEMBER_ROLE_FIELD: _ROLE_CO_CREATOR},
        headers=user_3_headers,
    )

    assert response.status_code == 403
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert _member_role(app, utub_id=1, user_id=2) == Member_Role.MEMBER


def test_modify_member_role_target_not_a_member_is_404(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """Targeting a user who is not a member of the UTub → 404."""
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))

    response = api_client.patch(
        _modify_member_role_url(app, utub_id=1, user_id=9999),
        json={_MEMBER_ROLE_FIELD: _ROLE_CO_CREATOR},
        headers=user_1_headers,
    )

    assert response.status_code == 404
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.MEMBER_NOT_IN_UTUB


def test_modify_member_role_target_owner_is_400(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """Targeting the literal creator → 400 with CANNOT_MODIFY_OWNER error code."""
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))

    response = api_client.patch(
        _modify_member_role_url(app, utub_id=1, user_id=1),
        json={_MEMBER_ROLE_FIELD: _ROLE_MEMBER},
        headers=user_1_headers,
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.CANNOT_MODIFY_OWNER_ROLE
    assert (
        int(response_json[STD_JSON.ERROR_CODE])
        == UTubMembersErrorCodes.CANNOT_MODIFY_OWNER
    )


def test_modify_member_role_locked_utub_is_403(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """A locked UTub rejects the role change → 403 with UTUB_IS_LOCKED."""
    with app.app_context():
        utub: Utubs = Utubs.query.get(1)
        utub.is_locked = True
        db.session.commit()

    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))

    response = api_client.patch(
        _modify_member_role_url(app, utub_id=1, user_id=2),
        json={_MEMBER_ROLE_FIELD: _ROLE_CO_CREATOR},
        headers=user_1_headers,
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED
    assert (
        int(response_json[STD_JSON.ERROR_CODE]) == UTubMembersErrorCodes.UTUB_IS_LOCKED
    )


@pytest.mark.parametrize(
    "bad_body",
    [
        {},
        {_MEMBER_ROLE_FIELD: "bogus"},
    ],
)
def test_modify_member_role_missing_or_invalid_role_is_400(
    bad_body: dict,
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """Missing or invalid `member_role` → 400 with the generic invalid-input
    envelope."""
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))

    response = api_client.patch(
        _modify_member_role_url(app, utub_id=1, user_id=2),
        json=bad_body,
        headers=user_1_headers,
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.UNABLE_TO_MODIFY_MEMBER_ROLE
    )
    assert (
        int(response_json[STD_JSON.ERROR_CODE])
        == UTubMembersErrorCodes.INVALID_FORM_INPUT
    )


def test_remove_member_creator_cannot_remove_self(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    add_multiple_users_to_utub_without_logging_in,
):
    """
    GIVEN user 1 is the creator of UTub id=1
    WHEN user 1 tries to remove themselves (user_id=1)
    THEN 400 (creator cannot remove themselves)

    Note: bearer headers minted after multi-user fixture to avoid fixture conflict.
    """
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))

    response = api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=1),
        headers=user_1_headers,
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.CREATOR_CANNOT_REMOVE_THEMSELF
    )


def test_remove_member_nonexistent_member_is_404(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    add_single_utub_as_user_without_logging_in,
):
    """
    GIVEN UTub id=1 with only creator (user 1); user 2 is not a member
    WHEN creator tries to remove user 2
    THEN 404 (member does not exist in UTub)
    """
    response = api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=2),
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 404
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


# ===========================================================================
# PATCH /api/v1/utubs/<utub_id>/owner — transfer UTub ownership
# ===========================================================================

_NEW_OWNER_ID_FIELD = "new_owner_id"


def test_transfer_ownership_happy_path(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN UTub id=1 with creator (user 1) and plain members (users 2, 3)
    WHEN the owner PATCHes /owner with new_owner_id=2
    THEN 200; user 2 becomes CREATOR (and the utub_creator), the outgoing owner
        (user 1) is demoted to CO_CREATOR, and the newOwner/previousOwner payload
        reflects the swap
    """
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))

    response = api_client.patch(
        _transfer_ownership_url(app, utub_id=1),
        json={_NEW_OWNER_ID_FIELD: 2},
        headers=user_1_headers,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.OWNERSHIP_TRANSFERRED

    with app.app_context():
        assert Utubs.query.get(1).utub_creator == 2
    assert _member_role(app, utub_id=1, user_id=2) == Member_Role.CREATOR
    assert _member_role(app, utub_id=1, user_id=1) == Member_Role.CO_CREATOR

    assert response_json[UTUB_ID] == 1
    assert (
        response_json[MODELS.NEW_OWNER][MODELS.MEMBER_ROLE] == Member_Role.CREATOR.value
    )
    assert response_json[MODELS.NEW_OWNER][MODELS.ID] == 2
    assert (
        response_json[MODELS.PREVIOUS_OWNER][MODELS.MEMBER_ROLE]
        == Member_Role.CO_CREATOR.value
    )
    assert response_json[MODELS.PREVIOUS_OWNER][MODELS.ID] == 1
    assert response_json[MODELS.NEW_OWNER][MODELS.JOINED_AT] is not None
    assert response_json[MODELS.PREVIOUS_OWNER][MODELS.JOINED_AT] is not None


def test_transfer_ownership_response_joined_at_null_for_dateless_member(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN UTub id=1 where the incoming owner (user 2) has no recorded join date
    WHEN the owner transfers ownership to user 2
    THEN newOwner.joinedAt is null while previousOwner.joinedAt stays set
    """
    with app.app_context():
        membership = Utub_Members.query.filter_by(utub_id=1, user_id=2).one()
        membership.joined_at = null()
        db.session.commit()

    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))
    response = api_client.patch(
        _transfer_ownership_url(app, utub_id=1),
        json={_NEW_OWNER_ID_FIELD: 2},
        headers=user_1_headers,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[MODELS.NEW_OWNER][MODELS.JOINED_AT] is None
    assert response_json[MODELS.PREVIOUS_OWNER][MODELS.JOINED_AT] is not None


def test_transfer_ownership_to_existing_co_owner_happy_path(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN UTub id=1 where user 2 has already been promoted to CO_CREATOR
    WHEN the owner PATCHes /owner with new_owner_id=2
    THEN 200; the same three-way invariant holds (target→CREATOR + utub_creator,
        outgoing owner→CO_CREATOR)
    """
    set_member_role(app, utub_id=1, user_id=2, role=Member_Role.CO_CREATOR)
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))

    response = api_client.patch(
        _transfer_ownership_url(app, utub_id=1),
        json={_NEW_OWNER_ID_FIELD: 2},
        headers=user_1_headers,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.OWNERSHIP_TRANSFERRED

    with app.app_context():
        assert Utubs.query.get(1).utub_creator == 2
    assert _member_role(app, utub_id=1, user_id=2) == Member_Role.CREATOR
    assert _member_role(app, utub_id=1, user_id=1) == Member_Role.CO_CREATOR


def test_transfer_ownership_no_token_is_401(app: Flask, api_client: FlaskClient):
    """No Authorization header → 401 JSON failure."""
    response = api_client.patch(
        _transfer_ownership_url(app, utub_id=1),
        json={_NEW_OWNER_ID_FIELD: 2},
    )

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_transfer_ownership_co_creator_actor_is_403(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """A co-creator (not the literal owner) cannot transfer ownership → 403, and
    utub_creator is unchanged."""
    set_member_role(app, utub_id=1, user_id=2, role=Member_Role.CO_CREATOR)
    user_2_headers = make_bearer_headers(token_for_user(app, user_id=2))

    response = api_client.patch(
        _transfer_ownership_url(app, utub_id=1),
        json={_NEW_OWNER_ID_FIELD: 3},
        headers=user_2_headers,
    )

    assert response.status_code == 403
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE
    with app.app_context():
        assert Utubs.query.get(1).utub_creator == 1


def test_transfer_ownership_plain_member_actor_is_403(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """A plain member cannot transfer ownership → 403, and utub_creator is
    unchanged."""
    user_3_headers = make_bearer_headers(token_for_user(app, user_id=3))

    response = api_client.patch(
        _transfer_ownership_url(app, utub_id=1),
        json={_NEW_OWNER_ID_FIELD: 2},
        headers=user_3_headers,
    )

    assert response.status_code == 403
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE
    with app.app_context():
        assert Utubs.query.get(1).utub_creator == 1


def test_transfer_ownership_target_not_a_member_is_404(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """Transferring to a user who is not a member of the UTub → 404 with
    TARGET_NOT_A_MEMBER error code."""
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))

    response = api_client.patch(
        _transfer_ownership_url(app, utub_id=1),
        json={_NEW_OWNER_ID_FIELD: 9999},
        headers=user_1_headers,
    )

    assert response.status_code == 404
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.MEMBER_NOT_IN_UTUB
    assert (
        int(response_json[STD_JSON.ERROR_CODE])
        == UTubMembersErrorCodes.TARGET_NOT_A_MEMBER
    )


def test_transfer_ownership_target_already_owner_is_400(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """Transferring to the current owner (themself) → 400 with TARGET_ALREADY_OWNER
    error code, and utub_creator unchanged."""
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))

    response = api_client.patch(
        _transfer_ownership_url(app, utub_id=1),
        json={_NEW_OWNER_ID_FIELD: 1},
        headers=user_1_headers,
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.TARGET_ALREADY_OWNER
    assert (
        int(response_json[STD_JSON.ERROR_CODE])
        == UTubMembersErrorCodes.TARGET_ALREADY_OWNER
    )
    with app.app_context():
        assert Utubs.query.get(1).utub_creator == 1


def test_transfer_ownership_locked_utub_is_403(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """A locked UTub rejects the transfer → 403 with UTUB_IS_LOCKED."""
    with app.app_context():
        utub: Utubs = Utubs.query.get(1)
        utub.is_locked = True
        db.session.commit()

    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))

    response = api_client.patch(
        _transfer_ownership_url(app, utub_id=1),
        json={_NEW_OWNER_ID_FIELD: 2},
        headers=user_1_headers,
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED
    assert (
        int(response_json[STD_JSON.ERROR_CODE]) == UTubMembersErrorCodes.UTUB_IS_LOCKED
    )
    with app.app_context():
        assert Utubs.query.get(1).utub_creator == 1


@pytest.mark.parametrize(
    "bad_body",
    [
        {},
        {_NEW_OWNER_ID_FIELD: "bogus"},
    ],
)
def test_transfer_ownership_missing_or_invalid_new_owner_id_is_400(
    bad_body: dict,
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """Missing or invalid `new_owner_id` → 400 with the generic invalid-input
    envelope."""
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))

    response = api_client.patch(
        _transfer_ownership_url(app, utub_id=1),
        json=bad_body,
        headers=user_1_headers,
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.UNABLE_TO_TRANSFER_OWNERSHIP
    )
    assert (
        int(response_json[STD_JSON.ERROR_CODE])
        == UTubMembersErrorCodes.INVALID_FORM_INPUT
    )


# ===========================================================================
# Per-IP Flask-Limiter 429 on the /api/v1 add-member twin (JSON envelope)
# ===========================================================================


def _enable_limiter(app: Flask) -> None:
    """Re-arm flask-limiter for this test (globally disabled in tests).

    Mirrors the established pattern in
    tests/integration/mobile_api/test_auth_rate_limit.py.
    """
    original_first_request = app._got_first_request
    app._got_first_request = False
    app.config["RATELIMIT_ENABLED"] = True
    limiter.enabled = True
    limiter.init_app(app)
    app._got_first_request = original_first_request


def _disable_limiter() -> None:
    if limiter._storage is not None:
        limiter._storage.reset()
    limiter._storage = None
    limiter._limiter = None
    limiter.enabled = False
    limiter.initialized = False


def test_add_member_rate_limit_returns_json_429(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    every_user_makes_a_unique_utub,
):
    """
    GIVEN the per-IP MEMBER_ADD_RATE_LIMIT (30/minute) on POST
        /api/v1/utubs/<id>/members
    WHEN a 31st add-member request arrives within the window
    THEN a 429 is returned as the JSON ErrorResponse envelope (never HTML).
    """
    user_1_headers = make_bearer_headers(token_for_user(app, user_id=1))
    user_2_username = valid_users[1]["username"]
    add_url = _create_member_url(app, utub_id=1)
    add_body = {_USERNAME_FIELD: user_2_username}
    allowed_per_window = int(MEMBER_ADD_RATE_LIMIT.split("/")[0])

    _enable_limiter(app)
    try:
        for _attempt_number in range(allowed_per_window):
            response = api_client.post(add_url, json=add_body, headers=user_1_headers)
            assert response.status_code != 429

        rate_limited_response = api_client.post(
            add_url, json=add_body, headers=user_1_headers
        )
        assert rate_limited_response.status_code == 429
        assert rate_limited_response.is_json
        rate_limited_json = rate_limited_response.get_json()
        assert rate_limited_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert rate_limited_json[STD_JSON.MESSAGE] == STD_JSON.TOO_MANY_REQUESTS
    finally:
        _disable_limiter()
