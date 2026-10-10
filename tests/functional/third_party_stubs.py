"""Keep the UI tests off the public CDNs without changing the page under test.

The page loads jQuery and Bootstrap from CDNs as parser-blocking scripts (see
`backend/templates/components/head/bundles.html`). A hung CDN request holds the `load` event
until it times out, which fails the shared fixture's `page.goto`. Instead of switching the page
to its local-bundle mode, the browser still requests the production CDN URLs and Playwright
answers them from the files `frontend/setup-vendor.sh` downloads. The production markup, the
integrity check on the served bytes and the request origins all stay in play.
"""

from pathlib import Path
from typing import Callable

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

JS_CONTENT_TYPE = "application/javascript"


def _serve_file(vendor_file: Path) -> Callable[[Route], None]:
    def handler(route: Route) -> None:
        route.fulfill(path=vendor_file, content_type=JS_CONTENT_TYPE)

    return handler


def _serve_empty_script(route: Route) -> None:
    route.fulfill(status=200, content_type=JS_CONTENT_TYPE, body="")


def stub_third_party_requests(
    *, context: BrowserContext, vendor_dir: Path = VENDOR_DIR
) -> None:
    """Answer the page's CDN scripts from `vendor_dir` and neutralize the analytics beacon.

    A CDN script is only stubbed when its vendor file exists, so a checkout that never ran
    `frontend/setup-vendor.sh` (a local run) keeps using the real CDN as before.
    """
    for url, file_name in CDN_SCRIPT_URLS_TO_VENDOR_FILES.items():
        vendor_file = vendor_dir / file_name
        if vendor_file.is_file():
            context.route(url, _serve_file(vendor_file))

    context.route(ANALYTICS_BEACON_URL, _serve_empty_script)
