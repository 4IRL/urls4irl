"""Integration tests for the Google OAuth login/callback flow.

Authlib's token exchange (`oauth.google.authorize_access_token`) and, where
needed, `find_or_create_oauth_user` are mocked at the call sites used inside
`backend/splash/services/oauth/google_service.py` — the same
`unittest.mock.patch`-as-decorator convention used by `test_email_validation.py`
and `test_forgot_password_oauth.py`. `oauth.google` itself is registered for
every test run via `tests/conftest.py`'s `build_app` fixture (dummy
credentials), so no per-test Authlib client setup is needed.
"""

from __future__ import annotations

from unittest import mock

from authlib.integrations.base_client.errors import OAuthError
from flask import Flask, url_for
from flask_login import current_user
import pytest

from backend import db
from backend.metrics.events import EventName
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.utils.all_routes import OAUTH_ROUTES, ROUTES
from backend.utils.strings import model_strs
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
)
from tests.models_for_test import valid_user_1

pytestmark = pytest.mark.splash

_AUTHORIZE_ACCESS_TOKEN_TARGET = (
    "backend.splash.services.oauth.google_service.oauth.google.authorize_access_token"
)
_FIND_OR_CREATE_OAUTH_USER_TARGET = (
    "backend.splash.services.oauth.google_service.find_or_create_oauth_user"
)

_FAKE_CODE = "fake-authorization-code"
_FAKE_STATE = "fake-state-value"

_EXISTING_SUBJECT = "sub_existing"
_EXISTING_EMAIL = "existingoauthuser@example.com"
_EXISTING_USERNAME = "existingoauthuser"

_NEW_USER_SUBJECT = "sub_brand_new"
_NEW_USER_EMAIL = "newoauthuser@example.com"
_NEW_USER_NAME = "New OAuth User"

_UNVERIFIED_SUBJECT = "sub_unverified"
_UNVERIFIED_EMAIL = "unverifiedoauthuser@example.com"

_METRICS_NEW_USER_SUBJECT = "sub_metrics_new"
_METRICS_NEW_USER_EMAIL = "metricsnewuser@example.com"
_METRICS_COLLISION_SUBJECT = "sub_metrics_collision"
_METRICS_COLLISION_USERNAME = "metricscollisionuser"
_METRICS_COLLISION_EMAIL = "metricscollisionuser@example.com"
_METRICS_COLLISION_PASSWORD = "P@ssword123!"

_GENERIC_FAILURE_MESSAGE = "Sign-in failed, please try again."
_UNVERIFIED_EMAIL_MESSAGE = (
    "Google has not verified this email address — please verify it with "
    "Google and try again."
)
_EMAIL_COLLISION_MESSAGE = (
    "Email already registered — log in with your password instead."
)
_CONSENT_DECLINED_MESSAGE = "Sign-in was cancelled."

_LOGIN_SUCCESS_METHOD_DIM_KEY = "method"
_LOGIN_FAILURE_REASON_DIM_KEY = "reason"
_GOOGLE_METHOD_DIM_VALUE = "google"


def _build_mocked_token(
    *,
    subject: str,
    email: str,
    email_verified: bool | None = True,
    name: str | None = None,
) -> dict:
    """Builds the dict shape `authorize_access_token()` returns with a parsed
    `userinfo` OIDC claims set attached, matching the real-openid-scope branch
    `handle_google_callback` reads from. Passing `email_verified=None` omits
    the claim entirely, matching a provider response that never sets it."""
    userinfo = {"sub": subject, "email": email}
    if email_verified is not None:
        userinfo["email_verified"] = email_verified
    if name is not None:
        userinfo["name"] = name
    return {"userinfo": userinfo}


def _callback_url(**query_args: str) -> str:
    return url_for(OAUTH_ROUTES.GOOGLE_CALLBACK, **query_args)


def _seed_existing_oauth_user(
    app: Flask, *, subject: str, email: str, username: str
) -> None:
    """Create and commit an email-validated, password-less user with one
    linked google `UserOAuthIdentity`, matching `test_forgot_password_oauth.py`'s
    `_make_oauth_only_user` pattern."""
    with app.app_context():
        user = Users(username=username, email=email, plaintext_password=None)
        user.oauth_identities.append(
            UserOAuthIdentity(provider="google", provider_subject=subject)
        )
        user.email_validated = True
        db.session.add(user)
        db.session.commit()


@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_google_callback_returning_user_logs_in_without_new_rows(
    mock_authorize_access_token: mock.MagicMock, app: Flask, load_login_page
):
    """
    GIVEN a Users row with a linked google UserOAuthIdentity
    WHEN the callback's mocked token exchange returns matching sub/email
    THEN the existing user is logged in, redirected home, and no new
        Users/UserOAuthIdentity rows are created
    """
    mock_authorize_access_token.return_value = _build_mocked_token(
        subject=_EXISTING_SUBJECT, email=_EXISTING_EMAIL
    )
    _seed_existing_oauth_user(
        app,
        subject=_EXISTING_SUBJECT,
        email=_EXISTING_EMAIL,
        username=_EXISTING_USERNAME,
    )
    client, _ = load_login_page

    with app.app_context():
        assert Users.query.count() == 1
        assert UserOAuthIdentity.query.count() == 1

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].location == url_for(ROUTES.UTUBS.HOME)
    assert current_user.is_authenticated
    assert current_user.username == _EXISTING_USERNAME
    mock_authorize_access_token.assert_called_once()

    with app.app_context():
        assert Users.query.count() == 1
        assert UserOAuthIdentity.query.count() == 1


