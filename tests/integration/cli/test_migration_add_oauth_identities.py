import os
from datetime import datetime, timezone

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from backend import db, migrate
from backend.models.user_oauth_identities import UserOAuthIdentity  # noqa: F401
from backend.models.users import Users  # noqa: F401

pytestmark = pytest.mark.cli

_PRE_OAUTH_REVISION = "681906a2f237"
_OAUTH_REVISION = "1c458837fe0c"

_OAUTH_TABLE = "UserOAuthIdentities"
_USERS_TABLE = "Users"
_ALEMBIC_VERSION_TABLE = "alembic_version"
_EXPECTED_OAUTH_COLUMNS = {
    "id",
    "userID",
    "provider",
    "providerSubject",
    "email",
    "linkedAt",
}
_EXPECTED_OAUTH_UNIQUE_CONSTRAINTS = {
    "unique_provider_subject",
    "unique_user_provider",
}
_OAUTH_INDEX = "idx_oauth_identity_user"

_MANAGEDB_DROP_ARGS = ["managedb", "drop", "test"]
_ADDMOCK_ALL_ARGS = ["addmock", "all"]

_SEED_TIMESTAMP = datetime(2026, 6, 14, 11, 0, 0, tzinfo=timezone.utc)

_NULL_PASSWORD_USERNAME = "oauth_null_password_user"
_NULL_PASSWORD_EMAIL = "oauth_null_password_user@example.com"


def _build_alembic_config() -> Config:
    alembic_config = Config("./migrations/alembic.ini")
    alembic_config.set_main_option("script_location", "migrations/")
    alembic_config.attributes["connection"] = db.engine.connect()
    return alembic_config


def _seed_null_password_user(connection: Connection) -> int:
    return connection.execute(
        text(
            'INSERT INTO "Users" '
            '(username, email, "createdAt", role, "emailValidated") '
            "VALUES (:username, :email, :created_at, 'USER', true) "
            "RETURNING id"
        ),
        {
            "username": _NULL_PASSWORD_USERNAME,
            "email": _NULL_PASSWORD_EMAIL,
            "created_at": _SEED_TIMESTAMP,
        },
    ).scalar_one()


