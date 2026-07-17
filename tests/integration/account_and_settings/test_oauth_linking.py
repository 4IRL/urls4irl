"""Integration tests for the settings-page account-linking endpoints (Phase 3
of the OAuth initiative):

- ``POST /users/<id>/oauth/link/<provider>`` — starts a link (password
  re-auth for password accounts, an OAuth proof round-trip for password-less
  accounts) via ``linking_service.initiate_settings_link``.
- ``GET /oauth/<provider>/link`` — the shared OAuth dance entry point for a
  pending link/proof intent, via ``linking_service.initiate_link_oauth_redirect``.
- ``DELETE /users/<id>/oauth/link/<provider>`` — disconnects a linked
  provider via ``linking_service.unlink_provider``.
- The authenticated branch of the shared provider callbacks
  (``google_service.handle_google_callback`` / ``github_service.handle_github_callback``
  → ``linking_service.handle_authenticated_oauth_callback``), which completes
  the link/proof dance and redirects back to Settings.

Authlib calls are mocked at the call sites used inside
``google_service.py``/``github_service.py``/``linking_service.py``, the same
convention as ``tests/integration/splash/test_oauth_google.py``.
"""

from __future__ import annotations

from typing import Generator, Tuple
from unittest import mock

from flask import Flask, redirect, url_for
from flask.testing import FlaskClient
import pytest

from backend import db
from backend.metrics.events import EventName
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.splash.constants import OAuthLinkErrorCodes
from backend.splash.services.oauth.constants import (
    LINK_INTENT_ACTION_LINK,
    LINK_INTENT_ACTION_PROOF,
    OAUTH_LINK_INTENT_SESSION_KEY,
)
from backend.utils.all_routes import OAUTH_ROUTES, ROUTES
from backend.utils.strings import model_strs
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.oauth_strs import (
    LINK_INVALID_PASSWORD_MESSAGE,
    LINK_PASSWORD_REQUIRED_MESSAGE,
    UNLINK_LAST_METHOD_MESSAGE,
)
from backend.utils.strings.user_strs import REDIRECT_URL
from tests.conftest import AjaxFlaskLoginClient
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
)
from tests.models_for_test import valid_user_1
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.account_and_support

_GOOGLE_AUTHORIZE_ACCESS_TOKEN_TARGET = (
    "backend.splash.services.oauth.google_service.oauth.google.authorize_access_token"
)
_GITHUB_AUTHORIZE_ACCESS_TOKEN_TARGET = (
    "backend.splash.services.oauth.github_service.oauth.github.authorize_access_token"
)
_GITHUB_GET_TARGET = "backend.splash.services.oauth.github_service.oauth.github.get"
_LINKING_GOOGLE_AUTHORIZE_REDIRECT_TARGET = (
    "backend.splash.services.oauth.linking_service.oauth.google.authorize_redirect"
)
_LINKING_GITHUB_AUTHORIZE_REDIRECT_TARGET = (
    "backend.splash.services.oauth.linking_service.oauth.github.authorize_redirect"
)

_FAKE_CODE = "fake-authorization-code"
_FAKE_STATE = "fake-state-value"
_FAKE_GITHUB_TOKEN = {"access_token": "fake-github-access-token"}
_MOCK_GOOGLE_CONSENT_URL = "https://accounts.google.com/o/oauth2/mock-consent"
_MOCK_GITHUB_CONSENT_URL = "https://github.com/login/oauth/mock-consent"

_OAUTH_ONLY_USERNAME = "settingslinkoauthonly"
_OAUTH_ONLY_EMAIL = "settingslinkoauthonly@example.com"
_OAUTH_ONLY_GOOGLE_SUBJECT = "sub_settings_link_oauth_only_google"

_OTHER_TAKEN_USERNAME = "settingslinkothertaken"
_OTHER_TAKEN_EMAIL = "settingslinkothertaken@example.com"
_OTHER_TAKEN_PASSWORD = "P@ssw0rdOtherTaken1234!"
_TAKEN_GITHUB_ID = 91_001

_NEW_GITHUB_ID = 91_002
_PROOF_PATH_GITHUB_ID = 91_003
_IDEMPOTENT_GITHUB_ID = 91_004


