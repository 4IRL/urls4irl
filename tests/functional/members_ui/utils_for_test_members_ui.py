# Standard library

# External libraries
from selenium.common.exceptions import NoSuchElementException

# Internal libraries
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.utils_for_test import (
    clear_then_send_keys,
    is_owner,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
)


def create_member_active_utub(browser, user_name, member_name):
    if is_owner(user_name):

        # Click createMember button to show input
        wait_then_click_element(browser, MPL.BUTTON_MEMBER_CREATE)

        # Types new member name
        create_member_input = wait_then_get_element(browser, MPL.INPUT_MEMBER_CREATE)
        clear_then_send_keys(create_member_input, member_name)

        # Submits new member form
        wait_then_click_element(browser, MPL.BUTTON_MEMBER_SUBMIT_CREATE)
    else:
        return False


def leave_active_utub(browser):
    """
    Selects UTub matching the indicated utub_name, selects and confirms leaving the UTub
    """

    try:
        leave_utub_btn = browser.find_element_by_css_selector(MPL.BUTTON_UTUB_LEAVE)
    except NoSuchElementException:
        return False

    leave_utub_btn.click()

    # assert modal
    # wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)


def leave_all_utubs(browser, user_name):
    """
    Cycles through all user's UTubs and leaves them, if not owner.
    """

    UTub_selectors = wait_then_get_elements(browser, MPL.SELECTORS_UTUB)

    # Cycle through all UTubs and leave, if possible.
    for selector in UTub_selectors:
        selector.click()
        if is_owner(browser, user_name):
            continue
        else:
            leave_active_utub(browser)
