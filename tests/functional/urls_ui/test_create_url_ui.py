from typing import Tuple

from flask import Flask
from flask.testing import FlaskCliRunner
import pytest
from playwright.sync_api import Page, expect

from backend.cli.mock_constants import (
    MOCK_URL_TITLES,
    MOCK_URL_STRINGS,
    MOCK_URL_TRACKING_STRIPPED,
    MOCK_URL_WITH_TRACKING_PARAMS,
)
from backend.models.users import Users
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_urls import Utub_Urls
from backend.utils.constants import CONSTANTS, TAG_CONSTANTS
from backend.utils.strings.json_strs import FIELD_REQUIRED_STR
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from backend.utils.strings.url_strs import URL_FAILURE
from tests.functional.db_utils import (
    add_mock_urls,
    add_tag_to_single_url_in_utub,
    add_tag_to_utub_user_created,
    count_urls_with_tag_applied_by_tag_string,
    get_newly_added_utub_url_id_by_url_string,
    get_tag_in_utub_by_tag_string,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_login_with_username,
    assert_not_visible_css_selector,
    assert_on_429_page,
    assert_url_coloring_is_correct,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid,
)
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    clear_then_send_keys,
    get_selected_url,
    get_url_row_by_id,
    invalidate_csrf_token_on_page,
    wait_for_element_presence,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.tags_ui.playwright_utils import (
    apply_tag_filter_based_on_id,
    get_visible_urls_and_urls_with_tag_text_by_tag_id,
)
from tests.functional.urls_ui.playwright_utils import (
    create_url,
    fill_create_url_form,
    stage_new_tag_in_create_form,
    stage_tag_suggestion_in_create_form,
)

pytestmark = pytest.mark.create_urls_ui


def test_create_url_open_input_no_urls_corner_btn(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Test that clicking on the + in the URL Deck opens up the new URL input when
    there are no URLs previously generated

    GIVEN a user and selected UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """
    app = provide_app
    user_id_for_test = 1
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=UTS.TEST_UTUB_NAME_1
    )

    url_creation_row = page.locator(HPL.WRAP_URL_CREATE).first
    expect(url_creation_row).to_be_hidden()

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(
        page=page, css_selector=HPL.WRAP_URL_CREATE
    )
    expect(url_creation_row).to_be_visible()

    assert_not_visible_css_selector(page=page, css_selector=HPL.BUTTON_DECK_URL_CREATE)

    wait_until_visible_css_selector(page=page, css_selector=HPL.INPUT_URL_TITLE_CREATE)
    expect(page.locator(HPL.INPUT_URL_TITLE_CREATE)).to_be_focused()


def test_create_url_open_input_no_urls_deck_btn(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Test that clicking on the 'Add One!' button in the URL Deck opens up the new URL input when
    there are no URLs previously generated

    GIVEN a user and selected UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """
    app = provide_app
    user_id_for_test = 1
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=UTS.TEST_UTUB_NAME_1
    )

    url_creation_row = page.locator(HPL.WRAP_URL_CREATE).first
    expect(url_creation_row).to_be_hidden()

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_DECK_URL_CREATE)

    url_creation_row = wait_then_get_element(
        page=page, css_selector=HPL.WRAP_URL_CREATE
    )
    expect(url_creation_row).to_be_visible()

    assert_not_visible_css_selector(page=page, css_selector=HPL.BUTTON_DECK_URL_CREATE)

    wait_until_visible_css_selector(page=page, css_selector=HPL.INPUT_URL_TITLE_CREATE)
    expect(page.locator(HPL.INPUT_URL_TITLE_CREATE)).to_be_focused()


def test_create_url_open_input_with_added_urls(
    page: Page,
    create_test_utubs,
    create_test_urls,
    provide_app: Flask,
):
    """
    Test that clicking on the + in the URL Deck opens up the new URL input when
    there previously generated URLs

    GIVEN a user and selected UTub
    WHEN click on the + to add a new URL after URLs have already been added
    THEN ensure the appropriate input field is shown and in focus
    """
    app = provide_app
    user_id_for_test = 1
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=UTS.TEST_UTUB_NAME_1
    )

    url_creation_row = page.locator(HPL.WRAP_URL_CREATE).first
    expect(url_creation_row).to_be_hidden()

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(
        page=page, css_selector=HPL.WRAP_URL_CREATE
    )
    expect(url_creation_row).to_be_visible()

    wait_until_visible_css_selector(page=page, css_selector=HPL.INPUT_URL_TITLE_CREATE)
    expect(page.locator(HPL.INPUT_URL_TITLE_CREATE)).to_be_focused()


