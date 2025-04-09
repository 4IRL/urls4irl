from flask import Flask
import pytest
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from src import db
from src.models.utub_tags import Utub_Tags
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utub_urls import Utub_Urls
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.tags_ui.utils_for_test_tag_ui import (
    add_tag_to_utub_user_created,
    add_two_tags_across_urls_in_utub,
    apply_tag_based_on_id_and_get_shown_urls,
    get_utub_tag_badge_selector,
)
from tests.functional.utils_for_test import (
    get_utub_this_user_created,
    login_user_and_select_utub_by_utubid,
    wait_then_click_element,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.tags_ui


def test_filter_tag_with_all_urls_filtered(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to filter a specific tag in the URL deck by selecting a tag filter.

    GIVEN a user has access to UTubs with URLs with no tags on any URLs
    WHEN the user selects a tag from the tag deck
    THEN ensure all URLs are hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, "TestTag"
    )

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )
    utub_tag_badge_selector = get_utub_tag_badge_selector(tag_in_utub.id)
    wait_then_click_element(browser, utub_tag_badge_selector, time=3)

    url_row_elements = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    for url_row in url_row_elements:
        assert not url_row.is_displayed()


def test_filter_tag_with_some_urls_filtered(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to filter a specific tag in the URL deck by selecting a tag filter.

    GIVEN a user has access to UTubs with URLs with tags on some URLs
    WHEN the user selects a tag from the tag deck
    THEN ensure some URLs are hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, "TestTag"
    )
    tag_id = tag_in_utub.id

    with app.app_context():
        utub_urls: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_created.id
        ).all()
        urls_tag_applied_to = len(utub_urls) - 2
        for idx in range(urls_tag_applied_to):
            utub_url = utub_urls[idx]
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
    displayed_urls = apply_tag_based_on_id_and_get_shown_urls(browser, tag_id)
    assert len(displayed_urls) == urls_tag_applied_to


