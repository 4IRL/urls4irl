from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.db_utils import create_test_cross_utub_searchable_data
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import login_user_to_home_page
from tests.functional.search_ui.selenium_utils import (
    open_cross_search_via_shortcut,
    open_cross_search_via_trigger,
    type_cross_search_query,
    wait_for_cross_search_group_count,
    wait_for_cross_search_history,
    wait_for_cross_search_no_results,
    wait_for_cross_search_results,
)
from tests.functional.selenium_utils import (
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
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


def _login(app: Flask, browser: WebDriver):
    login_user_to_home_page(app, browser, USER_ID_FOR_TEST)
    # The cross-search trigger only un-hides once initCrossUtubSearch() runs and
    # the synchronously-loaded UTub state is non-empty; wait for the UTub deck to
    # have rendered selectors so the module has initialized.
    wait_until_visible_css_selector(browser, HPL.SELECTORS_UTUB, timeout=10)


def test_trigger_opens_cross_search_and_focuses_input(
    browser: WebDriver, logged_in_with_cross_search_data
):
    """
    GIVEN a logged-in user with >=1 UTub
    WHEN they click the navbar cross-search trigger
    THEN search mode becomes visible and the input is focused
    """
    app, _ = logged_in_with_cross_search_data
    _login(app, browser)

    open_cross_search_via_trigger(browser)

    assert_visible_css_selector(browser, HPL.CROSS_SEARCH_MODE, time=10)
    wait_until_in_focus(browser, HPL.CROSS_SEARCH_INPUT)


def test_shortcut_opens_cross_search_and_focuses_input(
    browser: WebDriver, logged_in_with_cross_search_data
):
    """
    GIVEN a logged-in user with >=1 UTub
    WHEN they press Cmd/Ctrl+K
    THEN search mode becomes visible and the input is focused
    """
    app, _ = logged_in_with_cross_search_data
    _login(app, browser)

    open_cross_search_via_shortcut(browser)

    assert_visible_css_selector(browser, HPL.CROSS_SEARCH_MODE, time=10)
    wait_until_in_focus(browser, HPL.CROSS_SEARCH_INPUT)


def test_typing_shows_grouped_results_across_utubs(
    browser: WebDriver, logged_in_with_cross_search_data
):
    """
    GIVEN search mode open and two UTubs each holding a matching URL
    WHEN the user types the shared query term
    THEN >=2 grouped result sections render, each with >=1 hit card
    """
    app, _ = logged_in_with_cross_search_data
    _login(app, browser)

    open_cross_search_via_trigger(browser)
    type_cross_search_query(browser, QUERY_TERM)

    wait_for_cross_search_results(browser)
    groups = wait_for_cross_search_group_count(browser, 2)
    assert len(groups) >= 2


def test_clicking_result_navigates_to_source_utub_and_highlights_card(
    browser: WebDriver, logged_in_with_cross_search_data
):
    """
    GIVEN grouped results are showing
    WHEN the user clicks a result card
    THEN search mode closes, the LHS is restored, the source UTub is selected,
        and the matched URL card is highlighted
    """
    app, seeded = logged_in_with_cross_search_data
    _login(app, browser)

    open_cross_search_via_trigger(browser)
    type_cross_search_query(browser, QUERY_TERM)
    wait_for_cross_search_results(browser)

    first_card = wait_then_get_element(browser, HPL.CROSS_SEARCH_HIT_CARD, time=10)
    assert first_card is not None
    target_utub_id = first_card.get_attribute("data-utub-id")
    target_utub_url_id = first_card.get_attribute("data-utub-url-id")
    assert target_utub_id is not None
    assert target_utub_url_id is not None
    first_card.click()

    # Search mode closes and the LHS (UTub deck) is restored.
    wait_until_hidden(browser, HPL.CROSS_SEARCH_MODE, timeout=10)
    wait_until_visible_css_selector(browser, HPL.UTUB_DECK, timeout=10)

    # The source UTub is now the active selector.
    active_selector = wait_then_get_element(
        browser, f"{HPL.SELECTORS_UTUB}.active[utubid='{target_utub_id}']", time=10
    )
    assert active_selector is not None

    # The matched URL card is selected/highlighted in the URL deck.
    selected_card = wait_then_get_element(
        browser,
        f"{HPL.ROWS_URLS}[utuburlid='{target_utub_url_id}'][urlselected='true']",
        time=10,
    )
    assert selected_card is not None


def test_no_results_shows_distinct_message(
    browser: WebDriver, logged_in_with_cross_search_data
):
    """
    GIVEN search mode open
    WHEN the user types a term that matches nothing
    THEN the distinct no-results message is shown
    """
    app, _ = logged_in_with_cross_search_data
    _login(app, browser)

    open_cross_search_via_trigger(browser)
    type_cross_search_query(browser, NO_MATCH_TERM)

    wait_for_cross_search_no_results(browser)
    no_results = wait_then_get_element(browser, HPL.CROSS_SEARCH_NO_RESULTS, time=10)
    assert no_results is not None
    assert UTS.CROSS_SEARCH_NO_RESULTS_TEXT in no_results.text


def test_deselecting_tag_field_still_yields_results(
    browser: WebDriver, logged_in_with_cross_search_data
):
    """
    GIVEN results are showing for a term matching via title AND url
    WHEN the user deselects the 'tag' field
    THEN the debounced fetch re-runs and >=1 result still renders
    """
    app, _ = logged_in_with_cross_search_data
    _login(app, browser)

    open_cross_search_via_trigger(browser)
    type_cross_search_query(browser, QUERY_TERM)
    wait_for_cross_search_results(browser)

    tag_checkbox_selector = (
        f"{HPL.CROSS_SEARCH_FIELD_CONTROLS} "
        ".crossSearchFieldRow[data-field='tag'] .crossSearchFieldInclude"
    )
    wait_then_click_element(browser, tag_checkbox_selector, time=10)

    # Field change re-triggers the debounced fetch; gate on results settling.
    wait_for_cross_search_results(browser)
    groups = wait_for_cross_search_group_count(browser, 2)
    assert len(groups) >= 2


def test_reordering_fields_keeps_results(
    browser: WebDriver, logged_in_with_cross_search_data
):
    """
    GIVEN results are showing
    WHEN the user reorders fields (title-first)
    THEN the debounced fetch re-runs and results still render
    """
    app, _ = logged_in_with_cross_search_data
    _login(app, browser)

    open_cross_search_via_trigger(browser)
    type_cross_search_query(browser, QUERY_TERM)
    wait_for_cross_search_results(browser)

    title_up_selector = (
        f"{HPL.CROSS_SEARCH_FIELD_CONTROLS} "
        ".crossSearchFieldRow[data-field='title'] .crossSearchFieldUp"
    )
    wait_then_click_element(browser, title_up_selector, time=10)

    wait_for_cross_search_results(browser)
    groups = wait_for_cross_search_group_count(browser, 2)
    assert len(groups) >= 2


def test_escape_closes_cross_search(
    browser: WebDriver, logged_in_with_cross_search_data
):
    """
    GIVEN search mode is open with the input focused
    WHEN the user presses Escape
    THEN search mode closes
    """
    app, _ = logged_in_with_cross_search_data
    _login(app, browser)

    open_cross_search_via_trigger(browser)
    # Focus the input before sending ESC so the keydown lands on a focused
    # element (per the flake-hardening rule).
    wait_until_in_focus(browser, HPL.CROSS_SEARCH_INPUT)
    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    wait_until_hidden(browser, HPL.CROSS_SEARCH_MODE, timeout=10)
    assert_not_visible_css_selector(browser, HPL.CROSS_SEARCH_MODE, time=10)


def test_cross_search_input_is_usable_width_on_mobile(
    browser_mobile_portrait: WebDriver, logged_in_with_cross_search_data
):
    """
    GIVEN a logged-in user on a narrow (mobile) viewport
    WHEN they open cross-UTub search mode
    THEN the search input is laid out full-width on its own row rather than being
        squeezed toward zero width by the inline field controls sharing its row
    """
    browser = browser_mobile_portrait
    app, _ = logged_in_with_cross_search_data
    _login(app, browser)

    open_cross_search_via_trigger(browser)
    assert_visible_css_selector(browser, HPL.CROSS_SEARCH_MODE, time=10)

    search_input = wait_then_get_element(browser, HPL.CROSS_SEARCH_INPUT, time=10)
    assert search_input is not None
    # Pre-fix the input collapsed to ~28px on a 420px-wide viewport. A usable
    # full-width input is far wider; assert a generous floor well above the break.
    assert search_input.size["width"] >= MOBILE_INPUT_MIN_WIDTH_PX
    # Touch-target height floor for the input on mobile.
    assert search_input.size["height"] >= MOBILE_TOUCH_TARGET_MIN_PX


def test_close_button_closes_cross_search(
    browser: WebDriver, logged_in_with_cross_search_data
):
    """
    GIVEN search mode is open
    WHEN the user clicks the close (X) button
    THEN search mode closes
    """
    app, _ = logged_in_with_cross_search_data
    _login(app, browser)

    open_cross_search_via_trigger(browser)
    wait_then_click_element(browser, HPL.CROSS_SEARCH_CLOSE, time=10)

    wait_until_hidden(browser, HPL.CROSS_SEARCH_MODE, timeout=10)
    assert_not_visible_css_selector(browser, HPL.CROSS_SEARCH_MODE, time=10)


def test_recent_search_history_renders_reruns_and_clears(
    browser: WebDriver, logged_in_with_cross_search_data
):
    """
    GIVEN the user performs a search then closes and re-opens search mode
    WHEN the input is empty
    THEN the recent-searches history list renders with the prior query,
        clicking the history row re-runs the search, and clicking clear
        removes the history list
    """
    app, _ = logged_in_with_cross_search_data
    _login(app, browser)

    # Perform a search so an entry lands in history.
    open_cross_search_via_trigger(browser)
    type_cross_search_query(browser, QUERY_TERM)
    wait_for_cross_search_results(browser)

    # Close and re-open with an empty input.
    wait_then_click_element(browser, HPL.CROSS_SEARCH_CLOSE, time=10)
    wait_until_hidden(browser, HPL.CROSS_SEARCH_MODE, timeout=10)

    open_cross_search_via_trigger(browser)
    wait_for_cross_search_history(browser)

    history_row = wait_then_get_element(browser, HPL.CROSS_SEARCH_HISTORY_ROW, time=10)
    assert history_row is not None
    assert QUERY_TERM in history_row.text

    # Clicking the history row re-runs the saved search.
    history_row.click()
    wait_for_cross_search_results(browser)

    # Re-open empty again and clear the history.
    wait_then_click_element(browser, HPL.CROSS_SEARCH_CLOSE, time=10)
    wait_until_hidden(browser, HPL.CROSS_SEARCH_MODE, timeout=10)

    open_cross_search_via_trigger(browser)
    wait_for_cross_search_history(browser)
    wait_then_click_element(browser, HPL.CROSS_SEARCH_HISTORY_CLEAR, time=10)

    # The history list element is removed from the DOM.
    assert (
        len(browser.find_elements(By.CSS_SELECTOR, HPL.CROSS_SEARCH_HISTORY_LIST)) == 0
    )
