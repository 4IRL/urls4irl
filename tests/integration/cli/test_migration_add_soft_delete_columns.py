"""Integration test for the a9d3e5f7b1c2 migration: add soft-delete columns.

Exercises the upgrade → downgrade → upgrade roundtrip against a real seeded
dataset, proving the additive nullable soft-delete columns (``deletedAt``,
``deletedBy`` and their ``fk_*_deleted_by`` FKs on Utubs/UtubUrls, plus the
``UtubUrls.trashedTagIds`` JSONB snapshot) are created on upgrade, dropped on
downgrade even when populated, re-apply cleanly, and come back NULL after a
re-upgrade (the migration never backfills; downgrade data loss is expected).
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Connection
from sqlalchemy.types import Integer

from backend import db, migrate
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from tests.integration.cli.utils import assert_row_counts_match_ignoring_new_tables

pytestmark = pytest.mark.cli

_PRE_SOFT_DELETE_REVISION: str = "58dfdcfa3921"
_SOFT_DELETE_REVISION: str = "a9d3e5f7b1c2"
_UTUBS_TABLE: str = "Utubs"
_UTUB_URLS_TABLE: str = "UtubUrls"
_USERS_TABLE: str = "Users"
_ALEMBIC_VERSION_TABLE: str = "alembic_version"
_DELETED_AT_COLUMN: str = "deletedAt"
_DELETED_BY_COLUMN: str = "deletedBy"
_TRASHED_TAG_IDS_COLUMN: str = "trashedTagIds"
_UTUBS_DELETED_BY_FK: str = "fk_utubs_deleted_by"
_UTUB_URLS_DELETED_BY_FK: str = "fk_utuburls_deleted_by"

_UTUBS_SOFT_DELETE_COLUMNS: set[str] = {_DELETED_AT_COLUMN, _DELETED_BY_COLUMN}
_UTUB_URLS_SOFT_DELETE_COLUMNS: set[str] = {
    _DELETED_AT_COLUMN,
    _DELETED_BY_COLUMN,
    _TRASHED_TAG_IDS_COLUMN,
}

_MANAGEDB_DROP_ARGS: list[str] = ["managedb", "drop", "test"]
_ADDMOCK_ALL_ARGS: list[str] = ["addmock", "all"]


def _build_alembic_config() -> Config:
    alembic_config = Config("./migrations/alembic.ini")
    alembic_config.set_main_option("script_location", "migrations/")
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


def _get_columns_by_name(
    connection: Connection, table_name: str
) -> dict[str, dict[str, Any]]:
    """Return the inspector's column metadata for a table, keyed by column name."""
    inspector = inspect(connection)
    return {col["name"]: col for col in inspector.get_columns(table_name)}


def _has_deleted_by_foreign_key(
    connection: Connection, table_name: str, constraint_name: str
) -> bool:
    """Return whether the named deletedBy → Users.id FK constraint is present.

    Matches both by the constraint name emitted by the migration and by the
    referenced table/column so a mismatch on either surfaces as a failure.
    """
    inspector = inspect(connection)
    for foreign_key in inspector.get_foreign_keys(table_name):
        if (
            foreign_key.get("name") == constraint_name
            and foreign_key.get("referred_table") == _USERS_TABLE
            and foreign_key.get("constrained_columns") == [_DELETED_BY_COLUMN]
            and foreign_key.get("referred_columns") == ["id"]
        ):
            return True
    return False


