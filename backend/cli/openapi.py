from __future__ import annotations

from collections import defaultdict
from enum import IntEnum
import functools
import json
from pathlib import Path
import re
from typing import Any, Type
import warnings

import click
from flask import Flask, current_app
from flask.cli import AppGroup, with_appcontext
from pydantic import BaseModel

from backend.api_common.auth_decorators import SESSION_AUTH_DECORATORS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON

openapi_cli = AppGroup(
    "openapi",
    help="OpenAPI spec generation for U4I.",
)

# Methods that require CSRF protection (Flask-WTF global enforcement)
MUTATING_METHODS = frozenset({"POST", "PATCH", "DELETE", "PUT"})

# Flask path parameter pattern: <converter:name> or <name>
PATH_PARAM_PATTERN = re.compile(r"<(\w+:)?(\w+)>")

# Converter mapping: Flask converter → OpenAPI type
CONVERTER_TYPE_MAP = {
    "int": "integer",
    "float": "number",
    "string": "string",
}


HTTP_STATUS_DESCRIPTIONS: dict[int, str] = {
    200: "Success",
    201: "Created",
    400: "Bad request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not found",
    409: "Conflict",
    429: "Too many requests",
    503: "Service unavailable",
}

ACRONYM_MAP: dict[str, str] = {
    "Utub": "UTub",
    "Url": "URL",
    "Api": "API",
    "Id": "ID",
}


def _humanize_class_name(name: str) -> str:
    """Convert a PascalCase schema class name to a human-readable description."""
    # Step 1: strip ResponseSchema or Schema suffix
    stripped = re.sub(r"(ResponseSchema|Response|Schema)$", "", name)
    # Step 2: insert a space before each uppercase letter that follows a lowercase letter
    spaced = re.sub(r"(?<=[a-z])([A-Z])", r" \1", stripped)
    # Step 3: split into tokens, apply acronym substitution, lowercase non-acronym tokens
    tokens = spaced.split()
    result_tokens = []
    for index, token in enumerate(tokens):
        if token in ACRONYM_MAP:
            result_tokens.append(ACRONYM_MAP[token])
        elif index == 0:
            result_tokens.append(token)
        else:
            result_tokens.append(token.lower())
    return " ".join(result_tokens)


def _response_description(status_code: int, schema_cls: Type[BaseModel]) -> str:
    """Build a human-readable response description for the OpenAPI spec."""
    if status_code >= 400:
        return HTTP_STATUS_DESCRIPTIONS.get(status_code, "Error")
    if schema_cls.__doc__ is not None:
        return schema_cls.__doc__.strip()
    return _humanize_class_name(schema_cls.__name__)


SUCCESS_ENVELOPE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": [STD_JSON.SUCCESS, STD_JSON.FAILURE, STD_JSON.NO_CHANGE],
            "description": "Response status: Success, Failure, or No change",
        },
        "message": {
            "type": "string",
            "description": "Human-readable response message, if applicable",
        },
    },
    "required": ["status"],
}
SUCCESS_ENVELOPE_NAME = "SuccessEnvelope"


def _flask_path_to_openapi(rule_path: str) -> str:
    """Convert Flask path `/utubs/<int:utub_id>` to OpenAPI `/utubs/{utub_id}`."""
    return PATH_PARAM_PATTERN.sub(lambda match: f"{{{match.group(2)}}}", rule_path)


def _extract_path_parameters(rule_path: str) -> list[dict[str, Any]]:
    """Extract OpenAPI path parameter objects from a Flask rule string."""
    params = []
    for match in PATH_PARAM_PATTERN.finditer(rule_path):
        converter_raw = match.group(1)  # e.g. "int:" or None
        param_name = match.group(2)

        if converter_raw:
            converter_name = converter_raw.rstrip(":")
        else:
            converter_name = "string"

        openapi_type = CONVERTER_TYPE_MAP.get(converter_name, "string")
        params.append(
            {
                "name": param_name,
                "in": "path",
                "required": True,
                "schema": {"type": openapi_type},
            }
        )
    return params


