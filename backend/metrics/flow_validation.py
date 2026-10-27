"""Structural (lenient) validation and serialization for custom metric flows.

Stored or submitted JSON hydrates into the ``Lenient*`` models without ever
consulting the event/dimension registries, so a saved flow that names an event
removed later still loads. Errors carry dotted, 0-based paths
(``steps.1.dim_filter.0``) and short UI-oriented messages.
"""

import re
import unicodedata
from typing import Annotated, Literal

from flask import current_app
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError

from backend.api_common.request_errors import (
    humanize_error_message,
    max_length_message,
    min_length_message,
)
from backend.extensions.metrics.middleware import API_HIT_COUNTED_METHODS, should_skip
from backend.metrics.event_registry import EVENT_REGISTRY
from backend.metrics.events import (
    DEVICE_TYPE_DIM_KEY,
    EVENT_CATEGORY,
    DeviceType,
    EventCategory,
    EventName,
)
from backend.metrics.flow_limits import FLOW_LIMITS
from backend.metrics.flows import FlowDefinition, FlowStep, FlowStepBreakdown
from backend.metrics.query_service import validate_dim_keys
from backend.utils.strings.json_strs import FIELD_REQUIRED_STR
from backend.utils.strings.metric_flow_strs import (
    API_STEP_NO_EVENT_STR,
    BAD_FILTER_VALUE_STR,
    BAD_STATUS_CODE_STR,
    CANNOT_FILTER_STR,
    CHOOSE_STEP_TYPE_STR,
    ENDPOINT_ONLY_API_STR,
    ENDPOINT_REQUIRED_STR,
    EVENT_REQUIRED_STR,
    FILTER_FORMAT_STR,
    METHOD_ONLY_API_STR,
    METHOD_REQUIRED_STR,
    NAME_CHARACTERS_STR,
    UNEXPECTED_FIELD_STR,
    WRONG_TYPE_LIST_STR,
    WRONG_TYPE_OBJECT_STR,
    WRONG_TYPE_TEXT_STR,
    duplicate_filter_message,
    filters_too_many_message,
    method_not_allowed_message,
    steps_too_few_message,
    steps_too_many_message,
    unknown_endpoint_message,
    unknown_event_message,
    unknown_field_message,
    wrong_category_message,
)

__all__ = [
    "LenientFlowDefinition",
    "LenientFlowStep",
    "LenientFlowStepBreakdown",
    "allowed_methods_by_endpoint",
    "flow_errors_from_validation_error",
    "inspect_flow_payload",
    "serialize_flow_steps",
    "validate_flow_definition",
    "validate_flow_payload",
]

_VALUE_ERROR_PREFIX = "Value error, "
_ROOT_KEY = "__root__"
_STATUS_CODE_KEY = "status_code"
_DEVICE_TYPE_VALUES = frozenset(str(member.value) for member in DeviceType)
# Exactly three ASCII digits; `fullmatch` so a trailing newline is not accepted.
_STATUS_CODE_PATTERN = re.compile(r"[0-9]{3}")
_STATUS_CODE_MIN = 100
_STATUS_CODE_MAX = 599
# Int-castable placeholder so `validate_dim_keys` acts as a pure key check.
_PROBE_VALUE = "1"
# Unicode categories rejected inside a trimmed name/label: control, line sep, paragraph sep.
_REJECTED_CATEGORIES = frozenset({"Cc", "Zl", "Zp"})


def _clean_text(*, value: str, min_length: int, max_length: int) -> str:
    """Trim, then reject empty, control/separator characters and over-long text."""
    stripped = value.strip()
    if not stripped:
        raise ValueError(FIELD_REQUIRED_STR)
    if any(unicodedata.category(char) in _REJECTED_CATEGORIES for char in stripped):
        raise ValueError(NAME_CHARACTERS_STR)
    if len(stripped) < min_length:
        raise ValueError(min_length_message(min_length))
    if len(stripped) > max_length:
        raise ValueError(max_length_message(max_length))
    return stripped