def test_create_url_cancel_input_click_button(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to escape URL creation input by clicking the cancel button

    GIVEN a user attempting to create a URL
    WHEN they are focused on the input  boxes in the URL creation elements and click the cancel button
    THEN ensure the input is closed

    """
    app = provide_app
    user_id_for_test = 1
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=UTS.TEST_UTUB_NAME_1
    )

    url_creation_row = page.locator(HPL.WRAP_URL_CREATE).first
    expect(url_creation_row).to_be_hidden()

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(
        page=page, css_selector=HPL.WRAP_URL_CREATE
    )
    expect(url_creation_row).to_be_visible()

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_CANCEL_CREATE)

    url_creation_row = page.locator(HPL.WRAP_URL_CREATE).first
    expect(url_creation_row).to_be_hidden()


def test_create_url_cancel_input_escape(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to escape URL creation input by using escape key

    GIVEN a user attempting to create a URL
    WHEN they are focused on the input  boxes in the URL creation elements and use the escape key
    THEN ensure the input is closed

    """
    app = provide_app
    user_id_for_test = 1
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=UTS.TEST_UTUB_NAME_1
    )

    url_creation_row = page.locator(HPL.WRAP_URL_CREATE).first
    expect(url_creation_row).to_be_hidden()

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(
        page=page, css_selector=HPL.WRAP_URL_CREATE
    )
    expect(url_creation_row).to_be_visible()

    page.keyboard.press("Escape")

    url_creation_row = page.locator(HPL.WRAP_URL_CREATE).first
    expect(url_creation_row).to_be_hidden()


def test_create_url_submit_btn_no_urls(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to create a new URL in a selected UTub

    GIVEN a user and selected UTub
    WHEN they submit a new URL using the submit button
    THEN ensure the URL is added and input is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0]

    fill_create_url_form(page=page, url_title=url_title, url_string=url_string)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SUBMIT_CREATE)

    # Wait for HTTP request to complete
    wait_until_hidden(page=page, css_selector=HPL.INPUT_URL_STRING_CREATE)
    url_creation_row = page.locator(HPL.WRAP_URL_CREATE).first
    expect(url_creation_row).to_be_hidden()

    # Extract URL title and string from new row in URL deck
    utub_url_id = get_newly_added_utub_url_id_by_url_string(
        app, utub_user_created.id, url_string
    )
    url_row = get_url_row_by_id(page=page, utub_url_id=utub_url_id)

    url_row_title = url_row.locator(HPL.URL_TITLE_READ).inner_text()
    url_row_string = url_row.locator(HPL.URL_STRING_READ).inner_text()
    url_row_href = url_row.locator(HPL.URL_STRING_READ).get_attribute(
        HPL.URL_STRING_IN_DATA
    )

    url_string_visible = url_string.replace("https://", "").replace("www.", "")

    assert url_title == url_row_title
    assert url_row_string == url_string_visible
    assert url_string == url_row_href

    assert_url_coloring_is_correct(page=page)

    url_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    wait_until_visible_css_selector(page=page, css_selector=url_selector)
    selected_url = get_selected_url(page=page)
    selected_utub_url_id = selected_url.get_attribute("utuburlid")

    assert selected_utub_url_id and selected_utub_url_id.isnumeric()
    assert int(selected_utub_url_id) == utub_url_id


def test_create_url_submit_btn_some_urls(
    page: Page,
    provide_app: Flask,
    create_test_urls,
):
    """
    Tests a user's ability to create a new URL in a selected UTub

    GIVEN a user and selected UTub
    WHEN they submit a new URL using the submit button
    THEN ensure the URL is added and input is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0] + "extraextra"

    fill_create_url_form(page=page, url_title=url_title, url_string=url_string)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SUBMIT_CREATE)

    # Wait for HTTP request to complete
    wait_until_hidden(page=page, css_selector=HPL.INPUT_URL_STRING_CREATE)
    url_creation_row = page.locator(HPL.WRAP_URL_CREATE).first
    expect(url_creation_row).to_be_hidden()

    # Extract URL title and string from new row in URL deck
    utub_url_id = get_newly_added_utub_url_id_by_url_string(
        app, utub_user_created.id, url_string
    )
    url_row = get_url_row_by_id(page=page, utub_url_id=utub_url_id)

    url_row_title = url_row.locator(HPL.URL_TITLE_READ).inner_text()
    url_row_string = url_row.locator(HPL.URL_STRING_READ).inner_text()
    url_row_href = url_row.locator(HPL.URL_STRING_READ).get_attribute(
        HPL.URL_STRING_IN_DATA
    )

    url_string_visible = url_string.replace("https://", "").replace("www.", "")

    assert url_title == url_row_title
    assert url_row_string == url_string_visible
    assert url_string == url_row_href

    assert_url_coloring_is_correct(page=page)

    url_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    wait_until_visible_css_selector(page=page, css_selector=url_selector)
    selected_url = get_selected_url(page=page)
    selected_utub_url_id = selected_url.get_attribute("utuburlid")

    assert selected_utub_url_id and selected_utub_url_id.isnumeric()
    assert int(selected_utub_url_id) == utub_url_id


def test_create_url_rate_limits(page: Page, create_test_utubs, provide_app: Flask):
    """
    Tests a user's ability to create a new URL in a selected UTub when rate limited

    GIVEN a user and selected UTub but they are rate limited
    WHEN they submit a new URL using the submit button
    THEN ensure the 429 error page is shown
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0]

    fill_create_url_form(page=page, url_title=url_title, url_string=url_string)
    add_forced_rate_limit_header(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SUBMIT_CREATE)

    assert_on_429_page(page=page)


