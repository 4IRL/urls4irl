"""add invite link preview columns

Revision ID: c5e1a7d3b9f2
Revises: a9c3e5b7d1f4
Create Date: 2026-11-13 12:00:00.000000

Adds ``UtubInviteLinks."previewEnabled"`` (NOT NULL, default false),
``"previewWindowDays"`` (NOT NULL, default 3) and the nullable timestamptz
``"previewEndsAt"``, plus a CHECK that an enabled preview always has an end.
The server defaults backfill every existing row to preview off, window 3, no end.

The downgrade drops the constraint and then the columns. It is lossy: all
preview settings are discarded.

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c5e1a7d3b9f2"
down_revision = "a9c3e5b7d1f4"
branch_labels = None
depends_on = None

_CHECK_NAME = "ck_utub_invite_links_preview_end_when_enabled"


def upgrade() -> None:
    with op.batch_alter_table("UtubInviteLinks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "previewEnabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "previewWindowDays",
                sa.Integer(),
                nullable=False,
                server_default="3",
            )
        )
        batch_op.add_column(
            sa.Column("previewEndsAt", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_check_constraint(
            _CHECK_NAME, '"previewEnabled" = false OR "previewEndsAt" IS NOT NULL'
        )


def downgrade() -> None:
    # Lossy: preview settings are discarded
    with op.batch_alter_table("UtubInviteLinks", schema=None) as batch_op:
        batch_op.drop_constraint(_CHECK_NAME, type_="check")
        batch_op.drop_column("previewEndsAt")
        batch_op.drop_column("previewWindowDays")
        batch_op.drop_column("previewEnabled")
