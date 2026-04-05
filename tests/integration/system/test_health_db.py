from flask import Flask
import pytest

from backend import db
from backend.schemas.system import HealthDbResponseSchema
from backend.utils.db_table_names import TABLE_NAMES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from tests.integration.utils import assert_response_conforms_to_schema

pytestmark = pytest.mark.cli


def test_health_db_check_passes_when_all_tables_exist(app: Flask):
    """
    GIVEN a database with all model tables created
    WHEN a GET request is made to /health?db=true
    THEN ensure a 200 response with a verification success message
    """
    with app.test_client() as client:
        response = client.get("/health?db=true")

    assert response.status_code == 200
    response_json = response.json

    assert_response_conforms_to_schema(
        response_json, HealthDbResponseSchema, {STD_JSON.STATUS, STD_JSON.MESSAGE}
    )
    assert response_json[STD_JSON.MESSAGE] == "All database tables verified"


def test_health_db_check_fails_when_tables_are_missing(runner):
    """
    GIVEN a database where application tables have been dropped
    WHEN a GET request is made to /health?db=true
    THEN ensure a 503 response listing the missing tables
    """
    app, cli_runner = runner

    with app.app_context():
        db.drop_all()

    try:
        with app.test_client() as client:
            response = client.get("/health?db=true")

        assert response.status_code == 503
        response_json = response.json

        assert_response_conforms_to_schema(
            response_json,
            HealthDbResponseSchema,
            {STD_JSON.STATUS, STD_JSON.MESSAGE},
        )
        assert TABLE_NAMES.USERS in response_json[STD_JSON.MESSAGE]
        assert TABLE_NAMES.UTUBS in response_json[STD_JSON.MESSAGE]
    finally:
        with app.app_context():
            db.create_all()


def test_health_without_db_param_does_not_check_database(app: Flask):
    """
    GIVEN a running Flask application
    WHEN a GET request is made to /health (without ?db=true)
    THEN ensure a 200 response with only the status field (no message),
        confirming no database check was performed
    """
    with app.test_client() as client:
        response = client.get("/health")

    assert response.status_code == 200
    response_json = response.json

    assert STD_JSON.STATUS in response_json
    assert STD_JSON.MESSAGE not in response_json


def test_health_db_param_is_case_insensitive(app: Flask):
    """
    GIVEN a running Flask application with all tables present
    WHEN a GET request is made to /health?db=True (capitalized)
    THEN ensure the database check still runs and returns 200
    """
    with app.test_client() as client:
        response = client.get("/health?db=True")

    assert response.status_code == 200
    assert STD_JSON.MESSAGE in response.json


def test_health_db_param_ignored_when_not_true(app: Flask):
    """
    GIVEN a running Flask application
    WHEN a GET request is made to /health?db=false
    THEN ensure no database check is performed (standard liveness response)
    """
    with app.test_client() as client:
        response = client.get("/health?db=false")

    assert response.status_code == 200
    response_json = response.json

    assert STD_JSON.STATUS in response_json
    assert STD_JSON.MESSAGE not in response_json
