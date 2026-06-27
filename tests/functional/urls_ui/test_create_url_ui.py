from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from backend.cli.mock_constants import (
    MOCK_URL_TITLES,
    MOCK_URL_STRINGS,
)
from backend.models.users import Users
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_urls import Utub_Urls
from backend.utils.constants import CONSTANTS, TAG_CONSTANTS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from backend.utils.strings.json_strs import FIELD_REQUIRED_STR
from backend.utils.strings.url_strs import URL_FAILURE
from tests.functional.assert_utils import (
    assert_login_with_username,
    assert_not_visible_css_selector,
    assert_on_429_page,
    assert_url_coloring_is_correct,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.db_utils import (
    add_tag_to_single_url_in_utub,
    add_tag_to_utub_user_created,
    count_urls_with_tag_applied_by_tag_string,
    get_tag_in_utub_by_tag_string,
    get_utub_this_user_created,
    get_newly_added_utub_url_id_by_url_string,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid,
)
from tests.functional.tags_ui.selenium_utils import (
    apply_tag_filter_based_on_id,
    get_visible_urls_and_urls_with_tag_text_by_tag_id,
)
from tests.functional.selenium_utils import (
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
from tests.functional.urls_ui.selenium_utils import (
    create_url,
    fill_create_url_form,
    stage_new_tag_in_create_form,
    stage_tag_suggestion_in_create_form,
)

pytestmark = pytest.mark.create_urls_ui


def test_create_url_open_input_no_urls_corner_btn(
    browser: WebDriver, create_test_utubs, provide_app: Flask
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
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    wait_then_click_element(browser, HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    assert_not_visible_css_selector(browser, HPL.BUTTON_DECK_URL_CREATE)

    url_title_create_elemnent = browser.find_element(
        By.CSS_SELECTOR, HPL.INPUT_URL_TITLE_CREATE
    )

    assert browser.switch_to.active_element == url_title_create_elemnent


def test_create_url_open_input_no_urls_deck_btn(
    browser: WebDriver, create_test_utubs, provide_app: Flask
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
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    wait_then_click_element(browser, HPL.BUTTON_DECK_URL_CREATE)

    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    assert_not_visible_css_selector(browser, HPL.BUTTON_DECK_URL_CREATE)

    url_title_create_elemnent = browser.find_element(
        By.CSS_SELECTOR, HPL.INPUT_URL_TITLE_CREATE
    )

    assert browser.switch_to.active_element == url_title_create_elemnent


def test_create_url_open_input_with_added_urls(
    browser: WebDriver,
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
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    wait_then_click_element(browser, HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    url_title_create_elemnent = browser.find_element(
        By.CSS_SELECTOR, HPL.INPUT_URL_TITLE_CREATE
    )

    assert browser.switch_to.active_element == url_title_create_elemnent


def test_create_url_cancel_input_click_button(
    browser: WebDriver, create_test_utubs, provide_app: Flask
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
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    wait_then_click_element(browser, HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    wait_then_click_element(browser, HPL.BUTTON_URL_CANCEL_CREATE)

    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()


def test_create_url_cancel_input_escape(
    browser: WebDriver, create_test_utubs, provide_app: Flask
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
        app, browser, user_id_for_test, UTS.TEST_UTUB_NAME_1
    )

    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    wait_then_click_element(browser, HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()


def test_create_url_submit_btn_no_urls(
    browser: WebDriver, create_test_utubs, provide_app: Flask
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0]

    fill_create_url_form(browser, url_title, url_string)
    wait_then_click_element(browser, HPL.BUTTON_URL_SUBMIT_CREATE, time=3)

    # Wait for HTTP request to complete
    wait_until_hidden(browser, HPL.INPUT_URL_STRING_CREATE, timeout=3)
    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    # Extract URL title and string from new row in URL deck
    utub_url_id = get_newly_added_utub_url_id_by_url_string(
        app, utub_user_created.id, url_string
    )
    url_row = get_url_row_by_id(browser, utub_url_id)
    assert url_row is not None

    url_row_title = url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).text
    url_row_string = url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).text
    url_row_href = url_row.find_element(
        By.CSS_SELECTOR, HPL.URL_STRING_READ
    ).get_attribute(HPL.URL_STRING_IN_DATA)

    url_string_visible = url_string.replace("https://", "").replace("www.", "")

    assert url_title == url_row_title
    assert url_row_string == url_string_visible
    assert url_string == url_row_href

    assert_url_coloring_is_correct(browser)

    url_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    wait_until_visible_css_selector(browser, url_selector)
    selected_url = get_selected_url(browser)
    selected_utub_url_id = selected_url.get_attribute("utuburlid")

    assert selected_utub_url_id and selected_utub_url_id.isnumeric()
    assert int(selected_utub_url_id) == utub_url_id


def test_create_url_submit_btn_some_urls(
    browser: WebDriver,
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0] + "extraextra"

    fill_create_url_form(browser, url_title, url_string)
    wait_then_click_element(browser, HPL.BUTTON_URL_SUBMIT_CREATE, time=3)

    # Wait for HTTP request to complete
    wait_until_hidden(browser, HPL.INPUT_URL_STRING_CREATE, timeout=3)
    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    # Extract URL title and string from new row in URL deck
    utub_url_id = get_newly_added_utub_url_id_by_url_string(
        app, utub_user_created.id, url_string
    )
    url_row = get_url_row_by_id(browser, utub_url_id)
    assert url_row is not None

    url_row_title = url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).text
    url_row_string = url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).text
    url_row_href = url_row.find_element(
        By.CSS_SELECTOR, HPL.URL_STRING_READ
    ).get_attribute(HPL.URL_STRING_IN_DATA)

    url_string_visible = url_string.replace("https://", "").replace("www.", "")

    assert url_title == url_row_title
    assert url_row_string == url_string_visible
    assert url_string == url_row_href

    assert_url_coloring_is_correct(browser)

    url_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    wait_until_visible_css_selector(browser, url_selector)
    selected_url = get_selected_url(browser)
    selected_utub_url_id = selected_url.get_attribute("utuburlid")

    assert selected_utub_url_id and selected_utub_url_id.isnumeric()
    assert int(selected_utub_url_id) == utub_url_id


def test_create_url_rate_limits(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0]

    fill_create_url_form(browser, url_title, url_string)
    add_forced_rate_limit_header(browser)
    wait_then_click_element(browser, HPL.BUTTON_URL_SUBMIT_CREATE, time=3)

    assert_on_429_page(browser)


@pytest.mark.parametrize(
    "validated_url,input_url",
    [
        ("https://example.com/", "https://example.com"),
        ("https://example.com/", "example.com"),
        ("https://example.com/", " https://example.com "),
    ],
)
def test_valid_url_input(
    browser: WebDriver,
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    if input_url.startswith(("\t", "\n")):
        # This is needed to insert escaped characters via Selenium into input fields
        input_url = input_url.encode("unicode_escape").decode("utf-8")

    url_title = MOCK_URL_TITLES[0]

    fill_create_url_form(browser, url_title, input_url)
    wait_then_click_element(browser, HPL.BUTTON_URL_SUBMIT_CREATE, time=3)

    # Wait for HTTP request to complete
    wait_until_hidden(browser, HPL.INPUT_URL_STRING_CREATE, timeout=3)
    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    # Extract URL title and string from new row in URL deck
    utub_url_id = get_newly_added_utub_url_id_by_url_string(
        app, utub_user_created.id, ada_validated_url
    )
    url_row = get_url_row_by_id(browser, utub_url_id)
    assert url_row is not None

    url_row_title = url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).text
    url_row_string = url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).text
    url_row_href = url_row.find_element(
        By.CSS_SELECTOR, HPL.URL_STRING_READ
    ).get_attribute(HPL.URL_STRING_IN_DATA)

    url_string_visible = ada_validated_url
    url_string_visible = url_string_visible.removeprefix("https://")
    url_string_visible = url_string_visible.removeprefix("http://")
    url_string_visible = url_string_visible.removeprefix("www.")

    assert url_title == url_row_title
    assert url_row_string == url_string_visible
    assert url_row_href is not None
    assert url_row_href == ada_validated_url

    assert_url_coloring_is_correct(browser)

    url_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    wait_until_visible_css_selector(browser, url_selector)
    selected_url = get_selected_url(browser)
    selected_utub_url_id = selected_url.get_attribute("utuburlid")

    assert selected_utub_url_id and selected_utub_url_id.isnumeric()
    assert int(selected_utub_url_id) == utub_url_id


def test_create_url_using_enter_key_no_urls(
    browser: WebDriver, create_test_utubs, provide_app: Flask
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0]

    fill_create_url_form(browser, url_title, url_string)
    browser.switch_to.active_element.send_keys(Keys.ENTER)

    # Wait for HTTP request to complete
    wait_until_hidden(browser, HPL.INPUT_URL_STRING_CREATE, timeout=3)
    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    # Extract URL title and string from new row in URL deck
    utub_url_id = get_newly_added_utub_url_id_by_url_string(
        app, utub_user_created.id, url_string
    )
    url_row = get_url_row_by_id(browser, utub_url_id)
    assert url_row is not None

    url_row_title = url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).text
    url_row_string = url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).text
    url_row_href = url_row.find_element(
        By.CSS_SELECTOR, HPL.URL_STRING_READ
    ).get_attribute(HPL.URL_STRING_IN_DATA)

    url_string_visible = url_string.replace("https://", "").replace("www.", "")

    assert url_title == url_row_title
    assert url_row_string == url_string_visible
    assert url_string == url_row_href

    assert_url_coloring_is_correct(browser)

    url_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    wait_until_visible_css_selector(browser, url_selector)
    selected_url = get_selected_url(browser)
    selected_utub_url_id = selected_url.get_attribute("utuburlid")

    assert selected_utub_url_id and selected_utub_url_id.isnumeric()
    assert int(selected_utub_url_id) == utub_url_id


def test_create_url_using_enter_key_some_urls(
    browser: WebDriver, create_test_urls, provide_app: Flask
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0] + "extraextra"

    fill_create_url_form(browser, url_title, url_string)
    browser.switch_to.active_element.send_keys(Keys.ENTER)

    # Wait for HTTP request to complete
    wait_until_hidden(browser, HPL.INPUT_URL_STRING_CREATE, timeout=3)
    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    # Extract URL title and string from new row in URL deck
    utub_url_id = get_newly_added_utub_url_id_by_url_string(
        app, utub_user_created.id, url_string
    )
    url_row = get_url_row_by_id(browser, utub_url_id)
    assert url_row is not None

    url_row_title = url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ).text
    url_row_string = url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).text
    url_row_href = url_row.find_element(
        By.CSS_SELECTOR, HPL.URL_STRING_READ
    ).get_attribute(HPL.URL_STRING_IN_DATA)

    url_string_visible = url_string.replace("https://", "").replace("www.", "")

    assert url_title == url_row_title
    assert url_row_string == url_string_visible
    assert url_string == url_row_href

    assert_url_coloring_is_correct(browser)

    url_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    wait_until_visible_css_selector(browser, url_selector)
    selected_url = get_selected_url(browser)
    selected_utub_url_id = selected_url.get_attribute("utuburlid")

    assert selected_utub_url_id and selected_utub_url_id.isnumeric()
    assert int(selected_utub_url_id) == utub_url_id


def test_create_url_title_length_exceeded(
    browser: WebDriver, create_test_utubs, provide_app: Flask
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    wait_then_click_element(browser, HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    # Input new URL Title
    url_title_input_field = wait_then_get_element(browser, HPL.INPUT_URL_TITLE_CREATE)
    assert url_title_input_field is not None
    clear_then_send_keys(
        url_title_input_field, "a" * (CONSTANTS.URLS.MAX_URL_TITLE_LENGTH + 1)
    )

    create_url_title_input = wait_then_get_element(
        browser, HPL.INPUT_URL_TITLE_CREATE, time=3
    )
    assert create_url_title_input is not None
    new_url_title = create_url_title_input.get_attribute("value")
    assert new_url_title is not None

    assert len(new_url_title) == CONSTANTS.URLS.MAX_URL_TITLE_LENGTH


def test_create_url_empty_fields(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    wait_then_click_element(browser, HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    # Submit URL
    wait_then_click_element(browser, HPL.BUTTON_URL_SUBMIT_CREATE, time=3)

    invalid_url_title_error = wait_then_get_element(
        browser, HPL.INPUT_URL_TITLE_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_url_title_error is not None
    assert invalid_url_title_error.text == FIELD_REQUIRED_STR

    invalid_url_string_error = wait_then_get_element(
        browser, HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_url_string_error is not None
    assert invalid_url_string_error.text == FIELD_REQUIRED_STR


def test_create_url_empty_title(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    wait_then_click_element(browser, HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    url_string_input_field = wait_then_get_element(browser, HPL.INPUT_URL_STRING_CREATE)
    assert url_string_input_field is not None
    clear_then_send_keys(url_string_input_field, MOCK_URL_STRINGS[0])

    # Submit URL
    wait_then_click_element(browser, HPL.BUTTON_URL_SUBMIT_CREATE, time=3)

    invalid_url_title_error = wait_then_get_element(
        browser, HPL.INPUT_URL_TITLE_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_url_title_error is not None
    assert invalid_url_title_error.text == FIELD_REQUIRED_STR


def test_create_url_empty_string(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    wait_then_click_element(browser, HPL.BUTTON_CORNER_URL_CREATE)

    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    url_title_input_field = wait_then_get_element(browser, HPL.INPUT_URL_TITLE_CREATE)
    assert url_title_input_field is not None
    clear_then_send_keys(url_title_input_field, "Testing")

    # Submit URL
    wait_then_click_element(browser, HPL.BUTTON_URL_SUBMIT_CREATE, time=3)

    invalid_url_string_error = wait_then_get_element(
        browser, HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_url_string_error is not None
    assert invalid_url_string_error.text == FIELD_REQUIRED_STR


@pytest.mark.parametrize(
    "invalid_url",
    [
        "javascript:alert(1)",
        "data:text/html,<script>",
        "https://asdfasdfasdf",
    ],
)
def test_invalid_url_input(
    browser: WebDriver, create_test_utubs, provide_app: Flask, invalid_url: str
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    create_url(browser, url_title="Test", url_string=invalid_url)

    wait_until_visible_css_selector(
        browser, HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX, timeout=3
    )

    invalid_url_string_error = wait_then_get_element(
        browser, HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_url_string_error is not None
    assert invalid_url_string_error.text == URL_FAILURE.UNABLE_TO_VALIDATE_THIS_URL


def test_invalid_credentials_url_input(
    browser: WebDriver, create_test_utubs, provide_app: Flask
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    invalid_url = "https://user:password@example.com"
    create_url(browser, url_title="Test", url_string=invalid_url)

    wait_until_visible_css_selector(
        browser, HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX, timeout=3
    )

    invalid_url_string_error = wait_then_get_element(
        browser, HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_url_string_error is not None
    assert invalid_url_string_error.text == URL_FAILURE.URLS_WITH_CREDENTIALS_EXCEPTION


def test_create_url_sanitized_title(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    create_url(browser, url_title='<img src="evl.jpg">', url_string=MOCK_URL_STRINGS[0])
    wait_until_visible_css_selector(
        browser, HPL.INPUT_URL_TITLE_CREATE + HPL.INVALID_FIELD_SUFFIX, timeout=3
    )

    invalid_url_title_error = wait_then_get_element(
        browser, HPL.INPUT_URL_TITLE_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_url_title_error is not None
    assert invalid_url_title_error.text == URL_FAILURE.INVALID_INPUT


def test_create_url_duplicate_url(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    create_url(browser, url_title="Testing", url_string=url_string_already_added)

    invalid_url_string_error = wait_then_get_element(
        browser, HPL.INPUT_URL_STRING_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_url_string_error is not None
    assert invalid_url_string_error.text == URL_FAILURE.URL_IN_UTUB


def test_create_url_invalid_csrf_token(
    browser: WebDriver, create_test_utubs, provide_app: Flask
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    invalidate_csrf_token_on_page(browser)
    create_url(browser, url_title="Testing", url_string=MOCK_URL_STRINGS[0])

    assert_visited_403_on_invalid_csrf_and_reload(browser)

    # Page reloads after user clicks button in CSRF 403 error page
    create_utub_name_input = wait_until_hidden(
        browser, HPL.INPUT_URL_STRING_CREATE, timeout=3
    )
    assert not create_utub_name_input.is_displayed()
    assert_login_with_username(browser, user.username)


def test_create_url_when_utub_tag_applied(
    browser: WebDriver, create_test_tags, provide_app: Flask
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
        app, browser, user_id_for_test, utub_user_created.id
    )

    apply_tag_filter_based_on_id(browser, tag_id_in_utub)

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0] + "extraextra"

    fill_create_url_form(browser, url_title, url_string)
    wait_then_click_element(browser, HPL.BUTTON_URL_SUBMIT_CREATE, time=3)

    # Wait for HTTP request to complete
    wait_until_hidden(browser, HPL.INPUT_URL_STRING_CREATE, timeout=3)
    url_creation_row = browser.find_element(By.CSS_SELECTOR, HPL.WRAP_URL_CREATE)
    assert not url_creation_row.is_displayed()

    # Extract URL title and string from new row in URL deck
    utub_url_id = get_newly_added_utub_url_id_by_url_string(
        app, utub_user_created.id, url_string
    )
    assert_not_visible_css_selector(
        browser, HPL.ROWS_URLS + f'[utuburlid="{utub_url_id}"]'
    )


EXISTING_TAG_FOR_CREATE = "Alpha"
FRESH_TAG_FOR_CREATE = "Fresh"
FILTER_TAG = "filterme"
NON_MATCHING_TAG = "different"


def _badge_count_on_url_row(url_row: WebElement) -> int:
    return len(url_row.find_elements(By.CSS_SELECTOR, HPL.TAG_BADGES))


def test_create_url_with_staged_tags(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
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

    with app.app_context():
        init_fresh_tag_count: int = count_urls_with_tag_applied_by_tag_string(
            app, utub_id, FRESH_TAG_FOR_CREATE
        )
    assert init_fresh_tag_count == 0

    login_user_and_select_utub_by_utubid(app, browser, user_id_for_test, utub_id)

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0] + "withtags"

    fill_create_url_form(browser, url_title, url_string)
    # A brand-new tag is staged via the "Create tag" option; an existing UTub
    # tag has an exact match so it surfaces as a suggestion (no create-new
    # option) and must be staged via the suggestion flow.
    stage_new_tag_in_create_form(browser, FRESH_TAG_FOR_CREATE)
    stage_tag_suggestion_in_create_form(browser, EXISTING_TAG_FOR_CREATE)

    staged_chips = browser.find_elements(
        By.CSS_SELECTOR, HPL.CREATE_FORM_TAG_STAGED_CHIP
    )
    assert len(staged_chips) == 2

    wait_then_click_element(browser, HPL.BUTTON_URL_SUBMIT_CREATE, time=3)
    wait_until_hidden(browser, HPL.INPUT_URL_STRING_CREATE, timeout=5)

    utub_url_id = get_newly_added_utub_url_id_by_url_string(app, utub_id, url_string)
    url_row = get_url_row_by_id(browser, utub_url_id)
    assert url_row is not None

    wait_until_visible_css_selector(
        browser, f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}'] {HPL.TAG_BADGES}"
    )
    assert _badge_count_on_url_row(url_row) == 2

    # The brand-new tag appears in the tag deck with count 1.
    fresh_tag = get_tag_in_utub_by_tag_string(app, utub_id, FRESH_TAG_FOR_CREATE)
    fresh_tag_selector = (
        f'{HPL.LIST_TAGS} {HPL.TAG_FILTERS}[data-utub-tag-id="{fresh_tag.id}"]'
    )
    fresh_tag_elem = wait_then_get_element(browser, fresh_tag_selector, time=3)
    assert fresh_tag_elem is not None

    _, fresh_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, fresh_tag.id
    )
    assert fresh_total == init_fresh_tag_count + 1

    # The existing tag's deck counter reflects the new URL.
    existing_tag = get_tag_in_utub_by_tag_string(app, utub_id, EXISTING_TAG_FOR_CREATE)
    _, existing_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, existing_tag.id
    )
    assert existing_total == 1


def test_create_url_with_zero_tags_regression(
    browser: WebDriver, create_test_urls, provide_app: Flask
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

    login_user_and_select_utub_by_utubid(app, browser, user_id_for_test, utub_id)

    url_title = MOCK_URL_TITLES[0]
    url_string = MOCK_URL_STRINGS[0] + "notags"

    create_url(browser, url_title, url_string)
    wait_until_hidden(browser, HPL.INPUT_URL_STRING_CREATE, timeout=5)

    utub_url_id = get_newly_added_utub_url_id_by_url_string(app, utub_id, url_string)
    url_row = get_url_row_by_id(browser, utub_url_id)
    assert url_row is not None
    assert _badge_count_on_url_row(url_row) == 0


def test_create_url_staging_respects_tag_cap(
    browser: WebDriver, create_test_urls, provide_app: Flask
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

    login_user_and_select_utub_by_utubid(app, browser, user_id_for_test, utub_id)

    fill_create_url_form(browser, MOCK_URL_TITLES[0], MOCK_URL_STRINGS[0] + "cap")

    for tag_index in range(TAG_CONSTANTS.MAX_URL_TAGS):
        stage_new_tag_in_create_form(browser, f"captag{tag_index}")

    staged_chips = browser.find_elements(
        By.CSS_SELECTOR, HPL.CREATE_FORM_TAG_STAGED_CHIP
    )
    assert len(staged_chips) == TAG_CONSTANTS.MAX_URL_TAGS

    # At the cap, the combobox input is disabled so no further chip can be staged.
    combobox_input = browser.find_element(
        By.CSS_SELECTOR, HPL.CREATE_FORM_TAG_COMBOBOX_INPUT
    )
    assert not combobox_input.is_enabled()

    staged_chips_after = browser.find_elements(
        By.CSS_SELECTOR, HPL.CREATE_FORM_TAG_STAGED_CHIP
    )
    assert len(staged_chips_after) == TAG_CONSTANTS.MAX_URL_TAGS


def test_create_url_with_matching_filter_tag_is_visible(
    browser: WebDriver, create_test_urls, provide_app: Flask
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

    login_user_and_select_utub_by_utubid(app, browser, user_id_for_test, utub_id)

    apply_tag_filter_based_on_id(browser, filter_tag.id)

    url_string = MOCK_URL_STRINGS[1] + "matchfilter"
    fill_create_url_form(browser, MOCK_URL_TITLES[1], url_string)
    # `FILTER_TAG` already exists in the UTub (applied to an existing URL), so it
    # surfaces as a suggestion rather than a create-new option.
    stage_tag_suggestion_in_create_form(browser, FILTER_TAG)
    wait_then_click_element(browser, HPL.BUTTON_URL_SUBMIT_CREATE, time=3)
    wait_until_hidden(browser, HPL.INPUT_URL_STRING_CREATE, timeout=5)

    utub_url_id = get_newly_added_utub_url_id_by_url_string(app, utub_id, url_string)
    new_url_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    wait_until_visible_css_selector(browser, new_url_selector, timeout=5)
    new_url_row = browser.find_element(By.CSS_SELECTOR, new_url_selector)
    assert new_url_row.is_displayed()
    assert new_url_row.get_attribute("filterable") == "true"
    assert _badge_count_on_url_row(new_url_row) == 1


def test_create_url_with_non_matching_filter_tag_is_hidden(
    browser: WebDriver, create_test_urls, provide_app: Flask
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

    login_user_and_select_utub_by_utubid(app, browser, user_id_for_test, utub_id)

    apply_tag_filter_based_on_id(browser, filter_tag.id)

    url_string = MOCK_URL_STRINGS[1] + "nomatch"
    fill_create_url_form(browser, MOCK_URL_TITLES[1], url_string)
    stage_new_tag_in_create_form(browser, NON_MATCHING_TAG)
    wait_then_click_element(browser, HPL.BUTTON_URL_SUBMIT_CREATE, time=3)
    wait_until_hidden(browser, HPL.INPUT_URL_STRING_CREATE, timeout=5)

    utub_url_id = get_newly_added_utub_url_id_by_url_string(app, utub_id, url_string)
    new_url_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    # The card is created but hidden by the active filter; use a presence wait
    # (not a visibility wait) since the row is in the DOM but not displayed.
    wait_for_element_presence(browser, new_url_selector, timeout=5)
    new_url_row = browser.find_element(By.CSS_SELECTOR, new_url_selector)
    assert new_url_row.get_attribute("filterable") == "false"
    assert_not_visible_css_selector(browser, new_url_selector)
