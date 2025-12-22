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
    RESET_PASSWORD = _SPLASH + "reset_password"
    ERROR_PAGE = _SPLASH + "error_page"


class URL_TAG_ROUTES:
    _URL_TAGS = "utub_url_tags."
    CREATE_URL_TAG = _URL_TAGS + "create_utub_url_tag"
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


class UTUB_ROUTES:
    _UTUBS = "utubs."
    HOME = _UTUBS + "home"
    GET_SINGLE_UTUB = _UTUBS + "get_single_utub"
    GET_UTUBS = _UTUBS + "get_utubs"
    CREATE_UTUB = _UTUBS + "create_utub"
    DELETE_UTUB = _UTUBS + "delete_utub"
    UPDATE_UTUB_NAME = _UTUBS + "update_utub_name"
    UPDATE_UTUB_DESC = _UTUBS + "update_utub_desc"


class ROUTES:
    MEMBERS = MEMBER_ROUTES
    SPLASH = SPLASH_ROUTES
    URL_TAGS = URL_TAG_ROUTES
    UTUB_TAGS = UTUB_TAG_ROUTES
    URLS = URL_ROUTES
    USERS = USER_ROUTES
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
        # Util routes
        "errorPage": url_for(SPLASH_ROUTES.ERROR_PAGE),
        # Logout
        "logout": url_for(USER_ROUTES.LOGOUT),
    }
