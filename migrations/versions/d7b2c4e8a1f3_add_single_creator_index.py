"""add single-CREATOR partial unique index on UtubMembers

Revision ID: d7b2c4e8a1f3
Revises: a9d3e5f7b1c2
Create Date: 2026-10-10 12:00:00.000000

Adds ``uq_utub_members_single_creator``, a partial unique index on
``UtubMembers ("utubID") WHERE "memberRole" = 'CREATOR'``, so the database
allows at most one CREATOR row per UTub (the owner-mutation race in issue
#757 could previously leave two). The predicate uses the enum NAME
(``'CREATOR'``), which is how ``memberRole`` is stored.

Before the index is created, the upgrade repairs existing data so the
``CREATE UNIQUE INDEX`` does not fail on duplicates: (1) every CREATOR row
that is not the UTub's literal creator (``Utubs.utubCreator``) is demoted to
``CO_CREATOR``, but only when the literal creator actually has a membership
row (otherwise the existing CREATOR is kept rather than leaving the UTub with
none); (2) the literal creator's row is promoted to CREATOR if it is not
already; (3) any UTub that still has more than one CREATOR (its literal
creator has no membership row and 2+ other members are CREATOR) keeps the
CREATOR with the lowest ``userID`` and demotes the rest to ``CO_CREATOR``.
After these steps each UTub has at most one CREATOR row.

The data repair is irreversible: the downgrade only drops the index and does
not restore the previous (duplicate or missing) roles.

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d7b2c4e8a1f3"
down_revision = "a9d3e5f7b1c2"
branch_labels = None
depends_on = None

_INDEX_NAME = "uq_utub_members_single_creator"


def upgrade() -> None:
    op.execute(
        sa.text(
            'UPDATE "UtubMembers" m SET "memberRole" = \'CO_CREATOR\' '
            'FROM "Utubs" u '
            'WHERE m."utubID" = u.id AND m."memberRole" = \'CREATOR\' '
            'AND m."userID" <> u."utubCreator" '
            'AND EXISTS (SELECT 1 FROM "UtubMembers" c '
            'WHERE c."utubID" = u.id AND c."userID" = u."utubCreator")'
        )
    )
    # Relies on statement 1 having run first: any other CREATOR in a UTub whose
    # literal creator has a row is already demoted, so this promotion cannot
    # create a second CREATOR.
    op.execute(
        sa.text(
            'UPDATE "UtubMembers" m SET "memberRole" = \'CREATOR\' '
            'FROM "Utubs" u '
            'WHERE m."utubID" = u.id AND m."userID" = u."utubCreator" '
            "AND m.\"memberRole\" <> 'CREATOR'"
        )
    )
    # Remaining duplicates: literal creator has no row, 2+ other CREATORs.
    # Keep the lowest userID per UTub, demote the rest.
    op.execute(
        sa.text(
            'UPDATE "UtubMembers" m SET "memberRole" = \'CO_CREATOR\' '
            'FROM (SELECT "utubID", "userID", ROW_NUMBER() OVER '
            '(PARTITION BY "utubID" ORDER BY "userID") AS rn '
            'FROM "UtubMembers" WHERE "memberRole" = \'CREATOR\') ranked '
            'WHERE m."utubID" = ranked."utubID" AND m."userID" = ranked."userID" '
            "AND ranked.rn > 1"
        )
    )
    op.create_index(
        _INDEX_NAME,
        "UtubMembers",
        ["utubID"],
        unique=True,
        postgresql_where=sa.text("\"memberRole\" = 'CREATOR'"),
    )


def downgrade() -> None:
    # The upgrade's role repair is irreversible and is not restored here.
    op.drop_index(_INDEX_NAME, table_name="UtubMembers")