def _assert_soft_delete_schema_present(connection: Connection) -> None:
    utubs_columns = _get_columns_by_name(connection, _UTUBS_TABLE)
    assert _UTUBS_SOFT_DELETE_COLUMNS <= utubs_columns.keys()
    assert utubs_columns[_DELETED_AT_COLUMN]["nullable"] is True
    assert utubs_columns[_DELETED_AT_COLUMN]["type"].timezone is True
    assert utubs_columns[_DELETED_BY_COLUMN]["nullable"] is True
    assert isinstance(utubs_columns[_DELETED_BY_COLUMN]["type"], Integer)
    assert _has_deleted_by_foreign_key(connection, _UTUBS_TABLE, _UTUBS_DELETED_BY_FK)

    utub_urls_columns = _get_columns_by_name(connection, _UTUB_URLS_TABLE)
    assert _UTUB_URLS_SOFT_DELETE_COLUMNS <= utub_urls_columns.keys()
    assert utub_urls_columns[_DELETED_AT_COLUMN]["nullable"] is True
    assert utub_urls_columns[_DELETED_AT_COLUMN]["type"].timezone is True
    assert utub_urls_columns[_DELETED_BY_COLUMN]["nullable"] is True
    assert isinstance(utub_urls_columns[_DELETED_BY_COLUMN]["type"], Integer)
    assert utub_urls_columns[_TRASHED_TAG_IDS_COLUMN]["nullable"] is True
    assert isinstance(utub_urls_columns[_TRASHED_TAG_IDS_COLUMN]["type"], JSONB)
    assert _has_deleted_by_foreign_key(
        connection, _UTUB_URLS_TABLE, _UTUB_URLS_DELETED_BY_FK
    )


def _assert_soft_delete_schema_absent(connection: Connection) -> None:
    utubs_columns = _get_columns_by_name(connection, _UTUBS_TABLE)
    assert not (_UTUBS_SOFT_DELETE_COLUMNS & utubs_columns.keys())
    assert not _has_deleted_by_foreign_key(
        connection, _UTUBS_TABLE, _UTUBS_DELETED_BY_FK
    )

    utub_urls_columns = _get_columns_by_name(connection, _UTUB_URLS_TABLE)
    assert not (_UTUB_URLS_SOFT_DELETE_COLUMNS & utub_urls_columns.keys())
    assert not _has_deleted_by_foreign_key(
        connection, _UTUB_URLS_TABLE, _UTUB_URLS_DELETED_BY_FK
    )


def _assert_models_match_migrated_schema(connection: Connection) -> None:
    """Compare the model's view of each new column with the inspected schema.

    Normal tests build the schema from the models via ``db.create_all()``, so
    this is the only drift check between the models and the migration.
    """
    for model, table_name in ((Utubs, _UTUBS_TABLE), (Utub_Urls, _UTUB_URLS_TABLE)):
        model_columns = model.__table__.c
        inspected_columns = _get_columns_by_name(connection, table_name)

        model_deleted_at = model_columns[_DELETED_AT_COLUMN]
        inspected_deleted_at = inspected_columns[_DELETED_AT_COLUMN]
        assert model_deleted_at.nullable is inspected_deleted_at["nullable"]
        assert model_deleted_at.type.timezone is inspected_deleted_at["type"].timezone

        model_deleted_by = model_columns[_DELETED_BY_COLUMN]
        inspected_deleted_by = inspected_columns[_DELETED_BY_COLUMN]
        assert model_deleted_by.nullable is inspected_deleted_by["nullable"]
        assert isinstance(model_deleted_by.type, Integer)
        assert {
            foreign_key.target_fullname for foreign_key in model_deleted_by.foreign_keys
        } == {f"{_USERS_TABLE}.id"}

    model_trashed_tag_ids = Utub_Urls.__table__.c[_TRASHED_TAG_IDS_COLUMN]
    inspected_trashed_tag_ids = _get_columns_by_name(connection, _UTUB_URLS_TABLE)[
        _TRASHED_TAG_IDS_COLUMN
    ]
    assert isinstance(model_trashed_tag_ids.type, JSONB)
    assert isinstance(inspected_trashed_tag_ids["type"], JSONB)
    assert model_trashed_tag_ids.nullable is inspected_trashed_tag_ids["nullable"]


def _mark_one_row_per_table_trashed(connection: Connection) -> None:
    """Populate the soft-delete columns on one Utubs row and one UtubUrls row.

    Uses raw SQL (never the ORM): the models may be ahead of, or behind, the
    schema at this point in the migration roundtrip. Populating the columns
    (including a live FK reference to Users) proves the downgrade succeeds
    with real soft-delete state present.
    """
    connection.execute(
        text(
            'UPDATE "Utubs" SET "deletedAt" = now(), "deletedBy" = "utubCreator" '
            'WHERE id = (SELECT MIN(id) FROM "Utubs")'
        )
    )
    connection.execute(
        text(
            'UPDATE "UtubUrls" SET "deletedAt" = now(), "deletedBy" = "userID", '
            "\"trashedTagIds\" = '[1, 2]'::jsonb "
            'WHERE id = (SELECT MIN(id) FROM "UtubUrls")'
        )
    )


