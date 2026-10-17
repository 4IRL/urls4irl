"""Integration test for the b6f2d8a4c1e7 migration: ``UtubUrls.trashedTagNames``.

Exercises the upgrade -> downgrade -> upgrade roundtrip against a real seeded
dataset, proving the nullable JSONB ``trashedTagNames`` column is created on
upgrade (matching the model, NULL on every existing row) and dropped on
downgrade, without touching ``trashedTagIds`` or any row count.
"""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, inspect, select, table, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Connection

from backend import db, migrate
from backend.models.utub_urls import Utub_Urls
from tests.integration.cli.utils import assert_row_counts_match_ignoring_new_tables

pytestmark = pytest.mark.cli

_PRE_REVISION: str = "e5a1c7d9b3f2"
_TRASHED_TAG_NAMES_REVISION: str = "b6f2d8a4c1e7"
_UTUB_URLS_TABLE: str = "UtubUrls"
_USERS_TABLE: str = "Users"
_ALEMBIC_VERSION_TABLE: str = "alembic_version"
_COLUMN_NAME: str = "trashedTagNames"
_TAG_IDS_COLUMN_NAME: str = "trashedTagIds"

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


def _get_column_info(connection: Connection, column_name: str) -> dict | None:
    """Return the inspector description of the named UtubUrls column, or None."""
    columns = inspect(connection).get_columns(_UTUB_URLS_TABLE)
    return next((column for column in columns if column["name"] == column_name), None)


def _assert_models_match_migrated_schema(connection: Connection) -> None:
    """Compare the model's declared column with the migrated database's column.

    Normal tests build the schema from the models via ``db.create_all()``, so
    this is the only drift check between the model and the migration.
    """
    model_column = Utub_Urls.__table__.columns[_COLUMN_NAME]
    assert model_column.nullable is True
    assert isinstance(model_column.type, JSONB)

    column_info = _get_column_info(connection, _COLUMN_NAME)
    assert column_info is not None
    assert column_info["nullable"] is True
    assert isinstance(column_info["type"], JSONB)


def test_add_trashed_tag_names_migration_roundtrips(runner) -> None:
    """
    GIVEN a database upgraded to head and seeded with the full mock dataset via
        ``flask addmock all``
    WHEN the b6f2d8a4c1e7 migration is downgraded to e5a1c7d9b3f2 and upgraded
        again
    THEN ``UtubUrls.trashedTagNames`` is a nullable JSONB column matching the
        model after each upgrade, is gone after the downgrade, is NULL on every
        row after the re-upgrade, ``trashedTagIds`` survives, and per-table row
        counts are unchanged - confirming the migration is reversible and safe
        on existing rows against the real seeded dataset (per CLAUDE.md).

    Args:
        runner (pytest.fixture): Provides a Flask application and a FlaskCLIRunner.
    """
    script = ScriptDirectory.from_config(_build_alembic_config()).get_revision(
        _TRASHED_TAG_NAMES_REVISION
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
                _assert_models_match_migrated_schema(connection)

            cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)

            with db.engine.connect() as connection:
                row_counts_before_roundtrip = _capture_row_counts(connection)
            # The post-roundtrip assertions are only meaningful if rows exist.
            assert row_counts_before_roundtrip[_USERS_TABLE] > 0
            assert row_counts_before_roundtrip[_UTUB_URLS_TABLE] > 0

            command.downgrade(_build_alembic_config(), _PRE_REVISION)

            with db.engine.connect() as connection:
                assert _get_column_info(connection, _COLUMN_NAME) is None
                assert _get_column_info(connection, _TAG_IDS_COLUMN_NAME) is not None
                row_counts_after_downgrade = _capture_row_counts(connection)
            assert_row_counts_match_ignoring_new_tables(
                row_counts_before_roundtrip, row_counts_after_downgrade
            )

            command.upgrade(_build_alembic_config(), "head")

            with db.engine.connect() as connection:
                _assert_models_match_migrated_schema(connection)
                assert _get_column_info(connection, _TAG_IDS_COLUMN_NAME) is not None
                non_null_rows = connection.execute(
                    text(
                        'SELECT COUNT(*) FROM "UtubUrls" WHERE "trashedTagNames" IS NOT NULL'
                    )
                ).scalar_one()
                row_counts_after_reupgrade = _capture_row_counts(connection)
            assert non_null_rows == 0
            assert_row_counts_match_ignoring_new_tables(
                row_counts_before_roundtrip, row_counts_after_reupgrade
            )

            # Schema is fully migrated to head; recreate any tables the
            # migrations left absent so the runner fixture teardown operates
            # against the full schema for subsequent tests.
            db.create_all()
    finally:
        del os.environ["PYTEST_RUNNING"]
