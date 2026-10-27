"""Integration tests for the metric flow builder preview endpoint."""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from typing import Any, Tuple

import pytest
from flask import Flask
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from backend import db
from backend.admin.constants import AdminActionErrorCodes
from backend.metrics import flow_counting
from backend.metrics.constants import MetricsErrorCodes, MetricsFailureMessages
from backend.metrics.events import EventCategory, EventName
from backend.metrics.flow_limits import FLOW_LIMITS
from backend.metrics.flow_validation import (
    serialize_flow_steps,
    validate_flow_payload,
)
from backend.metrics.flows import FLOWS, FlowId
from backend.models.audit_log import AuditLog
from backend.models.metric_flows import Metric_Flows
from backend.models.users import Users
from backend.utils.strings.admin_portal_strs import ADMIN_ACTION_STRINGS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from tests.integration.system.test_metrics_query_endpoints import (
    _breakdown_raising,
    _bucket_inside_window,
    _scalar_raising_on_third_call,
    _seed_add_url_flow,
    _seed_event_with_count,
)
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.admin

_PREVIEW_URL: str = "/admin/metrics/flows/preview"
_FLOWS_URL: str = "/admin/metrics/flows"
_FLOW_QUERY_URL: str = "/api/metrics/query/flow"
_NO_AJAX_HEADERS: dict[str, str] = {URL_VALIDATION.X_REQUESTED_WITH: ""}

AdminSession = Tuple[FlaskClient, str, Users, Flask]


def _counts(app: Flask) -> Tuple[int, int]:
    with app.app_context():
        return Metric_Flows.query.count(), AuditLog.query.count()


def _base_steps() -> list[dict[str, Any]]:
    return copy.deepcopy(
        serialize_flow_steps(FLOWS[FlowId.ADD_URL_TO_UTUB])["steps"]  # type: ignore[arg-type]
    )


def _filtered_draft(name: str = "Preview probe") -> dict[str, Any]:
    """Add-URL steps plus a ``device_type:2`` filter on step 1 (and its breakdown)."""
    steps = _base_steps()
    steps[1]["dim_filter"] = [*steps[1]["dim_filter"], "device_type:2"]
    return {"display_name": name, "steps": steps}


def _api_breakdown_draft(name: str = "API breakdown probe") -> dict[str, Any]:
    """Add-URL steps whose last step breaks drops down by an ``api_hit`` column."""
    steps = _base_steps()
    steps[3]["drop_breakdown"] = {
        "event_name": EventName.API_HIT.value,
        "group_by": "endpoint",
        "dim_filter": ["status_code:400"],
    }
    return {"display_name": name, "steps": steps}


def _seed_filter_rows(bucket: datetime) -> None:
    """Seed rows so both the device_type filter and drop_breakdown rows count."""
    _seed_add_url_flow(bucket, with_rejections=True)
    _seed_event_with_count(
        event_name=EventName.UI_FORM_SUBMIT,
        category=EventCategory.UI,
        bucket_start=bucket,
        count=3,
        dimensions={"trigger": "button_click", "form": "url_create", "device_type": 1},
    )
    _seed_event_with_count(
        event_name=EventName.UI_FORM_CANCEL,
        category=EventCategory.UI,
        bucket_start=bucket,
        count=2,
        dimensions={"trigger": "button_click", "form": "url_create", "device_type": 2},
    )


def _seed_api_breakdown_rows(bucket: datetime) -> None:
    _seed_add_url_flow(bucket, with_rejections=False)
    # Distinct buckets: (bucket, event, dimensions) is unique and the add-URL
    # seed already used `bucket` for an api_hit row.
    for offset, (endpoint, count) in enumerate(
        (("urls.create_url", 3), ("utubs.create_utub", 2)), start=1
    ):
        _seed_event_with_count(
            event_name=EventName.API_HIT,
            category=EventCategory.API,
            bucket_start=bucket - timedelta(minutes=offset),
            count=count,
            endpoint=endpoint,
            method="POST",
            status_code=400,
        )


def _preview(
    client: FlaskClient,
    csrf: str,
    body: Any,
    *,
    query: str = "?window=day",
) -> TestResponse:
    return client.post(
        f"{_PREVIEW_URL}{query}", json=body, headers={"X-CSRFToken": csrf}
    )


def _save(client: FlaskClient, csrf: str, draft: dict[str, Any]) -> str:
    response = client.post(_FLOWS_URL, json=draft, headers={"X-CSRFToken": csrf})
    assert response.status_code == 201
    return response.get_json()["id"]


def _saved_flow_steps(client: FlaskClient, flow_id: str, query: str) -> Any:
    response = client.get(f"{_FLOW_QUERY_URL}?flow_id={flow_id}&{query}")
    assert response.status_code == 200
    return response.get_json()["steps"]


