"""Migration round-trip test for the AuditLogs table (revision 09f8ae70fc61).

Mirrors tests/integration/cli/test_migration_add_api_refresh_tokens.py exactly
in structure: drops the schema, rebuilds via Alembic to the pre-migration
revision, seeds data via ``flask addmock all``, upgrades to head, asserts the
table + columns + index, seeds an AuditLogs row, downgrades, asserts the table
is gone and seeded relational data is intact, then re-applies and confirms the
table reappears.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from backend import db, migrate

pytestmark = pytest.mark.cli

_PRE_AUDITLOGS_REVISION = "c9e4f1a52b83"

_AUDITLOGS_TABLE = "AuditLogs"
_USERS_TABLE = "Users"
_ALEMBIC_VERSION_TABLE = "alembic_version"
_EXPECTED_COLUMNS: frozenset[str] = frozenset(
    {
        "id",
        "actorId",
        "action",
        "targetType",
        "targetId",
        "metadata",
        "createdAt",
    }
)
_EXPECTED_INDEXES: frozenset[str] = frozenset({"idx_audit_logs_created_at_actor"})

_SEED_AUDIT_ACTION = "admin.test.migration_seed"
_SEED_TIMESTAMP = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

_MANAGEDB_DROP_ARGS = ["managedb", "drop", "test"]
_ADDMOCK_ALL_ARGS = ["addmock", "all"]


def _build_alembic_config() -> Config:
    alembic_config = Config("./migrations/alembic.ini")
    alembic_config.set_main_option("script_location", "migrations/")
    alembic_config.attributes["connection"] = db.engine.connect()
    return alembic_config


def _capture_row_counts(connection: Connection) -> dict[str, int]:
    """Return a per-table row count for every persisted table except the
    Alembic bookkeeping table, keyed by table name.

    Proves the AuditLogs migration up/down roundtrip preserves the mock
    dataset seeded by ``flask addmock all`` (drift-proof row-count equality,
    per CLAUDE.md — never hardcode counts).
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


def test_add_auditlogs_migration_upgrade_and_downgrade(runner):
    """
    GIVEN a database at revision c9e4f1a52b83 (pre-AuditLogs) seeded with the
         full mock dataset via ``flask addmock all``
    WHEN the 09f8ae70fc61 migration is applied, an AuditLogs row is seeded,
         the migration is reverted, and then re-applied
    THEN the AuditLogs table, its seven columns, and the composite index are
         created on upgrade; every seeded relational row survives the up/down
         roundtrip (row-count equality on downgrade); the seeded AuditLogs row
         proves the table was functional before drop; the table is absent on
         downgrade; and the re-apply is idempotent — confirming the migration
         is reversible against real seeded data (per CLAUDE.md).

    Args:
        runner (pytest.fixture): Provides a Flask application and a FlaskCliRunner
    """
    os.environ["PYTEST_RUNNING"] = "1"  # Silence alembic logging for this test
    app, cli_runner = runner
    migrate.init_app(app)

    cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)

    with app.app_context():
        command.upgrade(_build_alembic_config(), _PRE_AUDITLOGS_REVISION)

        inspector = inspect(db.engine)
        assert not inspector.has_table(_AUDITLOGS_TABLE)

        cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)

        with db.engine.connect() as connection:
            row_counts_before_roundtrip = _capture_row_counts(connection)
        assert row_counts_before_roundtrip[_USERS_TABLE] > 0

        command.upgrade(_build_alembic_config(), "head")

        inspector = inspect(db.engine)
        assert inspector.has_table(_AUDITLOGS_TABLE)
        actual_columns: frozenset[str] = frozenset(
            column["name"] for column in inspector.get_columns(_AUDITLOGS_TABLE)
        )
        assert actual_columns == _EXPECTED_COLUMNS
        actual_indexes: frozenset[str] = frozenset(
            index["name"] for index in inspector.get_indexes(_AUDITLOGS_TABLE)
        )
        assert _EXPECTED_INDEXES <= actual_indexes

        with db.engine.connect() as connection:
            first_user_id: int = connection.execute(
                text('SELECT id FROM "Users" ORDER BY id LIMIT 1')
            ).scalar_one()

        with db.engine.begin() as connection:
            connection.execute(
                text(
                    'INSERT INTO "AuditLogs" '
                    '("actorId", "action", "createdAt") '
                    "VALUES (:actor_id, :action, :created_at)"
                ),
                {
                    "actor_id": first_user_id,
                    "action": _SEED_AUDIT_ACTION,
                    "created_at": _SEED_TIMESTAMP,
                },
            )

        with db.engine.connect() as connection:
            seeded_audit_count: int = connection.execute(
                text('SELECT COUNT(*) FROM "AuditLogs" WHERE "action" = :action'),
                {"action": _SEED_AUDIT_ACTION},
            ).scalar_one()
        assert seeded_audit_count == 1

        command.downgrade(_build_alembic_config(), _PRE_AUDITLOGS_REVISION)

        inspector = inspect(db.engine)
        assert not inspector.has_table(_AUDITLOGS_TABLE)

        with db.engine.connect() as connection:
            row_counts_after_roundtrip = _capture_row_counts(connection)
        assert row_counts_after_roundtrip == row_counts_before_roundtrip

        command.upgrade(_build_alembic_config(), "head")

        inspector = inspect(db.engine)
        assert inspector.has_table(_AUDITLOGS_TABLE)

        # Schema is now fully migrated to head; recreate any tables the
        # migrations left absent so the runner fixture teardown operates
        # against the full schema for subsequent tests.
        db.create_all()

    del os.environ["PYTEST_RUNNING"]
