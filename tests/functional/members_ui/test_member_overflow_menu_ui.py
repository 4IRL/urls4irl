"""Real-browser acceptance for the Members title-row overflow (three-dot) menu.

Below a 380px title row (measured; see the comment above the container query in
members.css) the member filter and Members gear fold into the menu. The desktop
viewport is 350px wide at 992-1699px and 422px from 1700px."""

from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import OWNER_ID, login_as

pytestmark = [pytest.mark.members_ui, pytest.mark.home_ui]

NARROW_VIEWPORT = {"width": 1280, "height": 900}
WIDE_VIEWPORT = {"width": 1800, "height": 900}
_BUTTONS = "#MemberDeck .button-container button:visible"


def _narrow_login(*, app: Flask, page: Page) -> None:
    page.set_viewport_size(NARROW_VIEWPORT)
    login_as(app=app, page=page, user_id=OWNER_ID)
    expect(page.locator(HPL.BUTTON_MEMBER_OVERFLOW)).to_be_visible()


def _visible_boxes(*, page: Page) -> list[dict]:
    boxes = []
    for button in page.locator(_BUTTONS).all():
        box = button.bounding_box()
        assert box is not None
        box["id"] = button.get_attribute("id")
        boxes.append(box)
    return sorted(boxes, key=lambda box: box["x"])


