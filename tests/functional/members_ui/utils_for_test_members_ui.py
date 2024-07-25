# Standard library
from time import sleep

# External libraries
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.utils_for_test import (
    clear_then_send_keys,
    user_is_selected_utub_owner,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
)
from tests.functional.utubs_ui.utils_for_test_utub_ui import (
    delete_active_utub_confirmed,
)


def get_all_member_badges(browser: WebDriver):
    """
    Args:
        WebDriver open to a selected UTub

    Returns:
        List of member badge WebElements
        WebDriver handoff to member tests
    """

    return wait_then_get_elements(browser, MPL.BADGES_MEMBERS)


def get_all_member_usernames(browser: WebDriver):
    """
    Args:
        WebDriver open to a selected UTub

    Returns:
        List of member names
        WebDriver handoff to member tests
    """

    members = get_all_member_badges(browser)
    member_names = []

    for member in members:
        member_name = member.get_attribute("innerText")
        member_names.append(member_name)

    return member_names


def create_member_active_utub(browser: WebDriver, member_name: str):
    """
    Args:
        WebDriver open to a selected UTub
        Username of a U4I user to add as a member to the selected UTub

    Returns:
        Boolean confirmation of successful creation of member
        WebDriver handoff to member tests
    """

    if user_is_selected_utub_owner(browser):

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


def delete_member_active_utub(browser: WebDriver, member_name: str):
    """
    Args:
        WebDriver open to a selected UTub
        Username of a member to remove from the selected UTub

    Returns:
        Boolean confirmation of successful deletion of member
        WebDriver handoff to member tests
    """

    actions = ActionChains(browser)
    if user_is_selected_utub_owner(browser):

        member_badges = get_all_member_badges(browser)

        # Find index for appropriate member to delete
        member_usernames = get_all_member_usernames(browser)
        for i, username in enumerate(member_usernames):
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

        return False
    else:
        return False


def leave_active_utub(browser: WebDriver):
    """
    Args:
        WebDriver open to a selected UTub

    Returns:
        WebDriver handoff to member tests
    """

    try:
        wait_then_click_element(browser, MPL.BUTTON_UTUB_LEAVE)
    except NoSuchElementException:
        return False


def leave_all_utubs(browser: WebDriver):
    """
    Args:
        WebDriver open to U4I Home Page

    Returns:
        WebDriver handoff to member tests

    Cycles through all user's UTubs and leaves or deletes them.
    """

    UTub_selectors = wait_then_get_elements(browser, MPL.SELECTORS_UTUB)

    # Cycle through all UTubs and leave or delete, as appropriate.
    for selector in UTub_selectors:
        selector.click()

        if user_is_selected_utub_owner(browser):
            delete_active_utub_confirmed(browser)
        else:
            leave_active_utub(browser)
            wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)

        # Wait for POST request
        sleep(4)
