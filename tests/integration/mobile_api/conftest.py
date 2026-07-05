from typing import Callable

from flask import Flask
from flask.testing import FlaskClient
import pytest

from backend.api_v1.services.tokens import create_access_token, issue_refresh_token
from backend.models.users import Users
from backend.utils.strings.api_auth_strs import API_AUTH


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
