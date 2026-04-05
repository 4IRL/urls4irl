from __future__ import annotations

from flask import jsonify
from pydantic import Field

from backend.api_common.responses import FlaskResponse
from backend.schemas.base import BaseSchema
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.url_strs import URL_FAILURE


class ErrorResponse(BaseSchema):
    status: str = Field(
        default=STD_JSON.FAILURE,
        alias=STD_JSON.STATUS,
        description="Error status, always Failure",
    )
    message: str = Field(
        alias=STD_JSON.MESSAGE, description="Human-readable error message"
    )
    error_code: int | None = Field(
        default=None,
        alias=STD_JSON.ERROR_CODE,
        description="Application-specific error code, if applicable",
    )
    field_errors: dict[str, list[str]] | None = Field(
        default=None,
        alias=STD_JSON.ERRORS,
        description="Map of field names to lists of validation error messages, if applicable",
    )
    error_detail: str | None = Field(
        default=None,
        alias=STD_JSON.DETAILS,
        description="Additional error detail, if applicable",
    )
    url_string: str | None = Field(
        default=None,
        alias=URL_FAILURE.URL_STRING,
        description="URL string involved in the error, if applicable",
    )

    def to_response(self, status_code: int) -> FlaskResponse:
        payload = self.model_dump(by_alias=True, exclude_none=True)
        return jsonify(payload), status_code


def build_field_error_response(
    message: str,
    errors: dict[str, list[str]],
    error_code: int | None = None,
    status_code: int = 400,
) -> FlaskResponse:
    return ErrorResponse(
        message=message, error_code=error_code, field_errors=errors
    ).to_response(status_code)


def build_message_error_response(
    message: str,
    error_code: int | None = None,
    status_code: int = 400,
) -> FlaskResponse:
    return ErrorResponse(message=message, error_code=error_code).to_response(
        status_code
    )


def build_detail_error_response(
    message: str,
    details: str,
    error_code: int,
    status_code: int = 400,
) -> FlaskResponse:
    return ErrorResponse(
        message=message, error_code=error_code, error_detail=details
    ).to_response(status_code)


def build_url_conflict_error_response(
    message: str,
    url_string: str,
    error_code: int,
    status_code: int = 409,
) -> FlaskResponse:
    return ErrorResponse(
        message=message, error_code=error_code, url_string=url_string
    ).to_response(status_code)
