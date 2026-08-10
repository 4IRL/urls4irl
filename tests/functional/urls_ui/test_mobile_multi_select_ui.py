from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend.models.utubs import Utubs
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import assert_panel_visibility_mobile
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    Decks,
    click_on_navbar,
    get_all_url_ids_in_selected_utub,
    wait_for_class_to_be_removed,
    wait_then_click_element,
)
from tests.functional.urls_ui.playwright_assert_utils import (
    assert_urls_are_multi_selected,
)

pytestmark = [pytest.mark.urls_ui, pytest.mark.mobile_ui]

USER_ID_FOR_TEST = 1


def _enter_multi_select_mode(*, page: Page) -> None:
    """Tap the header toggle and settle into multi-select mode (bottom-docked
    bar visible, aria-pressed reflecting the pressed state)."""
    toggle = page.locator(HPL.BUTTON_MULTI_SELECT_TOGGLE)
    expect(toggle).to_be_visible()
    toggle.click()
    expect(toggle).to_have_attribute("aria-pressed", "true")
    expect(page.locator(HPL.BULK_ACTION_BAR)).to_be_visible()


def _tap_url_checkbox(*, page: Page, utub_url_id: int) -> None:
    """Tap a row's 44px multi-select checkbox to toggle that row's selection."""
    checkbox_selector = (
        f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}'] {HPL.URL_SELECT_CHECKBOX}"
    )
    page.locator(checkbox_selector).first.click()


def test_mobile_bulk_bar_appears_and_checkbox_toggles(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck
    WHEN they enter multi-select mode and tap a 44px row checkbox
    THEN the bottom-docked bulk bar appears and the checkbox tap toggles the
        row's selection on, then off
    """
    page = page_mobile_portrait
    app = provide_app
    utub: Utubs = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    url_ids = get_all_url_ids_in_selected_utub(page=page)
    assert len(url_ids) >= 1

    _enter_multi_select_mode(page=page)
    expect(page.locator(HPL.URL_SELECT_CHECKBOX).first).to_be_visible()

    _tap_url_checkbox(page=page, utub_url_id=url_ids[0])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("1")
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(1)
    assert_urls_are_multi_selected(page=page, utub_url_ids=[url_ids[0]])

    _tap_url_checkbox(page=page, utub_url_id=url_ids[0])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("0")
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(0)


def test_mobile_switching_panel_exits_mode(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a mobile user with a live multi-selection on the URL deck
    WHEN they switch to another panel (fires MOBILE_DECK_SWITCHED)
    THEN multi-select mode exits: the bar hides and no rows remain marked
    """
    page = page_mobile_portrait
    app = provide_app
    utub: Utubs = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    url_ids = get_all_url_ids_in_selected_utub(page=page)
    assert len(url_ids) >= 1

    _enter_multi_select_mode(page=page)
    _tap_url_checkbox(page=page, utub_url_id=url_ids[0])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("1")

    # Switch to the Members panel via the mobile navbar.
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=HPL.NAVBAR_MEMBER_DECK)
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="collapsing"
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.MEMBERS)

    expect(page.locator(HPL.BULK_ACTION_BAR)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MULTI_SELECT_TOGGLE)).to_have_attribute(
        "aria-pressed", "false"
    )
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(0)


def test_mobile_back_button_exits_mode(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a mobile user with a live multi-selection on the URL deck
    WHEN they press the browser Back button (leaving the URL deck)
    THEN multi-select mode exits: the bar hides and no rows remain marked
    """
    page = page_mobile_portrait
    app = provide_app
    utub: Utubs = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    url_ids = get_all_url_ids_in_selected_utub(page=page)
    assert len(url_ids) >= 1

    _enter_multi_select_mode(page=page)
    _tap_url_checkbox(page=page, utub_url_id=url_ids[0])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("1")

    # Back leaves the selected UTub's URL deck for the pre-selection UTub list,
    # deselecting the UTub and firing the deck switch — both exit multi-select.
    page.go_back()
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.UTUBS)

    expect(page.locator(HPL.BULK_ACTION_BAR)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MULTI_SELECT_TOGGLE)).to_have_attribute(
        "aria-pressed", "false"
    )
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(0)
