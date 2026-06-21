import importlib.util
import os
from datetime import date, datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect, text

from backend import db, migrate

pytestmark = pytest.mark.cli

_ROLLUP_REVISION = "af33bd794058"
_ROLLUP_MIGRATION_FILE = (
    Path(__file__).resolve().parents[3]
    / "migrations"
    / "versions"
    / f"{_ROLLUP_REVISION}_add_anonymouslatencydailyrollups_table.py"
)


def _load_pre_revision() -> str:
    """Read `down_revision` directly off the generated migration module.

    Hardcoding the pre-revision would silently break if another migration lands
    ahead of this one before implementation; reading it from the file keeps the
    test in sync with whatever chain head the generator targeted.
    """
    spec = importlib.util.spec_from_file_location(
        "_rollup_migration", _ROLLUP_MIGRATION_FILE
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.down_revision


_PRE_REVISION = _load_pre_revision()

_ROLLUP_TABLE = "AnonymousLatencyDailyRollups"
_EXPECTED_ROLLUP_COLUMNS = {
    "id",
    "metricName",
    "endpoint",
    "method",
    "rollupDate",
    "p50Ms",
    "p95Ms",
    "p99Ms",
    "sampleCount",
    "dimensions",
}
_EXPECTED_ROLLUP_INDEXES = {
    "idx_latency_rollup_metric_date",
    "idx_latency_rollup_endpoint_date",
}
_EXPECTED_ROLLUP_UNIQUE_CONSTRAINT = "unique_latency_rollup_day"

_SEED_USERNAME = "latency_rollup_migr"
_SEED_EMAIL = "latency_rollup_migration_user@example.com"
_SEED_PASSWORD = "hashed-placeholder"
_SEED_UTUB_NAME = "Latency Rollup Migration UTub"
_SEED_TIMESTAMP = datetime(2026, 6, 20, 11, 0, 0, tzinfo=timezone.utc)

_SAMPLE_METRIC_NAME = "api_request_duration"
_SAMPLE_ENDPOINT = "utubs.get_utub"
_SAMPLE_METHOD = "GET"
_SAMPLE_ROLLUP_DATE = date(2026, 6, 19)
_SAMPLE_P50_MS = 55.0
_SAMPLE_P95_MS = 95.5
_SAMPLE_P99_MS = 99.1
_SAMPLE_SAMPLE_COUNT = 10


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


def test_add_latency_rollups_table_upgrade_and_downgrade(runner):
    """
    GIVEN a database at the pre-rollup revision seeded with one Users row and
        one Utubs row
    WHEN the latency-rollup migration is applied (`upgrade head`), reverted
        (`downgrade <pre>`), and re-applied (`upgrade head`)
    THEN the AnonymousLatencyDailyRollups table, its ten columns, and both
        indexes are created on upgrade, the pre-existing Users/Utubs rows survive
        every transition unchanged, a rollup row round-trips while the table
        exists, the table is dropped on downgrade, and the re-apply is
        idempotent — confirming the migration is reversible in both directions
        against real seeded data (per CLAUDE.md).

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    os.environ["PYTEST_RUNNING"] = "1"  # Silence alembic logging for this test
    app, cli_runner = runner
    migrate.init_app(app)

    # build_app provisions the schema via db.create_all() (no alembic_version row),
    # so drop the schema and rebuild it via migrations up to the pre-rollup
    # revision — this gives alembic a real version context to downgrade/upgrade
    # against, mirroring test_migration_add_latency_samples_table.
    cli_runner.invoke(args=["managedb", "drop", "test"])

    with app.app_context():
        command.upgrade(_build_alembic_config(), _PRE_REVISION)

        inspector = inspect(db.engine)
        assert not inspector.has_table(_ROLLUP_TABLE)

        with db.engine.begin() as connection:
            seeded_user_id = _seed_user(connection)
            _seed_utub(connection, seeded_user_id)

        with db.engine.connect() as connection:
            assert _user_exists(connection)
            assert _utub_exists(connection)

        command.upgrade(_build_alembic_config(), "head")

        inspector = inspect(db.engine)
        assert inspector.has_table(_ROLLUP_TABLE)
        actual_columns = {
            column["name"] for column in inspector.get_columns(_ROLLUP_TABLE)
        }
        assert _EXPECTED_ROLLUP_COLUMNS == actual_columns
        # Postgres backs a UniqueConstraint with a unique index, so
        # get_indexes() surfaces unique_latency_rollup_day alongside the two
        # explicit indexes; assert the constraint via get_unique_constraints()
        # and compare only the non-unique indexes against the explicit set.
        actual_indexes = {
            index["name"]
            for index in inspector.get_indexes(_ROLLUP_TABLE)
            if not index.get("unique")
        }
        assert _EXPECTED_ROLLUP_INDEXES == actual_indexes
        actual_unique_constraints = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints(_ROLLUP_TABLE)
        }
        assert _EXPECTED_ROLLUP_UNIQUE_CONSTRAINT in actual_unique_constraints

        with db.engine.connect() as connection:
            assert _user_exists(connection)
            assert _utub_exists(connection)

        with db.engine.begin() as connection:
            connection.execute(
                text(
                    'INSERT INTO "AnonymousLatencyDailyRollups" '
                    '("metricName", endpoint, method, "rollupDate", '
                    '"p50Ms", "p95Ms", "p99Ms", "sampleCount") '
                    "VALUES (:metric_name, :endpoint, :method, :rollup_date, "
                    ":p50_ms, :p95_ms, :p99_ms, :sample_count)"
                ),
                {
                    "metric_name": _SAMPLE_METRIC_NAME,
                    "endpoint": _SAMPLE_ENDPOINT,
                    "method": _SAMPLE_METHOD,
                    "rollup_date": _SAMPLE_ROLLUP_DATE,
                    "p50_ms": _SAMPLE_P50_MS,
                    "p95_ms": _SAMPLE_P95_MS,
                    "p99_ms": _SAMPLE_P99_MS,
                    "sample_count": _SAMPLE_SAMPLE_COUNT,
                },
            )

        with db.engine.connect() as connection:
            readback_p95, readback_count = connection.execute(
                text(
                    'SELECT "p95Ms", "sampleCount" '
                    'FROM "AnonymousLatencyDailyRollups" '
                    'WHERE "metricName" = :metric_name'
                ),
                {"metric_name": _SAMPLE_METRIC_NAME},
            ).one()
            assert float(readback_p95) == _SAMPLE_P95_MS
            assert readback_count == _SAMPLE_SAMPLE_COUNT

        command.downgrade(_build_alembic_config(), _PRE_REVISION)

        inspector = inspect(db.engine)
        assert not inspector.has_table(_ROLLUP_TABLE)

        with db.engine.connect() as connection:
            assert _user_exists(connection)
            assert _utub_exists(connection)

        command.upgrade(_build_alembic_config(), "head")

        inspector = inspect(db.engine)
        assert inspector.has_table(_ROLLUP_TABLE)

        # Schema is now fully migrated to head; recreate any tables the
        # migrations left absent so the runner fixture teardown (clear_database)
        # operates against the full schema for subsequent tests.
        db.create_all()

    del os.environ["PYTEST_RUNNING"]
