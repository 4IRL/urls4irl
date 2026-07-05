from typing import Callable

from flask import Flask
from flask.testing import FlaskClient
import pytest

from backend import db
from backend.api_v1.services.tokens import create_access_token, issue_refresh_token
from backend.models.email_validations import Email_Validations
from backend.models.users import Users
from backend.utils.strings.api_auth_strs import API_AUTH

UNVALIDATED_USERNAME = "unvalidated_mobile"
UNVALIDATED_EMAIL = "unvalidated_mobile_user@example.com"
UNVALIDATED_PASSWORD = "unvalidatedPassword123!"


def _bearer_headers(access_token: str) -> dict[str, str]:
    return {API_AUTH.AUTHORIZATION_HEADER: f"{API_AUTH.BEARER_PREFIX}{access_token}"}


@pytest.fixture
def api_client(app: Flask) -> FlaskClient:
    """A plain test client for the bearer-token /api/v1 surface.

    Deliberately NOT the AjaxFlaskClient/AjaxFlaskLoginClient used by web-route
    tests: no session cookie, no CSRF token, no X-Requested-With header —
    exactly what a native mobile client sends.
    """
    app.test_client_class = FlaskClient
    return app.test_client()


@pytest.fixture
def access_token_first_user(app: Flask, register_first_user) -> str:
    with app.app_context():
        first_user: Users = Users.query.get(1)
        return create_access_token(user=first_user)


@pytest.fixture
def bearer_headers_first_user(access_token_first_user: str) -> dict[str, str]:
    return _bearer_headers(access_token_first_user)


@pytest.fixture
def refresh_token_first_user(app: Flask, register_first_user) -> str:
    with app.app_context():
        first_user: Users = Users.query.get(1)
        return issue_refresh_token(user=first_user)


@pytest.fixture
def make_bearer_headers() -> Callable[[str], dict[str, str]]:
    """Build an Authorization header dict from any access token string."""
    return _bearer_headers


@pytest.fixture
def register_unvalidated_user_with_email_validation_row(app: Flask) -> int:
    """Create a user with email_validated=False and a pending
    Email_Validations row (mirrors the web registration state before the
    validation link is clicked). Returns the new user's id."""
    with app.app_context():
        unvalidated_user = Users(
            username=UNVALIDATED_USERNAME,
            email=UNVALIDATED_EMAIL,
            plaintext_password=UNVALIDATED_PASSWORD,
        )
        pending_email_validation = Email_Validations(
            validation_token=unvalidated_user.get_email_validation_token()
        )
        unvalidated_user.email_confirm = pending_email_validation
        db.session.add(unvalidated_user)
        db.session.commit()
        return unvalidated_user.id


@pytest.fixture
def access_token_unvalidated_user(
    app: Flask, register_unvalidated_user_with_email_validation_row: int
) -> str:
    with app.app_context():
        unvalidated_user: Users = Users.query.get(
            register_unvalidated_user_with_email_validation_row
        )
        return create_access_token(user=unvalidated_user)
