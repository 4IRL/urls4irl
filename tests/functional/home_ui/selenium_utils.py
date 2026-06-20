from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.wait import WebDriverWait

from tests.functional.assert_utils import (
    assert_not_visible_css_selector,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.selenium_utils import (
    Decks,
    wait_for_animation_to_end_check_height,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_css_property,
)

_MAIN_PANEL_COLLAPSED_CLASS = "lhs-collapsed"


def collapse_deck(browser: WebDriver, deck_header_selector: str, collapsed_deck: Decks):
    first_collapsed_deck_header_elem = wait_then_get_element(
        browser, deck_header_selector, time=3
    )
    assert first_collapsed_deck_header_elem is not None

    wait_then_click_element(browser, deck_header_selector, time=3)

    wait_for_animation_to_end_check_height(browser, collapsed_deck.value)
    assert_not_visible_css_selector(browser, f"{collapsed_deck.value} .content")


def toggle_lhs_panels(browser: WebDriver, via: str = "seam"):
    """Click the chosen LHS hide/show affordance.

    `via="seam"` clicks the chevron handle on the LHS<->center seam;
    `via="url_header"` clicks the mirror button in the URL deck header.
    """
    toggle_selector = (
        HPL.LHS_TOGGLE_SEAM_BTN if via == "seam" else HPL.LHS_TOGGLE_HEADER_BTN
    )
    wait_then_click_element(browser, toggle_selector, time=3)


def assert_lhs_panels_hidden(browser: WebDriver):
    """Assert the left panel has animated away to a collapsed, hidden state.

    The panel collapses via `width`/`visibility` (not `display:none`), so
    assert the computed CSS properties rather than relying on
    `is_displayed()`, which does not track those transitions reliably.

    `visibility: hidden` is the load-bearing signal: it only resolves after
    the 0.3s width slide completes (the collapsed-state rule delays the
    `visibility` transition by 0.3s), so observing `hidden` confirms the
    collapse animation finished. Width is verified via the `lhs-collapsed`
    state class on `#mainPanel`, not an exact pixel value.
    """

    def main_panel_collapsed(driver: WebDriver) -> bool:
        return bool(
            driver.execute_script(
                "return document.querySelector(arguments[0])"
                ".classList.contains(arguments[1]);",
                HPL.MAIN_PANEL,
                _MAIN_PANEL_COLLAPSED_CLASS,
            )
        )

    WebDriverWait(browser, 10).until(main_panel_collapsed)
    wait_until_css_property(browser, HPL.LEFT_PANEL, "visibility", "hidden")


def assert_lhs_panels_visible(browser: WebDriver):
    """Assert the left panel is restored (expanded).

    The primary signal is the absence of the `lhs-collapsed` state class on
    `#mainPanel`, avoiding the fragility of asserting an exact expanded-width
    pixel value.
    """

    def main_panel_not_collapsed(driver: WebDriver) -> bool:
        return not driver.execute_script(
            "return document.querySelector(arguments[0])"
            ".classList.contains(arguments[1]);",
            HPL.MAIN_PANEL,
            _MAIN_PANEL_COLLAPSED_CLASS,
        )

    WebDriverWait(browser, 10).until(main_panel_not_collapsed)
