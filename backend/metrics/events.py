from __future__ import annotations

from enum import IntEnum, StrEnum


class EventCategory(StrEnum):
    API = "api"
    DOMAIN = "domain"
    UI = "ui"


# Wire-format identifiers for the auto-injected `device_type` UI dimension.
# Int values are shipped across both the backend Pydantic boundary and the
# frontend metrics-client (via APP_CONFIG.constants.DEVICE_TYPE) so the two
# layers reference a single source of truth instead of duplicated string literals.
class DeviceType(IntEnum):
    MOBILE = 1
    DESKTOP = 2


# Wire/JSONB key for the auto-injected device_type dimension. Defined once
# so middleware, writer, and query layers reference the same literal; also
# surfaced to the frontend via APP_CONFIG.constants.DEVICE_TYPE_DIM_KEY.
DEVICE_TYPE_DIM_KEY: str = "device_type"


class EventName(StrEnum):
    # API — auto-instrumented via middleware
    API_HIT = "api_hit"
    API_METRICS_INGEST_BATCH = "api_metrics_ingest_batch"

    # Domain — explicit record_event() calls in service layer
    EMAIL_VERIFIED = "email_verified"
    LOGIN_FAILURE = "login_failure"
    LOGIN_SUCCESS = "login_success"
    MEMBER_ADDED = "member_added"
    MEMBER_REMOVED = "member_removed"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    REGISTER_SUCCESS = "register_success"
    TAG_APPLIED = "tag_applied"
    TAG_DELETED = "tag_deleted"
    TAG_REMOVED = "tag_removed"
    URL_ACCESSED = "url_accessed"
    URL_ADDED_TO_UTUB = "url_added_to_utub"
    URL_REMOVED_FROM_UTUB = "url_removed_from_utub"
    URL_STRING_UPDATED = "url_string_updated"
    URL_TITLE_UPDATED = "url_title_updated"
    UTUB_CREATED = "utub_created"
    UTUB_DELETED = "utub_deleted"
    UTUB_DESC_UPDATED = "utub_desc_updated"
    UTUB_OPENED = "utub_opened"
    UTUB_TAG_CREATED = "utub_tag_created"
    UTUB_TITLE_UPDATED = "utub_title_updated"

    # UI — browser-side emit() shipped to POST /api/metrics
    # — UTubs
    UI_UTUB_SELECT = "ui_utub_select"
    UI_UTUB_CREATE_OPEN = "ui_utub_create_open"
    UI_UTUB_DELETE_OPEN = "ui_utub_delete_open"
    UI_UTUB_DELETE_CONFIRM = "ui_utub_delete_confirm"
    UI_UTUB_DELETE_CANCEL = "ui_utub_delete_cancel"
    UI_UTUB_NAME_EDIT_OPEN = "ui_utub_name_edit_open"
    UI_UTUB_DESC_EDIT_OPEN = "ui_utub_desc_edit_open"
    # — URLs
    UI_URL_ACCESS = "ui_url_access"
    UI_URL_CARD_CLICK = "ui_url_card_click"
    UI_URL_CREATE_OPEN = "ui_url_create_open"
    UI_URL_TITLE_EDIT_OPEN = "ui_url_title_edit_open"
    UI_URL_STRING_EDIT_OPEN = "ui_url_string_edit_open"
    UI_URL_DELETE_OPEN = "ui_url_delete_open"
    UI_URL_DELETE_CONFIRM = "ui_url_delete_confirm"
    UI_URL_DELETE_CANCEL = "ui_url_delete_cancel"
    UI_URL_COPY = "ui_url_copy"
    UI_URL_ACCESS_WARNING = "ui_url_access_warning"
    UI_URL_ACCESS_WARNING_DISMISS = "ui_url_access_warning_dismiss"
    # — Search
    UI_UTUB_SEARCH_OPEN = "ui_utub_search_open"
    UI_UTUB_SEARCH_CLOSE = "ui_utub_search_close"
    UI_URL_SEARCH_OPEN = "ui_url_search_open"
    UI_URL_SEARCH_CLOSE = "ui_url_search_close"
    # — Tags
    UI_TAG_APPLY = "ui_tag_apply"
    UI_TAG_REMOVE = "ui_tag_remove"
    UI_TAG_CREATE_OPEN = "ui_tag_create_open"
    UI_TAG_DELETE_OPEN = "ui_tag_delete_open"
    UI_TAG_DELETE_CONFIRM = "ui_tag_delete_confirm"
    UI_TAG_DELETE_CANCEL = "ui_tag_delete_cancel"
    UI_TAG_FILTER_TOGGLE = "ui_tag_filter_toggle"
    # — Members
    UI_MEMBER_INVITE_OPEN = "ui_member_invite_open"
    UI_MEMBER_REMOVE_OPEN = "ui_member_remove_open"
    UI_MEMBER_REMOVE_CONFIRM = "ui_member_remove_confirm"
    UI_MEMBER_REMOVE_CANCEL = "ui_member_remove_cancel"
    UI_MEMBER_LEAVE_OPEN = "ui_member_leave_open"
    UI_MEMBER_LEAVE_CONFIRM = "ui_member_leave_confirm"
    UI_MEMBER_LEAVE_CANCEL = "ui_member_leave_cancel"
    # — Forms
    UI_FORM_SUBMIT = "ui_form_submit"
    UI_FORM_CANCEL = "ui_form_cancel"
    UI_VALIDATION_ERROR = "ui_validation_error"
    # — Layout & Navigation
    UI_DECK_COLLAPSE = "ui_deck_collapse"
    UI_DECK_EXPAND = "ui_deck_expand"
    UI_NAVBAR_MOBILE_MENU_OPEN = "ui_navbar_mobile_menu_open"
    UI_NAVBAR_MOBILE_MENU_CLOSE = "ui_navbar_mobile_menu_close"
    UI_MOBILE_NAV = "ui_mobile_nav"
    # — Auth / splash
    UI_LOGIN_SUBMIT = "ui_login_submit"
    UI_REGISTER_SUBMIT = "ui_register_submit"
    UI_FORGOT_PASSWORD_SUBMIT = "ui_forgot_password_submit"
    UI_AUTH_FORM_SWITCH = "ui_auth_form_switch"
    UI_AUTH_MODAL_OPEN = "ui_auth_modal_open"
    UI_RESET_PASSWORD_SUBMIT = "ui_reset_password_submit"
    UI_EMAIL_VALIDATION_SUBMIT = "ui_email_validation_submit"
    # — Contact / errors
    UI_CONTACT_SUBMIT = "ui_contact_submit"
    UI_ERROR_PAGE_REFRESH = "ui_error_page_refresh"
    UI_RATE_LIMIT_HIT = "ui_rate_limit_hit"


