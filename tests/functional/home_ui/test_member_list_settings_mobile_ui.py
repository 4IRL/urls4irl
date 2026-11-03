from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.models.user_preferences import MemberSort
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.home_ui.test_member_list_settings_ui import (
    ORDER_BY_SORT,
    OWNER_ID,
    SORT_UI,
    expect_deck_order,
    seed_members,
    sort_notice,
)
from tests.functional.home_ui.test_panel_settings_mobile_ui import (
    _MIN_TOUCH_TARGET_PX,
    _SHEET_OPEN_CLASS_RE,
    _close_sheet_via_close_button,
    _expect_sheet_closed,
    _go_to_deck_via_navbar,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import wait_for_css_transitions_to_finish

pytestmark = [pytest.mark.home_ui, pytest.mark.members_ui, pytest.mark.mobile_ui]


def test_sheet_select_is_a_touch_target_and_deck_is_reordered_on_close(
    page_mobile_portrait: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a phone viewport on the Members deck of the owner's UTub
    WHEN the user opens the Members gear, picks Role then name, and closes the sheet
    THEN the select is at least 44px tall, the pick is saved and announced, the
        sheet closes with focus back on the gear, and the deck is in role order
    """
    app = provide_app
    page = page_mobile_portrait
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    seed_members(app=app, utub_id=utub_id)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=OWNER_ID, utub_id=utub_id
    )
    _go_to_deck_via_navbar(page, HPL.NAVBAR_MEMBER_DECK)
    expect_deck_order(page=page, order=ORDER_BY_SORT[MemberSort.NAME_AZ])

    gear = page.locator(HPL.BUTTON_MEMBER_SETTINGS_GEAR)
    expect(gear).to_be_visible()
    gear.tap()
    expect(page.locator(HPL.PANEL_SETTINGS_SHEET)).to_have_class(_SHEET_OPEN_CLASS_RE)
    select = page.locator(HPL.MEMBERS_SETTINGS_SHEET_SORT_SELECT)
    expect(select).to_be_visible()
    # The sheet slides in: a box read mid-transition is fractional.
    wait_for_css_transitions_to_finish(locator=page.locator(HPL.PANEL_SETTINGS_SHEET))
    box = select.bounding_box()
    assert box is not None
    assert box["height"] >= _MIN_TOUCH_TARGET_PX, box

    sort = MemberSort.ROLE_THEN_NAME
    select.select_option(label=SORT_UI[sort][0])
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        sort_notice(sort=sort)
    )
    _close_sheet_via_close_button(page)
    _expect_sheet_closed(page)
    expect(gear).to_be_focused()

    expect_deck_order(page=page, order=ORDER_BY_SORT[sort])
