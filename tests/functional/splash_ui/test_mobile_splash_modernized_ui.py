import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.selenium_utils import wait_for_element_presence

pytestmark = pytest.mark.mobile_ui

MIN_TOUCH_TARGET_PX = 44
EXPECTED_TILE_COUNT = 3
EXPECTED_MOCK_UTUB_COUNT = 4
EXPECTED_MOCK_ACTION_COUNT = 5


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


def test_mobile_splash_product_preview_visible_and_stacked(
    browser_mobile_portrait: WebDriver,
):
    """
    GIVEN a fresh load of the U4I splash page on a mobile-portrait viewport
    WHEN the user scrolls to the product-preview section
    THEN the app mock is shown (not hidden) as a single-column preview — the
        UTubs deck stacked above the selected UTub's URLs deck, with its rows,
        tags, and action buttons all rendered
    """
    browser = browser_mobile_portrait

    preview = wait_for_element_presence(browser, SPL.SPLASH_PRODUCT_PREVIEW)
    assert preview is not None
    assert preview.is_displayed()

    # The mock is shown on mobile (the section is no longer display:none). It
    # fades in via scroll-reveal, so assert it is laid out and sized rather than
    # is_displayed(): the reveal's opacity transition only fires once the element
    # scrolls into view, which headless Chrome's programmatic scroll does not
    # reliably trigger. display != none + a non-zero height proves the un-hiding.
    mock = wait_for_element_presence(browser, SPL.SPLASH_PRODUCT_MOCK)
    assert mock is not None
    assert mock.value_of_css_property("display") != "none"
    assert mock.size["height"] > 0

    utub_rows = browser.find_elements(By.CSS_SELECTOR, SPL.SPLASH_MOCK_UTUB_ROWS)
    url_rows = browser.find_elements(By.CSS_SELECTOR, SPL.SPLASH_MOCK_URL_ROWS)
    actions = browser.find_elements(By.CSS_SELECTOR, SPL.SPLASH_MOCK_ACTIONS)
    assert len(utub_rows) == EXPECTED_MOCK_UTUB_COUNT
    assert len(url_rows) >= 1
    assert len(actions) == EXPECTED_MOCK_ACTION_COUNT

    # Single column on mobile: the URLs deck sits below the UTubs deck (the
    # two-column grid collapsed at the 768px breakpoint), so the URLs deck's
    # top edge is at or below the UTubs deck's bottom edge.
    utubs_deck = browser.find_element(By.CSS_SELECTOR, SPL.SPLASH_MOCK_UTUBS_DECK)
    urls_deck = browser.find_element(By.CSS_SELECTOR, SPL.SPLASH_MOCK_URLS_DECK)
    urls_below_utubs = browser.execute_script(
        "const utubsRect = arguments[0].getBoundingClientRect();"
        "const urlsRect = arguments[1].getBoundingClientRect();"
        "return urlsRect.top >= utubsRect.bottom;",
        utubs_deck,
        urls_deck,
    )
    assert urls_below_utubs
