from __future__ import annotations

import json
import re
from typing import Any

import pytest
from flask import Flask
from playwright.sync_api import Locator, Page, Route, expect

from backend import db
from backend.config import ConfigTestUI
from backend.metrics.events import EventName
from backend.metrics.flow_limits import FLOW_LIMITS
from backend.models.metric_flows import Metric_Flows
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.locators import MetricsDashboardLocators as MDL
from tests.functional.metrics_ui.playwright_utils import (
    EXPECTED_FLOW_CARD_COUNT,
    FLOW_LIST_URL_RE,
    FLOW_QUERY_URL_RE,
    LONG_FLOW_NAME,
    MIN_TOUCH_TARGET_PX,
    MOBILE_VIEWPORT,
    SEEDED_SUBMIT_OTHER_FORM_COUNT,
    SEEDED_SUBMIT_URL_CREATE_COUNT,
    VIEWPORTS,
    HeldFlowQueries,
    SeedCustomFlows,
    build_valid_flow_steps,
    count_text,
    custom_card,
    filtered_breakdown_definition,
    open_flows_tab,
    removed_event_definition,
    seed_add_url_funnel_metrics,
    two_step_filtered_definition,
)
from tests.functional.playwright_utils import wait_then_click_element

pytestmark = pytest.mark.metrics_ui

