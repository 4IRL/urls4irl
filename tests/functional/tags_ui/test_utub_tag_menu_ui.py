from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.assert_utils import (
    assert_not_visible_css_selector,
    assert_utub_selected,
    assert_visible_css_selector,
)
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import login_user_and_select_utub_by_utubid
from tests.functional.members_ui.selenium_utils import leave_utub_as_member
from tests.functional.selenium_utils import (
    select_utub_by_id,
    wait_then_click_element,
)
from tests.functional.tags_ui.selenium_utils import click_open_update_utub_tags_btn
from tests.functional.utubs_ui.selenium_utils import delete_utub_as_creator

pytestmark = pytest.mark.tags_ui


def test_utub_tag_menu_not_shown_when_no_utub_tags(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests that the UTub Tag Menu button is hidden when no tags are available.

    GIVEN a user in a UTub with no UTub tags
    WHEN user selects the UTub
    THEN ensure the UTub Tag Menu button is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_did_not_create.id
    )
    assert_utub_selected(browser, app, utub_user_did_not_create.id)
    assert_not_visible_css_selector(
        browser, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN
    )


def test_open_utub_tag_menu(browser: WebDriver, create_test_tags, provide_app: Flask):
    app = provide_app
    user_id_for_test = 1
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_did_not_create.id
    )
    assert_utub_selected(browser, app, utub_user_did_not_create.id)
    click_open_update_utub_tags_btn(browser)


def test_open_utub_tag_menu_enter_key(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_did_not_create.id
    )
    assert_utub_selected(browser, app, utub_user_did_not_create.id)

    browser.find_element(By.CSS_SELECTOR, HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN).send_keys(
        Keys.ENTER
    )

    assert_visible_css_selector(browser, css_selector=HPL.UTUB_TAG_MENU_WRAP)
    assert_visible_css_selector(
        browser, css_selector=HPL.WRAP_BUTTON_UPDATE_TAG_ALL_CLOSE
    )
    assert_not_visible_css_selector(browser, css_selector=HPL.UTUB_TAG_COUNT_WRAP)
    assert_not_visible_css_selector(
        browser, css_selector=HPL.WRAP_BUTTONS_CREATE_UNFILTER_UTUB_TAGS
    )
    assert_not_visible_css_selector(
        browser, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN
    )
    assert_visible_css_selector(browser, css_selector=HPL.BUTTON_UTUB_TAG_DELETE)
    assert_visible_css_selector(
        browser, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_CLOSE
    )


def test_close_utub_tag_menu_on_click(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests that the UTub Tag Menu is hidden and the Add/Unfilter buttons are shown when the User clicks on the return button.

    GIVEN a user in a UTub with the UTub Tag Menu open
    WHEN user presses the Close Update UTub Tag Menu
    THEN ensure the UTub Tag Menu is hidden and add/unfilter UTub Tag buttons are shown
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_did_not_create.id
    )
    assert_utub_selected(browser, app, utub_user_did_not_create.id)

    click_open_update_utub_tags_btn(browser)

    wait_then_click_element(browser, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_CLOSE)
    assert_visible_css_selector(
        browser, css_selector=HPL.WRAP_BUTTONS_CREATE_UNFILTER_UTUB_TAGS
    )
    assert_visible_css_selector(browser, css_selector=HPL.UTUB_TAG_COUNT_WRAP)
    assert_not_visible_css_selector(browser, css_selector=HPL.UTUB_TAG_MENU_WRAP)
    assert_not_visible_css_selector(
        browser, css_selector=HPL.WRAP_BUTTON_UPDATE_TAG_ALL_CLOSE
    )
    assert_not_visible_css_selector(browser, css_selector=HPL.BUTTON_UTUB_TAG_DELETE)


