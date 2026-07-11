from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from backend.schemas.requests._sanitize import OptionalSanitizedStr, SanitizedStr

_REASON_MAX_LENGTH: int = 500


class AdminActionRequest(BaseModel):
    reason: OptionalSanitizedStr = Field(
        default=None,
        description=(
            "Optional reason for this admin action (max 500 characters). "
            "Empty or whitespace-only strings are treated as no reason provided."
        ),
    )

    @field_validator("reason", mode="after")
    @classmethod
    def reason_max_length(cls, value: str | None) -> str | None:
        if value is not None and len(value) > _REASON_MAX_LENGTH:
            raise ValueError(
                f"String should have at most {_REASON_MAX_LENGTH} characters"
            )
        return value


class AdminReasonRequiredRequest(BaseModel):
    reason: SanitizedStr = Field(
        description=(
            "Required reason for this admin action (max 500 characters). "
            "Whitespace-only values are rejected."
        ),
    )

    @field_validator("reason", mode="after")
    @classmethod
    def reason_not_empty_or_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Reason cannot be empty or whitespace-only.")
        if len(value) > _REASON_MAX_LENGTH:
            raise ValueError(
                f"String should have at most {_REASON_MAX_LENGTH} characters"
            )
        return value
