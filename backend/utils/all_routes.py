"""
Contains all routes for easy insertion into `url_for` flask function
"""

from enum import StrEnum
from typing import NamedTuple

from flask import url_for


class MEMBER_ROUTES:
    _MEMBERS = "members."
    REMOVE_MEMBER = _MEMBERS + "remove_member"
    CREATE_MEMBER = _MEMBERS + "create_member"
    CO_MEMBER_CANDIDATES = _MEMBERS + "get_co_member_candidates_route"
    MODIFY_MEMBER_ROLE = _MEMBERS + "modify_member_role"
    TRANSFER_UTUB_OWNERSHIP = _MEMBERS + "transfer_utub_ownership"


class SPLASH_ROUTES:
    _SPLASH = "splash."
    SPLASH_PAGE = _SPLASH + "splash_page"
    REGISTER = _SPLASH + "register_user"
    LOGIN = _SPLASH + "login"
    CONFIRM_EMAIL = _SPLASH + "confirm_email_after_register"
    SEND_VALIDATION_EMAIL = _SPLASH + "send_validation_email"
    RESEND_REGISTRATION_EMAIL = _SPLASH + "resend_registration_email"
    VALIDATE_EMAIL = _SPLASH + "validate_email"
    CONFIRM_EMAIL_CHANGE = _SPLASH + "confirm_email_change"
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
    APPLY_TAGS_TO_URLS = _URL_TAGS + "apply_tags_to_utub_urls"
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
    COPY_URLS_MULTI = _URLS + "copy_urls_to_utubs"
    DELETE_URLS_BULK = _URLS + "delete_urls_from_utub"


class USER_ROUTES:
    _USERS = "users."
    LOGOUT = _USERS + "logout"
    PRIVACY = _USERS + "privacy_policy"
    TERMS = _USERS + "terms_and_conditions"
    SETTINGS = _USERS + "settings"
    CHANGE_USERNAME = _USERS + "change_username"
    CHANGE_PASSWORD = _USERS + "change_password"
    CHANGE_EMAIL = _USERS + "change_email"
    DELETE_ACCOUNT = _USERS + "delete_account"
    LOGOUT_EVERYWHERE = _USERS + "logout_everywhere"
    DATA_EXPORT = _USERS + "data_export"
    UPDATE_PREFERENCES = _USERS + "update_preferences"
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


class METRICS_ROUTES:
    _METRICS = "metrics."
    INGEST = _METRICS + "ingest"
    QUERY_TOP = _METRICS + "query_top"
    QUERY_TIMESERIES = _METRICS + "query_timeseries"
    QUERY_SUMMARY = _METRICS + "query_summary"
    QUERY_GROUPED_TIMESERIES = _METRICS + "query_grouped_timeseries"
    QUERY_FLOW = _METRICS + "query_flow"
    QUERY_GAUGES_TIMESERIES = _METRICS + "query_gauges_timeseries"
    QUERY_LATENCY = _METRICS + "query_latency"
    QUERY_LATENCY_TIMESERIES = _METRICS + "query_latency_timeseries"


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
    CO_MEMBER_CANDIDATES = _API_V1 + "api_v1_get_co_member_candidates"
    MODIFY_MEMBER_ROLE = _API_V1 + "api_v1_modify_member_role"
    TRANSFER_UTUB_OWNERSHIP = _API_V1 + "api_v1_transfer_utub_ownership"
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
    METRICS = METRICS_ROUTES
    SEARCH = SEARCH_ROUTES
    UTUBS = UTUB_ROUTES


class JsRoute(NamedTuple):
    """A frontend-exposed route: its Flask endpoint and URL placeholder kwargs.

    `placeholders` holds the negative-int URL kwargs the frontend substitutes
    at call time (`utub_id=-1`, `utub_url_id=-2`, `utub_tag_id=-3`,
    `user_id=-4`). The tables below are readable without a request context,
    so tooling can inspect them without rendering URLs.
    """

    endpoint: str
    placeholders: dict[str, int]


