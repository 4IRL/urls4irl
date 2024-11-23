# Standard library

# External libraries
# import pytest
from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.tags_ui.utils_for_test_tag_ui import (
    show_delete_tag_button_on_hover,
)
from tests.functional.utils_for_test import (
    delete_tag_from_url_in_utub,
    get_selected_url,
    get_tag_badge_by_id,
    get_tag_filter_by_name,
    get_url_row_by_id,
    get_url_by_title,
    login_user_select_utub_by_name_and_url_by_title,
    wait_then_get_element,
)


# @pytest.mark.skip(reason="Testing another in isolation")
def test_filter_tag2(
    browser: WebDriver, create_test_tags, provide_app_for_session_generation: Flask
):
    """
    Tests a user's ability to filter the URL deck by selecting a tag filter.

    GIVEN a user has access to UTubs with URLs with tags applied, and user removes all but one
    WHEN the associated tag filter is selected in the TagDeck
    THEN ensure the corresponding URL is hidden
    """

    app = provide_app_for_session_generation

    utub_title = UTS.TEST_UTUB_NAME_1

    utub_url_id, utub_tag_id = delete_tag_from_url_in_utub(app, utub_title)

    url_row = get_url_row_by_id(browser, utub_url_id)
    tag_badge = get_tag_badge_by_id(browser, utub_url_id, utub_tag_id)

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, utub_title, UTS.TEST_URL_TITLE_1
    )

    # Save the URL title for assertion after filtering it out
    url_title = url_row.find_element(By.CLASS_NAME, "urlTitle").get_attribute(
        "innerText"
    )

    # Delete first tag badge from first URL row
    tag_badge_name = tag_badge.find_element(By.TAG_NAME, "span").get_attribute(
        "innerText"
    )

    # Assert appropriate initial state of unselectAll button
    unselect_all_button = wait_then_get_element(browser, MPL.SELECTOR_UNSELECT_ALL)
    unselect_all_button_class_list = unselect_all_button.get_attribute("class")
    assert "disabled" in unselect_all_button_class_list
    assert "unselected" in unselect_all_button_class_list

    # Select tag filter associated with the name of the tag badge deleted above
    corresponding_tag_filter = get_tag_filter_by_name(browser, tag_badge_name)
    corresponding_tag_filter.click()

    # Assert appropriate behavior of unselectAll button
    unselect_all_button_class_list = unselect_all_button.get_attribute("class")
    assert "disabled" not in unselect_all_button_class_list
    assert "unselected" in unselect_all_button_class_list

    # Assert tag filter is applied
    assert "selected" in corresponding_tag_filter.get_attribute("class")

    # Assert filtered URL is now no longer visible to user
    assert not get_url_by_title(browser, url_title)


@pytest.mark.skip(reason="Testing another in isolation")
def test_filter_tag(
    browser: WebDriver, create_test_tags, provide_app_for_session_generation: Flask
):
    """
    Tests a user's ability to filter the URL deck by selecting a tag filter.

    GIVEN a user has access to UTubs with URLs with tags applied, and user removes all but one
    WHEN the associated tag filter is selected in the TagDeck
    THEN ensure the corresponding URL is hidden
    """
    app = provide_app_for_session_generation
    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )

    # Save the URL title for assertion after filtering it out
    first_url_row = get_selected_url(browser)
    first_url_title = first_url_row.find_element(
        By.CLASS_NAME, "urlTitle"
    ).get_attribute("innerText")

    # Delete first tag badge from first URL row
    first_tag_badge = first_url_row.find_elements(By.CSS_SELECTOR, MPL.TAG_BADGES)[0]
    first_tag_badge_name = first_tag_badge.find_element(
        By.TAG_NAME, "span"
    ).get_attribute("innerText")
    delete_tag_button = show_delete_tag_button_on_hover(browser, first_tag_badge)
    delete_tag_button.click()

    # Assert appropriate initial state of unselectAll button
    unselect_all_button = wait_then_get_element(browser, MPL.SELECTOR_UNSELECT_ALL)
    unselect_all_button_class_list = unselect_all_button.get_attribute("class")
    assert "disabled" in unselect_all_button_class_list
    assert "unselected" in unselect_all_button_class_list

    # Select tag filter associated with the name of the tag badge deleted above
    corresponding_tag_filter = get_tag_filter_by_name(browser, first_tag_badge_name)
    corresponding_tag_filter.click()

    # Assert appropriate behavior of unselectAll button
    unselect_all_button_class_list = unselect_all_button.get_attribute("class")
    assert "disabled" not in unselect_all_button_class_list
    assert "unselected" in unselect_all_button_class_list

    # Assert tag filter is applied
    assert "selected" in corresponding_tag_filter.get_attribute("class")

    # Assert filtered URL is now no longer visible to user
    assert not get_url_by_title(browser, first_url_title)


def test_unfilter_tag(
    browser: WebDriver, create_test_tags, provide_app_for_session_generation: Flask
):
    """
    Tests a user's ability to unfilter the URL deck by deselecting tag filter.

    GIVEN a user has access to UTubs with URLs with tags applied, and user removes all but one
    WHEN the associated tag filter is selected in the TagDeck
    THEN ensure the corresponding URL is hidden
    """
    app = provide_app_for_session_generation
    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1, UTS.TEST_URL_TITLE_1
    )
