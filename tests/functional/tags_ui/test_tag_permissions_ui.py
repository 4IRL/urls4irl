"""Playwright UI tests (desktop) for per-UTub tag permissions.

The Tags gear section itself is covered by ``test_tag_permissions_settings_ui.py``;
this file covers what each role sees on the decks (blocked controls with a reason),
and the stale-tab self-heal when a manager changes a switch under an open page.

A plain member is user 2 on user 1's UTub (the mock data makes every user a plain
member of every other user's UTub). A manager changing a switch from another tab is
a direct DB settings write (``set_tags_permissions``). Flip-while-open observer
behaviours (menu close, drag end, picker close) are Vitest-only; the browser can
only deliver a flip through a refresh (after the busy UI closes) or a 403.
"""

from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Locator, Page, Response, expect

from backend.cli.mock_constants import MOCK_URL_STRINGS, MOCK_URL_TITLES
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    add_url_to_utub_as_other_member,
    get_utub_this_user_created,
    set_utub_locked_state,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_utubid
from tests.functional.playwright_utils import (
    login_user_to_home_page,
    refocus_window,
    select_utub_by_id,
    wait_then_click_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.tags_ui.db_utils import (
    apply_tag_to_url_in_db,
    count_tags_on_url,
    count_utub_urls_in_utub,
    create_utub_tag,
    get_url_ids_in_utub_ordered,
    utub_tag_exists,
)
from tests.functional.tags_ui.playwright_utils import (
    TAG_PERMISSIONS_MEMBER_ID,
    TAG_PERMISSIONS_OWNER_ID,
    enter_multi_select_and_select_urls,
    expect_can_delete_tags,
    expect_can_tag,
    login_member_into_owner_utub,
    open_delete_utub_tag_confirm_modal_for_tag,
    open_tag_combobox,
    select_url_row,
    set_tags_permissions,
    stage_new_tag,
    submit_staged_tags,
)
from tests.functional.urls_ui.playwright_utils import fill_create_url_form

pytestmark = pytest.mark.tags_ui

REFRESH_INTERVAL_PASSED_MS = 31_000
MEMBER_URL_STRING = "https://tag-permissions.example.com/"
MEMBER_URL_TITLE = "Tag permissions member URL"
SEEDED_TAG_STRING = "permtag"
NEW_TAG_STRING = "freshtag"
DISABLED_CLASS_RE = re.compile(r"(^|\s)disabledReasonControl(\s|$)")
TOOLTIP_VISIBLE_CLASS_RE = re.compile(r"(^|\s)disabledReasonTooltipVisible(\s|$)")
HOME_URL_RE = re.compile(r"/home(\?|$)")

# Makes both pointer capabilities report true, like a touch laptop (desktop Chromium
# reports fine only). Registered before the first navigation to the home page.
_HYBRID_POINTER_INIT_SCRIPT = """
(() => {
  const realMatchMedia = window.matchMedia.bind(window);
  const forced = new Set(['(any-pointer: coarse)', '(any-pointer: fine)']);
  window.matchMedia = (query) => {
    const result = realMatchMedia(query);
    if (!forced.has(query)) return result;
    return new Proxy(result, {
      get(target, prop) {
        if (prop === 'matches') return true;
        const value = Reflect.get(target, prop);
        return typeof value === 'function' ? value.bind(target) : value;
      },
    });
  };
})();
"""

_SEED_ONBOARDING_SEEN = (
    "localStorage.setItem('u4i:onboardingSeen',"
    " JSON.stringify({createUtub: true, addUrl: true}))"
)


def _owner_utub_id(*, app: Flask) -> int:
    return get_utub_this_user_created(app, TAG_PERMISSIONS_OWNER_ID).id


def _seed_member_url_with_tag(*, app: Flask, utub_id: int) -> tuple[int, int]:
    """A URL the member added, carrying one UTub tag. Returns (url id, tag id)."""
    url_id = add_url_to_utub_as_other_member(
        app, utub_id, TAG_PERMISSIONS_MEMBER_ID, MEMBER_URL_STRING, MEMBER_URL_TITLE
    )
    tag_id = create_utub_tag(
        app=app,
        utub_id=utub_id,
        user_id=TAG_PERMISSIONS_OWNER_ID,
        tag_string=SEEDED_TAG_STRING,
    )
    apply_tag_to_url_in_db(
        app=app,
        utub_id=utub_id,
        user_id=TAG_PERMISSIONS_MEMBER_ID,
        utub_url_id=url_id,
        utub_tag_id=tag_id,
    )
    return url_id, tag_id


def _is_settings_patch(response: Response) -> bool:
    return response.request.method == "PATCH" and "settings" in response.url


def _open_tags_gear(*, page: Page) -> None:
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_TAG_SETTINGS_GEAR)
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_visible()
    expect(page.locator(HPL.TAGS_PERMISSIONS_MEMBERS_CAN_TAG_SWITCH)).to_be_visible()


