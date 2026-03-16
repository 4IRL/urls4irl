from __future__ import annotations
from functools import wraps
from typing import Callable, Type, TypeVar
from pydantic import BaseModel, ValidationError
from flask import request
from flask_login import current_user
from backend.api_common.responses import APIResponse
from backend.api_common.request_errors import pydantic_errors_to_dict
from backend.app_logger import warning_log

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
                return APIResponse(
                    status_code=400,
                    message=message,
                    error_code=error_code,
                ).to_response()
            try:
                kwargs["validated_request"] = schema.model_validate(raw)
            except ValidationError as validation_error:
                user_id = getattr(current_user, "id", "unknown")
                warning_log(
                    f"User={user_id} | Invalid JSON: {pydantic_errors_to_dict(validation_error)}"
                )
                return APIResponse(
                    status_code=400,
                    message=message,
                    error_code=error_code,
                    errors=pydantic_errors_to_dict(validation_error),
                ).to_response()
            return route_fn(*args, **kwargs)

        return wrapper

    return decorator
