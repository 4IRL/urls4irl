from __future__ import annotations

import pytest
from playwright.sync_api import Page

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_assert_utils import (
    assert_on_429_page,
    assert_visible_css_selector,
)
from tests.functional.playwright_utils import (
    modify_navigational_link_for_rate_limit,
    scroll_footer_link_into_view,
    visit_contact_us_page,
    visit_privacy_page,
    visit_terms_page,
    wait_then_click_element,
    wait_then_get_element,
)

pytestmark = pytest.mark.splash_ui

EXPECTED_TEXTAREA_MIN_HEIGHT_PX = "320px"

NARROW_VIEWPORT_WIDTH_PX = 380
NARROW_VIEWPORT_HEIGHT_PX = 812
# WCAG 2.1 AA minimum contrast ratio for normal-size text (SC 1.4.3).
WCAG_AA_NORMAL_TEXT_MIN_CONTRAST = 4.5

# Computes the WCAG 2.1 relative-luminance contrast ratio between the footer
# Privacy link's resolved text color and the footer band's actual background.
# The footer band is always dark (Bootstrap `bg-dark`, Design Decision 4)
# regardless of the page theme, so both colors are read from the live DOM and
# the ratio is asserted rather than pinning one theme's --footerURLColor literal.
_FOOTER_PRIVACY_LINK_CONTRAST_JS = """() => {
    const parseRgb = (value) => value.match(/[\\d.]+/g).slice(0, 3).map(Number);
    const relativeLuminance = ([red, green, blue]) => {
        const linear = [red, green, blue].map((channel) => {
            const srgb = channel / 255;
            return srgb <= 0.03928
                ? srgb / 12.92
                : Math.pow((srgb + 0.055) / 1.055, 2.4);
        });
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
    };
    const privacyLink = document.getElementById('PrivacyBtn');
    const footerBand = privacyLink.closest('footer');
    const linkLuminance = relativeLuminance(
        parseRgb(getComputedStyle(privacyLink).color)
    );
    const bandLuminance = relativeLuminance(
        parseRgb(getComputedStyle(footerBand).backgroundColor)
    );
    const lighter = Math.max(linkLuminance, bandLuminance);
    const darker = Math.min(linkLuminance, bandLuminance);
    return (lighter + 0.05) / (darker + 0.05);
}"""


def test_privacy_policy(page: Page):
    """
    Tests a non-logged in user's ability to visit the privacy page from the splash page.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the privacy button in the footer
    THEN ensure the U4I Privacy Policy is displayed
    """
    visit_privacy_page(page=page)


def test_privacy_policy_rate_limits(page: Page):
    """
    Tests a non-logged in user's ability to visit the privacy page from the splash page, but they are rate limited.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the privacy button in the footer
    THEN ensure the rate limited error page is shown
    """
    modify_navigational_link_for_rate_limit(
        page=page, element_id=HPL.PRIVACY_BTN.lstrip("#")
    )
    scroll_footer_link_into_view(page=page, css_selector=HPL.PRIVACY_BTN)
    wait_then_click_element(page=page, css_selector=HPL.PRIVACY_BTN)
    assert_on_429_page(page=page)


@pytest.mark.parametrize("splash_btn_css_selector", [SPL.U4I_LOGO, SPL.BACK_SPLASH_BTN])
def test_privacy_policy_return_splash(page: Page, splash_btn_css_selector: str):
    """
    Tests a non-logged in user's ability to visit the privacy page and then return to splash page.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the privacy button in the footer and then tries to go splash via the buttons
    THEN ensure the splash page is displayed
    """
    visit_privacy_page(page=page)
    wait_then_click_element(page=page, css_selector=splash_btn_css_selector)
    assert_visible_css_selector(page=page, css_selector=SPL.WELCOME_TEXT)


def test_terms_page(page: Page):
    """
    Tests a non-logged in user's ability to visit the terms page from the splash page.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the terms button in the footer
    THEN ensure the U4I Terms & Conditions are displayed
    """
    visit_terms_page(page=page)


