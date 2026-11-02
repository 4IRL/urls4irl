from __future__ import annotations

import copy
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import pytest
from flask import Flask
from playwright.sync_api import BrowserContext, Locator, Page, Route, expect

from backend import db
from backend.config import ConfigTestUI
from backend.metrics.events import (
    EVENT_DESCRIPTIONS,
    DeviceType,
    EventCategory,
    EventName,
)
from backend.metrics.flow_limits import FLOW_LIMITS
from backend.metrics.flow_validation import serialize_flow_steps
from backend.metrics.flows import FLOWS, FlowId, format_custom_flow_id
from backend.metrics.suppression import MIN_CELL_COUNT
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.models.event_registry import Event_Registry
from backend.models.metric_flows import Metric_Flows
from backend.models.users import User_Role, Users
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.locators import MetricsDashboardLocators as MDL
from tests.functional.playwright_utils import (
    create_user_session_and_provide_session_id,
    login_user_with_cookie_from_session,
    wait_then_click_element,
)

ADMIN_METRICS_DASHBOARD_PATH: str = "/admin/metrics"
REMOVED_EVENT_NAME: str = "removed_event"
DEFAULT_ADMIN_USER_ID: int = 1
EXPECTED_FLOW_CARD_COUNT: int = 4
# Type of the `seed_custom_flows` fixture: `(*, display_names, definition=None)`.
SeedCustomFlows = Callable[..., list[str]]

DESKTOP_VIEWPORT: dict[str, int] = {"width": 1280, "height": 900}
MOBILE_VIEWPORT: dict[str, int] = {"width": 420, "height": 900}
VIEWPORTS = pytest.mark.parametrize(
    "viewport",
    [DESKTOP_VIEWPORT, MOBILE_VIEWPORT],
    ids=["1280", "420"],
)
FLOW_LIST_URL_RE: re.Pattern[str] = re.compile(r".*/admin/metrics/flows(\?.*)?$")
FLOW_DELETE_URL_RE: re.Pattern[str] = re.compile(r".*/admin/metrics/flows/[^/?]+$")
FLOW_QUERY_URL_RE: re.Pattern[str] = re.compile(r".*/api/metrics/query/flow(\?.*)?$")
MIN_TOUCH_TARGET_PX: int = 44
LONG_FLOW_NAME: str = "x" * FLOW_LIMITS.NAME_MAX_LENGTH


class HeldFlowQueries:
    """Holds every `/api/metrics/query/flow` request until `release()`;
    afterwards requests pass straight through."""

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
        """Requests currently held (zero once released)."""
        return len(self._held)

    def release(self) -> None:
        self._released = True
        for route in self._held:
            route.continue_()
        self._held.clear()


def open_flows_tab(
    *,
    page: Page,
    app: Flask,
    port: int,
    config: ConfigTestUI,
    viewport: dict[str, int] | None = None,
    wait_for_settled: bool = True,
    wait_for_dashboard_idle: bool = False,
) -> None:
    """Log in, open the Flows tab and (by default) wait for every card to leave
    the loading state, since cards are rebuilt when their funnel settles.
    Tests that hold `/flow` responses pass ``wait_for_settled=False``.
    ``wait_for_dashboard_idle=True`` waits for the dashboard root's own load to
    settle (`aria-busy` false) before the tab click, so a late dashboard fetch
    cannot clear the shared `#MetricsErrorBanner` set by a Flows-list failure."""
    if viewport is not None:
        page.set_viewport_size(viewport)
    login_admin_and_open_metrics_dashboard(
        app=app,
        context=page.context,
        page=page,
        port=port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=config,
    )
    if wait_for_dashboard_idle:
        expect(page.locator(MDL.DASHBOARD_ROOT)).to_have_attribute("aria-busy", "false")
    wait_then_click_element(page=page, css_selector=MDL.TAB_FLOWS_BUTTON)
    if wait_for_settled:
        expect(page.locator(MDL.FLOWS_COUNT)).not_to_have_text(
            UI_TEST_STRINGS.METRICS_FLOWS_COUNT_LOADING
        )
        expect(page.locator(MDL.FLOWS_CARD_LOADING)).to_have_count(0)


