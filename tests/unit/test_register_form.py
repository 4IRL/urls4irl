import pytest
from flask import url_for, request


def test_register_user_form_only_username_csrf(load_register_page):
    """
    GIVEN an unregistered user
    WHEN "/register" is POST'd with only username and CSRF
    THEN ensure registration does not occur
    """

    client, csrf_token_string = load_register_page
    response = client.post(
        "/register",
        data={
            "csrf_token": csrf_token_string,
            "username": "FakeUserName123",
            "email": "",
            "confirm_email": "",
            "password": "",
            "confirm_password": "",
        },
    )

    assert response.status_code == 200
    assert request.path == url_for("users.register_user")
    assert b"<span>This field is required.</span>" in response.data


def test_register_user_form_only_invalid_email_csrf(load_register_page):
    """
    GIVEN an unregistered user
    WHEN "/register" is POST'd with only invalid email and CSRF
    THEN ensure registration does not occur due to missing fields and invalid email
    """

    client, csrf_token_string = load_register_page
    response = client.post(
        "/register",
        data={
            "csrf_token": csrf_token_string,
            "username": "",
            "email": "FakeUserName123",
            "confirm_email": "",
            "password": "",
            "confirm_password": "",
        },
    )

    assert response.status_code == 200
    assert request.path == url_for("users.register_user")
    assert b"<span>This field is required.</span>" in response.data
    assert b"<span>Invalid email address.</span>" in response.data


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
            "csrf_token": csrf_token_string,
            "username": "",
            "email": "FakeUserName123@email.com",
            "confirm_email": "",
            "password": "",
            "confirm_password": "",
        },
    )

    assert response.status_code == 200
    assert request.path == url_for("users.register_user")
    assert b"<span>This field is required.</span>" in response.data


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
            "csrf_token": csrf_token_string,
            "username": "",
            "email": "",
            "confirm_email": "FakeUserName123@email.com",
            "password": "",
            "confirm_password": "",
        },
    )

    assert response.status_code == 200
    assert request.path == url_for("users.register_user")
    assert b"<span>This field is required.</span>" in response.data
    assert b"<span>Field must be equal to email.</span>" in response.data


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
            "csrf_token": csrf_token_string,
            "username": "",
            "email": "",
            "confirm_email": "",
            "password": "FakeUser123",
            "confirm_password": "",
        },
    )

    assert response.status_code == 200
    assert request.path == url_for("users.register_user")
    assert b"<span>This field is required.</span>" in response.data
    assert (
        b"<span>Field must be between 12 and 64 characters long.</span>"
        in response.data
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
            "csrf_token": csrf_token_string,
            "username": "",
            "email": "",
            "confirm_email": "",
            "password": "FakeUserName123",
            "confirm_password": "",
        },
    )

    assert response.status_code == 200
    assert request.path == url_for("users.register_user")
    assert b"<span>This field is required.</span>" in response.data


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
            "csrf_token": csrf_token_string,
            "username": "",
            "email": "",
            "confirm_email": "",
            "password": "",
            "confirm_password": "FakeUserName123",
        },
    )

    assert response.status_code == 200
    assert request.path == url_for("users.register_user")
    assert b"<span>This field is required.</span>" in response.data
    assert b"<span>Field must be equal to password.</span>" in response.data


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
            "csrf_token": "",
            "username": "",
            "email": "",
            "confirm_email": "",
            "password": "",
            "confirm_password": "FakeUserName123",
        },
    )

    assert response.status_code == 400
    assert request.path == url_for("users.register_user")
    assert b"<p>The CSRF token is missing.</p>" in response.data
