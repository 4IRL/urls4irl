# Standard library

# External libraries
from flask import Flask
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from src.models.utubs import Utubs
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.tags_ui.utils_for_test_tag_ui import (
    login_user_select_utub_by_name_open_create_utub_tag,
    verify_create_utub_tag_input_form_is_hidden,
    verify_new_utub_tag_created,
)
from tests.functional.utils_for_test import (
    login_user_and_select_utub_by_name,
    wait_then_click_element,
    wait_until_hidden,
    wait_until_visible,
)


def test_open_input_create_utub_tag(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests ability to open the create UTub tag form

    GIVEN a user is a UTub member and has selected the UTub
    WHEN the user clicks on the create UTub tag plus button
    THEN ensure the createUTubTag form is opened
    """
    app = provide_app
    user_id_for_test = 1

    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    elem = wait_then_click_element(browser, HPL.BUTTON_UTUB_TAG_CREATE)
    assert elem is not None

    utub_tag_input = browser.find_element(By.CSS_SELECTOR, HPL.INPUT_UTUB_TAG_CREATE)

    wait_until_visible(browser, utub_tag_input)

    # Ensure input is focused
    assert browser.switch_to.active_element == utub_tag_input

    visible_elems = (
        HPL.INPUT_UTUB_TAG_CREATE,
        HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE,
        HPL.BUTTON_UTUB_TAG_CANCEL_CREATE,
    )

    for visible_elem_selector in visible_elems:
        visible_elem = browser.find_element(By.CSS_SELECTOR, visible_elem_selector)
        assert visible_elem.is_displayed()
        assert visible_elem.is_enabled()

    non_visible_elems = (
        HPL.BUTTON_UTUB_TAG_CREATE,
        HPL.LIST_TAGS,
        HPL.SELECTOR_UNSELECT_ALL,
    )
    for non_visible_elem_selector in non_visible_elems:
        non_visible_elem = browser.find_element(
            By.CSS_SELECTOR, non_visible_elem_selector
        )
        assert not non_visible_elem.is_displayed()


def test_open_input_create_utub_tag_click_cancel_btn(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests ability to close the create UTub tag form by clicking cancel button

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user clicks on the cancel button
    THEN ensure the createUTubTag form is closed
    """
    app = provide_app
    user_id_for_test = 1

    login_user_select_utub_by_name_open_create_utub_tag(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    wait_then_click_element(browser, HPL.BUTTON_UTUB_TAG_CANCEL_CREATE)
    wait_until_hidden(browser, HPL.BUTTON_UTUB_TAG_CANCEL_CREATE)
    verify_create_utub_tag_input_form_is_hidden(browser)


def test_open_input_create_utub_tag_press_esc_key(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests ability to close the create UTub tag form by clicking cancel button

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the escape key while focused on the input field
    THEN ensure the createUTubTag form is closed
    """
    app = provide_app
    user_id_for_test = 1

    login_user_select_utub_by_name_open_create_utub_tag(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    # Ensure input is focused
    browser.switch_to.active_element.send_keys(Keys.ESCAPE)
    wait_until_hidden(browser, HPL.BUTTON_UTUB_TAG_CANCEL_CREATE)
    verify_create_utub_tag_input_form_is_hidden(browser)


def test_open_input_create_utub_tag_click_submit_btn(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests ability to add a new tag to the UTub

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the submit button after typing in a new UTub tag
    THEN ensure the createUTubTag form is closed and the new UTub tag is added
    """
    app = provide_app
    user_id_for_test = 1
    new_tag = "WOWZA123"

    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.name == UTS.TEST_UTUB_NAME_1).first()
        init_num_of_utub_tags = len(utub.utub_tags)

    login_user_select_utub_by_name_open_create_utub_tag(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    # Ensure input is focused
    browser.switch_to.active_element.send_keys(new_tag)
    wait_then_click_element(browser, HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)
    wait_until_hidden(browser, HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    verify_create_utub_tag_input_form_is_hidden(browser)
    verify_new_utub_tag_created(browser, new_tag, init_num_of_utub_tags)


def test_open_input_create_utub_tag_press_enter_key(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests ability to add a new tag to the UTub

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the enter key after typing in a new UTub tag and focused on input
    THEN ensure the createUTubTag form is closed and the new UTub tag is added
    """
    app = provide_app
    user_id_for_test = 1
    new_tag = "WOWZA123"

    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.name == UTS.TEST_UTUB_NAME_1).first()
        init_num_of_utub_tags = len(utub.utub_tags)

    login_user_select_utub_by_name_open_create_utub_tag(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    # Ensure input is focused
    browser.switch_to.active_element.send_keys(new_tag)
    browser.switch_to.active_element.send_keys(Keys.ENTER)
    wait_until_hidden(browser, HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    verify_create_utub_tag_input_form_is_hidden(browser)
    verify_new_utub_tag_created(browser, new_tag, init_num_of_utub_tags)


# TODO: Check sanitized inputs in sad path tests
