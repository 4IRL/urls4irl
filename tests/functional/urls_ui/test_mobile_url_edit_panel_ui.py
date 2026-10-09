import random
import re
from typing import Tuple
from urllib.parse import urlsplit

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner
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
    wait_until_same_width_and_right_edge,
    wait_until_vertical_gap,
    wait_until_visible_css_selector,
)
from tests.functional.urls_ui.playwright_utils import (
    TRIM_URL_KEEP_ONLY,
    TRIM_URL_TWO_PARAMS,
    set_trim_section_expanded,
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

    # Opening the consolidated panel must NOT deselect the card (guards the
    # previously-fixed deselect-on-open bug).
    expect(selected_url).to_have_attribute("urlselected", "true")

    # BOTH forms are open together.
    expect(selected_url.locator(HPL.INPUT_URL_TITLE_UPDATE)).to_be_visible()
    expect(selected_url.locator(HPL.INPUT_URL_STRING_UPDATE)).to_be_visible()

    # The corner go-to-URL icon is hidden while the panel is open.
    expect(selected_url.locator(HPL.GO_TO_URL_ICON)).to_be_hidden()

    # The four sibling option buttons collapse away, leaving a single full-width
    # "Close" button (the repurposed edit button morphed to
    # .urlStringCancelBigBtnUpdate) as the only control in the options row. On a
    # coarse pointer this control closes the whole panel, so it reads "Close".
    for sibling_btn in _SIBLING_OPTION_BTNS:
        expect(selected_url.locator(sibling_btn)).to_be_hidden()
    big_cancel = selected_url.locator(HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)
    expect(big_cancel).to_be_visible()
    expect(big_cancel).to_have_text("Close")
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

    # Mobile form model: a per-field submit keeps the URL-string field OPEN (it
    # does NOT collapse back to read-only), flashes a transient "Saved ✓", and
    # leaves the panel chrome untouched until the whole panel closes.
    expect(selected_url.locator(HPL.SAVED_TICK_URL_STRING)).to_have_class(
        re.compile(r"\bopa-1\b")
    )
    # The shared polite announcer states which field was saved.
    expect(page.locator(HPL.FIELD_SAVED_ANNOUNCEMENT)).to_have_text("URL Saved")

    # Both the string wrap and its sibling title wrap stay visible.
    expect(selected_url.locator(HPL.UPDATE_URL_STRING_WRAP)).to_be_visible()
    expect(selected_url.locator(HPL.UPDATE_URL_TITLE_WRAP)).to_be_visible()
    # The four sibling option buttons and the go-to-URL icon stay hidden —
    # chrome is only restored when the whole panel closes.
    for sibling_btn in _SIBLING_OPTION_BTNS:
        expect(selected_url.locator(sibling_btn)).to_be_hidden()
    expect(selected_url.locator(HPL.GO_TO_URL_ICON)).to_be_hidden()
    # The full-width Cancel bar stays (the panel-open signal), and the edit
    # button is still morphed away.
    expect(
        selected_url.locator(HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)
    ).to_be_visible()
    expect(selected_url.locator(HPL.BUTTON_URL_STRING_UPDATE)).to_have_count(0)

    # The URL string persisted (href updated even though .urlString is hidden).
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

    # Closing the panel (full-width Cancel) collapses BOTH fields and restores
    # the sibling option buttons and the go-to-URL icon.
    selected_url.locator(HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE).click()
    wait_until_hidden(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE}",
    )
    expect(selected_url.locator(HPL.INPUT_URL_TITLE_UPDATE)).to_be_hidden()
    for sibling_btn in _SIBLING_OPTION_BTNS:
        expect(selected_url.locator(sibling_btn)).to_be_visible()
    expect(selected_url.locator(HPL.GO_TO_URL_ICON)).to_be_visible()


def _bounding_box(*, locator: Locator) -> dict[str, float]:
    box = locator.bounding_box()
    assert box is not None
    return box


