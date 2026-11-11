"""Phone-viewport acceptance for the Members "Member permissions" settings:
the owner's switches in the bottom sheet, the read-only and hidden role views,
the co-owner kebab's touch target and the refusal notice in the Members panel."""

from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.models.utub_members import Member_Role
from backend.utils.strings.user_strs import (
    CO_OWNER_REMOVE_NOT_ALLOWED,
    MEMBER_ADD_NOT_ALLOWED,
)
from backend.utils.strings.utub_strs import PANEL_SETTINGS_OWNER_ONLY
from tests.functional.db_utils import (
    get_utub_this_user_created,
    isolate_user_from_viewer,
    remove_user_from_utub,
    set_member_role_in_utub,
    set_utub_settings,
)
from tests.functional.home_ui.test_panel_settings_mobile_ui import (
    _MIN_TOUCH_TARGET_PX,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    CO_OWNER_ID,
    OUTSIDER_ID,
    OUTSIDER_NAME,
    OWNER_ID,
    TARGET_ID,
    click_add_member_submit,
    co_owner_kebab,
    element_box,
    expect_notice,
    is_settings_patch,
    open_add_member_combobox,
    open_co_owner_menu_and_click_remove,
    open_members_gear,
    seed_policy,
    stage_outsider_username,
    submit_confirm_modal,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    go_to_deck_via_navbar,
    wait_for_modal_ready,
    wait_until_hidden,
    wait_until_visible_css_selector,
)

pytestmark = [pytest.mark.home_ui, pytest.mark.members_ui, pytest.mark.mobile_ui]

_SWITCHES = [
    pytest.param(
        HPL.MEMBERS_PERMISSIONS_SHEET_CO_OWNERS_REMOVE_SWITCH,
        id="co_owners_can_remove",
    ),
    pytest.param(
        HPL.MEMBERS_PERMISSIONS_SHEET_MEMBERS_ADD_SWITCH, id="members_can_add"
    ),
]


def open_members_deck_as(
    *, app: Flask, page: Page, user_id: int, role: Member_Role | None = None
) -> int:
    """Log ``user_id`` in on the owner's UTub, go to the Members deck and wait
    for the member rows. Returns the UTub id."""
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    if role is not None:
        set_member_role_in_utub(app, user_id, utub_id, role)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id, utub_id=utub_id
    )
    go_to_members_deck(page=page)
    return utub_id


def wait_for_members_after_reload(*, page: Page) -> None:
    """A reload on the phone keeps the selected UTub and the Members panel, so
    only the member rows need waiting for (the navbar has no Members entry then)."""
    wait_until_visible_css_selector(page=page, css_selector=HPL.MEMBER_ROW_ROLE_ICON)


def go_to_members_deck(*, page: Page) -> None:
    go_to_deck_via_navbar(page=page, navbar_selector=HPL.NAVBAR_MEMBER_DECK)
    wait_until_visible_css_selector(page=page, css_selector=HPL.MEMBER_ROW_ROLE_ICON)


@pytest.mark.parametrize("sheet_switch", _SWITCHES)
def test_owner_toggles_switch_in_sheet_with_touch_target_and_reload_keeps_it(
    page_mobile_portrait: Page,
    create_test_utubmembers,
    provide_app: Flask,
    sheet_switch: str,
):
    """
    GIVEN the owner on the phone Members deck
    WHEN they tap a permission switch in the gear sheet and reload
    THEN the switch is at least 44px in both dimensions, the PATCH succeeds and
        the switch is still on after the reload
    """
    page = page_mobile_portrait
    open_members_deck_as(app=provide_app, page=page, user_id=OWNER_ID)

    open_members_gear(page=page, mobile=True)
    switch = page.locator(sheet_switch)
    expect(switch).to_have_attribute("aria-checked", "false")
    box = element_box(locator=switch)
    assert box["width"] >= _MIN_TOUCH_TARGET_PX, box
    assert box["height"] >= _MIN_TOUCH_TARGET_PX, box

    with page.expect_response(is_settings_patch) as response_info:
        switch.tap()
    assert response_info.value.status == 200
    expect(switch).to_have_attribute("aria-checked", "true")

    page.reload()
    wait_for_members_after_reload(page=page)
    open_members_gear(page=page, mobile=True)
    expect(page.locator(sheet_switch)).to_have_attribute("aria-checked", "true")


