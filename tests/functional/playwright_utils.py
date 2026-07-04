from dataclasses import dataclass
import re

from playwright.sync_api import BrowserContext, Page, expect

from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import GenericPageLocator

# Baseline auto-retrying assertion timeout for all Playwright `expect()` calls.
# Matches the existing Selenium `wait_for_element_presence(timeout=10)` baseline
# under n=8 parallel load — a documented suite-wide baseline, not a per-test pad.
DEFAULT_EXPECT_TIMEOUT_MS = 10_000

expect.set_options(timeout=DEFAULT_EXPECT_TIMEOUT_MS)


@dataclass
class PageBundle:
    page: Page
    context: BrowserContext
    base_url: str


def wait_then_click_element(*, page: Page, css_selector: str) -> None:
    """Click the first element matching the selector, auto-waiting for
    actionability (visible, stable, enabled, not obscured)."""
    page.locator(css_selector).first.click()


def wait_then_get_element(*, page: Page, css_selector: str):
    """Return a locator for the first selector match after asserting it is
    visible (Playwright twin of the Selenium visibility-gated getter)."""
    locator = page.locator(css_selector).first
    expect(locator).to_be_visible()
    return locator


def wait_for_element_presence(*, page: Page, css_selector: str):
    """Return a locator for the first selector match after asserting DOM
    presence (attached), NOT visibility — e.g. links inside a collapsed
    navbar dropdown."""
    locator = page.locator(css_selector).first
    expect(locator).to_be_attached()
    return locator


def clear_then_send_keys(*, locator, input_text: str) -> None:
    """Clear an input field then fill it with the provided text."""
    locator.fill("")
    locator.fill(input_text)


def wait_until_in_focus(*, page: Page, css_selector: str) -> None:
    expect(page.locator(css_selector)).to_be_focused()


def click_on_navbar(*, page: Page) -> None:
    """Open the collapsed Bootstrap navbar dropdown, settling any in-progress
    collapse transition before and after the toggler click. Bootstrap ignores
    a toggle click while `collapsing` is active, so clicking mid-transition
    silently no-ops and the dropdown never opens."""
    navbar_dropdown = page.locator(GenericPageLocator.NAVBAR_DROPDOWN)
    expect(navbar_dropdown).not_to_have_class(re.compile(r"collapsing"))
    page.locator(GenericPageLocator.NAVBAR_TOGGLER).click()
    expect(navbar_dropdown).not_to_have_class(re.compile(r"collapsing"))


def add_cookie_banner_cookie(*, context: BrowserContext, base_url: str) -> None:
    """Add the consent cookie so the cookie banner never intercepts clicks.

    Unlike Selenium, Playwright's `add_cookies` requires either `url` or
    `domain`+`path`, and works before any navigation (domain+path are
    inferred from the `url` argument).
    """
    context.add_cookies(
        [
            {
                "name": UTS.COOKIE_NAME,
                "value": UTS.COOKIE_VALUE,
                "url": base_url,
            }
        ]
    )


def login_user_with_cookie_from_session(
    *, context: BrowserContext, session_id: str, base_url: str
) -> None:
    """Playwright analog of `login_utils.login_user_with_cookie_from_session`:
    installs the pre-built server-side session's cookie on the browser context.

    The Selenium version calls `browser.refresh()` after adding the cookie;
    here the caller's subsequent `page.goto()` navigates directly to the
    target page, making a reload redundant.
    """
    context.add_cookies(
        [
            {
                "name": "session",
                "value": session_id,
                "url": base_url,
                "httpOnly": True,
            }
        ]
    )
