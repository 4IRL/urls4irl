from typing import Tuple

from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from src.models.users import Users
from src.utils.all_routes import ROUTES
from src.utils.strings.utub_strs import UTUB_ID_QUERY_PARAM

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
    THEN verify the server resopnds with a 404 message

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
