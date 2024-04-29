from typing import Generator, Tuple

from flask import Flask
import pytest

from src import db
from src.models.email_validations import Email_Validations
from src.models.users import Users
from src.utils.strings import model_strs
from tests.models_for_test import valid_user_2, valid_user_3


@pytest.fixture
def register_all_but_first_user(
    app: Flask,
) -> Generator[Tuple[Flask, Tuple[dict[str, str | None]]], None, None]:
    """
    Registers two User models with unique usernames, emails, passwords, and ID's.
    See 'models_for_test.py' for model information.
    Assumes the first user is already registered.
    The newly registered User's will have ID's 2 and 3

    Args:
        app (Flask): The Flask client for providing an app context

    Yields:
        (tuple): Contains models of all valid registered users
        (Flask): The Flask client for providing an app context
    """
    # Add multiple users for testing
    all_users: Tuple[dict[str, str | None]] = (
        valid_user_2,
        valid_user_3,
    )
    with app.app_context():
        for user in all_users:
            new_user = Users(
                username=user[model_strs.USERNAME],
                email=user[model_strs.EMAIL].lower(),
                plaintext_password=user[model_strs.PASSWORD],
            )

            new_email_validation = Email_Validations(
                confirm_url=new_user.get_email_validation_token()
            )
            new_email_validation.is_validated = True
            new_user.email_confirm = new_email_validation

            db.session.add(new_user)
            db.session.commit()

    yield app, all_users
