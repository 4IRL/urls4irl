from __future__ import annotations

from typing import Literal

from flask import jsonify
from pydantic import Field

from backend.api_common.responses import FlaskResponse
from backend.schemas.base import BaseSchema
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON


class AdminOpsActionResponseSchema(BaseSchema):
    """Envelope returned by every admin ops-action endpoint on success."""

    status: Literal["Success"] = Field(
        alias=STD_JSON.STATUS,
        description="Response status, always Success",
    )
    message: str = Field(
        alias=STD_JSON.MESSAGE,
        description="Human-readable summary of the operation result",
    )
    count: int | None = Field(
        default=None,
        description="Rows or items affected by the operation, when applicable",
    )

    def to_response(self, status_code: int = 200) -> FlaskResponse:
        payload = self.model_dump(by_alias=True, exclude_none=True)
        return jsonify(payload), status_code
