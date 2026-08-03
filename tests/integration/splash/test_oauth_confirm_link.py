"""Integration tests for the collision confirm-link flow (Phase 3 of the
OAuth initiative).

An anonymous OAuth sign-in whose email collides with an existing local
account no longer renders a reject page — it stashes the pending provider
identity (`backend/splash/services/oauth/linking_service.py:stash_pending_collision_link`)
and redirects to `GET /oauth/link/confirm`. That page (or the paired
`POST /oauth/link/confirm`) completes the link:

- **Password accounts** re-authenticate with their password
  (`confirm_link_with_password`).
- **Password-less (OAuth-only) accounts** cannot re-auth locally, so the
  second proof is a normal sign-in with a provider already linked to the
  account — `complete_pending_collision_link` runs right after that sign-in
  succeeds.

Authlib's token exchange and, for GitHub, the two resource calls are mocked
at the call sites used inside `google_service.py`/`github_service.py`, the
same convention as `test_oauth_google.py`/`test_oauth_github.py`.
"""

from __future__ import annotations

from unittest import mock

from flask import Flask, url_for
from flask_login import current_user
import pytest

from backend import db
from backend.metrics.events import EventName
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.splash.constants import (
    LOGIN_FAILURE_REASON_BAD_PASSWORD,
    LoginErrorCodes,
    OAuthLinkErrorCodes,
)
from backend.splash.services.oauth.constants import (
    OAUTH_LINK_MAX_AGE_SECONDS,
    OAUTH_PENDING_LINK_SESSION_KEY,
)
from backend.utils.all_routes import OAUTH_ROUTES, ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.oauth_strs import (
    CONFIRM_LINK_EXPIRED_MESSAGE,
    CONFIRM_LINK_OAUTH_ONLY_PROMPT,
    CONFIRM_LINK_PASSWORD_PROMPT,
    LINK_INVALID_PASSWORD_MESSAGE,
)
from backend.utils.strings.user_strs import USER_FAILURE
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
)

pytestmark = pytest.mark.splash

_GOOGLE_AUTHORIZE_ACCESS_TOKEN_TARGET = (
    "backend.splash.services.oauth.google_service.oauth.google.authorize_access_token"
)
_GITHUB_AUTHORIZE_ACCESS_TOKEN_TARGET = (
    "backend.splash.services.oauth.github_service.oauth.github.authorize_access_token"
)
_GITHUB_GET_TARGET = "backend.splash.services.oauth.github_service.oauth.github.get"

_FAKE_CODE = "fake-authorization-code"
_FAKE_STATE = "fake-state-value"
_FAKE_GITHUB_TOKEN = {"access_token": "fake-github-access-token"}

_PASSWORD_OWNER_USERNAME = "confirmlinkpwowner"
_PASSWORD_OWNER_EMAIL = "confirmlinkpwowner@example.com"
_PASSWORD_OWNER_PASSWORD = "P@ssw0rdOwner1234!"

_SUSPENDED_OWNER_USERNAME = "confirmlinksuspowner"
_SUSPENDED_OWNER_EMAIL = "confirmlinksuspowner@example.com"
_SUSPENDED_OWNER_PASSWORD = "P@ssw0rdSuspended1234!"

_UNVALIDATED_OWNER_USERNAME = "confirmlinkunvalowner"
_UNVALIDATED_OWNER_EMAIL = "confirmlinkunvalowner@example.com"
_UNVALIDATED_OWNER_PASSWORD = "P@ssw0rdUnvalidated1234!"

_MISMATCH_OWNER_USERNAME = "confirmlinkmismatchowner"
_MISMATCH_OWNER_EMAIL = "confirmlinkmismatchowner@example.com"
_MISMATCH_OWNER_PASSWORD = "P@ssw0rdMismatch1234!"

_OTHER_USER_USERNAME = "confirmlinkotheruser"
_OTHER_USER_EMAIL = "confirmlinkotheruser@example.com"
_OTHER_USER_GOOGLE_SUBJECT = "sub_confirm_link_other_user_google"

_OAUTH_ONLY_OWNER_USERNAME = "confirmlinkoauthowner"
_OAUTH_ONLY_OWNER_EMAIL = "confirmlinkoauthowner@example.com"
_OAUTH_ONLY_OWNER_GOOGLE_SUBJECT = "sub_confirm_link_oauth_owner_google"

