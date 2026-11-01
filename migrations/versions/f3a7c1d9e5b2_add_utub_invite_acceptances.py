"""add UtubInviteAcceptances table

Revision ID: f3a7c1d9e5b2
Revises: e8c4a6f2b0d9
Create Date: 2026-11-01 12:00:00.000000

Purely additive: a permanent record of who joined through which invite link.
``inviteID`` and ``utubID`` cascade on delete; ``userID`` is SET NULL so an
erased account leaves an anonymous row. The downgrade drops the table; any
acceptance rows are lost, which is acceptable because nothing writes them yet.

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f3a7c1d9e5b2"
down_revision = "e8c4a6f2b0d9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "UtubInviteAcceptances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inviteID", sa.Integer(), nullable=False),
        sa.Column("utubID", sa.Integer(), nullable=False),
        sa.Column("userID", sa.Integer(), nullable=True),
        sa.Column("acceptedAt", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["inviteID"],
            ["UtubInviteLinks.id"],
            name="fk_utub_invite_acceptances_invite",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["utubID"],
            ["Utubs.id"],
            name="fk_utub_invite_acceptances_utub",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["userID"],
            ["Users.id"],
            name="fk_utub_invite_acceptances_user",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_utub_invite_acceptances_invite_id",
        "UtubInviteAcceptances",
        ["inviteID"],
    )


def downgrade():
    op.drop_index(
        "ix_utub_invite_acceptances_invite_id", table_name="UtubInviteAcceptances"
    )
    op.drop_table("UtubInviteAcceptances")
