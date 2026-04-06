from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.cli


def test_generate_openapi_spec_to_file(runner, tmp_path):
    """
    GIVEN a fully configured Flask app with all blueprints registered
    WHEN the developer runs `flask openapi generate --output <tmp_path>/openapi-test.json`
    THEN verify the JSON file is written with a valid OpenAPI 3.1 spec
    """
    app, cli_runner = runner
    output_path = tmp_path / "openapi-test.json"

    result = cli_runner.invoke(
        args=["openapi", "generate", "--output", str(output_path)]
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"

    spec = json.loads(output_path.read_text())

    # Top-level keys exist
    for key in ("openapi", "info", "paths", "components"):
        assert key in spec, f"Missing top-level key: {key}"

    # OpenAPI version
    assert spec["openapi"] == "3.1.0"

    # Info block
    assert spec["info"]["title"] == "urls4irl API"
    assert spec["info"]["version"] == "1.0.0"

    # At least 20 API routes
    assert len(spec["paths"]) >= 20, f"Only {len(spec['paths'])} paths found"

    # Each path item has at least one method key
    valid_methods = {"get", "post", "patch", "delete", "put"}
    for path, path_item in spec["paths"].items():
        method_keys = set(path_item.keys()) & valid_methods
        assert method_keys, f"Path {path} has no HTTP method keys"

        # Each operation has operationId, tags, responses
        for method in method_keys:
            operation = path_item[method]
            assert (
                "operationId" in operation
            ), f"{method.upper()} {path} missing operationId"
            assert "tags" in operation, f"{method.upper()} {path} missing tags"
            assert (
                "responses" in operation
            ), f"{method.upper()} {path} missing responses"

    # Components has schemas
    assert "schemas" in spec["components"]
    schemas = spec["components"]["schemas"]
    for expected_schema in (
        "CreateUTubRequest",
        "UtubCreatedResponseSchema",
        "ErrorResponse",
    ):
        assert expected_schema in schemas, f"Missing schema: {expected_schema}"

    # Security schemes
    assert "securitySchemes" in spec["components"]
    assert "sessionAuth" in spec["components"]["securitySchemes"]
