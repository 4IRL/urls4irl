"""Integration test for the e5a1c7d9b3f2 migration: deletedAt partial indexes.

Exercises the upgrade → downgrade → upgrade roundtrip against a real seeded
dataset, proving the ``idx_utubs_deleted_at`` and ``idx_utub_urls_deleted_at``
partial indexes are created on upgrade (matching the models), dropped on
downgrade, re-created on the second upgrade, and that no row is touched in
either direction.
"""

from __future__ import annotations

import os
import re

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, inspect, select, table, text
from sqlalchemy.engine import Connection

from backend import db, migrate
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from tests.integration.cli.utils import assert_row_counts_match_ignoring_new_tables

pytestmark = pytest.mark.cli

_PRE_INDEX_REVISION: str = "c4e8a1f3b7d2"
_INDEX_REVISION: str = "e5a1c7d9b3f2"
_USERS_TABLE: str = "Users"
_UTUBS_TABLE: str = "Utubs"
_UTUB_URLS_TABLE: str = "UtubUrls"
_ALEMBIC_VERSION_TABLE: str = "alembic_version"
_UTUBS_INDEX_NAME: str = "idx_utubs_deleted_at"
_UTUB_URLS_INDEX_NAME: str = "idx_utub_urls_deleted_at"
_EXPECTED_PREDICATE: str = '"deletedAt"ISNOTNULL'

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


def _get_index_definition(
    connection: Connection, table_name: str, index_name: str
) -> str | None:
    """Return the ``pg_indexes.indexdef`` of the named index, or None."""
    return connection.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE tablename = :table_name AND indexname = :index_name"
        ),
        {"table_name": table_name, "index_name": index_name},
    ).scalar_one_or_none()


def _normalize_predicate(predicate: str) -> str:
    """Strip whitespace and parentheses so a model predicate and a
    ``pg_indexes`` predicate can be compared textually."""
    return re.sub(r"[\s()]", "", predicate)


def _assert_index_is_partial_on_deleted_at(
    connection: Connection, table_name: str, index_name: str
) -> None:
    """Assert the index exists on ``deletedAt`` with the trashed-rows predicate."""
    index_definition = _get_index_definition(connection, table_name, index_name)
    assert index_definition is not None, index_name
    assert "UNIQUE" not in index_definition
    assert '("deletedAt")' in index_definition
    assert " WHERE " in index_definition
    database_where = _normalize_predicate(index_definition.split(" WHERE ", 1)[1])
    assert database_where == _EXPECTED_PREDICATE


def _assert_models_match_migrated_schema(connection: Connection) -> None:
    """Compare each model's declared index with the migrated database's index.

    Normal tests build the schema from the models via ``db.create_all()``, so
    this is the only drift check between the models and the migration.
    """
    for model_table, index_name in (
        (Utubs.__table__, _UTUBS_INDEX_NAME),
        (Utub_Urls.__table__, _UTUB_URLS_INDEX_NAME),
    ):
        model_index = next(
            index for index in model_table.indexes if index.name == index_name
        )
        assert [column.name for column in model_index.columns] == ["deletedAt"]
        model_where = _normalize_predicate(
            str(model_index.dialect_options["postgresql"]["where"])
        )
        assert model_where == _EXPECTED_PREDICATE
        _assert_index_is_partial_on_deleted_at(connection, model_table.name, index_name)


def test_add_deleted_at_partial_indexes_migration_roundtrips(runner) -> None:
    """
    GIVEN a database upgraded to head and seeded with the full mock dataset via
        ``flask addmock all``
    WHEN the e5a1c7d9b3f2 migration is downgraded to c4e8a1f3b7d2 and upgraded
        again
    THEN both ``idx_utubs_deleted_at`` and ``idx_utub_urls_deleted_at`` exist as
        partial indexes ``WHERE "deletedAt" IS NOT NULL`` matching the models
        after each upgrade, are gone after the downgrade, and the per-table row
        counts are unchanged across the roundtrip — confirming the migration is
        reversible against the real seeded dataset (per CLAUDE.md).

    Args:
        runner (pytest.fixture): Provides a Flask application and a FlaskCLIRunner.
    """
    index_script = ScriptDirectory.from_config(_build_alembic_config()).get_revision(
        _INDEX_REVISION
    )
    assert index_script.down_revision == _PRE_INDEX_REVISION
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
            assert row_counts_before_roundtrip[_UTUBS_TABLE] > 0
            assert row_counts_before_roundtrip[_UTUB_URLS_TABLE] > 0

            command.downgrade(_build_alembic_config(), _PRE_INDEX_REVISION)

            with db.engine.connect() as connection:
                assert (
                    _get_index_definition(connection, _UTUBS_TABLE, _UTUBS_INDEX_NAME)
                    is None
                )
                assert (
                    _get_index_definition(
                        connection, _UTUB_URLS_TABLE, _UTUB_URLS_INDEX_NAME
                    )
                    is None
                )
                row_counts_after_downgrade = _capture_row_counts(connection)
            assert_row_counts_match_ignoring_new_tables(
                row_counts_before_roundtrip, row_counts_after_downgrade
            )

            command.upgrade(_build_alembic_config(), "head")

            with db.engine.connect() as connection:
                _assert_models_match_migrated_schema(connection)
                row_counts_after_reupgrade = _capture_row_counts(connection)
            assert_row_counts_match_ignoring_new_tables(
                row_counts_before_roundtrip, row_counts_after_reupgrade
            )

            # Schema is fully migrated to head; recreate any tables the
            # migrations left absent so the runner fixture teardown operates
            # against the full schema for subsequent tests.
            db.create_all()
    finally:
        del os.environ["PYTEST_RUNNING"]
