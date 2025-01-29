from flask import url_for, request
import pytest

from src.utils.all_routes import ROUTES
from src.utils.constants import USER_CONSTANTS
from src.utils.strings.email_validation_strs import EMAILS_FAILURE
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.splash_form_strs import REGISTER_FORM
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from src.utils.strings.user_strs import USER_FAILURE as REGISTER_FAILURE

pytestmark = pytest.mark.unit


def test_register_user_form_only_username_csrf(load_register_page):
    """
    GIVEN an unregistered user
    WHEN "/register" is POST'd with only username and CSRF
    THEN ensure registration does not occur
    """

    client, csrf_token_string = load_register_page
    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        data={
            REGISTER_FORM.CSRF_TOKEN: csrf_token_string,
            REGISTER_FORM.USERNAME: "FakeUserName123",
            REGISTER_FORM.EMAIL: "",
            REGISTER_FORM.CONFIRM_EMAIL: "",
            REGISTER_FORM.PASSWORD: "",
            REGISTER_FORM.CONFIRM_PASSWORD: "",
        },
    )

    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.REGISTER)
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == REGISTER_FAILURE.UNABLE_TO_REGISTER
    assert len(response_json[STD_JSON.ERRORS]) == 4

    for input_key in REGISTER_FORM.REGISTER_FORM_KEYS:
        if input_key == REGISTER_FORM.USERNAME:
            continue
        assert (
            response_json[STD_JSON.ERRORS][input_key] == REGISTER_FAILURE.FIELD_REQUIRED
        )


def test_register_user_form_only_invalid_email_csrf(load_register_page):
    """
    GIVEN an unregistered user
    WHEN "/register" is POST'd with only invalid email and CSRF
    THEN ensure registration does not occur due to missing fields and invalid email
    """

    client, csrf_token_string = load_register_page
    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        data={
            REGISTER_FORM.CSRF_TOKEN: csrf_token_string,
            REGISTER_FORM.USERNAME: "",
            REGISTER_FORM.EMAIL: "FakeUserName123",
            REGISTER_FORM.CONFIRM_EMAIL: "",
            REGISTER_FORM.PASSWORD: "",
            REGISTER_FORM.CONFIRM_PASSWORD: "",
        },
    )

    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.REGISTER)
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == REGISTER_FAILURE.UNABLE_TO_REGISTER
    assert len(response_json[STD_JSON.ERRORS]) == 5

    for input_key in REGISTER_FORM.REGISTER_FORM_KEYS:
        form_error = response_json[STD_JSON.ERRORS][input_key]
        if input_key == REGISTER_FORM.EMAIL:
            assert form_error == [EMAILS_FAILURE.INVALID_EMAIL_INPUT]
        else:
            assert (
                response_json[STD_JSON.ERRORS][input_key]
                == REGISTER_FAILURE.FIELD_REQUIRED
            )


def test_register_user_form_only_valid_email_csrf(load_register_page):
    """
    GIVEN an unregistered user
    WHEN "/register" is POST'd with only valid email and CSRF
    THEN ensure registration does not occur due to missing fields
    """

    client, csrf_token_string = load_register_page
    # Only email and valid email
    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        data={
            REGISTER_FORM.CSRF_TOKEN: csrf_token_string,
            REGISTER_FORM.USERNAME: "",
            REGISTER_FORM.EMAIL: "FakeUserName123@email.com",
            REGISTER_FORM.CONFIRM_EMAIL: "",
            REGISTER_FORM.PASSWORD: "",
            REGISTER_FORM.CONFIRM_PASSWORD: "",
        },
    )

    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.REGISTER)
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == REGISTER_FAILURE.UNABLE_TO_REGISTER
    assert len(response_json[STD_JSON.ERRORS]) == 4

    for input_key in REGISTER_FORM.REGISTER_FORM_KEYS:
        if input_key == REGISTER_FORM.EMAIL:
            continue
        assert (
            response_json[STD_JSON.ERRORS][input_key] == REGISTER_FAILURE.FIELD_REQUIRED
        )


