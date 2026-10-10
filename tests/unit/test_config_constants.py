import json

import pytest

from backend.extensions.url_validation.constants import (
    AUTHORITY_URL_SCHEMES,
    CORE_SCHEMES,
    DEV_URLS,
    OTHER_VALID_SCHEMES,
    TRACKING_QUERY_PARAM_PREFIXES,
    TRACKING_QUERY_PARAMS,
    WEB_SCHEMES_FOR_TRACKING_STRIP,
)
from backend.metrics.dimension_models import get_all_dimension_keys
from backend.metrics.events import DeviceType
from backend.utils.constants import generate_constants_js, generate_strings_js
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


def test_generate_constants_js_includes_url_scheme_whitelist():
    """The scheme selector's options are the backend whitelist, deterministically ordered."""
    constants = generate_constants_js()
    whitelist = CORE_SCHEMES | OTHER_VALID_SCHEMES
    url_schemes = constants["URL_SCHEMES"]

    assert isinstance(url_schemes, list)
    assert all(isinstance(scheme, str) for scheme in url_schemes)
    assert len(url_schemes) == len(whitelist)
    assert set(url_schemes) == whitelist
    assert len(set(url_schemes)) == len(url_schemes)
    assert url_schemes[:2] == ["https", "http"]
    assert constants["URL_DEFAULT_SCHEME"] == "https"


def test_generate_constants_js_url_scheme_order_is_deterministic():
    first = json.dumps(generate_constants_js()["URL_SCHEMES"], sort_keys=False)
    second = json.dumps(generate_constants_js()["URL_SCHEMES"], sort_keys=False)
    assert first == second


def test_generate_constants_js_includes_url_authority_schemes():
    constants = generate_constants_js()
    whitelist = CORE_SCHEMES | OTHER_VALID_SCHEMES
    assert set(constants["URL_AUTHORITY_SCHEMES"]) == AUTHORITY_URL_SCHEMES
    assert set(constants["URL_AUTHORITY_SCHEMES"]) <= whitelist


def test_generate_constants_js_includes_url_dev_hosts():
    constants = generate_constants_js()
    assert constants["URL_DEV_HOSTS"] == list(DEV_URLS)


def test_generate_constants_js_url_scheme_hints_shape():
    constants = generate_constants_js()
    whitelist = CORE_SCHEMES | OTHER_VALID_SCHEMES
    hints = constants["URL_SCHEME_HINTS"]

    assert isinstance(hints, dict)
    assert hints
    assert set(hints) <= whitelist
    assert all(isinstance(hint, str) and hint for hint in hints.values())


def test_generate_strings_js_includes_url_scheme_selector_strings():
    """Every selector label is read by TS (the selector DOM is built in JS), so all are bridged."""
    strings = generate_strings_js()
    expected_keys = (
        "URL_SCHEME_TOGGLE_LABEL",
        "URL_SCHEME_FILTER_LABEL",
        "URL_SCHEME_NO_MATCHES",
        "URL_SCHEME_MATCH_ONE",
        "URL_SCHEME_MATCH_MANY",
        "URL_SCHEME_SET_ANNOUNCE",
    )
    for key in expected_keys:
        assert key in strings, f"generate_strings_js() is missing {key}"
        assert strings[key]

    assert "{count}" in strings["URL_SCHEME_MATCH_MANY"]
    assert "{scheme}" in strings["URL_SCHEME_SET_ANNOUNCE"]


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
