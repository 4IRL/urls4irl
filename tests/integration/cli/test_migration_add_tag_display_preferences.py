"""Integration test for the d7a2e4c6f8b1 migration: the six personal tag display
columns on ``UserPreferences``.

Exercises upgrade -> downgrade -> upgrade against the ``flask addmock all``
dataset: existing preference rows read the defaults, a raw insert with none of
the columns proves the server defaults, an invalid enum value is rejected, and
the downgrade drops every column and enum type with row counts preserved.
"""

from __future__ import annotations

import os
from enum import Enum

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, inspect, select, table, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DataError

from backend import db, migrate
from backend.models.user_preferences import (
    CollapsedTagsStyle,
    TagCountStyle,
    TagMatchMode,
    TagSort,
    User_Preferences,
)
from tests.integration.cli.utils import assert_row_counts_match_ignoring_new_tables

pytestmark = pytest.mark.cli

_PRE_REVISION: str = "c5f9b3d7e1a2"
_TAG_DISPLAY_REVISION: str = "d7a2e4c6f8b1"
_USER_PREFERENCES_TABLE: str = "UserPreferences"
_USERS_TABLE: str = "Users"
_ALEMBIC_VERSION_TABLE: str = "alembic_version"

_TAG_COLUMNS: tuple[str, ...] = (
    "tagSort",
    "tagMatchMode",
    "tagCountStyle",
    "showTagsOnCollapsed",
    "collapsedTagsStyle",
    "tagDropOpensUrl",
)
_TAG_ENUMS: tuple[str, ...] = (
    "tag_sort_enum",
    "tag_match_mode_enum",
    "tag_count_style_enum",
    "collapsed_tags_style_enum",
)
_ENUM_CLASSES: dict[str, type[Enum]] = {
    "tag_sort_enum": TagSort,
    "tag_match_mode_enum": TagMatchMode,
    "tag_count_style_enum": TagCountStyle,
    "collapsed_tags_style_enum": CollapsedTagsStyle,
}
_ENUM_COLUMNS: tuple[str, ...] = (
    "tagSort",
    "tagMatchMode",
    "tagCountStyle",
    "collapsedTagsStyle",
)
_DEFAULT_WHERE: str = (
    "\"tagSort\" = 'most_in_view' AND \"tagMatchMode\" = 'all' "
    "AND \"tagCountStyle\" = 'in_view_total' "
    'AND "showTagsOnCollapsed" = false '
    "AND \"collapsedTagsStyle\" = 'one_line' "
    'AND "tagDropOpensUrl" = true'
)

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


def _column_names(connection: Connection) -> set[str]:
    return {
        column["name"]
        for column in inspect(connection).get_columns(_USER_PREFERENCES_TABLE)
    }


def _existing_enum_types(connection: Connection) -> set[str]:
    rows = connection.execute(
        text("SELECT typname FROM pg_type WHERE typname = ANY(:names)"),
        {"names": list(_TAG_ENUMS)},
    ).all()
    return {row[0] for row in rows}