def test_register_user_form_only_confirm_email_csrf(load_register_page):
    """
    GIVEN an unregistered user
    WHEN "/register" is POST'd with only confirm email and CSRF
    THEN ensure registration does not occur due to missing fields
    """

    client, csrf_token_string = load_register_page
    # Only confirm email and no email
    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        data={
            REGISTER_FORM.CSRF_TOKEN: csrf_token_string,
            REGISTER_FORM.USERNAME: "",
            REGISTER_FORM.EMAIL: "",
            REGISTER_FORM.CONFIRM_EMAIL: "FakeUserName123@email.com",
            REGISTER_FORM.PASSWORD: "",
            REGISTER_FORM.CONFIRM_PASSWORD: "",
        },
    )

    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.REGISTER)
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == REGISTER_FAILURE.UNABLE_TO_REGISTER
    assert len(response_json[STD_JSON.ERRORS]) == 5

    for input_key in REGISTER_FORM.REGISTER_FORM_KEYS:
        if input_key == REGISTER_FORM.CONFIRM_EMAIL:
            assert response_json[STD_JSON.ERRORS][input_key] == [
                UI_TEST_STRINGS.EMAIL_EQUALITY_FAILED
            ]
        else:
            assert (
                response_json[STD_JSON.ERRORS][input_key]
                == REGISTER_FAILURE.FIELD_REQUIRED
            )


def test_register_user_form_invalid_password_csrf(load_register_page):
    """
    GIVEN an unregistered user
    WHEN "/register" is POST'd with only an invalid password and CSRF
    THEN ensure registration does not occur due to missing field and invalid password
    """

    client, csrf_token_string = load_register_page
    # Only password, short password
    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        data={
            REGISTER_FORM.CSRF_TOKEN: csrf_token_string,
            REGISTER_FORM.USERNAME: "",
            REGISTER_FORM.EMAIL: "",
            REGISTER_FORM.CONFIRM_EMAIL: "",
            REGISTER_FORM.PASSWORD: "FakeUser123",
            REGISTER_FORM.CONFIRM_PASSWORD: "",
        },
    )

    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.REGISTER)
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == REGISTER_FAILURE.UNABLE_TO_REGISTER
    assert len(response_json[STD_JSON.ERRORS]) == 5

    for input_key in REGISTER_FORM.REGISTER_FORM_KEYS:
        if input_key == REGISTER_FORM.PASSWORD:
            assert response_json[STD_JSON.ERRORS][input_key] == [
                f"Field must be between {USER_CONSTANTS.MIN_PASSWORD_LENGTH} and {USER_CONSTANTS.MAX_PASSWORD_LENGTH} characters long."
            ]
        else:
            assert (
                response_json[STD_JSON.ERRORS][input_key]
                == REGISTER_FAILURE.FIELD_REQUIRED
            )


def test_register_user_form_only_valid_password_csrf(load_register_page):
    """
    GIVEN an unregistered user
    WHEN "/register" is POST'd with only a valid password and CSRF
    THEN ensure registration does not occur due to missing fields
    """

    client, csrf_token_string = load_register_page
    # Only password, valid password
    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        data={
            REGISTER_FORM.CSRF_TOKEN: csrf_token_string,
            REGISTER_FORM.USERNAME: "",
            REGISTER_FORM.EMAIL: "",
            REGISTER_FORM.CONFIRM_EMAIL: "",
            REGISTER_FORM.PASSWORD: "FakeUserName123",
            REGISTER_FORM.CONFIRM_PASSWORD: "",
        },
    )

    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.REGISTER)
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == REGISTER_FAILURE.UNABLE_TO_REGISTER
    assert len(response_json[STD_JSON.ERRORS]) == 4

    for input_key in REGISTER_FORM.REGISTER_FORM_KEYS:
        if input_key == REGISTER_FORM.PASSWORD:
            continue
        assert (
            response_json[STD_JSON.ERRORS][input_key] == REGISTER_FAILURE.FIELD_REQUIRED
        )


def test_register_user_form_only_confirm_password_csrf(load_register_page):
    """
    GIVEN an unregistered user
    WHEN "/register" is POST'd with only confirm password field and CSRF
    THEN ensure registration does not occur
    """

    client, csrf_token_string = load_register_page
    # Only password confirm
    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        data={
            REGISTER_FORM.CSRF_TOKEN: csrf_token_string,
            REGISTER_FORM.USERNAME: "",
            REGISTER_FORM.EMAIL: "",
            REGISTER_FORM.CONFIRM_EMAIL: "",
            REGISTER_FORM.PASSWORD: "",
            REGISTER_FORM.CONFIRM_PASSWORD: "FakeUserName123",
        },
    )

    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.REGISTER)
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == REGISTER_FAILURE.UNABLE_TO_REGISTER
    assert len(response_json[STD_JSON.ERRORS]) == 5

    for input_key in REGISTER_FORM.REGISTER_FORM_KEYS:
        if input_key == REGISTER_FORM.CONFIRM_PASSWORD:
            assert response_json[STD_JSON.ERRORS][input_key] == [
                UI_TEST_STRINGS.PASSWORD_EQUALITY_FAILED
            ]
        else:
            assert (
                response_json[STD_JSON.ERRORS][input_key]
                == REGISTER_FAILURE.FIELD_REQUIRED
            )


