from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.models.utub_members import Member_Role
from backend.utils.strings.url_strs import URL_MOVED_TO_TRASH_ONE
from backend.utils.strings.utub_strs import URLS_SETTINGS_SECTION_TITLE
from tests.functional.db_utils import (
    get_url_in_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
    set_member_role_in_utub,
    set_member_settings,
)
from tests.functional.home_ui.test_panel_settings_mobile_ui import (
    _close_sheet_via_close_button,
    _expect_sheet_closed,
    _open_urls_sheet,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_panel_visibility_mobile,
    assert_settings_panel_controls_fit,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    Decks,
    get_num_url_rows,
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_for_element_to_be_removed,
    wait_then_click_element,
)
from tests.functional.urls_ui.playwright_utils import (
    get_url_row_selector,
    swipe_url_card_delete,
    wait_until_url_card_swipe_reset,
)

pytestmark = [pytest.mark.urls_ui, pytest.mark.mobile_ui]

USER_ID_FOR_TEST = 1
URL_DECK = HPL.URL_DECK
NUDGE_PEEKING_ROW = f"{HPL.ROWS_URLS}.swipe-nudge-peeking"
NUDGE_SESSION_KEY = "u4i:urlSwipeNudgeShown"
SWIPE_OFF_SETTINGS = {"urls": {"disable_swipe_delete": True}}


def _login_to_owned_utub_on_phone(*, app: Flask, page: Page) -> tuple[int, str]:
    """Log user 1 (creator, so every URL is deletable) into their own UTub on a
    phone. Returns (utub id, first URL's row selector)."""
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    row_selector = get_url_row_selector(utub_url_id=get_url_in_utub(app, utub.id).id)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)
    expect(page.locator(row_selector)).to_be_visible()
    return utub.id, row_selector


def _read_nudge_flag(*, page: Page) -> str | None:
    return page.evaluate(f"sessionStorage.getItem('{NUDGE_SESSION_KEY}')")


def test_swipe_off_leaves_row_in_place_and_delete_button_still_deletes(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a member with swipe to delete turned off
    WHEN they swipe a deletable row left past the commit threshold
    THEN the row stays, the reveal panel is hidden, and tapping the card's
        Delete button still moves the URL to Trash
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = get_utub_this_user_created(app, USER_ID_FOR_TEST).id
    set_member_settings(app, utub_id, USER_ID_FOR_TEST, SWIPE_OFF_SETTINGS)
    _, row_selector = _login_to_owned_utub_on_phone(app=app, page=page)
    expect(page.locator(URL_DECK)).to_have_attribute("data-swipe-delete", "off")
    reveal = page.locator(f"{row_selector} {HPL.URL_ROW_SWIPE_REVEAL}")
    expect(reveal).to_be_attached()
    expect(reveal).to_be_hidden()
    init_num_url_rows = get_num_url_rows(page=page)

    swipe_url_card_delete(page=page, url_row_selector=row_selector)
    wait_until_url_card_swipe_reset(page=page)

    # The companion test below proves the same swipe commits when swipe is on,
    # so a row still present with no transform and no banner is a real no-op.
    expect(page.locator(row_selector)).to_have_count(1)
    expect(page.locator(row_selector)).to_have_css("transform", "none")
    expect(page.locator(HPL.URL_OUTCOME_BANNER)).to_be_hidden()
    assert init_num_url_rows == get_num_url_rows(page=page)

    wait_then_click_element(page=page, css_selector=row_selector)
    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )
    wait_then_click_element(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}"
    )
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_MOVED_TO_TRASH_ONE
    )
    wait_for_element_to_be_removed(page=page, locator=page.locator(row_selector))