FLOW_CATALOG_URL_RE: re.Pattern[str] = re.compile(r".*/admin/metrics/flows/catalog$")
FLOW_UPDATE_URL_RE: re.Pattern[str] = re.compile(
    r".*/admin/metrics/flows/custom_[1-9][0-9]*$"
)
FLOW_QUERY_PATH: str = "/api/metrics/query/flow"
OPEN_EVENT: str = EventName.UI_URL_CREATE_OPEN.value
SUBMIT_EVENT: str = EventName.UI_FORM_SUBMIT.value
BUILDER_INPUT_FONT_SIZE: str = "16px"
ERR_TARGET_NOT_FOUND: int = 5
JSON_HEADERS: dict[str, str] = {"X-Requested-With": "XMLHttpRequest"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_new_builder(page: Page) -> None:
    """Click "+ New flow" and wait until the catalog loaded and the form is
    interactive (the heading keeps focus through the load)."""
    page.locator(MDL.FLOWS_NEW_BUTTON).click()
    expect(page.locator(MDL.FLOW_BUILDER_FORM)).to_be_visible()
    expect(page.locator(MDL.FLOW_BUILDER_HEADING)).to_be_focused()


def _open_edit_builder(page: Page, flow_id: str) -> None:
    custom_card(page, flow_id).locator(".flow-edit-btn").click()
    expect(page.locator(MDL.FLOW_BUILDER_FORM)).to_be_visible()
    expect(page.locator(MDL.FLOW_BUILDER_HEADING)).to_be_focused()


def _step(page: Page, position: int) -> Locator:
    return page.locator(MDL.FLOW_BUILDER_STEP).nth(position - 1)


def _field(page: Page, position: int, field: str) -> Locator:
    return _step(page, position).locator(f"[data-field={field}]")


def _action(page: Page, position: int, action: str) -> Locator:
    return _step(page, position).locator(f"button[data-action={action}]")


def _fill_blank_steps(page: Page) -> None:
    """Give the two blank steps of a new draft a label and an event each."""
    for position, event in ((1, OPEN_EVENT), (2, SUBMIT_EVENT)):
        _field(page, position, "label").fill(f"Step {position} label")
        _field(page, position, "event_name").select_option(event)
        expect(_field(page, position, "event_name")).to_have_value(event)


def _make_draft_dirty(page: Page) -> None:
    page.locator(MDL.FLOW_BUILDER_NAME_INPUT).fill("Unsaved work")


def _get_json(page: Page, url: str) -> dict[str, Any]:
    return page.evaluate(
        """async ({url, headers}) => {
            const response = await fetch(url, {headers, credentials: "same-origin"});
            return await response.json();
        }""",
        {"url": url, "headers": JSON_HEADERS},
    )


def _list_entry(page: Page, flow_id: str) -> dict[str, Any]:
    flows = _get_json(page, "/admin/metrics/flows")["flows"]
    [entry] = [flow for flow in flows if flow["id"] == flow_id]
    return entry


def _funnel_counts(page: Page, flow_id: str) -> list[dict[str, Any]]:
    """Per-step count and breakdown of the `/flow` response (the response is
    only `{"steps": [...]}`; derived fields such as pct_of_top are dropped)."""
    steps = _get_json(page, f"{FLOW_QUERY_PATH}?flow_id={flow_id}&window=day")["steps"]
    return [{"count": step["count"], "breakdown": step["breakdown"]} for step in steps]


def _reload_flows_tab(page: Page) -> None:
    page.reload()
    wait_then_click_element(page=page, css_selector=MDL.TAB_FLOWS_BUTTON)
    expect(page.locator(MDL.FLOWS_COUNT)).not_to_have_text(
        UI_TEST_STRINGS.METRICS_FLOWS_COUNT_LOADING
    )
    expect(page.locator(MDL.FLOWS_CARD_LOADING)).to_have_count(0)


def _page_overflow(page: Page) -> float:
    return page.evaluate(
        "() => document.documentElement.scrollWidth - window.innerWidth"
    )


def _element_overflow(locator: Locator) -> float:
    return locator.evaluate("el => el.scrollWidth - el.clientWidth")


def _delete_row(*, app: Flask, flow_id: str) -> None:
    with app.app_context():
        Metric_Flows.query.filter_by(id=int(flow_id.removeprefix("custom_"))).delete()
        db.session.commit()


# ---------------------------------------------------------------------------
# Focus, keyboard and validation
# ---------------------------------------------------------------------------


@VIEWPORTS
def test_builder_entry_focus_escape_guard_and_home_end_keys(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    viewport: dict[str, int],
):
    """
    GIVEN the flow builder opened from "+ New flow"
    WHEN keys are pressed in its inputs and selects
    THEN entry focus is the heading; Home/End still move the caret and the
        select; Escape on a select is ignored; Escape on a dirty draft opens
        the discard confirm and Keep editing returns focus to Cancel; Escape on
        a clean draft closes the builder and focuses "+ New flow".
    """
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    _open_new_builder(page)
    expect(page.locator(MDL.FLOW_BUILDER_HEADING)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_TITLE_NEW
    )

    name = page.locator(MDL.FLOW_BUILDER_NAME_INPUT)
    name.fill("Home end")
    name.press("Home")
    assert name.evaluate("el => el.selectionStart") == 0
    name.press("End")
    assert name.evaluate("el => el.selectionStart") == len("Home end")

    event_select = _field(page, 1, "event_name")
    event_select.select_option(SUBMIT_EVENT)
    expect(event_select).to_have_value(SUBMIT_EVENT)
    event_select.focus()
    event_select.press("Home")
    expect(event_select).to_have_value("")

    # Escape on a focused select is ignored (no confirm, builder stays open).
    event_select.focus()
    event_select.press("Escape")
    expect(page.locator(MDL.FLOW_BUILDER_CONFIRM)).to_have_count(0)
    expect(page.locator(MDL.FLOW_BUILDER_FORM)).to_be_visible()

    # Dirty draft: Escape runs through the discard guard.
    name.focus()
    name.press("Escape")
    expect(page.locator(MDL.FLOW_BUILDER_CONFIRM)).to_be_visible()
    expect(page.locator(MDL.FLOW_BUILDER_CONFIRM_SAFE_BUTTON)).to_be_focused()
    expect(page.locator(MDL.FLOW_BUILDER_CONFIRM_SAFE_BUTTON)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_DISCARD_KEEP
    )
    page.keyboard.press("Escape")
    expect(page.locator(MDL.FLOW_BUILDER_CONFIRM)).to_have_count(0)
    expect(page.locator(MDL.FLOW_BUILDER_CANCEL_BUTTON)).to_be_focused()

    # Clean draft: Escape closes the builder and focus returns to "+ New flow".
    name.fill("")
    name.press("Escape")
    expect(page.locator(MDL.FLOW_BUILDER)).to_be_hidden()
    expect(page.locator(MDL.FLOWS_NEW_BUTTON)).to_be_focused()


@VIEWPORTS
def test_builder_rejects_whitespace_name_and_focuses_summary_once(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    viewport: dict[str, int],
):
    """
    GIVEN a new flow with valid steps and a whitespace-only display name
    WHEN the admin presses Save
    THEN no request is sent, the name shows an inline error, the error summary
        takes focus with a single problem, the only `role=alert` region stays
        empty (one announcement, not two), and the summary link focuses the
        name input.
    """
    saves: list[str] = []

    def _record_save(route: Route) -> None:
        if route.request.method == "POST":
            saves.append(route.request.url)
        route.fallback()

    page.route(FLOW_LIST_URL_RE, _record_save)
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    _open_new_builder(page)
    _fill_blank_steps(page)
    page.locator(MDL.FLOW_BUILDER_NAME_INPUT).fill("   ")
    page.locator(MDL.FLOW_BUILDER_SAVE_BUTTON).click()

    name_error = page.locator(MDL.FLOW_BUILDER_NAME_ERROR)
    expect(name_error).to_be_visible()
    expect(name_error).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_ERR_NAME_LENGTH.format(
            min=FLOW_LIMITS.NAME_MIN_LENGTH, max=FLOW_LIMITS.NAME_MAX_LENGTH
        )
    )
    expect(page.locator(MDL.FLOW_BUILDER_NAME_INPUT)).to_have_attribute(
        "aria-invalid", "true"
    )
    expect(page.locator(MDL.FLOW_BUILDER_SUMMARY)).to_be_focused()
    expect(page.locator(MDL.FLOW_BUILDER_SUMMARY_TITLE)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_ERR_PROBLEM_ONE
    )
    alerts = page.locator(f"{MDL.FLOW_BUILDER} [role=alert]")
    expect(alerts).to_have_count(1)
    expect(alerts).to_be_empty()
    assert saves == []

    page.locator(MDL.FLOW_BUILDER_SUMMARY_LINK).click()
    expect(page.locator(MDL.FLOW_BUILDER_NAME_INPUT)).to_be_focused()


