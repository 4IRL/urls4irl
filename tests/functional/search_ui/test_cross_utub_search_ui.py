from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import create_test_cross_utub_searchable_data
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_utils import (
    clear_then_send_keys,
    login_user_to_home_page,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)
from tests.functional.search_ui.playwright_utils import (
    open_cross_search_settings,
    open_cross_search_via_shortcut,
    open_cross_search_via_trigger,
    type_cross_search_query,
    wait_for_cross_search_group_count,
    wait_for_cross_search_history,
    wait_for_cross_search_no_results,
    wait_for_cross_search_results,
)

pytestmark = pytest.mark.search_ui

USER_ID_FOR_TEST = 1
QUERY_TERM = UTS.CROSS_SEARCH_QUERY_TERM
NO_MATCH_TERM = UTS.CROSS_SEARCH_NO_MATCH_TERM
# Floor for the mobile search-input rendered width: comfortably above the broken
# ~28px single-row collapse, but below the ~388px a full-width input yields on the
# 420px mobile-portrait viewport, leaving slack for padding/rounding.
MOBILE_INPUT_MIN_WIDTH_PX = 200
# 44px (2.75rem) minimum touch-target dimension.
MOBILE_TOUCH_TARGET_MIN_PX = 44


@pytest.fixture
def logged_in_with_cross_search_data(create_test_users, provide_app: Flask):
    """Seeds the two-UTub cross-search scenario and logs the user into /home."""
    app = provide_app
    seeded = create_test_cross_utub_searchable_data(app, USER_ID_FOR_TEST)
    yield app, seeded


def _login(*, app: Flask, page: Page) -> None:
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    # The cross-search trigger only un-hides once initCrossUtubSearch() runs and
    # the synchronously-loaded UTub state is non-empty; wait for the UTub deck to
    # have rendered selectors so the module has initialized.
    wait_until_visible_css_selector(page=page, css_selector=HPL.SELECTORS_UTUB)


def test_trigger_opens_cross_search_and_focuses_input(
    page: Page, logged_in_with_cross_search_data
):
    """
    GIVEN a logged-in user with >=1 UTub
    WHEN they click the navbar cross-search trigger
    THEN search mode becomes visible and the input is focused
    """
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    open_cross_search_via_trigger(page=page)

    expect(page.locator(HPL.CROSS_SEARCH_MODE).first).to_be_visible()
    wait_until_in_focus(page=page, css_selector=HPL.CROSS_SEARCH_INPUT)


def test_shortcut_opens_cross_search_and_focuses_input(
    page: Page, logged_in_with_cross_search_data
):
    """
    GIVEN a logged-in user with >=1 UTub
    WHEN they press Cmd/Ctrl+K
    THEN search mode becomes visible and the input is focused
    """
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    open_cross_search_via_shortcut(page=page)

    expect(page.locator(HPL.CROSS_SEARCH_MODE).first).to_be_visible()
    wait_until_in_focus(page=page, css_selector=HPL.CROSS_SEARCH_INPUT)


def test_typing_shows_grouped_results_across_utubs(
    page: Page, logged_in_with_cross_search_data
):
    """
    GIVEN search mode open and two UTubs each holding a matching URL
    WHEN the user types the shared query term
    THEN >=2 grouped result sections render, each with >=1 hit card
    """
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    open_cross_search_via_trigger(page=page)
    type_cross_search_query(page=page, term=QUERY_TERM)

    wait_for_cross_search_results(page=page)
    groups = wait_for_cross_search_group_count(page=page, minimum_count=2)
    assert len(groups) >= 2


