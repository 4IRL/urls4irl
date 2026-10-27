"""Integration tests for the admin custom metric flow list and create endpoints.

GET  /admin/metrics/flows
POST /admin/metrics/flows
"""

from __future__ import annotations

import copy
from typing import Any, Tuple

import pytest
from flask import Flask
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

import backend.admin.metric_flow_service as metric_flow_service
from backend import db
from backend.admin.constants import AdminActionErrorCodes
from backend.metrics.flow_invalid import first_invalid_detail
from backend.metrics.flow_limits import FLOW_LIMITS
from backend.metrics.flow_validation import serialize_flow_steps, validate_flow_payload
from backend.metrics.flows import (
    ALL_FLOW_IDS,
    FLOWS,
    FlowId,
    format_custom_flow_id,
)
from backend.models.audit_log import AuditLog
from backend.models.metric_flows import Metric_Flows
from backend.models.users import Users
from backend.utils.strings.admin_portal_strs import (
    ADMIN_ACTION_STRINGS,
    ADMIN_AUDIT_ACTIONS,
)
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.admin

_FLOWS_URL: str = "/admin/metrics/flows"
_FLOW_QUERY_URL: str = "/api/metrics/query/flow"
_CUSTOM_NAME: str = "Custom add URL"
_ROOT_KEY: str = "__root__"
_NO_AJAX_HEADERS: dict[str, str] = {URL_VALIDATION.X_REQUESTED_WITH: ""}
_SIX_FIELDS: set[str] = {
    "id",
    "display_name",
    "is_builtin",
    "definition",
    "errors",
    "first_invalid",
}

AdminSession = Tuple[FlaskClient, str, Users, Flask]


def _valid_steps() -> list[dict[str, Any]]:
    """Fresh copy of the serialized add-URL funnel steps."""
    return copy.deepcopy(
        serialize_flow_steps(FLOWS[FlowId.ADD_URL_TO_UTUB])["steps"]  # type: ignore[arg-type]
    )


def _valid_draft(display_name: str = _CUSTOM_NAME) -> dict[str, Any]:
    return {"display_name": display_name, "steps": _valid_steps()}


def _post_flow(client: FlaskClient, csrf: str, body: object) -> TestResponse:
    return client.post(_FLOWS_URL, json=body, headers={"X-CSRFToken": csrf})


def _insert_flow(
    app: Flask,
    *,
    display_name: str,
    definition: dict[str, Any] | None = None,
    created_by: int | None = None,
) -> int:
    with app.app_context():
        row = Metric_Flows(
            display_name=display_name,
            definition=definition
            if definition is not None
            else {"steps": _valid_steps()},
            created_by=created_by,
            updated_by=created_by,
        )
        db.session.add(row)
        db.session.commit()
        return row.id


def _seed_flows(app: Flask, *, count: int) -> None:
    for index in range(count):
        _insert_flow(app, display_name=f"Seeded flow {index}")


def _counts(app: Flask) -> Tuple[int, int]:
    with app.app_context():
        return Metric_Flows.query.count(), AuditLog.query.count()


def _assert_error_envelope(
    response: TestResponse,
    *,
    message: str,
    error_code: int,
    errors: dict[str, list[str]],
) -> None:
    assert response.status_code == 400
    assert response.get_json() == {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: message,
        STD_JSON.ERROR_CODE: error_code,
        STD_JSON.ERRORS: errors,
    }


def _assert_name_taken(response: TestResponse) -> None:
    _assert_error_envelope(
        response,
        message=ADMIN_ACTION_STRINGS.METRIC_FLOW_INVALID,
        error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
        errors={"display_name": [ADMIN_ACTION_STRINGS.METRIC_FLOW_NAME_TAKEN]},
    )


