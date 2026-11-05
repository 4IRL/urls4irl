"""Unit coverage for the standalone ``__main__`` entrypoint of ``scripts/purge_invite_links.py``.

Runs the script as ``__main__`` with ``psycopg2.connect`` patched, so no database
is needed. The DB behaviour of ``run_purge`` is covered by the integration tests
under ``tests/integration/invite_links/``.
"""

from __future__ import annotations

import os
import runpy
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import psycopg2
import pytest

from scripts import purge_invite_links

pytestmark = pytest.mark.unit

_PG_ENV_KEYS: tuple[str, ...] = (
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
)
_SCRIPT_PATH: str = purge_invite_links.__file__


@pytest.fixture(autouse=True)
def isolated_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swap ``os.environ`` for a scrubbed copy: the loader writes to it directly."""
    monkeypatch.setattr(os, "environ", os.environ.copy())
    for env_key in _PG_ENV_KEYS:
        monkeypatch.delenv(env_key, raising=False)


def _run_script_as_main() -> int:
    """Execute purge_invite_links.py as ``__main__`` and return its exit code."""
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
    WHEN purge_invite_links.py runs as __main__
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
    WHEN purge_invite_links.py runs as __main__
    THEN it rolls back once, closes the connection once and exits 1
    """
    mock_connection = _patch_connection(monkeypatch)
    mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
    mock_cursor.execute.side_effect = RuntimeError("boom")

    assert _run_script_as_main() == 1

    mock_connection.rollback.assert_called_once()
    mock_connection.commit.assert_not_called()
    mock_connection.close.assert_called_once()


def test_main_exits_one_when_the_connection_cannot_be_built(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN missing POSTGRES_* vars and no usable env dump
    WHEN purge_invite_links.py runs as __main__
    THEN it exits 1 without connecting
    """
    connect_mock = MagicMock()
    monkeypatch.setattr(psycopg2, "connect", connect_mock)
    # The re-executed script binds its own default dump path, so make any dump absent.
    monkeypatch.setattr(Path, "is_file", lambda self: False)

    assert _run_script_as_main() == 1

    connect_mock.assert_not_called()
