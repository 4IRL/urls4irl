"""Phone-viewport acceptance for the Members invite link panel: no horizontal
overflow, 44px touch targets and unclipped header buttons."""

from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.home_ui.test_member_permissions_mobile_ui import (
    go_to_members_deck,
    open_members_deck_as,
)
from tests.functional.home_ui.test_panel_settings_mobile_ui import (
    _go_to_deck_via_navbar,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import OWNER_ID
from tests.utils_for_test import add_invite_link

pytestmark = [pytest.mark.home_ui, pytest.mark.members_ui, pytest.mark.mobile_ui]

_MIN_TOUCH_TARGET_PX = 44


def test_panel_fits_phone_width_with_touch_targets(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the owner on the phone Members deck with a live invite link
    WHEN they open the invite link panel
    THEN the page has no horizontal overflow and the trigger and copy button are
        at least 44px tall
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    add_invite_link(app, utub_id, OWNER_ID, max_uses=10)
    open_members_deck_as(app=app, page=page, user_id=OWNER_ID)

    trigger = page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)
    trigger.tap()
    expect(page.locator(HPL.MEMBER_INVITE_PANEL)).to_be_visible()

    for locator in (
        trigger,
        page.locator(HPL.INVITE_LINK_COPY_BTN),
        page.locator("#inviteLinkNewBtn"),
        page.locator("#inviteLinkRevokeBtn"),
        page.locator(HPL.INVITE_LINK_EXPIRES_SELECT),
        page.locator(HPL.INVITE_LINK_USES_SELECT),
        page.locator(HPL.INVITE_LINK_URL_INPUT),
    ):
        box = locator.bounding_box()
        assert box is not None
        assert box["height"] >= _MIN_TOUCH_TARGET_PX, box
        assert box["width"] >= _MIN_TOUCH_TARGET_PX, box

    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - window.innerWidth"
    )
    assert overflow <= 0, overflow


def test_gear_sheet_closes_panel(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the owner on the phone Members deck with the invite link panel open
    WHEN they tap the Members gear
    THEN the gear sheet opens and the panel is closed
    """
    page = page_mobile_portrait
    open_members_deck_as(app=provide_app, page=page, user_id=OWNER_ID)
    page.locator(HPL.BUTTON_MEMBER_INVITE_LINK).tap()
    expect(page.locator(HPL.MEMBER_INVITE_PANEL)).to_be_visible()

    page.locator(HPL.BUTTON_MEMBER_SETTINGS_GEAR).tap()
    expect(page.locator(HPL.PANEL_SETTINGS_SHEET)).to_be_visible()
    expect(page.locator(HPL.MEMBER_INVITE_PANEL)).to_be_hidden()


def test_deck_switch_closes_panel(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the owner on the phone Members deck with the invite link panel open
    WHEN they switch to the UTubs deck and back
    THEN the panel stays closed after returning
    """
    page = page_mobile_portrait
    open_members_deck_as(app=provide_app, page=page, user_id=OWNER_ID)
    page.locator(HPL.BUTTON_MEMBER_INVITE_LINK).tap()
    expect(page.locator(HPL.MEMBER_INVITE_PANEL)).to_be_visible()

    _go_to_deck_via_navbar(page, HPL.NAVBAR_UTUB_DECK)
    go_to_members_deck(page=page)
    expect(page.locator(HPL.MEMBER_INVITE_PANEL)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_have_attribute(
        "aria-expanded", "false"
    )


@pytest.mark.parametrize("width", [360, 390])
def test_header_buttons_not_clipped_or_overlapping(
    page_mobile_portrait: Page,
    create_test_utubmembers,
    provide_app: Flask,
    width: int,
):
    """
    GIVEN the owner on the phone Members deck at a narrow width
    WHEN the header shows its buttons
    THEN each visible button lies inside the viewport and none overlap
    """
    page = page_mobile_portrait
    open_members_deck_as(app=provide_app, page=page, user_id=OWNER_ID)
    page.set_viewport_size({"width": width, "height": 800})

    boxes = []
    for button in page.locator("#MemberDeck .button-container button:visible").all():
        box = button.bounding_box()
        assert box is not None
        assert box["x"] >= 0 and box["x"] + box["width"] <= width, box
        box["id"] = button.get_attribute("id")
        boxes.append(box)
    assert {box["id"] for box in boxes} >= {
        "memberNameFilterBtn",
        "memberBtnInviteLink",
        "memberBtnCreate",
        "memberBtnSettings",
    }, boxes
    boxes.sort(key=lambda box: box["x"])
    # The gear's 44px hit area deliberately overlaps its neighbor by its
    # negative touch margin (panel-settings.css), so only the other buttons
    # are held to a no-overlap check; every button is still inside the viewport.
    plain = [box for box in boxes if box["id"] != "memberBtnSettings"]
    for left, right in zip(plain, plain[1:]):
        assert left["x"] + left["width"] <= right["x"] + 1, (left, right)
