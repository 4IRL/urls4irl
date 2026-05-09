from __future__ import annotations

from enum import IntEnum


class MetricsErrorCodes(IntEnum):
    # Value 1 mirrors `ContactErrorCodes.INVALID_FORM_INPUT` in
    # `backend/contact/constants.py`. `UTubErrorCodes` uses a different
    # numbering scheme (value 2 for `INVALID_FORM_INPUT`); that inconsistency
    # is pre-existing across the codebase and not introduced here.
    INVALID_FORM_INPUT = 1


class MetricsFailureMessages:
    UNABLE_TO_RECORD_METRICS = "Unable to record metrics."
    MISSING_CSRF = "Missing CSRF token."
    METRICS_RECORDED = "Metrics recorded."