def _count_non_null(connection: Connection, table_name: str, column: str) -> int:
    """Return how many rows in the table have a non-NULL value in the column."""
    return connection.execute(
        text(f'SELECT COUNT(*) FROM "{table_name}" WHERE "{column}" IS NOT NULL')
    ).scalar_one()


def test_add_soft_delete_columns_migration_upgrade_and_downgrade(runner) -> None:
    """
    GIVEN a database upgraded to head and seeded with the full mock dataset
        via ``flask addmock all``, with one Utubs row and one UtubUrls row
        carrying populated soft-delete values
    WHEN the a9d3e5f7b1c2 migration is downgraded to 58dfdcfa3921 and then
        re-applied to head
    THEN the deletedAt/deletedBy columns (both tables), the trashedTagIds
        JSONB column (UtubUrls) and both deletedBy → Users FKs are present at
        head; all are absent after downgrade; all seeded rows survive the
        down/up roundtrip (row-count equality); and every soft-delete column
        comes back NULL on re-upgrade (the migration never backfills, and
        downgrade data loss is expected) — confirming the migration is
        reversible and additive-only against the real seeded dataset (per
        CLAUDE.md).

    Args:
        runner (pytest.fixture): Provides a Flask application and a FlaskCLIRunner.
    """
    soft_delete_script = ScriptDirectory.from_config(
        _build_alembic_config()
    ).get_revision(_SOFT_DELETE_REVISION)
    assert soft_delete_script.down_revision == _PRE_SOFT_DELETE_REVISION
    os.environ["PYTEST_RUNNING"] = "1"
    flask_app, cli_runner = runner
    migrate.init_app(flask_app)

    try:
        cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)

        with flask_app.app_context():
            command.upgrade(_build_alembic_config(), "head")

            with db.engine.connect() as connection:
                _assert_soft_delete_schema_present(connection)

            cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)

            with db.engine.connect() as connection:
                row_counts_before_roundtrip = _capture_row_counts(connection)
            # The post-roundtrip assertions are only meaningful if rows exist.
            assert row_counts_before_roundtrip[_USERS_TABLE] > 0
            assert row_counts_before_roundtrip[_UTUBS_TABLE] > 0
            assert row_counts_before_roundtrip[_UTUB_URLS_TABLE] > 0

            # engine.begin() commits on exit, so the writes are visible to the
            # connections the downgrade opens.
            with db.engine.begin() as connection:
                _mark_one_row_per_table_trashed(connection)
            with db.engine.connect() as connection:
                assert (
                    _count_non_null(connection, _UTUBS_TABLE, _DELETED_AT_COLUMN) == 1
                )
                assert (
                    _count_non_null(
                        connection, _UTUB_URLS_TABLE, _TRASHED_TAG_IDS_COLUMN
                    )
                    == 1
                )

            command.downgrade(_build_alembic_config(), _PRE_SOFT_DELETE_REVISION)

            with db.engine.connect() as connection:
                _assert_soft_delete_schema_absent(connection)
                row_counts_after_downgrade = _capture_row_counts(connection)
            assert_row_counts_match_ignoring_new_tables(
                row_counts_before_roundtrip, row_counts_after_downgrade
            )

            command.upgrade(_build_alembic_config(), "head")

            with db.engine.connect() as connection:
                _assert_soft_delete_schema_present(connection)
                _assert_models_match_migrated_schema(connection)
                for table_name, columns in (
                    (_UTUBS_TABLE, _UTUBS_SOFT_DELETE_COLUMNS),
                    (_UTUB_URLS_TABLE, _UTUB_URLS_SOFT_DELETE_COLUMNS),
                ):
                    for column in columns:
                        assert _count_non_null(connection, table_name, column) == 0

            # Schema is fully migrated to head; recreate any tables the
            # migrations left absent so the runner fixture teardown operates
            # against the full schema for subsequent tests.
            db.create_all()
    finally:
        del os.environ["PYTEST_RUNNING"]
