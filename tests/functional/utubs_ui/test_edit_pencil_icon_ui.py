from flask import Flask
import pytest
from playwright.sync_api import Page

from backend.models.utubs import Utubs
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid,
)
from tests.functional.playwright_utils import (
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_utub_name_appears,
)
from tests.functional.utubs_ui.playwright_utils import (
    open_update_utub_name_input,
)

pytestmark = pytest.mark.utubs_ui


def test_pencil_icon_visible_for_creator_on_name_hover(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a creator selects their own UTub
    WHEN the user hovers over the UTub name area
    THEN the pencil icon for the name header should be visible
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    name_wrap = wait_then_get_element(page=page, css_selector=HPL.WRAP_UTUB_NAME_UPDATE)
    assert name_wrap is not None

    name_wrap.hover()

    assert_visible_css_selector(page=page, css_selector=HPL.PENCIL_ICON_NAME)


def test_pencil_icon_visible_for_creator_on_description_hover(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a creator selects their own UTub
    WHEN the user hovers over the UTub description area
    THEN the pencil icon for the description header should be visible
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    desc_wrap = wait_then_get_element(
        page=page, css_selector=HPL.WRAP_UTUB_DESCRIPTION_UPDATE
    )
    assert desc_wrap is not None

    desc_wrap.hover()

    assert_visible_css_selector(page=page, css_selector=HPL.PENCIL_ICON_DESCRIPTION)


def test_pencil_icon_not_visible_for_member(
    page: Page, create_test_utubmembers, provide_app: Flask
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

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub.id
    )
    wait_until_utub_name_appears(page=page, utub_name=utub.name)

    assert_not_visible_css_selector(page=page, css_selector=HPL.PENCIL_ICON_NAME)
    assert_not_visible_css_selector(page=page, css_selector=HPL.PENCIL_ICON_DESCRIPTION)


def test_clicking_pencil_icon_opens_name_edit(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a creator selects their own UTub
    WHEN the user clicks the pencil icon next to the UTub name
    THEN the name edit input should open
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    name_wrap = wait_then_get_element(page=page, css_selector=HPL.WRAP_UTUB_NAME_UPDATE)
    name_wrap.hover()

    wait_then_click_element(page=page, css_selector=HPL.PENCIL_ICON_NAME)

    utub_name_update_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE
    )
    assert utub_name_update_input is not None


def test_clicking_pencil_icon_opens_description_edit(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a creator selects their own UTub
    WHEN the user clicks the pencil icon next to the UTub description
    THEN the description edit input should open
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    desc_wrap = wait_then_get_element(
        page=page, css_selector=HPL.WRAP_UTUB_DESCRIPTION_UPDATE
    )
    desc_wrap.hover()

    wait_then_click_element(page=page, css_selector=HPL.PENCIL_ICON_DESCRIPTION)

    utub_desc_update_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )
    assert utub_desc_update_input is not None


def test_pencil_icon_hidden_during_name_edit(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a creator opens the name edit form
    WHEN the edit form is visible
    THEN the name pencil icon should not be visible
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    open_update_utub_name_input(page=page)
    wait_then_get_element(page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE)

    assert_not_visible_css_selector(page=page, css_selector=HPL.PENCIL_ICON_NAME)


def test_pencil_icon_restored_after_name_edit_cancel(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a creator opens and then cancels the name edit form
    WHEN the cancel button is clicked
    THEN the name pencil icon should be visible again on hover
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    open_update_utub_name_input(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_NAME_CANCEL_UPDATE)

    name_wrap = wait_then_get_element(page=page, css_selector=HPL.WRAP_UTUB_NAME_UPDATE)
    name_wrap.hover()

    assert_visible_css_selector(page=page, css_selector=HPL.PENCIL_ICON_NAME)


def test_pencil_icon_hidden_after_switching_to_non_owned_utub(
    page: Page, create_test_utubmembers, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    name_wrap = wait_then_get_element(page=page, css_selector=HPL.WRAP_UTUB_NAME_UPDATE)
    name_wrap.hover()
    assert_visible_css_selector(page=page, css_selector=HPL.PENCIL_ICON_NAME)

    select_utub_by_name(page=page, utub_name=utub_not_owned.name)
    wait_until_utub_name_appears(page=page, utub_name=utub_not_owned.name)

    assert_not_visible_css_selector(page=page, css_selector=HPL.PENCIL_ICON_NAME)
    assert_not_visible_css_selector(page=page, css_selector=HPL.PENCIL_ICON_DESCRIPTION)
