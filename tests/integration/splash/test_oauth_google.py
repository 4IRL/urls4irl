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
from flask import Flask, redirect, url_for
from flask_login import current_user
import pytest
from redis import Redis

from backend import db
from backend.metrics.events import EventName
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.splash.services.user_login import (
    _LOGIN_FAILURE_REASON_OAUTH_CONSENT_DECLINED,
    _LOGIN_FAILURE_REASON_OAUTH_EMAIL_COLLISION,
    _LOGIN_FAILURE_REASON_OAUTH_GENERIC_FAILURE,
    _LOGIN_FAILURE_REASON_OAUTH_UNVERIFIED_EMAIL,
)
from backend.testing.fake_oauth_provider import fake_oauth
from backend.utils.all_routes import OAUTH_ROUTES, ROUTES
from backend.utils.strings import model_strs
from backend.utils.strings.oauth_strs import (
    CONSENT_DECLINED_MESSAGE as _CONSENT_DECLINED_MESSAGE,
    EMAIL_COLLISION_MESSAGE as _EMAIL_COLLISION_MESSAGE,
    GENERIC_FAILURE_MESSAGE as _GENERIC_FAILURE_MESSAGE,
    UNVERIFIED_EMAIL_MESSAGE as _UNVERIFIED_EMAIL_MESSAGE,
)
from backend.utils.strings.utub_strs import UTUB_ID_QUERY_PARAM
from tests.conftest import TEST_GOOGLE_OAUTH_CLIENT_ID, TEST_GOOGLE_OAUTH_CLIENT_SECRET
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
_AUTHORIZE_REDIRECT_TARGET = (
    "backend.splash.services.oauth.google_service.oauth.google.authorize_redirect"
)
_FIND_OR_CREATE_OAUTH_USER_TARGET = (
    "backend.splash.services.oauth.google_service.find_or_create_oauth_user"
)

_FAKE_CODE = "fake-authorization-code"
_FAKE_STATE = "fake-state-value"
_FAKE_OAUTH_PROVIDER_SECRET_KEY = "fake-oauth-provider-test-secret-key"
_WRONG_CLIENT_SECRET = "wrong-client-secret"

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

_NEXT_TARGET_UTUB_NAME = "OAuth Next Target"
_UNAUTHORIZED_UTUB_ID = 999_999

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


def _assert_single_login_failure_reason(
    metrics_redis: Redis, expected_reason: str
) -> None:
    """Asserts exactly one LOGIN_FAILURE counter key exists and carries
    `reason=expected_reason`, matching the assertion shape already used by
    `test_google_callback_records_login_metrics_across_scenarios`'s
    email-collision scenario."""
    assert count_counter_keys(metrics_redis, EventName.LOGIN_FAILURE) == 1
    login_failure_keys = find_counter_keys(metrics_redis, EventName.LOGIN_FAILURE)
    assert (
        parse_dims(login_failure_keys[0])[_LOGIN_FAILURE_REASON_DIM_KEY]
        == expected_reason
    )


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


def _seed_utub_membership(app: Flask, *, user_email: str, utub_name: str) -> int:
    """Creates a UTub with the given user as its sole (creator) member,
    matching `tests/integration/utubs/conftest.py`'s membership-seeding
    pattern, and returns the new UTub's id."""
    with app.app_context():
        user = Users.query.filter_by(email=user_email).first()
        new_utub = Utubs(name=utub_name, utub_creator=user.id, utub_description="")
        creator_to_utub = Utub_Members(member_role=Member_Role.CREATOR)
        creator_to_utub.to_user = user
        new_utub.members.append(creator_to_utub)
        db.session.add(new_utub)
        db.session.commit()
        return new_utub.id


