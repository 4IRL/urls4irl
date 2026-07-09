"""add AuditLogs table

Revision ID: 09f8ae70fc61
Revises: c9e4f1a52b83
Create Date: 2026-07-09 12:00:00.000000

Purely additive: creates the admin-portal audit trail table. The downgrade
drops the table (and any recorded audit history with it) — acceptable because
the audit log is operational telemetry with a 90-day retention window, not
application data.

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "09f8ae70fc61"
down_revision = "c9e4f1a52b83"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "AuditLogs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actorId", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("targetType", sa.String(length=50), nullable=True),
        sa.Column("targetId", sa.String(length=64), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actorId"], ["Users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # Composite index for newest-first time-windowed scans, optionally
    # narrowed by actor (the audit-log viewer's dominant access pattern).
    op.create_index(
        "idx_audit_logs_created_at_actor",
        "AuditLogs",
        [sa.text('"createdAt" DESC'), "actorId"],
    )


def downgrade():
    op.drop_index("idx_audit_logs_created_at_actor", table_name="AuditLogs")
    op.drop_table("AuditLogs")