_NEW_GOOGLE_SUBJECT = "sub_confirm_link_new_google"
_NEW_GITHUB_ID = 88_001
_NEW_GITHUB_ID_FOR_MISMATCH = 88_002

_LOGIN_SUCCESS_METHOD_DIM_KEY = "method"
_LOGIN_FAILURE_REASON_DIM_KEY = "reason"
_OAUTH_IDENTITY_LINKED_PROVIDER_DIM_KEY = "provider"


def _build_mocked_google_token(
    *, subject: str, email: str, email_verified: bool | None = True
) -> dict:
    userinfo = {"sub": subject, "email": email}
    if email_verified is not None:
        userinfo["email_verified"] = email_verified
    return {"userinfo": userinfo}


def _google_callback_url(**query_args: str) -> str:
    return url_for(OAUTH_ROUTES.GOOGLE_CALLBACK, **query_args)


def _github_callback_url(**query_args: str) -> str:
    return url_for(OAUTH_ROUTES.GITHUB_CALLBACK, **query_args)


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


def _seed_password_user(
    app: Flask,
    *,
    username: str,
    email: str,
    password: str,
    email_validated: bool = True,
    is_suspended: bool = False,
) -> None:
    with app.app_context():
        user = Users(username=username, email=email, plaintext_password=password)
        user.email_validated = email_validated
        user.is_suspended = is_suspended
        db.session.add(user)
        db.session.commit()


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


def test_confirm_link_page_no_pending_stash_renders_expired_banner(load_login_page):
    """
    GIVEN no pending collision stash in the session
    WHEN GET /oauth/link/confirm is hit directly
    THEN the splash page renders with the generic-failure banner showing
        CONFIRM_LINK_EXPIRED_MESSAGE
    """
    client, _ = load_login_page

    response = client.get(url_for(OAUTH_ROUTES.CONFIRM_LINK_PAGE))

    assert response.status_code == 200
    assert CONFIRM_LINK_EXPIRED_MESSAGE.encode() in response.data


