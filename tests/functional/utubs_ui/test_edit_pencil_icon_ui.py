from flask import Flask
import pytest
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webdriver import WebDriver

from backend.models.utubs import Utubs
from locators import HomePageLocators as HPL
from tests.functional.assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid,
)
from tests.functional.selenium_utils import (
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_utub_name_appears,
)
from tests.functional.utubs_ui.selenium_utils import (
    open_update_utub_name_input,
)

pytestmark = pytest.mark.utubs_ui


def test_pencil_icon_visible_for_creator_on_name_hover(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a creator selects their own UTub
    WHEN the user hovers over the UTub name area
    THEN the pencil icon for the name header should be visible
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    name_wrap = wait_then_get_element(browser, HPL.WRAP_UTUB_NAME_UPDATE)
    assert name_wrap is not None

    ActionChains(browser).move_to_element(name_wrap).perform()

    assert_visible_css_selector(browser, HPL.PENCIL_ICON_NAME, time=3)


def test_pencil_icon_visible_for_creator_on_description_hover(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a creator selects their own UTub
    WHEN the user hovers over the UTub description area
    THEN the pencil icon for the description header should be visible
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    desc_wrap = wait_then_get_element(browser, HPL.WRAP_UTUB_DESCRIPTION_UPDATE)
    assert desc_wrap is not None

    ActionChains(browser).move_to_element(desc_wrap).perform()

    assert_visible_css_selector(browser, HPL.PENCIL_ICON_DESCRIPTION, time=3)


def test_pencil_icon_not_visible_for_member(
    browser: WebDriver, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a member (non-creator) selects a UTub they don't own
    WHEN the page loads
    THEN neither pencil icon should be visible
    """
    app = provide_app
    user_id = 1
    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.utub_creator != user_id).first()

    login_user_and_select_utub_by_utubid(app, browser, user_id, utub.id)
    wait_until_utub_name_appears(browser, utub.name)

    assert_not_visible_css_selector(browser, HPL.PENCIL_ICON_NAME, time=3)
    assert_not_visible_css_selector(browser, HPL.PENCIL_ICON_DESCRIPTION, time=3)


def test_clicking_pencil_icon_opens_name_edit(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a creator selects their own UTub
    WHEN the user clicks the pencil icon next to the UTub name
    THEN the name edit input should open
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    name_wrap = wait_then_get_element(browser, HPL.WRAP_UTUB_NAME_UPDATE)
    ActionChains(browser).move_to_element(name_wrap).perform()

    wait_then_click_element(browser, HPL.PENCIL_ICON_NAME)

    utub_name_update_input = wait_then_get_element(browser, HPL.INPUT_UTUB_NAME_UPDATE)
    assert utub_name_update_input is not None
    assert utub_name_update_input.is_displayed()


def test_clicking_pencil_icon_opens_description_edit(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a creator selects their own UTub
    WHEN the user clicks the pencil icon next to the UTub description
    THEN the description edit input should open
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    desc_wrap = wait_then_get_element(browser, HPL.WRAP_UTUB_DESCRIPTION_UPDATE)
    ActionChains(browser).move_to_element(desc_wrap).perform()

    wait_then_click_element(browser, HPL.PENCIL_ICON_DESCRIPTION)

    utub_desc_update_input = wait_then_get_element(
        browser, HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )
    assert utub_desc_update_input is not None
    assert utub_desc_update_input.is_displayed()


def test_pencil_icon_hidden_during_name_edit(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a creator opens the name edit form
    WHEN the edit form is visible
    THEN the name pencil icon should not be visible
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    open_update_utub_name_input(browser)
    wait_then_get_element(browser, HPL.INPUT_UTUB_NAME_UPDATE)

    assert_not_visible_css_selector(browser, HPL.PENCIL_ICON_NAME, time=3)


def test_pencil_icon_restored_after_name_edit_cancel(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a creator opens and then cancels the name edit form
    WHEN the cancel button is clicked
    THEN the name pencil icon should be visible again on hover
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    open_update_utub_name_input(browser)
    wait_then_click_element(browser, HPL.BUTTON_UTUB_NAME_CANCEL_UPDATE)

    name_wrap = wait_then_get_element(browser, HPL.WRAP_UTUB_NAME_UPDATE)
    ActionChains(browser).move_to_element(name_wrap).perform()

    assert_visible_css_selector(browser, HPL.PENCIL_ICON_NAME, time=3)


def test_pencil_icon_hidden_after_switching_to_non_owned_utub(
    browser: WebDriver, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a creator selects their own UTub and sees pencil icons
    WHEN they switch to a UTub they don't own
    THEN pencil icons should no longer be visible
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    with app.app_context():
        utub_not_owned: Utubs = Utubs.query.filter(
            Utubs.utub_creator != user_id
        ).first()

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    name_wrap = wait_then_get_element(browser, HPL.WRAP_UTUB_NAME_UPDATE)
    ActionChains(browser).move_to_element(name_wrap).perform()
    assert_visible_css_selector(browser, HPL.PENCIL_ICON_NAME, time=3)

    select_utub_by_name(browser, utub_not_owned.name)
    wait_until_utub_name_appears(browser, utub_not_owned.name)

    assert_not_visible_css_selector(browser, HPL.PENCIL_ICON_NAME, time=3)
    assert_not_visible_css_selector(browser, HPL.PENCIL_ICON_DESCRIPTION, time=3)
