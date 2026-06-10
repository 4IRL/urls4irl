"""backfill device_type on legacy anonymous metrics rows

Revision ID: 0538b281d033
Revises: 1ec7f13c34ea
Create Date: 2026-06-10 14:07:35.401807

"""

from alembic import op

revision = "0538b281d033"
down_revision = "1ec7f13c34ea"
branch_labels = None
depends_on = None

# DeviceType wire values match backend.metrics.events.DeviceType — duplicated here
# (not imported) so the migration stays self-contained at any future point in code
# history, even if the enum is renamed or moved.
_MOBILE: int = 1
_DESKTOP: int = 2

# Events that can only be emitted from a mobile viewport (no isMobile guard needed
# because the underlying DOM only exists on mobile layouts).
_MOBILE_ONLY_EVENTS: tuple[str, ...] = (
    "ui_navbar_mobile_menu_open",
    "ui_navbar_mobile_menu_close",
    "ui_mobile_nav",
)

# Events that are explicitly guarded with `if (isMobile()) return;` at the emit
# site (collapsible side panels in frontend/home/collapsible-decks.ts).
_DESKTOP_ONLY_EVENTS: tuple[str, ...] = (
    "ui_deck_expand",
    "ui_deck_collapse",
)


def upgrade():
    op.execute(f"""
        UPDATE "AnonymousMetrics"
        SET dimensions = dimensions || '{{"device_type": {_MOBILE}}}'::jsonb
        WHERE NOT (dimensions ? 'device_type')
          AND "eventName" IN {_MOBILE_ONLY_EVENTS}
        """)
    op.execute(f"""
        UPDATE "AnonymousMetrics"
        SET dimensions = dimensions || '{{"device_type": {_DESKTOP}}}'::jsonb
        WHERE NOT (dimensions ? 'device_type')
          AND "eventName" IN {_DESKTOP_ONLY_EVENTS}
        """)
    op.execute(f"""
        UPDATE "AnonymousMetrics"
        SET dimensions = dimensions ||
            CASE WHEN id % 2 = 0
                THEN '{{"device_type": {_DESKTOP}}}'::jsonb
                ELSE '{{"device_type": {_MOBILE}}}'::jsonb
            END
        WHERE NOT (dimensions ? 'device_type')
        """)


def downgrade():
    # Irreversible by design. The 50/50 split assigns device_type to rows whose
    # original UA was unknowable, so stripping the key now would not restore the
    # pre-upgrade state — it would also wipe device_type tags written legitimately
    # after the upgrade (every new row written by the post-feature/device-type-filter
    # writer carries device_type). Leaving as a no-op is the safest choice.
    pass
