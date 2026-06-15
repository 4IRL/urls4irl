import pytest
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from backend.utils.constants import CONSTANTS
from backend.utils.strings.html_identifiers import IDENTIFIERS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.selenium_utils import wait_for_element_presence

pytestmark = pytest.mark.splash_ui

MAX_TAB_PRESSES = 10
HERO_REGISTER_BUTTON_SELECTOR = ".btn.to-register"
EMPTY_OUTLINE_WIDTHS = ("", "0px", "none")


def test_splash_hero_renders_title_tagline_and_ctas(browser: WebDriver):
    """
    GIVEN a fresh load of the U4I splash page
    WHEN the modernized hero section renders
    THEN the welcome title, tagline, and both CTA buttons are present and clickable
    """
    # Before-state: no modal is open on a fresh splash load
    assert not browser.find_elements(By.CSS_SELECTOR, f"{SPL.LOGIN_MODAL}.show")
    assert not browser.find_elements(By.CSS_SELECTOR, f"{SPL.REGISTER_MODAL}.show")

    welcome = wait_for_element_presence(browser, SPL.WELCOME_TEXT)
    assert welcome is not None
    assert welcome.text == IDENTIFIERS.SPLASH_PAGE

    tagline = wait_for_element_presence(browser, SPL.SPLASH_TAGLINE)
    assert tagline is not None
    assert CONSTANTS.STRINGS.SPLASH_TAGLINE in tagline.text

    register_button = browser.find_element(By.CSS_SELECTOR, SPL.BUTTON_REGISTER)
    login_button = browser.find_element(By.CSS_SELECTOR, SPL.BUTTON_LOGIN)
    assert register_button.is_displayed() and register_button.is_enabled()
    assert login_button.is_displayed() and login_button.is_enabled()


def test_splash_hero_button_keyboard_focusable(browser: WebDriver):
    """
    GIVEN a fresh load of the U4I splash page
    WHEN the user tabs through the page to the hero Register button
    THEN focus lands on the button and a visible focus outline is rendered
    """
    # Ensure the browser window has OS-level focus before sending Tab keypresses;
    # without this, headless Chrome under parallel load drops the keydown.
    browser.find_element(By.TAG_NAME, "body").click()

    landed_on_hero_register = False
    for _ in range(MAX_TAB_PRESSES):
        ActionChains(browser).send_keys(Keys.TAB).perform()
        if browser.execute_script(
            f"return document.activeElement.matches('{HERO_REGISTER_BUTTON_SELECTOR}')"
        ):
            landed_on_hero_register = True
            break

    assert landed_on_hero_register

    outline_width = browser.execute_script(
        "return getComputedStyle(document.activeElement).outlineWidth"
    )
    assert outline_width not in EMPTY_OUTLINE_WIDTHS
