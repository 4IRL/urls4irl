"""Integration tests for the metric flow builder catalog endpoint."""

from __future__ import annotations

import copy
from typing import Any, Tuple

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend.metrics.dimension_models import DIMENSION_MODELS
from backend.metrics.events import EVENT_CATEGORY, EventName
from backend.metrics.flow_validation import (
    serialize_flow_steps,
    validate_flow_payload,
)
from backend.metrics.flows import FLOWS, FlowDefinition, FlowId
from backend.models.audit_log import AuditLog
from backend.models.metric_flows import Metric_Flows
from backend.models.users import Users
from backend.utils.strings.admin_portal_strs import ADMIN_ACTION_STRINGS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.admin

_CATALOG_URL: str = "/admin/metrics/flows/catalog"
_NO_AJAX_HEADERS: dict[str, str] = {URL_VALIDATION.X_REQUESTED_WITH: ""}
_BAD_VALUE: str = "zz-not-a-value"
_SKIPPED_BLUEPRINTS: set[str] = {"metrics", "static", "health"}

AdminSession = Tuple[FlaskClient, str, Users, Flask]


def _counts(app: Flask) -> Tuple[int, int]:
    with app.app_context():
        return Metric_Flows.query.count(), AuditLog.query.count()


def _get_catalog(client: FlaskClient) -> dict[str, Any]:
    response = client.get(_CATALOG_URL)
    assert response.status_code == 200
    return response.get_json()


def _events_by_name(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        event["event_name"]: event
        for group in catalog["event_groups"]
        for event in group["events"]
    }


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------


