import pytest
from urls4irl import db
from flask_sqlalchemy import inspect

def test_db_created_correctly(app):
    """
    GIVEN a valid database with all given tables
    WHEN these tests are running
    THEN ensure all tables exist in the database
    """

    with app.app_context():

        table_names = set(inspect(db.engine).get_table_names())

        assert 'Urls' in table_names
        assert 'sessions' in table_names
        assert 'UrlTags' in table_names
        assert 'UtubUsers' in table_names
        assert 'Utub' in table_names
        assert 'Tags' in table_names
        assert 'User' in table_names
        assert 'UtubUrls' in table_names
