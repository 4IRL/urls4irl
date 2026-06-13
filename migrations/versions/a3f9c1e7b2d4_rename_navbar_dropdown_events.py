"""Rename ui_navbar_mobile_menu_open/close to ui_navbar_dropdown_open/close

The navbar hamburger dropdown is now surfaced on desktop as well as mobile, so
the "mobile" qualifier in the event name no longer reflects where it fires. The
device_type dimension already distinguishes desktop from mobile, so the rename
is purely cosmetic on the event name and preserves every dimension verbatim.

Mirrors the rename pattern in 1ec7f13c34ea, minus the target-dimension split:
these two events carry only device_type, so the rename is a straight 1:1 map
and no preflight dimension check is required.

Revision ID: a3f9c1e7b2d4
Revises: 0538b281d033
Create Date: 2026-06-13 11:33:00.000000

"""

from alembic import op

revision = "a3f9c1e7b2d4"
down_revision = "0538b281d033"
branch_labels = None
depends_on = None

# (old_event_name, new_event_name, new_description)
_RENAMES: tuple[tuple[str, str, str], ...] = (
    (
        "ui_navbar_mobile_menu_open",
        "ui_navbar_dropdown_open",
        "Navbar dropdown menu opened",
    ),
    (
        "ui_navbar_mobile_menu_close",
        "ui_navbar_dropdown_close",
        "Navbar dropdown menu closed",
    ),
)

# Descriptions used when re-creating the legacy EventRegistry rows on downgrade,
# matched to the pre-rename wording in backend/metrics/event_registry.py.
_LEGACY_EVENTS: tuple[tuple[str, str], ...] = (
    ("ui_navbar_mobile_menu_open", "Mobile hamburger menu opened"),
    ("ui_navbar_mobile_menu_close", "Mobile hamburger menu closed"),
)


def _rename_event(old_name: str, new_name: str, new_description: str) -> None:
    # Step 1 — seed the new EventRegistry row. `flask metrics sync-registry`
    # runs AFTER `flask db upgrade` in docker/startup-flask.sh, so the new
    # event name does not yet exist in EventRegistry when this migration runs;
    # without this insert the AnonymousMetrics.eventName FK would block step 3.
    op.execute(f"""
        INSERT INTO "EventRegistry" (name, category, description)
        VALUES ('{new_name}', 'ui', '{new_description}')
        ON CONFLICT (name) DO NOTHING
        """)

    # Step 2 — rewrite existing AnonymousMetrics rows onto the new event name.
    # The ON CONFLICT merge sums counts in the (dev-only) case where new-name
    # rows already exist; the follow-up DELETE clears the legacy rows so the
    # EventRegistry DELETE in step 3 cannot be blocked by the FK.
    op.execute(f"""
        INSERT INTO "AnonymousMetrics" ("eventName", endpoint, method, "statusCode", "bucketStart", dimensions, count)
        SELECT '{new_name}', endpoint, method, "statusCode", "bucketStart", dimensions, count
        FROM "AnonymousMetrics"
        WHERE "eventName" = '{old_name}'
        ON CONFLICT ("bucketStart", "eventName", dimensions)
        DO UPDATE SET count = "AnonymousMetrics".count + EXCLUDED.count
        """)
    op.execute(f"""
        DELETE FROM "AnonymousMetrics"
        WHERE "eventName" = '{old_name}'
        """)

    # Step 3 — drop the orphan EventRegistry row. No AnonymousMetrics row
    # references it now, so the FK cannot reject the DELETE.
    op.execute(f"""
        DELETE FROM "EventRegistry"
        WHERE name = '{old_name}'
        """)


def upgrade():
    for old_name, new_name, new_description in _RENAMES:
        _rename_event(old_name, new_name, new_description)


def downgrade():
    # Restore the legacy EventRegistry rows first so the rename-back satisfies
    # the AnonymousMetrics.eventName FK, then rewrite the rows in reverse.
    for legacy_name, legacy_description in _LEGACY_EVENTS:
        op.execute(f"""
            INSERT INTO "EventRegistry" (name, category, description)
            VALUES ('{legacy_name}', 'ui', '{legacy_description}')
            ON CONFLICT (name) DO NOTHING
            """)

    for old_name, new_name, _ in _RENAMES:
        op.execute(f"""
            INSERT INTO "AnonymousMetrics" ("eventName", endpoint, method, "statusCode", "bucketStart", dimensions, count)
            SELECT '{old_name}', endpoint, method, "statusCode", "bucketStart", dimensions, count
            FROM "AnonymousMetrics"
            WHERE "eventName" = '{new_name}'
            ON CONFLICT ("bucketStart", "eventName", dimensions)
            DO UPDATE SET count = "AnonymousMetrics".count + EXCLUDED.count
            """)
        op.execute(f"""
            DELETE FROM "AnonymousMetrics"
            WHERE "eventName" = '{new_name}'
            """)
        op.execute(f"""
            DELETE FROM "EventRegistry"
            WHERE name = '{new_name}'
            """)
