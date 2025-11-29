from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from src.models.utubs import Utubs
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.selenium_utils import (
    clear_then_send_keys,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_hidden,
)


def get_all_member_badges(browser: WebDriver) -> list[WebElement]:
    """
    Args:
        WebDriver open to a selected UTub

    Returns:
        List of member badge WebElements
        WebDriver handoff to member tests
    """

    return wait_then_get_elements(browser, HPL.BADGES_MEMBERS)


def get_all_member_usernames(browser: WebDriver) -> list[str]:
    """
    Args:
        WebDriver open to a selected UTub

    Returns:
        List of member names
        WebDriver handoff to member tests
    """

    members = get_all_member_badges(browser)
    return [member.text for member in members] if members else []


def create_member_active_utub(browser: WebDriver, member_name: str):
    """
    Args:
        WebDriver open to a selected UTub
        Username of a U4I user to add as a member to the selected UTub

    Returns:
        Boolean confirmation of successful creation of member
        WebDriver handoff to member tests
    """
    # Click createMember button to show input
    wait_then_click_element(browser, HPL.BUTTON_MEMBER_CREATE)

    # Types new member name
    create_member_input = wait_then_get_element(browser, HPL.INPUT_MEMBER_CREATE)
    assert create_member_input is not None
    clear_then_send_keys(create_member_input, member_name)


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

    member_badges = get_all_member_badges(browser)

    # Find index for appropriate member to delete
    for member_badge in member_badges:
        # Delete only indicated member
        username = member_badge.text
        if username == member_name:
            # Hover over badge to display deleteMember button
            actions.move_to_element(member_badge)

            # Pause to make sure deleteMember button is visible
            actions.pause(3).perform()

            member_delete_button = member_badge.find_element(
                By.CSS_SELECTOR, HPL.BUTTON_MEMBER_DELETE
            )

            actions.move_to_element(member_delete_button).pause(2)

            actions.click(member_delete_button)

            actions.perform()


def leave_utub_as_member(browser: WebDriver, utub_to_leave: Utubs):
    """
    Performs actions to leave a UTub as a UTub Member.

    Args:
        browser (WebDriver): WebDriver open to a selected UTub
        utub_to_leave (Utubs): UTub to leave

    Returns:
        Boolean confirmation of successful deletion of member
        WebDriver handoff to member tests
    """
    wait_then_click_element(browser, HPL.BUTTON_UTUB_LEAVE, time=3)

    warning_modal_body = wait_then_get_element(browser, HPL.BODY_MODAL)
    assert warning_modal_body is not None

    utub_css_selector = f'{HPL.SELECTORS_UTUB}[utubid="{utub_to_leave.id}"]'
    utub_selector = browser.find_element(By.CSS_SELECTOR, utub_css_selector)

    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT, time=3)
    wait_until_hidden(browser, HPL.BUTTON_MODAL_SUBMIT, timeout=3)
    wait_for_element_to_be_removed(browser, utub_selector)
