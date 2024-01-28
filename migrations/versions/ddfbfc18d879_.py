"""empty message

Revision ID: ddfbfc18d879
Revises: ba14a342e5bb
Create Date: 2022-12-07 21:38:54.918203

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "ddfbfc18d879"
down_revision = "ba14a342e5bb"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("sessions")
    with op.batch_alter_table("Urls", schema=None) as batch_op:
        batch_op.drop_column("url_description")

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("Urls", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "url_description",
                sa.VARCHAR(length=500),
                autoincrement=False,
                nullable=True,
            )
        )

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
