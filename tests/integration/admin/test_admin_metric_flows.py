"""Integration tests for the admin custom metric flow endpoints.

GET    /admin/metrics/flows
POST   /admin/metrics/flows
PUT    /admin/metrics/flows/<flow_id>
DELETE /admin/metrics/flows/<flow_id>
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Tuple

import pytest
from flask import Flask
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

import backend.admin.metric_flow_service as metric_flow_service
from backend import db
from backend.admin.constants import AdminActionErrorCodes
from backend.metrics.constants import MetricsFailureMessages
from backend.metrics.events import EVENT_DESCRIPTIONS, EventCategory, EventName
from backend.metrics.flow_invalid import first_invalid_detail
from backend.metrics.flow_limits import FLOW_LIMITS
from backend.metrics.flow_validation import serialize_flow_steps, validate_flow_payload
from backend.metrics.flows import (
    ALL_FLOW_IDS,
    FLOWS,
    FlowId,
    format_custom_flow_id,
    parse_custom_flow_id,
)
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.models.audit_log import AuditLog
from backend.models.event_registry import Event_Registry
from backend.models.metric_flows import Metric_Flows
from backend.models.users import Users
from backend.utils.strings.admin_portal_strs import (
    ADMIN_ACTION_STRINGS,
    ADMIN_AUDIT_ACTIONS,
)
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.metric_flow_strs import group_by_not_available_message
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
    monkeypatch.setitem(app.config, "PROPAGATE_EXCEPTIONS", False)

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


def test_list_metric_flows_unregistered_group_by_matches_flow_query_422(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a stored flow whose breakdown groups by a declared but unregistered
          dim, and a second valid stored flow
    WHEN the flow query and GET /admin/metrics/flows run
    THEN the bad flow answers 422 with the distinct "cannot break down" text at
         `steps.N.drop_breakdown.group_by`, the list reports the same
         `first_invalid`, and the valid flow still returns 200
    """
    client, _, _, app = login_admin_user_with_register
    steps = _valid_steps()
    breakdown_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("drop_breakdown", {}).get("event_name") == "url_create_rejected"
    )
    steps[breakdown_index]["drop_breakdown"]["group_by"] = "device_type"
    bad_id = format_custom_flow_id(
        _insert_flow(app, display_name="Bad group by", definition={"steps": steps})
    )
    good_id = format_custom_flow_id(_insert_flow(app, display_name="Good flow"))

    invalid = _flow_query_invalid(client, bad_id)

    field = f"steps.{breakdown_index}.drop_breakdown.group_by"
    assert invalid["field"] == field
    assert invalid["step_index"] == breakdown_index
    expected_text = group_by_not_available_message(
        group_by="device_type", allowed=["reason"]
    )
    assert invalid["reason"] == expected_text
    assert "does not exist" not in invalid["reason"]
    flows = client.get(_FLOWS_URL).get_json()["flows"]
    entry = next(flow for flow in flows if flow["id"] == bad_id)
    assert entry["first_invalid"] == invalid
    good = client.get(
        f"{_FLOW_QUERY_URL}?flow_id={good_id}&window=day",
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )
    assert good.status_code == 200


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
# Update and delete
# ---------------------------------------------------------------------------


def _flow_url(flow_id: str) -> str:
    return f"{_FLOWS_URL}/{flow_id}"


def _put_flow(
    client: FlaskClient, csrf: str, flow_id: str, body: object
) -> TestResponse:
    return client.put(_flow_url(flow_id), json=body, headers={"X-CSRFToken": csrf})


def _delete_flow(client: FlaskClient, csrf: str, flow_id: str) -> TestResponse:
    return client.delete(_flow_url(flow_id), headers={"X-CSRFToken": csrf})


def _row_snapshot(app: Flask, row_id: int) -> tuple[Any, ...] | None:
    with app.app_context():
        row = db.session.get(Metric_Flows, row_id)
        if row is None:
            return None
        return (
            row.display_name,
            copy.deepcopy(row.definition),
            row.created_by,
            row.created_at,
            row.updated_by,
        )


def _audit_rows(app: Flask, action: str) -> list[AuditLog]:
    with app.app_context():
        rows = AuditLog.query.filter_by(action=action).all()
        for row in rows:
            db.session.expunge(row)
        return rows


