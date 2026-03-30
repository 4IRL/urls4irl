from __future__ import annotations

from pydantic import BaseModel, Field

from backend.contact.constants import CONTACT_FORM_CONSTANTS
from backend.schemas.requests._sanitize import SanitizedStr


class ContactRequest(BaseModel):
    subject: SanitizedStr = Field(
        min_length=CONTACT_FORM_CONSTANTS.MIN_SUBJECT_LENGTH,
        max_length=CONTACT_FORM_CONSTANTS.MAX_SUBJECT_LENGTH,
    )
    content: SanitizedStr = Field(
        min_length=1,
        max_length=CONTACT_FORM_CONSTANTS.MAX_CONTENT_LENGTH,
    )
