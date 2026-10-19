"""add settings to Utubs

Revision ID: c7a3e9b5d2f4
Revises: b6f2d8a4c1e7
Create Date: 2026-10-19 12:00:00.000000

Adds a nullable ``settings`` JSONB column to Utubs holding sparse per-section
setting overrides. ``NULL`` means "all defaults", which is the state of every
existing row, so no backfill runs.

The downgrade drops the column, discarding any settings recorded since the
upgrade (lossy).

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "c7a3e9b5d2f4"
down_revision = "b6f2d8a4c1e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("Utubs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("settings", JSONB(none_as_null=True), nullable=True)
        )


def downgrade() -> None:
    # Lossy: discards the settings recorded since the upgrade.
    with op.batch_alter_table("Utubs", schema=None) as batch_op:
        batch_op.drop_column("settings")
