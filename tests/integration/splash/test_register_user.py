from copy import deepcopy
from flask import url_for, request
from flask_login import current_user
import pytest
from werkzeug.security import check_password_hash

from backend.schemas.users import RegisterResponseSchema
from backend.splash.constants import RegisterErrorCodes
from backend.utils.strings.html_identifiers import IDENTIFIERS
from tests.models_for_test import valid_user_1
from tests.utils_for_test import get_csrf_token
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.splash_form_strs import REGISTER_FORM
from tests.integration.utils import assert_response_conforms_to_schema
from backend.utils.strings.user_strs import USER_FAILURE
from tests.integration.splash.conftest import register_json

pytestmark = pytest.mark.splash


def test_register_new_user(app, load_register_page):
    """
    GIVEN a new, unregistered user to the page
    WHEN they register to an empty database, and POST to "/register" correctly
    THEN ensure they are logged in and set to their home page
    """
    client, csrf_token_string = load_register_page

    new_user = deepcopy(valid_user_1)

    # Ensure no user with this data exists in database
    with app.app_context():
        assert (
            Users.query.filter(
                Users.username == new_user[REGISTER_FORM.USERNAME]
            ).first()
            is None
        )

    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        json=register_json(new_user),
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Correctly responds with JSON 201
    assert response.status_code == 201
    assert response.json[STD_JSON.STATUS] == STD_JSON.SUCCESS

    # Test if user logged in
    assert current_user.username == new_user[REGISTER_FORM.USERNAME]
    assert current_user.password != new_user[REGISTER_FORM.PASSWORD]
    assert current_user.email == new_user[REGISTER_FORM.EMAIL].lower()

    # Ensure user exists in database
    with app.app_context():
        new_db_user: Users = Users.query.filter(
            Users.username == new_user[REGISTER_FORM.USERNAME]
        ).first()

    # Ensure user model after loading from database is logged in
    assert new_db_user.is_authenticated is True
    assert new_db_user.is_active is True

    # Test if user db data is same as input when registering
    assert new_db_user.username == new_user[REGISTER_FORM.USERNAME]
    assert new_db_user.password != new_user[REGISTER_FORM.PASSWORD]
    assert new_db_user.email == new_user[REGISTER_FORM.EMAIL].lower()

    # Test if user db data is same as current user variable
    assert new_db_user.username == current_user.username
    assert new_db_user.password == current_user.password
    assert new_db_user.email == current_user.email.lower()
    assert new_db_user.id == int(current_user.get_id())


def test_register_duplicate_user(app, load_register_page, register_first_user):
    """
    GIVEN a user to the page
    WHEN they register with same credentials, and POST to "/register" correctly
    THEN ensure they are not logged in and not registered again

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: USER_FAILURE.UNABLE_TO_REGISTER,
        STD_JSON.ERROR_CODE: Integer representing the failure code, 2 for invalid form inputs
        STD_JSON.ERRORS: Array containing objects for each field and their specific error. For example:
            [
                {
                    REGISTER_FORM.USERNAME: "That username is taken. Please choose another.",
                    REGISTER_FORM.EMAIL: "That email address is already in use."
                }
            ]
    }
    """
    client, csrf_token_string = load_register_page
    already_registered_user_data, _ = register_first_user

    # Ensure user already exists
    with app.app_context():
        new_db_user = Users.query.filter(
            Users.username == already_registered_user_data[REGISTER_FORM.USERNAME]
        ).first()

    assert new_db_user is not None

    # Ensure no one is logged in
    assert current_user.get_id() is None
    assert current_user.is_active is False

    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        json=register_json(already_registered_user_data),
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Check that does not reroute
    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.REGISTER)
    assert len(response.history) == 0

    # Ensure json response from server is valid
    register_user_response_json = response.json
    assert register_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        register_user_response_json[STD_JSON.MESSAGE] == USER_FAILURE.UNABLE_TO_REGISTER
    )
    assert (
        int(register_user_response_json[STD_JSON.ERROR_CODE])
        == RegisterErrorCodes.INVALID_FORM_INPUT
    )
    assert (
        USER_FAILURE.USERNAME_TAKEN
        in register_user_response_json[STD_JSON.ERRORS][REGISTER_FORM.USERNAME]
    )
    assert (
        USER_FAILURE.EMAIL_TAKEN
        in register_user_response_json[STD_JSON.ERRORS][REGISTER_FORM.EMAIL]
    )