@pytest.mark.parametrize(
    "validated_url,input_url",
    [
        ("https://example.com/", "https://example.com"),
        ("https://example.com/", "example.com"),
        ("https://example.com/", " https://example.com "),
    ],
)
def test_valid_url_input(
    page: Page,
    provide_app: Flask,
    create_test_urls,
    validated_url: str,
    input_url: str,
):
    """
    Tests a user's ability to create a new URL in a selected UTub

    GIVEN a user and selected UTub
    WHEN they submit a new URL using the submit button
    THEN ensure the URL is added and input is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    ada_validated_url = validated_url

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    url_title = MOCK_URL_TITLES[0]

    fill_create_url_form(page=page, url_title=url_title, url_string=input_url)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SUBMIT_CREATE)

    # Wait for HTTP request to complete
    wait_until_hidden(page=page, css_selector=HPL.INPUT_URL_STRING_CREATE)
    url_creation_row = page.locator(HPL.WRAP_URL_CREATE).first
    expect(url_creation_row).to_be_hidden()

    # Extract URL title and string from new row in URL deck
    utub_url_id = get_newly_added_utub_url_id_by_url_string(
        app, utub_user_created.id, ada_validated_url
    )
    url_row = get_url_row_by_id(page=page, utub_url_id=utub_url_id)

    url_row_title = url_row.locator(HPL.URL_TITLE_READ).inner_text()
    url_row_string = url_row.locator(HPL.URL_STRING_READ).inner_text()
    url_row_href = url_row.locator(HPL.URL_STRING_READ).get_attribute(
        HPL.URL_STRING_IN_DATA
    )

    url_string_visible = ada_validated_url
    url_string_visible = url_string_visible.removeprefix("https://")
    url_string_visible = url_string_visible.removeprefix("http://")
    url_string_visible = url_string_visible.removeprefix("www.")

    assert url_title == url_row_title
    assert url_row_string == url_string_visible
    assert url_row_href is not None
    assert url_row_href == ada_validated_url

    assert_url_coloring_is_correct(page=page)

    url_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    wait_until_visible_css_selector(page=page, css_selector=url_selector)
    selected_url = get_selected_url(page=page)
    selected_utub_url_id = selected_url.get_attribute("utuburlid")

    assert selected_utub_url_id and selected_utub_url_id.isnumeric()
    assert int(selected_utub_url_id) == utub_url_id


def test_create_url_using_enter_key_no_urls(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to create a new URL in a selected UTub

    GIVEN a user and selected UTub
    WHEN they submit a new URL using the submit button
    THEN ensure the URL is added and input is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0]

    fill_create_url_form(page=page, url_title=url_title, url_string=url_string)
    page.keyboard.press("Enter")

    # Wait for HTTP request to complete
    wait_until_hidden(page=page, css_selector=HPL.INPUT_URL_STRING_CREATE)
    url_creation_row = page.locator(HPL.WRAP_URL_CREATE).first
    expect(url_creation_row).to_be_hidden()

    # Extract URL title and string from new row in URL deck
    utub_url_id = get_newly_added_utub_url_id_by_url_string(
        app, utub_user_created.id, url_string
    )
    url_row = get_url_row_by_id(page=page, utub_url_id=utub_url_id)

    url_row_title = url_row.locator(HPL.URL_TITLE_READ).inner_text()
    url_row_string = url_row.locator(HPL.URL_STRING_READ).inner_text()
    url_row_href = url_row.locator(HPL.URL_STRING_READ).get_attribute(
        HPL.URL_STRING_IN_DATA
    )

    url_string_visible = url_string.replace("https://", "").replace("www.", "")

    assert url_title == url_row_title
    assert url_row_string == url_string_visible
    assert url_string == url_row_href

    assert_url_coloring_is_correct(page=page)

    url_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    wait_until_visible_css_selector(page=page, css_selector=url_selector)
    selected_url = get_selected_url(page=page)
    selected_utub_url_id = selected_url.get_attribute("utuburlid")

    assert selected_utub_url_id and selected_utub_url_id.isnumeric()
    assert int(selected_utub_url_id) == utub_url_id


def test_create_url_using_enter_key_some_urls(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to create a new URL in a selected UTub

    GIVEN a user and selected UTub
    WHEN they submit a new URL using the submit button
    THEN ensure the URL is added and input is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0] + "extraextra"

    fill_create_url_form(page=page, url_title=url_title, url_string=url_string)
    page.keyboard.press("Enter")

    # Wait for HTTP request to complete
    wait_until_hidden(page=page, css_selector=HPL.INPUT_URL_STRING_CREATE)
    url_creation_row = page.locator(HPL.WRAP_URL_CREATE).first
    expect(url_creation_row).to_be_hidden()

    # Extract URL title and string from new row in URL deck
    utub_url_id = get_newly_added_utub_url_id_by_url_string(
        app, utub_user_created.id, url_string
    )
    url_row = get_url_row_by_id(page=page, utub_url_id=utub_url_id)

    url_row_title = url_row.locator(HPL.URL_TITLE_READ).inner_text()
    url_row_string = url_row.locator(HPL.URL_STRING_READ).inner_text()
    url_row_href = url_row.locator(HPL.URL_STRING_READ).get_attribute(
        HPL.URL_STRING_IN_DATA
    )

    url_string_visible = url_string.replace("https://", "").replace("www.", "")

    assert url_title == url_row_title
    assert url_row_string == url_string_visible
    assert url_string == url_row_href

    assert_url_coloring_is_correct(page=page)

    url_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    wait_until_visible_css_selector(page=page, css_selector=url_selector)
    selected_url = get_selected_url(page=page)
    selected_utub_url_id = selected_url.get_attribute("utuburlid")

    assert selected_utub_url_id and selected_utub_url_id.isnumeric()
    assert int(selected_utub_url_id) == utub_url_id


def test_create_url_title_length_exceeded(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to create a new URL with a title that exceeds the maximum character length limit.

    GIVEN a user and selected UTub
    WHEN the createURL form is populated and submitted with a title that exceeds character limits
    THEN ensure the appropriate error and prompt is shown to user.
    """

    # Login test user and select first test UTub
    app = provide_app

    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(
        page=page, css_selector=HPL.WRAP_URL_CREATE
    )
    expect(url_creation_row).to_be_visible()

    # Input new URL Title
    url_title_input_field = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_URL_TITLE_CREATE
    )
    clear_then_send_keys(
        locator=url_title_input_field,
        input_text="a" * (CONSTANTS.URLS.MAX_URL_TITLE_LENGTH + 1),
    )

    create_url_title_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_URL_TITLE_CREATE
    )
    new_url_title = create_url_title_input.input_value()

    assert len(new_url_title) == CONSTANTS.URLS.MAX_URL_TITLE_LENGTH


