from __future__ import annotations
from functools import wraps
from typing import Callable, Type, TypeVar

from flask import request
from flask_login import current_user
from pydantic import BaseModel, ValidationError

from backend.api_common.request_errors import pydantic_errors_to_dict
from backend.app_logger import warning_log
from backend.schemas.base import BaseSchema
from backend.schemas.errors import (
    build_field_error_response,
    build_message_error_response,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def api_route(
    *,
    request_schema: Type[SchemaT] | None = None,
    response_schema: Type[BaseSchema] | None = None,
    error_message: str = "",
    error_code: int = 0,
) -> Callable:
    """Unified decorator that handles request body validation and response schema
    declaration for API routes.

    When ``request_schema`` is provided, parses the JSON body, validates it, and
    injects the result as a ``validated_request`` kwarg. Returns 400 on missing
    body or validation failure.

    When ``request_schema`` is ``None``, skips body parsing entirely (useful for
    GET/DELETE routes).

    ``response_schema`` is stashed on the wrapped function for introspection
    (e.g. OpenAPI generation) and has no runtime effect.

    Must be placed innermost (closest to the function), after auth decorators.
    """

    def decorator(route_fn: Callable) -> Callable:
        @wraps(route_fn)
        def wrapper(*args, **kwargs):
            if request_schema is not None:
                raw = request.get_json(silent=True)
                if raw is None:
                    user_id = getattr(current_user, "id", "unknown")
                    warning_log(f"User={user_id} | Missing JSON body")
                    return build_message_error_response(
                        message=error_message,
                        error_code=error_code,
                        status_code=400,
                    )
                try:
                    kwargs["validated_request"] = request_schema.model_validate(raw)
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

        wrapper._api_route_request_schema = request_schema
        wrapper._api_route_response_schema = response_schema
        return wrapper

    return decorator
