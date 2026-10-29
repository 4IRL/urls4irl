"""add UTub list preference columns to UserPreferences

Revision ID: b4e8a2c6d0f1
Revises: b3e7c1d9a4f2
Create Date: 2026-10-27 10:00:00.000000

Adds the per-user UTub list preferences to ``UserPreferences``: ``utubSort``
(native Postgres enum ``utub_sort_enum``, default ``recent_activity``),
``showRowCounts`` (default false) and ``showListTotals`` (default true). Each
column carries a server default so existing rows backfill to the values that
reproduce today's deck. The downgrade drops the columns, then the enum type
(``checkfirst=True``) so a later re-upgrade does not raise DuplicateObject.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b4e8a2c6d0f1"
down_revision = "b3e7c1d9a4f2"
branch_labels = None
depends_on = None

_UTUB_SORT_VALUES = (
    "recent_activity",
    "last_opened",
    "name_az",
    "newest_created",
    "oldest_created",
)


def upgrade():
    bind = op.get_bind()
    utub_sort_enum = sa.Enum(*_UTUB_SORT_VALUES, name="utub_sort_enum")
    utub_sort_enum.create(bind, checkfirst=True)
    op.add_column(
        "UserPreferences",
        sa.Column(
            "utubSort",
            sa.Enum(*_UTUB_SORT_VALUES, name="utub_sort_enum", create_type=False),
            nullable=False,
            server_default="recent_activity",
        ),
    )
    op.add_column(
        "UserPreferences",
        sa.Column(
            "showRowCounts",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "UserPreferences",
        sa.Column(
            "showListTotals",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade():
    op.drop_column("UserPreferences", "showListTotals")
    op.drop_column("UserPreferences", "showRowCounts")
    op.drop_column("UserPreferences", "utubSort")
    bind = op.get_bind()
    sa.Enum(name="utub_sort_enum").drop(bind, checkfirst=True)
