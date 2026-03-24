from datetime import timedelta
from typing import Generator, Tuple

from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend import db
from backend.models.email_validations import Email_Validations
from backend.models.forgot_passwords import Forgot_Passwords
from backend.models.users import Users
from tests.utils_for_test import get_csrf_token
from backend.utils.all_routes import ROUTES
from backend.utils.strings import model_strs, reset_password_strs
from backend.utils.strings.splash_form_strs import REGISTER_FORM
from tests.models_for_test import valid_user_1


def register_json(user_data: dict) -> dict:
    """Build the JSON payload for a register request from a user data dict."""
    return {
        REGISTER_FORM.USERNAME: user_data[REGISTER_FORM.USERNAME],
        REGISTER_FORM.EMAIL: user_data[REGISTER_FORM.EMAIL],
        REGISTER_FORM.CONFIRM_EMAIL: user_data[REGISTER_FORM.CONFIRM_EMAIL],
        REGISTER_FORM.PASSWORD: user_data[REGISTER_FORM.PASSWORD],
        REGISTER_FORM.CONFIRM_PASSWORD: user_data[REGISTER_FORM.CONFIRM_PASSWORD],
    }


@pytest.fixture
def register_first_user_without_email_validation(
    app: Flask,
) -> Generator[Tuple[dict[str, str | None], Users], None, None]:
    """
    Registers a User model with.
    See 'models_for_test.py' for model information.
    The newly registered User's will have ID == 1

    Args:
        app (Flask): The Flask client for providing an app context

    Yields:
        (dict): The information used to generate the new User model
        (User): The newly generated User model
    """
    # Add a new user for testing
    with app.app_context():
        new_user = Users(
            username=valid_user_1[model_strs.USERNAME],
            email=valid_user_1[model_strs.EMAIL].lower(),
            plaintext_password=valid_user_1[model_strs.PASSWORD],
        )

        new_email_validation = Email_Validations(
            validation_token=new_user.get_email_validation_token()
        )
        new_user.email_confirm = new_email_validation

        db.session.add(new_user)
        db.session.commit()

    yield valid_user_1, new_user


@pytest.fixture
def user_attempts_reset_password(
    app: Flask,
    register_first_user: Tuple[dict[str, str | None], Users],
    load_login_page: Tuple[FlaskClient, str],
) -> Generator[Tuple[Flask, FlaskClient, dict[str, str | None], str, str], None, None]:
    """
    After registering a new user, the user forgets their password
    and performs the forgot-password sequence, which would send a user an email with
    a unique token identifying them, that expires after a given set of time.
    The reset token is also stored in the database in the Forgot_Passwords object

    Args:
        app (Flask): The Flask client providing an app context
        register_first_user (pytest fixture): Registers the user with ID == 1
        load_login_page (pytest fixture): Brings user to login page and yields test client

    Yields:
        (Flask): The Flask client for providing an app context
        (FlaskLoginClient): Flask client
        (dict): The user data who forgot their password
        (str): The reset token associated with the user's current reset-password attempt
    """
    new_user, _ = register_first_user
    client, _ = load_login_page

    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    client.post(
        url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE),
        json={
            reset_password_strs.FORGOT_PASSWORD.EMAIL: new_user[
                reset_password_strs.FORGOT_PASSWORD.EMAIL
            ],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    with app.app_context():
        user_to_reset: Users = Users.query.filter(
            Users.email == new_user[reset_password_strs.FORGOT_PASSWORD.EMAIL].lower()
        ).first()
        password_reset_obj: Forgot_Passwords = Forgot_Passwords.query.filter(
            Forgot_Passwords.user_id == user_to_reset.id
        ).first()
        reset_token = password_reset_obj.reset_token
        user_to_reset.password_reset = password_reset_obj
        db.session.commit()

    yield app, client, new_user, reset_token, csrf_token


@pytest.fixture
def user_attempts_reset_password_one_hour_old(
    app: Flask,
    register_first_user: Tuple[dict[str, str | None], Users],
    load_login_page: Tuple[FlaskClient, str],
) -> Generator[Tuple[Flask, FlaskClient, dict[str, str | None], str, str], None, None]:
    """
    After registering a new user, the user forgets their password
    and performs the forgot-password sequence, which would send a user an email with
    a unique token identifying them, that expires after a given set of time.
    The reset token is also stored in the database in the Forgot_Passwords object.
    In this scenario, the Forgot_Passwords object used to store and verify the token,
    is more than one hour old, the limit for age on these objects. This is separate from the
    tokens also expiring in one hour.

    Args:
        app (Flask): The Flask client providing an app context
        register_first_user (pytest fixture): Registers the user with ID == 1
        load_login_page (pytest fixture): Brings user to login page and yields test client

    Yields:
        (Flask): The Flask client for providing an app context
        (FlaskLoginClient): Flask client
        (dict): The user data who forgot their password
        (str): The reset token associated with the user's current reset-password attempt
        (str): CSRF token on the page
    """
    new_user, _ = register_first_user
    client, _ = load_login_page

    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    client.post(
        url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE),
        json={
            reset_password_strs.FORGOT_PASSWORD.EMAIL: new_user[
                reset_password_strs.FORGOT_PASSWORD.EMAIL
            ],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    with app.app_context():
        user_to_reset: Users = Users.query.filter(
            Users.email == new_user[model_strs.EMAIL].lower()
        ).first()
        password_reset_obj: Forgot_Passwords = Forgot_Passwords.query.filter(
            Forgot_Passwords.user_id == user_to_reset.id
        ).first()
        password_reset_obj.initial_attempt = (
            password_reset_obj.initial_attempt - timedelta(minutes=60)
        )

        # Avoid rate limiting on next reset attempt for testing
        password_reset_obj.last_attempt = (
            password_reset_obj.initial_attempt - timedelta(minutes=60)
        )
        reset_token = password_reset_obj.reset_token
        user_to_reset.password_reset = password_reset_obj
        db.session.commit()

    yield app, client, new_user, reset_token, csrf_token
