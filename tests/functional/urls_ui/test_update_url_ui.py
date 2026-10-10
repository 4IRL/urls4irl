import random
import re
from typing import Tuple
from urllib.parse import urlsplit

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner
from playwright.sync_api import Locator, Page, expect

from backend import db
from backend.cli.mock_constants import (
    MOCK_URL_STRINGS,
    MOCK_URL_TRACKING_STRIPPED,
    MOCK_URL_WITH_TRACKING_PARAMS,
)
from backend.models.users import Users
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.constants import STRINGS, TAG_CONSTANTS, URL_CONSTANTS
from backend.utils.strings.json_strs import FIELD_REQUIRED_STR
from backend.utils.strings.tag_strs import TAGS_FAILURE
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from backend.utils.strings.url_strs import (
    URL_FAILURE,
    URL_REVIVED_FROM_TRASH,
    URL_TRIM_CONFLICT,
    URL_TRIM_HEADER_DROPPED,
    URL_TRIM_SAVED_BANNER_ONE,
    URL_UPDATED_BANNER,
)
from tests.functional.db_utils import (
    add_mock_urls,
    add_tags_to_utub_url,
    get_url_in_utub,
    get_utub_this_user_created,
    trash_utub_url,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_login_with_username,
    assert_on_429_page,
    assert_tooltip_animates,
    assert_update_url_state_is_hidden,
    assert_update_url_state_is_shown,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_login_utils import (
    login_user_select_utub_by_id_and_url_by_id,
    login_user_select_utub_by_name_and_url_by_string,
    login_user_select_utub_by_name_and_url_by_title,
)
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    clear_then_send_keys,
    get_selected_url,
    get_url_row_by_id,
    invalidate_csrf_token_on_page,
    open_update_url_title,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)
from tests.functional.urls_ui.playwright_assert_utils import (
    assert_select_url_as_utub_owner_or_url_creator,
)
from tests.functional.urls_ui.playwright_utils import (
    CLOSED_CLASS,
    TRIM_BASE_URL,
    TRIM_DROPPED_PARAM,
    TRIM_URL_KEEP_ONLY,
    TRIM_URL_TWO_PARAMS,
    set_trim_section_expanded,
    update_url_string,
    update_url_title,
)

pytestmark = pytest.mark.update_urls_ui


def _login_and_select_first_url(*, app: Flask, page: Page, user_id: int) -> None:
    """Log in and select the first URL of a UTub this user created — the shared
    setup for the URL-card update-form tooltip tests below."""
    utub_user_created = get_utub_this_user_created(app, user_id)
    utub_url = get_url_in_utub(app, utub_id=utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id,
        utub_id=utub_user_created.id,
        utub_url_id=utub_url.id,
    )


def _open_update_url_string_form(*, page: Page) -> None:
    """Drive the real reveal path for the URL-string update form."""
    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}",
    )
    wait_until_visible_css_selector(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE}",
    )


def test_update_url_string_tooltip_animates(
    page: Page,
    create_test_urls,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a tooltip showing when user hovers over the edit URL button .

    GIVEN a user has access to a URL
    WHEN the user hover over the edit URL button
    THEN ensure a tooltip is shown appropriately
    """

    _, cli_runner = runner
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_url = get_url_in_utub(app, utub_id=utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=utub_url.id,
    )

    assert_tooltip_animates(
        page=page,
        parent_css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}",
        tooltip_parent_class=HPL.BUTTON_URL_STRING_UPDATE,
        tooltip_text=STRINGS.EDIT_URL_TOOLTIP,
    )


@pytest.mark.parametrize(
    "validated_url,input_url",
    [
        ("https://example.com/", "https://example.com"),
        ("https://example.com/", "example.com"),
        ("https://example.com/", " https://example.com "),
    ],
)
def test_update_url_with_valid_url(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
    validated_url: str,
    input_url: str,
):
    """
    Tests a user's ability to update the URL string of the selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL and user presses submit
    THEN ensure the URL is updated accordingly
    """
    VALIDATED_URL = validated_url

    _, cli_runner = runner
    app = provide_app
    random_url_to_add = random.sample(MOCK_URL_STRINGS, 1)[0]
    add_mock_urls(
        cli_runner,
        [
            random_url_to_add,
        ],
    )

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_string(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=random_url_to_add,
    )
    assert_select_url_as_utub_owner_or_url_creator(
        page=page, url_selector=HPL.ROW_SELECTED_URL
    )

    url_row = get_selected_url(page=page)

    if input_url.startswith(("\t", "\n")):
        # This is needed to insert escaped characters via Selenium into input fields
        input_url = input_url.encode("unicode_escape").decode("utf-8")

    update_url_string(page=page, url_string=input_url)
    assert_update_url_state_is_shown(page=page, url_row=url_row)

    submit_css_selector = (
        f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}"
    )
    wait_then_click_element(page=page, css_selector=submit_css_selector)

    wait_until_hidden(page=page, css_selector=HPL.UPDATE_URL_STRING_WRAP)
    assert_update_url_state_is_hidden(url_row=url_row)

    url_row_string_elem = url_row.locator(HPL.URL_STRING_READ)

    # Extract URL string from updated URL row
    url_row_string_display = url_row_string_elem.inner_text()
    url_row_data_attrib = url_row_string_elem.get_attribute("href")

    assert url_row_data_attrib == url_row_string_display
    assert url_row_data_attrib == VALIDATED_URL

    expect(page.locator(HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)).to_have_count(0)

    expect(page.locator(HPL.UPDATE_URL_STRING_WRAP)).to_be_hidden()


def test_update_url_string_submit_btn(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to update the URL string of the selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL and user presses submit
    THEN ensure the URL is updated accordingly
    """

    _, cli_runner = runner
    app = provide_app
    random_url_to_add, random_url_to_change_to = random.sample(MOCK_URL_STRINGS, 2)
    add_mock_urls(
        cli_runner,
        [
            random_url_to_add,
        ],
    )

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_string(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=random_url_to_add,
    )

    url_row = get_selected_url(page=page)

    update_url_string(page=page, url_string=random_url_to_change_to)
    assert_update_url_state_is_shown(page=page, url_row=url_row)

    submit_css_selector = (
        f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}"
    )
    wait_then_click_element(page=page, css_selector=submit_css_selector)

    wait_until_hidden(page=page, css_selector=HPL.UPDATE_URL_STRING_WRAP)
    assert_update_url_state_is_hidden(url_row=url_row)

    url_row_string_elem = url_row.locator(HPL.URL_STRING_READ)

    # Extract URL string from updated URL row
    url_row_string_display = url_row_string_elem.inner_text()
    url_row_data_attrib = url_row_string_elem.get_attribute("href")

    assert url_row_data_attrib == url_row_string_display

    host_changed_to = urlsplit(random_url_to_change_to).hostname
    actual_host = urlsplit(url_row_data_attrib).hostname
    assert isinstance(host_changed_to, str)
    assert isinstance(actual_host, str)

    assert host_changed_to in actual_host or actual_host in host_changed_to

    expect(page.locator(HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)).to_have_count(0)

    expect(page.locator(HPL.UPDATE_URL_STRING_WRAP)).to_be_hidden()


