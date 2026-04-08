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
from backend.app_logger import warning_log
from backend.schemas.base import BaseSchema
from backend.schemas.errors import (
    build_field_error_response,
    build_message_error_response,
)
from backend.utils.all_routes import ROUTES
from backend.utils.strings.url_validation_strs import URL_VALIDATION

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _schema_name_to_kwarg(schema_cls: Type[BaseModel]) -> str:
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
        _schema_name_to_kwarg(request_schema) if request_schema is not None else None
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
        wrapper._api_route_response_schema = response_schema
        wrapper._api_route_ajax_required = ajax_required
        wrapper._api_route_tags = tags
        wrapper._api_route_description = description
        wrapper._api_route_status_codes = status_codes
        if isinstance(error_code, IntEnum):
            wrapper._api_route_error_code_enum = type(error_code)
        elif isinstance(error_code, int):
            raise TypeError(
                "error_code must be an IntEnum member, not a plain int. "
                "Define an IntEnum class for your error codes."
            )
        else:
            wrapper._api_route_error_code_enum = None
        return wrapper

    return decorator
