"""Integration test for the d7b2c4e8a1f3 migration: single-CREATOR partial index.

Exercises the upgrade → downgrade → dirty seed → upgrade roundtrip against a
real seeded dataset, proving the ``uq_utub_members_single_creator`` partial
unique index is created on upgrade, dropped on downgrade, and that the
upgrade repairs duplicate-CREATOR and missing-CREATOR data before creating it.
"""

from __future__ import annotations

import os
import re

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, inspect, select, table, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from backend import db, migrate
from backend.models.utub_members import Utub_Members
from tests.integration.cli.utils import assert_row_counts_match_ignoring_new_tables

pytestmark = pytest.mark.cli

_PRE_INDEX_REVISION: str = "a9d3e5f7b1c2"
_INDEX_REVISION: str = "d7b2c4e8a1f3"
_UTUB_MEMBERS_TABLE: str = "UtubMembers"
_USERS_TABLE: str = "Users"
_UTUBS_TABLE: str = "Utubs"
_ALEMBIC_VERSION_TABLE: str = "alembic_version"
_INDEX_NAME: str = "uq_utub_members_single_creator"

_MANAGEDB_DROP_ARGS: list[str] = ["managedb", "drop", "test"]
_ADDMOCK_ALL_ARGS: list[str] = ["addmock", "all"]


def _build_alembic_config() -> Config:
    alembic_config = Config("./migrations/alembic.ini")
    alembic_config.set_main_option("script_location", "migrations/")
    return alembic_config


def _capture_row_counts(connection: Connection) -> dict[str, int]:
    """Return a per-table row count for every persisted table except the
    Alembic bookkeeping table, keyed by table name.

    Args:
        connection: Active SQLAlchemy engine connection.

    Returns:
        Mapping of table name to row count.
    """
    inspector = inspect(connection)
    row_counts: dict[str, int] = {}
    for table_name in inspector.get_table_names():
        if table_name == _ALEMBIC_VERSION_TABLE:
            continue
        row_counts[table_name] = connection.execute(
            select(func.count()).select_from(table(table_name))
        ).scalar_one()
    return row_counts


def _get_index_definition(connection: Connection) -> str | None:
    """Return the ``pg_indexes.indexdef`` of the single-CREATOR index, or None."""
    return connection.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE tablename = :table_name AND indexname = :index_name"
        ),
        {"table_name": _UTUB_MEMBERS_TABLE, "index_name": _INDEX_NAME},
    ).scalar_one_or_none()


def _normalize_predicate(predicate: str) -> str:
    """Strip whitespace, parentheses and type casts so a model predicate and
    a ``pg_indexes`` predicate can be compared textually."""
    without_casts = re.sub(r'::(?:"[^"]+"|\w+)', "", predicate)
    return re.sub(r"[\s()]", "", without_casts)


def _assert_models_match_migrated_schema(connection: Connection) -> None:
    """Compare the model's declared index with the migrated database's index.

    Normal tests build the schema from the models via ``db.create_all()``, so
    this is the only drift check between the model and the migration.
    """
    model_index = next(
        index for index in Utub_Members.__table__.indexes if index.name == _INDEX_NAME
    )
    assert model_index.unique is True
    assert [column.name for column in model_index.columns] == ["utubID"]
    model_where = _normalize_predicate(
        str(model_index.dialect_options["postgresql"]["where"])
    )
    assert model_where == "\"memberRole\"='CREATOR'"

    index_definition = _get_index_definition(connection)
    assert index_definition is not None
    assert "UNIQUE" in index_definition
    assert '("utubID")' in index_definition
    assert " WHERE " in index_definition
    database_where = _normalize_predicate(index_definition.split(" WHERE ", 1)[1])
    assert database_where == model_where


def _utub_ids_with_members(connection: Connection, minimum: int) -> list[int]:
    """Return UTub ids having at least ``minimum`` members, ascending."""
    return list(
        connection.execute(
            text(
                'SELECT "utubID" FROM "UtubMembers" GROUP BY "utubID" '
                'HAVING COUNT(*) >= :minimum ORDER BY "utubID"'
            ),
            {"minimum": minimum},
        ).scalars()
    )


def _get_utub_creator(connection: Connection, utub_id: int) -> int:
    """Return the literal creator (``Utubs.utubCreator``) of a UTub."""
    return connection.execute(
        text('SELECT "utubCreator" FROM "Utubs" WHERE id = :utub_id'),
        {"utub_id": utub_id},
    ).scalar_one()


