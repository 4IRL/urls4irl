from flask import Flask
import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from src.models.users import Users
from tests.functional.assert_utils import (
    assert_login_with_username,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.db_utils import (
    count_urls_with_tag_applied_by_tag_id,
    get_utub_this_user_created,
    get_url_in_utub,
    get_tag_on_url_in_utub,
)
from tests.functional.login_utils import login_user_select_utub_by_id_and_url_by_id
from tests.functional.tags_ui.selenium_utils import (
    get_tag_badge_selector_on_selected_url_by_tag_id,
    get_delete_tag_button_on_hover,
)
from tests.functional.selenium_utils import (
    get_selected_url,
    invalidate_csrf_token_on_page,
    open_update_url_title,
    wait_for_animation_to_end,
    wait_for_element_to_be_removed,
    wait_then_click_element,
)
from locators import HomePageLocators as HPL

pytestmark = pytest.mark.tags_ui


def test_get_delete_tag_button_on_hover(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests a user's ability to open the tag delete button when hovering on a tag in a URL

    GIVEN a user has access to UTubs, URLs, and tags
    WHEN user hovers over tag badge
    THEN ensure the deleteTag button is displayed
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(url_tag.id)
    delete_tag_button = get_delete_tag_button_on_hover(browser, tag_badge_selector)

    assert delete_tag_button.is_displayed()


def test_hide_delete_tag_button_after_hover(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests a user's ability to hide the tag delete button when moving cursor away from a tag in a URL

    GIVEN a user has access to UTubs, URLs, and tags
    WHEN user hovers over tag badge and then moves cursor to another element
    THEN ensure the deleteTag button is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(url_tag.id)
    delete_tag_button = get_delete_tag_button_on_hover(browser, tag_badge_selector)

    assert delete_tag_button.is_displayed()

    url_title_selector = f"{HPL.ROW_SELECTED_URL} {HPL.URL_TITLE_READ}"
    url_title = browser.find_element(By.CSS_SELECTOR, url_title_selector)
    actions = ActionChains(browser)
    actions.move_to_element(url_title).pause(3).perform()

    delete_tag_btn_selector = f"{tag_badge_selector} > {HPL.BUTTON_TAG_DELETE}"
    wait_for_animation_to_end(browser, delete_tag_btn_selector)
    assert not browser.find_element(
        By.CSS_SELECTOR, delete_tag_btn_selector
    ).is_displayed()


def test_delete_tag(browser: WebDriver, create_test_tags, provide_app: Flask):
    """
    Tests a user's ability to delete tags from a URL

    GIVEN a user has access to UTubs with URLs and tags applied
    WHEN user clicks the deleteTag button
    THEN ensure the tag is removed from the URL
    """

    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)
    url_id = url_in_utub.id
    url_tag = get_tag_on_url_in_utub(app, utub_id, url_id)
    tag_id = url_tag.utub_tag_id

    with app.app_context():
        init_tag_count_in_utub: int = count_urls_with_tag_applied_by_tag_id(app, tag_id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_id, url_id
    )

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(url_id)
    delete_tag_button = get_delete_tag_button_on_hover(browser, tag_badge_selector)

    tag_badge = browser.find_element(By.CSS_SELECTOR, tag_badge_selector)
    delete_tag_button.click()

    # Wait for DELETE request
    wait_for_element_to_be_removed(browser, tag_badge, timeout=3)

    # Assert tag no longer exists in URL
    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, tag_badge_selector)

    # Assert URL count in Tag Deck is decremented
    with app.app_context():
        updated_tag_count_in_utub: int = count_urls_with_tag_applied_by_tag_id(
            app, tag_id
        )
        assert updated_tag_count_in_utub == init_tag_count_in_utub - 1


# Sad Path Tests
def test_no_get_delete_tag_button_on_hover_update_url_title(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests the limitation on users, preventing deletion of tags while updating URL titles

    GIVEN a user has selected a URL they added to a UTub
    WHEN user clicks the editURLTitle button, and subsequently hovers over a tag
    THEN ensure the deleteTag button is not displayed
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    open_update_url_title(browser, get_selected_url(browser))

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(url_tag.id)
    delete_tag_button = get_delete_tag_button_on_hover(browser, tag_badge_selector)
    assert not delete_tag_button.is_displayed()


def test_no_get_delete_tag_button_on_hover_update_url_string(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests the limitation on users, preventing deletion of tags while updating URL strings

    GIVEN a user has selected a URL they added to a UTub
    WHEN user clicks the editURLTitle button, and subsequently hovers over a tag
    THEN ensure the deleteTag button is not displayed
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    edit_url_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}"
    wait_then_click_element(browser, edit_url_selector, time=3)

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(url_tag.id)
    delete_tag_button = get_delete_tag_button_on_hover(browser, tag_badge_selector)
    assert not delete_tag_button.is_displayed()


def test_no_get_delete_tag_button_on_hover_add_tag(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests the limitation on users, preventing deletion of tags while adding tags

    GIVEN a user has selected a URL they added to a UTub
    WHEN user clicks the addTag button, and subsequently hovers over a tag
    THEN ensure the deleteTag button is not displayed
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    add_tag_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_CREATE}"
    wait_then_click_element(browser, add_tag_selector, time=3)

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(url_tag.id)
    delete_tag_button = get_delete_tag_button_on_hover(browser, tag_badge_selector)
    assert not delete_tag_button.is_displayed()


def test_delete_tag_invalid_csrf(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests a user's ability to delete tags from a URL with an invalid csrf token

    GIVEN a user has access to UTubs with URLs and tags applied
    WHEN user clicks the deleteTag button with an invalid csrf token
    THEN ensure U4I responds with a proper error message
    """

    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        user: Users = Users.query.get(user_id_for_test)

    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, user_id_for_test, utub_user_created.id, url_in_utub.id
    )

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(url_tag.id)
    delete_tag_button = get_delete_tag_button_on_hover(browser, tag_badge_selector)

    invalidate_csrf_token_on_page(browser)
    delete_tag_button.click()

    assert_visited_403_on_invalid_csrf_and_reload(browser)
    assert_login_with_username(browser, user.username)

    # Assert tag not in DOM as return to page has all UTubs unselected
    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, tag_badge_selector)