def test_builder_remove_and_add_keep_focus_at_the_step_bounds(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN a two-step flow open in the builder
    WHEN Remove is activated at 2 steps, Add is used up to 8 steps and then
        activated again, and a middle step is removed
    THEN the aria-disabled controls keep focus and change nothing, and after
        the middle removal focus lands on the next step's label.
    """
    [flow_id] = seed_custom_flows(
        display_names=["Bounds flow"], definition=two_step_filtered_definition()
    )
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )
    _open_edit_builder(page, flow_id)
    steps = page.locator(MDL.FLOW_BUILDER_STEP)
    expect(steps).to_have_count(FLOW_LIMITS.MIN_STEPS)

    remove = _action(page, 1, "remove")
    expect(remove).to_have_attribute("aria-disabled", "true")
    remove.focus()
    remove.press("Enter")
    expect(remove).to_be_focused()
    expect(steps).to_have_count(FLOW_LIMITS.MIN_STEPS)

    add = page.locator(MDL.FLOW_BUILDER_ADD_BUTTON)
    for expected in range(FLOW_LIMITS.MIN_STEPS + 1, FLOW_LIMITS.MAX_STEPS + 1):
        add.click()
        expect(steps).to_have_count(expected)
        expect(_field(page, expected, "label")).to_be_focused()
    expect(add).to_have_attribute("aria-disabled", "true")
    expect(page.locator(MDL.FLOW_BUILDER_ADD_REASON)).not_to_be_empty()
    add.focus()
    add.press("Enter")
    expect(add).to_be_focused()
    expect(steps).to_have_count(FLOW_LIMITS.MAX_STEPS)

    _action(page, 3, "remove").click()
    expect(steps).to_have_count(FLOW_LIMITS.MAX_STEPS - 1)
    expect(_field(page, 3, "label")).to_be_focused()


# ---------------------------------------------------------------------------
# Persisted round trips
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("reorder", [False, True], ids=["rename", "reorder"])
def test_edit_save_round_trip_preserves_filters_and_breakdowns(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
    reorder: bool,
):
    """
    GIVEN a saved flow whose steps carry a `dim_filter` and a `drop_breakdown`
        (which the form cannot edit) and real counts behind them
    WHEN the admin changes only the name (or only the order), saves and reloads
    THEN the list definition keeps every hidden filter and breakdown (moving
        with its step on a reorder) and, for a rename, the `/flow` response is
        identical to before.
    """
    seed_add_url_funnel_metrics(app=provide_app)
    [flow_id] = seed_custom_flows(
        display_names=["Round trip"], definition=filtered_breakdown_definition()
    )
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )

    before_entry = _list_entry(page, flow_id)
    before_funnel_steps = _funnel_counts(page, flow_id)
    # Precondition: the comparison must not be between zeros (DD-61).
    funnel_steps = before_funnel_steps
    assert all(step["count"] > 0 for step in funnel_steps), funnel_steps
    assert funnel_steps[1]["breakdown"], funnel_steps[1]
    assert funnel_steps[3]["breakdown"], funnel_steps[3]
    assert funnel_steps[1]["count"] == SEEDED_SUBMIT_URL_CREATE_COUNT
    assert funnel_steps[1]["count"] < (
        SEEDED_SUBMIT_URL_CREATE_COUNT + SEEDED_SUBMIT_OTHER_FORM_COUNT
    ), "the filter must remove the other form's rows"
    before_steps = before_entry["definition"]["steps"]

    _open_edit_builder(page, flow_id)
    if reorder:
        _action(page, 2, "move-down").click()
        # The moved step is now third; focus follows its action button.
        expect(_action(page, 3, "move-down")).to_be_focused()
        new_name = "Round trip"
    else:
        new_name = "Round trip renamed"
        page.locator(MDL.FLOW_BUILDER_NAME_INPUT).fill(new_name)
    page.locator(MDL.FLOW_BUILDER_SAVE_BUTTON).click()
    expect(page.locator(MDL.FLOW_BUILDER)).to_be_hidden()

    _reload_flows_tab(page)
    after_entry = _list_entry(page, flow_id)
    assert after_entry["display_name"] == new_name
    after_steps = after_entry["definition"]["steps"]
    after_funnel_steps = _funnel_counts(page, flow_id)
    if reorder:
        permutation = [0, 2, 1, 3]
        expected_steps = [before_steps[index] for index in permutation]
        assert after_steps == expected_steps
        assert after_steps[2]["dim_filter"] == before_steps[1]["dim_filter"]
        assert after_steps[2]["drop_breakdown"] == before_steps[1]["drop_breakdown"]
        assert after_funnel_steps == [
            before_funnel_steps[index] for index in permutation
        ]
        assert after_funnel_steps[2]["breakdown"]
    else:
        assert after_steps == before_steps
        assert after_funnel_steps == before_funnel_steps


@VIEWPORTS
def test_create_flow_through_the_ui_persists_and_focuses_new_card(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    viewport: dict[str, int],
):
    """
    GIVEN no custom flows
    WHEN the admin opens "+ New flow", fills a name and two steps from the real
        catalog and saves
    THEN the real 201 body yields a new card whose Edit button has focus, the
        count reads one custom flow, and the flow is still listed after reload.
    """
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    _open_new_builder(page)
    expect(page.locator(MDL.FLOW_BUILDER_STEP)).to_have_count(FLOW_LIMITS.MIN_STEPS)
    name = "Created in the UI"
    page.locator(MDL.FLOW_BUILDER_NAME_INPUT).fill(name)
    _fill_blank_steps(page)
    page.locator(MDL.FLOW_BUILDER_SAVE_BUTTON).click()

    expect(page.locator(MDL.FLOW_BUILDER)).to_be_hidden()
    new_card = page.locator(f"{MDL.FLOWS_CARD}[data-flow-id^=custom_]")
    expect(new_card).to_have_count(1)
    expect(page.locator(MDL.FLOWS_COUNT)).to_have_text(count_text(custom=1))
    expect(page.locator(MDL.FLOWS_CARD_LOADING)).to_have_count(0)
    expect(new_card.locator(".flow-edit-btn")).to_be_focused()
    expect(page.locator(MDL.FLOWS_ACTION_ANNOUNCEMENT)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_ANNOUNCE_SAVED.format(name=name)
    )

    _reload_flows_tab(page)
    expect(page.locator(f"{MDL.FLOWS_CARD}[data-flow-id^=custom_]")).to_have_count(1)
    expect(page.locator(MDL.FLOWS_COUNT)).to_have_text(count_text(custom=1))


def test_cancel_returns_focus_to_the_re_resolved_opener(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN a custom flow
    WHEN the builder is opened from the card's Edit button and cancelled, then
        opened from "+ New flow" and cancelled
    THEN focus returns to the card's (rebuilt) Edit button and to "+ New flow".
    """
    [flow_id] = seed_custom_flows(display_names=["Opener flow"])
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )

    _open_edit_builder(page, flow_id)
    page.locator(MDL.FLOW_BUILDER_CANCEL_BUTTON).click()
    expect(page.locator(MDL.FLOW_BUILDER)).to_be_hidden()
    expect(page.locator(MDL.FLOWS_CARD_LOADING)).to_have_count(0)
    expect(custom_card(page, flow_id).locator(".flow-edit-btn")).to_be_focused()

    _open_new_builder(page)
    page.locator(MDL.FLOW_BUILDER_CANCEL_BUTTON).click()
    expect(page.locator(MDL.FLOW_BUILDER)).to_be_hidden()
    expect(page.locator(MDL.FLOWS_NEW_BUTTON)).to_be_focused()


