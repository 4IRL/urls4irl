"""add sessionsInvalidatedAt to Users

Revision ID: b8d2f0c4e6a1
Revises: a7c1e9b3d5f0
Create Date: 2026-07-11 12:05:00.000000

Purely additive: adds a nullable ``sessionsInvalidatedAt`` timestamp to the
Users table. Web sessions issued before this timestamp are rejected by the
Flask-Login user_loader, giving the admin portal an O(1) per-user web-session
kill switch. NULL (the default for every existing row) means no invalidation
has ever been requested. The downgrade drops the column.

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b8d2f0c4e6a1"
down_revision = "a7c1e9b3d5f0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "Users",
        sa.Column(
            "sessionsInvalidatedAt",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("Users", "sessionsInvalidatedAt")
