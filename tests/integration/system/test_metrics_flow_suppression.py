"""Floor + flag for dim-filtered flow steps on `GET /api/metrics/query/flow`."""

from __future__ import annotations

import copy
from typing import Any, Tuple

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend.metrics.events import EventCategory, EventName
from backend.metrics.suppression import MIN_CELL_COUNT, SUPPRESSED_DIM_VALUE
from backend.models.users import Users
from backend.utils.constants import generate_constants_js, generate_strings_js
from tests.integration.system.test_metrics_query_endpoints import (
    _add_url_steps,
    _bucket_inside_window,
    _get_custom_flow,
    _insert_custom_flow,
    _seed_add_url_flow,
    _seed_event_with_count,
)

pytestmark = pytest.mark.cli

AdminSession = Tuple[FlaskClient, str, Users, Flask]

_SUBMIT_DIMS: dict[str, Any] = {
    "trigger": "button_click",
    "form": "url_create",
    "device_type": 2,
}


def _seed_submit(app: Flask, *, count: int) -> None:
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UI_FORM_SUBMIT,
            category=EventCategory.UI,
            bucket_start=_bucket_inside_window(),
            count=count,
            dimensions=_SUBMIT_DIMS,
        )


def _seed_domain_added(app: Flask, *, count: int) -> None:
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.URL_ADDED_TO_UTUB,
            category=EventCategory.DOMAIN,
            bucket_start=_bucket_inside_window(),
            count=count,
            dimensions={"device_type": 2},
        )


def _two_step_steps(*, submit_filter: list[str]) -> list[dict[str, Any]]:
    """Submit step (with `submit_filter`, no breakdown) then the domain step."""
    steps = copy.deepcopy(_add_url_steps())
    submit = steps[1]
    submit["dim_filter"] = submit_filter
    submit.pop("drop_breakdown", None)
    domain = steps[3]
    domain.pop("drop_breakdown", None)
    return [submit, domain]