def test_swipe_off_shows_no_onboarding_nudge_and_keeps_session_flag_unset(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a member with swipe to delete turned off on an otherwise nudge-eligible
        load (phone, unlocked UTub, rows in view, flag unset)
    WHEN the UTub loads
    THEN no row peeks and the session flag is never written
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = get_utub_this_user_created(app, USER_ID_FOR_TEST).id
    set_member_settings(app, utub_id, USER_ID_FOR_TEST, SWIPE_OFF_SETTINGS)

    _login_to_owned_utub_on_phone(app=app, page=page)

    expect(page.locator(URL_DECK)).to_have_attribute("data-swipe-delete", "off")
    expect(page.locator(NUDGE_PEEKING_ROW)).to_have_count(0)
    assert _read_nudge_flag(page=page) is None


def test_swipe_on_load_writes_the_nudge_session_flag(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the same nudge-eligible load with swipe to delete left on
    WHEN the UTub loads
    THEN the session flag is written, so the swipe-off test above is not vacuous
    """
    page = page_mobile_portrait

    _login_to_owned_utub_on_phone(app=provide_app, page=page)

    page.wait_for_function(f"sessionStorage.getItem('{NUDGE_SESSION_KEY}') === 'true'")


def test_turning_swipe_off_in_sheet_makes_swipe_delete_work_again_without_reload(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN swipe to delete turned off, so a swipe does nothing
    WHEN the member switches "Turn off swipe to delete" back off in the sheet
    THEN the same rows commit a swipe delete again, with no reload
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = get_utub_this_user_created(app, USER_ID_FOR_TEST).id
    set_member_settings(app, utub_id, USER_ID_FOR_TEST, SWIPE_OFF_SETTINGS)
    _, row_selector = _login_to_owned_utub_on_phone(app=app, page=page)

    _open_urls_sheet(page)
    swipe_switch = page.locator(HPL.URLS_PERSONAL_DISABLE_SWIPE_SWITCH)
    expect(swipe_switch).to_have_attribute("aria-checked", "true")
    swipe_switch.tap()
    expect(swipe_switch).to_have_attribute("aria-checked", "false")
    expect(page.locator(URL_DECK)).to_have_attribute("data-swipe-delete", "on")
    _close_sheet_via_close_button(page)
    _expect_sheet_closed(page)

    swipe_url_card_delete(page=page, url_row_selector=row_selector)

    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_MOVED_TO_TRASH_ONE
    )
    wait_for_element_to_be_removed(page=page, locator=page.locator(row_selector))


def test_plain_member_writes_personal_section_in_mobile_sheet(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a plain member on a phone
    WHEN they turn on Hide Copy in the sheet's "Your view of this UTub" section
    THEN the deck hides Copy and the choice is still on after a reload
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST).id
    set_member_role_in_utub(app, USER_ID_FOR_TEST, utub_id, Member_Role.MEMBER)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    _open_urls_sheet(page)
    hide_copy = page.locator(HPL.URLS_PERSONAL_HIDE_COPY_SWITCH)
    expect(hide_copy).to_have_attribute("aria-checked", "false")
    expect(hide_copy).not_to_have_attribute("aria-disabled", "true")
    hide_copy.tap()
    expect(hide_copy).to_have_attribute("aria-checked", "true")
    expect(page.locator(URL_DECK)).to_have_attribute("data-hide-copy", "true")
    _close_sheet_via_close_button(page)

    page.reload()
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)
    expect(page.locator(URL_DECK)).to_have_attribute("data-hide-copy", "true")
    _open_urls_sheet(page)
    expect(page.locator(HPL.URLS_PERSONAL_HIDE_COPY_SWITCH)).to_have_attribute(
        "aria-checked", "true"
    )


def test_layout_select_has_no_cards_option_on_a_phone_without_an_override(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a phone-width sheet and no per-UTub Layout override
    WHEN the URLs settings sheet opens
    THEN the Layout select does not offer Cards
    """
    page = page_mobile_portrait
    _login_to_owned_utub_on_phone(app=provide_app, page=page)
    _open_urls_sheet(page)

    expect(page.locator(HPL.URLS_PERSONAL_VIEW_SELECT)).to_be_attached()
    expect(
        page.locator(f'{HPL.URLS_PERSONAL_VIEW_SELECT} option[value="cards"]')
    ).to_have_count(0)


def test_cards_override_shows_one_selected_small_screen_option_on_a_phone(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a member whose per-UTub Layout override is cards, on a phone
    WHEN the URLs settings sheet opens
    THEN the one cards option is the selected "Cards (List on small screens)"
        and the Default option keeps its true label
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = get_utub_this_user_created(app, USER_ID_FOR_TEST).id
    set_member_settings(
        app, utub_id, USER_ID_FOR_TEST, {"urls": {"view_mode": "cards"}}
    )
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)
    _open_urls_sheet(page)

    view_select = page.locator(HPL.URLS_PERSONAL_VIEW_SELECT)
    cards_option = page.locator(
        f'{HPL.URLS_PERSONAL_VIEW_SELECT} option[value="cards"]'
    )
    expect(cards_option).to_have_count(1)
    expect(cards_option).to_have_text("Cards (List on small screens)")
    expect(view_select).to_have_value("cards")
    expect(
        page.locator(f'{HPL.URLS_PERSONAL_VIEW_SELECT} option[value=""]')
    ).to_have_text("Default: List")


def test_lone_sections_have_no_heading_in_the_sheet_and_density_is_absent(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the URLs settings sheet on a touch device
    WHEN it opens
    THEN the lone "New URLs" section shows no heading but stays a labelled group
        with its controls visible, and the personal section offers Sort and
        Layout but no Density row
    """
    page = page_mobile_portrait
    _login_to_owned_utub_on_phone(app=provide_app, page=page)
    _open_urls_sheet(page)

    expect(page.locator(HPL.URLS_PERSONAL_SORT_SELECT)).to_be_attached()
    expect(page.locator(HPL.URLS_PERSONAL_VIEW_SELECT)).to_be_attached()
    expect(page.locator(HPL.URLS_PERSONAL_DENSITY_SELECT)).to_have_count(0)

    section = page.locator(
        HPL.SETTINGS_GROUP_SECTION_FORMAT.format(
            scope=HPL.SETTINGS_GROUP_UTUB,
            section_id=HPL.SETTINGS_SECTION_URLS_DEFAULTS,
        )
    )
    expect(section).to_have_attribute("role", "group")
    expect(section).to_have_attribute("aria-label", URLS_SETTINGS_SECTION_TITLE)
    expect(section.locator("h3")).to_be_hidden()
    expect(
        page.locator(
            HPL.SETTINGS_SECTION_TOGGLE_FORMAT.format(
                section_id=HPL.SETTINGS_SECTION_URLS_DEFAULTS
            )
        )
    ).to_be_hidden()
    expect(page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME)).to_be_visible()


def test_parent_header_tap_collapses_its_sections_in_the_sheet(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the URLs settings sheet on a touch device
    WHEN the "Shared with this UTub" parent header is tapped, then tapped again
    THEN its "New URLs" controls hide and return while "Just for you" is untouched
    """
    page = page_mobile_portrait
    _login_to_owned_utub_on_phone(app=provide_app, page=page)
    _open_urls_sheet(page)

    parent_toggle = page.locator(
        HPL.SETTINGS_GROUP_TOGGLE_FORMAT.format(scope=HPL.SETTINGS_GROUP_UTUB)
    )
    expect(parent_toggle).to_have_attribute("aria-expanded", "true")

    parent_toggle.tap()
    expect(parent_toggle).to_have_attribute("aria-expanded", "false")
    expect(page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME)).to_be_hidden()
    expect(page.locator(HPL.URLS_PERSONAL_SORT_SELECT)).to_be_visible()

    parent_toggle.tap()
    expect(parent_toggle).to_have_attribute("aria-expanded", "true")
    expect(page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME)).to_be_visible()


@pytest.mark.parametrize("viewport_width", [320, 360, 420])
def test_every_sheet_control_fits_inside_the_sheet_at_phone_widths(
    page_mobile_portrait: Page,
    create_test_urls,
    provide_app: Flask,
    viewport_width: int,
):
    """
    GIVEN the URLs settings sheet with both parents and all sections expanded on
        a 320, 360 or 420px phone
    WHEN the default scheme is https, then a non-https one (which adds the hint)
    THEN no row element extends past the sheet body's right inner edge, the body
        does not scroll horizontally, and the scheme toggle is a complete box
    """
    page = page_mobile_portrait
    page.set_viewport_size({"width": viewport_width, "height": 900})
    _login_to_owned_utub_on_phone(app=provide_app, page=page)
    _open_urls_sheet(page)
    expect(page.locator(HPL.PANEL_SETTINGS_SCHEME_TOGGLE)).to_be_visible()
    expect(page.locator(HPL.URLS_PERSONAL_HIDE_DATE_SWITCH)).to_be_visible()

    assert_settings_panel_controls_fit(
        page=page, container_selector=HPL.PANEL_SETTINGS_SHEET_BODY
    )

    page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME).tap()
    page.locator(HPL.URLS_SETTINGS_SHEET_SCHEME_FILTER).fill("ftp")
    page.locator(HPL.URLS_SETTINGS_SHEET_SCHEME_OPTION_VISIBLE).first.tap()
    expect(page.locator(HPL.URLS_SETTINGS_HIDE_HINT)).to_be_visible()
    assert_settings_panel_controls_fit(
        page=page, container_selector=HPL.PANEL_SETTINGS_SHEET_BODY
    )
