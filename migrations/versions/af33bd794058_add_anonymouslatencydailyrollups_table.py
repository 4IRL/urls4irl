"""add AnonymousLatencyDailyRollups table

Revision ID: af33bd794058
Revises: a7df1b215595
Create Date: 2026-06-20 19:40:21.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "af33bd794058"
down_revision = "a7df1b215595"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "AnonymousLatencyDailyRollups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("metricName", sa.String(length=100), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("rollupDate", sa.Date(), nullable=False),
        sa.Column("p50Ms", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("p95Ms", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("p99Ms", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("sampleCount", sa.BigInteger(), nullable=False),
        sa.Column(
            "dimensions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "metricName",
            "endpoint",
            "method",
            "rollupDate",
            name="unique_latency_rollup_day",
        ),
    )
    op.create_index(
        "idx_latency_rollup_metric_date",
        "AnonymousLatencyDailyRollups",
        ["metricName", "rollupDate"],
    )
    op.create_index(
        "idx_latency_rollup_endpoint_date",
        "AnonymousLatencyDailyRollups",
        ["endpoint", "method", "rollupDate"],
    )


def downgrade():
    op.drop_index(
        "idx_latency_rollup_endpoint_date",
        table_name="AnonymousLatencyDailyRollups",
    )
    op.drop_index(
        "idx_latency_rollup_metric_date",
        table_name="AnonymousLatencyDailyRollups",
    )
    op.drop_table("AnonymousLatencyDailyRollups")
