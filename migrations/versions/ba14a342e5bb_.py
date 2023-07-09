"""empty message

Revision ID: ba14a342e5bb
Revises: a24a7134a8a3
Create Date: 2022-12-07 21:38:09.511584

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "ba14a342e5bb"
down_revision = "a24a7134a8a3"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("sessions")
    with op.batch_alter_table("Urls", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("url_description", sa.String(length=500), nullable=True)
        )

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("Urls", schema=None) as batch_op:
        batch_op.drop_column("url_description")

    op.create_table(
        "sessions",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column(
            "session_id", sa.VARCHAR(length=255), autoincrement=False, nullable=True
        ),
        sa.Column("data", postgresql.BYTEA(), autoincrement=False, nullable=True),
        sa.Column("expiry", postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
        sa.PrimaryKeyConstraint("id", name="sessions_pkey"),
        sa.UniqueConstraint("session_id", name="sessions_session_id_key"),
    )
    # ### end Alembic commands ###
