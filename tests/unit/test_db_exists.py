import pytest
from sqlalchemy import inspect

from backend import db
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.models.contact_form_entries import ContactFormEntries
from backend.models.event_registry import Event_Registry
from backend.models.utub_tags import Utub_Tags
from backend.models.urls import Urls
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.users import Users
from backend.models.utubs import Utubs
from backend.models.utub_members import Utub_Members
from backend.models.utub_urls import Utub_Urls

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
        assert inspector.has_table(ContactFormEntries.__tablename__)


def test_metrics_tables_exist(app):
    """
    GIVEN a valid database with all given tables
    WHEN these tests are running
    THEN ensure the metrics tables exist in the database
    """
    with app.app_context():
        engine = db.engine
        inspector = inspect(engine)

        assert inspector.has_table(Event_Registry.__tablename__)
        assert inspector.has_table(Anonymous_Metrics.__tablename__)
