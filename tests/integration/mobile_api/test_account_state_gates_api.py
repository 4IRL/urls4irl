"""Integration tests for the account-state gates on the /api/v1 surface.

Covers the Phase 5 suspension gate for bearer clients: a suspended user is
refused a token pair at login, and an already-issued access token stops
authenticating the moment the account is suspended (request_loader gate).
"""

from __future__ import annotations

from flask import Flask, g, url_for
from flask.testing import FlaskClient
import pytest

from backend import db
from backend.admin.account_service import kill_user_sessions
from backend.api_v1.constants import ApiAuthErrorCodes
from backend.api_v1.services.google_tokens import GoogleIdTokenClaims
from backend.models.api_refresh_tokens import ApiRefreshTokens
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import API_AUTH_FAILURE
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.splash_form_strs import REGISTER_FORM
from backend.utils.strings.user_strs import USER_FAILURE
from tests.models_for_test import valid_user_1

pytestmark = pytest.mark.mobile_api

_FIRST_USER_ID: int = 1

_ID_TOKEN_KEY = "idToken"
_ACCESS_TOKEN_KEY = "accessToken"
_REFRESH_TOKEN_KEY = "refreshToken"
_FAKE_ID_TOKEN = "fake-google-id-token"
_GOOGLE_SUBJECT = "google-subject-suspended-mobile"
_GOOGLE_EMAIL = "suspended_google_mobile@example.com"
_GOOGLE_NAME = "Suspended Google Mobile User"
_GOOGLE_USERNAME = "suspended_google_mobile"

# Patch target for the id_token verifier inside the mobile Google auth service,
# mirroring tests/integration/mobile_api/test_auth_google.py.
_VERIFY_FN_PATH = "backend.api_v1.services.auth.verify_google_id_token"

# An arbitrary non-target actor id for admin service calls. Bypasses the
# self-action guard and need not correspond to a real row, matching
# test_admin_account_actions.py's last-admin guard test.
_ADMIN_ACTOR_ID: int = 99999
_KILL_REASON = "integration test kill sessions"


def _login_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.AUTH_LOGIN)


def _me_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.GET_ME)


def _google_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.AUTH_GOOGLE)


def _refresh_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.AUTH_REFRESH)


def _valid_login_body() -> dict[str, str]:
    return {
        MODELS.USERNAME: valid_user_1[REGISTER_FORM.USERNAME],
        "password": valid_user_1[REGISTER_FORM.PASSWORD],
    }


def _verified_google_claims() -> GoogleIdTokenClaims:
    """Verified id_token claims for the seeded linked google user, matching
    test_auth_google.py's ``_verified_claims`` shape."""
    return GoogleIdTokenClaims(
        subject=_GOOGLE_SUBJECT,
        email=_GOOGLE_EMAIL,
        email_verified=True,
        name=_GOOGLE_NAME,
    )


def _seed_linked_google_user(app: Flask, *, suspended: bool) -> int:
    """Create a password-less, email-validated user with one linked google
    ``UserOAuthIdentity`` and return the new user's id. ``suspended`` sets the
    account-state gate under test."""
    with app.app_context():
        user = Users(
            username=_GOOGLE_USERNAME, email=_GOOGLE_EMAIL, plaintext_password=None
        )
        user.oauth_identities.append(
            UserOAuthIdentity(provider="google", provider_subject=_GOOGLE_SUBJECT)
        )
        user.email_validated = True
        user.is_suspended = suspended
        db.session.add(user)
        db.session.commit()
        return user.id


def _suspend_first_user(app: Flask) -> None:
    with app.app_context():
        target_user: Users = Users.query.get(_FIRST_USER_ID)
        target_user.is_suspended = True
        db.session.commit()


def _clear_flask_login_request_cache() -> None:
    """Drop Flask-Login's per-request user cache (``g._login_user``).

    The test harness keeps one app context alive for the whole test, so the
    per-request ``g`` cache persists across sequential test-client requests —
    never the case in production. Clearing it forces the next request through
    the request_loader again, matching production per-request behavior.
    """
    if hasattr(g, "_login_user"):
        delattr(g, "_login_user")


def test_suspended_user_api_login_returns_403(
    app: Flask, api_client: FlaskClient, register_first_user
):
    """
    GIVEN a registered, validated, SUSPENDED user with correct credentials
    WHEN POST /api/v1/auth/login
    THEN 403 with the account-suspended message and error code — no token
         pair is issued.
    """
    _suspend_first_user(app)

    response = api_client.post(_login_url(app), json=_valid_login_body())

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == USER_FAILURE.ACCOUNT_SUSPENDED
    assert response_json[STD_JSON.ERROR_CODE] == int(
        ApiAuthErrorCodes.ACCOUNT_SUSPENDED
    )


def test_suspended_user_bearer_token_stops_authenticating(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
):
    """
    GIVEN a valid, unexpired access token for a user
    WHEN the user is suspended after the token was issued
    THEN the token no longer authenticates — /api/v1/me returns 401 — even
         though the JWT itself is still cryptographically valid.
    """
    pre_suspension_response = api_client.get(
        _me_url(app), headers=bearer_headers_first_user
    )
    assert pre_suspension_response.status_code == 200

    _suspend_first_user(app)
    _clear_flask_login_request_cache()

    post_suspension_response = api_client.get(
        _me_url(app), headers=bearer_headers_first_user
    )
    assert post_suspension_response.status_code == 401


