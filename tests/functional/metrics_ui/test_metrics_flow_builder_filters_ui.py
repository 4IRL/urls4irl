from __future__ import annotations

import re
from typing import Any

import pytest
from flask import Flask
from playwright.sync_api import Locator, Page, Route, expect

from backend.config import ConfigTestUI
from backend.metrics.events import EventName
from backend.metrics.flow_limits import FLOW_LIMITS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.locators import MetricsDashboardLocators as MDL
from tests.functional.metrics_ui.playwright_utils import (
    BUILDER_INPUT_FONT_SIZE,
    DESKTOP_VIEWPORT,
    MIN_TOUCH_TARGET_PX,
    MOBILE_VIEWPORT,
    OPEN_EVENT,
    REMOVED_EVENT_NAME,
    SUBMIT_EVENT,
    VIEWPORTS,
    SeedCustomFlows,
    builder_field,
    builder_step,
    damaged_list_definition,
    element_overflow,
    fill_blank_steps,
    list_entry,
    malformed_entry_definition,
    missing_breakdown_event_definition,
    non_groupable_group_by_definition,
    open_edit_builder,
    open_flows_tab,
    open_new_builder,
    page_overflow,
    reload_flows_tab,
    stale_filter_definition,
    zero_groupable_breakdown_definition,
)

pytestmark = pytest.mark.metrics_ui

FLOW_WRITE_URL_RE: re.Pattern[str] = re.compile(
    r".*/admin/metrics/flows(?:/custom_[1-9][0-9]*)?(?:\?.*)?$"
)
CANCEL_EVENT: str = EventName.UI_FORM_CANCEL.value
API_HIT_EVENT: str = EventName.API_HIT.value
API_ENDPOINT: str = "urls.create_url"
API_METHOD: str = "POST"
REJECTED_STATUS_CODE: str = "99"
ACCEPTED_STATUS_CODE: str = "201"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _expect_description_contains(control: Locator, text: str) -> None:
    """Auto-waiting check that the control's `aria-describedby` text has `text`."""
    expect(control).to_have_accessible_description(re.compile(re.escape(text)))


def _expect_disabled_with_reason(button: Locator, reason: str) -> None:
    expect(button).to_have_attribute("aria-disabled", "true")
    _expect_description_contains(button, reason)


def _press_disabled(button: Locator, *, other: Locator) -> None:
    """Move focus to a different control, force-click the aria-disabled `button`
    (Playwright treats aria-disabled as not enabled) and expect the click to
    leave focus on it, i.e. the button stays focusable and does nothing.

    `force=True` skips the stable check, so `hover()` first waits for a settled
    position (it has no enabled check to fail on aria-disabled)."""
    other.focus()
    expect(other).to_be_focused()
    button.hover()
    button.click(force=True)
    expect(button).to_be_focused()


def _expect_enabled(button: Locator) -> None:
    expect(button).not_to_have_attribute("aria-disabled", "true")


def _choose(control: Locator, value: str) -> None:
    """Focus a select, pick `value` and expect focus to stay on the control."""
    control.focus()
    control.select_option(value)
    expect(control).to_have_value(value)
    expect(control).to_be_focused()


def _first_value(select: Locator) -> str:
    """Value of the first real (non-placeholder) option of a select."""
    option = select.locator("option:not([value=''])").first
    expect(option).to_be_attached()
    value = option.get_attribute("value")
    assert value
    return value


def _expect_selected_text(select: Locator, text: str) -> None:
    expect(select.locator("option:checked")).to_have_text(text)


def _stale(value: str) -> str:
    return UI_TEST_STRINGS.METRICS_FLOW_BUILDER_NOTE_STALE_VALUE.format(value=value)


def _step_filter_rows(page: Page, position: int) -> Locator:
    return builder_step(page, position).locator(MDL.FLOW_BUILDER_FILTER_ROW)


def _breakdown(page: Page, position: int) -> Locator:
    return builder_step(page, position).locator(MDL.FLOW_BUILDER_BREAKDOWN)


def _add_step_filter(
    page: Page, position: int, *, dim: str, value: str | None = None
) -> str:
    """Add one step filter through the UI; returns the chosen value."""
    rows = _step_filter_rows(page, position)
    count = rows.count()
    builder_step(page, position).locator(MDL.FLOW_BUILDER_ADD_FILTER_BUTTON).click()
    expect(rows).to_have_count(count + 1)
    row = rows.nth(count)
    _choose(row.locator(MDL.FLOW_BUILDER_FILTER_DIM), dim)
    value_control = row.locator(MDL.FLOW_BUILDER_FILTER_VALUE)
    expect(value_control).to_be_enabled()
    chosen = value if value is not None else _first_value(value_control)
    _choose(value_control, chosen)
    return chosen


def _add_breakdown_filter(
    page: Page, position: int, *, dim: str, value: str | None = None
) -> str:
    breakdown = _breakdown(page, position)
    rows = breakdown.locator(MDL.FLOW_BUILDER_BREAKDOWN_FILTER_ROW)
    count = rows.count()
    breakdown.locator(MDL.FLOW_BUILDER_ADD_BREAKDOWN_FILTER_BUTTON).click()
    expect(rows).to_have_count(count + 1)
    row = rows.nth(count)
    _choose(row.locator(MDL.FLOW_BUILDER_BREAKDOWN_FILTER_DIM), dim)
    value_control = row.locator(MDL.FLOW_BUILDER_BREAKDOWN_FILTER_VALUE)
    expect(value_control).to_be_enabled()
    chosen = value if value is not None else _first_value(value_control)
    _choose(value_control, chosen)
    return chosen


