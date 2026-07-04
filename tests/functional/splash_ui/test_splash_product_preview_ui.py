from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_utils import wait_for_element_presence

pytestmark = pytest.mark.splash_ui

EXPECTED_UTUB_ROW_COUNT = 4
EXPECTED_SELECTED_UTUB_COUNT = 1
EXPECTED_URL_ROW_COUNT = 3
EXPECTED_SELECTED_URL_COUNT = 1
EXPECTED_TAG_COUNT = 3
EXPECTED_ACTION_COUNT = 5
EXPECTED_ACTION_ORDER = ["--access", "--tag", "--copy", "--edit", "--delete"]


def test_splash_product_preview_renders_both_decks(page: Page):
    """
    GIVEN a fresh load of the U4I splash page
    WHEN the user scrolls down to the product-preview section
    THEN the UTubs deck shows 4 rows (1 selected) and the URLs deck shows
         3 rows (1 selected) with 3 tag pills and 5 action buttons
    """
    wait_for_element_presence(page=page, css_selector=SPL.SPLASH_FEATURES)
    preview_section = wait_for_element_presence(
        page=page, css_selector=SPL.SPLASH_PRODUCT_PREVIEW
    )

    # Before-state: with the page scrolled to the top, the product preview is
    # stacked below the feature-tile section in document order (its top edge sits
    # at or beyond the features' bottom edge), confirming the mock renders beneath
    # the marketing tiles rather than overlapping them.
    page.evaluate("() => window.scrollTo(0, 0)")
    preview_below_features = page.evaluate(f"""() => {{
            const featuresRect = document.querySelector('{SPL.SPLASH_FEATURES}').getBoundingClientRect();
            const previewRect = document.querySelector('{SPL.SPLASH_PRODUCT_PREVIEW}').getBoundingClientRect();
            return previewRect.top >= featuresRect.bottom;
        }}""")
    assert preview_below_features

    preview_section.scroll_into_view_if_needed()

    utub_rows = page.locator(SPL.SPLASH_MOCK_UTUB_ROWS).all()
    assert len(utub_rows) == EXPECTED_UTUB_ROW_COUNT

    selected_utubs = page.locator(SPL.SPLASH_MOCK_UTUB_SELECTED).all()
    assert len(selected_utubs) == EXPECTED_SELECTED_UTUB_COUNT

    url_rows = page.locator(SPL.SPLASH_MOCK_URL_ROWS).all()
    assert len(url_rows) == EXPECTED_URL_ROW_COUNT

    selected_urls = page.locator(SPL.SPLASH_MOCK_URL_SELECTED).all()
    assert len(selected_urls) == EXPECTED_SELECTED_URL_COUNT

    selected_url = selected_urls[0]
    tags = selected_url.locator(SPL.SPLASH_MOCK_TAGS).all()
    assert len(tags) == EXPECTED_TAG_COUNT

    actions = selected_url.locator(SPL.SPLASH_MOCK_ACTIONS).all()
    assert len(actions) == EXPECTED_ACTION_COUNT


def test_splash_product_mock_marked_aria_hidden(page: Page):
    """
    GIVEN a fresh load of the U4I splash page
    WHEN the product-preview mock renders
    THEN the decorative mock container is aria-hidden and every button inside
         it is removed from the keyboard tab order via tabindex="-1"
    """
    mock = wait_for_element_presence(page=page, css_selector=SPL.SPLASH_PRODUCT_MOCK)
    expect(mock).to_have_attribute("aria-hidden", "true")

    buttons = mock.locator("button").all()
    assert len(buttons) > 0
    for button in buttons:
        expect(button).to_have_attribute("tabindex", "-1")


def test_splash_mock_action_buttons_in_production_order(page: Page):
    """
    GIVEN a fresh load of the U4I splash page
    WHEN the selected URL row's action buttons render
    THEN they appear in the production order: access, tag, copy, edit, delete
         (mirrors frontend/home/urls/cards/options/btns.ts)
    """
    wait_for_element_presence(page=page, css_selector=SPL.SPLASH_PRODUCT_PREVIEW)
    actions = page.locator(SPL.SPLASH_MOCK_ACTIONS).all()
    assert len(actions) == EXPECTED_ACTION_COUNT

    for action, expected_modifier in zip(actions, EXPECTED_ACTION_ORDER):
        class_attr = action.get_attribute("class")
        assert expected_modifier in class_attr
