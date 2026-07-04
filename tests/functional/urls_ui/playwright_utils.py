import re

from playwright.sync_api import Page, expect

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_utils import (
    wait_then_get_element,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)


def focus_url_search_input(*, page: Page) -> None:
    """Focuses the always-visible URL search input (desktop flow)."""
    expect(page.locator(HPL.URL_SEARCH_WRAP).first).to_have_class(
        re.compile(r"(^|\s)search-ready(\s|$)")
    )
    wait_until_visible_css_selector(page=page, css_selector=HPL.URL_SEARCH_INPUT)
    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)
    search_input.click()
    wait_until_in_focus(page=page, css_selector=HPL.URL_SEARCH_INPUT)


def wait_for_url_search_filter_applied(*, page: Page) -> None:
    """Wait until the URL search handler has updated the DOM.

    After typing into the search input, the handler (possibly debounced)
    sets a ``searchable`` attribute on every visible filterable URL row;
    block until all such rows carry the attribute, confirming the search
    filter cycle has completed."""
    page.wait_for_function(
        """(visibleRowSelector) => {
            const rows = Array.from(document.querySelectorAll(visibleRowSelector));
            if (rows.length === 0) return false;
            return rows.every((row) => row.getAttribute("searchable") !== null);
        }""",
        arg=HPL.ROW_VISIBLE_URL,
    )
