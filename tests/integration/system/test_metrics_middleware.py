from __future__ import annotations

import json
from unittest import mock

import pytest
from flask import Flask
from flask.testing import FlaskClient
from redis import Redis

from backend import metrics_writer as app_metrics_writer
from backend.metrics.events import EventName
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.metrics_strs import METRICS_REDIS
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.cli


def _api_hit_keys(metrics_redis: Redis) -> list[bytes]:
    pattern = f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*:{EventName.API_HIT.value}:*"
    return list(metrics_redis.scan_iter(match=pattern))


def _parse_dims(counter_key: bytes) -> dict:
    """Extract the trailing canonical-dims JSON segment from a counter key.

    Key shape: `metrics:counter:<bucket>:<event_name>:<canonical_dims_json>`
    The JSON segment is everything after the 4th colon — split with
    `maxsplit=4` so a `:` inside the JSON does not corrupt the parse.
    """
    decoded = counter_key.decode("utf-8")
    parts = decoded.split(":", 4)
    return json.loads(parts[4])


def test_middleware_records_api_hit_for_normal_route(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a Flask app with the metrics after_request middleware installed
    WHEN a normal route is requested (the splash page)
    THEN exactly one api_hit counter key exists, encoding the resolved
        endpoint, method, and status_code in its canonical-dims segment.
    """
    response = client.get("/")
    assert response.status_code == 200

    keys = _api_hit_keys(provide_metrics_redis)
    assert len(keys) == 1
    assert provide_metrics_redis.get(keys[0]) == b"1"

    dims = _parse_dims(keys[0])
    assert dims["endpoint"] == "splash.splash_page"
    assert dims["method"] == "GET"
    assert dims["status_code"] == 200


def test_middleware_skips_static(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN the static endpoint is in the skip set
    WHEN a /static/* path is requested
    THEN no api_hit counter key is recorded.
    """
    client.get("/static/dist/does-not-exist.js")
    assert _api_hit_keys(provide_metrics_redis) == []


def test_middleware_skips_health(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN the system.health endpoint is in the skip set
    WHEN /health is requested
    THEN no api_hit counter key is recorded.
    """
    client.get("/health")
    assert _api_hit_keys(provide_metrics_redis) == []


def test_middleware_skips_metrics_blueprint_self(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN the metrics blueprint is self-skipped to avoid feedback loops
    WHEN POST /api/metrics is invoked with a valid payload
    THEN no api_hit counter key is created (only the per-event keys from dispatch).
    """
    splash_response = client.get("/")
    csrf = get_csrf_token(splash_response.get_data(), meta_tag=True)

    response = client.post(
        "/api/metrics",
        json={
            "events": [
                {
                    "event_name": EventName.UI_URL_COPY.value,
                    "dimensions": {"result": "success"},
                }
            ]
        },
        headers={"X-CSRFToken": csrf},
    )
    assert response.status_code == 200

    api_hit_keys = _api_hit_keys(provide_metrics_redis)
    for key in api_hit_keys:
        dims = _parse_dims(key)
        assert dims.get("endpoint") != "metrics.ingest", (
            "metrics blueprint self-skip failed: "
            f"api_hit recorded for endpoint={dims.get('endpoint')!r}"
        )


def test_middleware_skips_404_unmatched(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a request that does not match any registered route
    WHEN it is served (404)
    THEN no api_hit counter key is recorded (request.endpoint is None).
    """
    response = client.get("/this-does-not-exist-xyz")
    assert response.status_code == 404
    assert _api_hit_keys(provide_metrics_redis) == []


def test_middleware_records_status_code(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a request to a route that returns a non-200 status
    WHEN the middleware records the api_hit
    THEN the recorded dims encode the actual response status code.
    """
    response = client.get("/utubs")
    assert response.status_code != 200

    keys = _api_hit_keys(provide_metrics_redis)
    assert len(keys) == 1
    dims = _parse_dims(keys[0])
    assert dims["status_code"] == response.status_code
    assert dims["method"] == "GET"


def test_middleware_records_post_method(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a POST request to a normal route
    WHEN the middleware records the api_hit
    THEN the recorded dims report method=POST.
    """
    splash_response = client.get("/")
    csrf = get_csrf_token(splash_response.get_data(), meta_tag=True)
    api_hits_before = len(_api_hit_keys(provide_metrics_redis))

    client.post(
        "/login",
        data={"username": "no_such_user", "password": "wrong", "csrf_token": csrf},
        headers={"X-CSRFToken": csrf},
    )

    keys = _api_hit_keys(provide_metrics_redis)
    assert len(keys) > api_hits_before
    methods_seen = {_parse_dims(key)["method"] for key in keys}
    assert "POST" in methods_seen


def test_middleware_disabled_when_metrics_enabled_false(
    app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN METRICS_ENABLED is False (the ConfigTest default)
    WHEN any route is requested
    THEN no api_hit counter key is recorded.
    """
    assert not app.config.get(CONFIG_ENVS.METRICS_ENABLED, False)
    client.get("/")
    assert _api_hit_keys(provide_metrics_redis) == []


def test_middleware_does_not_break_request_on_writer_failure(
    metrics_enabled_app: Flask,
    client: FlaskClient,
):
    """
    GIVEN the writer's underlying Redis client raises on pipeline()
    WHEN a normal route is requested
    THEN the response is unaffected (no 500 from the middleware) — the writer's
        own log-and-drop wrapper swallows the Redis failure.
    """

    class _BrokenRedis:
        def pipeline(self):
            raise RuntimeError("simulated redis failure")

    with mock.patch.object(app_metrics_writer, "_redis", _BrokenRedis()):
        response = client.get("/")

    assert response.status_code == 200