def test_co_owner_sheet_is_read_only_with_owner_only_note(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a co-owner on the phone Members deck
    WHEN they open the gear sheet
    THEN both switches are read-only and the owner-only note is shown
    """
    page = page_mobile_portrait
    open_members_deck_as(
        app=provide_app,
        page=page,
        user_id=CO_OWNER_ID,
        role=Member_Role.CO_CREATOR,
    )

    open_members_gear(page=page, mobile=True)
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_NOTE)).to_have_text(
        PANEL_SETTINGS_OWNER_ONLY
    )
    for sheet_switch in (
        HPL.MEMBERS_PERMISSIONS_SHEET_CO_OWNERS_REMOVE_SWITCH,
        HPL.MEMBERS_PERMISSIONS_SHEET_MEMBERS_ADD_SWITCH,
    ):
        expect(page.locator(sheet_switch)).to_have_attribute("aria-disabled", "true")


def test_plain_member_sheet_has_no_permissions_section(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a plain member on the phone Members deck
    WHEN they open the gear sheet
    THEN there is no Member permissions section
    """
    page = page_mobile_portrait
    open_members_deck_as(app=provide_app, page=page, user_id=CO_OWNER_ID)

    open_members_gear(page=page, mobile=True)
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_SECTION)).to_have_count(0)


def test_co_owner_kebab_is_a_touch_target_when_on_and_hidden_when_off(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a co-owner on a coarse-pointer phone
    WHEN removal is off, and then on
    THEN the kebab's computed display is none, and when on its box is at least 44px
    """
    app = provide_app
    page = page_mobile_portrait
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    open_members_deck_as(
        app=app, page=page, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR
    )
    kebab = co_owner_kebab(page=page, member_id=TARGET_ID)
    expect(kebab).to_have_css("display", "none")

    seed_policy(app=app, utub_id=utub_id, co_owners_can_remove=True)
    page.reload()
    wait_for_members_after_reload(page=page)
    expect(kebab).to_be_visible()
    box = element_box(locator=kebab)
    assert box["width"] >= _MIN_TOUCH_TARGET_PX, box
    assert box["height"] >= _MIN_TOUCH_TARGET_PX, box


def test_remove_refusal_notice_is_visible_in_phone_members_panel(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a co-owner loaded the phone Members panel with removal on, then the owner
        turned it off
    WHEN they confirm Remove on a plain member
    THEN the refusal notice is visible in the panel with its reason text
    """
    app = provide_app
    page = page_mobile_portrait
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    seed_policy(app=app, utub_id=utub_id, co_owners_can_remove=True)
    open_members_deck_as(
        app=app, page=page, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR
    )
    expect(co_owner_kebab(page=page, member_id=TARGET_ID)).to_be_visible()

    set_utub_settings(app, utub_id, None)
    open_co_owner_menu_and_click_remove(page=page, member_id=TARGET_ID)
    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    submit_confirm_modal(page=page)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)

    expect_notice(page=page, text=CO_OWNER_REMOVE_NOT_ALLOWED)


def test_add_refusal_notice_is_visible_in_phone_members_panel(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a plain member staged a chip on the phone with adding on, then the
        owner turned adding off
    WHEN they submit
    THEN the refusal notice is visible in the Members panel with its reason text
    """
    app = provide_app
    page = page_mobile_portrait
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    seed_policy(app=app, utub_id=utub_id, members_can_add=True)
    remove_user_from_utub(app, OUTSIDER_ID, utub_id)
    isolate_user_from_viewer(app, user_id=OUTSIDER_ID, viewer_id=CO_OWNER_ID)
    open_members_deck_as(app=app, page=page, user_id=CO_OWNER_ID)

    open_add_member_combobox(page=page)
    stage_outsider_username(page=page, username=OUTSIDER_NAME)
    seed_policy(app=app, utub_id=utub_id, members_can_add=False)
    click_add_member_submit(page=page)

    expect_notice(page=page, text=MEMBER_ADD_NOT_ALLOWED)
