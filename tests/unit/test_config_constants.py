import pytest

from backend.extensions.url_validation.constants import (
    TRACKING_QUERY_PARAM_PREFIXES,
    TRACKING_QUERY_PARAMS,
    WEB_SCHEMES_FOR_TRACKING_STRIP,
)
from backend.metrics.dimension_models import get_all_dimension_keys
from backend.metrics.events import DeviceType
from backend.utils.constants import generate_constants_js
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
        assert hasattr(CONFIG_ENVS, metrics_key), (
            f"CONFIG_ENVS is missing metrics key: {metrics_key}"
        )
        assert getattr(CONFIG_ENVS, metrics_key) == metrics_key


def test_generate_constants_js_includes_dimension_keys():
    constants = generate_constants_js()
    assert constants["DIMENSION_KEYS"] == list(get_all_dimension_keys())


def test_generate_constants_js_includes_tracking_blocklist():
    """The client blocklist mirrors the server's, so a blocklist edit cannot desync it."""
    constants = generate_constants_js()
    assert set(constants["TRACKING_QUERY_PARAMS"]) == TRACKING_QUERY_PARAMS
    assert constants["TRACKING_QUERY_PARAMS"] == sorted(TRACKING_QUERY_PARAMS)
    assert constants["TRACKING_QUERY_PARAM_PREFIXES"] == list(
        TRACKING_QUERY_PARAM_PREFIXES
    )
    assert set(constants["TRACKING_STRIP_SCHEMES"]) == WEB_SCHEMES_FOR_TRACKING_STRIP


def test_generate_constants_js_device_type_shape():
    """`generate_constants_js()["DEVICE_TYPE"]` mirrors the `DeviceType` enum exactly.

    Any renumbering of `DeviceType` or change to the dict comprehension in
    `constants.py` trips this test, preventing silent divergence from the
    `test-setup.ts` mock (which hardcodes `{MOBILE: 1, DESKTOP: 2}`).
    """
    constants = generate_constants_js()
    assert constants["DEVICE_TYPE"] == {
        member.name: member.value for member in DeviceType
    }
