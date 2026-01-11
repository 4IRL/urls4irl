from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from src.models.users import Users
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utub_urls import Utub_Urls
from src.utils.constants import CONSTANTS, STRINGS
from src.utils.strings.tag_strs import TAGS_FAILURE
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.assert_utils import (
    assert_login_with_username,
    assert_on_429_page,
    assert_tooltip_animates,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.db_utils import (
    add_tag_to_utub_user_created,
    count_urls_with_tag_applied_by_tag_string,
    get_tag_in_utub_by_tag_string,
    get_tag_string_already_on_url_in_utub_and_delete,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
    get_url_in_utub,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import login_user_select_utub_by_id_and_url_by_id
from tests.functional.tags_ui.assert_utils import (
    assert_btns_shown_on_cancel_url_tag_input_creator,
    assert_btns_shown_on_cancel_url_tag_input_member,
)
from tests.functional.tags_ui.selenium_utils import (
    add_tag_to_url,
    get_visible_urls_and_urls_with_tag_text_by_tag_id,
    open_url_tag_input,
)
from tests.functional.selenium_utils import (
    add_forced_rate_limit_header,
    invalidate_csrf_token_on_page,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_hidden,
)

pytestmark = pytest.mark.tags_ui


def test_create_tag_btn_tooltip_animates(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a member's ability to see the tooltip animate when hovering over the add URL tag button.

    GIVEN a user in a UTub with URLs
    WHEN the user selects a URL, and hovers over the add URL tag button
    THEN ensure the tooltip for the add URL tag button is animated properly
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    assert_tooltip_animates(
        browser=browser,
        parent_css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_CREATE}",
        tooltip_parent_class=HPL.BUTTON_TAG_CREATE,
        tooltip_text=STRINGS.ADD_URL_TAG_TOOLTIP,
    )


def test_open_input_create_tag_creator(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a UTub creator's ability to open the create tag input field on a given URL.

    GIVEN a user is a UTub creator with the UTub selected
    WHEN the user selects a URL, and clicks the 'Add Tag' button
    THEN ensure the createTag form is opened.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    open_url_tag_input(browser, url_in_utub.id)
    selected_url_create_tag_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_TAG_CREATE}"

    url_tag_input = wait_then_get_element(
        browser, selected_url_create_tag_selector, time=3
    )
    assert browser.switch_to.active_element == browser.find_element(
        By.CSS_SELECTOR, selected_url_create_tag_selector
    )
    assert url_tag_input is not None
    assert url_tag_input.is_displayed()

    hidden_elements = (
        HPL.BUTTON_URL_ACCESS,
        HPL.BUTTON_URL_STRING_UPDATE,
        HPL.BUTTON_URL_DELETE,
    )

    for elem_selector in hidden_elements:
        hidden_elem_selector = f"{HPL.ROW_SELECTED_URL} {elem_selector}"
        hidden_btn = browser.find_element(By.CSS_SELECTOR, hidden_elem_selector)
        assert not hidden_btn.is_displayed()

    # Verify Add Tag button now includes class and text indicating it is the big cancel button
    add_tag_btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_CREATE}"
    add_tag_btn = browser.find_element(By.CSS_SELECTOR, add_tag_btn_selector)
    assert add_tag_btn.is_displayed()
    classes = add_tag_btn.get_attribute("class")
    assert classes and HPL.BUTTON_BIG_TAG_CANCEL_CREATE.replace(".", "") in classes


def test_open_input_create_tag_member(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a UTub member's ability to open the create tag input field on a given URL.

    GIVEN a user is a UTub member with the UTub selected and a URL selected that they did not add
    WHEN the user clicks the 'Add Tag' button
    THEN ensure the createTag form is opened.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id_for_test)

    with app.app_context():
        utub_url_user_did_not_add: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_did_not_create.id,
            Utub_Urls.user_id != user_id_for_test,
        ).first()

    login_user_select_utub_by_id_and_url_by_id(
        app,
        browser,
        user_id_for_test,
        utub_user_did_not_create.id,
        utub_url_user_did_not_add.id,
    )

    open_url_tag_input(browser, utub_url_user_did_not_add.id)
    selected_url_create_tag_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_TAG_CREATE}"

    url_tag_input = wait_then_get_element(
        browser, selected_url_create_tag_selector, time=3
    )
    assert browser.switch_to.active_element == browser.find_element(
        By.CSS_SELECTOR, selected_url_create_tag_selector
    )
    assert url_tag_input is not None
    assert url_tag_input.is_displayed()

    hidden_elem_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    hidden_btn = browser.find_element(By.CSS_SELECTOR, hidden_elem_selector)
    assert not hidden_btn.is_displayed()

    # Verify Add Tag button now includes class and text indicating it is the big cancel button
    add_tag_btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_CREATE}"
    add_tag_btn = browser.find_element(By.CSS_SELECTOR, add_tag_btn_selector)
    assert add_tag_btn.is_displayed()
    classes = add_tag_btn.get_attribute("class")
    assert classes and HPL.BUTTON_BIG_TAG_CANCEL_CREATE.replace(".", "") in classes


