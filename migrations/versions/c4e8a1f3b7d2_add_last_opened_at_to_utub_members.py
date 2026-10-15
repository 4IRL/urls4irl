"""add lastOpenedAt to UtubMembers

Revision ID: c4e8a1f3b7d2
Revises: d7b2c4e8a1f3
Create Date: 2026-10-15 12:00:00.000000

Adds the nullable ``UtubMembers."lastOpenedAt"`` timestamptz, the per-member
"last opened this UTub" time that replaces bumping ``Utubs.lastUpdated`` on
every open. The upgrade backfills each member's value from its UTub's
``lastUpdated`` so the sidebar order (``max(lastOpenedAt, lastUpdated)``) is
unchanged at deploy time.

The downgrade only drops the column; the per-member last-opened times are
discarded (lossy), though ``Utubs.lastUpdated`` is untouched.

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c4e8a1f3b7d2"
down_revision = "d7b2c4e8a1f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("UtubMembers", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("lastOpenedAt", sa.DateTime(timezone=True), nullable=True)
        )
    op.execute(
        sa.text(
            'UPDATE "UtubMembers" m SET "lastOpenedAt" = u."lastUpdated" '
            'FROM "Utubs" u WHERE m."utubID" = u.id'
        )
    )


def downgrade() -> None:
    # Lossy: per-member last-opened times are discarded
    with op.batch_alter_table("UtubMembers", schema=None) as batch_op:
        batch_op.drop_column("lastOpenedAt")
