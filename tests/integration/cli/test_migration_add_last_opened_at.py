"""Integration test for the c4e8a1f3b7d2 migration: ``UtubMembers.lastOpenedAt``.

Exercises the upgrade -> downgrade -> reseed -> upgrade roundtrip against a
real seeded dataset, proving the nullable ``lastOpenedAt`` column is created on
upgrade (backfilled from ``Utubs.lastUpdated``) and dropped on downgrade.
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

_PRE_REVISION: str = "d7b2c4e8a1f3"
_LAST_OPENED_REVISION: str = "c4e8a1f3b7d2"
_UTUB_MEMBERS_TABLE: str = "UtubMembers"
_USERS_TABLE: str = "Users"
_UTUBS_TABLE: str = "Utubs"
_ALEMBIC_VERSION_TABLE: str = "alembic_version"
_COLUMN_NAME: str = "lastOpenedAt"

_MANAGEDB_DROP_ARGS: list[str] = ["managedb", "drop", "test"]
_ADDMOCK_ALL_ARGS: list[str] = ["addmock", "all"]


def _build_alembic_config() -> Config:
    alembic_config = Config("./migrations/alembic.ini")
    alembic_config.set_main_option("script_location", "migrations/")
    return alembic_config


def _capture_row_counts(connection: Connection) -> dict[str, int]:
    """Return a per-table row count for every persisted table except the
    Alembic bookkeeping table, keyed by table name.

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
            select(func.count()).select_from(table(table_name))
        ).scalar_one()
    return row_counts


def _get_column_info(connection: Connection) -> dict | None:
    """Return the inspector description of ``UtubMembers.lastOpenedAt``, or None."""
    columns = inspect(connection).get_columns(_UTUB_MEMBERS_TABLE)
    return next((column for column in columns if column["name"] == _COLUMN_NAME), None)


def _assert_models_match_migrated_schema(connection: Connection) -> None:
    """Compare the model's declared column with the migrated database's column.

    Normal tests build the schema from the models via ``db.create_all()``, so
    this is the only drift check between the model and the migration.
    """
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


def _seed_distinct_last_updated(connection: Connection) -> None:
    """Give every UTub a distinct ``lastUpdated`` via raw SQL."""
    connection.execute(
        text(
            'UPDATE "Utubs" SET "lastUpdated" = '
            "TIMESTAMPTZ '2026-01-01 00:00:00+00' + (id * INTERVAL '1 hour')"
        )
    )


def test_add_last_opened_at_migration_roundtrips_and_backfills(runner) -> None:
    """
    GIVEN a database upgraded to head and seeded with the full mock dataset
        via ``flask addmock all``, then downgraded to d7b2c4e8a1f3 (column
        absent) with distinct ``Utubs.lastUpdated`` values seeded via raw SQL
    WHEN the c4e8a1f3b7d2 migration is applied
    THEN ``UtubMembers.lastOpenedAt`` exists as a nullable timestamptz that
        matches the model, every member's value equals its UTub's
        ``lastUpdated``, and the downgrade drops the column without changing
        row counts - confirming the migration is reversible and backfills
        against the real seeded dataset (per CLAUDE.md).

    Args:
        runner (pytest.fixture): Provides a Flask application and a FlaskCLIRunner.
    """
    script = ScriptDirectory.from_config(_build_alembic_config()).get_revision(
        _LAST_OPENED_REVISION
    )
    assert script.down_revision == _PRE_REVISION
    os.environ["PYTEST_RUNNING"] = "1"
    flask_app, cli_runner = runner
    migrate.init_app(flask_app)

    try:
        cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)

        with flask_app.app_context():
            command.upgrade(_build_alembic_config(), "head")

            with db.engine.connect() as connection:
                assert _get_column_info(connection) is not None

            cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)

            with db.engine.connect() as connection:
                row_counts_before_roundtrip = _capture_row_counts(connection)
            # The post-roundtrip assertions are only meaningful if rows exist.
            assert row_counts_before_roundtrip[_USERS_TABLE] > 0
            assert row_counts_before_roundtrip[_UTUBS_TABLE] > 0
            assert row_counts_before_roundtrip[_UTUB_MEMBERS_TABLE] > 0

            command.downgrade(_build_alembic_config(), _PRE_REVISION)

            with db.engine.begin() as connection:
                assert _get_column_info(connection) is None
                _seed_distinct_last_updated(connection)
            with db.engine.connect() as connection:
                row_counts_after_downgrade = _capture_row_counts(connection)
            assert_row_counts_match_ignoring_new_tables(
                row_counts_before_roundtrip, row_counts_after_downgrade
            )

            command.upgrade(_build_alembic_config(), "head")

            with db.engine.connect() as connection:
                _assert_models_match_migrated_schema(connection)

                members_total = connection.execute(
                    text('SELECT COUNT(*) FROM "UtubMembers"')
                ).scalar_one()
                members_matching = connection.execute(
                    text(
                        'SELECT COUNT(*) FROM "UtubMembers" m '
                        'JOIN "Utubs" u ON u.id = m."utubID" '
                        'WHERE m."lastOpenedAt" = u."lastUpdated"'
                    )
                ).scalar_one()
                assert members_total > 0
                assert members_matching == members_total

                distinct_values = connection.execute(
                    text('SELECT COUNT(DISTINCT "lastOpenedAt") FROM "UtubMembers"')
                ).scalar_one()
                assert distinct_values > 1

                row_counts_after_upgrade = _capture_row_counts(connection)
            assert_row_counts_match_ignoring_new_tables(
                row_counts_after_upgrade, row_counts_after_downgrade
            )

            # Schema is fully migrated to head; recreate any tables the
            # migrations left absent so the runner fixture teardown operates
            # against the full schema for subsequent tests.
            db.create_all()
    finally:
        del os.environ["PYTEST_RUNNING"]
