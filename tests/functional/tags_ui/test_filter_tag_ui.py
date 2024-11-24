# Standard library

# External libraries
# import pytest
from flask import Flask
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

# Internal libraries
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.tags_ui.utils_for_test_tag_ui import (
    delete_each_tag_from_one_url_in_utub,
    delete_tag_from_url_in_utub_random,
)
from tests.functional.utils_for_test import (
    get_all_tag_ids_in_url_row,
    get_num_url_unfiltered_rows,
    get_tag_filter_by_id,
    get_tag_filter_by_name,
    get_tag_filter_id,
    get_tag_filter_name_by_id,
    get_url_row_by_id,
    get_url_by_title,
    get_utub_tag_filters,
    login_user_select_utub_by_name_and_url_by_title,
    wait_then_get_element,
    wait_then_get_elements,
)


# @pytest.mark.skip(reason="Testing another in isolation")
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

    utub_title = UTS.TEST_UTUB_NAME_1

    # From the db, delete a random tag from a random URL in the current UTub
    utub_url_id, utub_tag_id = delete_tag_from_url_in_utub_random(app, utub_title)

    # Load page
    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, utub_title, UTS.TEST_URL_TITLE_1
    )

    # Find URL row to be filtered
    url_row = get_url_row_by_id(browser, utub_url_id)

    # Save the URL title for assertion after filtering it out
    url_title = url_row.find_element(By.CLASS_NAME, "urlTitle").get_attribute(
        "innerText"
    )

    # Extract the filtered tag name
    tag_name = get_tag_filter_name_by_id(browser, utub_tag_id)

    # Assert appropriate initial state of unselectAll button
    unselect_all_button = wait_then_get_element(browser, MPL.SELECTOR_UNSELECT_ALL)
    unselect_all_button_class_list = unselect_all_button.get_attribute("class")
    assert "disabled" in unselect_all_button_class_list
    assert "unselected" in unselect_all_button_class_list

    # Select tag filter associated with the name of the tag badge deleted above
    corresponding_tag_filter = get_tag_filter_by_name(browser, tag_name)
    corresponding_tag_filter.click()

    # Assert appropriate behavior of unselectAll button
    unselect_all_button_class_list = unselect_all_button.get_attribute("class")
    assert "disabled" not in unselect_all_button_class_list
    assert "unselected" in unselect_all_button_class_list

    # Assert tag filter is applied
    assert "selected" in corresponding_tag_filter.get_attribute("class")

    # Assert filtered URL is now no longer visible to user
    assert not get_url_by_title(browser, url_title)


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

    utub_title = UTS.TEST_UTUB_NAME_1

    # From the db, delete a random tag from a random URL in the current UTub
    utub_url_id, utub_tag_id = delete_tag_from_url_in_utub_random(app, utub_title)

    # Load page
    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, utub_title, UTS.TEST_URL_TITLE_1
    )

    # Find URL row to be filtered
    url_row = get_url_row_by_id(browser, utub_url_id)

    # Save the URL title for assertion after filtering it out
    url_title = url_row.find_element(By.CLASS_NAME, "urlTitle").get_attribute(
        "innerText"
    )

    # Select tag filter associated with the id of the tag badge deleted above
    corresponding_tag_filter = get_tag_filter_by_id(browser, utub_tag_id)
    corresponding_tag_filter.click()

    # Assert filtered URL is now no longer visible to user
    assert not get_url_by_title(browser, url_title)

    # Unselect tag filter
    corresponding_tag_filter.click()

    # Assert unfiltered URL is now visible to user
    assert get_url_by_title(browser, url_title)


def test_unselect_all_filters(
    browser: WebDriver, create_test_tags, provide_app_for_session_generation: Flask
):
    """
    Tests a user's ability to unfilter the URL deck by deselecting tag filter.

    GIVEN a user has access to UTubs with URLs with tags applied, and user removes all but one
    WHEN the associated tag filter is selected in the TagDeck
    THEN ensure the corresponding URL is hidden
    """

    app = provide_app_for_session_generation

    utub_title = UTS.TEST_UTUB_NAME_1

    # From the db, delete a different tag from each URL in the current UTub
    delete_each_tag_from_one_url_in_utub(app, utub_title)

    # Load page
    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app, browser, user_id_for_test, utub_title, UTS.TEST_URL_TITLE_1
    )

    # Save the number of visible URLs
    num_visible_url_rows = get_num_url_unfiltered_rows(browser)
    unfiltered_url_rows: list[WebElement] = wait_then_get_elements(
        browser, MPL.ROWS_URLS
    )

    tag_filters = get_utub_tag_filters(browser)

    # Apply each tag filter. Assert URLs without the associated tagBadge are hidden
    for tag_filter in tag_filters:
        tag_id = get_tag_filter_id(tag_filter)

        # Find all URLs that don't have this tag. Save the titles for check
        filtered_url_row_titles: list[str] = []
        for i, url_row in enumerate(unfiltered_url_rows):
            url_tag_ids = get_all_tag_ids_in_url_row(url_row)
            if tag_id in url_tag_ids:
                filtered_url_row = unfiltered_url_rows.pop(i)

                # Save the URL title for assertion after filtering it out
                url_title = filtered_url_row.find_element(
                    By.CLASS_NAME, "urlTitle"
                ).get_attribute("innerText")
                filtered_url_row_titles.append(url_title)

        # Apply the tag filter
        corresponding_tag_filter = get_tag_filter_by_id(browser, tag_id)
        corresponding_tag_filter.click()

        # Assert all URLs that didn't have the tag are now hidden
        for url_title in filtered_url_row_titles:
            assert not get_url_by_title(browser, url_title)

    # All URLs with tags are filtered

    # Unselect all tag filters
    unselect_all_button = wait_then_get_element(browser, MPL.SELECTOR_UNSELECT_ALL)
    unselect_all_button.click()

    # Assert all URLs are unfiltered and are now visible to user
    assert num_visible_url_rows == get_num_url_unfiltered_rows(browser)