def _build_mocked_google_token(*, subject: str, email: str) -> dict:
    return {"userinfo": {"sub": subject, "email": email, "email_verified": True}}


def _build_github_user_payload(*, github_id: int, login: str) -> dict:
    return {"id": github_id, "login": login, "name": None, "email": None}


def _build_github_emails_payload(*, email: str) -> list[dict]:
    return [{"email": email, "primary": True, "verified": True, "visibility": "public"}]


def _mock_github_response(*, json_payload) -> mock.Mock:
    response = mock.Mock(status_code=200)
    response.json.return_value = json_payload
    return response


def _github_get_side_effect(*, github_id: int, login: str, email: str):
    user_response = _mock_github_response(
        json_payload=_build_github_user_payload(github_id=github_id, login=login)
    )
    emails_response = _mock_github_response(
        json_payload=_build_github_emails_payload(email=email)
    )

    def _side_effect(resource_path: str, **_kwargs):
        if resource_path == "user":
            return user_response
        if resource_path == "user/emails":
            return emails_response
        raise AssertionError(f"Unexpected GitHub resource path: {resource_path!r}")

    return _side_effect


def _seed_oauth_only_user(
    app: Flask, *, username: str, email: str, provider: str, subject: str
) -> None:
    with app.app_context():
        user = Users(username=username, email=email, plaintext_password=None)
        user.oauth_identities.append(
            UserOAuthIdentity(provider=provider, provider_subject=subject)
        )
        user.email_validated = True
        db.session.add(user)
        db.session.commit()


@pytest.fixture
def oauth_only_google_user_logged_in(
    app: Flask,
) -> Generator[Tuple[FlaskClient, str, Users, Flask], None, None]:
    """Seeds an email-validated, password-less user with a linked google
    identity, then logs them in via Flask-Login's test-client shortcut
    (mirrors ``tests/conftest.py:login_first_user_with_register``) — how the
    session was originally established is orthogonal to the settings-link
    endpoints under test here."""
    _seed_oauth_only_user(
        app,
        username=_OAUTH_ONLY_USERNAME,
        email=_OAUTH_ONLY_EMAIL,
        provider="google",
        subject=_OAUTH_ONLY_GOOGLE_SUBJECT,
    )

    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        user_to_login: Users = Users.query.filter_by(email=_OAUTH_ONLY_EMAIL).first()

    with app.test_client(user=user_to_login) as logged_in_client:
        logged_in_response = logged_in_client.get("/home")
        csrf_token_string = get_csrf_token(logged_in_response.get_data(), meta_tag=True)
        yield logged_in_client, csrf_token_string, user_to_login, app


# --- a-f: POST /users/<id>/oauth/link/<provider> validation branches -------