def test_cancel_input_create_tag_btn_creator(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a UTub owner's ability to close the create tag input field.

    GIVEN a user is the UTub owner with the UTub and URL selected
    WHEN the user clicks the createURLTag button, then clicks the cancel button
    THEN ensure the createURLTag form is hidden.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    open_url_tag_input(browser, url_in_utub.id)

    wait_then_click_element(browser, HPL.BUTTON_TAG_CANCEL_CREATE, time=3)

    create_tag_input = wait_until_hidden(browser, HPL.INPUT_TAG_CREATE, timeout=3)
    assert not create_tag_input.is_displayed()

    assert_btns_shown_on_cancel_url_tag_input_creator(browser)


def test_cancel_input_create_tag_btn_member(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a UTub member's ability to close the create tag input field.

    GIVEN a user is the UTub owner with the UTub and URL selected that they did not add
    WHEN the user clicks the createURLTag button, then clicks the cancel button
    THEN ensure the createURLTag form is hidden.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id_for_test)

    with app.app_context():
        utub_url_user_did_not_add: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_did_not_create.id,
            Utub_Urls.user_id != user_id_for_test,
        ).first()

    login_user_select_utub_by_id_and_url_by_id(
        app,
        browser,
        user_id_for_test,
        utub_user_did_not_create.id,
        utub_url_user_did_not_add.id,
    )

    open_url_tag_input(browser, utub_url_user_did_not_add.id)

    wait_then_click_element(browser, HPL.BUTTON_TAG_CANCEL_CREATE, time=3)

    create_tag_input = wait_until_hidden(browser, HPL.INPUT_TAG_CREATE, timeout=3)
    assert not create_tag_input.is_displayed()

    assert_btns_shown_on_cancel_url_tag_input_member(browser)


def test_cancel_input_create_tag_key_creator(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a UTub owner's ability to close the create tag input field.

    GIVEN a user is the UTub owner with the UTub and URL selected
    WHEN the user clicks the createURLTag button, then presses the escape key
    THEN ensure the createURLTag form is hidden.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    open_url_tag_input(browser, url_in_utub.id)

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    create_tag_input = wait_until_hidden(browser, HPL.INPUT_TAG_CREATE, timeout=3)
    assert not create_tag_input.is_displayed()

    assert_btns_shown_on_cancel_url_tag_input_creator(browser)


def test_cancel_input_create_tag_key_member(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a UTub member's ability to close the create tag input field.

    GIVEN a user is the UTub owner with the UTub and URL selected that they did not add
    WHEN the user clicks the createURLTag button, then presses the escape key
    THEN ensure the createURLTag form is hidden.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id_for_test)

    with app.app_context():
        utub_url_user_did_not_add: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_did_not_create.id,
            Utub_Urls.user_id != user_id_for_test,
        ).first()

    login_user_select_utub_by_id_and_url_by_id(
        app,
        browser,
        user_id_for_test,
        utub_user_did_not_create.id,
        utub_url_user_did_not_add.id,
    )

    open_url_tag_input(browser, utub_url_user_did_not_add.id)

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    create_tag_input = wait_until_hidden(browser, HPL.INPUT_TAG_CREATE, timeout=3)
    assert not create_tag_input.is_displayed()

    assert_btns_shown_on_cancel_url_tag_input_member(browser)


def test_create_tag_btn(browser: WebDriver, create_test_urls, provide_app: Flask):
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

    # Count badges for increase
    badge_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_BADGES}"
    badge_elems = wait_then_get_elements(browser, badge_selector, time=3)
    assert badge_elems
    assert len(badge_elems) == init_tag_count_on_url + 1
    assert all([badge.is_displayed() for badge in badge_elems])

    badge_text_elems_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_BADGE_NAME_READ}"
    badge_text_elems: list[WebElement] = wait_then_get_elements(
        browser, badge_text_elems_selector, time=3
    )
    assert badge_text_elems
    assert any([elem.text == tag_text for elem in badge_text_elems])

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


