from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend.models.utubs import Utubs
from tests.functional.db_utils import (
    get_url_in_utub,
    get_utub_this_user_created,
    set_utub_locked_state,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_panel_visibility_mobile,
    assert_visible_css_selector,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    Decks,
    wait_then_click_element,
    wait_until_hidden,
)
from tests.functional.utubs_ui.playwright_utils import open_utub_edit_panel_mobile

pytestmark = pytest.mark.mobile_ui

# A name distinct from every seeded MockUTub_N so the owner's name submit
# persists directly instead of tripping the duplicate-name confirmation modal.
_NEW_UTUB_NAME = "Renamed Mobile UTub"
_NEW_UTUB_DESCRIPTION = "Updated via mobile panel"


def test_utub_edit_panel_toggle_opens_both_name_and_description_mobile(
    page_mobile_portrait: Page,
    create_test_urls,
    provide_app: Flask,
):
    """
    Tests that the consolidated UTub edit toggle opens BOTH the name and
    description forms on mobile, and that each field's own submit button persists
    only that field's change independently (no combined/batched submit).

    GIVEN an owner views one of their unlocked UTubs on a mobile device
    WHEN the user taps the consolidated edit toggle and submits the description,
        then the name, each via its own submit button
    THEN both forms open together and each submit persists only its own field
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    utub: Utubs = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    # The toggle is the owner-only mobile entry point; the inline pencils stay hidden.
    assert_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UTUB_EDIT_PANEL_TOGGLE
    )
    assert_not_visible_css_selector(page=page, css_selector=HPL.PENCIL_ICON_NAME)
    assert_not_visible_css_selector(page=page, css_selector=HPL.PENCIL_ICON_DESCRIPTION)

    open_utub_edit_panel_mobile(page=page)

    # Both forms opened together.
    assert_visible_css_selector(page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE)
    assert_visible_css_selector(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )
    # Opening swapped the toggle for the close button.
    assert_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UTUB_EDIT_PANEL_CLOSE
    )

    # The name input pre-fills with the current (clean) name — capture it to prove
    # it is untouched by the independent description submit below.
    original_name = page.locator(HPL.INPUT_UTUB_NAME_UPDATE).input_value()

    # Submit ONLY the description while both forms are open.
    page.locator(HPL.INPUT_UTUB_DESCRIPTION_UPDATE).fill(_NEW_UTUB_DESCRIPTION)
    wait_then_click_element(
        page=page, css_selector=HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE
    )
    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE)

    # Description persisted; the name field was NOT submitted — its input still
    # holds the original name, proving the submits are independent.
    expect(page.locator(HPL.SUBHEADER_URL_DECK)).to_have_text(_NEW_UTUB_DESCRIPTION)
    expect(page.locator(HPL.INPUT_UTUB_NAME_UPDATE)).to_have_value(original_name)

    # Now submit ONLY the name.
    page.locator(HPL.INPUT_UTUB_NAME_UPDATE).fill(_NEW_UTUB_NAME)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    # Name persisted; the previously-submitted description is unchanged.
    expect(page.locator(HPL.HEADER_URL_DECK)).to_have_text(_NEW_UTUB_NAME)
    expect(page.locator(HPL.SUBHEADER_URL_DECK)).to_have_text(_NEW_UTUB_DESCRIPTION)


def test_utub_edit_panel_close_closes_both_name_and_description_mobile(
    page_mobile_portrait: Page,
    create_test_urls,
    provide_app: Flask,
):
    """
    Tests the symmetric close path: after opening the consolidated panel, tapping
    the close button hides BOTH the name and description forms and restores the
    toggle as the visible control.

    GIVEN an owner has opened the consolidated UTub edit panel on mobile
    WHEN the user taps the close button
    THEN both the name and description forms hide and the toggle is visible again
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    utub: Utubs = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    open_utub_edit_panel_mobile(page=page)
    assert_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UTUB_EDIT_PANEL_CLOSE
    )

    # On mobile the per-field red × is hidden; the header × (panel close) is the
    # only close control for the consolidated panel.
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UTUB_NAME_CANCEL_UPDATE
    )
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UTUB_DESCRIPTION_CANCEL_UPDATE
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_EDIT_PANEL_CLOSE)

    # Both forms close together.
    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )

    # The toggle is the visible control once more; the close button is hidden.
    assert_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UTUB_EDIT_PANEL_TOGGLE
    )
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UTUB_EDIT_PANEL_CLOSE
    )