def test_clicking_result_navigates_to_source_utub_and_highlights_card(
    page: Page, logged_in_with_cross_search_data
):
    """
    GIVEN grouped results are showing
    WHEN the user clicks a result card
    THEN search mode closes, the LHS is restored, the source UTub is selected,
        and the matched URL card is highlighted
    """
    app, seeded = logged_in_with_cross_search_data
    _login(app=app, page=page)

    open_cross_search_via_trigger(page=page)
    type_cross_search_query(page=page, term=QUERY_TERM)
    wait_for_cross_search_results(page=page)

    first_card = wait_then_get_element(
        page=page, css_selector=HPL.CROSS_SEARCH_HIT_CARD
    )
    target_utub_id = first_card.get_attribute("data-utub-id")
    target_utub_url_id = first_card.get_attribute("data-utub-url-id")
    assert target_utub_id is not None
    assert target_utub_url_id is not None
    first_card.click()

    # Search mode closes and the LHS (UTub deck) is restored.
    wait_until_hidden(page=page, css_selector=HPL.CROSS_SEARCH_MODE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.UTUB_DECK)

    # The source UTub is now the active selector.
    active_selector = wait_then_get_element(
        page=page,
        css_selector=f"{HPL.SELECTORS_UTUB}.active[utubid='{target_utub_id}']",
    )
    assert active_selector is not None

    # The matched URL card is selected/highlighted in the URL deck.
    selected_card = wait_then_get_element(
        page=page,
        css_selector=f"{HPL.ROWS_URLS}[utuburlid='{target_utub_url_id}'][urlselected='true']",
    )
    assert selected_card is not None


def test_browser_back_after_result_click_restores_search_results(
    page: Page, logged_in_with_cross_search_data
):
    """
    GIVEN the user searched, then clicked a result card and landed in the source
        UTub
    WHEN they press the browser Back button
    THEN cross-UTub search mode re-opens with the prior query and the grouped
        results render again; pressing Back once more leaves search for /home
    """
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    open_cross_search_via_trigger(page=page)
    type_cross_search_query(page=page, term=QUERY_TERM)
    wait_for_cross_search_results(page=page)

    first_card = wait_then_get_element(
        page=page, css_selector=HPL.CROSS_SEARCH_HIT_CARD
    )
    first_card.click()

    # Landed in the source UTub: search closed, the UTub deck (LHS) restored.
    wait_until_hidden(page=page, css_selector=HPL.CROSS_SEARCH_MODE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.UTUB_DECK)

    # Browser Back returns to the search results (re-running the query).
    page.go_back()
    wait_until_visible_css_selector(page=page, css_selector=HPL.CROSS_SEARCH_MODE)
    restored_input = wait_then_get_element(
        page=page, css_selector=HPL.CROSS_SEARCH_INPUT
    )
    expect(restored_input).to_have_value(QUERY_TERM)
    wait_for_cross_search_results(page=page)

    # Backing past the search entry leaves search mode (a non-search history
    # entry exits the overlay rather than stranding it open).
    page.go_back()
    wait_until_hidden(page=page, css_selector=HPL.CROSS_SEARCH_MODE)
    expect(page.locator(HPL.CROSS_SEARCH_MODE).first).to_be_hidden()


def test_no_results_shows_distinct_message(
    page: Page, logged_in_with_cross_search_data
):
    """
    GIVEN search mode open
    WHEN the user types a term that matches nothing
    THEN the distinct no-results message is shown
    """
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    open_cross_search_via_trigger(page=page)
    type_cross_search_query(page=page, term=NO_MATCH_TERM)

    wait_for_cross_search_no_results(page=page)
    no_results = wait_then_get_element(
        page=page, css_selector=HPL.CROSS_SEARCH_NO_RESULTS
    )
    assert no_results is not None
    expect(no_results).to_contain_text(UTS.CROSS_SEARCH_NO_RESULTS_TEXT)


def test_deselecting_tag_field_still_yields_results(
    page: Page, logged_in_with_cross_search_data
):
    """
    GIVEN results are showing for a term matching via title AND url
    WHEN the user deselects the 'tag' field
    THEN the search re-runs and >=1 result still renders
    """
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    open_cross_search_via_trigger(page=page)
    type_cross_search_query(page=page, term=QUERY_TERM)
    wait_for_cross_search_results(page=page)

    open_cross_search_settings(page=page)

    tag_checkbox_selector = (
        f"{HPL.CROSS_SEARCH_FIELD_CONTROLS} "
        ".crossSearchFieldRow[data-field='tag'] .crossSearchFieldInclude"
    )
    wait_then_click_element(page=page, css_selector=tag_checkbox_selector)

    # Field change re-runs the search; gate on results settling.
    wait_for_cross_search_results(page=page)
    groups = wait_for_cross_search_group_count(page=page, minimum_count=2)
    assert len(groups) >= 2


