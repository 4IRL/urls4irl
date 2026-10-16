"""add partial indexes on deletedAt for Utubs and UtubUrls

Revision ID: e5a1c7d9b3f2
Revises: c4e8a1f3b7d2
Create Date: 2026-10-16 12:00:00.000000

Adds ``idx_utubs_deleted_at`` and ``idx_utub_urls_deleted_at``, partial indexes on
``"deletedAt"`` restricted to ``WHERE "deletedAt" IS NOT NULL``. Only trashed
rows are indexed, so the indexes stay tiny while letting the trash purge sweep
and the Trash list avoid scanning the full tables. This closes the index
question that ``a9d3e5f7b1c2`` (add soft delete columns) deferred to "the purge
sweep".

The downgrade drops both indexes; no data is touched in either direction.

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e5a1c7d9b3f2"
down_revision = "c4e8a1f3b7d2"
branch_labels = None
depends_on = None

_UTUBS_INDEX = "idx_utubs_deleted_at"
_UTUB_URLS_INDEX = "idx_utub_urls_deleted_at"


def upgrade() -> None:
    op.create_index(
        _UTUBS_INDEX,
        "Utubs",
        ["deletedAt"],
        postgresql_where=sa.text('"deletedAt" IS NOT NULL'),
    )
    op.create_index(
        _UTUB_URLS_INDEX,
        "UtubUrls",
        ["deletedAt"],
        postgresql_where=sa.text('"deletedAt" IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index(_UTUB_URLS_INDEX, table_name="UtubUrls")
    op.drop_index(_UTUBS_INDEX, table_name="Utubs")
