"""Phone-viewport acceptance for the Members invite link panel: no horizontal
overflow, 44px touch targets and unclipped header buttons."""

from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.home_ui.test_member_permissions_mobile_ui import (
    open_members_deck_as,
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
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_visible()

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


def test_modal_is_a_full_width_bottom_sheet_that_closes_on_escape(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the owner on the phone Members deck
    WHEN they open the invite link modal
    THEN it is a full-width sheet resting on the bottom edge, with no horizontal
        overflow, and Escape closes it and returns focus to the trigger
    """
    page = page_mobile_portrait
    open_members_deck_as(app=provide_app, page=page, user_id=OWNER_ID)
    page.locator(HPL.BUTTON_MEMBER_INVITE_LINK).tap()
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_visible()
    # Fully shown (the fade slides the sheet in): focus lands in it only then.
    expect(page.locator(f"{HPL.INVITE_LINK_MODAL} :focus")).to_have_count(1)

    viewport = page.viewport_size
    assert viewport is not None
    content = page.locator(f"{HPL.INVITE_LINK_MODAL} .modal-content").bounding_box()
    assert content is not None
    assert content["x"] <= 1 and content["width"] >= viewport["width"] - 2, content
    assert abs(content["y"] + content["height"] - viewport["height"]) <= 2, content

    page.keyboard.press("Escape")
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_be_focused()


def test_close_button_tap_target_is_at_least_44px(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the invite link modal open on a phone
    WHEN the close button is measured
    THEN it is at least 44px tall and wide, and tapping it closes the modal
    """
    page = page_mobile_portrait
    open_members_deck_as(app=provide_app, page=page, user_id=OWNER_ID)
    page.locator(HPL.BUTTON_MEMBER_INVITE_LINK).tap()
    close = page.locator(HPL.INVITE_LINK_MODAL_CLOSE)
    expect(close).to_be_visible()
    expect(page.locator(f"{HPL.INVITE_LINK_MODAL} :focus")).to_have_count(1)
    box = close.bounding_box()
    assert box is not None
    assert (
        box["height"] >= _MIN_TOUCH_TARGET_PX and box["width"] >= _MIN_TOUCH_TARGET_PX
    )
    close.tap()
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_hidden()


@pytest.mark.parametrize(
    ("width", "expected"),
    [
        (
            360,
            ["memberBtnInviteLink", "memberBtnCreate", "memberBtnOverflow"],
        ),
        (
            390,
            [
                "memberNameFilterBtn",
                "memberBtnInviteLink",
                "memberBtnCreate",
                "memberBtnSettings",
            ],
        ),
    ],
)
def test_header_buttons_not_clipped_or_overlapping(
    page_mobile_portrait: Page,
    create_test_utubmembers,
    provide_app: Flask,
    width: int,
    expected: list[str],
):
    """
    GIVEN the owner on the phone Members deck at a narrow width
    WHEN the header shows its buttons
    THEN each visible button lies inside the viewport and none overlap; the
        filter and gear fold into the overflow menu below the 380px row
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
    boxes.sort(key=lambda box: box["x"])
    assert [box["id"] for box in boxes] == expected, boxes
    # The gear's 44px hit area deliberately overlaps its neighbor by its
    # negative touch margin (panel-settings.css), so only the other buttons
    # are held to a no-overlap check; every button is still inside the viewport.
    plain = [box for box in boxes if box["id"] != "memberBtnSettings"]
    for left, right in zip(plain, plain[1:]):
        assert left["x"] + left["width"] <= right["x"] + 1, (left, right)


def test_overflow_menu_items_are_44px_and_open_the_gear_sheet(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the owner on a 360px phone Members deck, where the gear is folded away
    WHEN they open the overflow menu and tap "Members settings"
    THEN both items are at least 44px tall and the gear bottom sheet opens
    """
    page = page_mobile_portrait
    open_members_deck_as(app=provide_app, page=page, user_id=OWNER_ID)
    page.set_viewport_size({"width": 360, "height": 800})
    page.locator(HPL.BUTTON_MEMBER_OVERFLOW).tap()
    expect(page.locator(HPL.MEMBER_OVERFLOW_MENU)).to_be_visible()
    for selector in (HPL.MEMBER_OVERFLOW_FILTER, HPL.MEMBER_OVERFLOW_SETTINGS):
        box = page.locator(selector).bounding_box()
        assert box is not None
        assert box["height"] >= _MIN_TOUCH_TARGET_PX, box
    page.locator(HPL.MEMBER_OVERFLOW_SETTINGS).tap()
    expect(page.locator(HPL.PANEL_SETTINGS_SHEET)).to_be_visible()