def test_update_url_string_press_enter_key(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to update the URL string of the selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL and user presses enter key
    THEN ensure the URL is updated accordingly
    """

    _, cli_runner = runner
    app = provide_app
    random_url_to_add, random_url_to_change_to = random.sample(MOCK_URL_STRINGS, 2)
    add_mock_urls(
        cli_runner,
        [
            random_url_to_add,
        ],
    )

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_string(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=random_url_to_add,
    )

    url_row = get_selected_url(page=page)

    update_url_string(page=page, url_string=random_url_to_change_to)
    assert_update_url_state_is_shown(page=page, url_row=url_row)
    page.keyboard.press("Enter")

    wait_until_hidden(page=page, css_selector=HPL.UPDATE_URL_STRING_WRAP)
    assert_update_url_state_is_hidden(url_row=url_row)

    url_row_string_elem = url_row.locator(HPL.URL_STRING_READ)

    # Extract URL string from updated URL row
    url_row_string_display = url_row_string_elem.inner_text()
    url_row_data_attrib = url_row_string_elem.get_attribute("href")

    assert url_row_data_attrib == url_row_string_display

    host_changed_to = urlsplit(random_url_to_change_to).hostname
    actual_host = urlsplit(url_row_data_attrib).hostname
    assert isinstance(host_changed_to, str)
    assert isinstance(actual_host, str)

    assert host_changed_to in actual_host or actual_host in host_changed_to

    expect(page.locator(HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)).to_have_count(0)

    expect(page.locator(HPL.UPDATE_URL_STRING_WRAP)).to_be_hidden()


def test_update_url_string_rate_limits(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to update the URL string of the selected URL, but they are rate limited.

    GIVEN a user has access to a URL and is rate limited
    WHEN the updateURL form is populated with a new URL and user presses submit
    THEN ensure the 429 error page is shown
    """

    _, cli_runner = runner
    app = provide_app
    random_url_to_add, random_url_to_change_to = random.sample(MOCK_URL_STRINGS, 2)
    add_mock_urls(
        cli_runner,
        [
            random_url_to_add,
        ],
    )

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_string(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=random_url_to_add,
    )

    url_row = get_selected_url(page=page)

    update_url_string(page=page, url_string=random_url_to_change_to)
    assert_update_url_state_is_shown(page=page, url_row=url_row)

    add_forced_rate_limit_header(page=page)

    submit_css_selector = (
        f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}"
    )
    wait_then_click_element(page=page, css_selector=submit_css_selector)

    assert_on_429_page(page=page)


def test_update_url_string_big_cancel_btn(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to close the update URL input box by pressing cancel btn

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL but user presses cancel btn
    THEN ensure the URL is not updated and input is hidden
    """

    _, cli_runner = runner
    app = provide_app
    random_url_to_add = random.sample(MOCK_URL_STRINGS, 1)[0]
    add_mock_urls(
        cli_runner,
        [
            random_url_to_add,
        ],
    )

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_string(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=random_url_to_add,
    )

    url_row = get_selected_url(page=page)
    url_row_string_elem = url_row.locator(HPL.URL_STRING_READ)

    init_url_row_data = url_row_string_elem.get_attribute("href")
    init_url_row_string_display = url_row_string_elem.inner_text()

    update_btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}"
    wait_then_click_element(page=page, css_selector=update_btn_selector)
    assert_update_url_state_is_shown(page=page, url_row=url_row)

    cancel_update_btn = wait_then_get_element(
        page=page, css_selector=HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE
    )
    cancel_update_btn.click()
    wait_until_hidden(page=page, css_selector=HPL.UPDATE_URL_STRING_WRAP)
    assert_update_url_state_is_hidden(url_row=url_row)

    url_row_string_elem = url_row.locator(HPL.URL_STRING_READ)

    # Extract URL string from updated URL row
    url_row_string_display = url_row_string_elem.inner_text()
    url_row_data_attrib = url_row_string_elem.get_attribute("href")

    assert url_row_data_attrib == init_url_row_data
    assert url_row_string_display == init_url_row_string_display

    expect(page.locator(HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)).to_have_count(0)

    expect(page.locator(HPL.UPDATE_URL_STRING_WRAP)).to_be_hidden()


def test_update_url_string_cancel_btn(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to close the update URL input box by pressing cancel btn

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL but user presses cancel btn
    THEN ensure the URL is not updated and input is hidden
    """

    _, cli_runner = runner
    app = provide_app
    random_url_to_add = random.sample(MOCK_URL_STRINGS, 1)[0]
    add_mock_urls(
        cli_runner,
        [
            random_url_to_add,
        ],
    )

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_string(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=random_url_to_add,
    )

    url_row = get_selected_url(page=page)
    url_row_string_elem = url_row.locator(HPL.URL_STRING_READ)

    init_url_row_data = url_row_string_elem.get_attribute("href")
    init_url_row_string_display = url_row_string_elem.inner_text()

    url_update_btn_css_selector = (
        f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}"
    )
    wait_until_visible_css_selector(page=page, css_selector=url_update_btn_css_selector)
    wait_then_click_element(page=page, css_selector=url_update_btn_css_selector)
    assert_update_url_state_is_shown(page=page, url_row=url_row)

    cancel_update_btn = wait_then_get_element(
        page=page, css_selector=HPL.BUTTON_URL_STRING_CANCEL_UPDATE
    )
    cancel_update_btn.click()
    wait_until_hidden(page=page, css_selector=HPL.UPDATE_URL_STRING_WRAP)
    assert_update_url_state_is_hidden(url_row=url_row)

    url_row_string_elem = url_row.locator(HPL.URL_STRING_READ)

    # Extract URL string from updated URL row
    url_row_string_display = url_row_string_elem.inner_text()
    url_row_data_attrib = url_row_string_elem.get_attribute("href")

    assert url_row_data_attrib == init_url_row_data
    assert url_row_string_display == init_url_row_string_display

    expect(page.locator(HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)).to_have_count(0)

    expect(page.locator(HPL.UPDATE_URL_STRING_WRAP)).to_be_hidden()


