from dataclasses import dataclass, field
from typing import Any, Dict
from flask import jsonify, Response

from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON

FlaskResponse = tuple[Response, int]


@dataclass
class APIResponse:
    """Represents the result of an API operation"""

    status: str | None = None
    status_code: int = 200
    message: str | None = None
    error_code: int | None = None
    errors: dict | None = None
    details: str | None = None
    data: Dict[str, Any] = field(default_factory=dict)

    def to_response(self) -> FlaskResponse:
        """Convert to Flask response"""
        payload = {
            STD_JSON.STATUS: (
                STD_JSON.SUCCESS if self.status_code < 400 else STD_JSON.FAILURE
            ),
            **self.data,
        }

        if self.status is not None:
            payload[STD_JSON.STATUS] = self.status

        if self.message:
            payload[STD_JSON.MESSAGE] = self.message

        if self.error_code is not None:
            payload[STD_JSON.ERROR_CODE] = self.error_code

        if self.errors:
            payload[STD_JSON.ERRORS] = self.errors

        if self.details:
            payload[STD_JSON.DETAILS] = self.details

        return jsonify(payload), self.status_code
