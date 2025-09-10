from typing import List
from flask import Flask, url_for
import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from src import db
from src.models.urls import Urls
from src.models.utub_tags import Utub_Tags
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utub_urls import Utub_Urls
from src.models.utubs import Utubs
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import TAG_FORM
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from src.utils.strings.url_strs import DELETE_URL_WARNING
from tests.functional.db_utils import (
    add_tag_to_utub_user_created,
    add_two_tags_across_urls_in_utub,
    count_urls_with_tag_applied_by_tag_string,
    get_tag_id_by_name,
    get_tag_in_utub_by_tag_string,
    get_url_in_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from src.cli.mock_constants import MOCK_TAGS
from tests.functional.login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_select_utub_by_id_and_url_by_id,
)
from tests.functional.selenium_utils import (
    get_num_url_rows,
    select_utub_by_id,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
)
from tests.functional.tags_ui.selenium_utils import (
    add_tag_to_url,
    apply_tag_filter_by_id_and_get_shown_urls,
    get_visible_urls_and_urls_with_tag_text_by_tag_id,
)
from tests.functional.urls_ui.login_utils import (
    login_select_utub_select_url_click_delete_get_modal_url,
)

pytestmark = pytest.mark.tags_ui


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

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.url_id
    )

    add_tag_to_url(browser, url_in_utub.url_id, UTS.TEST_TAG_NAME_1)

    btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_SUBMIT_CREATE}"
    wait_then_click_element(browser, btn_selector, time=3)

    wait_until_hidden(browser, btn_selector, timeout=3)

    tag_id = get_tag_id_by_name(app, utub_user_created.id, UTS.TEST_TAG_NAME_1)

    vis_count, total_count = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, tag_id
    )

    assert vis_count == 1
    assert total_count == 1


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

    new_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: new_tag_string,
    }

    client.post(
        url_for(ROUTES.UTUB_TAGS.CREATE_UTUB_TAG, utub_id=utub_id),
        data=new_tag_form,
    )

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_id, url_id
    )

    tag_id = get_tag_id_by_name(app, utub_id, new_tag_string)
    init_vis, init_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, tag_id
    )
    assert init_vis == 0
    assert init_total == 0

    add_tag_to_url(browser, url_id, new_tag_string)
    btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_SUBMIT_CREATE}"
    wait_then_click_element(browser, btn_selector, time=3)

    wait_until_hidden(browser, btn_selector, timeout=3)
    final_vis, final_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, tag_id
    )
    assert final_vis == init_vis + 1
    assert final_total == init_total + 1


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

    login_user_and_select_utub_by_utubid(
        app,
        browser,
        user_id_for_test,
        utub_user_created.id,
    )

    tag_id = tag_in_utub.id
    visible, total = get_visible_urls_and_urls_with_tag_text_by_tag_id(browser, tag_id)
    assert visible == 0
    assert total == 0


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

    visible, total = get_visible_urls_and_urls_with_tag_text_by_tag_id(browser, tag_id)
    assert visible == urls_tag_applied_to
    assert total == urls_tag_applied_to


def test_tag_filter_count_display_on_utub_selection_change(
    browser: WebDriver, create_test_tags, app: Flask
):
    """
    Tests the tag filter count in the Tag Deck when a new UTub is selected.

    This test needs to have a starting point where the user has multiple UTubs with varied numbers (and possible values) for tags.
    As is, create_test_tags will have 5 instances of each tag on all URLs in all UTubs. The tag filter count will be 5 for all tags.

    GIVEN a user has access to UTubs, and has one displayed
    WHEN the user selects another UTub
    THEN ensure the tag filter counts are updated to reflect those of the new UTub
    """
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)

    with app.app_context():
        new_tag = Utub_Tags(
            utub_id=utub_user_member_of.id,
            tag_string=UTS.TEST_TAG_NAME_1,
            created_by=user_id_for_test,
        )
        db.session.add(new_tag)
        db.session.commit()
        tag_id = get_tag_id_by_name(app, utub_user_member_of.id, UTS.TEST_TAG_NAME_1)

        utub_urls: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_member_of.id
        ).all()
        urls_tag_applied_to = len(utub_urls)
        for utub_url in utub_urls:
            new_url_tag = Utub_Url_Tags(
                utub_id=utub_user_member_of.id,
                utub_url_id=utub_url.id,
                utub_tag_id=tag_id,
            )
            db.session.add(new_url_tag)
        db.session.commit()

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )
    select_utub_by_id(browser, utub_user_member_of.id)

    displayed_urls = apply_tag_filter_by_id_and_get_shown_urls(browser, tag_id)
    assert len(displayed_urls) == urls_tag_applied_to

    visible, total = get_visible_urls_and_urls_with_tag_text_by_tag_id(browser, tag_id)
    assert visible == urls_tag_applied_to
    assert total == urls_tag_applied_to