def _add_breakdown(page: Page, position: int, *, event: str, group_by: str) -> None:
    step = builder_step(page, position)
    step.locator(MDL.FLOW_BUILDER_ADD_BREAKDOWN_BUTTON).click()
    breakdown = _breakdown(page, position)
    expect(breakdown).to_be_visible()
    _choose(breakdown.locator(MDL.FLOW_BUILDER_BREAKDOWN_EVENT), event)
    group_control = breakdown.locator(MDL.FLOW_BUILDER_BREAKDOWN_GROUP_BY)
    expect(group_control).to_be_enabled()
    _choose(group_control, group_by)


def _fill_two_steps_with_filters_and_breakdown(page: Page) -> dict[str, Any]:
    """Fill the two blank steps of a new draft: step 1 (open) with a
    `device_type` filter; step 2 (submit) with two filters and a breakdown on
    cancel grouped by `trigger` with one filter of its own. Returns the
    values chosen."""
    fill_blank_steps(page)
    device = _add_step_filter(page, 1, dim="device_type")
    _add_step_filter(page, 2, dim="form", value="url_create")
    _add_step_filter(page, 2, dim="trigger", value="button_click")
    _add_breakdown(page, 2, event=CANCEL_EVENT, group_by="trigger")
    _add_breakdown_filter(page, 2, dim="form", value="url_create")
    return {"device": device}


def _save_requests(page: Page) -> list[str]:
    """Record every write (create or update) the page sends for a flow."""
    saves: list[str] = []

    def _record(route: Route) -> None:
        if route.request.method != "GET":
            saves.append(route.request.url)
        route.fallback()

    page.route(FLOW_WRITE_URL_RE, _record)
    return saves


def _summary_lines(page: Page) -> Locator:
    return page.locator(f"{MDL.FLOW_BUILDER_SUMMARY} li")


# ---------------------------------------------------------------------------
# Add / Remove contract
# ---------------------------------------------------------------------------


@VIEWPORTS
def test_step_add_filter_reasons_focus_and_row_contract(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    viewport: dict[str, int],
):
    """
    GIVEN a new flow whose first step has no event yet
    WHEN Add filter is used before and after choosing `ui_url_create_open`
        (one filterable field, `device_type`)
    THEN Add is aria-disabled with the adjacent reason and keeps focus on click;
        a row's value select stays disabled until a field is chosen; choosing a
        field uses it up (the "every field" reason) while focus stays on the
        control; Remove re-enables Add; row controls and Add/Remove have
        step-numbered accessible names.
    """
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    open_new_builder(page)
    step = builder_step(page, 1)
    add_filter = step.locator(MDL.FLOW_BUILDER_ADD_FILTER_BUTTON)
    add_breakdown = step.locator(MDL.FLOW_BUILDER_ADD_BREAKDOWN_BUTTON)
    rows = _step_filter_rows(page, 1)

    needs_event = UI_TEST_STRINGS.METRICS_FLOW_BUILDER_FILTER_NEEDS_EVENT_REASON
    event_select = builder_field(page, 1, "event_name")
    _expect_disabled_with_reason(add_filter, needs_event)
    _expect_disabled_with_reason(add_breakdown, needs_event)
    _press_disabled(add_filter, other=event_select)
    _press_disabled(add_breakdown, other=event_select)
    expect(rows).to_have_count(0)
    expect(_breakdown(page, 1)).to_have_count(0)

    builder_field(page, 1, "event_name").select_option(OPEN_EVENT)
    _expect_enabled(add_filter)
    _expect_enabled(add_breakdown)
    expect(add_filter).to_have_accessible_name(
        re.compile(
            "^"
            + re.escape(
                UI_TEST_STRINGS.METRICS_FLOW_BUILDER_ADD_FILTER.format(
                    count=0, max=FLOW_LIMITS.MAX_FILTERS
                )
            )
        )
    )
    expect(add_breakdown).to_have_accessible_name(
        re.compile("^" + re.escape(UI_TEST_STRINGS.METRICS_FLOW_BUILDER_ADD_BREAKDOWN))
    )

    add_filter.click()
    expect(rows).to_have_count(1)
    dim = rows.nth(0).locator(MDL.FLOW_BUILDER_FILTER_DIM)
    value = rows.nth(0).locator(MDL.FLOW_BUILDER_FILTER_VALUE)
    expect(value).to_be_disabled()
    expect(dim).to_have_accessible_name(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_FILTER_DIM_LABEL.format(step=1, n=1)
    )
    expect(
        rows.nth(0).locator(MDL.FLOW_BUILDER_REMOVE_FILTER_BUTTON)
    ).to_have_accessible_name(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_FILTER_REMOVE_LABEL.format(step=1, n=1)
    )

    _choose(dim, "device_type")
    expect(value).to_be_enabled()
    _choose(value, _first_value(value))
    _expect_disabled_with_reason(
        add_filter,
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_FILTER_ALL_USED_REASON,
    )
    _press_disabled(add_filter, other=dim)
    expect(rows).to_have_count(1)

    rows.nth(0).locator(MDL.FLOW_BUILDER_REMOVE_FILTER_BUTTON).click()
    expect(rows).to_have_count(0)
    _expect_enabled(add_filter)

    # An API step with no endpoint chosen has no event either.
    step_two = builder_step(page, 2)
    add_filter_two = step_two.locator(MDL.FLOW_BUILDER_ADD_FILTER_BUTTON)
    add_breakdown_two = step_two.locator(MDL.FLOW_BUILDER_ADD_BREAKDOWN_BUTTON)
    stream_two = builder_field(page, 2, "stream")
    stream_two.select_option("api")
    expect(stream_two).to_have_value("api")
    _expect_disabled_with_reason(add_filter_two, needs_event)
    _expect_disabled_with_reason(add_breakdown_two, needs_event)
    _press_disabled(add_filter_two, other=stream_two)
    _press_disabled(add_breakdown_two, other=stream_two)
    expect(_step_filter_rows(page, 2)).to_have_count(0)
    expect(_breakdown(page, 2)).to_have_count(0)