def test_create_url_empty_fields(page: Page, create_test_utubs, provide_app: Flask):
    """
    Tests the site error response to a user's attempt to create a new URL with empty fields.

    GIVEN a user and selected UTub
    WHEN the createURL form is submitted empty
    THEN ensure the appropriate error and prompt is shown to user.
    """
    # Login test user and select first test UTub
    app = provide_app

    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(
        page=page, css_selector=HPL.WRAP_URL_CREATE
    )
    expect(url_creation_row).to_be_visible()

    # Submit URL
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SUBMIT_CREATE)

    invalid_url_title_error = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_URL_TITLE_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert invalid_url_title_error.inner_text() == FIELD_REQUIRED_STR

    invalid_url_string_error = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert invalid_url_string_error.inner_text() == FIELD_REQUIRED_STR


def test_create_url_empty_title(page: Page, create_test_utubs, provide_app: Flask):
    """
    Tests the site error response to a user's attempt to create a new URL with an empty URL title.

    GIVEN a user and selected UTub
    WHEN the createURL form is submitted with an empty URL title
    THEN ensure the appropriate error and prompt is shown to user.
    """
    # Login test user and select first test UTub
    app = provide_app

    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(
        page=page, css_selector=HPL.WRAP_URL_CREATE
    )
    expect(url_creation_row).to_be_visible()

    url_string_input_field = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_URL_STRING_CREATE
    )
    clear_then_send_keys(locator=url_string_input_field, input_text=MOCK_URL_STRINGS[0])

    # Submit URL
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SUBMIT_CREATE)

    invalid_url_title_error = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_URL_TITLE_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert invalid_url_title_error.inner_text() == FIELD_REQUIRED_STR