JS_ROUTES: dict[str, JsRoute] = {
    # UTub routes
    "home": JsRoute(UTUB_ROUTES.HOME, {}),
    "createUTub": JsRoute(UTUB_ROUTES.CREATE_UTUB, {}),
    "getUTubs": JsRoute(UTUB_ROUTES.GET_UTUBS, {}),
    "getUTub": JsRoute(UTUB_ROUTES.GET_SINGLE_UTUB, {"utub_id": -1}),
    "deleteUTub": JsRoute(UTUB_ROUTES.DELETE_UTUB, {"utub_id": -1}),
    "updateUTubName": JsRoute(UTUB_ROUTES.UPDATE_UTUB_NAME, {"utub_id": -1}),
    "updateUTubDescription": JsRoute(UTUB_ROUTES.UPDATE_UTUB_DESC, {"utub_id": -1}),
    # URL routes
    "getURL": JsRoute(URL_ROUTES.GET_URL, {"utub_id": -1, "utub_url_id": -2}),
    "createURL": JsRoute(URL_ROUTES.CREATE_URL, {"utub_id": -1}),
    "deleteURL": JsRoute(URL_ROUTES.DELETE_URL, {"utub_id": -1, "utub_url_id": -2}),
    "updateURL": JsRoute(URL_ROUTES.UPDATE_URL, {"utub_id": -1, "utub_url_id": -2}),
    "updateURLTitle": JsRoute(
        URL_ROUTES.UPDATE_URL_TITLE, {"utub_id": -1, "utub_url_id": -2}
    ),
    "copyURLsToUtubs": JsRoute(URL_ROUTES.COPY_URLS_MULTI, {}),
    "bulkDeleteURLs": JsRoute(URL_ROUTES.DELETE_URLS_BULK, {"utub_id": -1}),
    # UTub URL Tag routes
    "createURLTag": JsRoute(
        URL_TAG_ROUTES.CREATE_URL_TAG, {"utub_id": -1, "utub_url_id": -2}
    ),
    "createURLTagsBatch": JsRoute(
        URL_TAG_ROUTES.BATCH_ADD_URL_TAGS, {"utub_id": -1, "utub_url_id": -2}
    ),
    "applyTagsToURLs": JsRoute(URL_TAG_ROUTES.APPLY_TAGS_TO_URLS, {"utub_id": -1}),
    "deleteURLTag": JsRoute(
        URL_TAG_ROUTES.DELETE_URL_TAG,
        {"utub_id": -1, "utub_url_id": -2, "utub_tag_id": -3},
    ),
    # UTub Tag routes
    "createUTubTag": JsRoute(UTUB_TAG_ROUTES.CREATE_UTUB_TAG, {"utub_id": -1}),
    "deleteUTubTag": JsRoute(
        UTUB_TAG_ROUTES.DELETE_UTUB_TAG, {"utub_id": -1, "utub_tag_id": -2}
    ),
    # Member routes
    "createMember": JsRoute(MEMBER_ROUTES.CREATE_MEMBER, {"utub_id": -1}),
    "coMemberCandidates": JsRoute(MEMBER_ROUTES.CO_MEMBER_CANDIDATES, {"utub_id": -1}),
    "removeMember": JsRoute(
        MEMBER_ROUTES.REMOVE_MEMBER, {"utub_id": -1, "user_id": -4}
    ),
    "modifyMemberRole": JsRoute(
        MEMBER_ROUTES.MODIFY_MEMBER_ROLE, {"utub_id": -1, "user_id": -4}
    ),
    "transferUtubOwnership": JsRoute(
        MEMBER_ROUTES.TRANSFER_UTUB_OWNERSHIP, {"utub_id": -1}
    ),
    # Splash routes
    "login": JsRoute(SPLASH_ROUTES.LOGIN, {}),
    "register": JsRoute(SPLASH_ROUTES.REGISTER, {}),
    "confirmEmailAfterRegister": JsRoute(SPLASH_ROUTES.CONFIRM_EMAIL, {}),
    "sendValidationEmail": JsRoute(SPLASH_ROUTES.SEND_VALIDATION_EMAIL, {}),
    "resendRegistrationEmail": JsRoute(SPLASH_ROUTES.RESEND_REGISTRATION_EMAIL, {}),
    "forgotPassword": JsRoute(SPLASH_ROUTES.FORGOT_PASSWORD_PAGE, {}),
    "oauthGoogleLogin": JsRoute(OAUTH_ROUTES.GOOGLE_LOGIN, {}),
    "oauthGithubLogin": JsRoute(OAUTH_ROUTES.GITHUB_LOGIN, {}),
    # Util routes
    "errorPage": JsRoute(SPLASH_ROUTES.ERROR_PAGE, {}),
    # Logout
    "logout": JsRoute(USER_ROUTES.LOGOUT, {}),
    # Contact
    "contactUs": JsRoute(ACCOUNT_AND_SETTING_ROUTES.CONTACT_US_SUBMIT, {}),
    # Search
    "crossUtubSearch": JsRoute(SEARCH_ROUTES.SEARCH, {}),
    # Metrics ingest (emitted from every page)
    "metricsIngest": JsRoute(METRICS_ROUTES.INGEST, {}),
}

