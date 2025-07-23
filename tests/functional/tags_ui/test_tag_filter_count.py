from flask import Flask, url_for
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from src import db
from src.models.utub_tags import Utub_Tags
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utub_urls import Utub_Urls
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import TAG_FORM
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.tags_ui.utils_for_test_tag_ui import (
    add_tag_to_url,
    add_tag_to_utub_user_created,
    add_two_tags_across_urls_in_utub,
    apply_tag_filter_by_id_and_get_shown_urls,
    count_urls_with_tag_applied_by_tag_id,
    count_urls_with_tag_applied_by_tag_string,
    get_urls_count_with_tag_applied_from_tag_filter_by_tag_id,
    get_utub_tag_filter_selector,
)
from tests.functional.urls_ui.utils_for_test_url_ui import get_url_in_utub
from tests.functional.utils_for_test import (
    get_tag_id_by_name,
    get_utub_this_user_created,
    login_user_and_select_utub_by_utubid,
    login_user_select_utub_by_id_and_url_by_id,
    wait_then_click_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from src.cli.mock_constants import MOCK_TAGS

pytestmark = pytest.mark.tags_ui


# CREATE
def test_tag_filter_count_after_add_fresh_tag_to_url(
    browser: WebDriver, create_test_urls, app: Flask
):
    """
    Tests the tag filter count in the Tag Deck when a new tag badge is applied to an existing URL.

    GIVEN a user has access to UTubs with URLs with no tags on any URLs
    WHEN the user adds a tag to a URL
    THEN ensure a new corresponding tag filter is created and its count is instantiated at 1
    """
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    # Login and select UTub and URL
    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.url_id
    )

    # Create tag badge
    add_tag_to_url(browser, url_in_utub.url_id, UTS.TEST_TAG_NAME_1)
    # Submit
    btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_SUBMIT_CREATE}"
    wait_then_click_element(browser, btn_selector, time=3)

    # Wait for POST request
    wait_until_hidden(browser, btn_selector, timeout=3)

    tag_id = get_tag_id_by_name(app, utub_user_created.id, UTS.TEST_TAG_NAME_1)

    # Assert the tag filter count is 1
    tag_filter_count = get_urls_count_with_tag_applied_from_tag_filter_by_tag_id(
        browser, tag_id
    )

    assert (
        tag_filter_count == 1
    ), f"Expected tag filter count to be 1, but got {tag_filter_count} for tag ID {tag_id}"


def test_tag_filter_count_after_add_existing_tag_to_url(
    browser: WebDriver, create_test_urls, login_first_user_without_register, app: Flask
):
    """
    Tests the tag filter count in the Tag Deck when an existing tag is added to an existing URL.

    GIVEN a user has access to UTubs with URLs AND tags
    WHEN the user adds a tag to a URL
    THEN ensure the corresponding tag filter is incremented by 1
    """
    client, csrf_token, _, _ = login_first_user_without_register

    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)
    url_id = url_in_utub.url_id

    new_tag_string = MOCK_TAGS[0]

    # Create UTub Tag to apply to URL
    new_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: new_tag_string,
    }

    client.post(
        url_for(ROUTES.UTUB_TAGS.CREATE_UTUB_TAG, utub_id=utub_id),
        data=new_tag_form,
    )

    with app.app_context():
        # Assert UTub Tag count is instantiated at 0.
        init_tag_filter_count = count_urls_with_tag_applied_by_tag_string(
            app, utub_id, new_tag_string
        )
        assert init_tag_filter_count == 0

    # Login and select UTub and URL
    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_id, url_id
    )

    # Create tag badge
    add_tag_to_url(browser, url_id, new_tag_string)
    # Submit
    btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_SUBMIT_CREATE}"
    wait_then_click_element(browser, btn_selector, time=3)

    # Wait for POST request
    wait_until_hidden(browser, btn_selector, timeout=3)

    # Assert the tag filter count is incremented by 1
    tag_filter_count = count_urls_with_tag_applied_by_tag_string(
        app, utub_id, new_tag_string
    )

    assert init_tag_filter_count + 1 == tag_filter_count


def test_tag_filter_count_on_tag_filter_creation(
    browser: WebDriver, create_test_utubs, app: Flask
):
    """
    Tests the tag filter count in the Tag Deck when a new tag filter is created to an existing URL.

    GIVEN a user has access to UTubs without URLs
    WHEN the user adds a tag to the Tag Deck
    THEN ensure the new tag filter count is instantiated at 0
    """

    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )
    tag_id = tag_in_utub.id

    assert count_urls_with_tag_applied_by_tag_id(app, tag_id) == 0


