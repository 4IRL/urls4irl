from flask import url_for
from flask_login import current_user

from src import db
from src.models import User, ForgotPassword, verify_token
from src.utils.all_routes import ROUTES
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.reset_password_strs import RESET_PASSWORD

NEW_PASSWORD = "NEW_PASSWORD!"


def test_valid_token_receives_reset_password_form(user_attempts_reset_password):
    """
    GIVEN a user trying to reset their password
    WHEN they click on the URL with their associated password reset token
    THEN ensure that the splash page is called with the modal call for Password Reset included in the data
    """
    _, client, _, reset_token, _ = user_attempts_reset_password

    reset_response = client.get(url_for(ROUTES.SPLASH.RESET_PASSWORD, token=reset_token))

    # JS AJAX call to modal that contains reset password form
    assert RESET_PASSWORD.RESET_PASSWORD_MODAL_CALL.encode() in reset_response.data

    assert IDENTIFIERS.SPLASH_PAGE.encode() in reset_response.data
    assert reset_response.status_code == 200


def test_reset_password_token_can_expire(app, register_first_user):
    """
    GIVEN a reset password JWT token
    WHEN the token is expired
    THEN ensure the server can verify the token is expired
    """
    registered_user, _ = register_first_user

    with app.app_context():
        user: User = User.query.filter(
            User.email == registered_user[RESET_PASSWORD.EMAIL]
        ).first()
        quick_expiring_token = user.get_password_reset_token(expires_in=0)

        assert verify_token(
            quick_expiring_token, RESET_PASSWORD.RESET_PASSWORD_KEY
        ) == (
            None,
            True,
        )


def test_expired_token_deletes_object_and_redirects(
    app, load_login_page, register_first_user
):
    """
    GIVEN a user with an expired reset password token
    WHEN they click on the expired token in their email
    THEN ensure that the ForgotPassword object is deleted, and they are redirected to the splash page
    """
    registered_user, _ = register_first_user
    client, _ = load_login_page

    with app.app_context():
        user: User = User.query.filter(
            User.email == registered_user[RESET_PASSWORD.EMAIL]
        ).first()
        expired_token = user.get_password_reset_token(expires_in=0)
        password_reset = ForgotPassword(reset_token=expired_token)
        password_reset.user = user
        db.session.add(password_reset)
        db.session.commit()

    reset_response = client.get(
        url_for(ROUTES.SPLASH.RESET_PASSWORD, token=expired_token), follow_redirects=True
    )

    assert len(reset_response.history) == 1
    redirected_response = reset_response.history[-1]
    assert redirected_response.status_code == 302
    assert redirected_response.location == url_for("splash.splash_page")
    assert reset_response.status_code == 200
    assert IDENTIFIERS.SPLASH_PAGE.encode() in reset_response.data

    with app.app_context():
        assert (
            len(
                ForgotPassword.query.filter(
                    ForgotPassword.reset_token == expired_token
                ).all()
            )
            == 0
        )


def test_invalid_reset_password_token(user_attempts_reset_password):
    """
    GIVEN an attempt to access the reset password URL
    WHEN an invalid token is included in the URL
    THEN ensure that the server responds with a 404
    """
    app, client, _, _, _ = user_attempts_reset_password

    invalid_token = "AAA"
    # Verify invalid token is invalid
    with app.app_context():
        assert (
            len(
                ForgotPassword.query.filter(
                    ForgotPassword.reset_token == invalid_token
                ).all()
            )
            == 0
        )

    reset_response = client.get(url_for(ROUTES.SPLASH.RESET_PASSWORD, token=invalid_token))

    assert reset_response.status_code == 404


