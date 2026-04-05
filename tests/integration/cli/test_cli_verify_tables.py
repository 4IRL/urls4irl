from unittest.mock import patch

import pytest
from sqlalchemy import inspect as sa_inspect, text
from sqlalchemy.engine.reflection import Inspector

from backend import db
from backend.cli.utils import (
    VERIFY_TABLES_ALL_OK,
    VERIFY_TABLES_FATAL_DEPLOYED,
    VERIFY_TABLES_FATAL_REPAIR_FAILED,
    VERIFY_TABLES_REPAIRED,
)
from backend.utils.db_table_names import TABLE_NAMES
from backend.utils.strings.config_strs import CONFIG_ENVS

pytestmark = pytest.mark.cli


def test_verify_tables_passes_when_all_tables_exist(runner):
    """
    GIVEN a database with all model tables created
    WHEN the developer runs `flask utils verify-tables`
    THEN verify the command exits with code 0 and reports success
    """
    app, cli_runner = runner
    result = cli_runner.invoke(args=["utils", "verify-tables"])

    assert result.exit_code == 0
    assert VERIFY_TABLES_ALL_OK in result.output


def test_verify_tables_fails_in_deployed_mode_when_tables_missing(runner):
    """
    GIVEN a deployed environment where application tables have been dropped
    WHEN the developer runs `flask utils verify-tables`
    THEN verify the command exits with code 1 and refuses to auto-repair
    """
    app, cli_runner = runner

    with app.app_context():
        db.drop_all()
        app.config[CONFIG_ENVS.PRODUCTION] = True

    try:
        result = cli_runner.invoke(args=["utils", "verify-tables"])

        assert result.exit_code == 1
        assert VERIFY_TABLES_FATAL_DEPLOYED in result.output
        assert TABLE_NAMES.USERS in result.output
        assert TABLE_NAMES.UTUBS in result.output
    finally:
        with app.app_context():
            app.config[CONFIG_ENVS.PRODUCTION] = False
            db.create_all()


def test_verify_tables_fails_in_dev_server_mode_when_tables_missing(runner):
    """
    GIVEN a DEV_SERVER environment where application tables have been dropped
    WHEN the developer runs `flask utils verify-tables`
    THEN verify the command exits with code 1 and refuses to auto-repair,
        identical to PRODUCTION behavior
    """
    app, cli_runner = runner

    with app.app_context():
        db.drop_all()
        app.config[CONFIG_ENVS.DEV_SERVER] = True

    try:
        result = cli_runner.invoke(args=["utils", "verify-tables"])

        assert result.exit_code == 1
        assert VERIFY_TABLES_FATAL_DEPLOYED in result.output
        assert TABLE_NAMES.USERS in result.output
        assert TABLE_NAMES.UTUBS in result.output
    finally:
        with app.app_context():
            app.config[CONFIG_ENVS.DEV_SERVER] = False
            db.create_all()


def test_verify_tables_reports_single_missing_table_in_deployed_mode(runner):
    """
    GIVEN a deployed environment where only ContactFormEntries has been dropped
    WHEN the developer runs `flask utils verify-tables`
    THEN verify the command exits with code 1 and reports only that table
    """
    app, cli_runner = runner

    with app.app_context():
        db.session.execute(
            text(f'DROP TABLE IF EXISTS "{TABLE_NAMES.CONTACT_FORM_ENTRIES}" CASCADE')
        )
        db.session.commit()
        app.config[CONFIG_ENVS.PRODUCTION] = True

    try:
        result = cli_runner.invoke(args=["utils", "verify-tables"])

        assert result.exit_code == 1
        assert TABLE_NAMES.CONTACT_FORM_ENTRIES in result.output
        assert TABLE_NAMES.USERS not in result.output
    finally:
        with app.app_context():
            app.config[CONFIG_ENVS.PRODUCTION] = False
            db.create_all()


def test_verify_tables_checks_all_model_tables(runner):
    """
    GIVEN a database with all model tables created
    WHEN inspecting the database
    THEN verify that every table in SQLAlchemy metadata exists in the database
        and the verify-tables command passes
    """
    app, cli_runner = runner

    with app.app_context():
        expected_tables = {table.name for table in db.metadata.sorted_tables}
        inspector: Inspector = sa_inspect(db.engine)
        actual_tables = set(inspector.get_table_names())

    assert expected_tables.issubset(actual_tables)

    result = cli_runner.invoke(args=["utils", "verify-tables"])
    assert result.exit_code == 0


def test_verify_tables_auto_repairs_when_tables_missing_in_non_deployed_mode(runner):
    """
    GIVEN a non-deployed environment where all tables have been dropped
    WHEN the developer runs `flask utils verify-tables`
    THEN verify the command auto-repairs by dropping the schema, re-running
        migrations, and exits with code 0 reporting successful repair
    """
    app, cli_runner = runner

    with app.app_context():
        db.drop_all()

    with patch(
        "flask_migrate.upgrade",
        side_effect=lambda: db.create_all(),
    ):
        result = cli_runner.invoke(args=["utils", "verify-tables"])

    assert result.exit_code == 0
    assert VERIFY_TABLES_REPAIRED in result.output

    with app.app_context():
        expected_tables = {table.name for table in db.metadata.sorted_tables}
        inspector: Inspector = sa_inspect(db.engine)
        actual_tables = set(inspector.get_table_names())

    assert expected_tables.issubset(actual_tables)


def test_verify_tables_exits_with_fatal_when_repair_fails(runner):
    """
    GIVEN a non-deployed environment where all tables have been dropped
    WHEN `flask_migrate.upgrade` is mocked to no-op (tables remain missing)
        and the developer runs `flask utils verify-tables`
    THEN verify the command exits with code 1 and reports fatal repair failure
    """
    app, cli_runner = runner

    with app.app_context():
        db.drop_all()

    with patch("flask_migrate.upgrade"):
        result = cli_runner.invoke(args=["utils", "verify-tables"])

    assert result.exit_code == 1
    assert VERIFY_TABLES_FATAL_REPAIR_FAILED in result.output

    # Restore tables for subsequent tests
    with app.app_context():
        db.create_all()
