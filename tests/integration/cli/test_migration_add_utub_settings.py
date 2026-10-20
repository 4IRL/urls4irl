"""Integration test for the add_utub_settings migration: add settings to Utubs.

Exercises the upgrade -> downgrade -> upgrade roundtrip against a real seeded
dataset, proving the migration is reversible without row loss.
"""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Connection

from backend import db, migrate
from tests.integration.cli.utils import assert_row_counts_match_ignoring_new_tables

pytestmark = pytest.mark.cli

_PRE_SETTINGS_REVISION: str = "b6f2d8a4c1e7"
_UTUBS_TABLE: str = "Utubs"
_USERS_TABLE: str = "Users"
_ALEMBIC_VERSION_TABLE: str = "alembic_version"
_SETTINGS_COLUMN: str = "settings"

_MANAGEDB_DROP_ARGS: list[str] = ["managedb", "drop", "test"]
_ADDMOCK_ALL_ARGS: list[str] = ["addmock", "all"]


def _build_alembic_config() -> Config:
    alembic_config = Config("./migrations/alembic.ini")
    alembic_config.set_main_option("script_location", "migrations/")
    return alembic_config


def _capture_row_counts(connection: Connection) -> dict[str, int]:
    """Return a per-table row count for every table except Alembic bookkeeping."""
    inspector = inspect(connection)
    row_counts: dict[str, int] = {}
    for table_name in inspector.get_table_names():
        if table_name == _ALEMBIC_VERSION_TABLE:
            continue
        row_counts[table_name] = connection.execute(
            text(f'SELECT COUNT(*) FROM "{table_name}"')
        ).scalar_one()
    return row_counts


def _get_settings_column(connection: Connection) -> dict | None:
    inspector = inspect(connection)
    for column in inspector.get_columns(_UTUBS_TABLE):
        if column["name"] == _SETTINGS_COLUMN:
            return column
    return None


def test_add_utub_settings_migration_upgrade_and_downgrade(runner):
    """
    GIVEN a database upgraded to head and seeded via ``flask addmock all``,
        with one Utubs row holding a non-NULL settings value
    WHEN the add_utub_settings migration is downgraded to b6f2d8a4c1e7 and
        re-applied to head
    THEN the column is absent after downgrade, row counts are preserved, and
        after re-upgrade the column is nullable JSONB with every row NULL.

    Args:
        runner (pytest.fixture): Provides a Flask application and a FlaskCLIRunner.
    """
    os.environ["PYTEST_RUNNING"] = "1"
    flask_app, cli_runner = runner
    migrate.init_app(flask_app)

    cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)

    with flask_app.app_context():
        alembic_config = _build_alembic_config()
        script = ScriptDirectory.from_config(alembic_config)
        assert len(script.get_heads()) == 1
        head_revision = script.get_heads()[0]
        assert script.get_revision(head_revision).down_revision == (
            _PRE_SETTINGS_REVISION
        )

        command.upgrade(alembic_config, "head")

        with db.engine.connect() as connection:
            assert _get_settings_column(connection) is not None

        cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)

        with db.engine.begin() as connection:
            connection.execute(
                text(
                    'UPDATE "Utubs" SET settings = \'{"urls": {}}\'::jsonb '
                    'WHERE id = (SELECT MIN(id) FROM "Utubs")'
                )
            )

        with db.engine.connect() as connection:
            row_counts_before_roundtrip = _capture_row_counts(connection)
            non_null_count = connection.execute(
                text('SELECT COUNT(*) FROM "Utubs" WHERE settings IS NOT NULL')
            ).scalar_one()
        assert row_counts_before_roundtrip[_USERS_TABLE] > 0
        assert row_counts_before_roundtrip[_UTUBS_TABLE] > 0
        assert non_null_count == 1

        command.downgrade(alembic_config, _PRE_SETTINGS_REVISION)

        with db.engine.connect() as connection:
            assert _get_settings_column(connection) is None
            row_counts_after_downgrade = _capture_row_counts(connection)
        assert_row_counts_match_ignoring_new_tables(
            row_counts_before_roundtrip, row_counts_after_downgrade
        )

        command.upgrade(alembic_config, "head")

        with db.engine.connect() as connection:
            settings_column = _get_settings_column(connection)
            assert settings_column is not None
            assert isinstance(settings_column["type"], JSONB)
            assert settings_column["nullable"] is True
            non_null_after = connection.execute(
                text('SELECT COUNT(*) FROM "Utubs" WHERE settings IS NOT NULL')
            ).scalar_one()
            row_counts_after_reupgrade = _capture_row_counts(connection)
        assert non_null_after == 0
        assert_row_counts_match_ignoring_new_tables(
            row_counts_before_roundtrip, row_counts_after_reupgrade
        )

        db.create_all()

    del os.environ["PYTEST_RUNNING"]