def _clean_display_name(value: str) -> str:
    return _clean_text(
        value=value,
        min_length=FLOW_LIMITS.NAME_MIN_LENGTH,
        max_length=FLOW_LIMITS.NAME_MAX_LENGTH,
    )


def _clean_label(value: str) -> str:
    return _clean_text(
        value=value,
        min_length=FLOW_LIMITS.LABEL_MIN_LENGTH,
        max_length=FLOW_LIMITS.LABEL_MAX_LENGTH,
    )


def _check_filter_entry(value: str) -> str:
    """Check one ``'dim:value'`` entry; split on the first colon."""
    dim_key, separator, dim_value = value.partition(":")
    if not separator or not dim_key or not dim_value:
        raise ValueError(FILTER_FORMAT_STR)
    if len(dim_key) > FLOW_LIMITS.IDENTIFIER_MAX_LENGTH:
        raise ValueError(max_length_message(FLOW_LIMITS.IDENTIFIER_MAX_LENGTH))
    if len(dim_value) > FLOW_LIMITS.FILTER_VALUE_MAX_LENGTH:
        raise ValueError(max_length_message(FLOW_LIMITS.FILTER_VALUE_MAX_LENGTH))
    return value


_FilterEntry = Annotated[str, AfterValidator(_check_filter_entry)]
_DisplayName = Annotated[str, AfterValidator(_clean_display_name)]
_Label = Annotated[str, AfterValidator(_clean_label)]
_Identifier = Annotated[str, Field(max_length=FLOW_LIMITS.IDENTIFIER_MAX_LENGTH)]


class LenientFlowStepBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_name: _Identifier
    dim_filter: list[_FilterEntry] | None = Field(
        default=None, max_length=FLOW_LIMITS.MAX_FILTERS
    )
    group_by: _Identifier


class LenientFlowStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stream: Literal["ui", "api", "domain"]
    label: _Label
    event_name: _Identifier | None = None
    api_endpoint: _Identifier | None = None
    api_method: _Identifier | None = None
    dim_filter: list[_FilterEntry] | None = Field(
        default=None, max_length=FLOW_LIMITS.MAX_FILTERS
    )
    drop_breakdown: LenientFlowStepBreakdown | None = None


class LenientFlowDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: _DisplayName
    steps: list[LenientFlowStep] = Field(
        min_length=FLOW_LIMITS.MIN_STEPS, max_length=FLOW_LIMITS.MAX_STEPS
    )


_TYPE_MESSAGES: dict[str, str] = {
    "string_type": WRONG_TYPE_TEXT_STR,
    "list_type": WRONG_TYPE_LIST_STR,
    "missing": FIELD_REQUIRED_STR,
    "literal_error": CHOOSE_STEP_TYPE_STR,
    "model_type": WRONG_TYPE_OBJECT_STR,
    "dict_type": WRONG_TYPE_OBJECT_STR,
    "extra_forbidden": UNEXPECTED_FIELD_STR,
}


def _list_length_message(*, error_type: str, last_segment: str, raw: str) -> str:
    """Item-count message for ``too_short``/``too_long``, picked by the last loc segment."""
    if last_segment == "steps":
        if error_type == "too_short":
            return steps_too_few_message()
        return steps_too_many_message()
    if last_segment == "dim_filter" and error_type == "too_long":
        return filters_too_many_message()
    return humanize_error_message(raw)


def flow_errors_from_validation_error(error: ValidationError) -> dict[str, list[str]]:
    """Map a ``ValidationError`` to ``{dotted.path: [message]}``.

    Unlike ``pydantic_errors_to_dict`` the full ``loc`` is kept, so nested
    errors are addressable per step and per filter entry.
    """
    errors: dict[str, list[str]] = {}
    for item in error.errors(include_url=False):
        loc = item["loc"]
        path = ".".join(str(segment) for segment in loc) if loc else _ROOT_KEY
        error_type = item["type"]
        raw = item["msg"]
        if raw.startswith(_VALUE_ERROR_PREFIX):
            raw = raw[len(_VALUE_ERROR_PREFIX) :]
        if error_type in ("too_short", "too_long"):
            last_segment = str(loc[-1]) if loc else ""
            message = _list_length_message(
                error_type=error_type, last_segment=last_segment, raw=raw
            )
        elif error_type in _TYPE_MESSAGES:
            message = _TYPE_MESSAGES[error_type]
        else:
            message = humanize_error_message(raw)
        errors.setdefault(path, []).append(message)
    return errors


