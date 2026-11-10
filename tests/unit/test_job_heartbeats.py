"""Unit coverage for the hub heartbeat pings in the scheduled jobs' ``__main__`` blocks.

Each of the six Python jobs (metrics flush, gauge sampler, four purges) is executed as
``__main__`` through ``runpy`` with the database and Redis mocked. The network is
reached only through the global ``urllib.request.urlopen``, patched with a counting stub
(the scripts re-load ``notifs_hub`` on every execution, so patching ``ping`` or
``safe_ping`` would be discarded). Asserted per job: success sends one success ping,
failure sends one ``/fail`` ping and exits 1, a failed ping never changes the exit code,
and a ping that raises is swallowed without a second (``/fail``) ping.
"""

from __future__ import annotations

import runpy
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import psycopg2
import psycopg2.extras
import pytest
import redis

pytestmark = pytest.mark.unit

_SCRIPTS_DIR: Path = Path(__file__).resolve().parents[2] / "scripts"
_BASE_URL: str = "https://hub.test"
_FREQUENT_TIMEOUT_SECONDS: float = 3.0
_DEFAULT_TIMEOUT_SECONDS: float = 10.0

# (script file, check name, expected urlopen timeout)
_JOBS: list[tuple[str, str, float]] = [
    ("flush_metrics.py", "metrics_flush", _FREQUENT_TIMEOUT_SECONDS),
    ("sample_gauges.py", "gauge_sample", _FREQUENT_TIMEOUT_SECONDS),
    ("purge_audit_log.py", "purge_audit_log", _DEFAULT_TIMEOUT_SECONDS),
    ("purge_trash.py", "purge_trash", _DEFAULT_TIMEOUT_SECONDS),
    ("purge_short_links.py", "purge_short_links", _DEFAULT_TIMEOUT_SECONDS),
    ("purge_invite_links.py", "purge_invite_links", _DEFAULT_TIMEOUT_SECONDS),
]


class _UrlopenStub:
    """Counting stand-in for ``urllib.request.urlopen`` returning a configured result."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, float]] = []
        self.status: int = 200
        self.error: BaseException | None = None

    def __call__(self, request: Any, timeout: float) -> _UrlopenStub:
        self.calls.append((request.full_url, timeout))
        if self.error is not None:
            raise self.error
        return self

    def __enter__(self) -> _UrlopenStub:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


@pytest.fixture
def urlopen_stub(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _UrlopenStub:
    """Production env with a populated key dir, and a counting ``urlopen`` stub."""
    for file_name, value in (
        ("delivery_key", "dak_test"),
        ("access_client_id", "client-id"),
        ("access_client_secret", "client-secret"),
    ):
        (tmp_path / file_name).write_text(value + "\n", encoding="utf-8")
    monkeypatch.setenv("PRODUCTION", "true")
    monkeypatch.setenv("NOTIFS_BASE_URL", _BASE_URL)
    monkeypatch.setenv("NOTIFS_KEY_DIR", str(tmp_path))
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    monkeypatch.setenv("METRICS_REDIS_URI", "redis://localhost:6379/0")
    stub = _UrlopenStub()
    monkeypatch.setattr(urllib.request, "urlopen", stub)
    return stub


def _arrange_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock Postgres and Redis so every job's run completes without work to do."""
    mock_connection = MagicMock()
    mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
    mock_cursor.rowcount = 0
    mock_cursor.fetchall.return_value = []
    mock_cursor.fetchone.return_value = (0,)
    monkeypatch.setattr(psycopg2, "connect", MagicMock(return_value=mock_connection))
    monkeypatch.setattr(psycopg2.extras, "execute_values", MagicMock())
    mock_redis = MagicMock()
    mock_redis.set.return_value = True
    mock_redis.get.return_value = None
    mock_redis.getdel.return_value = None
    mock_redis.delete.return_value = 0
    mock_redis.scan_iter.side_effect = lambda *args, **kwargs: iter([])
    monkeypatch.setattr(redis.Redis, "from_url", MagicMock(return_value=mock_redis))


