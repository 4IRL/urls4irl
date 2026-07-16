"""Integration tests for the GitHub OAuth login/callback flow.

GitHub is plain OAuth2 with no OIDC layer, so where the Google callback reads
parsed `userinfo` claims off the exchanged token, this one makes two
resource calls: `GET user` (account payload; `id` is the stable subject,
`login` the preferred-username seed) and `GET user/emails` (the account's
email list; the address marked both `primary` and `verified` is the one
trusted for account resolution). Authlib's token exchange
(`oauth.github.authorize_access_token`) and `oauth.github.get` are mocked at
the call sites used inside
`backend/splash/services/oauth/github_service.py` — the same
`unittest.mock.patch`-as-decorator convention used by `test_oauth_google.py`.
`oauth.github` itself is registered for every test run via
`tests/conftest.py`'s `build_app` fixture (dummy credentials), so no
per-test Authlib client setup is needed.
"""

from __future__ import annotations

from typing import Any, Callable
from unittest import mock
from urllib.parse import parse_qs, urlencode, urlparse

from authlib.integrations.base_client.errors import OAuthError
from flask import Flask, redirect, url_for
from flask_login import current_user
from pydantic import BaseModel, ValidationError
import pytest
from redis import Redis
from werkzeug import Response as WerkzeugResponse

from backend import db
from backend.metrics.events import EventName
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.splash.constants import (
    LOGIN_FAILURE_REASON_OAUTH_CONSENT_DECLINED,
    LOGIN_FAILURE_REASON_OAUTH_EMAIL_COLLISION,
    LOGIN_FAILURE_REASON_OAUTH_GENERIC_FAILURE,
    LOGIN_FAILURE_REASON_OAUTH_UNVERIFIED_EMAIL,
    OAuthErrorCodes,
)
from backend.testing.fake_oauth_provider import fake_oauth
from backend.utils.all_routes import OAUTH_ROUTES, ROUTES
from backend.utils.strings import model_strs
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.oauth_strs import (
    CONSENT_DECLINED_MESSAGE as _CONSENT_DECLINED_MESSAGE,
    EMAIL_COLLISION_MESSAGE as _EMAIL_COLLISION_MESSAGE,
    GENERIC_FAILURE_MESSAGE as _GENERIC_FAILURE_MESSAGE,
    GITHUB_INVALID_CALLBACK_QUERY_MESSAGE as _GITHUB_INVALID_CALLBACK_QUERY_MESSAGE,
    GITHUB_UNVERIFIED_EMAIL_MESSAGE as _GITHUB_UNVERIFIED_EMAIL_MESSAGE,
)
from backend.utils.strings.utub_strs import UTUB_ID_QUERY_PARAM
from tests.conftest import TEST_GITHUB_OAUTH_CLIENT_ID, TEST_GITHUB_OAUTH_CLIENT_SECRET
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
)
from tests.models_for_test import valid_user_1

pytestmark = pytest.mark.splash

_AUTHORIZE_ACCESS_TOKEN_TARGET = (
    "backend.splash.services.oauth.github_service.oauth.github.authorize_access_token"
)
_AUTHORIZE_REDIRECT_TARGET = (
    "backend.splash.services.oauth.github_service.oauth.github.authorize_redirect"
)
_GITHUB_GET_TARGET = "backend.splash.services.oauth.github_service.oauth.github.get"
_FIND_OR_CREATE_OAUTH_USER_TARGET = (
    "backend.splash.services.oauth.github_service.find_or_create_oauth_user"
)

# Mirrors the relative resource paths `github_service._fetch_github_json` is
# called with — kept as local constants (rather than imported) since the
# source module's are intentionally private.
_GITHUB_USER_RESOURCE = "user"
_GITHUB_USER_EMAILS_RESOURCE = "user/emails"

_FAKE_CODE = "fake-authorization-code"
_FAKE_STATE = "fake-state-value"
_FAKE_TOKEN = {"access_token": "fake-github-access-token"}
_FAKE_OAUTH_PROVIDER_SECRET_KEY = "fake-oauth-provider-test-secret-key"
_WRONG_CLIENT_SECRET = "wrong-client-secret"
_MOCK_CONSENT_REDIRECT_URL = "https://github.com/login/oauth/mock-consent"

_EXISTING_GITHUB_ID = 10_001
_EXISTING_SUBJECT = str(_EXISTING_GITHUB_ID)
_EXISTING_EMAIL = "existinggithubuser@example.com"
_EXISTING_USERNAME = "existinggithubuser"
_EXISTING_LOGIN = "existinggithubuser"

_NEW_USER_GITHUB_ID = 20_002
_NEW_USER_SUBJECT = str(_NEW_USER_GITHUB_ID)
_NEW_USER_EMAIL = "newgithubuser@example.com"
_NEW_USER_LOGIN = "newgithubuser"
_NEW_USER_NAME = "New GitHub User"

_UNVERIFIED_GITHUB_ID = 30_003
_UNVERIFIED_LOGIN = "unverifiedgithubuser"
_UNVERIFIED_EMAIL = "unverifiedgithubuser@example.com"