def _reason_tooltip(*, page: Page, control: Locator) -> Locator:
    """The reason tooltip a blocked control exposes through aria-describedby."""
    expect(control).to_have_attribute(
        "aria-describedby", re.compile(r"^disabledReasonTooltip\d+$")
    )
    tooltip_id = control.get_attribute("aria-describedby")
    assert tooltip_id is not None
    return page.locator(f"#{tooltip_id}")


def _expect_blocked_with_reason(
    *, page: Page, control: Locator, reason: str, check_hover: bool = True
) -> None:
    """aria-disabled, in the tab order, and the reason as tooltip on hover/focus."""
    expect(control).to_have_attribute("aria-disabled", "true")
    expect(control).to_have_class(DISABLED_CLASS_RE)
    expect(control).not_to_have_attribute("tabindex", "-1")
    tooltip = _reason_tooltip(page=page, control=control)
    expect(tooltip).to_have_text(reason)
    expect(tooltip).to_have_attribute("role", "tooltip")
    if not check_hover:
        return
    control.hover()
    expect(tooltip).to_have_class(TOOLTIP_VISIBLE_CLASS_RE)
    page.mouse.move(0, 0)
    expect(tooltip).not_to_have_class(TOOLTIP_VISIBLE_CLASS_RE)
    # A keyboard keydown first, so a scripted focus() counts as keyboard focus.
    page.keyboard.press("Shift")
    control.focus()
    expect(control).to_be_focused()
    expect(tooltip).to_have_class(TOOLTIP_VISIBLE_CLASS_RE)
    control.blur()
    expect(tooltip).not_to_have_class(TOOLTIP_VISIBLE_CLASS_RE)


def _expect_no_picker_open(*, page: Page) -> None:
    """No tag combobox input is shown (cards keep a hidden one mounted)."""
    expect(page.locator(f"{HPL.INPUT_TAG_COMBOBOX}:visible")).to_have_count(0)


def _expect_not_blocked(*, control: Locator) -> None:
    expect(control).not_to_have_attribute("aria-disabled", "true")
    expect(control).not_to_have_class(DISABLED_CLASS_RE)


def _selected_row_add_tag_btn(*, page: Page) -> Locator:
    return page.locator(f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_CREATE}").first


def _selected_row_remove_btn(*, page: Page) -> Locator:
    return page.locator(f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_DELETE}").first


def _banner(*, page: Page) -> Locator:
    return page.locator(HPL.URL_DECK_ERROR_INDICATOR)


def _login_with_clock(*, app: Flask, page: Page, can_tag: bool = True) -> int:
    """Install the fake clock before the page loads (so a later fast-forward passes
    the refresh-on-focus interval) and log the member in."""
    page.clock.install()
    return login_member_into_owner_utub(
        app=app, page=page, can_tag=can_tag, can_delete_tags=can_tag
    )


# --- Manager settings section --------------------------------------------------


def test_manager_switches_persist_across_reload(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN an owner who turned "Members can tag" off and, separately, only
          "Members can delete tags" off
    WHEN the page reloads
    THEN each reload shows the stored switches (Delete forced off and disabled
         while Tagging is off)
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=TAG_PERMISSIONS_OWNER_ID, utub_id=utub_id
    )

    _open_tags_gear(page=page)
    tag_switch = page.locator(HPL.TAGS_PERMISSIONS_MEMBERS_CAN_TAG_SWITCH)
    delete_switch = page.locator(HPL.TAGS_PERMISSIONS_MEMBERS_CAN_DELETE_SWITCH)
    with page.expect_response(_is_settings_patch) as response_info:
        delete_switch.click()
    assert response_info.value.status == 200
    expect(delete_switch).to_have_attribute("aria-checked", "false")

    page.reload()
    select_utub_by_id(page=page, utub_id=utub_id)
    _open_tags_gear(page=page)
    expect(tag_switch).to_have_attribute("aria-checked", "true")
    expect(delete_switch).to_have_attribute("aria-checked", "false")

    with page.expect_response(_is_settings_patch) as response_info:
        tag_switch.click()
    assert response_info.value.status == 200

    page.reload()
    select_utub_by_id(page=page, utub_id=utub_id)
    _open_tags_gear(page=page)
    expect(tag_switch).to_have_attribute("aria-checked", "false")
    expect(delete_switch).to_have_attribute("aria-checked", "false")
    expect(delete_switch).to_have_attribute("aria-disabled", "true")


