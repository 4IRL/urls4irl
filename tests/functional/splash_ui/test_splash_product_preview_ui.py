import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.selenium_utils import wait_for_element_presence

pytestmark = pytest.mark.splash_ui

EXPECTED_UTUB_ROW_COUNT = 4
EXPECTED_SELECTED_UTUB_COUNT = 1
EXPECTED_URL_ROW_COUNT = 3
EXPECTED_SELECTED_URL_COUNT = 1
EXPECTED_TAG_COUNT = 3
EXPECTED_ACTION_COUNT = 5
EXPECTED_ACTION_ORDER = ["--access", "--tag", "--copy", "--edit", "--delete"]


def test_splash_product_preview_renders_both_decks(browser: WebDriver):
    """
    GIVEN a fresh load of the U4I splash page
    WHEN the user scrolls down to the product-preview section
    THEN the UTubs deck shows 4 rows (1 selected) and the URLs deck shows
         3 rows (1 selected) with 3 tag pills and 5 action buttons
    """
    features_section = wait_for_element_presence(browser, SPL.SPLASH_FEATURES)
    preview_section = wait_for_element_presence(browser, SPL.SPLASH_PRODUCT_PREVIEW)
    assert features_section is not None
    assert preview_section is not None

    # Before-state: with the page scrolled to the top, the product preview is
    # stacked below the feature-tile section in document order (its top edge sits
    # at or beyond the features' bottom edge), confirming the mock renders beneath
    # the marketing tiles rather than overlapping them.
    browser.execute_script("window.scrollTo(0, 0);")
    preview_below_features = browser.execute_script(
        "const featuresRect = arguments[0].getBoundingClientRect();"
        "const previewRect = arguments[1].getBoundingClientRect();"
        "return previewRect.top >= featuresRect.bottom;",
        features_section,
        preview_section,
    )
    assert preview_below_features

    browser.execute_script("arguments[0].scrollIntoView();", preview_section)

    utub_rows = browser.find_elements(By.CSS_SELECTOR, SPL.SPLASH_MOCK_UTUB_ROWS)
    assert len(utub_rows) == EXPECTED_UTUB_ROW_COUNT
    selected_utubs = browser.find_elements(
        By.CSS_SELECTOR, SPL.SPLASH_MOCK_UTUB_SELECTED
    )
    assert len(selected_utubs) == EXPECTED_SELECTED_UTUB_COUNT

    url_rows = browser.find_elements(By.CSS_SELECTOR, SPL.SPLASH_MOCK_URL_ROWS)
    assert len(url_rows) == EXPECTED_URL_ROW_COUNT
    selected_urls = browser.find_elements(By.CSS_SELECTOR, SPL.SPLASH_MOCK_URL_SELECTED)
    assert len(selected_urls) == EXPECTED_SELECTED_URL_COUNT

    selected_url = selected_urls[0]
    tags = selected_url.find_elements(By.CSS_SELECTOR, SPL.SPLASH_MOCK_TAGS)
    assert len(tags) == EXPECTED_TAG_COUNT

    actions = selected_url.find_elements(By.CSS_SELECTOR, SPL.SPLASH_MOCK_ACTIONS)
    assert len(actions) == EXPECTED_ACTION_COUNT


def test_splash_product_mock_marked_aria_hidden(browser: WebDriver):
    """
    GIVEN a fresh load of the U4I splash page
    WHEN the product-preview mock renders
    THEN the decorative mock container is aria-hidden and every button inside
         it is removed from the keyboard tab order via tabindex="-1"
    """
    mock = wait_for_element_presence(browser, SPL.SPLASH_PRODUCT_MOCK)
    assert mock is not None
    assert mock.get_attribute("aria-hidden") == "true"

    buttons = mock.find_elements(By.TAG_NAME, "button")
    assert len(buttons) > 0
    for button in buttons:
        assert button.get_attribute("tabindex") == "-1"


def test_splash_mock_action_buttons_in_production_order(browser: WebDriver):
    """
    GIVEN a fresh load of the U4I splash page
    WHEN the selected URL row's action buttons render
    THEN they appear in the production order: access, tag, copy, edit, delete
         (mirrors frontend/home/urls/cards/options/btns.ts)
    """
    wait_for_element_presence(browser, SPL.SPLASH_PRODUCT_PREVIEW)
    actions = browser.find_elements(By.CSS_SELECTOR, SPL.SPLASH_MOCK_ACTIONS)
    assert len(actions) == EXPECTED_ACTION_COUNT

    for action, expected_modifier in zip(actions, EXPECTED_ACTION_ORDER):
        assert expected_modifier in action.get_attribute("class")
