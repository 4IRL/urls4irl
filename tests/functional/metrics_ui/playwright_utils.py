from __future__ import annotations

import copy
from typing import Any, Callable

from flask import Flask
from playwright.sync_api import BrowserContext, Page

from backend import db
from backend.config import ConfigTestUI
from backend.metrics.events import DeviceType, EventName
from backend.metrics.flow_validation import serialize_flow_steps
from backend.metrics.flows import FLOWS, FlowId, format_custom_flow_id
from backend.metrics.suppression import MIN_CELL_COUNT
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.models.metric_flows import Metric_Flows
from backend.models.users import User_Role, Users
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.playwright_utils import (
    create_user_session_and_provide_session_id,
    login_user_with_cookie_from_session,
)

ADMIN_METRICS_DASHBOARD_PATH: str = "/admin/metrics"
REMOVED_EVENT_NAME: str = "removed_event"
# Type of the `seed_custom_flows` fixture: `(*, display_names, definition=None)`.
SeedCustomFlows = Callable[..., list[str]]


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