def _flow_steps(
    client: FlaskClient, app: Flask, steps: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    row_id = _insert_custom_flow(app, definition={"steps": steps})
    response = _get_custom_flow(client, row_id)
    assert response.status_code == 200
    return response.get_json()["steps"]


def test_dim_filtered_step_below_floor_is_zeroed_and_flagged(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a UI step filtered on `form` with 3 events and a domain step with 10
    WHEN the custom flow is fetched
    THEN the step reports count 0, count_suppressed true, pct_of_top null, and
        no numeric field anywhere in the body equals 3.
    """
    client, _, _, app = login_admin_user_with_register
    _seed_submit(app, count=3)
    _seed_domain_added(app, count=10)

    steps = _flow_steps(client, app, _two_step_steps(submit_filter=["form:url_create"]))

    assert steps[0]["count"] == 0
    assert steps[0]["count_suppressed"] is True
    assert steps[0]["pct_of_top"] is None
    # A floored top step makes every pct_of_top null and leaks no 3.
    assert steps[1]["count"] == 10
    assert steps[1]["count_suppressed"] is False
    assert steps[1]["pct_of_top"] is None
    for step in steps:
        assert 3 not in (step["count"], step["pct_of_top"])


@pytest.mark.parametrize(
    "submit_filter",
    [["form:url_create"], ["form:url_create", "device_type:2"]],
)
def test_dim_filtered_step_at_floor_returns_real_count(
    login_admin_user_with_register: AdminSession, submit_filter: list[str]
) -> None:
    """
    GIVEN a step filtered on `form` (alone, or mixed with `device_type`) with
        exactly MIN_CELL_COUNT events
    WHEN the custom flow is fetched
    THEN the real count is returned and the step is not flagged.
    """
    client, _, _, app = login_admin_user_with_register
    _seed_submit(app, count=MIN_CELL_COUNT)
    _seed_domain_added(app, count=10)

    steps = _flow_steps(client, app, _two_step_steps(submit_filter=submit_filter))

    assert steps[0]["count"] == MIN_CELL_COUNT
    assert steps[0]["count_suppressed"] is False
    assert steps[0]["pct_of_top"] == 1.0


def test_suppressed_non_top_step_keeps_top_step_real(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN an unfiltered top step (13 events) and a last step filtered on `form`
        matching only 3 events
    WHEN the custom flow is fetched
    THEN the last step is zeroed and flagged with null pct_of_top while the top
        step keeps its real count and a pct_of_top of 1.0.
    """
    client, _, _, app = login_admin_user_with_register
    _seed_submit(app, count=3)
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UI_FORM_SUBMIT,
            category=EventCategory.UI,
            bucket_start=_bucket_inside_window(),
            count=10,
            dimensions={**_SUBMIT_DIMS, "form": "url_string_edit"},
        )

    top, last = (
        _two_step_steps(submit_filter=[])[0],
        _two_step_steps(submit_filter=["form:url_create"])[0],
    )
    steps = _flow_steps(client, app, [top, last])

    assert steps[0]["count"] == 13
    assert steps[0]["count_suppressed"] is False
    assert steps[0]["pct_of_top"] == 1.0
    assert steps[1]["count"] == 0
    assert steps[1]["count_suppressed"] is True
    assert steps[1]["pct_of_top"] is None


def test_mixed_filter_below_floor_is_suppressed(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a step filtered on `device_type` plus `form` with 3 events
    WHEN the custom flow is fetched
    THEN the step is floored and flagged (a mixed filter is not device-only).
    """
    client, _, _, app = login_admin_user_with_register
    _seed_submit(app, count=3)
    _seed_domain_added(app, count=10)

    steps = _flow_steps(
        client,
        app,
        _two_step_steps(submit_filter=["form:url_create", "device_type:2"]),
    )

    assert steps[0]["count"] == 0
    assert steps[0]["count_suppressed"] is True


def test_device_type_only_filter_is_not_floored(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN the add-URL funnel whose step 0 (3 events) filters on `device_type` only
    WHEN the custom flow is fetched
    THEN step 0 reports the real count 3 and is not flagged.
    """
    client, _, _, app = login_admin_user_with_register
    bucket = _bucket_inside_window()
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UI_URL_CREATE_OPEN,
            category=EventCategory.UI,
            bucket_start=bucket,
            count=3,
            dimensions={"device_type": 2},
        )
    _seed_domain_added(app, count=10)
    steps = _add_url_steps()
    steps[0]["dim_filter"] = ["device_type:2"]

    body = _flow_steps(client, app, [steps[0], steps[3]])

    assert body[0]["count"] == 3
    assert body[0]["count_suppressed"] is False


def test_unfiltered_step_is_not_floored(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN an unfiltered domain step with 3 events
    WHEN the custom flow is fetched
    THEN the real count 3 is returned and not flagged.
    """
    client, _, _, app = login_admin_user_with_register
    _seed_submit(app, count=10)
    _seed_domain_added(app, count=3)
    steps = _two_step_steps(submit_filter=["form:url_create"])

    body = _flow_steps(client, app, steps)

    assert body[1]["count"] == 3
    assert body[1]["count_suppressed"] is False


def test_api_step_with_extra_filter_is_not_floored(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN an api-stream step with a non-device `status_code` filter and 3 hits
    WHEN the custom flow is fetched
    THEN the real count 3 is returned and the step is not flagged.
    """
    client, _, _, app = login_admin_user_with_register
    _seed_add_url_flow(_bucket_inside_window(), with_rejections=False)
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.API_HIT,
            category=EventCategory.API,
            bucket_start=_bucket_inside_window().replace(microsecond=1),
            count=3,
            endpoint="urls.update_url",
            method="PATCH",
            status_code=200,
        )
    steps = _add_url_steps()
    api_step = steps[2]
    api_step["api_endpoint"] = "urls.update_url"
    api_step["api_method"] = "PATCH"
    api_step["dim_filter"] = ["status_code:200"]

    body = _flow_steps(client, app, [steps[0], api_step])

    assert body[1]["count"] == 3
    assert body[1]["count_suppressed"] is False


def test_floored_step_breakdown_sub_floor_row_folds_smallest_kept_row(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a floored step whose same-filter breakdown has a sub-floor row of 3
        and a kept row of 6
    WHEN the custom flow is fetched
    THEN secondary suppression folds the kept row in: one "suppressed" row of 9
        and no row carries the lone count 3.
    """
    client, _, _, app = login_admin_user_with_register
    _seed_submit(app, count=3)
    _seed_domain_added(app, count=10)
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UI_FORM_CANCEL,
            category=EventCategory.UI,
            bucket_start=_bucket_inside_window(),
            count=3,
            dimensions={
                "trigger": "button_click",
                "form": "url_create",
                "device_type": 2,
            },
        )
        _seed_event_with_count(
            event_name=EventName.UI_FORM_CANCEL,
            category=EventCategory.UI,
            bucket_start=_bucket_inside_window(),
            count=6,
            dimensions={
                "trigger": "escape_key",
                "form": "url_create",
                "device_type": 2,
            },
        )
    steps = _add_url_steps()
    submit = steps[1]
    submit["dim_filter"] = ["form:url_create"]
    domain = steps[3]
    domain.pop("drop_breakdown", None)

    body = _flow_steps(client, app, [submit, domain])

    assert body[0]["count_suppressed"] is True
    assert body[0]["count"] == 0
    assert body[0]["breakdown"] is not None
    assert [(row["label"], row["count"]) for row in body[0]["breakdown"]] == [
        (SUPPRESSED_DIM_VALUE, 9)
    ]


def test_floored_step_breakdown_lone_sub_floor_row_has_nothing_to_fold(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a floored step whose breakdown holds only a sub-floor row of 3
    WHEN the custom flow is fetched
    THEN no kept row exists to fold in, so the "suppressed" row stays at 3
        (documented residual).
    """
    client, _, _, app = login_admin_user_with_register
    _seed_submit(app, count=3)
    _seed_domain_added(app, count=10)
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UI_FORM_CANCEL,
            category=EventCategory.UI,
            bucket_start=_bucket_inside_window(),
            count=3,
            dimensions={
                "trigger": "button_click",
                "form": "url_create",
                "device_type": 2,
            },
        )
    steps = _add_url_steps()
    submit = steps[1]
    submit["dim_filter"] = ["form:url_create"]
    domain = steps[3]
    domain.pop("drop_breakdown", None)

    body = _flow_steps(client, app, [submit, domain])

    assert body[0]["count_suppressed"] is True
    assert body[0]["count"] == 0
    assert body[0]["breakdown"] is not None
    assert [(row["label"], row["count"]) for row in body[0]["breakdown"]] == [
        (SUPPRESSED_DIM_VALUE, 3)
    ]


def test_bridged_suppressed_dim_value_matches_backend_constant() -> None:
    """
    GIVEN the constants bridged to the frontend
    WHEN SUPPRESSED_DIM_VALUE is read
    THEN it equals the backend sentinel.
    """
    assert generate_constants_js()["SUPPRESSED_DIM_VALUE"] == SUPPRESSED_DIM_VALUE


def test_bridged_suppressed_strings_embed_the_floor() -> None:
    """
    GIVEN the strings bridged to the frontend
    WHEN the suppressed label and aria strings are read
    THEN both name MIN_CELL_COUNT.
    """
    strings = generate_strings_js()
    assert strings["METRICS_SUPPRESSED_LABEL"] == (
        f"suppressed (fewer than {MIN_CELL_COUNT})"
    )
    assert strings["METRICS_FLOW_COUNT_SUPPRESSED_ARIA"] == (
        f"Count suppressed (fewer than {MIN_CELL_COUNT})"
    )
