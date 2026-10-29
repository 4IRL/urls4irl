from __future__ import annotations

import copy
from typing import Any, Callable

from flask import Flask
from playwright.sync_api import BrowserContext, Page

from backend import db
from backend.config import ConfigTestUI
from backend.metrics.flow_validation import serialize_flow_steps
from backend.metrics.flows import FLOWS, FlowId, format_custom_flow_id
from backend.models.metric_flows import Metric_Flows
from backend.models.users import User_Role, Users
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
