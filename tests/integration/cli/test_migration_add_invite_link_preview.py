"""Integration tests for the c5e1a7d3b9f2 migration: invite-link preview columns.

Covers an upgrade -> downgrade -> upgrade roundtrip against the full mock dataset,
and the ``server_default`` backfill on rows seeded at the pre-revision schema.
"""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from backend import db, migrate
from backend.invite_links.constants import CK_INVITE_PREVIEW_END_WHEN_ENABLED
from tests.integration.cli.utils import assert_row_counts_match_ignoring_new_tables

pytestmark = pytest.mark.cli

_PRE_REVISION: str = "a9c3e5b7d1f4"
_REVISION: str = "c5e1a7d3b9f2"
_TABLE: str = "UtubInviteLinks"
_ALEMBIC_VERSION_TABLE: str = "alembic_version"
_PREVIEW_COLUMNS: dict[str, bool] = {
    "previewEnabled": False,
    "previewWindowDays": False,
    "previewEndsAt": True,
}

_MANAGEDB_DROP_ARGS: list[str] = ["managedb", "drop", "test"]
_ADDMOCK_ALL_ARGS: list[str] = ["addmock", "all"]


def _build_alembic_config() -> Config:
    alembic_config = Config("./migrations/alembic.ini")
    alembic_config.set_main_option("script_location", "migrations/")
    return alembic_config


def _capture_row_counts(connection: Connection) -> dict[str, int]:
    inspector = inspect(connection)
    row_counts: dict[str, int] = {}
    for table_name in inspector.get_table_names():
        if table_name == _ALEMBIC_VERSION_TABLE:
            continue
        row_counts[table_name] = connection.execute(
            text(f'SELECT COUNT(*) FROM "{table_name}"')
        ).scalar_one()
    return row_counts


def _preview_columns(connection: Connection) -> dict[str, bool]:
    columns = inspect(connection).get_columns(_TABLE)
    return {
        column["name"]: column["nullable"]
        for column in columns
        if column["name"] in _PREVIEW_COLUMNS
    }


def _check_names(connection: Connection) -> set[str]:
    return {
        constraint["name"]
        for constraint in inspect(connection).get_check_constraints(_TABLE)
    }


def _assert_preview_schema_present(connection: Connection) -> None:
    assert _preview_columns(connection) == _PREVIEW_COLUMNS
    assert CK_INVITE_PREVIEW_END_WHEN_ENABLED in _check_names(connection)
    columns = {
        column["name"]: column for column in inspect(connection).get_columns(_TABLE)
    }
    assert columns["previewEndsAt"]["type"].timezone is True


def _assert_preview_schema_absent(connection: Connection) -> None:
    assert _preview_columns(connection) == {}
    assert CK_INVITE_PREVIEW_END_WHEN_ENABLED not in _check_names(connection)


def _assert_every_row_preview_off(connection: Connection) -> None:
    assert (
        connection.execute(
            text(
                f'SELECT COUNT(*) FROM "{_TABLE}" WHERE "previewEnabled" = true '
                'OR "previewWindowDays" <> 3 OR "previewEndsAt" IS NOT NULL'
            )
        ).scalar_one()
        == 0
    )


def test_add_invite_link_preview_migration_roundtrip(runner) -> None:
    """
    GIVEN a database at head seeded with ``flask addmock all``
    WHEN the c5e1a7d3b9f2 migration is downgraded and re-applied
    THEN there is one head, the downgrade drops the columns and CHECK, the
        re-upgrade restores them with every row preview off / window 3 / NULL end,
        and row counts never change.

    Args:
        runner (pytest.fixture): Provides a Flask application and a FlaskCLIRunner.
    """
    os.environ["PYTEST_RUNNING"] = "1"
    flask_app, cli_runner = runner
    migrate.init_app(flask_app)

    try:
        cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)

        with flask_app.app_context():
            alembic_config = _build_alembic_config()
            script = ScriptDirectory.from_config(alembic_config)
            assert len(script.get_heads()) == 1
            assert script.get_revision(_REVISION).down_revision == _PRE_REVISION

            command.upgrade(alembic_config, "head")
            cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)

            with db.engine.connect() as connection:
                _assert_preview_schema_present(connection)
                row_counts_before = _capture_row_counts(connection)
            assert row_counts_before[_TABLE] > 0

            command.downgrade(alembic_config, _PRE_REVISION)

            with db.engine.connect() as connection:
                _assert_preview_schema_absent(connection)
                row_counts_after_downgrade = _capture_row_counts(connection)
            assert_row_counts_match_ignoring_new_tables(
                row_counts_before, row_counts_after_downgrade
            )

            command.upgrade(alembic_config, "head")

            with db.engine.connect() as connection:
                _assert_preview_schema_present(connection)
                _assert_every_row_preview_off(connection)
                row_counts_after_reupgrade = _capture_row_counts(connection)
            assert_row_counts_match_ignoring_new_tables(
                row_counts_before, row_counts_after_reupgrade
            )

            db.create_all()
    finally:
        del os.environ["PYTEST_RUNNING"]


def test_add_invite_link_preview_migration_backfills_old_rows(runner) -> None:
    """
    GIVEN rows inserted with raw SQL at the pre-revision schema
    WHEN the c5e1a7d3b9f2 migration is applied
    THEN the columns and CHECK exist and every old row is preview off, window 3,
        NULL end (the ``server_default`` backfill).

    Args:
        runner (pytest.fixture): Provides a Flask application and a FlaskCLIRunner.
    """
    os.environ["PYTEST_RUNNING"] = "1"
    flask_app, cli_runner = runner
    migrate.init_app(flask_app)

    try:
        cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)

        with flask_app.app_context():
            alembic_config = _build_alembic_config()
            command.upgrade(alembic_config, "head")
            command.downgrade(alembic_config, _PRE_REVISION)

            with db.engine.begin() as connection:
                connection.execute(
                    text(
                        'INSERT INTO "Users" (id, username, email, "createdAt", '
                        "role, \"emailValidated\") VALUES (1, 'old_user', "
                        "'old_user@urls4irl.app', now(), 'USER', true)"
                    )
                )
                connection.execute(
                    text(
                        'INSERT INTO "Utubs" (id, "utubName", "utubCreator", '
                        '"createdAt", "lastUpdated") VALUES '
                        "(1, 'Old UTub', 1, now(), now())"
                    )
                )
                connection.execute(
                    text(
                        'INSERT INTO "UtubInviteLinks" (id, "utubID", token, '
                        '"createdBy", "createdAt", "expiresAt", "revokedAt") VALUES '
                        "(1, 1, 'liveTokenliveTokenli01', 1, now(), "
                        "now() + interval '7 days', NULL), "
                        "(2, 1, 'deadTokendeadTokende02', 1, now(), "
                        "now() - interval '1 day', now())"
                    )
                )

            command.upgrade(alembic_config, "head")

            with db.engine.connect() as connection:
                _assert_preview_schema_present(connection)
                assert (
                    connection.execute(
                        text(f'SELECT COUNT(*) FROM "{_TABLE}"')
                    ).scalar_one()
                    == 2
                )
                _assert_every_row_preview_off(connection)

            db.create_all()
    finally:
        del os.environ["PYTEST_RUNNING"]
