"""Service layer for the admin custom metric flow endpoints (list and create)."""

from __future__ import annotations

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError

from backend import db
from backend.admin.constants import METRIC_FLOW_CAP_LOCK_KEY, AdminActionErrorCodes
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs
from backend.extensions.audit.record import record
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
)
from backend.models.metric_flows import DISPLAY_NAME_LOWER_INDEX, Metric_Flows
from backend.schemas.errors import build_field_error_response
from backend.schemas.metrics import MetricFlowEntrySchema, MetricFlowListResponseSchema
from backend.utils.strings.admin_portal_strs import (
    ADMIN_ACTION_STRINGS,
    ADMIN_AUDIT_ACTIONS,
)

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


def _is_display_name_taken(*, display_name: str) -> bool:
    """True when a built-in or saved flow already uses this name, ignoring case.

    Built-ins are compared with Python ``str.lower()`` and saved flows with
    Postgres ``lower()`` on purpose: the latter is exactly what the unique index
    uses, so the pre-check and the backstop agree.
    """
    lowered_name = display_name.lower()
    if any(
        built_in.display_name.strip().lower() == lowered_name
        for built_in in FLOWS.values()
    ):
        return True
    return (
        db.session.query(Metric_Flows.id)
        .filter(func.lower(Metric_Flows.display_name) == func.lower(display_name))
        .first()
        is not None
    )


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