def test_reordering_fields_keeps_results(page: Page, logged_in_with_cross_search_data):
    """
    GIVEN results are showing
    WHEN the user reorders fields (title-first)
    THEN the search re-runs and results still render
    """
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    open_cross_search_via_trigger(page=page)
    type_cross_search_query(page=page, term=QUERY_TERM)
    wait_for_cross_search_results(page=page)

    open_cross_search_settings(page=page)

    title_up_selector = (
        f"{HPL.CROSS_SEARCH_FIELD_CONTROLS} "
        ".crossSearchFieldRow[data-field='title'] .crossSearchFieldUp"
    )
    wait_then_click_element(page=page, css_selector=title_up_selector)

    wait_for_cross_search_results(page=page)
    groups = wait_for_cross_search_group_count(page=page, minimum_count=2)
    assert len(groups) >= 2


def test_escape_closes_cross_search(page: Page, logged_in_with_cross_search_data):
    """
    GIVEN search mode is open with the input focused
    WHEN the user presses Escape
    THEN search mode closes
    """
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    open_cross_search_via_trigger(page=page)
    # Focus the input before sending ESC so the keydown lands on a focused
    # element (per the flake-hardening rule).
    wait_until_in_focus(page=page, css_selector=HPL.CROSS_SEARCH_INPUT)
    page.keyboard.press("Escape")

    wait_until_hidden(page=page, css_selector=HPL.CROSS_SEARCH_MODE)
    expect(page.locator(HPL.CROSS_SEARCH_MODE).first).to_be_hidden()


def test_cross_search_input_is_usable_width_on_mobile(
    page_mobile_portrait: Page, logged_in_with_cross_search_data
):
    """
    GIVEN a logged-in user on a narrow (mobile) viewport
    WHEN they open cross-UTub search mode
    THEN the search input is laid out full-width on its own row rather than being
        squeezed toward zero width by the inline field controls sharing its row
    """
    page = page_mobile_portrait
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    open_cross_search_via_trigger(page=page)
    expect(page.locator(HPL.CROSS_SEARCH_MODE).first).to_be_visible()

    search_input = wait_then_get_element(page=page, css_selector=HPL.CROSS_SEARCH_INPUT)
    bounding_box = search_input.bounding_box()
    assert bounding_box is not None
    # Pre-fix the input collapsed to ~28px on a 420px-wide viewport. A usable
    # full-width input is far wider; assert a generous floor well above the break.
    assert bounding_box["width"] >= MOBILE_INPUT_MIN_WIDTH_PX
    # Touch-target height floor for the input on mobile.
    assert bounding_box["height"] >= MOBILE_TOUCH_TARGET_MIN_PX


def test_trigger_morphs_to_close_glyph_while_open(
    page: Page, logged_in_with_cross_search_data
):
    """
    GIVEN the navbar search trigger shows the magnifying glass when closed
    WHEN search mode opens
    THEN the trigger swaps to the close (glass-with-X) glyph, and reverts to the
        search glyph once search closes
    """
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    # Closed: open glyph visible, close glyph hidden.
    expect(page.locator(HPL.CROSS_SEARCH_TRIGGER_OPEN_ICON).first).to_be_visible()
    expect(page.locator(HPL.CROSS_SEARCH_TRIGGER_CLOSE_ICON).first).to_be_hidden()

    open_cross_search_via_trigger(page=page)

    # Open: morphed to the close glyph.
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.CROSS_SEARCH_TRIGGER_CLOSE_ICON
    )
    expect(page.locator(HPL.CROSS_SEARCH_TRIGGER_OPEN_ICON).first).to_be_hidden()

    # Close via Escape and confirm the glyph reverts.
    wait_until_in_focus(page=page, css_selector=HPL.CROSS_SEARCH_INPUT)
    page.keyboard.press("Escape")
    wait_until_hidden(page=page, css_selector=HPL.CROSS_SEARCH_MODE)
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.CROSS_SEARCH_TRIGGER_OPEN_ICON
    )
    expect(page.locator(HPL.CROSS_SEARCH_TRIGGER_CLOSE_ICON).first).to_be_hidden()


