import re

import pytest
from flask import Flask
from playwright.sync_api import Page, Request, expect

from backend.models.users import Users
from backend.models.utub_members import Member_Role
from backend.utils.strings.user_strs import (
    MEMBERS_PERMISSIONS_CHANGE_NOT_APPLIED,
    MEMBERS_PERMISSIONS_INVITE_CREATORS_DESC_OWNER_ONLY,
    MEMBERS_PERMISSIONS_INVITE_CREATORS_NOTICE_OWNER_ONLY,
    MEMBERS_PERMISSIONS_INVITE_CREATORS_REVOKED_OWNER_ONLY,
    MEMBERS_PERMISSIONS_INVITE_CREATORS_WARN_OWNER_ONLY,
    MEMBERS_PERMISSIONS_NOT_APPLIED_YET,
    MEMBERS_PERMISSIONS_SECTION_TITLE,
)
from backend.utils.strings.utub_strs import (
    PANEL_SETTINGS_OWNER_ONLY,
    PANEL_SETTINGS_SAVE_FAILED,
    PANEL_SETTINGS_SAVED,
)
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
    set_member_role_in_utub,
)
from tests.functional.home_ui.test_member_permissions_mobile_ui import (
    open_members_deck_as,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    CO_OWNER_ID,
    OWNER_ID,
    element_box,
    fail_settings_patch,
    is_invite_link_revoked_in_db,
    is_settings_patch,
    is_settings_patch_request,
    login_as,
    open_members_gear,
    seed_co_creator_in_utub,
)
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_name
from tests.functional.playwright_utils import (
    wait_for_css_transitions_to_finish,
    wait_until_visible_css_selector,
)
from tests.utils_for_test import add_invite_link

pytestmark = pytest.mark.members_ui

_MIN_TOUCH_TARGET_PX = 44
_MIN_SELECT_FONT_PX = 16
_TOUCH_SCROLL_PX = 60
_STAGED_ANNOUNCEMENT = (
    f"{MEMBERS_PERMISSIONS_INVITE_CREATORS_WARN_OWNER_ONLY} "
    f"{MEMBERS_PERMISSIONS_NOT_APPLIED_YET}"
)
_SAVE_FAILED_ANNOUNCEMENT = (
    f"{MEMBERS_PERMISSIONS_SECTION_TITLE}: {PANEL_SETTINGS_SAVE_FAILED}"
)

_PERMISSION_SWITCHES = (
    HPL.MEMBERS_PERMISSIONS_CO_OWNERS_REMOVE_SWITCH,
    HPL.MEMBERS_PERMISSIONS_MEMBERS_ADD_SWITCH,
)


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
    with page.expect_response(is_settings_patch) as response_info:
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


# ---------------------------------------------------------------------------
# "Who can create invite links": staging, Apply, discard and failure paths
# ---------------------------------------------------------------------------


def _record_settings_patches(page: Page) -> list[Request]:
    """Every settings PATCH request the page sends from now on (a request counter,
    so a "no PATCH went out" claim is read from the wire, not inferred)."""
    seen: list[Request] = []

    def _on_request(request: Request) -> None:
        if is_settings_patch_request(request):
            seen.append(request)

    page.on("request", _on_request)
    return seen


def _seed_co_owner_link(*, app: Flask) -> tuple[int, int]:
    """Make user 2 a co-owner of the owner's UTub and seed a live link they made.
    Returns ``(utub_id, invite_link_id)``."""
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    set_member_role_in_utub(app, CO_OWNER_ID, utub_id, Member_Role.CO_CREATOR)
    return utub_id, add_invite_link(app, utub_id, CO_OWNER_ID)


def _open_owner_gear_with_co_owner_link(*, app: Flask, page: Page) -> int:
    """Owner on the desktop Members gear with a live co-owner link. Returns the
    link id."""
    _, link_id = _seed_co_owner_link(app=app)
    login_as(app=app, page=page, user_id=OWNER_ID)
    open_members_gear(page=page)
    return link_id


