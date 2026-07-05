from flask import Flask
import pytest
from playwright.sync_api import Page

from backend import db
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    add_tag_to_utub_user_created,
    create_test_searchable_urls_with_tags,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid,
)
from tests.functional.playwright_utils import (
    select_utub_by_id,
    wait_then_click_element,
    wait_then_get_element,
)
from tests.functional.tags_ui.playwright_utils import get_utub_tag_filter_selector
from tests.functional.urls_ui.playwright_utils import (
    focus_url_search_input,
    wait_for_url_search_filter_applied,
)

pytestmark = pytest.mark.tags_ui

UNMATCHED_TAG_STRING = "unmatched-tag"


def test_tag_filter_hides_all_urls_shows_no_results_message(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with URLs and a tag applied to the UTub but not to any URL
    WHEN the user selects that tag as a filter
    THEN the no-results message is displayed and all URL rows are hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UNMATCHED_TAG_STRING
    )

    login_user_and_select_utub_by_utubid(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
    )

    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=tag_in_utub.id)
    wait_then_click_element(page=page, css_selector=utub_tag_filter)

    assert_visible_css_selector(page=page, css_selector=HPL.TAG_FILTER_NO_RESULTS)

    no_results_elem = wait_then_get_element(
        page=page, css_selector=HPL.TAG_FILTER_NO_RESULTS
    )
    assert no_results_elem.inner_text() == UTS.TAG_FILTER_NO_URLS

    url_row_elements = page.locator(HPL.ROWS_URLS).all()
    for url_row in url_row_elements:
        assert not url_row.is_visible()


def test_unselect_tag_filter_hides_no_results_message(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with the tag filter no-results message displayed
    WHEN the user clicks the same tag filter again to unselect it
    THEN the no-results message is hidden and all URL rows are visible
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UNMATCHED_TAG_STRING
    )

    login_user_and_select_utub_by_utubid(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
    )

    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=tag_in_utub.id)
    wait_then_click_element(page=page, css_selector=utub_tag_filter)

    assert_visible_css_selector(page=page, css_selector=HPL.TAG_FILTER_NO_RESULTS)

    # Unselect the tag
    wait_then_click_element(page=page, css_selector=utub_tag_filter)

    assert_not_visible_css_selector(page=page, css_selector=HPL.TAG_FILTER_NO_RESULTS)

    url_row_elements = page.locator(HPL.ROWS_URLS).all()
    for url_row in url_row_elements:
        assert url_row.is_visible()


def test_unselect_all_button_hides_no_results_message(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with the tag filter no-results message displayed
    WHEN the user clicks the "unselect all" tag filters button
    THEN the no-results message is hidden and all URL rows are visible
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UNMATCHED_TAG_STRING
    )

    login_user_and_select_utub_by_utubid(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
    )

    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=tag_in_utub.id)
    wait_then_click_element(page=page, css_selector=utub_tag_filter)

    assert_visible_css_selector(page=page, css_selector=HPL.TAG_FILTER_NO_RESULTS)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UNSELECT_ALL)

    assert_not_visible_css_selector(page=page, css_selector=HPL.TAG_FILTER_NO_RESULTS)

    url_row_elements = page.locator(HPL.ROWS_URLS).all()
    for url_row in url_row_elements:
        assert url_row.is_visible()


