import pytest
from sqlalchemy import inspect

from src import db
from src.models import URLS, Utub, User, Utub_Urls, Utub_Users, Url_Tags

pytestmark = pytest.mark.unit


def test_db_created_correctly(app):
    """
    GIVEN a valid database with all given tables
    WHEN these tests are running
    THEN ensure all tables exist in the database
    """
    with app.app_context():
        engine = db.engine
        inspector = inspect(engine)

        assert inspector.has_table(URLS.__tablename__)
        assert inspector.has_table(Utub.__tablename__)
        assert inspector.has_table(User.__tablename__)
        assert inspector.has_table(Utub_Urls.__tablename__)
        assert inspector.has_table(Utub_Users.__tablename__)
        assert inspector.has_table(Url_Tags.__tablename__)
        assert inspector.has_table("sessions")