def test_not_email_validated_user_with_password_reset_token_fails(
    app, load_login_page, register_first_user_without_email_validation
):
    """
    GIVEN a non-email-validated user who somehow generates a ForgotPassword object with a reset token
    WHEN they perform a GET on the reset password URL with their newly created reset token
    THEN ensure that the ForgotPassword object gets deleted and the server returns a 404 since they
        are not email validated
    """
    registered_user, _ = register_first_user_without_email_validation
    client, _ = load_login_page

    with app.app_context():
        user: User = User.query.filter(
            User.email == registered_user[RESET_PASSWORD.EMAIL]
        ).first()
        reset_token = user.get_password_reset_token()
        new_password_reset = ForgotPassword(reset_token=reset_token)
        new_password_reset.user = user
        db.session.add(new_password_reset)
        db.session.commit()

    reset_password_response = client.get(url_for(ROUTES.SPLASH.RESET_PASSWORD, token=reset_token))

    assert reset_password_response.status_code == 404

    with app.app_context():
        assert (
            len(
                ForgotPassword.query.filter(
                    ForgotPassword.reset_token == reset_token
                ).all()
            )
            == 0
        )


def test_matching_user_reset_token_not_in_database_fails(user_attempts_reset_password):
    """
    GIVEN a user who has a second token that corresponds to them but is not part of their ForgotPassword object
    WHEN they perform a GET on the reset password URL with their secondary token
    THEN ensure the server responds with a 404 and does not delete their primary ForgotPassword object
    """
    app, client, new_user, correct_token, _ = user_attempts_reset_password

    with app.app_context():
        user: User = User.query.filter(
            User.email == new_user[RESET_PASSWORD.EMAIL]
        ).first()
        invalid_token = user.get_password_reset_token()

    reset_password_response = client.get(
        url_for(ROUTES.SPLASH.RESET_PASSWORD, token=invalid_token)
    )

    assert reset_password_response.status_code == 404

    with app.app_context():
        assert (
            len(
                ForgotPassword.query.filter(
                    ForgotPassword.reset_token == correct_token
                ).all()
            )
            == 1
        )


def test_password_reset_object_expires_after_one_hour(
    user_attempts_reset_password_one_hour_old,
):
    """
    GIVEN a user with a ForgotPassword object of more than 1 hour old
    WHEN they try to access the token in their email to reset their password
    THEN ensure the client responds with a 404
    """
    _, client, _, reset_token, _ = user_attempts_reset_password_one_hour_old

    reset_password_response = client.get(url_for(ROUTES.SPLASH.RESET_PASSWORD, token=reset_token))

    assert reset_password_response.status_code == 404


def test_password_reset_without_csrf_fails(user_attempts_reset_password):
    """
    GIVEN a user trying to reset their password
    WHEN they submit a reset password form with a missing CSRF token
    THEN ensure server responds indicating a missing CSRF token and status code 400
    """
    _, client, _, reset_token, _ = user_attempts_reset_password

    reset_response = client.post(
        url_for(ROUTES.SPLASH.RESET_PASSWORD, token=reset_token),
        data={
            RESET_PASSWORD.NEW_PASSWORD_FIELD: NEW_PASSWORD,
            RESET_PASSWORD.CONFIRM_NEW_PASSWORD_FIELD: NEW_PASSWORD,
        },
    )

    # Assert invalid response code
    assert reset_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in reset_response.data


