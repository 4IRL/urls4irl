# External libraries
from time import sleep

# Internal libraries
from src.mocks.mock_constants import MOCK_UTUB_NAME_BASE, USERNAME_BASE
from tests.functional.members_ui.utils_for_test_members_ui import (
    create_member_active_utub,
    get_all_member_usernames,
)
from tests.functional.utils_for_test import (
    get_current_user_name,
    login_user,
    select_utub_by_name,
)


# @pytest.mark.skip(reason="Testing another in isolation")
def test_create_member(browser, create_test_utubs):
    """
    GIVEN a user is the UTub owner
    WHEN they submit the createMember form
    THEN ensure the new member is successfully added to the UTub.
    """

    login_user(browser)

    new_member_username = USERNAME_BASE + "2"
    utub_name = MOCK_UTUB_NAME_BASE + "1"
    user_name = get_current_user_name(browser)

    select_utub_by_name(browser, utub_name)
    create_member_active_utub(browser, user_name, new_member_username)

    # Wait for POST request
    sleep(4)

    member_usernames = get_all_member_usernames(browser)

    # Assert new member is added to UTub
    assert new_member_username in member_usernames
