from enum import IntEnum


class ContactErrorCodes(IntEnum):
    INVALID_FORM_INPUT = 1


class CONTACT_FORM_CONSTANTS:
    MIN_SUBJECT_LENGTH = 5
    MAX_SUBJECT_LENGTH = 100
    MAX_CONTENT_LENGTH = 1500
