from __future__ import annotations

import pytest
from playwright.sync_api import Page

from tests.functional.third_party_stubs import (
    CDN_SCRIPT_URLS_TO_VENDOR_FILES,
    VENDOR_DIR,
)

pytestmark = pytest.mark.splash_ui

LOCAL_VENDOR_FALLBACK_PATH = "/static/dist/vendor/"

requires_vendor_files = pytest.mark.skipif(
    not all(
        (VENDOR_DIR / name).is_file()
        for name in CDN_SCRIPT_URLS_TO_VENDOR_FILES.values()
    ),
    reason="frontend/setup-vendor.sh has not been run; CDN scripts are not stubbed",
)


@requires_vendor_files
def test_stubbed_cdn_scripts_load_without_the_local_fallback(page: Page):
    """
    GIVEN the UI-test context answers the jQuery and Bootstrap CDN URLs from the vendor files
    WHEN the splash page is reloaded
    THEN both libraries are defined and the template's local fallback is never requested,
        proving the browser accepted the stubbed bytes (integrity hash and CORS) as the CDN scripts
    """
    requested_urls: list[str] = []
    page.on("request", lambda request: requested_urls.append(request.url))

    page.reload()

    assert page.evaluate("typeof window.jQuery") == "function"
    assert page.evaluate("typeof window.bootstrap") == "object"
    fallback_requests = [
        url for url in requested_urls if LOCAL_VENDOR_FALLBACK_PATH in url
    ]
    assert not fallback_requests, (
        f"Local vendor fallback was requested: {fallback_requests}"
    )
