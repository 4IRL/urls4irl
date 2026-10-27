"""Service layer for the admin custom metric flow endpoints (list, create, update, delete)."""

from __future__ import annotations

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError

from backend import db
from backend.admin.constants import METRIC_FLOW_CAP_LOCK_KEY, AdminActionErrorCodes
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs
from backend.extensions.audit.record import record
from backend.metrics.constants import MetricsFailureMessages
from backend.metrics.flow_invalid import first_invalid_detail
from backend.metrics.flow_limits import FLOW_LIMITS
from backend.metrics.flow_validation import (
    inspect_flow_payload,
    serialize_flow_steps,
    validate_flow_payload,
)
from backend.metrics.flows import (
    ALL_FLOW_IDS,
    FLOWS,
    FlowDefinition,
    FlowId,
    format_custom_flow_id,
    parse_custom_flow_id,
)
from backend.models.metric_flows import DISPLAY_NAME_LOWER_INDEX, Metric_Flows
from backend.schemas.admin_actions import AdminActionResponseSchema
from backend.schemas.errors import (
    build_field_error_response,
    build_message_error_response,
)
from backend.schemas.metrics import MetricFlowEntrySchema, MetricFlowListResponseSchema
from backend.utils.strings.admin_portal_strs import (
    ADMIN_ACTION_STRINGS,
    ADMIN_AUDIT_ACTIONS,
)
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON

METRIC_FLOW_AUDIT_TARGET_TYPE: str = "MetricFlow"
_ROOT_KEY: str = "__root__"
_DISPLAY_NAME_KEY: str = "display_name"


def _violated_constraint(error: IntegrityError) -> str | None:
    """Return the name of the constraint a Postgres ``IntegrityError`` violated, if known."""
    diagnostics = getattr(error.orig, "diag", None)
    return getattr(diagnostics, "constraint_name", None)


def build_builtin_flow_entry(*, flow_id: FlowId) -> MetricFlowEntrySchema:
    """Return the list entry for a built-in funnel (never has errors)."""
    definition = FLOWS[flow_id]
    return MetricFlowEntrySchema(
        id=flow_id.value,
        display_name=definition.display_name,
        is_builtin=True,
        definition=serialize_flow_steps(definition),
        errors={},
        first_invalid=None,
    )


def build_flow_entry(*, row: Metric_Flows) -> MetricFlowEntrySchema:
    """Return the list entry for a saved custom funnel.

    The stored envelope is validated with the column name, exactly as the flow
    query does, so ``errors`` and ``first_invalid`` always agree with its ``422``.
    A flow that hydrates is returned in the normalized stored shape; one whose
    envelope fails the lenient model is returned as its raw stored JSON.
    """
    draft, errors = inspect_flow_payload(
        {**row.definition, _DISPLAY_NAME_KEY: row.display_name}
    )
    definition: dict[str, object]
    if draft is not None:
        definition = {
            "steps": [
                step.model_dump(mode="json", exclude_none=True) for step in draft.steps
            ]
        }
    else:
        definition = row.definition
    return MetricFlowEntrySchema(
        id=format_custom_flow_id(row.id),
        display_name=row.display_name,
        is_builtin=False,
        definition=definition,
        errors=errors,
        first_invalid=first_invalid_detail(errors) if errors else None,
    )


def list_metric_flows() -> FlaskResponse:
    """Return every funnel: built-ins in registry order, then custom by creation."""
    entries: list[MetricFlowEntrySchema] = [
        build_builtin_flow_entry(flow_id=FlowId(flow_id)) for flow_id in ALL_FLOW_IDS
    ]
    custom_rows = Metric_Flows.query.order_by(
        Metric_Flows.created_at, Metric_Flows.id
    ).all()
    entries.extend(build_flow_entry(row=row) for row in custom_rows)
    return APIResponse(
        data=MetricFlowListResponseSchema(flows=entries), status_code=200
    ).to_response()


