"""replace the compact view mode with title_line and url_line

Revision ID: b3e7c1d9a4f2
Revises: 7c3f9a1b5d82
Create Date: 2026-10-27 12:00:00.000000

The ``compact`` view mode is split into two single-line views, ``title_line`` and
``url_line``. Two places store the view mode:

* ``UserPreferences.defaultView``, a native Postgres enum (``view_mode_enum``)
  whose members change from ``list, compact, cards`` to
  ``list, title_line, url_line, cards``. Postgres cannot drop an enum member, so
  a new type is created, the column is cast over with ``compact`` mapped to
  ``title_line``, the old type is dropped, and the new type takes the old name.
* ``UtubMembers.settings`` (JSONB), whose ``urls.view_mode`` string is rewritten
  from ``compact`` to ``title_line`` with ``jsonb_set`` so sibling keys survive.

The downgrade is the mirror: both new values map back to ``compact``, in the
column and in the member JSONB. ``defaultView`` is NOT NULL with no server
default before and after, so no default is dropped or restored.

Deploy window (accepted): this is a single revision and ``migrate`` runs before
the app starts, so an old-code instance may briefly read a migrated
``title_line``/``url_line`` row.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b3e7c1d9a4f2"
down_revision = "7c3f9a1b5d82"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE TYPE view_mode_enum_new AS ENUM "
        "('list', 'title_line', 'url_line', 'cards')"
    )
    op.execute(
        'ALTER TABLE "UserPreferences" ALTER COLUMN "defaultView" '
        "TYPE view_mode_enum_new USING "
        "(CASE WHEN \"defaultView\"::text = 'compact' THEN 'title_line' "
        'ELSE "defaultView"::text END)::view_mode_enum_new'
    )
    op.execute("DROP TYPE view_mode_enum")
    op.execute("ALTER TYPE view_mode_enum_new RENAME TO view_mode_enum")
    op.execute(
        'UPDATE "UtubMembers" SET settings = '
        "jsonb_set(settings, '{urls,view_mode}', '\"title_line\"') "
        "WHERE settings #>> '{urls,view_mode}' = 'compact'"
    )


def downgrade():
    # Lossy by design: the title_line / url_line distinction collapses to compact.
    op.execute("CREATE TYPE view_mode_enum_old AS ENUM ('list', 'compact', 'cards')")
    op.execute(
        'ALTER TABLE "UserPreferences" ALTER COLUMN "defaultView" '
        "TYPE view_mode_enum_old USING "
        "(CASE WHEN \"defaultView\"::text IN ('title_line', 'url_line') "
        "THEN 'compact' ELSE \"defaultView\"::text END)::view_mode_enum_old"
    )
    op.execute("DROP TYPE view_mode_enum")
    op.execute("ALTER TYPE view_mode_enum_old RENAME TO view_mode_enum")
    op.execute(
        'UPDATE "UtubMembers" SET settings = '
        "jsonb_set(settings, '{urls,view_mode}', '\"compact\"') "
        "WHERE settings #>> '{urls,view_mode}' IN ('title_line', 'url_line')"
    )
