"""add soft-delete columns to Utubs and UtubUrls

Revision ID: a9d3e5f7b1c2
Revises: 58dfdcfa3921
Create Date: 2026-10-08 12:00:00.000000

Purely additive: adds nullable ``deletedAt`` / ``deletedBy`` columns to both the
Utubs and UtubUrls tables, plus a nullable ``trashedTagIds`` JSONB tag snapshot
on UtubUrls. ``NULL`` means "not trashed", so every existing row is untouched
and no backfill runs. Nothing reads these columns yet; the soft-delete-restore
behavior phases consume them.

``deletedBy`` is a FK to Users.id with no ``ondelete``, matching every other
content FK to Users (``utubCreator``, ``UtubUrls.userID``,
``UtubUrlTags.userID``). Users are tombstoned, never hard-deleted
(``erase_user_core``), and "Deleted by" must resolve through the tombstoned
Users row. ``CASCADE`` would destroy other members' trashed content, and
``SET NULL`` would be the lone exception to the convention for no current
benefit. No index on ``deletedAt`` is added here; the purge sweep that would
scan by it decides whether it needs one.

The downgrade is lossy: it drops the FK constraints then the columns, which
discards any soft-delete state recorded since the upgrade.

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "a9d3e5f7b1c2"
down_revision = "58dfdcfa3921"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("Utubs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("deletedAt", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("deletedBy", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_utubs_deleted_by", "Users", ["deletedBy"], ["id"]
        )

    with op.batch_alter_table("UtubUrls", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("deletedAt", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("deletedBy", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("trashedTagIds", JSONB(), nullable=True))
        batch_op.create_foreign_key(
            "fk_utuburls_deleted_by", "Users", ["deletedBy"], ["id"]
        )


def downgrade() -> None:
    # Lossy: discards any soft-delete state recorded since the upgrade.
    with op.batch_alter_table("UtubUrls", schema=None) as batch_op:
        batch_op.drop_constraint("fk_utuburls_deleted_by", type_="foreignkey")
        batch_op.drop_column("trashedTagIds")
        batch_op.drop_column("deletedBy")
        batch_op.drop_column("deletedAt")

    with op.batch_alter_table("Utubs", schema=None) as batch_op:
        batch_op.drop_constraint("fk_utubs_deleted_by", type_="foreignkey")
        batch_op.drop_column("deletedBy")
        batch_op.drop_column("deletedAt")
