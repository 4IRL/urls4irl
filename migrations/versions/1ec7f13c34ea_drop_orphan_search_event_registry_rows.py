"""Drop orphan ui_search_open and ui_search_close from EventRegistry after event rename

Revision ID: 1ec7f13c34ea
Revises: f83b112abd2c
Create Date: 2026-06-08 09:26:10.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "1ec7f13c34ea"
down_revision = "f83b112abd2c"
branch_labels = None
depends_on = None


def upgrade():
    # `sync_event_registry()` only inserts/updates — it never deletes. After
    # the rename from ui_search_{open,close} to per-target events
    # (ui_utub_search_*, ui_url_search_*), the legacy rows linger as orphans
    # in `EventRegistry` even though no `AnonymousMetrics` rows reference
    # them in this pre-production branch. Purge them surgically so future
    # joins on event_name see only the live taxonomy.
    op.execute("""
        DELETE FROM "EventRegistry"
        WHERE name IN ('ui_search_open', 'ui_search_close')
        """)


def downgrade():
    # Recreate the two legacy rows with the descriptions/category they
    # carried before the rename so the downgrade leaves `EventRegistry` in
    # the shape it would have had pre-upgrade. `addedAt` defaults to now()
    # at the column level (server_default), so we omit it here.
    op.execute("""
        INSERT INTO "EventRegistry" (name, category, description)
        VALUES
            ('ui_search_open', 'ui', 'Search box opened'),
            ('ui_search_close', 'ui', 'Search box closed')
        """)
