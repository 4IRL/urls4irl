from __future__ import annotations

from enum import StrEnum


class EventCategory(StrEnum):
    API = "api"
    DOMAIN = "domain"
    UI = "ui"


class EventName(StrEnum):
    # API (1) — auto-instrumented via middleware (Phase 2)
    API_HIT = "api_hit"

    # Domain (12) — explicit record_event() calls in service layer (Phase 3)
    UTUB_CREATED = "utub_created"
    UTUB_DELETED = "utub_deleted"
    UTUB_OPENED = "utub_opened"
    URL_ACCESSED = "url_accessed"
    TAG_APPLIED = "tag_applied"
    TAG_REMOVED = "tag_removed"
    TAG_DELETED = "tag_deleted"
    MEMBER_ADDED = "member_added"
    MEMBER_REMOVED = "member_removed"
    URL_TITLE_UPDATED = "url_title_updated"
    UTUB_TITLE_UPDATED = "utub_title_updated"
    UTUB_DESC_UPDATED = "utub_desc_updated"

    # UI (47) — browser-side emit() shipped to POST /api/metrics (Phase 5)
    # — UTubs (7)
    UI_UTUB_SELECT = "ui_utub_select"
    UI_UTUB_CREATE_OPEN = "ui_utub_create_open"
    UI_UTUB_DELETE_OPEN = "ui_utub_delete_open"
    UI_UTUB_DELETE_CONFIRM = "ui_utub_delete_confirm"
    UI_UTUB_DELETE_CANCEL = "ui_utub_delete_cancel"
    UI_UTUB_NAME_EDIT_OPEN = "ui_utub_name_edit_open"
    UI_UTUB_DESC_EDIT_OPEN = "ui_utub_desc_edit_open"
    # — URLs (11)
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
    # — Search (2)
    UI_SEARCH_OPEN = "ui_search_open"
    UI_SEARCH_CLOSE = "ui_search_close"
    # — Tags (7)
    UI_TAG_APPLY = "ui_tag_apply"
    UI_TAG_REMOVE = "ui_tag_remove"
    UI_TAG_CREATE_OPEN = "ui_tag_create_open"
    UI_TAG_DELETE_OPEN = "ui_tag_delete_open"
    UI_TAG_DELETE_CONFIRM = "ui_tag_delete_confirm"
    UI_TAG_DELETE_CANCEL = "ui_tag_delete_cancel"
    UI_TAG_FILTER_TOGGLE = "ui_tag_filter_toggle"
    # — Members (7)
    UI_MEMBER_INVITE_OPEN = "ui_member_invite_open"
    UI_MEMBER_REMOVE_OPEN = "ui_member_remove_open"
    UI_MEMBER_REMOVE_CONFIRM = "ui_member_remove_confirm"
    UI_MEMBER_REMOVE_CANCEL = "ui_member_remove_cancel"
    UI_MEMBER_LEAVE_OPEN = "ui_member_leave_open"
    UI_MEMBER_LEAVE_CONFIRM = "ui_member_leave_confirm"
    UI_MEMBER_LEAVE_CANCEL = "ui_member_leave_cancel"
    # — Forms (3)
    UI_FORM_SUBMIT = "ui_form_submit"
    UI_FORM_CANCEL = "ui_form_cancel"
    UI_VALIDATION_ERROR = "ui_validation_error"
    # — Layout & Navigation (5)
    UI_DECK_COLLAPSE = "ui_deck_collapse"
    UI_DECK_EXPAND = "ui_deck_expand"
    UI_NAVBAR_MOBILE_MENU_OPEN = "ui_navbar_mobile_menu_open"
    UI_NAVBAR_MOBILE_MENU_CLOSE = "ui_navbar_mobile_menu_close"
    UI_MOBILE_NAV = "ui_mobile_nav"
    # — Auth / splash (4)
    UI_LOGIN_SUBMIT = "ui_login_submit"
    UI_REGISTER_SUBMIT = "ui_register_submit"
    UI_FORGOT_PASSWORD_SUBMIT = "ui_forgot_password_submit"
    UI_AUTH_FORM_SWITCH = "ui_auth_form_switch"
    # — Errors (1)
    UI_RATE_LIMIT_HIT = "ui_rate_limit_hit"


EVENT_CATEGORY: dict[EventName, EventCategory] = {
    # API
    EventName.API_HIT: EventCategory.API,
    # Domain
    EventName.UTUB_CREATED: EventCategory.DOMAIN,
    EventName.UTUB_DELETED: EventCategory.DOMAIN,
    EventName.UTUB_OPENED: EventCategory.DOMAIN,
    EventName.URL_ACCESSED: EventCategory.DOMAIN,
    EventName.TAG_APPLIED: EventCategory.DOMAIN,
    EventName.TAG_REMOVED: EventCategory.DOMAIN,
    EventName.TAG_DELETED: EventCategory.DOMAIN,
    EventName.MEMBER_ADDED: EventCategory.DOMAIN,
    EventName.MEMBER_REMOVED: EventCategory.DOMAIN,
    EventName.URL_TITLE_UPDATED: EventCategory.DOMAIN,
    EventName.UTUB_TITLE_UPDATED: EventCategory.DOMAIN,
    EventName.UTUB_DESC_UPDATED: EventCategory.DOMAIN,
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
    EventName.UI_SEARCH_OPEN: EventCategory.UI,
    EventName.UI_SEARCH_CLOSE: EventCategory.UI,
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
    EventName.UI_RATE_LIMIT_HIT: EventCategory.UI,
}


EVENT_DESCRIPTIONS: dict[EventName, str] = {
    # API
    EventName.API_HIT: "Every HTTP request (excl. static, health, /metrics)",
    # Domain
    EventName.UTUB_CREATED: "New UTub created",
    EventName.UTUB_DELETED: "UTub deleted by owner",
    EventName.UTUB_OPENED: "UTub explicitly opened/selected",
    EventName.URL_ACCESSED: "URL click-through (distinct from list)",
    EventName.TAG_APPLIED: "Tag added to a URL",
    EventName.TAG_REMOVED: "Tag removed from a URL",
    EventName.TAG_DELETED: "Tag deleted from a UTub (UTub-level destructive)",
    EventName.MEMBER_ADDED: "Member invited to a UTub",
    EventName.MEMBER_REMOVED: "Member removed from a UTub",
    EventName.URL_TITLE_UPDATED: "URL title edited",
    EventName.UTUB_TITLE_UPDATED: "UTub name changed",
    EventName.UTUB_DESC_UPDATED: "UTub description changed",
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
    EventName.UI_SEARCH_OPEN: "Search box opened",
    EventName.UI_SEARCH_CLOSE: "Search box closed",
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
    EventName.UI_RATE_LIMIT_HIT: "429 rate limit response shown to user",
}