_MISSING_ID_LOGIN = "missingidgithubuser"
_MISSING_ID_EMAIL = "missingidgithubuser@example.com"

_METRICS_NEW_USER_GITHUB_ID = 40_004
_METRICS_NEW_USER_SUBJECT = str(_METRICS_NEW_USER_GITHUB_ID)
_METRICS_NEW_USER_LOGIN = "metricsnewghuser"
_METRICS_NEW_USER_EMAIL = "metricsnewghuser@example.com"
_METRICS_COLLISION_USERNAME = "metricscollisionghuser"
_METRICS_COLLISION_EMAIL = "metricscollisionghuser@example.com"
_METRICS_COLLISION_PASSWORD = "P@ssword123!"
_METRICS_COLLISION_GITHUB_ID = 50_005
_METRICS_UNVERIFIED_GITHUB_ID = 60_006
_METRICS_UNVERIFIED_LOGIN = "metricsunverifiedghuser"
_METRICS_UNVERIFIED_EMAIL = "metricsunverifiedghuser@example.com"
_METRICS_MISSING_ID_LOGIN = "metricsmissingidghuser"
_METRICS_MISSING_ID_EMAIL = "metricsmissingidghuser@example.com"

_MULTI_PROVIDER_GOOGLE_SUBJECT = "sub_multi_provider_google"
_MULTI_PROVIDER_GITHUB_ID = 70_007
_MULTI_PROVIDER_GITHUB_SUBJECT = str(_MULTI_PROVIDER_GITHUB_ID)
_MULTI_PROVIDER_USERNAME = "multiprovideruser"
_MULTI_PROVIDER_LOGIN = "multiprovideruser"
_MULTI_PROVIDER_EMAIL = "multiprovideruser@example.com"

_NEXT_TARGET_UTUB_NAME = "OAuth Next Target"
_UNAUTHORIZED_UTUB_ID = 999_999

_LOGIN_SUCCESS_METHOD_DIM_KEY = "method"
_LOGIN_FAILURE_REASON_DIM_KEY = "reason"
_GITHUB_METHOD_DIM_VALUE = "github"


def _build_github_user_payload(
    *, github_id: int | None, login: str | None = None, name: str | None = None
) -> dict[str, Any]:
    """Builds the dict shape GitHub's `GET user` resource returns, matching
    the fields `handle_github_callback` reads (`id`, `login`, `name`).
    `github_id=None` omits the `id` key entirely (rather than setting it to
    `None`), matching a real payload that never carried the field."""
    payload: dict[str, Any] = {"login": login, "name": name, "email": None}
    if github_id is not None:
        payload["id"] = github_id
    return payload


def _build_github_emails_payload(
    *, email: str, primary: bool = True, verified: bool = True
) -> list[dict[str, Any]]:
    """Builds the list shape GitHub's `GET user/emails` resource returns."""
    return [
        {
            "email": email,
            "primary": primary,
            "verified": verified,
            "visibility": "public",
        }
    ]


def _mock_github_response(
    *, status_code: int = 200, json_payload: Any = None
) -> mock.Mock:
    """Builds a `requests.Response`-shaped mock matching the surface
    `_fetch_github_json` reads off `oauth.github.get(...)`'s return value:
    `.status_code` and a `.json()` call."""
    response = mock.Mock(status_code=status_code)
    response.json.return_value = json_payload
    return response


def _build_github_get_side_effect(
    *, user_response: mock.Mock, emails_response: mock.Mock
) -> Callable[..., mock.Mock]:
    """Builds the `side_effect` for the mocked `oauth.github.get`, dispatching
    on the relative resource path (the call's first positional arg) the same
    way Authlib's real client resolves it against `api_base_url`."""

    def _side_effect(resource_path: str, **_kwargs: Any) -> mock.Mock:
        if resource_path == _GITHUB_USER_RESOURCE:
            return user_response
        if resource_path == _GITHUB_USER_EMAILS_RESOURCE:
            return emails_response
        raise AssertionError(f"Unexpected GitHub resource path: {resource_path!r}")

    return _side_effect


def _default_github_get_side_effect(
    *, github_id: int | None, login: str, email: str, name: str | None = None
) -> Callable[..., mock.Mock]:
    """Convenience wrapper for the common case: a 200 `/user` payload and a
    single primary+verified `/user/emails` entry."""
    return _build_github_get_side_effect(
        user_response=_mock_github_response(
            json_payload=_build_github_user_payload(
                github_id=github_id, login=login, name=name
            )
        ),
        emails_response=_mock_github_response(
            json_payload=_build_github_emails_payload(email=email)
        ),
    )


def _callback_url(**query_args: str) -> str:
    return url_for(OAUTH_ROUTES.GITHUB_CALLBACK, **query_args)


def _build_real_validation_error() -> ValidationError:
    """Builds a genuine `pydantic.ValidationError` by validating bad data against
    a throwaway schema. `GitHubOAuthCallbackQuerySchema`'s fields are all
    unconstrained `str | None`, so no real query string can fail it — this
    stand-in error is used to exercise the `except ValidationError` branch in
    `parse_query_args` directly."""

    class _StrictIntSchema(BaseModel):
        value: int

    try:
        _StrictIntSchema.model_validate({"value": "not-an-int"})
    except ValidationError as validation_error:
        return validation_error
    raise AssertionError("expected ValidationError to be raised")