# ---------------------------------------------------------------------------
# Staged failures (page.route + fulfill)
# ---------------------------------------------------------------------------


@VIEWPORTS
def test_save_rate_limited_shows_inline_message_and_keeps_draft(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    viewport: dict[str, int],
):
    """
    GIVEN a valid new flow
    WHEN the create POST is answered 429 with a JSON body
    THEN the builder stays open with the draft intact and the form-level alert
        reads the rate-limited message.
    """

    def _rate_limit(route: Route) -> None:
        if route.request.method != "POST":
            route.fallback()
            return
        route.fulfill(
            status=429,
            content_type="application/json",
            body=json.dumps({"status": "Failure", "message": "Too many requests"}),
        )

    page.route(FLOW_LIST_URL_RE, _rate_limit)
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    _open_new_builder(page)
    name = "Rate limited flow"
    page.locator(MDL.FLOW_BUILDER_NAME_INPUT).fill(name)
    _fill_blank_steps(page)
    page.locator(MDL.FLOW_BUILDER_SAVE_BUTTON).click()

    expect(page.locator(MDL.FLOW_BUILDER_FORM_ERRORS)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_RATE_LIMITED
    )
    expect(page.locator(MDL.FLOW_BUILDER_FORM)).to_be_visible()
    expect(page.locator(MDL.FLOW_BUILDER_NAME_INPUT)).to_have_value(name)
    expect(_field(page, 1, "event_name")).to_have_value(OPEN_EVENT)
    expect(page.locator(MDL.FLOW_BUILDER_SAVE_BUTTON)).not_to_have_attribute(
        "aria-disabled", "true"
    )


