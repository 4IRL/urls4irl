from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scripts.check_flush_liveness import (
    DEFAULT_THRESHOLD_SECONDS,
    LIVENESS_KEY,
    _resolve_threshold_seconds,
    check_liveness,
)

pytestmark = pytest.mark.unit


_FIXED_NOW_EPOCH = 1_800_000_000


def _build_redis_mock(get_return: bytes | str | None) -> MagicMock:
    """Construct a Redis mock whose ``get(LIVENESS_KEY)`` returns the given value."""
    redis_mock = MagicMock()
    redis_mock.get.return_value = get_return
    return redis_mock


def test_check_liveness_returns_failure_when_sentinel_missing(capsys):
    """
    GIVEN Redis returns None for the liveness sentinel
    WHEN check_liveness is invoked
    THEN it returns exit code 1 and a stderr message containing "missing".
    """
    redis_mock = _build_redis_mock(get_return=None)

    exit_code, stderr_message = check_liveness(
        redis_client=redis_mock,
        threshold_seconds=DEFAULT_THRESHOLD_SECONDS,
        now_epoch=_FIXED_NOW_EPOCH,
    )

    assert exit_code == 1
    assert "missing" in stderr_message
    redis_mock.get.assert_called_once_with(LIVENESS_KEY)


def test_check_liveness_returns_success_when_sentinel_fresh(capsys):
    """
    GIVEN the liveness sentinel was stamped 30 seconds ago and threshold is
        the 180s default
    WHEN check_liveness is invoked
    THEN it returns exit code 0 and an empty stderr message.
    """
    fresh_epoch = _FIXED_NOW_EPOCH - 30
    redis_mock = _build_redis_mock(get_return=str(fresh_epoch).encode("utf-8"))

    exit_code, stderr_message = check_liveness(
        redis_client=redis_mock,
        threshold_seconds=DEFAULT_THRESHOLD_SECONDS,
        now_epoch=_FIXED_NOW_EPOCH,
    )

    assert exit_code == 0
    assert stderr_message == ""


def test_check_liveness_returns_failure_when_sentinel_stale(capsys):
    """
    GIVEN the liveness sentinel was stamped 300 seconds ago and threshold is 180s
    WHEN check_liveness is invoked
    THEN it returns exit code 1 and a stderr message containing "stale" and
        the actual age + threshold values.
    """
    stale_epoch = _FIXED_NOW_EPOCH - 300
    redis_mock = _build_redis_mock(get_return=str(stale_epoch).encode("utf-8"))

    exit_code, stderr_message = check_liveness(
        redis_client=redis_mock,
        threshold_seconds=180,
        now_epoch=_FIXED_NOW_EPOCH,
    )

    assert exit_code == 1
    assert "stale" in stderr_message
    assert "300s" in stderr_message
    assert "180s" in stderr_message


def test_check_liveness_accepts_string_redis_value(capsys):
    """
    GIVEN a Redis client configured with decode_responses=True returns a str
        instead of bytes for the sentinel value
    WHEN check_liveness is invoked with a fresh value
    THEN the str path is exercised and the call succeeds.
    """
    fresh_epoch = _FIXED_NOW_EPOCH - 10
    redis_mock = _build_redis_mock(get_return=str(fresh_epoch))

    exit_code, stderr_message = check_liveness(
        redis_client=redis_mock,
        threshold_seconds=DEFAULT_THRESHOLD_SECONDS,
        now_epoch=_FIXED_NOW_EPOCH,
    )

    assert exit_code == 0
    assert stderr_message == ""


def test_check_liveness_returns_failure_when_value_not_integer(capsys):
    """
    GIVEN the liveness sentinel value is non-numeric (corrupted)
    WHEN check_liveness is invoked
    THEN it returns exit code 1 and a stderr message indicating the value
        is not parseable.
    """
    redis_mock = _build_redis_mock(get_return=b"not-a-number")

    exit_code, stderr_message = check_liveness(
        redis_client=redis_mock,
        threshold_seconds=DEFAULT_THRESHOLD_SECONDS,
        now_epoch=_FIXED_NOW_EPOCH,
    )

    assert exit_code == 1
    assert "not an integer" in stderr_message


def test_check_liveness_boundary_at_threshold_is_success(capsys):
    """
    GIVEN the sentinel is stamped exactly threshold_seconds ago
    WHEN check_liveness is invoked
    THEN it returns success — the boundary `age == threshold` is treated as
        in-window (only `age > threshold` fails). Documents the comparison.
    """
    boundary_epoch = _FIXED_NOW_EPOCH - 180
    redis_mock = _build_redis_mock(get_return=str(boundary_epoch).encode("utf-8"))

    exit_code, stderr_message = check_liveness(
        redis_client=redis_mock,
        threshold_seconds=180,
        now_epoch=_FIXED_NOW_EPOCH,
    )

    assert exit_code == 0
    assert stderr_message == ""


def test_resolve_threshold_seconds_uses_default_when_unset(monkeypatch):
    """
    GIVEN METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS is not set
    WHEN _resolve_threshold_seconds is invoked
    THEN it returns DEFAULT_THRESHOLD_SECONDS (180).
    """
    monkeypatch.delenv("METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS", raising=False)

    assert _resolve_threshold_seconds() == DEFAULT_THRESHOLD_SECONDS


def test_resolve_threshold_seconds_uses_default_when_empty(monkeypatch):
    """
    GIVEN METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS is set to an empty string
    WHEN _resolve_threshold_seconds is invoked
    THEN it returns DEFAULT_THRESHOLD_SECONDS (an empty env var should not be
        treated as a numeric override).
    """
    monkeypatch.setenv("METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS", "")

    assert _resolve_threshold_seconds() == DEFAULT_THRESHOLD_SECONDS


def test_resolve_threshold_seconds_uses_env_override(monkeypatch):
    """
    GIVEN METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS is set to "300"
    WHEN _resolve_threshold_seconds is invoked
    THEN it returns 300, proving the threshold is tunable per environment.
    """
    monkeypatch.setenv("METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS", "300")

    assert _resolve_threshold_seconds() == 300