EVENT_CATEGORY: dict[EventName, EventCategory] = {
    # API
    EventName.API_HIT: EventCategory.API,
    EventName.API_METRICS_INGEST_BATCH: EventCategory.API,
    # Domain
    EventName.EMAIL_VERIFIED: EventCategory.DOMAIN,
    EventName.LOGIN_FAILURE: EventCategory.DOMAIN,
    EventName.LOGIN_SUCCESS: EventCategory.DOMAIN,
    EventName.MEMBER_ADDED: EventCategory.DOMAIN,
    EventName.MEMBER_REMOVED: EventCategory.DOMAIN,
    EventName.PASSWORD_RESET_COMPLETED: EventCategory.DOMAIN,
    EventName.PASSWORD_RESET_REQUESTED: EventCategory.DOMAIN,
    EventName.REGISTER_SUCCESS: EventCategory.DOMAIN,
    EventName.TAG_APPLIED: EventCategory.DOMAIN,
    EventName.TAG_DELETED: EventCategory.DOMAIN,
    EventName.TAG_REMOVED: EventCategory.DOMAIN,
    EventName.URL_ACCESSED: EventCategory.DOMAIN,
    EventName.URL_ADDED_TO_UTUB: EventCategory.DOMAIN,
    EventName.URL_REMOVED_FROM_UTUB: EventCategory.DOMAIN,
    EventName.URL_STRING_UPDATED: EventCategory.DOMAIN,
    EventName.URL_TITLE_UPDATED: EventCategory.DOMAIN,
    EventName.UTUB_CREATED: EventCategory.DOMAIN,
    EventName.UTUB_DELETED: EventCategory.DOMAIN,
    EventName.UTUB_DESC_UPDATED: EventCategory.DOMAIN,
    EventName.UTUB_OPENED: EventCategory.DOMAIN,
    EventName.UTUB_TAG_CREATED: EventCategory.DOMAIN,
    EventName.UTUB_TITLE_UPDATED: EventCategory.DOMAIN,
    # UI
    EventName.UI_UTUB_SELECT: EventCategory.UI,
    EventName.UI_UTUB_CREATE_OPEN: EventCategory.UI,
    EventName.UI_UTUB_DELETE_OPEN: EventCategory.UI,
    EventName.UI_UTUB_DELETE_CONFIRM: EventCategory.UI,
    EventName.UI_UTUB_DELETE_CANCEL: EventCategory.UI,
    EventName.UI_UTUB_NAME_EDIT_OPEN: EventCategory.UI,
    EventName.UI_UTUB_DESC_EDIT_OPEN: EventCategory.UI,
    EventName.UI_URL_ACCESS: EventCategory.UI,
    EventName.UI_URL_CARD_CLICK: EventCategory.UI,
    EventName.UI_URL_CREATE_OPEN: EventCategory.UI,
    EventName.UI_URL_TITLE_EDIT_OPEN: EventCategory.UI,
    EventName.UI_URL_STRING_EDIT_OPEN: EventCategory.UI,
    EventName.UI_URL_DELETE_OPEN: EventCategory.UI,
    EventName.UI_URL_DELETE_CONFIRM: EventCategory.UI,
    EventName.UI_URL_DELETE_CANCEL: EventCategory.UI,
    EventName.UI_URL_COPY: EventCategory.UI,
    EventName.UI_URL_ACCESS_WARNING: EventCategory.UI,
    EventName.UI_URL_ACCESS_WARNING_DISMISS: EventCategory.UI,
    EventName.UI_UTUB_SEARCH_OPEN: EventCategory.UI,
    EventName.UI_UTUB_SEARCH_CLOSE: EventCategory.UI,
    EventName.UI_URL_SEARCH_OPEN: EventCategory.UI,
    EventName.UI_URL_SEARCH_CLOSE: EventCategory.UI,
    EventName.UI_TAG_APPLY: EventCategory.UI,
    EventName.UI_TAG_REMOVE: EventCategory.UI,
    EventName.UI_TAG_CREATE_OPEN: EventCategory.UI,
    EventName.UI_TAG_DELETE_OPEN: EventCategory.UI,
    EventName.UI_TAG_DELETE_CONFIRM: EventCategory.UI,
    EventName.UI_TAG_DELETE_CANCEL: EventCategory.UI,
    EventName.UI_TAG_FILTER_TOGGLE: EventCategory.UI,
    EventName.UI_MEMBER_INVITE_OPEN: EventCategory.UI,
    EventName.UI_MEMBER_REMOVE_OPEN: EventCategory.UI,
    EventName.UI_MEMBER_REMOVE_CONFIRM: EventCategory.UI,
    EventName.UI_MEMBER_REMOVE_CANCEL: EventCategory.UI,
    EventName.UI_MEMBER_LEAVE_OPEN: EventCategory.UI,
    EventName.UI_MEMBER_LEAVE_CONFIRM: EventCategory.UI,
    EventName.UI_MEMBER_LEAVE_CANCEL: EventCategory.UI,
    EventName.UI_FORM_SUBMIT: EventCategory.UI,
    EventName.UI_FORM_CANCEL: EventCategory.UI,
    EventName.UI_VALIDATION_ERROR: EventCategory.UI,
    EventName.UI_DECK_COLLAPSE: EventCategory.UI,
    EventName.UI_DECK_EXPAND: EventCategory.UI,
    EventName.UI_NAVBAR_MOBILE_MENU_OPEN: EventCategory.UI,
    EventName.UI_NAVBAR_MOBILE_MENU_CLOSE: EventCategory.UI,
    EventName.UI_MOBILE_NAV: EventCategory.UI,
    EventName.UI_LOGIN_SUBMIT: EventCategory.UI,
    EventName.UI_REGISTER_SUBMIT: EventCategory.UI,
    EventName.UI_FORGOT_PASSWORD_SUBMIT: EventCategory.UI,
    EventName.UI_AUTH_FORM_SWITCH: EventCategory.UI,
    EventName.UI_AUTH_MODAL_OPEN: EventCategory.UI,
    EventName.UI_RESET_PASSWORD_SUBMIT: EventCategory.UI,
    EventName.UI_EMAIL_VALIDATION_SUBMIT: EventCategory.UI,
    EventName.UI_CONTACT_SUBMIT: EventCategory.UI,
    EventName.UI_ERROR_PAGE_REFRESH: EventCategory.UI,
    EventName.UI_RATE_LIMIT_HIT: EventCategory.UI,
}


