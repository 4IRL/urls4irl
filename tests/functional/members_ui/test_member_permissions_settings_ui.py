import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.models.users import Users
from backend.utils.strings.user_strs import MEMBERS_PERMISSIONS_SECTION_TITLE
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    open_members_gear,
    seed_co_creator_in_utub,
)
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_name
from tests.functional.playwright_utils import wait_until_visible_css_selector

pytestmark = pytest.mark.members_ui

_PERMISSION_SWITCHES = (
    HPL.MEMBERS_PERMISSIONS_CO_OWNERS_REMOVE_SWITCH,
    HPL.MEMBERS_PERMISSIONS_MEMBERS_ADD_SWITCH,
)


def _is_settings_patch(response) -> bool:
    return response.request.method == "PATCH" and "settings" in response.url


def test_owner_sees_both_switches_off_and_enabled(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub
    WHEN they open the Members gear
    THEN the Member permissions section shows two enabled switches, both off
    """
    app = provide_app
    user_id = 1
    utub = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub.name
    )

    open_members_gear(page=page)
    for selector in _PERMISSION_SWITCHES:
        switch = page.locator(selector)
        expect(switch).to_be_visible()
        expect(switch).to_have_attribute("aria-checked", "false")
        expect(switch).not_to_have_attribute("aria-disabled", "true")
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_contain_text(
        MEMBERS_PERMISSIONS_SECTION_TITLE
    )


def test_owner_flip_saves_and_survives_reload(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub
    WHEN they turn on "Members can add members" and reload the page
    THEN the PATCH succeeds and the switch is still on after the reload
    """
    app = provide_app
    user_id = 1
    utub = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub.name
    )

    open_members_gear(page=page)
    switch = page.locator(HPL.MEMBERS_PERMISSIONS_MEMBERS_ADD_SWITCH)
    with page.expect_response(_is_settings_patch) as response_info:
        switch.click()
    assert response_info.value.status == 200
    expect(switch).to_have_attribute("aria-checked", "true")

    page.reload()
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_MEMBER_SETTINGS_GEAR
    )
    open_members_gear(page=page)
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_MEMBERS_ADD_SWITCH)).to_have_attribute(
        "aria-checked", "true"
    )
    expect(
        page.locator(HPL.MEMBERS_PERMISSIONS_CO_OWNERS_REMOVE_SWITCH)
    ).to_have_attribute("aria-checked", "false")


def test_co_owner_sees_switches_read_only_and_click_changes_nothing(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user is a co-owner of a UTub they did not create
    WHEN they open the Members gear and click a switch
    THEN both switches are aria-disabled and unchanged
    """
    app = provide_app
    user_id = 1
    utub = get_utub_this_user_did_not_create(app, user_id)
    with app.app_context():
        username = Users.query.get(user_id).username
    seed_co_creator_in_utub(app=app, utub_id=utub.id, username=username)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub.name
    )

    wait_until_visible_css_selector(page=page, css_selector=HPL.MEMBER_ROW_ROLE_ICON)
    open_members_gear(page=page)
    for selector in _PERMISSION_SWITCHES:
        switch = page.locator(selector)
        expect(switch).to_be_visible()
        expect(switch).to_have_attribute("aria-disabled", "true")
        # force: Playwright treats aria-disabled as "not enabled" and would wait.
        expect(switch).to_have_attribute(
            "aria-describedby", re.compile(r"panelSettingsNote-members-permissions")
        )
        # Still focusable; Space must change nothing.
        switch.focus()
        expect(switch).to_be_focused()
        switch.click(force=True)
        page.keyboard.press("Space")
        expect(switch).to_have_attribute("aria-checked", "false")


def test_plain_member_does_not_see_permissions_section(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user is a plain member of a UTub they did not create
    WHEN they open the Members gear
    THEN no Member permissions switches are rendered
    """
    app = provide_app
    user_id = 1
    utub = get_utub_this_user_did_not_create(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub.name
    )

    open_members_gear(page=page)
    for selector in _PERMISSION_SWITCHES:
        expect(page.locator(selector)).to_have_count(0)
