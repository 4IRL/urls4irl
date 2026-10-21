"""add ShortLinks table

Revision ID: d4a8c2e6f0b1
Revises: c7a3e9b5d2f4
Create Date: 2026-10-20 12:00:00.000000

Purely additive: creates the URL share-link table. ``utubUrlID`` cascades on delete
at the DB level so raw-SQL and bulk hard-deletes of UtubUrls rows remove their link.
The downgrade drops the table; any live links (7-day, temporary) are lost, which is
acceptable because a member simply mints a new one.

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d4a8c2e6f0b1"
down_revision = "c7a3e9b5d2f4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ShortLinks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("utubUrlID", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("createdBy", sa.Integer(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expiresAt", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["utubUrlID"], ["UtubUrls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["createdBy"], ["Users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("utubUrlID", name="unique_short_link_per_utub_url"),
        sa.UniqueConstraint("code", name="unique_short_link_code"),
    )


def downgrade():
    op.drop_table("ShortLinks")