def test_password_reset_without_equal_passwords_fails(user_attempts_reset_password):
    """
    GIVEN a user trying to reset their password
    WHEN they submit a reset password form with the password and confirm password fields not equal
    THEN ensure server responds with form errors indicating the passwords aren't equal, and
        status code 400

    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: RESET_PASSWORD.RESET_PASSWORD_INVALID,
        STD_JSON.ERROR_CODE: 2
        STD_JSON.ERRORS: {
            RESET_PASSWORD.CONFIRM_NEW_PASSWORD_FIELD: [RESET_PASSWORD.PASSWORDS_NOT_IDENTICAL,]
        }
    }
    """
    app, client, new_user, reset_token, csrf_token = user_attempts_reset_password

    reset_response = client.post(
        url_for(ROUTES.SPLASH.RESET_PASSWORD, token=reset_token),
        data={
            RESET_PASSWORD.NEW_PASSWORD_FIELD: NEW_PASSWORD,
            RESET_PASSWORD.CONFIRM_NEW_PASSWORD_FIELD: NEW_PASSWORD + "AAA",
            RESET_PASSWORD.CSRF_TOKEN: csrf_token,
        },
    )

    assert reset_response.status_code == 400
    reset_response_json = reset_response.json
    assert reset_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        reset_response_json[STD_JSON.MESSAGE] == RESET_PASSWORD.RESET_PASSWORD_INVALID
    )
    assert int(reset_response_json[STD_JSON.ERROR_CODE]) == 2
    assert (
        reset_response_json[STD_JSON.ERRORS][RESET_PASSWORD.CONFIRM_NEW_PASSWORD_FIELD][
            -1
        ]
        == RESET_PASSWORD.PASSWORDS_NOT_IDENTICAL
    )

    with app.app_context():
        user: User = User.query.filter(
            User.email == new_user[RESET_PASSWORD.EMAIL]
        ).first()
        assert user.is_password_correct(new_user[RESET_PASSWORD.PASSWORD])


def test_password_reset_with_identical_to_previous_password_fails(
    user_attempts_reset_password,
):
    """
    GIVEN a user trying to reset their password
    WHEN they submit a reset password form with the password and confirm password equal to their previous passwords
    THEN ensure server responds indicating the password is same as old password, and a status code of 400

    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: RESET_PASSWORD.SAME_PASSWORD,
        STD_JSON.ERROR_CODE: 1
    }
    """
    _, client, new_user, reset_token, csrf_token = user_attempts_reset_password

    reset_response = client.post(
        url_for(ROUTES.SPLASH.RESET_PASSWORD, token=reset_token),
        data={
            RESET_PASSWORD.NEW_PASSWORD_FIELD: new_user[RESET_PASSWORD.PASSWORD],
            RESET_PASSWORD.CONFIRM_NEW_PASSWORD_FIELD: new_user[
                RESET_PASSWORD.PASSWORD
            ],
            RESET_PASSWORD.CSRF_TOKEN: csrf_token,
        },
    )

    assert reset_response.status_code == 400
    reset_response_json = reset_response.json
    assert reset_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert reset_response_json[STD_JSON.MESSAGE] == RESET_PASSWORD.SAME_PASSWORD
    assert int(reset_response_json[STD_JSON.ERROR_CODE]) == 1


def test_valid_new_password_changes_password_and_deletes_forgot_password_object(
    user_attempts_reset_password,
):
    """
    GIVEN a user trying to reset their password
    WHEN they submit a valid reset password form
    THEN ensure server responds indicating the password is changed, status code of 200, the
        ForgotPassword object is deleted from the database, and no user is logged in

    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: RESET_PASSWORD.PASSWORD_RESET,
    }
    """
    app, client, new_user, reset_token, csrf_token = user_attempts_reset_password

    reset_response = client.post(
        url_for(ROUTES.SPLASH.RESET_PASSWORD, token=reset_token),
        data={
            RESET_PASSWORD.NEW_PASSWORD_FIELD: NEW_PASSWORD,
            RESET_PASSWORD.CONFIRM_NEW_PASSWORD_FIELD: NEW_PASSWORD,
            RESET_PASSWORD.CSRF_TOKEN: csrf_token,
        },
    )

    assert reset_response.status_code == 200
    reset_response_json = reset_response.json
    assert reset_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert reset_response_json[STD_JSON.MESSAGE] == RESET_PASSWORD.PASSWORD_RESET

    with app.app_context():
        user: User = User.query.filter(
            User.email == new_user[RESET_PASSWORD.EMAIL]
        ).first()
        assert user.is_password_correct(NEW_PASSWORD) and not user.is_password_correct(
            new_user[RESET_PASSWORD.PASSWORD]
        )
        assert (
            len(
                ForgotPassword.query.filter(
                    ForgotPassword.reset_token == reset_token
                ).all()
            )
            == 0
        )

    # Ensure no one is logged in
    assert current_user.get_id() is None
    assert current_user.is_active is False
