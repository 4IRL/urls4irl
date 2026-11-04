"""add UserPreferences tag display columns

Revision ID: d7a2e4c6f8b1
Revises: c5f9b3d7e1a2
Create Date: 2026-11-03 10:00:00.000000

Adds the six personal tag display defaults to ``UserPreferences``: four native
Postgres enums (``tag_sort_enum``, ``tag_match_mode_enum``,
``tag_count_style_enum``, ``collapsed_tags_style_enum``) and two booleans. Every
column is NOT NULL with a server default that preserves today's behavior, so
existing rows read the defaults with no backfill.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d7a2e4c6f8b1"
down_revision = "c5f9b3d7e1a2"
branch_labels = None
depends_on = None

_TAG_SORT_VALUES = ("most_in_view", "most_used", "name_az", "newest", "oldest")
_TAG_MATCH_MODE_VALUES = ("all", "any")
_TAG_COUNT_STYLE_VALUES = ("in_view_total", "total_only", "hidden")
_COLLAPSED_TAGS_STYLE_VALUES = ("one_line", "all")

_ENUMS = (
    ("tag_sort_enum", _TAG_SORT_VALUES),
    ("tag_match_mode_enum", _TAG_MATCH_MODE_VALUES),
    ("tag_count_style_enum", _TAG_COUNT_STYLE_VALUES),
    ("collapsed_tags_style_enum", _COLLAPSED_TAGS_STYLE_VALUES),
)


def upgrade():
    bind = op.get_bind()
    for enum_name, values in _ENUMS:
        sa.Enum(*values, name=enum_name).create(bind, checkfirst=True)

    op.add_column(
        "UserPreferences",
        sa.Column(
            "tagSort",
            sa.Enum(*_TAG_SORT_VALUES, name="tag_sort_enum", create_type=False),
            nullable=False,
            server_default="most_in_view",
        ),
    )
    op.add_column(
        "UserPreferences",
        sa.Column(
            "tagMatchMode",
            sa.Enum(
                *_TAG_MATCH_MODE_VALUES, name="tag_match_mode_enum", create_type=False
            ),
            nullable=False,
            server_default="all",
        ),
    )
    op.add_column(
        "UserPreferences",
        sa.Column(
            "tagCountStyle",
            sa.Enum(
                *_TAG_COUNT_STYLE_VALUES, name="tag_count_style_enum", create_type=False
            ),
            nullable=False,
            server_default="in_view_total",
        ),
    )
    op.add_column(
        "UserPreferences",
        sa.Column(
            "showTagsOnCollapsed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "UserPreferences",
        sa.Column(
            "collapsedTagsStyle",
            sa.Enum(
                *_COLLAPSED_TAGS_STYLE_VALUES,
                name="collapsed_tags_style_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="one_line",
        ),
    )
    op.add_column(
        "UserPreferences",
        sa.Column(
            "tagDropOpensUrl",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade():
    for column_name in (
        "tagDropOpensUrl",
        "collapsedTagsStyle",
        "showTagsOnCollapsed",
        "tagCountStyle",
        "tagMatchMode",
        "tagSort",
    ):
        op.drop_column("UserPreferences", column_name)
    bind = op.get_bind()
    for enum_name, _values in _ENUMS:
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)
