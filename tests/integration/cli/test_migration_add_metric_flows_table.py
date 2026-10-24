"""Migration round-trip test for the MetricFlows table (revision e5b9d3f7a1c2).

Drops the schema, upgrades to head, seeds data via ``flask addmock all``,
downgrades to the pre-MetricFlows revision (table gone, every other row count
unchanged), upgrades again, and exercises the DB-level constraints on the
migrated table. Finally it snapshots the migrated ``MetricFlows`` schema and
compares it with the schema ``db.create_all()`` builds from the model.
"""

from __future__ import annotations

import os
import unicodedata
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from backend import db, migrate
from backend.models.metric_flows import (
    DEFINITION_STEPS_ARRAY_CHECK,
    DISPLAY_NAME_LOWER_INDEX,
    DISPLAY_NAME_TRIMMED_CHECK,
)
from backend.models.users import Users
from backend.utils.db_table_names import TABLE_NAMES
from tests.integration.cli.utils import assert_row_counts_match_ignoring_new_tables

pytestmark = pytest.mark.cli

_PRE_METRIC_FLOWS_REVISION = "d4a8c2e6f0b1"

_ALEMBIC_VERSION_TABLE = "alembic_version"
_MANAGEDB_DROP_ARGS = ["managedb", "drop", "test"]
_ADDMOCK_ALL_ARGS = ["addmock", "all"]

_INSERT_FLOW_SQL = (
    'INSERT INTO "MetricFlows" '
    '("displayName", "definition", "createdAt", "updatedAt") '
    "VALUES (:display_name, CAST(:definition AS jsonb), now(), now())"
)
_VALID_DEFINITION = '{"steps": []}'

_COLUMNS_SNAPSHOT_SQL = (
    "SELECT column_name, data_type, udt_name, character_maximum_length, "
    "is_nullable, column_default IS NOT NULL AS has_default "
    "FROM information_schema.columns "
    "WHERE table_schema = current_schema() AND table_name = 'MetricFlows' "
    "ORDER BY column_name"
)
_INDEXES_SNAPSHOT_SQL = (
    "SELECT indexname, indexdef FROM pg_indexes "
    "WHERE schemaname = current_schema() AND tablename = 'MetricFlows' "
    "ORDER BY indexname"
)
_CONSTRAINTS_SNAPSHOT_SQL = (
    "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
    "WHERE conrelid = to_regclass('\"MetricFlows\"') "
    "ORDER BY conname"
)


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


def _snapshot_metric_flows_schema(connection: Connection) -> dict[str, list[Any]]:
    """Capture columns, index definitions and constraint definitions of MetricFlows."""
    return {
        "columns": [
            tuple(row) for row in connection.execute(text(_COLUMNS_SNAPSHOT_SQL))
        ],
        "indexes": [
            tuple(row) for row in connection.execute(text(_INDEXES_SNAPSHOT_SQL))
        ],
        "constraints": [
            tuple(row) for row in connection.execute(text(_CONSTRAINTS_SNAPSHOT_SQL))
        ],
    }


def _assert_insert_rejected(
    connection: Connection, *, display_name: str, constraint_name: str
) -> None:
    """Insert a flow in a throwaway transaction and assert the named constraint fires."""
    transaction = connection.begin()
    try:
        with pytest.raises(IntegrityError) as raised:
            connection.execute(
                text(_INSERT_FLOW_SQL),
                {"display_name": display_name, "definition": _VALID_DEFINITION},
            )
        assert constraint_name in str(raised.value)
    finally:
        transaction.rollback()


def _assert_name_pairs_accepted(connection: Connection) -> None:
    """Postgres lower() uniqueness only: ß vs SS and NFC vs NFD names are distinct."""
    nfc_name = unicodedata.normalize("NFC", "Café")
    nfd_name = unicodedata.normalize("NFD", "Café")
    assert nfc_name != nfd_name
    display_names = ("Straße", "STRASSE", nfc_name, nfd_name)
    for display_name in display_names:
        connection.execute(
            text(_INSERT_FLOW_SQL),
            {"display_name": display_name, "definition": _VALID_DEFINITION},
        )
    stored_count = connection.execute(
        text(
            'SELECT COUNT(*) FROM "MetricFlows" WHERE "displayName" = ANY(:display_names)'
        ),
        {"display_names": list(display_names)},
    ).scalar_one()
    assert stored_count == len(display_names)


def _assert_insert_rejected_cases(connection: Connection) -> None:
    """Case variants and padded names violate the unique/trim constraints."""
    with db.engine.begin() as seed_connection:
        seed_connection.execute(
            text(_INSERT_FLOW_SQL),
            {"display_name": "Foo", "definition": _VALID_DEFINITION},
        )
    try:
        _assert_insert_rejected(
            connection, display_name="foo", constraint_name=DISPLAY_NAME_LOWER_INDEX
        )
        _assert_insert_rejected(
            connection, display_name=" Foo", constraint_name=DISPLAY_NAME_TRIMMED_CHECK
        )
    finally:
        with db.engine.begin() as cleanup_connection:
            cleanup_connection.execute(text('DELETE FROM "MetricFlows"'))


