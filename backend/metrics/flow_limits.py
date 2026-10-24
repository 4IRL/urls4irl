"""Single source of truth for custom metric-flow limits.

Backend validators read ``FLOW_LIMITS``; the browser reads the same numbers
through ``FLOW_LIMITS_FOR_FRONTEND`` -> ``generate_constants_js()`` ->
``APP_CONFIG.constants``. ``flow_limit_keys.json`` mirrors the frontend dict so
tests on both sides can detect drift.
"""

BRIDGE_KEY_PREFIX = "METRIC_FLOWS_"


class FLOW_LIMITS:
    MIN_STEPS: int = 2
    MAX_STEPS: int = 8
    MAX_FILTERS: int = 5
    NAME_MIN_LENGTH: int = 1
    NAME_MAX_LENGTH: int = 64
    LABEL_MIN_LENGTH: int = 1
    LABEL_MAX_LENGTH: int = 64
    FILTER_VALUE_MAX_LENGTH: int = 255
    # Enforced by the create-flow service, not by the validators.
    MAX_CUSTOM: int = 20
    # Backend-only: event/endpoint/method/dim identifiers. Not bridged to the frontend.
    IDENTIFIER_MAX_LENGTH: int = 255


FLOW_LIMITS_FOR_FRONTEND: dict[str, int] = {
    f"{BRIDGE_KEY_PREFIX}MIN_STEPS": FLOW_LIMITS.MIN_STEPS,
    f"{BRIDGE_KEY_PREFIX}MAX_STEPS": FLOW_LIMITS.MAX_STEPS,
    f"{BRIDGE_KEY_PREFIX}MAX_FILTERS": FLOW_LIMITS.MAX_FILTERS,
    f"{BRIDGE_KEY_PREFIX}NAME_MIN_LENGTH": FLOW_LIMITS.NAME_MIN_LENGTH,
    f"{BRIDGE_KEY_PREFIX}NAME_MAX_LENGTH": FLOW_LIMITS.NAME_MAX_LENGTH,
    f"{BRIDGE_KEY_PREFIX}LABEL_MIN_LENGTH": FLOW_LIMITS.LABEL_MIN_LENGTH,
    f"{BRIDGE_KEY_PREFIX}LABEL_MAX_LENGTH": FLOW_LIMITS.LABEL_MAX_LENGTH,
    f"{BRIDGE_KEY_PREFIX}FILTER_VALUE_MAX_LENGTH": FLOW_LIMITS.FILTER_VALUE_MAX_LENGTH,
    f"{BRIDGE_KEY_PREFIX}MAX_CUSTOM": FLOW_LIMITS.MAX_CUSTOM,
}