def test_catalog_groups_events_and_dims(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a logged-in admin
    WHEN GET /admin/metrics/flows/catalog
    THEN groups are ui, domain, api; every EventName appears once; only api events
         are not step-allowed; device_type and api_hit dims have the expected kinds
    """
    client, _, _, _ = login_admin_user_with_register

    catalog = _get_catalog(client)

    assert [group["category"] for group in catalog["event_groups"]] == [
        "ui",
        "domain",
        "api",
    ]
    all_names = [
        event["event_name"]
        for group in catalog["event_groups"]
        for event in group["events"]
    ]
    assert sorted(all_names) == sorted(event.value for event in EventName)
    for group in catalog["event_groups"]:
        names = [event["event_name"] for event in group["events"]]
        assert names == sorted(names)
        for event in group["events"]:
            assert event["category"] == group["category"]
            assert (
                event["category"]
                == EVENT_CATEGORY[EventName(event["event_name"])].value
            )
            assert event["step_allowed"] is (group["category"] != "api")

    events = _events_by_name(catalog)
    api_hit_dims = {dim["key"]: dim for dim in events["api_hit"]["dims"]}
    assert [dim["key"] for dim in events["api_hit"]["dims"]] == [
        "endpoint",
        "method",
        "status_code",
    ]
    assert api_hit_dims["endpoint"]["filter_kind"] == "group_by_only"
    assert api_hit_dims["method"]["filter_kind"] == "group_by_only"
    assert api_hit_dims["status_code"]["filter_kind"] == "status_code"
    assert all(dim["values"] == [] for dim in api_hit_dims.values())

    device_dims = [
        dim
        for event in events.values()
        for dim in event["dims"]
        if dim["key"] == "device_type"
    ]
    assert device_dims
    for dim in device_dims:
        assert dim["filter_kind"] == "values"
        assert dim["values"] == ["1", "2"]

    kinds = {dim["filter_kind"] for event in events.values() for dim in event["dims"]}
    assert {"values", "status_code", "group_by_only"} <= kinds

    dimensionless = [name for name, event in events.items() if event["dims"] == []]
    # Vacuous while every event has a dimension model; pins the branch for later.
    for name in dimensionless:
        assert DIMENSION_MODELS[EventName(name)] is None


def test_catalog_api_endpoints(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a logged-in admin
    WHEN GET /admin/metrics/flows/catalog
    THEN api_endpoints are sorted, carry the blueprint prefix, list only counted
         methods, and exclude the metrics/static/health blueprints
    """
    client, _, _, _ = login_admin_user_with_register

    endpoints = _get_catalog(client)["api_endpoints"]

    names = [entry["endpoint"] for entry in endpoints]
    assert names == sorted(names)
    by_name = {entry["endpoint"]: entry for entry in endpoints}
    assert "POST" in by_name["urls.create_url"]["methods"]
    assert by_name["urls.create_url"]["blueprint"] == "urls"
    for entry in endpoints:
        assert entry["blueprint"] == entry["endpoint"].split(".", 1)[0]
        assert entry["blueprint"] not in _SKIPPED_BLUEPRINTS
        assert entry["methods"] == sorted(entry["methods"])
        assert entry["methods"]
        assert not {"HEAD", "OPTIONS"} & set(entry["methods"])
    assert by_name["admin.get_metric_flow_catalog"]["blueprint"] == "admin"
    assert by_name["admin.list_metric_flows"]["blueprint"] == "admin"
    assert "static" not in by_name


def test_catalog_writes_no_row_and_no_audit_row(
    login_admin_user_with_register: AdminSession,
) -> None:
    client, _, _, app = login_admin_user_with_register

    _get_catalog(client)

    assert _counts(app) == (0, 0)


# ---------------------------------------------------------------------------
# Parity with the validator
# ---------------------------------------------------------------------------


def _base_steps() -> list[dict[str, Any]]:
    """Fresh copy of the serialized add-URL funnel steps (a valid 2+ step draft)."""
    return copy.deepcopy(
        serialize_flow_steps(FLOWS[FlowId.ADD_URL_TO_UTUB])["steps"]  # type: ignore[arg-type]
    )


def _draft(first_step: dict[str, Any]) -> dict[str, Any]:
    steps = _base_steps()
    steps[0] = first_step
    return {"display_name": "Parity probe", "steps": steps}


def _event_step(
    *, event: dict[str, Any], filters: list[str] | None = None
) -> dict[str, Any]:
    step: dict[str, Any] = {
        "stream": event["category"],
        "label": "Probe",
        "event_name": event["event_name"],
    }
    if filters is not None:
        step["dim_filter"] = filters
    return step


def _breakdown_step(
    *, event: dict[str, Any], group_by: str, filters: list[str] | None = None
) -> dict[str, Any]:
    base = _base_steps()[0]
    base.pop("drop_breakdown", None)
    breakdown: dict[str, Any] = {
        "event_name": event["event_name"],
        "group_by": group_by,
    }
    if filters is not None:
        breakdown["dim_filter"] = filters
    base["drop_breakdown"] = breakdown
    return base


def _probe_filter(
    *, event: dict[str, Any], dim_key: str, value: str
) -> tuple[dict[str, Any], str]:
    """Return ``(draft, error_path)`` placing the filter where the event may sit."""
    entry = [f"{dim_key}:{value}"]
    if event["step_allowed"]:
        return _draft(_event_step(event=event, filters=entry)), "steps.0.dim_filter.0"
    draft = _draft(_breakdown_step(event=event, group_by=dim_key, filters=entry))
    return draft, "steps.0.drop_breakdown.dim_filter.0"


def _accepted(payload: dict[str, Any]) -> bool:
    return isinstance(validate_flow_payload(payload), FlowDefinition)


def _rejected_at(payload: dict[str, Any], path: str) -> bool:
    result = validate_flow_payload(payload)
    return isinstance(result, dict) and path in result


def test_catalog_parity_with_validator(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN the catalog served to the builder
    WHEN every listed value, dim, endpoint and method is fed to the validator
    THEN everything listed is accepted and every unlisted value, method or
         group_by_only filter is rejected at the expected path
    """
    client, _, _, app = login_admin_user_with_register
    catalog = _get_catalog(client)
    events = _events_by_name(catalog)

    with app.app_context():
        for event in events.values():
            for dim in event["dims"]:
                key = dim["key"]
                assert _accepted(_draft(_breakdown_step(event=event, group_by=key))), (
                    f"{event['event_name']} group_by {key}"
                )

                if dim["filter_kind"] == "values":
                    assert dim["values"]
                    for value in dim["values"]:
                        draft, _ = _probe_filter(event=event, dim_key=key, value=value)
                        assert _accepted(draft), f"{event['event_name']} {key}:{value}"
                    draft, path = _probe_filter(
                        event=event, dim_key=key, value=_BAD_VALUE
                    )
                    assert _rejected_at(draft, path), (
                        f"{event['event_name']} {key}:{_BAD_VALUE}"
                    )
                elif dim["filter_kind"] == "group_by_only":
                    assert dim["values"] == []
                    draft, path = _probe_filter(event=event, dim_key=key, value="1")
                    assert _rejected_at(draft, path), (
                        f"{event['event_name']} filter {key}"
                    )
                else:
                    assert dim["filter_kind"] == "status_code"
                    assert dim["values"] == []
                    for value in ("404", "100", "599"):
                        draft, _ = _probe_filter(event=event, dim_key=key, value=value)
                        assert _accepted(draft), f"{event['event_name']} {key}:{value}"
                    for value in ("99", "abc", "600", "-40", "40 "):
                        draft, path = _probe_filter(
                            event=event, dim_key=key, value=value
                        )
                        assert _rejected_at(draft, path), (
                            f"{event['event_name']} {key}:{value}"
                        )

        _assert_api_endpoint_parity(catalog["api_endpoints"])


def _assert_api_endpoint_parity(endpoints: list[dict[str, Any]]) -> None:
    all_methods = {"GET", "POST", "PATCH", "PUT", "DELETE"}
    assert endpoints
    for entry in endpoints:
        for method in entry["methods"]:
            step = {
                "stream": "api",
                "label": "Probe",
                "api_endpoint": entry["endpoint"],
                "api_method": method,
            }
            assert _accepted(_draft(step)), f"{entry['endpoint']} {method}"
        for method in sorted(all_methods - set(entry["methods"])):
            step = {
                "stream": "api",
                "label": "Probe",
                "api_endpoint": entry["endpoint"],
                "api_method": method,
            }
            assert _rejected_at(_draft(step), "steps.0.api_method"), (
                f"{entry['endpoint']} {method} should be rejected"
            )


def test_status_code_kind_matches_validator_for_api_step_and_breakdown(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN the status_code filter kind
    WHEN used on an API step and as an api_hit breakdown filter
    THEN 404 is accepted and 99, abc and 600 are rejected at the matching paths
    """
    client, _, _, app = login_admin_user_with_register
    catalog = _get_catalog(client)
    api_hit = _events_by_name(catalog)["api_hit"]
    endpoint = catalog["api_endpoints"][0]

    def api_step(value: str) -> dict[str, Any]:
        return _draft(
            {
                "stream": "api",
                "label": "Probe",
                "api_endpoint": endpoint["endpoint"],
                "api_method": endpoint["methods"][0],
                "dim_filter": [f"status_code:{value}"],
            }
        )

    with app.app_context():
        assert _accepted(api_step("404"))
        for value in ("99", "abc", "600"):
            assert _rejected_at(api_step(value), "steps.0.dim_filter.0")
        draft, _ = _probe_filter(event=api_hit, dim_key="status_code", value="404")
        assert _accepted(draft)
        for value in ("99", "abc", "600"):
            draft, path = _probe_filter(
                event=api_hit, dim_key="status_code", value=value
            )
            assert path == "steps.0.drop_breakdown.dim_filter.0"
            assert _rejected_at(draft, path)


# ---------------------------------------------------------------------------
# Routing, auth and AJAX
# ---------------------------------------------------------------------------


def test_catalog_is_not_read_as_a_flow_id(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a logged-in admin
    WHEN GET and DELETE target /admin/metrics/flows/catalog
    THEN GET is served by the catalog; DELETE still hits the invalid-id 400
    """
    client, csrf, _, app = login_admin_user_with_register

    assert "event_groups" in _get_catalog(client)

    response = client.delete(_CATALOG_URL, headers={"X-CSRFToken": csrf})

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.METRIC_FLOW_INVALID_ID
    assert _counts(app) == (0, 0)


def test_catalog_anonymous_returns_401(client: FlaskClient) -> None:
    csrf_token = get_csrf_token(client.get("/").get_data(), meta_tag=True)

    response = client.get(_CATALOG_URL, headers={"X-CSRFToken": csrf_token})

    assert response.status_code == 401
    assert response.is_json


def test_catalog_non_admin_returns_404(
    login_first_user_with_register: AdminSession,
) -> None:
    client, csrf, _, app = login_first_user_with_register

    response = client.get(_CATALOG_URL, headers={"X-CSRFToken": csrf})

    assert response.status_code == 404
    assert response.is_json
    assert _counts(app) == (0, 0)


def test_catalog_admin_without_ajax_header_redirects(
    login_admin_user_with_register: AdminSession,
) -> None:
    client, csrf, _, app = login_admin_user_with_register

    response = client.get(
        _CATALOG_URL, headers={**_NO_AJAX_HEADERS, "X-CSRFToken": csrf}
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/home")
    assert _counts(app) == (0, 0)
