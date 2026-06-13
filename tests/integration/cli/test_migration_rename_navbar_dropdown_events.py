import os
from datetime import datetime, timezone

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import text

from backend import db, migrate

pytestmark = pytest.mark.cli

_PRE_RENAME_REVISION = "0538b281d033"

_LEGACY_OPEN_EVENT = "ui_navbar_mobile_menu_open"
_LEGACY_CLOSE_EVENT = "ui_navbar_mobile_menu_close"
_RENAMED_OPEN_EVENT = "ui_navbar_dropdown_open"
_RENAMED_CLOSE_EVENT = "ui_navbar_dropdown_close"

_LEGACY_OPEN_DESCRIPTION = "Mobile hamburger menu opened"
_LEGACY_CLOSE_DESCRIPTION = "Mobile hamburger menu closed"
_RENAMED_OPEN_DESCRIPTION = "Navbar dropdown menu opened"
_RENAMED_CLOSE_DESCRIPTION = "Navbar dropdown menu closed"

_SEED_BUCKET_START = datetime(2026, 6, 13, 11, 0, 0, tzinfo=timezone.utc)
_SEED_DIMENSIONS = '{"device_type": 1}'
_SEED_COUNT = 7


def _build_alembic_config() -> Config:
    alembic_config = Config("./migrations/alembic.ini")
    alembic_config.set_main_option("script_location", "migrations/")
    alembic_config.attributes["connection"] = db.engine.connect()
    return alembic_config


def _seed_legacy_event(connection, event_name: str, description: str) -> None:
    connection.execute(
        text(
            'INSERT INTO "EventRegistry" (name, category, description) '
            "VALUES (:name, 'ui', :description) "
            "ON CONFLICT (name) DO NOTHING"
        ),
        {"name": event_name, "description": description},
    )


def _seed_legacy_metric_row(connection, event_name: str) -> None:
    connection.execute(
        text(
            'INSERT INTO "AnonymousMetrics" '
            '("eventName", "bucketStart", dimensions, count) '
            "VALUES (:event_name, :bucket_start, "
            "CAST(:dimensions AS JSONB), :count)"
        ),
        {
            "event_name": event_name,
            "bucket_start": _SEED_BUCKET_START,
            "dimensions": _SEED_DIMENSIONS,
            "count": _SEED_COUNT,
        },
    )


def _registry_names(connection) -> set[str]:
    return set(
        connection.execute(text('SELECT name FROM "EventRegistry"')).scalars().all()
    )


def _metric_event_names(connection) -> list[str]:
    return list(
        connection.execute(text('SELECT "eventName" FROM "AnonymousMetrics"'))
        .scalars()
        .all()
    )


def _metric_count_for_event(connection, event_name: str) -> int | None:
    return connection.execute(
        text('SELECT count FROM "AnonymousMetrics" WHERE "eventName" = :event_name'),
        {"event_name": event_name},
    ).scalar_one_or_none()


