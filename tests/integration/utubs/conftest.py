from flask import Flask
from flask.testing import FlaskClient
from flask_login import current_user
import pytest
from typing import Generator, Tuple

from src import db
from src.models.users import Users
from src.models.utubs import Utubs
from src.models.utub_members import Utub_Members
from src.utils.strings import model_strs
from tests.models_for_test import (
    valid_empty_utub_1,
)


@pytest.fixture
def add_single_utub_as_user_after_logging_in(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> Generator[Tuple[FlaskClient, int, str, Flask], None, None]:
    """
    After logging in a user with ID == 1, has the user create a UTub and adds the
        UTub and UTub-User association to the database

    Args:
        login_first_user_with_register (pytest fixture): Registers the user with ID == 1, logs them in,
            and routes to them "/home"

    Yields:
        (FlaskLoginClient): Flask client that logs in a user using flask_login
        (int): The ID of the added UTub
        (str): The CSRF token for the current client
        (Flask): The Flask client for providing an app context
    """
    client, csrf_token, valid_user, app = login_first_user_with_register

    with app.app_context():
        new_utub = Utubs(
            name=valid_empty_utub_1[model_strs.NAME],
            utub_creator=valid_user.id,
            utub_description=valid_empty_utub_1[model_strs.UTUB_DESCRIPTION],
        )

        creator_to_utub = Utub_Members()
        creator_to_utub.to_user = current_user
        new_utub.members.append(creator_to_utub)
        db.session.commit()

        new_utub_id = new_utub.id

    yield client, new_utub_id, csrf_token, app
