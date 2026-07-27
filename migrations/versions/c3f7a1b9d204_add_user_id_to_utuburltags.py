"""add userID to UtubUrlTags

Revision ID: c3f7a1b9d204
Revises: b8d2f0c4e6a1
Create Date: 2026-07-27 07:33:27.000000

Purely additive: adds a nullable ``userID`` FK column to the UtubUrlTags table,
attributing each tag-application row to the user who applied it (powering the
Settings "Tags applied" personal count). Intentional, accepted data loss: every
pre-existing UtubUrlTags row keeps NULL ``userID`` (the acting user was never
recorded historically) and is naturally excluded from the per-user count;
attribution is recorded only going forward. The downgrade drops the FK
constraint then the column.

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c3f7a1b9d204"
down_revision = "b8d2f0c4e6a1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("UtubUrlTags", schema=None) as batch_op:
        batch_op.add_column(sa.Column("userID", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_utuburltags_user", "Users", ["userID"], ["id"])


def downgrade():
    with op.batch_alter_table("UtubUrlTags", schema=None) as batch_op:
        batch_op.drop_constraint("fk_utuburltags_user", type_="foreignkey")
        batch_op.drop_column("userID")
