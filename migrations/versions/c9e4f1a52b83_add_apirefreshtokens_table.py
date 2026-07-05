"""add ApiRefreshTokens table

Revision ID: c9e4f1a52b83
Revises: 1c458837fe0c
Create Date: 2026-07-05 12:00:00.000000

Purely additive: creates the mobile /api/v1 refresh-token table. The downgrade
drops the table (and any live refresh tokens with it) — acceptable because
losing refresh tokens only forces mobile clients to log in again.

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c9e4f1a52b83"
down_revision = "1c458837fe0c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ApiRefreshTokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("userID", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("familyId", sa.String(length=36), nullable=False),
        sa.Column("issuedAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expiresAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotatedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replacedBy", sa.Integer(), nullable=True),
        sa.Column("revokedAt", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["userID"], ["Users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["replacedBy"], ["ApiRefreshTokens.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="unique_api_refresh_token"),
    )
    op.create_index("idx_api_refresh_token_user", "ApiRefreshTokens", ["userID"])
    op.create_index("idx_api_refresh_token_family", "ApiRefreshTokens", ["familyId"])


def downgrade():
    op.drop_index("idx_api_refresh_token_family", table_name="ApiRefreshTokens")
    op.drop_index("idx_api_refresh_token_user", table_name="ApiRefreshTokens")
    op.drop_table("ApiRefreshTokens")
