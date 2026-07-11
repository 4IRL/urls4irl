"""add isSuspended to Users

Revision ID: a7c1e9b3d5f0
Revises: f3d5a7c9e1b2
Create Date: 2026-07-11 12:00:00.000000

Purely additive: adds an ``isSuspended`` boolean column to the Users table so
the admin portal can suspend an account. Suspended users are blocked at login
and their existing sessions resolve to anonymous. All existing rows default to
false (not suspended). The downgrade drops the column.

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a7c1e9b3d5f0"
down_revision = "f3d5a7c9e1b2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "Users",
        sa.Column(
            "isSuspended",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade():
    op.drop_column("Users", "isSuspended")