@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_google_callback_new_user_creates_account_and_logs_in(
    mock_authorize_access_token: mock.MagicMock, app: Flask, load_login_page
):
    """
    GIVEN no existing Users/UserOAuthIdentity row for the mocked subject/email
    WHEN the callback resolves the token exchange
    THEN exactly one new Users row and one new UserOAuthIdentity row are created
        in a single transaction, and the new user is logged in and redirected home
    """
    mock_authorize_access_token.return_value = _build_mocked_token(
        subject=_NEW_USER_SUBJECT, email=_NEW_USER_EMAIL, name=_NEW_USER_NAME
    )
    client, _ = load_login_page

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].location == url_for(ROUTES.UTUBS.HOME)
    assert current_user.is_authenticated
    assert current_user.email == _NEW_USER_EMAIL
    mock_authorize_access_token.assert_called_once()

    with app.app_context():
        assert Users.query.count() == 1
        assert UserOAuthIdentity.query.count() == 1
        created_identity = UserOAuthIdentity.query.filter_by(
            provider_subject=_NEW_USER_SUBJECT
        ).first()
        assert created_identity is not None
        assert created_identity.user.email == _NEW_USER_EMAIL


@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_google_callback_email_collision_renders_reject_page(
    mock_authorize_access_token: mock.MagicMock,
    app: Flask,
    register_first_user,
    load_login_page,
):
    """
    GIVEN a password-based Users row with no matching UserOAuthIdentity
    WHEN the callback's mocked userinfo returns that same email under a new subject
    THEN EmailAlreadyRegisteredError surfaces as the reject-page render (not a 500)
        and no new Users/UserOAuthIdentity rows are created
    """
    collision_email = valid_user_1[model_strs.EMAIL].lower()
    mock_authorize_access_token.return_value = _build_mocked_token(
        subject=_NEW_USER_SUBJECT, email=collision_email
    )
    client, _ = load_login_page

    with app.app_context():
        assert Users.query.count() == 1
        assert UserOAuthIdentity.query.count() == 0

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    assert _EMAIL_COLLISION_MESSAGE.encode() in response.data
    assert not current_user.is_authenticated
    mock_authorize_access_token.assert_called_once()

    with app.app_context():
        assert Users.query.count() == 1
        assert UserOAuthIdentity.query.count() == 0


