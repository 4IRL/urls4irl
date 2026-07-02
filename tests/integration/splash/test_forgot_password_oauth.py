from flask import url_for
import pytest

from backend import db
from backend.models.forgot_passwords import Forgot_Passwords
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.schemas.users import ForgotPasswordResponseSchema
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.reset_password_strs import FORGOT_PASSWORD
from tests.integration.utils import assert_response_conforms_to_schema
from tests.models_for_test import valid_user_1

pytestmark = pytest.mark.splash

_OAUTH_ONLY_USERNAME = "oauthforgotuser"
_OAUTH_ONLY_EMAIL = "oauthforgotuser@example.com"


def _make_oauth_only_user(app, *, with_identity: bool) -> str:
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


def _post_forgot_password(client, csrf_token, email):
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


def test_forgot_password_oauth_only_user_with_identity_creates_no_row(
    app, load_login_page
):
    """
    GIVEN an OAuth-only user (password is None) with one linked identity (branch c)
    WHEN the forgot password form is POST'd with their email
    THEN the server returns the generic 200 opaque success, sends no email, and
        creates no Forgot_Passwords row.
    """
    email = _make_oauth_only_user(app, with_identity=True)
    client, csrf_token = load_login_page

    with app.app_context():
        assert Forgot_Passwords.query.count() == 0

    response = _post_forgot_password(client, csrf_token, email)

    assert response.status_code == 200
    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == FORGOT_PASSWORD.EMAIL_SENT_MESSAGE

    with app.app_context():
        assert Forgot_Passwords.query.count() == 0


def test_forgot_password_oauth_only_user_without_identity_creates_no_row(
    app, load_login_page
):
    """
    GIVEN an OAuth-only user (password is None) with zero linked identities (branch d)
    WHEN the forgot password form is POST'd with their email
    THEN the server returns the generic 200 opaque success, sends no email, and
        creates no Forgot_Passwords row.
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

    with app.app_context():
        assert Forgot_Passwords.query.count() == 0


def test_forgot_password_oauth_only_response_conforms_to_schema(app, load_login_page):
    """
    GIVEN an OAuth-only user (password is None) with one linked identity
    WHEN the forgot password form is POST'd with their email
    THEN the 200 JSON response conforms to ForgotPasswordResponseSchema — covering the
        null-password branch that the password-bearing schema test never reaches.
    """
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
