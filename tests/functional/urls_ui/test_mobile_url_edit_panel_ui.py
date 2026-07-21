import random
from typing import Tuple
from urllib.parse import urlsplit

from flask import Flask
from flask.testing import FlaskCliRunner
import pytest
from playwright.sync_api import Locator, Page, expect

from backend.cli.mock_constants import MOCK_URL_STRINGS
from backend.models.utubs import Utubs
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    add_mock_urls,
    get_url_in_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
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
    get_selected_url,
    wait_then_click_element,
    wait_until_css_property,
    wait_until_hidden,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.mobile_ui

# The four sibling option buttons that collapse away while the consolidated edit
# panel is open, leaving only the full-width "Cancel" button in the options row.
_SIBLING_OPTION_BTNS = (
    HPL.BUTTON_URL_ACCESS,
    HPL.BUTTON_TAG_CREATE,
    HPL.BUTTON_URL_COPY,
    HPL.BUTTON_URL_DELETE,
)


def _select_first_url_in_utub_mobile(
    *, page: Page, app: Flask, utub_id: int
) -> Locator:
    """Select the first URL in the UTub and return the selected URL Locator."""
    utub_url = get_url_in_utub(app, utub_id)
    wait_then_click_element(
        page=page, css_selector=f"{HPL.ROWS_URLS}[utuburlid='{utub_url.id}']"
    )
    return get_selected_url(page=page)


def _open_url_edit_panel_mobile(*, page: Page) -> None:
    """Tap the consolidated bottom-row edit button and wait for BOTH the title
    and string forms to open together."""
    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}",
    )
    wait_until_visible_css_selector(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_TITLE_UPDATE}",
    )
    wait_until_visible_css_selector(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE}",
    )


def test_url_title_pencil_hidden_on_selected_url_mobile(
    page_mobile_portrait: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests that the URL title pencil icon stays hidden on mobile even after a URL
    card is selected — the title row is title + go-to-URL icon only, and editing
    is reached exclusively through the consolidated bottom-row edit button.

    GIVEN a user views a UTub on a mobile device
    WHEN the user taps a URL card to select it
    THEN the URL title pencil icon is NOT displayed on the selected card
    """
    page = page_mobile_portrait
    app = provide_app
    user_id_for_test = 1
    _, cli_runner = runner
    add_mock_urls(cli_runner, [UTS.TEST_URL_STRING_CREATE])
    utub: Utubs = get_utub_this_user_created(app, user_id=user_id_for_test)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    _select_first_url_in_utub_mobile(page=page, app=app, utub_id=utub.id)

    # The consolidated bottom-row edit button IS reachable on the selected card...
    assert_visible_css_selector(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}",
    )
    # ...but the legacy title pencil stays hidden on mobile (desktop-only now).
    assert_not_visible_css_selector(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_TITLE_UPDATE}",
    )


def test_url_edit_button_opens_both_title_and_string_forms_mobile(
    page_mobile_portrait: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests that tapping the consolidated bottom-row edit button on mobile opens
    BOTH the URL title and URL string forms together, collapses the sibling
    option buttons into a single full-width Cancel button, hides the corner
    go-to-URL icon, and that cancelling restores all of them.

    GIVEN a user has a URL card selected on a mobile device
    WHEN the user taps the bottom-row edit button
    THEN both the title and string edit inputs open, Access/Tag/Copy/Delete are
        hidden behind a single full-width Cancel button, and the go-to-URL icon
        is hidden; tapping Cancel restores the row and the go-to-URL icon
    """
    page = page_mobile_portrait
    app = provide_app
    user_id_for_test = 1
    _, cli_runner = runner
    add_mock_urls(cli_runner, [UTS.TEST_URL_STRING_CREATE])
    utub: Utubs = get_utub_this_user_created(app, user_id=user_id_for_test)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    selected_url = _select_first_url_in_utub_mobile(page=page, app=app, utub_id=utub.id)

    # The go-to-URL icon is visible on the selected card before opening the panel.
    expect(selected_url.locator(HPL.GO_TO_URL_ICON)).to_be_visible()

    _open_url_edit_panel_mobile(page=page)

    # BOTH forms are open together.
    expect(selected_url.locator(HPL.INPUT_URL_TITLE_UPDATE)).to_be_visible()
    expect(selected_url.locator(HPL.INPUT_URL_STRING_UPDATE)).to_be_visible()

    # The corner go-to-URL icon is hidden while the panel is open.
    expect(selected_url.locator(HPL.GO_TO_URL_ICON)).to_be_hidden()

    # The four sibling option buttons collapse away, leaving a single full-width
    # "Cancel" button (the repurposed edit button morphed to
    # .urlStringCancelBigBtnUpdate) as the only control in the options row.
    for sibling_btn in _SIBLING_OPTION_BTNS:
        expect(selected_url.locator(sibling_btn)).to_be_hidden()
    big_cancel = selected_url.locator(HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)
    expect(big_cancel).to_be_visible()
    expect(big_cancel).to_have_text("Cancel")
    # The morphed button replaced .urlStringBtnUpdate while the panel is open.
    expect(selected_url.locator(HPL.BUTTON_URL_STRING_UPDATE)).to_have_count(0)

    # On mobile the small per-field red × on each of the title/string forms is
    # hidden — the full-width Cancel bar is the single close control.
    expect(selected_url.locator(HPL.BUTTON_URL_TITLE_CANCEL_UPDATE)).to_be_hidden()
    expect(selected_url.locator(HPL.BUTTON_URL_STRING_CANCEL_UPDATE)).to_be_hidden()

    # Tapping the full-width Cancel closes the whole panel (both fields).
    big_cancel.click()

    wait_until_hidden(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE}",
    )
    expect(selected_url.locator(HPL.INPUT_URL_TITLE_UPDATE)).to_be_hidden()

    # All four sibling buttons and the go-to-URL icon are restored on close, and
    # the edit button reverts to its .urlStringBtnUpdate identity.
    for sibling_btn in _SIBLING_OPTION_BTNS:
        expect(selected_url.locator(sibling_btn)).to_be_visible()
    expect(selected_url.locator(HPL.GO_TO_URL_ICON)).to_be_visible()
    expect(selected_url.locator(HPL.BUTTON_URL_STRING_UPDATE)).to_be_visible()
    expect(selected_url.locator(HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)).to_have_count(
        0
    )


