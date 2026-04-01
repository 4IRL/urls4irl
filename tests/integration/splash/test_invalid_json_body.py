"""Integration tests for invalid/missing JSON bodies on splash POST routes.

Verifies that the @api_route decorator correctly returns 400 responses
when JSON is missing entirely, empty, or missing required fields.
"""

from flask import url_for
import pytest

from backend.splash.constants import (
    ForgotPasswordErrorCodes,
    LoginErrorCodes,
    RegisterErrorCodes,
    ResetPasswordErrorCodes,
)
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.reset_password_strs import FORGOT_PASSWORD, RESET_PASSWORD
from backend.utils.strings.user_strs import USER_FAILURE

pytestmark = pytest.mark.splash


class TestLoginInvalidJson:
    """Tests for /login with missing or malformed JSON bodies."""

    def test_login_missing_json_body(self, load_login_page):
        """
        GIVEN a user on the login page
        WHEN "/login" is POST'd with no JSON body (content_type text/plain)
        THEN ensure 400 with correct error message and error code, no errors dict
        """
        client, csrf_token = load_login_page

        response = client.post(
            url_for(ROUTES.SPLASH.LOGIN),
            data="not json",
            content_type="text/plain",
            headers={"X-CSRFToken": csrf_token},
        )

        assert response.status_code == 400
        response_json = response.json
        assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert response_json[STD_JSON.MESSAGE] == USER_FAILURE.UNABLE_TO_LOGIN
        assert (
            int(response_json[STD_JSON.ERROR_CODE])
            == LoginErrorCodes.INVALID_FORM_INPUT
        )
        assert STD_JSON.ERRORS not in response_json

    def test_login_empty_json_body(self, load_login_page):
        """
        GIVEN a user on the login page
        WHEN "/login" is POST'd with an empty JSON object
        THEN ensure 400 with validation errors for missing fields
        """
        client, csrf_token = load_login_page

        response = client.post(
            url_for(ROUTES.SPLASH.LOGIN),
            json={},
            headers={"X-CSRFToken": csrf_token},
        )

        assert response.status_code == 400
        response_json = response.json
        assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert response_json[STD_JSON.MESSAGE] == USER_FAILURE.UNABLE_TO_LOGIN
        assert (
            int(response_json[STD_JSON.ERROR_CODE])
            == LoginErrorCodes.INVALID_FORM_INPUT
        )
        assert STD_JSON.ERRORS in response_json
        assert "username" in response_json[STD_JSON.ERRORS]
        assert "password" in response_json[STD_JSON.ERRORS]

    def test_login_missing_password_field(self, load_login_page):
        """
        GIVEN a user on the login page
        WHEN "/login" is POST'd with username but no password
        THEN ensure 400 with validation error for password only
        """
        client, csrf_token = load_login_page

        response = client.post(
            url_for(ROUTES.SPLASH.LOGIN),
            json={"username": "testuser"},
            headers={"X-CSRFToken": csrf_token},
        )

        assert response.status_code == 400
        response_json = response.json
        assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert STD_JSON.ERRORS in response_json
        assert "password" in response_json[STD_JSON.ERRORS]
        assert "username" not in response_json[STD_JSON.ERRORS]


class TestRegisterInvalidJson:
    """Tests for /register with missing or malformed JSON bodies."""

    def test_register_missing_json_body(self, load_register_page):
        """
        GIVEN a user on the register page
        WHEN "/register" is POST'd with no JSON body
        THEN ensure 400 with correct error message and error code, no errors dict
        """
        client, csrf_token = load_register_page

        response = client.post(
            url_for(ROUTES.SPLASH.REGISTER),
            data="not json",
            content_type="text/plain",
            headers={"X-CSRFToken": csrf_token},
        )

        assert response.status_code == 400
        response_json = response.json
        assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert response_json[STD_JSON.MESSAGE] == USER_FAILURE.UNABLE_TO_REGISTER
        assert (
            int(response_json[STD_JSON.ERROR_CODE])
            == RegisterErrorCodes.INVALID_FORM_INPUT
        )
        assert STD_JSON.ERRORS not in response_json

    def test_register_empty_json_body(self, load_register_page):
        """
        GIVEN a user on the register page
        WHEN "/register" is POST'd with an empty JSON object
        THEN ensure 400 with validation errors for all required fields
        """
        client, csrf_token = load_register_page

        response = client.post(
            url_for(ROUTES.SPLASH.REGISTER),
            json={},
            headers={"X-CSRFToken": csrf_token},
        )

        assert response.status_code == 400
        response_json = response.json
        assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert response_json[STD_JSON.MESSAGE] == USER_FAILURE.UNABLE_TO_REGISTER
        assert (
            int(response_json[STD_JSON.ERROR_CODE])
            == RegisterErrorCodes.INVALID_FORM_INPUT
        )
        assert STD_JSON.ERRORS in response_json
        assert "username" in response_json[STD_JSON.ERRORS]
        assert "email" in response_json[STD_JSON.ERRORS]
        assert "password" in response_json[STD_JSON.ERRORS]

    def test_register_partial_json_body(self, load_register_page):
        """
        GIVEN a user on the register page
        WHEN "/register" is POST'd with only username
        THEN ensure 400 with validation errors for remaining required fields
        """
        client, csrf_token = load_register_page

        response = client.post(
            url_for(ROUTES.SPLASH.REGISTER),
            json={"username": "testuser"},
            headers={"X-CSRFToken": csrf_token},
        )

        assert response.status_code == 400
        response_json = response.json
        assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert STD_JSON.ERRORS in response_json
        assert "username" not in response_json[STD_JSON.ERRORS]
        assert "email" in response_json[STD_JSON.ERRORS]
        assert "password" in response_json[STD_JSON.ERRORS]


