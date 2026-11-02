"""Integration test for the c5f9b3d7e1a2 migration: ``UserPreferences.memberSort``
and ``UtubMembers.joinedAt``.

Exercises upgrade -> downgrade -> upgrade against the ``flask addmock all``
dataset: existing members stay dateless, existing preference rows read
``name_az``, the server default stamps only later inserts, and the downgrade
removes both columns and the enum type.
"""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, inspect, select, table, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DataError

from backend import db, migrate
from backend.models.user_preferences import User_Preferences
from backend.models.utub_members import Utub_Members
from tests.integration.cli.utils import assert_row_counts_match_ignoring_new_tables

pytestmark = pytest.mark.cli

_PRE_REVISION: str = "f3a7c1d9e5b2"
_MEMBER_SORT_REVISION: str = "c5f9b3d7e1a2"
_UTUB_MEMBERS_TABLE: str = "UtubMembers"
_USER_PREFERENCES_TABLE: str = "UserPreferences"
_USERS_TABLE: str = "Users"
_ALEMBIC_VERSION_TABLE: str = "alembic_version"
_MEMBER_SORT_ENUM: str = "member_sort_enum"

_MANAGEDB_DROP_ARGS: list[str] = ["managedb", "drop", "test"]
_ADDMOCK_ALL_ARGS: list[str] = ["addmock", "all"]


def _build_alembic_config() -> Config:
    alembic_config = Config("./migrations/alembic.ini")
    alembic_config.set_main_option("script_location", "migrations/")
    return alembic_config


def _capture_row_counts(connection: Connection) -> dict[str, int]:
    row_counts: dict[str, int] = {}
    for table_name in inspect(connection).get_table_names():
        if table_name == _ALEMBIC_VERSION_TABLE:
            continue
        row_counts[table_name] = connection.execute(
            select(func.count()).select_from(table(table_name))
        ).scalar_one()
    return row_counts


def _column_names(connection: Connection, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(connection).get_columns(table_name)}


def _enum_type_exists(connection: Connection) -> bool:
    return bool(
        connection.execute(
            text("SELECT 1 FROM pg_type WHERE typname = :name"),
            {"name": _MEMBER_SORT_ENUM},
        ).scalar()
    )


def _joined_at_has_server_default(connection: Connection) -> bool:
    default = connection.execute(
        text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name = :table_name AND column_name = 'joinedAt'"
        ),
        {"table_name": _UTUB_MEMBERS_TABLE},
    ).scalar()
    return default is not None


