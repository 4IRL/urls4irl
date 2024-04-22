from flask import url_for, request
import pytest

from src.utils.all_routes import ROUTES
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.splash_form_strs import LOGIN_FORM
from src.utils.strings.user_strs import USER_FAILURE as LOGIN_FAILURE

pytestmark = pytest.mark.unit

def test_login_no_password(load_login_page):
    """
    GIVEN an unregistered user
    WHEN "/login" is POST'd with empty password field form data
    THEN ensure login does not occur
    """

    client, csrf_token_string = load_login_page

    # No password
    response = client.post(
        url_for(ROUTES.SPLASH.LOGIN),
        data={
            LOGIN_FORM.CSRF_TOKEN: csrf_token_string,
            LOGIN_FORM.USERNAME: "FakeUserName123",
        },
    )

    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.LOGIN)
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == LOGIN_FAILURE.UNABLE_TO_LOGIN
    assert len(response_json[STD_JSON.ERRORS]) == 2
    assert response_json[STD_JSON.ERRORS][LOGIN_FORM.USERNAME] == [
        LOGIN_FAILURE.USER_NOT_EXIST
    ]
    assert (
        response_json[STD_JSON.ERRORS][LOGIN_FORM.PASSWORD]
        == LOGIN_FAILURE.FIELD_REQUIRED
    )


def test_login_no_username(load_login_page):
    """
    GIVEN an unregistered user
    WHEN "/login" is POST'd with empty username field form data
    THEN ensure login does not occur
    """

    client, csrf_token_string = load_login_page

    # No username
    response = client.post(
        url_for(ROUTES.SPLASH.LOGIN),
        data={
            LOGIN_FORM.CSRF_TOKEN: csrf_token_string,
            LOGIN_FORM.PASSWORD: "FakeUserName123",
        },
    )

    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.LOGIN)
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == LOGIN_FAILURE.UNABLE_TO_LOGIN
    assert len(response_json[STD_JSON.ERRORS]) == 1

    for input_key in LOGIN_FORM.LOGIN_FORM_KEYS:
        if input_key != LOGIN_FORM.USERNAME:
            continue
        assert response_json[STD_JSON.ERRORS][input_key] == LOGIN_FAILURE.FIELD_REQUIRED


def test_login_no_username_or_password(load_login_page):
    """
    GIVEN an unregistered user
    WHEN "/login" is POST'd with empty password and username field form data
    THEN ensure login does not occur
    """

    client, csrf_token_string = load_login_page

    # No username or password
    response = client.post(
        url_for(ROUTES.SPLASH.LOGIN),
        data={
            LOGIN_FORM.CSRF_TOKEN: csrf_token_string,
        },
    )

    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.LOGIN)
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == LOGIN_FAILURE.UNABLE_TO_LOGIN
    assert len(response_json[STD_JSON.ERRORS]) == 2

    for input_key in LOGIN_FORM.LOGIN_FORM_KEYS:
        if input_key == LOGIN_FORM.CSRF_TOKEN:
            continue
        assert response_json[STD_JSON.ERRORS][input_key] == LOGIN_FAILURE.FIELD_REQUIRED


def test_login_no_csrf(load_login_page):
    """
    GIVEN an unregistered user
    WHEN "/login" is POST'd with empty field form data, or no CSRF token
    THEN ensure login does not occur
    """

    client, _ = load_login_page

    # Without CSRF token
    response = client.post("/login", data={})

    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.LOGIN)
    assert b"<p>The CSRF token is missing.</p>" in response.data
