from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from redis import Redis
from selenium.webdriver.remote.webdriver import WebDriver

from backend.cli.mock_constants import MOCK_UTUB_DESCRIPTION
from backend.metrics.events import DeviceType, EventName
from backend.models.utubs import Utubs
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.assert_utils import assert_on_429_page
from tests.functional.home_ui.selenium_utils import toggle_lhs_panels
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_to_home_page,
)
from tests.functional.metrics_helpers.db_utils import wait_for_metrics_row
from tests.functional.selenium_utils import (
    add_forced_rate_limit_header,
    wait_then_click_element,
)
from tests.functional.utubs_ui.selenium_utils import create_utub

pytestmark = pytest.mark.home_ui

# Headless Chrome at 1920x1080 (see `tests/functional/conftest.py::build_driver`)
# resolves to DESKTOP via `frontend/lib/device-type.ts`'s media-query check.
_EXPECTED_DEVICE_TYPE: int = DeviceType.DESKTOP.value

# The collapsible-deck click handler in `frontend/home/collapsible-decks.ts`
# attaches to `#MemberDeckHeaderAndCaret` (not `#MemberDeckHeader`). Targeting
# the same selector the production click handler is bound to keeps the test
# resilient to selector renames in the locator module.
_MEMBER_DECK_HEADER_AND_CARET: str = "#MemberDeckHeaderAndCaret"

# Bridges the gap between the `$.ajaxPrefilter` 429 handler in
# `frontend/lib/csrf.ts` (which calls `showNewPageOnAJAXHTMLResponse`, a
# `$.fadeOut(150)` -> `document.open() + document.write()` chain) and the
# metrics-client's `pagehide` -> `flushBeacon` listener. `document.write`
# replaces the page in-place and does NOT fire a native `pagehide` event,
# so the buffered `ui_rate_limit_hit` emit would never be flushed without
# this hook. The `ajaxComplete` callback fires synchronously right after
# the prefilter's `options.error` runs (which is where the emit happens)
# and BEFORE the 150ms `fadeOut` timer completes — so the dispatched
# `pagehide` reaches the metrics-client while its `_buffer` still holds
# the rate-limit event, and `sendBeacon` queues the POST before
# `document.write` tears the page down. `sendBeacon` survives the
# in-place navigation per the W3C Beacon spec.
_INSTALL_RATE_LIMIT_FLUSH_HOOK_JS: str = """
$(document).ajaxComplete(function (event, xhr) {
    if (xhr && xhr.status === 429) {
        const pageHideEvent = new PageTransitionEvent("pagehide", {
            persisted: false,
            bubbles: false,
            cancelable: false,
        });
        window.dispatchEvent(pageHideEvent);
    }
});
"""


def test_deck_collapse_emits_to_anonymous_metrics(
    browser: WebDriver,
    create_test_users: Any,
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics: Any,
):
    """
    GIVEN a logged-in user on the home page (no UTub selected) and the
        metrics pipeline activated end-to-end
    WHEN the user clicks the Member deck header (the desktop deck-collapse
        gesture), then the test dispatches a `pagehide` event to fire the
        metrics-client's real flush path
    THEN the flush worker drains the counter into Postgres and exactly one
        `AnonymousMetrics` row exists for `ui_deck_collapse` with
        `dimensions = {"device_type": 2, "deck": "members"}` and count == 1.

    The Member deck is chosen over UTubs/Tags because it has no selection-
    state preconditions — the click handler in
    `frontend/home/collapsible-decks.ts::setupMemberHeaderForMaximizeMinimize`
    fires the emit on any header click while the Member deck is expanded
    (the default state on home page load).
    """
    user_id_for_test = 1
    login_user_to_home_page(provide_app, browser, user_id_for_test)

    # First click collapses the Member deck (default state is expanded), so
    # the emit fires UI_DECK_COLLAPSE.
    wait_then_click_element(browser, _MEMBER_DECK_HEADER_AND_CARET, time=10)

    expected_dimensions: dict[str, Any] = {
        "device_type": _EXPECTED_DEVICE_TYPE,
        "deck": "members",
    }
    matched_row = wait_for_metrics_row(
        browser=browser,
        redis_client=metrics_redis_client,
        pg_conn=pg_conn_for_metrics,
        event_name=EventName.UI_DECK_COLLAPSE,
        expected_dimensions=expected_dimensions,
    )
    assert matched_row["count"] == 1
    assert matched_row["bucket_start"] is not None


