# External libraries
from time import sleep

# Internal libraries
from src.mocks.mock_constants import USERNAME_BASE
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.members_ui.utils_for_test_members_ui import (
    create_member_active_utub,
    get_all_member_usernames,
)
from tests.functional.utils_for_test import (
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

    select_utub_by_name(browser, UTS.TEST_UTUB_NAME_1)
    create_member_active_utub(browser, new_member_username)

    # Wait for POST request
    sleep(4)

    member_usernames = get_all_member_usernames(browser)

    # Assert new member is added to UTub
    assert new_member_username in member_usernames
