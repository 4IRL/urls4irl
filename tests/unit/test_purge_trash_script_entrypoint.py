"""Unit coverage for the standalone entrypoint of ``scripts/purge_trash.py``.

Covers the container env-dump loader, the connection builder and the ``__main__``
exit codes (0 on success, 1 on failure) with ``psycopg2.connect`` patched, so no
database is needed. The DB behaviour of ``run_trash_purge`` is covered by the
integration tests under ``tests/integration/trash/``.
"""

from __future__ import annotations

import logging
import os
import runpy
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import psycopg2
import pytest

from scripts import purge_trash

pytestmark = pytest.mark.unit

_PG_ENV_KEYS: tuple[str, ...] = (
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
)
_SCRIPT_PATH: str = purge_trash.__file__


@pytest.fixture(autouse=True)
def isolated_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swap ``os.environ`` for a scrubbed copy: the loader writes to it directly."""
    monkeypatch.setattr(os, "environ", os.environ.copy())
    for env_key in _PG_ENV_KEYS:
        monkeypatch.delenv(env_key, raising=False)


def _write_dump(tmp_path: Path, content: str) -> Path:
    dump_path = tmp_path / "container_environment"
    dump_path.write_text(content, encoding="utf-8")
    return dump_path


def test_load_env_from_container_dump_sets_missing_keys(tmp_path: Path) -> None:
    """
    GIVEN a container env dump with KEY=value lines, a comment, a blank line and a
        line with no "="
    WHEN _load_env_from_container_dump reads it
    THEN each KEY=value entry is set (value split on the first "=") and the rest is
        ignored
    """
    dump_path = _write_dump(
        tmp_path,
        "# comment\n\nPOSTGRES_USER=dump_user\nPOSTGRES_PASSWORD=pw=with=equals\nnot a pair\n",
    )

    purge_trash._load_env_from_container_dump(str(dump_path))

    assert os.environ["POSTGRES_USER"] == "dump_user"
    assert os.environ["POSTGRES_PASSWORD"] == "pw=with=equals"
    assert "not a pair" not in os.environ


def test_load_env_from_container_dump_keeps_existing_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN POSTGRES_USER already set in the environment and a dump that also sets it
    WHEN _load_env_from_container_dump reads the dump
    THEN the existing value wins and the dump only fills the missing keys
    """
    monkeypatch.setenv("POSTGRES_USER", "real_override")
    dump_path = _write_dump(tmp_path, "POSTGRES_USER=dump_user\nPOSTGRES_DB=dump_db\n")

    purge_trash._load_env_from_container_dump(str(dump_path))

    assert os.environ["POSTGRES_USER"] == "real_override"
    assert os.environ["POSTGRES_DB"] == "dump_db"


def test_load_env_from_container_dump_missing_file_is_a_noop(tmp_path: Path) -> None:
    """
    GIVEN a dump path that does not exist
    WHEN _load_env_from_container_dump runs
    THEN it returns without raising or changing the environment
    """
    environ_before = dict(os.environ)

    purge_trash._load_env_from_container_dump(str(tmp_path / "absent"))

    assert dict(os.environ) == environ_before


