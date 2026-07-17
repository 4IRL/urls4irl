"""
Contains all routes for easy insertion into `url_for` flask function
"""

from flask import url_for


class MEMBER_ROUTES:
    _MEMBERS = "members."
    REMOVE_MEMBER = _MEMBERS + "remove_member"
    CREATE_MEMBER = _MEMBERS + "create_member"


class SPLASH_ROUTES:
    _SPLASH = "splash."
    SPLASH_PAGE = _SPLASH + "splash_page"
    REGISTER = _SPLASH + "register_user"
    LOGIN = _SPLASH + "login"
    CONFIRM_EMAIL = _SPLASH + "confirm_email_after_register"
    SEND_VALIDATION_EMAIL = _SPLASH + "send_validation_email"
    VALIDATE_EMAIL = _SPLASH + "validate_email"
    FORGOT_PASSWORD_PAGE = _SPLASH + "forgot_password"
    CONFIRM_PASSWORD_RESET = _SPLASH + "confirm_password_reset"
    RESET_PASSWORD = _SPLASH + "reset_password_page"
    ERROR_PAGE = _SPLASH + "error_page"


class OAUTH_ROUTES:
    _SPLASH = "splash."
    GOOGLE_LOGIN = _SPLASH + "google_login"
    GOOGLE_CALLBACK = _SPLASH + "google_callback"
    GITHUB_LOGIN = _SPLASH + "github_login"
    GITHUB_CALLBACK = _SPLASH + "github_callback"
    LINK = _SPLASH + "oauth_link"
    CONFIRM_LINK_PAGE = _SPLASH + "oauth_confirm_link_page"
    CONFIRM_LINK = _SPLASH + "oauth_confirm_link"


class URL_TAG_ROUTES:
    _URL_TAGS = "utub_url_tags."
    CREATE_URL_TAG = _URL_TAGS + "create_utub_url_tag"
    BATCH_ADD_URL_TAGS = _URL_TAGS + "create_utub_url_tags"
    DELETE_URL_TAG = _URL_TAGS + "delete_utub_url_tag"


class UTUB_TAG_ROUTES:
    _UTUB_TAGS = "utub_tags."
    CREATE_UTUB_TAG = _UTUB_TAGS + "create_utub_tag"
    DELETE_UTUB_TAG = _UTUB_TAGS + "delete_utub_tag"


class URL_ROUTES:
    _URLS = "urls."
    DELETE_URL = _URLS + "delete_url"
    GET_URL = _URLS + "get_url"
    CREATE_URL = _URLS + "create_url"
    UPDATE_URL = _URLS + "update_url"
    UPDATE_URL_TITLE = _URLS + "update_url_title"


class USER_ROUTES:
    _USERS = "users."
    LOGOUT = _USERS + "logout"
    PRIVACY = _USERS + "privacy_policy"
    TERMS = _USERS + "terms_and_conditions"
    SETTINGS = _USERS + "settings"
    OAUTH_LINK = _USERS + "link_oauth_provider"
    OAUTH_UNLINK = _USERS + "unlink_oauth_provider"


class ACCOUNT_AND_SETTING_ROUTES:
    _CONTACT = "contact."
    CONTACT_US = _CONTACT + "contact_us"
    CONTACT_US_SUBMIT = _CONTACT + "submit_contact_us"


class ADMIN_ROUTES:
    _ADMIN = "admin."
    METRICS_PAGE = _ADMIN + "admin_metrics"
    PORTAL = _ADMIN + "admin_portal"
    HEALTH_PAGE = _ADMIN + "admin_health"
    HEALTH_SNAPSHOT = _ADMIN + "admin_health_snapshot"
    SYSTEM_OPERATIONS_PAGE = _ADMIN + "admin_system_operations"
    USERS_PAGE = _ADMIN + "admin_users"
    USERS_SEARCH = _ADMIN + "admin_users_search"
    USER_DETAIL = _ADMIN + "admin_user_detail"
    UTUBS_PAGE = _ADMIN + "admin_utubs"
    UTUB_DETAIL = _ADMIN + "admin_utub_detail"
    AUDIT_LOG_PAGE = _ADMIN + "admin_audit_log"
    AUDIT_LOG_ROWS = _ADMIN + "admin_audit_log_rows"
    # Ops action endpoints
    OPS_METRICS_FLUSH = _ADMIN + "admin_ops_metrics_flush"
    OPS_GAUGE_SAMPLE = _ADMIN + "admin_ops_gauge_sample"
    OPS_AUDIT_PURGE = _ADMIN + "admin_ops_audit_purge"
    OPS_VERIFY_TABLES = _ADMIN + "admin_ops_verify_tables"
    OPS_SHORT_URLS_SYNC = _ADMIN + "admin_ops_short_urls_sync"
    OPS_BACKUP_TRIGGER = _ADMIN + "admin_ops_backup_trigger"
    # Content moderation endpoints
    MOD_UTUB_LOCK = _ADMIN + "admin_utub_lock"
    MOD_UTUB_UNLOCK = _ADMIN + "admin_utub_unlock"
    MOD_UTUB_DELETE = _ADMIN + "admin_utub_delete"
    MOD_MEMBER_REMOVE = _ADMIN + "admin_member_remove"
    MOD_URL_DELETE = _ADMIN + "admin_url_delete"
    MOD_URL_PURGE = _ADMIN + "admin_url_purge"


