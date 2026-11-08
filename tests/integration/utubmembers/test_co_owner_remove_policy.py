import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend.members.constants import UTubMembersErrorCodes
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS
from backend.utils.strings.utub_strs import UTUB_FAILURE
from tests.utils_for_test import lock_utub, set_member_role, set_members_settings

pytestmark = pytest.mark.members

OWNER_ID = 1
CO_OWNER_ID = 2
OTHER_ID = 3
NON_MEMBER_ID = 9999


def _utub_id(app: Flask) -> int:
    with app.app_context():
        return Utubs.query.first().id


def _remove(client: FlaskClient, csrf_token_string: str, utub_id: int, user_id: int):
    return client.delete(
        url_for(ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=utub_id, user_id=user_id),
        headers={"X-CSRFToken": csrf_token_string},
    )


def _is_member(app: Flask, utub_id: int, user_id: int) -> bool:
    with app.app_context():
        return Utub_Members.query.get((utub_id, user_id)) is not None


def _assert_switch_off_refusal(response) -> None:
    assert response.status_code == 403
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response.json[STD_JSON.MESSAGE] == MEMBER_FAILURE.CO_OWNER_REMOVE_NOT_ALLOWED
    assert (
        int(response.json[STD_JSON.ERROR_CODE])
        == UTubMembersErrorCodes.CO_OWNER_REMOVE_NOT_ALLOWED
    )


def test_co_owner_removing_plain_member_with_switch_off_is_refused(
    add_multiple_users_to_utub_without_logging_in, login_second_user_without_register
):
    """
    GIVEN a UTub with the default (off) co-owner removal switch and user 2 a co-owner
    WHEN the co-owner removes plain member user 3
    THEN 403 with errorCode CO_OWNER_REMOVE_NOT_ALLOWED and the member stays
    """
    client, csrf_token_string, _, app = login_second_user_without_register
    utub_id = _utub_id(app)
    set_member_role(
        app, utub_id=utub_id, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR
    )

    response = _remove(client, csrf_token_string, utub_id, OTHER_ID)

    _assert_switch_off_refusal(response)
    assert _is_member(app, utub_id, OTHER_ID)


def test_co_owner_removing_plain_member_with_switch_on_succeeds(
    add_multiple_users_to_utub_without_logging_in, login_second_user_without_register
):
    """
    GIVEN a UTub with the co-owner removal switch on and user 2 a co-owner
    WHEN the co-owner removes plain member user 3
    THEN 200 and the member is removed
    """
    client, csrf_token_string, _, app = login_second_user_without_register
    utub_id = _utub_id(app)
    set_member_role(
        app, utub_id=utub_id, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR
    )
    set_members_settings(app, utub_id, {"co_owners_can_remove": True})

    response = _remove(client, csrf_token_string, utub_id, OTHER_ID)

    assert response.status_code == 200
    assert response.json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.MEMBER_REMOVED
    assert not _is_member(app, utub_id, OTHER_ID)


@pytest.mark.parametrize("corrupt_value", ["garbage", 2, None, [True]])
def test_co_owner_removing_with_corrupt_stored_override_is_refused(
    add_multiple_users_to_utub_without_logging_in,
    login_second_user_without_register,
    corrupt_value,
):
    """
    GIVEN a stored co_owners_can_remove override that is not exactly True
    WHEN a co-owner removes plain member user 3
    THEN the removal fails closed with 403 and the member stays
    """
    client, csrf_token_string, _, app = login_second_user_without_register
    utub_id = _utub_id(app)
    set_member_role(
        app, utub_id=utub_id, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR
    )
    set_members_settings(app, utub_id, {"co_owners_can_remove": corrupt_value})

    response = _remove(client, csrf_token_string, utub_id, OTHER_ID)

    assert response.status_code == 403
    assert _is_member(app, utub_id, OTHER_ID)


def test_co_owner_removing_co_owner_with_switch_off_gets_switch_refusal(
    add_multiple_users_to_utub_without_logging_in, login_second_user_without_register
):
    """
    GIVEN the switch off and users 2 and 3 both co-owners
    WHEN co-owner 2 removes co-owner 3
    THEN errorCode CO_OWNER_REMOVE_NOT_ALLOWED (the switch check runs before the target
        lookup) and the target stays
    """
    client, csrf_token_string, _, app = login_second_user_without_register
    utub_id = _utub_id(app)
    set_member_role(
        app, utub_id=utub_id, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR
    )
    set_member_role(app, utub_id=utub_id, user_id=OTHER_ID, role=Member_Role.CO_CREATOR)

    response = _remove(client, csrf_token_string, utub_id, OTHER_ID)

    _assert_switch_off_refusal(response)
    assert _is_member(app, utub_id, OTHER_ID)


def test_co_owner_removing_co_owner_with_switch_on_is_refused_without_error_code(
    add_multiple_users_to_utub_without_logging_in, login_second_user_without_register
):
    """
    GIVEN the switch on and users 2 and 3 both co-owners
    WHEN co-owner 2 removes co-owner 3
    THEN 403 with CO_OWNER_CANNOT_REMOVE_CO_OWNER and no errorCode; the target stays
    """
    client, csrf_token_string, _, app = login_second_user_without_register
    utub_id = _utub_id(app)
    set_member_role(
        app, utub_id=utub_id, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR
    )
    set_member_role(app, utub_id=utub_id, user_id=OTHER_ID, role=Member_Role.CO_CREATOR)
    set_members_settings(app, utub_id, {"co_owners_can_remove": True})

    response = _remove(client, csrf_token_string, utub_id, OTHER_ID)

    assert response.status_code == 403
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        response.json[STD_JSON.MESSAGE]
        == MEMBER_FAILURE.CO_OWNER_CANNOT_REMOVE_CO_OWNER
    )
    assert response.json.get(STD_JSON.ERROR_CODE) is None
    assert _is_member(app, utub_id, OTHER_ID)