def test_submit_button_runs_search(page: Page, logged_in_with_cross_search_data):
    """
    GIVEN search mode is open with a typed query
    WHEN the user clicks the submit button (rather than pressing Enter)
    THEN the search runs and grouped results render
    """
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    open_cross_search_via_trigger(page=page)

    search_input = wait_then_get_element(page=page, css_selector=HPL.CROSS_SEARCH_INPUT)
    clear_then_send_keys(locator=search_input, input_text=QUERY_TERM)

    wait_then_click_element(page=page, css_selector=HPL.CROSS_SEARCH_SUBMIT)
    wait_for_cross_search_results(page=page)


def test_submit_button_morphs_to_refresh_and_re_runs(
    page: Page, logged_in_with_cross_search_data
):
    """
    GIVEN search mode is open and a query has been submitted, returning results
    WHEN the submit button morphs to the Refresh glyph
    THEN clicking it re-runs the unchanged query and results still render
    """
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    open_cross_search_via_trigger(page=page)
    type_cross_search_query(page=page, term=QUERY_TERM)
    wait_for_cross_search_results(page=page)

    # With the query unchanged since submit, the button shows the Refresh glyph
    # (the search glyph is hidden via the `.hidden` display:none class).
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.CROSS_SEARCH_REFRESH_ICON
    )
    expect(page.locator(HPL.CROSS_SEARCH_SUBMIT_ICON).first).to_be_hidden()

    # Clicking Refresh re-runs the same query; results still render.
    wait_then_click_element(page=page, css_selector=HPL.CROSS_SEARCH_SUBMIT)
    wait_for_cross_search_results(page=page)


def test_clear_button_clears_input_text(page: Page, logged_in_with_cross_search_data):
    """
    GIVEN search mode is open with a typed query showing results
    WHEN the user clicks the in-input clear (circle-×) button
    THEN the input text is cleared and the clear button hides again
    """
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    open_cross_search_via_trigger(page=page)
    type_cross_search_query(page=page, term=QUERY_TERM)
    wait_for_cross_search_results(page=page)

    # The clear button is visible once the input has text.
    expect(page.locator(HPL.CROSS_SEARCH_CLEAR_INPUT).first).to_be_visible()

    wait_then_click_element(page=page, css_selector=HPL.CROSS_SEARCH_CLEAR_INPUT)

    # The input is now empty and the clear button is hidden again.
    cleared_input = wait_then_get_element(
        page=page, css_selector=HPL.CROSS_SEARCH_INPUT
    )
    expect(cleared_input).to_have_value("")
    expect(page.locator(HPL.CROSS_SEARCH_CLEAR_INPUT).first).to_be_hidden()


def test_trigger_toggles_search_closed(page: Page, logged_in_with_cross_search_data):
    """
    GIVEN search mode is open
    WHEN the user taps the navbar search trigger again
    THEN search mode closes (the trigger toggles open/closed)
    """
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    open_cross_search_via_trigger(page=page)
    expect(page.locator(HPL.CROSS_SEARCH_MODE).first).to_be_visible()

    wait_then_click_element(page=page, css_selector=HPL.CROSS_SEARCH_TRIGGER)
    wait_until_hidden(page=page, css_selector=HPL.CROSS_SEARCH_MODE)
    expect(page.locator(HPL.CROSS_SEARCH_MODE).first).to_be_hidden()


def test_closing_search_on_mobile_restores_left_panel(
    page_mobile_portrait: Page, logged_in_with_cross_search_data
):
    """
    GIVEN search mode is open on a mobile viewport with no UTub selected
    WHEN the user closes search via the navbar trigger
    THEN the left panel (UTub deck) is shown again rather than an empty screen
    """
    page = page_mobile_portrait
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    open_cross_search_via_trigger(page=page)
    expect(page.locator(HPL.CROSS_SEARCH_MODE).first).to_be_visible()

    wait_then_click_element(page=page, css_selector=HPL.CROSS_SEARCH_TRIGGER)
    wait_until_hidden(page=page, css_selector=HPL.CROSS_SEARCH_MODE)

    expect(page.locator(HPL.HEADER_UTUB_DECK).first).to_be_visible()


