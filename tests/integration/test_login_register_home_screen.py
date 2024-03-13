from flask import url_for, request

LOGIN_URL = "splash.login"
REGISTER_URL = "splash.register_user"
SPLASH_URL = "splash.splash_page"


def test_get_home_screen_not_logged_in(app_with_server_name, client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/" is requested (GET)
    THEN ensure redirect to splash page
    """
    with client:
        with app_with_server_name.app_context():
            response = client.get(url_for(SPLASH_URL), follow_redirects=True)

        # Hits splash page
        assert response.status_code == 200
        assert (
            bytes("A simple, clean way to permanently save and share URLs.", "utf-8")
            in response.data
        )


def test_post_home_screen_not_logged_in(app_with_server_name, client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/" is requested (POST)
    THEN check 405 occurs and user is not redirected
    """
    with client:
        with app_with_server_name.app_context():
            response = client.post(url_for(SPLASH_URL), follow_redirects=True)

        assert response.status_code == 405
        assert len(response.history) == 0
        assert request.path != url_for(LOGIN_URL)


def test_get_login_screen_not_logged_in(app_with_server_name, client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/login" is requested (GET)
    THEN ensure page contains Login form data, and successful page load
    """
    with client:
        with app_with_server_name.app_context():
            response = client.get(url_for(LOGIN_URL))

        assert response.status_code == 200

        assert (
            b'<input class="form-control login-register-form-group" id="username" name="username" required type="text" value="">'
            in response.data
        )
        assert (
            b'<input class="form-control login-register-form-group" id="password" name="password" required type="password" value="">'
            in response.data
        )
        assert (
            b'<input id="csrf_token" name="csrf_token" type="hidden" value='
            in response.data
        )

        assert request.path == url_for(LOGIN_URL)

def test_get_register_screen_not_logged_in(app_with_server_name, client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/register" is requested (GET)
    THEN ensure page contains Register form data, and successful page load
    """
    with client:
        with app_with_server_name.app_context():
            response = client.get(url_for(REGISTER_URL))

        assert response.status_code == 200

        assert (
            b'<input class="form-control login-register-form-group" id="username" maxlength="20" minlength="4" name="username" required type="text" value="">'
            in response.data
        )
        assert (
            b'<input class="form-control login-register-form-group" id="email" name="email" required type="text" value="">'
            in response.data
        )
        assert (
            b'<input class="form-control login-register-form-group" id="confirm_email" name="confirm_email" required type="text" value="">'
            in response.data
        )
        assert (
            b'<input class="form-control login-register-form-group" id="password" maxlength="64" minlength="12" name="password" required type="password" value="">'
            in response.data
        )
        assert (
            b'<input class="form-control login-register-form-group" id="confirm_password" name="confirm_password" required type="password" value="">'
            in response.data
        )
        assert (
            b'<input id="csrf_token" name="csrf_token" type="hidden" value='
            in response.data
        )

        assert request.path == url_for(REGISTER_URL)
