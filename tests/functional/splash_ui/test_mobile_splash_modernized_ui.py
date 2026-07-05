from __future__ import annotations

import pytest
from playwright.sync_api import Page

from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_utils import wait_for_element_presence

pytestmark = pytest.mark.mobile_ui

MIN_TOUCH_TARGET_PX = 44
EXPECTED_TILE_COUNT = 3
EXPECTED_MOCK_UTUB_COUNT = 4
EXPECTED_MOCK_ACTION_COUNT = 5


def test_mobile_splash_hero_ctas_meet_touch_target(
    page_mobile_portrait: Page,
):
    """
    GIVEN a fresh load of the U4I splash page on a mobile-portrait viewport
    WHEN the hero Register and Login CTA buttons render
    THEN each button's rendered height meets the 44px minimum touch target
    """
    register_button = wait_for_element_presence(
        page=page_mobile_portrait, css_selector=SPL.BUTTON_REGISTER
    )
    login_button = wait_for_element_presence(
        page=page_mobile_portrait, css_selector=SPL.BUTTON_LOGIN
    )

    register_height = register_button.evaluate(
        "element => element.getBoundingClientRect().height"
    )
    login_height = login_button.evaluate(
        "element => element.getBoundingClientRect().height"
    )
    assert register_height >= MIN_TOUCH_TARGET_PX
    assert login_height >= MIN_TOUCH_TARGET_PX


def test_mobile_splash_features_stack_vertically(
    page_mobile_portrait: Page,
):
    """
    GIVEN a fresh load of the U4I splash page on a mobile-portrait viewport
    WHEN the user scrolls to the feature-tile section
    THEN the three feature tiles render stacked in a single column (equal x offset)
    """
    wait_for_element_presence(page=page_mobile_portrait, css_selector=SPL.SPLASH_HERO)
    features_section = wait_for_element_presence(
        page=page_mobile_portrait, css_selector=SPL.SPLASH_FEATURES
    )

    # Before-state: the feature section is stacked below the hero in the
    # document (its top edge sits at or beyond the hero's bottom edge),
    # confirming the marketing tiles render under the hero on mobile.
    features_below_hero = page_mobile_portrait.evaluate(f"""() => {{
            const heroRect = document.querySelector('{SPL.SPLASH_HERO}').getBoundingClientRect();
            const featuresRect = document.querySelector('{SPL.SPLASH_FEATURES}').getBoundingClientRect();
            return featuresRect.top >= heroRect.bottom;
        }}""")
    assert features_below_hero

    features_section.scroll_into_view_if_needed()

    tiles = page_mobile_portrait.locator(SPL.SPLASH_FEATURE_TILES).all()
    assert len(tiles) == EXPECTED_TILE_COUNT

    # On a mobile-portrait viewport the 768px breakpoint collapses the
    # feature grid to a single column, so all three tiles share one x offset.
    tile_x_offsets = {
        tile.evaluate("element => element.getBoundingClientRect().left")
        for tile in tiles
    }
    assert len(tile_x_offsets) == 1


def test_mobile_splash_product_preview_visible_and_stacked(
    page_mobile_portrait: Page,
):
    """
    GIVEN a fresh load of the U4I splash page on a mobile-portrait viewport
    WHEN the user scrolls to the product-preview section
    THEN the app mock is shown (not hidden) as a single-column preview — the
        UTubs deck stacked above the selected UTub's URLs deck, with its rows,
        tags, and action buttons all rendered
    """
    preview = wait_for_element_presence(
        page=page_mobile_portrait, css_selector=SPL.SPLASH_PRODUCT_PREVIEW
    )
    preview_bounding_box = preview.bounding_box()
    assert preview_bounding_box is not None

    # The mock is shown on mobile (the section is no longer display:none). It
    # fades in via scroll-reveal, so assert it is laid out and sized rather than
    # checking visibility: the reveal's opacity transition only fires once the
    # element scrolls into view, which headless Chrome's programmatic scroll does
    # not reliably trigger. display != none + a non-zero height proves the un-hiding.
    mock = wait_for_element_presence(
        page=page_mobile_portrait, css_selector=SPL.SPLASH_PRODUCT_MOCK
    )
    mock_display = mock.evaluate("element => getComputedStyle(element).display")
    assert mock_display != "none"
    mock_height = mock.evaluate("element => element.getBoundingClientRect().height")
    assert mock_height > 0

    utub_rows = page_mobile_portrait.locator(SPL.SPLASH_MOCK_UTUB_ROWS).all()
    url_rows = page_mobile_portrait.locator(SPL.SPLASH_MOCK_URL_ROWS).all()
    actions = page_mobile_portrait.locator(SPL.SPLASH_MOCK_ACTIONS).all()
    assert len(utub_rows) == EXPECTED_MOCK_UTUB_COUNT
    assert len(url_rows) >= 1
    assert len(actions) == EXPECTED_MOCK_ACTION_COUNT

    # Single column on mobile: the URLs deck sits below the UTubs deck (the
    # two-column grid collapsed at the 768px breakpoint), so the URLs deck's
    # top edge is at or below the UTubs deck's bottom edge.
    urls_below_utubs = page_mobile_portrait.evaluate(f"""() => {{
            const utubsRect = document.querySelector('{SPL.SPLASH_MOCK_UTUBS_DECK}').getBoundingClientRect();
            const urlsRect = document.querySelector('{SPL.SPLASH_MOCK_URLS_DECK}').getBoundingClientRect();
            return urlsRect.top >= utubsRect.bottom;
        }}""")
    assert urls_below_utubs