def test_create_url_empty_string(page: Page, create_test_utubs, provide_app: Flask):
    """
    Tests the site error response to a user's attempt to create a new URL with an empty URL string.

    GIVEN a user and selected UTub
    WHEN the createURL form is submitted with an empty URL string
    THEN ensure the appropriate error and prompt is shown to user.
    """
    # Login test user and select first test UTub
    app = provide_app

    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(
        page=page, css_selector=HPL.WRAP_URL_CREATE
    )
    expect(url_creation_row).to_be_visible()

    url_title_input_field = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_URL_TITLE_CREATE
    )
    clear_then_send_keys(locator=url_title_input_field, input_text="Testing")

    # Submit URL
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SUBMIT_CREATE)

    invalid_url_string_error = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert invalid_url_string_error.inner_text() == FIELD_REQUIRED_STR


@pytest.mark.parametrize(
    "invalid_url",
    [
        "javascript:alert(1)",
        "data:text/html,<script>",
        "https://asdfasdfasdf",
    ],
)
def test_invalid_url_input(
    page: Page, create_test_utubs, provide_app: Flask, invalid_url: str
):
    """
    Tests the site error response to a user's attempt to create an invalid URL

    GIVEN a user and selected UTub
    WHEN the createURL form is submitted with an invalid URL
    THEN ensure the appropriate error and prompt is shown to user.
    """
    # Login test user and select first test UTub
    app = provide_app

    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    create_url(page=page, url_title="Test", url_string=invalid_url)

    wait_until_visible_css_selector(
        page=page,
        css_selector=HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )

    invalid_url_string_error = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert (
        invalid_url_string_error.inner_text() == URL_FAILURE.UNABLE_TO_VALIDATE_THIS_URL
    )


def test_invalid_credentials_url_input(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to create an invalid URL

    GIVEN a user and selected UTub
    WHEN the createURL form is submitted with an invalid URL
    THEN ensure the appropriate error and prompt is shown to user.
    """
    # Login test user and select first test UTub
    app = provide_app

    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    invalid_url = "https://user:password@example.com"
    create_url(page=page, url_title="Test", url_string=invalid_url)

    wait_until_visible_css_selector(
        page=page,
        css_selector=HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )

    invalid_url_string_error = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert (
        invalid_url_string_error.inner_text()
        == URL_FAILURE.URLS_WITH_CREDENTIALS_EXCEPTION
    )


def test_create_url_sanitized_title(page: Page, create_test_utubs, provide_app: Flask):
    """
    Tests the site error response to a user's attempt to create a URL with a title that
    contains improper or unsanitized inputs

    GIVEN a user and selected UTub
    WHEN the createURL form is submitted with an invalid URL title that is sanitized
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    create_url(
        page=page,
        url_title='<img src="evl.jpg">',
        url_string=MOCK_URL_STRINGS[0],
    )
    wait_until_visible_css_selector(
        page=page,
        css_selector=HPL.INPUT_URL_TITLE_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )

    invalid_url_title_error = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_URL_TITLE_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert invalid_url_title_error.inner_text() == URL_FAILURE.INVALID_INPUT


def test_create_url_duplicate_url(page: Page, create_test_urls, provide_app: Flask):
    """
    Tests the site error response to a user's attempt to create a URL that is already in the UTub

    GIVEN a user and selected UTub
    WHEN the createURL form is submitted with a duplicate URL string
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    with app.app_context():
        utub_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_created.id
        ).first()
        url_string_already_added = utub_url.standalone_url.url_string

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    create_url(page=page, url_title="Testing", url_string=url_string_already_added)

    invalid_url_string_error = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert invalid_url_string_error.inner_text() == URL_FAILURE.URL_IN_UTUB


def test_create_url_invalid_csrf_token(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to attempt to create a new URL with an invalid CSRF token

    GIVEN a user attempting to create a new URL in a UTub
    WHEN the createURL form is sent with an invalid CSRF token
    THEN ensure U4I responds with a proper error message
    """
    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        user: Users = Users.query.get(user_id_for_test)
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    invalidate_csrf_token_on_page(page=page)
    create_url(page=page, url_title="Testing", url_string=MOCK_URL_STRINGS[0])

    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    # Page reloads after user clicks button in CSRF 403 error page
    wait_until_hidden(page=page, css_selector=HPL.INPUT_URL_STRING_CREATE)
    assert_login_with_username(page=page, username=user.username)


def test_create_url_when_utub_tag_applied(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    Tests a user's ability to create a new URL in a selected UTub when a tag is selected.
    If a tag is selected, a newly created URL shouldn't be shown since it has no tags applied!

    GIVEN a user and selected UTub
    WHEN they submit a new URL using the submit button
    THEN ensure the URL is added and input is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    with app.app_context():
        tag_in_utub: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_user_created.id
        ).first()
        tag_id_in_utub = tag_in_utub.id

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    apply_tag_filter_based_on_id(page=page, utub_tag_id=tag_id_in_utub)

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0] + "extraextra"

    fill_create_url_form(page=page, url_title=url_title, url_string=url_string)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SUBMIT_CREATE)

    # Wait for HTTP request to complete
    wait_until_hidden(page=page, css_selector=HPL.INPUT_URL_STRING_CREATE)
    url_creation_row = page.locator(HPL.WRAP_URL_CREATE).first
    expect(url_creation_row).to_be_hidden()

    # Extract URL title and string from new row in URL deck
    utub_url_id = get_newly_added_utub_url_id_by_url_string(
        app, utub_user_created.id, url_string
    )
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.ROWS_URLS + f'[utuburlid="{utub_url_id}"]'
    )