def test_update_404_returns_to_grid_with_notice_and_refreshed_list(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN a flow another admin deleted while it was open in the builder
    WHEN Save's PUT is answered 404 with errorCode 5
    THEN the builder closes to the grid with the "no longer exists" notice, the
        heading is focused and the refreshed list no longer has the card.
    """
    [flow_id] = seed_custom_flows(display_names=["Vanishing flow"])

    def _answer_404(route: Route) -> None:
        if route.request.method != "PUT":
            route.fallback()
            return
        _delete_row(app=provide_app, flow_id=flow_id)
        route.fulfill(
            status=404,
            content_type="application/json",
            body=json.dumps(
                {
                    "status": "Failure",
                    "message": "Not found",
                    "errorCode": ERR_TARGET_NOT_FOUND,
                }
            ),
        )

    page.route(FLOW_UPDATE_URL_RE, _answer_404)
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )
    _open_edit_builder(page, flow_id)
    page.locator(MDL.FLOW_BUILDER_NAME_INPUT).fill("Vanishing flow edited")
    page.locator(MDL.FLOW_BUILDER_SAVE_BUTTON).click()

    expect(page.locator(MDL.FLOW_BUILDER)).to_be_hidden()
    expect(page.locator(MDL.FLOWS_NOTICE)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_ERR_FLOW_GONE
    )
    expect(page.locator(MDL.FLOWS_HEADING)).to_be_focused()
    expect(page.locator(MDL.FLOWS_CARD)).to_have_count(EXPECTED_FLOW_CARD_COUNT)
    expect(page.locator(MDL.FLOWS_COUNT)).to_have_text(count_text(custom=0))


@VIEWPORTS
def test_catalog_failure_shows_error_with_try_again_that_recovers(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    viewport: dict[str, int],
):
    """
    GIVEN the catalog request fails once
    WHEN the admin opens "+ New flow"
    THEN the builder shows the catalog error with a focused Try again button
        and no form; Try again loads the form and the heading takes focus.
    """
    calls: list[str] = []

    def _fail_first_catalog(route: Route) -> None:
        if route.request.method != "GET":
            route.fallback()
            return
        calls.append(route.request.url)
        if len(calls) == 1:
            route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"status": "Failure", "message": "boom"}),
            )
        else:
            route.fallback()

    page.route(FLOW_CATALOG_URL_RE, _fail_first_catalog)
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    page.locator(MDL.FLOWS_NEW_BUTTON).click()

    expect(page.locator(MDL.FLOW_BUILDER_CATALOG_STATUS)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_ERR_CATALOG_FAILED
    )
    retry = page.locator(MDL.FLOW_BUILDER_CATALOG_RETRY)
    expect(retry).to_have_text(UI_TEST_STRINGS.METRICS_FLOW_BUILDER_CATALOG_RETRY)
    expect(retry).to_be_focused()
    expect(page.locator(MDL.FLOW_BUILDER_FORM)).to_have_count(0)

    retry.click()
    expect(page.locator(MDL.FLOW_BUILDER_FORM)).to_be_visible()
    expect(page.locator(MDL.FLOW_BUILDER_HEADING)).to_be_focused()
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# Delete inside the builder, cap, inert, tab gates
# ---------------------------------------------------------------------------


@VIEWPORTS
def test_delete_in_builder_focus_dirty_warning_and_post_delete_focus(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
    viewport: dict[str, int],
):
    """
    GIVEN a custom flow open in the builder
    WHEN Delete flow is pressed on a clean draft, cancelled, pressed again on a
        dirty draft and confirmed
    THEN Cancel is focused with the clean body, Cancel returns focus to Delete
        flow, the dirty body warns about unsaved changes, the flow is removed,
        "+ New flow" has focus and the deletion is announced; the delete button
        is absent in create mode.
    """
    name = "Delete in builder"
    [flow_id] = seed_custom_flows(display_names=[name])
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    _open_new_builder(page)
    expect(page.locator(MDL.FLOW_BUILDER_DELETE_BUTTON)).to_have_count(0)
    page.locator(MDL.FLOW_BUILDER_CANCEL_BUTTON).click()
    expect(page.locator(MDL.FLOW_BUILDER)).to_be_hidden()

    _open_edit_builder(page, flow_id)
    delete = page.locator(MDL.FLOW_BUILDER_DELETE_BUTTON)
    delete.click()
    expect(page.locator(MDL.FLOW_BUILDER_CONFIRM_TITLE)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_DELETE_TITLE.format(name=name)
    )
    expect(page.locator(MDL.FLOW_BUILDER_CONFIRM_BODY)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_DELETE_BODY_CLEAN
    )
    expect(page.locator(MDL.FLOW_BUILDER_CONFIRM_SAFE_BUTTON)).to_be_focused()
    page.locator(MDL.FLOW_BUILDER_CONFIRM_SAFE_BUTTON).click()
    expect(page.locator(MDL.FLOW_BUILDER_CONFIRM)).to_have_count(0)
    expect(delete).to_be_focused()

    page.locator(MDL.FLOW_BUILDER_NAME_INPUT).fill("Edited before delete")
    delete.click()
    expect(page.locator(MDL.FLOW_BUILDER_CONFIRM_BODY)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_DELETE_BODY
    )
    page.locator(MDL.FLOW_BUILDER_CONFIRM_BUTTON).click()

    expect(page.locator(MDL.FLOW_BUILDER)).to_be_hidden()
    expect(page.locator(MDL.FLOWS_CARD)).to_have_count(EXPECTED_FLOW_CARD_COUNT)
    expect(page.locator(MDL.FLOWS_NEW_BUTTON)).to_be_focused()
    expect(page.locator(MDL.FLOWS_ACTION_ANNOUNCEMENT)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_DELETED.format(name=name)
    )


def test_new_flow_button_is_disabled_at_the_cap_with_its_reason(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN the maximum number of custom flows
    WHEN the admin opens the Flows tab and activates "+ New flow"
    THEN the button is aria-disabled and still focusable, its reason is
        visible and the builder does not open.
    """
    seed_custom_flows(
        display_names=[f"Cap flow {index}" for index in range(FLOW_LIMITS.MAX_CUSTOM)],
        definition={"steps": build_valid_flow_steps()[:2]},
    )
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )

    new_button = page.locator(MDL.FLOWS_NEW_BUTTON)
    expect(new_button).to_have_attribute("aria-disabled", "true")
    expect(page.locator(MDL.FLOWS_NEW_REASON)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_HINT_CAP.format(max=FLOW_LIMITS.MAX_CUSTOM)
    )
    new_button.focus()
    expect(new_button).to_be_focused()
    new_button.press("Enter")
    expect(page.locator(MDL.FLOW_BUILDER)).to_be_hidden()
    expect(new_button).to_be_focused()


