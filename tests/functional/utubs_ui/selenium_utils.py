from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.assert_utils import assert_visible_css_selector
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.selenium_utils import (
    clear_then_send_keys,
    wait_for_animation_to_end,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)


def create_utub(browser: WebDriver, utub_name: str, utub_description: str):
    """
    Once logged in, this function adds new UTub by selecting the option to open the input field, fills in the fields with the specified values for utub_name and utub_description, and submits the form.

    Args:
        WebDriver open to U4I Home Page
        UTub name and description inputs for creation of a new UTub

    Returns:
        WebDriver handoff to UTub tests
    """

    # Click createUTub button to show input
    wait_then_click_element(browser, HPL.BUTTON_UTUB_CREATE)

    # Types new UTub name
    create_utub_name_input = wait_then_get_element(browser, HPL.INPUT_UTUB_NAME_CREATE)
    assert create_utub_name_input is not None
    clear_then_send_keys(create_utub_name_input, utub_name)

    # Types new UTub description
    create_utub_description_input = wait_then_get_element(
        browser, HPL.INPUT_UTUB_DESCRIPTION_CREATE
    )
    assert create_utub_description_input is not None
    clear_then_send_keys(create_utub_description_input, utub_description)


def open_update_utub_name_input(browser: WebDriver):
    """
    Once logged in and UTub selected, this function conducts the actions for opening either the update UTub name or description input field. First hover over the UTub name or description to display the edit button. Then clicks the edit button.

    Args:
        WebDriver open to U4I Home Page
    """

    update_wrap_element = wait_then_get_element(browser, HPL.WRAP_UTUB_NAME_UPDATE)
    assert update_wrap_element is not None

    _update_utub_input(
        browser,
        HPL.WRAP_UTUB_NAME_UPDATE,
        HPL.HEADER_URL_DECK,
        HPL.BUTTON_UTUB_NAME_UPDATE,
    )


def open_update_utub_desc_input(browser: WebDriver):
    """
    Once logged in and UTub selected, this function conducts the actions for opening either the update UTub name or description input field. First hover over the UTub name or description to display the edit button. Then clicks the edit button.

    Args:
        WebDriver open to U4I Home Page
    """
    update_wrap_element = wait_then_get_element(
        browser, HPL.WRAP_UTUB_DESCRIPTION_UPDATE, time=3
    )
    assert update_wrap_element is not None

    _update_utub_input(
        browser,
        HPL.WRAP_UTUB_DESCRIPTION_UPDATE,
        HPL.SUBHEADER_URL_DECK,
        HPL.BUTTON_UTUB_DESCRIPTION_UPDATE,
    )


def _update_utub_input(
    browser: WebDriver, wrap_elem_selector: str, elem_locator: str, btn_locator: str
):
    # Hover over UTub name to display utubNameBtnUpdate button
    actions = ActionChains(browser)

    wrap_elem = wait_then_get_element(browser, wrap_elem_selector, time=3)
    assert wrap_elem is not None
    update_element = wrap_elem.find_element(By.CSS_SELECTOR, elem_locator)
    update_button = wrap_elem.find_element(By.CSS_SELECTOR, btn_locator)

    # Pause to make sure utubNameBtnUpdate button is visible
    actions.move_to_element(update_element).pause(3).move_to_element(
        update_button
    ).pause(2).click(update_button).perform()
    # Update input field visible


def update_utub_name(browser: WebDriver, utub_name: str):
    """
    Once logged in and UTub selected, this function conducts the actions for editing the selected UTub name. First hover over the UTub name to display the edit button. Then clicks the edit button, interacts with the input field and submits it.

    Args:
        WebDriver open to U4I Home Page
        New UTub name

    Returns:
        WebDriver handoff to UTub tests
    """

    open_update_utub_name_input(browser)

    # Types new UTub name
    utub_name_update_input = wait_then_get_element(browser, HPL.INPUT_UTUB_NAME_UPDATE)
    assert utub_name_update_input is not None
    clear_then_send_keys(utub_name_update_input, utub_name)


def update_utub_description(browser: WebDriver, utub_description: str):
    """
    Once logged in and UTub selected, this function conducts the actions for editing the selected UTub description. First hover over the UTub decsription to display the edit button. Then clicks the edit button, interacts with the input field and submits it.

    Args:
        WebDriver open to U4I Home Page
        New UTub description
    """

    open_update_utub_desc_input(browser)

    # Types new UTub description
    utub_description_update_input = wait_then_get_element(
        browser, HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )
    assert utub_description_update_input is not None
    clear_then_send_keys(utub_description_update_input, utub_description)


def hover_over_utub_title_to_show_add_utub_description(browser: WebDriver):
    # Hover over UTub name to display utubNameBtnUpdate button
    actions = ActionChains(browser)

    utub_title_elem = browser.find_element(By.CSS_SELECTOR, HPL.HEADER_URL_DECK)
    utub_desc_input_elem = browser.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY
    )

    # Pause to make sure utubNameBtnUpdate button is visible
    actions.move_to_element(utub_title_elem).pause(5).move_to_element(
        utub_desc_input_elem
    ).pause(5).perform()

    wait_until_visible_css_selector(
        browser, HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY, timeout=3
    )

    assert wait_until_hidden(browser, HPL.SUBHEADER_URL_DECK, timeout=3) is not None
    utub_desc_elem = browser.find_element(By.CSS_SELECTOR, HPL.SUBHEADER_URL_DECK)
    assert not utub_desc_elem.is_displayed()


def open_utub_search_box(browser: WebDriver):
    wait_until_visible_css_selector(browser, HPL.UTUB_OPEN_SEARCH_ICON, timeout=3)
    assert_visible_css_selector(browser, HPL.UTUB_OPEN_SEARCH_ICON)

    wait_then_click_element(browser, HPL.UTUB_OPEN_SEARCH_ICON, time=3)
    browser.get_screenshot_as_file("p1.png")
    wait_for_animation_to_end(browser, HPL.UTUB_SEARCH_INPUT, timeout=3)
    wait_until_in_focus(browser, HPL.UTUB_SEARCH_INPUT)

    assert_visible_css_selector(browser, HPL.UTUB_CLOSE_SEARCH_ICON, time=3)
    utub_search_elem = wait_then_get_element(browser, HPL.UTUB_SEARCH_INPUT, time=3)
    assert browser.switch_to.active_element == utub_search_elem
