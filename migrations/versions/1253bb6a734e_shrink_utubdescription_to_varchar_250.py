"""shrink utubDescription to varchar 250

Shrinks "Utubs"."utubDescription" from VARCHAR(500) to VARCHAR(250) so the live
column matches UTUB_CONSTANTS.MAX_DESCRIPTION_LENGTH (the model already declares
String(250)). This reconciles the model/DB drift introduced when the validation
cap was lowered to 250.

The deploy of this migration is GATED on issue #655's production audit: the
shrink will error if any existing "utubDescription" row exceeds 250 characters,
so the audit must confirm no live row is longer than 250 chars before upgrade.

Revision ID: 1253bb6a734e
Revises: af33bd794058
Create Date: 2026-06-23 05:04:57.953597

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "1253bb6a734e"
down_revision = "af33bd794058"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "Utubs",
        "utubDescription",
        type_=sa.String(length=250),
        existing_type=sa.String(length=500),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "Utubs",
        "utubDescription",
        type_=sa.String(length=500),
        existing_type=sa.String(length=250),
        existing_nullable=True,
    )