def test_partial_tag_filter_does_not_show_no_results(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with URLs where a tag is applied to some but not all URLs
    WHEN the user selects that tag as a filter
    THEN the no-results message is NOT displayed (some URLs remain visible)
    """
    app = provide_app
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
        # Apply tag to first URL only so some remain visible
        utub_url = utub_urls[0]
        new_url_tag = Utub_Url_Tags(
            utub_id=utub_user_created.id,
            utub_url_id=utub_url.id,
            utub_tag_id=tag_id,
        )
        db.session.add(new_url_tag)
        db.session.commit()

    login_user_and_select_utub_by_utubid(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
    )

    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=tag_id)
    wait_then_click_element(page=page, css_selector=utub_tag_filter)

    assert_not_visible_css_selector(page=page, css_selector=HPL.TAG_FILTER_NO_RESULTS)

    url_row_elements = page.locator(HPL.ROWS_URLS).all()
    visible_urls = [url_row for url_row in url_row_elements if url_row.is_visible()]
    assert len(visible_urls) >= 1


def test_switching_utub_hides_no_results_message(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with the tag filter no-results message displayed
    WHEN the user switches to a different UTub
    THEN the no-results message is hidden in the new UTub
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UNMATCHED_TAG_STRING
    )

    second_utub = get_utub_this_user_created(app, 2)
    second_utub_id = second_utub.id

    login_user_and_select_utub_by_utubid(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
    )

    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=tag_in_utub.id)
    wait_then_click_element(page=page, css_selector=utub_tag_filter)

    assert_visible_css_selector(page=page, css_selector=HPL.TAG_FILTER_NO_RESULTS)

    select_utub_by_id(page=page, utub_id=second_utub_id)

    assert_not_visible_css_selector(page=page, css_selector=HPL.TAG_FILTER_NO_RESULTS)


def test_tag_filter_no_results_with_search_active(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with URLs, an active search, and an unmatched tag filter
    WHEN the user applies the unmatched tag filter while search is active
    THEN the tag filter no-results message is shown and the search no-results is NOT shown
    """
    app = provide_app
    user_id_for_test = 1

    url_title_to_id, utub_tag_id, utub_id = create_test_searchable_urls_with_tags(
        app, user_id_for_test
    )
    unmatched_tag = add_tag_to_utub_user_created(
        app, utub_id, user_id_for_test, UNMATCHED_TAG_STRING
    )

    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.URL_SEARCH_UTUB_NAME,
    )

    focus_url_search_input(page=page)
    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)
    assert search_input is not None
    search_input.fill(UTS.URL_SEARCH_TITLES[0])
    wait_for_url_search_filter_applied(page=page)

    # Apply the unmatched tag filter to hide all URLs
    unmatched_tag_filter = get_utub_tag_filter_selector(utub_tag_id=unmatched_tag.id)
    wait_then_click_element(page=page, css_selector=unmatched_tag_filter)

    assert_visible_css_selector(page=page, css_selector=HPL.TAG_FILTER_NO_RESULTS)
    assert_not_visible_css_selector(page=page, css_selector=HPL.URL_SEARCH_NO_RESULTS)


def test_tag_filter_aria_announcement(page: Page, create_test_urls, provide_app: Flask):
    """
    GIVEN a UTub with URLs and an unmatched tag
    WHEN the user selects then unselects the tag filter
    THEN the aria-live announcement is populated when message shows and cleared when hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UNMATCHED_TAG_STRING
    )

    login_user_and_select_utub_by_utubid(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
    )

    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=tag_in_utub.id)
    wait_then_click_element(page=page, css_selector=utub_tag_filter)

    assert_visible_css_selector(page=page, css_selector=HPL.TAG_FILTER_NO_RESULTS)

    announcement_elem = wait_then_get_element(
        page=page, css_selector=HPL.TAG_FILTER_ANNOUNCEMENT
    )
    assert (
        announcement_elem.evaluate("element => element.textContent")
        == UTS.TAG_FILTER_NO_URLS
    )

    # Unselect to hide the message
    wait_then_click_element(page=page, css_selector=utub_tag_filter)

    assert_not_visible_css_selector(page=page, css_selector=HPL.TAG_FILTER_NO_RESULTS)

    announcement_elem = wait_then_get_element(
        page=page, css_selector=HPL.TAG_FILTER_ANNOUNCEMENT
    )
    assert announcement_elem.evaluate("element => element.textContent") == ""


def test_zero_urls_utub_tag_filter_does_not_show_no_results(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub with zero URLs and a tag added to the UTub
    WHEN the user selects that tag as a filter
    THEN the no-results message remains hidden (zero-URL UTub should not trigger the message)
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UNMATCHED_TAG_STRING
    )

    login_user_and_select_utub_by_utubid(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
    )

    assert page.locator(HPL.ROWS_URLS).count() == 0

    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=tag_in_utub.id)
    wait_then_click_element(page=page, css_selector=utub_tag_filter)

    assert_not_visible_css_selector(page=page, css_selector=HPL.TAG_FILTER_NO_RESULTS)
