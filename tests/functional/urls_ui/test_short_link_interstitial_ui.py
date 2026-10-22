import re
from typing import Generator
from urllib.parse import urlsplit

import pytest
from flask import Flask
from playwright.sync_api import Browser, BrowserContext, Page, expect

from backend.models.urls import Urls
from tests.functional.db_utils import (
    add_url_to_utub_as_other_member,
    get_url_in_utub,
    get_utub_this_user_created,
)
from tests.functional.locators import ModalLocators
from tests.functional.locators import ShortLinkPageLocators as SLPL
from tests.functional.playwright_utils import current_base_url
from tests.functional.third_party_stubs import stub_third_party_requests
from tests.functional.urls_ui.db_utils import mint_short_link_in_db
from tests.functional.urls_ui.playwright_utils import stub_mock_url_responses

pytestmark = pytest.mark.urls_ui

DESKTOP_VIEWPORT = {"width": 1280, "height": 900}
MOBILE_VIEWPORT = {"width": 390, "height": 844}

# About 2000 characters, with one unbreakable path segment and a long host label,
# the worst case for the confirmation page's full-URL box and h1 host.
LONG_HOST = "a" * 60 + ".example.com"
LONG_DESTINATION_URL = f"https://{LONG_HOST}/" + "b" * 1950
LONG_DESTINATION_TITLE = "Very long destination"


def _new_anonymous_context(
    *, browser: Browser, viewport: dict[str, int]
) -> BrowserContext:
    """A fresh logged-out browser context: no session and no consent cookie."""
    context = browser.new_context(viewport=viewport)
    context.set_default_timeout(10_000)
    context.set_default_navigation_timeout(30_000)
    stub_third_party_requests(context=context, test_fixture_names=[])
    return context


@pytest.fixture
def anonymous_desktop_page(
    page: Page, build_page_browser: Browser
) -> Generator[Page, None, None]:
    """A logged-out desktop page (`page` is requested first so the DB is clear)."""
    context = _new_anonymous_context(
        browser=build_page_browser, viewport=DESKTOP_VIEWPORT
    )
    try:
        yield context.new_page()
    finally:
        context.close()


@pytest.fixture
def anonymous_mobile_page(
    page: Page, build_page_browser: Browser
) -> Generator[Page, None, None]:
    """A logged-out 390px page (`page` is requested first so the DB is clear)."""
    context = _new_anonymous_context(
        browser=build_page_browser, viewport=MOBILE_VIEWPORT
    )
    try:
        yield context.new_page()
    finally:
        context.close()


def _mint_for_first_url(*, app: Flask, page: Page) -> tuple[str, str, str]:
    """Mint a link for the first URL of user 1's UTub. Returns the page URL of the
    link (`<origin>/s/<code>`), the destination and the code."""
    utub = get_utub_this_user_created(app, 1)
    utub_url = get_url_in_utub(app, utub.id)
    with app.app_context():
        destination = Urls.query.get(utub_url.url_id).url_string
    code = mint_short_link_in_db(
        app=app, utub_url_id=utub_url.id, created_by=utub.utub_creator
    )
    return f"{current_base_url(page=page)}/s/{code}", destination, code


def test_anonymous_visitor_sees_destination_and_continue_navigates(
    page: Page,
    anonymous_desktop_page: Page,
    create_test_access_urls,
    provide_app: Flask,
):
    """
    GIVEN a short link and a visitor who is not logged in
    WHEN the visitor opens `/s/<code>` and clicks Continue
    THEN the page shows the destination (never a redirect) and Continue takes them there
    """
    short_page_url, destination, _ = _mint_for_first_url(app=provide_app, page=page)
    visitor = anonymous_desktop_page
    stub_mock_url_responses(context=visitor.context)

    response = visitor.goto(short_page_url)

    assert response is not None
    assert response.status == 200
    assert visitor.url == short_page_url
    expect(visitor.locator(SLPL.VALID_LINK_HEADING)).to_be_visible()
    expect(visitor.locator(SLPL.VALID_LINK_HEADING)).to_have_text(
        urlsplit(destination).hostname
    )
    expect(visitor.locator(SLPL.FULL_URL)).to_have_text(destination)
    continue_btn = visitor.locator(SLPL.BUTTON_CONTINUE)
    expect(continue_btn).to_have_text("Continue")
    expect(continue_btn).to_have_attribute("href", destination)

    continue_btn.click()

    visitor.wait_for_url(destination)
    assert visitor.url == destination