def _get_non_creator_members(
    connection: Connection, utub_id: int, limit: int
) -> list[int]:
    """Return up to ``limit`` member user ids that are not the UTub's literal
    creator, ascending."""
    return list(
        connection.execute(
            text(
                'SELECT m."userID" FROM "UtubMembers" m '
                'JOIN "Utubs" u ON u.id = m."utubID" '
                'WHERE m."utubID" = :utub_id AND m."userID" <> u."utubCreator" '
                'ORDER BY m."userID" LIMIT :limit'
            ),
            {"utub_id": utub_id, "limit": limit},
        ).scalars()
    )


def _get_creator_user_ids(connection: Connection, utub_id: int) -> list[int]:
    """Return the user ids holding the CREATOR role in a UTub, ascending."""
    return list(
        connection.execute(
            text(
                'SELECT "userID" FROM "UtubMembers" '
                'WHERE "utubID" = :utub_id AND "memberRole" = \'CREATOR\' '
                'ORDER BY "userID"'
            ),
            {"utub_id": utub_id},
        ).scalars()
    )


def _get_member_role(connection: Connection, utub_id: int, user_id: int) -> str:
    """Return a member's ``memberRole`` enum name as text."""
    return connection.execute(
        text(
            'SELECT "memberRole"::text FROM "UtubMembers" '
            'WHERE "utubID" = :utub_id AND "userID" = :user_id'
        ),
        {"utub_id": utub_id, "user_id": user_id},
    ).scalar_one()


def _seed_dirty_creator_rows(connection: Connection) -> dict[str, int]:
    """Seed three dirty scenarios with raw SQL on three different UTubs.

    (a) duplicate CREATOR: a non-creator member of UTub A is also CREATOR.
    (b) missing CREATOR: UTub B's literal creator row is demoted to CO_CREATOR.
    (c) literal creator has no membership row: two other members are both
        CREATOR and the creator's row is deleted, so the EXISTS guard must not
        demote them and the lowest-userID rule must keep exactly one.

    Returns:
        Mapping with the UTub ids and users involved.
    """
    # Scenario (c) needs the literal creator plus two stand-ins: >= 3 members.
    three_member_utub_ids = _utub_ids_with_members(connection, minimum=3)
    assert three_member_utub_ids
    utub_c = three_member_utub_ids[0]
    candidate_utub_ids = [
        utub_id
        for utub_id in _utub_ids_with_members(connection, minimum=2)
        if utub_id != utub_c
    ]
    # The mock dataset must offer two more multi-member UTubs for (a) and (b).
    assert len(candidate_utub_ids) >= 2
    utub_a, utub_b = candidate_utub_ids[:2]

    (duplicate_user,) = _get_non_creator_members(connection, utub_a, limit=1)
    connection.execute(
        text(
            'UPDATE "UtubMembers" SET "memberRole" = \'CREATOR\' '
            'WHERE "utubID" = :utub_id AND "userID" = :user_id'
        ),
        {"utub_id": utub_a, "user_id": duplicate_user},
    )

    creator_b = _get_utub_creator(connection, utub_b)
    connection.execute(
        text(
            'UPDATE "UtubMembers" SET "memberRole" = \'CO_CREATOR\' '
            'WHERE "utubID" = :utub_id AND "userID" = :user_id'
        ),
        {"utub_id": utub_b, "user_id": creator_b},
    )

    creator_c = _get_utub_creator(connection, utub_c)
    stand_in_user, extra_stand_in_user = _get_non_creator_members(
        connection, utub_c, limit=2
    )
    for stand_in in (stand_in_user, extra_stand_in_user):
        connection.execute(
            text(
                'UPDATE "UtubMembers" SET "memberRole" = \'CREATOR\' '
                'WHERE "utubID" = :utub_id AND "userID" = :user_id'
            ),
            {"utub_id": utub_c, "user_id": stand_in},
        )
    connection.execute(
        text(
            'DELETE FROM "UtubMembers" '
            'WHERE "utubID" = :utub_id AND "userID" = :user_id'
        ),
        {"utub_id": utub_c, "user_id": creator_c},
    )

    return {
        "utub_a": utub_a,
        "duplicate_user": duplicate_user,
        "utub_b": utub_b,
        "creator_b": creator_b,
        "utub_c": utub_c,
        "stand_in_user": stand_in_user,
        "extra_stand_in_user": extra_stand_in_user,
    }


