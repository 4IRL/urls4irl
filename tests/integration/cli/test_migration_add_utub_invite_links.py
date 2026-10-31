"""Integration test for the add_utub_invite_links migration.

Exercises upgrade -> downgrade -> upgrade against a real seeded dataset and
checks that the migrated schema matches the model (the only drift check, since
other tests build the schema with ``db.create_all()``).
"""

from __future__ import annotations

import os
import re

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from backend import db, migrate
from backend.invite_links.constants import (
    FK_EMAIL_VALIDATIONS_PENDING_INVITE,
    INVITE_LINK_TOKEN_LENGTH,
    ONE_ACTIVE_INVITE_LINK_PER_UTUB,
    UNIQUE_INVITE_LINK_TOKEN,
)
from backend.models.utub_invite_links import Utub_Invite_Links
from tests.integration.cli.utils import assert_row_counts_match_ignoring_new_tables

pytestmark = pytest.mark.cli

_PRE_INVITE_LINKS_REVISION: str = "b4e8a2c6d0f1"
_INVITE_LINKS_REVISION: str = "e8c4a6f2b0d9"
_INVITE_LINKS_TABLE: str = "UtubInviteLinks"
_EMAIL_VALIDATIONS_TABLE: str = "EmailValidations"
_PENDING_COLUMN: str = "pendingInviteID"
_USERS_TABLE: str = "Users"
_UTUBS_TABLE: str = "Utubs"
_ALEMBIC_VERSION_TABLE: str = "alembic_version"

_EXPECTED_COLUMNS: dict[str, bool] = {
    "id": False,
    "utubID": False,
    "token": False,
    "createdBy": True,
    "createdAt": False,
    "expiresAt": False,
    "maxUses": True,
    "useCount": False,
    "revokedAt": True,
}
_EXPECTED_FOREIGN_KEYS: dict[str, tuple[str, str]] = {
    "utubID": ("Utubs", "CASCADE"),
    "createdBy": ("Users", "SET NULL"),
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


def _normalize_predicate(predicate: str) -> str:
    without_casts = re.sub(r'::(?:"[^"]+"|\w+)', "", predicate)
    return re.sub(r"[\s()]", "", without_casts)


def _assert_invite_links_schema(connection: Connection) -> None:
    inspector = inspect(connection)
    assert inspector.has_table(_INVITE_LINKS_TABLE)

    columns = {
        column["name"]: column for column in inspector.get_columns(_INVITE_LINKS_TABLE)
    }
    assert {name: col["nullable"] for name, col in columns.items()} == (
        _EXPECTED_COLUMNS
    )
    assert columns["token"]["type"].length == INVITE_LINK_TOKEN_LENGTH
    assert str(columns["useCount"]["default"]).strip("'()") == "0"
    for timestamp_column in ("createdAt", "expiresAt", "revokedAt"):
        assert columns[timestamp_column]["type"].timezone is True

    assert inspector.get_pk_constraint(_INVITE_LINKS_TABLE)["constrained_columns"] == [
        "id"
    ]

    unique_constraints = {
        constraint["name"]: tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints(_INVITE_LINKS_TABLE)
    }
    assert unique_constraints == {UNIQUE_INVITE_LINK_TOKEN: ("token",)}

    foreign_keys = {
        foreign_key["constrained_columns"][0]: (
            foreign_key["referred_table"],
            foreign_key["options"].get("ondelete"),
        )
        for foreign_key in inspector.get_foreign_keys(_INVITE_LINKS_TABLE)
    }
    assert foreign_keys == _EXPECTED_FOREIGN_KEYS

    # EmailValidations.pendingInviteID
    email_columns = {
        column["name"]: column
        for column in inspector.get_columns(_EMAIL_VALIDATIONS_TABLE)
    }
    assert email_columns[_PENDING_COLUMN]["nullable"] is True
    pending_fks = [
        foreign_key
        for foreign_key in inspector.get_foreign_keys(_EMAIL_VALIDATIONS_TABLE)
        if foreign_key["constrained_columns"] == [_PENDING_COLUMN]
    ]
    assert len(pending_fks) == 1
    assert pending_fks[0]["name"] == FK_EMAIL_VALIDATIONS_PENDING_INVITE
    assert pending_fks[0]["referred_table"] == _INVITE_LINKS_TABLE
    assert pending_fks[0]["options"].get("ondelete") == "SET NULL"

    # Partial unique index matches the model
    model_index = next(
        index
        for index in Utub_Invite_Links.__table__.indexes
        if index.name == ONE_ACTIVE_INVITE_LINK_PER_UTUB
    )
    assert model_index.unique is True
    assert [column.name for column in model_index.columns] == ["utubID"]
    model_where = _normalize_predicate(
        str(model_index.dialect_options["postgresql"]["where"])
    )
    assert model_where == '"revokedAt"ISNULL'

    index_definition = connection.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE tablename = :table_name AND indexname = :index_name"
        ),
        {
            "table_name": _INVITE_LINKS_TABLE,
            "index_name": ONE_ACTIVE_INVITE_LINK_PER_UTUB,
        },
    ).scalar_one_or_none()
    assert index_definition is not None
    assert "UNIQUE" in index_definition
    assert '("utubID")' in index_definition
    assert " WHERE " in index_definition
    assert _normalize_predicate(index_definition.split(" WHERE ", 1)[1]) == model_where

    # The token unique constraint is on the model too
    assert any(
        getattr(constraint, "name", None) == UNIQUE_INVITE_LINK_TOKEN
        for constraint in Utub_Invite_Links.__table__.constraints
    )


