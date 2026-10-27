"""add settings to UtubMembers

Revision ID: 7c3f9a1b5d82
Revises: e5b9d3f7a1c2
Create Date: 2026-10-25 12:00:00.000000

Adds a nullable ``settings`` JSONB column to UtubMembers holding a member's
sparse, private per-UTub view overrides. ``NULL`` means "all defaults", which
is the state of every existing row, so no backfill runs.

The downgrade drops the column, discarding any member settings recorded since
the upgrade (lossy).

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "7c3f9a1b5d82"
down_revision = "e5b9d3f7a1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("UtubMembers", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("settings", JSONB(none_as_null=True), nullable=True)
        )


def downgrade() -> None:
    # Lossy: discards the member settings recorded since the upgrade.
    with op.batch_alter_table("UtubMembers", schema=None) as batch_op:
        batch_op.drop_column("settings")
