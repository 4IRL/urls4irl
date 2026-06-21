from __future__ import annotations

import logging

import pytest
from flask import Flask

from backend.extensions.metrics.writer import validate_latency_cap_overrides
from tests.utils_for_test import is_string_in_logs

pytestmark = pytest.mark.cli

_OVERRIDES_ATTR = "backend.extensions.metrics.writer.LATENCY_SAMPLE_CAP_OVERRIDES"
_UNKNOWN_ENDPOINT = "bogus.not_a_real_endpoint"
_WARNING_NEEDLE = (
    "latency_sample_cap_override_unknown_endpoint: bogus.not_a_real_endpoint"
)


def test_validate_latency_cap_overrides_warns_on_unknown_endpoint(
    app: Flask,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    GIVEN LATENCY_SAMPLE_CAP_OVERRIDES contains a key not present in url_map
    WHEN validate_latency_cap_overrides runs against the built app
    THEN a specific WARNING naming the unknown endpoint is logged.
    """
    monkeypatch.setattr(_OVERRIDES_ATTR, {_UNKNOWN_ENDPOINT: 1000})

    caplog.set_level(logging.WARNING)
    validate_latency_cap_overrides(app)

    assert is_string_in_logs(_WARNING_NEEDLE, caplog.records)


def test_validate_latency_cap_overrides_silent_for_known_endpoint(
    app: Flask,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    GIVEN every LATENCY_SAMPLE_CAP_OVERRIDES key is a real url_map endpoint
    WHEN validate_latency_cap_overrides runs against the built app
    THEN no unknown-endpoint warning is logged.
    """
    known_endpoint = next(iter(app.url_map.iter_rules())).endpoint
    monkeypatch.setattr(_OVERRIDES_ATTR, {known_endpoint: 1000})

    caplog.set_level(logging.WARNING)
    validate_latency_cap_overrides(app)

    assert not is_string_in_logs(
        "latency_sample_cap_override_unknown_endpoint", caplog.records
    )