def custom_card(page: Page, flow_id: str) -> Locator:
    return page.locator(f'{MDL.FLOWS_CARD}[data-flow-id="{flow_id}"]')


def count_text(*, custom: int) -> str:
    return UI_TEST_STRINGS.METRICS_FLOWS_COUNT.format(
        builtin=EXPECTED_FLOW_CARD_COUNT,
        custom=custom,
        max=FLOW_LIMITS.MAX_CUSTOM,
    )


def build_valid_flow_steps() -> list[dict[str, Any]]:
    """Fresh deep copy of the serialized add-URL funnel steps."""
    return copy.deepcopy(
        serialize_flow_steps(FLOWS[FlowId.ADD_URL_TO_UTUB])["steps"]  # type: ignore[arg-type]
    )


def removed_event_definition() -> dict[str, Any]:
    """Definition whose second step names an event that no longer exists
    (needs-attention card with a "Step 2:" prefix)."""
    steps = build_valid_flow_steps()
    steps[1]["event_name"] = REMOVED_EVENT_NAME
    return {"steps": steps}


def one_step_definition() -> dict[str, Any]:
    """Definition with a single step (flow-level needs-attention, no step number)."""
    return {"steps": build_valid_flow_steps()[:1]}


def filtered_breakdown_definition() -> dict[str, Any]:
    """Four-step definition whose submit and domain steps carry a `dim_filter`
    and a `drop_breakdown` (the add-URL funnel), so a form that cannot edit
    either must still round-trip them untouched."""
    steps = build_valid_flow_steps()
    assert steps[1].get("dim_filter"), "filtered step lost its dim_filter"
    assert steps[1].get("drop_breakdown"), "filtered step lost its breakdown"
    assert steps[3].get("drop_breakdown"), "domain step lost its breakdown"
    return {"steps": steps}


def two_step_filtered_definition() -> dict[str, Any]:
    """Minimum-length (2 steps) filtered-and-breakdown definition."""
    steps = build_valid_flow_steps()
    return {"steps": [steps[1], steps[3]]}


# Counts the add-URL funnel seed writes (see `seed_add_url_funnel_metrics`).
SEEDED_OPEN_COUNT: int = 10
SEEDED_SUBMIT_URL_CREATE_COUNT: int = 8
SEEDED_SUBMIT_OTHER_FORM_COUNT: int = 12
SEEDED_API_COUNT: int = 7
SEEDED_DOMAIN_COUNT: int = 6


def _seed_metric_row(
    *,
    event_name: EventName,
    category: EventCategory,
    count: int,
    dimensions: dict[str, Any] | None = None,
    endpoint: str | None = None,
    method: str | None = None,
    status_code: int | None = None,
) -> None:
    if Event_Registry.query.filter_by(name=event_name.value).one_or_none() is None:
        db.session.add(
            Event_Registry(
                name=event_name.value,
                category=category,
                description=EVENT_DESCRIPTIONS[event_name],
            )
        )
        db.session.flush()
    db.session.add(
        Anonymous_Metrics(
            event_name=event_name.value,
            bucket_start=datetime.now(timezone.utc) - timedelta(hours=1),
            dimensions=dimensions if dimensions is not None else {},
            count=count,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
        )
    )
    db.session.commit()