def test_update_url_string_escape_key(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to close the update URL input box by pressing escape key

    GIVEN a user has access to a URL
    WHEN the updateURL form is populated with a new URL but user presses cancel btn
    THEN ensure the URL is not updated and input is hidden
    """

    _, cli_runner = runner
    app = provide_app
    random_url_to_add = random.sample(MOCK_URL_STRINGS, 1)[0]
    add_mock_urls(
        cli_runner,
        [
            random_url_to_add,
        ],
    )

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_string(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=random_url_to_add,
    )

    url_row = get_selected_url(page=page)
    url_row_string_elem = url_row.locator(HPL.URL_STRING_READ)

    init_url_row_data = url_row_string_elem.get_attribute("href")
    init_url_row_string_display = url_row_string_elem.inner_text()

    url_update_btn_css_selector = (
        f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}"
    )
    wait_until_visible_css_selector(page=page, css_selector=url_update_btn_css_selector)
    wait_then_click_element(page=page, css_selector=url_update_btn_css_selector)
    assert_update_url_state_is_shown(page=page, url_row=url_row)

    wait_until_in_focus(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE}"
    )
    page.keyboard.press("Escape")
    wait_until_hidden(page=page, css_selector=HPL.UPDATE_URL_STRING_WRAP)
    assert_update_url_state_is_hidden(url_row=url_row)

    url_row_string_elem = url_row.locator(HPL.URL_STRING_READ)

    # Extract URL string from updated URL row
    url_row_string_display = url_row_string_elem.inner_text()
    url_row_data_attrib = url_row_string_elem.get_attribute("href")

    assert url_row_data_attrib == init_url_row_data
    assert url_row_string_display == init_url_row_string_display

    expect(page.locator(HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)).to_have_count(0)

    expect(page.locator(HPL.UPDATE_URL_STRING_WRAP)).to_be_hidden()


def test_update_url_title_submit_btn(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to update the URL title of a selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURLTitle form is populated with a new URL Title
    THEN ensure the URL Title is updated accordingly
    """

    _, cli_runner = runner
    app = provide_app
    add_mock_urls(cli_runner, list([UTS.TEST_URL_STRING_CREATE]))

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_title=UTS.TEST_URL_TITLE_1,
    )

    url_row = get_selected_url(page=page)
    url_title = UTS.TEST_URL_TITLE_UPDATE
    update_url_title(page=page, selected_url_row=url_row, url_title=url_title)
    expect(url_row.locator(HPL.URL_TITLE_READ)).to_be_hidden()

    # Submit
    submit_css_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE}"
    wait_then_click_element(page=page, css_selector=submit_css_selector)

    # Wait for POST request
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE)
    expect(url_row.locator(HPL.URL_TITLE_READ)).to_be_visible()

    # Extract URL string from updated URL row
    url_row_title = url_row.locator(HPL.URL_TITLE_READ).inner_text()

    assert url_title == url_row_title


def test_update_url_title_submit_enter_key(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to update the URL title of a selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURLTitle form is submitted with enter key and populated with a new URL Title
    THEN ensure the URL Title is updated accordingly
    """

    _, cli_runner = runner
    app = provide_app
    add_mock_urls(cli_runner, list([UTS.TEST_URL_STRING_CREATE]))

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_title=UTS.TEST_URL_TITLE_1,
    )

    url_row = get_selected_url(page=page)
    url_title = UTS.TEST_URL_TITLE_UPDATE
    update_url_title(page=page, selected_url_row=url_row, url_title=url_title)
    expect(url_row.locator(HPL.URL_TITLE_READ)).to_be_hidden()

    # Submit
    page.keyboard.press("Enter")

    # Wait for update to hide
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE)
    expect(url_row.locator(HPL.URL_TITLE_READ)).to_be_visible()

    # Extract URL string from updated URL row
    url_row_title = url_row.locator(HPL.URL_TITLE_READ).inner_text()

    assert url_title == url_row_title


def test_update_url_title_cancel_click_btn(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to update the URL title of a selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURLTitle form is populated with a new URL Title, but the user cancels by pressing the X btn
    THEN ensure the URL Title is not updated, and the form is hidden
    """

    _, cli_runner = runner
    app = provide_app
    add_mock_urls(cli_runner, list([UTS.TEST_URL_STRING_CREATE]))

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_title=UTS.TEST_URL_TITLE_1,
    )

    url_row = get_selected_url(page=page)

    # Extract URL string from updated URL row
    init_url_row_title = url_row.locator(HPL.URL_TITLE_READ).inner_text()

    url_title = UTS.TEST_URL_TITLE_UPDATE
    update_url_title(page=page, selected_url_row=url_row, url_title=url_title)
    expect(url_row.locator(HPL.URL_TITLE_READ)).to_be_hidden()

    cancel_css_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_TITLE_CANCEL_UPDATE}"
    wait_then_click_element(page=page, css_selector=cancel_css_selector)

    wait_until_hidden(page=page, css_selector=HPL.BUTTON_URL_TITLE_CANCEL_UPDATE)
    expect(url_row.locator(HPL.URL_TITLE_READ)).to_be_visible()

    # Extract URL string from updated URL row
    url_row_title = url_row.locator(HPL.URL_TITLE_READ).inner_text()

    assert init_url_row_title == url_row_title


def test_update_url_title_cancel_press_escape(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a user's ability to update the URL title of a selected URL.

    GIVEN a user has access to a URL
    WHEN the updateURLTitle form is populated with a new URL Title, but the user cancels by pressing the escape key
    THEN ensure the URL Title is not updated, and the form is hidden
    """

    _, cli_runner = runner
    app = provide_app
    add_mock_urls(cli_runner, list([UTS.TEST_URL_STRING_CREATE]))

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_title=UTS.TEST_URL_TITLE_1,
    )

    url_row = get_selected_url(page=page)

    # Extract URL string from updated URL row
    init_url_row_title = url_row.locator(HPL.URL_TITLE_READ).inner_text()

    url_title = UTS.TEST_URL_TITLE_UPDATE
    update_url_title(page=page, selected_url_row=url_row, url_title=url_title)
    expect(url_row.locator(HPL.URL_TITLE_READ)).to_be_hidden()

    page.keyboard.press("Escape")

    wait_until_hidden(page=page, css_selector=HPL.BUTTON_URL_TITLE_CANCEL_UPDATE)
    expect(url_row.locator(HPL.URL_TITLE_READ)).to_be_visible()

    # Extract URL string from updated URL row
    url_row_title = url_row.locator(HPL.URL_TITLE_READ).inner_text()

    assert init_url_row_title == url_row_title


def test_update_url_title_length_exceeded(
    page: Page,
    create_test_urls,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests the site error response to a user's attempt to update a URL with a title that exceeds the maximum character length limit.

    GIVEN a user and selected UTub
    WHEN the updateURL title form is populated and submitted with a title that exceeds character limits
    THEN ensure the appropriate error and prompt is shown to user.
    """

    _, cli_runner = runner
    app = provide_app
    add_mock_urls(cli_runner, list([UTS.TEST_URL_STRING_CREATE]))

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_title=UTS.TEST_URL_TITLE_1,
    )

    url_row = get_selected_url(page=page)

    update_url_title(
        page=page,
        selected_url_row=url_row,
        url_title="a" * (URL_CONSTANTS.MAX_URL_TITLE_LENGTH + 1),
    )

    update_url_title_input = wait_then_get_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_TITLE_UPDATE}",
    )

    new_url_title = update_url_title_input.input_value()
    assert len(new_url_title) == URL_CONSTANTS.MAX_URL_TITLE_LENGTH