def test_add_member_sort_and_joined_at_migration_roundtrips(runner) -> None:
    """
    GIVEN a database seeded with the full mock dataset, then downgraded to
        f3a7c1d9e5b2 (neither column present)
    WHEN the c5f9b3d7e1a2 migration is applied, reverted and re-applied
    THEN every existing member has a NULL ``joinedAt``, every existing
        preference row reads ``name_az``, a raw insert without ``joinedAt`` is
        stamped, the migrated columns match the model, an invalid enum value is
        rejected, and the downgrade drops both columns and the enum type with
        row counts preserved.

    Args:
        runner (pytest.fixture): Provides a Flask application and a FlaskCLIRunner.
    """
    script = ScriptDirectory.from_config(_build_alembic_config()).get_revision(
        _MEMBER_SORT_REVISION
    )
    assert script.down_revision == _PRE_REVISION
    os.environ["PYTEST_RUNNING"] = "1"
    flask_app, cli_runner = runner
    migrate.init_app(flask_app)

    try:
        cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)

        with flask_app.app_context():
            command.upgrade(_build_alembic_config(), "head")
            cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)
            command.downgrade(_build_alembic_config(), _PRE_REVISION)

            with db.engine.connect() as connection:
                assert "joinedAt" not in _column_names(connection, _UTUB_MEMBERS_TABLE)
                assert "memberSort" not in _column_names(
                    connection, _USER_PREFERENCES_TABLE
                )
                assert not _enum_type_exists(connection)
                row_counts_before = _capture_row_counts(connection)
            assert row_counts_before[_USERS_TABLE] > 0
            assert row_counts_before[_UTUB_MEMBERS_TABLE] > 0
            assert row_counts_before[_USER_PREFERENCES_TABLE] > 0

            command.upgrade(_build_alembic_config(), "head")

            with db.engine.connect() as connection:
                # Existing rows: dateless members, default sort.
                assert (
                    connection.execute(
                        text(
                            'SELECT COUNT(*) FROM "UtubMembers" WHERE "joinedAt" IS NOT NULL'
                        )
                    ).scalar_one()
                    == 0
                )
                assert (
                    connection.execute(
                        text(
                            'SELECT COUNT(*) FROM "UserPreferences" '
                            "WHERE \"memberSort\" = 'name_az'"
                        )
                    ).scalar_one()
                    == row_counts_before[_USER_PREFERENCES_TABLE]
                )

                # The server default exists and the column matches the model.
                assert _joined_at_has_server_default(connection)
                model_column = Utub_Members.__table__.columns["joinedAt"]
                assert model_column.nullable is True
                assert model_column.type.timezone is True
                assert model_column.server_default is not None
                column_info = next(
                    column
                    for column in inspect(connection).get_columns(_UTUB_MEMBERS_TABLE)
                    if column["name"] == "joinedAt"
                )
                assert column_info["nullable"] is True
                assert getattr(column_info["type"], "timezone", False) is True
                preferences_column = User_Preferences.__table__.columns["memberSort"]
                assert preferences_column.nullable is False
                assert preferences_column.server_default is not None

            # A raw insert with no joinedAt is stamped by the server default.
            with db.engine.begin() as connection:
                template_row = connection.execute(
                    text(
                        'SELECT "utubID", "userID" FROM "UtubMembers" '
                        'ORDER BY "utubID", "userID" LIMIT 1'
                    )
                ).one()
                connection.execute(
                    text(
                        'DELETE FROM "UtubMembers" WHERE "utubID" = :utub AND "userID" = :usr'
                    ),
                    {"utub": template_row[0], "usr": template_row[1]},
                )
                connection.execute(
                    text(
                        'INSERT INTO "UtubMembers" ("utubID", "userID", "memberRole") '
                        "VALUES (:utub, :usr, 'MEMBER')"
                    ),
                    {"utub": template_row[0], "usr": template_row[1]},
                )
            with db.engine.connect() as connection:
                stamped = connection.execute(
                    text(
                        'SELECT "joinedAt" FROM "UtubMembers" '
                        'WHERE "utubID" = :utub AND "userID" = :usr'
                    ),
                    {"utub": template_row[0], "usr": template_row[1]},
                ).scalar_one()
            assert stamped is not None

            # The DB enum rejects an invalid value.
            with pytest.raises(DataError):
                with db.engine.begin() as connection:
                    connection.execute(
                        text(
                            'UPDATE "UserPreferences" SET "memberSort" = \'bogus\' '
                            'WHERE id = (SELECT MIN(id) FROM "UserPreferences")'
                        )
                    )

            command.downgrade(_build_alembic_config(), _PRE_REVISION)

            with db.engine.connect() as connection:
                assert "joinedAt" not in _column_names(connection, _UTUB_MEMBERS_TABLE)
                assert "memberSort" not in _column_names(
                    connection, _USER_PREFERENCES_TABLE
                )
                assert not _enum_type_exists(connection)
                row_counts_after_downgrade = _capture_row_counts(connection)
            assert_row_counts_match_ignoring_new_tables(
                row_counts_before, row_counts_after_downgrade
            )

            command.upgrade(_build_alembic_config(), "head")

            with db.engine.connect() as connection:
                assert "joinedAt" in _column_names(connection, _UTUB_MEMBERS_TABLE)
                assert "memberSort" in _column_names(
                    connection, _USER_PREFERENCES_TABLE
                )
                assert _enum_type_exists(connection)
                row_counts_after_upgrade = _capture_row_counts(connection)
            assert_row_counts_match_ignoring_new_tables(
                row_counts_after_upgrade, row_counts_after_downgrade
            )

            db.create_all()
    finally:
        del os.environ["PYTEST_RUNNING"]
