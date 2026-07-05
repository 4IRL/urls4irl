from __future__ import annotations

from enum import IntEnum
from functools import wraps
import inspect
import re
from typing import Callable, Type, TypeVar

from flask import redirect, request, url_for
from flask_login import current_user
from pydantic import BaseModel, ValidationError

from backend.api_common.request_errors import pydantic_errors_to_dict
from backend.api_common.responses import FlaskResponse
from backend.app_logger import warning_log
from backend.schemas.base import BaseSchema
from backend.schemas.errors import (
    build_field_error_response,
    build_message_error_response,
)
from backend.utils.all_routes import ROUTES
from backend.utils.strings.url_validation_strs import URL_VALIDATION

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def parse_query_args(
    schema_cls: type[BaseModel],
    message: str,
    error_code: IntEnum | int,
    multi_value_keys: frozenset[str] | None = None,
) -> BaseModel | FlaskResponse:
    """Validate `request.args` against a Pydantic query schema.

    Returns the validated model on success or a 400 field-error response on
    `ValidationError`. Callers check `isinstance(result, BaseModel)` to
    short-circuit on the error branch. `@api_route(query_schema=...)` is
    OpenAPI metadata only and does not validate at runtime, so every query
    route runs this same args-to-dict + model_validate + error-envelope dance;
    centralizing it keeps the route bodies focused on the service call and
    envelope.

    `message` and `error_code` populate the 400 field-error envelope so each
    blueprint surfaces its own failure copy and error code.

    `multi_value_keys` names query-string keys that should be promoted from a
    single flat string to a list (via `request.args.getlist(key)`) before
    Pydantic validation. Callers that pass `None` get the default empty
    frozenset and the original flat behaviour. The `None` default mirrors
    the project's non-mutable-default-arg convention even though `frozenset`
    is immutable.
    """
    multi_value_keys = multi_value_keys or frozenset()
    args_dict = request.args.to_dict(flat=True)
    for multi_value_key in multi_value_keys:
        args_dict[multi_value_key] = request.args.getlist(multi_value_key)
    try:
        return schema_cls.model_validate(args_dict)
    except ValidationError as validation_error:
        return build_field_error_response(
            message=message,
            errors=pydantic_errors_to_dict(validation_error),
            error_code=error_code,
            status_code=400,
        )


def schema_name_to_kwarg(schema_cls: Type[BaseModel]) -> str:
    """Convert a schema class name from CamelCase to snake_case for kwarg injection.

    Examples::

        LoginRequest        → login_request
        CreateURLRequest    → create_url_request
        CreateUTubRequest   → create_utub_request
        AddMemberRequest    → add_member_request
    """
    name = schema_cls.__name__
    # Normalize product name "UTub" to "Utub" so it converts as a single word
    name = name.replace("UTub", "Utub")
    # Insert underscore between lowercase/digit and uppercase
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    # Insert underscore between consecutive uppercase letters followed by lowercase
    snake = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", snake)
    return snake.lower()


def api_route(
    *,
    request_schema: Type[SchemaT] | None = None,
    query_schema: Type[BaseModel] | None = None,
    response_schema: Type[BaseSchema] | None = None,
    error_message: str | None = None,
    error_code: IntEnum | int | None = None,
    ajax_required: bool = True,
    tags: list[str] | None = None,
    description: str | None = None,
    status_codes: dict[int, Type[BaseSchema]] | None = None,
) -> Callable:
    """Unified decorator that handles request body validation and response schema
    declaration for API routes.

    When ``request_schema`` is provided, parses the JSON body, validates it, and
    injects the result as a kwarg whose name is derived from the schema class
    (e.g. ``LoginRequest`` → ``login_request``). Returns 400 on missing body or
    validation failure.

    When ``request_schema`` is ``None``, skips body parsing entirely (useful for
    GET/DELETE routes).

    ``query_schema`` is OpenAPI-only metadata: it advertises the Pydantic model
    that describes the GET route's accepted query parameters so the OpenAPI
    generator can emit ``in: query`` parameter entries. Runtime query validation
    still lives at the route layer (``parse_query_args``); this kwarg never
    changes request handling.

    ``response_schema`` is stashed on the wrapped function for introspection
    (e.g. OpenAPI generation) and has no runtime effect.

    Must be placed innermost (closest to the function), after auth decorators.
    """

    if request_schema is not None:
        if error_message is None:
            raise ValueError(
                f"error_message is required when request_schema is provided "
                f"(got request_schema={request_schema.__name__})"
            )
        if error_code is None:
            raise ValueError(
                f"error_code is required when request_schema is provided "
                f"(got request_schema={request_schema.__name__})"
            )

    kwarg_name: str | None = (
        schema_name_to_kwarg(request_schema) if request_schema is not None else None
    )

    def decorator(route_fn: Callable) -> Callable:
        if kwarg_name is not None:
            fn_params = set(inspect.signature(route_fn).parameters.keys())
            if kwarg_name not in fn_params:
                raise ValueError(
                    f"Route '{route_fn.__name__}' must declare a '{kwarg_name}' "
                    f"parameter to receive the validated "
                    f"{request_schema.__name__} body"
                )

        @wraps(route_fn)
        def wrapper(*args, **kwargs):
            if ajax_required:
                if (
                    request.headers.get(URL_VALIDATION.X_REQUESTED_WITH, None)
                    != URL_VALIDATION.XMLHTTPREQUEST
                ):
                    user_id = getattr(current_user, "id", "unknown")
                    warning_log(f"User={user_id} did not make an AJAX request")
                    return redirect(url_for(ROUTES.UTUBS.HOME))

            if request_schema is not None:
                json_body = request.get_json(silent=True)
                if json_body is None:
                    user_id = getattr(current_user, "id", "unknown")
                    warning_log(f"User={user_id} | Missing JSON body")
                    return build_message_error_response(
                        message=error_message,
                        error_code=error_code,
                        status_code=400,
                    )
                try:
                    kwargs[kwarg_name] = request_schema.model_validate(json_body)
                except ValidationError as validation_error:
                    user_id = getattr(current_user, "id", "unknown")
                    field_errors = pydantic_errors_to_dict(validation_error)
                    warning_log(f"User={user_id} | Invalid JSON: {field_errors}")
                    return build_field_error_response(
                        message=error_message,
                        errors=field_errors,
                        error_code=error_code,
                        status_code=400,
                    )
            return route_fn(*args, **kwargs)

        # Stashed for OpenAPI schema generation via route introspection.
        wrapper._api_route_request_schema = request_schema
        wrapper._api_route_query_schema = query_schema
        wrapper._api_route_response_schema = response_schema
        wrapper._api_route_ajax_required = ajax_required
        wrapper._api_route_tags = tags
        wrapper._api_route_description = description
        wrapper._api_route_status_codes = status_codes
        wrapper._api_route_error_code_enum = None
        if isinstance(error_code, IntEnum):
            wrapper._api_route_error_code_enum = type(error_code)
        elif isinstance(error_code, int):
            raise TypeError(
                "error_code must be an IntEnum member, not a plain int. "
                "Define an IntEnum class for your error codes."
            )
        return wrapper

    return decorator
