from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.selenium_utils import (
    clear_then_send_keys,
    click_on_navbar,
    wait_then_click_element,
    wait_then_get_at_least_n_elements,
    wait_then_get_element,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)


def _navbar_dropdown_is_open(browser: WebDriver) -> bool:
    dropdown = browser.find_element(By.CSS_SELECTOR, HPL.NAVBAR_DROPDOWN)
    classes = dropdown.get_attribute("class") or ""
    return "show" in classes.split()


def open_cross_search_via_trigger(browser: WebDriver):
    """
    Opens cross-UTub search mode by clicking the navbar trigger.

    The home navbar uses ``navbar-expand-none``, so the trigger lives inside the
    collapsed dropdown and is only reachable after opening the navbar. The
    dropdown may already be open (it stays open behind a prior search overlay),
    so only toggle it open when it is currently collapsed — toggling an
    already-open dropdown would collapse it and re-hide the trigger.
    """
    if not _navbar_dropdown_is_open(browser):
        click_on_navbar(browser)
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
