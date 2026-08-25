"""
Integration tests for the bearer-token co-member candidates endpoint:
  GET /api/v1/utubs/<utub_id>/co-members

Exact mobile twin of the web route
(backend/members/routes.py:get_co_member_candidates_route). Delegates to the
same get_co_member_candidates service.

Conventions:
  - Uses api_client (plain FlaskClient, no session/CSRF/AjaxFlaskLoginClient).
  - URL built with url_for() inside app.test_request_context().
  - All JSON key constants imported from backend string modules.
  - pytestmark = pytest.mark.mobile_api
"""

from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend import db
from backend.api_v1.services.tokens import create_access_token
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import API_AUTH, API_AUTH_FAILURE
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS as M

pytestmark = pytest.mark.mobile_api

FIRST_USER_ID = 1
SECOND_USER_ID = 2
THIRD_USER_ID = 3
NONEXISTENT_UTUB_ID = 9999


# ---------------------------------------------------------------------------
# URL / auth helpers
# ---------------------------------------------------------------------------


def _co_members_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.CO_MEMBER_CANDIDATES, utub_id=utub_id)


def _bearer(token: str) -> dict[str, str]:
    return {API_AUTH.AUTHORIZATION_HEADER: f"{API_AUTH.BEARER_PREFIX}{token}"}


def _token_for_user(app: Flask, user_id: int) -> str:
    with app.app_context():
        user: Users = Users.query.get(user_id)
        return create_access_token(user=user)


# ---------------------------------------------------------------------------
# DB builders (mirror the web-route test's fixture shape)
# ---------------------------------------------------------------------------


def _make_utub(creator: Users, name: str) -> Utubs:
    new_utub = Utubs(name=name, utub_creator=creator.id, utub_description="")
    db.session.add(new_utub)
    db.session.commit()

    creator_membership = Utub_Members(member_role=Member_Role.CREATOR)
    creator_membership.utub_id = new_utub.id
    creator_membership.user_id = creator.id
    db.session.add(creator_membership)
    db.session.commit()
    return new_utub


def _add_member(utub: Utubs, user: Users) -> None:
    membership = Utub_Members()
    membership.utub_id = utub.id
    membership.user_id = user.id
    db.session.add(membership)
    db.session.commit()


# ===========================================================================
# GET /api/v1/utubs/<utub_id>/co-members
# ===========================================================================


def test_co_member_candidates_happy_path(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    register_multiple_users,
):
    """
    GIVEN user 1 creates a target UTub and shares another UTub with users 2 and 3
    WHEN GET /api/v1/utubs/<target_id>/co-members with user 1's bearer token
    THEN 200 with success envelope and the co-member {id, username,
         sharedUtubCount} shape, ordered case-insensitively by username
    """
    user_1_token = _token_for_user(app, user_id=1)

    with app.app_context():
        requester = Users.query.get(FIRST_USER_ID)
        second = Users.query.get(SECOND_USER_ID)
        third = Users.query.get(THIRD_USER_ID)

        target = _make_utub(requester, "Target")
        shared = _make_utub(requester, "Shared")
        _add_member(shared, second)
        _add_member(shared, third)
        target_id = target.id

    response = api_client.get(
        _co_members_url(app, utub_id=target_id),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS

    members = response_json[M.MEMBERS]
    assert isinstance(members, list)
    # Ordered case-insensitively by username: CenturyUser1234, PersonalEntry1234
    assert [member[M.USERNAME] for member in members] == [
        "CenturyUser1234",
        "PersonalEntry1234",
    ]
    for member in members:
        assert M.ID in member
        assert M.USERNAME in member
        assert member[M.SHARED_UTUB_COUNT] == 1


def test_co_member_candidates_empty_list(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    register_multiple_users,
):
    """
    GIVEN user 1 creates a UTub but shares no other UTub with anyone
    WHEN GET /api/v1/utubs/<target_id>/co-members with user 1's bearer token
    THEN 200 with success envelope and an empty members list
    """
    user_1_token = _token_for_user(app, user_id=1)

    with app.app_context():
        requester = Users.query.get(FIRST_USER_ID)
        target = _make_utub(requester, "Target")
        target_id = target.id

    response = api_client.get(
        _co_members_url(app, utub_id=target_id),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[M.MEMBERS] == []


def test_co_member_candidates_no_token_is_401(app: Flask, api_client: FlaskClient):
    """No Authorization header → 401 JSON failure."""
    response = api_client.get(_co_members_url(app, utub_id=1))

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_co_member_candidates_unvalidated_email_is_403(
    app: Flask,
    api_client: FlaskClient,
    access_token_unvalidated_user: str,
):
    """
    GIVEN a bearer token for a user whose email is NOT validated
    WHEN GET /api/v1/utubs/1/co-members
    THEN 403 with EMAIL_VALIDATION_REQUIRED (checked before the UTub lookup)
    """
    response = api_client.get(
        _co_members_url(app, utub_id=1),
        headers=_bearer(access_token_unvalidated_user),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.EMAIL_VALIDATION_REQUIRED


def test_co_member_candidates_non_creator_is_403(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    register_multiple_users,
):
    """
    GIVEN user 1 is a member (not creator) of a UTub created by user 2
    WHEN user 1 GETs that UTub's co-members
    THEN 403 (creator-only endpoint)
    """
    user_1_token = _token_for_user(app, user_id=1)

    with app.app_context():
        creator = Users.query.get(SECOND_USER_ID)
        requester = Users.query.get(FIRST_USER_ID)
        target = _make_utub(creator, "SomeoneElsesTarget")
        _add_member(target, requester)
        target_id = target.id

    response = api_client.get(
        _co_members_url(app, utub_id=target_id),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_co_member_candidates_nonexistent_utub_is_404(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
):
    """
    GIVEN a validated creator token
    WHEN GET /api/v1/utubs/<nonexistent_id>/co-members
    THEN 404 (get_or_404 in the membership decorator)
    """
    response = api_client.get(
        _co_members_url(app, utub_id=NONEXISTENT_UTUB_ID),
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 404
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