_MALFORMED_IDS: list[str] = [
    "custom_0",
    "custom_007",
    "custom_-1",
    "custom_abc",
    "custom_1000000000",
    "custom_2147483648",
    "Custom_1",
    "custom_",
    *ALL_FLOW_IDS,
]


def _assert_invalid_id(response: TestResponse) -> None:
    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.METRIC_FLOW_INVALID_ID
    assert body[STD_JSON.ERROR_CODE] == AdminActionErrorCodes.INVALID_FORM_INPUT
    assert STD_JSON.ERRORS not in body


def _assert_flow_not_found(response: TestResponse) -> None:
    assert response.status_code == 404
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == MetricsFailureMessages.FLOW_NOT_FOUND
    assert body[STD_JSON.ERROR_CODE] == AdminActionErrorCodes.TARGET_NOT_FOUND


def test_update_metric_flow_returns_entry_and_audits(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a saved flow created by someone else
    WHEN PUT /admin/metrics/flows/<id> with a new valid draft
    THEN 200 with the entry shape; name, definition and updated_by change while
         created_by and created_at keep their values; one update audit row holds
         the previous name and definition
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    old_steps = _valid_steps()
    row_id = _insert_flow(
        app, display_name="Old name", definition={"steps": old_steps}, created_by=None
    )
    flow_id = format_custom_flow_id(row_id)
    before = _row_snapshot(app, row_id)
    assert before is not None
    new_steps = _valid_steps()[:3]
    new_steps[0]["label"] = "Renamed first step"

    response = _put_flow(
        client, csrf, flow_id, {"display_name": " New name ", "steps": new_steps}
    )

    assert response.status_code == 200
    body = response.get_json()
    assert _SIX_FIELDS <= set(body)
    assert body["id"] == flow_id
    assert body["display_name"] == "New name"
    assert body["is_builtin"] is False
    assert body["definition"] == {"steps": new_steps}
    assert body["errors"] == {}
    assert body["first_invalid"] is None
    after = _row_snapshot(app, row_id)
    assert after is not None
    assert after[0] == "New name"
    assert after[1] == {"steps": new_steps}
    assert after[2] == before[2]
    assert after[3] == before[3]
    assert after[4] == admin_user.id
    audit_rows = _audit_rows(app, ADMIN_AUDIT_ACTIONS.METRIC_FLOW_UPDATE)
    assert len(audit_rows) == 1
    assert audit_rows[0].actor_id == admin_user.id
    assert audit_rows[0].target_type == "MetricFlow"
    assert audit_rows[0].target_id == flow_id
    assert audit_rows[0].log_metadata == {
        "display_name": "New name",
        "previous_display_name": "Old name",
        "previous_definition": {"steps": old_steps},
    }
    assert _counts(app)[1] == 1


def test_update_metric_flow_rename_to_own_name_case_variant_succeeds(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a saved flow named `Foo`
    WHEN it is updated with the name `foo`
    THEN 200 (the unique index and pre-check exclude the row itself)
    """
    client, csrf, _, app = login_admin_user_with_register
    row_id = _insert_flow(app, display_name="Foo")

    response = _put_flow(
        client, csrf, format_custom_flow_id(row_id), _valid_draft("foo")
    )

    assert response.status_code == 200
    snapshot = _row_snapshot(app, row_id)
    assert snapshot is not None
    assert snapshot[0] == "foo"


@pytest.mark.parametrize(
    "taken_name",
    ["Other flow", " OTHER FLOW ", FLOWS[FlowId.ADD_URL_TO_UTUB].display_name],
)
def test_update_metric_flow_taken_name_rejected(
    login_admin_user_with_register: AdminSession, taken_name: str
) -> None:
    """
    GIVEN a saved flow and another custom flow
    WHEN the first is renamed to the other's name (any case) or a built-in name
    THEN 400 `display_name` error, the row unchanged and no audit row
    """
    client, csrf, _, app = login_admin_user_with_register
    _insert_flow(app, display_name="Other flow")
    row_id = _insert_flow(app, display_name="Mine")
    before = _row_snapshot(app, row_id)

    response = _put_flow(
        client, csrf, format_custom_flow_id(row_id), _valid_draft(taken_name)
    )

    _assert_name_taken(response)
    assert _row_snapshot(app, row_id) == before
    assert _counts(app)[1] == 0


def test_update_metric_flow_invalid_draft_leaves_row_unchanged(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a saved flow
    WHEN PUT with a draft naming an unknown event
    THEN 400 with the validator map, the row unchanged and no audit row
    """
    client, csrf, _, app = login_admin_user_with_register
    row_id = _insert_flow(app, display_name="Mine")
    before = _row_snapshot(app, row_id)
    draft = _valid_draft("Mine")
    draft["steps"][1]["event_name"] = "not_an_event"
    with app.app_context():
        expected_errors = validate_flow_payload(draft)
    assert isinstance(expected_errors, dict)

    response = _put_flow(client, csrf, format_custom_flow_id(row_id), draft)

    _assert_error_envelope(
        response,
        message=ADMIN_ACTION_STRINGS.METRIC_FLOW_INVALID,
        error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
        errors=expected_errors,
    )
    assert _row_snapshot(app, row_id) == before
    assert _counts(app)[1] == 0


def test_update_metric_flow_race_on_name_index_maps_to_display_name(
    login_admin_user_with_register: AdminSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN the name pre-check misses (a concurrent write took the name)
    WHEN PUT hits the unique `lower(displayName)` index
    THEN the IntegrityError maps to the `display_name` 400, the row is unchanged
         and no audit row exists
    """
    client, csrf, _, app = login_admin_user_with_register
    _insert_flow(app, display_name="Taken")
    row_id = _insert_flow(app, display_name="Mine")
    before = _row_snapshot(app, row_id)
    monkeypatch.setattr(
        metric_flow_service, "_is_display_name_taken", lambda **_kwargs: False
    )

    response = _put_flow(
        client, csrf, format_custom_flow_id(row_id), _valid_draft("TAKEN")
    )

    _assert_name_taken(response)
    assert _row_snapshot(app, row_id) == before
    assert _counts(app)[1] == 0


def test_update_metric_flow_with_cap_reached_succeeds(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN 20 saved flows (the cap)
    WHEN one of them is updated
    THEN 200 (update has no cap check)
    """
    client, csrf, _, app = login_admin_user_with_register
    _seed_flows(app, count=FLOW_LIMITS.MAX_CUSTOM - 1)
    row_id = _insert_flow(app, display_name="Last one")

    response = _put_flow(
        client, csrf, format_custom_flow_id(row_id), _valid_draft("Last one renamed")
    )

    assert response.status_code == 200
    assert _counts(app)[0] == FLOW_LIMITS.MAX_CUSTOM


def test_update_metric_flow_corrected_draft_clears_needs_attention(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a saved flow stored with a removed event (non-empty `errors`)
    WHEN a corrected draft is PUT
    THEN 200 with `errors == {}`, `first_invalid` null and the corrected definition
    """
    client, csrf, _, app = login_admin_user_with_register
    broken_steps = _valid_steps()
    broken_steps[1]["event_name"] = "removed_event"
    row_id = _insert_flow(
        app, display_name="Broken", definition={"steps": broken_steps}
    )

    response = _put_flow(
        client, csrf, format_custom_flow_id(row_id), _valid_draft("Broken")
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["errors"] == {}
    assert body["first_invalid"] is None
    snapshot = _row_snapshot(app, row_id)
    assert snapshot is not None
    assert snapshot[1] == {"steps": _valid_steps()}


def test_delete_metric_flow_removes_row_and_audits_definition(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a saved flow
    WHEN DELETE /admin/metrics/flows/<id>
    THEN 200 success, the row is gone, one delete audit row holds the full stored
         definition, and the flow query for that id is now 404
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    definition = {"steps": _valid_steps()}
    row_id = _insert_flow(app, display_name="Doomed", definition=definition)
    flow_id = format_custom_flow_id(row_id)

    response = _delete_flow(client, csrf, flow_id)

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.METRIC_FLOW_DELETED
    assert _row_snapshot(app, row_id) is None
    audit_rows = _audit_rows(app, ADMIN_AUDIT_ACTIONS.METRIC_FLOW_DELETE)
    assert len(audit_rows) == 1
    assert audit_rows[0].actor_id == admin_user.id
    assert audit_rows[0].target_id == flow_id
    assert audit_rows[0].log_metadata == {
        "display_name": "Doomed",
        "definition": definition,
    }
    query_response = client.get(
        f"{_FLOW_QUERY_URL}?flow_id={flow_id}&window=day",
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )
    assert query_response.status_code == 404


@pytest.mark.parametrize("method", ["put", "delete"])
@pytest.mark.parametrize("flow_id", _MALFORMED_IDS)
def test_update_delete_metric_flow_malformed_or_builtin_id_returns_400(
    login_admin_user_with_register: AdminSession, method: str, flow_id: str
) -> None:
    """
    GIVEN a saved flow
    WHEN update or delete is called with a malformed or built-in id
    THEN 400 `METRIC_FLOW_INVALID_ID`, nothing changes and no audit row
    """
    client, csrf, _, app = login_admin_user_with_register
    _insert_flow(app, display_name="Bystander")

    response = getattr(client, method)(
        _flow_url(flow_id), json=_valid_draft(), headers={"X-CSRFToken": csrf}
    )

    _assert_invalid_id(response)
    assert _counts(app) == (1, 0)


@pytest.mark.parametrize("method", ["put", "delete"])
def test_update_delete_metric_flow_missing_row_returns_404_without_audit(
    login_admin_user_with_register: AdminSession, method: str
) -> None:
    """
    GIVEN no row with the well-formed id `custom_999999999`
    WHEN update or delete is called
    THEN 404 and zero audit rows
    """
    client, csrf, _, app = login_admin_user_with_register

    response = getattr(client, method)(
        _flow_url("custom_999999999"),
        json=_valid_draft(),
        headers={"X-CSRFToken": csrf},
    )

    _assert_flow_not_found(response)
    assert _counts(app) == (0, 0)


@pytest.mark.parametrize(
    "send_body",
    [
        pytest.param(lambda: {"json": {"display_name": "", "steps": []}}, id="invalid"),
        pytest.param(lambda: {}, id="missing"),
        pytest.param(
            lambda: {"data": "not json", "content_type": "text/plain"}, id="non_json"
        ),
    ],
)
def test_update_metric_flow_id_then_lookup_then_validation_order(
    login_admin_user_with_register: AdminSession, send_body: Any
) -> None:
    """
    GIVEN an invalid, missing or non-JSON body
    WHEN PUT to a well-formed id with no row, a malformed id, then an existing row
    THEN 404, 400 invalid id, then 400 validation: id parse, lookup, validation
    """
    client, csrf, _, app = login_admin_user_with_register
    row_id = _insert_flow(app, display_name="Mine")
    before = _row_snapshot(app, row_id)
    headers = {"X-CSRFToken": csrf}

    missing = client.put(_flow_url("custom_999999999"), headers=headers, **send_body())
    malformed = client.put(_flow_url("custom_abc"), headers=headers, **send_body())
    existing = client.put(
        _flow_url(format_custom_flow_id(row_id)), headers=headers, **send_body()
    )

    _assert_flow_not_found(missing)
    _assert_invalid_id(malformed)
    assert existing.status_code == 400
    assert (
        existing.get_json()[STD_JSON.MESSAGE]
        == ADMIN_ACTION_STRINGS.METRIC_FLOW_INVALID
    )
    assert _row_snapshot(app, row_id) == before
    assert _counts(app) == (1, 0)


_ROUND_TRIP_NAME: str = "Round trip"


def _seed_round_trip_metrics(app: Flask) -> None:
    """Seed rows the UTub-create funnel's first two steps and breakdown count."""
    bucket_start = datetime.now(timezone.utc) - timedelta(hours=1)
    rows: list[tuple[EventName, EventCategory, int, dict[str, Any]]] = [
        (EventName.UI_UTUB_CREATE_OPEN, EventCategory.UI, 10, {}),
        (EventName.UI_FORM_SUBMIT, EventCategory.UI, 8, {"form": "utub_create"}),
        (
            EventName.UI_FORM_CANCEL,
            EventCategory.UI,
            2,
            {"form": "utub_create", "trigger": "escape"},
        ),
    ]
    with app.app_context():
        for event_name, category, count, dimensions in rows:
            if (
                Event_Registry.query.filter_by(name=event_name.value).one_or_none()
                is None
            ):
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
                    bucket_start=bucket_start,
                    dimensions=dimensions,
                    count=count,
                )
            )
        db.session.commit()


def test_update_metric_flow_list_definition_round_trips_byte_equal(
    login_admin_user_with_register: AdminSession,
) -> None:
    """
    GIVEN a saved flow whose steps carry `dim_filter` and a `drop_breakdown` with
          its own `dim_filter` and `group_by`, plus seeded metrics in the window
    WHEN its list-entry `definition` is PUT back with the same name
    THEN the stored definition is byte-equal and the flow query is identical
    """
    client, csrf, _, app = login_admin_user_with_register
    steps = serialize_flow_steps(FLOWS[FlowId.CREATE_UTUB])["steps"][:2]  # type: ignore[index]
    assert steps[1]["dim_filter"]
    assert steps[1]["drop_breakdown"]["dim_filter"]
    assert steps[1]["drop_breakdown"]["group_by"]
    create_response = _post_flow(
        client, csrf, {"display_name": _ROUND_TRIP_NAME, "steps": steps}
    )
    assert create_response.status_code == 201
    flow_id = create_response.get_json()["id"]
    row_id = parse_custom_flow_id(flow_id)
    assert row_id is not None
    _seed_round_trip_metrics(app)
    ajax_headers = {URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST}
    query_url = f"{_FLOW_QUERY_URL}?flow_id={flow_id}&window=day"
    query_before = client.get(query_url, headers=ajax_headers)
    assert query_before.status_code == 200
    stored_before = _row_snapshot(app, row_id)
    assert stored_before is not None

    listed = next(
        entry
        for entry in client.get(_FLOWS_URL).get_json()["flows"]
        if entry["id"] == flow_id
    )
    put_response = _put_flow(
        client,
        csrf,
        flow_id,
        {
            "display_name": listed["display_name"],
            "steps": listed["definition"]["steps"],
        },
    )

    assert put_response.status_code == 200
    stored_after = _row_snapshot(app, row_id)
    assert stored_after is not None
    assert json.dumps(stored_after[1], sort_keys=True) == json.dumps(
        stored_before[1], sort_keys=True
    )
    query_after = client.get(query_url, headers=ajax_headers)
    assert query_after.status_code == 200
    assert query_after.get_json() == query_before.get_json()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["put", "delete"])
def test_update_delete_metric_flow_anonymous_returns_401(
    client: FlaskClient, method: str
) -> None:
    """
    GIVEN an anonymous session
    WHEN update or delete is called
    THEN 401
    """
    csrf_token = get_csrf_token(client.get("/").get_data(), meta_tag=True)

    response = getattr(client, method)(
        _flow_url("custom_1"), headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 401


@pytest.mark.parametrize("method", ["put", "delete"])
def test_update_delete_metric_flow_non_admin_returns_404(
    login_first_user_with_register: AdminSession, method: str
) -> None:
    """
    GIVEN a logged-in non-admin
    WHEN update or delete is called
    THEN 404
    """
    client, csrf, _, app = login_first_user_with_register

    response = getattr(client, method)(
        _flow_url("custom_1"), headers={"X-CSRFToken": csrf}
    )

    assert response.status_code == 404
    assert _counts(app) == (0, 0)


@pytest.mark.parametrize("method", ["put", "delete"])
def test_update_delete_metric_flow_admin_without_ajax_header_redirects(
    login_admin_user_with_register: AdminSession, method: str
) -> None:
    """
    GIVEN a logged-in admin sending no AJAX header and an existing flow
    WHEN update or delete is called
    THEN 302 to /home and the flow is untouched
    """
    client, csrf, _, app = login_admin_user_with_register
    row_id = _insert_flow(app, display_name="Mine")
    before = _row_snapshot(app, row_id)

    response = getattr(client, method)(
        _flow_url(format_custom_flow_id(row_id)),
        json=_valid_draft("Changed"),
        headers={**_NO_AJAX_HEADERS, "X-CSRFToken": csrf},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/home")
    assert _row_snapshot(app, row_id) == before
    assert _counts(app)[1] == 0


# ---------------------------------------------------------------------------
# Auth (list and create)
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