def test_link_password_user_correct_password_returns_redirect_and_stashes_intent(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN an authenticated password account with no linked github identity
    WHEN POST /users/<id>/oauth/link/github is submitted with the correct
        password
    THEN the response is 200 with redirectUrl == GET /oauth/github/link, and
        the session carries a link intent with action="link"
    """
    client, csrf_token, user, _ = login_first_user_with_register
    password = valid_user_1[model_strs.PASSWORD]

    response = client.post(
        url_for(ROUTES.USERS.OAUTH_LINK, user_id=user.id, provider="github"),
        json={"password": password},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.json[REDIRECT_URL] == url_for(OAUTH_ROUTES.LINK, provider="github")

    with client.session_transaction() as flask_session:
        intent = flask_session[OAUTH_LINK_INTENT_SESSION_KEY]
        assert intent["action"] == LINK_INTENT_ACTION_LINK
        assert intent["target_provider"] == "github"
        assert intent["user_id"] == user.id


def test_link_password_user_wrong_password_returns_400_and_stashes_no_intent(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN an authenticated password account
    WHEN POST /users/<id>/oauth/link/github is submitted with the WRONG
        password
    THEN the response is 400 with a field error and
        OAuthLinkErrorCodes.INVALID_PASSWORD, and no link intent is stashed
    """
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.post(
        url_for(ROUTES.USERS.OAUTH_LINK, user_id=user.id, provider="github"),
        json={"password": "TotallyWrongPassword!23"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    response_json = response.json
    assert response_json[STD_JSON.ERROR_CODE] == OAuthLinkErrorCodes.INVALID_PASSWORD
    assert response_json[STD_JSON.ERRORS]["password"] == [LINK_INVALID_PASSWORD_MESSAGE]

    with client.session_transaction() as flask_session:
        assert OAUTH_LINK_INTENT_SESSION_KEY not in flask_session


def test_link_password_user_missing_password_returns_400(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN an authenticated password account
    WHEN POST /users/<id>/oauth/link/github is submitted with no password
    THEN the response is 400 with LINK_PASSWORD_REQUIRED_MESSAGE
    """
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.post(
        url_for(ROUTES.USERS.OAUTH_LINK, user_id=user.id, provider="github"),
        json={},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    assert response.json[STD_JSON.MESSAGE] == LINK_PASSWORD_REQUIRED_MESSAGE


def test_link_provider_already_linked_returns_400(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN an authenticated account with a google identity already linked
    WHEN POST /users/<id>/oauth/link/google is submitted
    THEN the response is 400 with OAuthLinkErrorCodes.ALREADY_LINKED and the
        message names the provider's display name
    """
    client, csrf_token, user, app = login_first_user_with_register
    password = valid_user_1[model_strs.PASSWORD]

    with app.app_context():
        identity = UserOAuthIdentity(
            provider="google", provider_subject="already_linked_subject"
        )
        identity.user_id = user.id
        db.session.add(identity)
        db.session.commit()

    response = client.post(
        url_for(ROUTES.USERS.OAUTH_LINK, user_id=user.id, provider="google"),
        json={"password": password},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    response_json = response.json
    assert response_json[STD_JSON.ERROR_CODE] == OAuthLinkErrorCodes.ALREADY_LINKED
    assert "Google" in response_json[STD_JSON.MESSAGE]


def test_link_user_id_mismatch_returns_403(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN an authenticated user
    WHEN POST /users/<other_id>/oauth/link/github targets a different user_id
    THEN the response is 403 LINK_FORBIDDEN_MESSAGE
    """
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.post(
        url_for(ROUTES.USERS.OAUTH_LINK, user_id=user.id + 999, provider="github"),
        json={"password": valid_user_1[model_strs.PASSWORD]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403


def test_link_unknown_provider_returns_404(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN an authenticated user
    WHEN POST /users/<id>/oauth/link/gitlab targets an unsupported provider
    THEN the response is 404 with OAuthLinkErrorCodes.PROVIDER_NOT_CONFIGURED
    """
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.post(
        url_for(ROUTES.USERS.OAUTH_LINK, user_id=user.id, provider="gitlab"),
        json={"password": valid_user_1[model_strs.PASSWORD]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 404
    assert (
        response.json[STD_JSON.ERROR_CODE]
        == OAuthLinkErrorCodes.PROVIDER_NOT_CONFIGURED
    )


def test_link_oauth_only_user_proof_flow_targets_existing_provider(
    oauth_only_google_user_logged_in: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN an authenticated password-less user with only a google identity
    WHEN POST /users/<id>/oauth/link/github is submitted with no password
    THEN the response is 200 with redirectUrl == GET /oauth/google/link (the
        proof provider), and the intent's action is "proof"
    """
    client, csrf_token, user, _ = oauth_only_google_user_logged_in

    response = client.post(
        url_for(ROUTES.USERS.OAUTH_LINK, user_id=user.id, provider="github"),
        json={},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.json[REDIRECT_URL] == url_for(OAUTH_ROUTES.LINK, provider="google")

    with client.session_transaction() as flask_session:
        intent = flask_session[OAUTH_LINK_INTENT_SESSION_KEY]
        assert intent["action"] == LINK_INTENT_ACTION_PROOF
        assert intent["target_provider"] == "github"
        assert intent["proof_provider"] == "google"


# --- h: GET /oauth/<provider>/link ------------------------------------------


def test_oauth_link_redirect_with_valid_intent_targets_provider_consent(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a stashed link intent targeting github
    WHEN GET /oauth/github/link is hit (mocked authorize_redirect)
    THEN the route responds 302 and the redirect_uri argument passed to
        authorize_redirect matches the GitHub callback URL
    """
    client, csrf_token, user, _ = login_first_user_with_register
    password = valid_user_1[model_strs.PASSWORD]
    client.post(
        url_for(ROUTES.USERS.OAUTH_LINK, user_id=user.id, provider="github"),
        json={"password": password},
        headers={"X-CSRFToken": csrf_token},
    )

    with mock.patch(
        _LINKING_GITHUB_AUTHORIZE_REDIRECT_TARGET
    ) as mock_authorize_redirect:

        def _echo_redirect_uri(redirect_uri: str):
            return redirect(f"{_MOCK_GITHUB_CONSENT_URL}?redirect_uri={redirect_uri}")

        mock_authorize_redirect.side_effect = _echo_redirect_uri
        response = client.get(url_for(OAUTH_ROUTES.LINK, provider="github"))

    assert response.status_code == 302
    mock_authorize_redirect.assert_called_once()
    expected_redirect_uri = url_for(OAUTH_ROUTES.GITHUB_CALLBACK, _external=True)
    assert expected_redirect_uri in response.location


def test_oauth_link_redirect_with_no_intent_redirects_to_settings(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN no stashed link intent
    WHEN GET /oauth/github/link is hit directly
    THEN the route responds 302 back to /settings
    """
    client, _, _, _ = login_first_user_with_register

    response = client.get(url_for(OAUTH_ROUTES.LINK, provider="github"))

    assert response.status_code == 302
    assert response.location == url_for(ROUTES.USERS.SETTINGS)


def test_oauth_link_redirect_with_mismatched_provider_redirects_and_clears_intent(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a stashed link intent targeting github
    WHEN GET /oauth/google/link is hit (a different provider than the intent)
    THEN the route responds 302 back to /settings and the intent is cleared
    """
    client, csrf_token, user, _ = login_first_user_with_register
    password = valid_user_1[model_strs.PASSWORD]
    client.post(
        url_for(ROUTES.USERS.OAUTH_LINK, user_id=user.id, provider="github"),
        json={"password": password},
        headers={"X-CSRFToken": csrf_token},
    )

    response = client.get(url_for(OAUTH_ROUTES.LINK, provider="google"))

    assert response.status_code == 302
    assert response.location == url_for(ROUTES.USERS.SETTINGS)
    with client.session_transaction() as flask_session:
        assert OAUTH_LINK_INTENT_SESSION_KEY not in flask_session


# --- i-m: full authenticated-callback dances --------------------------------


def test_settings_link_full_happy_path_password_user(
    metrics_enabled_app: Flask,
    provide_metrics_redis,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN an authenticated password account
    WHEN POST link github (correct password) -> GET /oauth/github/link
        (mocked authorize_redirect) -> the authenticated github callback
        resolves a NEW github subject
    THEN the response redirects to /settings?linked=github, a
        UserOAuthIdentity row is created for the user, and
        OAUTH_IDENTITY_LINKED (provider=github) is recorded
    """
    client, csrf_token, user, app = login_first_user_with_register
    password = valid_user_1[model_strs.PASSWORD]

    link_response = client.post(
        url_for(ROUTES.USERS.OAUTH_LINK, user_id=user.id, provider="github"),
        json={"password": password},
        headers={"X-CSRFToken": csrf_token},
    )
    assert link_response.status_code == 200

    with mock.patch(
        _LINKING_GITHUB_AUTHORIZE_REDIRECT_TARGET
    ) as mock_authorize_redirect:
        mock_authorize_redirect.return_value = redirect(_MOCK_GITHUB_CONSENT_URL)
        redirect_dance_response = client.get(
            url_for(OAUTH_ROUTES.LINK, provider="github")
        )
    assert redirect_dance_response.status_code == 302

    with (
        mock.patch(_GITHUB_AUTHORIZE_ACCESS_TOKEN_TARGET) as mock_token,
        mock.patch(_GITHUB_GET_TARGET) as mock_github_get,
    ):
        mock_token.return_value = _FAKE_GITHUB_TOKEN
        mock_github_get.side_effect = _github_get_side_effect(
            github_id=_NEW_GITHUB_ID,
            login="newlinkedgithub",
            email="newlinkedgithub@example.com",
        )
        callback_response = client.get(
            url_for(OAUTH_ROUTES.GITHUB_CALLBACK, code=_FAKE_CODE, state=_FAKE_STATE)
        )

    assert callback_response.status_code == 302
    assert callback_response.location == url_for(ROUTES.USERS.SETTINGS, linked="github")

    with app.app_context():
        identity = UserOAuthIdentity.query.filter_by(
            user_id=user.id, provider="github"
        ).first()
        assert identity is not None
        assert identity.provider_subject == str(_NEW_GITHUB_ID)

    assert (
        count_counter_keys(provide_metrics_redis, EventName.OAUTH_IDENTITY_LINKED) == 1
    )
    linked_keys = find_counter_keys(
        provide_metrics_redis, EventName.OAUTH_IDENTITY_LINKED
    )
    assert parse_dims(linked_keys[0])["provider"] == "github"


def test_settings_link_full_oauth_only_proof_path(
    oauth_only_google_user_logged_in: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN an authenticated password-less user with only a google identity
    WHEN POST link github -> GET /oauth/google/link (proof) -> authenticated
        google callback with the user's EXISTING google subject (upgrading
        the intent) -> GET /oauth/github/link -> authenticated github
        callback with a NEW subject
    THEN the final response redirects to /settings?linked=github and a github
        UserOAuthIdentity row is created for the user
    """
    client, csrf_token, user, app = oauth_only_google_user_logged_in

    link_response = client.post(
        url_for(ROUTES.USERS.OAUTH_LINK, user_id=user.id, provider="github"),
        json={},
        headers={"X-CSRFToken": csrf_token},
    )
    assert link_response.status_code == 200
    assert link_response.json[REDIRECT_URL] == url_for(
        OAUTH_ROUTES.LINK, provider="google"
    )

    with mock.patch(
        _LINKING_GOOGLE_AUTHORIZE_REDIRECT_TARGET
    ) as mock_authorize_redirect:
        mock_authorize_redirect.return_value = redirect(_MOCK_GOOGLE_CONSENT_URL)
        proof_redirect_response = client.get(
            url_for(OAUTH_ROUTES.LINK, provider="google")
        )
    assert proof_redirect_response.status_code == 302

    with mock.patch(_GOOGLE_AUTHORIZE_ACCESS_TOKEN_TARGET) as mock_token:
        mock_token.return_value = _build_mocked_google_token(
            subject=_OAUTH_ONLY_GOOGLE_SUBJECT, email=_OAUTH_ONLY_EMAIL
        )
        proof_callback_response = client.get(
            url_for(OAUTH_ROUTES.GOOGLE_CALLBACK, code=_FAKE_CODE, state=_FAKE_STATE)
        )
    assert proof_callback_response.status_code == 302
    assert proof_callback_response.location == url_for(
        OAUTH_ROUTES.LINK, provider="github"
    )

    with client.session_transaction() as flask_session:
        intent = flask_session[OAUTH_LINK_INTENT_SESSION_KEY]
        assert intent["action"] == LINK_INTENT_ACTION_LINK
        assert intent["target_provider"] == "github"

    with mock.patch(_LINKING_GITHUB_AUTHORIZE_REDIRECT_TARGET) as mock_github_redirect:
        mock_github_redirect.return_value = redirect(_MOCK_GITHUB_CONSENT_URL)
        github_redirect_response = client.get(
            url_for(OAUTH_ROUTES.LINK, provider="github")
        )
    assert github_redirect_response.status_code == 302

    with (
        mock.patch(_GITHUB_AUTHORIZE_ACCESS_TOKEN_TARGET) as mock_github_token,
        mock.patch(_GITHUB_GET_TARGET) as mock_github_get,
    ):
        mock_github_token.return_value = _FAKE_GITHUB_TOKEN
        mock_github_get.side_effect = _github_get_side_effect(
            github_id=_PROOF_PATH_GITHUB_ID,
            login="proofpathgithub",
            email=_OAUTH_ONLY_EMAIL,
        )
        github_callback_response = client.get(
            url_for(OAUTH_ROUTES.GITHUB_CALLBACK, code=_FAKE_CODE, state=_FAKE_STATE)
        )

    assert github_callback_response.status_code == 302
    assert github_callback_response.location == url_for(
        ROUTES.USERS.SETTINGS, linked="github"
    )

    with app.app_context():
        identity = UserOAuthIdentity.query.filter_by(
            user_id=user.id, provider="github"
        ).first()
        assert identity is not None
        assert identity.provider_subject == str(_PROOF_PATH_GITHUB_ID)


def test_settings_link_proof_mismatch_redirects_with_error(
    oauth_only_google_user_logged_in: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a stashed "proof" intent expecting the user's EXISTING google
        subject
    WHEN the authenticated google callback resolves a DIFFERENT google
        subject
    THEN the response redirects to /settings?link_error=proof_mismatch, the
        intent is cleared, and no identity row is inserted
    """
    client, csrf_token, user, app = oauth_only_google_user_logged_in

    client.post(
        url_for(ROUTES.USERS.OAUTH_LINK, user_id=user.id, provider="github"),
        json={},
        headers={"X-CSRFToken": csrf_token},
    )
    with mock.patch(
        _LINKING_GOOGLE_AUTHORIZE_REDIRECT_TARGET
    ) as mock_authorize_redirect:
        mock_authorize_redirect.return_value = redirect(_MOCK_GOOGLE_CONSENT_URL)
        client.get(url_for(OAUTH_ROUTES.LINK, provider="google"))

    with mock.patch(_GOOGLE_AUTHORIZE_ACCESS_TOKEN_TARGET) as mock_token:
        mock_token.return_value = _build_mocked_google_token(
            subject="a_different_unlinked_google_subject", email=_OAUTH_ONLY_EMAIL
        )
        response = client.get(
            url_for(OAUTH_ROUTES.GOOGLE_CALLBACK, code=_FAKE_CODE, state=_FAKE_STATE)
        )

    assert response.status_code == 302
    assert response.location == url_for(
        ROUTES.USERS.SETTINGS, link_error="proof_mismatch"
    )

    with client.session_transaction() as flask_session:
        assert OAUTH_LINK_INTENT_SESSION_KEY not in flask_session

    with app.app_context():
        assert (
            UserOAuthIdentity.query.filter_by(
                user_id=user.id, provider="github"
            ).first()
            is None
        )


def test_authenticated_callback_without_intent_redirects_home(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN an authenticated session with no pending link intent
    WHEN GET /oauth/github/callback is hit directly
    THEN the response redirects home (mirrors the removed
        @no_authenticated_users_allowed behavior)
    """
    client, _, _, _ = login_first_user_with_register

    response = client.get(
        url_for(OAUTH_ROUTES.GITHUB_CALLBACK, code=_FAKE_CODE, state=_FAKE_STATE)
    )

    assert response.status_code == 302
    assert response.location == url_for(ROUTES.UTUBS.HOME)


def test_settings_link_github_subject_already_taken_returns_error(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the github subject the authenticated user is about to link already
        belongs to a DIFFERENT user
    WHEN the authenticated github callback resolves that subject
    THEN the response redirects to /settings?link_error=subject_taken and no
        new identity row is created for the current user
    """
    client, csrf_token, user, app = login_first_user_with_register
    password = valid_user_1[model_strs.PASSWORD]

    with app.app_context():
        other_user = Users(
            username=_OTHER_TAKEN_USERNAME,
            email=_OTHER_TAKEN_EMAIL,
            plaintext_password=_OTHER_TAKEN_PASSWORD,
        )
        other_user.email_validated = True
        other_user.oauth_identities.append(
            UserOAuthIdentity(provider="github", provider_subject=str(_TAKEN_GITHUB_ID))
        )
        db.session.add(other_user)
        db.session.commit()

    client.post(
        url_for(ROUTES.USERS.OAUTH_LINK, user_id=user.id, provider="github"),
        json={"password": password},
        headers={"X-CSRFToken": csrf_token},
    )
    with mock.patch(
        _LINKING_GITHUB_AUTHORIZE_REDIRECT_TARGET
    ) as mock_authorize_redirect:
        mock_authorize_redirect.return_value = redirect(_MOCK_GITHUB_CONSENT_URL)
        client.get(url_for(OAUTH_ROUTES.LINK, provider="github"))

    with (
        mock.patch(_GITHUB_AUTHORIZE_ACCESS_TOKEN_TARGET) as mock_token,
        mock.patch(_GITHUB_GET_TARGET) as mock_github_get,
    ):
        mock_token.return_value = _FAKE_GITHUB_TOKEN
        mock_github_get.side_effect = _github_get_side_effect(
            github_id=_TAKEN_GITHUB_ID,
            login="takensubjectgithub",
            email="whoever@example.com",
        )
        response = client.get(
            url_for(OAUTH_ROUTES.GITHUB_CALLBACK, code=_FAKE_CODE, state=_FAKE_STATE)
        )

    assert response.status_code == 302
    assert response.location == url_for(
        ROUTES.USERS.SETTINGS, link_error="subject_taken"
    )

    with app.app_context():
        assert (
            UserOAuthIdentity.query.filter_by(
                user_id=user.id, provider="github"
            ).first()
            is None
        )


def test_authenticated_link_callback_idempotent_for_already_linked_subject(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a stashed link intent targeting github, and a github identity for
        that exact (provider, subject) ALREADY linked to this same user
        (e.g. linked concurrently in another tab)
    WHEN the authenticated github callback resolves that same subject
    THEN the response redirects to /settings?linked=github (idempotent
        success) and exactly one identity row exists — no duplicate is
        inserted
    """
    client, csrf_token, user, app = login_first_user_with_register
    password = valid_user_1[model_strs.PASSWORD]

    link_response = client.post(
        url_for(ROUTES.USERS.OAUTH_LINK, user_id=user.id, provider="github"),
        json={"password": password},
        headers={"X-CSRFToken": csrf_token},
    )
    assert link_response.status_code == 200

    with app.app_context():
        identity = UserOAuthIdentity(
            provider="github", provider_subject=str(_IDEMPOTENT_GITHUB_ID)
        )
        identity.user_id = user.id
        db.session.add(identity)
        db.session.commit()

    with mock.patch(
        _LINKING_GITHUB_AUTHORIZE_REDIRECT_TARGET
    ) as mock_authorize_redirect:
        mock_authorize_redirect.return_value = redirect(_MOCK_GITHUB_CONSENT_URL)
        redirect_response = client.get(url_for(OAUTH_ROUTES.LINK, provider="github"))
    assert redirect_response.status_code == 302

    with (
        mock.patch(_GITHUB_AUTHORIZE_ACCESS_TOKEN_TARGET) as mock_token,
        mock.patch(_GITHUB_GET_TARGET) as mock_github_get,
    ):
        mock_token.return_value = _FAKE_GITHUB_TOKEN
        mock_github_get.side_effect = _github_get_side_effect(
            github_id=_IDEMPOTENT_GITHUB_ID,
            login="idempotentgithub",
            email="idempotentgithub@example.com",
        )
        callback_response = client.get(
            url_for(OAUTH_ROUTES.GITHUB_CALLBACK, code=_FAKE_CODE, state=_FAKE_STATE)
        )

    assert callback_response.status_code == 302
    assert callback_response.location == url_for(ROUTES.USERS.SETTINGS, linked="github")

    with app.app_context():
        assert (
            UserOAuthIdentity.query.filter_by(
                user_id=user.id, provider="github"
            ).count()
            == 1
        )


# --- n-p: DELETE /users/<id>/oauth/link/<provider> --------------------------


def test_unlink_password_user_with_linked_github_succeeds(
    metrics_enabled_app: Flask,
    provide_metrics_redis,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN an authenticated password account with a linked github identity
    WHEN DELETE /users/<id>/oauth/link/github is submitted
    THEN the response is 200 with a message naming "GitHub", the identity row
        is deleted, and OAUTH_IDENTITY_UNLINKED (provider=github) is recorded
    """
    client, csrf_token, user, app = login_first_user_with_register
    with app.app_context():
        identity = UserOAuthIdentity(
            provider="github", provider_subject="unlink_subject"
        )
        identity.user_id = user.id
        db.session.add(identity)
        db.session.commit()

    response = client.delete(
        url_for(ROUTES.USERS.OAUTH_UNLINK, user_id=user.id, provider="github"),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert "GitHub" in response.json[STD_JSON.MESSAGE]

    with app.app_context():
        assert (
            UserOAuthIdentity.query.filter_by(
                user_id=user.id, provider="github"
            ).first()
            is None
        )

    assert (
        count_counter_keys(provide_metrics_redis, EventName.OAUTH_IDENTITY_UNLINKED)
        == 1
    )
    unlinked_keys = find_counter_keys(
        provide_metrics_redis, EventName.OAUTH_IDENTITY_UNLINKED
    )
    assert parse_dims(unlinked_keys[0])["provider"] == "github"


def test_unlink_provider_not_linked_returns_404(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """DELETE for a provider with no linked identity returns 404 NOT_LINKED."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.delete(
        url_for(ROUTES.USERS.OAUTH_UNLINK, user_id=user.id, provider="github"),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 404
    assert response.json[STD_JSON.ERROR_CODE] == OAuthLinkErrorCodes.NOT_LINKED


def test_unlink_unknown_provider_returns_404(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """DELETE for an unsupported provider key returns 404
    PROVIDER_NOT_CONFIGURED."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.delete(
        url_for(ROUTES.USERS.OAUTH_UNLINK, user_id=user.id, provider="gitlab"),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 404
    assert (
        response.json[STD_JSON.ERROR_CODE]
        == OAuthLinkErrorCodes.PROVIDER_NOT_CONFIGURED
    )


def test_unlink_user_id_mismatch_returns_403(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """DELETE targeting a different user_id than the current session returns
    403."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.delete(
        url_for(ROUTES.USERS.OAUTH_UNLINK, user_id=user.id + 999, provider="github"),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403


def test_unlink_oauth_only_user_last_identity_blocked(
    oauth_only_google_user_logged_in: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a password-less user with ONLY a google identity
    WHEN DELETE /users/<id>/oauth/link/google is submitted
    THEN the response is 403 UNLINK_LAST_METHOD_MESSAGE and the row remains
    """
    client, csrf_token, user, app = oauth_only_google_user_logged_in

    response = client.delete(
        url_for(ROUTES.USERS.OAUTH_UNLINK, user_id=user.id, provider="google"),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    assert response.json[STD_JSON.MESSAGE] == UNLINK_LAST_METHOD_MESSAGE

    with app.app_context():
        assert (
            UserOAuthIdentity.query.filter_by(
                user_id=user.id, provider="google"
            ).first()
            is not None
        )


def test_unlink_oauth_only_user_with_two_identities_then_last_blocked(
    oauth_only_google_user_logged_in: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a password-less user with google+github identities
    WHEN DELETE github succeeds
    THEN a subsequent DELETE google (now the last remaining identity) is
        blocked with 403 UNLINK_LAST_METHOD_MESSAGE
    """
    client, csrf_token, user, app = oauth_only_google_user_logged_in
    with app.app_context():
        identity = UserOAuthIdentity(
            provider="github", provider_subject="second_identity_subject"
        )
        identity.user_id = user.id
        db.session.add(identity)
        db.session.commit()

    first_response = client.delete(
        url_for(ROUTES.USERS.OAUTH_UNLINK, user_id=user.id, provider="github"),
        headers={"X-CSRFToken": csrf_token},
    )
    assert first_response.status_code == 200

    second_response = client.delete(
        url_for(ROUTES.USERS.OAUTH_UNLINK, user_id=user.id, provider="google"),
        headers={"X-CSRFToken": csrf_token},
    )
    assert second_response.status_code == 403
    assert second_response.json[STD_JSON.MESSAGE] == UNLINK_LAST_METHOD_MESSAGE


def test_unlink_password_user_single_oauth_identity_succeeds(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a password account with a single linked google identity
    WHEN DELETE /users/<id>/oauth/link/google is submitted
    THEN the response is 200 — the password remains a valid sign-in method,
        so the last-method guard does not apply
    """
    client, csrf_token, user, app = login_first_user_with_register
    with app.app_context():
        identity = UserOAuthIdentity(
            provider="google", provider_subject="password_user_google_subject"
        )
        identity.user_id = user.id
        db.session.add(identity)
        db.session.commit()

    response = client.delete(
        url_for(ROUTES.USERS.OAUTH_UNLINK, user_id=user.id, provider="google"),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