def test_update_url_string_empty_field(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a user and selected UTub
    WHEN the updateURL string form is submitted empty
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_title=UTS.TEST_URL_TITLE_1,
    )

    get_selected_url(page=page)
    update_url_string(page=page, url_string="")

    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}",
    )

    invalid_url_string_error = wait_then_get_element(
        page=page,
        css_selector=(
            f"{HPL.ROW_SELECTED_URL} "
            f"{HPL.INPUT_URL_STRING_UPDATE + HPL.INVALID_FIELD_SUFFIX}"
        ),
    )
    assert invalid_url_string_error.inner_text() == FIELD_REQUIRED_STR


def test_update_url_title_empty_field(page: Page, create_test_urls, provide_app: Flask):
    """
    GIVEN a user and selected UTub
    WHEN the updateURL title form is submitted empty
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_title(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_title=UTS.TEST_URL_TITLE_1,
    )

    url_row = get_selected_url(page=page)
    update_url_title(page=page, selected_url_row=url_row, url_title="")

    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE}",
    )

    invalid_url_title_error = wait_then_get_element(
        page=page,
        css_selector=(
            f"{HPL.ROW_SELECTED_URL} "
            f"{HPL.INPUT_URL_TITLE_UPDATE + HPL.INVALID_FIELD_SUFFIX}"
        ),
    )
    assert invalid_url_title_error.inner_text() == FIELD_REQUIRED_STR


def test_update_url_string_duplicate_url(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a user and selected UTub
    WHEN the updateURL string form is submitted with a URL that is already in the UTub
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.utub_creator == user_id_for_test).first()
        utub_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub.id
        ).first()
        url_to_update_to: str = utub_url.standalone_url.url_string
        another_utub_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.url_title != utub_url.url_title
        ).first()

    login_user_select_utub_by_name_and_url_by_title(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub.name,
        url_title=another_utub_url.url_title,
    )

    get_selected_url(page=page)
    update_url_string(page=page, url_string=url_to_update_to)

    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}",
    )

    error_css_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE + HPL.INVALID_FIELD_SUFFIX}"
    wait_until_visible_css_selector(page=page, css_selector=error_css_selector)

    invalid_url_string_error = wait_then_get_element(
        page=page, css_selector=error_css_selector
    )
    assert invalid_url_string_error.inner_text() == URL_FAILURE.URL_IN_UTUB


@pytest.mark.parametrize(
    "invalid_url",
    [
        "javascript:alert(1)",
        "data:text/html,<script>",
        "https://asdfasdfasdf",
    ],
)
def test_update_url_string_invalid_urls(
    page: Page, create_test_urls, provide_app: Flask, invalid_url: str
):
    """
    GIVEN a user and selected UTub
    WHEN the updateURL string form is submitted with an invalid URL
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1

    login_user_select_utub_by_name_and_url_by_title(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_title=UTS.TEST_URL_TITLE_1,
    )

    get_selected_url(page=page)
    update_url_string(page=page, url_string=invalid_url)

    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}",
    )

    error_css_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE + HPL.INVALID_FIELD_SUFFIX}"
    wait_until_visible_css_selector(page=page, css_selector=error_css_selector)

    invalid_url_string_error = wait_then_get_element(
        page=page, css_selector=error_css_selector
    )
    assert (
        invalid_url_string_error.inner_text() == URL_FAILURE.UNABLE_TO_VALIDATE_THIS_URL
    )


def test_update_url_string_credentials_url(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a user and selected UTub
    WHEN the updateURL string form is submitted with an invalid URL
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1

    login_user_select_utub_by_name_and_url_by_title(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_title=UTS.TEST_URL_TITLE_1,
    )

    invalid_url = "https://user:password@example.com"
    get_selected_url(page=page)
    update_url_string(page=page, url_string=invalid_url)

    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}",
    )

    error_css_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE + HPL.INVALID_FIELD_SUFFIX}"
    wait_until_visible_css_selector(page=page, css_selector=error_css_selector)

    invalid_url_string_error = wait_then_get_element(
        page=page, css_selector=error_css_selector
    )
    assert (
        invalid_url_string_error.inner_text()
        == URL_FAILURE.URLS_WITH_CREDENTIALS_EXCEPTION
    )


def test_update_url_sanitized_title(page: Page, create_test_urls, provide_app: Flask):
    """
    Tests the site error response to a user's attempt to update a URL with a title that
    contains improper or unsanitized inputs

    GIVEN a user and selected UTub
    WHEN the updateURL title form is submitted with an invalid URL title that is sanitized
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1

    login_user_select_utub_by_name_and_url_by_title(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_title=UTS.TEST_URL_TITLE_1,
    )

    url_row = get_selected_url(page=page)

    update_url_title(
        page=page, selected_url_row=url_row, url_title='<img src="evl.jpg">'
    )
    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE}",
    )

    error_css_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_TITLE_UPDATE + HPL.INVALID_FIELD_SUFFIX}"
    wait_until_visible_css_selector(page=page, css_selector=error_css_selector)

    invalid_url_title_error = wait_then_get_element(
        page=page, css_selector=error_css_selector
    )
    assert invalid_url_title_error.inner_text() == URL_FAILURE.INVALID_INPUT


def test_update_url_title_invalid_csrf_token(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to update a URL with a title
    with an invalid CSRF token

    GIVEN a user and selected UTub
    WHEN the updateURL title form is submitted with an invalid CSRF token
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        user: Users = Users.query.get(user_id_for_test)

    login_user_select_utub_by_name_and_url_by_title(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_title=UTS.TEST_URL_TITLE_1,
    )

    url_row = get_selected_url(page=page)

    update_url_title(page=page, selected_url_row=url_row, url_title="Testing")
    invalidate_csrf_token_on_page(page=page)
    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE}",
    )

    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    # Page reloads after user clicks button in CSRF 403 error page
    expect(page.locator(HPL.ROW_SELECTED_URL)).to_have_count(0)

    assert_login_with_username(page=page, username=user.username)


def test_update_url_strips_tracking_params(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests that updating a URL to a tracking-laden URL renders the stripped,
    canonical URL in the URL row.

    GIVEN a user with access to an existing URL
    WHEN they update the URL to one containing tracking params (utm_source, gclid)
    THEN the rendered row's link text and href show the stripped URL
    """
    _, cli_runner = runner
    app = provide_app
    random_url_to_add = random.sample(MOCK_URL_STRINGS, 1)[0]
    add_mock_urls(cli_runner, [random_url_to_add])

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_string(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=random_url_to_add,
    )

    url_row = get_selected_url(page=page)
    update_url_string(page=page, url_string=MOCK_URL_WITH_TRACKING_PARAMS)
    assert_update_url_state_is_shown(page=page, url_row=url_row)

    submit_css_selector = (
        f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}"
    )
    wait_then_click_element(page=page, css_selector=submit_css_selector)

    wait_until_hidden(page=page, css_selector=HPL.UPDATE_URL_STRING_WRAP)
    assert_update_url_state_is_hidden(url_row=url_row)

    url_row_string_elem = url_row.locator(HPL.URL_STRING_READ)
    url_row_string_display = url_row_string_elem.inner_text()
    url_row_data_attrib = url_row_string_elem.get_attribute("href")

    # The update path sets `.text(updatedURLString)` directly (no prefix
    # stripping), so text and href both equal the full stripped URL.
    assert url_row_data_attrib == MOCK_URL_TRACKING_STRIPPED
    assert url_row_string_display == MOCK_URL_TRACKING_STRIPPED


