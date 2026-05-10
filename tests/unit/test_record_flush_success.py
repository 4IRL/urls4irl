from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
import redis

from scripts.flush_metrics import FLUSH_LAST_SUCCESS_KEY, _record_flush_success

pytestmark = pytest.mark.unit


def test_record_flush_success_swallows_redis_connection_error(caplog):
    """
    GIVEN a Redis client whose .set(...) raises redis.exceptions.ConnectionError
    WHEN _record_flush_success is invoked
    THEN the function returns without raising and the failure is logged at
        ERROR level on the metrics_flush logger — confirming that a transient
        Redis hiccup at the very end of an otherwise-successful flush does not
        flip the whole run to failure (Postgres commit has already landed, so
        the next cron tick will detect liveness failure if Redis genuinely
        stays down).
    """
    redis_mock = MagicMock()
    redis_mock.set.side_effect = redis.exceptions.ConnectionError("redis down")

    with caplog.at_level(logging.ERROR, logger="metrics_flush"):
        _record_flush_success(redis_mock)

    assert "failed to stamp liveness sentinel" in caplog.text
    assert "redis down" in caplog.text
    redis_mock.set.assert_called_once()
    set_call_args = redis_mock.set.call_args
    assert set_call_args.args[0] == FLUSH_LAST_SUCCESS_KEY
