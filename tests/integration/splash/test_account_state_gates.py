"""Integration tests for the account-state auth gates.

Covers the two Phase 5 gates:
  - Suspension: a suspended user is blocked at login (403 + suspended
    message) and any existing session resolves to anonymous via the
    user_loader.
  - Web-session invalidation: sessions issued before
    ``Users.sessionsInvalidatedAt`` are rejected; a fresh login after the
    invalidation succeeds; a session with no issued-at stamp is rejected
    once an invalidation exists.
"""

from __future__ import annotations

from typing import Tuple

from flask import Flask, g, url_for
from flask.testing import FlaskClient
import pytest

from backend import db
from backend.models.users import Users
from backend.splash.constants import LoginErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.splash_form_strs import LOGIN_FORM
from backend.utils.strings.user_strs import SESSION_ISSUED_AT_KEY, USER_FAILURE
from tests.models_for_test import valid_user_1
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.splash


def _login_payload() -> dict[str, str]:
    return {
        LOGIN_FORM.USERNAME: valid_user_1[LOGIN_FORM.USERNAME],
        LOGIN_FORM.PASSWORD: valid_user_1[LOGIN_FORM.PASSWORD],
    }


def _suspend_user(app: Flask, user_id: int) -> None:
    with app.app_context():
        target_user: Users = Users.query.get(user_id)
        target_user.is_suspended = True
        db.session.commit()


def _clear_flask_login_request_cache() -> None:
    """Drop Flask-Login's per-request user cache (``g._login_user``).

    The test harness keeps one app context alive for the whole test
    (db_transaction fixture), so Flask-Login's per-request ``g`` cache
    persists across sequential test-client requests — something that never
    happens in production, where every request gets a fresh app context.
    Clearing it forces the next request to consult the user_loader again,
    matching production per-request behavior.
    """
    if hasattr(g, "_login_user"):
        delattr(g, "_login_user")


def test_suspended_user_blocked_at_login(app: Flask, register_first_user):
    """
    GIVEN a registered, validated, SUSPENDED user with correct credentials
    WHEN POST /login
    THEN 403 with the account-suspended message and error code, and no
         authenticated session is created (subsequent /home redirects).
    """
    _, registered_user = register_first_user
    _suspend_user(app, registered_user.id)

    client: FlaskClient = app.test_client()
    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    with app.test_request_context():
        login_url = url_for(ROUTES.SPLASH.LOGIN)
        home_url = url_for(ROUTES.UTUBS.HOME)

    login_response = client.post(
        login_url, json=_login_payload(), headers={"X-CSRFToken": csrf_token}
    )

    assert login_response.status_code == 403
    login_body = login_response.get_json()
    assert login_body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert login_body[STD_JSON.MESSAGE] == USER_FAILURE.ACCOUNT_SUSPENDED
    assert login_body[STD_JSON.ERROR_CODE] == int(LoginErrorCodes.ACCOUNT_SUSPENDED)

    home_response = client.get(home_url)
    assert home_response.status_code == 302


def test_suspended_user_existing_session_resolves_anonymous(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged-in user with a live session
    WHEN the user is suspended mid-session
    THEN the next request to a login-gated route redirects to login — the
         user_loader resolves the suspended account to anonymous.
    """
    client, _, logged_in_user, app = login_first_user_with_register

    with app.test_request_context():
        home_url = url_for(ROUTES.UTUBS.HOME)

    pre_suspension_response = client.get(home_url)
    assert pre_suspension_response.status_code == 200

    _suspend_user(app, logged_in_user.id)
    _clear_flask_login_request_cache()

    post_suspension_response = client.get(home_url)
    assert post_suspension_response.status_code == 302


def test_session_issued_before_invalidation_is_rejected(
    app: Flask, register_first_user
):
    """
    GIVEN a user logged in via the real login POST (session stamped with an
          issued-at time)
    WHEN sessions_invalidated_at is set to a moment after that login
    THEN the pre-invalidation session is rejected (redirect to login), and a
         fresh login AFTER the invalidation succeeds again.
    """
    _, registered_user = register_first_user
    registered_user_id: int = registered_user.id

    client: FlaskClient = app.test_client()
    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    with app.test_request_context():
        login_url = url_for(ROUTES.SPLASH.LOGIN)
        home_url = url_for(ROUTES.UTUBS.HOME)

    first_login_response = client.post(
        login_url, json=_login_payload(), headers={"X-CSRFToken": csrf_token}
    )
    assert first_login_response.status_code == 200
    assert client.get(home_url).status_code == 200

    with app.app_context():
        target_user: Users = Users.query.get(registered_user_id)
        assert target_user.sessions_invalidated_at is None
        target_user.sessions_invalidated_at = utc_now()
        db.session.commit()
    _clear_flask_login_request_cache()

    rejected_response = client.get(home_url)
    assert rejected_response.status_code == 302

    _clear_flask_login_request_cache()
    second_login_response = client.post(
        login_url, json=_login_payload(), headers={"X-CSRFToken": csrf_token}
    )
    assert second_login_response.status_code == 200
    assert client.get(home_url).status_code == 200


def test_session_without_issued_stamp_rejected_once_invalidation_set(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a live session whose issued-at stamp is removed (simulating a
          session created before the stamp mechanism existed)
    WHEN sessions_invalidated_at is set for the user
    THEN the unstamped session is rejected — missing stamps fail closed.
    """
    client, _, logged_in_user, app = login_first_user_with_register

    with app.test_request_context():
        home_url = url_for(ROUTES.UTUBS.HOME)

    assert client.get(home_url).status_code == 200

    with client.session_transaction() as flask_session:
        flask_session.pop(SESSION_ISSUED_AT_KEY, None)

    with app.app_context():
        target_user: Users = Users.query.get(logged_in_user.id)
        target_user.sessions_invalidated_at = utc_now()
        db.session.commit()
    _clear_flask_login_request_cache()

    assert client.get(home_url).status_code == 302
