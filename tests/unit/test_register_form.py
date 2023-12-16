from flask import url_for, request

from src.utils import strings as U4I_STRINGS

REGISTER_FORM = U4I_STRINGS.REGISTER_FORM
STD_JSON = U4I_STRINGS.STD_JSON_RESPONSE
REGISTER_FAILURE = U4I_STRINGS.USER_FAILURE


def test_register_user_form_only_username_csrf(load_register_page):
    """
    GIVEN an unregistered user
    WHEN "/register" is POST'd with only username and CSRF
    THEN ensure registration does not occur
    """

    client, csrf_token_string = load_register_page
    response = client.post(
        url_for("users.register_user"),
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
    assert request.path == url_for("users.register_user")
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

    INVALID_EMAIL_ADDRESS = ["Invalid email address."]
    client, csrf_token_string = load_register_page
    response = client.post(
        "/register",
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
    assert request.path == url_for("users.register_user")
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == REGISTER_FAILURE.UNABLE_TO_REGISTER
    assert len(response_json[STD_JSON.ERRORS]) == 5

    for input_key in REGISTER_FORM.REGISTER_FORM_KEYS:
        form_error = response_json[STD_JSON.ERRORS][input_key]
        if input_key == REGISTER_FORM.EMAIL:
            assert form_error == INVALID_EMAIL_ADDRESS
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
        "/register",
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
    assert request.path == url_for("users.register_user")
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
        "/register",
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
    assert request.path == url_for("users.register_user")
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == REGISTER_FAILURE.UNABLE_TO_REGISTER
    assert len(response_json[STD_JSON.ERRORS]) == 5

    for input_key in REGISTER_FORM.REGISTER_FORM_KEYS:
        if input_key == REGISTER_FORM.CONFIRM_EMAIL:
            assert response_json[STD_JSON.ERRORS][input_key] == [
                "Field must be equal to email."
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
        "/register",
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
    assert request.path == url_for("users.register_user")
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == REGISTER_FAILURE.UNABLE_TO_REGISTER
    assert len(response_json[STD_JSON.ERRORS]) == 5

    for input_key in REGISTER_FORM.REGISTER_FORM_KEYS:
        if input_key == REGISTER_FORM.PASSWORD:
            assert response_json[STD_JSON.ERRORS][input_key] == [
                "Field must be between 12 and 64 characters long."
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
        "/register",
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
    assert request.path == url_for("users.register_user")
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
        "/register",
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
    assert request.path == url_for("users.register_user")
    response_json = response.json

    assert int(response_json[STD_JSON.ERROR_CODE]) == 2
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == REGISTER_FAILURE.UNABLE_TO_REGISTER
    assert len(response_json[STD_JSON.ERRORS]) == 5

    for input_key in REGISTER_FORM.REGISTER_FORM_KEYS:
        if input_key == REGISTER_FORM.CONFIRM_PASSWORD:
            assert response_json[STD_JSON.ERRORS][input_key] == [
                "Field must be equal to password."
            ]
        else:
            assert (
                response_json[STD_JSON.ERRORS][input_key]
                == REGISTER_FAILURE.FIELD_REQUIRED
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
        "/register",
        data={
            REGISTER_FORM.CSRF_TOKEN: "",
            REGISTER_FORM.USERNAME: "",
            REGISTER_FORM.EMAIL: "",
            REGISTER_FORM.CONFIRM_EMAIL: "",
            REGISTER_FORM.PASSWORD: "",
            REGISTER_FORM.CONFIRM_PASSWORD: "FakeUserName123",
        },
    )

    assert response.status_code == 400
    assert request.path == url_for("users.register_user")
    assert b"<p>The CSRF token is missing.</p>" in response.data