def test_shell_has_plain_nav_no_splash_modals_hamburger_and_cookie_banner(
    page: Page,
    anonymous_mobile_page: Page,
    create_test_access_urls,
    provide_app: Flask,
):
    """
    GIVEN a short link opened by an anonymous visitor on a phone
    WHEN the page loads
    THEN it has plain nav links (no Login/Register splash buttons), no modals, a
        working hamburger and a dismissible cookie banner
    """
    short_page_url, _, _ = _mint_for_first_url(app=provide_app, page=page)
    visitor = anonymous_mobile_page

    visitor.goto(short_page_url)

    expect(visitor.locator(SLPL.MAIN)).to_be_visible()
    expect(visitor.locator(ModalLocators.ELEMENT_MODAL)).to_have_count(0)
    expect(visitor.locator(f"{SLPL.NAVBAR_DROPDOWN} button.to-login")).to_have_count(0)
    expect(visitor.locator(f"{SLPL.NAVBAR_DROPDOWN} button.to-register")).to_have_count(
        0
    )

    # The banner slides/fades (opacity), so its `is-visible` class is the state.
    banner = visitor.locator(SLPL.COOKIE_BANNER)
    expect(banner).to_have_class(re.compile(r"\bis-visible\b"))
    visitor.locator(SLPL.COOKIE_BANNER_BTN).click()
    expect(banner).not_to_have_class(re.compile(r"\bis-visible\b"))
    expect(banner).to_have_css("opacity", "0")

    expect(visitor.locator(SLPL.BACK_SPLASH_BTN)).to_be_hidden()
    visitor.locator(SLPL.NAVBAR_TOGGLER).click()
    expect(visitor.locator(SLPL.BACK_SPLASH_BTN)).to_be_visible()
    # A plain link, not a splash modal button.
    expect(visitor.locator(f"a{SLPL.BACK_SPLASH_BTN}")).to_have_attribute("href", "/")


def test_long_destination_does_not_overflow_horizontally_at_390(
    page: Page,
    anonymous_mobile_page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a short link whose stored destination is about 2000 characters
    WHEN an anonymous visitor opens it at 390px
    THEN the page does not scroll sideways, the full-URL box wraps and the h1 host
        does not widen the page
    """
    app = provide_app
    utub = get_utub_this_user_created(app, 1)
    utub_url_id = add_url_to_utub_as_other_member(
        app, utub.id, utub.utub_creator, LONG_DESTINATION_URL, LONG_DESTINATION_TITLE
    )
    code = mint_short_link_in_db(
        app=app, utub_url_id=utub_url_id, created_by=utub.utub_creator
    )
    visitor = anonymous_mobile_page

    visitor.goto(f"{current_base_url(page=page)}/s/{code}")

    full_url = visitor.locator(SLPL.FULL_URL)
    expect(full_url).to_have_text(LONG_DESTINATION_URL)
    expect(visitor.locator(SLPL.VALID_LINK_HEADING)).to_be_visible()

    assert visitor.evaluate(
        "() => document.documentElement.scrollWidth <= window.innerWidth"
    )
    full_url_box = full_url.bounding_box()
    heading_box = visitor.locator(SLPL.VALID_LINK_HEADING).bounding_box()
    assert full_url_box is not None and heading_box is not None
    assert full_url_box["x"] + full_url_box["width"] <= MOBILE_VIEWPORT["width"]
    assert heading_box["x"] + heading_box["width"] <= MOBILE_VIEWPORT["width"]
    # Wrapped over several lines rather than clipped or scrolled.
    assert full_url_box["height"] > 2 * visitor.evaluate(
        "(sel) => parseFloat(getComputedStyle(document.querySelector(sel)).lineHeight) || 16",
        SLPL.FULL_URL,
    )