def test_manager_tag_switch_toggles_by_keyboard_and_disabled_delete_keeps_hint(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN an owner with the Tags gear open
    WHEN they toggle "Members can tag" with Enter
    THEN it saves, and the now-disabled Delete switch stays focusable and exposes
         its hint through aria-describedby
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=TAG_PERMISSIONS_OWNER_ID, utub_id=utub_id
    )

    _open_tags_gear(page=page)
    tag_switch = page.locator(HPL.TAGS_PERMISSIONS_MEMBERS_CAN_TAG_SWITCH)
    delete_switch = page.locator(HPL.TAGS_PERMISSIONS_MEMBERS_CAN_DELETE_SWITCH)
    tag_switch.focus()
    with page.expect_response(_is_settings_patch) as response_info:
        page.keyboard.press("Enter")
    assert response_info.value.status == 200
    expect(tag_switch).to_have_attribute("aria-checked", "false")

    expect(delete_switch).to_have_attribute("aria-disabled", "true")
    expect(delete_switch).to_have_attribute(
        "aria-describedby", re.compile(r"tagsPermissionsMembersCanDeleteHint")
    )
    delete_switch.focus()
    expect(delete_switch).to_be_focused()
    page.keyboard.press("Space")
    expect(delete_switch).to_have_attribute("aria-checked", "false")
    expect(page.locator(HPL.TAGS_PERMISSIONS_MEMBERS_CAN_DELETE_HINT)).to_be_visible()


def test_switches_are_reachable_by_tab_and_toggle_with_space(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN an owner with the Tags gear open and focus on "Members can tag"
    WHEN they press Space, then Tab to "Members can delete tags" and press Space
    THEN each press saves its own switch (Tab reaches the second switch)
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=TAG_PERMISSIONS_OWNER_ID, utub_id=utub_id
    )

    _open_tags_gear(page=page)
    tag_switch = page.locator(HPL.TAGS_PERMISSIONS_MEMBERS_CAN_TAG_SWITCH)
    delete_switch = page.locator(HPL.TAGS_PERMISSIONS_MEMBERS_CAN_DELETE_SWITCH)
    tag_switch.focus()
    page.keyboard.press("Tab")
    expect(delete_switch).to_be_focused()
    with page.expect_response(_is_settings_patch) as response_info:
        page.keyboard.press("Space")
    assert response_info.value.status == 200
    expect(delete_switch).to_have_attribute("aria-checked", "false")
    expect(tag_switch).to_have_attribute("aria-checked", "true")

    page.keyboard.press("Shift+Tab")
    expect(tag_switch).to_be_focused()
    with page.expect_response(_is_settings_patch) as response_info:
        page.keyboard.press("Space")
    assert response_info.value.status == 200
    expect(tag_switch).to_have_attribute("aria-checked", "false")


