from backend.utils.strings.email_validation_strs import EMAILS
from backend.utils.strings.json_strs import FAILURE_GENERAL

# URL prefix shared by the api_v1 blueprint, the bearer request_loader, and the
# app-level JSON error-handler branches so they can never drift apart.
API_V1_URL_PREFIX = "/api/v1"


class API_AUTH:
    API_V1_URL_PREFIX = API_V1_URL_PREFIX
    AUTHORIZATION_HEADER = "Authorization"
    BEARER_PREFIX = "Bearer "
    # HS256, same signing setup as the email-validation and password-reset JWTs
    ALGORITHM = EMAILS.ALGORITHM
    SUBJECT_CLAIM = "sub"
    ISSUED_AT_CLAIM = "iat"
    EXPIRATION_CLAIM = "exp"
    TOKEN_TYPE_CLAIM = "type"
    ACCESS_TOKEN_TYPE = "access"


class API_AUTH_FAILURE(FAILURE_GENERAL):
    AUTHENTICATION_REQUIRED = "Authentication required."
    EMAIL_VALIDATION_REQUIRED = "Email validation required."
    EMAIL_ALREADY_VALIDATED = "Email is already validated."
    INVALID_REFRESH_TOKEN = "Invalid, expired, or revoked refresh token."
    REFRESH_TOKEN_REUSE_DETECTED = (
        "Refresh token reuse detected. All sessions for this device were revoked."
    )
    UNABLE_TO_VERIFY_GOOGLE_TOKEN = "Unable to verify Google identity token."


class API_AUTH_SUCCESS:
    LOGGED_OUT = "Logged out."
    LOGGED_OUT_EVERYWHERE = "Logged out on all devices."
