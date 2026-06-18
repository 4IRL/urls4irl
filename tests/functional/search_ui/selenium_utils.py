from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.selenium_utils import (
    clear_then_send_keys,
    wait_then_click_element,
    wait_then_get_at_least_n_elements,
    wait_then_get_element,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)


def open_cross_search_via_trigger(browser: WebDriver):
    """
    Opens cross-UTub search mode by clicking the navbar trigger.

    The trigger is a standalone icon button inline next to the hamburger (outside
    the collapsed dropdown), so it is directly clickable on every viewport without
    first opening the navbar menu.
    """
    wait_until_visible_css_selector(browser, HPL.CROSS_SEARCH_TRIGGER, timeout=10)
    wait_then_click_element(browser, HPL.CROSS_SEARCH_TRIGGER, time=10)
    wait_until_visible_css_selector(browser, HPL.CROSS_SEARCH_INPUT, timeout=10)
    wait_until_in_focus(browser, HPL.CROSS_SEARCH_INPUT)


def open_cross_search_via_shortcut(browser: WebDriver):
    """
    Opens cross-UTub search mode via the Cmd/Ctrl+K shortcut.

    The shortcut handler ignores the keystroke when the active element is an
    INPUT/TEXTAREA, so the combo is delivered to <body>. Chrome in the Selenium
    grid is Ctrl-based; the handler accepts either metaKey or ctrlKey.
    """
    body = browser.find_element(By.TAG_NAME, "body")
    body.click()
    body.send_keys(Keys.CONTROL + "k")
    wait_until_visible_css_selector(browser, HPL.CROSS_SEARCH_INPUT, timeout=10)
    wait_until_in_focus(browser, HPL.CROSS_SEARCH_INPUT)


def open_cross_search_settings(browser: WebDriver):
    """Opens the search-options modal via the gear button and waits for it to show."""
    wait_then_click_element(browser, HPL.CROSS_SEARCH_SETTINGS_BTN, time=10)
    wait_until_visible_css_selector(
        browser, HPL.CROSS_SEARCH_SETTINGS_MODAL, timeout=10
    )


def type_cross_search_query(browser: WebDriver, term: str):
    """Focuses the cross-search input and types the given query term."""
    wait_until_in_focus(browser, HPL.CROSS_SEARCH_INPUT)
    search_input = wait_then_get_element(browser, HPL.CROSS_SEARCH_INPUT, time=10)
    assert search_input is not None
    clear_then_send_keys(search_input, term)


def wait_for_cross_search_results(browser: WebDriver, timeout: float = 10):
    """
    Blocks until at least one result card is present in the DOM.

    The debounced fetch makes a bare send-keys-then-assert flake; gate on the
    live count of ``.crossSearchHitCard`` settling to >=1 before asserting.
    """
    cards = wait_then_get_at_least_n_elements(
        browser, HPL.CROSS_SEARCH_HIT_CARD, 1, time=timeout
    )
    assert len(cards) >= 1
    return cards


def wait_for_cross_search_no_results(browser: WebDriver, timeout: int = 10):
    """Blocks until the distinct no-results message is visible."""
    wait_until_visible_css_selector(
        browser, HPL.CROSS_SEARCH_NO_RESULTS, timeout=timeout
    )


def wait_for_cross_search_history(browser: WebDriver, timeout: int = 10):
    """Blocks until the recent-searches history list is visible."""
    wait_until_visible_css_selector(
        browser, HPL.CROSS_SEARCH_HISTORY_LIST, timeout=timeout
    )


def wait_for_cross_search_group_count(
    browser: WebDriver, minimum_count: int, timeout: float = 10
):
    """Blocks until at least ``minimum_count`` result group sections are present."""
    return wait_then_get_at_least_n_elements(
        browser, HPL.CROSS_SEARCH_GROUP, minimum_count, time=timeout
    )
