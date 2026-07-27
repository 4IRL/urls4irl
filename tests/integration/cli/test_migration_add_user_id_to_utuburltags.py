"""Integration test for the c3f7a1b9d204 migration: add userID to UtubUrlTags.

Exercises the upgrade → downgrade → upgrade roundtrip against a real seeded
dataset, proving the additive nullable ``userID`` FK column (and its
``fk_utuburltags_user`` constraint) is created on upgrade, dropped on
downgrade, re-applies idempotently, and that rows which pre-date the column
come back NULL (the migration attributes tag-applications only going forward
and never backfills — per the migration docstring and CLAUDE.md).
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

_PRE_USER_ID_REVISION: str = "b8d2f0c4e6a1"
_UTUB_URL_TAGS_TABLE: str = "UtubUrlTags"
_USERS_TABLE: str = "Users"
_ALEMBIC_VERSION_TABLE: str = "alembic_version"
_USER_ID_COLUMN: str = "userID"
_USER_ID_FK_CONSTRAINT: str = "fk_utuburltags_user"

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


def _get_utub_url_tags_column_names(connection: Connection) -> set[str]:
    inspector = inspect(connection)
    return {col["name"] for col in inspector.get_columns(_UTUB_URL_TAGS_TABLE)}


def _has_user_id_foreign_key(connection: Connection) -> bool:
    """Return whether the named userID → Users FK constraint is present.

    Matches both by the constraint name emitted by the migration and by the
    referenced table/column so a mismatch on either surfaces as a failure.
    """
    inspector = inspect(connection)
    for foreign_key in inspector.get_foreign_keys(_UTUB_URL_TAGS_TABLE):
        if (
            foreign_key.get("name") == _USER_ID_FK_CONSTRAINT
            and foreign_key.get("referred_table") == _USERS_TABLE
            and foreign_key.get("constrained_columns") == [_USER_ID_COLUMN]
            and foreign_key.get("referred_columns") == ["id"]
        ):
            return True
    return False


def test_add_user_id_to_utuburltags_migration_upgrade_and_downgrade(runner):
    """
    GIVEN a database upgraded to head and seeded with the full mock dataset
        via ``flask addmock all``
    WHEN the c3f7a1b9d204 migration is downgraded to b8d2f0c4e6a1 and then
        re-applied to head
    THEN the userID column and its fk_utuburltags_user → Users FK are present
        at head; both are absent after downgrade; all seeded rows survive the
        down/up roundtrip (row-count equality); and every UtubUrlTags row that
        pre-dated the column comes back NULL on re-upgrade (the migration never
        backfills) — confirming the migration is reversible and additive-only
        against the real seeded dataset (per CLAUDE.md).

    Args:
        runner (pytest.fixture): Provides a Flask application and a FlaskCLIRunner.
    """
    os.environ["PYTEST_RUNNING"] = "1"
    flask_app, cli_runner = runner
    migrate.init_app(flask_app)

    cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)

    with flask_app.app_context():
        # Start at head so addmock all runs against a complete schema
        # (userID column already exists — the updated Utub_Url_Tags() seed
        # call sites populate it without failing).
        command.upgrade(_build_alembic_config(), "head")

        with db.engine.connect() as connection:
            assert _USER_ID_COLUMN in _get_utub_url_tags_column_names(connection)
            assert _has_user_id_foreign_key(connection)

        cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)

        with db.engine.connect() as connection:
            row_counts_before_roundtrip = _capture_row_counts(connection)
        assert row_counts_before_roundtrip[_USERS_TABLE] > 0
        # The NULL-on-re-upgrade assertion below is only meaningful if rows
        # actually pre-date the column, so pin that there are seeded tag rows.
        assert row_counts_before_roundtrip[_UTUB_URL_TAGS_TABLE] > 0

        command.downgrade(_build_alembic_config(), _PRE_USER_ID_REVISION)

        with db.engine.connect() as connection:
            assert _USER_ID_COLUMN not in _get_utub_url_tags_column_names(connection)
            assert not _has_user_id_foreign_key(connection)
            row_counts_after_downgrade = _capture_row_counts(connection)
        assert row_counts_after_downgrade == row_counts_before_roundtrip

        command.upgrade(_build_alembic_config(), "head")

        with db.engine.connect() as connection:
            assert _USER_ID_COLUMN in _get_utub_url_tags_column_names(connection)
            assert _has_user_id_foreign_key(connection)
            # Rows that existed at the downgraded revision (before the column)
            # must come back NULL — the migration is additive-only and never
            # backfills historical attribution.
            non_null_user_id_count = connection.execute(
                text('SELECT COUNT(*) FROM "UtubUrlTags" WHERE "userID" IS NOT NULL')
            ).scalar_one()
        assert non_null_user_id_count == 0

        # Schema is fully migrated to head; recreate any tables the
        # migrations left absent so the runner fixture teardown operates
        # against the full schema for subsequent tests.
        db.create_all()

    del os.environ["PYTEST_RUNNING"]