def test_update_url_tracking_params_collision_shows_error(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests that updating a URL to a tracking-laden variant whose stripped canonical
    form already exists in the UTub surfaces the informative collision error.

    GIVEN a UTub that already contains the stripped canonical URL plus a
        separate URL the user is editing
    WHEN the user updates the separate URL to a tracking-laden variant that
        strips to the already-present canonical URL
    THEN the update-form error shows the tracking-params-stripped collision message
    """
    _, cli_runner = runner
    app = provide_app
    url_to_edit = MOCK_URL_STRINGS[0]
    add_mock_urls(cli_runner, [MOCK_URL_TRACKING_STRIPPED, url_to_edit])

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_string(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=url_to_edit,
    )

    get_selected_url(page=page)
    update_url_string(page=page, url_string=MOCK_URL_WITH_TRACKING_PARAMS)

    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}",
    )

    error_css_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE + HPL.INVALID_FIELD_SUFFIX}"
    wait_until_visible_css_selector(page=page, css_selector=error_css_selector)

    invalid_url_string_error = wait_then_get_element(
        page=page, css_selector=error_css_selector
    )
    assert (
        invalid_url_string_error.inner_text()
        == UTS.URL_IN_UTUB_TRACKING_PARAMS_STRIPPED
    )


def test_update_url_preserves_non_tracking_params(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests that updating a URL to one with legitimate (non-tracking) query params
    keeps those params intact in the rendered row.

    GIVEN a user with access to an existing URL
    WHEN they update the URL to one containing ?q=search&sort=date
    THEN the rendered row's link text and href preserve the query string
    """
    _, cli_runner = runner
    app = provide_app
    random_url_to_add = random.sample(MOCK_URL_STRINGS, 1)[0]
    add_mock_urls(cli_runner, [random_url_to_add])

    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_string(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=random_url_to_add,
    )

    url_with_legit_params = UTS.URL_WITH_NON_TRACKING_PARAMS
    url_row = get_selected_url(page=page)
    update_url_string(page=page, url_string=url_with_legit_params)
    assert_update_url_state_is_shown(page=page, url_row=url_row)

    submit_css_selector = (
        f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}"
    )
    wait_then_click_element(page=page, css_selector=submit_css_selector)

    wait_until_hidden(page=page, css_selector=HPL.UPDATE_URL_STRING_WRAP)
    assert_update_url_state_is_hidden(url_row=url_row)

    url_row_string_elem = url_row.locator(HPL.URL_STRING_READ)
    url_row_string_display = url_row_string_elem.inner_text()
    url_row_data_attrib = url_row_string_elem.get_attribute("href")

    assert url_row_data_attrib == url_with_legit_params
    assert url_row_string_display == url_with_legit_params


