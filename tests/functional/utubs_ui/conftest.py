# External libraries
import pytest

# Internal libraries
from tests.functional.utils_for_test import login_user


@pytest.fixture
# def login_test_user(browser, add_test_users, debug_strings):
def login_test_user(browser, add_test_users):
    """
    Provides test with predetermined users
    """
    login_user(browser)

    # if debug_strings:
    #     print("Logged in as " + username)

    yield browser


@pytest.fixture
def create_test_utub(browser, add_test_utub):
    """
    Provides test with predetermined users and utubs
    """

    login_user(browser)

    yield browser


@pytest.fixture
def create_test_utubs(browser, add_test_utubs):
    """
    Provides test with predetermined users and utubs
    """

    login_user(browser)

    yield browser
