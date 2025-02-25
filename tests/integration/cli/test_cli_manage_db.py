import os

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect
from sqlalchemy.engine.reflection import Inspector

from src import db, migrate
from src.cli.utils import TABLE_NAMES
from src.models.utub_tags import Utub_Tags
from src.models.urls import Urls
from src.models.users import Users
from src.models.utub_members import Utub_Members
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utub_urls import Utub_Urls
from src.models.utubs import Utubs

pytestmark = pytest.mark.cli


def test_clear_db(runner):
    """
    GIVEN a filled database, using the CLI arguments to add mock
        entries for all associated Users, Utubs, Url/Tags
    WHEN the developer clears the database using the CLI command as follows:
        `flask managedb clear test`
    THEN verify that the database tables are now empty

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner
    cli_runner.invoke(args=["addmock", "all"])
    with app.app_context():
        initial_user_count = Users.query.count()
        initial_utub_count = Utubs.query.count()
        initial_urls_count = Urls.query.count()
        initial_tags_count = Utub_Tags.query.count()
        initial_utub_member_count = Utub_Members.query.count()
        initial_utub_urls_count = Utub_Urls.query.count()
        initial_utub_tag_count = Utub_Url_Tags.query.count()

    cli_runner.invoke(args=["managedb", "clear", "test"])

    with app.app_context():
        assert initial_user_count != Users.query.count() and Users.query.count() == 0
        assert initial_utub_count != Utubs.query.count() and Utubs.query.count() == 0
        assert initial_urls_count != Urls.query.count() and Urls.query.count() == 0
        assert (
            initial_tags_count != Utub_Tags.query.count()
            and Utub_Tags.query.count() == 0
        )
        assert (
            initial_utub_member_count != Utub_Members.query.count()
            and Utub_Members.query.count() == 0
        )
        assert (
            initial_utub_urls_count != Utub_Urls.query.count()
            and Utub_Urls.query.count() == 0
        )
        assert (
            initial_utub_tag_count != Utub_Url_Tags.query.count()
            and Utub_Url_Tags.query.count() == 0
        )


def test_drop_db_without_migrations(runner):
    """
    GIVEN a database containing relevant tables for URLS4IRL
    WHEN the developer drops all the tables from the database using the CLI command as follows:
        `flask managedb drop test --drop-alembic`
    THEN verify that the database tables are dropped from the database

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner
    with app.app_context():
        inspector: Inspector = inspect(db.engine)
        has_users = inspector.has_table(TABLE_NAMES.USERS)
        has_forgot_password = inspector.has_table(TABLE_NAMES.FORGOT_PASSWORDS)
        has_email_validations = inspector.has_table(TABLE_NAMES.EMAIL_VALIDATIONS)
        has_utubs = inspector.has_table(TABLE_NAMES.UTUBS)
        has_urls = inspector.has_table(TABLE_NAMES.URLS)
        has_tags = inspector.has_table(TABLE_NAMES.UTUB_TAGS)
        has_utub_members = inspector.has_table(TABLE_NAMES.UTUB_MEMBERS)
        has_utub_urls = inspector.has_table(TABLE_NAMES.UTUB_URLS)
        has_utub_tags = inspector.has_table(TABLE_NAMES.UTUB_URL_TAGS)

    cli_runner.invoke(args=["managedb", "drop", "test", "--drop-alembic"])

    with app.app_context():
        inspector: Inspector = inspect(db.engine)
        assert has_users != inspector.has_table(TABLE_NAMES.USERS)
        assert has_forgot_password != inspector.has_table(TABLE_NAMES.FORGOT_PASSWORDS)
        assert has_email_validations != inspector.has_table(
            TABLE_NAMES.EMAIL_VALIDATIONS
        )
        assert has_utubs != inspector.has_table(TABLE_NAMES.UTUBS)
        assert has_urls != inspector.has_table(TABLE_NAMES.URLS)
        assert has_tags != inspector.has_table(TABLE_NAMES.UTUB_TAGS)
        assert has_utub_members != inspector.has_table(TABLE_NAMES.UTUB_MEMBERS)
        assert has_utub_urls != inspector.has_table(TABLE_NAMES.UTUB_URLS)
        assert has_utub_tags != inspector.has_table(TABLE_NAMES.UTUB_URL_TAGS)
        assert not inspector.has_table(TABLE_NAMES.ALEMBIC_VERSION)

        # Make sure to recreate the database for future tests
        db.create_all()


def test_drop_db_with_migrations(runner):
    """
    GIVEN a database containing relevant tables for URLS4IRL that is fully migrated
    WHEN the developer drops all the tables except migration table from the database using the CLI command as follows:
        `flask managedb drop test`
    THEN verify that the database tables are dropped from the database, but the migration table is kept

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    os.environ["PYTEST_RUNNING"] = (
        "1"  # Turn off alembic logging for this test via flag
    )
    app, cli_runner = runner
    cli_runner.invoke(args=["managedb", "drop", "test"])
    migrate.init_app(app)

    with app.app_context():
        alembic_config = Config("./migrations/alembic.ini")
        alembic_config.set_main_option("script_location", "migrations/")
        alembic_config.attributes["connection"] = db.engine.connect()

        command.upgrade(alembic_config, "head")

        inspector: Inspector = inspect(db.engine)
        has_users = inspector.has_table(TABLE_NAMES.USERS)
        has_forgot_password = inspector.has_table(TABLE_NAMES.FORGOT_PASSWORDS)
        has_email_validations = inspector.has_table(TABLE_NAMES.EMAIL_VALIDATIONS)
        has_utubs = inspector.has_table(TABLE_NAMES.UTUBS)
        has_urls = inspector.has_table(TABLE_NAMES.URLS)
        has_tags = inspector.has_table(TABLE_NAMES.UTUB_TAGS)
        has_utub_members = inspector.has_table(TABLE_NAMES.UTUB_MEMBERS)
        has_utub_urls = inspector.has_table(TABLE_NAMES.UTUB_URLS)
        has_utub_tags = inspector.has_table(TABLE_NAMES.UTUB_URL_TAGS)
        has_alembic_version = inspector.has_table(TABLE_NAMES.ALEMBIC_VERSION)

    cli_runner.invoke(args=["managedb", "drop", "test"])

    with app.app_context():
        inspector: Inspector = inspect(db.engine)

        assert has_users != inspector.has_table(TABLE_NAMES.USERS)
        assert has_forgot_password != inspector.has_table(TABLE_NAMES.FORGOT_PASSWORDS)
        assert has_email_validations != inspector.has_table(
            TABLE_NAMES.EMAIL_VALIDATIONS
        )
        assert has_utubs != inspector.has_table(TABLE_NAMES.UTUBS)
        assert has_urls != inspector.has_table(TABLE_NAMES.URLS)
        assert has_tags != inspector.has_table(TABLE_NAMES.UTUB_TAGS)
        assert has_utub_members != inspector.has_table(TABLE_NAMES.UTUB_MEMBERS)
        assert has_utub_urls != inspector.has_table(TABLE_NAMES.UTUB_URLS)
        assert has_utub_tags != inspector.has_table(TABLE_NAMES.UTUB_URL_TAGS)
        assert has_alembic_version == inspector.has_table(TABLE_NAMES.ALEMBIC_VERSION)

        # Make sure to recreate the database for future tests
        db.create_all()
    del os.environ[
        "PYTEST_RUNNING"
    ]  # Remove env variable used to turn off alembic logging