def _stage_owner_only(*, page: Page) -> None:
    """Pick "Owner only" (a tightening, so it is staged) with focus on the select,
    and wait until the staged warning has been announced. That announcement is
    scheduled with the same debounce an autosave would use, so once it has
    landed any (wrongly) debounced save would already have been sent."""
    select = page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_SELECT)
    select.focus()
    expect(select).to_be_focused()
    select.select_option("owner_only")
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_WARNING)).to_have_text(
        MEMBERS_PERMISSIONS_INVITE_CREATORS_WARN_OWNER_ONLY
    )
    expect(
        page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_NOT_APPLIED)
    ).to_have_text(MEMBERS_PERMISSIONS_NOT_APPLIED_YET)
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_APPLY)).to_be_visible()
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_have_text(
        _STAGED_ANNOUNCEMENT
    )


def _expect_staging_gone_and_stored_value(*, page: Page) -> None:
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_APPLY)).to_have_count(0)
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_WARNING)).to_have_count(
        0
    )
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_SELECT)).to_have_value(
        "owner_and_co_owners"
    )


@pytest.mark.parametrize("apply_with", ["keyboard", "pointer"])
def test_owner_only_is_staged_until_apply_then_revokes_the_co_owner_link(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
    apply_with: str,
):
    """
    GIVEN the owner with a live co-owner link and the gear open
    WHEN they pick "Owner only" and then press Apply (Tab then Enter, or a click)
    THEN nothing is sent and the link stays live until Apply; after Apply focus is
        on the select, the saved text and the live region carry the revoked
        sentence, the link is revoked in the DB and a reload shows the neutral
        settled description
    """
    app = provide_app
    link_id = _open_owner_gear_with_co_owner_link(app=app, page=page)
    patches = _record_settings_patches(page)
    select = page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_SELECT)
    apply = page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_APPLY)

    _stage_owner_only(page=page)
    assert patches == []
    assert not is_invite_link_revoked_in_db(app=app, invite_link_id=link_id)

    with page.expect_response(is_settings_patch) as response_info:
        if apply_with == "keyboard":
            # Tab from the select reaches Apply: the real-browser focus move
            # between the pair must not discard the staged choice.
            page.keyboard.press("Tab")
            expect(apply).to_be_focused()
            page.keyboard.press("Enter")
        else:
            apply.click()
    assert response_info.value.status == 200

    expect(apply).to_have_count(0)
    expect(select).to_be_focused()
    expect(select).to_have_value("owner_only")
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_STATUS)).to_have_text(
        PANEL_SETTINGS_SAVED
    )
    announcement = page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)
    expect(announcement).to_contain_text(
        MEMBERS_PERMISSIONS_INVITE_CREATORS_NOTICE_OWNER_ONLY
    )
    expect(announcement).to_contain_text(
        MEMBERS_PERMISSIONS_INVITE_CREATORS_REVOKED_OWNER_ONLY
    )
    assert len(patches) == 1
    assert is_invite_link_revoked_in_db(app=app, invite_link_id=link_id)

    page.reload()
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_MEMBER_SETTINGS_GEAR
    )
    open_members_gear(page=page)
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_SELECT)).to_have_value(
        "owner_only"
    )
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_DESC)).to_have_text(
        MEMBERS_PERMISSIONS_INVITE_CREATORS_DESC_OWNER_ONLY
    )
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_WARNING)).to_have_count(
        0
    )


