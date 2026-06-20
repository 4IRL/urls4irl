"""add AnonymousLatencySamples table

Revision ID: a7df1b215595
Revises: 53e2183f1a73
Create Date: 2026-06-20 15:10:30.214642

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a7df1b215595"
down_revision = "53e2183f1a73"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "AnonymousLatencySamples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("metricName", sa.String(length=100), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=True),
        sa.Column("observedAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("durationMs", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column(
            "dimensions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_latency_metric_time",
        "AnonymousLatencySamples",
        ["metricName", "observedAt"],
    )
    op.create_index(
        "idx_latency_endpoint_time",
        "AnonymousLatencySamples",
        ["endpoint", "method", "observedAt"],
    )


def downgrade():
    op.drop_index("idx_latency_endpoint_time", table_name="AnonymousLatencySamples")
    op.drop_index("idx_latency_metric_time", table_name="AnonymousLatencySamples")
    op.drop_table("AnonymousLatencySamples")
