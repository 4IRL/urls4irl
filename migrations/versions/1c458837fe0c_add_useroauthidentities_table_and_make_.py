"""add UserOAuthIdentities table and make Users.password nullable

Revision ID: 1c458837fe0c
Revises: 681906a2f237
Create Date: 2026-07-02 02:06:41.797304

Irreversibility risk: the downgrade re-applies NOT NULL to Users.password and
will FAIL if any OAuth-only (null-password) rows exist at that point. This is
acceptable because `addmock all` seeds no null-password users; any environment
carrying real OAuth-only accounts must delete or backfill them before
downgrading.

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "1c458837fe0c"
down_revision = "681906a2f237"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "UserOAuthIdentities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("userID", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("providerSubject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("linkedAt", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["userID"], ["Users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "providerSubject", name="unique_provider_subject"
        ),
        sa.UniqueConstraint("userID", "provider", name="unique_user_provider"),
    )
    op.create_index("idx_oauth_identity_user", "UserOAuthIdentities", ["userID"])

    with op.batch_alter_table("Users", schema=None) as batch_op:
        batch_op.alter_column(
            "password", existing_type=sa.String(length=166), nullable=True
        )


def downgrade():
    op.drop_index("idx_oauth_identity_user", table_name="UserOAuthIdentities")
    op.drop_table("UserOAuthIdentities")

    with op.batch_alter_table("Users", schema=None) as batch_op:
        batch_op.alter_column(
            "password", existing_type=sa.String(length=166), nullable=False
        )
