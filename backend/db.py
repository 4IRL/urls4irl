from sqlalchemy import inspect

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def get_missing_tables() -> list[str]:
    """Compare registered model tables against what actually exists in the database.

    Returns a list of table names that are defined in SQLAlchemy metadata but
    missing from the database. An empty list means all tables are present.
    """
    expected_tables = {table.name for table in db.metadata.sorted_tables}
    actual_tables = set(inspect(db.engine).get_table_names())
    missing = expected_tables - actual_tables
    return sorted(missing)
