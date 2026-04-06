from unittest.mock import patch

import pytest
from sqlalchemy import text

from backend import db
from backend.utils.db_table_names import TABLE_NAMES

pytestmark = pytest.mark.cli


def test_starting_log_warns_on_partial_missing_tables(runner):
    """
    GIVEN a database where some tables have been dropped (partial missing state)
    WHEN the developer runs `flask utils start-log`
    THEN verify the CLI logger emits a warning containing the missing table names
    """
    app, cli_runner = runner

    with app.app_context():
        db.session.execute(
            text(f'DROP TABLE IF EXISTS "{TABLE_NAMES.CONTACT_FORM_ENTRIES}" CASCADE')
        )
        db.session.commit()

    try:
        with app.app_context():
            with patch.object(app.cli_logger, "warning") as mock_warning:
                result = cli_runner.invoke(args=["utils", "start-log"])

                assert result.exit_code == 0
                mock_warning.assert_called_once()
                warning_message = mock_warning.call_args[0][0]
                assert "missing tables" in warning_message.lower()
                assert TABLE_NAMES.CONTACT_FORM_ENTRIES in warning_message
    finally:
        with app.app_context():
            db.create_all()
