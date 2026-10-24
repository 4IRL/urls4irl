"""Structural (lenient) validation and serialization for custom metric flows.

Stored or submitted JSON hydrates into the ``Lenient*`` models without ever
consulting the event/dimension registries, so a saved flow that names an event
removed later still loads. Errors carry dotted, 0-based paths
(``steps.1.dim_filter.0``) and short UI-oriented messages.
"""

import unicodedata
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError

from backend.api_common.request_errors import (
    humanize_error_message,
    max_length_message,
    min_length_message,
)
from backend.metrics.flow_limits import FLOW_LIMITS
from backend.metrics.flows import FlowDefinition
from backend.utils.strings.json_strs import FIELD_REQUIRED_STR
from backend.utils.strings.metric_flow_strs import (
    CHOOSE_STEP_TYPE_STR,
    FILTER_FORMAT_STR,
    NAME_CHARACTERS_STR,
    UNEXPECTED_FIELD_STR,
    WRONG_TYPE_LIST_STR,
    WRONG_TYPE_OBJECT_STR,
    WRONG_TYPE_TEXT_STR,
    filters_too_many_message,
    steps_too_few_message,
    steps_too_many_message,
)

__all__ = [
    "LenientFlowDefinition",
    "LenientFlowStep",
    "LenientFlowStepBreakdown",
    "flow_errors_from_validation_error",
    "serialize_flow_steps",
]

_VALUE_ERROR_PREFIX = "Value error, "
_ROOT_KEY = "__root__"
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


def _filters_to_strings(filters: object) -> object:
    if not isinstance(filters, list):
        return filters
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