def seed_add_url_funnel_metrics(*, app: Flask) -> None:
    """Seed non-zero counts for every step and breakdown of the add-URL funnel,
    plus submits from another form that the `form:url_create` filter must drop
    (DD-10: the uniform seed has no data for these events)."""
    ui_dims = {"device_type": 2}
    with app.app_context():
        _seed_metric_row(
            event_name=EventName.UI_URL_CREATE_OPEN,
            category=EventCategory.UI,
            count=SEEDED_OPEN_COUNT,
            dimensions=ui_dims,
        )
        _seed_metric_row(
            event_name=EventName.UI_FORM_SUBMIT,
            category=EventCategory.UI,
            count=SEEDED_SUBMIT_URL_CREATE_COUNT,
            dimensions={
                "trigger": "button_click",
                "form": "url_create",
                "device_type": 2,
            },
        )
        _seed_metric_row(
            event_name=EventName.UI_FORM_SUBMIT,
            category=EventCategory.UI,
            count=SEEDED_SUBMIT_OTHER_FORM_COUNT,
            dimensions={
                "trigger": "button_click",
                "form": "utub_create",
                "device_type": 2,
            },
        )
        _seed_metric_row(
            event_name=EventName.UI_FORM_CANCEL,
            category=EventCategory.UI,
            count=SEEDED_OPEN_COUNT,
            dimensions={
                "trigger": "escape_key",
                "form": "url_create",
                "device_type": 2,
            },
        )
        _seed_metric_row(
            event_name=EventName.API_HIT,
            category=EventCategory.API,
            count=SEEDED_API_COUNT,
            endpoint="urls.create_url",
            method="POST",
            status_code=201,
        )
        _seed_metric_row(
            event_name=EventName.URL_ADDED_TO_UTUB,
            category=EventCategory.DOMAIN,
            count=SEEDED_DOMAIN_COUNT,
            dimensions=ui_dims,
        )
        _seed_metric_row(
            event_name=EventName.URL_CREATE_REJECTED,
            category=EventCategory.DOMAIN,
            count=6,
            dimensions={"reason": "invalid_url", "device_type": 2},
        )
        _seed_metric_row(
            event_name=EventName.URL_CREATE_REJECTED,
            category=EventCategory.DOMAIN,
            count=5,
            dimensions={"reason": "url_already_in_utub", "device_type": 2},
        )


def insert_custom_flows(
    *,
    app: Flask,
    display_names: list[str],
    definition: dict[str, Any] | None = None,
    created_by: int = 1,
) -> list[str]:
    """Insert one `Metric_Flows` row per display name and return the
    `custom_<id>` flow ids, in order."""
    flow_ids: list[str] = []
    with app.app_context():
        for display_name in display_names:
            row = Metric_Flows(
                display_name=display_name,
                definition=copy.deepcopy(definition)
                if definition is not None
                else {"steps": build_valid_flow_steps()},
                created_by=created_by,
                updated_by=created_by,
            )
            db.session.add(row)
            db.session.commit()
            flow_ids.append(format_custom_flow_id(row.id))
    return flow_ids


def promote_user_to_admin(*, app: Flask, user_id: int) -> None:
    """Promote a Users row to the ADMIN role so the user can access
    `/admin/metrics`.

    Mirrors the integration test fixture pattern — opens an app context,
    fetches the user by id, mutates the `role` column, and commits.
    """
    with app.app_context():
        user_to_promote: Users | None = Users.query.get(user_id)
        assert user_to_promote is not None, (
            f"promote_user_to_admin: no Users row found for user_id={user_id}"
        )
        user_to_promote.role = User_Role.ADMIN
        db.session.commit()


SUB_FLOOR_ROW_BATCH_SIZE_BUCKETS: tuple[str, ...] = ("26-100", "101+")
SUB_FLOOR_ROW_COUNT: int = MIN_CELL_COUNT - 2