@VIEWPORTS
def test_breakdown_add_reasons_status_code_hint_and_remove(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    viewport: dict[str, int],
):
    """
    GIVEN a step with an event and a drop-off breakdown just added
    WHEN the breakdown event is `api_hit` (one filterable field, `status_code`)
    THEN breakdown Add filter is aria-disabled until an event is chosen, the
        `status_code` value is a text input with the hint, a used-up field
        disables Add again, and Remove breakdown brings the step's Add
        breakdown back.
    """
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    open_new_builder(page)
    builder_field(page, 1, "event_name").select_option(OPEN_EVENT)
    step = builder_step(page, 1)
    step.locator(MDL.FLOW_BUILDER_ADD_BREAKDOWN_BUTTON).click()
    breakdown = _breakdown(page, 1)
    expect(breakdown).to_be_visible()
    expect(step.locator(MDL.FLOW_BUILDER_ADD_BREAKDOWN_BUTTON)).to_have_count(0)

    add_bd_filter = breakdown.locator(MDL.FLOW_BUILDER_ADD_BREAKDOWN_FILTER_BUTTON)
    group_by = breakdown.locator(MDL.FLOW_BUILDER_BREAKDOWN_GROUP_BY)
    remove_breakdown = breakdown.locator(MDL.FLOW_BUILDER_REMOVE_BREAKDOWN_BUTTON)
    event_select = breakdown.locator(MDL.FLOW_BUILDER_BREAKDOWN_EVENT)
    _expect_disabled_with_reason(
        add_bd_filter,
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_FILTER_NEEDS_EVENT_REASON,
    )
    expect(group_by).to_be_disabled()
    _press_disabled(add_bd_filter, other=event_select)

    _choose(event_select, API_HIT_EVENT)
    expect(group_by).to_be_enabled()
    _choose(group_by, "status_code")
    _expect_enabled(add_bd_filter)
    suffix = UI_TEST_STRINGS.METRICS_FLOW_BUILDER_FOR_STEP_SUFFIX.format(step=1)
    expect(add_bd_filter).to_have_accessible_name(
        re.compile(
            "^"
            + re.escape(
                UI_TEST_STRINGS.METRICS_FLOW_BUILDER_ADD_BREAKDOWN_FILTER.format(
                    count=0, max=FLOW_LIMITS.MAX_FILTERS
                )
            )
            + ".*"
            + re.escape(suffix)
        )
    )
    expect(remove_breakdown).to_have_accessible_name(
        re.compile(
            "^"
            + re.escape(UI_TEST_STRINGS.METRICS_FLOW_BUILDER_REMOVE_BREAKDOWN)
            + ".*"
            + re.escape(suffix)
        )
    )

    add_bd_filter.click()
    row = breakdown.locator(MDL.FLOW_BUILDER_BREAKDOWN_FILTER_ROW).nth(0)
    row_dim = row.locator(MDL.FLOW_BUILDER_BREAKDOWN_FILTER_DIM)
    status_input = row.locator(MDL.FLOW_BUILDER_BREAKDOWN_FILTER_VALUE)
    expect(status_input).to_be_disabled()
    expect(row_dim).to_have_accessible_name(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_BREAKDOWN_FILTER_DIM_LABEL.format(
            step=1, n=1
        )
    )
    expect(status_input).to_have_accessible_name(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_BREAKDOWN_FILTER_VALUE_LABEL.format(
            step=1, n=1
        )
    )
    expect(
        row.locator(MDL.FLOW_BUILDER_REMOVE_BREAKDOWN_FILTER_BUTTON)
    ).to_have_accessible_name(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_BREAKDOWN_FILTER_REMOVE_LABEL.format(
            step=1, n=1
        )
    )
    _choose(row_dim, "status_code")
    expect(status_input).to_have_js_property("tagName", "INPUT")
    expect(row).to_contain_text(UI_TEST_STRINGS.METRICS_FLOW_BUILDER_FILTER_STATUS_HINT)
    status_input.fill("500")
    _expect_disabled_with_reason(
        add_bd_filter,
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_FILTER_ALL_USED_REASON,
    )

    remove_breakdown.click()
    expect(_breakdown(page, 1)).to_have_count(0)
    _expect_enabled(step.locator(MDL.FLOW_BUILDER_ADD_BREAKDOWN_BUTTON))