@pytest.mark.parametrize("switch_on", [False, True])
def test_co_owner_removing_owner_gets_cannot_remove_owner(
    add_multiple_users_to_utub_without_logging_in,
    login_second_user_without_register,
    switch_on,
):
    """
    GIVEN a co-owner (user 2) and the switch off or on
    WHEN the co-owner removes the owner
    THEN CANNOT_REMOVE_OWNER either way and the owner stays
    """
    client, csrf_token_string, _, app = login_second_user_without_register
    utub_id = _utub_id(app)
    set_member_role(
        app, utub_id=utub_id, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR
    )
    set_members_settings(app, utub_id, {"co_owners_can_remove": switch_on})

    response = _remove(client, csrf_token_string, utub_id, OWNER_ID)

    assert response.status_code == 403
    assert response.json[STD_JSON.MESSAGE] == MEMBER_FAILURE.CANNOT_REMOVE_OWNER
    assert _is_member(app, utub_id, OWNER_ID)


def test_co_owner_removing_non_member_with_switch_off_gets_switch_refusal(
    add_multiple_users_to_utub_without_logging_in, login_second_user_without_register
):
    """
    GIVEN the switch off and user 2 a co-owner
    WHEN the co-owner removes a user id that is not a member
    THEN errorCode CO_OWNER_REMOVE_NOT_ALLOWED, not a 404 (learns nothing about targets)
    """
    client, csrf_token_string, _, app = login_second_user_without_register
    utub_id = _utub_id(app)
    set_member_role(
        app, utub_id=utub_id, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR
    )

    response = _remove(client, csrf_token_string, utub_id, NON_MEMBER_ID)

    _assert_switch_off_refusal(response)


def test_co_owner_can_leave_with_switch_off(
    add_multiple_users_to_utub_without_logging_in, login_second_user_without_register
):
    """
    GIVEN the switch off and user 2 a co-owner
    WHEN the co-owner removes themself
    THEN 200 and they are no longer a member
    """
    client, csrf_token_string, _, app = login_second_user_without_register
    utub_id = _utub_id(app)
    set_member_role(
        app, utub_id=utub_id, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR
    )

    response = _remove(client, csrf_token_string, utub_id, CO_OWNER_ID)

    assert response.status_code == 200
    assert not _is_member(app, utub_id, CO_OWNER_ID)


@pytest.mark.parametrize("target_role", [Member_Role.MEMBER, Member_Role.CO_CREATOR])
def test_owner_removes_anyone_regardless_of_switch(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    target_role,
):
    """
    GIVEN the switch off (default) and the owner logged in
    WHEN the owner removes a plain member or a co-owner
    THEN 200 and the target is removed
    """
    client, csrf_token_string, _, app = login_first_user_without_register
    utub_id = _utub_id(app)
    set_member_role(app, utub_id=utub_id, user_id=OTHER_ID, role=target_role)

    response = _remove(client, csrf_token_string, utub_id, OTHER_ID)

    assert response.status_code == 200
    assert not _is_member(app, utub_id, OTHER_ID)


def test_plain_member_cannot_remove_others_even_with_switch_on(
    add_multiple_users_to_utub_without_logging_in, login_second_user_without_register
):
    """
    GIVEN the switch on and user 2 a plain member
    WHEN the plain member removes user 3
    THEN 403 INVALID_PERMISSION_TO_REMOVE and the target stays
    """
    client, csrf_token_string, _, app = login_second_user_without_register
    utub_id = _utub_id(app)
    set_members_settings(app, utub_id, {"co_owners_can_remove": True})

    response = _remove(client, csrf_token_string, utub_id, OTHER_ID)

    assert response.status_code == 403
    assert (
        response.json[STD_JSON.MESSAGE] == MEMBER_FAILURE.INVALID_PERMISSION_TO_REMOVE
    )
    assert _is_member(app, utub_id, OTHER_ID)


def test_locked_utub_response_wins_over_switch_off_refusal(
    add_multiple_users_to_utub_without_logging_in, login_second_user_without_register
):
    """
    GIVEN a locked UTub with the switch off and user 2 a co-owner
    WHEN the co-owner removes a plain member
    THEN the locked response, not errorCode CO_OWNER_REMOVE_NOT_ALLOWED
    """
    client, csrf_token_string, _, app = login_second_user_without_register
    utub_id = _utub_id(app)
    set_member_role(
        app, utub_id=utub_id, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR
    )
    lock_utub(app, utub_id)

    response = _remove(client, csrf_token_string, utub_id, OTHER_ID)

    assert response.status_code == 403
    assert response.json[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED
    assert (
        int(response.json[STD_JSON.ERROR_CODE]) == UTubMembersErrorCodes.UTUB_IS_LOCKED
    )
    assert _is_member(app, utub_id, OTHER_ID)


def test_switch_turned_off_after_page_load_refuses_removal(
    add_multiple_users_to_utub_without_logging_in, login_second_user_without_register
):
    """
    GIVEN the switch on when the co-owner loaded the page, then turned off by the owner
    WHEN the co-owner removes a plain member
    THEN the request is refused (the setting is read after the lock)
    """
    client, csrf_token_string, _, app = login_second_user_without_register
    utub_id = _utub_id(app)
    set_member_role(
        app, utub_id=utub_id, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR
    )
    set_members_settings(app, utub_id, {"co_owners_can_remove": True})
    set_members_settings(app, utub_id, {"co_owners_can_remove": False})

    response = _remove(client, csrf_token_string, utub_id, OTHER_ID)

    _assert_switch_off_refusal(response)
    assert _is_member(app, utub_id, OTHER_ID)
