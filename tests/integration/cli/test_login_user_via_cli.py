from typing import Tuple

from click.testing import Result
from flask import Flask
from flask.testing import FlaskCliRunner
import pytest

from src.mocks.mock_constants import TEST_USER_COUNT
from src.mocks.mock_options import USER_ID_INVALID_TO_LOGIN_WITH

pytestmark = pytest.mark.cli


def test_login_valid_user_via_cli(runner: Tuple[Flask, FlaskCliRunner]):
    app, cli_runner = runner

    for user_id in range(1, TEST_USER_COUNT + 1):
        result: Result = cli_runner.invoke(args=["addmock", "login", f"{user_id}"])
        user_session_id = result.output.strip()

        with app.app_context():
            store_id = f"session:{user_session_id}"
            assert app.session_interface._retrieve_session_data(store_id) is not None
            assert result.exit_code == 0
            app.session_interface._delete_session(store_id)


def test_login_invalid_user_via_cli(runner):
    app, cli_runner = runner

    result: Result = cli_runner.invoke(args=["addmock", "login", "0"])
    user_session_output = result.output.strip()

    with app.app_context():
        assert USER_ID_INVALID_TO_LOGIN_WITH in user_session_output
        assert result.exit_code == 1
