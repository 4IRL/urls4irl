from dataclasses import dataclass, field
from typing import Any, Dict
from flask import jsonify, Response
from pydantic import BaseModel

from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON

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
    data: Dict[str, Any] | BaseModel = field(default_factory=dict)

    def to_response(self) -> FlaskResponse:
        """Convert to Flask response.

        `mode="json"` is critical for datetime fields: without it, Pydantic
        emits native `datetime` objects that Flask's `jsonify` serializes via
        `http_date()` (RFC 822 / HTTP-Date — "Sat, 06 Jun 2026 17:00:00 GMT").
        That format contradicts the schemas' "UTC ISO-8601" field descriptions
        and the OpenAPI `format: "date-time"` declaration. JSON mode hands
        jsonify pre-serialized ISO-8601 strings (`2026-06-06T17:00:00+00:00`),
        so the wire shape matches what TypeScript consumers expect.
        """
        data_dict = (
            self.data.model_dump(by_alias=True, mode="json")
            if isinstance(self.data, BaseModel)
            else self.data
        )
        payload = {
            STD_JSON.STATUS: (
                STD_JSON.SUCCESS if self.status_code < 400 else STD_JSON.FAILURE
            ),
            **data_dict,
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