class SEARCH_ROUTES:
    _SEARCH = "search."
    SEARCH = _SEARCH + "search_across_utubs"


class SYSTEM_ROUTES:
    _SYSTEM = "system."
    HEALTH = _SYSTEM + "health"


class UTUB_ROUTES:
    _UTUBS = "utubs."
    HOME = _UTUBS + "home"
    GET_SINGLE_UTUB = _UTUBS + "get_single_utub"
    GET_UTUBS = _UTUBS + "get_utubs"
    CREATE_UTUB = _UTUBS + "create_utub"
    DELETE_UTUB = _UTUBS + "delete_utub"
    UPDATE_UTUB_NAME = _UTUBS + "update_utub_name"
    UPDATE_UTUB_DESC = _UTUBS + "update_utub_desc"


class API_V1_ROUTES:
    """Endpoint names for the bearer-token mobile surface.

    Used by integration tests via url_for(); deliberately NOT included in
    generate_routes_js() — the web frontend never calls /api/v1.
    """

    _API_V1 = "api_v1."
    GET_ME = _API_V1 + "api_v1_get_me"
    AUTH_LOGIN = _API_V1 + "api_v1_auth_login"
    AUTH_REFRESH = _API_V1 + "api_v1_auth_refresh"
    AUTH_LOGOUT = _API_V1 + "api_v1_auth_logout"
    AUTH_LOGOUT_ALL = _API_V1 + "api_v1_auth_logout_all"
    AUTH_RESEND_VALIDATION = _API_V1 + "api_v1_auth_resend_validation"
    AUTH_GOOGLE = _API_V1 + "api_v1_auth_google"
    # UTub routes
    CREATE_UTUB = _API_V1 + "api_v1_create_utub"
    GET_UTUBS = _API_V1 + "api_v1_get_utubs"
    GET_SINGLE_UTUB = _API_V1 + "api_v1_get_single_utub"
    UPDATE_UTUB_NAME = _API_V1 + "api_v1_update_utub_name"
    UPDATE_UTUB_DESC = _API_V1 + "api_v1_update_utub_desc"
    DELETE_UTUB = _API_V1 + "api_v1_delete_utub"
    # Member routes
    CREATE_MEMBER = _API_V1 + "api_v1_create_member"
    REMOVE_MEMBER = _API_V1 + "api_v1_remove_member"
    # URL routes
    CREATE_URL = _API_V1 + "api_v1_create_url"
    GET_URL = _API_V1 + "api_v1_get_url"
    UPDATE_URL = _API_V1 + "api_v1_update_url"
    UPDATE_URL_TITLE = _API_V1 + "api_v1_update_url_title"
    DELETE_URL = _API_V1 + "api_v1_delete_url"
    # URL-tag routes
    CREATE_URL_TAG = _API_V1 + "api_v1_create_utub_url_tag"
    CREATE_URL_TAGS_BATCH = _API_V1 + "api_v1_create_utub_url_tags"
    DELETE_URL_TAG = _API_V1 + "api_v1_delete_utub_url_tag"
    # UTub-tag routes
    CREATE_UTUB_TAG = _API_V1 + "api_v1_create_utub_tag"
    DELETE_UTUB_TAG = _API_V1 + "api_v1_delete_utub_tag"
    # Search
    SEARCH = _API_V1 + "api_v1_search_across_utubs"


class ROUTES:
    API_V1 = API_V1_ROUTES
    MEMBERS = MEMBER_ROUTES
    SPLASH = SPLASH_ROUTES
    OAUTH = OAUTH_ROUTES
    URL_TAGS = URL_TAG_ROUTES
    UTUB_TAGS = UTUB_TAG_ROUTES
    URLS = URL_ROUTES
    USERS = USER_ROUTES
    ACCOUNT_AND_SETTINGS = ACCOUNT_AND_SETTING_ROUTES
    ADMIN = ADMIN_ROUTES
    SEARCH = SEARCH_ROUTES
    UTUBS = UTUB_ROUTES


