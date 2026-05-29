import type { UIEventName } from "./metrics-client.js";

// Wire-format identifiers for UI events emitted via `emit()`. Each key mirrors
// the matching `EventName.UI_*` member in `backend/metrics/events.py`; the value
// is the wire string the backend Pydantic validator expects.
//
// Two compile-time checks keep this object in lockstep with the backend:
//   1. `satisfies Record<string, UIEventName>` — any value that is not a member
//      of `UIEventName` (derived from `api.d.ts` via `make generate-types`) is
//      a type error.
//   2. The `_exhaustive` assertion below — any `UIEventName` member missing
//      from `UI_EVENTS` values is a type error.
//
// Net effect: adding a new event on the backend without adding a constant here
// fails `make typecheck` / `make vite-build` immediately.
export const UI_EVENTS = {
  // — UTubs
  UI_UTUB_SELECT: "ui_utub_select",
  UI_UTUB_CREATE_OPEN: "ui_utub_create_open",
  UI_UTUB_DELETE_OPEN: "ui_utub_delete_open",
  UI_UTUB_DELETE_CONFIRM: "ui_utub_delete_confirm",
  UI_UTUB_DELETE_CANCEL: "ui_utub_delete_cancel",
  UI_UTUB_NAME_EDIT_OPEN: "ui_utub_name_edit_open",
  UI_UTUB_DESC_EDIT_OPEN: "ui_utub_desc_edit_open",

  // — URLs
  UI_URL_ACCESS: "ui_url_access",
  UI_URL_CARD_CLICK: "ui_url_card_click",
  UI_URL_CREATE_OPEN: "ui_url_create_open",
  UI_URL_TITLE_EDIT_OPEN: "ui_url_title_edit_open",
  UI_URL_STRING_EDIT_OPEN: "ui_url_string_edit_open",
  UI_URL_DELETE_OPEN: "ui_url_delete_open",
  UI_URL_DELETE_CONFIRM: "ui_url_delete_confirm",
  UI_URL_DELETE_CANCEL: "ui_url_delete_cancel",
  UI_URL_COPY: "ui_url_copy",
  UI_URL_ACCESS_WARNING: "ui_url_access_warning",
  UI_URL_ACCESS_WARNING_DISMISS: "ui_url_access_warning_dismiss",

  // — Search
  UI_SEARCH_OPEN: "ui_search_open",
  UI_SEARCH_CLOSE: "ui_search_close",

  // — Tags
  UI_TAG_APPLY: "ui_tag_apply",
  UI_TAG_REMOVE: "ui_tag_remove",
  UI_TAG_CREATE_OPEN: "ui_tag_create_open",
  UI_TAG_DELETE_OPEN: "ui_tag_delete_open",
  UI_TAG_DELETE_CONFIRM: "ui_tag_delete_confirm",
  UI_TAG_DELETE_CANCEL: "ui_tag_delete_cancel",
  UI_TAG_FILTER_TOGGLE: "ui_tag_filter_toggle",

  // — Members
  UI_MEMBER_INVITE_OPEN: "ui_member_invite_open",
  UI_MEMBER_REMOVE_OPEN: "ui_member_remove_open",
  UI_MEMBER_REMOVE_CONFIRM: "ui_member_remove_confirm",
  UI_MEMBER_REMOVE_CANCEL: "ui_member_remove_cancel",
  UI_MEMBER_LEAVE_OPEN: "ui_member_leave_open",
  UI_MEMBER_LEAVE_CONFIRM: "ui_member_leave_confirm",
  UI_MEMBER_LEAVE_CANCEL: "ui_member_leave_cancel",

  // — Forms
  UI_FORM_SUBMIT: "ui_form_submit",
  UI_FORM_CANCEL: "ui_form_cancel",
  UI_VALIDATION_ERROR: "ui_validation_error",

  // — Decks / navbar / mobile
  UI_DECK_COLLAPSE: "ui_deck_collapse",
  UI_DECK_EXPAND: "ui_deck_expand",
  UI_NAVBAR_MOBILE_MENU_OPEN: "ui_navbar_mobile_menu_open",
  UI_NAVBAR_MOBILE_MENU_CLOSE: "ui_navbar_mobile_menu_close",
  UI_MOBILE_NAV: "ui_mobile_nav",

  // — Auth / splash
  UI_LOGIN_SUBMIT: "ui_login_submit",
  UI_REGISTER_SUBMIT: "ui_register_submit",
  UI_FORGOT_PASSWORD_SUBMIT: "ui_forgot_password_submit",
  UI_AUTH_FORM_SWITCH: "ui_auth_form_switch",
  UI_AUTH_MODAL_OPEN: "ui_auth_modal_open",
  UI_RESET_PASSWORD_SUBMIT: "ui_reset_password_submit",
  UI_EMAIL_VALIDATION_SUBMIT: "ui_email_validation_submit",

  // — Contact / errors
  UI_CONTACT_SUBMIT: "ui_contact_submit",
  UI_ERROR_PAGE_REFRESH: "ui_error_page_refresh",
  UI_RATE_LIMIT_HIT: "ui_rate_limit_hit",
} as const satisfies Record<string, UIEventName>;

type _UiEventValues = (typeof UI_EVENTS)[keyof typeof UI_EVENTS];
type _MissingFromUiEvents = Exclude<UIEventName, _UiEventValues>;
const _exhaustive: [_MissingFromUiEvents] extends [never] ? true : false = true;
void _exhaustive;
