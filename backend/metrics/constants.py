from __future__ import annotations

from enum import IntEnum


class MetricsErrorCodes(IntEnum):
    INVALID_FORM_INPUT = 1
    INVALID_QUERY_PARAM = 2


class MetricsFailureMessages:
    UNABLE_TO_RECORD_METRICS = "Unable to record metrics."
    METRICS_RECORDED = "Metrics recorded."
    UNABLE_TO_QUERY_METRICS = "Unable to query metrics."
    INVALID_WINDOW = "Invalid window."
    INVALID_QUERY = "Invalid query parameters."