@pytest.mark.parametrize(
    "missing_key", ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"]
)
def test_build_pg_conn_from_env_requires_credentials(
    missing_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN two of the three required POSTGRES_* vars set and no usable env dump
    WHEN _build_pg_conn_from_env runs
    THEN it raises RuntimeError and never connects
    """
    for env_key in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
        if env_key != missing_key:
            monkeypatch.setenv(env_key, "value")
    monkeypatch.setattr(purge_trash, "_load_env_from_container_dump", lambda: None)
    connect_mock = MagicMock()
    monkeypatch.setattr(psycopg2, "connect", connect_mock)

    with pytest.raises(RuntimeError, match="are required"):
        purge_trash._build_pg_conn_from_env()

    connect_mock.assert_not_called()


def test_build_pg_conn_from_env_defaults_host_and_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN the required POSTGRES_* vars and no POSTGRES_HOST or POSTGRES_PORT
    WHEN _build_pg_conn_from_env runs
    THEN it connects to host "db" on port 5432 with the given credentials
    """
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    connect_mock = MagicMock()
    monkeypatch.setattr(psycopg2, "connect", connect_mock)

    returned_connection = purge_trash._build_pg_conn_from_env()

    connect_mock.assert_called_once_with(
        host="db", port=5432, user="u", password="p", dbname="d"
    )
    assert returned_connection is connect_mock.return_value


def test_build_pg_conn_from_env_honors_host_and_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN POSTGRES_HOST and POSTGRES_PORT set alongside the required vars
    WHEN _build_pg_conn_from_env runs
    THEN it connects to that host and the port as an int
    """
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    monkeypatch.setenv("POSTGRES_HOST", "pg.example")
    monkeypatch.setenv("POSTGRES_PORT", "6543")
    connect_mock = MagicMock()
    monkeypatch.setattr(psycopg2, "connect", connect_mock)

    purge_trash._build_pg_conn_from_env()

    connect_mock.assert_called_once_with(
        host="pg.example", port=6543, user="u", password="p", dbname="d"
    )


def test_build_pg_conn_from_env_falls_back_to_the_env_dump(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN no POSTGRES_* vars in the environment but a container env dump holding them
    WHEN _build_pg_conn_from_env runs
    THEN it loads the dump and connects with its credentials
    """
    dump_path = _write_dump(
        tmp_path,
        "POSTGRES_USER=du\nPOSTGRES_PASSWORD=dp\nPOSTGRES_DB=dd\n",
    )
    original_loader = purge_trash._load_env_from_container_dump
    monkeypatch.setattr(
        purge_trash,
        "_load_env_from_container_dump",
        lambda: original_loader(str(dump_path)),
    )
    connect_mock = MagicMock()
    monkeypatch.setattr(psycopg2, "connect", connect_mock)

    purge_trash._build_pg_conn_from_env()

    connect_mock.assert_called_once_with(
        host="db", port=5432, user="du", password="dp", dbname="dd"
    )


def _run_script_as_main() -> int:
    """Execute purge_trash.py as ``__main__`` and return its exit code."""
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(_SCRIPT_PATH, run_name="__main__")
    exit_code: Any = exit_info.value.code
    return exit_code


def _patch_connection(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Patch psycopg2.connect to return a mock connection whose purge finds no rows."""
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    mock_connection = MagicMock()
    mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
    mock_cursor.rowcount = 0
    mock_cursor.fetchall.return_value = []
    monkeypatch.setattr(psycopg2, "connect", MagicMock(return_value=mock_connection))
    return mock_connection


def test_main_exits_zero_and_closes_the_connection_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a patched psycopg2.connect whose purge finds nothing to delete
    WHEN purge_trash.py runs as __main__
    THEN it commits, closes the connection and exits 0
    """
    mock_connection = _patch_connection(monkeypatch)

    assert _run_script_as_main() == 0

    mock_connection.commit.assert_called_once()
    mock_connection.close.assert_called_once()


def test_main_exits_one_and_closes_the_connection_when_the_purge_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a patched connection whose cursor raises during the purge
    WHEN purge_trash.py runs as __main__
    THEN it rolls back, closes the connection and exits 1
    """
    mock_connection = _patch_connection(monkeypatch)
    mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
    mock_cursor.execute.side_effect = RuntimeError("boom")

    assert _run_script_as_main() == 1

    mock_connection.rollback.assert_called_once()
    mock_connection.close.assert_called_once()


def test_run_trash_purge_reraises_the_original_error_when_rollback_also_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    GIVEN a connection whose cursor raises RuntimeError("boom") and whose rollback
        raises a different error
    WHEN run_trash_purge runs
    THEN it re-raises the original RuntimeError (not the rollback error) and logs a
        warning about the failed rollback
    """
    mock_connection = MagicMock()
    mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
    mock_cursor.execute.side_effect = RuntimeError("boom")
    mock_connection.rollback.side_effect = ConnectionError("rollback failed")

    with caplog.at_level(logging.WARNING, logger="trash_purge"):
        with pytest.raises(RuntimeError, match="boom"):
            purge_trash.run_trash_purge(pg_conn=mock_connection)

    mock_connection.rollback.assert_called_once()
    mock_connection.commit.assert_not_called()
    assert "trash purge rollback failed: rollback failed" in caplog.text


def test_main_exits_one_when_the_connection_cannot_be_built(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN missing POSTGRES_* vars and no usable env dump
    WHEN purge_trash.py runs as __main__
    THEN it exits 1 without connecting
    """
    connect_mock = MagicMock()
    monkeypatch.setattr(psycopg2, "connect", connect_mock)
    # The re-executed script binds its own default dump path, so make any dump absent.
    monkeypatch.setattr(Path, "is_file", lambda self: False)

    assert _run_script_as_main() == 1

    connect_mock.assert_not_called()
