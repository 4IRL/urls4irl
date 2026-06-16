from typing import Generator, Tuple

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend import db
from backend.models.users import Users
from tests.conftest import AjaxFlaskLoginClient


@pytest.fixture
def logged_out_app(app_with_server_name: Flask) -> Generator[Flask, None, None]:
    with app_with_server_name.app_context():
        yield app_with_server_name


@pytest.fixture
def login_unvalidated_user(
    app: Flask, register_first_user
) -> Generator[Tuple[FlaskClient, Users, Flask], None, None]:
    """
    Registers the user with ID == 1, flips ``email_validated`` to ``False``,
    then logs them in via flask_login. Used to exercise the
    ``email_validation_required`` gate's redirect for authenticated-but-
    unvalidated users.
    """
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        unvalidated_user: Users = Users.query.get(1)
        unvalidated_user.email_validated = False
        db.session.commit()

    with app.test_client(user=unvalidated_user) as logged_in_client:
        yield logged_in_client, unvalidated_user, app
