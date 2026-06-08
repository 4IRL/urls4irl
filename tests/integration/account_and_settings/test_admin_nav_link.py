from typing import Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend.models.users import Users
from backend.utils.all_routes import ROUTES

pytestmark = pytest.mark.account_and_support

ADMIN_METRICS_HREF = b'href="/admin/metrics"'


def test_admin_nav_link_visible_to_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin user logged in
    WHEN they GET /home
    THEN the response HTML contains the admin metrics nav link
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    home_response = logged_in_client.get(url_for(ROUTES.UTUBS.HOME))

    assert home_response.status_code == 200
    assert ADMIN_METRICS_HREF in home_response.data


def test_admin_nav_link_hidden_for_regular_user(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a regular (non-admin) user logged in
    WHEN they GET /home
    THEN the response HTML does NOT contain the admin metrics nav link
    """
    logged_in_client, _, _, _ = login_first_user_with_register

    home_response = logged_in_client.get(url_for(ROUTES.UTUBS.HOME))

    assert home_response.status_code == 200
    assert ADMIN_METRICS_HREF not in home_response.data