def _build_fake_oauth_provider_app() -> Flask:
    """Mounts only the fake OAuth provider blueprint on a throwaway Flask app.

    `token()` reads just `SECRET_KEY`, `GOOGLE_OAUTH_CLIENT_ID`, and
    `GOOGLE_OAUTH_CLIENT_SECRET` off `current_app.config`, so a full
    `create_app()` boot is unnecessary. The shared `app` fixture from
    `tests/conftest.py` never registers this blueprint since it is built with
    `UI_TESTING=False` — `backend/testing/fake_oauth_provider.py` is only
    wired in for Selenium's `ConfigTestUI` (see `backend/__init__.py`).
    """
    fake_oauth_app = Flask(__name__)
    fake_oauth_app.config["SECRET_KEY"] = _FAKE_OAUTH_PROVIDER_SECRET_KEY
    fake_oauth_app.config["GOOGLE_OAUTH_CLIENT_ID"] = TEST_GOOGLE_OAUTH_CLIENT_ID
    fake_oauth_app.config["GOOGLE_OAUTH_CLIENT_SECRET"] = (
        TEST_GOOGLE_OAUTH_CLIENT_SECRET
    )
    fake_oauth_app.register_blueprint(fake_oauth)
    return fake_oauth_app


def test_fake_oauth_token_rejects_wrong_client_secret():
    """
    GIVEN the fake OAuth provider's `/fake-oauth/token` endpoint configured
        with the real test client_id/client_secret pair
    WHEN a POST supplies the correct client_id but a wrong client_secret via
        HTTP Basic auth
    THEN the endpoint rejects with 401 and {"error": "invalid_client"} — the
        `hmac.compare_digest` mismatch path this hardening protects, not just
        a missing-credentials shortcut
    """
    fake_oauth_client = _build_fake_oauth_provider_app().test_client()

    response = fake_oauth_client.post(
        "/fake-oauth/token",
        data={"code": "irrelevant-code"},
        auth=(TEST_GOOGLE_OAUTH_CLIENT_ID, _WRONG_CLIENT_SECRET),
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid_client"}


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
@mock.patch(_AUTHORIZE_REDIRECT_TARGET)
def test_google_login_preserves_next_query_param_through_callback(
    mock_authorize_redirect: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN a Users row with a linked google UserOAuthIdentity and membership in
        a UTub
    WHEN `GET /oauth/google/login` is hit with a `next` query param pointing at
        that UTub, and the callback subsequently completes successfully
    THEN the user is redirected to the originally requested UTub page instead
        of the default home page, mirroring password login's `next` handling
    """
    mock_authorize_redirect.return_value = redirect(
        "https://accounts.google.com/o/oauth2/mock-consent"
    )
    mock_authorize_access_token.return_value = _build_mocked_token(
        subject=_EXISTING_SUBJECT, email=_EXISTING_EMAIL
    )
    _seed_existing_oauth_user(
        app,
        subject=_EXISTING_SUBJECT,
        email=_EXISTING_EMAIL,
        username=_EXISTING_USERNAME,
    )
    utub_id = _seed_utub_membership(
        app, user_email=_EXISTING_EMAIL, utub_name=_NEXT_TARGET_UTUB_NAME
    )
    client, _ = load_login_page

    expected_next = f"{url_for(ROUTES.UTUBS.HOME)}?{UTUB_ID_QUERY_PARAM}={utub_id}"
    login_response = client.get(url_for(OAUTH_ROUTES.GOOGLE_LOGIN, next=expected_next))
    assert login_response.status_code == 302
    mock_authorize_redirect.assert_called_once()

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].location == expected_next
    assert current_user.is_authenticated
    mock_authorize_access_token.assert_called_once()


@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
@mock.patch(_AUTHORIZE_REDIRECT_TARGET)
def test_google_login_invalid_next_query_param_falls_back_to_home(
    mock_authorize_redirect: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN a Users row with a linked google UserOAuthIdentity
    WHEN `GET /oauth/google/login` is hit with a `next` query param targeting a
        UTub the user is not a member of, and the callback subsequently
        completes successfully
    THEN the user is redirected to the default home page rather than the
        rejected `next` target
    """
    mock_authorize_redirect.return_value = redirect(
        "https://accounts.google.com/o/oauth2/mock-consent"
    )
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

    unauthorized_next = (
        f"{url_for(ROUTES.UTUBS.HOME)}?{UTUB_ID_QUERY_PARAM}={_UNAUTHORIZED_UTUB_ID}"
    )
    login_response = client.get(
        url_for(OAUTH_ROUTES.GOOGLE_LOGIN, next=unauthorized_next)
    )
    assert login_response.status_code == 302
    mock_authorize_redirect.assert_called_once()

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].location == url_for(ROUTES.UTUBS.HOME)
    assert current_user.is_authenticated
    mock_authorize_access_token.assert_called_once()


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

    _assert_single_login_failure_reason(
        provide_metrics_redis, _LOGIN_FAILURE_REASON_OAUTH_EMAIL_COLLISION
    )


def test_google_callback_consent_declined_records_login_failure_metric(
    metrics_enabled_app: Flask, provide_metrics_redis, load_login_page
):
    """
    GIVEN metrics enabled for the shared app
    WHEN the callback is hit with `error=access_denied` (declined consent)
    THEN LOGIN_FAILURE records once with reason="oauth_consent_declined"
    """
    client, _ = load_login_page
    assert count_counter_keys(provide_metrics_redis, EventName.LOGIN_FAILURE) == 0

    response = client.get(
        _callback_url(error="access_denied", state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    _assert_single_login_failure_reason(
        provide_metrics_redis, _LOGIN_FAILURE_REASON_OAUTH_CONSENT_DECLINED
    )


@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_google_callback_token_exchange_failure_records_login_failure_metric(
    mock_authorize_access_token: mock.MagicMock,
    metrics_enabled_app: Flask,
    provide_metrics_redis,
    load_login_page,
):
    """
    GIVEN metrics enabled for the shared app
    WHEN Authlib's token exchange raises OAuthError
    THEN LOGIN_FAILURE records once with reason="oauth_generic_failure"
    """
    mock_authorize_access_token.side_effect = OAuthError("invalid_grant", "bad token")
    client, _ = load_login_page
    assert count_counter_keys(provide_metrics_redis, EventName.LOGIN_FAILURE) == 0

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    mock_authorize_access_token.assert_called_once()
    _assert_single_login_failure_reason(
        provide_metrics_redis, _LOGIN_FAILURE_REASON_OAUTH_GENERIC_FAILURE
    )


@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_google_callback_unverified_email_records_login_failure_metric(
    mock_authorize_access_token: mock.MagicMock,
    metrics_enabled_app: Flask,
    provide_metrics_redis,
    load_login_page,
):
    """
    GIVEN metrics enabled for the shared app
    WHEN the mocked userinfo reports `email_verified: False`
    THEN LOGIN_FAILURE records once with reason="oauth_unverified_email"
    """
    mock_authorize_access_token.return_value = _build_mocked_token(
        subject=_UNVERIFIED_SUBJECT, email=_UNVERIFIED_EMAIL, email_verified=False
    )
    client, _ = load_login_page
    assert count_counter_keys(provide_metrics_redis, EventName.LOGIN_FAILURE) == 0

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    mock_authorize_access_token.assert_called_once()
    _assert_single_login_failure_reason(
        provide_metrics_redis, _LOGIN_FAILURE_REASON_OAUTH_UNVERIFIED_EMAIL
    )


@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_google_callback_missing_claims_records_login_failure_metric(
    mock_authorize_access_token: mock.MagicMock,
    metrics_enabled_app: Flask,
    provide_metrics_redis,
    load_login_page,
):
    """
    GIVEN metrics enabled for the shared app
    WHEN the mocked userinfo has `email_verified: True` but omits both the
        `sub` and `email` OIDC claims
    THEN LOGIN_FAILURE records once with reason="oauth_generic_failure"
    """
    mock_authorize_access_token.return_value = {"userinfo": {"email_verified": True}}
    client, _ = load_login_page
    assert count_counter_keys(provide_metrics_redis, EventName.LOGIN_FAILURE) == 0

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    mock_authorize_access_token.assert_called_once()
    _assert_single_login_failure_reason(
        provide_metrics_redis, _LOGIN_FAILURE_REASON_OAUTH_GENERIC_FAILURE
    )
