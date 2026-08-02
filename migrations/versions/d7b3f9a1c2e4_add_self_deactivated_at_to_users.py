"""add selfDeactivatedAt to Users

Revision ID: d7b3f9a1c2e4
Revises: e1a4c7f2b9d6
Create Date: 2026-08-01 12:00:00.000000

Purely additive: adds a nullable ``selfDeactivatedAt`` column to the Users
table so a reversible self-service account deactivation can be distinguished
from an admin suspension. Both set ``isSuspended=True``; only a self-service
pause stamps ``selfDeactivatedAt``, which the login path reads to auto-lift the
deactivation on a subsequent successful credential/subject check. NULL (the
default for every existing row) means the account was never self-deactivated.
An admin suspension clears this back to NULL so an admin lock always overrides
a prior self-pause. The downgrade drops the column.

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d7b3f9a1c2e4"
down_revision = "e1a4c7f2b9d6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "Users",
        sa.Column(
            "selfDeactivatedAt",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("Users", "selfDeactivatedAt")