def test_close_utub_tag_menu_on_enter_key(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests that the UTub Tag Menu is hidden and the Add/Unfilter buttons are shown when the User clicks on the return button.

    GIVEN a user in a UTub with the UTub Tag Menu open
    WHEN user presses the Close Update UTub Tag Menu
    THEN ensure the UTub Tag Menu is hidden and add/unfilter UTub Tag buttons are shown
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_did_not_create.id
    )
    assert_utub_selected(browser, app, utub_user_did_not_create.id)

    click_open_update_utub_tags_btn(browser)

    browser.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_UPDATE_TAG_BTN_ALL_CLOSE
    ).send_keys(Keys.ENTER)

    assert_visible_css_selector(
        browser, css_selector=HPL.WRAP_BUTTONS_CREATE_UNFILTER_UTUB_TAGS
    )
    assert_visible_css_selector(browser, css_selector=HPL.UTUB_TAG_COUNT_WRAP)
    assert_not_visible_css_selector(browser, css_selector=HPL.UTUB_TAG_MENU_WRAP)
    assert_not_visible_css_selector(
        browser, css_selector=HPL.WRAP_BUTTON_UPDATE_TAG_ALL_CLOSE
    )
    assert_not_visible_css_selector(browser, css_selector=HPL.BUTTON_UTUB_TAG_DELETE)


def test_update_tag_menu_btn_hidden_on_utub_select(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests that the UTub Tag Menu is hidden and the Add/Unfilter buttons are shown when the User selects another UTub.

    GIVEN a user in a UTub with the UTub Tag Menu open
    WHEN user selects another UTub
    THEN ensure the UTub Tag Menu is hidden and add/unfilter UTub Tag buttons are shown
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id_for_test)
    utub_user_did_create = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_did_not_create.id
    )
    assert_utub_selected(browser, app, utub_user_did_not_create.id)

    click_open_update_utub_tags_btn(browser)

    select_utub_by_id(browser, utub_user_did_create.id)

    assert_visible_css_selector(
        browser, css_selector=HPL.WRAP_BUTTONS_CREATE_UNFILTER_UTUB_TAGS
    )
    assert_visible_css_selector(browser, css_selector=HPL.UTUB_TAG_COUNT_WRAP)
    assert_not_visible_css_selector(browser, css_selector=HPL.UTUB_TAG_MENU_WRAP)
    assert_not_visible_css_selector(
        browser, css_selector=HPL.WRAP_BUTTON_UPDATE_TAG_ALL_CLOSE
    )
    assert_not_visible_css_selector(browser, css_selector=HPL.BUTTON_UTUB_TAG_DELETE)


def test_update_tag_menu_btn_hidden_on_utub_member_leave(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests that the UTub Tag menus are hidden when a UTub is left as a member.

    GIVEN a user in a UTub with the UTub Tag Menu open
    WHEN user leaves the UTub
    THEN ensure the UTub Tag Menu is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_did_not_create.id
    )
    assert_utub_selected(browser, app, utub_user_did_not_create.id)

    click_open_update_utub_tags_btn(browser)

    leave_utub_as_member(browser, utub_user_did_not_create)

    assert_not_visible_css_selector(
        browser, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN
    )
    assert_not_visible_css_selector(
        browser, css_selector=HPL.WRAP_BUTTON_UPDATE_TAG_ALL_CLOSE
    )


def test_update_tag_menu_btn_hidden_on_utub_delete(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests that the UTub Tag menus are hidden when a UTub is deleted as the creator.

    GIVEN a user in a UTub with the UTub Tag Menu open
    WHEN user deletes the UTub
    THEN ensure the UTub Tag Menu is hidden
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app, browser, user_id_for_test, utub_user_created.id
    )
    assert_utub_selected(browser, app, utub_user_created.id)

    click_open_update_utub_tags_btn(browser)

    delete_utub_as_creator(browser, utub_user_created)

    assert_not_visible_css_selector(
        browser, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN
    )
    assert_not_visible_css_selector(
        browser, css_selector=HPL.WRAP_BUTTON_UPDATE_TAG_ALL_CLOSE
    )


# TODO: Test that the menu is hidden on last tag delete
# TODO: Test delete with invalid CSRF token