def _display_name_taken_response() -> FlaskResponse:
    return build_field_error_response(
        message=ADMIN_ACTION_STRINGS.METRIC_FLOW_INVALID,
        errors={_DISPLAY_NAME_KEY: [ADMIN_ACTION_STRINGS.METRIC_FLOW_NAME_TAKEN]},
        error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
        status_code=400,
    )


def _is_display_name_taken(
    *, display_name: str, exclude_row_id: int | None = None
) -> bool:
    """True when a built-in or saved flow already uses this name, ignoring case.

    Built-ins are compared with Python ``str.lower()`` and saved flows with
    Postgres ``lower()`` on purpose: the latter is exactly what the unique index
    uses, so the pre-check and the backstop agree. ``exclude_row_id`` skips the
    row being updated so it may be renamed to another case of its own name.
    """
    lowered_name = display_name.lower()
    if any(
        built_in.display_name.strip().lower() == lowered_name
        for built_in in FLOWS.values()
    ):
        return True
    query = db.session.query(Metric_Flows.id).filter(
        func.lower(Metric_Flows.display_name) == func.lower(display_name)
    )
    if exclude_row_id is not None:
        query = query.filter(Metric_Flows.id != exclude_row_id)
    return query.first() is not None


def create_metric_flow(*, actor_id: int, payload: object) -> FlaskResponse:
    """Validate and save a new custom funnel, auditing it in the same transaction.

    Errors surface one class at a time, in this order: the draft itself, the
    name, then the cap. The count and the insert run under a transaction-scoped
    advisory lock taken before the count, so two concurrent creates at one below
    the cap cannot both pass it. The unique ``lower(displayName)`` index remains
    the backstop for two concurrent creates of the same name.

    Returns:
        FlaskResponse: 201 with the saved entry, or a 400 envelope.
    """
    validated = validate_flow_payload(payload)
    if not isinstance(validated, FlowDefinition):
        return build_field_error_response(
            message=ADMIN_ACTION_STRINGS.METRIC_FLOW_INVALID,
            errors=validated,
            error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
            status_code=400,
        )

    if _is_display_name_taken(display_name=validated.display_name):
        db.session.rollback()
        return _display_name_taken_response()

    db.session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": METRIC_FLOW_CAP_LOCK_KEY}
    )
    if Metric_Flows.query.count() >= FLOW_LIMITS.MAX_CUSTOM:
        # Rolling back ends the transaction, releasing the advisory lock.
        db.session.rollback()
        return build_field_error_response(
            message=ADMIN_ACTION_STRINGS.METRIC_FLOW_LIMIT_REACHED,
            errors={_ROOT_KEY: [ADMIN_ACTION_STRINGS.METRIC_FLOW_LIMIT_REACHED]},
            error_code=AdminActionErrorCodes.METRIC_FLOW_LIMIT_REACHED,
            status_code=400,
        )

    try:
        with db.session.begin_nested():
            row = Metric_Flows(
                display_name=validated.display_name,
                definition=serialize_flow_steps(validated),
                created_by=actor_id,
                updated_by=actor_id,
            )
            db.session.add(row)
            db.session.flush()
    except IntegrityError as integrity_error:
        db.session.rollback()
        if _violated_constraint(integrity_error) != DISPLAY_NAME_LOWER_INDEX:
            raise
        return _display_name_taken_response()

    flow_id: str = format_custom_flow_id(row.id)
    entry = build_flow_entry(row=row)
    record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.METRIC_FLOW_CREATE,
        target_type=METRIC_FLOW_AUDIT_TARGET_TYPE,
        target_id=flow_id,
        metadata={"display_name": validated.display_name},
    )
    db.session.commit()
    safe_add_many_logs(
        ["Created metric flow", f"User.id={actor_id}", f"MetricFlow.id={flow_id}"]
    )
    return APIResponse(data=entry, status_code=201).to_response()


def _invalid_id_response() -> FlaskResponse:
    return build_message_error_response(
        message=ADMIN_ACTION_STRINGS.METRIC_FLOW_INVALID_ID,
        error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
        status_code=400,
    )