@VIEWPORTS
def test_status_code_input_shows_hint_and_enter_saves_a_complete_draft(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    viewport: dict[str, int],
):
    """
    GIVEN a new flow whose second step is an API step filtered on `status_code`
    WHEN the admin types a code into the text input and presses Enter
    THEN the input shows its hint and the flow saves with the
        `status_code:<code>` filter.
    """
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    open_new_builder(page)
    page.locator(MDL.FLOW_BUILDER_NAME_INPUT).fill("Status code flow")
    builder_field(page, 1, "label").fill("Open")
    builder_field(page, 1, "event_name").select_option(OPEN_EVENT)
    builder_field(page, 2, "label").fill("API")
    builder_field(page, 2, "stream").select_option("api")
    builder_field(page, 2, "api_endpoint").select_option(API_ENDPOINT)
    builder_field(page, 2, "api_method").select_option(API_METHOD)

    builder_step(page, 2).locator(MDL.FLOW_BUILDER_ADD_FILTER_BUTTON).click()
    row = _step_filter_rows(page, 2).nth(0)
    _choose(row.locator(MDL.FLOW_BUILDER_FILTER_DIM), "status_code")
    status_input = row.locator(MDL.FLOW_BUILDER_FILTER_VALUE)
    expect(status_input).to_have_js_property("tagName", "INPUT")
    expect(row).to_contain_text(UI_TEST_STRINGS.METRICS_FLOW_BUILDER_FILTER_STATUS_HINT)
    status_input.fill(ACCEPTED_STATUS_CODE)
    status_input.press("Enter")

    expect(page.locator(MDL.FLOW_BUILDER)).to_be_hidden()
    [flow_id] = [
        card.get_attribute("data-flow-id")
        for card in page.locator(f"{MDL.FLOWS_CARD}[data-flow-id^=custom_]").all()
    ]
    assert flow_id is not None
    steps = list_entry(page, flow_id)["definition"]["steps"]
    assert steps[1]["dim_filter"] == [f"status_code:{ACCEPTED_STATUS_CODE}"]


@VIEWPORTS
def test_server_rejection_maps_to_the_exact_filter_row(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    viewport: dict[str, int],
):
    """
    GIVEN an API step filtered on `status_code:99` (only the server rejects it)
    WHEN the admin saves
    THEN the server's message lands on that filter row with its controls
        invalid, the summary holds that one problem and takes focus, its link
        focuses a control of the row, and fixing the code lets Save succeed.
    """
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    open_new_builder(page)
    page.locator(MDL.FLOW_BUILDER_NAME_INPUT).fill("Rejected code")
    builder_field(page, 1, "label").fill("Open")
    builder_field(page, 1, "event_name").select_option(OPEN_EVENT)
    builder_field(page, 2, "label").fill("API")
    builder_field(page, 2, "stream").select_option("api")
    builder_field(page, 2, "api_endpoint").select_option(API_ENDPOINT)
    # Let the step settle: its change-driven preview response is the last async
    # re-render, so a filter row added before it can be dropped under load.
    with page.expect_response(
        lambda response: "/admin/metrics/flows/preview" in response.url
    ):
        builder_field(page, 2, "api_method").select_option(API_METHOD)
    builder_step(page, 2).locator(MDL.FLOW_BUILDER_ADD_FILTER_BUTTON).click()
    rows = _step_filter_rows(page, 2)
    expect(rows).to_have_count(1)
    row = rows.nth(0)
    _choose(row.locator(MDL.FLOW_BUILDER_FILTER_DIM), "status_code")
    status_input = row.locator(MDL.FLOW_BUILDER_FILTER_VALUE)
    # The live preview (300 ms debounce, then a request) marks controls on its own
    # response. Wait for that response before Save so its marks cannot land between
    # the Save rejection and the assertions below and strip/replace the row's flags.
    with page.expect_response(
        lambda response: "/admin/metrics/flows/preview" in response.url
    ):
        status_input.fill(REJECTED_STATUS_CODE)

    page.locator(MDL.FLOW_BUILDER_SAVE_BUTTON).click()
    row_error = row.locator(MDL.FLOW_BUILDER_ERROR)
    expect(row_error).to_be_visible()
    expect(row_error).not_to_be_empty()
    expect(row.locator(MDL.FLOW_BUILDER_FILTER_DIM)).to_have_attribute(
        "aria-invalid", "true"
    )
    expect(status_input).to_have_attribute("aria-invalid", "true")
    expect(page.locator(MDL.FLOW_BUILDER_SUMMARY_TITLE)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_ERR_PROBLEM_ONE
    )
    expect(page.locator(MDL.FLOW_BUILDER_SUMMARY)).to_be_focused()
    expect(page.locator(MDL.FLOW_BUILDER_SUMMARY_LINK)).to_contain_text(
        row_error.inner_text()
    )

    page.locator(MDL.FLOW_BUILDER_SUMMARY_LINK).click()
    expect(row.locator(":focus")).to_have_count(1)

    status_input.fill(ACCEPTED_STATUS_CODE)
    expect(row_error).to_have_count(0)
    page.locator(MDL.FLOW_BUILDER_SAVE_BUTTON).click()
    expect(page.locator(MDL.FLOW_BUILDER)).to_be_hidden()
    [flow_id] = [
        card.get_attribute("data-flow-id")
        for card in page.locator(f"{MDL.FLOWS_CARD}[data-flow-id^=custom_]").all()
    ]
    assert flow_id is not None
    steps = list_entry(page, flow_id)["definition"]["steps"]
    assert steps[1]["dim_filter"] == [f"status_code:{ACCEPTED_STATUS_CODE}"]


