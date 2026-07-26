from unittest.mock import MagicMock

from flask import Flask, url_for
import pytest
from requests import Response

from backend import db
from backend.extensions.email_sender.email_sender import EmailSender
from backend.models.email_validations import Email_Validations
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.constants import EMAIL_CONSTANTS
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.splash_form_strs import REGISTER_FORM
from backend.utils.strings.user_strs import MEMBER_SUCCESS
from tests.models_for_test import valid_user_1, valid_user_2

pytestmark = pytest.mark.splash


def _ok_email_response() -> Response:
    response = Response()
    response.status_code = 200
    return response


def _patch_email_confirmation_spy(monkeypatch) -> MagicMock:
    send_spy = MagicMock(return_value=_ok_email_response())
    monkeypatch.setattr(EmailSender, "send_account_email_confirmation", send_spy)
    return send_spy


def _server_error_email_response() -> Response:
    """A Mailjet response simulating a server-side (>= 500) send failure."""
    response = Response()
    response.status_code = 502
    return response


def _patch_email_confirmation_server_error(monkeypatch) -> MagicMock:
    send_spy = MagicMock(return_value=_server_error_email_response())
    monkeypatch.setattr(EmailSender, "send_account_email_confirmation", send_spy)
    return send_spy


def _create_user(
    app: Flask, username: str, email: str, password: str, *, validated: bool
) -> None:
    with app.app_context():
        new_user = Users(
            username=username,
            email=email.lower(),
            plaintext_password=password,
        )
        if validated:
            new_user.email_validated = True
        else:
            new_user.email_confirm = Email_Validations(
                validation_token=new_user.get_email_validation_token()
            )
        db.session.add(new_user)
        db.session.commit()


def _post_resend(client, csrf_token: str, email: str):
    return client.post(
        url_for(ROUTES.SPLASH.RESEND_REGISTRATION_EMAIL),
        json={"email": email},
        headers={"X-CSRFToken": csrf_token},
    )


def test_resend_pending_unvalidated_user_sends_opaque_success(
    app, load_register_page, monkeypatch
):
    """
    GIVEN a pending (unvalidated) user
    WHEN POST /resend-registration-email with their email
    THEN the confirmation email is sent once AND the uniform opaque success is returned.
    """
    send_spy = _patch_email_confirmation_spy(monkeypatch)
    _create_user(
        app,
        username=valid_user_1[REGISTER_FORM.USERNAME],
        email=valid_user_1[REGISTER_FORM.EMAIL],
        password=valid_user_1[REGISTER_FORM.PASSWORD],
        validated=False,
    )
    client, csrf_token = load_register_page

    response = _post_resend(client, csrf_token, valid_user_1[REGISTER_FORM.EMAIL])

    assert response.status_code == 200
    assert response.json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response.json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.CONFIRM_EMAIL_SENT
    send_spy.assert_called_once()
    assert send_spy.call_args.args[0] == valid_user_1[REGISTER_FORM.EMAIL].lower()


def test_resend_validated_email_does_not_send(app, load_register_page, monkeypatch):
    """
    GIVEN an already-validated user
    WHEN POST /resend-registration-email with their email
    THEN no email is sent, yet the uniform opaque success is still returned.
    """
    send_spy = _patch_email_confirmation_spy(monkeypatch)
    _create_user(
        app,
        username=valid_user_1[REGISTER_FORM.USERNAME],
        email=valid_user_1[REGISTER_FORM.EMAIL],
        password=valid_user_1[REGISTER_FORM.PASSWORD],
        validated=True,
    )
    client, csrf_token = load_register_page

    response = _post_resend(client, csrf_token, valid_user_1[REGISTER_FORM.EMAIL])

    assert response.status_code == 200
    assert response.json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.CONFIRM_EMAIL_SENT
    send_spy.assert_not_called()


def test_resend_unknown_email_does_not_send(app, load_register_page, monkeypatch):
    """
    GIVEN no user with the requested email
    WHEN POST /resend-registration-email with that email
    THEN no email is sent, yet the uniform opaque success is still returned.
    """
    send_spy = _patch_email_confirmation_spy(monkeypatch)
    client, csrf_token = load_register_page

    response = _post_resend(client, csrf_token, valid_user_2[REGISTER_FORM.EMAIL])

    assert response.status_code == 200
    assert response.json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.CONFIRM_EMAIL_SENT
    send_spy.assert_not_called()


