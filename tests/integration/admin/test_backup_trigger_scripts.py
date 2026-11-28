"""Integration tests for the cross-container backup trigger scripts.

Covers the workflow-container side of the on-demand backup mechanism:
  - scripts/backup_sentinel.py — stamps the backup last-success sentinel.
  - scripts/run_backup_if_requested.py — per-minute cron poller that consumes
    the admin portal's trigger flag (GETDEL), takes the overlap lock, and runs
    the backup pipeline.

The web-side flag-setting endpoint is covered in test_admin_ops_actions.py.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from backend.utils.strings.metrics_strs import METRICS_REDIS
from scripts.backup_sentinel import stamp_backup_success
from scripts.run_backup_if_requested import (
    acquire_trigger_lock,
    consume_trigger_request,
    main,
    release_trigger_lock,
    resolve_backup_script_path,
    run_backup_pipeline,
)

pytestmark = pytest.mark.admin

_TEST_EPOCH: int = 1_760_000_000
_TEST_FLAG_VALUE: str = "1760000123"


def _require_metrics_redis(provide_metrics_redis: Redis | None) -> Redis:
    if provide_metrics_redis is None:
        pytest.skip("metrics Redis not configured in test environment")
    return provide_metrics_redis


def test_stamp_backup_success_sets_sentinel(provide_metrics_redis: Redis | None):
    """
    GIVEN a metrics Redis with no backup sentinel
    WHEN stamp_backup_success() is called with an epoch
    THEN the BACKUP_LAST_SUCCESS_KEY holds that epoch (no TTL).
    """
    metrics_redis = _require_metrics_redis(provide_metrics_redis)
    assert metrics_redis.get(METRICS_REDIS.BACKUP_LAST_SUCCESS_KEY) is None

    try:
        stamp_backup_success(redis_client=metrics_redis, epoch=_TEST_EPOCH)

        sentinel_value = metrics_redis.get(METRICS_REDIS.BACKUP_LAST_SUCCESS_KEY)
        assert sentinel_value is not None
        assert int(sentinel_value) == _TEST_EPOCH
        assert metrics_redis.ttl(METRICS_REDIS.BACKUP_LAST_SUCCESS_KEY) == -1
    finally:
        metrics_redis.delete(METRICS_REDIS.BACKUP_LAST_SUCCESS_KEY)


def test_consume_trigger_request_returns_none_when_no_flag(
    provide_metrics_redis: Redis | None,
):
    """
    GIVEN no pending trigger flag
    WHEN consume_trigger_request() is called
    THEN it returns None and sets nothing.
    """
    metrics_redis = _require_metrics_redis(provide_metrics_redis)
    assert metrics_redis.get(METRICS_REDIS.BACKUP_TRIGGER_KEY) is None

    assert consume_trigger_request(redis_client=metrics_redis) is None
    assert metrics_redis.get(METRICS_REDIS.BACKUP_TRIGGER_KEY) is None


def test_consume_trigger_request_consumes_flag_exactly_once(
    provide_metrics_redis: Redis | None,
):
    """
    GIVEN a pending trigger flag
    WHEN consume_trigger_request() is called twice
    THEN the first call returns the flag value and removes the key (GETDEL),
         and the second call returns None — the flag is consumed exactly once.
    """
    metrics_redis = _require_metrics_redis(provide_metrics_redis)
    metrics_redis.set(METRICS_REDIS.BACKUP_TRIGGER_KEY, _TEST_FLAG_VALUE)

    first_result = consume_trigger_request(redis_client=metrics_redis)
    second_result = consume_trigger_request(redis_client=metrics_redis)

    assert first_result == _TEST_FLAG_VALUE
    assert second_result is None
    assert metrics_redis.get(METRICS_REDIS.BACKUP_TRIGGER_KEY) is None


def test_trigger_lock_blocks_second_acquire_until_released(
    provide_metrics_redis: Redis | None,
):
    """
    GIVEN an unheld trigger lock
    WHEN the lock is acquired, re-acquired, released, and acquired again
    THEN the first acquire succeeds, the overlapping acquire fails, and a
         fresh acquire succeeds after release.
    """
    metrics_redis = _require_metrics_redis(provide_metrics_redis)
    assert metrics_redis.get(METRICS_REDIS.BACKUP_TRIGGER_LOCK_KEY) is None

    try:
        assert acquire_trigger_lock(redis_client=metrics_redis)
        assert not acquire_trigger_lock(redis_client=metrics_redis)

        release_trigger_lock(redis_client=metrics_redis)

        assert acquire_trigger_lock(redis_client=metrics_redis)
    finally:
        release_trigger_lock(redis_client=metrics_redis)


def test_resolve_backup_script_path_finds_repo_script():
    """
    GIVEN the repository layout (no /app directory)
    WHEN resolve_backup_script_path() is called
    THEN it resolves to an existing daily-docker.sh file.
    """
    backup_script_path = resolve_backup_script_path()
    assert backup_script_path is not None
    assert backup_script_path.is_file()
    assert backup_script_path.name == "daily-docker.sh"


def test_run_backup_pipeline_invokes_bash_with_script_path(
    monkeypatch: pytest.MonkeyPatch,
):
    """
    GIVEN subprocess.run monkeypatched to capture its argv and env
    WHEN run_backup_pipeline() is called with a script path
    THEN bash is invoked with exactly that path, the subprocess env carries
         BACKUP_TRIGGER_SOURCE=manual, and the exit code is propagated back.
    """
    captured_argv: list[list[str]] = []
    captured_env: list[dict[str, str] | None] = []

    class _FakeCompletedProcess:
        returncode = 7

    def _fake_run(
        argv: list[str], check: bool, env: dict[str, str] | None = None
    ) -> _FakeCompletedProcess:
        assert not check
        captured_argv.append(argv)
        captured_env.append(env)
        return _FakeCompletedProcess()

    monkeypatch.setattr("scripts.run_backup_if_requested.subprocess.run", _fake_run)

    exit_code = run_backup_pipeline(backup_script_path=Path("/app/daily-docker.sh"))

    assert exit_code == 7
    assert captured_argv == [["/bin/bash", "/app/daily-docker.sh"]]
    assert captured_env[0] is not None
    assert captured_env[0]["BACKUP_TRIGGER_SOURCE"] == "manual"


def test_main_logs_an_unreachable_metrics_redis_and_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """
    GIVEN a metrics Redis that cannot be reached
    WHEN the poller's main() runs
    THEN it logs the error through the timestamped logger (not a bare traceback,
         #1060), never starts a backup, and exits 1.
    """

    class _UnreachableRedis:
        def getdel(self, name: str) -> None:
            raise RedisConnectionError(
                "Error -2 connecting to redis-metrics:6379. Name or service not known."
            )

        def close(self) -> None:
            pass

    def _fail_if_run(**_kwargs: object) -> int:
        raise AssertionError("no backup may start without the trigger flag")

    monkeypatch.setenv("METRICS_REDIS_URI", "redis://redis-metrics:6379/0")
    monkeypatch.setattr(
        "scripts.run_backup_if_requested.redis.Redis.from_url",
        lambda _uri: _UnreachableRedis(),
    )
    monkeypatch.setattr(
        "scripts.run_backup_if_requested.run_backup_pipeline", _fail_if_run
    )

    with caplog.at_level(logging.ERROR, logger="backup_trigger_poller"):
        exit_code = main()

    assert exit_code == 1
    assert any(
        "cannot poll the backup trigger in metrics Redis" in record.getMessage()
        and "redis-metrics:6379" in record.getMessage()
        for record in caplog.records
    )


def test_main_logs_a_dropped_trigger_when_the_lock_acquire_fails(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """
    GIVEN a trigger flag that is consumed and then a lock SET that hits a Redis outage
    WHEN the poller's main() runs
    THEN it logs a dropped-trigger error naming the requested epoch, never starts
         a backup, and exits 1.
    """

    class _LockFailsRedis:
        def getdel(self, name: str) -> str:
            return _TEST_FLAG_VALUE

        def set(self, *_args: object, **_kwargs: object) -> None:
            raise RedisConnectionError("Connection reset by peer")

        def close(self) -> None:
            pass

    def _fail_if_run(**_kwargs: object) -> int:
        raise AssertionError("no backup may start when the lock is not acquired")

    monkeypatch.setenv("METRICS_REDIS_URI", "redis://redis-metrics:6379/0")
    monkeypatch.setattr(
        "scripts.run_backup_if_requested.redis.Redis.from_url",
        lambda _uri: _LockFailsRedis(),
    )
    monkeypatch.setattr(
        "scripts.run_backup_if_requested.run_backup_pipeline", _fail_if_run
    )

    with caplog.at_level(logging.ERROR, logger="backup_trigger_poller"):
        exit_code = main()

    assert exit_code == 1
    assert any(
        "dropped" in record.getMessage()
        and _TEST_FLAG_VALUE in record.getMessage()
        and "re-triggered" in record.getMessage()
        for record in caplog.records
    )
