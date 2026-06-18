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
    CROSS_UTUB_SEARCH_PERFORMED = "cross_utub_search_performed"
    EMAIL_VERIFIED = "email_verified"
    LOGIN_FAILURE = "login_failure"
    LOGIN_SUCCESS = "login_success"
    MEMBER_ADDED = "member_added"
    MEMBER_REMOVED = "member_removed"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    REGISTER_REJECTED = "register_rejected"
    REGISTER_SUCCESS = "register_success"
    TAG_APPLIED = "tag_applied"
    TAG_DELETED = "tag_deleted"
    TAG_REMOVED = "tag_removed"
    URL_ACCESSED = "url_accessed"
    URL_ADDED_TO_UTUB = "url_added_to_utub"
    URL_CREATE_REJECTED = "url_create_rejected"
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
    UI_NAVBAR_DROPDOWN_OPEN = "ui_navbar_dropdown_open"
    UI_NAVBAR_DROPDOWN_CLOSE = "ui_navbar_dropdown_close"
    UI_MOBILE_NAV = "ui_mobile_nav"
    # — Auth / splash
    UI_LOGIN_SUBMIT = "ui_login_submit"
    UI_REGISTER_SUBMIT = "ui_register_submit"
    UI_FORGOT_PASSWORD_SUBMIT = "ui_forgot_password_submit"
    UI_AUTH_CANCEL = "ui_auth_cancel"
    UI_AUTH_FORM_SWITCH = "ui_auth_form_switch"
    UI_AUTH_MODAL_OPEN = "ui_auth_modal_open"
    UI_RESET_PASSWORD_SUBMIT = "ui_reset_password_submit"
    UI_EMAIL_VALIDATION_SUBMIT = "ui_email_validation_submit"
    # — Contact / errors
    UI_CONTACT_SUBMIT = "ui_contact_submit"
    UI_ERROR_PAGE_REFRESH = "ui_error_page_refresh"
    UI_RATE_LIMIT_HIT = "ui_rate_limit_hit"


# EVENT_CATEGORY and EVENT_DESCRIPTIONS are derived from the single source of
# truth in `backend.metrics.event_registry`. Re-exported here so existing
# callers continue to `from backend.metrics.events import EVENT_CATEGORY`.
# The import is intentionally placed AFTER `EventName` is fully defined so the
# `event_registry` module (which imports from this one) can resolve cleanly.
from backend.metrics.event_registry import (  # noqa: E402  (post-enum import)
    EVENT_CATEGORY,
    EVENT_DESCRIPTIONS,
)

__all__ = [
    "DEVICE_TYPE_DIM_KEY",
    "EVENT_CATEGORY",
    "EVENT_DESCRIPTIONS",
    "DeviceType",
    "EventCategory",
    "EventName",
]
