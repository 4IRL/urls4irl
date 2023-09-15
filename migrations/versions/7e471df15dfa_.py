"""empty message

Revision ID: 7e471df15dfa
Revises: ddfbfc18d879
Create Date: 2023-09-03 16:01:51.264520

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "7e471df15dfa"
down_revision = "ddfbfc18d879"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("sessions")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
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
