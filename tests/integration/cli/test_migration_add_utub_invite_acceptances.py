"""Integration test for the add_utub_invite_acceptances migration.

Exercises upgrade -> downgrade -> upgrade against a real seeded dataset and
checks the migrated schema matches the model.
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
from backend.cli.mock_constants import MOCK_INVITE_LINK_STATES
from backend.invite_links.constants import (
    FK_INVITE_ACCEPTANCES_INVITE,
    FK_INVITE_ACCEPTANCES_USER,
    FK_INVITE_ACCEPTANCES_UTUB,
    IX_INVITE_ACCEPTANCES_INVITE,
)
from backend.models.utub_invite_acceptances import Utub_Invite_Acceptances
from tests.integration.cli.utils import assert_row_counts_match_ignoring_new_tables

pytestmark = pytest.mark.cli

_PRE_REVISION: str = "e8c4a6f2b0d9"
_REVISION: str = "f3a7c1d9e5b2"
_TABLE: str = "UtubInviteAcceptances"
_ALEMBIC_VERSION_TABLE: str = "alembic_version"

_EXPECTED_COLUMNS: dict[str, bool] = {
    "id": False,
    "inviteID": False,
    "utubID": False,
    "userID": True,
    "acceptedAt": False,
}
_EXPECTED_FOREIGN_KEYS: dict[str, tuple[str, str, str]] = {
    "inviteID": ("UtubInviteLinks", "CASCADE", FK_INVITE_ACCEPTANCES_INVITE),
    "utubID": ("Utubs", "CASCADE", FK_INVITE_ACCEPTANCES_UTUB),
    "userID": ("Users", "SET NULL", FK_INVITE_ACCEPTANCES_USER),
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


def _assert_schema(connection: Connection) -> None:
    inspector = inspect(connection)
    assert inspector.has_table(_TABLE)

    columns = {column["name"]: column for column in inspector.get_columns(_TABLE)}
    assert {name: col["nullable"] for name, col in columns.items()} == (
        _EXPECTED_COLUMNS
    )
    assert columns["acceptedAt"]["type"].timezone is True
    assert inspector.get_pk_constraint(_TABLE)["constrained_columns"] == ["id"]

    foreign_keys = {
        foreign_key["constrained_columns"][0]: (
            foreign_key["referred_table"],
            foreign_key["options"].get("ondelete"),
            foreign_key["name"],
        )
        for foreign_key in inspector.get_foreign_keys(_TABLE)
    }
    assert foreign_keys == _EXPECTED_FOREIGN_KEYS

    indexes = {
        index["name"]: (tuple(index["column_names"]), index["unique"])
        for index in inspector.get_indexes(_TABLE)
    }
    assert indexes == {IX_INVITE_ACCEPTANCES_INVITE: (("inviteID",), False)}

    model_indexes = {index.name for index in Utub_Invite_Acceptances.__table__.indexes}
    assert model_indexes == {IX_INVITE_ACCEPTANCES_INVITE}


def test_add_utub_invite_acceptances_migration_upgrade_and_downgrade(runner) -> None:
    """
    GIVEN a database upgraded to head and seeded via ``flask addmock all``
    WHEN the add_utub_invite_acceptances migration is downgraded to e8c4a6f2b0d9
        and re-applied to head
    THEN there is one Alembic head, the schema matches the model, the downgrade
        drops only the table, and the re-upgrade recreates it empty.

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

            with db.engine.connect() as connection:
                _assert_schema(connection)

            cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)

            with db.engine.connect() as connection:
                row_counts_before = _capture_row_counts(connection)
            assert row_counts_before[_TABLE] == sum(
                state.use_count for state in MOCK_INVITE_LINK_STATES
            )

            command.downgrade(alembic_config, _PRE_REVISION)

            with db.engine.connect() as connection:
                assert not inspect(connection).has_table(_TABLE)
                row_counts_after_downgrade = _capture_row_counts(connection)
            assert _TABLE not in row_counts_after_downgrade
            assert_row_counts_match_ignoring_new_tables(
                row_counts_before, row_counts_after_downgrade
            )

            command.upgrade(alembic_config, "head")

            with db.engine.connect() as connection:
                _assert_schema(connection)
                row_counts_after_reupgrade = _capture_row_counts(connection)
            assert row_counts_after_reupgrade[_TABLE] == 0
            assert_row_counts_match_ignoring_new_tables(
                row_counts_before, row_counts_after_reupgrade
            )

            # Restore any tables the migrations do not manage, as the sibling test does.
            db.create_all()
    finally:
        del os.environ["PYTEST_RUNNING"]
