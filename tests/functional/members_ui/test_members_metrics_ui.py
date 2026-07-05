from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from playwright.sync_api import Page
from redis import Redis

from backend.cli.mock_constants import USERNAME_BASE
from backend.metrics.events import DeviceType, EventName
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import create_member_active_utub
from tests.functional.metrics_helpers.db_utils import wait_for_metrics_row
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_name
from tests.functional.playwright_utils import (
    wait_then_click_element,
    wait_until_hidden,
)

pytestmark = pytest.mark.members_ui

# Headless Chrome at 1920x1080 (see `tests/functional/conftest.py::build_page_browser`)
# resolves to DESKTOP via `frontend/lib/device-type.ts`'s media-query check.
_EXPECTED_DEVICE_TYPE: int = DeviceType.DESKTOP.value


def test_member_invite_form_submit_emits_to_anonymous_metrics(
    page: Page,
    create_test_utubs: Any,
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics: Any,
):
    """
    GIVEN a logged-in UTub owner with a UTub selected and the metrics
        pipeline activated end-to-end
    WHEN the owner opens the invite-member form, types another user's
        username, clicks the submit button, and the test then dispatches a
        `pagehide` event to fire the metrics-client's real flush path
    THEN the flush worker drains the counter into Postgres and exactly one
        `AnonymousMetrics` row exists for `ui_form_submit` with
        `dimensions = {"device_type": 2, "form": "member_invite",
        "trigger": "button_click"}` and count == 1.
    """
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(provide_app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=provide_app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
    )

    new_member_username = USERNAME_BASE + "2"
    create_member_active_utub(page=page, member_name=new_member_username)

    # Submitting the invite form fires
    # `emitFormSubmit("member_invite", "button_click")` in
    # `frontend/home/members/create.ts`.
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_SUBMIT_CREATE)

    # Confirm the invite POST completed (submit button hidden) before
    # triggering the flush — otherwise the emit may not have been buffered
    # yet and the dispatch would flush an empty buffer.
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_MEMBER_SUBMIT_CREATE)

    expected_dimensions: dict[str, Any] = {
        "device_type": _EXPECTED_DEVICE_TYPE,
        "form": "member_invite",
        "trigger": "button_click",
    }
    matched_row = wait_for_metrics_row(
        browser=page,
        redis_client=metrics_redis_client,
        pg_conn=pg_conn_for_metrics,
        event_name=EventName.UI_FORM_SUBMIT,
        expected_dimensions=expected_dimensions,
    )
    assert matched_row["count"] == 1
    assert matched_row["bucket_start"] is not None
