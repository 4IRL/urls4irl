"""Integration test for the a7c1e9b3d5f0 + b8d2f0c4e6a1 migrations:
add isSuspended and sessionsInvalidatedAt to Users.

Exercises the downgrade → upgrade roundtrip against a real seeded dataset,
proving both account-state migrations are reversible without data loss.
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

_PRE_ACCOUNT_STATE_REVISION: str = "f3d5a7c9e1b2"
_USERS_TABLE: str = "Users"
_ALEMBIC_VERSION_TABLE: str = "alembic_version"
_IS_SUSPENDED_COLUMN: str = "isSuspended"
_SESSIONS_INVALIDATED_AT_COLUMN: str = "sessionsInvalidatedAt"

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


def _get_users_column_names(connection: Connection) -> set[str]:
    inspector = inspect(connection)
    return {col["name"] for col in inspector.get_columns(_USERS_TABLE)}


def test_add_account_state_columns_migration_upgrade_and_downgrade(runner):
    """
    GIVEN a database upgraded to head and seeded with the full mock dataset
        via ``flask addmock all``
    WHEN the b8d2f0c4e6a1 and a7c1e9b3d5f0 migrations are downgraded to
        f3d5a7c9e1b2 and then re-applied to head
    THEN both columns are present at head with all rows unsuspended and no
        invalidation timestamps; both columns are absent after downgrade;
        all seeded rows survive the down/up roundtrip (row-count equality);
        existing rows receive the defaults on re-upgrade — confirming both
        migrations are reversible against the real seeded dataset.

    Args:
        runner (pytest.fixture): Provides a Flask application and a FlaskCLIRunner.
    """
    os.environ["PYTEST_RUNNING"] = "1"
    flask_app, cli_runner = runner
    migrate.init_app(flask_app)

    cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)

    with flask_app.app_context():
        # Start at head so addmock all runs against a complete schema.
        command.upgrade(_build_alembic_config(), "head")

        with db.engine.connect() as connection:
            users_columns_at_head = _get_users_column_names(connection)
        assert _IS_SUSPENDED_COLUMN in users_columns_at_head
        assert _SESSIONS_INVALIDATED_AT_COLUMN in users_columns_at_head

        cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)

        with db.engine.connect() as connection:
            row_counts_before_roundtrip = _capture_row_counts(connection)
        assert row_counts_before_roundtrip[_USERS_TABLE] > 0

        with db.engine.connect() as connection:
            non_default_count = connection.execute(
                text(
                    'SELECT COUNT(*) FROM "Users" WHERE "isSuspended" = TRUE '
                    'OR "sessionsInvalidatedAt" IS NOT NULL'
                )
            ).scalar_one()
        assert non_default_count == 0

        command.downgrade(_build_alembic_config(), _PRE_ACCOUNT_STATE_REVISION)

        with db.engine.connect() as connection:
            users_columns_after_downgrade = _get_users_column_names(connection)
            row_counts_after_downgrade = _capture_row_counts(connection)
        assert _IS_SUSPENDED_COLUMN not in users_columns_after_downgrade
        assert _SESSIONS_INVALIDATED_AT_COLUMN not in users_columns_after_downgrade
        assert row_counts_after_downgrade == row_counts_before_roundtrip

        command.upgrade(_build_alembic_config(), "head")

        with db.engine.connect() as connection:
            users_columns_after_reupgrade = _get_users_column_names(connection)
            re_upgraded_non_default_count = connection.execute(
                text(
                    'SELECT COUNT(*) FROM "Users" WHERE "isSuspended" = TRUE '
                    'OR "sessionsInvalidatedAt" IS NOT NULL'
                )
            ).scalar_one()
        assert _IS_SUSPENDED_COLUMN in users_columns_after_reupgrade
        assert _SESSIONS_INVALIDATED_AT_COLUMN in users_columns_after_reupgrade
        assert re_upgraded_non_default_count == 0

        # Schema is fully migrated to head; recreate any tables the
        # migrations left absent so the runner fixture teardown operates
        # against the full schema for subsequent tests.
        db.create_all()

    del os.environ["PYTEST_RUNNING"]