def test_form_behind_a_confirm_is_inert(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a dirty draft with the discard confirm open
    WHEN focus is forced onto a form field, the field's centre is hit-tested
        and Tab is pressed
    THEN the form is `inert` (focus stays out, hit-testing skips it) and Tab
        stays trapped inside the confirm.
    """
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )
    _open_new_builder(page)
    _make_draft_dirty(page)
    name = page.locator(MDL.FLOW_BUILDER_NAME_INPUT)
    # Scroll first (an inert element may refuse it) so the hit-test point is
    # inside the viewport and elementFromPoint cannot return null.
    name.scroll_into_view_if_needed()
    page.locator(MDL.FLOW_BUILDER_CANCEL_BUTTON).click()
    expect(page.locator(MDL.FLOW_BUILDER_CONFIRM)).to_be_visible()

    form = page.locator(MDL.FLOW_BUILDER_FORM)
    assert form.evaluate("el => el.inert") is True
    name.evaluate("el => el.focus()")
    expect(name).not_to_be_focused()
    box = name.bounding_box()
    assert box is not None
    hit = page.evaluate(
        """({x, y, form, builder}) => {
            const el = document.elementFromPoint(x, y);
            if (el === null) {
                return "null";
            }
            if (document.querySelector(form).contains(el)) {
                return "form";
            }
            return el.closest(builder) !== null ? "builder" : "other";
        }""",
        {
            "x": box["x"] + box["width"] / 2,
            "y": box["y"] + box["height"] / 2,
            "form": MDL.FLOW_BUILDER_FORM,
            "builder": MDL.FLOW_BUILDER,
        },
    )
    # Non-null and not the form: the point lands on the builder container
    # behind the (non-overlay) confirm, proving the inert form is skipped.
    assert hit == "builder", hit

    safe = page.locator(MDL.FLOW_BUILDER_CONFIRM_SAFE_BUTTON)
    confirm = page.locator(MDL.FLOW_BUILDER_CONFIRM_BUTTON)
    expect(safe).to_be_focused()
    page.keyboard.press("Tab")
    expect(confirm).to_be_focused()
    page.keyboard.press("Tab")
    expect(safe).to_be_focused()

    safe.click()
    expect(page.locator(MDL.FLOW_BUILDER_CONFIRM)).to_have_count(0)
    assert form.evaluate("el => el.inert") is False


def test_arrow_right_with_dirty_draft_and_decline_keeps_the_tab_selected(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a dirty draft and focus on the selected Flows tab
    WHEN ArrowRight is pressed and the admin declines (Keep editing)
    THEN the Flows tab stays selected and focused and the draft is intact.
    """
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )
    _open_new_builder(page)
    _make_draft_dirty(page)

    flows_tab = page.locator(MDL.TAB_FLOWS_BUTTON)
    flows_tab.focus()
    flows_tab.press("ArrowRight")
    expect(page.locator(MDL.FLOW_BUILDER_CONFIRM)).to_be_visible()
    expect(page.locator(MDL.FLOW_BUILDER_CONFIRM_SAFE_BUTTON)).to_be_focused()
    page.locator(MDL.FLOW_BUILDER_CONFIRM_SAFE_BUTTON).click()

    expect(page.locator(MDL.FLOW_BUILDER_CONFIRM)).to_have_count(0)
    expect(flows_tab).to_have_attribute("aria-selected", "true")
    expect(flows_tab).to_be_focused()
    expect(page.locator(MDL.FLOW_BUILDER_NAME_INPUT)).to_have_value("Unsaved work")