def test_filter_tag_with_no_urls_filtered(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to filter a specific tag in the URL deck by selecting a tag filter.

    GIVEN a user has access to UTubs with URLs with tags on some URLs
    WHEN the user selects a tag from the tag deck
    THEN ensure no URLs are hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, "TestTag"
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
    displayed_urls = apply_tag_based_on_id_and_get_shown_urls(browser, tag_id)
    assert len(displayed_urls) == urls_tag_applied_to


def test_filter_multiple_tags_with_some_urls_filtered(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to filter a specific tag in the URL deck by selecting a tag filter.

    GIVEN a user has access to UTubs with URLs with tags on some URLs
    WHEN the user selects a tag from the tag deck applied to some, and then another tag applied to some
    THEN ensure some URLs are hidden
    """
    app = provide_app
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

    displayed_urls_for_first_tag = apply_tag_based_on_id_and_get_shown_urls(
        browser, first_tag_id
    )
    assert len(displayed_urls_for_first_tag) == num_urls_for_first_tag

    displayed_urls_for_second_tag = apply_tag_based_on_id_and_get_shown_urls(
        browser, second_tag_id
    )
    assert len(displayed_urls_for_second_tag) == num_urls_for_second_tag


def test_unselect_button_toggle_when_filter_selected(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to toggle the unselect all tag filters button

    GIVEN a user has access to UTubs with URLs with no tags on any URLs
    WHEN the user selects a tag from the tag deck
    THEN ensure the unselect all tag filters button is clickable
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, "TestTag"
    )

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )

    unselect_filters_btn = browser.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_UNSELECT_ALL
    )

    with pytest.raises(
        (ElementNotInteractableException, ElementClickInterceptedException)
    ):
        unselect_filters_btn.click()

    utub_tag_badge_selector = get_utub_tag_badge_selector(tag_in_utub.id)
    wait_then_click_element(browser, utub_tag_badge_selector, time=3)

    unselect_filters_btn = browser.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_UNSELECT_ALL
    )
    unselect_filters_btn.click()


def test_unselect_button_unselects_all_tags_when_clicked(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests a user's ability to unselect tags using the unselect all tag button

    GIVEN a user has access to UTubs with URLs with all tag filters selected
    WHEN the user clicks the unselect tag button
    THEN ensure all tags are then unselected
    """
    app = provide_app
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
        utub_tag_badge_selector = get_utub_tag_badge_selector(utub_tag_id)
        wait_then_click_element(browser, utub_tag_badge_selector, time=3)

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


def test_unfilter_tag_with_all_urls_filtered(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to filter a specific tag in the URL deck by selecting a tag filter.

    GIVEN a user has access to UTubs with URLs with no tags on any URLs
    WHEN the user selects a tag from the tag deck
    THEN ensure all URLs are hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, "TestTag"
    )

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )
    utub_tag_badge_selector = get_utub_tag_badge_selector(tag_in_utub.id)
    wait_then_click_element(browser, utub_tag_badge_selector, time=3)

    # Click again to unselect the tag and show all filtered URLs
    wait_then_click_element(browser, utub_tag_badge_selector, time=3)

    url_row_elements = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    for url_row in url_row_elements:
        assert url_row.is_displayed()


def test_unfilter_multiple_tags_with_some_urls_filtered(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to filter a specific tag in the URL deck by selecting a tag filter.

    GIVEN a user has access to UTubs with URLs with tags on some URLs
    WHEN the user selects a tag from the tag deck applied to some, and then another tag applied to some
    THEN ensure some URLs are hidden
    """
    app = provide_app
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

    num_utub_urls, num_urls_for_first_tag, num_urls_for_second_tag = (
        add_two_tags_across_urls_in_utub(
            app, utub_user_created.id, first_tag_id, second_tag_id
        )
    )

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )

    apply_tag_based_on_id_and_get_shown_urls(browser, first_tag_id)
    filtered_urls = apply_tag_based_on_id_and_get_shown_urls(browser, second_tag_id)

    assert len(filtered_urls) == num_urls_for_second_tag

    utub_tag_badge_selector = get_utub_tag_badge_selector(second_tag_id)
    wait_then_click_element(browser, utub_tag_badge_selector, time=3)

    url_row_elements = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    assert (
        len([url_row for url_row in url_row_elements if url_row.is_displayed()])
        == num_urls_for_first_tag
    )

    utub_tag_badge_selector = get_utub_tag_badge_selector(first_tag_id)
    wait_then_click_element(browser, utub_tag_badge_selector, time=3)

    url_row_elements = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    assert (
        len([url_row for url_row in url_row_elements if url_row.is_displayed()])
        == num_utub_urls
    )


def test_filter_tag_attempt_with_tag_limit_reached(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests a user's ability to attempt to add another tag filter when at the limit

    GIVEN a user has access to UTubs with URLs with tags on all URLs
    WHEN the user attempts to select a tag from the tag deck above the tag limit
    THEN ensure user cannot select the tag
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )
    wait_until_visible_css_selector(
        browser, f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}", timeout=3
    )

    with app.app_context():
        utub_tags: list[Utub_Tags] = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_user_created.id
        ).all()
        utub_tag_ids = [utub_tag.id for utub_tag in utub_tags]

    # Add the extra tag above the limit
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, "TestTag"
    )

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )
    wait_until_visible_css_selector(
        browser, f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}", timeout=3
    )

    for utub_tag_id in utub_tag_ids:
        utub_tag_badge_selector = get_utub_tag_badge_selector(utub_tag_id)
        wait_then_click_element(browser, utub_tag_badge_selector, time=3)

    utub_tag_badge_selector = get_utub_tag_badge_selector(tag_in_utub.id)

    utub_tag_badge = browser.find_element(By.CSS_SELECTOR, utub_tag_badge_selector)
    with pytest.raises(
        (ElementNotInteractableException, ElementClickInterceptedException)
    ):
        utub_tag_badge.click()


def test_filter_tag_clickable_after_unclicking_from_tag_limit(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests a user's ability to attempt to add another tag filter when at the limit

    GIVEN a user has access to UTubs with URLs with tags on all URLs
    WHEN the user attempts to select a tag from the tag deck after going above, then below the tag selection limit
    THEN ensure user can select the tag
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )
    wait_until_visible_css_selector(
        browser, f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}", timeout=3
    )

    with app.app_context():
        utub_tags: list[Utub_Tags] = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_user_created.id
        ).all()
        utub_tag_ids = [utub_tag.id for utub_tag in utub_tags]

    # Add the extra tag above the limit
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, "TestTag"
    )

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )
    wait_until_visible_css_selector(
        browser, f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}", timeout=3
    )

    utub_tag_id = -1
    for utub_tag_id in utub_tag_ids:
        utub_tag_badge_selector = get_utub_tag_badge_selector(utub_tag_id)
        wait_then_click_element(browser, utub_tag_badge_selector, time=3)

    # Click the last UTub tag id again to unselect it
    utub_tag_badge_selector = get_utub_tag_badge_selector(utub_tag_id)
    wait_then_click_element(browser, utub_tag_badge_selector, time=3)

    utub_tag_badge_selector = get_utub_tag_badge_selector(tag_in_utub.id)

    utub_tag_badge = browser.find_element(By.CSS_SELECTOR, utub_tag_badge_selector)
    utub_tag_badge.click()


# TODO: Test URL hidden when all tags selected, all tags on URL, and one of tags on URL is deleted
