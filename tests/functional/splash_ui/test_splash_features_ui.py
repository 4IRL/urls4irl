import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.selenium_utils import wait_for_element_presence

pytestmark = pytest.mark.splash_ui

EXPECTED_TILE_COUNT = 3


def test_splash_features_section_renders_three_tiles(browser: WebDriver):
    """
    GIVEN a fresh load of the U4I splash page
    WHEN the user scrolls to the feature-tile section below the hero
    THEN exactly three feature tiles render, each with a non-empty title and body
    """
    hero_section = wait_for_element_presence(browser, SPL.SPLASH_HERO)
    features_section = wait_for_element_presence(browser, SPL.SPLASH_FEATURES)
    assert hero_section is not None
    assert features_section is not None

    # Before-state: the feature section is stacked below the hero in the
    # document (its top edge sits at or beyond the hero's bottom edge),
    # confirming the marketing tiles render under the hero, not overlapping it.
    features_below_hero = browser.execute_script(
        "const heroRect = arguments[0].getBoundingClientRect();"
        "const featuresRect = arguments[1].getBoundingClientRect();"
        "return featuresRect.top >= heroRect.bottom;",
        hero_section,
        features_section,
    )
    assert features_below_hero

    browser.execute_script("arguments[0].scrollIntoView();", features_section)

    features_top_in_viewport_after_scroll = browser.execute_script(
        "const rect = arguments[0].getBoundingClientRect();"
        "return rect.top >= 0 && rect.top < window.innerHeight;",
        features_section,
    )
    assert features_top_in_viewport_after_scroll

    tiles = browser.find_elements(By.CSS_SELECTOR, SPL.SPLASH_FEATURE_TILES)
    assert len(tiles) == EXPECTED_TILE_COUNT

    for tile in tiles:
        title = tile.find_element(By.CSS_SELECTOR, ".splash-feature-title")
        body = tile.find_element(By.CSS_SELECTOR, ".splash-feature-body")
        assert title.text.strip()
        assert body.text.strip()
