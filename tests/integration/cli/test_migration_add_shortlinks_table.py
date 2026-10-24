"""Integration test for the add_shortlinks_table migration: create ShortLinks.

Exercises the upgrade -> downgrade -> upgrade roundtrip against a real seeded
dataset, proving the migration is reversible without loss of other tables' rows.
"""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from backend import db, migrate
from tests.integration.cli.utils import assert_row_counts_match_ignoring_new_tables

pytestmark = pytest.mark.cli

_PRE_SHORTLINKS_REVISION: str = "c7a3e9b5d2f4"
_SHORTLINKS_REVISION: str = "d4a8c2e6f0b1"
_SHORTLINKS_TABLE: str = "ShortLinks"
_USERS_TABLE: str = "Users"
_UTUBS_TABLE: str = "Utubs"
_ALEMBIC_VERSION_TABLE: str = "alembic_version"

_EXPECTED_COLUMNS: dict[str, bool] = {
    "id": False,
    "utubUrlID": False,
    "code": False,
    "createdBy": True,
    "createdAt": False,
    "expiresAt": False,
}
_EXPECTED_UNIQUE_CONSTRAINTS: dict[str, tuple[str, ...]] = {
    "unique_short_link_per_utub_url": ("utubUrlID",),
    "unique_short_link_code": ("code",),
}
_EXPECTED_FOREIGN_KEYS: dict[str, tuple[str, str]] = {
    "utubUrlID": ("UtubUrls", "CASCADE"),
    "createdBy": ("Users", "SET NULL"),
}

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


def _assert_shortlinks_schema(connection: Connection) -> None:
    inspector = inspect(connection)
    assert inspector.has_table(_SHORTLINKS_TABLE)

    columns = {
        column["name"]: column for column in inspector.get_columns(_SHORTLINKS_TABLE)
    }
    assert {name: col["nullable"] for name, col in columns.items()} == (
        _EXPECTED_COLUMNS
    )
    assert columns["code"]["type"].length == 10
    assert columns["createdAt"]["type"].timezone is True
    assert columns["expiresAt"]["type"].timezone is True

    assert inspector.get_pk_constraint(_SHORTLINKS_TABLE)["constrained_columns"] == [
        "id"
    ]

    unique_constraints = {
        constraint["name"]: tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints(_SHORTLINKS_TABLE)
    }
    assert unique_constraints == _EXPECTED_UNIQUE_CONSTRAINTS

    # Postgres backs each unique constraint with a unique index of the same name
    unique_indexes = {
        index["name"]: tuple(index["column_names"])
        for index in inspector.get_indexes(_SHORTLINKS_TABLE)
        if index.get("unique")
    }
    assert unique_indexes == _EXPECTED_UNIQUE_CONSTRAINTS

    foreign_keys = {
        foreign_key["constrained_columns"][0]: (
            foreign_key["referred_table"],
            foreign_key["options"].get("ondelete"),
        )
        for foreign_key in inspector.get_foreign_keys(_SHORTLINKS_TABLE)
    }
    assert foreign_keys == _EXPECTED_FOREIGN_KEYS


def test_add_shortlinks_table_migration_upgrade_and_downgrade(runner):
    """
    GIVEN a database upgraded to head and seeded via ``flask addmock all``
    WHEN the add_shortlinks_table migration is downgraded to c7a3e9b5d2f4 and
        re-applied to head
    THEN there is exactly one Alembic head (d4a8c2e6f0b1), the ShortLinks table
        has the expected columns, constraints, indexes and foreign keys, the
        downgrade drops it without changing any other table's row count, and
        the re-upgrade recreates the empty table.

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
        assert script.get_revision(_SHORTLINKS_REVISION).down_revision == (
            _PRE_SHORTLINKS_REVISION
        )

        # Start at head so addmock all runs against a complete schema
        # (it seeds MetricFlows, which a later migration creates).
        command.upgrade(alembic_config, "head")

        with db.engine.connect() as connection:
            _assert_shortlinks_schema(connection)

        cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)

        with db.engine.connect() as connection:
            row_counts_before_roundtrip = _capture_row_counts(connection)
        assert row_counts_before_roundtrip[_USERS_TABLE] > 0
        assert row_counts_before_roundtrip[_UTUBS_TABLE] > 0

        command.downgrade(alembic_config, _PRE_SHORTLINKS_REVISION)

        with db.engine.connect() as connection:
            assert not inspect(connection).has_table(_SHORTLINKS_TABLE)
            row_counts_after_downgrade = _capture_row_counts(connection)
        assert _SHORTLINKS_TABLE not in row_counts_after_downgrade
        assert_row_counts_match_ignoring_new_tables(
            row_counts_before_roundtrip, row_counts_after_downgrade
        )

        command.upgrade(alembic_config, "head")

        with db.engine.connect() as connection:
            _assert_shortlinks_schema(connection)
            row_counts_after_reupgrade = _capture_row_counts(connection)
        assert row_counts_after_reupgrade[_SHORTLINKS_TABLE] == 0
        assert_row_counts_match_ignoring_new_tables(
            row_counts_before_roundtrip, row_counts_after_reupgrade
        )

        db.create_all()

    del os.environ["PYTEST_RUNNING"]