def _not_found_response() -> FlaskResponse:
    return build_message_error_response(
        message=MetricsFailureMessages.FLOW_NOT_FOUND,
        error_code=AdminActionErrorCodes.TARGET_NOT_FOUND,
        status_code=404,
    )


def _get_locked_row(*, flow_id: str) -> Metric_Flows | FlaskResponse:
    """Parse the id and fetch its row under a row lock.

    Returns the row on success, else the error response: 400 for a malformed or
    built-in id, 404 for a well-formed id with no row. Any early exit rolls back
    so the row lock is not held.
    """
    row_id = parse_custom_flow_id(flow_id)
    if row_id is None:
        return _invalid_id_response()
    row = db.session.get(Metric_Flows, row_id, with_for_update=True)
    if row is None:
        db.session.rollback()
        return _not_found_response()
    return row


def update_metric_flow(
    *, actor_id: int, flow_id: str, payload: object
) -> FlaskResponse:
    """Replace a saved funnel's name and steps (last write wins), auditing it.

    Checks run in this order: id parse (400), locked row lookup (404), draft
    validation (400), name (400). There is no cap check: the row already exists.

    Returns:
        FlaskResponse: 200 with the updated entry, or a 400/404 envelope.
    """
    row = _get_locked_row(flow_id=flow_id)
    if not isinstance(row, Metric_Flows):
        return row

    validated = validate_flow_payload(payload)
    if not isinstance(validated, FlowDefinition):
        db.session.rollback()
        return build_field_error_response(
            message=ADMIN_ACTION_STRINGS.METRIC_FLOW_INVALID,
            errors=validated,
            error_code=AdminActionErrorCodes.INVALID_FORM_INPUT,
            status_code=400,
        )

    if _is_display_name_taken(
        display_name=validated.display_name, exclude_row_id=row.id
    ):
        db.session.rollback()
        return _display_name_taken_response()

    previous_display_name: str = row.display_name
    previous_definition = row.definition
    try:
        with db.session.begin_nested():
            row.display_name = validated.display_name
            row.definition = serialize_flow_steps(validated)
            row.updated_by = actor_id
            db.session.flush()
    except IntegrityError as integrity_error:
        db.session.rollback()
        if _violated_constraint(integrity_error) != DISPLAY_NAME_LOWER_INDEX:
            raise
        return _display_name_taken_response()

    entry = build_flow_entry(row=row)
    record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.METRIC_FLOW_UPDATE,
        target_type=METRIC_FLOW_AUDIT_TARGET_TYPE,
        target_id=flow_id,
        metadata={
            "display_name": validated.display_name,
            "previous_display_name": previous_display_name,
            "previous_definition": previous_definition,
        },
    )
    db.session.commit()
    safe_add_many_logs(
        ["Updated metric flow", f"User.id={actor_id}", f"MetricFlow.id={flow_id}"]
    )
    return APIResponse(data=entry, status_code=200).to_response()


def delete_metric_flow(*, actor_id: int, flow_id: str) -> FlaskResponse:
    """Hard-delete a saved funnel; the audit row keeps its full definition.

    Returns:
        FlaskResponse: 200 success message, or a 400/404 envelope.
    """
    row = _get_locked_row(flow_id=flow_id)
    if not isinstance(row, Metric_Flows):
        return row

    display_name: str = row.display_name
    definition = row.definition
    db.session.delete(row)
    record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.METRIC_FLOW_DELETE,
        target_type=METRIC_FLOW_AUDIT_TARGET_TYPE,
        target_id=flow_id,
        metadata={"display_name": display_name, "definition": definition},
    )
    db.session.commit()
    safe_add_many_logs(
        ["Deleted metric flow", f"User.id={actor_id}", f"MetricFlow.id={flow_id}"]
    )
    return AdminActionResponseSchema(
        status=STD_JSON.SUCCESS, message=ADMIN_ACTION_STRINGS.METRIC_FLOW_DELETED
    ).to_response()