@mock.patch(_GOOGLE_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_confirm_link_password_account_full_flow_links_and_logs_in(
    mock_authorize_access_token: mock.MagicMock,
    app: Flask,
    metrics_enabled_app: Flask,
    provide_metrics_redis,
    load_login_page,
):
    """
    GIVEN a password-validated Users row
    WHEN a google sign-in collides with that email (stashing the pending
        identity), the confirm page is fetched, then POST /oauth/link/confirm
        is submitted with the CORRECT password
    THEN the response is 200 with redirect_url to home, a UserOAuthIdentity
        row is created for the owner/provider/subject, the user is logged in,
        and LOGIN_SUCCESS (method=google) + OAUTH_IDENTITY_LINKED
        (provider=google) are both recorded
    """
    _seed_password_user(
        app,
        username=_PASSWORD_OWNER_USERNAME,
        email=_PASSWORD_OWNER_EMAIL,
        password=_PASSWORD_OWNER_PASSWORD,
    )
    mock_authorize_access_token.return_value = _build_mocked_google_token(
        subject=_NEW_GOOGLE_SUBJECT, email=_PASSWORD_OWNER_EMAIL
    )
    client, csrf_token = load_login_page

    collision_response = client.get(
        _google_callback_url(code=_FAKE_CODE, state=_FAKE_STATE)
    )
    assert collision_response.status_code == 302
    assert collision_response.location == url_for(OAUTH_ROUTES.CONFIRM_LINK_PAGE)

    confirm_page_response = client.get(url_for(OAUTH_ROUTES.CONFIRM_LINK_PAGE))
    assert confirm_page_response.status_code == 200
    expected_prompt = CONFIRM_LINK_PASSWORD_PROMPT.format(
        email=_PASSWORD_OWNER_EMAIL, provider="Google"
    )
    assert expected_prompt.encode() in confirm_page_response.data
    assert b'id="ConfirmLinkPrompt"' in confirm_page_response.data

    post_response = client.post(
        url_for(OAUTH_ROUTES.CONFIRM_LINK),
        json={"password": _PASSWORD_OWNER_PASSWORD},
        headers={"X-CSRFToken": csrf_token},
    )

    assert post_response.status_code == 200
    assert post_response.json["redirectUrl"] == url_for(ROUTES.UTUBS.HOME)
    assert current_user.is_authenticated
    assert current_user.email == _PASSWORD_OWNER_EMAIL

    with app.app_context():
        identity = UserOAuthIdentity.query.filter_by(
            provider="google", provider_subject=_NEW_GOOGLE_SUBJECT
        ).first()
        assert identity is not None
        assert identity.user.email == _PASSWORD_OWNER_EMAIL

    assert count_counter_keys(provide_metrics_redis, EventName.LOGIN_SUCCESS) == 1
    login_success_keys = find_counter_keys(
        provide_metrics_redis, EventName.LOGIN_SUCCESS
    )
    assert parse_dims(login_success_keys[0])[_LOGIN_SUCCESS_METHOD_DIM_KEY] == "google"

    assert (
        count_counter_keys(provide_metrics_redis, EventName.OAUTH_IDENTITY_LINKED) == 1
    )
    linked_keys = find_counter_keys(
        provide_metrics_redis, EventName.OAUTH_IDENTITY_LINKED
    )
    assert (
        parse_dims(linked_keys[0])[_OAUTH_IDENTITY_LINKED_PROVIDER_DIM_KEY] == "google"
    )


@mock.patch(_GOOGLE_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_confirm_link_wrong_password_then_retry_with_correct_password_succeeds(
    mock_authorize_access_token: mock.MagicMock,
    app: Flask,
    metrics_enabled_app: Flask,
    provide_metrics_redis,
    load_login_page,
):
    """
    GIVEN a stashed pending collision link for a password account
    WHEN POST /oauth/link/confirm is submitted with the WRONG password
    THEN the response is 400 with field error LINK_INVALID_PASSWORD_MESSAGE,
        no identity row is created, the user is not logged in, and
        LOGIN_FAILURE (reason=bad_password) is recorded — but the pending
        stash remains usable: a second POST with the correct password
        succeeds
    """
    _seed_password_user(
        app,
        username=_PASSWORD_OWNER_USERNAME,
        email=_PASSWORD_OWNER_EMAIL,
        password=_PASSWORD_OWNER_PASSWORD,
    )
    mock_authorize_access_token.return_value = _build_mocked_google_token(
        subject=_NEW_GOOGLE_SUBJECT, email=_PASSWORD_OWNER_EMAIL
    )
    client, csrf_token = load_login_page
    client.get(_google_callback_url(code=_FAKE_CODE, state=_FAKE_STATE))

    wrong_response = client.post(
        url_for(OAUTH_ROUTES.CONFIRM_LINK),
        json={"password": "TotallyWrongPassword!23"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert wrong_response.status_code == 400
    wrong_json = wrong_response.json
    assert wrong_json[STD_JSON.ERROR_CODE] == OAuthLinkErrorCodes.INVALID_PASSWORD
    assert wrong_json[STD_JSON.ERRORS]["password"] == [LINK_INVALID_PASSWORD_MESSAGE]
    assert not current_user.is_authenticated

    with app.app_context():
        assert (
            UserOAuthIdentity.query.filter_by(
                provider_subject=_NEW_GOOGLE_SUBJECT
            ).first()
            is None
        )

    # Two distinct LOGIN_FAILURE dims combos are expected by this point: the
    # earlier collision GET recorded reason=oauth_email_collision, and this
    # wrong-password POST recorded a second, distinct reason=bad_password key.
    failure_keys = find_counter_keys(provide_metrics_redis, EventName.LOGIN_FAILURE)
    failure_reasons = {
        parse_dims(key)[_LOGIN_FAILURE_REASON_DIM_KEY] for key in failure_keys
    }
    assert LOGIN_FAILURE_REASON_BAD_PASSWORD in failure_reasons

    retry_response = client.post(
        url_for(OAUTH_ROUTES.CONFIRM_LINK),
        json={"password": _PASSWORD_OWNER_PASSWORD},
        headers={"X-CSRFToken": csrf_token},
    )

    assert retry_response.status_code == 200
    assert current_user.is_authenticated

    with app.app_context():
        assert (
            UserOAuthIdentity.query.filter_by(
                provider_subject=_NEW_GOOGLE_SUBJECT
            ).first()
            is not None
        )


def test_confirm_link_post_with_no_pending_stash_returns_expired_error(
    load_login_page,
):
    """
    GIVEN no pending collision stash in the session
    WHEN POST /oauth/link/confirm is submitted
    THEN the response is 400 with CONFIRM_LINK_EXPIRED_MESSAGE and
        error_code OAuthLinkErrorCodes.INTENT_INVALID
    """
    client, csrf_token = load_login_page

    response = client.post(
        url_for(OAUTH_ROUTES.CONFIRM_LINK),
        json={"password": "WhateverPassword123!"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    response_json = response.json
    assert response_json[STD_JSON.MESSAGE] == CONFIRM_LINK_EXPIRED_MESSAGE
    assert response_json[STD_JSON.ERROR_CODE] == OAuthLinkErrorCodes.INTENT_INVALID


@mock.patch(_GOOGLE_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_confirm_link_expired_pending_stash_rejected_on_get_and_post(
    mock_authorize_access_token: mock.MagicMock, app: Flask, load_login_page
):
    """
    GIVEN a pending collision stash whose issued_at is older than
        OAUTH_LINK_MAX_AGE_SECONDS (simulated via session_transaction)
    WHEN GET /oauth/link/confirm is hit
    THEN the expired banner renders
    WHEN POST /oauth/link/confirm is submitted with the correct password
    THEN the response is 400 with CONFIRM_LINK_EXPIRED_MESSAGE
    """
    _seed_password_user(
        app,
        username=_PASSWORD_OWNER_USERNAME,
        email=_PASSWORD_OWNER_EMAIL,
        password=_PASSWORD_OWNER_PASSWORD,
    )
    mock_authorize_access_token.return_value = _build_mocked_google_token(
        subject=_NEW_GOOGLE_SUBJECT, email=_PASSWORD_OWNER_EMAIL
    )
    client, csrf_token = load_login_page
    client.get(_google_callback_url(code=_FAKE_CODE, state=_FAKE_STATE))

    with client.session_transaction() as flask_session:
        pending = dict(flask_session[OAUTH_PENDING_LINK_SESSION_KEY])
        pending["issued_at"] = pending["issued_at"] - OAUTH_LINK_MAX_AGE_SECONDS - 1
        flask_session[OAUTH_PENDING_LINK_SESSION_KEY] = pending

    expired_page_response = client.get(url_for(OAUTH_ROUTES.CONFIRM_LINK_PAGE))
    assert expired_page_response.status_code == 200
    assert CONFIRM_LINK_EXPIRED_MESSAGE.encode() in expired_page_response.data

    expired_post_response = client.post(
        url_for(OAUTH_ROUTES.CONFIRM_LINK),
        json={"password": _PASSWORD_OWNER_PASSWORD},
        headers={"X-CSRFToken": csrf_token},
    )
    assert expired_post_response.status_code == 400
    expired_json = expired_post_response.json
    assert expired_json[STD_JSON.MESSAGE] == CONFIRM_LINK_EXPIRED_MESSAGE
    assert expired_json[STD_JSON.ERROR_CODE] == OAuthLinkErrorCodes.INTENT_INVALID


@mock.patch(_GOOGLE_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_confirm_link_suspended_owner_blocked(
    mock_authorize_access_token: mock.MagicMock, app: Flask, load_login_page
):
    """
    GIVEN the colliding email's owner account is suspended
    WHEN POST /oauth/link/confirm is submitted with the correct password
    THEN the response is 403 with USER_FAILURE.ACCOUNT_SUSPENDED, no identity
        row is created, and the user is not logged in
    """
    _seed_password_user(
        app,
        username=_SUSPENDED_OWNER_USERNAME,
        email=_SUSPENDED_OWNER_EMAIL,
        password=_SUSPENDED_OWNER_PASSWORD,
        is_suspended=True,
    )
    mock_authorize_access_token.return_value = _build_mocked_google_token(
        subject=_NEW_GOOGLE_SUBJECT, email=_SUSPENDED_OWNER_EMAIL
    )
    client, csrf_token = load_login_page
    client.get(_google_callback_url(code=_FAKE_CODE, state=_FAKE_STATE))

    response = client.post(
        url_for(OAUTH_ROUTES.CONFIRM_LINK),
        json={"password": _SUSPENDED_OWNER_PASSWORD},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    response_json = response.json
    assert response_json[STD_JSON.MESSAGE] == USER_FAILURE.ACCOUNT_SUSPENDED
    assert response_json[STD_JSON.ERROR_CODE] == LoginErrorCodes.ACCOUNT_SUSPENDED
    assert not current_user.is_authenticated

    with app.app_context():
        assert (
            UserOAuthIdentity.query.filter_by(
                provider_subject=_NEW_GOOGLE_SUBJECT
            ).first()
            is None
        )


@mock.patch(_GOOGLE_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_confirm_link_unvalidated_owner_blocked(
    mock_authorize_access_token: mock.MagicMock, app: Flask, load_login_page
):
    """
    GIVEN the colliding email's owner account has not validated its email
    WHEN POST /oauth/link/confirm is submitted with the correct password
    THEN the response is 401 with ACCOUNT_CREATED_EMAIL_NOT_VALIDATED and no
        identity row is inserted
    """
    _seed_password_user(
        app,
        username=_UNVALIDATED_OWNER_USERNAME,
        email=_UNVALIDATED_OWNER_EMAIL,
        password=_UNVALIDATED_OWNER_PASSWORD,
        email_validated=False,
    )
    mock_authorize_access_token.return_value = _build_mocked_google_token(
        subject=_NEW_GOOGLE_SUBJECT, email=_UNVALIDATED_OWNER_EMAIL
    )
    client, csrf_token = load_login_page
    client.get(_google_callback_url(code=_FAKE_CODE, state=_FAKE_STATE))

    response = client.post(
        url_for(OAUTH_ROUTES.CONFIRM_LINK),
        json={"password": _UNVALIDATED_OWNER_PASSWORD},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 401
    response_json = response.json
    assert (
        response_json[STD_JSON.MESSAGE]
        == USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED
    )
    assert (
        response_json[STD_JSON.ERROR_CODE]
        == LoginErrorCodes.ACCOUNT_NOT_EMAIL_VALIDATED
    )

    with app.app_context():
        assert (
            UserOAuthIdentity.query.filter_by(
                provider_subject=_NEW_GOOGLE_SUBJECT
            ).first()
            is None
        )


@mock.patch(_GOOGLE_AUTHORIZE_ACCESS_TOKEN_TARGET)
@mock.patch(_GITHUB_GET_TARGET)
@mock.patch(_GITHUB_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_confirm_link_oauth_only_owner_completes_after_proof_login(
    mock_github_authorize_access_token: mock.MagicMock,
    mock_github_get: mock.MagicMock,
    mock_google_authorize_access_token: mock.MagicMock,
    app: Flask,
    metrics_enabled_app: Flask,
    provide_metrics_redis,
    load_login_page,
):
    """
    GIVEN a password-less Users row with a linked google identity
    WHEN a github sign-in collides with that email (stashing the pending
        github identity), the confirm page shows the OAuth-only variant, and
        the owner then completes a normal google sign-in with their EXISTING
        google subject (the required second proof of ownership)
    THEN the pending github identity is auto-inserted for that user, the user
        is logged in, and OAUTH_IDENTITY_LINKED (provider=github) is recorded
    """
    _seed_oauth_only_user(
        app,
        username=_OAUTH_ONLY_OWNER_USERNAME,
        email=_OAUTH_ONLY_OWNER_EMAIL,
        provider="google",
        subject=_OAUTH_ONLY_OWNER_GOOGLE_SUBJECT,
    )
    mock_github_authorize_access_token.return_value = _FAKE_GITHUB_TOKEN
    mock_github_get.side_effect = _github_get_side_effect(
        github_id=_NEW_GITHUB_ID,
        login="confirmlinknewgithub",
        email=_OAUTH_ONLY_OWNER_EMAIL,
    )
    client, _ = load_login_page

    collision_response = client.get(
        _github_callback_url(code=_FAKE_CODE, state=_FAKE_STATE)
    )
    assert collision_response.status_code == 302
    assert collision_response.location == url_for(OAUTH_ROUTES.CONFIRM_LINK_PAGE)

    confirm_page_response = client.get(url_for(OAUTH_ROUTES.CONFIRM_LINK_PAGE))
    assert confirm_page_response.status_code == 200
    expected_prompt = CONFIRM_LINK_OAUTH_ONLY_PROMPT.format(
        email=_OAUTH_ONLY_OWNER_EMAIL, provider="GitHub"
    )
    assert expected_prompt.encode() in confirm_page_response.data
    assert b'id="ConfirmLinkContinueWithGoogle"' in confirm_page_response.data
    assert url_for(OAUTH_ROUTES.GOOGLE_LOGIN).encode() in confirm_page_response.data

    mock_google_authorize_access_token.return_value = _build_mocked_google_token(
        subject=_OAUTH_ONLY_OWNER_GOOGLE_SUBJECT, email=_OAUTH_ONLY_OWNER_EMAIL
    )
    proof_login_response = client.get(
        _google_callback_url(code=_FAKE_CODE, state=_FAKE_STATE)
    )

    assert proof_login_response.status_code == 302
    assert proof_login_response.location == url_for(ROUTES.UTUBS.HOME)
    assert current_user.is_authenticated
    assert current_user.email == _OAUTH_ONLY_OWNER_EMAIL

    with app.app_context():
        github_identity = UserOAuthIdentity.query.filter_by(
            provider="github", provider_subject=str(_NEW_GITHUB_ID)
        ).first()
        assert github_identity is not None
        assert github_identity.user.email == _OAUTH_ONLY_OWNER_EMAIL

    assert count_counter_keys(provide_metrics_redis, EventName.LOGIN_SUCCESS) == 1
    login_success_keys = find_counter_keys(
        provide_metrics_redis, EventName.LOGIN_SUCCESS
    )
    assert parse_dims(login_success_keys[0])[_LOGIN_SUCCESS_METHOD_DIM_KEY] == "google"

    assert (
        count_counter_keys(provide_metrics_redis, EventName.OAUTH_IDENTITY_LINKED) == 1
    )
    linked_keys = find_counter_keys(
        provide_metrics_redis, EventName.OAUTH_IDENTITY_LINKED
    )
    assert (
        parse_dims(linked_keys[0])[_OAUTH_IDENTITY_LINKED_PROVIDER_DIM_KEY] == "github"
    )


@mock.patch(_GOOGLE_AUTHORIZE_ACCESS_TOKEN_TARGET)
@mock.patch(_GITHUB_GET_TARGET)
@mock.patch(_GITHUB_AUTHORIZE_ACCESS_TOKEN_TARGET)
def test_confirm_link_pending_email_mismatch_not_consumed(
    mock_github_authorize_access_token: mock.MagicMock,
    mock_github_get: mock.MagicMock,
    mock_google_authorize_access_token: mock.MagicMock,
    app: Flask,
    load_login_page,
):
    """
    GIVEN a pending collision stash for email A (a password account)
    WHEN a DIFFERENT user (email B, an OAuth-only google account) signs in
        with their own existing google subject
    THEN complete_pending_collision_link returns None without consuming the
        stash — no identity row is inserted for the pending (github, email A)
        identity, and the pending stash remains in the session
    """
    _seed_password_user(
        app,
        username=_MISMATCH_OWNER_USERNAME,
        email=_MISMATCH_OWNER_EMAIL,
        password=_MISMATCH_OWNER_PASSWORD,
    )
    _seed_oauth_only_user(
        app,
        username=_OTHER_USER_USERNAME,
        email=_OTHER_USER_EMAIL,
        provider="google",
        subject=_OTHER_USER_GOOGLE_SUBJECT,
    )
    mock_github_authorize_access_token.return_value = _FAKE_GITHUB_TOKEN
    mock_github_get.side_effect = _github_get_side_effect(
        github_id=_NEW_GITHUB_ID_FOR_MISMATCH,
        login="mismatchgithub",
        email=_MISMATCH_OWNER_EMAIL,
    )
    client, _ = load_login_page

    collision_response = client.get(
        _github_callback_url(code=_FAKE_CODE, state=_FAKE_STATE)
    )
    assert collision_response.status_code == 302
    assert collision_response.location == url_for(OAUTH_ROUTES.CONFIRM_LINK_PAGE)

    mock_google_authorize_access_token.return_value = _build_mocked_google_token(
        subject=_OTHER_USER_GOOGLE_SUBJECT, email=_OTHER_USER_EMAIL
    )
    other_login_response = client.get(
        _google_callback_url(code=_FAKE_CODE, state=_FAKE_STATE)
    )

    assert other_login_response.status_code == 302
    assert other_login_response.location == url_for(ROUTES.UTUBS.HOME)
    assert current_user.is_authenticated
    assert current_user.email == _OTHER_USER_EMAIL

    with app.app_context():
        assert (
            UserOAuthIdentity.query.filter_by(
                provider="github", provider_subject=str(_NEW_GITHUB_ID_FOR_MISMATCH)
            ).first()
            is None
        )

    with client.session_transaction() as flask_session:
        assert OAUTH_PENDING_LINK_SESSION_KEY in flask_session
        pending = flask_session[OAUTH_PENDING_LINK_SESSION_KEY]
        assert pending["email"] == _MISMATCH_OWNER_EMAIL
