from __future__ import annotations

import pytest
from playwright.sync_api import Page

from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_utils import wait_for_element_presence

pytestmark = pytest.mark.splash_ui

EXPECTED_TILE_COUNT = 3


def test_splash_features_section_renders_three_tiles(page: Page):
    """
    GIVEN a fresh load of the U4I splash page
    WHEN the user scrolls to the feature-tile section below the hero
    THEN exactly three feature tiles render, each with a non-empty title and body
    """
    wait_for_element_presence(page=page, css_selector=SPL.SPLASH_HERO)
    features_section = wait_for_element_presence(
        page=page, css_selector=SPL.SPLASH_FEATURES
    )

    # Before-state: the feature section is stacked below the hero in the
    # document (its top edge sits at or beyond the hero's bottom edge),
    # confirming the marketing tiles render under the hero, not overlapping it.
    features_below_hero = page.evaluate(f"""() => {{
            const heroRect = document.querySelector('{SPL.SPLASH_HERO}').getBoundingClientRect();
            const featuresRect = document.querySelector('{SPL.SPLASH_FEATURES}').getBoundingClientRect();
            return featuresRect.top >= heroRect.bottom;
        }}""")
    assert features_below_hero

    features_section.scroll_into_view_if_needed()

    features_top_in_viewport_after_scroll = features_section.evaluate(
        "element => { const rect = element.getBoundingClientRect(); return rect.top >= 0 && rect.top < window.innerHeight; }"
    )
    assert features_top_in_viewport_after_scroll

    tiles = page.locator(SPL.SPLASH_FEATURE_TILES).all()
    assert len(tiles) == EXPECTED_TILE_COUNT

    for tile in tiles:
        title = tile.locator(".splash-feature-title").first
        body = tile.locator(".splash-feature-body").first
        assert title.inner_text().strip()
        assert body.inner_text().strip()
