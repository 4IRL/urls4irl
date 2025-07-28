from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.assert_utils import (
    assert_not_visible_css_selector,
)
from tests.functional.selenium_utils import (
    Decks,
    wait_for_animation_to_end_check_height,
    wait_then_click_element,
    wait_then_get_element,
)


def collapse_deck(browser: WebDriver, deck_header_selector: str, collapsed_deck: Decks):
    first_collapsed_deck_header_elem = wait_then_get_element(
        browser, deck_header_selector, time=3
    )
    assert first_collapsed_deck_header_elem is not None

    wait_then_click_element(browser, deck_header_selector, time=3)

    wait_for_animation_to_end_check_height(browser, collapsed_deck.value)
    assert_not_visible_css_selector(browser, f"{collapsed_deck.value} .content")