@pytest.mark.parametrize(
    "viewer_id", [TAG_PERMISSIONS_OWNER_ID, TAG_PERMISSIONS_MEMBER_ID]
)
def test_locked_utub_renders_tag_switches_read_only(
    page: Page, create_test_tags, provide_app: Flask, viewer_id: int
):
    """
    GIVEN a locked UTub
    WHEN its owner, or a plain member, opens the Tags gear
    THEN both switches are aria-disabled and the existing read-only note shows
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    set_utub_locked_state(app, utub_id, True)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=viewer_id, utub_id=utub_id
    )

    _open_tags_gear(page=page)
    for selector in (
        HPL.TAGS_PERMISSIONS_MEMBERS_CAN_TAG_SWITCH,
        HPL.TAGS_PERMISSIONS_MEMBERS_CAN_DELETE_SWITCH,
    ):
        switch = page.locator(selector)
        expect(switch).to_have_attribute("aria-disabled", "true")
        switch.click(force=True)
        expect(switch).to_have_attribute("aria-checked", "true")
    expect(page.locator(HPL.URLS_SETTINGS_READ_ONLY_NOTE).first).to_be_visible()


# --- Blocked controls for a plain member ---------------------------------------


def test_member_with_tagging_off_sees_blocked_controls_with_reasons(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN Tagging is off for a plain member
    WHEN they view the decks
    THEN create, pencil, URL Add tag and the badge x are aria-disabled in the tab
         order with the reason as tooltip on hover and focus, the Add URL form has no
         tag picker, tag chips are not draggable and the bulk toolbar shows no tag
         picker
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    url_id, _ = _seed_member_url_with_tag(app=app, utub_id=utub_id)
    set_tags_permissions(app=app, utub_id=utub_id, members_can_tag=False)
    login_member_into_owner_utub(
        app=app, page=page, can_tag=False, can_delete_tags=False
    )

    _expect_blocked_with_reason(
        page=page,
        control=page.locator(HPL.BUTTON_UTUB_TAG_CREATE),
        reason=UTS.TAG_CREATE_NOT_ALLOWED,
    )
    _expect_blocked_with_reason(
        page=page,
        control=page.locator(HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN),
        reason=UTS.TAG_DELETE_NOT_ALLOWED,
    )

    select_url_row(page=page, utub_url_id=url_id)
    _expect_blocked_with_reason(
        page=page,
        control=_selected_row_add_tag_btn(page=page),
        reason=UTS.TAG_URLS_NOT_ALLOWED,
    )
    _expect_blocked_with_reason(
        page=page,
        control=_selected_row_remove_btn(page=page),
        reason=UTS.TAG_REMOVE_NOT_ALLOWED,
    )

    # Activating a blocked control does nothing.
    _selected_row_add_tag_btn(page=page).click(force=True)
    _expect_no_picker_open(page=page)
    page.locator(HPL.BUTTON_UTUB_TAG_CREATE).click(force=True)
    expect(page.locator(HPL.INPUT_UTUB_TAG_CREATE)).to_be_hidden()

    # No tag picker in the Add URL form.
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.WRAP_URL_CREATE)
    expect(page.locator(HPL.CREATE_FORM_TAG_COMBOBOX_INPUT)).to_have_count(0)

    # Chips are not draggable.
    chips = page.locator(HPL.TAG_FILTERS)
    expect(chips.first).to_be_visible()
    for chip in chips.all():
        expect(chip).not_to_have_attribute("draggable", "true")


def test_blocked_url_add_tag_shows_only_the_reason_tooltip_until_allowed_again(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a plain member with Tagging off who hovers URL Add tag
    WHEN the reason tooltip shows
    THEN no second (Bootstrap) tooltip shows with it, and after a manager turns
         Tagging back on and the member refreshes, the button works and its own
         tooltip is back
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    url_id, _ = _seed_member_url_with_tag(app=app, utub_id=utub_id)
    set_tags_permissions(app=app, utub_id=utub_id, members_can_tag=False)
    _login_with_clock(app=app, page=page, can_tag=False)

    select_url_row(page=page, utub_url_id=url_id)
    add_button = _selected_row_add_tag_btn(page=page)
    tooltip = _reason_tooltip(page=page, control=add_button)
    add_button.hover()
    expect(tooltip).to_have_class(TOOLTIP_VISIBLE_CLASS_RE)
    expect(page.locator(".tooltip.show")).to_have_count(0)
    page.mouse.move(0, 0)

    set_tags_permissions(app=app, utub_id=utub_id)
    page.clock.fast_forward(REFRESH_INTERVAL_PASSED_MS)
    refocus_window(page=page)
    expect_can_tag(page=page, allowed=True)
    _expect_not_blocked(control=add_button)
    add_button.hover()
    expect(page.locator(".tooltip.show")).to_have_count(1)
    expect(page.locator(HPL.DISABLED_REASON_TOOLTIP_VISIBLE)).to_have_count(0)


def test_escape_hides_reason_tooltip_and_still_reaches_the_owning_layer(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a visible reason tooltip while the Add URL form is open
    WHEN the user presses Escape in the form
    THEN the tooltip hides and the form still receives the Escape and closes
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    set_tags_permissions(app=app, utub_id=utub_id, members_can_tag=False)
    login_member_into_owner_utub(
        app=app, page=page, can_tag=False, can_delete_tags=False
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.WRAP_URL_CREATE)
    page.locator(HPL.INPUT_URL_TITLE_CREATE).focus()

    create_button = page.locator(HPL.BUTTON_UTUB_TAG_CREATE)
    tooltip = _reason_tooltip(page=page, control=create_button)
    create_button.hover()
    expect(tooltip).to_have_class(TOOLTIP_VISIBLE_CLASS_RE)

    page.keyboard.press("Escape")
    expect(tooltip).not_to_have_class(TOOLTIP_VISIBLE_CLASS_RE)
    wait_until_hidden(page=page, css_selector=HPL.WRAP_URL_CREATE)


def test_hybrid_pointer_shows_tooltip_lock_glyph_and_tap_note(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a device reporting both a coarse and a fine pointer
    WHEN a plain member with Tagging off views a blocked control
    THEN the reason tooltip appears on hover and focus, the lock glyph is present,
         and a tap writes the reason into the note without running the action
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    url_id, tag_id = _seed_member_url_with_tag(app=app, utub_id=utub_id)
    set_tags_permissions(app=app, utub_id=utub_id, members_can_tag=False)
    page.add_init_script(_HYBRID_POINTER_INIT_SCRIPT)
    login_member_into_owner_utub(
        app=app, page=page, can_tag=False, can_delete_tags=False
    )

    select_url_row(page=page, utub_url_id=url_id)
    add_button = _selected_row_add_tag_btn(page=page)
    _expect_blocked_with_reason(
        page=page, control=add_button, reason=UTS.TAG_URLS_NOT_ALLOWED
    )
    expect(add_button.locator(HPL.DISABLED_REASON_LOCK)).to_have_count(1)

    note = add_button.locator("xpath=following-sibling::*[@role='status']")
    expect(note).to_have_text("")
    expect(note).to_have_css("height", "0px")
    add_button.click(force=True)
    expect(note).to_have_text(UTS.TAG_URLS_NOT_ALLOWED)
    _expect_no_picker_open(page=page)

    # The remove x lives inside the tag badge; its lock, tooltip and note nodes
    # are siblings in that badge and must not break the badge's layout.
    remove_button = _selected_row_remove_btn(page=page)
    expect(remove_button.locator(HPL.DISABLED_REASON_LOCK)).to_have_count(1)
    badge = page.locator(
        f"{HPL.ROW_SELECTED_URL} {HPL.TAG_BADGES}[{HPL.TAG_BADGE_ID_ATTRIB}='{tag_id}']"
    )
    badge_box_before = badge.bounding_box()
    assert badge_box_before is not None
    remove_note = remove_button.locator("xpath=following-sibling::*[@role='status']")
    expect(remove_note).to_have_text("")
    expect(remove_note).to_have_css("height", "0px")
    remove_button.click(force=True)
    expect(remove_note).to_have_text(UTS.TAG_REMOVE_NOT_ALLOWED)
    assert count_tags_on_url(app=app, utub_url_id=url_id) == 1
    # The reason notes replace each other (single-note rule).
    expect(note).to_have_text("")
    badge_box_after = badge.bounding_box()
    assert badge_box_after is not None
    assert badge_box_after["x"] == pytest.approx(badge_box_before["x"], abs=1)
    assert badge_box_after["y"] == pytest.approx(badge_box_before["y"], abs=1)


def test_add_tag_onboarding_nudge_never_shows_to_member_who_cannot_tag(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with URLs and no tags where the plain member may not tag
    WHEN the member selects it
    THEN the addTag nudge never shows (while it does for a member who may tag)
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    login_user_to_home_page(app=app, page=page, user_id=TAG_PERMISSIONS_MEMBER_ID)
    page.evaluate(_SEED_ONBOARDING_SEEN)
    select_utub_by_id(page=page, utub_id=utub_id)
    expect(page.locator(HPL.ONBOARDING_NUDGE_TOOLTIP)).to_be_visible()

    set_tags_permissions(app=app, utub_id=utub_id, members_can_tag=False)
    page.reload()
    # The first showing may have marked the tip seen; reseed so the absence below
    # is due to the permission, not the seen flag.
    page.evaluate(_SEED_ONBOARDING_SEEN)
    select_utub_by_id(page=page, utub_id=utub_id)
    expect_can_tag(page=page, allowed=False)
    expect(page.locator(HPL.ROWS_URLS).first).to_be_visible()
    expect(page.locator(HPL.BUTTON_UTUB_TAG_CREATE)).to_have_attribute(
        "aria-disabled", "true"
    )
    expect(page.locator(HPL.ONBOARDING_NUDGE_TOOLTIP)).to_have_count(0)


def test_member_with_delete_off_only_gets_a_blocked_pencil(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN Tagging is on but "Members can delete tags" is off
    WHEN a plain member views the decks
    THEN only the pencil is blocked
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    url_id, _ = _seed_member_url_with_tag(app=app, utub_id=utub_id)
    set_tags_permissions(app=app, utub_id=utub_id, members_can_delete_tags=False)
    login_member_into_owner_utub(app=app, page=page, can_delete_tags=False)

    _expect_blocked_with_reason(
        page=page,
        control=page.locator(HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN),
        reason=UTS.TAG_DELETE_NOT_ALLOWED,
    )
    _expect_not_blocked(control=page.locator(HPL.BUTTON_UTUB_TAG_CREATE))
    select_url_row(page=page, utub_url_id=url_id)
    _expect_not_blocked(control=_selected_row_add_tag_btn(page=page))
    _expect_not_blocked(control=_selected_row_remove_btn(page=page))


def test_blocked_badge_x_hidden_in_edit_mode_and_restored_after(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a plain member with Tagging off on a URL they added
    WHEN they open the URL string editor
    THEN the badge x is hidden (edit-mode hiding wins over the blocked x), and
         leaving edit mode restores it blocked
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    url_id, _ = _seed_member_url_with_tag(app=app, utub_id=utub_id)
    set_tags_permissions(app=app, utub_id=utub_id, members_can_tag=False)
    login_member_into_owner_utub(
        app=app, page=page, can_tag=False, can_delete_tags=False
    )

    select_url_row(page=page, utub_url_id=url_id)
    remove_button = _selected_row_remove_btn(page=page)
    expect(remove_button).to_be_visible()
    expect(remove_button).to_have_attribute("aria-disabled", "true")

    page.locator(f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}").first.click()
    expect(remove_button).to_be_hidden()

    page.locator(
        f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_CANCEL_UPDATE}"
    ).first.click()
    expect(remove_button).to_be_visible()
    expect(remove_button).to_have_attribute("aria-disabled", "true")


def test_bulk_add_tags_is_blocked_while_other_bulk_actions_work(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a plain member with Tagging off in multi-select with a URL selected
    WHEN they look at the bulk toolbar
    THEN "Add tags" is aria-disabled with the reason and opens no picker, while
         "Copy" stays enabled
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    set_tags_permissions(app=app, utub_id=utub_id, members_can_tag=False)
    login_member_into_owner_utub(
        app=app, page=page, can_tag=False, can_delete_tags=False
    )
    url_ids = get_url_ids_in_utub_ordered(app=app, utub_id=utub_id)

    enter_multi_select_and_select_urls(page=page, url_ids=url_ids[:1])
    add_tags_button = page.locator(HPL.BUTTON_BULK_ADD_TAGS)
    _expect_blocked_with_reason(
        page=page, control=add_tags_button, reason=UTS.TAG_URLS_NOT_ALLOWED
    )
    add_tags_button.click(force=True)
    _expect_no_picker_open(page=page)
    copy_button = page.locator(HPL.BUTTON_BULK_COPY_URLS)
    expect(copy_button).to_be_enabled()
    _expect_not_blocked(control=copy_button)


# --- Refresh and stale-tab self-heal --------------------------------------------


def test_refresh_after_form_close_blocks_controls_without_reload(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a member with staged tags in the Add URL form and a manager who turns
          Tagging off meanwhile
    WHEN the member closes the form and the tab refreshes on focus
    THEN the create button, URL Add tag, the badge x and (in multi-select) the bulk
         "Add tags" button all become aria-disabled, with no reload
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    url_id, _ = _seed_member_url_with_tag(app=app, utub_id=utub_id)
    _login_with_clock(app=app, page=page)

    fill_create_url_form(
        page=page,
        url_title=MOCK_URL_TITLES[0],
        url_string=MOCK_URL_STRINGS[0] + "refresh",
        tag_strings=[NEW_TAG_STRING],
    )
    set_tags_permissions(app=app, utub_id=utub_id, members_can_tag=False)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_CANCEL_CREATE)
    wait_until_hidden(page=page, css_selector=HPL.WRAP_URL_CREATE)

    select_url_row(page=page, utub_url_id=url_id)
    page.clock.fast_forward(REFRESH_INTERVAL_PASSED_MS)
    refocus_window(page=page)
    expect_can_tag(page=page, allowed=False)

    expect(page.locator(HPL.BUTTON_UTUB_TAG_CREATE)).to_have_attribute(
        "aria-disabled", "true"
    )
    expect(_selected_row_add_tag_btn(page=page)).to_have_attribute(
        "aria-disabled", "true"
    )
    expect(_selected_row_remove_btn(page=page)).to_have_attribute(
        "aria-disabled", "true"
    )

    enter_multi_select_and_select_urls(page=page, url_ids=[url_id])
    expect(page.locator(HPL.BUTTON_BULK_ADD_TAGS)).to_have_attribute(
        "aria-disabled", "true"
    )


def test_stale_tab_add_tag_is_refused_and_controls_flip(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a member whose tab still allows tagging while a manager turned it off
    WHEN the member adds a tag to a URL
    THEN the banner explains why (URL code 4), no tag is added, the controls flip
         to disabled without a reload, and focus never lands on the banner
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    url_id, _ = _seed_member_url_with_tag(app=app, utub_id=utub_id)
    login_member_into_owner_utub(app=app, page=page)
    select_url_row(page=page, utub_url_id=url_id)
    open_tag_combobox(page=page, url_id=url_id)
    stage_new_tag(page=page, text=NEW_TAG_STRING)
    tags_before = count_tags_on_url(app=app, utub_url_id=url_id)

    set_tags_permissions(app=app, utub_id=utub_id, members_can_tag=False)
    submit_staged_tags(page=page)

    expect(_banner(page=page)).to_have_text(UTS.TAG_URLS_NOT_ALLOWED)
    expect_can_tag(page=page, allowed=False)
    expect(_banner(page=page)).not_to_be_focused()
    expect(page.locator(HPL.BUTTON_UTUB_TAG_CREATE)).to_have_attribute(
        "aria-disabled", "true"
    )
    expect(_selected_row_add_tag_btn(page=page)).to_have_attribute(
        "aria-disabled", "true"
    )
    assert count_tags_on_url(app=app, utub_url_id=url_id) == tags_before
    assert HOME_URL_RE.search(page.url) is not None


def test_stale_tab_deck_create_is_refused_and_create_flips(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a member whose tab still allows tagging while a manager turned it off
    WHEN the member submits a new UTub tag in the deck
    THEN the create banner shows (UTub-tag code 4), the form closes without a
         redirect, the create button flips to disabled and the banner has no focus
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    login_member_into_owner_utub(app=app, page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_TAG_CREATE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.INPUT_UTUB_TAG_CREATE)
    page.locator(HPL.INPUT_UTUB_TAG_CREATE).fill(NEW_TAG_STRING)

    set_tags_permissions(app=app, utub_id=utub_id, members_can_tag=False)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    expect(_banner(page=page)).to_have_text(UTS.TAG_CREATE_NOT_ALLOWED)
    expect(page.locator(HPL.INPUT_UTUB_TAG_CREATE)).to_be_hidden()
    create_button = page.locator(HPL.BUTTON_UTUB_TAG_CREATE)
    expect(create_button).to_have_attribute("aria-disabled", "true")
    expect(_banner(page=page)).not_to_be_focused()
    assert HOME_URL_RE.search(page.url) is not None
    expect_can_tag(page=page, allowed=False)


def test_stale_tab_delete_off_only_refuses_delete_and_blocks_pencil(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a member whose tab still allows deleting tags while a manager turned only
          Delete off
    WHEN the member confirms a tag delete
    THEN the delete banner shows (UTub-tag code 5), the tag still exists, only the
         pencil flips to disabled and focus ends on the pencil
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    _, tag_id = _seed_member_url_with_tag(app=app, utub_id=utub_id)
    login_member_into_owner_utub(app=app, page=page)

    open_delete_utub_tag_confirm_modal_for_tag(page=page, tag_id=str(tag_id), app=app)
    set_tags_permissions(app=app, utub_id=utub_id, members_can_delete_tags=False)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    expect(_banner(page=page)).to_have_text(UTS.TAG_DELETE_NOT_ALLOWED)
    expect_can_delete_tags(page=page, allowed=False)
    pencil = page.locator(HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN)
    expect(pencil).to_have_attribute("aria-disabled", "true")
    expect(pencil).to_be_focused()
    expect(_banner(page=page)).not_to_be_focused()
    _expect_not_blocked(control=page.locator(HPL.BUTTON_UTUB_TAG_CREATE))
    assert utub_tag_exists(app=app, utub_tag_id=tag_id)


def test_stale_tab_url_create_with_staged_tags_is_refused(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a member with staged tags in the Add URL form while a manager turned
          Tagging off
    WHEN the member submits
    THEN there is no redirect, the banner shows once without taking focus, the title
         and URL are kept, focus is on the URL input, the picker and staged tags are
         gone and no URL row was created
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    login_member_into_owner_utub(app=app, page=page)
    url_string = MOCK_URL_STRINGS[0] + "stale18"
    fill_create_url_form(
        page=page,
        url_title=MOCK_URL_TITLES[0],
        url_string=url_string,
        tag_strings=[NEW_TAG_STRING],
    )
    urls_before = count_utub_urls_in_utub(app=app, utub_id=utub_id)

    set_tags_permissions(app=app, utub_id=utub_id, members_can_tag=False)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SUBMIT_CREATE)

    expect(_banner(page=page)).to_have_text(UTS.TAG_URLS_NOT_ALLOWED)
    assert HOME_URL_RE.search(page.url) is not None
    expect(page.locator(HPL.WRAP_URL_CREATE)).to_be_visible()
    expect(page.locator(HPL.INPUT_URL_TITLE_CREATE)).to_have_value(MOCK_URL_TITLES[0])
    # The scheme moves into the scheme picker, so the input keeps the rest.
    expect(page.locator(HPL.INPUT_URL_STRING_CREATE)).to_have_value(
        re.compile(r"abc\.com/stale18$")
    )
    expect(page.locator(HPL.INPUT_URL_STRING_CREATE)).to_be_focused()
    expect(_banner(page=page)).not_to_be_focused()
    expect(page.locator(HPL.CREATE_FORM_TAG_COMBOBOX_INPUT)).to_have_count(0)
    expect(page.locator(HPL.CREATE_FORM_TAG_STAGED_CHIP)).to_have_count(0)
    assert count_utub_urls_in_utub(app=app, utub_id=utub_id) == urls_before


def test_blocked_chip_drag_shows_the_reason_once(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a plain member with Tagging off on a fine-pointer desktop
    WHEN they press a tag chip and drag it with the mouse
    THEN the reason shows once in the URL deck banner (a second drag adds nothing)
    """
    app = provide_app
    utub_id = _owner_utub_id(app=app)
    set_tags_permissions(app=app, utub_id=utub_id, members_can_tag=False)
    login_member_into_owner_utub(
        app=app, page=page, can_tag=False, can_delete_tags=False
    )

    chip = page.locator(HPL.TAG_FILTERS).first
    expect(chip).to_be_visible()
    box = chip.bounding_box()
    assert box is not None
    start_x = box["x"] + box["width"] / 2
    start_y = box["y"] + box["height"] / 2

    page.mouse.move(start_x, start_y)
    page.mouse.down()
    page.mouse.move(start_x + 40, start_y + 40, steps=5)
    page.mouse.up()

    expect(_banner(page=page)).to_have_text(UTS.TAG_URLS_NOT_ALLOWED)
    expect(_banner(page=page)).not_to_be_focused()

    # A second blocked drag does not stack or repeat the reason.
    page.mouse.move(start_x, start_y)
    page.mouse.down()
    page.mouse.move(start_x + 40, start_y + 40, steps=5)
    page.mouse.up()
    expect(_banner(page=page)).to_have_text(UTS.TAG_URLS_NOT_ALLOWED)
    expect(page.locator(f"{HPL.URL_DECK_ERROR_INDICATOR}:visible")).to_have_count(1)
