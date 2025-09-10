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
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    add_tag_to_utub_user_created,
    add_two_tags_across_urls_in_utub,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import ModalLocators as ML
from tests.functional.login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_select_utub_by_id_and_url_by_id,
)
from tests.functional.tags_ui.selenium_utils import (
    add_tag_to_url,
    apply_tag_filter_by_id_and_get_shown_urls,
    get_delete_tag_button_on_hover,
    get_tag_badge_selector_on_selected_url_by_tag_id,
    get_utub_tag_filter_selector,
    get_visible_urls_and_urls_with_tag_text_by_tag_id,
)
from tests.functional.selenium_utils import (
    get_css_selector_for_url_by_id,
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_hidden,
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
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )
    utub_tag_filter = get_utub_tag_filter_selector(tag_in_utub.id)
    wait_then_click_element(browser, utub_tag_filter, time=3)

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
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
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
    displayed_urls = apply_tag_filter_by_id_and_get_shown_urls(browser, tag_id)
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


def test_filter_multiple_tags_with_some_urls_filtered(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to filter URLs by selecting tag filters.

    GIVEN a user has access to UTubs with URLs with tags on some URLs
    WHEN the user selects a tag from the tag deck applied to some URLs, and then another tag applied to some URLs
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

    displayed_urls_for_first_tag = apply_tag_filter_by_id_and_get_shown_urls(
        browser, first_tag_id
    )
    assert len(displayed_urls_for_first_tag) == num_urls_for_first_tag

    displayed_urls_for_second_tag = apply_tag_filter_by_id_and_get_shown_urls(
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
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
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

    utub_tag_filter = get_utub_tag_filter_selector(tag_in_utub.id)
    wait_then_click_element(browser, utub_tag_filter, time=3)

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

    for utub_tag_id in utub_tag_ids:
        utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id)
        wait_then_click_element(browser, utub_tag_filter, time=3)

    unselected_tags = wait_then_get_elements(
        browser, f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}", time=3
    )
    assert len(unselected_tags) == 0

    selected_tags = wait_then_get_elements(
        browser, f"{HPL.TAG_FILTERS}{HPL.SELECTED}", time=3
    )
    assert len(selected_tags) == len(utub_tag_ids)

    wait_then_click_element(browser, HPL.BUTTON_UNSELECT_ALL, time=3)

    selected_tags = wait_then_get_elements(
        browser, f"{HPL.TAG_FILTERS}{HPL.SELECTED}", time=3
    )
    assert len(selected_tags) == 0

    assert (
        len(browser.find_elements(By.CSS_SELECTOR, f"{HPL.TAG_FILTERS}{HPL.SELECTED}"))
        == 0
    )
    unselected_tags = wait_then_get_elements(
        browser, f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}", time=3
    )
    assert len(unselected_tags) == len(utub_tag_ids)


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
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )
    utub_tag_filter = get_utub_tag_filter_selector(tag_in_utub.id)
    wait_then_click_element(browser, utub_tag_filter, time=3)

    # Click again to unselect the tag and show all filtered URLs
    wait_then_click_element(browser, utub_tag_filter, time=3)

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

    apply_tag_filter_by_id_and_get_shown_urls(browser, first_tag_id)
    filtered_urls = apply_tag_filter_by_id_and_get_shown_urls(browser, second_tag_id)

    assert len(filtered_urls) == num_urls_for_second_tag

    utub_tag_filter = get_utub_tag_filter_selector(second_tag_id)
    wait_then_click_element(browser, utub_tag_filter, time=3)

    url_row_elements = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    assert (
        len([url_row for url_row in url_row_elements if url_row.is_displayed()])
        == num_urls_for_first_tag
    )

    utub_tag_filter = get_utub_tag_filter_selector(first_tag_id)
    wait_then_click_element(browser, utub_tag_filter, time=3)

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
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )
    wait_until_visible_css_selector(
        browser, f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}", timeout=3
    )

    for utub_tag_id in utub_tag_ids:
        utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id)
        wait_then_click_element(browser, utub_tag_filter, time=3)

    utub_tag_filter = get_utub_tag_filter_selector(tag_in_utub.id)

    utub_tag_badge = browser.find_element(By.CSS_SELECTOR, utub_tag_filter)
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
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )
    wait_until_visible_css_selector(
        browser, f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}", timeout=3
    )

    utub_tag_id = -1
    for utub_tag_id in utub_tag_ids:
        utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id)
        wait_then_click_element(browser, utub_tag_filter, time=3)

    # Click the last UTub tag id again to unselect it
    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id)
    wait_then_click_element(browser, utub_tag_filter, time=3)

    utub_tag_filter = get_utub_tag_filter_selector(tag_in_utub.id)

    utub_tag_badge = browser.find_element(By.CSS_SELECTOR, utub_tag_filter)
    utub_tag_badge.click()


