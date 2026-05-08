import pytest

from backend.utils.strings.metrics_strs import METRICS_REDIS

pytestmark = pytest.mark.unit


def test_metrics_strings_present():
    """Reserved Redis key prefixes for metrics match the documented values."""
    assert METRICS_REDIS.COUNTER_KEY_PREFIX == "metrics:counter:"
    assert METRICS_REDIS.BATCH_KEY_PREFIX == "metrics:batch:"