def test_register_user_form_long_password_csrf(load_register_page):
    """
    GIVEN an unregistered user
    WHEN "/register" is POST'd with a too long password
    THEN ensure registration does not occur
    """

    client, csrf_token_string = load_register_page
    # Only password confirm
    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        data={
            REGISTER_FORM.CSRF_TOKEN: csrf_token_string,
            REGISTER_FORM.USERNAME: "FakeUserName123",
            REGISTER_FORM.EMAIL: "FakeUser@Name123.com",
            REGISTER_FORM.CONFIRM_EMAIL: "FakeUser@Name123.com",
            REGISTER_FORM.PASSWORD: "a" * (USER_CONSTANTS.MAX_PASSWORD_LENGTH + 1),
            REGISTER_FORM.CONFIRM_PASSWORD: "a"
            * (USER_CONSTANTS.MAX_PASSWORD_LENGTH + 1),
        },
    )

    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.REGISTER)
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == REGISTER_FAILURE.UNABLE_TO_REGISTER
    assert len(response_json[STD_JSON.ERRORS]) == 1
    assert response_json[STD_JSON.ERRORS][REGISTER_FORM.PASSWORD] == [
        f"Field must be between {USER_CONSTANTS.MIN_PASSWORD_LENGTH} and {USER_CONSTANTS.MAX_PASSWORD_LENGTH} characters long."
    ]


def test_register_user_form_short_password_csrf(load_register_page):
    """
    GIVEN an unregistered user
    WHEN "/register" is POST'd with a too short password
    THEN ensure registration does not occur
    """

    client, csrf_token_string = load_register_page
    # Only password confirm
    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        data={
            REGISTER_FORM.CSRF_TOKEN: csrf_token_string,
            REGISTER_FORM.USERNAME: "FakeUserName123",
            REGISTER_FORM.EMAIL: "FakeUser@Name123.com",
            REGISTER_FORM.CONFIRM_EMAIL: "FakeUser@Name123.com",
            REGISTER_FORM.PASSWORD: "a" * (USER_CONSTANTS.MIN_PASSWORD_LENGTH - 1),
            REGISTER_FORM.CONFIRM_PASSWORD: "a"
            * (USER_CONSTANTS.MIN_PASSWORD_LENGTH - 1),
        },
    )

    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.REGISTER)
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == REGISTER_FAILURE.UNABLE_TO_REGISTER
    assert len(response_json[STD_JSON.ERRORS]) == 1
    assert response_json[STD_JSON.ERRORS][REGISTER_FORM.PASSWORD] == [
        f"Field must be between {USER_CONSTANTS.MIN_PASSWORD_LENGTH} and {USER_CONSTANTS.MAX_PASSWORD_LENGTH} characters long."
    ]


def test_register_user_form_long_username_csrf(load_register_page):
    """
    GIVEN an unregistered user
    WHEN "/register" is POST'd with a too long username
    THEN ensure registration does not occur
    """

    client, csrf_token_string = load_register_page
    # Only password confirm
    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        data={
            REGISTER_FORM.CSRF_TOKEN: csrf_token_string,
            REGISTER_FORM.USERNAME: "a" * (USER_CONSTANTS.MAX_USERNAME_LENGTH + 1),
            REGISTER_FORM.EMAIL: "FakeUser@Name123.com",
            REGISTER_FORM.CONFIRM_EMAIL: "FakeUser@Name123.com",
            REGISTER_FORM.PASSWORD: "FakeUser@Name123.com",
            REGISTER_FORM.CONFIRM_PASSWORD: "FakeUser@Name123.com",
        },
    )

    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.REGISTER)
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == REGISTER_FAILURE.UNABLE_TO_REGISTER
    assert len(response_json[STD_JSON.ERRORS]) == 1
    assert response_json[STD_JSON.ERRORS][REGISTER_FORM.USERNAME] == [
        f"Field must be between {USER_CONSTANTS.MIN_USERNAME_LENGTH} and {USER_CONSTANTS.MAX_USERNAME_LENGTH} characters long."
    ]


