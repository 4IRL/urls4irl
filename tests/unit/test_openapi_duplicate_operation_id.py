from __future__ import annotations

import warnings

import click
import pytest
from flask import Blueprint, Flask

from backend.api_common.parse_request import api_route
from backend.cli.openapi import _endpoint_to_operation_id, generate_openapi_spec

pytestmark = pytest.mark.unit


def test_duplicate_operation_id_raises_value_error():
    """
    GIVEN a Flask app with two blueprints each having a route with the same function name
    WHEN generate_openapi_spec is called
    THEN it raises ValueError about duplicate operationIds
    """
    bp_one = Blueprint("alpha", __name__)
    bp_two = Blueprint("beta", __name__)

    @bp_one.route("/alpha/items", methods=["POST"])
    @api_route(tags=["test"])
    def create_item() -> dict:
        return {}

    @bp_two.route("/beta/items", methods=["POST"])
    @api_route(tags=["test"])
    def create_item() -> dict:  # noqa: F811
        return {}

    app = Flask(__name__)
    app.register_blueprint(bp_one)
    app.register_blueprint(bp_two)

    with app.app_context():
        with pytest.raises(ValueError, match="Duplicate operationId"):
            generate_openapi_spec(app)


def test_endpoint_to_operation_id_strips_blueprint_prefix():
    """
    GIVEN a dotted Flask endpoint like 'utubs.create_utub'
    WHEN _endpoint_to_operation_id is called
    THEN it strips the blueprint prefix and returns camelCase 'createUtub'
    """
    assert _endpoint_to_operation_id("utubs.create_utub") == "createUtub"


def test_endpoint_to_operation_id_converts_snake_case():
    """
    GIVEN a plain snake_case endpoint like 'get_items'
    WHEN _endpoint_to_operation_id is called
    THEN it returns camelCase 'getItems'
    """
    assert _endpoint_to_operation_id("get_items") == "getItems"


def test_no_response_schema_produces_success_fallback_and_warning():
    """
    GIVEN a Flask app with an @api_route that has no response schema
    WHEN generate_openapi_spec is called (strict=False, the default)
    THEN the 200 response description is 'Success' and a UserWarning is raised
    """
    bp = Blueprint("test_bp", __name__)

    @bp.route("/no-schema", methods=["POST"])
    @api_route(tags=["test"])
    def no_schema_route() -> dict:
        return {}

    app = Flask(__name__)
    app.register_blueprint(bp)

    with app.app_context():
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            spec = generate_openapi_spec(app)

    post_op = spec["paths"]["/no-schema"]["post"]
    assert post_op["responses"] == {"200": {"description": "Success"}}

    warning_messages = [str(warning.message) for warning in caught_warnings]
    assert any("no response schema" in msg for msg in warning_messages)


def test_no_response_schema_strict_raises_click_exception():
    """
    GIVEN a Flask app with an @api_route that has no response schema
    WHEN generate_openapi_spec is called with strict=True
    THEN a click.ClickException is raised mentioning the endpoint name
    """
    bp = Blueprint("strict_bp", __name__)

    @bp.route("/no-schema-strict", methods=["POST"])
    @api_route(tags=["test"])
    def no_schema_strict_route() -> dict:
        return {}

    app = Flask(__name__)
    app.register_blueprint(bp)

    with app.app_context():
        with pytest.raises(click.ClickException, match="no response schema"):
            generate_openapi_spec(app, strict=True)


def test_multi_method_endpoint_gets_method_suffix_on_operation_id():
    """
    GIVEN a Flask app with a single endpoint that handles both GET and POST
    WHEN generate_openapi_spec is called
    THEN the operationIds include method suffixes (e.g., 'listItems_get', 'listItems_post')
    """
    bp = Blueprint("multi", __name__)

    @bp.route("/items", methods=["GET", "POST"])
    @api_route(tags=["test"])
    def list_items() -> dict:
        return {}

    app = Flask(__name__)
    app.register_blueprint(bp)

    with app.app_context():
        spec = generate_openapi_spec(app)

    items_path = spec["paths"]["/items"]
    assert items_path["get"]["operationId"] == "listItems_get"
    assert items_path["post"]["operationId"] == "listItems_post"


def test_single_method_endpoint_has_no_method_suffix():
    """
    GIVEN a Flask app with an endpoint that handles only POST
    WHEN generate_openapi_spec is called
    THEN the operationId has no method suffix (e.g., 'createItem')
    """
    bp = Blueprint("single", __name__)

    @bp.route("/items", methods=["POST"])
    @api_route(tags=["test"])
    def create_item() -> dict:
        return {}

    app = Flask(__name__)
    app.register_blueprint(bp)

    with app.app_context():
        spec = generate_openapi_spec(app)

    post_op = spec["paths"]["/items"]["post"]
    assert post_op["operationId"] == "createItem"