def _add_error(errors: dict[str, list[str]], path: str, message: str) -> None:
    errors.setdefault(path, []).append(message)


def _split_filter(entry: str) -> tuple[str, str]:
    """Split a hydrated ``'dim:value'`` entry on its first colon."""
    dim_key, _, dim_value = entry.partition(":")
    return dim_key, dim_value


def _event_or_none(value: str) -> EventName | None:
    try:
        return EventName(value)
    except ValueError:
        return None


def allowed_methods_by_endpoint() -> dict[str, list[str]]:
    """Map each endpoint API_HIT records to the sorted methods it records.

    Applies the middleware's own skip predicate and counted-method set, the same
    walk ``_count_auto_counted_api_routes`` uses.
    """
    methods_by_endpoint: dict[str, set[str]] = {}
    for rule in current_app.url_map.iter_rules():
        if rule.methods is None:
            continue
        if current_app.view_functions.get(rule.endpoint) is None:
            continue
        # Correct while blueprints are not nested.
        blueprint_name = (
            rule.endpoint.rsplit(".", 1)[0] if "." in rule.endpoint else None
        )
        if should_skip(rule.endpoint, blueprint_name):
            continue
        counted = set(rule.methods) & API_HIT_COUNTED_METHODS
        if counted:
            methods_by_endpoint.setdefault(rule.endpoint, set()).update(counted)
    return {
        endpoint: sorted(methods) for endpoint, methods in methods_by_endpoint.items()
    }


def _is_canonical_status_code(value: str) -> bool:
    """Exactly three ASCII digits within 100-599 (no sign, space, underscore)."""
    if not _STATUS_CODE_PATTERN.fullmatch(value):
        return False
    return _STATUS_CODE_MIN <= int(value) <= _STATUS_CODE_MAX


def _is_known_key(*, event: EventName, dim_key: str) -> bool:
    """Pass/fail key check via ``validate_dim_keys`` (probe value is int-castable)."""
    try:
        validate_dim_keys(
            event_name=event, dim_filter=[(dim_key, _PROBE_VALUE)], group_by=None
        )
    except ValueError:
        return False
    return True


def _filter_value_message(
    *, event: EventName, dim_key: str, dim_value: str
) -> str | None:
    """Return the error message for a filter on a known key, or None when valid."""
    if EVENT_CATEGORY[event] is EventCategory.API:
        if dim_key == _STATUS_CODE_KEY:
            return None if _is_canonical_status_code(dim_value) else BAD_STATUS_CODE_STR
        return CANNOT_FILTER_STR
    if dim_key == DEVICE_TYPE_DIM_KEY:
        return None if dim_value in _DEVICE_TYPE_VALUES else BAD_FILTER_VALUE_STR
    closed_set = EVENT_REGISTRY[event].dimensions.get(dim_key)
    if not closed_set:
        return CANNOT_FILTER_STR
    return None if dim_value in closed_set else BAD_FILTER_VALUE_STR


def _check_filters(
    *,
    errors: dict[str, list[str]],
    path: str,
    event: EventName,
    entries: list[str] | None,
) -> None:
    """Check each ``'dim:value'`` entry against one resolved event."""
    seen_keys: set[str] = set()
    for index, entry in enumerate(entries or []):
        entry_path = f"{path}.{index}"
        dim_key, dim_value = _split_filter(entry)
        if not _is_known_key(event=event, dim_key=dim_key):
            _add_error(errors, entry_path, unknown_field_message(value=dim_key))
            continue
        if dim_key in seen_keys:
            _add_error(errors, entry_path, duplicate_filter_message(dim_key=dim_key))
            continue
        seen_keys.add(dim_key)
        message = _filter_value_message(
            event=event, dim_key=dim_key, dim_value=dim_value
        )
        if message is not None:
            _add_error(errors, entry_path, message)


