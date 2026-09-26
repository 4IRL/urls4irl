from flask import Flask, url_for
import pytest
from playwright.sync_api import Page, Route, expect

from backend.utils.all_routes import ROUTES
from backend.utils.strings.html_identifiers import IDENTIFIERS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_assert_utils import (
    assert_no_page_errors,
    assert_on_429_page,
)
from tests.functional.playwright_utils import collect_page_errors

pytestmark = pytest.mark.splash_ui

# These tests navigate straight to an error page as a full document load, so
# error.ts evaluates its module graph (incl. lib/config.ts) fresh. The AJAX
# `document.write` path used by the *_invalid_csrf_token / *_rate_limits tests
# can reuse modules a previously loaded page already evaluated under the same
# URL, which hid a missing `#app-config` on the built stack.


def _assert_refresh_lands_on_splash(*, page: Page, splash_url: str) -> None:
    """Click "Click to Refresh" and assert it navigates to a real (2xx) splash
    page, not a 405 from re-requesting a POST-only route.

    Call after the "load" event: on a fresh document error.ts is a module script
    that binds the click handler on DOMContentLoaded (or immediately, if the DOM
    is already parsed), so the binding is in place by load. No retry is needed,
    unlike the document.write path in assert_visited_403_on_invalid_csrf_and_reload.
    """
    error_page_subheader = page.locator(f"{SPL.ERROR_PAGE_HANDLER} h2").first
    with page.expect_navigation() as navigation_info:
        page.locator(SPL.ERROR_PAGE_REFRESH_BTN).first.click()
    landing_response = navigation_info.value
    assert landing_response is not None
    assert landing_response.ok, f"Refresh landed on HTTP {landing_response.status}"
    expect(error_page_subheader).to_be_hidden()
    expect(page).to_have_url(splash_url)


def test_429_error_page_loaded_fresh_refreshes_without_page_errors(page: Page):
    """
    GIVEN a full-page navigation that is rate limited
    WHEN the 429 error page loads fresh and the user clicks its refresh button
    THEN ensure the page script initialized without errors and the refresh
         reloads the splash page
    """
    splash_url = page.url
    page_errors = collect_page_errors(page=page)

    # Rate-limit only the document request: the page's own script and asset
    # requests must load normally for the page to initialize.
    def force_rate_limit(route: Route) -> None:
        route.continue_(headers={**route.request.headers, "X-Force-Rate-Limit": "true"})

    page.route(splash_url, force_rate_limit)
    page.goto(splash_url)
    assert_on_429_page(page=page)
    page.wait_for_load_state("load")

    page.unroute(splash_url, force_rate_limit)
    # Reached by GET, so refresh reloads the same (now un-limited) URL.
    _assert_refresh_lands_on_splash(page=page, splash_url=splash_url)
    assert_no_page_errors(page_errors=page_errors)


def test_403_error_page_loaded_fresh_refreshes_without_page_errors(
    page: Page, provide_app: Flask
):
    """
    GIVEN a full-page form POST to the login route with an invalid CSRF token
    WHEN the 403 error page loads fresh and the user clicks its refresh button
    THEN ensure the page script initialized without errors and the refresh
         returns to the splash page that submitted the form, rather than
         re-requesting the POST-only /login and landing on a 405
    """
    with provide_app.test_request_context():
        login_path = url_for(ROUTES.SPLASH.LOGIN)
    splash_url = page.url
    page_errors = collect_page_errors(page=page)

    with page.expect_navigation():
        page.evaluate(
            """(loginPath) => {
            const form = document.createElement("form");
            form.method = "POST";
            form.action = loginPath;
            const csrfInput = document.createElement("input");
            csrfInput.name = "csrf_token";
            csrfInput.value = "invalid-csrf-token";
            form.appendChild(csrfInput);
            document.body.appendChild(form);
            form.submit();
        }""",
            login_path,
        )
    error_page_subheader = page.locator(f"{SPL.ERROR_PAGE_HANDLER} h2").first
    expect(error_page_subheader).to_have_text(IDENTIFIERS.HTML_403)
    page.wait_for_load_state("load")

    _assert_refresh_lands_on_splash(page=page, splash_url=splash_url)
    assert_no_page_errors(page_errors=page_errors)
