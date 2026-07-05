from unittest import mock

from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest
from requests import Response
from werkzeug.test import TestResponse

from backend import db
from backend.extensions.email_sender.email_sender import EmailSender
from backend.models.forgot_passwords import Forgot_Passwords
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.schemas.users import ForgotPasswordResponseSchema
from backend.splash.services.forgot_password import provider_display_name
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.reset_password_strs import FORGOT_PASSWORD
from tests.integration.utils import assert_response_conforms_to_schema
from tests.models_for_test import valid_user_1

pytestmark = pytest.mark.splash

_OAUTH_ONLY_USERNAME = "oauthforgotuser"
_OAUTH_ONLY_EMAIL = "oauthforgotuser@example.com"
_MIXED_USERNAME = "mixedcredentialsuser"
_MIXED_EMAIL = "mixedcredentialsuser@example.com"
_MIXED_PASSWORD = "P@ssword123!"


def _make_oauth_only_user(app: Flask, *, with_identity: bool) -> str:
    """Create and commit an email-validated, password-less user, optionally with one
    linked OAuth identity. Returns the user's email address.

    Args:
        app (Flask): app providing the DB context
        with_identity (bool): when True, attach one linked ``UserOAuthIdentity``;
            when False, leave ``oauth_identities`` empty (defensive zero-identity case)

    Returns:
        (str): the persisted user's email address
    """
    with app.app_context():
        user = Users(
            username=_OAUTH_ONLY_USERNAME,
            email=_OAUTH_ONLY_EMAIL,
            plaintext_password=None,
        )
        if with_identity:
            user.oauth_identities.append(
                UserOAuthIdentity(provider="google", provider_subject="sub_forgot_123")
            )
        user.email_validated = True
        db.session.add(user)
        db.session.commit()
        return user.email


def _make_mixed_credentials_user(app: Flask) -> str:
    """Create and commit an email-validated user with both a password and a linked
    OAuth identity. Returns the user's email address.

    Args:
        app (Flask): app providing the DB context

    Returns:
        (str): the persisted user's email address
    """
    with app.app_context():
        user = Users(
            username=_MIXED_USERNAME,
            email=_MIXED_EMAIL,
            plaintext_password=_MIXED_PASSWORD,
        )
        user.oauth_identities.append(
            UserOAuthIdentity(provider="google", provider_subject="sub_mixed_123")
        )
        user.email_validated = True
        db.session.add(user)
        db.session.commit()
        return user.email


def _build_mock_email_response(status_code: int) -> Response:
    """Builds a bare ``requests.Response`` stand-in with only ``status_code`` set,
    matching the shape ``EmailSender``'s real send methods return.

    Args:
        status_code (int): the HTTP status code to set on the mock response

    Returns:
        (Response): a ``requests.Response`` with only ``status_code`` populated
    """
    mock_response = Response()
    mock_response.status_code = status_code
    return mock_response


def _post_forgot_password(
    client: FlaskClient, csrf_token: str, email: str
) -> TestResponse:
    return client.post(
        url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE),
        json={FORGOT_PASSWORD.EMAIL: email},
        headers={"X-CSRFToken": csrf_token},
    )


def test_forgot_password_no_user_creates_no_row_generic_success(app, load_login_page):
    """
    GIVEN an email that is not in the database (branch a)
    WHEN the forgot password form is POST'd with that email
    THEN the server returns the generic 200 opaque success and creates no
        Forgot_Passwords row (regression anchor for the no-user branch).
    """
    client, csrf_token = load_login_page

    with app.app_context():
        assert Forgot_Passwords.query.count() == 0

    response = _post_forgot_password(
        client, csrf_token, valid_user_1[FORGOT_PASSWORD.EMAIL]
    )

    assert response.status_code == 200
    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == FORGOT_PASSWORD.EMAIL_SENT_MESSAGE

    with app.app_context():
        assert Forgot_Passwords.query.count() == 0


def test_forgot_password_password_user_creates_row_generic_success(
    app, register_first_user, load_login_page
):
    """
    GIVEN a registered, email-validated, password-bearing user (branch b)
    WHEN the forgot password form is POST'd with their email
    THEN the server returns the generic 200 opaque success and creates exactly one
        Forgot_Passwords row (regression anchor for the password branch).
    """
    new_user, _ = register_first_user
    client, csrf_token = load_login_page

    with app.app_context():
        assert Forgot_Passwords.query.count() == 0

    response = _post_forgot_password(
        client, csrf_token, new_user[FORGOT_PASSWORD.EMAIL]
    )

    assert response.status_code == 200
    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == FORGOT_PASSWORD.EMAIL_SENT_MESSAGE

    with app.app_context():
        assert Forgot_Passwords.query.count() == 1


