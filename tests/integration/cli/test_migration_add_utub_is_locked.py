"""Integration test for the f3d5a7c9e1b2 migration: add isLocked to Utubs.

Exercises the downgrade → upgrade roundtrip against a real seeded dataset,
proving the migration is reversible without data loss.
"""

from __future__ import annotations

import os

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from backend import db, migrate

pytestmark = pytest.mark.cli

_PRE_IS_LOCKED_REVISION: str = "09f8ae70fc61"
_UTUBS_TABLE: str = "Utubs"
_USERS_TABLE: str = "Users"
_ALEMBIC_VERSION_TABLE: str = "alembic_version"
_ISLOCKED_COLUMN: str = "isLocked"

_MANAGEDB_DROP_ARGS: list[str] = ["managedb", "drop", "test"]
_ADDMOCK_ALL_ARGS: list[str] = ["addmock", "all"]


def _build_alembic_config() -> Config:
    alembic_config = Config("./migrations/alembic.ini")
    alembic_config.set_main_option("script_location", "migrations/")
    alembic_config.attributes["connection"] = db.engine.connect()
    return alembic_config


def _capture_row_counts(connection: Connection) -> dict[str, int]:
    """Return a per-table row count for every persisted table except the
    Alembic bookkeeping table, keyed by table name.

    Used to prove the roundtrip preserves the seeded dataset without relying
    on hardcoded counts (drift-proof, per CLAUDE.md).

    Args:
        connection: Active SQLAlchemy engine connection.

    Returns:
        Mapping of table name to row count.
    """
    inspector = inspect(connection)
    row_counts: dict[str, int] = {}
    for table_name in inspector.get_table_names():
        if table_name == _ALEMBIC_VERSION_TABLE:
            continue
        row_counts[table_name] = connection.execute(
            text(f'SELECT COUNT(*) FROM "{table_name}"')
        ).scalar_one()
    return row_counts


def _get_utubs_column_names(connection: Connection) -> set[str]:
    inspector = inspect(connection)
    return {col["name"] for col in inspector.get_columns(_UTUBS_TABLE)}


def test_add_utub_is_locked_migration_upgrade_and_downgrade(runner):
    """
    GIVEN a database upgraded to head and seeded with the full mock dataset
        via ``flask addmock all``
    WHEN the f3d5a7c9e1b2 migration is downgraded to 09f8ae70fc61 and then
        re-applied to head
    THEN the isLocked column is present with all rows False at head; the
        column is absent after downgrade; all seeded rows survive the
        down/up roundtrip (row-count equality); existing rows default to
        False on re-upgrade — confirming the migration is reversible against
        the real seeded dataset (per CLAUDE.md).

    Args:
        runner (pytest.fixture): Provides a Flask application and a FlaskCLIRunner.
    """
    os.environ["PYTEST_RUNNING"] = "1"
    flask_app, cli_runner = runner
    migrate.init_app(flask_app)

    cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)

    with flask_app.app_context():
        # Start at head so addmock all runs against a complete schema
        # (isLocked column already exists — no RETURNING-clause failures).
        command.upgrade(_build_alembic_config(), "head")

        with db.engine.connect() as connection:
            assert _ISLOCKED_COLUMN in _get_utubs_column_names(connection)

        cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)

        with db.engine.connect() as connection:
            row_counts_before_roundtrip = _capture_row_counts(connection)
        assert row_counts_before_roundtrip[_USERS_TABLE] > 0
        assert row_counts_before_roundtrip[_UTUBS_TABLE] > 0

        with db.engine.connect() as connection:
            locked_count = connection.execute(
                text('SELECT COUNT(*) FROM "Utubs" WHERE "isLocked" = TRUE')
            ).scalar_one()
        assert locked_count == 0

        command.downgrade(_build_alembic_config(), _PRE_IS_LOCKED_REVISION)

        with db.engine.connect() as connection:
            assert _ISLOCKED_COLUMN not in _get_utubs_column_names(connection)
            row_counts_after_downgrade = _capture_row_counts(connection)
        assert row_counts_after_downgrade == row_counts_before_roundtrip

        command.upgrade(_build_alembic_config(), "head")

        with db.engine.connect() as connection:
            assert _ISLOCKED_COLUMN in _get_utubs_column_names(connection)
            # Existing rows must receive the server default (false) on re-upgrade.
            relocked_count = connection.execute(
                text('SELECT COUNT(*) FROM "Utubs" WHERE "isLocked" = TRUE')
            ).scalar_one()
        assert relocked_count == 0

        # Schema is fully migrated to head; recreate any tables the
        # migrations left absent so the runner fixture teardown operates
        # against the full schema for subsequent tests.
        db.create_all()

    del os.environ["PYTEST_RUNNING"]