EXISTING_TAG_FOR_CREATE = "Alpha"
FRESH_TAG_FOR_CREATE = "Fresh"
FILTER_TAG = "filterme"
NON_MATCHING_TAG = "different"


def _badge_count_on_url_row(url_row) -> int:
    return url_row.locator(HPL.TAG_BADGES).count()


def test_create_url_with_staged_tags(page: Page, create_test_urls, provide_app: Flask):
    """
    Tests creating a URL with two staged tags (one existing in the UTub, one
    brand-new) via the inline create-form combobox.

    GIVEN a user with a selected UTub containing an existing tag
    WHEN they open the create-URL form, stage one existing-tag chip and one
        brand-new chip, and submit
    THEN the new URL card shows 2 tag badges, the fresh tag appears in the
        #listTags deck with count 1, and the existing tag's deck count is
        incremented.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id

    add_tag_to_utub_user_created(
        app, utub_id, user_id_for_test, EXISTING_TAG_FOR_CREATE
    )

    init_fresh_tag_count: int = count_urls_with_tag_applied_by_tag_string(
        app, utub_id, FRESH_TAG_FOR_CREATE
    )
    assert init_fresh_tag_count == 0

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_id
    )

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0] + "withtags"

    fill_create_url_form(page=page, url_title=url_title, url_string=url_string)
    # A brand-new tag is staged via the "Create tag" option; an existing UTub
    # tag has an exact match so it surfaces as a suggestion (no create-new
    # option) and must be staged via the suggestion flow.
    stage_new_tag_in_create_form(page=page, text=FRESH_TAG_FOR_CREATE)
    stage_tag_suggestion_in_create_form(page=page, tag_text=EXISTING_TAG_FOR_CREATE)

    staged_chips = page.locator(HPL.CREATE_FORM_TAG_STAGED_CHIP)
    expect(staged_chips).to_have_count(2)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SUBMIT_CREATE)
    wait_until_hidden(page=page, css_selector=HPL.INPUT_URL_STRING_CREATE)

    utub_url_id = get_newly_added_utub_url_id_by_url_string(app, utub_id, url_string)
    url_row = get_url_row_by_id(page=page, utub_url_id=utub_url_id)

    wait_until_visible_css_selector(
        page=page,
        css_selector=f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}'] {HPL.TAG_BADGES}",
    )
    assert _badge_count_on_url_row(url_row) == 2

    # The brand-new tag appears in the tag deck with count 1.
    fresh_tag = get_tag_in_utub_by_tag_string(app, utub_id, FRESH_TAG_FOR_CREATE)
    fresh_tag_selector = (
        f'{HPL.LIST_TAGS} {HPL.TAG_FILTERS}[data-utub-tag-id="{fresh_tag.id}"]'
    )
    wait_then_get_element(page=page, css_selector=fresh_tag_selector)

    _, fresh_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        page=page, tag_id=fresh_tag.id
    )
    assert fresh_total == init_fresh_tag_count + 1

    # The existing tag's deck counter reflects the new URL.
    existing_tag = get_tag_in_utub_by_tag_string(app, utub_id, EXISTING_TAG_FOR_CREATE)
    _, existing_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        page=page, tag_id=existing_tag.id
    )
    assert existing_total == 1


def test_create_url_with_zero_tags_regression(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Regression: creating a URL with no staged tags still succeeds and adds a
    tagless card.

    GIVEN a user and selected UTub
    WHEN they create a URL without staging any tags
    THEN the URL is added with zero tag badges and the form hides.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_id
    )

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0] + "notags"

    create_url(page=page, url_title=url_title, url_string=url_string)
    wait_until_hidden(page=page, css_selector=HPL.INPUT_URL_STRING_CREATE)

    utub_url_id = get_newly_added_utub_url_id_by_url_string(app, utub_id, url_string)
    url_row = get_url_row_by_id(page=page, utub_url_id=utub_url_id)
    assert _badge_count_on_url_row(url_row) == 0


def test_create_url_staging_respects_tag_cap(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Staging in the create form respects the per-URL tag cap.

    GIVEN a user opening the create-URL form
    WHEN they stage `MAX_URL_TAGS` chips and attempt to stage one more
    THEN the combobox input is disabled at the cap and the chip count does not
        exceed `MAX_URL_TAGS`.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_id
    )

    fill_create_url_form(
        page=page,
        url_title=MOCK_URL_TITLES[0],
        url_string=MOCK_URL_STRINGS[0] + "cap",
    )

    for tag_index in range(TAG_CONSTANTS.MAX_URL_TAGS):
        stage_new_tag_in_create_form(page=page, text=f"captag{tag_index}")

    staged_chips = page.locator(HPL.CREATE_FORM_TAG_STAGED_CHIP)
    expect(staged_chips).to_have_count(TAG_CONSTANTS.MAX_URL_TAGS)

    # At the cap, the combobox input is disabled so no further chip can be staged.
    combobox_input = page.locator(HPL.CREATE_FORM_TAG_COMBOBOX_INPUT).first
    expect(combobox_input).to_be_disabled()

    staged_chips_after = page.locator(HPL.CREATE_FORM_TAG_STAGED_CHIP)
    expect(staged_chips_after).to_have_count(TAG_CONSTANTS.MAX_URL_TAGS)


def test_create_url_with_matching_filter_tag_is_visible(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Regression guard for the `updateURLsAndTagSubheaderWhenTagSelected()` fix:
    a URL created with a tag matching the active filter stays visible.

    GIVEN a selected tag filter
    WHEN the user creates a URL and stages a tag matching the active filter
    THEN the new URL card is visible (filterable=true).
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id

    filter_tag = add_tag_to_single_url_in_utub(
        app, utub_id, user_id_for_test, FILTER_TAG
    )

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_id
    )

    apply_tag_filter_based_on_id(page=page, utub_tag_id=filter_tag.id)

    url_string = MOCK_URL_STRINGS[1] + "matchfilter"
    fill_create_url_form(page=page, url_title=MOCK_URL_TITLES[1], url_string=url_string)
    # `FILTER_TAG` already exists in the UTub (applied to an existing URL), so it
    # surfaces as a suggestion rather than a create-new option.
    stage_tag_suggestion_in_create_form(page=page, tag_text=FILTER_TAG)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SUBMIT_CREATE)
    wait_until_hidden(page=page, css_selector=HPL.INPUT_URL_STRING_CREATE)

    utub_url_id = get_newly_added_utub_url_id_by_url_string(app, utub_id, url_string)
    new_url_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    wait_until_visible_css_selector(page=page, css_selector=new_url_selector)
    new_url_row = page.locator(new_url_selector).first
    expect(new_url_row).to_be_visible()
    assert new_url_row.get_attribute("filterable") == "true"
    assert _badge_count_on_url_row(new_url_row) == 1


def test_create_url_with_non_matching_filter_tag_is_hidden(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Regression guard for the `updateURLsAndTagSubheaderWhenTagSelected()` fix:
    a URL created with a tag NOT matching the active filter is hidden.

    GIVEN a selected tag filter
    WHEN the user creates a URL and stages a tag that does not match the filter
    THEN the new URL card is hidden (filterable=false).
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id

    filter_tag = add_tag_to_single_url_in_utub(
        app, utub_id, user_id_for_test, FILTER_TAG
    )

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_id
    )

    apply_tag_filter_based_on_id(page=page, utub_tag_id=filter_tag.id)

    url_string = MOCK_URL_STRINGS[1] + "nomatch"
    fill_create_url_form(page=page, url_title=MOCK_URL_TITLES[1], url_string=url_string)
    stage_new_tag_in_create_form(page=page, text=NON_MATCHING_TAG)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SUBMIT_CREATE)
    wait_until_hidden(page=page, css_selector=HPL.INPUT_URL_STRING_CREATE)

    utub_url_id = get_newly_added_utub_url_id_by_url_string(app, utub_id, url_string)
    new_url_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    # The card is created but hidden by the active filter; use a presence wait
    # (not a visibility wait) since the row is in the DOM but not displayed.
    wait_for_element_presence(page=page, css_selector=new_url_selector)
    new_url_row = page.locator(new_url_selector).first
    assert new_url_row.get_attribute("filterable") == "false"
    assert_not_visible_css_selector(page=page, css_selector=new_url_selector)


def test_create_url_strips_tracking_params(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests that creating a URL with tracking query params renders the stripped,
    canonical URL in the URL deck.

    GIVEN a user and selected UTub
    WHEN they create a URL containing tracking params (utm_source, gclid)
    THEN the rendered card's link text and href show the stripped URL
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    url_title = MOCK_URL_TITLES[0]

    fill_create_url_form(
        page=page, url_title=url_title, url_string=MOCK_URL_WITH_TRACKING_PARAMS
    )
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SUBMIT_CREATE)

    wait_until_hidden(page=page, css_selector=HPL.INPUT_URL_STRING_CREATE)
    url_creation_row = page.locator(HPL.WRAP_URL_CREATE).first
    expect(url_creation_row).to_be_hidden()

    # The DB stores the stripped canonical form; look the row up by that value.
    utub_url_id = get_newly_added_utub_url_id_by_url_string(
        app, utub_user_created.id, MOCK_URL_TRACKING_STRIPPED
    )
    url_row = get_url_row_by_id(page=page, utub_url_id=utub_url_id)

    url_row_string_elem = url_row.locator(HPL.URL_STRING_READ)
    url_row_string = url_row_string_elem.inner_text()
    url_row_href = url_row_string_elem.get_attribute(HPL.URL_STRING_IN_DATA)

    expected_visible = MOCK_URL_TRACKING_STRIPPED
    expected_visible = expected_visible.removeprefix("https://")
    expected_visible = expected_visible.removeprefix("http://")
    expected_visible = expected_visible.removeprefix("www.")

    assert url_row_string == expected_visible
    assert url_row_href == MOCK_URL_TRACKING_STRIPPED


def test_create_url_preserves_non_tracking_params(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests that creating a URL with legitimate (non-tracking) query params keeps
    those params intact in the rendered card.

    GIVEN a user and selected UTub
    WHEN they create a URL containing ?q=search&sort=date
    THEN the rendered card's link text and href preserve the query string
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    url_with_legit_params = UTS.URL_WITH_NON_TRACKING_PARAMS
    url_title = MOCK_URL_TITLES[0]

    fill_create_url_form(
        page=page, url_title=url_title, url_string=url_with_legit_params
    )
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SUBMIT_CREATE)

    wait_until_hidden(page=page, css_selector=HPL.INPUT_URL_STRING_CREATE)

    utub_url_id = get_newly_added_utub_url_id_by_url_string(
        app, utub_user_created.id, url_with_legit_params
    )
    url_row = get_url_row_by_id(page=page, utub_url_id=utub_url_id)

    url_row_string_elem = url_row.locator(HPL.URL_STRING_READ)
    url_row_string = url_row_string_elem.inner_text()
    url_row_href = url_row_string_elem.get_attribute(HPL.URL_STRING_IN_DATA)

    expected_visible = url_with_legit_params
    expected_visible = expected_visible.removeprefix("https://")
    expected_visible = expected_visible.removeprefix("http://")
    expected_visible = expected_visible.removeprefix("www.")

    assert url_row_string == expected_visible
    assert url_row_href == url_with_legit_params


def test_create_url_tracking_params_collision_shows_error(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests that creating a tracking-laden URL whose stripped canonical form is
    already in the UTub surfaces the informative collision error.

    GIVEN a UTub that already contains the stripped canonical URL
    WHEN the user submits the same URL with tracking params appended
    THEN the create-form error shows the tracking-params-stripped collision message
    """
    _, cli_runner = runner
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    add_mock_urls(cli_runner, [MOCK_URL_TRACKING_STRIPPED])

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    create_url(page=page, url_title="Testing", url_string=MOCK_URL_WITH_TRACKING_PARAMS)

    invalid_url_string_error = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert (
        invalid_url_string_error.inner_text()
        == UTS.URL_IN_UTUB_TRACKING_PARAMS_STRIPPED
    )
