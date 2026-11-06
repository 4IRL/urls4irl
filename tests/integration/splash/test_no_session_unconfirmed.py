"""No session can belong to an unconfirmed account (``load_user`` fails closed)."""

from typing import Generator, Tuple
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend import db
from backend.models.users import Users
from backend.users.routes import unauthorized
from backend.utils.all_routes import ROUTES
from backend.utils.strings.email_validation_strs import EMAILS
from tests.conftest import AjaxFlaskLoginClient

pytestmark = pytest.mark.splash

SPLASH_CONFIG_MARKER = b'id="splashConfig"'


@pytest.fixture
def stale_session_client(
    app: Flask, register_first_user
) -> Generator[Tuple[FlaskClient, Users, Flask], None, None]:
    """A client holding a live session for user 1, who is then marked
    unconfirmed. Simulates a session that pre-dates the rollout."""
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        user: Users = Users.query.get(1)

    with app.test_client(user=user) as client:
        with app.app_context():
            stale_user: Users = Users.query.get(1)
            stale_user.email_validated = False
            db.session.commit()
        yield client, user, app


def test_session_of_unconfirmed_user_is_anonymous(
    stale_session_client: Tuple[FlaskClient, Users, Flask],
):
    """
    GIVEN a session cookie created for a user who is then marked unconfirmed
    WHEN the next request hits an authenticated route
    THEN the request is anonymous and redirects to splash
    """
    client, _, _ = stale_session_client

    response = client.get("/home")

    assert response.status_code == 302
    location = urlsplit(response.location)
    assert location.path == "/"
    assert "next" in parse_qs(location.query)


def test_splash_config_absent_on_authenticated_page(
    register_first_user, login_first_user_without_register
):
    """
    GIVEN a confirmed, logged in user
    WHEN they load an authenticated page
    THEN #splashConfig is not in it (the layout includes splashModals.html only
    for unauthenticated visitors)
    """
    client, _, _, _ = login_first_user_without_register

    response = client.get("/home")

    assert response.status_code == 200
    assert SPLASH_CONFIG_MARKER not in response.data


def test_splash_config_present_on_anonymous_splash(app: Flask):
    """
    GIVEN an anonymous visitor
    WHEN they load the splash page
    THEN #splashConfig is present and no longer carries the removed
    data-show-email-validation attribute
    """
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert SPLASH_CONFIG_MARKER in response.data
    assert b"data-show-email-validation" not in response.data


@pytest.mark.parametrize("route", [ROUTES.SPLASH.LOGIN, ROUTES.SPLASH.REGISTER])
def test_authenticated_user_on_auth_routes_goes_home(
    register_first_user, login_first_user_without_register, route: str
):
    """
    GIVEN a confirmed, logged in user
    WHEN they POST to /login or /register
    THEN they are redirected to HOME
    """
    client, csrf_token, _, _ = login_first_user_without_register

    response = client.post(url_for(route), json={}, headers={"X-CSRFToken": csrf_token})

    assert response.status_code == 302
    assert urlsplit(response.location).path == url_for(ROUTES.UTUBS.HOME)


def test_email_validation_required_still_redirects_unvalidated_session(
    register_first_user, login_first_user_without_register
):
    """
    GIVEN a confirmed, authenticated user whose session flag says the email is
    not validated (defence in depth behind the load_user gate)
    WHEN they request a route gated by email_validation_required
    THEN they are redirected to splash
    """
    client, _, _, _ = login_first_user_without_register

    with client.session_transaction() as session:
        session[EMAILS.EMAIL_VALIDATED_SESS_KEY] = False

    response = client.get("/home")

    assert response.status_code == 302
    assert urlsplit(response.location).path == url_for(ROUTES.SPLASH.SPLASH_PAGE)


def test_unauthorized_handler_always_redirects_to_splash(app: Flask):
    """
    GIVEN the unauthorized handler
    WHEN it runs for an anonymous request
    THEN it returns a redirect to splash carrying the originating path
    """
    with app.test_request_context("/home"):
        response = unauthorized()
        splash_path = url_for(ROUTES.SPLASH.SPLASH_PAGE)

    assert response is not None
    assert response.status_code == 302
    location = urlsplit(response.location)
    assert location.path == splash_path
    assert parse_qs(location.query)["next"] == ["/home?"]
