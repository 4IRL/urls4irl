"""add MetricFlows table

Revision ID: e5b9d3f7a1c2
Revises: d4a8c2e6f0b1
Create Date: 2026-10-24 12:00:00.000000

Purely additive: creates the table for admin-built metric funnels. Display names
are unique regardless of case through a ``lower("displayName")`` unique index, and
two CHECK constraints keep names trimmed and non-empty and ``definition`` an object
whose ``steps`` is an array. The check expressions are identical to the ones on
``backend/models/metric_flows.py``. The downgrade drops the index, then the table;
any saved custom flows are lost.

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e5b9d3f7a1c2"
down_revision = "d4a8c2e6f0b1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "MetricFlows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("displayName", sa.String(length=64), nullable=False),
        sa.Column(
            "definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("createdBy", sa.Integer(), nullable=True),
        sa.Column("updatedBy", sa.Integer(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["createdBy"], ["Users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updatedBy"], ["Users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            '"displayName" = btrim("displayName") AND char_length("displayName") > 0',
            name="ck_metric_flows_display_name_trimmed",
        ),
        sa.CheckConstraint(
            "coalesce(jsonb_typeof(definition -> 'steps'), '') = 'array'",
            name="ck_metric_flows_definition_steps_array",
        ),
    )
    op.create_index(
        "uq_metric_flows_display_name_lower",
        "MetricFlows",
        [sa.text('lower("displayName")')],
        unique=True,
    )


def downgrade():
    op.drop_index("uq_metric_flows_display_name_lower", table_name="MetricFlows")
    op.drop_table("MetricFlows")