# ---------------------------------------------------------------------------
# Happy path and parity
# ---------------------------------------------------------------------------


def test_preview_valid_draft_returns_flow_body_and_writes_nothing(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN an admin and seeded add-URL rows
    WHEN a valid draft is previewed for the day window
    THEN 200 with the FlowResponseSchema body and no flow or audit row
    """
    client, csrf, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_add_url_flow(_bucket_inside_window(), with_rejections=True)

    response = _preview(client, csrf, _filtered_draft())

    assert response.status_code == 200
    steps = response.get_json()["steps"]
    assert len(steps) == 4
    assert steps[0]["count"] == 10
    assert _counts(app) == (0, 0)


def test_preview_matches_flow_endpoint_after_save(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a draft with a dim_filter and drop_breakdowns, and seeded rows
    WHEN it is previewed, then saved and read through /flow
    THEN the preview steps equal the /flow steps (day window and absolute range)
    """
    client, csrf, _, app = login_admin_user_with_register
    bucket = _bucket_inside_window()
    with app.app_context():
        _seed_filter_rows(bucket)
    draft = _filtered_draft()

    day_preview = _preview(client, csrf, draft).get_json()
    start = (bucket - timedelta(hours=2)).astimezone(timezone.utc)
    end = (bucket + timedelta(hours=2)).astimezone(timezone.utc)
    range_query = f"start={start.isoformat()}&end={end.isoformat()}"
    range_preview = _preview(
        client,
        csrf,
        draft,
        query="?" + range_query.replace("+", "%2B"),
    )
    flow_id = _save(client, csrf, draft)

    assert day_preview["steps"] == _saved_flow_steps(client, flow_id, "window=day")
    assert range_preview.status_code == 200
    assert range_preview.get_json()["steps"] == _saved_flow_steps(
        client, flow_id, range_query.replace("+", "%2B")
    )
    # The filter and breakdown rows actually counted.
    assert day_preview["steps"][1]["count"] == 8
    # Step 3's breakdown is the (unfiltered) rejection reasons seeded above.
    assert {row["label"] for row in day_preview["steps"][3]["breakdown"]} == {
        "invalid_url",
        "url_already_in_utub",
    }


def test_preview_api_category_breakdown_matches_flow_endpoint(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a draft whose drop_breakdown is an api_hit column grouping with a status filter
    WHEN it is previewed, then saved and read through /flow
    THEN the preview steps equal the /flow steps
    """
    client, csrf, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_api_breakdown_rows(_bucket_inside_window())
    draft = _api_breakdown_draft()

    preview = _preview(client, csrf, draft)
    flow_id = _save(client, csrf, draft)

    assert preview.status_code == 200
    assert preview.get_json()["steps"] == _saved_flow_steps(
        client, flow_id, "window=day"
    )
    breakdown = preview.get_json()["steps"][3]["breakdown"]
    assert {row["label"] for row in breakdown} == {
        "urls.create_url",
        "utubs.create_utub",
    }


def test_preview_empty_window_returns_zero_counts_and_null_pct(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN no metric rows
    WHEN a valid draft is previewed
    THEN 200, every count 0, every pct_of_top null, breakdown lists empty
    """
    client, csrf, _, app = login_admin_user_with_register

    response = _preview(client, csrf, _filtered_draft())

    assert response.status_code == 200
    for step in response.get_json()["steps"]:
        assert step["count"] == 0
        assert step["pct_of_top"] is None
        assert not step["breakdown"]
    assert _counts(app) == (0, 0)


def test_preview_ignores_name_collisions_and_flow_cap(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN an existing custom flow, a built-in name, and 20 stored flows
    WHEN drafts reusing those names are previewed
    THEN each is 200 (no name-uniqueness or cap check)
    """
    client, csrf, admin, app = login_admin_user_with_register
    _save(client, csrf, _filtered_draft("Taken Name"))

    for name in ("taken name", FLOWS[FlowId.ADD_URL_TO_UTUB].display_name):
        assert _preview(client, csrf, _filtered_draft(name)).status_code == 200

    with app.app_context():
        existing = Metric_Flows.query.count()
        definition = serialize_flow_steps(FLOWS[FlowId.ADD_URL_TO_UTUB])
        for index in range(FLOW_LIMITS.MAX_CUSTOM - existing):
            db.session.add(
                Metric_Flows(
                    display_name=f"Filler {index}",
                    definition=definition,
                    created_by=admin.id,
                    updated_by=admin.id,
                )
            )
        db.session.commit()
        assert Metric_Flows.query.count() == FLOW_LIMITS.MAX_CUSTOM

    assert _preview(client, csrf, _filtered_draft("Over cap")).status_code == 200


# ---------------------------------------------------------------------------
# Invalid drafts
# ---------------------------------------------------------------------------


def test_preview_invalid_draft_returns_validator_error_map(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a draft with an unknown event
    WHEN previewed
    THEN 400 with exactly validate_flow_payload's error map, never 422
    """
    client, csrf, _, app = login_admin_user_with_register
    draft = _filtered_draft()
    draft["steps"][0]["event_name"] = "removed_event_xyz"
    with app.app_context():
        expected = validate_flow_payload(draft)
    assert isinstance(expected, dict)

    response = _preview(client, csrf, draft)

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.METRIC_FLOW_INVALID
    assert body[STD_JSON.ERROR_CODE] == int(AdminActionErrorCodes.INVALID_FORM_INPUT)
    assert body[STD_JSON.ERRORS] == expected
    assert "steps.0.event_name" in body[STD_JSON.ERRORS]
    assert _counts(app) == (0, 0)


def test_preview_missing_or_non_object_body_returns_root_error(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a missing body, a non-JSON body and a JSON array
    WHEN previewed
    THEN each is a 400 with a __root__ error
    """
    client, csrf, _, app = login_admin_user_with_register
    headers = {"X-CSRFToken": csrf}
    responses = [
        client.post(f"{_PREVIEW_URL}?window=day", headers=headers),
        client.post(f"{_PREVIEW_URL}?window=day", data="nope", headers=headers),
        _preview(client, csrf, []),
    ]

    for response in responses:
        assert response.status_code == 400
        body = response.get_json()
        assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.METRIC_FLOW_INVALID
        assert list(body[STD_JSON.ERRORS]) == ["__root__"]
    assert _counts(app) == (0, 0)


# ---------------------------------------------------------------------------
# Count-time failures
# ---------------------------------------------------------------------------


def test_preview_scalar_count_failure_returns_400_at_step(
    login_admin_user_with_register: AdminSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, csrf, _, app = login_admin_user_with_register
    monkeypatch.setattr(
        flow_counting,
        "grouped_count_scalar",
        _scalar_raising_on_third_call(flow_counting.grouped_count_scalar),
    )

    response = _preview(client, csrf, _filtered_draft())

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.METRIC_FLOW_INVALID
    assert body[STD_JSON.ERROR_CODE] == int(AdminActionErrorCodes.INVALID_FORM_INPUT)
    assert body[STD_JSON.ERRORS] == {"steps.2": ["boom"]}
    assert _counts(app) == (0, 0)


def test_preview_breakdown_count_failure_returns_400_at_drop_breakdown(
    login_admin_user_with_register: AdminSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, csrf, _, app = login_admin_user_with_register
    monkeypatch.setattr(flow_counting, "grouped_count_by", _breakdown_raising)

    response = _preview(client, csrf, _filtered_draft())

    assert response.status_code == 400
    errors = response.get_json()[STD_JSON.ERRORS]
    assert len(errors) == 1
    ((field, reasons),) = errors.items()
    assert field.startswith("steps.") and field.endswith(".drop_breakdown")
    assert reasons == ["boom"]
    assert _counts(app) == (0, 0)


# ---------------------------------------------------------------------------
# Query, window and routing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query,expected_key",
    [
        ("?window=day&start=2026-01-01T00:00:00Z", "__root__"),
        ("", "__root__"),
        ("?window=day&flow_id=add_url_to_utub", "flow_id"),
        ("?window=day&bogus=1", "bogus"),
    ],
)
def test_preview_bad_query_returns_query_error(
    login_admin_user_with_register: AdminSession, query: str, expected_key: str
) -> None:
    client, csrf, _, app = login_admin_user_with_register

    response = _preview(client, csrf, _filtered_draft(), query=query)

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == MetricsFailureMessages.INVALID_QUERY
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)
    # The window/range XOR is a model validator, so it surfaces under __root__
    # exactly as on /flow; body-path keys never appear here.
    assert expected_key in body[STD_JSON.ERRORS]
    assert not any(key.startswith("steps.") for key in body[STD_JSON.ERRORS])
    assert _counts(app) == (0, 0)


def test_preview_unknown_window_returns_window_error_before_body(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN an unknown window and an invalid body
    WHEN previewed
    THEN the window error wins (query/window are checked before the body)
    """
    client, csrf, _, _ = login_admin_user_with_register

    response = _preview(client, csrf, [], query="?window=not_a_window")

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == MetricsFailureMessages.INVALID_WINDOW
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)
    assert list(body[STD_JSON.ERRORS]) == ["window"]


@pytest.mark.parametrize(
    "query",
    [
        "?start=2026-01-02T00:00:00Z&end=2026-01-01T00:00:00Z",
        "?start=2026-01-01T00:00:00Z&end=2026-01-01T00:00:00Z",
    ],
    ids=["inverted", "empty"],
)
def test_preview_non_increasing_absolute_range_is_rejected(
    login_admin_user_with_register: AdminSession, query: str
) -> None:
    """
    GIVEN an absolute range whose start is not strictly before its end
    WHEN previewed
    THEN 400 and nothing is written. The query schema's range-order validator
         rejects it first (INVALID_QUERY under __root__), so the route's
         INVALID_WINDOW branch is reachable only through named windows.
    """
    client, csrf, _, app = login_admin_user_with_register

    response = _preview(client, csrf, _filtered_draft(), query=query)

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == MetricsFailureMessages.INVALID_QUERY
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)
    assert "__root__" in body[STD_JSON.ERRORS]
    assert _counts(app) == (0, 0)


def test_preview_error_envelopes_by_origin(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a query-parse, a window and a body failure
    WHEN each is previewed
    THEN each keeps its own message, error code and key space
    """
    client, csrf, _, _ = login_admin_user_with_register

    query_error = _preview(client, csrf, _filtered_draft(), query="?bogus=1")
    window_error = _preview(client, csrf, _filtered_draft(), query="?window=zzz")
    body_error = _preview(client, csrf, [])

    query_body = query_error.get_json()
    assert query_body[STD_JSON.MESSAGE] == MetricsFailureMessages.INVALID_QUERY
    assert query_body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)
    assert "bogus" in query_body[STD_JSON.ERRORS]

    window_body = window_error.get_json()
    assert window_body[STD_JSON.MESSAGE] == MetricsFailureMessages.INVALID_WINDOW
    assert window_body[STD_JSON.ERROR_CODE] == int(
        MetricsErrorCodes.INVALID_QUERY_PARAM
    )
    assert list(window_body[STD_JSON.ERRORS]) == ["window"]

    body_body = body_error.get_json()
    assert body_body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.METRIC_FLOW_INVALID
    assert body_body[STD_JSON.ERROR_CODE] == int(
        AdminActionErrorCodes.INVALID_FORM_INPUT
    )
    assert list(body_body[STD_JSON.ERRORS]) == ["__root__"]


def test_preview_path_is_not_shadowed_by_flow_id_routes(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN the static preview rule beside the <flow_id> PUT/DELETE rules
    WHEN PUT and GET target /admin/metrics/flows/preview
    THEN PUT falls through to update's invalid-id 400 and GET is a 405
    """
    client, csrf, _, app = login_admin_user_with_register

    put_response = client.put(
        _PREVIEW_URL, json=_filtered_draft(), headers={"X-CSRFToken": csrf}
    )
    get_response = client.get(_PREVIEW_URL)

    assert put_response.status_code == 400
    assert (
        put_response.get_json()[STD_JSON.MESSAGE]
        == ADMIN_ACTION_STRINGS.METRIC_FLOW_INVALID_ID
    )
    assert get_response.status_code == 405
    assert _counts(app) == (0, 0)


# ---------------------------------------------------------------------------
# Auth, AJAX and CSRF
# ---------------------------------------------------------------------------


def test_preview_anonymous_returns_401_json(client: FlaskClient) -> None:
    csrf_token = get_csrf_token(client.get("/").get_data(), meta_tag=True)

    response = _preview(client, csrf_token, _filtered_draft())

    assert response.status_code == 401
    assert response.is_json


def test_preview_non_admin_returns_404_json(
    login_first_user_with_register: AdminSession,
) -> None:
    client, csrf, _, app = login_first_user_with_register

    response = _preview(client, csrf, _filtered_draft())

    assert response.status_code == 404
    assert response.is_json
    assert _counts(app) == (0, 0)


def test_preview_admin_without_ajax_header_redirects(
    login_admin_user_with_register: AdminSession,
) -> None:
    client, csrf, _, app = login_admin_user_with_register

    response = client.post(
        f"{_PREVIEW_URL}?window=day",
        json=_filtered_draft(),
        headers={**_NO_AJAX_HEADERS, "X-CSRFToken": csrf},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/home")
    assert _counts(app) == (0, 0)


def test_preview_missing_csrf_token_returns_html_403(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN an admin XHR without X-CSRFToken
    WHEN previewed
    THEN 403 as the HTML error page (the shared CSRF handler is JSON only for
        /api/v1); the builder must key off the status code
    """
    client, _, _, app = login_admin_user_with_register

    response = client.post(f"{_PREVIEW_URL}?window=day", json=_filtered_draft())

    assert response.status_code == 403
    assert response.content_type.startswith("text/html")
    assert _counts(app) == (0, 0)