@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_google_callback_consent_declined_short_circuits_without_token_exchange(
    mock_authorize_access_token: mock.MagicMock, app: Flask, load_login_page
):
    """
    GIVEN Google redirects back with `error=access_denied` and no `code`
    WHEN the callback is hit
    THEN the route short-circuits at the `parsed.error is not None` check without
        ever calling `authorize_access_token`, and the consent-declined reject page renders
    """
    client, _ = load_login_page

    with app.app_context():
        assert Users.query.count() == 0

    response = client.get(
        _callback_url(error="access_denied", state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    assert _CONSENT_DECLINED_MESSAGE.encode() in response.data
    mock_authorize_access_token.assert_not_called()

    with app.app_context():
        assert Users.query.count() == 0


@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_google_callback_token_exchange_failure_renders_generic_reject(
    mock_authorize_access_token: mock.MagicMock, app: Flask, load_login_page
):
    """
    GIVEN Authlib's token exchange raises OAuthError
    WHEN the callback is hit
    THEN the generic-failure reject page renders (a 200 render_template response,
        not a 400/500) and no new Users/UserOAuthIdentity rows are created
    """
    mock_authorize_access_token.side_effect = OAuthError("invalid_grant", "bad token")
    client, _ = load_login_page

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    assert _GENERIC_FAILURE_MESSAGE.encode() in response.data
    mock_authorize_access_token.assert_called_once()

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0


@mock.patch(_FIND_OR_CREATE_OAUTH_USER_TARGET)
@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_google_callback_unverified_email_renders_reject_without_resolving_user(
    mock_authorize_access_token: mock.MagicMock,
    mock_find_or_create_oauth_user: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN the mocked userinfo reports `email_verified: False`
    WHEN the callback is hit
    THEN the unverified-email reject page renders and `find_or_create_oauth_user`
        is never called
    """
    mock_authorize_access_token.return_value = _build_mocked_token(
        subject=_UNVERIFIED_SUBJECT, email=_UNVERIFIED_EMAIL, email_verified=False
    )
    client, _ = load_login_page

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    assert _UNVERIFIED_EMAIL_MESSAGE.encode() in response.data
    mock_find_or_create_oauth_user.assert_not_called()
    mock_authorize_access_token.assert_called_once()

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0


@mock.patch(_FIND_OR_CREATE_OAUTH_USER_TARGET)
@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_google_callback_missing_email_verified_renders_reject_without_resolving_user(
    mock_authorize_access_token: mock.MagicMock,
    mock_find_or_create_oauth_user: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN the mocked userinfo omits the `email_verified` claim entirely
    WHEN the callback is hit
    THEN the unverified-email reject page renders and `find_or_create_oauth_user`
        is never called, matching the explicit `email_verified: False` case
    """
    mock_authorize_access_token.return_value = _build_mocked_token(
        subject=_UNVERIFIED_SUBJECT, email=_UNVERIFIED_EMAIL, email_verified=None
    )
    client, _ = load_login_page

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    assert _UNVERIFIED_EMAIL_MESSAGE.encode() in response.data
    mock_find_or_create_oauth_user.assert_not_called()
    mock_authorize_access_token.assert_called_once()

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0


def test_google_callback_records_login_metrics_across_scenarios(
    metrics_enabled_app: Flask, provide_metrics_redis, load_login_page
):
    """
    GIVEN metrics enabled for the shared app (DD-31)
    WHEN the Google callback resolves a brand-new user, then that same user
        returning, then a separate email collision, run sequentially
    THEN LOGIN_SUCCESS records with method="google" after the new-user and
        returning-user scenarios, and LOGIN_FAILURE records with
        reason="oauth_email_collision" after the collision scenario
    """
    client, _ = load_login_page

    assert count_counter_keys(provide_metrics_redis, EventName.LOGIN_SUCCESS) == 0
    assert count_counter_keys(provide_metrics_redis, EventName.LOGIN_FAILURE) == 0

    # Scenario 1: brand-new user
    with mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET) as mock_authorize_access_token:
        mock_authorize_access_token.return_value = _build_mocked_token(
            subject=_METRICS_NEW_USER_SUBJECT, email=_METRICS_NEW_USER_EMAIL
        )
        response = client.get(
            _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
        )
        mock_authorize_access_token.assert_called_once()
    assert response.status_code == 200

    # New-user login records LOGIN_SUCCESS with method="google". The counter key
    # is a hash of (bucket_epoch, event, dims) collapsed via Redis INCR, so a
    # second google login with identical dims (same device_type from the same
    # test client) in the same time bucket increments the same key rather than
    # creating a second one.
    assert count_counter_keys(provide_metrics_redis, EventName.LOGIN_SUCCESS) == 1
    login_success_keys = find_counter_keys(
        provide_metrics_redis, EventName.LOGIN_SUCCESS
    )
    assert (
        parse_dims(login_success_keys[0])[_LOGIN_SUCCESS_METHOD_DIM_KEY]
        == _GOOGLE_METHOD_DIM_VALUE
    )

    client.get(url_for(ROUTES.USERS.LOGOUT))

    # Scenario 2: the same user returning
    with mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET) as mock_authorize_access_token:
        mock_authorize_access_token.return_value = _build_mocked_token(
            subject=_METRICS_NEW_USER_SUBJECT, email=_METRICS_NEW_USER_EMAIL
        )
        response = client.get(
            _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
        )
        mock_authorize_access_token.assert_called_once()
    assert response.status_code == 200

    assert count_counter_keys(provide_metrics_redis, EventName.LOGIN_SUCCESS) == 1
    login_success_keys = find_counter_keys(
        provide_metrics_redis, EventName.LOGIN_SUCCESS
    )
    assert (
        parse_dims(login_success_keys[0])[_LOGIN_SUCCESS_METHOD_DIM_KEY]
        == _GOOGLE_METHOD_DIM_VALUE
    )

    client.get(url_for(ROUTES.USERS.LOGOUT))

    # Scenario 3: email collision against a separate password-based user
    with metrics_enabled_app.app_context():
        collision_user = Users(
            username=_METRICS_COLLISION_USERNAME,
            email=_METRICS_COLLISION_EMAIL,
            plaintext_password=_METRICS_COLLISION_PASSWORD,
        )
        collision_user.email_validated = True
        db.session.add(collision_user)
        db.session.commit()

    assert count_counter_keys(provide_metrics_redis, EventName.LOGIN_FAILURE) == 0

    with mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET) as mock_authorize_access_token:
        mock_authorize_access_token.return_value = _build_mocked_token(
            subject=_METRICS_COLLISION_SUBJECT, email=_METRICS_COLLISION_EMAIL
        )
        response = client.get(
            _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
        )
        mock_authorize_access_token.assert_called_once()
    assert response.status_code == 200

    assert count_counter_keys(provide_metrics_redis, EventName.LOGIN_FAILURE) == 1
    login_failure_keys = find_counter_keys(
        provide_metrics_redis, EventName.LOGIN_FAILURE
    )
    assert (
        parse_dims(login_failure_keys[0])[_LOGIN_FAILURE_REASON_DIM_KEY]
        == "oauth_email_collision"
    )
