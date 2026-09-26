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


def _assert_refresh_leaves_error_page(*, page: Page) -> None:
    """Call after the "load" event: on a fresh document error.ts is a module
    script that runs before DOMContentLoaded, so its $(document).ready click
    binding is in place by load (no retry needed, unlike the document.write
    path handled in assert_visited_403_on_invalid_csrf_and_reload)."""
    error_page_subheader = page.locator(f"{SPL.ERROR_PAGE_HANDLER} h2").first
    page.locator(SPL.ERROR_PAGE_REFRESH_BTN).first.click()
    expect(error_page_subheader).to_be_hidden()


def test_429_error_page_loaded_fresh_refreshes_without_page_errors(page: Page):
    """
    GIVEN a full-page navigation that is rate limited
    WHEN the 429 error page loads fresh and the user clicks its refresh button
    THEN ensure the page script initialized without errors and the refresh
         navigates away from the error page
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
    _assert_refresh_leaves_error_page(page=page)
    assert_no_page_errors(page_errors=page_errors)


def test_403_error_page_loaded_fresh_refreshes_without_page_errors(
    page: Page, provide_app: Flask
):
    """
    GIVEN a full-page form POST to the login route with an invalid CSRF token
    WHEN the 403 error page loads fresh and the user clicks its refresh button
    THEN ensure the page script initialized without errors and the refresh
         navigates away from the error page
    """
    with provide_app.test_request_context():
        login_path = url_for(ROUTES.SPLASH.LOGIN)
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

    _assert_refresh_leaves_error_page(page=page)
    assert_no_page_errors(page_errors=page_errors)