def test_wide_row_keeps_all_four_buttons_and_no_overflow_button(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the owner on a wide desktop viewport (title row wider than 380px)
    WHEN they view the Members deck
    THEN the filter, invite link, add and gear buttons show and the overflow button does not
    """
    page.set_viewport_size(WIDE_VIEWPORT)
    login_as(app=provide_app, page=page, user_id=OWNER_ID)
    expect(page.locator(HPL.BUTTON_MEMBER_SETTINGS_GEAR)).to_be_visible()
    expect(page.locator(HPL.BUTTON_MEMBER_NAME_FILTER)).to_be_visible()
    expect(page.locator(HPL.BUTTON_MEMBER_OVERFLOW)).to_be_hidden()


@pytest.mark.parametrize("width", [992, 1100, 1280, 1400])
def test_narrow_row_folds_filter_and_gear_into_overflow(
    page: Page, create_test_utubmembers, provide_app: Flask, width: int
):
    """
    GIVEN the owner at a desktop width where the Members row is 350px
    WHEN they view the Members deck
    THEN the filter and gear are hidden, the overflow button shows, and no visible
        button overlaps its neighbor or the deck title
    """
    page.set_viewport_size({"width": width, "height": 900})
    login_as(app=provide_app, page=page, user_id=OWNER_ID)
    expect(page.locator(HPL.BUTTON_MEMBER_OVERFLOW)).to_be_visible()
    expect(page.locator(HPL.BUTTON_MEMBER_NAME_FILTER)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MEMBER_SETTINGS_GEAR)).to_be_hidden()

    boxes = _visible_boxes(page=page)
    assert [box["id"] for box in boxes] == [
        "memberBtnInviteLink",
        "memberBtnCreate",
        "memberBtnOverflow",
    ], boxes
    for left, right in zip(boxes, boxes[1:]):
        assert left["x"] + left["width"] <= right["x"] + 1, (left, right)
    header = page.locator(HPL.HEADER_AND_CARET_MEMBER_DECK).bounding_box()
    assert header is not None
    assert header["x"] + header["width"] <= boxes[0]["x"] + 1, (header, boxes[0])


def test_overflow_menu_opens_with_both_items_and_focuses_first(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the narrow Members row
    WHEN the owner clicks the overflow button
    THEN a menu with the filter and settings items opens, the button reports it,
        and focus is on the first item
    """
    _narrow_login(app=provide_app, page=page)
    page.locator(HPL.BUTTON_MEMBER_OVERFLOW).click()
    expect(page.locator(HPL.MEMBER_OVERFLOW_MENU)).to_be_visible()
    expect(page.locator(HPL.BUTTON_MEMBER_OVERFLOW)).to_have_attribute(
        "aria-expanded", "true"
    )
    expect(page.locator(HPL.MEMBER_OVERFLOW_FILTER)).to_be_focused()
    expect(page.locator(HPL.MEMBER_OVERFLOW_SETTINGS)).to_be_visible()


def test_overflow_menu_keyboard_navigation_and_escape(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the narrow Members row
    WHEN the owner opens the menu with ArrowDown, moves with the arrows and presses Escape
    THEN focus moves between the items and Escape closes the menu back to the button
    """
    _narrow_login(app=provide_app, page=page)
    page.locator(HPL.BUTTON_MEMBER_OVERFLOW).focus()
    page.keyboard.press("ArrowDown")
    expect(page.locator(HPL.MEMBER_OVERFLOW_FILTER)).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(page.locator(HPL.MEMBER_OVERFLOW_SETTINGS)).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(page.locator(HPL.MEMBER_OVERFLOW_FILTER)).to_be_focused()
    page.keyboard.press("End")
    expect(page.locator(HPL.MEMBER_OVERFLOW_SETTINGS)).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(HPL.MEMBER_OVERFLOW_MENU)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MEMBER_OVERFLOW)).to_be_focused()
    expect(page.locator(HPL.BUTTON_MEMBER_OVERFLOW)).to_have_attribute(
        "aria-expanded", "false"
    )


def test_overflow_menu_closes_on_outside_click(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an open overflow menu
    WHEN the owner clicks elsewhere on the page
    THEN the menu closes
    """
    _narrow_login(app=provide_app, page=page)
    page.locator(HPL.BUTTON_MEMBER_OVERFLOW).click()
    expect(page.locator(HPL.MEMBER_OVERFLOW_MENU)).to_be_visible()
    page.locator(HPL.HEADER_MEMBER_DECK).click()
    expect(page.locator(HPL.MEMBER_OVERFLOW_MENU)).to_be_hidden()


def test_overflow_filter_item_opens_the_member_filter(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the narrow Members row with the overflow menu open
    WHEN the owner picks "Filter members"
    THEN the menu closes and the member filter opens
    """
    _narrow_login(app=provide_app, page=page)
    page.locator(HPL.BUTTON_MEMBER_OVERFLOW).click()
    page.locator(HPL.MEMBER_OVERFLOW_FILTER).click()
    expect(page.locator(HPL.MEMBER_OVERFLOW_MENU)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MEMBER_NAME_FILTER_CLOSE)).to_be_visible()


def test_overflow_settings_item_opens_the_members_gear_popover(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the narrow Members row with the overflow menu open
    WHEN the owner picks "Members settings"
    THEN the menu closes and the settings popover opens next to the overflow button
    """
    _narrow_login(app=provide_app, page=page)
    page.locator(HPL.BUTTON_MEMBER_OVERFLOW).click()
    page.locator(HPL.MEMBER_OVERFLOW_SETTINGS).click()
    expect(page.locator(HPL.MEMBER_OVERFLOW_MENU)).to_be_hidden()
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_visible()
    popover = page.locator(HPL.PANEL_SETTINGS_POPOVER).bounding_box()
    overflow = page.locator(HPL.BUTTON_MEMBER_OVERFLOW).bounding_box()
    assert popover is not None and overflow is not None
    assert popover["x"] >= 0 and popover["x"] + popover["width"] <= 1280, popover
    assert popover["y"] >= overflow["y"], (popover, overflow)


def test_invite_modal_opens_from_narrow_row_and_returns_focus(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the narrow Members row
    WHEN the owner opens the invite link modal and closes it with Escape
    THEN the modal is centered over the page and focus returns to the invite trigger
    """
    _narrow_login(app=provide_app, page=page)
    page.locator(HPL.BUTTON_MEMBER_INVITE_LINK).click()
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_visible()
    expect(page.locator(f"{HPL.INVITE_LINK_MODAL} :focus")).to_have_count(1)
    dialog = page.locator(HPL.INVITE_LINK_MODAL_DIALOG).bounding_box()
    assert dialog is not None
    center = dialog["x"] + dialog["width"] / 2
    assert abs(center - NARROW_VIEWPORT["width"] / 2) <= 2, dialog
    page.keyboard.press("Escape")
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_be_focused()