def test_add_tag_display_preferences_migration_roundtrips(runner) -> None:
    """
    GIVEN a database seeded with the full mock dataset, then downgraded to
        c5f9b3d7e1a2 (no tag display columns)
    WHEN the d7a2e4c6f8b1 migration is applied, reverted and re-applied
    THEN every existing preference row reads the six defaults, a raw insert
        with none of the columns gets the server defaults, the columns match
        the model, an invalid enum value is rejected, and the downgrade drops
        all columns and enum types with row counts preserved.

    Args:
        runner (pytest.fixture): Provides a Flask application and a FlaskCLIRunner.
    """
    script = ScriptDirectory.from_config(_build_alembic_config()).get_revision(
        _TAG_DISPLAY_REVISION
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
                assert not set(_TAG_COLUMNS) & _column_names(connection)
                assert not _existing_enum_types(connection)
                row_counts_before = _capture_row_counts(connection)
            assert row_counts_before[_USERS_TABLE] > 0
            assert row_counts_before[_USER_PREFERENCES_TABLE] > 0

            command.upgrade(_build_alembic_config(), "head")

            with db.engine.connect() as connection:
                assert set(_TAG_COLUMNS) <= _column_names(connection)
                assert _existing_enum_types(connection) == set(_TAG_ENUMS)
                assert (
                    connection.execute(
                        text(
                            f'SELECT COUNT(*) FROM "UserPreferences" WHERE {_DEFAULT_WHERE}'
                        )
                    ).scalar_one()
                    == row_counts_before[_USER_PREFERENCES_TABLE]
                )
                for column_name in _TAG_COLUMNS:
                    model_column = User_Preferences.__table__.columns[column_name]
                    assert model_column.nullable is False
                    assert model_column.server_default is not None

            # A raw insert with none of the new columns gets the server defaults.
            with db.engine.begin() as connection:
                user_id = connection.execute(
                    text('SELECT MIN("userID") FROM "UserPreferences"')
                ).scalar_one()
                connection.execute(
                    text('DELETE FROM "UserPreferences" WHERE "userID" = :usr'),
                    {"usr": user_id},
                )
                connection.execute(
                    text(
                        'INSERT INTO "UserPreferences" '
                        '("userID", theme, "defaultView", "defaultSort", density, '
                        '"dateFormat", "createdAt", "updatedAt") '
                        "VALUES (:usr, 'system', 'list', 'newest', 'comfortable', "
                        "'iso', now(), now())"
                    ),
                    {"usr": user_id},
                )
            with db.engine.connect() as connection:
                assert (
                    connection.execute(
                        text(
                            'SELECT COUNT(*) FROM "UserPreferences" '
                            f'WHERE "userID" = :usr AND {_DEFAULT_WHERE}'
                        ),
                        {"usr": user_id},
                    ).scalar_one()
                    == 1
                )

            # The DB enum labels match the Python enums, in order.
            with db.engine.connect() as connection:
                for enum_name, enum_cls in _ENUM_CLASSES.items():
                    labels = (
                        connection.execute(
                            text(
                                "SELECT e.enumlabel FROM pg_enum e "
                                "JOIN pg_type t ON t.oid = e.enumtypid "
                                "WHERE t.typname = :name ORDER BY e.enumsortorder"
                            ),
                            {"name": enum_name},
                        )
                        .scalars()
                        .all()
                    )
                    assert labels == [member.value for member in enum_cls]

            # The DB enum rejects an invalid value on every enum column.
            for column_name in _ENUM_COLUMNS:
                with pytest.raises(DataError):
                    with db.engine.begin() as connection:
                        connection.execute(
                            text(
                                f'UPDATE "UserPreferences" SET "{column_name}" = '
                                "'bogus' WHERE id = "
                                '(SELECT MIN(id) FROM "UserPreferences")'
                            )
                        )

            command.downgrade(_build_alembic_config(), _PRE_REVISION)

            with db.engine.connect() as connection:
                assert not set(_TAG_COLUMNS) & _column_names(connection)
                assert not _existing_enum_types(connection)
                row_counts_after_downgrade = _capture_row_counts(connection)
            assert_row_counts_match_ignoring_new_tables(
                row_counts_before, row_counts_after_downgrade
            )

            command.upgrade(_build_alembic_config(), "head")

            with db.engine.connect() as connection:
                assert set(_TAG_COLUMNS) <= _column_names(connection)
                assert _existing_enum_types(connection) == set(_TAG_ENUMS)
                row_counts_after_upgrade = _capture_row_counts(connection)
            assert_row_counts_match_ignoring_new_tables(
                row_counts_after_upgrade, row_counts_after_downgrade
            )

            db.create_all()
    finally:
        del os.environ["PYTEST_RUNNING"]
