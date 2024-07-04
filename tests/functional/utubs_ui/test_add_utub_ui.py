# External libraries
import time

# Internal libraries
from src.mocks.mock_constants import UTUB_NAME_BASE
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.utils_for_test import add_utub, wait_then_get_element


# @pytest.mark.skip(reason="Testing another in isolation")
def test_add_utub(login_test_user):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    browser = login_test_user

    selector_UTub = add_utub(browser, UTUB_NAME_BASE + "1")

    time.sleep(10)

    # Assert new UTub selector was created with input UTub Name
    assert selector_UTub.text == UTUB_NAME_BASE + "1"
    # Assert new UTub is now active and displayed to user
    assert "active" in selector_UTub.get_attribute("class")


# @pytest.mark.skip(
#     reason="This test tests functionality that is not yet captured on the frontend"
# )
def test_add_utub_name_length_exceeded(login_test_user):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    browser = login_test_user

    add_utub(browser, UI_TEST_STRINGS.MAX_CHAR_LIM_UTUB_NAME)

    warning_modal_body = wait_then_get_element(browser, "#confirmModalBody")

    # Assert new UTub is now active and displayed to user
    assert warning_modal_body.text == "Try shortening your UTub name"


# @pytest.mark.skip(reason="This test is not yet implemented")
def test_add_utub_name_similar(create_test_utubs):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    browser = create_test_utubs

    # Extract name of a pre-existing UTub
    first_UTub_selector = wait_then_get_element(browser, ".UTubSelector")
    utub_name = first_UTub_selector.get_attribute("innerText")

    print(utub_name)

    # Attempt to add a new UTub with the same name
    add_utub(browser, utub_name)

    # Extract modal body element
    confirmation_modal_body = wait_then_get_element(browser, "#confirmModalBody")

    # Assert modal prompts user to consider duplicate UTub naming
    assert (
        confirmation_modal_body.text == "A UTub in your repository has a similar name."
    )
