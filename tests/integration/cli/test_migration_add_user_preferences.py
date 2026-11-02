import json
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DataError

from backend import db, migrate
from backend.models.user_preferences import User_Preferences  # noqa: F401
from backend.models.users import Users  # noqa: F401

pytestmark = pytest.mark.cli

_PRE_REVISION = "e1a4c7f2b9d6"
_USER_PREFERENCES_REVISION = "58dfdcfa3921"
_PRE_VIEW_SPLIT_REVISION = "7c3f9a1b5d82"
_VIEW_SPLIT_REVISION = "b3e7c1d9a4f2"

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
    "utubSort",
    "memberSort",
    "showRowCounts",
    "showListTotals",
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
    "utubSort",
    "memberSort",
}

_PRE_UTUB_LIST_REVISION = _VIEW_SPLIT_REVISION
_UTUB_SORT_ENUM = "utub_sort_enum"

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


def _seed_view_mode_rows(
    connection: Connection, view_modes: tuple[str, str]
) -> tuple[list[int], list[int]]:
    """Insert a UserPreferences row and set a member settings JSONB (with a
    sibling ``sort`` key) for two users / members, one per given view mode.

    Returns the seeded (user ids, member row ids).
    """
    # One membership per user (its lowest utubID); UtubMembers has a composite
    # primary key (utubID, userID), so a member is identified by that pair.
    member_rows = connection.execute(
        text(
            'SELECT "userID", MIN("utubID") FROM "UtubMembers" '
            'GROUP BY "userID" ORDER BY "userID" LIMIT 2'
        )
    ).all()
    assert len(member_rows) == 2
    user_ids = [row[0] for row in member_rows]
    member_ids = [row[1] for row in member_rows]
    for user_id, member_id, view_mode in zip(user_ids, member_ids, view_modes):
        connection.execute(
            text('DELETE FROM "UserPreferences" WHERE "userID" = :user_id'),
            {"user_id": user_id},
        )
        connection.execute(
            text(
                'INSERT INTO "UserPreferences" ("userID", theme, "defaultView", '
                '"defaultSort", density, "dateFormat", "createdAt", "updatedAt") '
                "VALUES (:user_id, 'system', CAST(:view_mode AS view_mode_enum), "
                "'newest', 'comfortable', 'iso', now(), now())"
            ),
            {"user_id": user_id, "view_mode": view_mode},
        )
        connection.execute(
            text(
                'UPDATE "UtubMembers" SET settings = CAST(:settings AS jsonb) '
                'WHERE "utubID" = :utub_id AND "userID" = :user_id'
            ),
            {
                "settings": json.dumps(
                    {"urls": {"view_mode": view_mode, "sort": "oldest"}}
                ),
                "utub_id": member_id,
                "user_id": user_id,
            },
        )
    return user_ids, member_ids


def _assert_default_view_not_null_without_default(connection: Connection) -> None:
    is_nullable, column_default = connection.execute(
        text(
            "SELECT is_nullable, column_default FROM information_schema.columns "
            "WHERE table_name = 'UserPreferences' AND column_name = 'defaultView'"
        )
    ).one()
    assert is_nullable == "NO"
    assert column_default is None


def _read_view_modes(
    connection: Connection, user_ids: list[int], member_ids: list[int]
) -> tuple[list[str], list[str], list[str]]:
    """Return (column view modes, JSONB view modes, JSONB sort values)."""
    column_modes = [
        connection.execute(
            text(
                'SELECT "defaultView"::text FROM "UserPreferences" WHERE "userID" = :u'
            ),
            {"u": user_id},
        ).scalar_one()
        for user_id in user_ids
    ]
    jsonb_modes = []
    jsonb_sorts = []
    for user_id, member_id in zip(user_ids, member_ids):
        settings = connection.execute(
            text(
                'SELECT settings FROM "UtubMembers" '
                'WHERE "utubID" = :utub_id AND "userID" = :user_id'
            ),
            {"utub_id": member_id, "user_id": user_id},
        ).scalar_one()
        jsonb_modes.append(settings["urls"]["view_mode"])
        jsonb_sorts.append(settings["urls"]["sort"])
    return column_modes, jsonb_modes, jsonb_sorts