def _assert_single_login_failure_reason(
    metrics_redis: Redis, expected_reason: str
) -> None:
    """Asserts exactly one LOGIN_FAILURE counter key exists and carries
    `reason=expected_reason`, matching the assertion shape already used by
    `test_oauth_google.py`."""
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
    linked github `UserOAuthIdentity`, matching `test_oauth_google.py`'s
    `_seed_existing_oauth_user` pattern."""
    with app.app_context():
        user = Users(username=username, email=email, plaintext_password=None)
        user.oauth_identities.append(
            UserOAuthIdentity(provider="github", provider_subject=subject)
        )
        user.email_validated = True
        db.session.add(user)
        db.session.commit()


def _seed_utub_membership(app: Flask, *, user_email: str, utub_name: str) -> int:
    """Creates a UTub with the given user as its sole (creator) member,
    matching `test_oauth_google.py`'s `_seed_utub_membership` pattern, and
    returns the new UTub's id."""
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

    `github_token()` reads just `SECRET_KEY`, `GITHUB_OAUTH_CLIENT_ID`, and
    `GITHUB_OAUTH_CLIENT_SECRET` off `current_app.config`, so a full
    `create_app()` boot is unnecessary. The shared `app` fixture from
    `tests/conftest.py` never registers this blueprint since it is built with
    `UI_TESTING=False` — `backend/testing/fake_oauth_provider.py` is only
    wired in for Selenium's `ConfigTestUI` (see `backend/__init__.py`).
    Mirrors `test_oauth_google.py`'s `_build_fake_oauth_provider_app`.
    """
    fake_oauth_app = Flask(__name__)
    fake_oauth_app.config["SECRET_KEY"] = _FAKE_OAUTH_PROVIDER_SECRET_KEY
    fake_oauth_app.config["GITHUB_OAUTH_CLIENT_ID"] = TEST_GITHUB_OAUTH_CLIENT_ID
    fake_oauth_app.config["GITHUB_OAUTH_CLIENT_SECRET"] = (
        TEST_GITHUB_OAUTH_CLIENT_SECRET
    )
    fake_oauth_app.register_blueprint(fake_oauth)
    return fake_oauth_app


def test_fake_github_oauth_token_rejects_wrong_client_secret():
    """
    GIVEN the fake OAuth provider's `/fake-oauth/github/token` endpoint
        configured with the real test client_id/client_secret pair
    WHEN a POST supplies the correct client_id but a wrong client_secret via
        HTTP Basic auth
    THEN the endpoint rejects with 401 and {"error": "invalid_client"} — the
        `hmac.compare_digest` mismatch path this hardening protects, not just
        a missing-credentials shortcut. Mirrors
        `test_oauth_google.py::test_fake_oauth_token_rejects_wrong_client_secret`.
    """
    fake_oauth_client = _build_fake_oauth_provider_app().test_client()

    response = fake_oauth_client.post(
        "/fake-oauth/github/token",
        data={"code": "irrelevant-code"},
        auth=(TEST_GITHUB_OAUTH_CLIENT_ID, _WRONG_CLIENT_SECRET),
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid_client"}


@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
@mock.patch(_GITHUB_GET_TARGET)
def test_github_callback_returning_user_logs_in_without_new_rows(
    mock_github_get: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN a Users row with a linked github UserOAuthIdentity
    WHEN the callback's mocked token exchange and resource calls return
        matching id/email
    THEN the existing user is logged in, redirected home, and no new
        Users/UserOAuthIdentity rows are created
    """
    mock_authorize_access_token.return_value = _FAKE_TOKEN
    mock_github_get.side_effect = _default_github_get_side_effect(
        github_id=_EXISTING_GITHUB_ID, login=_EXISTING_LOGIN, email=_EXISTING_EMAIL
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
@mock.patch(_GITHUB_GET_TARGET)
def test_github_callback_new_user_creates_account_and_logs_in(
    mock_github_get: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN no existing Users/UserOAuthIdentity row for the mocked github id/email
    WHEN the callback resolves the token exchange and both GitHub resource calls
    THEN exactly one new Users row and one new UserOAuthIdentity row are created
        in a single transaction, the new user is logged in and redirected home,
        and the username is derived from the `login` field
    """
    mock_authorize_access_token.return_value = _FAKE_TOKEN
    mock_github_get.side_effect = _default_github_get_side_effect(
        github_id=_NEW_USER_GITHUB_ID,
        login=_NEW_USER_LOGIN,
        email=_NEW_USER_EMAIL,
        name=_NEW_USER_NAME,
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
    assert current_user.username == _NEW_USER_LOGIN
    mock_authorize_access_token.assert_called_once()

    with app.app_context():
        assert Users.query.count() == 1
        assert UserOAuthIdentity.query.count() == 1
        created_identity = UserOAuthIdentity.query.filter_by(
            provider_subject=_NEW_USER_SUBJECT
        ).first()
        assert created_identity is not None
        assert created_identity.user.email == _NEW_USER_EMAIL
        assert created_identity.user.username == _NEW_USER_LOGIN


@mock.patch(_AUTHORIZE_REDIRECT_TARGET)
def test_github_login_redirects_with_expected_callback_redirect_uri(
    mock_authorize_redirect: mock.MagicMock, load_login_page
):
    """
    GIVEN the GitHub OAuth client registered for the test app
    WHEN `GET /oauth/github/login` is hit directly, independent of the full
        consent/callback round trip
    THEN the route responds 302, and the `redirect_uri` argument
        `initiate_github_login` passes to `authorize_redirect` — echoed back
        into the mocked consent redirect's `Location` query string — matches
        `OAUTH_ROUTES.GITHUB_CALLBACK` built as an absolute URL
    """

    def _echo_redirect_uri(redirect_uri: str) -> WerkzeugResponse:
        return redirect(
            f"{_MOCK_CONSENT_REDIRECT_URL}?{urlencode({'redirect_uri': redirect_uri})}"
        )

    mock_authorize_redirect.side_effect = _echo_redirect_uri
    client, _ = load_login_page

    expected_redirect_uri = url_for(OAUTH_ROUTES.GITHUB_CALLBACK, _external=True)
    response = client.get(url_for(OAUTH_ROUTES.GITHUB_LOGIN))

    assert response.status_code == 302
    mock_authorize_redirect.assert_called_once()
    location_query_params = parse_qs(urlparse(response.location).query)
    assert location_query_params["redirect_uri"] == [expected_redirect_uri]


@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
@mock.patch(_GITHUB_GET_TARGET)
@mock.patch(_AUTHORIZE_REDIRECT_TARGET)
def test_github_login_preserves_next_query_param_through_callback(
    mock_authorize_redirect: mock.MagicMock,
    mock_github_get: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN a Users row with a linked github UserOAuthIdentity and membership in
        a UTub
    WHEN `GET /oauth/github/login` is hit with a `next` query param pointing at
        that UTub, and the callback subsequently completes successfully
    THEN the user is redirected to the originally requested UTub page instead
        of the default home page, mirroring password login's `next` handling
    """
    mock_authorize_redirect.return_value = redirect(_MOCK_CONSENT_REDIRECT_URL)
    mock_authorize_access_token.return_value = _FAKE_TOKEN
    mock_github_get.side_effect = _default_github_get_side_effect(
        github_id=_EXISTING_GITHUB_ID, login=_EXISTING_LOGIN, email=_EXISTING_EMAIL
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
    login_response = client.get(url_for(OAUTH_ROUTES.GITHUB_LOGIN, next=expected_next))
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
@mock.patch(_GITHUB_GET_TARGET)
@mock.patch(_AUTHORIZE_REDIRECT_TARGET)
def test_github_login_invalid_next_query_param_falls_back_to_home(
    mock_authorize_redirect: mock.MagicMock,
    mock_github_get: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN a Users row with a linked github UserOAuthIdentity
    WHEN `GET /oauth/github/login` is hit with a `next` query param targeting a
        UTub the user is not a member of, and the callback subsequently
        completes successfully
    THEN the user is redirected to the default home page rather than the
        rejected `next` target
    """
    mock_authorize_redirect.return_value = redirect(_MOCK_CONSENT_REDIRECT_URL)
    mock_authorize_access_token.return_value = _FAKE_TOKEN
    mock_github_get.side_effect = _default_github_get_side_effect(
        github_id=_EXISTING_GITHUB_ID, login=_EXISTING_LOGIN, email=_EXISTING_EMAIL
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
        url_for(OAUTH_ROUTES.GITHUB_LOGIN, next=unauthorized_next)
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
@mock.patch(_GITHUB_GET_TARGET)
def test_github_callback_email_collision_renders_reject_page(
    mock_github_get: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    app: Flask,
    register_first_user,
    load_login_page,
):
    """
    GIVEN a password-based Users row with no matching UserOAuthIdentity
    WHEN the callback's mocked userinfo returns that same email under a new
        github id
    THEN EmailAlreadyRegisteredError surfaces as the reject-page render (not a
        500) and no new Users/UserOAuthIdentity rows are created
    """
    collision_email = valid_user_1[model_strs.EMAIL].lower()
    mock_authorize_access_token.return_value = _FAKE_TOKEN
    mock_github_get.side_effect = _default_github_get_side_effect(
        github_id=_NEW_USER_GITHUB_ID, login=_NEW_USER_LOGIN, email=collision_email
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
@mock.patch(
    "backend.splash.services.oauth.github_service.GitHubOAuthCallbackQuerySchema.model_validate"
)
def test_github_callback_invalid_query_args_returns_400_error_response(
    mock_model_validate: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN `GitHubOAuthCallbackQuerySchema.model_validate` raises `ValidationError`
        (its real fields are all unconstrained `str | None`, so no genuine query
        string can trigger this — see `_build_real_validation_error`)
    WHEN the callback is hit
    THEN `parse_query_args` returns the 400 field-error envelope with
        `OAuthErrorCodes.INVALID_FORM_INPUT` and the GitHub-specific message,
        matching the schema declared in the route's `status_codes`
    """
    mock_model_validate.side_effect = _build_real_validation_error()
    client, _ = load_login_page

    response = client.get(_callback_url(code=_FAKE_CODE, state=_FAKE_STATE))

    assert response.status_code == 400
    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.ERROR_CODE] == OAuthErrorCodes.INVALID_FORM_INPUT
    assert response_json[STD_JSON.MESSAGE] == _GITHUB_INVALID_CALLBACK_QUERY_MESSAGE
    mock_authorize_access_token.assert_not_called()


@mock.patch("backend.splash.services.oauth.github_service.oauth", new=object())
def test_github_login_unconfigured_oauth_redirects_to_splash_without_crashing(
    load_login_page,
):
    """
    GIVEN `oauth.github` is unregistered (simulating a deployment with no
        GitHub OAuth credentials configured)
    WHEN `GET /oauth/github/login` is hit directly — e.g. a stale bookmark or
        a client that bypasses the hidden splash button
    THEN the route redirects to the splash page instead of raising
        `AttributeError` from Authlib's `OAuth.__getattr__`
    """
    client, _ = load_login_page

    response = client.get(url_for(OAUTH_ROUTES.GITHUB_LOGIN))

    assert response.status_code == 302
    assert response.location == url_for(ROUTES.SPLASH.SPLASH_PAGE)


@mock.patch("backend.splash.services.oauth.github_service.oauth", new=object())
def test_github_callback_unconfigured_oauth_renders_generic_reject_without_crashing(
    load_login_page,
):
    """
    GIVEN `oauth.github` is unregistered (simulating credentials removed
        mid-session, or a stale bookmarked callback URL)
    WHEN `GET /oauth/github/callback` is hit directly
    THEN the generic-failure reject page renders instead of raising
        `AttributeError` from Authlib's `OAuth.__getattr__`
    """
    client, _ = load_login_page

    response = client.get(_callback_url(code=_FAKE_CODE, state=_FAKE_STATE))

    assert response.status_code == 200
    assert _GENERIC_FAILURE_MESSAGE.encode() in response.data


@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_github_callback_consent_declined_short_circuits_without_token_exchange(
    mock_authorize_access_token: mock.MagicMock, app: Flask, load_login_page
):
    """
    GIVEN GitHub redirects back with `error=access_denied` and no `code`
    WHEN the callback is hit
    THEN the route short-circuits at the `parsed.error is not None` check
        without ever calling `authorize_access_token`, and the
        consent-declined reject page renders
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
def test_github_callback_token_exchange_failure_renders_generic_reject(
    mock_authorize_access_token: mock.MagicMock, app: Flask, load_login_page
):
    """
    GIVEN Authlib's token exchange raises OAuthError
    WHEN the callback is hit
    THEN the generic-failure reject page renders (a 200 render_template
        response, not a 400/500) and no new Users/UserOAuthIdentity rows are
        created
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
@mock.patch(_GITHUB_GET_TARGET)
def test_github_callback_unverified_primary_email_renders_reject_without_resolving_user(
    mock_github_get: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    mock_find_or_create_oauth_user: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN the mocked `/user/emails` response reports the primary address as
        unverified
    WHEN the callback is hit
    THEN the GitHub-specific unverified-email reject page renders and
        `find_or_create_oauth_user` is never called
    """
    mock_authorize_access_token.return_value = _FAKE_TOKEN
    mock_github_get.side_effect = _build_github_get_side_effect(
        user_response=_mock_github_response(
            json_payload=_build_github_user_payload(
                github_id=_UNVERIFIED_GITHUB_ID, login=_UNVERIFIED_LOGIN
            )
        ),
        emails_response=_mock_github_response(
            json_payload=_build_github_emails_payload(
                email=_UNVERIFIED_EMAIL, primary=True, verified=False
            )
        ),
    )
    client, _ = load_login_page

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    assert _GITHUB_UNVERIFIED_EMAIL_MESSAGE.encode() in response.data
    mock_find_or_create_oauth_user.assert_not_called()
    mock_authorize_access_token.assert_called_once()

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0


@mock.patch(_FIND_OR_CREATE_OAUTH_USER_TARGET)
@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
@mock.patch(_GITHUB_GET_TARGET)
def test_github_callback_verified_non_primary_email_renders_reject_without_resolving_user(
    mock_github_get: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    mock_find_or_create_oauth_user: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN the mocked `/user/emails` response has a verified address that is
        not marked primary, and no primary address at all
    WHEN the callback is hit
    THEN the GitHub-specific unverified-email reject page renders and
        `find_or_create_oauth_user` is never called — a verified-but-not-primary
        address is not trusted for account resolution
    """
    mock_authorize_access_token.return_value = _FAKE_TOKEN
    mock_github_get.side_effect = _build_github_get_side_effect(
        user_response=_mock_github_response(
            json_payload=_build_github_user_payload(
                github_id=_UNVERIFIED_GITHUB_ID, login=_UNVERIFIED_LOGIN
            )
        ),
        emails_response=_mock_github_response(
            json_payload=_build_github_emails_payload(
                email=_UNVERIFIED_EMAIL, primary=False, verified=True
            )
        ),
    )
    client, _ = load_login_page

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    assert _GITHUB_UNVERIFIED_EMAIL_MESSAGE.encode() in response.data
    mock_find_or_create_oauth_user.assert_not_called()
    mock_authorize_access_token.assert_called_once()

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0


@mock.patch(_FIND_OR_CREATE_OAUTH_USER_TARGET)
@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
@mock.patch(_GITHUB_GET_TARGET)
def test_github_callback_empty_email_list_renders_reject_without_resolving_user(
    mock_github_get: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    mock_find_or_create_oauth_user: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN the mocked `/user/emails` response is an empty list
    WHEN the callback is hit
    THEN the GitHub-specific unverified-email reject page renders and
        `find_or_create_oauth_user` is never called
    """
    mock_authorize_access_token.return_value = _FAKE_TOKEN
    mock_github_get.side_effect = _build_github_get_side_effect(
        user_response=_mock_github_response(
            json_payload=_build_github_user_payload(
                github_id=_UNVERIFIED_GITHUB_ID, login=_UNVERIFIED_LOGIN
            )
        ),
        emails_response=_mock_github_response(json_payload=[]),
    )
    client, _ = load_login_page

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    assert _GITHUB_UNVERIFIED_EMAIL_MESSAGE.encode() in response.data
    mock_find_or_create_oauth_user.assert_not_called()
    mock_authorize_access_token.assert_called_once()

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0


@mock.patch(_FIND_OR_CREATE_OAUTH_USER_TARGET)
@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
@mock.patch(_GITHUB_GET_TARGET)
def test_github_callback_user_resource_non_200_renders_generic_reject(
    mock_github_get: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    mock_find_or_create_oauth_user: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN the mocked `GET user` resource call returns a non-200 status
    WHEN the callback is hit
    THEN the generic-failure reject page renders and `find_or_create_oauth_user`
        is never called, and no new Users/UserOAuthIdentity rows are created
    """
    mock_authorize_access_token.return_value = _FAKE_TOKEN
    mock_github_get.side_effect = _build_github_get_side_effect(
        user_response=_mock_github_response(status_code=404, json_payload=None),
        emails_response=_mock_github_response(
            json_payload=_build_github_emails_payload(email=_UNVERIFIED_EMAIL)
        ),
    )
    client, _ = load_login_page

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    assert _GENERIC_FAILURE_MESSAGE.encode() in response.data
    mock_find_or_create_oauth_user.assert_not_called()
    mock_authorize_access_token.assert_called_once()

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0


@mock.patch(_FIND_OR_CREATE_OAUTH_USER_TARGET)
@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
@mock.patch(_GITHUB_GET_TARGET)
def test_github_callback_user_emails_resource_non_200_renders_generic_reject(
    mock_github_get: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    mock_find_or_create_oauth_user: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN the mocked `GET user` resource call succeeds but `GET user/emails`
        returns a non-200 status
    WHEN the callback is hit
    THEN the generic-failure reject page renders and `find_or_create_oauth_user`
        is never called, and no new Users/UserOAuthIdentity rows are created
    """
    mock_authorize_access_token.return_value = _FAKE_TOKEN
    mock_github_get.side_effect = _build_github_get_side_effect(
        user_response=_mock_github_response(
            json_payload=_build_github_user_payload(
                github_id=_UNVERIFIED_GITHUB_ID, login=_UNVERIFIED_LOGIN
            )
        ),
        emails_response=_mock_github_response(status_code=500, json_payload=None),
    )
    client, _ = load_login_page

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    assert _GENERIC_FAILURE_MESSAGE.encode() in response.data
    mock_find_or_create_oauth_user.assert_not_called()
    mock_authorize_access_token.assert_called_once()

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0


@mock.patch(_FIND_OR_CREATE_OAUTH_USER_TARGET)
@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
@mock.patch(_GITHUB_GET_TARGET)
def test_github_callback_user_emails_non_list_payload_renders_generic_reject(
    mock_github_get: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    mock_find_or_create_oauth_user: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN the mocked `GET user/emails` resource returns 200 but a JSON dict
        (not the expected list)
    WHEN the callback is hit
    THEN the generic-failure reject page renders and `find_or_create_oauth_user`
        is never called, and no new Users/UserOAuthIdentity rows are created
    """
    mock_authorize_access_token.return_value = _FAKE_TOKEN
    mock_github_get.side_effect = _build_github_get_side_effect(
        user_response=_mock_github_response(
            json_payload=_build_github_user_payload(
                github_id=_UNVERIFIED_GITHUB_ID, login=_UNVERIFIED_LOGIN
            )
        ),
        emails_response=_mock_github_response(json_payload={"message": "not a list"}),
    )
    client, _ = load_login_page

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    assert _GENERIC_FAILURE_MESSAGE.encode() in response.data
    mock_find_or_create_oauth_user.assert_not_called()
    mock_authorize_access_token.assert_called_once()

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0


@mock.patch(_FIND_OR_CREATE_OAUTH_USER_TARGET)
@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
@mock.patch(_GITHUB_GET_TARGET)
def test_github_callback_user_payload_missing_id_renders_generic_reject(
    mock_github_get: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    mock_find_or_create_oauth_user: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN a verified-primary `/user/emails` entry (so the callback reaches the
        `id` check) but the mocked `GET user` payload omits the `id` field
    WHEN the callback is hit
    THEN the generic-failure reject page renders and `find_or_create_oauth_user`
        is never called, and no new Users/UserOAuthIdentity rows are created
    """
    mock_authorize_access_token.return_value = _FAKE_TOKEN
    mock_github_get.side_effect = _build_github_get_side_effect(
        user_response=_mock_github_response(
            json_payload=_build_github_user_payload(
                github_id=None, login=_MISSING_ID_LOGIN
            )
        ),
        emails_response=_mock_github_response(
            json_payload=_build_github_emails_payload(email=_MISSING_ID_EMAIL)
        ),
    )
    client, _ = load_login_page

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    assert _GENERIC_FAILURE_MESSAGE.encode() in response.data
    mock_find_or_create_oauth_user.assert_not_called()
    mock_authorize_access_token.assert_called_once()

    with app.app_context():
        assert Users.query.count() == 0
        assert UserOAuthIdentity.query.count() == 0


@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
@mock.patch(_GITHUB_GET_TARGET)
def test_github_callback_logs_in_existing_multi_provider_user_without_new_rows(
    mock_github_get: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN a single Users row with BOTH a linked google UserOAuthIdentity and a
        linked github UserOAuthIdentity
    WHEN the callback resolves the token exchange and resource calls for the
        github subject
    THEN the same single user logs in, `Users.query.count() == 1`, and no new
        Users/UserOAuthIdentity rows are created
    """
    mock_authorize_access_token.return_value = _FAKE_TOKEN
    mock_github_get.side_effect = _default_github_get_side_effect(
        github_id=_MULTI_PROVIDER_GITHUB_ID,
        login=_MULTI_PROVIDER_LOGIN,
        email=_MULTI_PROVIDER_EMAIL,
    )

    with app.app_context():
        user = Users(
            username=_MULTI_PROVIDER_USERNAME,
            email=_MULTI_PROVIDER_EMAIL,
            plaintext_password=None,
        )
        user.oauth_identities.append(
            UserOAuthIdentity(
                provider="google", provider_subject=_MULTI_PROVIDER_GOOGLE_SUBJECT
            )
        )
        user.oauth_identities.append(
            UserOAuthIdentity(
                provider="github", provider_subject=_MULTI_PROVIDER_GITHUB_SUBJECT
            )
        )
        user.email_validated = True
        db.session.add(user)
        db.session.commit()

    client, _ = load_login_page

    with app.app_context():
        assert Users.query.count() == 1
        assert UserOAuthIdentity.query.count() == 2

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].location == url_for(ROUTES.UTUBS.HOME)
    assert current_user.is_authenticated
    assert current_user.username == _MULTI_PROVIDER_USERNAME
    mock_authorize_access_token.assert_called_once()

    with app.app_context():
        assert Users.query.count() == 1
        assert UserOAuthIdentity.query.count() == 2


def test_github_callback_records_login_metrics_across_scenarios(
    metrics_enabled_app: Flask, provide_metrics_redis, load_login_page
):
    """
    GIVEN metrics enabled for the shared app (DD-31)
    WHEN the GitHub callback resolves a brand-new user, then that same user
        returning, then a separate email collision, run sequentially
    THEN LOGIN_SUCCESS records with method="github" after the new-user and
        returning-user scenarios, and LOGIN_FAILURE records with
        reason="oauth_email_collision" after the collision scenario
    """
    client, _ = load_login_page

    assert count_counter_keys(provide_metrics_redis, EventName.LOGIN_SUCCESS) == 0
    assert count_counter_keys(provide_metrics_redis, EventName.LOGIN_FAILURE) == 0

    # Scenario 1: brand-new user
    with (
        mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET) as mock_authorize_access_token,
        mock.patch(_GITHUB_GET_TARGET) as mock_github_get,
    ):
        mock_authorize_access_token.return_value = _FAKE_TOKEN
        mock_github_get.side_effect = _default_github_get_side_effect(
            github_id=_METRICS_NEW_USER_GITHUB_ID,
            login=_METRICS_NEW_USER_LOGIN,
            email=_METRICS_NEW_USER_EMAIL,
        )
        response = client.get(
            _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
        )
        mock_authorize_access_token.assert_called_once()
    assert response.status_code == 200

    # New-user login records LOGIN_SUCCESS with method="github". The counter key
    # is a hash of (bucket_epoch, event, dims) collapsed via Redis INCR, so a
    # second github login with identical dims (same device_type from the same
    # test client) in the same time bucket increments the same key rather than
    # creating a second one.
    assert count_counter_keys(provide_metrics_redis, EventName.LOGIN_SUCCESS) == 1
    login_success_keys = find_counter_keys(
        provide_metrics_redis, EventName.LOGIN_SUCCESS
    )
    assert (
        parse_dims(login_success_keys[0])[_LOGIN_SUCCESS_METHOD_DIM_KEY]
        == _GITHUB_METHOD_DIM_VALUE
    )

    client.get(url_for(ROUTES.USERS.LOGOUT))

    # Scenario 2: the same user returning
    with (
        mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET) as mock_authorize_access_token,
        mock.patch(_GITHUB_GET_TARGET) as mock_github_get,
    ):
        mock_authorize_access_token.return_value = _FAKE_TOKEN
        mock_github_get.side_effect = _default_github_get_side_effect(
            github_id=_METRICS_NEW_USER_GITHUB_ID,
            login=_METRICS_NEW_USER_LOGIN,
            email=_METRICS_NEW_USER_EMAIL,
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
        == _GITHUB_METHOD_DIM_VALUE
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

    with (
        mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET) as mock_authorize_access_token,
        mock.patch(_GITHUB_GET_TARGET) as mock_github_get,
    ):
        mock_authorize_access_token.return_value = _FAKE_TOKEN
        mock_github_get.side_effect = _default_github_get_side_effect(
            github_id=_METRICS_COLLISION_GITHUB_ID,
            login=_METRICS_COLLISION_USERNAME,
            email=_METRICS_COLLISION_EMAIL,
        )
        response = client.get(
            _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
        )
        mock_authorize_access_token.assert_called_once()
    assert response.status_code == 200

    _assert_single_login_failure_reason(
        provide_metrics_redis, LOGIN_FAILURE_REASON_OAUTH_EMAIL_COLLISION
    )


def test_github_callback_consent_declined_records_login_failure_metric(
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
        provide_metrics_redis, LOGIN_FAILURE_REASON_OAUTH_CONSENT_DECLINED
    )


@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_github_callback_token_exchange_failure_records_login_failure_metric(
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
        provide_metrics_redis, LOGIN_FAILURE_REASON_OAUTH_GENERIC_FAILURE
    )


@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
@mock.patch(_GITHUB_GET_TARGET)
def test_github_callback_unverified_email_records_login_failure_metric(
    mock_github_get: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    metrics_enabled_app: Flask,
    provide_metrics_redis,
    load_login_page,
):
    """
    GIVEN metrics enabled for the shared app
    WHEN the mocked `/user/emails` response has no primary+verified address
    THEN LOGIN_FAILURE records once with reason="oauth_unverified_email"
    """
    mock_authorize_access_token.return_value = _FAKE_TOKEN
    mock_github_get.side_effect = _build_github_get_side_effect(
        user_response=_mock_github_response(
            json_payload=_build_github_user_payload(
                github_id=_METRICS_UNVERIFIED_GITHUB_ID, login=_METRICS_UNVERIFIED_LOGIN
            )
        ),
        emails_response=_mock_github_response(
            json_payload=_build_github_emails_payload(
                email=_METRICS_UNVERIFIED_EMAIL, primary=True, verified=False
            )
        ),
    )
    client, _ = load_login_page
    assert count_counter_keys(provide_metrics_redis, EventName.LOGIN_FAILURE) == 0

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    mock_authorize_access_token.assert_called_once()
    _assert_single_login_failure_reason(
        provide_metrics_redis, LOGIN_FAILURE_REASON_OAUTH_UNVERIFIED_EMAIL
    )


@mock.patch(_AUTHORIZE_ACCESS_TOKEN_TARGET)
@mock.patch(_GITHUB_GET_TARGET)
def test_github_callback_user_payload_missing_id_records_login_failure_metric(
    mock_github_get: mock.MagicMock,
    mock_authorize_access_token: mock.MagicMock,
    metrics_enabled_app: Flask,
    provide_metrics_redis,
    load_login_page,
):
    """
    GIVEN metrics enabled for the shared app
    WHEN the mocked `GET user` payload omits `id` (after a verified-primary
        email list, so the callback reaches the `id` check)
    THEN LOGIN_FAILURE records once with reason="oauth_generic_failure"
    """
    mock_authorize_access_token.return_value = _FAKE_TOKEN
    mock_github_get.side_effect = _build_github_get_side_effect(
        user_response=_mock_github_response(
            json_payload=_build_github_user_payload(
                github_id=None, login=_METRICS_MISSING_ID_LOGIN
            )
        ),
        emails_response=_mock_github_response(
            json_payload=_build_github_emails_payload(email=_METRICS_MISSING_ID_EMAIL)
        ),
    )
    client, _ = load_login_page
    assert count_counter_keys(provide_metrics_redis, EventName.LOGIN_FAILURE) == 0

    response = client.get(
        _callback_url(code=_FAKE_CODE, state=_FAKE_STATE), follow_redirects=True
    )

    assert response.status_code == 200
    mock_authorize_access_token.assert_called_once()
    _assert_single_login_failure_reason(
        provide_metrics_redis, LOGIN_FAILURE_REASON_OAUTH_GENERIC_FAILURE
    )
