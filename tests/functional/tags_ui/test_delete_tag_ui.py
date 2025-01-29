# Standard library
from time import sleep

# External libraries
from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from src.cli.mock_constants import MOCK_URL_TITLES
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.tags_ui.utils_for_test_tag_ui import (
    hover_tag_badge,
    show_delete_tag_button_on_hover,
)
from tests.functional.urls_ui.utils_for_test_url_ui import (
    delete_url,
    open_update_url_title,
)
from tests.functional.utils_for_test import (
    get_selected_url,
    get_selected_url_tags,
    get_tag_badge_by_name,
    get_url_by_title,
    login_user_select_utub_by_name_and_url_by_title,
    login_utub_url,
    select_url_by_title,
    login_user,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_visible_css_selector,
)
from locators import HomePageLocators as HPL

pytestmark = pytest.mark.tags_ui


def test_show_delete_tag_button_on_hover(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests a user's ability to create a new URL in a selected UTub

    GIVEN a user has access to UTubs, URLs, and tags
    WHEN user hovers over tag badge
    THEN ensure the deleteTag button is displayed
    """
    app = provide_app
    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    url_row = get_selected_url(browser)

    url_tags = get_selected_url_tags(url_row)

    delete_tag_button = show_delete_tag_button_on_hover(browser, url_tags[0])

    assert delete_tag_button.is_displayed()


# @pytest.mark.skip(reason="Testing another in isolation")
def test_delete_tag(browser, create_test_tags):
    """
    Tests a user's ability to delete tags from a URL

    GIVEN a user has access to UTubs with URLs and tags applied
    WHEN user clicks the deleteTag button
    THEN ensure the tag is removed from the URL
    """

    login_utub_url(browser)

    url_row = get_selected_url(browser)
    tag_badges = get_selected_url_tags(url_row)
    tag_to_delete = tag_badges[0]
    tag_name = tag_to_delete.find_element(By.CLASS_NAME, "tagText").get_attribute(
        "innerText"
    )

    delete_tag_button = show_delete_tag_button_on_hover(browser, tag_to_delete)
    delete_tag_button.click()

    # Wait for DELETE request
    sleep(4)

    # Assert tag no longer exists in URL
    assert not get_tag_badge_by_name(url_row, tag_name)


# @pytest.mark.skip(reason="Bug. Currently FAILS")
def test_no_show_delete_tag_button_on_hover_update_url_title(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests the limitation on users, preventing deletion of tags while updating URL titles

    GIVEN a user has selected a URL they added to a UTub
    WHEN user clicks the editURLTitle button, and subsequently hovers over a tag
    THEN ensure the deleteTag button is not displayed
    """
    app = provide_app
    user_id_for_test = 1
    url_title = UTS.TEST_URL_TITLE_1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, url_title
    )

    selected_url_row = get_url_by_title(browser, url_title)

    open_update_url_title(browser, selected_url_row)

    wait_until_visible_css_selector(browser, HPL.INPUT_URL_TITLE_UPDATE)

    url_tags = get_selected_url_tags(selected_url_row)

    delete_tag_button = show_delete_tag_button_on_hover(browser, url_tags[0])

    assert not delete_tag_button.is_displayed()


def test_no_show_delete_tag_button_on_hover_update_url_string(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests the limitation on users, preventing deletion of tags while updating URL strings

    GIVEN a user has selected a URL they added to a UTub
    WHEN user clicks the editURLTitle button, and subsequently hovers over a tag
    THEN ensure the deleteTag button is not displayed
    """
    app = provide_app
    user_id_for_test = 1
    url_title = UTS.TEST_URL_TITLE_1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, url_title
    )

    selected_url_row = get_url_by_title(browser, url_title)

    selected_url_row.find_element(By.CSS_SELECTOR, HPL.BUTTON_URL_STRING_UPDATE).click()

    wait_until_visible_css_selector(browser, HPL.INPUT_URL_STRING_UPDATE)

    url_tags = get_selected_url_tags(selected_url_row)
    first_tag_badge = url_tags[0]

    hover_tag_badge(browser, first_tag_badge)

    delete_tag_button = first_tag_badge.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_TAG_DELETE
    )

    assert not delete_tag_button.is_displayed()


def test_no_show_delete_tag_button_on_hover_add_tag(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests the limitation on users, preventing deletion of tags while adding tags

    GIVEN a user has selected a URL they added to a UTub
    WHEN user clicks the addTag button, and subsequently hovers over a tag
    THEN ensure the deleteTag button is not displayed
    """
    app = provide_app
    user_id_for_test = 1
    url_title = UTS.TEST_URL_TITLE_1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, url_title
    )

    selected_url_row = get_url_by_title(browser, url_title)

    selected_url_row.find_element(By.CSS_SELECTOR, HPL.BUTTON_TAG_CREATE).click()

    wait_until_visible_css_selector(browser, HPL.INPUT_TAG_CREATE)

    url_tags = get_selected_url_tags(selected_url_row)
    first_tag_badge = url_tags[0]

    hover_tag_badge(browser, first_tag_badge)

    delete_tag_button = first_tag_badge.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_TAG_DELETE
    )

    assert not delete_tag_button.is_displayed()


@pytest.mark.skip(reason="Test not yet implemented")
def test_delete_last_tag(browser, create_test_tags):
    """
    Tests the site response to a user deleting the final instance of an applied tag in the selected UTub

    GIVEN a user has access to UTubs with URLs and tags applied
    WHEN user clicks the deleteTag button on the last instance of the tag in the UTub
    THEN ensure the tag is removed from the URL and the Tag Deck
    """

    login_user(browser)

    # Find submit button to login
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    utub_name = UTS.TEST_UTUB_NAME_1
    select_utub_by_name(browser, utub_name)

    # Select URL
    url_title = MOCK_URL_TITLES[0]
    url_row = select_url_by_title(browser, url_title)

    delete_url(browser, url_row)

    warning_modal_body = wait_then_get_element(browser, HPL.BODY_MODAL)
    confirmation_modal_body_text = warning_modal_body.get_attribute("innerText")

    url_delete_check_text = UTS.BODY_MODAL_URL_DELETE

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == url_delete_check_text

    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT)

    # Wait for DELETE request
    sleep(4)

    # Assert URL no longer exists in UTub
    assert not select_url_by_title(browser, url_title)


# TODO: Check invalid CSRF token for sad path tests
