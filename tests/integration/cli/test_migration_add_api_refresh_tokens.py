import os

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from backend import db, migrate
from backend.models.api_refresh_tokens import ApiRefreshTokens  # noqa: F401

pytestmark = pytest.mark.cli

_PRE_API_REFRESH_TOKENS_REVISION = "1c458837fe0c"

_API_REFRESH_TOKENS_TABLE = "ApiRefreshTokens"
_USERS_TABLE = "Users"
_ALEMBIC_VERSION_TABLE = "alembic_version"
_EXPECTED_COLUMNS = {
    "id",
    "userID",
    "token",
    "familyId",
    "issuedAt",
    "expiresAt",
    "rotatedAt",
    "replacedBy",
    "revokedAt",
}
_EXPECTED_UNIQUE_CONSTRAINTS = {"unique_api_refresh_token"}
_EXPECTED_INDEXES = {"idx_api_refresh_token_user", "idx_api_refresh_token_family"}

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

    Proves the ApiRefreshTokens migration up/down roundtrip preserves the mock
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


def test_add_api_refresh_tokens_migration_upgrade_and_downgrade(runner):
    """
    GIVEN a database at revision 1c458837fe0c (pre-ApiRefreshTokens) seeded
        with the full mock dataset via ``flask addmock all``
    WHEN the c9e4f1a52b83 migration is applied, reverted, and re-applied
    THEN the ApiRefreshTokens table, its columns, unique constraint, and
        indexes are created on upgrade; every seeded row survives the up/down
        roundtrip (row-count equality); the table is dropped on downgrade; and
        the re-apply is idempotent — confirming the migration is reversible
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
        # historical revision would fail on columns added by later
        # migrations), then downgrade to the pre-ApiRefreshTokens revision so
        # the migration under test is exercised against a populated dataset.
        command.upgrade(_build_alembic_config(), "head")
        cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)
        command.downgrade(_build_alembic_config(), _PRE_API_REFRESH_TOKENS_REVISION)

        inspector = inspect(db.engine)
        assert not inspector.has_table(_API_REFRESH_TOKENS_TABLE)

        with db.engine.connect() as connection:
            row_counts_before_roundtrip = _capture_row_counts(connection)
        assert row_counts_before_roundtrip[_USERS_TABLE] > 0

        command.upgrade(_build_alembic_config(), "head")

        inspector = inspect(db.engine)
        assert inspector.has_table(_API_REFRESH_TOKENS_TABLE)
        actual_columns = {
            column["name"]
            for column in inspector.get_columns(_API_REFRESH_TOKENS_TABLE)
        }
        assert actual_columns == _EXPECTED_COLUMNS
        actual_unique_constraints = {
            unique_constraint["name"]
            for unique_constraint in inspector.get_unique_constraints(
                _API_REFRESH_TOKENS_TABLE
            )
        }
        assert actual_unique_constraints == _EXPECTED_UNIQUE_CONSTRAINTS
        actual_indexes = {
            index["name"] for index in inspector.get_indexes(_API_REFRESH_TOKENS_TABLE)
        }
        assert _EXPECTED_INDEXES <= actual_indexes

        command.downgrade(_build_alembic_config(), _PRE_API_REFRESH_TOKENS_REVISION)

        inspector = inspect(db.engine)
        assert not inspector.has_table(_API_REFRESH_TOKENS_TABLE)

        with db.engine.connect() as connection:
            row_counts_after_roundtrip = _capture_row_counts(connection)
        assert row_counts_after_roundtrip == row_counts_before_roundtrip

        command.upgrade(_build_alembic_config(), "head")

        inspector = inspect(db.engine)
        assert inspector.has_table(_API_REFRESH_TOKENS_TABLE)

        # Schema is now fully migrated to head; recreate any tables the
        # migrations left absent so the runner fixture teardown operates
        # against the full schema for subsequent tests.
        db.create_all()

    del os.environ["PYTEST_RUNNING"]