def test_add_utub_invite_links_migration_upgrade_and_downgrade(runner) -> None:
    """
    GIVEN a database upgraded to head and seeded via ``flask addmock all``
    WHEN the add_utub_invite_links migration is downgraded to b4e8a2c6d0f1 and
        re-applied to head
    THEN there is exactly one Alembic head, the schema matches the model, the
        downgrade removes the table and pendingInviteID without changing any
        other table's row count, and the re-upgrade recreates the empty table.

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
            assert script.get_revision(_INVITE_LINKS_REVISION).down_revision == (
                _PRE_INVITE_LINKS_REVISION
            )

            command.upgrade(alembic_config, "head")

            with db.engine.connect() as connection:
                _assert_invite_links_schema(connection)

            cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)

            with db.engine.connect() as connection:
                row_counts_before_roundtrip = _capture_row_counts(connection)
            assert row_counts_before_roundtrip[_USERS_TABLE] > 0
            assert row_counts_before_roundtrip[_UTUBS_TABLE] > 0

            command.downgrade(alembic_config, _PRE_INVITE_LINKS_REVISION)

            with db.engine.connect() as connection:
                inspector = inspect(connection)
                assert not inspector.has_table(_INVITE_LINKS_TABLE)
                assert _PENDING_COLUMN not in {
                    column["name"]
                    for column in inspector.get_columns(_EMAIL_VALIDATIONS_TABLE)
                }
                row_counts_after_downgrade = _capture_row_counts(connection)
            assert _INVITE_LINKS_TABLE not in row_counts_after_downgrade
            assert_row_counts_match_ignoring_new_tables(
                row_counts_before_roundtrip, row_counts_after_downgrade
            )

            command.upgrade(alembic_config, "head")

            with db.engine.connect() as connection:
                _assert_invite_links_schema(connection)
                row_counts_after_reupgrade = _capture_row_counts(connection)
            assert row_counts_after_reupgrade[_INVITE_LINKS_TABLE] == 0
            assert_row_counts_match_ignoring_new_tables(
                row_counts_before_roundtrip, row_counts_after_reupgrade
            )

            db.create_all()
    finally:
        del os.environ["PYTEST_RUNNING"]
