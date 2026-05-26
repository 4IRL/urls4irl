from __future__ import annotations

from enum import IntEnum


class MetricsErrorCodes(IntEnum):
    INVALID_FORM_INPUT = 1


class MetricsFailureMessages:
    UNABLE_TO_RECORD_METRICS = "Unable to record metrics."
    METRICS_RECORDED = "Metrics recorded."
