from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from backend.utils.constants import CONSTANTS
from backend.utils.strings.html_identifiers import IDENTIFIERS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_utils import wait_for_element_presence

pytestmark = pytest.mark.splash_ui

MAX_TAB_PRESSES = 10
HERO_REGISTER_BUTTON_SELECTOR = ".btn.to-register"
EMPTY_OUTLINE_WIDTHS = ("", "0px", "none")


def test_splash_hero_renders_title_tagline_and_ctas(page: Page):
    """
    GIVEN a fresh load of the U4I splash page
    WHEN the modernized hero section renders
    THEN the welcome title, tagline, and both CTA buttons are present and clickable
    """
    # Before-state: no modal is open on a fresh splash load
    assert page.locator(f"{SPL.LOGIN_MODAL}.show").count() == 0
    assert page.locator(f"{SPL.REGISTER_MODAL}.show").count() == 0

    welcome = wait_for_element_presence(page=page, css_selector=SPL.WELCOME_TEXT)
    assert welcome.inner_text() == IDENTIFIERS.SPLASH_PAGE

    tagline = wait_for_element_presence(page=page, css_selector=SPL.SPLASH_TAGLINE)
    assert CONSTANTS.STRINGS.SPLASH_TAGLINE in tagline.inner_text()

    register_button = page.locator(SPL.BUTTON_REGISTER).first
    login_button = page.locator(SPL.BUTTON_LOGIN).first
    expect(register_button).to_be_visible()
    expect(register_button).to_be_enabled()
    expect(login_button).to_be_visible()
    expect(login_button).to_be_enabled()


def test_splash_hero_button_keyboard_focusable(page: Page):
    """
    GIVEN a fresh load of the U4I splash page
    WHEN the user tabs through the page to the hero Register button
    THEN focus lands on the button and a visible focus outline is rendered
    """
    # Ensure the page has OS-level focus before sending Tab keypresses;
    # without this, headless Chrome under parallel load drops the keydown.
    page.locator("body").click()

    landed_on_hero_register = False
    for _ in range(MAX_TAB_PRESSES):
        page.keyboard.press("Tab")
        if page.evaluate(
            f"() => document.activeElement.matches('{HERO_REGISTER_BUTTON_SELECTOR}')"
        ):
            landed_on_hero_register = True
            break

    assert landed_on_hero_register

    outline_width = page.evaluate(
        "() => getComputedStyle(document.activeElement).outlineWidth"
    )
    assert outline_width not in EMPTY_OUTLINE_WIDTHS