def test_terms_page_rate_limits(page: Page):
    """
    Tests a non-logged in user's ability to visit the terms page from the splash page but they are rate limited.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the terms button in the footer
    THEN ensure the 429 error page is shown
    """
    modify_navigational_link_for_rate_limit(
        page=page, element_id=HPL.TERMS_BTN.lstrip("#")
    )
    scroll_footer_link_into_view(page=page, css_selector=HPL.TERMS_BTN)
    wait_then_click_element(page=page, css_selector=HPL.TERMS_BTN)
    assert_on_429_page(page=page)


@pytest.mark.parametrize("splash_btn_css_selector", [SPL.U4I_LOGO, SPL.BACK_SPLASH_BTN])
def test_terms_return_splash(page: Page, splash_btn_css_selector: str):
    """
    Tests a non-logged in user's ability to visit the terms page and then return to splash page.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the terms button in the footer and then tries to go splash via the buttons
    THEN ensure the splash page is displayed
    """
    visit_terms_page(page=page)
    wait_then_click_element(page=page, css_selector=splash_btn_css_selector)
    assert_visible_css_selector(page=page, css_selector=SPL.WELCOME_TEXT)


def test_visit_contact_page(page: Page):
    """
    GIVEN a fresh load of the U4I splash page
    WHEN user clicks on the Contact Us button in the footer
    THEN ensure the Contact Us page is shown
    """
    visit_contact_us_page(page=page)


@pytest.mark.parametrize("splash_btn_css_selector", [SPL.U4I_LOGO, SPL.BACK_SPLASH_BTN])
def test_visit_contact_page_return_splash(page: Page, splash_btn_css_selector: str):
    """
    GIVEN a fresh load of the U4I Contact Us Page
    WHEN user clicks on the return to Splash buttons
    THEN ensure the Splash page is shown
    """
    visit_contact_us_page(page=page)
    wait_then_click_element(page=page, css_selector=splash_btn_css_selector)
    assert_visible_css_selector(page=page, css_selector=SPL.WELCOME_TEXT)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_privacy_btn_color_passes_wcag_at_380px(page: Page, scheme: str):
    """
    GIVEN a fresh load of the U4I Splash page at a 380px-wide viewport
    WHEN the footer renders under EITHER the light or the dark color scheme
    THEN ensure the #PrivacyBtn link color keeps WCAG AA contrast against the
        always-dark footer band

    The footer band is dark in every theme (Bootstrap `bg-dark`, Design
    Decision 4), so its link color (--footerURLColor) is theme-INDEPENDENT and
    must clear WCAG AA against the dark band regardless of the page theme. An
    anonymous visitor's <html> is stamped data-theme="system", which the
    pre-paint resolver maps to the OS color scheme; emulating both light and
    dark here exercises both resolutions of that "system" choice. Light mode is
    the regression guard: before the token was made theme-independent it
    resolved to the light-theme --cardURLTextColor (#5c6b6d ≈ 2.8:1), failing
    AA. The assertion computes the live contrast ratio rather than a hardcoded
    color so it stays meaningful if the footer token is retuned.
    """
    page.emulate_media(color_scheme=scheme)
    page.set_viewport_size(
        {"width": NARROW_VIEWPORT_WIDTH_PX, "height": NARROW_VIEWPORT_HEIGHT_PX}
    )
    page.reload()
    scroll_footer_link_into_view(page=page, css_selector=HPL.PRIVACY_BTN)
    contrast_ratio = page.evaluate(_FOOTER_PRIVACY_LINK_CONTRAST_JS)
    assert contrast_ratio >= WCAG_AA_NORMAL_TEXT_MIN_CONTRAST


def test_contact_textarea_min_height(page: Page):
    """
    GIVEN a fresh load of the U4I Contact Us page
    WHEN user views the contact form
    THEN ensure the textarea#content element has min-height: 20rem (320px) applied
    """
    visit_contact_us_page(page=page)
    textarea = wait_then_get_element(page=page, css_selector=HPL.CONTACT_CONTENT_INPUT)
    min_height = textarea.evaluate("element => getComputedStyle(element).minHeight")
    assert min_height == EXPECTED_TEXTAREA_MIN_HEIGHT_PX