def _capture_row_counts(connection: Connection) -> dict[str, int]:
    """Return a per-table row count for every persisted table except the
    Alembic bookkeeping table, keyed by table name.

    Used to prove the OAuth migration up/down roundtrip preserves the mock
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


def _password_column_is_nullable() -> bool:
    columns = inspect(db.engine).get_columns("Users")
    password_column = next(column for column in columns if column["name"] == "password")
    return password_column["nullable"]


def test_add_oauth_identities_migration_upgrade_and_downgrade(runner):
    """
    GIVEN a database at revision 681906a2f237 (pre-OAuth) seeded with the full
        mock dataset via ``flask addmock all``
    WHEN the 1c458837fe0c migration is applied, reverted, and re-applied
    THEN the UserOAuthIdentities table, its columns, unique constraints, and
        index are created on upgrade; Users.password flips to nullable; every
        seeded row survives the up/down roundtrip (row-count equality); a
        null-password Users row can be inserted while the table is migrated; the
        table is dropped and password reverts to NOT NULL on downgrade; and the
        re-apply is idempotent — confirming the migration is reversible against
        the real seeded dataset (per CLAUDE.md).

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
        # migrations), then downgrade to the pre-OAuth revision so the
        # migration under test is exercised against a populated dataset.
        command.upgrade(_build_alembic_config(), "head")
        cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)
        command.downgrade(_build_alembic_config(), _PRE_OAUTH_REVISION)

        inspector = inspect(db.engine)
        assert not inspector.has_table(_OAUTH_TABLE)
        assert not _password_column_is_nullable()

        with db.engine.connect() as connection:
            row_counts_before_roundtrip = _capture_row_counts(connection)
        assert row_counts_before_roundtrip[_USERS_TABLE] > 0

        command.upgrade(_build_alembic_config(), "head")

        inspector = inspect(db.engine)
        assert inspector.has_table(_OAUTH_TABLE)
        actual_columns = {
            column["name"] for column in inspector.get_columns(_OAUTH_TABLE)
        }
        assert actual_columns == _EXPECTED_OAUTH_COLUMNS
        actual_unique_constraints = {
            unique_constraint["name"]
            for unique_constraint in inspector.get_unique_constraints(_OAUTH_TABLE)
        }
        assert actual_unique_constraints == _EXPECTED_OAUTH_UNIQUE_CONSTRAINTS
        assert any(
            index["name"] == _OAUTH_INDEX
            for index in inspector.get_indexes(_OAUTH_TABLE)
        )
        assert _password_column_is_nullable()

        # Behavioral proof of the nullable contract: a null-password Users row
        # inserts cleanly while the schema is migrated. Remove it before the
        # downgrade so the NOT NULL re-apply is not blocked.
        with db.engine.begin() as connection:
            null_password_user_id = _seed_null_password_user(connection)
        with db.engine.begin() as connection:
            connection.execute(
                text('DELETE FROM "Users" WHERE id = :id'),
                {"id": null_password_user_id},
            )

        command.downgrade(_build_alembic_config(), _PRE_OAUTH_REVISION)

        inspector = inspect(db.engine)
        assert not inspector.has_table(_OAUTH_TABLE)
        assert not _password_column_is_nullable()

        with db.engine.connect() as connection:
            row_counts_after_roundtrip = _capture_row_counts(connection)
        assert row_counts_after_roundtrip == row_counts_before_roundtrip

        command.upgrade(_build_alembic_config(), "head")

        inspector = inspect(db.engine)
        assert inspector.has_table(_OAUTH_TABLE)

        # Schema is now fully migrated to head; recreate any tables the
        # migrations left absent so the runner fixture teardown operates
        # against the full schema for subsequent tests.
        db.create_all()

    del os.environ["PYTEST_RUNNING"]


def test_add_oauth_identities_migration_downgrade_blocked_by_null_password(runner):
    """
    GIVEN the OAuth migration applied to head over the full ``flask addmock all``
        dataset, plus a null-password Users row
    WHEN the migration is downgraded (which re-applies NOT NULL to password)
    THEN the downgrade raises — proving the irreversibility note in the
        migration docstring is accurate — and a clean downgrade succeeds once
        the null-password row is removed, preserving every seeded row
        (row-count equality).

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    os.environ["PYTEST_RUNNING"] = "1"
    app, cli_runner = runner
    migrate.init_app(app)

    cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)

    with app.app_context():
        # Seed at head (ORM models match head), then downgrade so the
        # row-count snapshot is taken at the pre-OAuth revision.
        command.upgrade(_build_alembic_config(), "head")
        cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)
        command.downgrade(_build_alembic_config(), _PRE_OAUTH_REVISION)

        with db.engine.connect() as connection:
            row_counts_before_roundtrip = _capture_row_counts(connection)
        assert row_counts_before_roundtrip[_USERS_TABLE] > 0

        command.upgrade(_build_alembic_config(), "head")

        with db.engine.begin() as connection:
            _seed_null_password_user(connection)

        with pytest.raises(Exception):
            command.downgrade(_build_alembic_config(), _PRE_OAUTH_REVISION)

        with db.engine.begin() as connection:
            connection.execute(text('DELETE FROM "Users" WHERE password IS NULL'))

        command.downgrade(_build_alembic_config(), _PRE_OAUTH_REVISION)

        inspector = inspect(db.engine)
        assert not inspector.has_table(_OAUTH_TABLE)
        assert not _password_column_is_nullable()

        with db.engine.connect() as connection:
            row_counts_after_roundtrip = _capture_row_counts(connection)
        assert row_counts_after_roundtrip == row_counts_before_roundtrip

        command.upgrade(_build_alembic_config(), "head")
        db.create_all()

    del os.environ["PYTEST_RUNNING"]