@mock.patch(
    "backend.extensions.email_sender.email_sender.EmailSender.send_oauth_provider_hint_email"
)
def test_forgot_password_oauth_only_user_with_identity_creates_no_row(
    mock_send_oauth_hint: mock.MagicMock, app, load_login_page
):
    """
    GIVEN an OAuth-only user (password is None) with one linked identity (branch c)
    WHEN the forgot password form is POST'd with their email
    THEN the server returns the generic 200 opaque success, sends an OAuth sign-in
        hint email naming the linked provider, and creates no Forgot_Passwords row.
    """
    mock_send_oauth_hint.return_value = _build_mock_email_response(200)
    email = _make_oauth_only_user(app, with_identity=True)
    client, csrf_token = load_login_page

    with app.app_context():
        assert Forgot_Passwords.query.count() == 0

    response = _post_forgot_password(client, csrf_token, email)

    assert response.status_code == 200
    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == FORGOT_PASSWORD.EMAIL_SENT_MESSAGE

    mock_send_oauth_hint.assert_called_once()
    call_args = mock_send_oauth_hint.call_args.args
    assert call_args[0] == email
    assert call_args[1] == _OAUTH_ONLY_USERNAME
    assert call_args[2] == ["Google"]

    with app.app_context():
        assert Forgot_Passwords.query.count() == 0


@mock.patch(
    "backend.extensions.email_sender.email_sender.EmailSender.send_oauth_provider_hint_email"
)
def test_forgot_password_oauth_only_user_without_identity_creates_no_row(
    mock_send_oauth_hint: mock.MagicMock, app, load_login_page
):
    """
    GIVEN an OAuth-only user (password is None) with zero linked identities (branch d)
    WHEN the forgot password form is POST'd with their email
    THEN the server returns the generic 200 opaque success, sends no email at all,
        and creates no Forgot_Passwords row.
    """
    email = _make_oauth_only_user(app, with_identity=False)
    client, csrf_token = load_login_page

    with app.app_context():
        assert Forgot_Passwords.query.count() == 0

    response = _post_forgot_password(client, csrf_token, email)

    assert response.status_code == 200
    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == FORGOT_PASSWORD.EMAIL_SENT_MESSAGE

    mock_send_oauth_hint.assert_not_called()

    with app.app_context():
        assert Forgot_Passwords.query.count() == 0


def test_forgot_password_mixed_credentials_user_uses_reset_token_path(
    app, load_login_page
):
    """
    GIVEN a user with both a password and a linked OAuth identity
    WHEN the forgot password form is POST'd with their email
    THEN the server routes to the normal password reset-token path (not the OAuth
        hint-email path), creating exactly one Forgot_Passwords row.
    """
    email = _make_mixed_credentials_user(app)
    client, csrf_token = load_login_page

    with app.app_context():
        assert Forgot_Passwords.query.count() == 0

    response = _post_forgot_password(client, csrf_token, email)

    assert response.status_code == 200
    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == FORGOT_PASSWORD.EMAIL_SENT_MESSAGE

    with app.app_context():
        assert Forgot_Passwords.query.count() == 1


@mock.patch(
    "backend.extensions.email_sender.email_sender.EmailSender.send_oauth_provider_hint_email"
)
def test_forgot_password_oauth_only_response_conforms_to_schema(
    mock_send_oauth_hint: mock.MagicMock, app, load_login_page
):
    """
    GIVEN an OAuth-only user (password is None) with one linked identity
    WHEN the forgot password form is POST'd with their email
    THEN the 200 JSON response conforms to ForgotPasswordResponseSchema — covering the
        null-password branch that the password-bearing schema test never reaches.
    """
    mock_send_oauth_hint.return_value = _build_mock_email_response(200)
    email = _make_oauth_only_user(app, with_identity=True)
    client, csrf_token = load_login_page

    response = _post_forgot_password(client, csrf_token, email)

    assert response.status_code == 200
    response_json = response.json

    assert_response_conforms_to_schema(
        response_json,
        ForgotPasswordResponseSchema,
        {STD_JSON.STATUS, STD_JSON.MESSAGE},
    )


def test_provider_display_name_falls_back_to_title_case_for_unmapped_provider():
    """
    GIVEN a provider key not present in `_PROVIDER_DISPLAY_NAMES` (e.g. "discord")
    WHEN `provider_display_name` is called with that key
    THEN it falls back to `str.title()` instead of raising or returning the raw key.
    """
    assert provider_display_name("discord") == "Discord"


def test_send_oauth_provider_hint_email_renders_templates_without_mocking(app):
    """
    GIVEN a real, app-initialized EmailSender (no @mock.patch on the send method)
    WHEN send_oauth_provider_hint_email is called directly with provider names
    THEN both the .txt and .html templates render without raising a Jinja error,
        proving the templates added for this feature are syntactically valid.
    """
    with app.test_request_context():
        email_sender = EmailSender()
        email_sender.init_app(app)

        email_send_result = email_sender.send_oauth_provider_hint_email(
            _OAUTH_ONLY_EMAIL, _OAUTH_ONLY_USERNAME, ["Google"]
        )

    assert email_send_result.status_code < 500
