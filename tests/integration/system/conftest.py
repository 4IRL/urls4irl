from __future__ import annotations

from typing import Any


def reset_postgres_enum_to_lowercase_values(pg_conn: Any) -> None:
    """Force the Postgres `event_category_enum` type to contain only the
    lowercase StrEnum VALUES — matching the production migration's
    `postgresql.ENUM("api", "domain", "ui", name="event_category_enum")`.

    `db.create_all()` (used in test setup) generates the enum from the
    SQLAlchemy column definition. Without `values_callable`, SQLAlchemy
    emits the enum using the member NAMES (uppercase), so the test DB's
    enum disagrees with production. We rebuild the enum here so callers
    reproduce the exact mismatch production hits.

    Accepts a raw psycopg2 connection. Tests driven by SQLAlchemy can
    obtain one via `db.engine.raw_connection()` and pass it through.
    """
    with pg_conn.cursor() as cur:
        cur.execute('DELETE FROM "EventRegistry"')
        cur.execute('ALTER TABLE "EventRegistry" ALTER COLUMN "category" TYPE TEXT')
        cur.execute("DROP TYPE IF EXISTS event_category_enum")
        cur.execute("CREATE TYPE event_category_enum AS ENUM ('api', 'domain', 'ui')")
        cur.execute(
            'ALTER TABLE "EventRegistry" ALTER COLUMN "category"'
            " TYPE event_category_enum USING category::event_category_enum"
        )
    pg_conn.commit()
