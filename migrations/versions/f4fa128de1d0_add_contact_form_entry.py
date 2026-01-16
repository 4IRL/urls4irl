"""Add contact form entry

Revision ID: f4fa128de1d0
Revises: cbacf42d21d0
Create Date: 2026-01-03 22:13:29.887704

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f4fa128de1d0"
down_revision = "cbacf42d21d0"
branch_labels = None
depends_on = None

url_valid_enum = postgresql.ENUM(
    "VALIDATED",
    "INVALIDATED",
    "UNKNOWN",
    name="possible_url_validation",
    create_type=True,
)


def upgrade():
    op.create_table(
        "ContactFormEntries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("userID", sa.Integer(), nullable=True),
        sa.Column("subject", sa.String(length=100), nullable=False),
        sa.Column("content", sa.String(length=1500), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lastDeliveryAttempt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered", sa.Boolean(), nullable=False),
        sa.Column("userAgentHash", sa.String(length=64), nullable=False),
        sa.Column("browser", sa.String(length=100), nullable=True),
        sa.Column("browserVersion", sa.String(length=50), nullable=True),
        sa.Column("os", sa.String(length=100), nullable=True),
        sa.Column("device", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["userID"],
            ["Users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("Urls", schema=None) as batch_op:
        batch_op.drop_column("isValidated")

    op.execute("""DROP TYPE possible_url_validation""")
    # ### end Alembic commands ###


def downgrade():
    url_valid_enum.create(op.get_bind(), checkfirst=True)

    with op.batch_alter_table("Urls", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "isValidated",
                sa.Enum(
                    "VALIDATED",
                    "INVALIDATED",
                    "UNKNOWN",
                    name="possible_url_validation",
                ),
                nullable=False,
                server_default="UNKNOWN",
            )
        )

    op.execute("""UPDATE "Urls" SET "isValidated"='VALIDATED'""")

    op.drop_table("ContactFormEntries")
    # ### end Alembic commands ###