EVENT_DESCRIPTIONS: dict[EventName, str] = {
    # API
    EventName.API_HIT: "Every HTTP request (excl. static, health, /metrics)",
    EventName.API_METRICS_INGEST_BATCH: "Counter on every accepted POST /api/metrics batch, tagged with batch_size_bucket × transport × device_type for pipeline-health telemetry.",
    # Domain
    EventName.EMAIL_VERIFIED: "User email validated via the post-registration confirmation link",
    EventName.LOGIN_FAILURE: "Login attempt rejected, tagged with closed-set failure reason",
    EventName.LOGIN_SUCCESS: "Login succeeded on the fully-validated path (email_validated guard passed)",
    EventName.MEMBER_ADDED: "Member invited to a UTub",
    EventName.MEMBER_REMOVED: "Member removed from a UTub",
    EventName.PASSWORD_RESET_COMPLETED: "Password successfully reset via the reset-token flow",
    EventName.PASSWORD_RESET_REQUESTED: "Forgot-password email delivery attempted within the rate-limit window",
    EventName.REGISTER_SUCCESS: "New user account successfully registered",
    EventName.TAG_APPLIED: "Tag added to a URL",
    EventName.TAG_DELETED: "Tag deleted from a UTub (UTub-level destructive)",
    EventName.TAG_REMOVED: "Tag removed from a URL",
    EventName.URL_ACCESSED: "URL click-through (distinct from list)",
    EventName.URL_ADDED_TO_UTUB: "URL associated with a UTub (new or existing URL row)",
    EventName.URL_REMOVED_FROM_UTUB: "URL disassociated from a UTub",
    EventName.URL_STRING_UPDATED: "URL string changed on a UTub URL (distinct from title update)",
    EventName.URL_TITLE_UPDATED: "URL title edited",
    EventName.UTUB_CREATED: "New UTub created",
    EventName.UTUB_DELETED: "UTub deleted by owner",
    EventName.UTUB_DESC_UPDATED: "UTub description changed",
    EventName.UTUB_OPENED: "UTub explicitly opened/selected",
    EventName.UTUB_TAG_CREATED: "New tag vocabulary added to a UTub (distinct from TAG_APPLIED)",
    EventName.UTUB_TITLE_UPDATED: "UTub name changed",
    # UI
    EventName.UI_UTUB_SELECT: "UTub selected in sidebar",
    EventName.UI_UTUB_CREATE_OPEN: '"Create UTub" form opened',
    EventName.UI_UTUB_DELETE_OPEN: "UTub delete-confirm modal opened",
    EventName.UI_UTUB_DELETE_CONFIRM: "UTub delete confirmed",
    EventName.UI_UTUB_DELETE_CANCEL: "UTub delete-confirm modal dismissed",
    EventName.UI_UTUB_NAME_EDIT_OPEN: "UTub name edit form opened",
    EventName.UI_UTUB_DESC_EDIT_OPEN: "UTub description edit form opened",
    EventName.UI_URL_ACCESS: "URL accessed via UI",
    EventName.UI_URL_CARD_CLICK: "URL card clicked/expanded",
    EventName.UI_URL_CREATE_OPEN: '"Add URL" form opened',
    EventName.UI_URL_TITLE_EDIT_OPEN: "URL title edit form opened",
    EventName.UI_URL_STRING_EDIT_OPEN: "URL string edit form opened",
    EventName.UI_URL_DELETE_OPEN: "URL delete-confirm modal opened",
    EventName.UI_URL_DELETE_CONFIRM: "URL delete confirmed",
    EventName.UI_URL_DELETE_CANCEL: "URL delete-confirm modal dismissed",
    EventName.UI_URL_COPY: "URL copied to clipboard",
    EventName.UI_URL_ACCESS_WARNING: "Non-HTTP URL warning modal shown",
    EventName.UI_URL_ACCESS_WARNING_DISMISS: "Non-HTTP URL warning dismissed (no access)",
    EventName.UI_UTUB_SEARCH_OPEN: "UTub search box opened",
    EventName.UI_UTUB_SEARCH_CLOSE: "UTub search box closed",
    EventName.UI_URL_SEARCH_OPEN: "URL search box opened",
    EventName.UI_URL_SEARCH_CLOSE: "URL search box closed",
    EventName.UI_TAG_APPLY: "Tag applied from picker",
    EventName.UI_TAG_REMOVE: "Tag removed from URL",
    EventName.UI_TAG_CREATE_OPEN: '"Create tag" input opened',
    EventName.UI_TAG_DELETE_OPEN: "Tag delete-confirm modal opened",
    EventName.UI_TAG_DELETE_CONFIRM: "Tag delete confirmed",
    EventName.UI_TAG_DELETE_CANCEL: "Tag delete-confirm modal dismissed",
    EventName.UI_TAG_FILTER_TOGGLE: "Tag filter toggled on/off",
    EventName.UI_MEMBER_INVITE_OPEN: "Member invite form opened",
    EventName.UI_MEMBER_REMOVE_OPEN: "Member-remove confirm modal opened",
    EventName.UI_MEMBER_REMOVE_CONFIRM: "Member removal confirmed",
    EventName.UI_MEMBER_REMOVE_CANCEL: "Member-remove confirm modal dismissed",
    EventName.UI_MEMBER_LEAVE_OPEN: "Self-leave confirm modal opened",
    EventName.UI_MEMBER_LEAVE_CONFIRM: "Self-removal from UTub confirmed",
    EventName.UI_MEMBER_LEAVE_CANCEL: "Self-leave confirm modal dismissed",
    EventName.UI_FORM_SUBMIT: "Form submitted",
    EventName.UI_FORM_CANCEL: "Form cancelled/dismissed",
    EventName.UI_VALIDATION_ERROR: "Client-side validation error shown",
    EventName.UI_DECK_COLLAPSE: "Deck collapsed",
    EventName.UI_DECK_EXPAND: "Deck expanded",
    EventName.UI_NAVBAR_MOBILE_MENU_OPEN: "Mobile hamburger menu opened",
    EventName.UI_NAVBAR_MOBILE_MENU_CLOSE: "Mobile hamburger menu closed",
    EventName.UI_MOBILE_NAV: "Mobile navbar section switch",
    EventName.UI_LOGIN_SUBMIT: "Login form submitted",
    EventName.UI_REGISTER_SUBMIT: "Registration form submitted",
    EventName.UI_FORGOT_PASSWORD_SUBMIT: "Forgot password form submitted",
    EventName.UI_AUTH_FORM_SWITCH: "Auth form switched",
    EventName.UI_AUTH_MODAL_OPEN: "Auth modal opened from initial CTA (navbar/header link) — not a form-to-form switch",
    EventName.UI_RESET_PASSWORD_SUBMIT: "Reset-password form submitted",
    EventName.UI_EMAIL_VALIDATION_SUBMIT: "Email-validation request submitted (manual click or post-register auto-send)",
    EventName.UI_CONTACT_SUBMIT: "Contact form submitted",
    EventName.UI_ERROR_PAGE_REFRESH: "User clicked refresh on the error page",
    EventName.UI_RATE_LIMIT_HIT: "429 rate limit response shown to user",
}
