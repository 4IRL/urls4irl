import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.selenium_utils import wait_for_element_presence

pytestmark = pytest.mark.mobile_ui

MIN_TOUCH_TARGET_PX = 44
EXPECTED_TILE_COUNT = 3


def test_mobile_splash_hero_ctas_meet_touch_target(
    browser_mobile_portrait: WebDriver,
):
    """
    GIVEN a fresh load of the U4I splash page on a mobile-portrait viewport
    WHEN the hero Register and Login CTA buttons render
    THEN each button's rendered height meets the 44px minimum touch target
    """
    browser = browser_mobile_portrait

    register_button = wait_for_element_presence(browser, SPL.BUTTON_REGISTER)
    login_button = wait_for_element_presence(browser, SPL.BUTTON_LOGIN)
    assert register_button is not None
    assert login_button is not None

    assert register_button.size["height"] >= MIN_TOUCH_TARGET_PX
    assert login_button.size["height"] >= MIN_TOUCH_TARGET_PX


def test_mobile_splash_features_stack_vertically(
    browser_mobile_portrait: WebDriver,
):
    """
    GIVEN a fresh load of the U4I splash page on a mobile-portrait viewport
    WHEN the user scrolls to the feature-tile section
    THEN the three feature tiles render stacked in a single column (equal x offset)
    """
    browser = browser_mobile_portrait

    hero_section = wait_for_element_presence(browser, SPL.SPLASH_HERO)
    features_section = wait_for_element_presence(browser, SPL.SPLASH_FEATURES)
    assert hero_section is not None
    assert features_section is not None

    # Before-state: the feature section is stacked below the hero in the
    # document (its top edge sits at or beyond the hero's bottom edge),
    # confirming the marketing tiles render under the hero on mobile.
    features_below_hero = browser.execute_script(
        "const heroRect = arguments[0].getBoundingClientRect();"
        "const featuresRect = arguments[1].getBoundingClientRect();"
        "return featuresRect.top >= heroRect.bottom;",
        hero_section,
        features_section,
    )
    assert features_below_hero

    browser.execute_script("arguments[0].scrollIntoView();", features_section)

    tiles = browser.find_elements(By.CSS_SELECTOR, SPL.SPLASH_FEATURE_TILES)
    assert len(tiles) == EXPECTED_TILE_COUNT

    # On a mobile-portrait viewport the 768px breakpoint collapses the
    # feature grid to a single column, so all three tiles share one x offset.
    tile_x_offsets = {tile.location["x"] for tile in tiles}
    assert len(tile_x_offsets) == 1
