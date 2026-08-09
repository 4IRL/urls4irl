import os

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import Enum as SQLEnum, inspect, text
from sqlalchemy.engine import Connection

from backend import db, migrate
from backend.models.user_preferences import User_Preferences  # noqa: F401
from backend.models.users import Users  # noqa: F401

pytestmark = pytest.mark.cli

_PRE_REVISION = "e1a4c7f2b9d6"
_USER_PREFERENCES_REVISION = "58dfdcfa3921"

_USER_PREFERENCES_TABLE = "UserPreferences"
_USERS_TABLE = "Users"
_ALEMBIC_VERSION_TABLE = "alembic_version"
_EXPECTED_USER_PREFERENCES_COLUMNS = {
    "id",
    "userID",
    "theme",
    "defaultView",
    "defaultSort",
    "density",
    "dateFormat",
    "createdAt",
    "updatedAt",
}
_EXPECTED_USER_PREFERENCES_UNIQUE_CONSTRAINTS = {
    "unique_user_preferences",
}
_ENUM_BACKED_COLUMNS = {
    "theme",
    "defaultView",
    "defaultSort",
    "density",
    "dateFormat",
}

_MANAGEDB_DROP_ARGS = ["managedb", "drop", "test"]
_ADDMOCK_ALL_ARGS = ["addmock", "all"]


def _build_alembic_config() -> Config:
    alembic_config = Config("./migrations/alembic.ini")
    alembic_config.set_main_option("script_location", "migrations/")
    return alembic_config


def _capture_row_counts(connection: Connection) -> dict[str, int]:
    """Return a per-table row count for every persisted table except the
    Alembic bookkeeping table, keyed by table name.

    Used to prove the UserPreferences migration up/down roundtrip preserves the
    mock dataset seeded by ``flask addmock all`` (drift-proof row-count equality,
    per CLAUDE.md — never hardcode counts). Both snapshots are captured while the
    table is absent (after downgrading), so neither includes UserPreferences.
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


def test_add_user_preferences_migration_upgrade_and_downgrade(runner):
    """
    GIVEN a database at revision e1a4c7f2b9d6 (pre-UserPreferences) seeded with
        the full mock dataset via ``flask addmock all``
    WHEN the 58dfdcfa3921 migration is applied, reverted, and re-applied
    THEN the UserPreferences table, its camelCase columns, native enum columns,
        and named unique constraint are created on upgrade; every seeded row
        survives the up/down roundtrip (row-count equality); the table is dropped
        on downgrade and the named enum TYPEs are cleaned up so a re-upgrade
        does not raise DuplicateObject — confirming the migration is reversible
        against the real seeded dataset (per CLAUDE.md).

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    os.environ["PYTEST_RUNNING"] = "1"  # Silence alembic logging for this test
    app, cli_runner = runner
    migrate.init_app(app)

    cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)

    with app.app_context():
        # Seed at head (the ORM models match the head schema — seeding at a
        # historical revision would fail on columns added by later migrations),
        # then downgrade to the pre-UserPreferences revision so the migration
        # under test is exercised against a populated dataset.
        command.upgrade(_build_alembic_config(), "head")
        cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)
        command.downgrade(_build_alembic_config(), _PRE_REVISION)

        inspector = inspect(db.engine)
        assert not inspector.has_table(_USER_PREFERENCES_TABLE)

        # Baseline snapshot taken AFTER downgrading, while UserPreferences is
        # absent, so both snapshots exclude the new table.
        with db.engine.connect() as connection:
            row_counts_before_roundtrip = _capture_row_counts(connection)
        assert row_counts_before_roundtrip[_USERS_TABLE] > 0

        command.upgrade(_build_alembic_config(), "head")

        inspector = inspect(db.engine)
        assert inspector.has_table(_USER_PREFERENCES_TABLE)
        actual_columns = {
            column["name"] for column in inspector.get_columns(_USER_PREFERENCES_TABLE)
        }
        assert actual_columns == _EXPECTED_USER_PREFERENCES_COLUMNS
        actual_unique_constraints = {
            unique_constraint["name"]
            for unique_constraint in inspector.get_unique_constraints(
                _USER_PREFERENCES_TABLE
            )
        }
        assert (
            actual_unique_constraints == _EXPECTED_USER_PREFERENCES_UNIQUE_CONSTRAINTS
        )
        # Each enum-backed column must be a native Postgres enum type, not a
        # plain string, so the values_callable lowercase contract is enforced by
        # the database.
        columns_by_name = {
            column["name"]: column
            for column in inspector.get_columns(_USER_PREFERENCES_TABLE)
        }
        for enum_column_name in _ENUM_BACKED_COLUMNS:
            assert isinstance(columns_by_name[enum_column_name]["type"], SQLEnum)

        command.downgrade(_build_alembic_config(), _PRE_REVISION)

        inspector = inspect(db.engine)
        assert not inspector.has_table(_USER_PREFERENCES_TABLE)

        with db.engine.connect() as connection:
            row_counts_after_roundtrip = _capture_row_counts(connection)
        assert row_counts_after_roundtrip == row_counts_before_roundtrip

        # Re-upgrade must be idempotent: this is the assertion that would fail
        # with a DuplicateObject error if downgrade() did not drop the named
        # enum TYPEs.
        command.upgrade(_build_alembic_config(), "head")

        inspector = inspect(db.engine)
        assert inspector.has_table(_USER_PREFERENCES_TABLE)

        # Schema is now fully migrated to head; recreate any tables the
        # migrations left absent so the runner fixture teardown operates against
        # the full schema for subsequent tests.
        db.create_all()

    del os.environ["PYTEST_RUNNING"]
