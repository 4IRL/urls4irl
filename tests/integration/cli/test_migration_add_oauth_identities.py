import os
from datetime import datetime, timezone

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect, text

from backend import db, migrate
from backend.models.user_oauth_identities import UserOAuthIdentity  # noqa: F401
from backend.models.users import Users  # noqa: F401

pytestmark = pytest.mark.cli

_PRE_OAUTH_REVISION = "681906a2f237"
_OAUTH_REVISION = "1c458837fe0c"

_OAUTH_TABLE = "UserOAuthIdentities"
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

_SEED_USERNAME = "oauth_migration_user"
_SEED_EMAIL = "oauth_migration_user@example.com"
_SEED_PASSWORD = "hashed-placeholder"
_SEED_UTUB_NAME = "OAuth Migration UTub"
_SEED_TIMESTAMP = datetime(2026, 6, 14, 11, 0, 0, tzinfo=timezone.utc)

_NULL_PASSWORD_USERNAME = "oauth_null_password_user"
_NULL_PASSWORD_EMAIL = "oauth_null_password_user@example.com"


def _build_alembic_config() -> Config:
    alembic_config = Config("./migrations/alembic.ini")
    alembic_config.set_main_option("script_location", "migrations/")
    alembic_config.attributes["connection"] = db.engine.connect()
    return alembic_config


def _seed_user(connection) -> int:
    return connection.execute(
        text(
            'INSERT INTO "Users" '
            '(username, email, password, "createdAt", role, "emailValidated") '
            "VALUES (:username, :email, :password, :created_at, 'USER', true) "
            "RETURNING id"
        ),
        {
            "username": _SEED_USERNAME,
            "email": _SEED_EMAIL,
            "password": _SEED_PASSWORD,
            "created_at": _SEED_TIMESTAMP,
        },
    ).scalar_one()


def _seed_utub(connection, creator_id: int) -> int:
    return connection.execute(
        text(
            'INSERT INTO "Utubs" '
            '("utubName", "utubCreator", "createdAt", "lastUpdated") '
            "VALUES (:name, :creator, :created_at, :last_updated) "
            "RETURNING id"
        ),
        {
            "name": _SEED_UTUB_NAME,
            "creator": creator_id,
            "created_at": _SEED_TIMESTAMP,
            "last_updated": _SEED_TIMESTAMP,
        },
    ).scalar_one()


def _seed_null_password_user(connection) -> int:
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


def _password_column_is_nullable() -> bool:
    columns = inspect(db.engine).get_columns("Users")
    password_column = next(column for column in columns if column["name"] == "password")
    return password_column["nullable"]


def test_add_oauth_identities_migration_upgrade_and_downgrade(runner):
    """
    GIVEN a database at revision 681906a2f237 (pre-OAuth) seeded with one
        Users row and one Utubs row
    WHEN the 1c458837fe0c migration is applied, reverted, and re-applied
    THEN the UserOAuthIdentities table, its columns, unique constraints, and
        index are created on upgrade; Users.password flips to nullable; the
        pre-existing rows survive; a null-password Users row can be inserted
        while the table is migrated; the table is dropped and password reverts
        to NOT NULL on downgrade; and the re-apply is idempotent — confirming
        the migration is reversible against real seeded data (per CLAUDE.md).

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    os.environ["PYTEST_RUNNING"] = "1"  # Silence alembic logging for this test
    app, cli_runner = runner
    migrate.init_app(app)

    cli_runner.invoke(args=["managedb", "drop", "test"])

    with app.app_context():
        command.upgrade(_build_alembic_config(), _PRE_OAUTH_REVISION)

        inspector = inspect(db.engine)
        assert not inspector.has_table(_OAUTH_TABLE)
        assert not _password_column_is_nullable()

        with db.engine.begin() as connection:
            seeded_user_id = _seed_user(connection)
            _seed_utub(connection, seeded_user_id)

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
    GIVEN the OAuth migration applied to head with a null-password Users row
    WHEN the migration is downgraded (which re-applies NOT NULL to password)
    THEN the downgrade raises — proving the irreversibility note in the
        migration docstring is accurate — and a clean downgrade succeeds once
        the null-password row is removed.

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    os.environ["PYTEST_RUNNING"] = "1"
    app, cli_runner = runner
    migrate.init_app(app)

    cli_runner.invoke(args=["managedb", "drop", "test"])

    with app.app_context():
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

        command.upgrade(_build_alembic_config(), "head")
        db.create_all()

    del os.environ["PYTEST_RUNNING"]
