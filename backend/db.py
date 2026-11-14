from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect
from sqlalchemy.engine import Connection

db = SQLAlchemy()


def get_missing_tables(*, connection: Connection | None = None) -> list[str]:
    """Compare registered model tables against what actually exists in the database.

    Returns a list of table names that are defined in SQLAlchemy metadata but
    missing from the database. An empty list means all tables are present.
    With ``connection`` the inspection runs on that connection instead of
    ``db.engine``.
    """
    expected_tables = {table.name for table in db.metadata.sorted_tables}
    inspect_target = connection if connection is not None else db.engine
    actual_tables = set(inspect(inspect_target).get_table_names())
    missing = expected_tables - actual_tables
    return sorted(missing)
