from __future__ import annotations

import logging
import socket
import time
from contextlib import contextmanager
from typing import Callable, Generator
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from redis import Redis
from sqlalchemy import event, text

import backend.system.health_checks as health_checks
from backend import db
from backend.db import get_missing_tables
from backend.system.health_checks import (
    DEEP_CHECK_DEADLINE_SECONDS,
    METRICS_REDIS_OPERATION_COUNT,
    POSTGRES_STATEMENT_COUNT,
    SESSION_REDIS_OPERATION_COUNT,
    STATUS_DOWN,
    STATUS_NOT_CONFIGURED,
    STATUS_UP,
    Budget,
    probe_metrics_redis,
    probe_postgres,
    probe_session_redis,
)
from backend.utils.strings.config_strs import CONFIG_ENVS

pytestmark = pytest.mark.cli

_MEMORY_URI = "memory://"
_BLACK_HOLE_MAX_SECONDS = 3.0
_REDIS_PASSWORD = "sup3rs3cretpw"
_WRONG_TOKEN = "wrong-health-token-value"


@contextmanager
def _black_hole_uri() -> Generator[str, None, None]:
    """A listening TCP socket that never accepts or responds."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        yield f"redis://127.0.0.1:{listener.getsockname()[1]}/0"
    finally:
        listener.close()


@contextmanager
def _closed_port_uri(password: str | None = None) -> Generator[str, None, None]:
    """A URI whose port refuses connections immediately."""
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind(("127.0.0.1", 0))
    port = holder.getsockname()[1]
    holder.close()
    userinfo = f":{password}@" if password else ""
    yield f"redis://{userinfo}127.0.0.1:{port}/0"


def _real_redis_or_skip(app: Flask, key: str) -> None:
    uri = app.config.get(key)
    if not uri or uri == _MEMORY_URI:
        pytest.skip(f"{key} is memory:// in this environment")


def test_budget_remaining_decreases(app: Flask) -> None:
    budget = Budget.start(0.5)
    first = budget.remaining()
    time.sleep(0.01)
    assert first <= 0.5
    assert budget.remaining() < first


def test_budget_start_reads_deadline_at_call_time(app: Flask) -> None:
    with patch.object(health_checks, "DEEP_CHECK_DEADLINE_SECONDS", 1):
        assert Budget.start().remaining() <= 1
    assert Budget.start().remaining() > 1
    assert DEEP_CHECK_DEADLINE_SECONDS > 1


def test_probe_session_redis_up(app: Flask) -> None:
    _real_redis_or_skip(app, CONFIG_ENVS.REDIS_URI)
    with app.app_context():
        assert probe_session_redis() == STATUS_UP
        assert probe_session_redis(Budget.start(7)) == STATUS_UP


def test_probe_metrics_redis_up(app: Flask) -> None:
    _real_redis_or_skip(app, CONFIG_ENVS.METRICS_REDIS_URI)
    with app.app_context():
        assert probe_metrics_redis() == STATUS_UP


def test_probe_postgres_up(app: Flask) -> None:
    with app.app_context():
        assert probe_postgres() == STATUS_UP
        assert probe_postgres(Budget.start(7)) == STATUS_UP


@pytest.mark.parametrize("uri", [None, "", _MEMORY_URI])
def test_redis_probes_not_configured(app: Flask, uri: str | None) -> None:
    with patch.dict(
        app.config, {CONFIG_ENVS.REDIS_URI: uri, CONFIG_ENVS.METRICS_REDIS_URI: uri}
    ):
        with app.app_context():
            assert probe_session_redis() == STATUS_NOT_CONFIGURED
            assert probe_metrics_redis() == STATUS_NOT_CONFIGURED


@pytest.mark.parametrize(
    "config_key,probe",
    [
        (CONFIG_ENVS.REDIS_URI, probe_session_redis),
        (CONFIG_ENVS.METRICS_REDIS_URI, probe_metrics_redis),
    ],
)
def test_black_hole_redis_is_down_quickly(
    app: Flask, config_key: str, probe: Callable[[], str]
) -> None:
    with _black_hole_uri() as uri:
        with patch.dict(app.config, {config_key: uri}):
            with app.app_context():
                started_at = time.monotonic()
                status = probe()
                elapsed = time.monotonic() - started_at
    assert status == STATUS_DOWN
    assert elapsed < _BLACK_HOLE_MAX_SECONDS


def test_postgres_connect_args_carry_apportioned_timeouts(app: Flask) -> None:
    budget = Budget.start(7)
    with app.app_context():
        expected_url = db.engine.url
        with patch.object(
            health_checks, "create_engine", wraps=health_checks.create_engine
        ) as engine_spy:
            status = probe_postgres(budget)
    assert status == STATUS_UP
    args, kwargs = engine_spy.call_args
    assert args[0] == expected_url
    connect_args = kwargs["connect_args"]
    assert isinstance(connect_args["connect_timeout"], int)
    assert connect_args["connect_timeout"] == 2
    statement_timeout_ms = int(connect_args["options"].split("statement_timeout=")[1])
    # The budget has ticked a little before the probe reads it.
    assert statement_timeout_ms <= int((7 - 2) * 1000 / POSTGRES_STATEMENT_COUNT)
    assert statement_timeout_ms > 1000


def test_postgres_full_budget_statement_timeout_exact(app: Flask) -> None:
    budget = MagicMock(spec=Budget)
    budget.remaining.return_value = 7.0
    with app.app_context():
        with patch.object(
            health_checks, "create_engine", wraps=health_checks.create_engine
        ) as engine_spy:
            probe_postgres(budget)
    options = engine_spy.call_args.kwargs["connect_args"]["options"]
    assert options == "-c statement_timeout=1250"


@pytest.mark.parametrize("remaining", [0, 1.9, 2.5, -1])
def test_postgres_low_budget_is_down_without_engine(
    app: Flask, remaining: float
) -> None:
    budget = MagicMock(spec=Budget)
    budget.remaining.return_value = remaining
    with app.app_context():
        with patch.object(health_checks, "create_engine") as engine_spy:
            assert probe_postgres(budget) == STATUS_DOWN
    engine_spy.assert_not_called()


def test_postgres_statement_count_within_budgeted_constant(app: Flask) -> None:
    executed: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        executed.append(statement)

    real_create_engine = health_checks.create_engine

    def _create_and_listen(*args, **kwargs):
        engine = real_create_engine(*args, **kwargs)
        event.listen(engine, "before_cursor_execute", _record)
        return engine

    with app.app_context():
        with patch.object(health_checks, "create_engine", _create_and_listen):
            assert probe_postgres(Budget.start(7)) == STATUS_UP
    assert 0 < len(executed) <= POSTGRES_STATEMENT_COUNT


def test_postgres_failure_closes_connection_and_disposes_engine(app: Flask) -> None:
    connection = MagicMock()
    connection.execute.side_effect = Exception("boom")
    engine = MagicMock()
    engine.connect.return_value = connection
    with app.app_context():
        with patch.object(health_checks, "create_engine", return_value=engine):
            assert probe_postgres() == STATUS_DOWN
    connection.close.assert_called_once()
    engine.dispose.assert_called_once()


def test_postgres_missing_table_is_down(app: Flask) -> None:
    with app.app_context():
        with patch.object(health_checks, "get_missing_tables", return_value=["users"]):
            assert probe_postgres() == STATUS_DOWN


def test_postgres_probe_does_not_leak_into_shared_session(app: Flask) -> None:
    with app.app_context():
        before = db.session.execute(text("SHOW statement_timeout")).scalar()
        assert probe_postgres() == STATUS_UP
        after_ok = db.session.execute(text("SHOW statement_timeout")).scalar()

        connection = MagicMock()
        connection.execute.side_effect = Exception("boom")
        engine = MagicMock()
        engine.connect.return_value = connection
        with patch.object(health_checks, "create_engine", return_value=engine):
            assert probe_postgres() == STATUS_DOWN
        after_failure = db.session.execute(text("SHOW statement_timeout")).scalar()
        assert db.session.execute(text("SELECT 1")).scalar() == 1
    assert before == after_ok == after_failure


@pytest.mark.parametrize("remaining", [0, -1])
def test_redis_probes_down_without_client_when_no_budget(
    app: Flask, remaining: float
) -> None:
    budget = MagicMock(spec=Budget)
    budget.remaining.return_value = remaining
    with patch.dict(
        app.config,
        {
            CONFIG_ENVS.REDIS_URI: "redis://127.0.0.1:1/0",
            CONFIG_ENVS.METRICS_REDIS_URI: "redis://127.0.0.1:1/0",
        },
    ):
        with app.app_context():
            with patch.object(Redis, "from_url") as from_url_spy:
                assert probe_session_redis(budget) == STATUS_DOWN
                assert probe_metrics_redis(budget) == STATUS_DOWN
    from_url_spy.assert_not_called()


def _captured_timeouts(
    probe: Callable[[Budget | None], str],
    config_key: str,
    app: Flask,
    budget: Budget | None,
) -> dict:
    with patch.dict(app.config, {config_key: "redis://127.0.0.1:1/0"}):
        with app.app_context():
            with patch.object(Redis, "from_url") as from_url_spy:
                probe(budget)
    return from_url_spy.call_args.kwargs


def test_redis_timeouts_are_apportioned_across_operations(app: Flask) -> None:
    session_kwargs = _captured_timeouts(
        probe_session_redis, CONFIG_ENVS.REDIS_URI, app, Budget.start(0.9)
    )
    metrics_kwargs = _captured_timeouts(
        probe_metrics_redis, CONFIG_ENVS.METRICS_REDIS_URI, app, Budget.start(0.9)
    )
    for key in ("socket_connect_timeout", "socket_timeout"):
        assert session_kwargs[key] <= 0.9 / SESSION_REDIS_OPERATION_COUNT
        assert metrics_kwargs[key] <= 0.9 / METRICS_REDIS_OPERATION_COUNT


def test_redis_timeouts_cap_at_two_seconds_with_full_budget(app: Flask) -> None:
    session_kwargs = _captured_timeouts(
        probe_session_redis, CONFIG_ENVS.REDIS_URI, app, Budget.start(7)
    )
    assert session_kwargs["socket_connect_timeout"] == 2
    assert session_kwargs["socket_timeout"] == 2
    # 7 / 4 = 1.75 is below the 2 s cap, so the metrics share is the quotient.
    metrics_kwargs = _captured_timeouts(
        probe_metrics_redis, CONFIG_ENVS.METRICS_REDIS_URI, app, Budget.start(7)
    )
    for key in ("socket_connect_timeout", "socket_timeout"):
        assert 1.7 < metrics_kwargs[key] <= 7 / METRICS_REDIS_OPERATION_COUNT
    huge_budget_kwargs = _captured_timeouts(
        probe_metrics_redis, CONFIG_ENVS.METRICS_REDIS_URI, app, Budget.start(60)
    )
    assert huge_budget_kwargs["socket_timeout"] == 2


def test_redis_timeouts_without_budget_fit_default_budget(app: Flask) -> None:
    session_kwargs = _captured_timeouts(
        probe_session_redis, CONFIG_ENVS.REDIS_URI, app, None
    )
    metrics_kwargs = _captured_timeouts(
        probe_metrics_redis, CONFIG_ENVS.METRICS_REDIS_URI, app, None
    )
    assert session_kwargs["socket_timeout"] <= 2 / SESSION_REDIS_OPERATION_COUNT
    assert metrics_kwargs["socket_timeout"] <= 2 / METRICS_REDIS_OPERATION_COUNT


def test_probe_logs_never_contain_password_or_token(
    app: Flask, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    with _closed_port_uri(password=_REDIS_PASSWORD) as uri:
        with patch.dict(
            app.config,
            {CONFIG_ENVS.REDIS_URI: uri, CONFIG_ENVS.METRICS_REDIS_URI: uri},
        ):
            with app.app_context():
                assert probe_session_redis() == STATUS_DOWN
                assert probe_metrics_redis() == STATUS_DOWN
                assert (
                    health_checks.is_health_token_valid(_WRONG_TOKEN, "other-token")
                    is False
                )
    assert caplog.records
    for record in caplog.records:
        message = record.getMessage()
        assert _REDIS_PASSWORD not in message
        assert _WRONG_TOKEN not in message


_TRICKY_PASSWORD = "pa/ss@word"


def test_redis_failure_log_masks_password_in_exception_text(
    app: Flask, caplog: pytest.LogCaptureFixture
) -> None:
    uri = f"redis://:{_TRICKY_PASSWORD}@127.0.0.1:1/0"
    caplog.set_level(logging.DEBUG)
    with patch.dict(app.config, {CONFIG_ENVS.REDIS_URI: uri}):
        with app.app_context():
            with patch.object(Redis, "from_url", side_effect=Exception(f"bad {uri}")):
                assert probe_session_redis() == STATUS_DOWN
    messages = [record.getMessage() for record in caplog.records]
    assert any("***@" in message for message in messages)
    for message in messages:
        assert _TRICKY_PASSWORD not in message
        assert "ss@word" not in message


def test_postgres_failure_log_masks_password_in_exception_text(
    app: Flask, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    error = Exception(f"could not connect postgresql://u4i:{_TRICKY_PASSWORD}@db/x")
    with app.app_context():
        with patch.object(health_checks, "create_engine", side_effect=error):
            assert probe_postgres() == STATUS_DOWN
    messages = [record.getMessage() for record in caplog.records]
    assert any("***@" in message for message in messages)
    for message in messages:
        assert _TRICKY_PASSWORD not in message


def test_redis_probe_closes_client_on_failure(app: Flask) -> None:
    client = MagicMock()
    client.ping.side_effect = Exception("boom")
    with patch.dict(app.config, {CONFIG_ENVS.REDIS_URI: "redis://127.0.0.1:1/0"}):
        with app.app_context():
            with patch.object(Redis, "from_url", return_value=client):
                assert probe_session_redis() == STATUS_DOWN
    client.close.assert_called_once()


def test_real_zero_budget_is_down_without_clients(app: Flask) -> None:
    with patch.dict(
        app.config,
        {
            CONFIG_ENVS.REDIS_URI: "redis://127.0.0.1:1/0",
            CONFIG_ENVS.METRICS_REDIS_URI: "redis://127.0.0.1:1/0",
        },
    ):
        with app.app_context():
            with patch.object(Redis, "from_url") as redis_spy:
                with patch.object(health_checks, "create_engine") as engine_spy:
                    assert probe_session_redis(Budget.start(0)) == STATUS_DOWN
                    assert probe_metrics_redis(Budget.start(0)) == STATUS_DOWN
                    assert probe_postgres(Budget.start(0)) == STATUS_DOWN
    redis_spy.assert_not_called()
    engine_spy.assert_not_called()


def test_get_missing_tables_default_inspects_engine(app: Flask) -> None:
    with app.app_context():
        with patch("backend.db.inspect") as inspect_spy:
            inspect_spy.return_value.get_table_names.return_value = []
            get_missing_tables()
        inspect_spy.assert_called_once_with(db.engine)


def test_get_missing_tables_with_connection_inspects_connection(app: Flask) -> None:
    connection = MagicMock()
    with app.app_context():
        with patch("backend.db.inspect") as inspect_spy:
            inspect_spy.return_value.get_table_names.return_value = []
            get_missing_tables(connection=connection)
    inspect_spy.assert_called_once_with(connection)


def test_get_missing_tables_rejects_positional_argument(app: Flask) -> None:
    with app.app_context():
        with pytest.raises(TypeError):
            get_missing_tables(MagicMock())  # type: ignore[misc]
