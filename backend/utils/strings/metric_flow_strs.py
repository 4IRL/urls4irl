"""Backend-only validation messages for custom metric flows.

TypeScript never reads these (the browser shows whatever the server returns),
so there is no bridge to ``APP_CONFIG.strings``.
"""

from backend.metrics.flow_limits import FLOW_LIMITS

NAME_CHARACTERS_STR = "Use letters, numbers and punctuation only."
FILTER_FORMAT_STR = "Enter a filter as field:value."

WRONG_TYPE_TEXT_STR = "Enter text."
WRONG_TYPE_LIST_STR = "Enter a list of items."
WRONG_TYPE_OBJECT_STR = "Enter an object."
CHOOSE_STEP_TYPE_STR = "Choose a step type."
UNEXPECTED_FIELD_STR = "Unexpected field."


def steps_too_few_message() -> str:
    return f"Add at least {FLOW_LIMITS.MIN_STEPS} steps."


def steps_too_many_message() -> str:
    return f"Use at most {FLOW_LIMITS.MAX_STEPS} steps."


def filters_too_many_message() -> str:
    return f"Use at most {FLOW_LIMITS.MAX_FILTERS} filters."