def test_lhs_collapse_and_expand_emit_to_anonymous_metrics(
    browser: WebDriver,
    create_test_tags: Any,
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics: Any,
):
    """
    GIVEN a logged-in user on the desktop home page with a UTub selected and
        the metrics pipeline activated end-to-end
    WHEN the user collapses/expands the LHS via the seam toggle, then again
        via the URL-deck-header mirror toggle
    THEN four `AnonymousMetrics` rows exist — `ui_lhs_collapse` and
        `ui_lhs_expand` for each `source` (`"seam"` and `"url_header"`) — each
        with `device_type = 2` and count == 1, proving both affordances
        forward their distinct `source` dim end-to-end.
    """
    user_id_for_test = 1
    with provide_app.app_context():
        utub = Utubs.query.first()
        utub_id = utub.id
    login_user_and_select_utub_by_utubid(
        provide_app, browser, user_id=user_id_for_test, utub_id=utub_id
    )

    def assert_toggle_emits(source: str):
        # Default state is expanded, so the first click collapses (emits
        # UI_LHS_COLLAPSE) and the second click expands (emits UI_LHS_EXPAND),
        # both carrying the affordance's `source` dim.
        toggle_lhs_panels(browser, via=source)
        collapse_row = wait_for_metrics_row(
            browser=browser,
            redis_client=metrics_redis_client,
            pg_conn=pg_conn_for_metrics,
            event_name=EventName.UI_LHS_COLLAPSE,
            expected_dimensions={
                "device_type": _EXPECTED_DEVICE_TYPE,
                "source": source,
            },
        )
        assert collapse_row["count"] == 1
        assert collapse_row["bucket_start"] is not None

        toggle_lhs_panels(browser, via=source)
        expand_row = wait_for_metrics_row(
            browser=browser,
            redis_client=metrics_redis_client,
            pg_conn=pg_conn_for_metrics,
            event_name=EventName.UI_LHS_EXPAND,
            expected_dimensions={
                "device_type": _EXPECTED_DEVICE_TYPE,
                "source": source,
            },
        )
        assert expand_row["count"] == 1
        assert expand_row["bucket_start"] is not None

    assert_toggle_emits(source="seam")
    assert_toggle_emits(source="url_header")


def test_rate_limit_hit_emits_to_anonymous_metrics(
    browser: WebDriver,
    create_test_users: Any,
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics: Any,
):
    """
    GIVEN a logged-in user on the home page and the metrics pipeline
        activated end-to-end
    WHEN the user attempts an action whose backend response is forced to a
        429 via `add_forced_rate_limit_header`, the global
        `$.ajaxPrefilter` 429 handler in `frontend/lib/csrf.ts` runs and
        emits `UI_RATE_LIMIT_HIT` to the metrics-client buffer, then the
        test's `ajaxComplete` hook dispatches a synchronous `pagehide`
        that fires the metrics-client's `flushBeacon` -> `sendBeacon`
        path BEFORE `showNewPageOnAJAXHTMLResponse`'s `document.write`
        replaces the page
    THEN the flush worker drains the counter into Postgres and exactly
        one `AnonymousMetrics` row exists for `ui_rate_limit_hit` with
        `dimensions = {"device_type": 2}` and count == 1.

    The create-UTub form-submit is chosen as the rate-limited gesture
    because (a) the existing 429 UI test `test_create_utub_at_rate_limit`
    in `tests/functional/utubs_ui/test_create_utub_ui.py` proves the
    `add_forced_rate_limit_header` -> form submit -> 429 page path is
    reliable, and (b) the gesture's own emit (`UI_FORM_SUBMIT`) lands on
    a different `event_name` so it cannot be confused with the rate-limit
    emit when querying `AnonymousMetrics`.
    """
    user_id_for_test = 1
    login_user_to_home_page(provide_app, browser, user_id_for_test)

    browser.execute_script(_INSTALL_RATE_LIMIT_FLUSH_HOOK_JS)
    add_forced_rate_limit_header(browser)

    create_utub(browser, UTS.TEST_UTUB_NAME_1, MOCK_UTUB_DESCRIPTION)
    wait_then_click_element(browser, HPL.BUTTON_UTUB_SUBMIT_CREATE)

    # Confirm the page-replacement chain (`showNewPageOnAJAXHTMLResponse`)
    # has completed and the 429 error page is rendered. This proves the
    # prefilter's error callback ran end-to-end (which means the
    # `UI_RATE_LIMIT_HIT` emit fired and the `ajaxComplete` hook flushed
    # the buffer to `sendBeacon`) before we begin polling Postgres.
    assert_on_429_page(browser)

    expected_dimensions: dict[str, Any] = {
        "device_type": _EXPECTED_DEVICE_TYPE,
    }
    matched_row = wait_for_metrics_row(
        browser=browser,
        redis_client=metrics_redis_client,
        pg_conn=pg_conn_for_metrics,
        event_name=EventName.UI_RATE_LIMIT_HIT,
        expected_dimensions=expected_dimensions,
    )
    assert matched_row["count"] == 1
    assert matched_row["bucket_start"] is not None
