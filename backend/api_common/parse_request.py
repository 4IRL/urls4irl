from __future__ import annotations
from functools import wraps
from typing import Callable, Type, TypeVar

from flask import request
from flask_login import current_user
from pydantic import BaseModel, ValidationError

from backend.api_common.request_errors import pydantic_errors_to_dict
from backend.app_logger import warning_log
from backend.schemas.errors import (
    build_field_error_response,
    build_message_error_response,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def parse_json_body(schema: Type[SchemaT], message: str, error_code: int) -> Callable:
    """Decorator that parses request JSON, validates against `schema`, and injects
    the result as `validated_request` kwarg. Returns 400 on missing body or validation
    failure. Must be placed innermost (closest to the function), after auth decorators.
    """

    def decorator(route_fn: Callable) -> Callable:
        @wraps(route_fn)
        def wrapper(*args, **kwargs):
            raw = request.get_json(silent=True)
            if raw is None:
                user_id = getattr(current_user, "id", "unknown")
                warning_log(f"User={user_id} | Missing JSON body")
                return build_message_error_response(
                    message=message,
                    error_code=error_code,
                    status_code=400,
                )
            try:
                kwargs["validated_request"] = schema.model_validate(raw)
            except ValidationError as validation_error:
                user_id = getattr(current_user, "id", "unknown")
                field_errors = pydantic_errors_to_dict(validation_error)
                warning_log(f"User={user_id} | Invalid JSON: {field_errors}")
                return build_field_error_response(
                    message=message,
                    errors=field_errors,
                    error_code=error_code,
                    status_code=400,
                )
            return route_fn(*args, **kwargs)

        return wrapper

    return decorator
