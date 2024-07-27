import pytest
from sqlalchemy import inspect
from sqlalchemy.engine.reflection import Inspector

from src import db
from src.models.tags import Tags
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
        initial_tags_count = Tags.query.count()
        initial_utub_member_count = Utub_Members.query.count()
        initial_utub_urls_count = Utub_Urls.query.count()
        initial_utub_tag_count = Utub_Url_Tags.query.count()

    cli_runner.invoke(args=["managedb", "clear", "test"])

    with app.app_context():
        assert initial_user_count != Users.query.count() and Users.query.count() == 0
        assert initial_utub_count != Utubs.query.count() and Utubs.query.count() == 0
        assert initial_urls_count != Urls.query.count() and Urls.query.count() == 0
        assert initial_tags_count != Tags.query.count() and Tags.query.count() == 0
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


def test_drop_db(runner):
    """
    GIVEN a database containing relevant tables for URLS4IRL
    WHEN the developer drops the tables from the database using the CLI command as follows:
        `flask managedb drop test`
    THEN verify that the database tables are dropped from the database

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner
    with app.app_context():
        inspector: Inspector = inspect(db.engine)
        has_users = inspector.has_table("Users")
        has_forgot_password = inspector.has_table("ForgotPasswords")
        has_email_validations = inspector.has_table("EmailValidations")
        has_utubs = inspector.has_table("Utubs")
        has_urls = inspector.has_table("Urls")
        has_tags = inspector.has_table("Tags")
        has_utub_members = inspector.has_table("UtubMembers")
        has_utub_urls = inspector.has_table("UtubUrls")
        has_utub_tags = inspector.has_table("UtubUrlTags")

    cli_runner.invoke(args=["managedb", "drop", "test"])

    with app.app_context():
        inspector: Inspector = inspect(db.engine)
        assert has_users != inspector.has_table("Users")
        assert has_forgot_password != inspector.has_table("ForgotPasswords")
        assert has_email_validations != inspector.has_table("EmailValidations")
        assert has_utubs != inspector.has_table("Utubs")
        assert has_urls != inspector.has_table("Urls")
        assert has_tags != inspector.has_table("Tags")
        assert has_utub_members != inspector.has_table("UtubMembers")
        assert has_utub_urls != inspector.has_table("UtubUrls")
        assert has_utub_tags != inspector.has_table("UtubUrlTags")

        # Make sure to recreate the database for future tests
        db.create_all()