def test_create_tag_key(browser: WebDriver, create_test_urls, provide_app: Flask):
    """
    Tests a user's ability to create a fresh tag to a URL.

    GIVEN a user has access to UTubs with URLs
    WHEN the createTag form is populated with a tag value that is not yet present and submitted
    THEN ensure the appropriate tag is applied and displayed
    """
    tag_text = UTS.TEST_TAG_NAME_1
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)
    with app.app_context():
        init_tag_count_on_url: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_utub.id,
        ).count()

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    add_tag_to_url(browser, url_in_utub.id, tag_text)

    # Submit
    browser.switch_to.active_element.send_keys(Keys.ENTER)

    # Wait for POST request
    btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_SUBMIT_CREATE}"
    wait_until_hidden(browser, btn_selector, timeout=3)

    # Count badges for increase
    badge_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_BADGES}"
    badge_elems = wait_then_get_elements(browser, badge_selector, time=3)
    assert badge_elems
    assert len(badge_elems) == init_tag_count_on_url + 1
    assert all([badge.is_displayed() for badge in badge_elems])

    badge_text_elems_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_BADGE_NAME_READ}"
    badge_text_elems = wait_then_get_elements(
        browser, badge_text_elems_selector, time=3
    )
    assert badge_text_elems
    assert any([elem.text == tag_text for elem in badge_text_elems])

    # Confirm Tag Deck counter incremented
    utub_tag = get_tag_in_utub_by_tag_string(app, utub_id, tag_text)
    utub_tag_selector = f'{HPL.TAG_FILTERS}[data-utub-tag-id="{utub_tag.id}"]'
    utub_tag_elem = wait_then_get_element(browser, utub_tag_selector)
    assert utub_tag_elem


def test_create_non_fresh_tag(browser: WebDriver, create_test_urls, provide_app: Flask):
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

    add_tag_to_utub_user_created(
        app=app,
        tag_string=tag_already_in_utub_str,
        utub_id=utub_id,
        user_id=user_id_for_test,
    )

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_id, url_in_utub.id
    )

    badge_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_BADGES}"
    badge_elems = wait_then_get_elements(browser, badge_selector, time=3)
    assert len(badge_elems) == 0

    add_tag_to_url(browser, url_in_utub.id, tag_already_in_utub_str)

    # Submit
    btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_SUBMIT_CREATE}"
    wait_then_click_element(browser, btn_selector, time=3)

    # Wait for POST request
    wait_until_hidden(browser, btn_selector, timeout=3)

    # Count badges for increase
    badge_elems = wait_then_get_elements(browser, badge_selector, time=3)
    assert len(badge_elems) == 1
    assert all([badge.is_displayed() for badge in badge_elems])

    badge_text_elems_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_BADGE_NAME_READ}"
    badge_text_elems: list[WebElement] = wait_then_get_elements(
        browser, badge_text_elems_selector, time=3
    )
    assert any([elem.text == tag_already_in_utub_str for elem in badge_text_elems])


def test_create_tag_rate_limits(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to create a fresh tag to a URL when they are rate limited

    GIVEN a user has access to UTubs with URLs and is rate limited
    WHEN the createTag form is populated with a tag value that is not yet in the UTub
    THEN ensure the 429 error page is shown
    """
    tag_text = UTS.TEST_TAG_NAME_1
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    add_tag_to_url(browser, url_in_utub.id, tag_text)

    # Submit
    btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_SUBMIT_CREATE}"

    add_forced_rate_limit_header(browser)
    wait_then_click_element(browser, btn_selector, time=3)

    assert_on_429_page(browser)


def test_create_existing_tag(browser: WebDriver, create_test_tags, provide_app: Flask):
    """
    Tests the site error response to a user's attempt to create a tag with the same name as another already on the selected URL.

    GIVEN a user has access to UTubs with URLs and tags applied
    WHEN the createTag form is populated with a tag value that is already applied to the selected URL and submitted
    THEN ensure the appropriate error is presented to the user.
    """

    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    existing_tag = get_tag_string_already_on_url_in_utub_and_delete(
        app, utub_user_created.id, url_in_utub.id
    )

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    add_tag_to_url(browser, url_in_utub.id, existing_tag)

    # Submit
    btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_SUBMIT_CREATE}"
    wait_then_click_element(browser, btn_selector, time=3)

    # Wait for POST request
    duplicate_url_tag_selector = f"{HPL.ROW_SELECTED_URL} {HPL.ERROR_TAG_CREATE}"
    duplicate_url_tag_error = wait_then_get_element(
        browser, duplicate_url_tag_selector, time=3
    )
    assert duplicate_url_tag_error is not None
    assert duplicate_url_tag_error.text == TAGS_FAILURE.TAG_ALREADY_ON_URL


def test_create_existing_tag_with_whitespace(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to create a tag with the same name as another already on the selected URL.

    GIVEN a user has access to UTubs with URLs and tags applied
    WHEN the createTag form is populated with a tag value that is already applied to the selected URL and submitted
    THEN ensure the appropriate error is presented to the user.
    """

    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    existing_tag = get_tag_string_already_on_url_in_utub_and_delete(
        app, utub_user_created.id, url_in_utub.id
    )

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    add_tag_to_url(browser, url_in_utub.id, f" {existing_tag} ")

    # Submit
    btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_SUBMIT_CREATE}"
    wait_then_click_element(browser, btn_selector, time=3)

    # Wait for POST request
    duplicate_url_tag_selector = f"{HPL.ROW_SELECTED_URL} {HPL.ERROR_TAG_CREATE}"
    duplicate_url_tag_error = wait_then_get_element(
        browser, duplicate_url_tag_selector, time=3
    )
    assert duplicate_url_tag_error is not None
    assert duplicate_url_tag_error.text == TAGS_FAILURE.TAG_ALREADY_ON_URL


