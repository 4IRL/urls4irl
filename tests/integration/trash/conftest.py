from typing import Generator, Tuple

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend.models.users import Users
from tests.conftest import AjaxFlaskLoginClient
from tests.utils_for_test import get_csrf_token


@pytest.fixture
def login_third_user_without_register(
    app: Flask,
) -> Generator[Tuple[FlaskClient, str, Users, Flask], None, None]:
    """
    Given a user with ID == 3, logs them in and routes them to "/home",
    https://flask-login.readthedocs.io/en/latest/#automated-testing

    Args:
        app (Flask): The Flask client providing an app context

    Yields:
        (FlaskLoginClient): Flask client that logs in a user using flask_login
        (str): The CSRF token string
        (Users): The User model of currently logged in user
        (Flask): The Flask client for providing an app context
    """
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        user_to_login = Users.query.get(3)

    with app.test_client(user=user_to_login) as logged_in_client:
        logged_in_response = logged_in_client.get("/home")
        csrf_token_string = get_csrf_token(logged_in_response.get_data(), meta_tag=True)
        yield logged_in_client, csrf_token_string, user_to_login, app
