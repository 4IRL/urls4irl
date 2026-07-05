from enum import IntEnum

# Stricter than the global 100/min default: token issuance is the
# highest-value brute-force target (design-doc rate-limit decision).
API_AUTH_RATE_LIMIT = "10/minute"


class ApiAuthErrorCodes(IntEnum):
    INVALID_FORM_INPUT = 1
    INVALID_REFRESH_TOKEN = 2
    REFRESH_TOKEN_REUSE_DETECTED = 3
    INVALID_GOOGLE_TOKEN = 4
    OAUTH_EMAIL_COLLISION = 5
