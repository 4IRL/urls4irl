from __future__ import annotations

from enum import IntEnum
import json

import pytest
from flask import Blueprint, Flask
from pydantic import BaseModel

from backend.api_common.parse_request import api_route
from backend.cli.openapi import register_openapi_cli
from backend.urls.constants import URLErrorCodes
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utubs.constants import UTubErrorCodes

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
    assert schema_ref.startswith(
        "#/components/schemas/ErrorResponse"
    ), f"Expected ErrorResponse or typed variant, got: {schema_ref}"


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
    assert spot_check_operation["x-error-codes"]["URLErrorCodes"] == {
        "$ref": "#/components/schemas/URLErrorCodes"
    }


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

    assert contact_post["x-error-codes"] == {
        "ContactErrorCodes": {"$ref": "#/components/schemas/ContactErrorCodes"}
    }


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


def test_success_responses_include_envelope_fields(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect a representative success response (POST /utubs -> 200)
    THEN the response schema uses allOf composition with SuccessEnvelope and the data schema
    """
    spec = _generate_spec(runner, tmp_path)
    post_utubs_200 = spec["paths"]["/utubs"]["post"]["responses"]["200"]
    response_schema = post_utubs_200["content"]["application/json"]["schema"]

    # Should use allOf composition
    assert (
        "allOf" in response_schema
    ), "Expected allOf composition for success response, got: " + json.dumps(
        response_schema
    )

    all_of_entries = response_schema["allOf"]

    # One entry should be the SuccessEnvelope ref
    envelope_ref = {"$ref": "#/components/schemas/SuccessEnvelope"}
    assert (
        envelope_ref in all_of_entries
    ), f"SuccessEnvelope ref not found in allOf entries: {all_of_entries}"

    # Another entry should be the data schema ref (UtubCreatedResponseSchema)
    data_ref = {"$ref": "#/components/schemas/UtubCreatedResponseSchema"}
    assert (
        data_ref in all_of_entries
    ), f"UtubCreatedResponseSchema ref not found in allOf entries: {all_of_entries}"


def test_success_envelope_schema_exists_in_components(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect the components/schemas
    THEN SuccessEnvelope exists with the correct structure
    """
    spec = _generate_spec(runner, tmp_path)
    schemas = spec["components"]["schemas"]

    assert (
        "SuccessEnvelope" in schemas
    ), "SuccessEnvelope not found in components/schemas"

    envelope = schemas["SuccessEnvelope"]

    # Has properties.status with type string and enum constraint
    assert "properties" in envelope
    assert "status" in envelope["properties"]
    status_prop = envelope["properties"]["status"]
    assert status_prop["type"] == "string"
    assert status_prop["enum"] == [
        STD_JSON.SUCCESS,
        STD_JSON.FAILURE,
        STD_JSON.NO_CHANGE,
    ]

    # Has properties.message with type string
    assert "message" in envelope["properties"]
    assert envelope["properties"]["message"]["type"] == "string"

    # status is required
    assert "required" in envelope
    assert "status" in envelope["required"]

    # message is NOT required
    assert "message" not in envelope["required"]


def test_schemas_with_existing_status_not_double_wrapped(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect a StatusMessageResponseSchema subclass (RegisterResponseSchema at 201)
         and an ErrorResponse at 400
    THEN they use a direct $ref, NOT allOf (no double-wrapping)
    """
    spec = _generate_spec(runner, tmp_path)

    # RegisterResponseSchema at 201 on POST /register
    register_responses = spec["paths"]["/register"]["post"]["responses"]
    assert (
        "201" in register_responses
    ), "POST /register missing 201 response — key guard failed"
    register_201_schema = register_responses["201"]["content"]["application/json"][
        "schema"
    ]
    assert "$ref" in register_201_schema, (
        "Expected direct $ref for RegisterResponseSchema (has status already), "
        f"got: {json.dumps(register_201_schema)}"
    )
    assert (
        "allOf" not in register_201_schema
    ), "RegisterResponseSchema should not be wrapped with allOf"

    # ErrorResponse at 400 on POST /register
    register_400_schema = register_responses["400"]["content"]["application/json"][
        "schema"
    ]
    assert (
        "$ref" in register_400_schema
    ), f"Expected direct $ref for ErrorResponse, got: {json.dumps(register_400_schema)}"
    assert (
        "allOf" not in register_400_schema
    ), "ErrorResponse should not be wrapped with allOf"


def test_error_responses_not_wrapped_with_envelope(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect all responses with status codes >= 400
    THEN none of them use allOf wrapping (no SuccessEnvelope on error responses)
    """
    spec = _generate_spec(runner, tmp_path)

    for path, path_item in spec["paths"].items():
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue
            responses = operation.get("responses", {})
            for code, response_obj in responses.items():
                if not code.isdigit() or int(code) < 400:
                    continue
                if "content" not in response_obj:
                    continue
                response_schema_dict = response_obj["content"]["application/json"][
                    "schema"
                ]
                assert "allOf" not in response_schema_dict, (
                    f"{method.upper()} {path} {code}: error response should not use "
                    f"allOf wrapping, got: {json.dumps(response_schema_dict)}"
                )


def test_all_success_responses_have_envelope_or_own_status(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we iterate all paths and operations
    THEN every success response (status < 400) either uses allOf with SuccessEnvelope
         or directly references a schema that has its own 'status' property
    """
    spec = _generate_spec(runner, tmp_path)
    envelope_ref = {"$ref": "#/components/schemas/SuccessEnvelope"}

    for path, path_item in spec["paths"].items():
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue
            responses = operation.get("responses", {})
            for code, response_obj in responses.items():
                if not code.isdigit() or int(code) >= 400:
                    continue
                if "content" not in response_obj:
                    continue

                schema_obj = response_obj["content"]["application/json"]["schema"]

                # Branch 1: allOf with SuccessEnvelope
                has_envelope_allof = "allOf" in schema_obj and any(
                    entry == envelope_ref for entry in schema_obj["allOf"]
                )

                # Branch 2: direct $ref to a component that has its own 'status'
                has_own_status = False
                if "$ref" in schema_obj:
                    component_name = schema_obj["$ref"].split("/")[-1]
                    assert component_name in spec["components"]["schemas"], (
                        f"{method.upper()} {path} {code}: $ref component "
                        f"'{component_name}' not in components/schemas"
                    )
                    component = spec["components"]["schemas"][component_name]
                    has_own_status = "status" in component.get("properties", {})

                assert has_envelope_allof or has_own_status, (
                    f"{method.upper()} {path} {code}: success response has neither "
                    f"allOf with SuccessEnvelope nor a schema with its own 'status' "
                    f"property. Schema: {json.dumps(schema_obj)}"
                )


def test_success_envelope_has_correct_status_description(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect the SuccessEnvelope schema's status property description
    THEN it documents all three possible values: Success, Failure, and No change
    """
    spec = _generate_spec(runner, tmp_path)
    envelope = spec["components"]["schemas"]["SuccessEnvelope"]
    status_description = envelope["properties"]["status"]["description"]

    assert "Success" in status_description, (
        f"SuccessEnvelope.status.description should mention 'Success', "
        f"got: {status_description}"
    )
    assert "Failure" in status_description, (
        f"SuccessEnvelope.status.description should mention 'Failure', "
        f"got: {status_description}"
    )
    assert "No change" in status_description, (
        f"SuccessEnvelope.status.description should mention 'No change', "
        f"got: {status_description}"
    )


def test_empty_schema_uses_direct_envelope_ref(tmp_path):
    """
    GIVEN a Flask app with an @api_route whose response schema has no properties
    WHEN the OpenAPI spec is generated
    THEN the success response uses a direct $ref to SuccessEnvelope (not allOf)
    """

    class EmptyResponseSchema(BaseModel):
        pass

    bp = Blueprint("empty_bp", __name__)

    @bp.route("/empty-response", methods=["POST"])
    @api_route(
        tags=["test"],
        response_schema=EmptyResponseSchema,
    )
    def empty_response_route() -> dict:
        return {}

    minimal_app = Flask(__name__)
    minimal_app.register_blueprint(bp)
    register_openapi_cli(minimal_app)

    cli_runner = minimal_app.test_cli_runner()
    output_path = tmp_path / "empty-schema-spec.json"

    result = cli_runner.invoke(
        args=["openapi", "generate", "--output", str(output_path)]
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"

    spec = json.loads(output_path.read_text())
    response_schema = spec["paths"]["/empty-response"]["post"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]

    # Should be a direct $ref to SuccessEnvelope, not allOf
    assert (
        "$ref" in response_schema
    ), f"Expected direct $ref for empty schema, got: {json.dumps(response_schema)}"
    assert response_schema["$ref"] == "#/components/schemas/SuccessEnvelope"
    assert "allOf" not in response_schema


def test_url_created_item_schema_is_distinct_component(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect components/schemas
    THEN UrlCreatedItemSchema appears as a distinct key, separate from UtubUrlDeleteSchema
    """
    spec = _generate_spec(runner, tmp_path)
    schemas = spec["components"]["schemas"]

    assert (
        "UrlCreatedItemSchema" in schemas
    ), "UrlCreatedItemSchema not found as a distinct component in schemas"
    assert "UtubUrlDeleteSchema" in schemas, "UtubUrlDeleteSchema not found in schemas"
    # They should be separate entries (not aliases)
    assert "UrlCreatedItemSchema" != "UtubUrlDeleteSchema"


def test_error_response_status_required_in_spec(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect the ErrorResponse component schema
    THEN "status" appears in the required list, matching runtime behavior
        where status is always present
    """
    spec = _generate_spec(runner, tmp_path)
    error_schema = spec["components"]["schemas"]["ErrorResponse"]
    assert "required" in error_schema, "ErrorResponse schema has no 'required' list"
    assert (
        "status" in error_schema["required"]
    ), "Expected 'status' in required fields but got: " + str(error_schema["required"])


def test_error_code_enums_in_components_schemas(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect components/schemas
    THEN at least one IntEnum (e.g., URLErrorCodes) appears with type: integer
         and an enum list matching the Python enum member values
    """
    spec = _generate_spec(runner, tmp_path)
    schemas = spec["components"]["schemas"]

    assert "URLErrorCodes" in schemas, "URLErrorCodes not found in components/schemas"
    url_error_schema = schemas["URLErrorCodes"]
    assert url_error_schema["type"] == "integer"
    expected_values = [member.value for member in URLErrorCodes]
    assert url_error_schema["enum"] == expected_values


def test_error_code_enum_has_varnames(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect the URLErrorCodes component schema
    THEN x-enum-varnames contains the expected member names for TS codegen
    """
    spec = _generate_spec(runner, tmp_path)
    schemas = spec["components"]["schemas"]

    assert "URLErrorCodes" in schemas, "URLErrorCodes not found in components/schemas"
    url_error_schema = schemas["URLErrorCodes"]
    expected_varnames = [member.name for member in URLErrorCodes]
    assert url_error_schema["x-enum-varnames"] == expected_varnames


def test_x_error_codes_uses_ref(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect an operation with x-error-codes (e.g., one using URLErrorCodes)
    THEN the extension contains a $ref pointer instead of an inline dict of values
    """
    spec = _generate_spec(runner, tmp_path)

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
    url_error_ref = spot_check_operation["x-error-codes"]["URLErrorCodes"]
    assert (
        "$ref" in url_error_ref
    ), f"Expected $ref pointer in x-error-codes, got: {url_error_ref}"
    assert url_error_ref["$ref"] == "#/components/schemas/URLErrorCodes"


def test_error_response_descriptions_are_http_phrases(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect all responses with status codes >= 400
    THEN none have "ErrorResponse" as the description — they should have
         HTTP phrases like "Bad request", "Not found", etc.
    """
    spec = _generate_spec(runner, tmp_path)

    for path, path_item in spec["paths"].items():
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue
            responses = operation.get("responses", {})
            for code, response_obj in responses.items():
                if not code.isdigit() or int(code) < 400:
                    continue
                description = response_obj.get("description", "")
                assert description != "ErrorResponse", (
                    f"{method.upper()} {path} {code}: error response description "
                    f"should be an HTTP phrase, not 'ErrorResponse'"
                )


def test_success_response_descriptions_are_human_readable(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect all 200/201 success responses
    THEN (1) none end with "Schema" or "ResponseSchema" (negative check), and
         (2) each description either contains a space or matches a known
         single-word allow-list (positive check to prevent stripped class names)
    """
    spec = _generate_spec(runner, tmp_path)

    # Single-word descriptions that are genuinely human-readable
    single_word_allowlist = {"Health", "Register", "Contact"}

    for path, path_item in spec["paths"].items():
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue
            responses = operation.get("responses", {})
            for code, response_obj in responses.items():
                if not code.isdigit() or int(code) >= 400:
                    continue
                description = response_obj.get("description", "")

                # Negative: must not end with Schema or ResponseSchema
                assert not description.endswith("Schema"), (
                    f"{method.upper()} {path} {code}: description "
                    f"'{description}' ends with 'Schema'"
                )
                assert not description.endswith("ResponseSchema"), (
                    f"{method.upper()} {path} {code}: description "
                    f"'{description}' ends with 'ResponseSchema'"
                )

                # Positive: must contain a space or be in the allow-list
                assert " " in description or description in single_word_allowlist, (
                    f"{method.upper()} {path} {code}: description "
                    f"'{description}' is a single word not in the allow-list "
                    f"{single_word_allowlist}"
                )


def test_error_response_status_is_literal_failure(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect the ErrorResponse component schema's status property
    THEN it has a const or enum constraint narrowing it to "Failure",
        matching the Literal["Failure"] annotation on ErrorResponse.status
    """
    spec = _generate_spec(runner, tmp_path)
    error_schema = spec["components"]["schemas"]["ErrorResponse"]
    status_prop = error_schema["properties"]["status"]

    has_const = status_prop.get("const") == "Failure"
    has_enum = status_prop.get("enum") == ["Failure"]
    assert has_const or has_enum, (
        f"Expected status to have const: 'Failure' or enum: ['Failure'], "
        f"got: {status_prop}"
    )


def test_register_response_status_has_literal_enum(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect POST /register's 201 response schema (RegisterResponseSchema)
    THEN the status property has enum: ["Success", "Failure", "No change"],
        matching the Literal annotation inherited from StatusMessageResponseSchema
    """
    spec = _generate_spec(runner, tmp_path)

    register_responses = spec["paths"]["/register"]["post"]["responses"]
    assert "201" in register_responses, "POST /register missing 201 response"

    register_201_schema = register_responses["201"]["content"]["application/json"][
        "schema"
    ]
    assert "$ref" in register_201_schema, (
        f"Expected direct $ref for RegisterResponseSchema, "
        f"got: {json.dumps(register_201_schema)}"
    )

    component_name = register_201_schema["$ref"].split("/")[-1]
    component = spec["components"]["schemas"][component_name]
    status_prop = component["properties"]["status"]

    assert status_prop.get("enum") == [
        "Success",
        "Failure",
        "No change",
    ], f"Expected status enum ['Success', 'Failure', 'No change'], got: {status_prop}"


def test_utub_detail_current_user_is_integer(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect the UtubDetailSchema component schema's currentUser property
    THEN its type is "integer", confirming the schema emits int (not string)
    """
    spec = _generate_spec(runner, tmp_path)
    utub_detail = spec["components"]["schemas"]["UtubDetailSchema"]
    current_user_prop = utub_detail["properties"]["currentUser"]
    assert (
        current_user_prop["type"] == "integer"
    ), f"Expected currentUser type 'integer', got: {current_user_prop}"


def test_typed_error_responses_narrow_error_code(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect a 400 response on an operation with x-error-codes
         (e.g., POST /utubs which uses UTubErrorCodes)
    THEN the response references ErrorResponse_UTubErrorCodes, and the
         component schema uses allOf with base ErrorResponse and narrows
         errorCode to $ref: UTubErrorCodes
    """
    spec = _generate_spec(runner, tmp_path)

    post_utubs = spec["paths"]["/utubs"]["post"]
    resp_400 = post_utubs["responses"]["400"]
    schema_ref = resp_400["content"]["application/json"]["schema"]["$ref"]

    expected_typed_name = f"ErrorResponse_{UTubErrorCodes.__name__}"
    assert (
        schema_ref == f"#/components/schemas/{expected_typed_name}"
    ), f"Expected typed error ref for POST /utubs 400, got: {schema_ref}"

    typed_component = spec["components"]["schemas"][expected_typed_name]
    assert "allOf" in typed_component, (
        f"Expected allOf composition in {expected_typed_name}, "
        f"got: {json.dumps(typed_component)}"
    )

    all_of = typed_component["allOf"]
    assert all_of[0] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }, f"First allOf entry should reference ErrorResponse, got: {all_of[0]}"

    narrowed_props = all_of[1]
    assert narrowed_props["type"] == "object"
    error_code_ref = narrowed_props["properties"]["errorCode"]["$ref"]
    assert (
        error_code_ref == f"#/components/schemas/{UTubErrorCodes.__name__}"
    ), f"Expected errorCode $ref to UTubErrorCodes, got: {error_code_ref}"


def test_utub_detail_created_at_has_datetime_format(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect the UtubDetailSchema component
    THEN the createdAt property has type "string" and format "date-time"
    """
    spec = _generate_spec(runner, tmp_path)

    utub_detail = spec["components"]["schemas"]["UtubDetailSchema"]
    created_at_prop = utub_detail["properties"]["createdAt"]
    assert (
        created_at_prop["type"] == "string"
    ), f"Expected createdAt type 'string', got: {created_at_prop.get('type')}"
    assert (
        created_at_prop["format"] == "date-time"
    ), f"Expected createdAt format 'date-time', got: {created_at_prop.get('format')}"


def test_error_responses_without_enum_still_use_plain_error_response(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect error responses on operations without error_code_enum
         (e.g., DELETE /utubs/{utub_id} which has 403 and 404 but no error_code)
    THEN those responses reference the plain ErrorResponse schema
    """
    spec = _generate_spec(runner, tmp_path)

    delete_op = spec["paths"]["/utubs/{utub_id}"]["delete"]
    for error_code in ("403", "404"):
        resp = delete_op["responses"].get(error_code)
        assert (
            resp is not None
        ), f"DELETE /utubs/{{utub_id}} missing {error_code} response"
        schema_ref = resp["content"]["application/json"]["schema"]["$ref"]
        assert schema_ref == "#/components/schemas/ErrorResponse", (
            f"Expected plain ErrorResponse for DELETE /utubs/{{utub_id}} "
            f"{error_code}, got: {schema_ref}"
        )


def test_typed_error_response_scoped_to_400_and_409_only(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect PATCH /utubs/{utub_id}/urls/{utub_url_id} which has
         error_code_enum=URLErrorCodes and status codes 400, 403, 404, 409
    THEN 400 and 409 reference the typed ErrorResponse_URLErrorCodes,
         while 403 and 404 reference the plain ErrorResponse
    """
    spec = _generate_spec(runner, tmp_path)

    patch_op = spec["paths"]["/utubs/{utub_id}/urls/{utub_url_id}"]["patch"]
    expected_typed_name = f"ErrorResponse_{URLErrorCodes.__name__}"

    # 400 and 409 should use typed error response
    for typed_code in ("400", "409"):
        resp = patch_op["responses"].get(typed_code)
        assert resp is not None, f"PATCH update_url missing {typed_code} response"
        resp_schema = resp["content"]["application/json"]["schema"]
        schema_ref = resp_schema["$ref"]
        assert (
            schema_ref == f"#/components/schemas/{expected_typed_name}"
        ), f"Expected typed error ref for {typed_code}, got: {schema_ref}"

    # 403 and 404 should use plain ErrorResponse
    for plain_code in ("403", "404"):
        resp = patch_op["responses"].get(plain_code)
        assert resp is not None, f"PATCH update_url missing {plain_code} response"
        resp_schema = resp["content"]["application/json"]["schema"]
        schema_ref = resp_schema["$ref"]
        assert (
            schema_ref == "#/components/schemas/ErrorResponse"
        ), f"Expected plain ErrorResponse for {plain_code}, got: {schema_ref}"


def test_component_schemas_have_no_title_fields(runner, tmp_path):
    """
    GIVEN a generated OpenAPI spec
    WHEN we inspect all component schemas
    THEN no schema or property has a "title" key, confirming
        _strip_auto_titles removed Pydantic's auto-generated titles
    """
    spec = _generate_spec(runner, tmp_path)
    schemas = spec["components"]["schemas"]

    violations = []
    for schema_name, schema_obj in schemas.items():
        if "title" in schema_obj:
            violations.append(f"{schema_name} has root-level 'title'")
        for prop_name, prop_obj in schema_obj.get("properties", {}).items():
            if isinstance(prop_obj, dict) and "title" in prop_obj:
                violations.append(f"{schema_name}.{prop_name} has 'title'")

    assert (
        not violations
    ), f"Found {len(violations)} schema(s) with 'title' keys:\n" + "\n".join(violations)