def test_tag_filter_count_update_with_multiple_tag_filters_applied(
    browser: WebDriver, create_test_tags, app: Flask
):
    """
    Tests the tag filter count in the Tag Deck when two tag badges are applied to.
    all available URLs in the UTub.

    GIVEN a user has access to UTubs with URLs and tags
    WHEN the user applies two tag filters
    THEN ensure the corresponding tag filter count is correct
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

    first_vis_init, first_total_init = (
        get_visible_urls_and_urls_with_tag_text_by_tag_id(browser, first_tag_id)
    )
    assert first_vis_init == num_urls_for_first_tag
    assert first_total_init == num_urls_for_first_tag

    second_vis_init, second_total_init = (
        get_visible_urls_and_urls_with_tag_text_by_tag_id(browser, second_tag_id)
    )
    assert second_vis_init == num_urls_for_second_tag
    assert second_total_init == num_urls_for_second_tag

    displayed_urls_for_second_tag = apply_tag_filter_by_id_and_get_shown_urls(
        browser, second_tag_id
    )
    assert len(displayed_urls_for_second_tag) == num_urls_for_second_tag

    first_vis_final, first_total_final = (
        get_visible_urls_and_urls_with_tag_text_by_tag_id(browser, first_tag_id)
    )
    assert first_vis_final == num_urls_for_second_tag
    assert first_total_final == num_urls_for_first_tag

    second_vis_final, second_total_final = (
        get_visible_urls_and_urls_with_tag_text_by_tag_id(browser, second_tag_id)
    )
    assert second_vis_final == num_urls_for_second_tag
    assert second_total_final == num_urls_for_second_tag


def test_delete_url_decrements_all_tag_counters(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests U4I's ability to decrement the tag counters when deleting a URL with all 5 tags
    visible in the Tag Deck

    GIVEN a user, selected UTub and selected URL
    WHEN deleteURL button is selected and confirmation modal confirmed
    THEN ensure the URL is deleted from the UTub, and the tag counters are decremented
    """
    user_id_for_test = 1
    app = provide_app

    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.name == UTS.TEST_UTUB_NAME_1).first()
        url: Urls = Urls.query.filter(
            Urls.url_string == UTS.TEST_URL_STRING_CREATE
        ).first()

        utub_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub.id, Utub_Urls.url_id == url.id
        ).first()
        url_tags: List[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub.id, Utub_Url_Tags.utub_url_id == utub_url.id
        ).all()

        utub_tag_ids = [tag.utub_tag_id for tag in url_tags]

    delete_modal, url_elem_to_delete = (
        login_select_utub_select_url_click_delete_get_modal_url(
            browser=browser,
            app=provide_app,
            user_id=user_id_for_test,
            utub_name=UTS.TEST_UTUB_NAME_1,
            url_string=UTS.TEST_URL_STRING_CREATE,
        )
    )

    init_vis_total = {}
    for tag_id in utub_tag_ids:
        init_vis_total[tag_id] = get_visible_urls_and_urls_with_tag_text_by_tag_id(
            browser, tag_id
        )

    css_selector = f'{HPL.URL_STRING_READ}[href="{UTS.TEST_URL_STRING_CREATE}"]'
    assert browser.find_element(By.CSS_SELECTOR, css_selector)

    init_num_url_rows = get_num_url_rows(browser)

    confirmation_modal_body_text = delete_modal.text

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == DELETE_URL_WARNING

    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(browser, HPL.BUTTON_MODAL_SUBMIT)

    # Wait for animation to complete
    assert wait_for_element_to_be_removed(browser, url_elem_to_delete)

    # Assert URL no longer exists in UTub
    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, css_selector)
    assert init_num_url_rows - 1 == get_num_url_rows(browser)

    for tag_id in utub_tag_ids:
        final_vis, final_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
            browser, tag_id
        )
        init_vis, init_total = init_vis_total[tag_id]
        assert final_vis == init_vis - 1
        assert final_total == init_total - 1


def test_create_fresh_tag_sets_count(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to create a fresh tag to a URL.

    GIVEN a user has access to UTubs with URLs
    WHEN the createTag form is populated with a tag value that is not yet in the UTub
    THEN ensure the appropriate tag is applied and displayed and the counter is incremented
    """
    tag_text = UTS.TEST_TAG_NAME_1
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)
    with app.app_context():
        init_tag_count_on_url: int = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_utub.id,
        ).count()

        init_tag_count_in_utub: int = count_urls_with_tag_applied_by_tag_string(
            app, utub_id, tag_text
        )

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    add_tag_to_url(browser, url_in_utub.id, tag_text)

    # Submit
    btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_SUBMIT_CREATE}"
    wait_then_click_element(browser, btn_selector, time=3)

    # Wait for POST request
    wait_until_hidden(browser, btn_selector, timeout=3)

    # Confirm Tag Deck counter incremented
    utub_tag = get_tag_in_utub_by_tag_string(app, utub_id, tag_text)
    utub_tag_selector = f'{HPL.TAG_FILTERS}[data-utub-tag-id="{utub_tag.id}"]'
    utub_tag_elem = wait_then_get_element(browser, utub_tag_selector)
    assert utub_tag_elem

    visible_urls, total_urls = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, utub_tag.id
    )
    assert visible_urls == init_tag_count_on_url + 1
    assert total_urls == init_tag_count_in_utub + 1


def test_create_non_fresh_tag_increments_counts(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to create a non-fresh tag to a URL.

    GIVEN a user has access to UTubs with URLs
    WHEN the createTag form is populated with a tag value that is already in the UTub
    THEN ensure the appropriate tag is applied and displayed and the counter is incremented
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)
    tag_already_in_utub_str = "Another"
    with app.app_context():
        utub_tag = add_tag_to_utub_user_created(
            app=app,
            tag_string=tag_already_in_utub_str,
            utub_id=utub_id,
            user_id=user_id_for_test,
        )

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    init_vis, init_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, utub_tag.id
    )

    add_tag_to_url(browser, url_in_utub.id, tag_already_in_utub_str)

    # Submit
    btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_SUBMIT_CREATE}"
    wait_then_click_element(browser, btn_selector, time=3)

    # Wait for POST request
    wait_until_hidden(browser, btn_selector, timeout=3)

    # Confirm Tag Deck counter incremented
    visible_urls, total_urls = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, utub_tag.id
    )
    assert visible_urls == init_vis + 1
    assert total_urls == init_total + 1