# ---------------------------------------------------------------------------
# Round trip
# ---------------------------------------------------------------------------


@VIEWPORTS
def test_filters_and_breakdown_survive_save_reload_and_edit(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    viewport: dict[str, int],
):
    """
    GIVEN a flow built in the UI with step filters and a breakdown with its own
        filter (focus stays on every control that was changed)
    WHEN it is saved, the page reloaded, the flow opened for edit, renamed and
        saved again
    THEN every control is prefilled from the stored definition and the
        persisted definition is unchanged by the edit.
    """
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    open_new_builder(page)
    page.locator(MDL.FLOW_BUILDER_NAME_INPUT).fill("Filtered flow")
    chosen = _fill_two_steps_with_filters_and_breakdown(page)
    page.locator(MDL.FLOW_BUILDER_SAVE_BUTTON).click()
    expect(page.locator(MDL.FLOW_BUILDER)).to_be_hidden()

    reload_flows_tab(page)
    [flow_id] = [
        card.get_attribute("data-flow-id")
        for card in page.locator(f"{MDL.FLOWS_CARD}[data-flow-id^=custom_]").all()
    ]
    assert flow_id is not None
    saved = list_entry(page, flow_id)["definition"]["steps"]
    assert saved[0]["dim_filter"] == [f"device_type:{chosen['device']}"]
    assert saved[1]["dim_filter"] == ["form:url_create", "trigger:button_click"]
    assert saved[1]["drop_breakdown"] == {
        "event_name": CANCEL_EVENT,
        "dim_filter": ["form:url_create"],
        "group_by": "trigger",
    }

    open_edit_builder(page, flow_id)
    rows_one = _step_filter_rows(page, 1)
    rows_two = _step_filter_rows(page, 2)
    expect(rows_one).to_have_count(1)
    expect(rows_one.nth(0).locator(MDL.FLOW_BUILDER_FILTER_DIM)).to_have_value(
        "device_type"
    )
    expect(rows_one.nth(0).locator(MDL.FLOW_BUILDER_FILTER_VALUE)).to_have_value(
        chosen["device"]
    )
    expect(rows_two).to_have_count(2)
    for index, (dim, value) in enumerate(
        (("form", "url_create"), ("trigger", "button_click"))
    ):
        expect(rows_two.nth(index).locator(MDL.FLOW_BUILDER_FILTER_DIM)).to_have_value(
            dim
        )
        expect(
            rows_two.nth(index).locator(MDL.FLOW_BUILDER_FILTER_VALUE)
        ).to_have_value(value)
    breakdown = _breakdown(page, 2)
    expect(breakdown.locator(MDL.FLOW_BUILDER_BREAKDOWN_EVENT)).to_have_value(
        CANCEL_EVENT
    )
    expect(breakdown.locator(MDL.FLOW_BUILDER_BREAKDOWN_GROUP_BY)).to_have_value(
        "trigger"
    )
    breakdown_row = breakdown.locator(MDL.FLOW_BUILDER_BREAKDOWN_FILTER_ROW).nth(0)
    expect(breakdown_row.locator(MDL.FLOW_BUILDER_BREAKDOWN_FILTER_DIM)).to_have_value(
        "form"
    )
    expect(
        breakdown_row.locator(MDL.FLOW_BUILDER_BREAKDOWN_FILTER_VALUE)
    ).to_have_value("url_create")

    page.locator(MDL.FLOW_BUILDER_NAME_INPUT).fill("Filtered flow renamed")
    page.locator(MDL.FLOW_BUILDER_SAVE_BUTTON).click()
    expect(page.locator(MDL.FLOW_BUILDER)).to_be_hidden()
    reload_flows_tab(page)
    after = list_entry(page, flow_id)
    assert after["display_name"] == "Filtered flow renamed"
    assert after["definition"]["steps"] == saved


# ---------------------------------------------------------------------------
# Stale and unavailable stored data
# ---------------------------------------------------------------------------


