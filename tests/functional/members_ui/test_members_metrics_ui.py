from __future__ import annotations

from typing import Any

from flask import Flask
from playwright.sync_api import Page, expect
import pytest
from redis import Redis

from backend.cli.mock_constants import USERNAME_BASE
from backend.metrics.events import DeviceType, EventName
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    click_add_member_submit,
    member_badge_by_username,
    open_add_member_combobox,
    seed_co_members_for_owner,
    stage_co_member_suggestion,
    type_in_member_combobox,
)
from tests.functional.metrics_helpers.db_utils import wait_for_metrics_row
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_name

pytestmark = pytest.mark.members_ui

# Headless Chrome at 1920x1080 (see `tests/functional/conftest.py::build_page_browser`)
# resolves to DESKTOP via `frontend/lib/device-type.ts`'s media-query check, and
# the server-side UA classifier resolves the same headless-Chrome UA to DESKTOP.
_EXPECTED_DEVICE_TYPE: int = DeviceType.DESKTOP.value

# An existing user made a co-member of user 1 (shares a seeded OTHER UTub), so
# they surface as a search-result candidate carrying source='search_result'.
_CO_MEMBER = USERNAME_BASE + "2"


def _login_owner_with_co_member(*, app: Flask, page: Page) -> None:
    """Seed one co-member for user 1, then log them into their target UTub."""
    target_utub = get_utub_this_user_created(app, 1)
    seed_co_members_for_owner(app=app, owner_id=1, co_member_usernames=[_CO_MEMBER])
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=1, utub_name=target_utub.name
    )


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
    WHEN the owner opens the add-member combobox, stages a co-member, clicks the
        "Add N" submit, and the test then dispatches a `pagehide` event to fire
        the metrics-client's real flush path
    THEN the flush worker drains the counter into Postgres and exactly one
        `AnonymousMetrics` row exists for `ui_form_submit` with
        `dimensions = {"device_type": 2, "form": "member_invite",
        "trigger": "button_click"}` and count == 1.
    """
    _login_owner_with_co_member(app=provide_app, page=page)

    open_add_member_combobox(page=page)
    stage_co_member_suggestion(page=page, username=_CO_MEMBER)

    # Clicking "Add N" fires `emit(UI_FORM_SUBMIT, form=member_invite,
    # trigger=button_click)` in member-combobox.ts's triggerBatchSubmit.
    click_add_member_submit(page=page)

    # Confirm the add completed (member badge appended to the deck) before
    # triggering the flush — otherwise the emit may not have been buffered yet.
    # The combobox stays open (hiding #displayMemberWrap), so the badge is
    # attached-but-hidden; `to_be_attached` is the correct completion signal.
    expect(member_badge_by_username(page=page, username=_CO_MEMBER)).to_be_attached()

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


def test_search_result_add_emits_member_added_with_source(
    page: Page,
    create_test_utubs: Any,
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics: Any,
):
    """
    GIVEN a logged-in UTub owner with a seeded co-member and metrics enabled
    WHEN the owner stages the co-member from the suggestion list and submits
    THEN the server-side `MEMBER_ADDED` domain event is recorded with
        `dimensions = {"source": "search_result", "device_type": 2}`.
    """
    _login_owner_with_co_member(app=provide_app, page=page)

    open_add_member_combobox(page=page)
    stage_co_member_suggestion(page=page, username=_CO_MEMBER)
    click_add_member_submit(page=page)

    # Wait for the add to complete (badge appended) so the server-side
    # record_event(MEMBER_ADDED) has run before we poll Postgres. The stay-open
    # combobox hides #displayMemberWrap, so assert attachment, not visibility.
    expect(member_badge_by_username(page=page, username=_CO_MEMBER)).to_be_attached()

    expected_dimensions: dict[str, Any] = {
        "source": "search_result",
        "device_type": _EXPECTED_DEVICE_TYPE,
    }
    matched_row = wait_for_metrics_row(
        browser=page,
        redis_client=metrics_redis_client,
        pg_conn=pg_conn_for_metrics,
        event_name=EventName.MEMBER_ADDED,
        expected_dimensions=expected_dimensions,
    )
    assert matched_row["count"] == 1


def test_opening_add_ui_emits_member_add_candidates_loaded(
    page: Page,
    create_test_utubs: Any,
    provide_app: Flask,
    metrics_redis_client: Redis,
    pg_conn_for_metrics: Any,
):
    """
    GIVEN a logged-in UTub owner with a seeded co-member and metrics enabled
    WHEN the owner opens the add-member combobox (firing the co-member GET)
    THEN the server-side `MEMBER_ADD_CANDIDATES_LOADED` domain event is recorded
        with `dimensions = {"has_results": "true", "device_type": 2}`.
    """
    _login_owner_with_co_member(app=provide_app, page=page)

    open_add_member_combobox(page=page)
    # Typing until the suggestion renders proves the co-member GET resolved, so
    # the server-side record_event(MEMBER_ADD_CANDIDATES_LOADED) has already run.
    type_in_member_combobox(page=page, text=_CO_MEMBER)
    expect(
        page.locator(HPL.MEMBER_COMBOBOX_OPTION).filter(
            has=page.locator(
                f"{HPL.MEMBER_COMBOBOX_OPTION_LABEL}:text-is('{_CO_MEMBER}')"
            )
        )
    ).to_be_visible()

    expected_dimensions: dict[str, Any] = {
        "has_results": "true",
        "device_type": _EXPECTED_DEVICE_TYPE,
    }
    matched_row = wait_for_metrics_row(
        browser=page,
        redis_client=metrics_redis_client,
        pg_conn=pg_conn_for_metrics,
        event_name=EventName.MEMBER_ADD_CANDIDATES_LOADED,
        expected_dimensions=expected_dimensions,
    )
    assert matched_row["count"] == 1
