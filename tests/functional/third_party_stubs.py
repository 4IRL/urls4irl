"""Keep the UI tests off the public CDNs without changing the page under test.

A hung parser-blocking CDN script holds the `load` event and fails the fixture's `page.goto`.
Rather than switching the page to its local-bundle mode, the production CDN URLs are stubbed
from the vendor files, so the production markup and integrity checks stay in play.
"""

from collections.abc import Callable, Collection
from pathlib import Path

from playwright.sync_api import BrowserContext, Route

VENDOR_DIR = Path(__file__).resolve().parents[2] / "frontend" / "public" / "vendor"

# URL the page requests -> file `frontend/setup-vendor.sh` writes into VENDOR_DIR.
CDN_SCRIPT_URLS_TO_VENDOR_FILES: dict[str, str] = {
    "https://code.jquery.com/jquery-3.7.1.min.js": "jquery-3.7.1.min.js",
    "https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js": (
        "bootstrap.bundle.min.js"
    ),
}
ANALYTICS_BEACON_URL = "https://static.cloudflareinsights.com/beacon.min.js"

# Every metrics test that asserts on the real `sendBeacon` flush requests this fixture. Any
# `context.route` makes Chromium pause every request (and disables its HTTP cache), so a beacon
# fired while a page unloads can be aborted (`net::ERR_ABORTED`) and its event lost. Those tests
# keep the real network so they exercise the production flush path.
UNLOAD_BEACON_TEST_FIXTURE = "metrics_redis_client"

JS_CONTENT_TYPE = "application/javascript"


def _serve_file(vendor_file: Path) -> Callable[[Route], None]:
    def handler(route: Route) -> None:
        route.fulfill(path=vendor_file, content_type=JS_CONTENT_TYPE)

    return handler


def _serve_empty_script(route: Route) -> None:
    route.fulfill(status=200, content_type=JS_CONTENT_TYPE, body="")


def stub_third_party_requests(
    *,
    context: BrowserContext,
    test_fixture_names: Collection[str],
    vendor_dir: Path = VENDOR_DIR,
) -> None:
    """Answer the page's CDN scripts from `vendor_dir` and neutralize the analytics beacon.

    Does nothing for a test that requests `UNLOAD_BEACON_TEST_FIXTURE` (see its comment).
    Stubbing applies where `frontend/public/vendor` exists (CI and host runs); local container
    runs do not mount it and keep using the real CDN. A script is only stubbed when its vendor
    file exists.
    """
    if UNLOAD_BEACON_TEST_FIXTURE in test_fixture_names:
        return

    for url, file_name in CDN_SCRIPT_URLS_TO_VENDOR_FILES.items():
        vendor_file = vendor_dir / file_name
        if vendor_file.is_file():
            context.route(url, _serve_file(vendor_file))

    context.route(ANALYTICS_BEACON_URL, _serve_empty_script)