def test_suspended_user_google_api_auth_returns_403(
    app: Flask, api_client: FlaskClient, monkeypatch: pytest.MonkeyPatch
):
    """
    GIVEN a SUSPENDED user with a linked google identity and a verifiable
        id_token
    WHEN POST /api/v1/auth/google resolves that identity
    THEN 403 with the account-suspended message and error code — no token pair
        is issued and no refresh token is persisted.
    """
    monkeypatch.setattr(_VERIFY_FN_PATH, lambda *, id_token: _verified_google_claims())
    _seed_linked_google_user(app, suspended=True)

    with app.app_context():
        assert ApiRefreshTokens.query.count() == 0

    response = api_client.post(_google_url(app), json={_ID_TOKEN_KEY: _FAKE_ID_TOKEN})

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == USER_FAILURE.ACCOUNT_SUSPENDED
    assert response_json[STD_JSON.ERROR_CODE] == int(
        ApiAuthErrorCodes.ACCOUNT_SUSPENDED
    )
    assert _ACCESS_TOKEN_KEY not in response_json
    assert _REFRESH_TOKEN_KEY not in response_json

    with app.app_context():
        assert ApiRefreshTokens.query.count() == 0


def test_unsuspended_user_google_api_auth_issues_token_pair(
    app: Flask, api_client: FlaskClient, monkeypatch: pytest.MonkeyPatch
):
    """
    GIVEN an UNSUSPENDED user with a linked google identity and a verifiable
        id_token
    WHEN POST /api/v1/auth/google resolves that identity
    THEN 200 with a token pair — the positive counterpart proving the 403 above
        is the suspension gate, not a broken google-auth path.
    """
    monkeypatch.setattr(_VERIFY_FN_PATH, lambda *, id_token: _verified_google_claims())
    _seed_linked_google_user(app, suspended=False)

    with app.app_context():
        assert ApiRefreshTokens.query.count() == 0

    response = api_client.post(_google_url(app), json={_ID_TOKEN_KEY: _FAKE_ID_TOKEN})

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[_ACCESS_TOKEN_KEY]
    assert response_json[_REFRESH_TOKEN_KEY]

    with app.app_context():
        assert ApiRefreshTokens.query.count() == 1


def test_kill_sessions_rejects_subsequent_refresh(
    app: Flask, api_client: FlaskClient, refresh_token_first_user: str
):
    """
    GIVEN a user with a live refresh token
    WHEN an admin kill-sessions the user, then that now-revoked refresh token is
        presented to POST /api/v1/auth/refresh
    THEN 401 with the invalid-refresh-token error code — the admin action
        revokes the refresh-token family end-to-end.
    """
    with app.app_context():
        token_row: ApiRefreshTokens = ApiRefreshTokens.query.filter_by(
            user_id=_FIRST_USER_ID
        ).first()
        assert token_row is not None
        assert token_row.revoked_at is None

    with app.app_context():
        kill_response = kill_user_sessions(
            actor_id=_ADMIN_ACTOR_ID,
            target_user_id=_FIRST_USER_ID,
            reason=_KILL_REASON,
        )
        assert kill_response[1] == 200

    with app.app_context():
        revoked_row: ApiRefreshTokens = ApiRefreshTokens.query.filter_by(
            user_id=_FIRST_USER_ID
        ).first()
        assert revoked_row.revoked_at is not None

    refresh_response = api_client.post(
        _refresh_url(app), json={_REFRESH_TOKEN_KEY: refresh_token_first_user}
    )

    assert refresh_response.status_code == 401
    refresh_json = refresh_response.get_json()
    assert refresh_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.INVALID_REFRESH_TOKEN
    assert refresh_json[STD_JSON.ERROR_CODE] == int(
        ApiAuthErrorCodes.INVALID_REFRESH_TOKEN
    )


def test_access_token_survives_kill_sessions_until_expiry_by_design(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    refresh_token_first_user: str,
):
    """
    Documents the intended short-lived-access-token design contract.

    An admin kill-sessions revokes the user's refresh tokens IMMEDIATELY (so no
    new access tokens can be minted) and stamps ``sessions_invalidated_at`` —
    but a still-unexpired access token continues to authenticate on the /api/v1
    surface until it naturally expires. The bearer request_loader
    (backend/users/routes.py) intentionally gates only on ``is_suspended``,
    never on ``sessions_invalidated_at``. This asymmetry — immediate refresh
    revocation plus eventual access-token expiry — is the deliberate design
    contract, not a bug: full lockout is achieved by suspending the account.
    """
    pre_kill_response = api_client.get(_me_url(app), headers=bearer_headers_first_user)
    assert pre_kill_response.status_code == 200

    with app.app_context():
        kill_response = kill_user_sessions(
            actor_id=_ADMIN_ACTOR_ID,
            target_user_id=_FIRST_USER_ID,
            reason=_KILL_REASON,
        )
        assert kill_response[1] == 200

    with app.app_context():
        target_user: Users = Users.query.get(_FIRST_USER_ID)
        assert target_user.sessions_invalidated_at is not None
        assert not target_user.is_suspended
    _clear_flask_login_request_cache()

    # The already-issued access token still authenticates by design.
    post_kill_response = api_client.get(_me_url(app), headers=bearer_headers_first_user)
    assert post_kill_response.status_code == 200

    # The refresh half of the contract: the refresh token is revoked at once.
    refresh_response = api_client.post(
        _refresh_url(app), json={_REFRESH_TOKEN_KEY: refresh_token_first_user}
    )
    assert refresh_response.status_code == 401