def test_update_url_string_invalid_csrf_token(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to update a URL with a url string
    with an invalid CSRF token

    GIVEN a user and selected UTub
    WHEN the updateURL string form is submitted with an invalid CSRF token
    THEN ensure the appropriate error and prompt is shown to user.
    """
    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        user: Users = Users.query.get(user_id_for_test)

    login_user_select_utub_by_name_and_url_by_title(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_title=UTS.TEST_URL_TITLE_1,
    )

    get_selected_url(page=page)

    update_url_string(page=page, url_string="Testing")
    invalidate_csrf_token_on_page(page=page)
    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}",
    )

    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    # Page reloads after user clicks button in CSRF 403 error page
    expect(page.locator(HPL.ROW_SELECTED_URL)).to_have_count(0)

    assert_login_with_username(page=page, username=user.username)


def test_update_url_title_submit_btn_tooltip_animates(
    page: Page,
    create_test_urls,
    provide_app: Flask,
):
    """
    Tests a tooltip showing when a user hovers the confirm URL-title edit button.

    GIVEN a user has opened the update-URL-title form on a selected URL
    WHEN the user hovers over the confirm (check) button
    THEN ensure the tooltip animates in with the expected copy, and the button
         carries the matching accessible name
    """
    app = provide_app
    user_id_for_test = 1
    _login_and_select_first_url(app=app, page=page, user_id=user_id_for_test)

    url_row = get_selected_url(page=page)
    open_update_url_title(page=page, selected_url_row=url_row)

    parent_css_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE}"
    assert_tooltip_animates(
        page=page,
        parent_css_selector=parent_css_selector,
        tooltip_parent_class=HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE,
        tooltip_text=STRINGS.CONFIRM_URL_TITLE_EDIT_TOOLTIP,
    )

    submit_btn = wait_then_get_element(page=page, css_selector=parent_css_selector)
    assert submit_btn is not None
    assert (
        submit_btn.get_attribute("aria-label") == STRINGS.CONFIRM_URL_TITLE_EDIT_TOOLTIP
    )


def test_update_url_title_cancel_btn_tooltip_animates(
    page: Page,
    create_test_urls,
    provide_app: Flask,
):
    """
    Tests a tooltip showing when a user hovers the cancel URL-title edit button.

    GIVEN a user has opened the update-URL-title form on a selected URL
    WHEN the user hovers over the cancel (x) button
    THEN ensure the tooltip animates in with the expected copy, and the button
         carries the matching accessible name
    """
    app = provide_app
    user_id_for_test = 1
    _login_and_select_first_url(app=app, page=page, user_id=user_id_for_test)

    url_row = get_selected_url(page=page)
    open_update_url_title(page=page, selected_url_row=url_row)

    parent_css_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_TITLE_CANCEL_UPDATE}"
    assert_tooltip_animates(
        page=page,
        parent_css_selector=parent_css_selector,
        tooltip_parent_class=HPL.BUTTON_URL_TITLE_CANCEL_UPDATE,
        tooltip_text=STRINGS.CANCEL_URL_TITLE_EDIT_TOOLTIP,
    )

    cancel_btn = wait_then_get_element(page=page, css_selector=parent_css_selector)
    assert cancel_btn is not None
    assert (
        cancel_btn.get_attribute("aria-label") == STRINGS.CANCEL_URL_TITLE_EDIT_TOOLTIP
    )


def test_update_url_string_submit_btn_tooltip_animates(
    page: Page,
    create_test_urls,
    provide_app: Flask,
):
    """
    Tests a tooltip showing when a user hovers the confirm URL edit button.

    GIVEN a user has opened the update-URL-string form on a selected URL
    WHEN the user hovers over the confirm (check) button
    THEN ensure the tooltip animates in with the expected copy, and the button
         carries the matching accessible name
    """
    app = provide_app
    user_id_for_test = 1
    _login_and_select_first_url(app=app, page=page, user_id=user_id_for_test)
    _open_update_url_string_form(page=page)

    parent_css_selector = (
        f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}"
    )
    assert_tooltip_animates(
        page=page,
        parent_css_selector=parent_css_selector,
        tooltip_parent_class=HPL.BUTTON_URL_STRING_SUBMIT_UPDATE,
        tooltip_text=STRINGS.CONFIRM_URL_EDIT_TOOLTIP,
    )

    submit_btn = wait_then_get_element(page=page, css_selector=parent_css_selector)
    assert submit_btn is not None
    assert submit_btn.get_attribute("aria-label") == STRINGS.CONFIRM_URL_EDIT_TOOLTIP


def test_update_url_string_cancel_btn_tooltip_animates(
    page: Page,
    create_test_urls,
    provide_app: Flask,
):
    """
    Tests a tooltip showing when a user hovers the cancel URL edit button.

    GIVEN a user has opened the update-URL-string form on a selected URL
    WHEN the user hovers over the cancel (x) button
    THEN ensure the tooltip animates in with the expected copy, and the button
         carries the matching accessible name
    """
    app = provide_app
    user_id_for_test = 1
    _login_and_select_first_url(app=app, page=page, user_id=user_id_for_test)
    _open_update_url_string_form(page=page)

    parent_css_selector = (
        f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_CANCEL_UPDATE}"
    )
    assert_tooltip_animates(
        page=page,
        parent_css_selector=parent_css_selector,
        tooltip_parent_class=HPL.BUTTON_URL_STRING_CANCEL_UPDATE,
        tooltip_text=STRINGS.CANCEL_URL_EDIT_TOOLTIP,
    )

    cancel_btn = wait_then_get_element(page=page, css_selector=parent_css_selector)
    assert cancel_btn is not None
    assert cancel_btn.get_attribute("aria-label") == STRINGS.CANCEL_URL_EDIT_TOOLTIP


# Query-parameter trim control (edit-URL-string form). Chips are counted with
# `expect(...).to_have_count(n)` so assertions auto-wait out the 200ms debounce.


def _select_first_mock_url_and_type(
    *, app: Flask, page: Page, typed_url: str
) -> Locator:
    """Select the seeded URL, open its string-edit form and type `typed_url`
    without submitting. Returns the selected URL row."""
    user_id_for_test = 1
    login_user_select_utub_by_name_and_url_by_string(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=MOCK_URL_STRINGS[0],
    )
    url_row = get_selected_url(page=page)
    update_url_string(page=page, url_string=typed_url)
    return url_row


def test_update_url_string_trim_section_absent_without_query(
    page: Page,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a user editing a URL's string
    WHEN the typed URL has no query string (after first having one, so the
        debounced re-parse is proven to have run)
    THEN the query-parameter trim section is not shown
    """
    _, cli_runner = runner
    add_mock_urls(cli_runner, [MOCK_URL_STRINGS[0]])

    _select_first_mock_url_and_type(
        app=provide_app, page=page, typed_url=TRIM_URL_TWO_PARAMS
    )
    expect(page.locator(HPL.EDIT_FORM_TRIM_HEADER)).to_be_visible()

    clear_then_send_keys(
        locator=page.locator(f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE}"),
        input_text=TRIM_BASE_URL,
    )

    expect(page.locator(HPL.EDIT_FORM_TRIM_WRAP)).to_be_hidden()


def test_update_url_string_trim_auto_chips_present_but_not_clickable(
    page: Page,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a user editing a URL's string to one mixing a server-stripped
        tracking param with a normal param
    WHEN the section is expanded and the tracking chip is clicked
    THEN the tracking chip is an inert "auto" chip, the click changes nothing,
        and only the normal param is actionable
    """
    _, cli_runner = runner
    add_mock_urls(cli_runner, [MOCK_URL_STRINGS[0]])

    _select_first_mock_url_and_type(
        app=provide_app, page=page, typed_url=f"{TRIM_BASE_URL}?utm_source=x&keep=1"
    )
    set_trim_section_expanded(
        page=page, header_selector=HPL.EDIT_FORM_TRIM_HEADER, expanded=True
    )

    auto_chip = page.locator(HPL.EDIT_FORM_TRIM_CHIP_AUTO)
    expect(auto_chip).to_have_count(1)
    expect(page.locator(HPL.EDIT_FORM_TRIM_CHIP_ACTIONABLE)).to_have_count(1)
    expect(auto_chip).not_to_have_attribute("aria-pressed", re.compile(r".*"))

    auto_chip.click()

    expect(page.locator(HPL.EDIT_FORM_TRIM_CHIP_ACTIONABLE)).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(auto_chip).to_have_count(1)
    expect(page.locator(HPL.EDIT_FORM_TRIM_DROPPED_COUNT)).to_be_hidden()


def test_update_url_string_trim_collapsed_toggle_drop_save_and_undo(
    page: Page,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a user editing a URL's string to one with two parameters
    WHEN the section appears it is collapsed; expanding it and dropping one
        parameter updates the preview and the (re-collapsed) header's count
    THEN saving stores the trimmed string, the outcome banner reports the
        dropped parameter, and Undo restores the original untrimmed string
    """
    _, cli_runner = runner
    add_mock_urls(cli_runner, [MOCK_URL_STRINGS[0]])

    url_row = _select_first_mock_url_and_type(
        app=provide_app, page=page, typed_url=TRIM_URL_TWO_PARAMS
    )

    header = page.locator(HPL.EDIT_FORM_TRIM_HEADER)
    caret = page.locator(HPL.EDIT_FORM_TRIM_CARET)
    expect(header).to_be_visible()
    expect(header).to_have_attribute("aria-expanded", "false")
    expect(caret).to_have_class(CLOSED_CLASS)
    expect(page.locator(HPL.EDIT_FORM_TRIM_CHIP_ACTIONABLE).first).to_be_hidden()

    set_trim_section_expanded(
        page=page, header_selector=HPL.EDIT_FORM_TRIM_HEADER, expanded=True
    )
    expect(caret).not_to_have_class(CLOSED_CLASS)
    chips = page.locator(HPL.EDIT_FORM_TRIM_CHIP_ACTIONABLE)
    expect(chips).to_have_count(2)

    chips.nth(1).click()
    expect(chips.nth(1)).to_have_attribute("aria-pressed", "false")
    expect(page.locator(HPL.EDIT_FORM_TRIM_PREVIEW)).to_have_text(TRIM_URL_KEEP_ONLY)

    set_trim_section_expanded(
        page=page, header_selector=HPL.EDIT_FORM_TRIM_HEADER, expanded=False
    )
    expect(page.locator(HPL.EDIT_FORM_TRIM_DROPPED_COUNT)).to_have_text(
        URL_TRIM_HEADER_DROPPED.format(n=1)
    )

    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}",
    )
    wait_until_hidden(page=page, css_selector=HPL.UPDATE_URL_STRING_WRAP)

    url_string_elem = url_row.locator(HPL.URL_STRING_READ)
    expect(url_string_elem).to_have_attribute(
        HPL.URL_STRING_IN_DATA, TRIM_URL_KEEP_ONLY
    )
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_TRIM_SAVED_BANNER_ONE
    )
    expect(page.locator(HPL.URL_OUTCOME_BANNER_DETAIL)).to_have_text(TRIM_DROPPED_PARAM)

    # Undo is the banner's one action: a solid fill, splashGreen mixed 75% with
    # black (rgb(36, 167, 69) * 0.75); Chromium serializes color-mix as color(srgb).
    undo_button = page.locator(HPL.URL_OUTCOME_BANNER_UNDO)
    expect(undo_button).to_have_css(
        "background-color", "color(srgb 0.105882 0.491176 0.202941)"
    )
    undo_button.click()

    expect(url_string_elem).to_have_attribute(
        HPL.URL_STRING_IN_DATA, TRIM_URL_TWO_PARAMS
    )
    expect(page.locator(HPL.URL_OUTCOME_BANNER)).to_be_hidden()
    # The (closed) edit input must not keep the trimmed string it was saved with:
    # opening the form again should show the restored original.
    expect(url_row.locator(HPL.INPUT_URL_STRING_UPDATE)).to_have_value(
        TRIM_URL_TWO_PARAMS
    )


