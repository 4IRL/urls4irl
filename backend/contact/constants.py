from __future__ import annotations

from enum import IntEnum


class CONTACT_FORM_CONSTANTS:
    MIN_SUBJECT_LENGTH = 5
    MAX_SUBJECT_LENGTH = 100
    MAX_CONTENT_LENGTH = 1500
    RATE_LIMIT_PER_HOUR = 5
    RATE_LIMIT_PER_DAY = 10


class ContactErrorCodes(IntEnum):
    INVALID_FORM_INPUT = 1
