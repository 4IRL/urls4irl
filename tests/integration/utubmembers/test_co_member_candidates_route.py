from __future__ import annotations

from typing import Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend import db
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS as M
from backend.utils.strings.url_validation_strs import URL_VALIDATION

pytestmark = pytest.mark.members

FIRST_USER_ID = 1
SECOND_USER_ID = 2
THIRD_USER_ID = 3
NONEXISTENT_UTUB_ID = 9999


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


def test_co_member_candidates_returns_200_with_shape(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Happy path: 200 + STD_JSON success envelope + members list with the
    {id, username, sharedUtubCount} co-member shape."""
    logged_in_client, _, _, app = login_first_user_without_register

    with app.app_context():
        requester = Users.query.get(FIRST_USER_ID)
        second = Users.query.get(SECOND_USER_ID)
        third = Users.query.get(THIRD_USER_ID)

        target = _make_utub(requester, "Target")
        shared = _make_utub(requester, "Shared")
        _add_member(shared, second)
        _add_member(shared, third)
        target_id = target.id

    response = logged_in_client.get(
        url_for(ROUTES.MEMBERS.CO_MEMBER_CANDIDATES, utub_id=target_id)
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS

    members = body[M.MEMBERS]
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
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A creator with no co-members gets 200 with an empty members list."""
    logged_in_client, _, _, app = login_first_user_without_register

    with app.app_context():
        requester = Users.query.get(FIRST_USER_ID)
        target = _make_utub(requester, "Target")
        target_id = target.id

    response = logged_in_client.get(
        url_for(ROUTES.MEMBERS.CO_MEMBER_CANDIDATES, utub_id=target_id)
    )

    assert response.status_code == 200
    assert response.get_json()[M.MEMBERS] == []


def test_co_member_candidates_non_ajax_redirects(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A non-AJAX request (ajax_required=True) 302-redirects."""
    logged_in_client, _, _, app = login_first_user_without_register

    with app.app_context():
        requester = Users.query.get(FIRST_USER_ID)
        target = _make_utub(requester, "Target")
        target_id = target.id

    response = logged_in_client.get(
        url_for(ROUTES.MEMBERS.CO_MEMBER_CANDIDATES, utub_id=target_id),
        headers={URL_VALIDATION.X_REQUESTED_WITH: "not-ajax"},
    )

    assert response.status_code == 302


def test_co_member_candidates_unauthenticated_redirects(client: FlaskClient) -> None:
    """Anonymous request 302-redirects (auth decorator), not a JSON 401."""
    response = client.get("/utubs/1/co-members")

    assert response.status_code == 302


def test_co_member_candidates_non_creator_forbidden(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A member who is not the creator of the target UTub gets 403."""
    logged_in_client, _, _, app = login_first_user_without_register

    with app.app_context():
        creator = Users.query.get(SECOND_USER_ID)
        requester = Users.query.get(FIRST_USER_ID)
        # UTub created by user 2; user 1 is a member but not the creator
        target = _make_utub(creator, "SomeoneElsesTarget")
        _add_member(target, requester)
        target_id = target.id

    response = logged_in_client.get(
        url_for(ROUTES.MEMBERS.CO_MEMBER_CANDIDATES, utub_id=target_id)
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_co_member_candidates_nonexistent_utub_404(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A request for a UTub that does not exist gets 404."""
    logged_in_client, _, _, _ = login_first_user_without_register

    response = logged_in_client.get(
        url_for(ROUTES.MEMBERS.CO_MEMBER_CANDIDATES, utub_id=NONEXISTENT_UTUB_ID)
    )

    assert response.status_code == 404
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
