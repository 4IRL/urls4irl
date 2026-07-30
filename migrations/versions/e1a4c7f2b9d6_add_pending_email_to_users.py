"""add pendingEmail to Users

Revision ID: e1a4c7f2b9d6
Revises: c3f7a1b9d204
Create Date: 2026-07-30 12:00:00.000000

Purely additive: adds a nullable ``pendingEmail`` column to the Users table so
the Settings "change email" flow can stash the not-yet-confirmed new address
while the user stays logged in on their existing (still-verified) email. The
live ``email`` column is only swapped when the user clicks the confirmation
link. NULL (the default for every existing row) means no email change is in
flight. The downgrade drops the column.

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e1a4c7f2b9d6"
down_revision = "c3f7a1b9d204"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "Users",
        sa.Column(
            "pendingEmail",
            sa.String(320),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("Users", "pendingEmail")