ADMIN_JS_ROUTES: dict[str, JsRoute] = {
    "adminMetricsPage": JsRoute(ADMIN_ROUTES.METRICS_PAGE, {}),
    # Metrics query routes (admin dashboard only)
    "metricsQueryTop": JsRoute(METRICS_ROUTES.QUERY_TOP, {}),
    "metricsQueryTimeseries": JsRoute(METRICS_ROUTES.QUERY_TIMESERIES, {}),
    "metricsQuerySummary": JsRoute(METRICS_ROUTES.QUERY_SUMMARY, {}),
    "metricsQueryGroupedTimeseries": JsRoute(
        METRICS_ROUTES.QUERY_GROUPED_TIMESERIES, {}
    ),
    "metricsQueryFlow": JsRoute(METRICS_ROUTES.QUERY_FLOW, {}),
    "metricsQueryGaugesTimeseries": JsRoute(METRICS_ROUTES.QUERY_GAUGES_TIMESERIES, {}),
    "metricsQueryLatency": JsRoute(METRICS_ROUTES.QUERY_LATENCY, {}),
    "metricsQueryLatencyTimeseries": JsRoute(
        METRICS_ROUTES.QUERY_LATENCY_TIMESERIES, {}
    ),
}


# JS linkage invariant. Every `@api_route` endpoint must be reachable through
# one of four channels (the two maps below never combine with another channel):
#   1. a `JS_ROUTES` / `ADMIN_JS_ROUTES` key (shipped in `APP_CONFIG.routes`);
#   2. a Jinja `url_for('<endpoint>')` reference in `backend/templates`
#      (typically a `data-*-url` attribute the frontend reads);
#   3. an `INDIRECT_JS_ENDPOINTS` entry below: the web frontend calls the
#      endpoint, but gets its URL another way (its own page URL, a URL built
#      server-side), so channels 1-2 cannot see the call;
#   4. a `NO_JS_ENDPOINTS` entry below, giving the reason nothing in the web
#      frontend calls the endpoint at all.
# `flask endpoints audit --strict` (`make audit-endpoints`) enforces this, and
# also flags `INDIRECT_JS_ENDPOINTS` / `NO_JS_ENDPOINTS` entries that name a
# dead endpoint, one that already has a key or template reference, or one
# listed in both maps. Never add an entry for an endpoint that could simply get
# a route key or a template `url_for`: link it instead.


class IndirectJsSource(StrEnum):
    PAGE_SELF_URL = "page-self-url"
    SERVER_BUILT_URL = "server-built-url"


# Keys are exact endpoints only (no `<blueprint>.*` wildcard): each entry names
# one frontend caller.
INDIRECT_JS_ENDPOINTS: dict[str, IndirectJsSource] = {
    # frontend/splash/reset-password-form.ts POSTs to its own page URL
    # (window.location.pathname).
    "splash.reset_password": IndirectJsSource.PAGE_SELF_URL,
    # frontend/settings/connected-accounts.ts reads a `data-action-url` whose
    # per-provider URL is built server-side (linking_service.py) into the
    # settings page's template context, not via a literal template url_for.
    "users.link_oauth_provider": IndirectJsSource.SERVER_BUILT_URL,
    "users.unlink_oauth_provider": IndirectJsSource.SERVER_BUILT_URL,
}


class NoJsReason(StrEnum):
    MOBILE_API = "mobile-api"
    OAUTH_CALLBACK = "oauth-callback"
    BROWSER_REDIRECT = "browser-redirect"
    INFRA_PROBE = "infra-probe"


# Keys are exact endpoints, or `<blueprint>.*` for a whole blueprint. A
# `<blueprint>.*` key matches only endpoints whose blueprint is exactly that
# name, not endpoints of blueprints nested under it. Exact keys win over
# blueprint-prefix keys. Entries here have no web-JS caller at all; an
# endpoint the frontend calls belongs in `INDIRECT_JS_ENDPOINTS` instead.
NO_JS_ENDPOINTS: dict[str, NoJsReason] = {
    # Bearer-token API consumed by the mobile app, never the web frontend.
    "api_v1.*": NoJsReason.MOBILE_API,
    # Container/uptime health check.
    "system.health": NoJsReason.INFRA_PROBE,
    # OAuth provider redirects back to these; the browser follows them.
    "splash.google_callback": NoJsReason.OAUTH_CALLBACK,
    "splash.github_callback": NoJsReason.OAUTH_CALLBACK,
    # Redirect target built server-side (linking_service, account_service).
    "splash.oauth_link": NoJsReason.BROWSER_REDIRECT,
}


def generate_routes_js() -> dict[str, str]:
    """
    Generate routes configuration for frontend JavaScript.
    Returns a dict that can be passed to Jinja and converted to JSON.
    """
    return {
        key: url_for(route.endpoint, **route.placeholders)
        for key, route in JS_ROUTES.items()
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
        key: url_for(route.endpoint, **route.placeholders)
        for key, route in ADMIN_JS_ROUTES.items()
    }