def _endpoint_to_operation_id(endpoint: str) -> str:
    """Convert Flask endpoint to camelCase operationId.

    Drop the blueprint prefix (everything before and including the first dot),
    then convert the remaining snake_case to camelCase.

    Examples:
        utubs.create_utub → createUtub
        utub_url_tags.create_utub_url_tag → createUtubUrlTag
        splash.register_user → registerUser
    """
    if "." in endpoint:
        endpoint = endpoint.split(".", 1)[1]

    parts = endpoint.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


def _build_schema_ref(schema_cls: Type[BaseModel]) -> str:
    """Return a JSON $ref string for a Pydantic schema."""
    return f"#/components/schemas/{schema_cls.__name__}"


def _collect_schema(
    schema_cls: Type[BaseModel],
    components_schemas: dict[str, Any],
) -> None:
    """Add a schema and its $defs to components.schemas (first-write wins)."""
    schema_dict = schema_cls.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )

    # Extract nested $defs first
    defs = schema_dict.pop("$defs", {})
    for def_name, def_schema in defs.items():
        if def_name not in components_schemas:
            components_schemas[def_name] = def_schema

    # Add root schema under its class name
    class_name = schema_cls.__name__
    if class_name not in components_schemas:
        components_schemas[class_name] = schema_dict


# NOTE: The lru_cache helpers below call model_json_schema() without ref_template,
# unlike _collect_schema which uses ref_template='#/components/schemas/{model}'.
# This is intentional — these helpers only inspect top-level 'properties' and never
# follow $ref pointers, so the ref format is irrelevant to their results.


@functools.lru_cache(maxsize=None)
def _schema_has_status_property(schema_cls: Type[BaseModel]) -> bool:
    """Check if the schema's JSON schema output has a 'status' property."""
    json_schema = schema_cls.model_json_schema()
    return "status" in json_schema.get("properties", {})


@functools.lru_cache(maxsize=None)
def _schema_is_empty(schema_cls: Type[BaseModel]) -> bool:
    """Check if the schema's JSON schema output has no properties."""
    return not schema_cls.model_json_schema().get("properties")


def _build_response_schema_obj(schema_cls: Type[BaseModel]) -> dict[str, Any]:
    """Build the OpenAPI response schema object for a success response.

    Applies the three-way branching logic:
    1. Schema already has 'status' property -> direct $ref (no envelope)
    2. Schema has no properties -> direct $ref to SuccessEnvelope
    3. Otherwise -> allOf composition with SuccessEnvelope + data schema
    """
    if _schema_has_status_property(schema_cls):
        return {"$ref": _build_schema_ref(schema_cls)}
    elif _schema_is_empty(schema_cls):
        return {"$ref": f"#/components/schemas/{SUCCESS_ENVELOPE_NAME}"}

    return {
        "allOf": [
            {"$ref": f"#/components/schemas/{SUCCESS_ENVELOPE_NAME}"},
            {"$ref": _build_schema_ref(schema_cls)},
        ]
    }


def _collect_error_code_enum_schema(
    enum_cls: Type[IntEnum],
    components_schemas: dict[str, Any],
) -> None:
    """Add an IntEnum error code class to components/schemas (first-write wins).

    Builds a schema with type: integer, enum values, and x-enum-varnames
    for TypeScript codegen.
    """
    class_name = enum_cls.__name__
    if class_name in components_schemas:
        return

    components_schemas[class_name] = {
        "type": "integer",
        "enum": [member.value for member in enum_cls],
        "x-enum-varnames": [member.name for member in enum_cls],
        "description": f"Error codes for {class_name}",
    }