def generate_routes_js() -> dict[str, str]:
    """
    Generate routes configuration for frontend JavaScript.
    Returns a dict that can be passed to Jinja and converted to JSON.
    """
    return {
        # UTub routes
        "home": url_for(UTUB_ROUTES.HOME),
        "createUTub": url_for(UTUB_ROUTES.CREATE_UTUB),
        "getUTubs": url_for(UTUB_ROUTES.GET_UTUBS),
        "getUTub": url_for(UTUB_ROUTES.GET_SINGLE_UTUB, utub_id=-1),
        "deleteUTub": url_for(UTUB_ROUTES.GET_SINGLE_UTUB, utub_id=-1),
        "updateUTubName": url_for(UTUB_ROUTES.UPDATE_UTUB_NAME, utub_id=-1),
        "updateUTubDescription": url_for(UTUB_ROUTES.UPDATE_UTUB_DESC, utub_id=-1),
        # URL routes
        "getURL": url_for(URL_ROUTES.GET_URL, utub_id=-1, utub_url_id=-2),
        "createURL": url_for(URL_ROUTES.CREATE_URL, utub_id=-1),
        "deleteURL": url_for(URL_ROUTES.DELETE_URL, utub_id=-1, utub_url_id=-2),
        "updateURL": url_for(URL_ROUTES.UPDATE_URL, utub_id=-1, utub_url_id=-2),
        "updateURLTitle": url_for(
            URL_ROUTES.UPDATE_URL_TITLE, utub_id=-1, utub_url_id=-2
        ),
        # UTub URL Tag routes
        "createURLTag": url_for(
            URL_TAG_ROUTES.CREATE_URL_TAG, utub_id=-1, utub_url_id=-2
        ),
        "createURLTagsBatch": url_for(
            URL_TAG_ROUTES.BATCH_ADD_URL_TAGS, utub_id=-1, utub_url_id=-2
        ),
        "deleteURLTag": url_for(
            URL_TAG_ROUTES.DELETE_URL_TAG, utub_id=-1, utub_url_id=-2, utub_tag_id=-3
        ),
        # UTub Tag routes
        "createUTubTag": url_for(UTUB_TAG_ROUTES.CREATE_UTUB_TAG, utub_id=-1),
        "deleteUTubTag": url_for(
            UTUB_TAG_ROUTES.DELETE_UTUB_TAG, utub_id=-1, utub_tag_id=-2
        ),
        # Member routes
        "createMember": url_for(MEMBER_ROUTES.CREATE_MEMBER, utub_id=-1),
        "removeMember": url_for(MEMBER_ROUTES.REMOVE_MEMBER, utub_id=-1, user_id=-4),
        # Splash routes
        "login": url_for(SPLASH_ROUTES.LOGIN),
        "register": url_for(SPLASH_ROUTES.REGISTER),
        "confirmEmailAfterRegister": url_for(SPLASH_ROUTES.CONFIRM_EMAIL),
        "sendValidationEmail": url_for(SPLASH_ROUTES.SEND_VALIDATION_EMAIL),
        "forgotPassword": url_for(SPLASH_ROUTES.FORGOT_PASSWORD_PAGE),
        "oauthGoogleLogin": url_for(OAUTH_ROUTES.GOOGLE_LOGIN),
        "oauthGithubLogin": url_for(OAUTH_ROUTES.GITHUB_LOGIN),
        # Util routes
        "errorPage": url_for(SPLASH_ROUTES.ERROR_PAGE),
        # Logout
        "logout": url_for(USER_ROUTES.LOGOUT),
        # Contact
        "contactUs": url_for(ACCOUNT_AND_SETTING_ROUTES.CONTACT_US_SUBMIT),
        # Search
        "crossUtubSearch": url_for(SEARCH_ROUTES.SEARCH),
    }


def generate_admin_routes_js() -> dict[str, str]:
    """
    Admin-only routes exposed to the frontend.

    Caller (`backend/utils/constants.py:STRINGS.build_config`) merges this
    into `APP_CONFIG.routes` only when the current user is an authenticated
    admin, so non-admin and anonymous clients never receive the admin URL
    in their payload.
    """
    return {
        "adminMetricsPage": url_for(ADMIN_ROUTES.METRICS_PAGE),
    }
