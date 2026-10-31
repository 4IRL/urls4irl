"""add UtubInviteLinks table and EmailValidations.pendingInviteID

Revision ID: e8c4a6f2b0d9
Revises: b4e8a2c6d0f1
Create Date: 2026-10-31 12:00:00.000000

Purely additive: creates the UTub invite link table and a nullable
``EmailValidations.pendingInviteID`` reference. ``utubID`` cascades on delete and
``createdBy`` / ``pendingInviteID`` are SET NULL, so no delete can fail or remove
a signup. A partial unique index allows one unrevoked link per UTub.
The downgrade drops the reference, then the table; any invite links are lost,
which is acceptable because no code reads them yet and a member can mint a new one.

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e8c4a6f2b0d9"
down_revision = "b4e8a2c6d0f1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "UtubInviteLinks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("utubID", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=22), nullable=False),
        sa.Column("createdBy", sa.Integer(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expiresAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("maxUses", sa.Integer(), nullable=True),
        sa.Column("useCount", sa.Integer(), server_default="0", nullable=False),
        sa.Column("revokedAt", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["utubID"], ["Utubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["createdBy"], ["Users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="unique_utub_invite_link_token"),
    )
    op.create_index(
        "uq_utub_invite_links_one_active_per_utub",
        "UtubInviteLinks",
        ["utubID"],
        unique=True,
        postgresql_where=sa.text('"revokedAt" IS NULL'),
    )
    op.add_column(
        "EmailValidations",
        sa.Column("pendingInviteID", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_email_validations_pending_invite",
        "EmailValidations",
        "UtubInviteLinks",
        ["pendingInviteID"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    # Order matters: EmailValidations references the table, so drop that first.
    op.drop_constraint(
        "fk_email_validations_pending_invite", "EmailValidations", type_="foreignkey"
    )
    op.drop_column("EmailValidations", "pendingInviteID")
    op.drop_index(
        "uq_utub_invite_links_one_active_per_utub",
        table_name="UtubInviteLinks",
        postgresql_where=sa.text('"revokedAt" IS NULL'),
    )
    op.drop_table("UtubInviteLinks")
