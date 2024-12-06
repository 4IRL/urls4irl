import pytest
from sqlalchemy import inspect

from src import db
from src.models.utub_tags import Utub_Tags
from src.models.urls import Urls
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.users import Users
from src.models.utubs import Utubs
from src.models.utub_members import Utub_Members
from src.models.utub_urls import Utub_Urls

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

        assert inspector.has_table(Utub_Tags.__tablename__)
        assert inspector.has_table(Urls.__tablename__)
        assert inspector.has_table(Users.__tablename__)
        assert inspector.has_table(Utubs.__tablename__)
        assert inspector.has_table(Utub_Members.__tablename__)
        assert inspector.has_table(Utub_Urls.__tablename__)
        assert inspector.has_table(Utub_Url_Tags.__tablename__)