def _build_typed_error_response_schema(
    enum_cls: type[IntEnum],
    components_schemas: dict[str, Any],
) -> str:
    """Build a per-operation typed error response schema using allOf composition.

    Creates a schema like ``ErrorResponse_UTubErrorCodes`` that narrows the
    ``errorCode`` field to the specific IntEnum, while inheriting everything
    else from the base ``ErrorResponse``.

    Returns the schema name for ``$ref`` usage.  First-write wins — if the
    schema already exists in *components_schemas* it is not overwritten.
    """
    schema_name = f"ErrorResponse_{enum_cls.__name__}"
    if schema_name not in components_schemas:
        components_schemas[schema_name] = {
            "allOf": [
                {"$ref": "#/components/schemas/ErrorResponse"},
                {
                    "type": "object",
                    "properties": {
                        "errorCode": {
                            "$ref": f"#/components/schemas/{enum_cls.__name__}"
                        }
                    },
                },
            ]
        }
    return schema_name


def _build_security(
    auth_decorator: str | None,
    method: str,
) -> list[dict[str, list]]:
    """Build the OpenAPI security requirement for an operation."""
    is_mutating = method.upper() in MUTATING_METHODS

    has_session_auth = auth_decorator in SESSION_AUTH_DECORATORS

    if has_session_auth:
        security_obj: dict[str, list] = {"sessionAuth": []}
        if is_mutating:
            security_obj["csrfToken"] = []
        return [security_obj]

    # no_authenticated_users_allowed or no auth decorator
    if is_mutating:
        return [{"csrfToken": []}]

    return []


