"""
Contains all routes for easy insertion into `url_for` flask function
"""


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
    RESET_PASSWORD = _SPLASH + "reset_password"


class TAG_ROUTES:
    _TAGS = "tags."
    CREATE_TAG = _TAGS + "create_utub_url_tag"
    DELETE_TAG = _TAGS + "delete_utub_url_tag"
    UPDATE_TAG = _TAGS + "update_tag_on_url"


class URL_ROUTES:
    _URLS = "urls."
    REMOVE_URL = _URLS + "remove_url"
    CREATE_URL = _URLS + "create_url"
    UPDATE_URL_AND_TITLE = _URLS + "update_url_and_title"
    UPDATE_URL = _URLS + "update_url"
    UPDATE_URL_TITLE = _URLS + "update_url_title"


class USER_ROUTES:
    _USERS = "users."
    LOGOUT = _USERS + "logout"


class UTUB_ROUTES:
    _UTUBS = "utubs."
    HOME = _UTUBS + "home"
    GET_UTUBS = _UTUBS + "get_utubs"
    CREATE_UTUB = _UTUBS + "create_utub"
    DELETE_UTUB = _UTUBS + "delete_utub"
    UPDATE_UTUB_NAME = _UTUBS + "update_utub_name"
    UPDATE_UTUB_DESC = _UTUBS + "update_utub_desc"


class ROUTES:
    MEMBERS = MEMBER_ROUTES
    SPLASH = SPLASH_ROUTES
    TAGS = TAG_ROUTES
    URLS = URL_ROUTES
    USERS = USER_ROUTES
    UTUBS = UTUB_ROUTES
