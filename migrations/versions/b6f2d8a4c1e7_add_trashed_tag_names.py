"""add trashedTagNames to UtubUrls

Revision ID: b6f2d8a4c1e7
Revises: e5a1c7d9b3f2
Create Date: 2026-10-17 12:00:00.000000

Adds a nullable ``trashedTagNames`` JSONB column to UtubUrls, a
``{tagId: tagString}`` snapshot taken at the same moment as ``trashedTagIds``.
Deleting a UTub tag hard-deletes its row, so the snapshot is the only way to
name a tag a trashed URL lost while it sat in the trash.

Purely additive: ``NULL`` means "no names known", which is exactly the state of
every existing row (trashed earlier, or never trashed), so no backfill runs. A
restore of such a row still reports the lost-tag count, just without names.

The downgrade drops the column, discarding any names recorded since the upgrade;
the ids in ``trashedTagIds`` are untouched.

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "b6f2d8a4c1e7"
down_revision = "e5a1c7d9b3f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("UtubUrls", schema=None) as batch_op:
        batch_op.add_column(sa.Column("trashedTagNames", JSONB(), nullable=True))


def downgrade() -> None:
    # Lossy: discards the tag names recorded since the upgrade.
    with op.batch_alter_table("UtubUrls", schema=None) as batch_op:
        batch_op.drop_column("trashedTagNames")