@pytest.mark.parametrize("kind", ["discard", "delete"])
def test_tab_click_with_a_confirm_open_focuses_its_safe_button(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
    kind: str,
):
    """
    GIVEN the discard or the delete confirm open in the builder
    WHEN another tab is clicked
    THEN focus moves to the confirm's safe button and Flows stays selected.
    """
    [flow_id] = seed_custom_flows(display_names=["Gate flow"])
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )
    _open_edit_builder(page, flow_id)
    if kind == "discard":
        _make_draft_dirty(page)
        page.locator(MDL.FLOW_BUILDER_CANCEL_BUTTON).click()
    else:
        page.locator(MDL.FLOW_BUILDER_DELETE_BUTTON).click()
    expect(page.locator(MDL.FLOW_BUILDER_CONFIRM)).to_be_visible()
    safe = page.locator(MDL.FLOW_BUILDER_CONFIRM_SAFE_BUTTON)
    gauges_tab = page.locator(MDL.TAB_GAUGES_BUTTON)
    # Precondition: focus is on the tab being clicked, not on the safe button,
    # so the final assertion can only pass if the guard moved it.
    gauges_tab.focus()
    expect(gauges_tab).to_be_focused()
    expect(safe).not_to_be_focused()

    gauges_tab.click()

    expect(safe).to_be_focused()
    expect(page.locator(MDL.GAUGES_PANEL)).to_be_hidden()
    expect(page.locator(MDL.TAB_FLOWS_BUTTON)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(page.locator(MDL.TAB_GAUGES_BUTTON)).to_have_attribute(
        "aria-selected", "false"
    )


def test_accept_discard_on_tab_click_then_return_shows_every_card_loaded(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN a dirty draft in the builder
    WHEN another tab is clicked and the discard is accepted
    THEN that tab is selected and no `/flow` request fires while away; returning
        to Flows shows the grid with every card loaded.
    """
    seed_custom_flows(display_names=["Away one", "Away two"])
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )
    _open_new_builder(page)
    _make_draft_dirty(page)

    held = HeldFlowQueries()
    page.route(FLOW_QUERY_URL_RE, held.handle)
    flow_requests: list[str] = []
    page.on(
        "request",
        lambda request: (
            flow_requests.append(request.url)
            if FLOW_QUERY_URL_RE.match(request.url)
            else None
        ),
    )
    page.locator(MDL.TAB_GAUGES_BUTTON).click()
    expect(page.locator(MDL.FLOW_BUILDER_CONFIRM)).to_be_visible()
    page.locator(MDL.FLOW_BUILDER_CONFIRM_BUTTON).click()

    expect(page.locator(MDL.TAB_GAUGES_BUTTON)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(page.locator(MDL.FLOW_BUILDER)).to_be_hidden()
    # Absence of traffic can only be shown once the network has gone quiet.
    expect(page.locator(MDL.GAUGES_PANEL)).to_be_visible()
    page.wait_for_load_state("networkidle")
    assert held.held_count == 0, "a /flow request fired while on another tab"
    assert flow_requests == [], "a /flow request fired while on another tab"
    held.release()

    page.locator(MDL.TAB_FLOWS_BUTTON).click()
    expect(page.locator(MDL.FLOWS_COUNT)).to_have_text(count_text(custom=2))
    expect(page.locator(MDL.FLOWS_CARD_LOADING)).to_have_count(0)
    expect(page.locator(MDL.FLOWS_CARD)).to_have_count(EXPECTED_FLOW_CARD_COUNT + 2)
    expect(page.locator(MDL.FLOW_BUILDER)).to_be_hidden()
    expect(page.locator(MDL.FLOWS_GRID)).to_be_visible()


# ---------------------------------------------------------------------------
# Paused Refresh, layout, needs-attention
# ---------------------------------------------------------------------------


@VIEWPORTS
def test_paused_refresh_shows_hint_without_spinner_or_overflow(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    viewport: dict[str, int],
):
    """
    GIVEN the builder open
    WHEN the header is inspected
    THEN the hint row is visible without horizontal overflow, Refresh is
        focusable and aria-disabled with the hint as its description, and its
        spinner is not displayed while the refresh icon is.
    """
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    _open_new_builder(page)

    refresh = page.locator(MDL.REFRESH_NOW_BUTTON)
    hint = page.locator(MDL.REFRESH_PAUSED_HINT)
    expect(hint).to_be_visible()
    expect(hint).to_have_text(UI_TEST_STRINGS.METRICS_FLOW_BUILDER_HINT_REFRESH_PAUSED)
    expect(refresh).to_have_attribute("aria-disabled", "true")
    expect(refresh).to_have_attribute("data-builder-paused", "")
    refresh.focus()
    expect(refresh).to_be_focused()
    expect(refresh).to_have_accessible_description(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_HINT_REFRESH_PAUSED
    )

    spinner_display = page.locator(MDL.REFRESH_SPINNER).evaluate(
        "el => getComputedStyle(el).display"
    )
    icon_display = page.locator(MDL.REFRESH_ICON).evaluate(
        "el => getComputedStyle(el).display"
    )
    assert spinner_display == "none", spinner_display
    if viewport == MOBILE_VIEWPORT:
        # Icon-only Refresh at mobile width: the icon (not a spinner) shows.
        assert icon_display != "none", icon_display
    else:
        # Desktop shows the text label instead of the icon.
        expect(refresh.locator(".refresh-btn-label")).to_be_visible()

    hint_box = hint.bounding_box()
    assert hint_box is not None
    assert hint_box["x"] + hint_box["width"] <= viewport["width"] + 1, hint_box
    assert _page_overflow(page) <= 1


def test_long_names_and_labels_do_not_overflow_at_420px(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN a flow with a 64-character name and 64-character step labels at 420px
    WHEN the grid and then the builder are shown
    THEN the card (title with Edit and Delete), the count row, the builder form
        and the page have no horizontal overflow.
    """
    steps = build_valid_flow_steps()
    for step in steps:
        step["label"] = "y" * FLOW_LIMITS.LABEL_MAX_LENGTH
    [flow_id] = seed_custom_flows(
        display_names=[LONG_FLOW_NAME], definition={"steps": steps}
    )
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=MOBILE_VIEWPORT,
    )

    card = custom_card(page, flow_id)
    expect(card.locator(".flow-edit-btn")).to_be_visible()
    expect(card.locator(".flow-delete-btn")).to_be_visible()
    assert _element_overflow(card) <= 1
    count_box = page.locator(MDL.FLOWS_COUNT).bounding_box()
    assert count_box is not None
    assert count_box["x"] + count_box["width"] <= MOBILE_VIEWPORT["width"] + 1
    assert _page_overflow(page) <= 1

    edit_box = card.locator(".flow-edit-btn").bounding_box()
    assert edit_box is not None
    assert edit_box["width"] >= MIN_TOUCH_TARGET_PX, edit_box
    assert edit_box["height"] >= MIN_TOUCH_TARGET_PX, edit_box

    _open_edit_builder(page, flow_id)
    expect(page.locator(MDL.FLOW_BUILDER_NAME_INPUT)).to_have_value(LONG_FLOW_NAME)
    assert _element_overflow(page.locator(MDL.FLOW_BUILDER)) <= 1
    assert _element_overflow(page.locator(MDL.FLOW_BUILDER_FORM)) <= 1
    for step in page.locator(MDL.FLOW_BUILDER_STEP).all():
        assert _element_overflow(step) <= 1
    assert _page_overflow(page) <= 1


def test_builder_controls_meet_touch_targets_and_sixteen_px_text_at_420px(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN a custom flow open in the builder at 420px
    WHEN every button, input and select is measured
    THEN each meets the touch-target size and inputs and selects compute to a
        16px font (no iOS zoom).
    """
    [flow_id] = seed_custom_flows(display_names=["Touch flow"])
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=MOBILE_VIEWPORT,
    )
    _open_edit_builder(page, flow_id)

    controls = [
        control
        for control in page.locator(
            f"{MDL.FLOW_BUILDER_FORM} button, {MDL.FLOW_BUILDER_FORM} input, "
            f"{MDL.FLOW_BUILDER_FORM} select"
        ).all()
        if control.is_visible()
    ]
    assert len(controls) > FLOW_LIMITS.MIN_STEPS * 3
    for control in controls:
        box = control.bounding_box()
        assert box is not None
        label = control.evaluate("el => el.outerHTML.slice(0, 120)")
        assert box["height"] >= MIN_TOUCH_TARGET_PX, (label, box)
        tag = control.evaluate("el => el.tagName")
        if tag == "BUTTON":
            assert box["width"] >= MIN_TOUCH_TARGET_PX, (label, box)
        else:
            font_size = control.evaluate("el => getComputedStyle(el).fontSize")
            assert font_size == BUILDER_INPUT_FONT_SIZE, (label, font_size)


def test_edit_of_a_needs_attention_flow_describes_the_problems(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN a saved flow whose step names a removed event
    WHEN the grid is shown and the admin opens its Edit button
    THEN the card has an Edit button and the restored hint ending "Edit the
        flow to fix it, or delete it."; the builder heading's accessible
        description is the "{count} problems to fix" summary.
    """
    [flow_id] = seed_custom_flows(
        display_names=["Broken flow"], definition=removed_event_definition()
    )
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
    )

    card = custom_card(page, flow_id)
    expect(card.locator(".flow-edit-btn")).to_have_count(1)
    expect(card).to_contain_text(UI_TEST_STRINGS.METRICS_FLOW_NEEDS_ATTENTION_HELP)

    _open_edit_builder(page, flow_id)
    expect(page.locator(MDL.FLOW_BUILDER_HEADING)).to_have_accessible_description(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_ERR_PROBLEM_ONE
    )