@VIEWPORTS
def test_stale_filter_field_and_value_prefill_flag_the_control_that_holds_them(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
    viewport: dict[str, int],
):
    """
    GIVEN a stored step filtered on a field that no longer exists and on a
        value its field no longer offers
    WHEN the flow opens in the builder
    THEN each control keeps its stored value as "<value> (no longer exists)"
        with aria-invalid and the summary lists the problems.
    """
    [flow_id] = seed_custom_flows(
        display_names=["Stale filters"], definition=stale_filter_definition()
    )
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    open_edit_builder(page, flow_id)
    rows = _step_filter_rows(page, 2)
    expect(rows).to_have_count(2)
    stale_dim = rows.nth(0).locator(MDL.FLOW_BUILDER_FILTER_DIM)
    expect(stale_dim).to_have_attribute("aria-invalid", "true")
    expect(stale_dim).to_have_value("bogus_dim")
    _expect_selected_text(stale_dim, _stale("bogus_dim"))
    stale_value = rows.nth(1).locator(MDL.FLOW_BUILDER_FILTER_VALUE)
    expect(stale_value).to_have_attribute("aria-invalid", "true")
    expect(stale_value).to_have_value("gone_value")
    _expect_selected_text(stale_value, _stale("gone_value"))
    expect(page.locator(MDL.FLOW_BUILDER_SUMMARY)).to_be_visible()


@VIEWPORTS
def test_stored_non_groupable_group_by_is_flagged_on_the_group_by_select(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
    viewport: dict[str, int],
):
    """
    GIVEN a stored breakdown on `ui_form_cancel` grouped by `form` (not groupable)
    WHEN the flow opens in the builder
    THEN the group by select keeps `form` as "form (no longer exists)" with
        aria-invalid and the server's reason beside it; the event select is
        not flagged.
    """
    [flow_id] = seed_custom_flows(
        display_names=["Bad group by"], definition=non_groupable_group_by_definition()
    )
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    open_edit_builder(page, flow_id)
    breakdown = _breakdown(page, 2)
    group_by = breakdown.locator(MDL.FLOW_BUILDER_BREAKDOWN_GROUP_BY)
    expect(group_by).to_have_attribute("aria-invalid", "true")
    expect(group_by).to_have_value("form")
    _expect_selected_text(group_by, _stale("form"))
    expect(
        breakdown.locator(f"[data-cell=breakdown_group_by] {MDL.FLOW_BUILDER_ERROR}")
    ).not_to_be_empty()
    expect(breakdown.locator(MDL.FLOW_BUILDER_BREAKDOWN_EVENT)).not_to_have_attribute(
        "aria-invalid", "true"
    )


@VIEWPORTS
def test_stored_zero_groupable_breakdown_event_shows_the_unavailable_helper(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
    viewport: dict[str, int],
):
    """
    GIVEN a stored breakdown on `ui_form_submit`, which has no groupable field
    WHEN the flow opens in the builder
    THEN the event is a plain selected option (no "(no longer exists)") that is
        invalid and described by "This event cannot be broken down."; group by
        and the breakdown's Add filter are disabled while the event select and
        Remove breakdown stay usable.
    """
    [flow_id] = seed_custom_flows(
        display_names=["Unavailable breakdown"],
        definition=zero_groupable_breakdown_definition(),
    )
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    open_edit_builder(page, flow_id)
    breakdown = _breakdown(page, 2)
    event_select = breakdown.locator(MDL.FLOW_BUILDER_BREAKDOWN_EVENT)
    helper_text = UI_TEST_STRINGS.METRICS_FLOW_BUILDER_BREAKDOWN_UNAVAILABLE
    expect(event_select).to_have_value(SUBMIT_EVENT)
    _expect_selected_text(event_select, SUBMIT_EVENT)
    expect(event_select).to_have_attribute("aria-invalid", "true")
    expect(event_select).to_be_enabled()
    _expect_description_contains(event_select, helper_text)
    expect(
        breakdown.locator(MDL.FLOW_BUILDER_HINT).filter(has_text=helper_text)
    ).to_be_visible()
    expect(breakdown.locator(MDL.FLOW_BUILDER_BREAKDOWN_GROUP_BY)).to_be_disabled()
    _expect_disabled_with_reason(
        breakdown.locator(MDL.FLOW_BUILDER_ADD_BREAKDOWN_FILTER_BUTTON),
        helper_text,
    )
    expect(breakdown.locator(MDL.FLOW_BUILDER_REMOVE_BREAKDOWN_BUTTON)).to_be_enabled()


@VIEWPORTS
def test_stored_missing_breakdown_event_is_read_only_with_its_helper(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
    viewport: dict[str, int],
):
    """
    GIVEN a stored breakdown whose event no longer exists, with a group by and
        a filter
    WHEN the flow opens in the builder
    THEN the event reads "<event> (no longer exists)" with aria-invalid; group
        by and the filter controls are disabled but still show the stored
        values; the helper "This event no longer exists." is shown; Remove
        breakdown and Remove filter stay usable.
    """
    [flow_id] = seed_custom_flows(
        display_names=["Missing breakdown event"],
        definition=missing_breakdown_event_definition(),
    )
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=viewport,
    )
    open_edit_builder(page, flow_id)
    breakdown = _breakdown(page, 2)
    event_select = breakdown.locator(MDL.FLOW_BUILDER_BREAKDOWN_EVENT)
    helper_text = UI_TEST_STRINGS.METRICS_FLOW_BUILDER_BREAKDOWN_EVENT_MISSING
    expect(event_select).to_have_value(REMOVED_EVENT_NAME)
    _expect_selected_text(event_select, _stale(REMOVED_EVENT_NAME))
    expect(event_select).to_have_attribute("aria-invalid", "true")
    _expect_description_contains(event_select, helper_text)
    expect(
        breakdown.locator(MDL.FLOW_BUILDER_HINT).filter(has_text=helper_text)
    ).to_be_visible()

    group_by = breakdown.locator(MDL.FLOW_BUILDER_BREAKDOWN_GROUP_BY)
    expect(group_by).to_be_disabled()
    _expect_selected_text(group_by, "trigger")
    row = breakdown.locator(MDL.FLOW_BUILDER_BREAKDOWN_FILTER_ROW).nth(0)
    filter_dim = row.locator(MDL.FLOW_BUILDER_BREAKDOWN_FILTER_DIM)
    filter_value = row.locator(MDL.FLOW_BUILDER_BREAKDOWN_FILTER_VALUE)
    expect(filter_dim).to_be_disabled()
    expect(filter_value).to_be_disabled()
    _expect_selected_text(filter_dim, "form")
    _expect_selected_text(filter_value, "url_create")
    expect(row.locator(MDL.FLOW_BUILDER_REMOVE_BREAKDOWN_FILTER_BUTTON)).to_be_enabled()
    expect(breakdown.locator(MDL.FLOW_BUILDER_REMOVE_BREAKDOWN_BUTTON)).to_be_enabled()