def test_utub_edit_panel_escape_closes_both_name_and_description_mobile(
    page_mobile_portrait: Page,
    create_test_urls,
    provide_app: Flask,
):
    """
    Tests the panel-level Escape coordination: after opening the consolidated
    panel, pressing Escape closes BOTH the name and description forms together
    and restores the toggle as the visible control — the same end state as the
    close button, reached via the document-level keydown handler.

    GIVEN an owner has opened the consolidated UTub edit panel on mobile
    WHEN the user presses the Escape key
    THEN both the name and description forms hide and the toggle is visible again
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    utub: Utubs = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    open_utub_edit_panel_mobile(page=page)
    assert_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UTUB_EDIT_PANEL_CLOSE
    )

    page.keyboard.press("Escape")

    # Both forms close together on Escape.
    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )

    # The toggle is the visible control once more; the close button is hidden.
    assert_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UTUB_EDIT_PANEL_TOGGLE
    )
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UTUB_EDIT_PANEL_CLOSE
    )


def test_utub_edit_panel_closes_when_url_card_selected_mobile(
    page_mobile_portrait: Page,
    create_test_urls,
    provide_app: Flask,
):
    """
    Tests the cross-component wiring: selecting a URL card while the consolidated
    UTub edit panel is open closes the panel end-to-end. Selecting a card emits
    AppEvents.URL_CARD_SELECTED, whose module-scope handler closes the open UTub
    panel — the same end state as the close button, reached via the event bus.

    GIVEN an owner has opened the consolidated UTub edit panel on mobile
    WHEN the user selects a URL card
    THEN both the name and description forms hide and the toggle is visible again
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    utub: Utubs = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    open_utub_edit_panel_mobile(page=page)
    assert_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UTUB_EDIT_PANEL_CLOSE
    )

    # Selecting a URL card emits URL_CARD_SELECTED, which closes the open panel.
    utub_url = get_url_in_utub(app, utub.id)
    wait_then_click_element(
        page=page, css_selector=f"{HPL.ROWS_URLS}[utuburlid='{utub_url.id}']"
    )

    # Both forms close together on selection.
    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )

    # The toggle is the visible control once more; the close button is hidden.
    assert_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UTUB_EDIT_PANEL_TOGGLE
    )
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UTUB_EDIT_PANEL_CLOSE
    )


def test_utub_edit_panel_toggle_hidden_on_locked_utub_mobile(
    page_mobile_portrait: Page,
    create_test_urls,
    provide_app: Flask,
):
    """
    Tests that the consolidated edit toggle is hidden on a LOCKED UTub even for
    its owner, matching the desktop pencils' owner-AND-not-locked gate.

    GIVEN an owner views one of their UTubs that is locked, on a mobile device
    WHEN the locked UTub is selected
    THEN the consolidated edit toggle is not displayed
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    locked_utub: Utubs = get_utub_this_user_created(app, user_id)
    set_utub_locked_state(app, locked_utub.id, True)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id, utub_id=locked_utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    # The URL-deck padlock confirms the locked UTub is selected.
    assert_visible_css_selector(page=page, css_selector=HPL.URL_DECK_LOCK_ICON)

    # The toggle is hidden on a locked UTub, exactly as the desktop pencils are.
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UTUB_EDIT_PANEL_TOGGLE
    )
