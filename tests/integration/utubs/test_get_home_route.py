from typing import Tuple

from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from src.models.users import Users
from src.models.utub_members import Utub_Members
from src.utils.all_routes import ROUTES
from src.utils.strings.utub_strs import UTUB_ID_QUERY_PARAM
from tests.utils_for_test import is_string_in_logs

pytestmark = pytest.mark.utubs


def test_get_invalid_utub_on_home_page(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user who is not a member a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the server resopnds with a 404 message

    Args:
        every_user_makes_a_unique_utub (None): Fixture to create a new UTub for every user, with no members but the creators
        login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask]): Fixture to login in the member instead of UTub creator
    """
    for utubid in ("5/asdf", "5.1", "9.abc", "-1"):
        client, _, _, _ = login_first_user_without_register
        url_to_get = url_for(ROUTES.UTUBS.HOME) + f"?{UTUB_ID_QUERY_PARAM}={utubid}"

        response = client.get(url_to_get)

        assert response.status_code == 404


def test_get_nonexistent_utub_on_home_page(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user who is not a member a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the server resopnds with a 404 message

    Args:
        every_user_makes_a_unique_utub (None): Fixture to create a new UTub for every user, with no members but the creators
        login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask]): Fixture to login in the member instead of UTub creator
    """
    for utubid in (
        2147483648,
        999999,
    ):
        client, _, _, _ = login_first_user_without_register
        url_to_get = url_for(ROUTES.UTUBS.HOME) + f"?{UTUB_ID_QUERY_PARAM}={utubid}"

        response = client.get(url_to_get)
        assert response.status_code == 404


def test_get_home_page(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user who is not a member a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the server responds with appropriate HTML

    Args:
        every_user_makes_a_unique_utub (None): Fixture to create a new UTub for every user, with no members but the creators
        login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask]): Fixture to login in the member instead of UTub creator
    """
    client, _, user, _ = login_first_user_without_register
    logged_in_username = user.username
    url_to_get = url_for(ROUTES.UTUBS.HOME)

    response = client.get(url_to_get)
    assert response.status_code == 200
    assert (
        f'<b id="loggedInAsHeader">Logged in as {logged_in_username}</b>'.encode()
        in response.data
    )


def test_get_home_page_when_not_in_utub(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    caplog,
):
    """
    GIVEN a user who is not a member a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the server responds with appropriate HTML

    Args:
        every_user_makes_a_unique_utub (None): Fixture to create a new UTub for every user, with no members but the creators
        login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask]): Fixture to login in the member instead of UTub creator
    """
    client, _, user, app = login_first_user_without_register
    with app.app_context():
        member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id != user.id
        ).first()
        utub_id_not_member_of = member.utub_id

    url_to_get = (
        url_for(ROUTES.UTUBS.HOME) + f"?{UTUB_ID_QUERY_PARAM}={utub_id_not_member_of}"
    )

    response = client.get(url_to_get)
    assert response.status_code == 302
    assert is_string_in_logs(
        f"User {user.id} not a member of UTub.id={utub_id_not_member_of}",
        caplog.records,
    )


def test_get_home_page_success_logs(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    caplog,
):
    """
    GIVEN a user who is not a member a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the logs are correct
    """
    client, _, user, _ = login_first_user_without_register
    url_to_get = url_for(ROUTES.UTUBS.HOME)

    response = client.get(url_to_get)
    assert response.status_code == 200
    assert is_string_in_logs("Returning user's UTubs on home page load", caplog.records)


def test_get_invalid_utub_on_home_page_logs(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    caplog,
):
    """
    GIVEN a user who is not a member a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the server logs are correct
    """
    client, _, user, _ = login_first_user_without_register

    invalid_query_params_and_logs = {
        f"?{UTUB_ID_QUERY_PARAM}=9.abc": f"Invalid UTub.id=9.abc for User={user.id}",
        f"?{UTUB_ID_QUERY_PARAM}=1&{UTUB_ID_QUERY_PARAM}=2": "Too many query parameters",
        "?abc=1": f"User={user.id} | Does not contain 'UTubID' as a query parameter",
    }

    for invalid_param, log_msg in invalid_query_params_and_logs.items():
        url_to_get = url_for(ROUTES.UTUBS.HOME) + invalid_param

        response = client.get(url_to_get)

        assert response.status_code == 404
        assert is_string_in_logs(log_msg, caplog.records)
