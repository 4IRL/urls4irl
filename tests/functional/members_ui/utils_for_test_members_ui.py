# Standard library
from time import sleep

# External libraries
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

# Internal libraries
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.utils_for_test import (
    clear_then_send_keys,
    current_user_is_owner,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
)


def get_all_member_badges(browser):
    return wait_then_get_elements(browser, MPL.BADGES_MEMBERS)


def get_all_member_usernames(browser):
    members = get_all_member_badges(browser)
    member_names = []

    for member in members:
        member_name = member.get_attribute("innerText")
        member_names.append(member_name)

    return member_names


def create_member_active_utub(browser, member_name):
    if current_user_is_owner(browser):

        # Click createMember button to show input
        wait_then_click_element(browser, MPL.BUTTON_MEMBER_CREATE)

        # Types new member name
        create_member_input = wait_then_get_element(browser, MPL.INPUT_MEMBER_CREATE)
        clear_then_send_keys(create_member_input, member_name)

        # Submits new member form
        wait_then_click_element(browser, MPL.BUTTON_MEMBER_SUBMIT_CREATE)

        return True
    else:
        return False


def delete_member_active_utub(browser, member_name):
    actions = ActionChains(browser)
    if current_user_is_owner(browser):

        member_badges = get_all_member_badges(browser)

        # Find index for appropriate member to delete
        member_usernames = get_all_member_usernames(browser)
        i = 0
        for username in member_usernames:
            # Delete only indicated member
            if username == member_name:
                member_badge_to_delete = member_badges[i]
                # Hover over badge to display deleteMember button
                actions.move_to_element(member_badge_to_delete)

                # Pause to make sure deleteMember button is visible
                actions.pause(3).perform()

                member_delete_button = member_badge_to_delete.find_element(
                    By.CSS_SELECTOR, MPL.BUTTON_MEMBER_DELETE
                )

                actions.move_to_element(member_delete_button).pause(2)

                actions.click(member_delete_button)

                actions.perform()

                return True
            i += 1

        return False
    else:
        return False


def leave_active_utub(browser):
    """
    Selects UTub matching the indicated utub_name, selects and confirms leaving the UTub
    """

    try:
        wait_then_click_element(browser, MPL.BUTTON_UTUB_LEAVE)
    except NoSuchElementException:
        return False


def leave_all_utubs(browser):
    """
    Cycles through all user's UTubs and leaves them, if not owner.
    """

    UTub_selectors = wait_then_get_elements(browser, MPL.SELECTORS_UTUB)

    # Cycle through all UTubs and leave, if possible.
    for selector in UTub_selectors:
        selector.click()
        if current_user_is_owner(browser):
            continue
        else:
            leave_active_utub(browser)
            wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)
            # Wait for POST request
            sleep(4)