def test_return_home_in_hamburger_closes_search(
    page_mobile_portrait: Page, logged_in_with_cross_search_data
):
    """
    GIVEN search mode is open on a mobile viewport
    WHEN the user opens the hamburger dropdown and taps "Return Home"
    THEN search mode closes and the left panel (UTub deck) is restored
    """
    page = page_mobile_portrait
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    open_cross_search_via_trigger(page=page)
    expect(page.locator(HPL.CROSS_SEARCH_MODE).first).to_be_visible()

    # The Return Home item only surfaces while search is open; open the hamburger
    # and click it.
    wait_then_click_element(page=page, css_selector=HPL.NAVBAR_TOGGLER)
    wait_then_click_element(page=page, css_selector=HPL.NAV_RETURN_HOME)

    wait_until_hidden(page=page, css_selector=HPL.CROSS_SEARCH_MODE)
    expect(page.locator(HPL.HEADER_UTUB_DECK).first).to_be_visible()


def test_recent_search_history_renders_reruns_and_clears(
    page: Page, logged_in_with_cross_search_data
):
    """
    GIVEN the user performs a search then closes and re-opens search mode
    WHEN the input is empty
    THEN the recent-searches history list renders with the prior query,
        clicking the history row re-runs the search, and clicking clear
        removes the history list
    """
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    # Perform a search so an entry lands in history.
    open_cross_search_via_trigger(page=page)
    type_cross_search_query(page=page, term=QUERY_TERM)
    wait_for_cross_search_results(page=page)

    # Close and re-open with an empty input.
    wait_then_click_element(page=page, css_selector=HPL.CROSS_SEARCH_TRIGGER)
    wait_until_hidden(page=page, css_selector=HPL.CROSS_SEARCH_MODE)

    open_cross_search_via_trigger(page=page)
    wait_for_cross_search_history(page=page)

    history_row = wait_then_get_element(
        page=page, css_selector=HPL.CROSS_SEARCH_HISTORY_ROW
    )
    expect(history_row).to_contain_text(QUERY_TERM)

    # Clicking the history row re-runs the saved search.
    history_row.click()
    wait_for_cross_search_results(page=page)

    # Re-open empty again and clear the history.
    wait_then_click_element(page=page, css_selector=HPL.CROSS_SEARCH_TRIGGER)
    wait_until_hidden(page=page, css_selector=HPL.CROSS_SEARCH_MODE)

    open_cross_search_via_trigger(page=page)
    wait_for_cross_search_history(page=page)
    wait_then_click_element(page=page, css_selector=HPL.CROSS_SEARCH_HISTORY_CLEAR)

    # The history list element is removed from the DOM.
    expect(page.locator(HPL.CROSS_SEARCH_HISTORY_LIST)).to_have_count(0)


def test_deleting_a_recent_search_removes_it(
    page: Page, logged_in_with_cross_search_data
):
    """
    GIVEN the user performs a search then closes and re-opens search mode
    WHEN they click the per-row trash button for the only recent search
    THEN that entry is removed and, being the last one, the history list is gone
    """
    app, _ = logged_in_with_cross_search_data
    _login(app=app, page=page)

    # Perform a search so an entry lands in history.
    open_cross_search_via_trigger(page=page)
    type_cross_search_query(page=page, term=QUERY_TERM)
    wait_for_cross_search_results(page=page)

    # Close and re-open with an empty input to surface the history list.
    wait_then_click_element(page=page, css_selector=HPL.CROSS_SEARCH_TRIGGER)
    wait_until_hidden(page=page, css_selector=HPL.CROSS_SEARCH_MODE)

    open_cross_search_via_trigger(page=page)
    wait_for_cross_search_history(page=page)

    history_row = wait_then_get_element(
        page=page, css_selector=HPL.CROSS_SEARCH_HISTORY_ROW
    )
    assert history_row is not None

    # Click the per-row trash button for the only row.
    wait_then_click_element(page=page, css_selector=HPL.CROSS_SEARCH_HISTORY_DELETE)

    # It was the last entry, so the whole history list is removed from the DOM.
    expect(page.locator(HPL.CROSS_SEARCH_HISTORY_LIST)).to_have_count(0)