def test_update_url_string_plain_edit_shows_updated_banner_and_undo_restores(
    page: Page,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a user editing a URL's string to a different URL with no parameters
    WHEN the edit is saved
    THEN the outcome banner reports "URL updated." (no dropped-parameter detail),
        and Undo restores the string the card showed before the edit, in both the
        card and the (closed) edit input
    """
    _, cli_runner = runner
    add_mock_urls(cli_runner, [MOCK_URL_STRINGS[0]])
    plain_new_url = "https://plain-edit.example.com/path"

    url_row = _select_first_mock_url_and_type(
        app=provide_app, page=page, typed_url=plain_new_url
    )
    url_string_elem = url_row.locator(HPL.URL_STRING_READ)
    original_url = url_string_elem.get_attribute(HPL.URL_STRING_IN_DATA)
    assert original_url is not None

    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}",
    )
    wait_until_hidden(page=page, css_selector=HPL.UPDATE_URL_STRING_WRAP)

    expect(url_string_elem).to_have_attribute(HPL.URL_STRING_IN_DATA, plain_new_url)
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_UPDATED_BANNER
    )
    expect(page.locator(HPL.URL_OUTCOME_BANNER_DETAIL)).to_have_count(0)

    page.locator(HPL.URL_OUTCOME_BANNER_UNDO).click()

    expect(url_string_elem).to_have_attribute(HPL.URL_STRING_IN_DATA, original_url)
    expect(page.locator(HPL.URL_OUTCOME_BANNER)).to_be_hidden()
    expect(url_row.locator(HPL.INPUT_URL_STRING_UPDATE)).to_have_value(original_url)


def test_update_url_string_enter_key_plain_edit_shows_updated_banner(
    page: Page,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a user editing a URL's string to a different URL with no parameters
    WHEN the edit is submitted with the Enter key
    THEN the outcome banner reports "URL updated." with an Undo
    """
    _, cli_runner = runner
    add_mock_urls(cli_runner, [MOCK_URL_STRINGS[0]])
    plain_new_url = "https://plain-edit.example.com/path"

    url_row = _select_first_mock_url_and_type(
        app=provide_app, page=page, typed_url=plain_new_url
    )
    page.keyboard.press("Enter")

    wait_until_hidden(page=page, css_selector=HPL.UPDATE_URL_STRING_WRAP)
    expect(url_row.locator(HPL.URL_STRING_READ)).to_have_attribute(
        HPL.URL_STRING_IN_DATA, plain_new_url
    )
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_UPDATED_BANNER
    )
    expect(page.locator(HPL.URL_OUTCOME_BANNER_UNDO)).to_be_visible()


def test_update_url_string_to_trashed_url_revives_it_and_replaces_edited_card(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with a trashed URL carrying two tags, and a live URL carrying one
        other tag
    WHEN the user edits the live URL's string to the trashed URL's link
    THEN the trashed URL's card reappears with the union of both tag sets, the
        edited card is gone, the edited card's title carries over, and the
        outcome banner reports it was restored from trash
    """
    app = provide_app
    user_id_for_test = 1
    utub_id = get_utub_this_user_created(app, user_id_for_test).id
    with app.app_context():
        utub_urls: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id
        ).all()
        edited_utub_url_id = utub_urls[0].id
        edited_url_title = utub_urls[0].url_title
        trashed_utub_url_id = utub_urls[1].id
        trashed_url_string = utub_urls[1].standalone_url.url_string

    trashed_tag_ids = add_tags_to_utub_url(
        app, utub_id, trashed_utub_url_id, user_id_for_test, ["revivea", "reviveb"]
    )
    trash_utub_url(app, trashed_utub_url_id, user_id_for_test, trashed_tag_ids)
    add_tags_to_utub_url(app, utub_id, edited_utub_url_id, user_id_for_test, ["editc"])

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_id,
        utub_url_id=edited_utub_url_id,
    )
    expect(
        page.locator(f"{HPL.ROWS_URLS}[utuburlid='{trashed_utub_url_id}']")
    ).to_have_count(0)

    update_url_string(page=page, url_string=trashed_url_string)
    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}",
    )

    revived_row = get_url_row_by_id(page=page, utub_url_id=trashed_utub_url_id)
    expect(
        page.locator(f"{HPL.ROWS_URLS}[utuburlid='{edited_utub_url_id}']")
    ).to_have_count(0)
    expect(revived_row.locator(HPL.URL_STRING_READ)).to_have_attribute(
        HPL.URL_STRING_IN_DATA, trashed_url_string
    )
    expect(revived_row.locator(HPL.URL_TITLE_READ)).to_have_text(edited_url_title)
    expect(revived_row.locator(HPL.TAG_BADGES)).to_have_count(3)

    banner = page.locator(HPL.URL_OUTCOME_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_class(re.compile(r"\bsuccess\b"))
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_REVIVED_FROM_TRASH
    )


def test_update_url_string_to_trashed_url_over_tag_limit_shows_error_and_keeps_edited_card(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with a trashed URL carrying 15 tags, and a live URL carrying 10
        other tags, so their union exceeds the per-URL tag limit
    WHEN the user edits the live URL's string to the trashed URL's link
    THEN the at-tag-limit error shows in the edit form, the edited card keeps its
        original link, and the trashed URL is not revived
    """
    app = provide_app
    user_id_for_test = 1
    utub_id = get_utub_this_user_created(app, user_id_for_test).id
    with app.app_context():
        utub_urls: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id
        ).all()
        edited_utub_url_id = utub_urls[0].id
        edited_url_string = utub_urls[0].standalone_url.url_string
        trashed_utub_url_id = utub_urls[1].id
        trashed_url_string = utub_urls[1].standalone_url.url_string

    trashed_tag_ids = add_tags_to_utub_url(
        app,
        utub_id,
        trashed_utub_url_id,
        user_id_for_test,
        [f"trashedtag{index}" for index in range(15)],
    )
    trash_utub_url(app, trashed_utub_url_id, user_id_for_test, trashed_tag_ids)
    add_tags_to_utub_url(
        app,
        utub_id,
        edited_utub_url_id,
        user_id_for_test,
        [f"editedtag{index}" for index in range(10)],
    )

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_id,
        utub_url_id=edited_utub_url_id,
    )

    update_url_string(page=page, url_string=trashed_url_string)
    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}",
    )

    error_css_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE + HPL.INVALID_FIELD_SUFFIX}"
    wait_until_visible_css_selector(page=page, css_selector=error_css_selector)
    expect(page.locator(error_css_selector)).to_have_text(
        TAGS_FAILURE.MAX_URL_TAGS_REACHED.format(max_tags=TAG_CONSTANTS.MAX_URL_TAGS)
    )

    expect(
        page.locator(f"{HPL.ROWS_URLS}[utuburlid='{trashed_utub_url_id}']")
    ).to_have_count(0)
    edited_row = get_url_row_by_id(page=page, utub_url_id=edited_utub_url_id)
    expect(edited_row.locator(HPL.URL_STRING_READ)).to_have_attribute(
        HPL.URL_STRING_IN_DATA, edited_url_string
    )
    expect(edited_row.locator(HPL.TAG_BADGES)).to_have_count(10)


