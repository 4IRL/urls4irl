from typing import Generator, Tuple

from flask import Flask
import pytest

from src import db
from src.models.email_validations import Email_Validations
from src.models.users import Users
from src.utils.strings import model_strs
from tests.models_for_test import valid_user_1


@pytest.fixture
def app_with_server_name(app: Flask) -> Generator[Flask, None, None]:
    app.config["SERVER_NAME"] = "localhost:5000"
    yield app


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
            confirm_url=new_user.get_email_validation_token()
        )
        new_user.email_confirm = new_email_validation

        db.session.add(new_user)
        db.session.commit()

    yield valid_user_1, new_user