def test_create_sixth_tag(browser: WebDriver, create_test_tags, provide_app: Flask):
    """
    Tests the site error response to a user's attempt to create an additional unique tag once a URL already has the maximum number of tags applied

    GIVEN a user has access to UTubs with URLs and a maximum of tags applied
    WHEN the createTag form is populated and submitted
    THEN ensure the appropriate error is presented to the user.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    add_tag_to_url(browser, url_in_utub.id, UTS.TEST_TAG_NAME_1)

    # Submit
    btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_SUBMIT_CREATE}"
    wait_then_click_element(browser, btn_selector, time=3)

    # Wait for POST request
    duplicate_url_tag_selector = f"{HPL.ROW_SELECTED_URL} {HPL.ERROR_TAG_CREATE}"
    duplicate_url_tag_error = wait_then_get_element(
        browser, duplicate_url_tag_selector, time=3
    )
    assert duplicate_url_tag_error is not None
    assert duplicate_url_tag_error.text == TAGS_FAILURE.FIVE_TAGS_MAX


def test_create_tag_text_length_exceeded(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to create a tag with name that exceeds the character limit.

    GIVEN a user has access to UTubs with URLs
    WHEN the createTag form is populated and submitted with a tag value that exceeds character limits
    THEN ensure the appropriate error is presented to the user.
    """

    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    add_tag_to_url(browser, url_in_utub.id, "a" * (CONSTANTS.TAGS.MAX_TAG_LENGTH + 1))

    create_url_tag_input = wait_then_get_element(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_TAG_CREATE}", time=3
    )
    assert create_url_tag_input is not None
    new_url_tag = create_url_tag_input.get_attribute("value")
    assert new_url_tag is not None
    assert len(new_url_tag) == CONSTANTS.TAGS.MAX_TAG_LENGTH


def test_create_tag_text_sanitized(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to create a tag with name that is sanitized

    GIVEN a user has access to UTubs with URLs
    WHEN the createTag form is populated and submitted with a tag value that is sanitized
    THEN ensure the appropriate error is presented to the user.
    """

    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    add_tag_to_url(browser, url_in_utub.id, '<img src="evl.jpg">')

    # Submit
    btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_SUBMIT_CREATE}"
    wait_then_click_element(browser, btn_selector, time=3)

    sanitized_url_tag_selector = f"{HPL.ROW_SELECTED_URL} {HPL.ERROR_TAG_CREATE}"
    sanitized_url_tag_error = wait_then_get_element(
        browser, sanitized_url_tag_selector, time=3
    )
    assert sanitized_url_tag_error is not None
    assert sanitized_url_tag_error.text == TAGS_FAILURE.INVALID_INPUT


def test_create_tag_text_invalid_csrf_token(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests the site error response to a user's attempt to create a tag with an invalid CSRF token

    GIVEN a user has access to UTubs with URLs
    WHEN the createTag form is populated and submitted with an invalid CSRF token
    THEN ensure the appropriate error is presented to the user.
    """

    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        user: Users = Users.query.get(user_id_for_test)
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    add_tag_to_url(browser, url_in_utub.id, '<img src="evl.jpg">')

    # Submit
    invalidate_csrf_token_on_page(browser)
    btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_SUBMIT_CREATE}"
    wait_then_click_element(browser, btn_selector, time=3)

    assert_visited_403_on_invalid_csrf_and_reload(browser)

    # Page reloads after user clicks button in CSRF 403 error page
    wait_then_get_element(browser, HPL.ROW_SELECTED_URL, time=3)
    assert_login_with_username(browser, user.username)