def _assert_cap_reached(response: TestResponse) -> None:
    _assert_error_envelope(
        response,
        message=ADMIN_ACTION_STRINGS.METRIC_FLOW_LIMIT_REACHED,
        error_code=AdminActionErrorCodes.METRIC_FLOW_LIMIT_REACHED,
        errors={_ROOT_KEY: [ADMIN_ACTION_STRINGS.METRIC_FLOW_LIMIT_REACHED]},
    )
    assert AdminActionErrorCodes.METRIC_FLOW_LIMIT_REACHED == 11


def _flow_query_invalid(client: FlaskClient, flow_id: str) -> dict[str, Any]:
    """The `invalid` object of the `422` the flow query returns for `flow_id`."""
    response = client.get(
        f"{_FLOW_QUERY_URL}?flow_id={flow_id}&window=day",
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )
    assert response.status_code == 422
    return response.get_json()["invalid"]


# ---------------------------------------------------------------------------
# Create: happy path
# ---------------------------------------------------------------------------


def test_create_metric_flow_returns_entry_and_audits(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a logged-in admin and a valid draft with a padded name
    WHEN POST /admin/metrics/flows
    THEN 201 with the entry shape, the row stored with the trimmed name and the
         admin as creator/updater, and exactly one create audit row
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    draft = _valid_draft(f"  {_CUSTOM_NAME}  ")

    response = _post_flow(client, csrf, draft)

    assert response.status_code == 201
    body = response.get_json()
    with app.app_context():
        rows = Metric_Flows.query.all()
        assert len(rows) == 1
        row = rows[0]
        row_id, created_by, updated_by = row.id, row.created_by, row.updated_by
        stored_name = row.display_name
        audit_rows = AuditLog.query.all()
        assert len(audit_rows) == 1
        audit_row = audit_rows[0]
        audit_snapshot = (
            audit_row.action,
            audit_row.actor_id,
            audit_row.target_type,
            audit_row.target_id,
            audit_row.log_metadata,
        )
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert _SIX_FIELDS <= set(body)
    assert body["id"] == format_custom_flow_id(row_id)
    assert body["display_name"] == _CUSTOM_NAME
    assert body["is_builtin"] is False
    assert body["definition"] == {"steps": _valid_steps()}
    assert body["errors"] == {}
    assert "first_invalid" in body
    assert body["first_invalid"] is None
    assert stored_name == _CUSTOM_NAME
    assert created_by == admin_user.id
    assert updated_by == admin_user.id
    assert audit_snapshot == (
        ADMIN_AUDIT_ACTIONS.METRIC_FLOW_CREATE,
        admin_user.id,
        "MetricFlow",
        format_custom_flow_id(row_id),
        {"display_name": _CUSTOM_NAME},
    )


# ---------------------------------------------------------------------------
# Create: rejections (each leaves no row and no audit row)
# ---------------------------------------------------------------------------


def test_create_metric_flow_invalid_draft_returns_validator_map(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a draft whose second step names an unknown event
    WHEN POST /admin/metrics/flows
    THEN 400 carries the validator map unchanged and nothing is written
    """
    client, csrf, _, app = login_admin_user_with_register
    draft = _valid_draft()
    draft["steps"][1]["event_name"] = "not_a_real_event"
    with app.app_context():
        expected = validate_flow_payload(draft)
    assert isinstance(expected, dict)
    assert list(expected) == ["steps.1.event_name"]

    response = _post_flow(client, csrf, draft)

    _assert_error_envelope(
        response,
        message=ADMIN_ACTION_STRINGS.METRIC_FLOW_INVALID,
        error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
        errors=expected,
    )
    assert _counts(app) == (0, 0)


def test_create_metric_flow_missing_body_returns_root_error(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN no body and a non-JSON body
    WHEN POST /admin/metrics/flows
    THEN each is a 400 with the `__root__` validator map and nothing is written
    """
    client, csrf, _, app = login_admin_user_with_register
    with app.app_context():
        expected = validate_flow_payload(None)
    assert isinstance(expected, dict)
    assert list(expected) == [_ROOT_KEY]

    no_body = client.post(_FLOWS_URL, headers={"X-CSRFToken": csrf})
    not_json = client.post(
        _FLOWS_URL,
        data="not json",
        content_type="text/plain",
        headers={"X-CSRFToken": csrf},
    )

    for response in (no_body, not_json):
        _assert_error_envelope(
            response,
            message=ADMIN_ACTION_STRINGS.METRIC_FLOW_INVALID,
            error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
            errors=expected,
        )
    assert _counts(app) == (0, 0)


@pytest.mark.parametrize(
    "variant_name",
    [_CUSTOM_NAME, _CUSTOM_NAME.upper(), f"  {_CUSTOM_NAME}  "],
    ids=["exact", "case", "whitespace"],
)
def test_create_metric_flow_duplicate_custom_name_rejected(
    login_admin_user_with_register: AdminSession, variant_name: str
) -> None:
    """
    GIVEN a saved flow
    WHEN a draft reuses its name (exact, other case, padded)
    THEN 400 maps to a `display_name` error and nothing is added
    """
    client, csrf, _, app = login_admin_user_with_register
    _insert_flow(app, display_name=_CUSTOM_NAME)

    response = _post_flow(client, csrf, _valid_draft(variant_name))

    _assert_name_taken(response)
    assert _counts(app) == (1, 0)


def test_create_metric_flow_builtin_name_rejected(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a built-in flow named "Create UTub"
    WHEN a draft is named " create utub "
    THEN 400 maps to a `display_name` error and nothing is written
    """
    client, csrf, _, app = login_admin_user_with_register
    assert FLOWS[FlowId.CREATE_UTUB].display_name.lower() == "create utub"

    response = _post_flow(client, csrf, _valid_draft(" create utub "))

    _assert_name_taken(response)
    assert _counts(app) == (0, 0)


def test_create_metric_flow_cap_rejects_21st_flow(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN 20 saved flows
    WHEN POST /admin/metrics/flows with a new valid draft
    THEN 400 carries the cap envelope with error code 11 and nothing is written
    """
    client, csrf, _, app = login_admin_user_with_register
    _seed_flows(app, count=FLOW_LIMITS.MAX_CUSTOM)

    response = _post_flow(client, csrf, _valid_draft())

    _assert_cap_reached(response)
    assert _counts(app) == (FLOW_LIMITS.MAX_CUSTOM, 0)


def test_create_metric_flow_last_slot_is_allowed(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN 19 saved flows
    WHEN POST /admin/metrics/flows with a new valid draft
    THEN 201 and the table holds 20 rows
    """
    client, csrf, _, app = login_admin_user_with_register
    _seed_flows(app, count=FLOW_LIMITS.MAX_CUSTOM - 1)

    response = _post_flow(client, csrf, _valid_draft())

    assert response.status_code == 201
    assert _counts(app) == (FLOW_LIMITS.MAX_CUSTOM, 1)


def test_create_metric_flow_field_errors_win_over_taken_name(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a saved flow and a draft that reuses its name AND has a bad event
    WHEN POST /admin/metrics/flows
    THEN only the field-error map is returned (no `display_name` entry)
    """
    client, csrf, _, app = login_admin_user_with_register
    _insert_flow(app, display_name=_CUSTOM_NAME)
    draft = _valid_draft(_CUSTOM_NAME.upper())
    draft["steps"][1]["event_name"] = "not_a_real_event"

    response = _post_flow(client, csrf, draft)

    assert response.status_code == 400
    errors = response.get_json()[STD_JSON.ERRORS]
    assert list(errors) == ["steps.1.event_name"]
    assert _counts(app) == (1, 0)


@pytest.mark.parametrize(
    "taken_name",
    [_CUSTOM_NAME.upper(), " create utub "],
    ids=["custom", "builtin"],
)
def test_create_metric_flow_taken_name_wins_over_cap(
    login_admin_user_with_register: AdminSession, taken_name: str
) -> None:
    """
    GIVEN 20 saved flows (one named like a custom flow) and a valid draft
    WHEN the draft reuses a custom (case variant) or built-in name
    THEN the name envelope is returned, not the cap envelope
    """
    client, csrf, _, app = login_admin_user_with_register
    _seed_flows(app, count=FLOW_LIMITS.MAX_CUSTOM - 1)
    _insert_flow(app, display_name=_CUSTOM_NAME)

    response = _post_flow(client, csrf, _valid_draft(taken_name))

    _assert_name_taken(response)
    assert _counts(app) == (FLOW_LIMITS.MAX_CUSTOM, 0)


def test_create_metric_flow_race_on_name_index_maps_to_display_name(
    login_admin_user_with_register: AdminSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN the name pre-check misses (a concurrent create committed the same name)
    WHEN POST /admin/metrics/flows hits the unique `lower(displayName)` index
    THEN the IntegrityError maps to the same `display_name` 400 and no audit row
    """
    client, csrf, _, app = login_admin_user_with_register
    _insert_flow(app, display_name=_CUSTOM_NAME)
    monkeypatch.setattr(
        metric_flow_service, "_is_display_name_taken", lambda **_kwargs: False
    )

    response = _post_flow(client, csrf, _valid_draft(_CUSTOM_NAME.upper()))

    _assert_name_taken(response)
    assert _counts(app) == (1, 0)


def test_create_metric_flow_other_integrity_error_not_mapped_to_display_name(
    login_admin_user_with_register: AdminSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN an IntegrityError whose violated constraint is not the name index
    WHEN POST /admin/metrics/flows
    THEN it is not mapped to the `display_name` 400: the request fails with a
         server error and no row or audit row is written
    """
    client, csrf, _, app = login_admin_user_with_register
    _insert_flow(app, display_name=_CUSTOM_NAME)
    monkeypatch.setattr(
        metric_flow_service, "_is_display_name_taken", lambda **_kwargs: False
    )
    monkeypatch.setattr(
        metric_flow_service, "_violated_constraint", lambda _error: "some_other_check"
    )
    app.config["PROPAGATE_EXCEPTIONS"] = False

    response = _post_flow(client, csrf, _valid_draft(_CUSTOM_NAME.upper()))

    assert response.status_code == 500
    assert _counts(app) == (1, 0)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def test_list_metric_flows_builtins_first_then_custom_by_creation(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN two saved flows (one with no creator)
    WHEN GET /admin/metrics/flows
    THEN built-ins come first in registry order with empty errors and null
         `first_invalid`, then the custom flows by creation; no audit row
    """
    client, _, admin_user, app = login_admin_user_with_register
    first_id = _insert_flow(app, display_name="First saved", created_by=None)
    second_id = _insert_flow(app, display_name="Second saved", created_by=admin_user.id)

    response = client.get(_FLOWS_URL)

    assert response.status_code == 200
    flows = response.get_json()["flows"]
    builtin_count = len(ALL_FLOW_IDS)
    assert [entry["id"] for entry in flows[:builtin_count]] == list(ALL_FLOW_IDS)
    for entry in flows[:builtin_count]:
        assert set(entry) == _SIX_FIELDS
        assert entry["is_builtin"] is True
        assert entry["errors"] == {}
        assert entry["first_invalid"] is None
        assert entry["definition"] == serialize_flow_steps(FLOWS[FlowId(entry["id"])])
        assert entry["display_name"] == FLOWS[FlowId(entry["id"])].display_name
    custom = flows[builtin_count:]
    assert [entry["id"] for entry in custom] == [
        format_custom_flow_id(first_id),
        format_custom_flow_id(second_id),
    ]
    assert [entry["is_builtin"] for entry in custom] == [False, False]
    assert custom[0]["definition"] == {"steps": _valid_steps()}
    assert custom[0]["errors"] == {}
    assert custom[0]["first_invalid"] is None
    assert _counts(app)[1] == 0


def test_list_metric_flows_removed_event_reports_errors_like_flow_query(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a saved flow whose step names an event that no longer exists
    WHEN GET /admin/metrics/flows
    THEN the entry keeps the stored string, `errors` equals the validator map and
         `first_invalid` equals the `invalid` of the flow query's 422
    """
    client, _, _, app = login_admin_user_with_register
    steps = _valid_steps()
    steps[1]["event_name"] = "removed_event"
    definition = {"steps": steps}
    row_id = _insert_flow(app, display_name="Needs attention", definition=definition)
    flow_id = format_custom_flow_id(row_id)
    with app.app_context():
        expected_errors = validate_flow_payload(
            {**definition, "display_name": "Needs attention"}
        )
    assert isinstance(expected_errors, dict)

    entry = next(
        flow
        for flow in client.get(_FLOWS_URL).get_json()["flows"]
        if flow["id"] == flow_id
    )

    assert entry["definition"] == definition
    assert entry["errors"] == expected_errors
    assert entry["first_invalid"] == _flow_query_invalid(client, flow_id)
    assert entry["first_invalid"] == first_invalid_detail(expected_errors).model_dump()
    assert entry["first_invalid"]["step_index"] == 1


def test_list_metric_flows_flow_level_error_returns_raw_definition(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a saved flow whose envelope has one step (below the minimum)
    WHEN GET /admin/metrics/flows
    THEN the entry returns the raw stored definition and a flow-level
         `first_invalid` (null `step_index`) equal to the flow query's 422
    """
    client, _, _, app = login_admin_user_with_register
    definition = {"steps": _valid_steps()[:1]}
    row_id = _insert_flow(app, display_name="Too short", definition=definition)
    flow_id = format_custom_flow_id(row_id)
    with app.app_context():
        expected_errors = validate_flow_payload(
            {**definition, "display_name": "Too short"}
        )
    assert isinstance(expected_errors, dict)

    entry = next(
        flow
        for flow in client.get(_FLOWS_URL).get_json()["flows"]
        if flow["id"] == flow_id
    )

    assert entry["definition"] == definition
    assert entry["errors"] == expected_errors
    assert entry["first_invalid"]["step_index"] is None
    assert entry["first_invalid"] == _flow_query_invalid(client, flow_id)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["get", "post"])
def test_metric_flows_anonymous_returns_401(client: FlaskClient, method: str) -> None:
    """
    GIVEN an anonymous session
    WHEN the list or create endpoint is called
    THEN 401
    """
    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    response = getattr(client, method)(_FLOWS_URL, headers={"X-CSRFToken": csrf_token})

    assert response.status_code == 401


@pytest.mark.parametrize("method", ["get", "post"])
def test_metric_flows_non_admin_returns_404(
    login_first_user_with_register: AdminSession, method: str
) -> None:
    """
    GIVEN a logged-in non-admin
    WHEN the list or create endpoint is called
    THEN 404
    """
    client, csrf, _, app = login_first_user_with_register

    response = getattr(client, method)(_FLOWS_URL, headers={"X-CSRFToken": csrf})

    assert response.status_code == 404
    assert _counts(app) == (0, 0)


@pytest.mark.parametrize("method", ["get", "post"])
def test_metric_flows_admin_without_ajax_header_redirects(
    login_admin_user_with_register: AdminSession, method: str
) -> None:
    """
    GIVEN a logged-in admin sending no AJAX header
    WHEN the list or create endpoint is called
    THEN 302 to /home and nothing is written
    """
    client, csrf, _, app = login_admin_user_with_register

    response = getattr(client, method)(
        _FLOWS_URL,
        json=_valid_draft(),
        headers={**_NO_AJAX_HEADERS, "X-CSRFToken": csrf},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/home")
    assert _counts(app) == (0, 0)
