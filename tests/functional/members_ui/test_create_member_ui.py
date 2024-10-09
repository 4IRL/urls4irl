# Standard library
from time import sleep

# External libraries
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from src.mocks.mock_constants import USERNAME_BASE
from tests.functional.members_ui.utils_for_test_members_ui import (
    create_member_active_utub,
    get_all_member_usernames,
)
from tests.functional.utils_for_test import login_utub


# @pytest.mark.skip(reason="Testing another in isolation")
def test_create_member(browser: WebDriver, create_test_utubs):
    """
    Tests a UTub owner's ability to create a member by adding another U4I user to the UTub.

    GIVEN a user is the UTub owner
    WHEN the createMember form is populated and submitted
    THEN ensure the new member is successfully added to the UTub.
    """

    login_utub(browser)

    new_member_username = USERNAME_BASE + "2"
    create_member_active_utub(browser, new_member_username)

    # Wait for POST request
    sleep(4)

    member_usernames = get_all_member_usernames(browser)

    # Assert new member is added to UTub
    assert new_member_username in member_usernames