def _arrange_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the database connection fail so every job takes its ``except`` branch."""
    _arrange_success(monkeypatch)
    monkeypatch.setattr(
        psycopg2, "connect", MagicMock(side_effect=RuntimeError("db down"))
    )


def _run_as_main(script_file: str) -> Any:
    """Execute a script as ``__main__`` and return its ``SystemExit`` code."""
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(_SCRIPTS_DIR / script_file), run_name="__main__")
    return exit_info.value.code


@pytest.mark.parametrize("script_file, check, expected_timeout", _JOBS)
def test_success_sends_one_success_ping(
    script_file: str,
    check: str,
    expected_timeout: float,
    monkeypatch: pytest.MonkeyPatch,
    urlopen_stub: _UrlopenStub,
) -> None:
    """
    GIVEN a job whose run succeeds and a hub answering 200
    WHEN the script runs as __main__
    THEN exactly one success ping is sent (with the job's timeout) and it exits 0
    """
    _arrange_success(monkeypatch)

    assert _run_as_main(script_file) == 0

    assert urlopen_stub.calls == [
        (f"{_BASE_URL}/v1/heartbeats/urls4irl/{check}", expected_timeout)
    ]


@pytest.mark.parametrize("script_file, check, expected_timeout", _JOBS)
def test_failure_sends_one_fail_ping_and_exits_one(
    script_file: str,
    check: str,
    expected_timeout: float,
    monkeypatch: pytest.MonkeyPatch,
    urlopen_stub: _UrlopenStub,
) -> None:
    """
    GIVEN a job whose run raises
    WHEN the script runs as __main__
    THEN exactly one /fail ping is sent (with the job's timeout) and it exits 1
    """
    _arrange_failure(monkeypatch)

    assert _run_as_main(script_file) == 1

    assert urlopen_stub.calls == [
        (f"{_BASE_URL}/v1/heartbeats/urls4irl/{check}/fail", expected_timeout)
    ]


@pytest.mark.parametrize("script_file, check, expected_timeout", _JOBS)
@pytest.mark.parametrize(
    "arrange_name, expected_code", [("success", 0), ("failure", 1)]
)
def test_a_failed_ping_never_changes_the_exit_code(
    script_file: str,
    check: str,
    expected_timeout: float,
    arrange_name: str,
    expected_code: int,
    monkeypatch: pytest.MonkeyPatch,
    urlopen_stub: _UrlopenStub,
) -> None:
    """
    GIVEN a hub that refuses the ping (HTTP 503)
    WHEN the script runs as __main__ on a successful and on a failing run
    THEN the exit code is the job's own (0 / 1) and exactly one ping was attempted
    """
    arrange = _arrange_success if arrange_name == "success" else _arrange_failure
    arrange(monkeypatch)
    urlopen_stub.error = urllib.error.HTTPError(
        f"{_BASE_URL}/x",
        503,
        "unavailable",
        {},
        None,  # type: ignore[arg-type]
    )

    assert _run_as_main(script_file) == expected_code

    assert len(urlopen_stub.calls) == 1


@pytest.mark.parametrize("script_file, check, expected_timeout", _JOBS)
def test_a_raising_ping_never_double_pings(
    script_file: str,
    check: str,
    expected_timeout: float,
    monkeypatch: pytest.MonkeyPatch,
    urlopen_stub: _UrlopenStub,
) -> None:
    """
    GIVEN a successful job whose success ping raises an exception outside ping's own
        caught set (RuntimeError)
    WHEN the script runs as __main__
    THEN safe_ping swallows it, the job exits 0, and only the success URL was called
        (no /fail ping from the except branch)
    """
    _arrange_success(monkeypatch)
    urlopen_stub.error = RuntimeError("unexpected")

    assert _run_as_main(script_file) == 0

    assert urlopen_stub.calls == [
        (f"{_BASE_URL}/v1/heartbeats/urls4irl/{check}", expected_timeout)
    ]


@pytest.mark.parametrize("script_file, check, expected_timeout", _JOBS)
def test_no_hub_call_outside_production(
    script_file: str,
    check: str,
    expected_timeout: float,
    monkeypatch: pytest.MonkeyPatch,
    urlopen_stub: _UrlopenStub,
) -> None:
    """
    GIVEN PRODUCTION is not "true"
    WHEN the script runs as __main__
    THEN no hub call is made and the exit code is unchanged
    """
    monkeypatch.setenv("PRODUCTION", "false")
    _arrange_success(monkeypatch)

    assert _run_as_main(script_file) == 0

    assert urlopen_stub.calls == []
