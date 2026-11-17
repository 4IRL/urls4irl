"""Playwright UI tests (mobile) for per-UTub tag permissions.

A plain member with a blocked tag control sees a lock glyph and gets the reason in
a tap note (no hover tooltip on touch). Deck refusals with the Tag sheet open put
the reason in the blocked control's own ``.disabledReasonNote`` inside the sheet
(the URL deck banner sits behind the inert URL deck then), never in the banner.
"""

from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Locator, Page, expect

from backend.cli.mock_constants import MOCK_URL_STRINGS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    add_url_to_utub_as_other_member,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_utils import (
    wait_then_click_element,
    wait_until_visible_css_selector,
)
from tests.functional.tags_ui.db_utils import (
    apply_tag_to_url_in_db,
    count_tags_on_url,
    create_utub_tag,
    utub_tag_exists,
)
from tests.functional.tags_ui.playwright_utils import (
    TAG_PERMISSIONS_MEMBER_ID,
    TAG_PERMISSIONS_OWNER_ID,
    expect_can_delete_tags,
    expect_can_tag,
    login_member_into_owner_utub,
    set_tags_permissions,
    swipe_tag_sheet_open,
    wait_until_tag_sheet_open,
)

pytestmark = [pytest.mark.tags_ui, pytest.mark.mobile_ui]

MEMBER_URL_STRING = MOCK_URL_STRINGS[0] + "mobile-tag-permissions"
MEMBER_URL_TITLE = "Mobile tag permissions URL"
SEEDED_TAG_STRING = "mobilepermtag"
NEW_TAG_STRING = "mobilefresh"
MIN_TOUCH_TARGET_PX = 44
NARROW_VIEWPORT = {"width": 420, "height": 900}


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


def _note_after(*, control: Locator) -> Locator:
    """The control's own live-region note (its next sibling)."""
    return control.locator("xpath=following-sibling::*[@role='status']").first


def _open_tag_sheet(*, page: Page) -> None:
    swipe_tag_sheet_open(page=page)
    wait_until_tag_sheet_open(page=page)


def _expect_touch_sized(*, control: Locator) -> None:
    box = control.bounding_box()
    assert box is not None
    assert box["width"] >= MIN_TOUCH_TARGET_PX - 1
    assert box["height"] >= MIN_TOUCH_TARGET_PX - 1


