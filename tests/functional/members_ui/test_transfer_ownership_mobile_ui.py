from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.utils.strings.user_strs import (
    MEMBERS_TRANSFER_SECTION_TITLE,
    TRANSFER_OWNER_ACTION,
)
from tests.functional.db_utils import (
    get_other_member_in_utub,
    get_utub_this_user_created,
)
from tests.functional.home_ui.test_panel_settings_mobile_ui import (
    _MIN_TOUCH_TARGET_PX,
    _expect_sheet_closed,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    open_members_gear,
    open_transfer_ownership_picker,
    stage_transfer_confirm_view,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    go_to_deck_via_navbar,
    wait_then_click_element,
    wait_until_hidden,
)

pytestmark = [pytest.mark.members_ui, pytest.mark.mobile_ui]

OWNER_ID = 1


def _login_to_members_deck(*, app: Flask, page: Page) -> int:
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=OWNER_ID, utub_id=utub_id
    )
    go_to_deck_via_navbar(page=page, navbar_selector=HPL.NAVBAR_MEMBER_DECK)
    return utub_id


def test_sheet_offers_a_touch_sized_transfer_action_that_opens_the_modal(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a phone viewport on the Members deck of a UTub the user owns
    WHEN they open the Members sheet and tap Transfer ownership
    THEN the action is at least 44px tall and named, the sheet closes, the
        transfer modal opens, and Cancel returns focus to the Members gear
    """
    app = provide_app
    page = page_mobile_portrait
    _login_to_members_deck(app=app, page=page)

    open_members_gear(page=page, mobile=True)
    action = page.locator(HPL.MEMBER_BTN_TRANSFER_OWNER)
    expect(action).to_be_visible()
    expect(action).to_have_text(TRANSFER_OWNER_ACTION)
    heading = page.locator(HPL.MEMBERS_SETTINGS_TRANSFER_HEADING)
    expect(heading).to_be_visible()
    expect(heading).to_have_text(MEMBERS_TRANSFER_SECTION_TITLE)
    box = action.bounding_box()
    assert box is not None
    assert box["height"] >= _MIN_TOUCH_TARGET_PX, box

    page.keyboard.press("Escape")
    _expect_sheet_closed(page)

    open_transfer_ownership_picker(page=page, mobile=True)
    _expect_sheet_closed(page)
    expect(page.locator(HPL.TRANSFER_OWNER_MODAL)).to_be_visible()

    wait_then_click_element(page=page, css_selector=HPL.TRANSFER_OWNER_CANCEL)
    wait_until_hidden(page=page, css_selector=HPL.TRANSFER_OWNER_MODAL)
    expect(page.locator(HPL.BUTTON_MEMBER_SETTINGS_GEAR)).to_be_focused()


def test_full_transfer_from_the_sheet_completes(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a phone viewport on the Members deck of a UTub the user owns
    WHEN they transfer ownership to another member through the sheet action
    THEN the modal closes, the member becomes owner and the acting user is a
        co-owner whose Members sheet no longer offers the action
    """
    app = provide_app
    page = page_mobile_portrait
    utub_id = _login_to_members_deck(app=app, page=page)
    other_member = get_other_member_in_utub(app, utub_id, OWNER_ID)
    with app.app_context():
        new_owner_id = other_member.id

    open_transfer_ownership_picker(page=page, mobile=True)
    stage_transfer_confirm_view(page=page, member_id=new_owner_id)
    page.locator(HPL.TRANSFER_OWNER_SUBMIT).tap()
    wait_until_hidden(page=page, css_selector=HPL.TRANSFER_OWNER_MODAL)

    # The phone layout lands back on the URL deck after the transfer reload.
    go_to_deck_via_navbar(page=page, navbar_selector=HPL.NAVBAR_MEMBER_DECK)
    expect(
        page.locator(
            f'{HPL.BADGES_MEMBERS}[memberid="{new_owner_id}"] svg.bi-diamond-fill'
        )
    ).to_be_visible()

    open_members_gear(page=page, mobile=True)
    expect(page.locator(HPL.MEMBER_BTN_TRANSFER_OWNER)).to_be_hidden()
    expect(page.locator(HPL.MEMBERS_SETTINGS_TRANSFER_HEADING)).to_be_hidden()
