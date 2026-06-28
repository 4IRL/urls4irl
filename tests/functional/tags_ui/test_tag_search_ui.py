from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.db_utils import (
    add_tag_to_single_url_in_utub,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.selenium_utils import (
    wait_then_click_element,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)
from tests.functional.tags_ui.selenium_utils import (
    get_utub_tag_filter_selector,
    open_tag_name_filter,
    wait_until_tag_sheet_open,
)

pytestmark = pytest.mark.tags_ui

# Tag strings provisioned onto a single URL so the tag deck has matchable rows.
MATCHING_TAG_STRING = "alpha-find-me"
OTHER_TAG_STRING = "beta-other"
# A search term that is a substring of MATCHING_TAG_STRING only (not OTHER_TAG_STRING).
MATCHING_SEARCH_TERM = "alpha"
# A search term that matches no tag in the deck.
NO_MATCH_SEARCH_TERM = "zzzzzz"


def _provision_utub_with_two_tags(app: Flask, user_id: int) -> int:
    """
    Seeds the user's created UTub (already populated with URLs) with two tags
    applied to a URL so the tag deck renders two filterable rows. Returns the
    UTub id.
    """
    utub_user_created = get_utub_this_user_created(app, user_id)
    add_tag_to_single_url_in_utub(
        app, utub_user_created.id, user_id, MATCHING_TAG_STRING
    )
    add_tag_to_single_url_in_utub(app, utub_user_created.id, user_id, OTHER_TAG_STRING)
    return utub_user_created.id


def test_tag_filter_funnel_visible_when_utub_with_tags_selected(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a user selects a UTub that has tags
    WHEN the tag deck renders
    THEN the funnel toggle (#tagNameFilterBtn) is visible while the filter input
         wrap (#SearchTagWrap) stays hidden until the funnel is opened.
    """
    app = provide_app
    user_id_for_test = 1
    utub_id = _provision_utub_with_two_tags(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(app, browser, user_id_for_test, utub_id)

    wait_until_visible_css_selector(browser, HPL.TAG_FILTERS, timeout=3)

    # Before opening: funnel shown, search wrap hidden.
    assert_visible_css_selector(browser, HPL.BUTTON_TAG_NAME_FILTER, time=3)
    assert_not_visible_css_selector(browser, HPL.TAG_SEARCH_WRAP, time=3)

    # Opening the funnel reveals the search input wrap and input.
    input_elem = open_tag_name_filter(browser)
    assert input_elem is not None
    assert_visible_css_selector(browser, HPL.TAG_SEARCH_WRAP, time=3)
    assert_visible_css_selector(browser, HPL.TAG_SEARCH_INPUT, time=3)


def test_tag_filter_togglable_on_mobile(
    browser_mobile_portrait: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a user on a mobile viewport (<992px) selects a UTub with tags
    WHEN the tag deck renders
    THEN the filter input is hidden by default and the funnel reveals it
         (divergence from the UTub filter, which is always-visible on mobile).
    """
    app = provide_app
    user_id_for_test = 1
    utub_id = _provision_utub_with_two_tags(app, user_id_for_test)
    browser = browser_mobile_portrait

    login_user_and_select_utub_by_utubid_mobile(app, browser, user_id_for_test, utub_id)

    # On mobile the tag deck lives in a bottom sheet; open it to reach the funnel.
    wait_then_click_element(browser, HPL.TAG_SHEET_HANDLE, time=3)
    wait_until_tag_sheet_open(browser)

    wait_until_visible_css_selector(browser, HPL.TAG_FILTERS, timeout=3)

    # Mobile: the search wrap is hidden by default; the funnel toggles it (this is
    # the divergence from the UTub filter, which is always-visible on mobile).
    assert_visible_css_selector(browser, HPL.BUTTON_TAG_NAME_FILTER, time=3)
    assert_not_visible_css_selector(browser, HPL.TAG_SEARCH_WRAP, time=3)

    open_tag_name_filter(browser)
    assert_visible_css_selector(browser, HPL.TAG_SEARCH_WRAP, time=3)
    assert_visible_css_selector(browser, HPL.TAG_SEARCH_INPUT, time=3)


def test_typing_substring_hides_non_matching_rows_and_clearing_shows_all(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with two tags is selected and the filter is open
    WHEN the user types a substring matching only one tag, then clears it
    THEN the non-matching row is hidden while matching one stays visible, and
         clearing the term shows all rows again.
    """
    app = provide_app
    user_id_for_test = 1
    utub_id = _provision_utub_with_two_tags(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(app, browser, user_id_for_test, utub_id)

    wait_until_visible_css_selector(browser, HPL.TAG_FILTERS, timeout=3)
    matching_tag = browser.find_element(
        By.XPATH,
        f"//*[contains(@class,'tagFilter')][.//span[text()='{MATCHING_TAG_STRING}']]",
    )
    other_tag = browser.find_element(
        By.XPATH,
        f"//*[contains(@class,'tagFilter')][.//span[text()='{OTHER_TAG_STRING}']]",
    )

    # Before typing: both rows visible.
    assert matching_tag.is_displayed()
    assert other_tag.is_displayed()

    input_elem = open_tag_name_filter(browser)
    input_elem.send_keys(MATCHING_SEARCH_TERM)

    # Matching row stays visible; non-matching row becomes hidden.
    WebDriverWait(browser, 3).until(lambda _: not other_tag.is_displayed())
    assert matching_tag.is_displayed()
    assert not other_tag.is_displayed()

    # Clearing the term shows all rows again. Backspace one key per typed char so
    # each deletion fires an `input` event (a single .clear() does not reliably
    # dispatch `input` across browsers, leaving the filter stale).
    input_elem.send_keys(Keys.BACKSPACE * len(MATCHING_SEARCH_TERM))
    WebDriverWait(browser, 3).until(lambda _: other_tag.is_displayed())
    assert matching_tag.is_displayed()
    assert other_tag.is_displayed()


def test_no_results_message_shown_when_term_matches_no_tags(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with tags is selected and the filter is open
    WHEN the user types a term matching no tag name
    THEN the no-results message (#TagSearchNoResults) is shown with the expected
         text from UTS.TAG_SEARCH_NO_TAGS.
    """
    app = provide_app
    user_id_for_test = 1
    utub_id = _provision_utub_with_two_tags(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(app, browser, user_id_for_test, utub_id)

    wait_until_visible_css_selector(browser, HPL.TAG_FILTERS, timeout=3)

    # Before typing: the no-results message is hidden.
    assert_not_visible_css_selector(browser, HPL.TAG_SEARCH_NO_RESULTS, time=3)

    input_elem = open_tag_name_filter(browser)
    input_elem.send_keys(NO_MATCH_SEARCH_TERM)

    assert_visible_css_selector(browser, HPL.TAG_SEARCH_NO_RESULTS, time=3)
    no_results_elem = browser.find_element(By.CSS_SELECTOR, HPL.TAG_SEARCH_NO_RESULTS)
    assert no_results_elem.text == UTS.TAG_SEARCH_NO_TAGS


def test_text_hidden_selected_tag_still_filters_url_cards(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with a tag applied to one of its two URLs
    WHEN the user selects that tag as a URL filter, then text-hides its row via
         the tag name filter
    THEN the URL-filter contribution persists: the untagged URL stays hidden even
         though the tag row is text-hidden (orthogonality of the two filters).
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id
    tag = add_tag_to_single_url_in_utub(
        app, utub_id, user_id_for_test, MATCHING_TAG_STRING
    )
    tag_id = tag.id

    login_user_and_select_utub_by_utubid(app, browser, user_id_for_test, utub_id)

    wait_until_visible_css_selector(browser, HPL.TAG_FILTERS, timeout=3)

    url_rows = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    # Before selecting the tag filter: more than one URL is visible (the tag is on
    # only one of them, so an unfiltered deck shows multiple).
    visible_before = [row for row in url_rows if row.is_displayed()]
    assert len(visible_before) >= 2

    # (2) Select the tag row to activate it as a URL filter; the untagged URL hides.
    tag_filter_selector = get_utub_tag_filter_selector(tag_id)
    wait_then_click_element(browser, tag_filter_selector, time=3)
    wait_until_visible_css_selector(browser, HPL.ROW_VISIBLE_URL, timeout=3)

    url_rows = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    visible_after_select = [row for row in url_rows if row.is_displayed()]
    assert len(visible_after_select) == 1

    # (3) Open the text filter and type a term that does NOT match this tag's name
    # so its (still-selected) row becomes text-hidden via the .hidden class.
    tag_row = browser.find_element(By.CSS_SELECTOR, tag_filter_selector)
    assert "hidden" not in (tag_row.get_attribute("class") or "")

    input_elem = open_tag_name_filter(browser)
    input_elem.send_keys(NO_MATCH_SEARCH_TERM)

    WebDriverWait(browser, 3).until(
        lambda _: "hidden" in (tag_row.get_attribute("class") or "")
    )
    # The row keeps its .selected URL-filter class even while text-hidden.
    assert "selected" in (tag_row.get_attribute("class") or "")

    # (4) The untagged URL is STILL hidden — the .selected URL-filter contribution
    # persists even while the tag row is text-hidden.
    url_rows = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    visible_after_text_hide = [row for row in url_rows if row.is_displayed()]
    assert len(visible_after_text_hide) == 1


def test_escape_closes_filter_returns_focus_to_funnel_and_clears_term(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with tags is selected and the filter is open with a typed term
    WHEN the user presses ESC
    THEN the filter closes, focus returns to the funnel toggle, and the term is
         cleared.
    """
    app = provide_app
    user_id_for_test = 1
    utub_id = _provision_utub_with_two_tags(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(app, browser, user_id_for_test, utub_id)

    wait_until_visible_css_selector(browser, HPL.TAG_FILTERS, timeout=3)

    input_elem = open_tag_name_filter(browser)
    input_elem.send_keys(MATCHING_SEARCH_TERM)

    # Before ESC: the term is present and the funnel is hidden (X shown instead).
    assert input_elem.get_attribute("value") == MATCHING_SEARCH_TERM
    assert_not_visible_css_selector(browser, HPL.BUTTON_TAG_NAME_FILTER, time=3)

    input_elem.send_keys(Keys.ESCAPE)

    # After ESC: the filter closes, the funnel reappears and regains focus, and the
    # term is cleared.
    assert_visible_css_selector(browser, HPL.BUTTON_TAG_NAME_FILTER, time=3)
    assert_not_visible_css_selector(browser, HPL.TAG_SEARCH_WRAP, time=3)
    wait_until_in_focus(browser, HPL.BUTTON_TAG_NAME_FILTER, timeout=3)

    open_tag_name_filter(browser)
    reopened_input = browser.find_element(By.CSS_SELECTOR, HPL.TAG_SEARCH_INPUT)
    assert reopened_input.get_attribute("value") == ""
