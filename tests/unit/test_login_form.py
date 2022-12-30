import pytest
from flask import url_for, request

def test_login_no_password(load_login_page):
    """
    GIVEN an unregistered user
    WHEN "/login" is POST'd with empty password field form data
    THEN ensure login does not occur
    """

    client, csrf_token_string = load_login_page

    # No password
    response = client.post("/login", data={
        "csrf_token": csrf_token_string,
        "username": "FakeUserName123",
    })

    assert response.status_code == 200
    assert request.path == url_for("users.login")
    assert b'<span>This field is required.</span>' in response.data

def test_login_no_username(load_login_page):
    """
    GIVEN an unregistered user
    WHEN "/login" is POST'd with empty username field form data
    THEN ensure login does not occur
    """

    client, csrf_token_string = load_login_page

    # No username
    response = client.post("/login", data={
        "csrf_token": csrf_token_string,
        "password": "FakeUserName123",
    })

    assert response.status_code == 200
    assert request.path == url_for("users.login")
    assert b'<span>This field is required.</span>' in response.data

def test_login_no_username_or_password(load_login_page):
    """
    GIVEN an unregistered user
    WHEN "/login" is POST'd with empty password and username field form data
    THEN ensure login does not occur
    """

    client, csrf_token_string = load_login_page

    # No username or password
    response = client.post("/login", data={
        "csrf_token": csrf_token_string,
    })

    assert response.status_code == 200
    assert request.path == url_for("users.login")
    assert b'<span>This field is required.</span>' in response.data


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
    assert request.path == url_for("users.login")
    assert b'<p>The CSRF token is missing.</p>' in response.data