def _check_group_by(
    *, errors: dict[str, list[str]], path: str, event: EventName, group_by: str
) -> None:
    try:
        validate_dim_keys(event_name=event, dim_filter=[], group_by=group_by)
    except ValueError:
        _add_error(errors, path, unknown_field_message(value=group_by))


def _check_breakdown(
    *,
    errors: dict[str, list[str]],
    path: str,
    breakdown: LenientFlowStepBreakdown,
) -> None:
    event = _event_or_none(breakdown.event_name)
    if event is None:
        _add_error(
            errors,
            f"{path}.event_name",
            unknown_event_message(value=breakdown.event_name),
        )
        return
    _check_filters(
        errors=errors,
        path=f"{path}.dim_filter",
        event=event,
        entries=breakdown.dim_filter,
    )
    _check_group_by(
        errors=errors, path=f"{path}.group_by", event=event, group_by=breakdown.group_by
    )


def _check_api_step(
    *,
    errors: dict[str, list[str]],
    path: str,
    step: LenientFlowStep,
    methods_by_endpoint: dict[str, list[str]],
) -> None:
    if step.event_name is not None:
        _add_error(errors, f"{path}.event_name", API_STEP_NO_EVENT_STR)
    if step.api_endpoint is None:
        _add_error(errors, f"{path}.api_endpoint", ENDPOINT_REQUIRED_STR)
    if step.api_method is None:
        _add_error(errors, f"{path}.api_method", METHOD_REQUIRED_STR)
    if step.api_endpoint is not None:
        allowed = methods_by_endpoint.get(step.api_endpoint)
        if allowed is None:
            _add_error(
                errors,
                f"{path}.api_endpoint",
                unknown_endpoint_message(value=step.api_endpoint),
            )
        elif step.api_method is not None and step.api_method not in allowed:
            _add_error(
                errors,
                f"{path}.api_method",
                method_not_allowed_message(allowed=allowed),
            )
    _check_filters(
        errors=errors,
        path=f"{path}.dim_filter",
        event=EventName.API_HIT,
        entries=step.dim_filter,
    )


def _check_event_step(
    *, errors: dict[str, list[str]], path: str, step: LenientFlowStep
) -> None:
    # Intentional fail-closed backstop: unreachable today, but denies any future stream value.
    if step.stream not in ("ui", "domain"):
        _add_error(errors, f"{path}.stream", CHOOSE_STEP_TYPE_STR)
        return
    if step.api_endpoint is not None:
        _add_error(errors, f"{path}.api_endpoint", ENDPOINT_ONLY_API_STR)
    if step.api_method is not None:
        _add_error(errors, f"{path}.api_method", METHOD_ONLY_API_STR)
    if step.event_name is None:
        _add_error(errors, f"{path}.event_name", EVENT_REQUIRED_STR)
        return
    event = _event_or_none(step.event_name)
    if event is None:
        _add_error(
            errors, f"{path}.event_name", unknown_event_message(value=step.event_name)
        )
        return
    if EVENT_CATEGORY[event].value != step.stream:
        _add_error(
            errors, f"{path}.event_name", wrong_category_message(stream=step.stream)
        )
        return
    _check_filters(
        errors=errors,
        path=f"{path}.dim_filter",
        event=event,
        entries=step.dim_filter,
    )


