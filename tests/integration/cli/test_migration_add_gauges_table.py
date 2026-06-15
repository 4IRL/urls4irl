import os
from datetime import datetime, timezone

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect, text

from backend import db, migrate

pytestmark = pytest.mark.cli

_PRE_GAUGE_REVISION = "a3f9c1e7b2d4"
_GAUGE_REVISION = "53e2183f1a73"

_GAUGES_TABLE = "AnonymousGauges"
_EXPECTED_GAUGE_COLUMNS = {
    "id",
    "gaugeName",
    "sampledAt",
    "valueInt",
    "valueFloat",
    "dimensions",
}

_SEED_USERNAME = "gauge_migration_user"
_SEED_EMAIL = "gauge_migration_user@example.com"
_SEED_PASSWORD = "hashed-placeholder"
_SEED_UTUB_NAME = "Gauge Migration UTub"
_SEED_TIMESTAMP = datetime(2026, 6, 14, 11, 0, 0, tzinfo=timezone.utc)

_SAMPLE_GAUGE_NAME = "total_users"
_SAMPLE_VALUE_INT = 42


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


def _user_exists(connection) -> bool:
    return (
        connection.execute(
            text('SELECT COUNT(*) FROM "Users" WHERE username = :username'),
            {"username": _SEED_USERNAME},
        ).scalar_one()
        == 1
    )


def _utub_exists(connection) -> bool:
    return (
        connection.execute(
            text('SELECT COUNT(*) FROM "Utubs" WHERE "utubName" = :name'),
            {"name": _SEED_UTUB_NAME},
        ).scalar_one()
        == 1
    )


def test_add_gauges_table_upgrade_and_downgrade(runner):
    """
    GIVEN a database at revision a3f9c1e7b2d4 (pre-gauge) seeded with one
        Users row and one Utubs row
    WHEN the 53e2183f1a73 migration is applied (`upgrade head`), reverted
        (`downgrade a3f9c1e7b2d4`), and re-applied (`upgrade head`)
    THEN the AnonymousGauges table and its six columns are created on upgrade,
        the pre-existing Users/Utubs rows survive every transition unchanged, a
        gauge row round-trips while the table exists, the table is dropped on
        downgrade, and the re-apply is idempotent — confirming the migration is
        reversible in both directions against real seeded data (per CLAUDE.md).

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    os.environ["PYTEST_RUNNING"] = "1"  # Silence alembic logging for this test
    app, cli_runner = runner
    migrate.init_app(app)

    # build_app provisions the schema via db.create_all() (no alembic_version row),
    # so drop the schema and rebuild it via migrations up to the pre-gauge
    # revision — this gives alembic a real version context to downgrade/upgrade
    # against, mirroring test_migration_rename_navbar_dropdown_events.
    cli_runner.invoke(args=["managedb", "drop", "test"])

    with app.app_context():
        command.upgrade(_build_alembic_config(), _PRE_GAUGE_REVISION)

        inspector = inspect(db.engine)
        assert not inspector.has_table(_GAUGES_TABLE)

        with db.engine.begin() as connection:
            seeded_user_id = _seed_user(connection)
            _seed_utub(connection, seeded_user_id)

        with db.engine.connect() as connection:
            assert _user_exists(connection)
            assert _utub_exists(connection)

        command.upgrade(_build_alembic_config(), "head")

        inspector = inspect(db.engine)
        assert inspector.has_table(_GAUGES_TABLE)
        actual_columns = {
            column["name"] for column in inspector.get_columns(_GAUGES_TABLE)
        }
        assert _EXPECTED_GAUGE_COLUMNS == actual_columns

        with db.engine.connect() as connection:
            assert _user_exists(connection)
            assert _utub_exists(connection)

        with db.engine.begin() as connection:
            connection.execute(
                text(
                    'INSERT INTO "AnonymousGauges" '
                    '("gaugeName", "sampledAt", "valueInt", dimensions) '
                    "VALUES (:name, :sampled_at, :value_int, "
                    "CAST('{}' AS JSONB))"
                ),
                {
                    "name": _SAMPLE_GAUGE_NAME,
                    "sampled_at": _SEED_TIMESTAMP,
                    "value_int": _SAMPLE_VALUE_INT,
                },
            )

        with db.engine.connect() as connection:
            readback_value = connection.execute(
                text(
                    'SELECT "valueInt" FROM "AnonymousGauges" '
                    'WHERE "gaugeName" = :name'
                ),
                {"name": _SAMPLE_GAUGE_NAME},
            ).scalar_one()
            assert readback_value == _SAMPLE_VALUE_INT

        command.downgrade(_build_alembic_config(), _PRE_GAUGE_REVISION)

        inspector = inspect(db.engine)
        assert not inspector.has_table(_GAUGES_TABLE)

        with db.engine.connect() as connection:
            assert _user_exists(connection)
            assert _utub_exists(connection)

        command.upgrade(_build_alembic_config(), "head")

        inspector = inspect(db.engine)
        assert inspector.has_table(_GAUGES_TABLE)

        # Schema is now fully migrated to head; recreate any tables the
        # migrations left absent so the runner fixture teardown (clear_database)
        # operates against the full schema for subsequent tests.
        db.create_all()

    del os.environ["PYTEST_RUNNING"]