def test_url_edit_panel_escape_closes_both_title_and_string_forms_mobile(
    page_mobile_portrait: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests the panel-level Escape coordination for the consolidated URL edit
    panel: after opening both the title and string forms together, pressing
    Escape closes BOTH fields and restores the sibling option buttons and the
    go-to-URL icon — the same end state as the full-width Cancel, reached via the
    document-level keydown handler.

    GIVEN a user has opened the consolidated URL edit panel on a mobile device
    WHEN the user presses the Escape key
    THEN both the title and string forms close and the row is restored
    """
    page = page_mobile_portrait
    app = provide_app
    user_id_for_test = 1
    _, cli_runner = runner
    add_mock_urls(cli_runner, [UTS.TEST_URL_STRING_CREATE])
    utub: Utubs = get_utub_this_user_created(app, user_id=user_id_for_test)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    selected_url = _select_first_url_in_utub_mobile(page=page, app=app, utub_id=utub.id)

    _open_url_edit_panel_mobile(page=page)

    # Both forms are open together before Escape.
    expect(selected_url.locator(HPL.INPUT_URL_TITLE_UPDATE)).to_be_visible()
    expect(selected_url.locator(HPL.INPUT_URL_STRING_UPDATE)).to_be_visible()

    page.keyboard.press("Escape")

    # Both fields close together on Escape.
    wait_until_hidden(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE}",
    )
    expect(selected_url.locator(HPL.INPUT_URL_TITLE_UPDATE)).to_be_hidden()

    # The row is restored: sibling option buttons and the go-to-URL icon are
    # visible again, and the edit button reverts to its .urlStringBtnUpdate form.
    for sibling_btn in _SIBLING_OPTION_BTNS:
        expect(selected_url.locator(sibling_btn)).to_be_visible()
    expect(selected_url.locator(HPL.GO_TO_URL_ICON)).to_be_visible()
    expect(selected_url.locator(HPL.BUTTON_URL_STRING_UPDATE)).to_be_visible()
    expect(selected_url.locator(HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)).to_have_count(
        0
    )


def test_url_edit_button_absent_for_non_owner_mobile(
    page_mobile_portrait: Page,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
):
    """
    Tests that neither the consolidated edit button nor the title pencil is
    rendered for a user who cannot edit the URL (non-owner / non-creator) on
    mobile — the whole edit affordance is gated by the same ``canDelete`` flag.

    GIVEN a non-owner member views a UTub they did not create on a mobile device
    WHEN the user selects a URL card
    THEN neither the consolidated edit button nor the title pencil is present
    """
    page = page_mobile_portrait
    app = provide_app
    user_id_for_test = 2
    non_owned_utub: Utubs = get_utub_this_user_did_not_create(
        app, user_id=user_id_for_test
    )
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id_for_test, utub_id=non_owned_utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    _select_first_url_in_utub_mobile(page=page, app=app, utub_id=non_owned_utub.id)

    # Neither edit affordance is in the DOM at all for a non-editor.
    expect(
        page.locator(f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}")
    ).to_have_count(0)
    expect(
        page.locator(f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_TITLE_UPDATE}")
    ).to_have_count(0)


def test_url_string_edit_via_consolidated_panel_mobile(
    page_mobile_portrait: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests that the URL string can be edited and submitted independently through
    the consolidated mobile panel, without also submitting the title field.

    GIVEN a user has a URL card selected on a mobile device
    WHEN the user opens the consolidated panel, edits only the URL string, and
        submits it
    THEN the URL string is updated while the title field remains unchanged
    """
    page = page_mobile_portrait
    app = provide_app
    user_id_for_test = 1
    _, cli_runner = runner
    random_url_to_add, random_url_to_change_to = random.sample(MOCK_URL_STRINGS, 2)
    add_mock_urls(cli_runner, [random_url_to_add])
    utub: Utubs = get_utub_this_user_created(app, user_id=user_id_for_test)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    selected_url = _select_first_url_in_utub_mobile(page=page, app=app, utub_id=utub.id)

    # Capture the title before editing so we can prove it is untouched by the
    # independent URL-string submit.
    original_title = selected_url.locator(HPL.URL_TITLE_READ).inner_text()

    _open_url_edit_panel_mobile(page=page)

    string_input = selected_url.locator(HPL.INPUT_URL_STRING_UPDATE)
    string_input.fill(random_url_to_change_to)

    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}",
    )

    # The URL-string form closes once the PATCH lands.
    wait_until_hidden(page=page, css_selector=HPL.UPDATE_URL_STRING_WRAP)

    # The URL string persisted.
    url_string_elem = selected_url.locator(HPL.URL_STRING_READ)
    updated_href = url_string_elem.get_attribute("href")
    host_changed_to = urlsplit(random_url_to_change_to).hostname
    actual_host = urlsplit(updated_href or "").hostname
    assert isinstance(host_changed_to, str)
    assert isinstance(actual_host, str)
    assert host_changed_to in actual_host or actual_host in host_changed_to

    # The title field never submitted — its editable input still holds the
    # original title, so the string submit was independent of the title.
    expect(selected_url.locator(HPL.INPUT_URL_TITLE_UPDATE)).to_have_value(
        original_title
    )


