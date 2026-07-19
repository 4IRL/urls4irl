from __future__ import annotations

import re

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend.models.utubs import Utubs
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_no_utub_selected,
    assert_not_visible_css_selector,
    assert_panel_visibility_mobile,
    assert_visible_css_selector,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    Decks,
    click_on_navbar,
    wait_for_class_to_be_removed,
    wait_for_selector_to_be_removed,
    wait_then_click_element,
    wait_until_visible_css_selector,
)
from tests.functional.tags_ui.playwright_utils import (
    wait_until_tag_sheet_collapsed,
    wait_until_tag_sheet_open,
)

pytestmark = pytest.mark.mobile_ui

USER_ID_FOR_TEST = 1


def _nav_to_panel(*, page: Page, navbar_option: str, visible_deck: Decks) -> None:
    """Open the mobile navbar and tap a deck-switch option, settling the
    collapse transition, then confirm the target panel is the visible one."""
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=navbar_option)
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="collapsing"
    )
    assert_panel_visibility_mobile(page=page, visible_deck=visible_deck)


def test_back_and_forward_unwinds_panel_stack_mobile(
    page_mobile_portrait: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user who selected a UTub (landing on the URL deck)
        and then switched panels several times via the navbar
    WHEN they press browser Back repeatedly, then Forward repeatedly
    THEN each panel is restored in strict chronological order — Back unwinds the
        panel stack (URL deck -> panels -> the pre-selection UTub list) and
        Forward re-applies it, instead of jumping straight past every panel
    """
    page = page_mobile_portrait
    app = provide_app
    utub: Utubs = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    # Selecting the UTub lands on the URL deck (the base panel entry).
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    # Drive a chronological sequence of panel switches, each pushing its own
    # history entry on top of the base URL-deck entry.
    _nav_to_panel(
        page=page, navbar_option=HPL.NAVBAR_MEMBER_DECK, visible_deck=Decks.MEMBERS
    )
    _nav_to_panel(
        page=page, navbar_option=HPL.NAVBAR_UTUB_DECK, visible_deck=Decks.UTUBS
    )
    _nav_to_panel(
        page=page, navbar_option=HPL.NAVBAR_URLS_DECK, visible_deck=Decks.URLS
    )

    # Chronological stack of pushed panel entries (oldest -> newest):
    #   URLS (selection) -> MEMBERS -> UTUBS -> URLS
    forward_panel_stack = [Decks.URLS, Decks.MEMBERS, Decks.UTUBS, Decks.URLS]

    # Go backwards: each Back restores the previous panel in the stack.
    for expected_deck in reversed(forward_panel_stack[:-1]):
        page.go_back()
        assert_panel_visibility_mobile(page=page, visible_deck=expected_deck)

    # One more Back leaves the selected UTub entirely, returning to the
    # pre-selection UTub list (no UTub selected).
    page.go_back()
    assert_no_utub_selected(page=page)
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.UTUBS)

    # Go forwards: each Forward re-applies the panels in chronological order.
    for expected_deck in forward_panel_stack:
        page.go_forward()
        assert_panel_visibility_mobile(page=page, visible_deck=expected_deck)


def test_tag_sheet_two_level_back_mobile(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck who opened the Tag sheet
    WHEN they press browser Back once, then again
    THEN the first Back closes the sheet (the URL deck remains visible beneath
        it) and the second Back leaves the URL deck for the pre-selection UTub
        list — the sheet has its own in-session history entry
    """
    page = page_mobile_portrait
    app = provide_app
    utub: Utubs = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    # Open the sheet via the navbar Tags button; it overlays the URL deck and
    # pushes its own session-only history entry.
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=HPL.NAVBAR_TAGS_DECK)
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="show"
    )
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="collapsing"
    )
    wait_until_tag_sheet_open(page=page)
    assert_visible_css_selector(page=page, css_selector=HPL.URL_DECK)

    # First Back closes the sheet only; the URL deck stays visible beneath it.
    page.go_back()
    wait_until_tag_sheet_collapsed(page=page)
    assert_visible_css_selector(page=page, css_selector=HPL.URL_DECK)

    # Second Back leaves the URL deck for the pre-selection UTub list.
    page.go_back()
    assert_no_utub_selected(page=page)
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.UTUBS)


def test_reload_persists_panel_and_keeps_tag_sheet_closed_mobile(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user who navigated to the Member deck
    WHEN they reload the page
    THEN the Member deck is restored and the URL carries `&panel=members`; and
        after opening the Tag sheet on the URL deck and reloading, the sheet
        stays closed (it does not auto-reopen across a reload)
    """
    page = page_mobile_portrait
    app = provide_app
    utub: Utubs = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    # Navigate to the Member deck; the URL now carries the panel query param.
    _nav_to_panel(
        page=page, navbar_option=HPL.NAVBAR_MEMBER_DECK, visible_deck=Decks.MEMBERS
    )
    expect(page).to_have_url(re.compile(r"panel=members"))

    # Reload restores the Member deck from the persisted panel state.
    page.reload()
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.MEMBERS)
    expect(page).to_have_url(re.compile(r"panel=members"))

    # Return to the URL deck and open the Tag sheet.
    _nav_to_panel(
        page=page, navbar_option=HPL.NAVBAR_URLS_DECK, visible_deck=Decks.URLS
    )
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=HPL.NAVBAR_TAGS_DECK)
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="show"
    )
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="collapsing"
    )
    wait_until_tag_sheet_open(page=page)

    # Reloading with the sheet open must NOT auto-reopen it: it lands on the
    # underlying URL deck with the sheet collapsed.
    page.reload()
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)
    wait_until_tag_sheet_collapsed(page=page)


def test_back_to_deleted_utub_panel_entry_degrades_gracefully_mobile(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user who selected a UTub, switched panels, then
        deleted that UTub
    WHEN they press browser Back onto a panel history entry pointing at the
        now-deleted UTub
    THEN the app degrades gracefully — it resets to the no-UTub-selected home
        state (no crash, no error page) rather than trying to restore the
        deleted UTub
    """
    page = page_mobile_portrait
    app = provide_app
    utub: Utubs = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    # Push a Member-deck panel entry for this UTub (the stale entry to Back to),
    # then return to the UTub deck where the delete affordance lives on mobile.
    _nav_to_panel(
        page=page, navbar_option=HPL.NAVBAR_MEMBER_DECK, visible_deck=Decks.MEMBERS
    )
    _nav_to_panel(
        page=page, navbar_option=HPL.NAVBAR_UTUB_DECK, visible_deck=Decks.UTUBS
    )

    # Delete the UTub (mobile delete flow: mirror test_navbar_after_utub_deleted).
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    expect(page.locator(HPL.SELECTOR_SELECTED_UTUB).first).to_be_attached()
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    wait_for_selector_to_be_removed(page=page, css_selector=HPL.SELECTOR_SELECTED_UTUB)

    assert_no_utub_selected(page=page)

    # Back lands on a panel entry whose UTub no longer exists: it must reset to
    # the no-UTub home state gracefully, not error or crash.
    page.go_back()
    assert_no_utub_selected(page=page)
    assert_not_visible_css_selector(page=page, css_selector=HPL.MEMBER_DECK)
    expect(page).not_to_have_title(re.compile(r"Invalid Request"))
