from enum import IntEnum, StrEnum

# Closed set of values for the `has_results` dimension on the
# MEMBER_ADD_CANDIDATES_LOADED metric event. Defined once here so the metrics
# registry tuple and the Pydantic `Literal` derive from a single source of
# truth (mirrors SEARCH_FIELD_ORDER_VALUES).
MEMBER_ADD_HAS_RESULTS_VALUES: tuple[str, ...] = ("true", "false")

# Closed set of values for the `source` dimension on the MEMBER_ADDED metric
# event. Defined once here so the metrics registry tuple and the Pydantic
# `Literal` derive from a single source of truth (mirrors
# MEMBER_ADD_HAS_RESULTS_VALUES). `search_result` = added by picking a co-member
# from the typeahead combobox; `exact_username` = added by the exact-username
# outsider path (also the default when the client omits the field).
MEMBER_ADD_SOURCE_VALUES: tuple[str, ...] = ("search_result", "exact_username")

# Closed set of values for the `new_role` dimension on the MEMBER_ROLE_CHANGED
# metric event, and the request-body target role for the grant/revoke endpoint.
# Defined once here so the metrics registry tuple and the Pydantic `Literal`
# derive from a single source of truth (mirrors MEMBER_ADD_SOURCE_VALUES). The
# strings MUST equal `Member_Role.CO_CREATOR.value` / `Member_Role.MEMBER.value`
# — `cocreator` promotes a plain member to co-owner; `member` revokes co-owner.
MEMBER_ROLE_CHANGE_VALUES: tuple[str, ...] = ("cocreator", "member")

# Per-IP Flask-Limiter cap on the add-member route (web + /api/v1 twin).
# Batch-friendly: adding a batch of chips fires one POST per chip, so the cap
# must exceed realistic batch sizes while still bounding burst abuse.
MEMBER_ADD_RATE_LIMIT: str = "30/minute"

# Per-user fail-open Redis daily cap on add-member attempts (the username
# oracle). Every attempt reaching the exact-username lookup burns a slot
# regardless of its outcome, so repeated enumeration probing is bounded.
MEMBER_ADD_DAILY_CAP: int = 100


class MemberAddSource(StrEnum):
    SEARCH_RESULT = "search_result"
    EXACT_USERNAME = "exact_username"


class MemberRoleTarget(StrEnum):
    """Target role carried by the grant/revoke co-owner endpoint's request body.

    ``CO_CREATOR`` promotes a plain member to co-owner; ``MEMBER`` revokes the
    co-owner role. The values MUST equal ``Member_Role.CO_CREATOR.value`` /
    ``Member_Role.MEMBER.value`` (mirrors ``MemberAddSource``).
    """

    CO_CREATOR = "cocreator"
    MEMBER = "member"


class UTubMembersErrorCodes(IntEnum):
    UNKNOWN_EXCEPTION = 1
    INVALID_FORM_INPUT = 2
    UTUB_IS_LOCKED = 3
    CANNOT_MODIFY_OWNER = 4
    TARGET_NOT_A_MEMBER = 5
    TARGET_ALREADY_OWNER = 6
