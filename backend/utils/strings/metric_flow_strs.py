"""Backend-only validation messages for custom metric flows.

TypeScript never reads these (the browser shows whatever the server returns),
so there is no bridge to ``APP_CONFIG.strings``.
"""

from collections.abc import Sequence

from backend.metrics.flow_limits import FLOW_LIMITS

NAME_CHARACTERS_STR = "Use letters, numbers and punctuation only."
FILTER_FORMAT_STR = "Enter a filter as field:value."

WRONG_TYPE_TEXT_STR = "Enter text."
WRONG_TYPE_LIST_STR = "Enter a list of items."
WRONG_TYPE_OBJECT_STR = "Enter an object."
CHOOSE_STEP_TYPE_STR = "Choose a step type."
UNEXPECTED_FIELD_STR = "Unexpected field."
FLOW_INVALID_UNKNOWN_STR = "This funnel needs attention."


# Registry (semantic) messages.
EVENT_REQUIRED_STR = "Choose an event."
API_STEP_NO_EVENT_STR = "API steps do not use an event."
ENDPOINT_REQUIRED_STR = "Choose an endpoint."
METHOD_REQUIRED_STR = "Choose a method."
ENDPOINT_ONLY_API_STR = "Only API steps use an endpoint."
METHOD_ONLY_API_STR = "Only API steps use a method."
BAD_FILTER_VALUE_STR = "Choose a value from the list."
CANNOT_FILTER_STR = "This field cannot be used as a filter."
BAD_STATUS_CODE_STR = "Use a status code like 200."


def echo_input(value: str) -> str:
    """Show user input `repr`-style, cut to 255 characters first (then `...`)."""
    shown = value
    if len(shown) > FLOW_LIMITS.IDENTIFIER_MAX_LENGTH:
        shown = shown[: FLOW_LIMITS.IDENTIFIER_MAX_LENGTH] + "..."
    return repr(shown)


def unknown_event_message(*, value: str) -> str:
    return f"Event {echo_input(value)} does not exist."


def wrong_category_message(*, stream: str) -> str:
    return f"Choose an event that fits a {stream} step."


def unknown_endpoint_message(*, value: str) -> str:
    return f"Endpoint {echo_input(value)} was not found."


def method_not_allowed_message(*, allowed: list[str]) -> str:
    return f"Use one of: {', '.join(allowed)}."


def unknown_field_message(*, value: str) -> str:
    return f"Field {echo_input(value)} does not exist for this event."


def group_by_not_available_message(*, group_by: str, allowed: Sequence[str]) -> str:
    if not allowed:
        return "This event cannot be broken down."
    allowed_text = ", ".join(f'"{name}"' for name in allowed)
    shown = group_by
    if len(shown) > FLOW_LIMITS.IDENTIFIER_MAX_LENGTH:
        shown = shown[: FLOW_LIMITS.IDENTIFIER_MAX_LENGTH] + "..."
    return (
        f'Cannot break down this event by "{shown}". '
        f"Allowed: {allowed_text}. Choose one or remove the breakdown."
    )


def duplicate_filter_message(*, dim_key: str) -> str:
    return f'Only one filter per field; "{dim_key}" is already used.'


def steps_too_few_message() -> str:
    return f"Add at least {FLOW_LIMITS.MIN_STEPS} steps."


def steps_too_many_message() -> str:
    return f"Use at most {FLOW_LIMITS.MAX_STEPS} steps."


def filters_too_many_message() -> str:
    return f"Use at most {FLOW_LIMITS.MAX_FILTERS} filters."