# ---------------------------------------------------------------------------
# Damaged and malformed stored data (1280 only)
# ---------------------------------------------------------------------------


def test_damaged_filter_list_on_a_removed_event_shows_server_text_and_recourse(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN a step on a removed event whose stored `dim_filter` is a string
    WHEN the flow opens and Save is pressed
    THEN the summary shows exactly one problem, the server's own "Enter a list
        of items." for the filter list (the removed event is flagged only on the
        needs-attention card, not in the builder summary); Add filter is
        aria-disabled and described by its reason, the server text and the
        recourse hint; Save sends no request.
    """
    [flow_id] = seed_custom_flows(
        display_names=["Damaged removed event"],
        definition=damaged_list_definition(removed_event=True),
    )
    saves = _save_requests(page)
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=DESKTOP_VIEWPORT,
    )
    open_edit_builder(page, flow_id)

    # Intentionally ONE entry: the stale event is flagged only by the
    # needs-attention card, so the builder summary lists just the filter list.
    expect(page.locator(MDL.FLOW_BUILDER_SUMMARY_TITLE)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_ERR_PROBLEM_ONE
    )
    lines = _summary_lines(page)
    expect(lines).to_have_count(1)
    expect(
        lines.filter(
            has_text=UI_TEST_STRINGS.METRICS_FLOW_BUILDER_ERR_FILTERS_LINE.format(
                step=2, message=UI_TEST_STRINGS.METRICS_FLOW_BUILDER_WRONG_TYPE_LIST
            )
        )
    ).to_have_count(1)

    add_filter = builder_step(page, 2).locator(MDL.FLOW_BUILDER_ADD_FILTER_BUTTON)
    expect(add_filter).to_have_attribute("aria-disabled", "true")
    _expect_description_contains(
        add_filter, UI_TEST_STRINGS.METRICS_FLOW_BUILDER_WRONG_TYPE_LIST
    )
    _expect_description_contains(
        add_filter, UI_TEST_STRINGS.METRICS_FLOW_BUILDER_DAMAGED_RECOURSE_STEP
    )
    _press_disabled(add_filter, other=builder_field(page, 2, "label"))
    expect(_step_filter_rows(page, 2)).to_have_count(0)

    page.locator(MDL.FLOW_BUILDER_SAVE_BUTTON).click()
    expect(page.locator(MDL.FLOW_BUILDER_SUMMARY)).to_be_focused()
    assert saves == []


def test_damaged_filter_list_is_replaced_through_add_then_saves(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN a valid step whose stored `dim_filter` is a string
    WHEN the flow opens, Add filter replaces the damaged list and the new row is
        removed again
    THEN the server's list message is shown first (one problem, no request on
        Save), Add clears it, and Save then succeeds with no filters stored.
    """
    [flow_id] = seed_custom_flows(
        display_names=["Damaged valid event"],
        definition=damaged_list_definition(removed_event=False),
    )
    saves = _save_requests(page)
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=DESKTOP_VIEWPORT,
    )
    open_edit_builder(page, flow_id)
    wrong_type = UI_TEST_STRINGS.METRICS_FLOW_BUILDER_WRONG_TYPE_LIST
    expect(page.locator(MDL.FLOW_BUILDER_SUMMARY_TITLE)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_ERR_PROBLEM_ONE
    )
    expect(page.locator(MDL.FLOW_BUILDER_SUMMARY)).to_contain_text(wrong_type)
    page.locator(MDL.FLOW_BUILDER_SAVE_BUTTON).click()
    expect(page.locator(MDL.FLOW_BUILDER_SUMMARY)).to_be_focused()
    assert saves == []

    add_filter = builder_step(page, 2).locator(MDL.FLOW_BUILDER_ADD_FILTER_BUTTON)
    _expect_enabled(add_filter)
    add_filter.click()
    expect(page.locator(MDL.FLOW_BUILDER_SUMMARY)).not_to_contain_text(wrong_type)
    rows = _step_filter_rows(page, 2)
    expect(rows).to_have_count(1)
    rows.nth(0).locator(MDL.FLOW_BUILDER_REMOVE_FILTER_BUTTON).click()
    expect(rows).to_have_count(0)

    page.locator(MDL.FLOW_BUILDER_SAVE_BUTTON).click()
    expect(page.locator(MDL.FLOW_BUILDER)).to_be_hidden()
    assert len(saves) == 1
    reload_flows_tab(page)
    step = list_entry(page, flow_id)["definition"]["steps"][1]
    assert not step.get("dim_filter")


