from unittest import mock

import jwt
import pytest
from flask import Flask, url_for

from backend import db
from backend.models.users import Users
from backend.splash.utils import decode_resend_validation_token, verify_token
from backend.utils.all_routes import ROUTES
from backend.utils.constants import EMAIL_CONSTANTS
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.email_validation_strs import EMAILS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.splash_form_strs import REGISTER_FORM
from backend.utils.strings.user_strs import MEMBER_SUCCESS
from tests.integration.splash.conftest import register_json
from tests.integration.splash.test_resend_registration_email import (
    _create_user,
    _patch_email_confirmation_spy,
)
from tests.models_for_test import valid_user_1, valid_user_2

pytestmark = pytest.mark.splash


@pytest.fixture(autouse=True)
def _block_real_notifications():
    """A successful /validate/<token> sends a "Welcome! New user" notification;
    never let it POST to the real webhook."""
    with mock.patch("backend.extensions.notifications.notifications.requests.post"):
        yield


RESEND_TOKEN_KEY = STD_JSON.RESEND_TOKEN
_USERNAME = valid_user_1[REGISTER_FORM.USERNAME]
_EMAIL = valid_user_1[REGISTER_FORM.EMAIL]


def _make_pending_user(app: Flask) -> None:
    _create_user(
        app,
        username=_USERNAME,
        email=_EMAIL,
        password=valid_user_1[REGISTER_FORM.PASSWORD],
        validated=False,
    )


def _resend_token_for(
    app: Flask, username: str = _USERNAME, expires_in: int | None = None
) -> str:
    with app.app_context():
        user = Users.query.filter(Users.username == username).first()
        if expires_in is None:
            return user.get_resend_validation_token()
        return user.get_resend_validation_token(expires_in=expires_in)


def _post_email(client, csrf_token: str, email: str):
    return client.post(
        url_for(ROUTES.SPLASH.RESEND_REGISTRATION_EMAIL),
        json={"email": email},
        headers={"X-CSRFToken": csrf_token},
    )


def _post_token(client, csrf_token: str, token: str):
    return client.post(
        url_for(ROUTES.SPLASH.RESEND_REGISTRATION_EMAIL),
        json={RESEND_TOKEN_KEY: token},
        headers={"X-CSRFToken": csrf_token},
    )


def _set_stored_token(app: Flask, token: str) -> None:
    with app.app_context():
        user = Users.query.filter(Users.username == _USERNAME).first()
        user.email_confirm.validation_token = token
        db.session.commit()


def _stored_token(app: Flask) -> str:
    with app.app_context():
        user = Users.query.filter(Users.username == _USERNAME).first()
        return user.email_confirm.validation_token


def _expired_validation_token(app: Flask) -> str:
    with app.app_context():
        user = Users.query.filter(Users.username == _USERNAME).first()
        return user.get_email_validation_token(expires_in=-10)


def _near_expiry_validation_token(app: Flask) -> str:
    with app.app_context():
        user = Users.query.filter(Users.username == _USERNAME).first()
        return user.get_email_validation_token(
            expires_in=EMAIL_CONSTANTS.VALIDATION_TOKEN_REFRESH_MARGIN_SECONDS // 2
        )


def _fresh_validation_token(app: Flask) -> str:
    with app.app_context():
        user = Users.query.filter(Users.username == _USERNAME).first()
        return user.get_email_validation_token()


def _trip_60s_gap(app: Flask) -> None:
    with app.app_context():
        user = Users.query.filter(Users.username == _USERNAME).first()
        user.email_confirm.attempts = 1
        user.email_confirm.last_attempt = utc_now()
        db.session.commit()


def _trip_hourly_cap(app: Flask) -> None:
    with app.app_context():
        user = Users.query.filter(Users.username == _USERNAME).first()
        user.email_confirm.attempts = EMAIL_CONSTANTS.MAX_EMAIL_ATTEMPTS_IN_HOUR + 1
        user.email_confirm.last_attempt = utc_now()
        db.session.commit()