def insert_sub_floor_ingest_batch_row(*, app: Flask) -> None:
    """Insert two `API_METRICS_INGEST_BATCH` rows, each below `MIN_CELL_COUNT`
    with dims tuples distinct from the shared seed.

    Their sum reaches the floor, so the sentinel folds exactly these two rows
    and secondary suppression does not pull a seeded cell into it (which would
    drop a seeded column). Rows sit at the current hour (inside the 24h
    window). Cleanup is covered by the autouse `clear_db` fixture.
    """
    assert SUB_FLOOR_ROW_COUNT < MIN_CELL_COUNT
    assert SUB_FLOOR_ROW_COUNT * len(SUB_FLOOR_ROW_BATCH_SIZE_BUCKETS) >= MIN_CELL_COUNT
    with app.app_context():
        current_hour = utc_now().replace(minute=0, second=0, microsecond=0)
        for batch_size_bucket in SUB_FLOOR_ROW_BATCH_SIZE_BUCKETS:
            db.session.add(
                Anonymous_Metrics(
                    event_name=EventName.API_METRICS_INGEST_BATCH.value,
                    bucket_start=current_hour,
                    endpoint=None,
                    method=None,
                    status_code=None,
                    dimensions={
                        "batch_size_bucket": batch_size_bucket,
                        "transport": "beacon",
                        "device_type": DeviceType.MOBILE.value,
                    },
                    count=SUB_FLOOR_ROW_COUNT,
                )
            )
        db.session.commit()


SUB_FLOOR_FLOW_COUNT: int = MIN_CELL_COUNT - 2
FLOW_TOP_STEP_COUNT: int = MIN_CELL_COUNT * 2


def insert_sub_floor_create_utub_flow_rows(*, app: Flask) -> None:
    """Seed the built-in "Create UTub" flow so its `form=utub_create` submit
    step and its same-filter cancel breakdown are both below `MIN_CELL_COUNT`.

    The top step (`UI_UTUB_CREATE_OPEN`) is above the floor, so the card
    renders; the dim-filtered step is floored and the lone sub-floor
    breakdown row (no kept cell to fold in) renders as the suppressed pill.
    Rows sit at the current hour (inside the window); cleanup is covered by
    the autouse `clear_db` fixture.
    """
    current_hour = utc_now().replace(minute=0, second=0, microsecond=0)
    device_type = DeviceType.DESKTOP.value
    seeded_rows: list[tuple[EventName, int, dict[str, str | int]]] = [
        (
            EventName.UI_UTUB_CREATE_OPEN,
            FLOW_TOP_STEP_COUNT,
            {"device_type": device_type},
        ),
        (
            EventName.UI_FORM_SUBMIT,
            SUB_FLOOR_FLOW_COUNT,
            {
                "trigger": "button_click",
                "form": "utub_create",
                "device_type": device_type,
            },
        ),
        (
            EventName.UI_FORM_CANCEL,
            SUB_FLOOR_FLOW_COUNT,
            {
                "trigger": "escape_key",
                "form": "utub_create",
                "device_type": device_type,
            },
        ),
    ]
    with app.app_context():
        for event_name, count, dimensions in seeded_rows:
            db.session.add(
                Anonymous_Metrics(
                    event_name=event_name.value,
                    bucket_start=current_hour,
                    endpoint=None,
                    method=None,
                    status_code=None,
                    dimensions=dimensions,
                    count=count,
                )
            )
        db.session.commit()


def login_admin_and_open_metrics_dashboard(
    *,
    app: Flask,
    context: BrowserContext,
    page: Page,
    port: int,
    user_id: int,
    config: ConfigTestUI,
) -> None:
    """Promote `user_id` to ADMIN, log them in via session cookie, then
    navigate the page directly to the admin metrics dashboard.

    Uses the same `create_user_session_and_provide_session_id` +
    `login_user_with_cookie_from_session` pair the other UI suites use
    so the Playwright context matches a logged-in browser exactly. The
    host portion of the URL is selected from the test config so the
    helper works both inside Docker (where the browser-server reaches Flask
    via `http://<U4I_WEB_HOST>:<port>`) and on the host (`http://127.0.0.1:<port>`).
    """
    promote_user_to_admin(app=app, user_id=user_id)
    session_id = create_user_session_and_provide_session_id(app=app, user_id=user_id)
    base_url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL if config.DOCKER else UI_TEST_STRINGS.BASE_URL
    )
    login_user_with_cookie_from_session(
        context=context, session_id=session_id, base_url=f"{base_url}{port}"
    )
    page.goto(f"{base_url}{port}{ADMIN_METRICS_DASHBOARD_PATH}")
