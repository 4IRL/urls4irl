import re

from playwright.sync_api import Page, expect

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_utils import (
    Decks,
    wait_for_animation_to_end_check_height,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_css_property,
)

_MAIN_PANEL_COLLAPSED_CLASS = "lhs-collapsed"


def collapse_deck(
    *, page: Page, deck_header_selector: str, collapsed_deck: Decks
) -> None:
    """Click a deck header to collapse it and wait for the animation to finish.

    The deck animates its height to zero; the ``.content`` child becomes hidden
    once the slide completes.  `wait_for_animation_to_end_check_height` gates on
    two consecutive identical-height polls so the subsequent visibility assert
    is deterministic rather than racing the CSS transition.
    """
    wait_then_get_element(page=page, css_selector=deck_header_selector)
    wait_then_click_element(page=page, css_selector=deck_header_selector)
    wait_for_animation_to_end_check_height(page=page, css_selector=collapsed_deck.value)
    expect(page.locator(f"{collapsed_deck.value} .content").first).to_be_hidden()


def toggle_lhs_panels(*, page: Page, via: str = "seam") -> None:
    """Click the chosen LHS hide/show affordance.

    ``via="seam"`` clicks the chevron handle on the LHS<->center seam;
    ``via="url_header"`` clicks the mirror button in the URL deck header.
    """
    toggle_selector = (
        HPL.LHS_TOGGLE_SEAM_BTN if via == "seam" else HPL.LHS_TOGGLE_HEADER_BTN
    )
    wait_then_click_element(page=page, css_selector=toggle_selector)


def assert_lhs_panels_hidden(*, page: Page) -> None:
    """Assert the left panel has animated away to a collapsed, hidden state.

    The panel collapses via ``width``/``visibility`` (not ``display:none``), so
    assert the computed CSS properties rather than relying on Playwright's
    ``.to_be_hidden()``, which does not track those transitions reliably.

    ``visibility: hidden`` is the load-bearing signal: it only resolves after
    the 0.3s width slide completes (the collapsed-state rule delays the
    ``visibility`` transition by 0.3s), so observing ``hidden`` confirms the
    collapse animation finished.  Width is verified via the ``lhs-collapsed``
    state class on ``#mainPanel``, not an exact pixel value.
    """
    expect(page.locator(HPL.MAIN_PANEL)).to_have_class(
        re.compile(rf"(^|\s){re.escape(_MAIN_PANEL_COLLAPSED_CLASS)}(\s|$)")
    )
    wait_until_css_property(
        page=page,
        css_selector=HPL.LEFT_PANEL,
        css_property="visibility",
        expected_value="hidden",
    )


def assert_lhs_panels_visible(*, page: Page) -> None:
    """Assert the left panel is restored (expanded).

    The primary signal is the absence of the ``lhs-collapsed`` state class on
    ``#mainPanel``, avoiding the fragility of asserting an exact expanded-width
    pixel value.
    """
    expect(page.locator(HPL.MAIN_PANEL)).not_to_have_class(
        re.compile(rf"(^|\s){re.escape(_MAIN_PANEL_COLLAPSED_CLASS)}(\s|$)")
    )
