"""add AnonymousGauges table

Revision ID: 53e2183f1a73
Revises: a3f9c1e7b2d4
Create Date: 2026-06-14 20:24:44.332811

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "53e2183f1a73"
down_revision = "a3f9c1e7b2d4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "AnonymousGauges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("gaugeName", sa.String(length=100), nullable=False),
        sa.Column("sampledAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valueInt", sa.BigInteger(), nullable=True),
        sa.Column("valueFloat", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column(
            "dimensions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_gauges_name_time", "AnonymousGauges", ["gaugeName", "sampledAt"]
    )


def downgrade():
    op.drop_index("idx_gauges_name_time", table_name="AnonymousGauges")
    op.drop_table("AnonymousGauges")
