"""Unit tests for the UI-test helper that answers the page's CDN scripts from local vendor files."""

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from playwright.sync_api import BrowserContext, Route

from tests.functional.third_party_stubs import (
    ANALYTICS_BEACON_URL,
    CDN_SCRIPT_URLS_TO_VENDOR_FILES,
    JS_CONTENT_TYPE,
    UNLOAD_BEACON_TEST_FIXTURE,
    stub_third_party_requests,
)

pytestmark = pytest.mark.unit

JQUERY_URL, BOOTSTRAP_URL = CDN_SCRIPT_URLS_TO_VENDOR_FILES
JQUERY_FILE_NAME = CDN_SCRIPT_URLS_TO_VENDOR_FILES[JQUERY_URL]
BUNDLES_TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "backend"
    / "templates"
    / "components"
    / "head"
    / "bundles.html"
)
LOCAL_FALLBACK_PATH = "/static/dist/vendor"
FUNCTIONAL_TESTS_DIR = Path(__file__).resolve().parents[1] / "functional"


class FakeContext:
    """Records the (url -> handler) routes the helper registers."""

    def __init__(self) -> None:
        self.routes: dict[str, Callable[[Route], None]] = {}

    def route(self, url: str, handler: Callable[[Route], None]) -> None:
        self.routes[url] = handler


class FakeRoute:
    """Captures the arguments of the single `fulfill` call a handler makes."""

    def __init__(self) -> None:
        self.fulfilled: dict[str, Any] | None = None

    def fulfill(self, **kwargs: Any) -> None:
        self.fulfilled = kwargs


def _stub(vendor_dir: Path, test_fixture_names: tuple[str, ...] = ()) -> FakeContext:
    context = FakeContext()
    stub_third_party_requests(
        context=cast(BrowserContext, context),
        test_fixture_names=test_fixture_names,
        vendor_dir=vendor_dir,
    )
    return context


def _fulfill(handler: Callable[[Route], None]) -> dict[str, Any]:
    route = FakeRoute()
    handler(cast(Route, route))
    assert route.fulfilled is not None
    return route.fulfilled


def _write_vendor_files(vendor_dir: Path, file_names: list[str]) -> None:
    for file_name in file_names:
        (vendor_dir / file_name).write_text("/* vendored */")


def test_cdn_urls_match_the_page_template():
    """
    GIVEN the production head template that requests the CDN scripts
    WHEN the URLs the helper stubs are looked up in its text
    THEN each CDN URL, the analytics beacon URL and the local fallback path appear in it,
        so the stub still intercepts the real requests
    """
    template_text = BUNDLES_TEMPLATE.read_text()

    for url in (
        *CDN_SCRIPT_URLS_TO_VENDOR_FILES,
        ANALYTICS_BEACON_URL,
        LOCAL_FALLBACK_PATH,
    ):
        assert url in template_text


def test_cdn_scripts_are_served_from_their_vendor_files(tmp_path: Path):
    """
    GIVEN both vendor files exist
    WHEN the helper is applied to a context
    THEN each CDN URL is fulfilled from its own file as JavaScript
    """
    _write_vendor_files(tmp_path, list(CDN_SCRIPT_URLS_TO_VENDOR_FILES.values()))

    context = _stub(tmp_path)

    for url, file_name in CDN_SCRIPT_URLS_TO_VENDOR_FILES.items():
        assert _fulfill(context.routes[url]) == {
            "path": tmp_path / file_name,
            "content_type": JS_CONTENT_TYPE,
        }


def test_cdn_script_is_left_on_the_real_cdn_without_its_vendor_file(tmp_path: Path):
    """
    GIVEN only the jQuery vendor file exists (setup-vendor.sh never ran fully)
    WHEN the helper is applied
    THEN jQuery is stubbed and Bootstrap keeps using the real CDN
    """
    _write_vendor_files(tmp_path, [JQUERY_FILE_NAME])

    context = _stub(tmp_path)

    assert JQUERY_URL in context.routes
    assert BOOTSTRAP_URL not in context.routes


def test_no_cdn_script_is_stubbed_without_any_vendor_files(tmp_path: Path):
    """
    GIVEN a checkout that never downloaded the vendor files
    WHEN the helper is applied
    THEN no CDN script is intercepted
    """
    context = _stub(tmp_path)

    assert set(context.routes) == {ANALYTICS_BEACON_URL}


def test_analytics_beacon_is_answered_with_an_empty_script(tmp_path: Path):
    """
    GIVEN the helper is applied
    WHEN the page requests the Cloudflare analytics beacon
    THEN it receives an empty 200 JavaScript response and never reaches the network
    """
    context = _stub(tmp_path)

    assert _fulfill(context.routes[ANALYTICS_BEACON_URL]) == {
        "status": 200,
        "content_type": JS_CONTENT_TYPE,
        "body": "",
    }


def test_nothing_is_intercepted_for_a_test_that_reads_the_unload_beacon(tmp_path: Path):
    """
    GIVEN both vendor files exist and the test requests the metrics fixture
    WHEN the helper is applied
    THEN no route is registered, so Chromium never pauses requests and the page's
        `sendBeacon` on unload cannot be aborted by interception
    """
    _write_vendor_files(tmp_path, list(CDN_SCRIPT_URLS_TO_VENDOR_FILES.values()))

    context = _stub(tmp_path, test_fixture_names=("page", UNLOAD_BEACON_TEST_FIXTURE))

    assert context.routes == {}


def test_every_metrics_ui_test_module_requests_the_unload_beacon_fixture():
    """
    GIVEN the metrics UI test modules, which assert on the real `sendBeacon` flush
    WHEN each is searched for the fixture the helper keys its opt-out on
    THEN every one requests it, so none is silently stubbed and left flaky
    """
    metrics_ui_modules = sorted(FUNCTIONAL_TESTS_DIR.glob("*/test_*_metrics_ui.py"))
    assert metrics_ui_modules, "no metrics UI test modules found"

    missing_fixture = [
        module.name
        for module in metrics_ui_modules
        if UNLOAD_BEACON_TEST_FIXTURE not in module.read_text()
    ]
    assert missing_fixture == []
