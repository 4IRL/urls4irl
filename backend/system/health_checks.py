from __future__ import annotations

import hmac
import re
import time

from flask import current_app
from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from backend import db
from backend.app_logger import info_log, warning_log
from backend.db import get_missing_tables
from backend.utils.strings.config_strs import CONFIG_ENVS

STATUS_UP: str = "up"
STATUS_DOWN: str = "down"
STATUS_NOT_CONFIGURED: str = "not configured"

MEMORY_URI: str = "memory://"

# Per-operation cap for any single bounded step of a probe.
PROBE_TIMEOUT_SECONDS: int = 2
# Overall deadline for one deep health call (under the watchdog's 10 s timeout).
DEEP_CHECK_DEADLINE_SECONDS: int = 7

# Known bounded operation counts used to apportion a probe's budget.
POSTGRES_STATEMENT_COUNT: int = 4
SESSION_REDIS_OPERATION_COUNT: int = 3
METRICS_REDIS_OPERATION_COUNT: int = 4
# libpq connect_timeout is an integer of at least 2 s (0 means unbounded).
POSTGRES_CONNECT_TIMEOUT_SECONDS: int = 2
POSTGRES_MIN_BUDGET_SECONDS: int = 3
POSTGRES_DEFAULT_BUDGET_SECONDS: int = 6

_MS_PER_SECOND: int = 1000
# Greedy up to the last "@" before whitespace, so a password containing "/" or
# an unencoded "@" is fully hidden.
_URI_USERINFO_PATTERN = re.compile(r"(\w+://)\S*@")
_MASKED_USERINFO: str = r"\1***@"


class Budget:
    """A monotonic-clock deadline shared by consecutive probes."""

    def __init__(self, deadline: float) -> None:
        self._deadline = deadline

    @classmethod
    def start(cls, total_seconds: float | None = None) -> Budget:
        if total_seconds is None:
            total_seconds = DEEP_CHECK_DEADLINE_SECONDS
        return cls(time.monotonic() + total_seconds)

    def remaining(self) -> float:
        return self._deadline - time.monotonic()


def _remaining_seconds(budget: Budget | None, *, default: float) -> float:
    return default if budget is None else budget.remaining()


def mask_userinfo(message: str) -> str:
    """Hide ``scheme://user:password@`` credentials in an exception message."""
    return _URI_USERINFO_PATTERN.sub(_MASKED_USERINFO, message)


def _log_failure(probe_name: str, error: Exception, started_at: float) -> None:
    warning_log(
        f"health probe {probe_name}: down after "
        f"{time.monotonic() - started_at:.3f}s: "
        f"{type(error).__name__}: {mask_userinfo(str(error))}"
    )


def _log_result(probe_name: str, status: str, started_at: float) -> None:
    info_log(
        f"health probe {probe_name}: {status} in {time.monotonic() - started_at:.3f}s"
    )


def bounded_redis_client(
    uri: str, *, operation_count: int, budget: Budget | None = None
) -> Redis | None:
    """Build a short-lived Redis client whose per-operation timeouts, summed over
    ``operation_count`` steps, fit in the budget. ``None`` when no time is left.
    """
    remaining = _remaining_seconds(budget, default=PROBE_TIMEOUT_SECONDS)
    if remaining <= 0:
        return None
    timeout = min(PROBE_TIMEOUT_SECONDS, remaining / operation_count)
    return Redis.from_url(uri, socket_timeout=timeout, socket_connect_timeout=timeout)


def _close_redis(client: Redis | None) -> None:
    if client is None:
        return
    try:
        client.close()
    except Exception:
        pass


def _probe_redis(
    probe_name: str, uri: str | None, operation_count: int, budget: Budget | None
) -> str:
    if not uri or uri == MEMORY_URI:
        return STATUS_NOT_CONFIGURED
    started_at = time.monotonic()
    client: Redis | None = None
    status = STATUS_DOWN
    try:
        client = bounded_redis_client(
            uri, operation_count=operation_count, budget=budget
        )
        if client is None:
            warning_log(f"health probe {probe_name}: down, no time budget left")
            return STATUS_DOWN
        client.ping()
        status = STATUS_UP
    except Exception as redis_error:
        _log_failure(probe_name, redis_error, started_at)
    finally:
        _close_redis(client)
    if status == STATUS_UP:
        _log_result(probe_name, status, started_at)
    return status


def probe_session_redis(budget: Budget | None = None) -> str:
    return _probe_redis(
        "session_redis",
        current_app.config.get(CONFIG_ENVS.REDIS_URI),
        SESSION_REDIS_OPERATION_COUNT,
        budget,
    )


def probe_metrics_redis(budget: Budget | None = None) -> str:
    return _probe_redis(
        "metrics_redis",
        current_app.config.get(CONFIG_ENVS.METRICS_REDIS_URI),
        METRICS_REDIS_OPERATION_COUNT,
        budget,
    )


def probe_postgres(budget: Budget | None = None) -> str:
    """``up`` when ``SELECT 1`` works and no model table is missing, checked on
    one dedicated short-lived connection (never the shared session or pool)."""
    remaining = _remaining_seconds(budget, default=POSTGRES_DEFAULT_BUDGET_SECONDS)
    if remaining < POSTGRES_MIN_BUDGET_SECONDS:
        warning_log("health probe postgres: down, not enough time budget left")
        return STATUS_DOWN
    statement_timeout_ms = int(
        (remaining - POSTGRES_CONNECT_TIMEOUT_SECONDS)
        * _MS_PER_SECOND
        / POSTGRES_STATEMENT_COUNT
    )
    started_at = time.monotonic()
    engine = None
    connection = None
    status = STATUS_DOWN
    try:
        engine = create_engine(
            db.engine.url,
            poolclass=NullPool,
            connect_args={
                "connect_timeout": POSTGRES_CONNECT_TIMEOUT_SECONDS,
                "options": f"-c statement_timeout={statement_timeout_ms}",
            },
        )
        connection = engine.connect()
        connection.execute(text("SELECT 1"))
        missing_tables = get_missing_tables(connection=connection)
        if missing_tables:
            warning_log(
                f"health probe postgres: down, {len(missing_tables)} missing tables"
            )
        else:
            status = STATUS_UP
    except Exception as database_error:
        _log_failure("postgres", database_error, started_at)
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                pass
    if status == STATUS_UP:
        _log_result("postgres", status, started_at)
    return status


def is_health_token_valid(provided: str | None, expected: str | None) -> bool:
    authorized = False
    if expected is None or not expected.strip():
        return authorized
    if not provided:
        return authorized
    if hmac.compare_digest(
        provided.encode("utf-8", "surrogatepass"),
        expected.strip().encode("utf-8", "surrogatepass"),
    ):
        authorized = True
    return authorized