def test_add_single_creator_index_migration_repairs_and_roundtrips(runner) -> None:
    """
    GIVEN a database upgraded to head and seeded with the full mock dataset
        via ``flask addmock all``, then downgraded to a9d3e5f7b1c2 (index
        absent) and seeded with dirty CREATOR data: (a) a UTub with two
        CREATOR rows, (b) a UTub whose literal creator was demoted so it has
        no CREATOR, (c) a UTub whose literal creator has no membership row
        but another member is CREATOR
    WHEN the d7b2c4e8a1f3 migration is applied
    THEN the single-CREATOR partial unique index exists and matches the
        model; (a) the duplicated user is CO_CREATOR and the literal creator
        is the only CREATOR; (b) the literal creator is re-promoted to
        CREATOR; (c) the existing CREATOR is kept; every UTub has exactly one
        CREATOR; and row counts are unchanged by the repair — confirming the
        migration is reversible (index) and repairs data against the real
        seeded dataset (per CLAUDE.md).

    Args:
        runner (pytest.fixture): Provides a Flask application and a FlaskCLIRunner.
    """
    index_script = ScriptDirectory.from_config(_build_alembic_config()).get_revision(
        _INDEX_REVISION
    )
    assert index_script.down_revision == _PRE_INDEX_REVISION
    os.environ["PYTEST_RUNNING"] = "1"
    flask_app, cli_runner = runner
    migrate.init_app(flask_app)

    try:
        cli_runner.invoke(args=_MANAGEDB_DROP_ARGS)

        with flask_app.app_context():
            command.upgrade(_build_alembic_config(), "head")

            with db.engine.connect() as connection:
                assert _get_index_definition(connection) is not None

            cli_runner.invoke(args=_ADDMOCK_ALL_ARGS)

            with db.engine.connect() as connection:
                row_counts_before_roundtrip = _capture_row_counts(connection)
            # The post-roundtrip assertions are only meaningful if rows exist.
            assert row_counts_before_roundtrip[_USERS_TABLE] > 0
            assert row_counts_before_roundtrip[_UTUBS_TABLE] > 0
            assert row_counts_before_roundtrip[_UTUB_MEMBERS_TABLE] > 0

            command.downgrade(_build_alembic_config(), _PRE_INDEX_REVISION)

            with db.engine.begin() as connection:
                assert _get_index_definition(connection) is None
                seeded = _seed_dirty_creator_rows(connection)
            with db.engine.connect() as connection:
                # Dirty state is really present before the repair runs.
                assert len(_get_creator_user_ids(connection, seeded["utub_a"])) == 2
                assert _get_creator_user_ids(connection, seeded["utub_b"]) == []
                row_counts_before_upgrade = _capture_row_counts(connection)

            command.upgrade(_build_alembic_config(), "head")

            with db.engine.connect() as connection:
                _assert_models_match_migrated_schema(connection)

                creator_a = _get_utub_creator(connection, seeded["utub_a"])
                assert _get_creator_user_ids(connection, seeded["utub_a"]) == [
                    creator_a
                ]
                assert (
                    _get_member_role(
                        connection, seeded["utub_a"], seeded["duplicate_user"]
                    )
                    == "CO_CREATOR"
                )

                assert _get_creator_user_ids(connection, seeded["utub_b"]) == [
                    seeded["creator_b"]
                ]

                # (c)/(d): two stand-in CREATORs, creator row gone: the lowest
                # userID stays CREATOR and the other is demoted.
                kept_user = min(seeded["stand_in_user"], seeded["extra_stand_in_user"])
                demoted_user = max(
                    seeded["stand_in_user"], seeded["extra_stand_in_user"]
                )
                assert _get_creator_user_ids(connection, seeded["utub_c"]) == [
                    kept_user
                ]
                assert (
                    _get_member_role(connection, seeded["utub_c"], demoted_user)
                    == "CO_CREATOR"
                )

                utubs_without_single_creator = connection.execute(
                    text(
                        'SELECT COUNT(*) FROM "Utubs" u WHERE '
                        '(SELECT COUNT(*) FROM "UtubMembers" m '
                        'WHERE m."utubID" = u.id AND m."memberRole" = \'CREATOR\') <> 1'
                    )
                ).scalar_one()
                assert utubs_without_single_creator == 0

                row_counts_after_upgrade = _capture_row_counts(connection)
            assert_row_counts_match_ignoring_new_tables(
                row_counts_before_upgrade, row_counts_after_upgrade
            )

            # The index rejects a second CREATOR; the transaction is rolled back.
            with db.engine.connect() as connection:
                transaction = connection.begin()
                try:
                    (second_creator,) = _get_non_creator_members(
                        connection, seeded["utub_a"], limit=1
                    )
                    with pytest.raises(IntegrityError):
                        connection.execute(
                            text(
                                'UPDATE "UtubMembers" SET "memberRole" = \'CREATOR\' '
                                'WHERE "utubID" = :utub_id AND "userID" = :user_id'
                            ),
                            {"utub_id": seeded["utub_a"], "user_id": second_creator},
                        )
                finally:
                    transaction.rollback()

            # Schema is fully migrated to head; recreate any tables the
            # migrations left absent so the runner fixture teardown operates
            # against the full schema for subsequent tests.
            db.create_all()
    finally:
        del os.environ["PYTEST_RUNNING"]