def test_rename_navbar_dropdown_events_upgrade_and_downgrade(runner):
    """
    GIVEN a database at revision 0538b281d033 (pre-rename) seeded with
        AnonymousMetrics rows and EventRegistry rows under the legacy
        ui_navbar_mobile_menu_open/close event names
    WHEN the a3f9c1e7b2d4 rename migration is applied (`upgrade head`),
        reverted (`downgrade 0538b281d033`), and re-applied (`upgrade head`)
    THEN the events and their metric rows are renamed to ui_navbar_dropdown_*
        on upgrade, reverted to ui_navbar_mobile_menu_* on downgrade, and the
        re-apply is idempotent — confirming the migration is reversible in
        both directions against real seeded data (per CLAUDE.md).

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    os.environ["PYTEST_RUNNING"] = "1"  # Silence alembic logging for this test
    app, cli_runner = runner
    migrate.init_app(app)

    # build_app provisions the schema via db.create_all() (no alembic_version row),
    # so drop the schema and rebuild it via migrations up to the pre-rename
    # revision — this gives alembic a real version context to downgrade/upgrade
    # against, mirroring test_drop_db_with_migrations.
    cli_runner.invoke(args=["managedb", "drop", "test"])

    with app.app_context():
        command.upgrade(_build_alembic_config(), _PRE_RENAME_REVISION)

        with db.engine.begin() as connection:
            _seed_legacy_event(connection, _LEGACY_OPEN_EVENT, _LEGACY_OPEN_DESCRIPTION)
            _seed_legacy_event(
                connection, _LEGACY_CLOSE_EVENT, _LEGACY_CLOSE_DESCRIPTION
            )
            _seed_legacy_metric_row(connection, _LEGACY_OPEN_EVENT)
            _seed_legacy_metric_row(connection, _LEGACY_CLOSE_EVENT)

        with db.engine.connect() as connection:
            registry_before = _registry_names(connection)
            metric_events_before = _metric_event_names(connection)
        assert _LEGACY_OPEN_EVENT in registry_before
        assert _LEGACY_CLOSE_EVENT in registry_before
        assert _RENAMED_OPEN_EVENT not in registry_before
        assert _RENAMED_CLOSE_EVENT not in registry_before
        assert sorted(metric_events_before) == sorted(
            [_LEGACY_OPEN_EVENT, _LEGACY_CLOSE_EVENT]
        )

        command.upgrade(_build_alembic_config(), "head")

        with db.engine.connect() as connection:
            registry_after_upgrade = _registry_names(connection)
            assert _RENAMED_OPEN_EVENT in registry_after_upgrade
            assert _RENAMED_CLOSE_EVENT in registry_after_upgrade
            assert _LEGACY_OPEN_EVENT not in registry_after_upgrade
            assert _LEGACY_CLOSE_EVENT not in registry_after_upgrade

            assert sorted(_metric_event_names(connection)) == sorted(
                [_RENAMED_OPEN_EVENT, _RENAMED_CLOSE_EVENT]
            )
            assert (
                _metric_count_for_event(connection, _RENAMED_OPEN_EVENT) == _SEED_COUNT
            )
            assert (
                _metric_count_for_event(connection, _RENAMED_CLOSE_EVENT) == _SEED_COUNT
            )
            assert _metric_count_for_event(connection, _LEGACY_OPEN_EVENT) is None
            assert _metric_count_for_event(connection, _LEGACY_CLOSE_EVENT) is None

        command.downgrade(_build_alembic_config(), _PRE_RENAME_REVISION)

        with db.engine.connect() as connection:
            registry_after_downgrade = _registry_names(connection)
            assert _LEGACY_OPEN_EVENT in registry_after_downgrade
            assert _LEGACY_CLOSE_EVENT in registry_after_downgrade
            assert _RENAMED_OPEN_EVENT not in registry_after_downgrade
            assert _RENAMED_CLOSE_EVENT not in registry_after_downgrade

            assert sorted(_metric_event_names(connection)) == sorted(
                [_LEGACY_OPEN_EVENT, _LEGACY_CLOSE_EVENT]
            )
            assert (
                _metric_count_for_event(connection, _LEGACY_OPEN_EVENT) == _SEED_COUNT
            )
            assert (
                _metric_count_for_event(connection, _LEGACY_CLOSE_EVENT) == _SEED_COUNT
            )
            assert _metric_count_for_event(connection, _RENAMED_OPEN_EVENT) is None
            assert _metric_count_for_event(connection, _RENAMED_CLOSE_EVENT) is None

        command.upgrade(_build_alembic_config(), "head")

        with db.engine.connect() as connection:
            registry_after_reapply = _registry_names(connection)
            assert _RENAMED_OPEN_EVENT in registry_after_reapply
            assert _RENAMED_CLOSE_EVENT in registry_after_reapply
            assert _LEGACY_OPEN_EVENT not in registry_after_reapply
            assert _LEGACY_CLOSE_EVENT not in registry_after_reapply

            assert sorted(_metric_event_names(connection)) == sorted(
                [_RENAMED_OPEN_EVENT, _RENAMED_CLOSE_EVENT]
            )
            assert (
                _metric_count_for_event(connection, _RENAMED_OPEN_EVENT) == _SEED_COUNT
            )
            assert (
                _metric_count_for_event(connection, _RENAMED_CLOSE_EVENT) == _SEED_COUNT
            )

        with db.engine.begin() as connection:
            connection.execute(
                text(
                    'DELETE FROM "AnonymousMetrics" WHERE "eventName" IN '
                    "(:open_event, :close_event)"
                ),
                {
                    "open_event": _RENAMED_OPEN_EVENT,
                    "close_event": _RENAMED_CLOSE_EVENT,
                },
            )

        # Schema is now fully migrated to head; recreate any tables the
        # migrations left absent so the runner fixture teardown (clear_database)
        # operates against the full schema for subsequent tests.
        db.create_all()

    del os.environ["PYTEST_RUNNING"]