def test_register_existing_username_with_trailing_leading_whitespace(
    app, load_register_page, register_first_user
):
    """
    GIVEN a user to the page
    WHEN they register with same credentials but username has leading/trailing whitespace,
        and POST to "/register" correctly
    THEN ensure the schema strips the whitespace and the service catches both
        username and email as duplicates

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: USER_FAILURE.UNABLE_TO_REGISTER,
        STD_JSON.ERROR_CODE: RegisterErrorCodes.INVALID_FORM_INPUT,
        STD_JSON.ERRORS: {
            REGISTER_FORM.USERNAME: [USER_FAILURE.USERNAME_TAKEN],
            REGISTER_FORM.EMAIL: [USER_FAILURE.EMAIL_TAKEN],
        }
    }
    """
    client, csrf_token_string = load_register_page
    already_registered_user_data, _ = register_first_user
    already_registered_user_data = deepcopy(already_registered_user_data)

    already_registered_user_data[REGISTER_FORM.USERNAME] = (
        f" {already_registered_user_data[REGISTER_FORM.USERNAME]} "
    )

    # Ensure no one is logged in
    assert current_user.get_id() is None
    assert current_user.is_active is False

    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        json=register_json(already_registered_user_data),
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Schema strips whitespace, service catches both duplicates
    assert response.status_code == 400
    assert request.path == url_for(ROUTES.SPLASH.REGISTER)
    assert len(response.history) == 0

    register_user_response_json = response.json
    assert register_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        register_user_response_json[STD_JSON.MESSAGE] == USER_FAILURE.UNABLE_TO_REGISTER
    )
    assert (
        int(register_user_response_json[STD_JSON.ERROR_CODE])
        == RegisterErrorCodes.INVALID_FORM_INPUT
    )
    assert (
        USER_FAILURE.USERNAME_TAKEN
        in register_user_response_json[STD_JSON.ERRORS][REGISTER_FORM.USERNAME]
    )
    assert (
        USER_FAILURE.EMAIL_TAKEN
        in register_user_response_json[STD_JSON.ERRORS][REGISTER_FORM.EMAIL]
    )


