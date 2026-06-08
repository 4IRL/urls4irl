from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from flask import Flask

from backend.extensions.metrics.writer import MetricsWriter
from backend.utils.strings.metrics_strs import METRICS_REDIS

pytestmark = pytest.mark.unit


_VALID_EPOCH_STRING = "1717890000"
_VALID_EPOCH_INT = 1717890000


def _build_writer(enabled: bool, redis_client: MagicMock | None) -> MetricsWriter:
    """Construct a writer with the given enabled flag + redis client.

    Bypasses ``init_app`` so the test does not need a fully wired Flask
    config; the only state ``get_last_flush_success_epoch`` reads is
    ``_enabled`` and ``_redis``.
    """
    writer = MetricsWriter()
    writer._enabled = enabled
    writer._redis = redis_client
    return writer


def test_get_last_flush_success_epoch_returns_none_when_disabled():
    """
    GIVEN metrics are disabled (``METRICS_ENABLED=false``)
    WHEN get_last_flush_success_epoch is invoked
    THEN it returns None without consulting Redis.
    """
    redis_mock = MagicMock()
    writer = _build_writer(enabled=False, redis_client=redis_mock)

    assert writer.get_last_flush_success_epoch() is None
    redis_mock.get.assert_not_called()


def test_get_last_flush_success_epoch_returns_none_when_no_redis_client():
    """
    GIVEN metrics are enabled but no Redis client was wired
    WHEN get_last_flush_success_epoch is invoked
    THEN it returns None.
    """
    writer = _build_writer(enabled=True, redis_client=None)

    assert writer.get_last_flush_success_epoch() is None


def test_get_last_flush_success_epoch_returns_parsed_int_for_valid_value():
    """
    GIVEN Redis returns a valid epoch string under FLUSH_LAST_SUCCESS_KEY
    WHEN get_last_flush_success_epoch is invoked
    THEN the parsed int is returned and Redis was queried with the expected key.
    """
    redis_mock = MagicMock()
    redis_mock.get.return_value = _VALID_EPOCH_STRING
    writer = _build_writer(enabled=True, redis_client=redis_mock)

    assert writer.get_last_flush_success_epoch() == _VALID_EPOCH_INT
    redis_mock.get.assert_called_once_with(METRICS_REDIS.FLUSH_LAST_SUCCESS_KEY)


def test_get_last_flush_success_epoch_returns_none_for_missing_key():
    """
    GIVEN Redis returns None for the liveness key (key never set)
    WHEN get_last_flush_success_epoch is invoked
    THEN it returns None.
    """
    redis_mock = MagicMock()
    redis_mock.get.return_value = None
    writer = _build_writer(enabled=True, redis_client=redis_mock)

    assert writer.get_last_flush_success_epoch() is None


def test_get_last_flush_success_epoch_returns_none_for_non_numeric_value():
    """
    GIVEN Redis returns a value that can't be parsed as an int (corruption)
    WHEN get_last_flush_success_epoch is invoked
    THEN it returns None rather than raising ValueError.
    """
    redis_mock = MagicMock()
    redis_mock.get.return_value = "abc"
    writer = _build_writer(enabled=True, redis_client=redis_mock)

    assert writer.get_last_flush_success_epoch() is None


def test_get_last_flush_success_epoch_returns_none_when_redis_raises():
    """
    GIVEN ``redis.get`` raises (transient Redis hiccup)
    WHEN get_last_flush_success_epoch is invoked
    THEN it returns None and the failure is logged via current_app.logger.

    The Flask app context is required because the method calls
    ``current_app.logger.exception(...)`` on the failure path.
    """
    redis_mock = MagicMock()
    redis_mock.get.side_effect = RuntimeError("redis down")
    writer = _build_writer(enabled=True, redis_client=redis_mock)

    app = Flask(__name__)
    with app.app_context():
        assert writer.get_last_flush_success_epoch() is None
