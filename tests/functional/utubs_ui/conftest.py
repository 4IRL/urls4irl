# External libraries
import pytest

# Internal libraries
from src.mocks.mock_constants import USERNAME_BASE, EMAIL_SUFFIX
from tests.functional.utils_for_test import click_and_wait, send_keys_to_input_field


@pytest.fixture
def add_test_utubs(runner):
    """
    Adds test users and sample UTubs
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "utubs"])


@pytest.fixture
def login_test_user(add_test_users, browser):
    username = USERNAME_BASE + "1"

    # Find login button to open modal
    click_and_wait(browser, ".to-login")

    # Input login details
    send_keys_to_input_field(browser, "#username", username)

    send_keys_to_input_field(browser, "#password", username + EMAIL_SUFFIX)

    # Find submit button to login
    click_and_wait(browser, "#submit")

    print("Logged in as " + username)

    yield browser
