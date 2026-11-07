"""add pinnedAt to UtubMembers

Revision ID: a9c3e5b7d1f4
Revises: d7a2e4c6f8b1
Create Date: 2026-11-05 12:00:00.000000

Adds the nullable ``UtubMembers."pinnedAt"`` timestamptz, the per-member time
a user pinned a UTub; NULL means not pinned. No data statement: every existing
membership starts unpinned.

The downgrade only drops the column. It is lossy: all pins are discarded.

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a9c3e5b7d1f4"
down_revision = "d7a2e4c6f8b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("UtubMembers", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("pinnedAt", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    # Lossy: per-member pins are discarded
    with op.batch_alter_table("UtubMembers", schema=None) as batch_op:
        batch_op.drop_column("pinnedAt")