def generate_openapi_spec(app: Flask, strict: bool = False) -> dict[str, Any]:
    """Build an OpenAPI 3.1 spec dict from the Flask app's registered routes."""
    paths: defaultdict[str, dict] = defaultdict(dict)
    components_schemas: dict[str, Any] = {}
    components_schemas[SUCCESS_ENVELOPE_NAME] = SUCCESS_ENVELOPE_SCHEMA
    # operation_id → endpoint (for collision detection)
    operation_ids: dict[str, str] = {}

    for rule in app.url_map.iter_rules():
        # Skip non-API endpoints
        if (
            rule.endpoint == "static"
            or rule.endpoint.endswith(".static")
            or rule.endpoint.startswith("debugtoolbar")
        ):
            continue

        view_fn = app.view_functions.get(rule.endpoint)
        if view_fn is None:
            continue

        # Only process routes decorated with @api_route
        if not hasattr(view_fn, "_api_route_request_schema"):
            continue

        # Read stashed attributes
        request_schema = view_fn._api_route_request_schema
        response_schema = view_fn._api_route_response_schema
        tags = view_fn._api_route_tags
        description = view_fn._api_route_description
        status_codes = view_fn._api_route_status_codes
        auth_decorator = getattr(view_fn, "_auth_decorator", None)
        error_code_enum = getattr(view_fn, "_api_route_error_code_enum", None)

        # Convert path
        openapi_path = _flask_path_to_openapi(rule.rule)

        # Extract path parameters
        path_params = _extract_path_parameters(rule.rule)

        # Determine effective HTTP methods (exclude HEAD/OPTIONS)
        effective_methods = sorted(
            method for method in rule.methods if method not in ("HEAD", "OPTIONS")
        )
        is_multi_method = len(effective_methods) > 1

        # Build operation for each HTTP method
        for method in effective_methods:
            base_operation_id = _endpoint_to_operation_id(rule.endpoint)
            operation_id = (
                f"{base_operation_id}_{method.lower()}"
                if is_multi_method
                else base_operation_id
            )

            # Check for duplicate operationIds
            if operation_id in operation_ids:
                existing_endpoint = operation_ids[operation_id]
                raise ValueError(
                    f"Duplicate operationId '{operation_id}' generated from "
                    f"endpoints '{existing_endpoint}' and '{rule.endpoint}'"
                )
            operation_ids[operation_id] = rule.endpoint

            operation: dict[str, Any] = {
                "operationId": operation_id,
                "tags": tags or [],
                "security": _build_security(auth_decorator, method),
            }

            if description:
                operation["description"] = description

            # Path parameters
            if path_params:
                operation["parameters"] = path_params

            # Request body
            if request_schema is not None:
                _collect_schema(request_schema, components_schemas)
                operation["requestBody"] = {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": _build_schema_ref(request_schema)},
                        }
                    }
                }

            # Responses
            if status_codes is not None:
                responses: dict[str, Any] = {}
                for code, schema_cls in status_codes.items():
                    _collect_schema(schema_cls, components_schemas)

                    # Determine response schema representation
                    if code >= 400:
                        if error_code_enum is not None and issubclass(
                            error_code_enum, IntEnum
                        ):
                            typed_name = _build_typed_error_response_schema(
                                error_code_enum, components_schemas
                            )
                            response_schema_obj = {
                                "$ref": f"#/components/schemas/{typed_name}"
                            }
                        else:
                            response_schema_obj = {
                                "$ref": _build_schema_ref(schema_cls)
                            }
                    else:
                        response_schema_obj = _build_response_schema_obj(schema_cls)

                    responses[str(code)] = {
                        "description": _response_description(code, schema_cls),
                        "content": {
                            "application/json": {
                                "schema": response_schema_obj,
                            }
                        },
                    }
                operation["responses"] = responses
            elif response_schema is not None:
                _collect_schema(response_schema, components_schemas)

                # Determine response schema representation for code 200
                fallback_schema_obj = _build_response_schema_obj(response_schema)

                operation["responses"] = {
                    "200": {
                        "description": _response_description(200, response_schema),
                        "content": {
                            "application/json": {
                                "schema": fallback_schema_obj,
                            }
                        },
                    }
                }
            else:
                if strict:
                    raise ValueError(
                        f"Route {rule.endpoint!r} has no response schema — "
                        f"add one to @api_route (use without --strict to warn instead)"
                    )
                else:
                    operation["responses"] = {"200": {"description": "Success"}}
                    warnings.warn(
                        f"Route {rule.endpoint!r} has no response schema — "
                        f"add one to @api_route"
                    )

            # Error code enums are automatically discovered from the error_code
            # kwarg stashed by @api_route — no manual registry needed.
            if error_code_enum is not None and issubclass(error_code_enum, IntEnum):
                operation["x-error-codes"] = {
                    error_code_enum.__name__: {
                        "$ref": f"#/components/schemas/{error_code_enum.__name__}"
                    }
                }
                _collect_error_code_enum_schema(error_code_enum, components_schemas)

            paths[openapi_path][method.lower()] = operation

    spec: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {
            "title": "urls4irl API",
            "version": "1.0.0",
        },
        "x-non-json-responses": (
            "Known non-JSON responses not documented in this spec: "
            "302 redirects from @no_authenticated_users_allowed and "
            "@email_validation_required auth decorators, "
            "and HTML 404s from abort()/get_or_404()."
        ),
        "paths": dict(paths),
        "components": {
            "schemas": components_schemas,
            "securitySchemes": {
                "sessionAuth": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": "session",
                },
                "csrfToken": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-CSRFToken",
                },
            },
        },
    }

    return spec


@openapi_cli.command("generate")
@click.option(
    "--output",
    "-o",
    default="openapi.json",
    help="Output file path",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Error on routes missing response schemas",
)
@with_appcontext
def generate_openapi_command(output: str, strict: bool) -> None:
    """Generate an OpenAPI 3.1 JSON specification from registered API routes."""
    output_path = Path(output)

    # Validate parent directory exists
    if not output_path.parent.exists():
        raise click.ClickException(f"Directory does not exist: {output_path.parent}")

    app = current_app._get_current_object()
    try:
        spec = generate_openapi_spec(app, strict=strict)
    except ValueError as exc:
        raise click.ClickException(str(exc))

    path_count = len(spec["paths"])
    schema_count = len(spec["components"]["schemas"])

    output_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    click.echo(
        f"Generated OpenAPI 3.1 spec with {path_count} paths, "
        f"{schema_count} schemas → {output_path}"
    )


def register_openapi_cli(app: Flask) -> None:
    app.cli.add_command(openapi_cli)
