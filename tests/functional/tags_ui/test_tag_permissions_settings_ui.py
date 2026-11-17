"""Playwright UI tests for the shared "Tag permissions" section (Tags gear)."""

from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, Response, expect

from backend.utils.strings.tag_strs import (
    TAGS_SETTINGS_DELETE_REQUIRES_TAG,
    TAGS_SETTINGS_MEMBERS_CAN_DELETE_OFF,
    TAGS_SETTINGS_MEMBERS_CAN_TAG_ON,
    TAGS_SETTINGS_SECTION_TITLE,
    TAGS_SETTINGS_TAG_OFF_DELETE_FORCED,
)
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_utubid
from tests.functional.playwright_utils import wait_then_click_element

pytestmark = pytest.mark.tags_ui

USER_ID_FOR_TEST = 1


def _is_settings_patch(response: Response) -> bool:
    return response.request.method == "PATCH" and "settings" in response.url


def _open_tags_gear(*, page: Page) -> None:
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_TAG_SETTINGS_GEAR)
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_visible()
    expect(page.locator(HPL.TAGS_PERMISSIONS_MEMBERS_CAN_TAG_SWITCH)).to_be_visible()


def test_owner_sees_both_switches_on_and_enabled(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub
    WHEN they open the Tags gear
    THEN the Tag permissions section shows two enabled switches, both on
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )

    _open_tags_gear(page=page)
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_contain_text(
        TAGS_SETTINGS_SECTION_TITLE
    )
    for selector in (
        HPL.TAGS_PERMISSIONS_MEMBERS_CAN_TAG_SWITCH,
        HPL.TAGS_PERMISSIONS_MEMBERS_CAN_DELETE_SWITCH,
    ):
        switch = page.locator(selector)
        expect(switch).to_have_attribute("aria-checked", "true")
        expect(switch).not_to_have_attribute("aria-disabled", "true")


def test_tagging_off_forces_delete_off_and_announces(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub
    WHEN they turn "Members can tag" off, then on again
    THEN Delete shows off, disabled and explained, the live region announces the
         combined notice, and Delete returns to its stored value with the plain notice
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )

    _open_tags_gear(page=page)
    tag_switch = page.locator(HPL.TAGS_PERMISSIONS_MEMBERS_CAN_TAG_SWITCH)
    delete_switch = page.locator(HPL.TAGS_PERMISSIONS_MEMBERS_CAN_DELETE_SWITCH)

    with page.expect_response(_is_settings_patch) as response_info:
        tag_switch.click()
    assert response_info.value.status == 200
    expect(tag_switch).to_have_attribute("aria-checked", "false")
    expect(delete_switch).to_have_attribute("aria-checked", "false")
    expect(delete_switch).to_have_attribute("aria-disabled", "true")
    expect(page.locator(HPL.TAGS_PERMISSIONS_MEMBERS_CAN_DELETE_HINT)).to_have_text(
        TAGS_SETTINGS_DELETE_REQUIRES_TAG
    )
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        TAGS_SETTINGS_TAG_OFF_DELETE_FORCED
    )

    with page.expect_response(_is_settings_patch) as response_info:
        tag_switch.click()
    assert response_info.value.status == 200
    expect(delete_switch).to_have_attribute("aria-checked", "true")
    expect(delete_switch).not_to_have_attribute("aria-disabled", "true")
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        TAGS_SETTINGS_MEMBERS_CAN_TAG_ON
    )


def test_delete_switch_toggles_from_keyboard_and_announces(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub
    WHEN they focus "Members can delete tags" and press Space
    THEN only that key is saved, the switch turns off and the notice is announced
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )

    _open_tags_gear(page=page)
    delete_switch = page.locator(HPL.TAGS_PERMISSIONS_MEMBERS_CAN_DELETE_SWITCH)
    delete_switch.focus()
    with page.expect_response(_is_settings_patch) as response_info:
        page.keyboard.press("Space")
    assert response_info.value.status == 200
    expect(delete_switch).to_have_attribute("aria-checked", "false")
    expect(page.locator(HPL.TAGS_PERMISSIONS_MEMBERS_CAN_TAG_SWITCH)).to_have_attribute(
        "aria-checked", "true"
    )
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        TAGS_SETTINGS_MEMBERS_CAN_DELETE_OFF
    )


def test_plain_member_sees_switches_read_only(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN a user is a plain member of a UTub they did not create
    WHEN they open the Tags gear and click a switch
    THEN both switches are aria-disabled and unchanged
    """
    app = provide_app
    utub = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )

    _open_tags_gear(page=page)
    for selector in (
        HPL.TAGS_PERMISSIONS_MEMBERS_CAN_TAG_SWITCH,
        HPL.TAGS_PERMISSIONS_MEMBERS_CAN_DELETE_SWITCH,
    ):
        switch = page.locator(selector)
        expect(switch).to_have_attribute("aria-disabled", "true")
        # force: Playwright treats aria-disabled as "not enabled" and would wait.
        switch.click(force=True)
        expect(switch).to_have_attribute("aria-checked", "true")
