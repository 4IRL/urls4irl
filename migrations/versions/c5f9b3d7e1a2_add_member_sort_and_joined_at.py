"""add UserPreferences.memberSort and UtubMembers.joinedAt

Revision ID: c5f9b3d7e1a2
Revises: f3a7c1d9e5b2
Create Date: 2026-11-01 10:00:00.000000

Adds the per-user member sort preference ``memberSort`` (native Postgres enum
``member_sort_enum``, default ``name_az``) and the nullable ``joinedAt``
timestamp on ``UtubMembers``. ``joinedAt`` is added with no default and no
backfill so existing members stay dateless; the server default is set in a
separate statement so only later inserts are stamped.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c5f9b3d7e1a2"
down_revision = "f3a7c1d9e5b2"
branch_labels = None
depends_on = None

_MEMBER_SORT_VALUES = ("name_az", "role_then_name", "recently_joined")


def upgrade():
    bind = op.get_bind()
    member_sort_enum = sa.Enum(*_MEMBER_SORT_VALUES, name="member_sort_enum")
    member_sort_enum.create(bind, checkfirst=True)
    op.add_column(
        "UserPreferences",
        sa.Column(
            "memberSort",
            sa.Enum(*_MEMBER_SORT_VALUES, name="member_sort_enum", create_type=False),
            nullable=False,
            server_default="name_az",
        ),
    )
    # No default here: Postgres must not stamp existing rows.
    op.add_column(
        "UtubMembers",
        sa.Column("joinedAt", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("UtubMembers", "joinedAt", server_default=sa.text("now()"))


def downgrade():
    # Dropping joinedAt loses every recorded join date; it cannot be restored.
    op.drop_column("UtubMembers", "joinedAt")
    op.drop_column("UserPreferences", "memberSort")
    bind = op.get_bind()
    sa.Enum(name="member_sort_enum").drop(bind, checkfirst=True)