def _build_definition(draft: LenientFlowDefinition) -> FlowDefinition:
    """Build the enum-typed definition; only called when no registry error exists."""
    steps: list[FlowStep] = []
    for step in draft.steps:
        breakdown: FlowStepBreakdown | None = None
        if step.drop_breakdown is not None:
            breakdown = FlowStepBreakdown(
                event_name=EventName(step.drop_breakdown.event_name),
                dim_filter=_tuples_or_none(step.drop_breakdown.dim_filter),
                group_by=step.drop_breakdown.group_by,
            )
        steps.append(
            FlowStep(
                stream=step.stream,
                label=step.label,
                event_name=(
                    EventName(step.event_name) if step.event_name is not None else None
                ),
                api_endpoint=step.api_endpoint,
                api_method=step.api_method,
                dim_filter=_tuples_or_none(step.dim_filter),
                drop_breakdown=breakdown,
            )
        )
    return FlowDefinition(display_name=draft.display_name, steps=steps)


def _tuples_or_none(entries: list[str] | None) -> list[tuple[str, str]] | None:
    if not entries:
        return None
    return [_split_filter(entry) for entry in entries]


def validate_flow_definition(
    draft: LenientFlowDefinition,
) -> FlowDefinition | dict[str, list[str]]:
    """Check a hydrated draft against the live registries.

    Collects every registry error in one pass. Returns a non-empty error map or
    a fully built, enum-typed ``FlowDefinition``, never both. Needs an app
    context for ``url_map``.
    """
    errors: dict[str, list[str]] = {}
    methods_by_endpoint = allowed_methods_by_endpoint()
    for index, step in enumerate(draft.steps):
        path = f"steps.{index}"
        if step.stream == "api":
            _check_api_step(
                errors=errors,
                path=path,
                step=step,
                methods_by_endpoint=methods_by_endpoint,
            )
        else:
            _check_event_step(errors=errors, path=path, step=step)
        if step.drop_breakdown is not None:
            _check_breakdown(
                errors=errors,
                path=f"{path}.drop_breakdown",
                breakdown=step.drop_breakdown,
            )
    if errors:
        return errors
    return _build_definition(draft)


def _hydrate_and_validate(
    payload: object,
) -> tuple[LenientFlowDefinition | None, FlowDefinition | dict[str, list[str]]]:
    """Single pass: hydrate, then run the registry layer once."""
    if not isinstance(payload, dict):
        return None, {_ROOT_KEY: [WRONG_TYPE_OBJECT_STR]}
    try:
        draft = LenientFlowDefinition.model_validate(payload)
    except ValidationError as error:
        return None, flow_errors_from_validation_error(error)
    return draft, validate_flow_definition(draft)


def inspect_flow_payload(
    payload: object,
) -> tuple[LenientFlowDefinition | None, dict[str, list[str]]]:
    """Return the hydrated draft (or None) and the merged error map."""
    draft, result = _hydrate_and_validate(payload)
    if isinstance(result, FlowDefinition):
        return draft, {}
    return draft, result


def validate_flow_payload(payload: object) -> FlowDefinition | dict[str, list[str]]:
    """Hydrate then registry-validate a raw payload in one pass."""
    return _hydrate_and_validate(payload)[1]


def _filters_to_strings(filters: list[list[str]]) -> list[str]:
    return [f"{dim_key}:{dim_value}" for dim_key, dim_value in filters]


def serialize_flow_steps(
    definition: FlowDefinition,
) -> dict[str, list[dict[str, object]]]:
    """Return the stored envelope ``{"steps": [...]}``.

    Enum values are plain strings, filters are ``'dim:value'`` strings and
    ``None`` keys are omitted.
    """
    steps: list[dict[str, object]] = []
    for step in definition.steps:
        dumped: dict[str, object] = step.model_dump(mode="json", exclude_none=True)
        if "dim_filter" in dumped:
            dumped["dim_filter"] = _filters_to_strings(dumped["dim_filter"])
        breakdown = dumped.get("drop_breakdown")
        if isinstance(breakdown, dict) and "dim_filter" in breakdown:
            breakdown["dim_filter"] = _filters_to_strings(breakdown["dim_filter"])
        steps.append(dumped)
    return {"steps": steps}