def test_url_edit_button_hidden_and_unreachable_when_not_selected_mobile(
    page_mobile_portrait: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests the negative case (Step 3 gate): while a URL card is NOT selected, the
    consolidated edit button is not visible (the whole options row is collapsed)
    and tapping where it would be does not open the edit panel.

    GIVEN a URL card is present but not selected on a mobile device
    WHEN nothing is selected, and then the user taps the collapsed card
    THEN the consolidated edit button (and its sibling options) are hidden while
        unselected, and the tap selects the card at most — it never opens the
        title/string edit panel
    """
    page = page_mobile_portrait
    app = provide_app
    user_id_for_test = 1
    _, cli_runner = runner
    add_mock_urls(cli_runner, [UTS.TEST_URL_STRING_CREATE])
    utub: Utubs = get_utub_this_user_created(app, user_id=user_id_for_test)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    utub_url = get_url_in_utub(app, utub.id)
    url_row_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url.id}']"
    url_row = page.locator(url_row_selector)
    expect(url_row).to_be_visible()

    # Before selection: the whole .urlOptions row is collapsed, so the
    # consolidated edit button and its siblings are unreachable. The collapse gate
    # is `opacity: 0; pointer-events: none` (not display:none) — Playwright treats
    # opacity:0 as "visible", so assert the actual reachability gate
    # (pointer-events, mirroring the locked-UTub test) rather than visibility.
    for option_btn in (HPL.BUTTON_URL_STRING_UPDATE, *_SIBLING_OPTION_BTNS):
        wait_until_css_property(
            page=page,
            css_selector=f"{url_row_selector} {option_btn}",
            css_property="pointer-events",
            expected_value="none",
        )
    # No edit input is open (these use the `hidden` class — genuinely display:none).
    expect(url_row.locator(HPL.INPUT_URL_STRING_UPDATE)).to_be_hidden()
    expect(url_row.locator(HPL.INPUT_URL_TITLE_UPDATE)).to_be_hidden()

    # A tap where the collapsed edit button sits passes through (pointer-events:
    # none) and selects the card at most — it must NOT open the consolidated
    # edit panel.
    url_row.click()
    wait_until_visible_css_selector(page=page, css_selector=HPL.ROW_SELECTED_URL)

    expect(url_row.locator(HPL.INPUT_URL_STRING_UPDATE)).to_be_hidden()
    expect(url_row.locator(HPL.INPUT_URL_TITLE_UPDATE)).to_be_hidden()