def test_blocked_controls_show_lock_glyphs_and_tap_notes(
    page_mobile_portrait: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN Tagging is off for a plain member on a touch phone
    WHEN they tap a blocked URL Add tag, a blocked badge x, then (Tag sheet open)
         the blocked create button and pencil
    THEN each shows a lock glyph, is a touch-sized target, writes the reason into
         its own note, and runs no action
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = get_utub_this_user_created(app, TAG_PERMISSIONS_OWNER_ID).id
    url_id, tag_id = _seed_member_url_with_tag(app=app, utub_id=utub_id)
    set_tags_permissions(app=app, utub_id=utub_id, members_can_tag=False)
    login_member_into_owner_utub(
        app=app, page=page, mobile=True, can_tag=False, can_delete_tags=False
    )

    wait_then_click_element(
        page=page, css_selector=f"{HPL.ROWS_URLS}[utuburlid='{url_id}']"
    )
    add_button = page.locator(f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_CREATE}").first
    expect(add_button).to_have_attribute("aria-disabled", "true")
    expect(add_button.locator(HPL.DISABLED_REASON_LOCK)).to_have_count(1)
    expect(page.locator(HPL.DISABLED_REASON_TOOLTIP)).to_have_count(0)
    _expect_touch_sized(control=add_button)
    add_note = _note_after(control=add_button)
    expect(add_note).to_have_text("")
    add_button.click(force=True)
    expect(add_note).to_have_text(UTS.TAG_URLS_NOT_ALLOWED)
    expect(add_note).to_be_visible()
    expect(page.locator(f"{HPL.INPUT_TAG_COMBOBOX}:visible")).to_have_count(0)

    remove_button = page.locator(
        f"{HPL.ROW_SELECTED_URL} {HPL.TAG_BADGES}[{HPL.TAG_BADGE_ID_ATTRIB}='{tag_id}']"
        f" {HPL.BUTTON_TAG_DELETE}"
    ).first
    expect(remove_button).to_have_attribute("aria-disabled", "true")
    expect(remove_button.locator(HPL.DISABLED_REASON_LOCK)).to_have_count(1)
    remove_note = _note_after(control=remove_button)
    remove_button.click(force=True)
    expect(remove_note).to_have_text(UTS.TAG_REMOVE_NOT_ALLOWED)
    expect(add_note).to_have_text("")
    assert count_tags_on_url(app=app, utub_url_id=url_id) == 1

    _open_tag_sheet(page=page)
    for selector, reason in (
        (HPL.BUTTON_UTUB_TAG_CREATE, UTS.TAG_CREATE_NOT_ALLOWED),
        (HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN, UTS.TAG_DELETE_NOT_ALLOWED),
    ):
        control = page.locator(f"{HPL.TAG_SHEET_BODY} {selector}")
        expect(control).to_have_attribute("aria-disabled", "true")
        expect(control.locator(HPL.DISABLED_REASON_LOCK)).to_have_count(1)
        _expect_touch_sized(control=control)
        note = _note_after(control=control)
        control.click(force=True)
        expect(note).to_have_text(reason)
        expect(note).to_be_in_viewport()
    expect(page.locator(HPL.INPUT_UTUB_TAG_CREATE)).to_be_hidden()
    expect(page.locator(HPL.WRAP_BUTTON_UPDATE_TAG_ALL_CLOSE)).to_be_hidden()


def _check_sheet_open_create_refusal(
    *, page: Page, app: Flask, expect_lock_glyph: bool
) -> None:
    """Stale-tab deck create with the Tag sheet open: the reason lands in the create
    button's own note inside the sheet, not in the URL deck banner."""
    utub_id = get_utub_this_user_created(app, TAG_PERMISSIONS_OWNER_ID).id
    login_member_into_owner_utub(app=app, page=page, mobile=True)
    _open_tag_sheet(page=page)

    create_button = page.locator(f"{HPL.TAG_SHEET_BODY} {HPL.BUTTON_UTUB_TAG_CREATE}")
    create_button.click()
    wait_until_visible_css_selector(page=page, css_selector=HPL.INPUT_UTUB_TAG_CREATE)
    page.locator(HPL.INPUT_UTUB_TAG_CREATE).fill(NEW_TAG_STRING)

    set_tags_permissions(app=app, utub_id=utub_id, members_can_tag=False)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    expect(create_button).to_have_attribute("aria-disabled", "true")
    note = _note_after(control=create_button)
    expect(note).to_have_text(UTS.TAG_CREATE_NOT_ALLOWED)
    expect(note).to_have_attribute("role", "status")
    expect(note).to_be_visible()
    expect(note).to_be_in_viewport()
    expect(page.locator(HPL.URL_DECK_ERROR_INDICATOR)).to_have_text("")
    expect(page.locator(HPL.INPUT_UTUB_TAG_CREATE)).to_be_hidden()
    expect(create_button.locator(HPL.DISABLED_REASON_LOCK)).to_have_count(
        1 if expect_lock_glyph else 0
    )
    expect_can_tag(page=page, allowed=False)


def test_sheet_open_deck_create_refusal_shows_reason_in_the_control_note(
    page_mobile_portrait: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a touch member with the Tag sheet open whose tab still allows tagging
    WHEN a manager turns Tagging off and the member submits a new UTub tag
    THEN the reason shows in the create button's note inside #tagSheetBody (visible
         on screen), the create button flips to disabled with a lock glyph, and the
         URL deck banner stays empty
    """
    _check_sheet_open_create_refusal(
        page=page_mobile_portrait, app=provide_app, expect_lock_glyph=True
    )


def test_sheet_open_deck_create_refusal_on_fine_pointer_narrow_viewport(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a fine-pointer narrow window (mobile layout, no touch, no coarse pointer)
          with the Tag sheet open
    WHEN a manager turns Tagging off and the member submits a new UTub tag
    THEN the empty note region already exists and shows the reason, without a lock
         glyph, and the URL deck banner stays empty
    """
    page.set_viewport_size(NARROW_VIEWPORT)
    _check_sheet_open_create_refusal(
        page=page, app=provide_app, expect_lock_glyph=False
    )


def test_sheet_open_delete_refusal_shows_reason_on_the_pencil_and_keeps_focus_there(
    page_mobile_portrait: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a touch member with the Tag sheet open whose tab still allows deleting
    WHEN a manager turns only Delete off and the member confirms a tag delete
    THEN the reason shows in the pencil's note in the sheet (not the banner), the
         tag still exists, the pencil flips to disabled and ends focused
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = get_utub_this_user_created(app, TAG_PERMISSIONS_OWNER_ID).id
    _, tag_id = _seed_member_url_with_tag(app=app, utub_id=utub_id)
    login_member_into_owner_utub(app=app, page=page, mobile=True)
    _open_tag_sheet(page=page)

    pencil = page.locator(f"{HPL.TAG_SHEET_BODY} {HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN}")
    pencil.click()
    delete_button = page.locator(
        f"{HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}='{tag_id}'] {HPL.BUTTON_UTUB_TAG_DELETE}"
    )
    expect(delete_button).to_be_visible()
    delete_button.click()
    wait_until_visible_css_selector(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    set_tags_permissions(app=app, utub_id=utub_id, members_can_delete_tags=False)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    expect_can_delete_tags(page=page, allowed=False)
    expect(pencil).to_have_attribute("aria-disabled", "true")
    note = _note_after(control=pencil)
    expect(note).to_have_text(UTS.TAG_DELETE_NOT_ALLOWED)
    expect(note).to_be_in_viewport()
    expect(pencil).to_be_focused()
    expect(page.locator(HPL.URL_DECK_ERROR_INDICATOR)).to_have_text("")
    assert utub_tag_exists(app=app, utub_tag_id=tag_id)