# READ
def test_tag_filter_count_display_on_utub_selection(
    browser: WebDriver, create_test_tags, app: Flask
):
    """
    Tests the tag filter count in the Tag Deck when a UTub is selected.

    GIVEN a user has access to UTubs
    WHEN the user selects a UTub
    THEN ensure the tag filter counts are displayed alongside the tag filters in the Tag Deck
    """
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )
    tag_id = tag_in_utub.id

    with app.app_context():
        utub_urls: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_created.id
        ).all()
        urls_tag_applied_to = len(utub_urls)
        for utub_url in utub_urls:
            new_url_tag = Utub_Url_Tags(
                utub_id=utub_user_created.id,
                utub_url_id=utub_url.id,
                utub_tag_id=tag_id,
            )
            db.session.add(new_url_tag)
        db.session.commit()

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )
    displayed_urls = apply_tag_filter_by_id_and_get_shown_urls(browser, tag_id)
    assert len(displayed_urls) == urls_tag_applied_to


def test_tag_filter_count_display_on_utub_selection_change(
    browser: WebDriver, create_test_tags, app: Flask
):
    """
    Tests the tag filter count in the Tag Deck when a new UTub is selected.

    GIVEN a user has access to UTubs, and has one displayed
    WHEN the user selects another UTub
    THEN ensure the tag filter counts are updated to reflect those of the new UTub
    """
    # This test needs to have a starting point where the user has multiple UTubs with varied numbers (and possible values) for tags. As is, create_test_tags will have 5 instances of each tag on all URLs in all UTubs. The tag filter count will be 5 for all tags.

    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )
    tag_id = tag_in_utub.id

    with app.app_context():
        utub_urls: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_created.id
        ).all()
        urls_tag_applied_to = len(utub_urls)
        for utub_url in utub_urls:
            new_url_tag = Utub_Url_Tags(
                utub_id=utub_user_created.id,
                utub_url_id=utub_url.id,
                utub_tag_id=tag_id,
            )
            db.session.add(new_url_tag)
        db.session.commit()

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )
    displayed_urls = apply_tag_filter_by_id_and_get_shown_urls(browser, tag_id)
    assert len(displayed_urls) == urls_tag_applied_to


# DELETE
def test_tag_filter_count_update_on_tag_badge_removal(
    browser: WebDriver, create_test_tags, app: Flask
):
    """
    Tests the tag filter count in the Tag Deck when a tag badge is remove from an existing URL.

    GIVEN a user has access to UTubs with URLs and tags
    WHEN the user removes a tag from a URL
    THEN ensure the corresponding tag filter is decremented by 1
    """

    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    first_tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, "TestTag1"
    )
    first_tag_id = first_tag_in_utub.id
    second_tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, "TestTag2"
    )
    second_tag_id = second_tag_in_utub.id

    _, num_urls_for_first_tag, num_urls_for_second_tag = (
        add_two_tags_across_urls_in_utub(
            app, utub_user_created.id, first_tag_id, second_tag_id
        )
    )

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )

    displayed_urls_for_first_tag = apply_tag_filter_by_id_and_get_shown_urls(
        browser, first_tag_id
    )
    assert len(displayed_urls_for_first_tag) == num_urls_for_first_tag

    displayed_urls_for_second_tag = apply_tag_filter_by_id_and_get_shown_urls(
        browser, second_tag_id
    )
    assert len(displayed_urls_for_second_tag) == num_urls_for_second_tag


def test_tag_filter_count_update_on_url_deletion(
    browser: WebDriver, create_test_tags, app: Flask
):
    """
    Tests the tag filter count in the Tag Deck when a URL with tags applied is deleted from the UTub.

    GIVEN a user has access to UTubs with URLs and tags
    WHEN the user deletes a URL with tags applied
    THEN ensure all the corresponding tag filters are each decremented by 1
    """

    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    with app.app_context():
        utub_tags: list[Utub_Tags] = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_user_created.id
        ).all()
        utub_tag_ids = [utub_tag.id for utub_tag in utub_tags]

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )
    wait_until_visible_css_selector(
        browser, f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}", timeout=3
    )

    assert len(
        browser.find_elements(By.CSS_SELECTOR, f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}")
    ) == len(utub_tag_ids)

    for utub_tag_id in utub_tag_ids:
        utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id)
        wait_then_click_element(browser, utub_tag_filter, time=3)

    assert (
        len(
            browser.find_elements(By.CSS_SELECTOR, f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}")
        )
        == 0
    )
    assert len(
        browser.find_elements(By.CSS_SELECTOR, f"{HPL.TAG_FILTERS}{HPL.SELECTED}")
    ) == len(utub_tag_ids)

    unselect_filters_btn = browser.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_UNSELECT_ALL
    )
    unselect_filters_btn.click()
    assert (
        len(browser.find_elements(By.CSS_SELECTOR, f"{HPL.TAG_FILTERS}{HPL.SELECTED}"))
        == 0
    )
    assert len(
        browser.find_elements(By.CSS_SELECTOR, f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}")
    ) == len(utub_tag_ids)