def test_register_user_cased_email(app, load_register_page, register_first_user):
    """
    GIVEN a user to the page
    WHEN they register with same credentials but UPPERCASE and lowercase email, and POST to "/register" correctly
    THEN ensure they are not logged in and not registered again

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: USER_FAILURE.UNABLE_TO_REGISTER,
        STD_JSON.ERROR_CODE: Integer representing the failure code, 2 for invalid form inputs
        STD_JSON.ERRORS: Array containing objects for each field and their specific error. For example:
            [
                {
                    REGISTER_FORM.USERNAME: "That username is taken. Please choose another.",
                    REGISTER_FORM.EMAIL: "That email address is already in use."
                }
            ]
    }
    """
    client, csrf_token_string = load_register_page
    already_registered_user_data, _ = register_first_user
    already_registered_user_data = deepcopy(already_registered_user_data)

    base_email = already_registered_user_data[REGISTER_FORM.EMAIL]
    local_part, domain = base_email.split("@")
    # EmailStr normalizes domain to lowercase but preserves local-part case.
    # confirmEmail must match the EmailStr-normalized output for schema validation to pass.
    cased_emails_with_confirm = (
        (base_email.upper(), f"{local_part.upper()}@{domain.lower()}"),
        (base_email.lower(), base_email.lower()),
    )

    for email, confirm_email in cased_emails_with_confirm:
        already_registered_user_data[REGISTER_FORM.EMAIL] = email
        already_registered_user_data[REGISTER_FORM.CONFIRM_EMAIL] = confirm_email

        # Ensure no one is logged in
        assert current_user.get_id() is None
        assert current_user.is_active is False

        response = client.post(
            url_for(ROUTES.SPLASH.REGISTER),
            json=register_json(already_registered_user_data),
            headers={"X-CSRFToken": csrf_token_string},
        )

        # Check that does not reroute
        assert response.status_code == 400
        assert request.path == url_for(ROUTES.SPLASH.REGISTER)
        assert len(response.history) == 0

        # Ensure json response from server is valid
        register_user_response_json = response.json
        assert register_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert (
            register_user_response_json[STD_JSON.MESSAGE]
            == USER_FAILURE.UNABLE_TO_REGISTER
        )
        assert (
            int(register_user_response_json[STD_JSON.ERROR_CODE])
            == RegisterErrorCodes.INVALID_FORM_INPUT
        )
        assert (
            USER_FAILURE.USERNAME_TAKEN
            in register_user_response_json[STD_JSON.ERRORS][REGISTER_FORM.USERNAME]
        )
        assert (
            USER_FAILURE.EMAIL_TAKEN
            in register_user_response_json[STD_JSON.ERRORS][REGISTER_FORM.EMAIL]
        )


def test_register_modal_is_shown(app_with_server_name, client):
    """
    GIVEN a non-registered user visiting the splash page ("/")
    WHEN the user makes a request to "/"
    THEN verify that the splash page contains the pre-rendered register form HTML
    """
    with client:
        with app_with_server_name.app_context():
            response = client.get(url_for(ROUTES.SPLASH.SPLASH_PAGE))
        assert (
            b'<form id="ModalForm" method="POST" class="login-register-form" action="/register" novalidate>'
            in response.data
        )

        # Ensure splash page contains register form with static HTML inputs
        assert (
            b'<input autocomplete="username" class="form-control login-register-form-group" id="username"'
            in response.data
        )
        assert (
            b'<input autocomplete="email" class="form-control login-register-form-group" id="email"'
            in response.data
        )
        assert (
            b'<input autocomplete="email" class="form-control login-register-form-group" id="confirmEmail"'
            in response.data
        )
        assert (
            b'<input autocomplete="new-password" class="form-control login-register-form-group" id="password"'
            in response.data
        )
        assert (
            b'<input autocomplete="new-password" class="form-control login-register-form-group" id="confirmPassword"'
            in response.data
        )
        assert b'<button id="submit"' in response.data
        assert request.path == url_for(ROUTES.SPLASH.SPLASH_PAGE)


def test_register_modal_logs_user_in(app_with_server_name, client):
    """
    GIVEN a non-logged in user visiting the splash page ("/")
    WHEN the user makes a GET request to "/register", and then a POST request with the applicable form info
    THEN verify that the backends responds with JSON 201, and logs the user in via session
    """
    with client:
        with app_with_server_name.app_context():
            splash_response = client.get(url_for(ROUTES.SPLASH.SPLASH_PAGE))
            csrf_token = get_csrf_token(splash_response.data, meta_tag=True)

        new_user = deepcopy(valid_user_1)

        response = client.post(
            url_for(ROUTES.SPLASH.REGISTER),
            json=register_json(new_user),
            headers={"X-CSRFToken": csrf_token},
        )

        assert response.status_code == 201
        assert response.json[STD_JSON.STATUS] == STD_JSON.SUCCESS

        assert current_user.username == new_user[REGISTER_FORM.USERNAME]
        assert check_password_hash(
            current_user.password, new_user[REGISTER_FORM.PASSWORD]
        )
        assert current_user.email == new_user[REGISTER_FORM.EMAIL].lower()


