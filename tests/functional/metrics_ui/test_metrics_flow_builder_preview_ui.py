from __future__ import annotations

import json
import re
import time
from typing import Callable
from urllib.parse import parse_qs, urlparse

import pytest
from flask import Flask
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, Request, Route, expect

from backend import db
from backend.config import ConfigTestUI
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.locators import MetricsDashboardLocators as MDL
from tests.functional.metrics_ui.playwright_utils import (
    MOBILE_VIEWPORT,
    OPEN_EVENT,
    SUBMIT_EVENT,
    VIEWPORTS,
    builder_field,
    fill_blank_steps,
    open_flows_tab,
    open_new_builder,
    page_overflow,
    seed_add_url_funnel_metrics,
)

pytestmark = pytest.mark.metrics_ui

FLOW_PREVIEW_URL_RE: re.Pattern[str] = re.compile(
    r".*/admin/metrics/flows/preview(\?.*)?$"
)
# The controller waits out a 2.5 s minimum send interval, so waits that span a
# deferral need more than the default 5 s expect timeout.
SETTLE_TIMEOUT_MS: int = 15_000
DESKTOP_VIEWPORT_WIDTH: int = 1280
SOFT_KEYBOARD_VIEWPORT: dict[str, int] = {"width": 420, "height": 480}
ANNOUNCE_RESULT_RE: re.Pattern[str] = re.compile(
    r"^Preview updated: \S+ of \S+ succeeded, \S+ conversion\.$"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class HeldPreviews:
    """Holds every preview request until `release_all()`; afterwards requests pass
    straight through to the real endpoint."""

    def __init__(self) -> None:
        self._held: list[Route] = []
        self._released: bool = False

    def handle(self, route: Route) -> None:
        if self._released:
            route.continue_()
        else:
            self._held.append(route)

    @property
    def held_count(self) -> int:
        return len(self._held)

    def release_all(self) -> None:
        self._released = True
        for route in self._held:
            try:
                route.continue_()
            except PlaywrightError:
                # The page aborted this superseded request already.
                continue
        self._held.clear()


def _wait_until(page: Page, condition: Callable[[], bool]) -> None:
    """Poll through the Playwright event loop so route handlers keep running."""
    deadline = time.monotonic() + SETTLE_TIMEOUT_MS / 1000
    while time.monotonic() < deadline:
        if condition():
            return
        page.wait_for_timeout(50)
    pytest.fail("condition not met before the settle timeout")


def _open_builder(
    *,
    page: Page,
    app: Flask,
    port: int,
    config: ConfigTestUI,
    viewport: dict[str, int] | None = None,
) -> None:
    open_flows_tab(page=page, app=app, port=port, config=config, viewport=viewport)
    open_new_builder(page)


def _expect_settled_card(page: Page) -> None:
    expect(page.locator(MDL.FLOW_PREVIEW_CARD)).to_be_visible(timeout=SETTLE_TIMEOUT_MS)
    expect(page.locator(MDL.FLOW_PREVIEW_BODY)).not_to_have_attribute(
        "aria-busy", "true", timeout=SETTLE_TIMEOUT_MS
    )
    expect(page.locator(MDL.FLOW_PREVIEW_STATUS)).to_be_hidden(
        timeout=SETTLE_TIMEOUT_MS
    )


def _route_status(*, page: Page, status: int, body: dict[str, object]) -> list[Route]:
    """Answer every preview request with `status`; returns the list the handler
    appends each fulfilled route to (its length is the request count)."""
    answered: list[Route] = []

    def _fulfill(route: Route) -> None:
        answered.append(route)
        route.fulfill(
            status=status,
            content_type="application/json",
            body=json.dumps(body),
        )

    page.route(FLOW_PREVIEW_URL_RE, _fulfill)
    return answered


# ---------------------------------------------------------------------------
# Placeholder, updating, results
# ---------------------------------------------------------------------------


@VIEWPORTS
def test_preview_placeholder_on_open_and_after_draft_turns_invalid(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    viewport: dict[str, int],
):
    """
    GIVEN a new flow builder
    WHEN it opens, a valid draft settles, and step 1's stream is changed (which
        clears its event)
    THEN the placeholder shows on open, the card replaces it, and the
        placeholder returns once the draft is no longer valid.
    """
    _open_builder(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    expect(page.locator(MDL.FLOW_PREVIEW_PLACEHOLDER)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_PREVIEW_PLACEHOLDER
    )

    fill_blank_steps(page)
    _expect_settled_card(page)
    expect(page.locator(MDL.FLOW_PREVIEW_PLACEHOLDER)).to_have_count(0)

    builder_field(page, 1, "stream").select_option("api")
    expect(page.locator(MDL.FLOW_PREVIEW_PLACEHOLDER)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_PREVIEW_PLACEHOLDER, timeout=SETTLE_TIMEOUT_MS
    )
    expect(page.locator(MDL.FLOW_PREVIEW_CARD)).to_have_count(0)


def test_preview_body_is_busy_with_status_line_until_response_released(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a valid draft whose preview response is held
    WHEN the request is pending
    THEN the body is aria-busy and the status line reads "Updating preview";
        both clear once the response is released and the card settles.
    """
    held = HeldPreviews()
    page.route(FLOW_PREVIEW_URL_RE, held.handle)
    _open_builder(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )
    fill_blank_steps(page)

    _wait_until(page, lambda: held.held_count >= 1)
    expect(page.locator(MDL.FLOW_PREVIEW_BODY)).to_have_attribute("aria-busy", "true")
    expect(page.locator(MDL.FLOW_PREVIEW_STATUS)).to_be_visible()
    expect(page.locator(MDL.FLOW_PREVIEW_STATUS)).to_contain_text(
        UI_TEST_STRINGS.METRICS_FLOW_PREVIEW_UPDATING
    )

    held.release_all()
    _expect_settled_card(page)
    expect(page.locator(MDL.FLOW_PREVIEW_BODY)).not_to_have_attribute(
        "aria-busy", "true"
    )


def test_preview_zero_count_shows_empty_state_and_announces_it(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN no metric rows for the OPEN or SUBMIT events (seed deliberately not applied)
    WHEN the unfiltered OPEN then SUBMIT draft is built against the real endpoint
    THEN the preview card shows the empty state and the live region announces it.
    """
    with provide_app.app_context():
        # Precondition: the unfiltered draft counts every row for these events.
        assert (
            db.session.query(Anonymous_Metrics)
            .filter(Anonymous_Metrics.event_name.in_([OPEN_EVENT, SUBMIT_EVENT]))
            .count()
            == 0
        )
    _open_builder(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )
    fill_blank_steps(page)

    expect(page.locator(MDL.FLOW_PREVIEW_CARD_EMPTY)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_EMPTY, timeout=SETTLE_TIMEOUT_MS
    )
    expect(page.locator(MDL.FLOW_PREVIEW_LIVE_REGION)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_PREVIEW_ANNOUNCE_EMPTY
    )
    live = page.locator(MDL.FLOW_PREVIEW_LIVE_REGION)
    # visually-hidden must be defined on this page (it lives in base.css).
    box = live.bounding_box()
    assert box is not None
    assert box["width"] <= 1 and box["height"] <= 1


def test_preview_real_result_renders_seeded_counts_and_announces_them(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN the add-URL funnel metrics seeded
    WHEN the unfiltered OPEN then SUBMIT draft is built against the real endpoint
    THEN the card shows non-zero counts (no empty state) and the live region holds
        the result sentence for them.
    """
    seed_add_url_funnel_metrics(app=provide_app)
    _open_builder(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )
    fill_blank_steps(page)

    _expect_settled_card(page)
    expect(page.locator(MDL.FLOW_PREVIEW_CARD_EMPTY)).to_have_count(0)
    expect(page.locator(MDL.FLOW_PREVIEW_LIVE_REGION)).to_have_text(ANNOUNCE_RESULT_RE)
    counts = page.locator(MDL.FLOW_PREVIEW_STEP_COUNT).all_inner_texts()
    assert counts, "preview card rendered no step counts"
    assert all(text.strip() not in ("", "0") for text in counts)
    announcement = page.locator(MDL.FLOW_PREVIEW_LIVE_REGION).inner_text()
    succeeded, total = re.findall(r"updated: (\S+) of (\S+) succeeded", announcement)[0]
    assert counts[0].strip() == total
    assert counts[-1].strip() == succeeded


def test_preview_window_change_sends_new_window_with_same_body(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN the builder open on a settled preview
    WHEN the dashboard time window changes
    THEN a preview request carries the new window and the same body, and the card
        settles again.
    """
    seen: list[Request] = []

    def _record(request: Request) -> None:
        if FLOW_PREVIEW_URL_RE.match(request.url):
            seen.append(request)

    page.on("request", _record)
    seed_add_url_funnel_metrics(app=provide_app)
    _open_builder(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )
    fill_blank_steps(page)
    _expect_settled_card(page)
    assert len(seen) >= 1
    first_body = seen[-1].post_data
    assert parse_qs(urlparse(seen[-1].url).query)["window"] == ["day"]
    before = len(seen)

    page.locator(MDL.WINDOW_WEEK_BUTTON).click()

    _wait_until(page, lambda: len(seen) > before)
    latest = seen[-1]
    assert parse_qs(urlparse(latest.url).query)["window"] == ["week"]
    assert latest.post_data == first_body
    _expect_settled_card(page)


# ---------------------------------------------------------------------------
# Staged failures (page.route)
# ---------------------------------------------------------------------------


def test_preview_400_marks_field_and_keeps_focus_on_edited_control(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a routed 400 for steps.0.event_name
    WHEN the preview request is answered
    THEN step 1's event control is aria-invalid, focus stays on the control last
        edited, and the live region announces the one problem.
    """
    _route_status(
        page=page,
        status=400,
        body={
            "status": "Failure",
            "message": "Invalid flow",
            "errors": {"steps.0.event_name": ["Pick an event."]},
        },
    )
    _open_builder(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )
    fill_blank_steps(page)
    edited = builder_field(page, 2, "label")
    edited.press_sequentially("!")

    expect(builder_field(page, 1, "event_name")).to_have_attribute(
        "aria-invalid", "true", timeout=SETTLE_TIMEOUT_MS
    )
    expect(edited).to_be_focused()
    expect(page.locator(MDL.FLOW_PREVIEW_LIVE_REGION)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_PREVIEW_ANNOUNCE_PROBLEM_ONE
    )


def test_preview_429_shows_rate_limited_with_retry_and_keeps_draft(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a routed JSON 429
    WHEN the preview request is answered
    THEN the rate-limited message and Retry show, the page is not replaced, the
        draft is intact and the live region holds the message.
    """
    _route_status(
        page=page,
        status=429,
        body={"status": "Failure", "message": "Too many requests"},
    )
    _open_builder(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )
    page.evaluate("() => { window.__previewSentinel = true; }")
    fill_blank_steps(page)

    expect(page.locator(MDL.FLOW_PREVIEW_ERROR)).to_contain_text(
        UI_TEST_STRINGS.METRICS_FLOW_RATE_LIMITED, timeout=SETTLE_TIMEOUT_MS
    )
    # A replaced or reloaded page would have lost the sentinel.
    assert page.evaluate("() => window.__previewSentinel === true")
    expect(page.locator(MDL.FLOW_PREVIEW_RETRY)).to_be_visible()
    expect(page.locator(MDL.FLOW_PREVIEW_LIVE_REGION)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_RATE_LIMITED
    )
    expect(page.locator(MDL.FLOW_BUILDER_FORM)).to_be_visible()
    expect(builder_field(page, 1, "event_name")).to_have_value(OPEN_EVENT)
    expect(builder_field(page, 2, "event_name")).to_have_value(SUBMIT_EVENT)
    expect(builder_field(page, 1, "label")).to_have_value("Step 1 label")


def test_preview_500_retry_keeps_focus_until_result_then_moves_to_title(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a routed 500 and then a held request
    WHEN Retry is clicked
    THEN the failure message and Retry show; focus stays on the aria-disabled
        Retry while the held request is pending; once a real success lands the
        focus moves to the preview title.
    """
    held = HeldPreviews()
    phase = {"failing": True}

    def _handle(route: Route) -> None:
        if phase["failing"]:
            route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"status": "Failure", "message": "boom"}),
            )
        else:
            held.handle(route)

    page.route(FLOW_PREVIEW_URL_RE, _handle)
    _open_builder(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )
    fill_blank_steps(page)

    expect(page.locator(MDL.FLOW_PREVIEW_ERROR)).to_contain_text(
        UI_TEST_STRINGS.METRICS_FLOW_PREVIEW_FAILED, timeout=SETTLE_TIMEOUT_MS
    )
    expect(page.locator(MDL.FLOW_PREVIEW_LIVE_REGION)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_PREVIEW_FAILED
    )
    # Let any trailing deferred send (2.5 s minimum interval) fire and fail first,
    # so only the Retry-driven request is held.
    page.wait_for_timeout(3000)
    expect(page.locator(MDL.FLOW_PREVIEW_ERROR)).to_be_visible()
    phase["failing"] = False
    retry = page.locator(MDL.FLOW_PREVIEW_RETRY)
    retry.focus()
    retry.click()

    _wait_until(page, lambda: held.held_count >= 1)
    expect(retry).to_have_attribute("aria-disabled", "true")
    expect(retry).to_be_focused()

    held.release_all()
    _expect_settled_card(page)
    expect(page.locator(MDL.FLOW_PREVIEW_TITLE)).to_be_focused()


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def test_preview_sits_right_of_form_at_1280(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN the builder at 1280px
    THEN the preview column starts to the right of the form's right edge.
    """
    _open_builder(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport={"width": DESKTOP_VIEWPORT_WIDTH, "height": 900},
    )
    form = page.locator(MDL.FLOW_BUILDER_FORM).bounding_box()
    preview = page.locator(MDL.FLOW_PREVIEW_REGION).bounding_box()
    assert form is not None and preview is not None
    assert preview["x"] > form["x"] + form["width"]


def test_preview_stacks_below_save_at_420_without_occluding_the_edited_field(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN the builder at 420px
    THEN the "Preview" title is visible below Save, typing in a label near the
        bottom keeps it in view, nothing scrolls horizontally, and with a short
        viewport (soft keyboard) the focused input is unobstructed, no preview
        ancestor is sticky or fixed, and scrollY is unchanged once it settles.
    """
    seen: list[Request] = []
    page.on(
        "request",
        lambda request: (
            seen.append(request) if FLOW_PREVIEW_URL_RE.match(request.url) else None
        ),
    )
    _open_builder(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=MOBILE_VIEWPORT,
    )
    fill_blank_steps(page)
    _expect_settled_card(page)

    title = page.locator(MDL.FLOW_PREVIEW_TITLE)
    expect(title).to_be_visible()
    expect(title).to_have_text(UI_TEST_STRINGS.METRICS_FLOW_PREVIEW_HEADING)
    save_box = page.locator(MDL.FLOW_BUILDER_SAVE_BUTTON).bounding_box()
    title_box = title.bounding_box()
    assert save_box is not None and title_box is not None
    assert title_box["y"] > save_box["y"]
    assert page_overflow(page) <= 0

    page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
    label = builder_field(page, 2, "label")
    label.scroll_into_view_if_needed()
    label.press_sequentially("!")
    label_box = label.bounding_box()
    viewport_height = page.evaluate("() => window.innerHeight")
    assert label_box is not None
    assert label_box["y"] >= 0
    assert label_box["y"] + label_box["height"] <= viewport_height
    assert page_overflow(page) <= 0

    page.set_viewport_size(SOFT_KEYBOARD_VIEWPORT)
    label.focus()
    label.scroll_into_view_if_needed()
    requests_before = len(seen)
    label.press_sequentially("?")
    short_box = label.bounding_box()
    assert short_box is not None
    short_height = page.evaluate("() => window.innerHeight")
    assert short_box["y"] >= 0
    assert short_box["y"] + short_box["height"] <= short_height
    center_is_input = label.evaluate(
        """(el) => {
            const rect = el.getBoundingClientRect();
            return document.elementFromPoint(
                rect.x + rect.width / 2, rect.y + rect.height / 2) === el;
        }"""
    )
    assert center_is_input
    positions = page.locator(MDL.FLOW_PREVIEW_REGION).evaluate(
        """(el) => {
            const out = [];
            for (let node = el; node && node !== document.documentElement;
                 node = node.parentElement) {
                out.push(getComputedStyle(node).position);
            }
            return out;
        }"""
    )
    assert positions
    assert not {"sticky", "fixed"} & set(positions)

    # The edit above started a new preview cycle: wait for its request, then for
    # it to settle, so the checks below run after the re-render.
    scroll_before = page.evaluate("() => window.scrollY")
    _wait_until(page, lambda: len(seen) > requests_before)
    _expect_settled_card(page)
    assert page.evaluate("() => window.scrollY") == scroll_before
    settled_box = label.bounding_box()
    assert settled_box is not None
    assert settled_box["y"] >= 0
    assert settled_box["y"] + settled_box["height"] <= short_height
    assert label.evaluate(
        """(el) => {
            const rect = el.getBoundingClientRect();
            return document.elementFromPoint(
                rect.x + rect.width / 2, rect.y + rect.height / 2) === el;
        }"""
    )
