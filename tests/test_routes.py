import pytest, re
from urls4irl import create_app
from flask import url_for, request

@pytest.fixture()
def app():
    app = create_app()

    yield app

@pytest.fixture()
def client(app):
    return app.test_client()

def test_home_screen(client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/" is requested (GET)
    THEN ensure redirect to "login"
    """
    with client:
        response = client.get("/", follow_redirects = True)
        
        # Currently redirects to login page, no splash page
        assert response.history[0].status_code == 302
        assert response.status_code == 200
        assert request.path == url_for("users.login")
        assert len(response.history) == 1

def test_login_screen(client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/login" is requested (GET)
    THEN ensure page contains Login form data, and successful page load
    """
    with client:
        response = client.get("/login")

        assert response.status_code == 200

        assert b'<input class="form-control form-control-lg" id="username" name="username" required type="text" value="">' in response.data
        assert b'<input class="form-control form-control-lg" id="password" name="password" required type="password" value="">' in response.data
        assert b'<input id="csrf_token" name="csrf_token" type="hidden" value=' in response.data

        assert request.path == url_for("users.login")

def test_register_screen(client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/register" is requested (GET)
    THEN ensure page contains Register form data, and successful page load
    """
    with client:
        response = client.get("/register")

        assert response.status_code == 200

        assert b'<input class="form-control form-control-lg" id="username" maxlength="20" minlength="4" name="username" required type="text" value="">' in response.data
        assert b'<input class="form-control form-control-lg" id="email" name="email" required type="text" value="">' in response.data
        assert b'<input class="form-control form-control-lg" id="confirm_email" name="confirm_email" required type="text" value="">' in response.data
        assert b'<input class="form-control form-control-lg" id="password" maxlength="64" minlength="12" name="password" required type="password" value="">' in response.data
        assert b'<input class="form-control form-control-lg" id="confirm_password" name="confirm_password" required type="password" value="">' in response.data
        assert b'<input id="csrf_token" name="csrf_token" type="hidden" value=' in response.data

        assert request.path == url_for("users.register_user")

def test_login_unregisterd_user(client):
    """
    GIVEN an unregistered user
    WHEN "/login" is POST'd with filled in form data
    THEN ensure login does not occur
    """
    with client:
        # Get the CSRF token
        get_response = client.get("/login")
        
        csrf_token_str = get_csrf_token(get_response.get_data())

        response = client.post("/login", data={
            "csrf_token": csrf_token_str,
            "username": "FakeUserName123",
            "password": "FakePassword123"
        })

        #TODO: Check for error message of some kind here eventually

        assert response.status_code == 400
        assert request.path == url_for("users.login")

def test_login_invalid_form(client):
    """
    GIVEN an unregistered user
    WHEN "/login" is POST'd with empty field form data, or no CSRF token
    THEN ensure login does not occur
    """
    with client:
        # Get the CSRF token
        get_response = client.get("/login")
        
        csrf_token_str = get_csrf_token(get_response.get_data())

        # No password
        response = client.post("/login", data={
            "csrf_token": csrf_token_str,
            "username": "FakeUserName123",
        })

        assert response.status_code == 200
        assert request.path == url_for("users.login")
        assert b'<span>This field is required.</span>' in response.data

        # No username
        response = client.post("/login", data={
            "csrf_token": csrf_token_str,
            "password": "FakeUserName123",
        })

        assert response.status_code == 200
        assert request.path == url_for("users.login")
        assert b'<span>This field is required.</span>' in response.data

        # No username or password
        response = client.post("/login", data={
            "csrf_token": csrf_token_str,
        })

        assert response.status_code == 200
        assert request.path == url_for("users.login")
        assert b'<span>This field is required.</span>' in response.data

        # Without CSRF token
        response = client.post("/login", data={})

        assert response.status_code == 400
        assert request.path == url_for("users.login")
        assert b'<p>The CSRF token is missing.</p>' in response.data


def test_register_user_invalid_form(client):
    """
    GIVEN an unregistered user
    WHEN "/register" is POST'd with invalid form data or missing CSRF token
    THEN ensure login does not occur
    """
    with client:
        # Get the CSRF token
        get_response = client.get("/register")
        
        csrf_token_str = get_csrf_token(get_response.get_data())

        # Only username
        response = client.post("/register", data={
            "csrf_token": csrf_token_str,
            "username": "FakeUserName123",
            "email": "",
            "confirm_email": "",
            "password": "",
            "confirm_password": ""
        })

        assert response.status_code == 200
        assert request.path == url_for("users.register_user")
        assert b'<span>This field is required.</span>' in response.data

        # Only email and invalid email
        response = client.post("/register", data={
            "csrf_token": csrf_token_str,
            "username": "",
            "email": "FakeUserName123",
            "confirm_email": "",
            "password": "",
            "confirm_password": ""
        })

        assert response.status_code == 200
        assert request.path == url_for("users.register_user")
        assert b'<span>This field is required.</span>' in response.data
        assert b'<span>Invalid email address.</span>' in response.data

        # Only email and valid email
        response = client.post("/register", data={
            "csrf_token": csrf_token_str,
            "username": "",
            "email": "FakeUserName123@email.com",
            "confirm_email": "",
            "password": "",
            "confirm_password": ""
        })

        assert response.status_code == 200
        assert request.path == url_for("users.register_user")
        assert b'<span>This field is required.</span>' in response.data

        # Only confirm email and no email
        response = client.post("/register", data={
            "csrf_token": csrf_token_str,
            "username": "",
            "email": "",
            "confirm_email": "FakeUserName123@email.com",
            "password": "",
            "confirm_password": ""
        })

        assert response.status_code == 200
        assert request.path == url_for("users.register_user")
        assert b'<span>This field is required.</span>' in response.data
        assert b'<span>Field must be equal to email.</span>' in response.data

        # Only password, short password
        response = client.post("/register", data={
            "csrf_token": csrf_token_str,
            "username": "",
            "email": "",
            "confirm_email": "",
            "password": "FakeUser123",
            "confirm_password": ""
        })

        assert response.status_code == 200
        assert request.path == url_for("users.register_user")
        assert b'<span>This field is required.</span>' in response.data
        assert b'<span>Field must be between 12 and 64 characters long.</span>' in response.data

        # Only password, valid password
        response = client.post("/register", data={
            "csrf_token": csrf_token_str,
            "username": "",
            "email": "",
            "confirm_email": "",
            "password": "FakeUserName123",
            "confirm_password": ""
        })

        assert response.status_code == 200
        assert request.path == url_for("users.register_user")
        assert b'<span>This field is required.</span>' in response.data

        # Only password confirm
        response = client.post("/register", data={
            "csrf_token": csrf_token_str,
            "username": "",
            "email": "",
            "confirm_email": "",
            "password": "",
            "confirm_password": "FakeUserName123"
        })

        assert response.status_code == 200
        assert request.path == url_for("users.register_user")
        assert b'<span>This field is required.</span>' in response.data
        assert b'<span>Field must be equal to password.</span>' in response.data

        # Without CSRF token
        response = client.post("/register", data={})

        assert response.status_code == 400
        assert request.path == url_for("users.register_user")
        assert b'<p>The CSRF token is missing.</p>' in response.data


""" 
###############################################################################
          ***********************************************************
                        ---- UTILITY FUNCTIONS ---- 
          ***********************************************************
############################################################################### 
"""

def get_csrf_token(html_page: bytes) -> str:
    """
    Reads in the html byte response from a GET of a page, finds the CSRF token using regex, returns it.

    Args:
        html_page (bytes): Byte data of html page

    Returns:
        str: CSRF from parsed HTML page
    """
    all_html_data = str([val for val in html_page.splitlines() if b'name="csrf_token"' in val][0])
    
    result = re.search('<input id="csrf_token" name="csrf_token" type="hidden" value="(.*)">', all_html_data)
    return result.group(1)