def test_register_user_missing_csrf(app, load_register_page):
    """
    GIVEN a new, unregistered user to the page
    WHEN they register to an empty database, and POST to "/register" without a CSRF token
    THEN ensure server responds with 403 and proper error message
    """
    client, _ = load_register_page

    # Ensure no user with this data exists in database
    with app.app_context():
        new_db_user = Users.query.filter(
            Users.username == valid_user_1[REGISTER_FORM.USERNAME]
        ).first()

    assert new_db_user is None

    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        json=register_json(valid_user_1),
    )

    # Correctly sends 403 for missing CSRF
    assert response.status_code == 403
    assert response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in response.data

    # Ensure no one is logged in
    assert current_user.get_id() is None
    assert current_user.is_active is False

    # Ensure no user with this data exists in database
    with app.app_context():
        new_db_user = Users.query.filter(
            Users.username == valid_user_1[REGISTER_FORM.USERNAME]
        ).first()

    assert new_db_user is None


def test_register_new_user_log(app, load_register_page, caplog):
    """
    GIVEN a new, unregistered user to the page
    WHEN they register to an empty database, and POST to "/register" correctly
    THEN ensure they are logged in and logs are valid
    """
    from tests.utils_for_test import is_string_in_logs

    client, csrf_token_string = load_register_page

    new_user = deepcopy(valid_user_1)

    # Ensure no user with this data exists in database
    with app.app_context():
        assert (
            Users.query.filter(
                Users.username == new_user[REGISTER_FORM.USERNAME]
            ).first()
            is None
        )

    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        json=register_json(new_user),
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Correctly responds with JSON 201
    assert response.status_code == 201
    assert response.json[STD_JSON.STATUS] == STD_JSON.SUCCESS

    # Test if user logged in
    assert current_user.username == new_user[REGISTER_FORM.USERNAME]
    with app.app_context():
        user: Users = Users.query.filter(
            Users.username == new_user[REGISTER_FORM.USERNAME]
        ).first()
        assert is_string_in_logs(
            f"User={user.id} successfully registered but not email validated",
            caplog.records,
        )


def test_register_unvalidated_email_with_valid_username(
    register_first_user_without_email_validation, load_register_page
):
    """
    GIVEN a registered user without a validated email
    WHEN a new session tries to register with the same email but a different, valid-format username
    THEN ensure a 401 response with error_code=1 is returned (not a 400 schema error)

    This verifies that the service layer's email-not-validated short-circuit
    is reached when the email belongs to an unvalidated account and the username
    is valid format but not yet taken.
    """
    registered_user, _ = register_first_user_without_email_validation
    client, csrf_token_string = load_register_page

    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        json={
            REGISTER_FORM.USERNAME: "BrandNewUser123",
            REGISTER_FORM.EMAIL: registered_user[REGISTER_FORM.EMAIL],
            REGISTER_FORM.CONFIRM_EMAIL: registered_user[REGISTER_FORM.EMAIL],
            REGISTER_FORM.PASSWORD: registered_user[REGISTER_FORM.PASSWORD],
            REGISTER_FORM.CONFIRM_PASSWORD: registered_user[REGISTER_FORM.PASSWORD],
        },
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert response.status_code == 401
    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        response_json[STD_JSON.MESSAGE]
        == USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED
    )
    assert (
        int(response_json[STD_JSON.ERROR_CODE])
        == RegisterErrorCodes.ACCOUNT_NOT_EMAIL_VALIDATED
    )


def test_register_response_conforms_to_schema(app, load_register_page):
    """
    GIVEN a new, unregistered user
    WHEN they register successfully via POST to "/register"
    THEN ensure the 201 JSON response conforms to RegisterResponseSchema
    """
    client, csrf_token_string = load_register_page

    new_user = deepcopy(valid_user_1)

    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        json=register_json(new_user),
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert response.status_code == 201
    response_json = response.json

    assert_response_conforms_to_schema(
        response_json,
        RegisterResponseSchema,
        {STD_JSON.STATUS, STD_JSON.MESSAGE},
    )
