from __future__ import annotations

import pytest
from flask import Flask

from backend.api_common.parse_request import api_route
from backend.cli.openapi import generate_openapi_spec

pytestmark = pytest.mark.unit


def test_duplicate_operation_id_raises_value_error():
    """
    GIVEN a Flask app with two blueprints each having a route with the same function name
    WHEN generate_openapi_spec is called
    THEN it raises ValueError about duplicate operationIds
    """
    from flask import Blueprint

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