def test_malformed_filter_entry_shows_server_text_and_remove_clears_it(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    seed_custom_flows: SeedCustomFlows,
):
    """
    GIVEN a step whose stored `dim_filter` holds an entry with no colon
    WHEN the flow opens, then the raw row is removed
    THEN the summary shows the server's "Enter a filter as field:value." for
        "Step 2, filter 1" and the row carries it; Save sends no request;
        Remove clears the problem and Save then succeeds.
    """
    [flow_id] = seed_custom_flows(
        display_names=["Malformed entry"], definition=malformed_entry_definition()
    )
    saves = _save_requests(page)
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=DESKTOP_VIEWPORT,
    )
    open_edit_builder(page, flow_id)
    message = UI_TEST_STRINGS.METRICS_FLOW_BUILDER_FILTER_FORMAT
    expect(page.locator(MDL.FLOW_BUILDER_SUMMARY_TITLE)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_ERR_PROBLEM_ONE
    )
    expect(_summary_lines(page)).to_have_text(
        UI_TEST_STRINGS.METRICS_FLOW_BUILDER_ERR_FILTER_LINE.format(
            step=2, n=1, message=message
        )
    )
    rows = _step_filter_rows(page, 2)
    expect(rows).to_have_count(1)
    expect(rows.nth(0).locator(MDL.FLOW_BUILDER_ERROR)).to_have_text(message)
    page.locator(MDL.FLOW_BUILDER_SAVE_BUTTON).click()
    expect(page.locator(MDL.FLOW_BUILDER_SUMMARY)).to_be_focused()
    assert saves == []

    rows.nth(0).locator(MDL.FLOW_BUILDER_REMOVE_FILTER_BUTTON).click()
    expect(rows).to_have_count(0)
    expect(page.locator(MDL.FLOW_BUILDER_SUMMARY)).to_be_hidden()
    page.locator(MDL.FLOW_BUILDER_SAVE_BUTTON).click()
    expect(page.locator(MDL.FLOW_BUILDER)).to_be_hidden()
    assert len(saves) == 1


# ---------------------------------------------------------------------------
# Layout at 420px
# ---------------------------------------------------------------------------


def test_maximum_real_rows_fit_and_meet_touch_targets_at_420px(
    page: Page,
    create_test_users,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a step with every filterable field filtered and a breakdown with every
        one of its own fields filtered (the most rows the real catalog allows)
    WHEN it is shown at 420px
    THEN neither the page, the form nor any step overflows horizontally, every
        visible button is at least 44px square and every visible input and
        select is at least 44px tall with a 16px font.
    """
    open_flows_tab(
        page=page,
        app=provide_app,
        port=provide_port,
        config=provide_config,
        viewport=MOBILE_VIEWPORT,
    )
    open_new_builder(page)
    fill_blank_steps(page)
    _add_step_filter(page, 2, dim="device_type")
    _add_step_filter(page, 2, dim="trigger")
    _add_step_filter(page, 2, dim="form")
    _add_breakdown(page, 2, event=CANCEL_EVENT, group_by="trigger")
    _add_breakdown_filter(page, 2, dim="device_type")
    _add_breakdown_filter(page, 2, dim="trigger")
    _add_breakdown_filter(page, 2, dim="form")
    assert _step_filter_rows(page, 2).count() == 3
    expect(
        builder_step(page, 2).locator(MDL.FLOW_BUILDER_ADD_FILTER_BUTTON)
    ).to_have_attribute("aria-disabled", "true")
    expect(
        _breakdown(page, 2).locator(MDL.FLOW_BUILDER_BREAKDOWN_FILTER_ROW)
    ).to_have_count(3)
    expect(
        _breakdown(page, 2).locator(MDL.FLOW_BUILDER_ADD_BREAKDOWN_FILTER_BUTTON)
    ).to_have_attribute("aria-disabled", "true")

    assert element_overflow(page.locator(MDL.FLOW_BUILDER_FORM)) <= 1
    for step in page.locator(MDL.FLOW_BUILDER_STEP).all():
        assert element_overflow(step) <= 1
    assert page_overflow(page) <= 1

    controls = [
        control
        for control in builder_step(page, 2).locator("button, input, select").all()
        if control.is_visible()
    ]
    assert len(controls) > 10
    for control in controls:
        box = control.bounding_box()
        assert box is not None
        label = control.evaluate("el => el.outerHTML.slice(0, 120)")
        assert box["height"] >= MIN_TOUCH_TARGET_PX, (label, box)
        if control.evaluate("el => el.tagName") == "BUTTON":
            assert box["width"] >= MIN_TOUCH_TARGET_PX, (label, box)
        else:
            font_size = control.evaluate("el => getComputedStyle(el).fontSize")
            assert font_size == BUILDER_INPUT_FONT_SIZE, (label, font_size)
