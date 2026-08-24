from enum import IntEnum

# Closed set of values for the `has_results` dimension on the
# MEMBER_ADD_CANDIDATES_LOADED metric event. Defined once here so the metrics
# registry tuple and the Pydantic `Literal` derive from a single source of
# truth (mirrors SEARCH_FIELD_ORDER_VALUES).
MEMBER_ADD_HAS_RESULTS_VALUES: tuple[str, ...] = ("true", "false")


class UTubMembersErrorCodes(IntEnum):
    UNKNOWN_EXCEPTION = 1
    INVALID_FORM_INPUT = 2
    UTUB_IS_LOCKED = 3
