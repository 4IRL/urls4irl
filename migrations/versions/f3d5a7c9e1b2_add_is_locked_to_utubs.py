"""add isLocked to Utubs

Revision ID: f3d5a7c9e1b2
Revises: 09f8ae70fc61
Create Date: 2026-07-11 10:00:00.000000

Purely additive: adds an ``isLocked`` boolean column to the Utubs table so
the admin portal can lock a UTub and prevent new content from being added.
All existing rows default to false (unlocked). The downgrade drops the column.

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f3d5a7c9e1b2"
down_revision = "09f8ae70fc61"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "Utubs",
        sa.Column(
            "isLocked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade():
    op.drop_column("Utubs", "isLocked")