def test_moving_focus_away_discards_the_staged_choice(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a staged "Owner only" choice
    WHEN focus moves to another control without Apply
    THEN the choice is discarded with "Change not applied.", nothing was sent and
        the link stays live
    """
    app = provide_app
    link_id = _open_owner_gear_with_co_owner_link(app=app, page=page)
    patches = _record_settings_patches(page)
    _stage_owner_only(page=page)

    page.locator(HPL.MEMBERS_PERMISSIONS_MEMBERS_ADD_SWITCH).focus()

    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_have_text(
        MEMBERS_PERMISSIONS_CHANGE_NOT_APPLIED
    )
    _expect_staging_gone_and_stored_value(page=page)
    assert patches == []
    assert not is_invite_link_revoked_in_db(app=app, invite_link_id=link_id)


def test_escape_discards_only_then_a_second_escape_closes_the_popover(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a staged "Owner only" choice with focus on the select
    WHEN the owner presses Escape twice
    THEN the first discards only (gear still open, "Change not applied.", focus on
        the select) and the second closes the gear; the link stays live
    """
    app = provide_app
    link_id = _open_owner_gear_with_co_owner_link(app=app, page=page)
    patches = _record_settings_patches(page)
    _stage_owner_only(page=page)

    page.keyboard.press("Escape")

    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_have_text(
        MEMBERS_PERMISSIONS_CHANGE_NOT_APPLIED
    )
    _expect_staging_gone_and_stored_value(page=page)
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_visible()
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_SELECT)).to_be_focused()

    page.keyboard.press("Escape")
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_hidden()
    assert patches == []
    assert not is_invite_link_revoked_in_db(app=app, invite_link_id=link_id)


