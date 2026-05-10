import pytest

from backend.utils.strings.config_strs import CONFIG_ENVS

pytestmark = pytest.mark.unit


def test_metrics_config_envs_exist():
    """Every metrics-related env-name constant is registered on CONFIG_ENVS."""
    expected_metrics_keys = (
        "METRICS_ENABLED",
        "METRICS_FLUSH_INTERVAL_SECONDS",
        "METRICS_BUCKET_SECONDS",
        "METRICS_REDIS_URI",
        "METRICS_BATCH_NONCE_TTL_SECONDS",
    )
    for metrics_key in expected_metrics_keys:
        assert hasattr(
            CONFIG_ENVS, metrics_key
        ), f"CONFIG_ENVS is missing metrics key: {metrics_key}"
        assert getattr(CONFIG_ENVS, metrics_key) == metrics_key
