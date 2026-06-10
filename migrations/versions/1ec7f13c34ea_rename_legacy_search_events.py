"""Rename legacy ui_search_open/close events to per-target names and prune the orphan EventRegistry rows

Revision ID: 1ec7f13c34ea
Revises: f83b112abd2c
Create Date: 2026-06-08 09:26:10.000000

"""

from alembic import op

revision = "1ec7f13c34ea"
down_revision = "f83b112abd2c"
branch_labels = None
depends_on = None

# Pre-rename `ui_search_open` / `ui_search_close` carried `target:
# Literal["utubs", "urls"]` as a JSONB dimension. Post-rename the target is
# encoded in the event name itself, but the new Pydantic dim models still
# require `target` narrowed to a single literal (e.g. `_DimUtubSearchOpen.
# target: Literal["utubs"]`), so dimensions are preserved verbatim when an
# AnonymousMetrics row is rewritten.
_RENAMES: tuple[tuple[str, str, str, str], ...] = (
    ("ui_search_open", "utubs", "ui_utub_search_open", "UTub search box opened"),
    ("ui_search_close", "utubs", "ui_utub_search_close", "UTub search box closed"),
    ("ui_search_open", "urls", "ui_url_search_open", "URL search box opened"),
    ("ui_search_close", "urls", "ui_url_search_close", "URL search box closed"),
)

# Descriptions used when re-creating the legacy EventRegistry rows on
# downgrade, matched to v1.16.1 production wording.
_LEGACY_EVENTS: tuple[tuple[str, str], ...] = (
    ("ui_search_open", "Search box opened"),
    ("ui_search_close", "Search box closed"),
)


def upgrade():
    # Step 1 — seed the four new EventRegistry rows. The new event-name enum
    # members live in post-v1.16.1 code, and `flask metrics sync-registry`
    # runs AFTER `flask db upgrade` in docker/startup-flask.sh, so without this
    # insert the new event names do not exist in the DB when the rename runs,
    # and the AnonymousMetrics.eventName FK (NO ACTION default on delete) would
    # block step 3.
    for _, _, new_name, description in _RENAMES:
        op.execute(f"""
            INSERT INTO "EventRegistry" (name, category, description)
            VALUES ('{new_name}', 'ui', '{description}')
            ON CONFLICT (name) DO NOTHING
            """)

    # Step 2 — rewrite legacy AnonymousMetrics rows to the new event name. The
    # INSERT ... ON CONFLICT merge handles the (vanishingly rare) case where a
    # row with the same bucket/dimensions already exists under the new name —
    # impossible in v1.16.1 prod, but possible in dev DBs where the new code
    # has already been writing new-name rows. The follow-up DELETE removes the
    # legacy rows so step 3's EventRegistry DELETE cannot be blocked by the
    # FK constraint.
    for legacy_name, target, new_name, _ in _RENAMES:
        op.execute(f"""
            INSERT INTO "AnonymousMetrics" ("eventName", endpoint, method, "statusCode", "bucketStart", dimensions, count)
            SELECT '{new_name}', endpoint, method, "statusCode", "bucketStart", dimensions, count
            FROM "AnonymousMetrics"
            WHERE "eventName" = '{legacy_name}'
              AND dimensions->>'target' = '{target}'
            ON CONFLICT ("bucketStart", "eventName", dimensions)
            DO UPDATE SET count = "AnonymousMetrics".count + EXCLUDED.count
            """)
        op.execute(f"""
            DELETE FROM "AnonymousMetrics"
            WHERE "eventName" = '{legacy_name}'
              AND dimensions->>'target' = '{target}'
            """)

    # Step 3 — drop the orphan EventRegistry rows. No AnonymousMetrics row
    # references them now, so the FK cannot reject the DELETE.
    op.execute("""
        DELETE FROM "EventRegistry"
        WHERE name IN ('ui_search_open', 'ui_search_close')
        """)


def downgrade():
    # Step 1 — restore the legacy EventRegistry rows so the rename-back can
    # satisfy the AnonymousMetrics.eventName FK.
    for legacy_name, description in _LEGACY_EVENTS:
        op.execute(f"""
            INSERT INTO "EventRegistry" (name, category, description)
            VALUES ('{legacy_name}', 'ui', '{description}')
            ON CONFLICT (name) DO NOTHING
            """)

    # Step 2 — rewrite new-name rows back to the legacy event name. Mirrors
    # the upgrade's merge-then-delete pattern in reverse: every new-name row
    # for a given target maps cleanly to the corresponding legacy name because
    # the `target` dimension is preserved verbatim.
    for legacy_name, target, new_name, _ in _RENAMES:
        op.execute(f"""
            INSERT INTO "AnonymousMetrics" ("eventName", endpoint, method, "statusCode", "bucketStart", dimensions, count)
            SELECT '{legacy_name}', endpoint, method, "statusCode", "bucketStart", dimensions, count
            FROM "AnonymousMetrics"
            WHERE "eventName" = '{new_name}'
              AND dimensions->>'target' = '{target}'
            ON CONFLICT ("bucketStart", "eventName", dimensions)
            DO UPDATE SET count = "AnonymousMetrics".count + EXCLUDED.count
            """)
        op.execute(f"""
            DELETE FROM "AnonymousMetrics"
            WHERE "eventName" = '{new_name}'
              AND dimensions->>'target' = '{target}'
            """)

    # Step 3 — drop the new EventRegistry rows. Safe because step 2 leaves
    # no AnonymousMetrics row referencing them.
    op.execute("""
        DELETE FROM "EventRegistry"
        WHERE name IN ('ui_utub_search_open', 'ui_utub_search_close',
                       'ui_url_search_open', 'ui_url_search_close')
        """)