def test_failed_apply_reverts_the_select_and_leaves_the_link_alone(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a staged "Owner only" choice and a settings PATCH that fails with a 500
    WHEN the owner presses Apply
    THEN the select shows the stored value with focus on it, the live region reads
        the save-failed text without "Change not applied." and the link is
        untouched in the DB
    """
    app = provide_app
    link_id = _open_owner_gear_with_co_owner_link(app=app, page=page)
    fail_settings_patch(page=page)
    _stage_owner_only(page=page)

    with page.expect_response(is_settings_patch) as response_info:
        page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_APPLY).click()
    assert response_info.value.status == 500

    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_have_text(
        _SAVE_FAILED_ANNOUNCEMENT
    )
    _expect_staging_gone_and_stored_value(page=page)
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_SELECT)).to_be_focused()
    assert not is_invite_link_revoked_in_db(app=app, invite_link_id=link_id)


def test_another_rows_failed_save_clears_the_staged_choice(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a staged "Owner only" choice and a settings PATCH that fails with a 500
    WHEN another row's switch is flipped (without moving focus off the pair)
    THEN the staging is cleared, the select shows the stored value, the live region
        reads the save-failed text joined with "Change not applied." and the link
        is untouched in the DB
    """
    app = provide_app
    link_id = _open_owner_gear_with_co_owner_link(app=app, page=page)
    fail_settings_patch(page=page)
    _stage_owner_only(page=page)

    # dispatch_event: a real click would first move focus to the switch, which
    # discards the staged choice before the save can fail.
    with page.expect_response(is_settings_patch) as response_info:
        page.locator(HPL.MEMBERS_PERMISSIONS_MEMBERS_ADD_SWITCH).dispatch_event("click")
    assert response_info.value.status == 500

    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_have_text(
        f"{_SAVE_FAILED_ANNOUNCEMENT}. {MEMBERS_PERMISSIONS_CHANGE_NOT_APPLIED}"
    )
    _expect_staging_gone_and_stored_value(page=page)
    assert not is_invite_link_revoked_in_db(app=app, invite_link_id=link_id)


def test_co_owner_select_is_read_only_and_a_change_reverts(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a co-owner with the gear open
    WHEN they try to pick "Owner only"
    THEN the select reverts to the stored value, nothing is staged or sent, and the
        owner-only note is shown
    """
    app = provide_app
    login_as(app=app, page=page, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR)
    open_members_gear(page=page)
    patches = _record_settings_patches(page)
    select = page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_SELECT)
    expect(select).to_have_attribute("aria-disabled", "true")
    expect(page.locator(HPL.URLS_SETTINGS_READ_ONLY_NOTE)).to_contain_text(
        PANEL_SETTINGS_OWNER_ONLY
    )

    # select_option refuses aria-disabled controls even with force, so drive the
    # change the way a browser would: set the value, then fire its change event.
    select.evaluate(
        """element => {
            element.value = 'owner_only';
            element.dispatchEvent(new Event('change', { bubbles: true }));
        }"""
    )

    expect(select).to_have_value("owner_and_co_owners")
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_APPLY)).to_have_count(0)
    assert patches == []


# ---------------------------------------------------------------------------
# Phone sheet
# ---------------------------------------------------------------------------


def _open_owner_sheet_with_co_owner_link(*, app: Flask, page: Page) -> int:
    """Owner on the phone Members sheet (420px) with a live co-owner link."""
    _, link_id = _seed_co_owner_link(app=app)
    open_members_deck_as(app=app, page=page, user_id=OWNER_ID)
    open_members_gear(page=page, mobile=True)
    return link_id


@pytest.mark.mobile_ui
def test_phone_sheet_shows_both_rows_with_touch_sized_controls(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the owner on a 420px phone
    WHEN they open the Members sheet
    THEN the creators select and the previews switch are shown with 44px hit
        areas and the select's computed font size is at least 16px
    """
    page = page_mobile_portrait
    _open_owner_sheet_with_co_owner_link(app=provide_app, page=page)

    select = page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_SELECT)
    switch = page.locator(HPL.MEMBERS_PERMISSIONS_CO_OWNERS_PREVIEW_SWITCH)
    expect(select).to_be_visible()
    expect(switch).to_be_visible()
    select_box = element_box(locator=select)
    switch_box = element_box(locator=switch)
    assert select_box["height"] >= _MIN_TOUCH_TARGET_PX, select_box
    assert switch_box["height"] >= _MIN_TOUCH_TARGET_PX, switch_box
    assert switch_box["width"] >= _MIN_TOUCH_TARGET_PX, switch_box
    font_px = select.evaluate(
        "element => parseFloat(getComputedStyle(element).fontSize)"
    )
    assert font_px >= _MIN_SELECT_FONT_PX, font_px
    select_computed = select.evaluate(
        """element => {
            const style = getComputedStyle(element);
            return {
                minHeight: parseFloat(style.minHeight) || 0,
                height: parseFloat(style.height) || 0,
            };
        }"""
    )
    assert (
        max(select_computed["minHeight"], select_computed["height"])
        >= _MIN_TOUCH_TARGET_PX
    ), select_computed
    switch_computed = switch.evaluate(
        """element => {
            const style = getComputedStyle(element);
            return {
                width: parseFloat(style.width) || 0,
                height: parseFloat(style.height) || 0,
            };
        }"""
    )
    assert switch_computed["width"] >= _MIN_TOUCH_TARGET_PX, switch_computed
    assert switch_computed["height"] >= _MIN_TOUCH_TARGET_PX, switch_computed


@pytest.mark.mobile_ui
def test_sheet_touch_tap_outside_discards_but_a_touch_scroll_keeps_the_staging(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a staged "Owner only" choice in the 420px sheet
    WHEN a touch scroll starts outside the section THEN the staged choice stays
    AND WHEN a touch tap lands outside the section THEN it is discarded with
        "Change not applied." and the link stays live
    """
    app = provide_app
    page = page_mobile_portrait
    link_id = _open_owner_sheet_with_co_owner_link(app=app, page=page)
    patches = _record_settings_patches(page)
    _stage_owner_only(page=page)
    apply = page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_APPLY)

    # A touch pointer that moves is a scroll, not a tap. Dispatched on the personal
    # sort row (inside the sheet, outside the permissions section); the document
    # listener reads it synchronously, so the DOM is settled when this returns.
    page.evaluate(
        """({ selector, dy }) => {
            const row = document.querySelector(selector).closest('.panelSettingsRow');
            const rect = row.getBoundingClientRect();
            const base = {
                bubbles: true, cancelable: true, pointerType: 'touch',
                pointerId: 7, isPrimary: true, clientX: rect.left + 20,
            };
            const startY = rect.top + rect.height / 2;
            row.dispatchEvent(new PointerEvent('pointerdown', { ...base, clientY: startY }));
            row.dispatchEvent(new PointerEvent('pointermove', { ...base, clientY: startY + dy / 2 }));
            row.dispatchEvent(new PointerEvent('pointerup', { ...base, clientY: startY + dy }));
        }""",
        {
            "selector": HPL.MEMBERS_SETTINGS_SHEET_SORT_SELECT,
            "dy": _TOUCH_SCROLL_PX,
        },
    )
    expect(apply).to_be_visible()
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_SELECT)).to_have_value(
        "owner_only"
    )
    assert patches == []
    assert not is_invite_link_revoked_in_db(app=app, invite_link_id=link_id)

    header = page.locator(HPL.PANEL_SETTINGS_SHEET_HEADER).bounding_box()
    assert header is not None
    page.touchscreen.tap(header["x"] + 24, header["y"] + header["height"] / 2)

    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_have_text(
        MEMBERS_PERMISSIONS_CHANGE_NOT_APPLIED
    )
    _expect_staging_gone_and_stored_value(page=page)
    assert not is_invite_link_revoked_in_db(app=app, invite_link_id=link_id)


@pytest.mark.mobile_ui
@pytest.mark.parametrize("staged", [False, True], ids=["unstaged", "staged"])
def test_320px_sheet_has_no_horizontal_scroll_and_controls_fit(
    page_mobile_portrait: Page,
    create_test_utubmembers,
    provide_app: Flask,
    staged: bool,
):
    """
    GIVEN the owner on a 320px phone (where the gear lives in the overflow menu)
    WHEN they open the Members sheet, with or without a staged choice
    THEN neither the document nor the sheet scrolls horizontally and the select
        (and the staged Apply button) fit inside the sheet
    """
    page = page_mobile_portrait
    _seed_co_owner_link(app=provide_app)
    open_members_deck_as(app=provide_app, page=page, user_id=OWNER_ID)
    page.set_viewport_size({"width": 320, "height": 800})
    page.locator(HPL.BUTTON_MEMBER_OVERFLOW).tap()
    page.locator(HPL.MEMBER_OVERFLOW_SETTINGS).tap()
    expect(page.locator(HPL.PANEL_SETTINGS_SHEET)).to_be_visible()
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_SELECT
    )
    wait_for_css_transitions_to_finish(locator=page.locator(HPL.PANEL_SETTINGS_SHEET))
    if staged:
        _stage_owner_only(page=page)

    overflow = page.evaluate(
        """(sheetSelector) => {
            const sheet = document.querySelector(sheetSelector);
            const root = document.documentElement;
            return {
                documentOverflow: root.scrollWidth - root.clientWidth,
                sheetOverflow: sheet.scrollWidth - sheet.clientWidth,
            };
        }""",
        HPL.PANEL_SETTINGS_SHEET,
    )
    assert overflow["documentOverflow"] <= 0, overflow
    assert overflow["sheetOverflow"] <= 0, overflow

    sheet_box = page.locator(HPL.PANEL_SETTINGS_SHEET).bounding_box()
    assert sheet_box is not None
    fitting = [HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_SELECT]
    if staged:
        fitting.append(HPL.MEMBERS_PERMISSIONS_INVITE_CREATORS_APPLY)
    for selector in fitting:
        box = page.locator(selector).bounding_box()
        assert box is not None
        assert box["x"] >= sheet_box["x"] - 0.5, (selector, box, sheet_box)
        assert box["x"] + box["width"] <= sheet_box["x"] + sheet_box["width"] + 0.5, (
            selector,
            box,
            sheet_box,
        )