def test_view_mode_title_and_url_line_migration_upgrade_and_downgrade(runner):
    """
    GIVEN a database at the pre-split revision seeded with ``flask addmock all``,
        a ``compact`` preference column and member JSONB (with a sibling key)
    WHEN b3e7c1d9a4f2 is applied, a ``url_line`` row is added, and it is reverted
    THEN every ``compact`` reads ``title_line`` after upgrade, every
        ``title_line``/``url_line`` reads ``compact`` after downgrade, sibling
        JSONB keys survive, and ``defaultView`` stays NOT NULL

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    os.environ["PYTEST_RUNNING"] = "1"
    app, cli_runner = runner
    migrate.init_app(app)

    cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)

    with app.app_context():
        command.upgrade(_build_alembic_config(), "head")
        cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)
        command.downgrade(_build_alembic_config(), _PRE_VIEW_SPLIT_REVISION)

        with db.engine.begin() as connection:
            user_ids, member_ids = _seed_view_mode_rows(connection, ("compact", "list"))

        command.upgrade(_build_alembic_config(), _VIEW_SPLIT_REVISION)

        with db.engine.begin() as connection:
            column_modes, jsonb_modes, jsonb_sorts = _read_view_modes(
                connection, user_ids, member_ids
            )
            assert column_modes == ["title_line", "list"]
            assert jsonb_modes == ["title_line", "list"]
            assert jsonb_sorts == ["oldest", "oldest"]
            _assert_default_view_not_null_without_default(connection)
            # Switch the second row to url_line so downgrade must map both.
            connection.execute(
                text(
                    'UPDATE "UserPreferences" SET "defaultView" = '
                    "CAST('url_line' AS view_mode_enum) WHERE \"userID\" = :u"
                ),
                {"u": user_ids[1]},
            )
            connection.execute(
                text(
                    'UPDATE "UtubMembers" SET settings = jsonb_set(settings, '
                    "'{urls,view_mode}', '\"url_line\"') "
                    'WHERE "utubID" = :utub_id AND "userID" = :user_id'
                ),
                {"utub_id": member_ids[1], "user_id": user_ids[1]},
            )

        command.downgrade(_build_alembic_config(), _PRE_VIEW_SPLIT_REVISION)

        with db.engine.connect() as connection:
            column_modes, jsonb_modes, jsonb_sorts = _read_view_modes(
                connection, user_ids, member_ids
            )
            assert column_modes == ["compact", "compact"]
            assert jsonb_modes == ["compact", "compact"]
            assert jsonb_sorts == ["oldest", "oldest"]
            _assert_default_view_not_null_without_default(connection)

        command.upgrade(_build_alembic_config(), "head")
        db.create_all()

    del os.environ["PYTEST_RUNNING"]


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


def _enum_type_exists(connection: Connection) -> bool:
    return bool(
        connection.execute(
            text("SELECT 1 FROM pg_type WHERE typname = :name"),
            {"name": _UTUB_SORT_ENUM},
        ).scalar()
    )


def test_add_utub_list_preferences_migration_roundtrip(runner):
    """
    GIVEN a database at revision b3e7c1d9a4f2 holding seeded UserPreferences rows
    WHEN the b4e8a2c6d0f1 migration is applied, reverted and re-applied
    THEN existing rows backfill to recent_activity / counts off / totals on,
        non-default values store and read back, an invalid enum value is
        rejected, the downgrade removes the columns and the enum type, and the
        re-upgrade succeeds.

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    os.environ["PYTEST_RUNNING"] = "1"
    app, cli_runner = runner
    migrate.init_app(app)

    cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)

    with app.app_context():
        command.upgrade(_build_alembic_config(), "head")
        cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)
        command.downgrade(_build_alembic_config(), _PRE_UTUB_LIST_REVISION)

        inspector = inspect(db.engine)
        pre_columns = {
            column["name"] for column in inspector.get_columns(_USER_PREFERENCES_TABLE)
        }
        assert "utubSort" not in pre_columns
        with db.engine.connect() as connection:
            assert not _enum_type_exists(connection)
            preference_row_count = connection.execute(
                text('SELECT COUNT(*) FROM "UserPreferences"')
            ).scalar_one()
        assert preference_row_count > 0

        command.upgrade(_build_alembic_config(), "head")

        with db.engine.connect() as connection:
            backfilled = connection.execute(
                text(
                    'SELECT COUNT(*) FROM "UserPreferences" WHERE "utubSort" = '
                    "'recent_activity' AND NOT \"showRowCounts\" "
                    'AND "showListTotals"'
                )
            ).scalar_one()
        assert backfilled == preference_row_count

        # Non-default values store and read back (the mock seed stays at defaults).
        with db.engine.begin() as connection:
            connection.execute(
                text(
                    'UPDATE "UserPreferences" SET "utubSort" = \'name_az\', '
                    '"showRowCounts" = true, "showListTotals" = false '
                    'WHERE id = (SELECT MIN(id) FROM "UserPreferences")'
                )
            )
        with db.engine.connect() as connection:
            stored = connection.execute(
                text(
                    'SELECT "utubSort"::text, "showRowCounts", "showListTotals" '
                    'FROM "UserPreferences" ORDER BY id LIMIT 1'
                )
            ).one()
        assert tuple(stored) == ("name_az", True, False)

        # The DB enum rejects an invalid value.
        with pytest.raises(DataError) as excinfo:
            with db.engine.begin() as connection:
                connection.execute(
                    text(
                        'UPDATE "UserPreferences" SET "utubSort" = \'bogus\' '
                        'WHERE id = (SELECT MIN(id) FROM "UserPreferences")'
                    )
                )
        assert _UTUB_SORT_ENUM in str(
            excinfo.value
        ) or "invalid input value for enum" in str(excinfo.value)

        command.downgrade(_build_alembic_config(), _PRE_UTUB_LIST_REVISION)

        inspector = inspect(db.engine)
        post_columns = {
            column["name"] for column in inspector.get_columns(_USER_PREFERENCES_TABLE)
        }
        assert post_columns.isdisjoint({"utubSort", "showRowCounts", "showListTotals"})
        with db.engine.connect() as connection:
            assert not _enum_type_exists(connection)

        command.upgrade(_build_alembic_config(), "head")

        inspector = inspect(db.engine)
        assert {"utubSort", "showRowCounts", "showListTotals"} <= {
            column["name"] for column in inspector.get_columns(_USER_PREFERENCES_TABLE)
        }

        db.create_all()

    del os.environ["PYTEST_RUNNING"]
