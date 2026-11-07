"""Integration test for the a9c3e5b7d1f4 migration: ``UtubMembers.pinnedAt``.

Exercises the upgrade -> downgrade -> upgrade roundtrip against a real seeded
dataset, proving the nullable ``pinnedAt`` column is created on upgrade with
every existing row unpinned and dropped on downgrade.
"""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, inspect, select, table, text
from sqlalchemy.engine import Connection

from backend import db, migrate
from backend.models.utub_members import Utub_Members
from tests.integration.cli.utils import assert_row_counts_match_ignoring_new_tables

pytestmark = pytest.mark.cli

_PRE_REVISION: str = "d7a2e4c6f8b1"
_PINNED_REVISION: str = "a9c3e5b7d1f4"
_UTUB_MEMBERS_TABLE: str = "UtubMembers"
_USERS_TABLE: str = "Users"
_UTUBS_TABLE: str = "Utubs"
_ALEMBIC_VERSION_TABLE: str = "alembic_version"
_COLUMN_NAME: str = "pinnedAt"

_MANAGEDB_DROP_ARGS: list[str] = ["managedb", "drop", "test"]
_ADDMOCK_ALL_ARGS: list[str] = ["addmock", "all"]


def _build_alembic_config() -> Config:
    alembic_config = Config("./migrations/alembic.ini")
    alembic_config.set_main_option("script_location", "migrations/")
    return alembic_config


def _capture_row_counts(connection: Connection) -> dict[str, int]:
    """Return a per-table row count for every persisted table except the
    Alembic bookkeeping table, keyed by table name."""
    inspector = inspect(connection)
    row_counts: dict[str, int] = {}
    for table_name in inspector.get_table_names():
        if table_name == _ALEMBIC_VERSION_TABLE:
            continue
        row_counts[table_name] = connection.execute(
            select(func.count()).select_from(table(table_name))
        ).scalar_one()
    return row_counts


def _get_column_info(connection: Connection) -> dict | None:
    """Return the inspector description of ``UtubMembers.pinnedAt``, or None."""
    columns = inspect(connection).get_columns(_UTUB_MEMBERS_TABLE)
    return next((column for column in columns if column["name"] == _COLUMN_NAME), None)


def _assert_models_match_migrated_schema(connection: Connection) -> None:
    """Compare the model's declared column with the migrated database's column."""
    model_column = Utub_Members.__table__.columns[_COLUMN_NAME]
    assert model_column.nullable is True
    assert model_column.type.timezone is True

    column_info = _get_column_info(connection)
    assert column_info is not None
    assert column_info["nullable"] is True
    assert getattr(column_info["type"], "timezone", False) is True
    assert (
        connection.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = :table_name AND column_name = :column_name"
            ),
            {"table_name": _UTUB_MEMBERS_TABLE, "column_name": _COLUMN_NAME},
        ).scalar_one()
        == "timestamp with time zone"
    )


def test_add_pinned_at_migration_roundtrips_unpinned(runner) -> None:
    """
    GIVEN a database upgraded to head and seeded with the full mock dataset
        via ``flask addmock all``
    WHEN the a9c3e5b7d1f4 migration is downgraded and re-applied
    THEN ``UtubMembers.pinnedAt`` is a nullable timestamptz matching the
        model, every row reads NULL after the upgrade, the downgrade drops the
        column, and row counts never change.

    Args:
        runner (pytest.fixture): Provides a Flask application and a FlaskCLIRunner.
    """
    script_directory = ScriptDirectory.from_config(_build_alembic_config())
    script = script_directory.get_revision(_PINNED_REVISION)
    assert script.down_revision == _PRE_REVISION
    assert script_directory.get_heads() == [_PINNED_REVISION]
    os.environ["PYTEST_RUNNING"] = "1"
    flask_app, cli_runner = runner
    migrate.init_app(flask_app)

    try:
        cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)

        with flask_app.app_context():
            command.upgrade(_build_alembic_config(), "head")
            cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)

            with db.engine.connect() as connection:
                assert _get_column_info(connection) is not None
                assert (
                    connection.execute(
                        text(
                            'SELECT COUNT(*) FROM "UtubMembers" '
                            'WHERE "pinnedAt" IS NOT NULL'
                        )
                    ).scalar_one()
                    == 0
                )
                row_counts_before = _capture_row_counts(connection)
            assert row_counts_before[_USERS_TABLE] > 0
            assert row_counts_before[_UTUBS_TABLE] > 0
            assert row_counts_before[_UTUB_MEMBERS_TABLE] > 0

            with db.engine.begin() as connection:
                connection.execute(
                    text(
                        'UPDATE "UtubMembers" SET "pinnedAt" = now() '
                        'WHERE ctid = (SELECT ctid FROM "UtubMembers" LIMIT 1)'
                    )
                )

            command.downgrade(_build_alembic_config(), _PRE_REVISION)

            with db.engine.connect() as connection:
                assert _get_column_info(connection) is None
                row_counts_after_downgrade = _capture_row_counts(connection)
            assert_row_counts_match_ignoring_new_tables(
                row_counts_before, row_counts_after_downgrade
            )

            command.upgrade(_build_alembic_config(), "head")

            with db.engine.connect() as connection:
                _assert_models_match_migrated_schema(connection)
                assert (
                    connection.execute(
                        text(
                            'SELECT COUNT(*) FROM "UtubMembers" '
                            'WHERE "pinnedAt" IS NOT NULL'
                        )
                    ).scalar_one()
                    == 0
                )
                row_counts_after_upgrade = _capture_row_counts(connection)
            assert_row_counts_match_ignoring_new_tables(
                row_counts_after_upgrade, row_counts_after_downgrade
            )

            # Recreate any tables the migrations left absent so the runner
            # fixture teardown operates against the full schema.
            db.create_all()
    finally:
        del os.environ["PYTEST_RUNNING"]