def test_url_string_trim_section_in_consolidated_panel_mobile(
    page_mobile_portrait: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests the query-parameter trim control inside the mobile edit panel.

    GIVEN a user has the consolidated edit panel open on a mobile device
    WHEN the user types a URL with two query parameters
    THEN the trim section appears collapsed; expanding it shows both chips inside
        the viewport; dropping one and submitting saves the trimmed string and
        leaves the (kept-open) form's trim section collapsed again
    """
    page = page_mobile_portrait
    app = provide_app
    user_id_for_test = 1
    _, cli_runner = runner
    add_mock_urls(cli_runner, [MOCK_URL_STRINGS[0]])
    utub: Utubs = get_utub_this_user_created(app, user_id=user_id_for_test)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    selected_url = _select_first_url_in_utub_mobile(page=page, app=app, utub_id=utub.id)
    _open_url_edit_panel_mobile(page=page)

    selected_url.locator(HPL.INPUT_URL_STRING_UPDATE).fill(TRIM_URL_TWO_PARAMS)

    header = page.locator(HPL.EDIT_FORM_TRIM_HEADER)
    expect(header).to_be_visible()
    expect(header).to_have_attribute("aria-expanded", "false")
    # The caret is the only open/closed cue; layout.css hides `.title-caret` on mobile.
    expect(page.locator(HPL.EDIT_FORM_TRIM_CARET)).to_be_visible()
    expect(page.locator(HPL.EDIT_FORM_TRIM_CHIP_ACTIONABLE).first).to_be_hidden()
    # Collapsed: the URL field's own green check is the way to save, so the extra
    # Save button beside Close stays hidden.
    save_button = selected_url.locator(HPL.BUTTON_BIG_URL_STRING_SAVE_UPDATE)
    expect(save_button).to_be_hidden()

    # The reserved "Saved" tick row must not become an empty strip above or below
    # the disclosure: with the disclosure showing, the tick stays directly under
    # the input but reserves no height (it fades in over the disclosure row's own
    # top padding), so the disclosure sits right under the input and right above
    # Close with only the small row gaps around it.
    wait_until_vertical_gap(
        page=page,
        upper_selector=HPL.EDIT_FORM_TRIM_HEADER,
        lower_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE}",
        min_px=2,
        max_px=8,
    )
    tick_slot_selector = (
        f"{HPL.ROW_SELECTED_URL} .updateUrlStringWrap .field-saved-tick-slot"
    )
    string_input_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE}"
    wait_until_vertical_gap(
        page=page,
        upper_selector=string_input_selector,
        lower_selector=HPL.EDIT_FORM_TRIM_HEADER,
        min_px=8,
        max_px=12,
    )
    wait_until_vertical_gap(
        page=page,
        upper_selector=string_input_selector,
        lower_selector=tick_slot_selector,
        min_px=3,
        max_px=7,
    )
    header_box = _bounding_box(locator=header)
    tick_slot_box = _bounding_box(locator=page.locator(tick_slot_selector))
    tick_box = _bounding_box(
        locator=selected_url.locator(".updateUrlStringWrap .field-saved-tick")
    )
    assert tick_slot_box["height"] <= 1, "tick slot must not reserve a row"
    assert abs(tick_box["y"] - tick_slot_box["y"]) <= 1, "tick is anchored to the slot"
    # The (faded) tick must clear the disclosure's caret/text (they start ~14px
    # into the 44px header), so it never overlaps them when it shows.
    assert tick_box["y"] + tick_box["height"] <= header_box["y"] + 16

    set_trim_section_expanded(
        page=page, header_selector=HPL.EDIT_FORM_TRIM_HEADER, expanded=True
    )
    chips = page.locator(HPL.EDIT_FORM_TRIM_CHIP_ACTIONABLE)
    expect(chips).to_have_count(2)
    expect(chips.nth(1)).to_be_visible()
    assert page.viewport_size is not None
    viewport_width = page.viewport_size["width"]
    for chip_index in range(2):
        chip_box = _bounding_box(locator=chips.nth(chip_index))
        assert chip_box["x"] >= 0
        assert chip_box["x"] + chip_box["width"] <= viewport_width

    # Open: the "Saves as" preview keeps breathing room above the Close bar, and
    # the Drop all / Keep all shortcuts run shorter than the 44px chip/header
    # targets (the chips themselves are the full-size toggles).
    wait_until_vertical_gap(
        page=page,
        upper_selector=HPL.EDIT_FORM_TRIM_PREVIEW,
        lower_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE}",
        min_px=14,
        max_px=40,
    )
    for bulk_selector in (HPL.TRIM_DROP_ALL, HPL.TRIM_KEEP_ALL):
        bulk_box = _bounding_box(
            locator=page.locator(f"{HPL.ROW_SELECTED_URL} {bulk_selector}")
        )
        assert 30 <= bulk_box["height"] <= 40, (
            f"{bulk_selector}: {bulk_box['height']}px"
        )

    # Open: "Save URL" appears next to Close, on the same row and to its right.
    expect(save_button).to_be_visible()
    expect(save_button).to_have_text("Save URL")
    save_box = _bounding_box(locator=save_button)
    close_bar_box = _bounding_box(
        locator=selected_url.locator(HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)
    )
    assert abs(save_box["y"] - close_bar_box["y"]) <= 2, (
        "Save URL must share Close's row"
    )
    # Spaced like the other option buttons (the row's 15px gap), not wider.
    button_gap = save_box["x"] - (close_bar_box["x"] + close_bar_box["width"])
    assert 13 <= button_gap <= 17, f"Close -> Save URL gap: {button_gap}px"
    assert save_box["x"] + save_box["width"] <= viewport_width

    chips.nth(1).click()
    expect(chips.nth(1)).to_have_attribute("aria-pressed", "false")

    # Saving through the new button follows the same path as the field's check.
    save_button.click()

    expect(selected_url.locator(HPL.URL_STRING_READ)).to_have_attribute(
        HPL.URL_STRING_IN_DATA, TRIM_URL_KEEP_ONLY
    )
    expect(header).to_have_attribute("aria-expanded", "false")

    # The kept-open form shows the saved (trimmed) string until Undo restores the
    # original: the field and the trim block must follow it, not the stale value.
    string_input = selected_url.locator(HPL.INPUT_URL_STRING_UPDATE)
    expect(string_input).to_have_value(TRIM_URL_KEEP_ONLY)
    page.locator(HPL.URL_OUTCOME_BANNER_UNDO).click()
    expect(selected_url.locator(HPL.URL_STRING_READ)).to_have_attribute(
        HPL.URL_STRING_IN_DATA, TRIM_URL_TWO_PARAMS
    )
    expect(string_input).to_have_value(TRIM_URL_TWO_PARAMS)
    expect(page.locator(HPL.EDIT_FORM_TRIM_DROPPED_COUNT)).to_be_hidden()


def _vertical_center(*, locator: Locator) -> float:
    box = _bounding_box(locator=locator)
    return box["y"] + box["height"] / 2


def test_url_edit_panel_field_spacing_and_errored_submit_centering_mobile(
    page_mobile_portrait: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests the consolidated edit panel's vertical rhythm and that each field's
    green check stays centered on its input box when an error message shows.

    GIVEN a user has the consolidated edit panel open on a mobile device
    WHEN the panel is open, then each field is blanked and submitted
    THEN the Title-to-URL gap is the same ~24px as the UTub name-to-description
        gap, and each submit button stays vertically centered on its own input
        (not on the input plus its error message)
    """
    page = page_mobile_portrait
    app = provide_app
    user_id_for_test = 1
    _, cli_runner = runner
    add_mock_urls(cli_runner, [MOCK_URL_STRINGS[0]])
    utub: Utubs = get_utub_this_user_created(app, user_id=user_id_for_test)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub.id
    )
    selected_url = _select_first_url_in_utub_mobile(page=page, app=app, utub_id=utub.id)
    _open_url_edit_panel_mobile(page=page)

    title_input = selected_url.locator(HPL.INPUT_URL_TITLE_UPDATE)
    string_input = selected_url.locator(HPL.INPUT_URL_STRING_UPDATE)

    # The Title and URL inputs (and their check buttons) are the same width and
    # end at the same right edge.
    wait_until_same_width_and_right_edge(
        page=page,
        first_selector=f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_TITLE_UPDATE}",
        second_selector=f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE}",
    )
    title_check_box = selected_url.locator(
        HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE
    ).bounding_box()
    string_check_box = selected_url.locator(
        HPL.BUTTON_URL_STRING_SUBMIT_UPDATE
    ).bounding_box()
    assert title_check_box is not None and string_check_box is not None
    assert abs(title_check_box["x"] - string_check_box["x"]) <= 1, (
        f"check buttons are offset: {title_check_box['x']} vs {string_check_box['x']}"
    )

    wait_until_vertical_gap(
        page=page,
        upper_selector=f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_TITLE_UPDATE}",
        lower_selector=f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE}",
        slot_selector=f"{HPL.ROW_SELECTED_URL} .updateUrlTitleWrap .field-saved-tick-slot",
        min_px=3,
        max_px=5,
    )

    # Without a query string there is no trim disclosure, so the reserved "Saved"
    # row sits directly under the input and the Close bar follows it closely.
    tick_slot_selector = (
        f"{HPL.ROW_SELECTED_URL} .updateUrlStringWrap .field-saved-tick-slot"
    )
    # Polled: the option row's top padding animates for 0.2s after the panel opens.
    wait_until_vertical_gap(
        page=page,
        upper_selector=f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE}",
        lower_selector=tick_slot_selector,
        min_px=0,
        max_px=8,
    )
    wait_until_vertical_gap(
        page=page,
        upper_selector=tick_slot_selector,
        lower_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE}",
        min_px=0,
        max_px=12,
    )

    for input_locator, submit_selector, error_selector in (
        (
            title_input,
            HPL.BUTTON_URL_TITLE_SUBMIT_UPDATE,
            f"{HPL.INPUT_URL_TITLE_UPDATE}-error",
        ),
        (
            string_input,
            HPL.BUTTON_URL_STRING_SUBMIT_UPDATE,
            f"{HPL.INPUT_URL_STRING_UPDATE}-error",
        ),
    ):
        input_locator.fill("")
        submit_button = selected_url.locator(submit_selector)
        submit_button.click()
        expect(selected_url.locator(error_selector)).to_be_visible()
        offset = abs(
            _vertical_center(locator=input_locator)
            - _vertical_center(locator=submit_button.locator("svg"))
        )
        assert offset <= 1.5, f"{submit_selector} is {offset}px off its errored input"


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
