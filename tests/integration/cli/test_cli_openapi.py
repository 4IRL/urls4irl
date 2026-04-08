from __future__ import annotations

import json
from enum import IntEnum

import pytest
from flask import Blueprint, Flask

from backend.api_common.parse_request import api_route
from backend.cli.openapi import register_openapi_cli
from backend.contact.constants import ContactErrorCodes
from backend.urls.constants import URLErrorCodes

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


def _generate_spec(runner, tmp_path):
    """Helper: invoke the CLI and return the parsed spec dict."""
    app, cli_runner = runner
    output_path = tmp_path / "openapi.json"
    result = cli_runner.invoke(
        args=["openapi", "generate", "--output", str(output_path)]
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    return json.loads(output_path.read_text())


def test_utubs_path_has_get_and_post_methods(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect the /utubs path item
    THEN both 'get' and 'post' method keys exist (multi-method merge)
    """
    spec = _generate_spec(runner, tmp_path)
    utubs_path = spec["paths"].get("/utubs")
    assert utubs_path is not None, "/utubs path not found"
    assert "get" in utubs_path, "/utubs missing GET"
    assert "post" in utubs_path, "/utubs missing POST"


def test_post_utubs_has_request_body_referencing_create_utub_request(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect POST /utubs
    THEN it has a requestBody referencing CreateUTubRequest
    """
    spec = _generate_spec(runner, tmp_path)
    post_op = spec["paths"]["/utubs"]["post"]
    assert "requestBody" in post_op
    schema_ref = post_op["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert schema_ref == "#/components/schemas/CreateUTubRequest"


def test_post_utubs_has_utubs_tag(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect POST /utubs
    THEN it has tags: ["utubs"]
    """
    spec = _generate_spec(runner, tmp_path)
    post_op = spec["paths"]["/utubs"]["post"]
    assert post_op["tags"] == ["utubs"]


def test_post_utubs_has_session_auth_and_csrf_security(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect POST /utubs (email_validation_required + POST)
    THEN security is [{"sessionAuth": [], "csrfToken": []}]
    """
    spec = _generate_spec(runner, tmp_path)
    post_op = spec["paths"]["/utubs"]["post"]
    assert post_op["security"] == [{"sessionAuth": [], "csrfToken": []}]


def test_get_health_has_empty_security_no_csrf(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect GET /health
    THEN security is [] (no auth, no CSRF for GET)
    """
    spec = _generate_spec(runner, tmp_path)
    health_op = spec["paths"]["/health"]["get"]
    assert health_op["security"] == []


def test_delete_utub_has_integer_path_param(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect DELETE /utubs/{utub_id}
    THEN it has a path parameter utub_id with type: integer
    """
    spec = _generate_spec(runner, tmp_path)
    delete_op = spec["paths"]["/utubs/{utub_id}"]["delete"]
    assert "parameters" in delete_op
    utub_id_param = next(
        (p for p in delete_op["parameters"] if p["name"] == "utub_id"), None
    )
    assert utub_id_param is not None, "utub_id param not found"
    assert utub_id_param["schema"]["type"] == "integer"
    assert utub_id_param["in"] == "path"
    assert utub_id_param["required"] is True


def test_post_utub_urls_has_path_param_and_request_body(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect POST /utubs/{utub_id}/urls
    THEN it has both utub_id path param and requestBody
    """
    spec = _generate_spec(runner, tmp_path)
    post_op = spec["paths"]["/utubs/{utub_id}/urls"]["post"]

    # Path param
    assert "parameters" in post_op
    utub_id_param = next(
        (p for p in post_op["parameters"] if p["name"] == "utub_id"), None
    )
    assert utub_id_param is not None, "utub_id param not found"

    # Request body
    assert "requestBody" in post_op


def test_error_responses_reference_error_response_schema(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect routes with 400/403/404 responses
    THEN those responses reference ErrorResponse schema
    """
    spec = _generate_spec(runner, tmp_path)
    # POST /utubs has 400: ErrorResponse
    post_op = spec["paths"]["/utubs"]["post"]
    resp_400 = post_op["responses"].get("400")
    assert resp_400 is not None, "POST /utubs missing 400 response"
    schema_ref = resp_400["content"]["application/json"]["schema"]["$ref"]
    assert schema_ref == "#/components/schemas/ErrorResponse"


def test_output_flag_writes_to_specified_path(runner, tmp_path):
    """
    GIVEN a fully configured Flask app
    WHEN the developer runs the generate command with --output pointing to a custom path
    THEN the spec is written to that exact path
    """
    app, cli_runner = runner
    output_path = tmp_path / "custom_dir" / "my_spec.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = cli_runner.invoke(
        args=["openapi", "generate", "--output", str(output_path)]
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert output_path.exists()

    spec = json.loads(output_path.read_text())
    assert spec["openapi"] == "3.1.0"


def test_output_to_nonexistent_directory_fails(runner, tmp_path):
    """
    GIVEN a fully configured Flask app
    WHEN --output points to a non-existent directory
    THEN exit_code != 0 and output contains a descriptive error
    """
    app, cli_runner = runner
    bad_path = tmp_path / "does_not_exist" / "spec.json"

    result = cli_runner.invoke(args=["openapi", "generate", "--output", str(bad_path)])
    assert result.exit_code != 0
    assert "does not exist" in result.output.lower() or "error" in result.output.lower()


def test_non_api_route_endpoints_excluded(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we look at the paths
    THEN static and template-rendered routes (e.g., /home) are excluded
    """
    spec = _generate_spec(runner, tmp_path)
    paths = spec["paths"]
    # Static endpoint should not be present
    for path in paths:
        assert "/static" not in path, f"Static path found: {path}"
    # /home is a template-rendered route, not an @api_route
    assert "/home" not in paths


def test_post_register_has_csrf_only_security(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect POST /register (decorated with @no_authenticated_users_allowed)
    THEN security is [{"csrfToken": []}] — CSRF required globally, no session auth
    """
    spec = _generate_spec(runner, tmp_path)
    register_op = spec["paths"]["/register"]["post"]
    assert register_op["security"] == [{"csrfToken": []}]


def test_get_utubs_has_session_auth_security(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect GET /utubs (decorated with @email_validation_required)
    THEN security is [{"sessionAuth": []}] — session auth only, no CSRF for GET
    """
    spec = _generate_spec(runner, tmp_path)
    utubs_path = spec["paths"].get("/utubs")
    assert utubs_path is not None, "/utubs path not found"
    get_op = utubs_path["get"]
    assert get_op["security"] == [{"sessionAuth": []}]


def test_default_output_path_writes_openapi_json_to_cwd(runner, tmp_path, monkeypatch):
    """
    GIVEN a fully configured Flask app
    WHEN the developer runs `flask openapi generate` without --output
    THEN openapi.json is written to the current working directory
    """
    monkeypatch.chdir(tmp_path)
    app, cli_runner = runner

    result = cli_runner.invoke(args=["openapi", "generate"])
    assert result.exit_code == 0, f"CLI failed: {result.output}"

    default_output = tmp_path / "openapi.json"
    assert default_output.exists(), "openapi.json not written to CWD"

    spec = json.loads(default_output.read_text())
    assert spec["openapi"] == "3.1.0"


def test_strict_flag_succeeds_when_all_routes_have_schemas(runner, tmp_path):
    """
    GIVEN a fully configured Flask app where all @api_route endpoints have response schemas
    WHEN the developer runs `flask openapi generate --strict`
    THEN exit code is 0 and the spec is written successfully
    """
    app, cli_runner = runner
    output_path = tmp_path / "strict-openapi.json"

    result = cli_runner.invoke(
        args=["openapi", "generate", "--strict", "--output", str(output_path)]
    )
    assert result.exit_code == 0, f"--strict failed unexpectedly: {result.output}"
    assert output_path.exists()

    spec = json.loads(output_path.read_text())
    assert spec["openapi"] == "3.1.0"


def test_strict_flag_fails_when_route_lacks_response_schema(tmp_path):
    """
    GIVEN a Flask app with an @api_route that has no response schema
    WHEN the developer runs `flask openapi generate --strict`
    THEN exit code is non-zero and the error mentions the missing response schema
    """
    bp = Blueprint("schemaless_bp", __name__)

    @bp.route("/schemaless", methods=["POST"])
    @api_route(tags=["test"])
    def schemaless_route() -> dict:
        return {}

    minimal_app = Flask(__name__)
    minimal_app.register_blueprint(bp)
    register_openapi_cli(minimal_app)

    cli_runner = minimal_app.test_cli_runner()
    output_path = tmp_path / "strict-fail.json"

    result = cli_runner.invoke(
        args=["openapi", "generate", "--strict", "--output", str(output_path)]
    )
    assert result.exit_code != 0
    assert "no response schema" in result.output
    assert "schemaless" in result.output


def _collect_registered_error_code_enums(app: Flask) -> set[type]:
    """Discover all IntEnum classes stashed on @api_route-decorated view functions.

    Walks the app's url_map exactly like the spec generator does, returning
    the set of unique enum classes. This means adding a new error_code enum
    to any @api_route is automatically picked up by tests — no manual list.
    """
    enums: set[type] = set()
    for rule in app.url_map.iter_rules():
        view_fn = app.view_functions.get(rule.endpoint)
        if view_fn is None:
            continue
        enum_cls = getattr(view_fn, "_api_route_error_code_enum", None)
        if enum_cls is not None and issubclass(enum_cls, IntEnum):
            enums.add(enum_cls)
    return enums


def test_operations_with_error_codes_have_x_error_codes_extension(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we collect all operations containing x-error-codes
    THEN every error code enum registered on @api_route appears in the spec,
         and spot-checked enum values match {member.name: member.value}

    The set of expected enums is auto-discovered from the app's routes — no
    hardcoded list to maintain. Adding a new IntEnum error_code to any
    @api_route is automatically covered.
    """
    app, _ = runner
    spec = _generate_spec(runner, tmp_path)

    registered_enums = _collect_registered_error_code_enums(app)
    assert len(registered_enums) > 0, "No error code enums found on any route"

    # Collect all enum names found in x-error-codes across the spec
    found_enum_names: set[str] = set()
    for path, path_item in spec["paths"].items():
        for method, operation in path_item.items():
            if isinstance(operation, dict) and "x-error-codes" in operation:
                found_enum_names.update(operation["x-error-codes"].keys())

    # Every registered enum class must appear in the spec
    for enum_cls in registered_enums:
        assert (
            enum_cls.__name__ in found_enum_names
        ), f"{enum_cls.__name__} is registered on a route but missing from x-error-codes"

    # Spot-check: verify URLErrorCodes value format
    spot_check_operation = next(
        (
            op
            for path_item in spec["paths"].values()
            for op in path_item.values()
            if isinstance(op, dict) and "URLErrorCodes" in op.get("x-error-codes", {})
        ),
        None,
    )
    assert spot_check_operation is not None, "URLErrorCodes not found in any operation"
    expected_url_error_codes = {member.name: member.value for member in URLErrorCodes}
    assert (
        spot_check_operation["x-error-codes"]["URLErrorCodes"]
        == expected_url_error_codes
    )


def test_routes_without_error_code_lack_x_error_codes(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect routes that have no error_code kwarg (GET /health, DELETE /utubs/{utub_id})
    THEN those operations do NOT contain x-error-codes
    """
    spec = _generate_spec(runner, tmp_path)

    # GET /health should not have x-error-codes
    assert "/health" in spec["paths"]
    assert "get" in spec["paths"]["/health"]
    get_operation = spec["paths"]["/health"]["get"]
    assert "x-error-codes" not in get_operation

    # DELETE /utubs/{utub_id} should not have x-error-codes
    delete_operation = spec["paths"]["/utubs/{utub_id}"]["delete"]
    assert "x-error-codes" not in delete_operation


def test_post_contact_has_x_error_codes(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect POST /contact
    THEN x-error-codes is present and matches ContactErrorCodes exactly
    """
    spec = _generate_spec(runner, tmp_path)

    contact_post = spec["paths"]["/contact"]["post"]
    assert "x-error-codes" in contact_post

    expected = {
        "ContactErrorCodes": {member.name: member.value for member in ContactErrorCodes}
    }
    assert contact_post["x-error-codes"] == expected


def test_all_routes_with_request_schema_have_x_error_codes(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we iterate all operations
    THEN every operation with a requestBody also has x-error-codes

    This is an intentional project invariant: all routes that accept a request
    body must define their error codes using an IntEnum, not plain ints. The
    @api_route decorator enforces IntEnum-only error_code at decoration time
    (raising TypeError for plain ints), and this test serves as an additional
    integration-level check that the convention is maintained across the entire
    spec — every requestBody operation must produce x-error-codes.
    """
    spec = _generate_spec(runner, tmp_path)

    for path, path_item in spec["paths"].items():
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue
            if "requestBody" in operation:
                assert (
                    "x-error-codes" in operation
                ), f"{method.upper()} {path} has requestBody but no x-error-codes"