def test_register_user_with_invalid_html_input_fully_sanitized(load_register_page):
    client, csrf_token_string = load_register_page

    client, csrf_token_string = load_register_page
    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        data={
            REGISTER_FORM.CSRF_TOKEN: csrf_token_string,
            REGISTER_FORM.USERNAME: '<img src="evl.jpg">',
            REGISTER_FORM.EMAIL: "FakeUser@Name123.com",
            REGISTER_FORM.CONFIRM_EMAIL: "FakeUser@Name123.com",
            REGISTER_FORM.PASSWORD: "FakeUser@Name123.com",
            REGISTER_FORM.CONFIRM_PASSWORD: "FakeUser@Name123.com",
        },
    )

    # Correctly sends URL to email validation modal
    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.REGISTER)
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == REGISTER_FAILURE.UNABLE_TO_REGISTER
    assert len(response_json[STD_JSON.ERRORS]) == 1
    assert response_json[STD_JSON.ERRORS][REGISTER_FORM.USERNAME] == [
        REGISTER_FAILURE.INVALID_INPUT
    ]


def test_register_user_with_invalid_html_input_partially_sanitized(load_register_page):
    client, csrf_token_string = load_register_page

    for username in (
        "<<HELLO>>",
        "<h1>Hello</h1>",
    ):
        client, csrf_token_string = load_register_page
        response = client.post(
            url_for(ROUTES.SPLASH.REGISTER),
            data={
                REGISTER_FORM.CSRF_TOKEN: csrf_token_string,
                REGISTER_FORM.USERNAME: username,
                REGISTER_FORM.EMAIL: "FakeUser@Name123.com",
                REGISTER_FORM.CONFIRM_EMAIL: "FakeUser@Name123.com",
                REGISTER_FORM.PASSWORD: "FakeUser@Name123.com",
                REGISTER_FORM.CONFIRM_PASSWORD: "FakeUser@Name123.com",
            },
        )

        # Correctly sends URL to email validation modal
        assert response.status_code == 400
        assert request.path == url_for(ROUTES.SPLASH.REGISTER)
        response_json = response.json

        assert int(response_json[STD_JSON.ERROR_CODE]) == 2
        assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert response_json[STD_JSON.MESSAGE] == REGISTER_FAILURE.UNABLE_TO_REGISTER
        assert len(response_json[STD_JSON.ERRORS]) == 1
        assert response_json[STD_JSON.ERRORS][REGISTER_FORM.USERNAME] == [
            REGISTER_FAILURE.INVALID_INPUT
        ]


def test_register_user_form_short_username_csrf(load_register_page):
    """
    GIVEN an unregistered user
    WHEN "/register" is POST'd with a too short username
    THEN ensure registration does not occur
    """

    client, csrf_token_string = load_register_page
    # Only password confirm
    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        data={
            REGISTER_FORM.CSRF_TOKEN: csrf_token_string,
            REGISTER_FORM.USERNAME: "a" * (USER_CONSTANTS.MIN_USERNAME_LENGTH - 1),
            REGISTER_FORM.EMAIL: "FakeUser@Name123.com",
            REGISTER_FORM.CONFIRM_EMAIL: "FakeUser@Name123.com",
            REGISTER_FORM.PASSWORD: "FakeUser@Name123.com",
            REGISTER_FORM.CONFIRM_PASSWORD: "FakeUser@Name123.com",
        },
    )

    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.REGISTER)
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == REGISTER_FAILURE.UNABLE_TO_REGISTER
    assert len(response_json[STD_JSON.ERRORS]) == 1
    assert (
        f"Field must be between {USER_CONSTANTS.MIN_USERNAME_LENGTH} and {USER_CONSTANTS.MAX_USERNAME_LENGTH} characters long."
        in response_json[STD_JSON.ERRORS][REGISTER_FORM.USERNAME]
    )


def test_register_user_form_no_csrf(load_register_page):
    """
    GIVEN an unregistered user
    WHEN "/register" is POST'd without a CSRF
    THEN ensure an invalid CSRF token error is sent
    """

    client, _ = load_register_page
    # Only password confirm
    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        data={
            REGISTER_FORM.CSRF_TOKEN: "",
            REGISTER_FORM.USERNAME: "",
            REGISTER_FORM.EMAIL: "",
            REGISTER_FORM.CONFIRM_EMAIL: "",
            REGISTER_FORM.PASSWORD: "",
            REGISTER_FORM.CONFIRM_PASSWORD: "FakeUserName123",
        },
    )

    assert response.status_code == 403
    assert response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in response.data
