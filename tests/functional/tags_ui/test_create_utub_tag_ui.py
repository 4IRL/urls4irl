from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from src.models.users import Users
from src.models.utub_tags import Utub_Tags
from src.models.utubs import Utubs
from src.utils.strings.tag_strs import TAGS_FAILURE
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.assert_utils import (
    assert_login_with_username,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.db_utils import (
    count_urls_with_tag_applied_by_tag_string,
    get_tag_in_utub_by_tag_string,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_select_utub_by_id_open_create_utub_tag,
)
from tests.functional.tags_ui.assert_utils import (
    assert_create_utub_tag_input_form_is_hidden,
    assert_new_utub_tag_created,
)
from tests.functional.selenium_utils import (
    invalidate_csrf_token_on_page,
    set_focus_on_element,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)
from tests.functional.tags_ui.selenium_utils import (
    get_visible_urls_and_urls_with_tag_text_by_tag_id,
)

pytestmark = pytest.mark.tags_ui


# Happy Path Tests :)
def test_open_input_create_utub_tag(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests ability to open the create UTub tag form

    GIVEN a user is a UTub member and has selected the UTub
    WHEN the user clicks on the create UTub tag plus button
    THEN ensure the createUTubTag form is opened
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )

    wait_then_click_element(browser, HPL.BUTTON_UTUB_TAG_CREATE, time=3)
    wait_until_visible_css_selector(browser, HPL.INPUT_UTUB_TAG_CREATE, timeout=3)

    assert browser.switch_to.active_element == browser.find_element(
        By.CSS_SELECTOR, HPL.INPUT_UTUB_TAG_CREATE
    )

    visible_elems = (
        HPL.INPUT_UTUB_TAG_CREATE,
        HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE,
        HPL.BUTTON_UTUB_TAG_CANCEL_CREATE,
        HPL.BUTTON_UNSELECT_ALL,
    )

    for visible_elem_selector in visible_elems:
        visible_elem = browser.find_element(By.CSS_SELECTOR, visible_elem_selector)
        assert visible_elem.is_displayed()
        assert visible_elem.is_enabled()

    non_visible_elems = (
        HPL.BUTTON_UTUB_TAG_CREATE,
        HPL.LIST_TAGS,
    )
    for non_visible_elem_selector in non_visible_elems:
        non_visible_elem = browser.find_element(
            By.CSS_SELECTOR, non_visible_elem_selector
        )
        assert not non_visible_elem.is_displayed()


def test_open_input_create_utub_tag_tab_focus(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests ability to open the create UTub tag form

    GIVEN a user is a UTub member and has selected the UTub
    WHEN the user tags to the create UTub tag plus button
    THEN ensure the createUTubTag form is opened
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )

    create_utub_tag_btn = wait_then_get_element(
        browser, HPL.BUTTON_UTUB_TAG_CREATE, time=3
    )
    assert create_utub_tag_btn is not None

    set_focus_on_element(browser, create_utub_tag_btn)
    create_utub_tag_btn.send_keys(Keys.ENTER)

    wait_until_visible_css_selector(browser, HPL.INPUT_UTUB_TAG_CREATE, timeout=3)

    assert browser.switch_to.active_element == browser.find_element(
        By.CSS_SELECTOR, HPL.INPUT_UTUB_TAG_CREATE
    )

    visible_elems = (
        HPL.INPUT_UTUB_TAG_CREATE,
        HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE,
        HPL.BUTTON_UTUB_TAG_CANCEL_CREATE,
        HPL.BUTTON_UNSELECT_ALL,
    )

    for visible_elem_selector in visible_elems:
        visible_elem = browser.find_element(By.CSS_SELECTOR, visible_elem_selector)
        assert visible_elem.is_displayed()
        assert visible_elem.is_enabled()

    non_visible_elems = (
        HPL.BUTTON_UTUB_TAG_CREATE,
        HPL.LIST_TAGS,
    )
    for non_visible_elem_selector in non_visible_elems:
        non_visible_elem = browser.find_element(
            By.CSS_SELECTOR, non_visible_elem_selector
        )
        assert not non_visible_elem.is_displayed()


def test_open_input_create_utub_tag_click_cancel_btn(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests ability to close the create UTub tag form by clicking cancel button

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user clicks on the cancel button
    THEN ensure the createUTubTag form is closed
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_select_utub_by_id_open_create_utub_tag(
        app, browser, user_id_for_test, utub_user_created.id
    )

    wait_then_click_element(browser, HPL.BUTTON_UTUB_TAG_CANCEL_CREATE)
    wait_until_hidden(browser, HPL.BUTTON_UTUB_TAG_CANCEL_CREATE)
    assert_create_utub_tag_input_form_is_hidden(browser)


def test_open_input_create_utub_tag_press_esc_key(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests ability to close the create UTub tag form by clicking cancel button

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the escape key while focused on the input field
    THEN ensure the createUTubTag form is closed
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_select_utub_by_id_open_create_utub_tag(
        app, browser, user_id_for_test, utub_user_created.id
    )

    wait_until_in_focus(browser, HPL.INPUT_UTUB_TAG_CREATE, timeout=3)
    browser.switch_to.active_element.send_keys(Keys.ESCAPE)
    wait_until_hidden(browser, HPL.BUTTON_UTUB_TAG_CANCEL_CREATE)
    assert_create_utub_tag_input_form_is_hidden(browser)


def test_open_input_create_utub_tag_click_submit_btn(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests ability to add a new tag to the UTub

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the submit button after typing in a new UTub tag
    THEN ensure the createUTubTag form is closed and the new UTub tag is added
    """
    app = provide_app
    user_id_for_test = 1
    new_tag = "WOWZA123"
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.name == UTS.TEST_UTUB_NAME_1).first()
        init_num_of_utub_tags = len(utub.utub_tags)

        # Count urls with new tag in UTub. Should be 0.
        init_tag_count_in_utub: int = count_urls_with_tag_applied_by_tag_string(
            app, utub.id, new_tag
        )

    login_user_select_utub_by_id_open_create_utub_tag(
        app, browser, user_id_for_test, utub_user_created.id
    )

    wait_until_in_focus(browser, HPL.INPUT_UTUB_TAG_CREATE, timeout=3)
    browser.switch_to.active_element.send_keys(new_tag)
    wait_then_click_element(browser, HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)
    wait_until_hidden(browser, HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    assert_create_utub_tag_input_form_is_hidden(browser)
    assert_new_utub_tag_created(browser, new_tag, init_num_of_utub_tags)

    # Assert Tag Deck counter initialized at 0
    utub_tag = get_tag_in_utub_by_tag_string(app, utub_user_created.id, new_tag)
    utub_tag_selector = f'{HPL.TAG_FILTERS}[data-utub-tag-id="{utub_tag.id}"]'
    utub_tag_elem = wait_then_get_element(browser, utub_tag_selector)
    assert utub_tag_elem

    visible_urls, total_urls = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, utub_tag.id
    )
    assert visible_urls == 0
    assert total_urls == init_tag_count_in_utub


def test_open_input_create_utub_tag_press_enter_key(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests ability to add a new tag to the UTub

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the enter key after typing in a new UTub tag and focused on input
    THEN ensure the createUTubTag form is closed and the new UTub tag is added
    """
    app = provide_app
    user_id_for_test = 1
    new_tag = "WOWZA123"
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.name == UTS.TEST_UTUB_NAME_1).first()
        init_num_of_utub_tags = len(utub.utub_tags)

        # Count urls with new tag in UTub. Should be 0.
        init_tag_count_in_utub: int = count_urls_with_tag_applied_by_tag_string(
            app, utub.id, new_tag
        )

    login_user_select_utub_by_id_open_create_utub_tag(
        app, browser, user_id_for_test, utub_user_created.id
    )

    wait_until_in_focus(browser, HPL.INPUT_UTUB_TAG_CREATE, timeout=3)
    browser.switch_to.active_element.send_keys(new_tag)
    browser.switch_to.active_element.send_keys(Keys.ENTER)
    wait_until_hidden(browser, HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    assert_create_utub_tag_input_form_is_hidden(browser)
    assert_new_utub_tag_created(browser, new_tag, init_num_of_utub_tags)

    # Assert Tag Deck counter initialized at 0
    utub_tag = get_tag_in_utub_by_tag_string(app, utub_user_created.id, new_tag)
    utub_tag_selector = f'{HPL.TAG_FILTERS}[data-utub-tag-id="{utub_tag.id}"]'
    utub_tag_elem = wait_then_get_element(browser, utub_tag_selector)
    assert utub_tag_elem

    visible_urls, total_urls = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, utub_tag.id
    )
    assert visible_urls == 0
    assert total_urls == init_tag_count_in_utub


# Sad Path Tests
def test_create_utub_tag_empty_field(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests ability to attempt to add a new tag to the UTub with an empty tag field

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the submit button after not typing in a tag
    THEN ensure U4I provides the proper error response to the user
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_select_utub_by_id_open_create_utub_tag(
        app, browser, user_id_for_test, utub_user_created.id
    )

    wait_until_in_focus(browser, HPL.INPUT_UTUB_TAG_CREATE, timeout=3)
    browser.switch_to.active_element.send_keys("")
    wait_then_click_element(browser, HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    invalid_utub_tag_error = wait_then_get_element(
        browser, HPL.INPUT_UTUB_TAG_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_utub_tag_error is not None
    assert invalid_utub_tag_error.text == TAGS_FAILURE.FIELD_REQUIRED_STR


def test_create_utub_tag_duplicate_tag(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests ability to attempt to add a duplicate tag to the UTub

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the submit button after typing in a tag that is already in this UTub
    THEN ensure U4I provides the proper error response to the user
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    with app.app_context():
        utub_tag: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_user_created.id
        ).first()
        utub_tag_duplicate = utub_tag.tag_string

    login_user_select_utub_by_id_open_create_utub_tag(
        app, browser, user_id_for_test, utub_user_created.id
    )

    wait_until_in_focus(browser, HPL.INPUT_UTUB_TAG_CREATE, timeout=3)
    browser.switch_to.active_element.send_keys(utub_tag_duplicate)
    wait_then_click_element(browser, HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    invalid_utub_tag_error = wait_then_get_element(
        browser, HPL.INPUT_UTUB_TAG_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_utub_tag_error is not None
    assert invalid_utub_tag_error.text == TAGS_FAILURE.TAG_ALREADY_IN_UTUB


def test_create_utub_tag_tag_with_whitespace(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests ability to attempt to add a duplicate tag to the UTub

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the submit button after typing in a tag that is already in this UTub
    THEN ensure U4I provides the proper error response to the user
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    with app.app_context():
        utub_tag: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_user_created.id
        ).first()
        utub_tag_duplicate = utub_tag.tag_string

    login_user_select_utub_by_id_open_create_utub_tag(
        app, browser, user_id_for_test, utub_user_created.id
    )

    wait_until_in_focus(browser, HPL.INPUT_UTUB_TAG_CREATE, timeout=3)
    browser.switch_to.active_element.send_keys(f" {utub_tag_duplicate} ")
    wait_then_click_element(browser, HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    invalid_utub_tag_error = wait_then_get_element(
        browser, HPL.INPUT_UTUB_TAG_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_utub_tag_error is not None
    assert invalid_utub_tag_error.text == TAGS_FAILURE.TAG_ALREADY_IN_UTUB


def test_create_utub_tag_sanitized_tag(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests ability to attempt to add a tag to the UTub that contains improper or unsanitzed inputs

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the submit button after typing in a tag that contains improper or unsanitized inputs
    THEN ensure U4I provides the proper error response to the user
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_select_utub_by_id_open_create_utub_tag(
        app, browser, user_id_for_test, utub_user_created.id
    )

    wait_until_in_focus(browser, HPL.INPUT_UTUB_TAG_CREATE, timeout=3)
    browser.switch_to.active_element.send_keys('<img src="evl.jpg">')
    wait_then_click_element(browser, HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    invalid_utub_tag_error = wait_then_get_element(
        browser, HPL.INPUT_UTUB_TAG_CREATE + HPL.INVALID_FIELD_SUFFIX, time=3
    )
    assert invalid_utub_tag_error is not None
    assert invalid_utub_tag_error.text == TAGS_FAILURE.INVALID_INPUT


def test_create_utub_tag_invalid_csrf(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests ability to attempt to add a tag to the UTub with an invalid csrf token

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the submit button with an invalid csrf token
    THEN ensure U4I provides the proper error response to the user
    """
    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        user: Users = Users.query.get(user_id_for_test)

    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_select_utub_by_id_open_create_utub_tag(
        app, browser, user_id_for_test, utub_user_created.id
    )

    wait_until_in_focus(browser, HPL.INPUT_UTUB_TAG_CREATE, timeout=3)
    browser.switch_to.active_element.send_keys("New tag123")
    invalidate_csrf_token_on_page(browser)
    wait_then_click_element(browser, HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    assert_visited_403_on_invalid_csrf_and_reload(browser)

    new_utub_tag_input = wait_until_hidden(
        browser, HPL.INPUT_UTUB_TAG_CREATE, timeout=3
    )
    assert not new_utub_tag_input.is_displayed()
    assert_login_with_username(browser, user.username)