def test_login_unconfirmed_returns_decodable_resend_token(
    app, register_first_user_without_email_validation, load_login_page
):
    """
    GIVEN a registered but unconfirmed user
    WHEN they log in with the right password
    THEN the 401 body carries a resendToken that decodes only as a resend token
    """
    client, csrf_token = load_login_page
    response = client.post(
        url_for(ROUTES.SPLASH.LOGIN),
        json={
            REGISTER_FORM.USERNAME: _USERNAME,
            REGISTER_FORM.PASSWORD: valid_user_1[REGISTER_FORM.PASSWORD],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 401
    token = response.json[RESEND_TOKEN_KEY]
    with app.app_context():
        user = decode_resend_validation_token(token)
        assert user is not None and user.username == _USERNAME
        assert verify_token(token, EMAILS.VALIDATE_EMAIL).failed_due_to_exception


def test_valid_token_sends_exactly_once(app, load_register_page, monkeypatch):
    """
    GIVEN a pending user and a valid resend token
    WHEN the token is posted to the resend endpoint
    THEN exactly one confirmation email is sent and the opaque success returned
    """
    send_spy = _patch_email_confirmation_spy(monkeypatch)
    _make_pending_user(app)
    client, csrf_token = load_register_page

    response = _post_token(client, csrf_token, _resend_token_for(app))

    assert response.status_code == 200
    assert response.json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.CONFIRM_EMAIL_SENT
    send_spy.assert_called_once()
    assert send_spy.call_args.args[0] == _EMAIL.lower()


def test_every_token_outcome_is_byte_identical_and_only_valid_sends(
    app, load_register_page, monkeypatch
):
    """
    GIVEN expired, tampered, wrong-purpose, unknown-user, confirmed-user and
        within-60s tokens, plus one valid token
    WHEN each is posted
    THEN all bodies are byte-identical and only the valid one sends
    """
    send_spy = _patch_email_confirmation_spy(monkeypatch)
    _make_pending_user(app)
    _create_user(
        app,
        username=valid_user_2[REGISTER_FORM.USERNAME],
        email=valid_user_2[REGISTER_FORM.EMAIL],
        password=valid_user_2[REGISTER_FORM.PASSWORD],
        validated=True,
    )
    with app.app_context():
        unknown_user_token = jwt.encode(
            payload={
                EMAILS.RESEND_VALIDATION: "nobody_here",
                EMAILS.EXPIRATION: utc_now().timestamp() + 600,
            },
            key=app.config[CONFIG_ENVS.SECRET_KEY],
            algorithm=EMAILS.ALGORITHM,
        )
    valid_token = _resend_token_for(app)
    with app.app_context():
        pending_user = Users.query.filter(Users.username == _USERNAME).first()
        pending_user.stage_email_change("changed.address@example.com")
        email_change_token = pending_user.get_email_change_token()
        reset_token = pending_user.get_password_reset_token()
    bad_tokens = [
        email_change_token,
        reset_token,
        _resend_token_for(app, expires_in=-10),
        valid_token + "tampered",
        _fresh_validation_token(app),
        unknown_user_token,
        _resend_token_for(app, username=valid_user_2[REGISTER_FORM.USERNAME]),
        "not-a-jwt",
    ]
    client, csrf_token = load_register_page

    bodies = [_post_token(client, csrf_token, token) for token in bad_tokens]
    send_spy.assert_not_called()

    valid_response = _post_token(client, csrf_token, valid_token)
    send_spy.assert_called_once()
    within_60s_response = _post_token(client, csrf_token, valid_token)
    send_spy.assert_called_once()

    for response in [*bodies, valid_response, within_60s_response]:
        assert response.status_code == 200
        assert response.get_data() == valid_response.get_data()


def test_sent_with_expired_stored_token_remints_and_emails_new_link(
    app, load_register_page, monkeypatch
):
    """
    GIVEN a pending user whose stored validation token is expired
    WHEN a valid resend passes the guard
    THEN a new validation token is stored and the emailed link is built from it
    """
    send_spy = _patch_email_confirmation_spy(monkeypatch)
    _make_pending_user(app)
    expired = _expired_validation_token(app)
    _set_stored_token(app, expired)
    client, csrf_token = load_register_page

    _post_token(client, csrf_token, _resend_token_for(app))

    new_token = _stored_token(app)
    assert new_token != expired
    send_spy.assert_called_once()
    # args[2] is confirmation_url (to_email, to_name, confirmation_url)
    assert new_token in send_spy.call_args.args[2]


def test_sent_with_near_expiry_stored_token_remints_and_old_link_404s(
    app, load_register_page, monkeypatch
):
    """
    GIVEN a stored token within the refresh margin of expiry
    WHEN a valid resend passes the guard
    THEN the token is re-minted, the old link 404s and the new link validates
    """
    _patch_email_confirmation_spy(monkeypatch)
    _make_pending_user(app)
    near_expiry = _near_expiry_validation_token(app)
    _set_stored_token(app, near_expiry)
    client, csrf_token = load_register_page

    _post_token(client, csrf_token, _resend_token_for(app))

    new_token = _stored_token(app)
    assert new_token != near_expiry
    old_link = client.get(url_for(ROUTES.SPLASH.VALIDATE_EMAIL, token=near_expiry))
    assert old_link.status_code == 404
    new_link = client.get(url_for(ROUTES.SPLASH.VALIDATE_EMAIL, token=new_token))
    assert new_link.status_code == 302


def test_sent_with_healthy_stored_token_reuses_it_and_old_link_validates(
    app, load_register_page, monkeypatch
):
    """
    GIVEN a stored token well within its lifetime
    WHEN a valid resend passes the guard
    THEN the stored token is unchanged, resent, and the link still validates
    """
    send_spy = _patch_email_confirmation_spy(monkeypatch)
    _make_pending_user(app)
    healthy = _fresh_validation_token(app)
    _set_stored_token(app, healthy)
    client, csrf_token = load_register_page

    _post_token(client, csrf_token, _resend_token_for(app))

    assert _stored_token(app) == healthy
    # args[2] is confirmation_url (to_email, to_name, confirmation_url)
    assert healthy in send_spy.call_args.args[2]
    link = client.get(url_for(ROUTES.SPLASH.VALIDATE_EMAIL, token=healthy))
    assert link.status_code == 302


@pytest.mark.parametrize("trip_guard", [_trip_60s_gap, _trip_hourly_cap])
def test_guard_skip_never_remints_expired_token(
    app, load_register_page, monkeypatch, trip_guard
):
    """
    GIVEN an expired stored token and a tripped guard (60 s gap or hourly cap)
    WHEN a valid resend arrives
    THEN nothing is sent and the stored token is unchanged
    """
    send_spy = _patch_email_confirmation_spy(monkeypatch)
    _make_pending_user(app)
    expired = _expired_validation_token(app)
    _set_stored_token(app, expired)
    trip_guard(app)
    client, csrf_token = load_register_page

    response = _post_token(client, csrf_token, _resend_token_for(app))

    assert response.status_code == 200
    send_spy.assert_not_called()
    assert _stored_token(app) == expired


def test_registration_branch_three_never_remints(app, load_register_page, monkeypatch):
    """
    GIVEN a pending user with an expired stored token
    WHEN someone registers again with that email (branch 3)
    THEN the stored token is not re-minted and the old expired link is emailed
    """
    send_spy = _patch_email_confirmation_spy(monkeypatch)
    _make_pending_user(app)
    expired = _expired_validation_token(app)
    _set_stored_token(app, expired)
    client, csrf_token = load_register_page

    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        json=register_json(valid_user_1),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert _stored_token(app) == expired
    send_spy.assert_called_once()
    # args[2] is confirmation_url (to_email, to_name, confirmation_url)
    assert expired in send_spy.call_args.args[2]


def test_email_keyed_resend_with_expired_stored_token_remints(
    app, load_register_page, monkeypatch
):
    """
    GIVEN a pending user whose stored validation token is expired
    WHEN the email-keyed resend passes the guard
    THEN a new validation token is stored and the emailed link is built from it
    """
    send_spy = _patch_email_confirmation_spy(monkeypatch)
    _make_pending_user(app)
    expired = _expired_validation_token(app)
    _set_stored_token(app, expired)
    client, csrf_token = load_register_page

    response = _post_email(client, csrf_token, _EMAIL)

    assert response.status_code == 200
    new_token = _stored_token(app)
    assert new_token != expired
    send_spy.assert_called_once()
    # args[2] is confirmation_url (to_email, to_name, confirmation_url)
    assert new_token in send_spy.call_args.args[2]


def test_email_keyed_resend_with_healthy_stored_token_reuses_it(
    app, load_register_page, monkeypatch
):
    """
    GIVEN a pending user whose stored validation token is healthy
    WHEN the email-keyed resend passes the guard
    THEN the stored token is unchanged and is the one emailed
    """
    send_spy = _patch_email_confirmation_spy(monkeypatch)
    _make_pending_user(app)
    healthy = _fresh_validation_token(app)
    _set_stored_token(app, healthy)
    client, csrf_token = load_register_page

    response = _post_email(client, csrf_token, _EMAIL)

    assert response.status_code == 200
    assert _stored_token(app) == healthy
    send_spy.assert_called_once()
    # args[2] is confirmation_url (to_email, to_name, confirmation_url)
    assert healthy in send_spy.call_args.args[2]


@pytest.mark.parametrize(
    "body",
    [
        {"email": "user@example.com", RESEND_TOKEN_KEY: "abc"},
        {},
        {RESEND_TOKEN_KEY: ""},
    ],
)
def test_invalid_shape_gives_400(app, load_register_page, body):
    """
    GIVEN both fields, neither, or an empty-string resendToken alone
    WHEN posted to the resend endpoint
    THEN the response is 400
    """
    client, csrf_token = load_register_page

    response = client.post(
        url_for(ROUTES.SPLASH.RESEND_REGISTRATION_EMAIL),
        json=body,
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400


def test_resend_token_as_validate_link_is_404(app, load_register_page):
    """
    GIVEN a resend token
    WHEN it is used as /validate/<token>
    THEN the response is 404 (not 500) and the user stays unconfirmed
    """
    _make_pending_user(app)
    client, _ = load_register_page

    response = client.get(
        url_for(ROUTES.SPLASH.VALIDATE_EMAIL, token=_resend_token_for(app))
    )

    assert response.status_code == 404


def test_authenticated_caller_is_redirected(
    app, login_first_user_with_register, monkeypatch
):
    """
    GIVEN an authenticated caller
    WHEN they post to the resend endpoint with a token
    THEN they are 302'd
    """
    send_spy = _patch_email_confirmation_spy(monkeypatch)
    client, csrf_token, _, _ = login_first_user_with_register

    response = _post_token(client, csrf_token, "anything")

    assert response.status_code == 302
    send_spy.assert_not_called()