def test_update_url_string_to_trashed_url_as_non_adder_member_drops_trashed_tags(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with a trashed URL carrying two tags that another user added, and
        a live URL the member added carrying one other tag
    WHEN that member, who is neither the trashed URL's adder nor a UTub manager,
        edits the live URL's string to the trashed URL's link
    THEN the trashed URL is revived carrying only the edited URL's tag
    """
    app = provide_app
    creator_user_id = 1
    member_user_id = 2
    utub_id = get_utub_this_user_created(app, creator_user_id).id
    with app.app_context():
        utub_urls: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id
        ).all()
        edited_utub_url_id = utub_urls[0].id
        trashed_utub_url_id = utub_urls[1].id
        trashed_url_string = utub_urls[1].standalone_url.url_string
        utub_urls[0].user_id = member_user_id
        utub_urls[1].user_id = creator_user_id
        db.session.commit()

    trashed_tag_ids = add_tags_to_utub_url(
        app, utub_id, trashed_utub_url_id, creator_user_id, ["revivea", "reviveb"]
    )
    trash_utub_url(app, trashed_utub_url_id, creator_user_id, trashed_tag_ids)
    add_tags_to_utub_url(app, utub_id, edited_utub_url_id, member_user_id, ["editc"])

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=member_user_id,
        utub_id=utub_id,
        utub_url_id=edited_utub_url_id,
    )

    update_url_string(page=page, url_string=trashed_url_string)
    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}",
    )

    revived_row = get_url_row_by_id(page=page, utub_url_id=trashed_utub_url_id)
    expect(
        page.locator(f"{HPL.ROWS_URLS}[utuburlid='{edited_utub_url_id}']")
    ).to_have_count(0)
    expect(revived_row.locator(HPL.TAG_BADGES)).to_have_count(1)
    expect(revived_row.locator(HPL.TAG_BADGES)).to_have_text("editc")
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_REVIVED_FROM_TRASH
    )


def _show_updated_banner_with_fake_clock(*, app: Flask, page: Page) -> Locator:
    """Install Playwright's fake clock, submit a plain edit and return the shown
    outcome banner with the pointer parked away from it."""
    _select_first_mock_url_and_type(
        app=app, page=page, typed_url="https://plain-edit.example.com/path"
    )
    # Installed before the banner shows, so its countdown runs on the fake clock.
    page.clock.install()
    page.keyboard.press("Enter")

    banner = page.locator(HPL.URL_OUTCOME_BANNER)
    expect(banner).to_be_visible()
    # A pointer resting where the banner appears would hold the countdown; moving
    # it away either releases that hold or is a no-op.
    page.mouse.move(1, 1)
    return banner


def test_outcome_banner_hides_itself_after_countdown(
    page: Page,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN the "URL updated." banner is showing
    WHEN the 10s countdown elapses with the pointer elsewhere
    THEN the banner hides itself
    """
    _, cli_runner = runner
    add_mock_urls(cli_runner, [MOCK_URL_STRINGS[0]])

    banner = _show_updated_banner_with_fake_clock(app=provide_app, page=page)
    expect(banner).to_be_visible()

    page.clock.fast_forward(11_000)

    expect(banner).to_be_hidden()


def test_outcome_banner_stays_while_hovered_and_hides_after_leaving(
    page: Page,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN the "URL updated." banner is showing
    WHEN the pointer hovers it past the countdown, then leaves
    THEN the banner stays up while hovered and hides one countdown after leaving
    """
    _, cli_runner = runner
    add_mock_urls(cli_runner, [MOCK_URL_STRINGS[0]])

    banner = _show_updated_banner_with_fake_clock(app=provide_app, page=page)

    banner.hover()
    page.clock.fast_forward(30_000)
    expect(banner).to_be_visible()

    page.mouse.move(1, 1)
    page.clock.fast_forward(11_000)
    expect(banner).to_be_hidden()


def test_update_url_string_trim_conflict_shows_trim_message_and_expands_section(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with two distinct URLs
    WHEN the user edits one to the other's string plus a parameter they drop
        (so the trimmed string collides)
    THEN the trim-specific conflict message replaces the plain one and the trim
        section is force-expanded so the cause is on screen
    """
    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.utub_creator == user_id_for_test).first()
        utub_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub.id
        ).first()
        colliding_url_string: str = utub_url.standalone_url.url_string
        another_utub_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.url_title != utub_url.url_title
        ).first()

    login_user_select_utub_by_name_and_url_by_title(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub.name,
        url_title=another_utub_url.url_title,
    )
    get_selected_url(page=page)
    update_url_string(page=page, url_string=colliding_url_string + "?ref=x")

    set_trim_section_expanded(
        page=page, header_selector=HPL.EDIT_FORM_TRIM_HEADER, expanded=True
    )
    conflict_chip = page.locator(HPL.EDIT_FORM_TRIM_CHIP_ACTIONABLE).first
    conflict_chip.click()
    expect(conflict_chip).to_have_attribute("aria-pressed", "false")
    set_trim_section_expanded(
        page=page, header_selector=HPL.EDIT_FORM_TRIM_HEADER, expanded=False
    )

    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}",
    )

    error_css_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE + HPL.INVALID_FIELD_SUFFIX}"
    expect(page.locator(error_css_selector)).to_have_text(URL_TRIM_CONFLICT)
    expect(page.locator(HPL.EDIT_FORM_TRIM_HEADER)).to_have_attribute(
        "aria-expanded", "true"
    )
