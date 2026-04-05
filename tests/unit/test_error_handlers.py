import pytest
from flask import Flask, abort

import backend
from backend.api_common.error_handler import handle_404_response
from backend.utils.strings.json_strs import FAILURE_GENERAL
from backend.utils.strings.url_validation_strs import URL_VALIDATION

pytestmark = pytest.mark.unit

XHR_HEADER = {URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST}


@pytest.fixture()
def error_handler_app():
    """Minimal Flask app with the 404 handler and a route that aborts with 404."""
    app = Flask(backend.__name__)
    app.config["TESTING"] = True
    app.register_error_handler(404, handle_404_response)

    @app.route("/trigger-404")
    def trigger_404():
        abort(404)

    return app


class TestHandle404ResponseXHR:
    """XHR requests that trigger a 404 should receive a JSON error response."""

    def test_xhr_404_returns_json_body(self, error_handler_app: Flask):
        with error_handler_app.test_client() as client:
            response = client.get("/trigger-404", headers=XHR_HEADER)

        assert response.status_code == 404
        data = response.get_json()
        assert data["status"] == "Failure"
        assert data["message"] == FAILURE_GENERAL.NOT_FOUND

    def test_xhr_404_content_type_is_json(self, error_handler_app: Flask):
        with error_handler_app.test_client() as client:
            response = client.get("/trigger-404", headers=XHR_HEADER)

        assert response.content_type == "application/json"


class TestHandle404ResponseNonXHR:
    """Non-XHR requests that trigger a 404 should receive the default HTML response."""

    def test_non_xhr_404_returns_html(self, error_handler_app: Flask):
        with error_handler_app.test_client() as client:
            response = client.get("/trigger-404")

        assert response.status_code == 404
        assert "text/html" in response.content_type
