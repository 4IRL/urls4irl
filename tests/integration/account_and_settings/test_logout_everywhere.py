"""Integration tests for the self-service "log out everywhere" endpoint
(``POST /users/<id>/logout-everywhere``).

Uses the ``login_first_user_with_register`` fixture and the meta-tag CSRF scrape,
and exercises the non-destructive session-revocation path (D-1: no re-auth):
``sessions_invalidated_at`` is bumped WITHOUT re-stamping the acting session
(D-4), every refresh token is revoked, and the acting session is logged out so a
follow-up gated request 302-redirects. The ``ACCOUNT_SESSIONS_REVOKED`` domain
metric emit is covered separately on the metrics-enabled app, mirroring
``test_account_delete.py``'s dedicated metric test.
"""

from __future__ import annotations

from typing import Tuple

import pytest
from flask import Flask, g, url_for
from flask.testing import FlaskClient
from redis import Redis

from backend.api_v1.services.tokens import issue_refresh_token
from backend.metrics.events import EventName
from backend.models.api_refresh_tokens import ApiRefreshTokens
from backend.models.users import Users
from backend.schemas.users import AccountRemovalResponseSchema
from backend.users.constants import LogoutEverywhereErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.user_strs import LOGOUT_EVERYWHERE_SUCCESS, REDIRECT_URL
from tests.conftest import AjaxFlaskLoginClient
from tests.integration.system.metrics_helpers import count_counter_keys
from tests.integration.utils import assert_response_conforms_to_schema
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.account_and_support


def _clear_flask_login_request_cache() -> None:
    """Drop Flask-Login's per-request user cache (``g._login_user``) so the next
    request consults the user_loader again."""
    if hasattr(g, "_login_user"):
        delattr(g, "_login_user")


def _seed_refresh_token(app: Flask, user_id: int) -> int:
    with app.app_context():
        user: Users = Users.query.get(user_id)
        issue_refresh_token(user=user)
        token_row: ApiRefreshTokens = ApiRefreshTokens.query.filter_by(
            user_id=user_id
        ).first()
        return token_row.id


# --------------------------------------------------------------------------- #
# Happy path — stamp bump + token revoke + redirect (no metric assertion here:
# login_first_user_with_register's app never enables metrics, so record_event
# no-ops and a metric assertion would be vacuous).
# --------------------------------------------------------------------------- #


def test_logout_everywhere_happy_path_revokes_sessions_and_tokens(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A valid POST returns 200 with the splash ``redirectUrl``, bumps
    ``sessions_invalidated_at``, and revokes every refresh token."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id
    refresh_token_id = _seed_refresh_token(app, user_id)

    response = client.post(
        url_for(ROUTES.USERS.LOGOUT_EVERYWHERE, user_id=user_id),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.content_type == "application/json"
    response_json = response.get_json()
    assert_response_conforms_to_schema(
        response_json,
        AccountRemovalResponseSchema,
        expected_keys={STD_JSON.STATUS, STD_JSON.MESSAGE, REDIRECT_URL},
    )
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == LOGOUT_EVERYWHERE_SUCCESS
    assert response_json[REDIRECT_URL] == url_for(ROUTES.SPLASH.SPLASH_PAGE)

    with app.app_context():
        refreshed: Users = Users.query.get(user_id)
        # Session kill-switch stamp bumped for the whole account.
        assert refreshed.sessions_invalidated_at is not None
        # Account is NOT destroyed — non-destructive flow.
        assert refreshed.email_validated is True
        assert refreshed.password is not None
        # Refresh token revoked.
        revoked_token: ApiRefreshTokens = ApiRefreshTokens.query.get(refresh_token_id)
        assert revoked_token.revoked_at is not None


def test_logout_everywhere_immediately_logs_acting_session_out(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """After logging out everywhere the acting session is dead too (D-4): the
    next gated GET resolves to anonymous and 302-redirects."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.post(
        url_for(ROUTES.USERS.LOGOUT_EVERYWHERE, user_id=user.id),
        headers={"X-CSRFToken": csrf_token},
    )
    assert response.status_code == 200

    _clear_flask_login_request_cache()
    settings_response = client.get(url_for(ROUTES.USERS.SETTINGS))
    assert settings_response.status_code == 302


def test_logout_everywhere_works_without_any_reauth(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """The endpoint takes no body — no password / OAuth-proof gate (D-1). A POST
    with no JSON payload still succeeds."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.post(
        url_for(ROUTES.USERS.LOGOUT_EVERYWHERE, user_id=user.id),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.SUCCESS


def test_logout_everywhere_self_ownership_mismatch_returns_403(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A POST whose URL user_id is not the acting user is rejected 403 with the
    NOT_AUTHORIZED error code; no session state is changed."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    response = client.post(
        url_for(ROUTES.USERS.LOGOUT_EVERYWHERE, user_id=user_id + 999),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    assert (
        response.get_json()[STD_JSON.ERROR_CODE]
        == LogoutEverywhereErrorCodes.NOT_AUTHORIZED
    )

    with app.app_context():
        untouched: Users = Users.query.get(user_id)
        assert untouched.sessions_invalidated_at is None


# --------------------------------------------------------------------------- #
# ACCOUNT_SESSIONS_REVOKED domain metric (dedicated per-flow emit test — the
# DOMAIN_EVENTS_TESTED_ELSEWHERE exclusion in metrics_helpers.py promises this).
# --------------------------------------------------------------------------- #


def test_logout_everywhere_records_account_sessions_revoked_metric(
    metrics_enabled_app: Flask,
    provide_metrics_redis: Redis | None,
    register_first_user,
) -> None:
    """A successful log-out-everywhere writes exactly one ACCOUNT_SESSIONS_REVOKED
    counter key to the metrics Redis DB."""
    if provide_metrics_redis is None:
        pytest.skip("metrics Redis is unavailable in this environment")

    app = metrics_enabled_app
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        target: Users = Users.query.get(1)
        user_id = target.id

    assert (
        count_counter_keys(provide_metrics_redis, EventName.ACCOUNT_SESSIONS_REVOKED)
        == 0
    )

    with app.app_context():
        user_to_login: Users = Users.query.get(user_id)

    with app.test_client(user=user_to_login) as logged_in_client:
        home_response = logged_in_client.get("/home")
        csrf_token = get_csrf_token(home_response.get_data(), meta_tag=True)
        response = logged_in_client.post(
            url_for(ROUTES.USERS.LOGOUT_EVERYWHERE, user_id=user_id),
            headers={"X-CSRFToken": csrf_token},
        )
        assert response.status_code == 200

    assert (
        count_counter_keys(provide_metrics_redis, EventName.ACCOUNT_SESSIONS_REVOKED)
        == 1
    )
