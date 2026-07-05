from playwright.sync_api import Page

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_utils import (
    clear_then_send_keys,
    wait_then_click_element,
    wait_then_get_at_least_n_elements,
    wait_then_get_element,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)


def open_cross_search_via_trigger(*, page: Page) -> None:
    """
    Opens cross-UTub search mode by clicking the navbar trigger.

    The trigger is a standalone icon button inline next to the hamburger (outside
    the collapsed dropdown), so it is directly clickable on every viewport without
    first opening the navbar menu.
    """
    wait_until_visible_css_selector(page=page, css_selector=HPL.CROSS_SEARCH_TRIGGER)
    wait_then_click_element(page=page, css_selector=HPL.CROSS_SEARCH_TRIGGER)
    wait_until_visible_css_selector(page=page, css_selector=HPL.CROSS_SEARCH_INPUT)
    wait_until_in_focus(page=page, css_selector=HPL.CROSS_SEARCH_INPUT)


def open_cross_search_via_shortcut(*, page: Page) -> None:
    """
    Opens cross-UTub search mode via the Cmd/Ctrl+K shortcut.

    The shortcut handler ignores the keystroke when the active element is an
    INPUT/TEXTAREA, so the combo is delivered to <body>. The handler accepts
    either metaKey or ctrlKey; ControlOrMeta covers both platforms.
    """
    page.locator("body").click()
    page.keyboard.press("ControlOrMeta+k")
    wait_until_visible_css_selector(page=page, css_selector=HPL.CROSS_SEARCH_INPUT)
    wait_until_in_focus(page=page, css_selector=HPL.CROSS_SEARCH_INPUT)


def open_cross_search_settings(*, page: Page) -> None:
    """Opens the search-options modal via the gear button and waits for it to show."""
    wait_then_click_element(page=page, css_selector=HPL.CROSS_SEARCH_SETTINGS_BTN)
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.CROSS_SEARCH_SETTINGS_MODAL
    )


def type_cross_search_query(*, page: Page, term: str) -> None:
    """
    Focuses the cross-search input, types the query, and submits it with Enter.

    Search no longer fires per keystroke — it runs only on an explicit submit
    (the button or Enter), so the Enter press here is what triggers the request
    every caller then waits on.
    """
    wait_until_in_focus(page=page, css_selector=HPL.CROSS_SEARCH_INPUT)
    search_input = wait_then_get_element(page=page, css_selector=HPL.CROSS_SEARCH_INPUT)
    clear_then_send_keys(locator=search_input, input_text=term)
    search_input.press("Enter")


def wait_for_cross_search_results(*, page: Page) -> list:
    """
    Blocks until at least one result card is present in the DOM.

    The request is async; gate on the live count of ``.crossSearchHitCard``
    settling to >=1 before asserting rather than a bare send-keys-then-assert.
    """
    cards = wait_then_get_at_least_n_elements(
        page=page, css_selector=HPL.CROSS_SEARCH_HIT_CARD, minimum_count=1
    )
    assert len(cards) >= 1
    return cards


def wait_for_cross_search_no_results(*, page: Page) -> None:
    """Blocks until the distinct no-results message is visible."""
    wait_until_visible_css_selector(page=page, css_selector=HPL.CROSS_SEARCH_NO_RESULTS)


def wait_for_cross_search_history(*, page: Page) -> None:
    """Blocks until the recent-searches history list is visible."""
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.CROSS_SEARCH_HISTORY_LIST
    )


def wait_for_cross_search_group_count(*, page: Page, minimum_count: int) -> list:
    """Blocks until at least ``minimum_count`` result group sections are present."""
    return wait_then_get_at_least_n_elements(
        page=page, css_selector=HPL.CROSS_SEARCH_GROUP, minimum_count=minimum_count
    )