class TestForgotPasswordInvalidJson:
    """Tests for /forgot-password with missing or malformed JSON bodies."""

    def test_forgot_password_missing_json_body(self, load_login_page):
        """
        GIVEN a user on the forgot-password page
        WHEN "/forgot-password" is POST'd with no JSON body
        THEN ensure 400 with correct error message and error code, no errors dict
        """
        client, csrf_token = load_login_page

        response = client.post(
            url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE),
            data="not json",
            content_type="text/plain",
            headers={"X-CSRFToken": csrf_token},
        )

        assert response.status_code == 400
        response_json = response.json
        assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert response_json[STD_JSON.MESSAGE] == FORGOT_PASSWORD.INVALID_EMAIL
        assert (
            int(response_json[STD_JSON.ERROR_CODE])
            == ForgotPasswordErrorCodes.INVALID_FORM_INPUT
        )
        assert STD_JSON.ERRORS not in response_json

    def test_forgot_password_empty_json_body(self, load_login_page):
        """
        GIVEN a user on the forgot-password page
        WHEN "/forgot-password" is POST'd with an empty JSON object
        THEN ensure 400 with validation error for email field
        """
        client, csrf_token = load_login_page

        response = client.post(
            url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE),
            json={},
            headers={"X-CSRFToken": csrf_token},
        )

        assert response.status_code == 400
        response_json = response.json
        assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert response_json[STD_JSON.MESSAGE] == FORGOT_PASSWORD.INVALID_EMAIL
        assert (
            int(response_json[STD_JSON.ERROR_CODE])
            == ForgotPasswordErrorCodes.INVALID_FORM_INPUT
        )
        assert STD_JSON.ERRORS in response_json
        assert "email" in response_json[STD_JSON.ERRORS]


class TestResetPasswordInvalidJson:
    """Tests for /reset-password/<token> with missing or malformed JSON bodies."""

    def test_reset_password_missing_json_body(self, user_attempts_reset_password):
        """
        GIVEN a user with a valid reset token
        WHEN "/reset-password/<token>" is POST'd with no JSON body
        THEN ensure 400 with correct error message and error code, no errors dict
        """
        _, client, _, reset_token, csrf_token = user_attempts_reset_password

        response = client.post(
            url_for(ROUTES.SPLASH.RESET_PASSWORD, token=reset_token),
            data="not json",
            content_type="text/plain",
            headers={"X-CSRFToken": csrf_token},
        )

        assert response.status_code == 400
        response_json = response.json
        assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert response_json[STD_JSON.MESSAGE] == RESET_PASSWORD.RESET_PASSWORD_INVALID
        assert (
            int(response_json[STD_JSON.ERROR_CODE])
            == ResetPasswordErrorCodes.INVALID_FORM_INPUT
        )
        assert STD_JSON.ERRORS not in response_json

    def test_reset_password_empty_json_body(self, user_attempts_reset_password):
        """
        GIVEN a user with a valid reset token
        WHEN "/reset-password/<token>" is POST'd with an empty JSON object
        THEN ensure 400 with validation errors for password fields
        """
        _, client, _, reset_token, csrf_token = user_attempts_reset_password

        response = client.post(
            url_for(ROUTES.SPLASH.RESET_PASSWORD, token=reset_token),
            json={},
            headers={"X-CSRFToken": csrf_token},
        )

        assert response.status_code == 400
        response_json = response.json
        assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert response_json[STD_JSON.MESSAGE] == RESET_PASSWORD.RESET_PASSWORD_INVALID
        assert (
            int(response_json[STD_JSON.ERROR_CODE])
            == ResetPasswordErrorCodes.INVALID_FORM_INPUT
        )
        assert STD_JSON.ERRORS in response_json
        assert "newPassword" in response_json[STD_JSON.ERRORS]

    def test_reset_password_missing_confirm_field(self, user_attempts_reset_password):
        """
        GIVEN a user with a valid reset token
        WHEN "/reset-password/<token>" is POST'd with newPassword but no confirmNewPassword
        THEN ensure 400 with validation error for confirmNewPassword
        """
        _, client, _, reset_token, csrf_token = user_attempts_reset_password

        response = client.post(
            url_for(ROUTES.SPLASH.RESET_PASSWORD, token=reset_token),
            json={"newPassword": "a" * 12},
            headers={"X-CSRFToken": csrf_token},
        )

        assert response.status_code == 400
        response_json = response.json
        assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert STD_JSON.ERRORS in response_json
        assert "confirmNewPassword" in response_json[STD_JSON.ERRORS]
