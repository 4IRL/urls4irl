import random
from typing import Tuple
from urllib.parse import urlsplit

from flask import Flask
from flask.testing import FlaskCliRunner
import pytest
from playwright.sync_api import Page, expect

from backend.cli.mock_constants import (
    MOCK_URL_STRINGS,
    MOCK_URL_TRACKING_STRIPPED,
    MOCK_URL_WITH_TRACKING_PARAMS,
)
from backend.models.users import Users
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.constants import STRINGS, URL_CONSTANTS
from backend.utils.strings.json_strs import FIELD_REQUIRED_STR
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from backend.utils.strings.url_strs import URL_FAILURE
from tests.functional.db_utils import (
    add_mock_urls,
    get_utub_this_user_created,
    get_url_in_utub,
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
    get_selected_url,
    invalidate_csrf_token_on_page,
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
    update_url_string,
    update_url_title,
)

pytestmark = pytest.mark.update_urls_ui


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
        css_selector=HPL.INPUT_URL_STRING_UPDATE + HPL.INVALID_FIELD_SUFFIX,
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
        css_selector=HPL.INPUT_URL_TITLE_UPDATE + HPL.INVALID_FIELD_SUFFIX,
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