def _select_flow_owner_ids(display_name: str) -> tuple[int | None, int | None]:
    with db.engine.connect() as connection:
        created_by, updated_by = connection.execute(
            text(
                'SELECT "createdBy", "updatedBy" FROM "MetricFlows" '
                'WHERE "displayName" = :display_name'
            ),
            {"display_name": display_name},
        ).one()
    return created_by, updated_by


def _assert_user_delete_nulls_creator_and_updater() -> None:
    """Deleting the creator nulls only createdBy; deleting the updater nulls updatedBy."""
    creator = Users(
        username="MetricFlowCreator1",
        email="metricflowcreator1@email.com",
        plaintext_password="MetricFlowCreator1Password",
    )
    updater = Users(
        username="MetricFlowUpdater1",
        email="metricflowupdater1@email.com",
        plaintext_password="MetricFlowUpdater1Password",
    )
    db.session.add_all([creator, updater])
    db.session.commit()
    creator_id = creator.id
    updater_id = updater.id
    assert creator_id != updater_id

    with db.engine.begin() as connection:
        connection.execute(
            text(
                'INSERT INTO "MetricFlows" '
                '("displayName", "definition", "createdBy", "updatedBy", '
                '"createdAt", "updatedAt") '
                "VALUES ('Owned', CAST(:definition AS jsonb), :creator_id, "
                ":updater_id, now(), now())"
            ),
            {
                "definition": _VALID_DEFINITION,
                "creator_id": creator_id,
                "updater_id": updater_id,
            },
        )

    db.session.delete(creator)
    db.session.commit()
    assert _select_flow_owner_ids("Owned") == (None, updater_id)

    db.session.delete(updater)
    db.session.commit()
    assert _select_flow_owner_ids("Owned") == (None, None)


def test_add_metric_flows_migration_roundtrip_and_constraints(runner) -> None:
    """
    GIVEN a database at head seeded with the full mock dataset
    WHEN the MetricFlows migration is downgraded, re-applied, and exercised
    THEN the table is gone after downgrade and every other row count is unchanged;
         a case variant or padded name violates the unique index while renaming a
         row's own case succeeds; ß/SS and NFC/NFD names are accepted; deleting a
         referenced user nulls createdBy/updatedBy; and the migrated schema equals
         the schema ``db.create_all()`` builds from the model

    Args:
        runner (pytest.fixture): Provides a Flask application and a FlaskCliRunner
    """
    os.environ["PYTEST_RUNNING"] = "1"  # Silence alembic logging for this test
    try:
        _run_roundtrip_and_constraint_checks(runner)
    finally:
        os.environ.pop("PYTEST_RUNNING", None)


def _run_roundtrip_and_constraint_checks(runner) -> None:
    app, cli_runner = runner
    migrate.init_app(app)

    cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)

    with app.app_context():
        command.upgrade(_build_alembic_config(), "head")
        cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)

        with db.engine.connect() as connection:
            row_counts_before_roundtrip = _capture_row_counts(connection)
        assert row_counts_before_roundtrip[TABLE_NAMES.USERS] > 0

        command.downgrade(_build_alembic_config(), _PRE_METRIC_FLOWS_REVISION)

        assert not inspect(db.engine).has_table(TABLE_NAMES.METRIC_FLOWS)
        with db.engine.connect() as connection:
            row_counts_after_downgrade = _capture_row_counts(connection)
        assert_row_counts_match_ignoring_new_tables(
            row_counts_before_roundtrip, row_counts_after_downgrade
        )

        command.upgrade(_build_alembic_config(), "head")
        assert inspect(db.engine).has_table(TABLE_NAMES.METRIC_FLOWS)

        with db.engine.connect() as connection:
            _assert_insert_rejected_cases(connection)

        with db.engine.begin() as connection:
            _assert_name_pairs_accepted(connection)
            # Renaming a row's own name to a different case succeeds.
            connection.execute(
                text(_INSERT_FLOW_SQL),
                {"display_name": "Foo", "definition": _VALID_DEFINITION},
            )
            connection.execute(
                text(
                    'UPDATE "MetricFlows" SET "displayName" = :new_name '
                    'WHERE "displayName" = :old_name'
                ),
                {"new_name": "foo", "old_name": "Foo"},
            )

        _assert_user_delete_nulls_creator_and_updater()

        with db.engine.connect() as connection:
            migrated_schema = _snapshot_metric_flows_schema(connection)

        cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)
        db.create_all()

        with db.engine.connect() as connection:
            model_schema = _snapshot_metric_flows_schema(connection)

        assert migrated_schema == model_schema
        assert migrated_schema["columns"], "MetricFlows columns were not captured"
        assert migrated_schema["indexes"], "MetricFlows indexes were not captured"
        index_names = [name for name, _ in migrated_schema["indexes"]]
        assert DISPLAY_NAME_LOWER_INDEX in index_names
        constraint_names = [name for name, _ in migrated_schema["constraints"]]
        assert DISPLAY_NAME_TRIMMED_CHECK in constraint_names
        assert DEFINITION_STEPS_ARRAY_CHECK in constraint_names