def test_resend_responses_are_byte_identical(app, load_register_page, monkeypatch):
    """
    GIVEN a pending user, a validated user, and an unknown email
    WHEN POST /resend-registration-email is hit for each
    THEN all three response bodies are byte-identical (no enumeration signal).
    """
    _patch_email_confirmation_spy(monkeypatch)
    _create_user(
        app,
        username=valid_user_1[REGISTER_FORM.USERNAME],
        email=valid_user_1[REGISTER_FORM.EMAIL],
        password=valid_user_1[REGISTER_FORM.PASSWORD],
        validated=False,
    )
    _create_user(
        app,
        username=valid_user_2[REGISTER_FORM.USERNAME],
        email=valid_user_2[REGISTER_FORM.EMAIL],
        password=valid_user_2[REGISTER_FORM.PASSWORD],
        validated=True,
    )
    client, csrf_token = load_register_page

    pending_response = _post_resend(
        client, csrf_token, valid_user_1[REGISTER_FORM.EMAIL]
    )
    validated_response = _post_resend(
        client, csrf_token, valid_user_2[REGISTER_FORM.EMAIL]
    )
    unknown_response = _post_resend(client, csrf_token, "nobody@example.com")

    assert pending_response.get_data() == validated_response.get_data()
    assert pending_response.get_data() == unknown_response.get_data()


def test_resend_mailjet_server_error_stays_opaque(
    app, load_register_page, monkeypatch, caplog
):
    """
    Security regression (DD-5a): GIVEN a pending (unvalidated) user whose Mailjet
        send fails with a server error (>= 500)
    WHEN POST /resend-registration-email with their email
    THEN the route STILL returns the identical opaque success (200) with the
        uniform CONFIRM_EMAIL_SENT message — a Mailjet outage must never leak the
        account's existence/state — and the >= 500 failure is logged.
    """
    from tests.utils_for_test import is_string_in_logs

    send_spy = _patch_email_confirmation_server_error(monkeypatch)
    _create_user(
        app,
        username=valid_user_1[REGISTER_FORM.USERNAME],
        email=valid_user_1[REGISTER_FORM.EMAIL],
        password=valid_user_1[REGISTER_FORM.PASSWORD],
        validated=False,
    )
    client, csrf_token = load_register_page

    response = _post_resend(client, csrf_token, valid_user_1[REGISTER_FORM.EMAIL])

    assert response.status_code == 200
    assert response.json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response.json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.CONFIRM_EMAIL_SENT
    send_spy.assert_called_once()

    with app.app_context():
        pending_user: Users = Users.query.filter(
            Users.email == valid_user_1[REGISTER_FORM.EMAIL].lower()
        ).first()
        assert is_string_in_logs(
            f"(4) Email failed to send: registration confirmation resend for "
            f"User={pending_user.id}",
            caplog.records,
        )


def test_resend_guard_tripped_sends_nothing(app, load_register_page, monkeypatch):
    """
    DD-22 (surface 2): GIVEN a pending user whose per-account email guard is tripped
    WHEN POST /resend-registration-email with their email
    THEN NO email is sent yet the response is still the identical opaque success.
    """
    send_spy = _patch_email_confirmation_spy(monkeypatch)
    _create_user(
        app,
        username=valid_user_1[REGISTER_FORM.USERNAME],
        email=valid_user_1[REGISTER_FORM.EMAIL],
        password=valid_user_1[REGISTER_FORM.PASSWORD],
        validated=False,
    )

    with app.app_context():
        pending_user: Users = Users.query.filter(
            Users.email == valid_user_1[REGISTER_FORM.EMAIL].lower()
        ).first()
        pending_user.email_confirm.attempts = (
            EMAIL_CONSTANTS.MAX_EMAIL_ATTEMPTS_IN_HOUR + 1
        )
        pending_user.email_confirm.last_attempt = utc_now()
        db.session.commit()

    client, csrf_token = load_register_page

    response = _post_resend(client, csrf_token, valid_user_1[REGISTER_FORM.EMAIL])

    assert response.status_code == 200
    assert response.json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.CONFIRM_EMAIL_SENT
    send_spy.assert_not_called()