def test_filtered_url_hides_when_filter_tag_deleted(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests U4I's decrementing of tag counts when deleting URL tag while a tag filter is applied.

    GIVEN a user has access to UTubs with URLs with tags on some URLs and the URLs are filtered
    WHEN the user deletes a URL tag that is shown while filtering
    THEN ensure the tag counter decrements and the URL hides
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
        url_id_to_hide = utub_urls[0].id

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, utub_url_id=url_id_to_hide
    )
    displayed_urls = apply_tag_filter_by_id_and_get_shown_urls(browser, tag_id)
    assert len(displayed_urls) == urls_tag_applied_to

    selected_url_selector = get_css_selector_for_url_by_id(url_id_to_hide)
    init_vis, init_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, tag_id
    )

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(tag_id)
    delete_tag_button = get_delete_tag_button_on_hover(browser, tag_badge_selector)
    delete_tag_button.click()

    # Wait for DELETE request
    wait_until_hidden(browser, selected_url_selector, timeout=3)
    final_vis, final_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, tag_id
    )
    assert final_vis == init_vis - 1
    assert final_total == init_total - 1


def test_filtered_url_count_decrements_when_url_deleted(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests U4I's decrementing of tag counts when deleting URL while a tag filter is applied.

    GIVEN a user has access to UTubs with URLs with tags on some URLs and the URLs are filtered
    WHEN the user deletes a URL that is shown while filtering
    THEN ensure the tag counter decrements
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
        url_id_to_hide = utub_urls[0].id

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, utub_url_id=url_id_to_hide
    )
    displayed_urls = apply_tag_filter_by_id_and_get_shown_urls(browser, tag_id)
    assert len(displayed_urls) == urls_tag_applied_to

    selected_url_selector = get_css_selector_for_url_by_id(url_id_to_hide)
    init_vis, init_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, tag_id
    )

    wait_for_animation_to_end_check_top_lhs_corner(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )
    wait_then_click_element(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}", time=3
    )
    wait_until_visible_css_selector(browser, ML.ELEMENT_MODAL, timeout=3)
    modal = wait_then_get_element(browser, HPL.BODY_MODAL)
    assert modal is not None

    url_elem_to_delete = browser.find_element(By.CSS_SELECTOR, selected_url_selector)

    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(browser, HPL.BUTTON_MODAL_SUBMIT)

    # Wait for DELETE request
    assert wait_for_element_to_be_removed(browser, url_elem_to_delete)
    final_vis, final_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, tag_id
    )
    assert final_vis == init_vis - 1
    assert final_total == init_total - 1


def test_filtered_url_count_increments_for_another_tag_while_filtered_when_added(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests U4I's incrementing of tag counts while adding a tag when a tag filter is applied.

    GIVEN a user has access to UTubs with URLs with tags on some URLs and the URLs are filtered
    WHEN the user adds a tag to a filtered URL
    THEN ensure the tag counter increments
    """
    app = provide_app
    user_id_for_test = 1
    new_tag_str = "Another"
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
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
        url_id_to_add_tag = utub_urls[0].id

        add_tag_to_utub_user_created(
            app=app,
            tag_string=new_tag_str,
            utub_id=utub_user_created.id,
            user_id=user_id_for_test,
        )

        new_tag = Utub_Tags.query.filter(Utub_Tags.tag_string == new_tag_str).first()
        new_tag_id = new_tag.id

    login_user_select_utub_by_id_and_url_by_id(
        app,
        browser,
        user_id_for_test,
        utub_user_created.id,
        utub_url_id=url_id_to_add_tag,
    )
    displayed_urls = apply_tag_filter_by_id_and_get_shown_urls(browser, tag_id)
    assert len(displayed_urls) == urls_tag_applied_to

    init_vis, init_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, new_tag_id
    )

    add_tag_to_url(browser, url_id_to_add_tag, new_tag_str)
    btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_SUBMIT_CREATE}"
    wait_then_click_element(browser, btn_selector, time=3)

    # Wait for POST request
    wait_until_hidden(browser, btn_selector, timeout=3)

    final_vis, final_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, new_tag_id
    )
    assert final_vis == init_vis + 1
    assert final_total == init_total + 1
