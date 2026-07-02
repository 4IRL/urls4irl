from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from backend.metrics.events import (
    EVENT_CATEGORY,
    DeviceType,
    EventCategory,
    EventName,
)
from backend.metrics.tag_batch import TAGS_BATCH_SIZE_BUCKETS, URL_TAG_COUNT_BUCKETS
from backend.search.constants import SEARCH_FIELD_ORDER_VALUES

# ---------------------------------------------------------------------------
# Shared dimension literal aliases — extracted only when a literal appears in
# 3+ dim models with identical shape. Pair-shapes (e.g., search target,
# deck name) are intentionally NOT aliased: their dim classes are split per
# the "may diverge" comments below, so coupling their literal types would
# undo that intent. `TagScope` covers the create/delete-open/delete-confirm
# tag-action triplet (UTub-level vs URL-level tag operation).
# ---------------------------------------------------------------------------


SearchActive = Literal["true", "false"]
TagScope = Literal["utub", "url"]

# Home-page forms. Used by `_DimFormSubmit` and `_DimFormCancel` only — the
# splash/contact forms have dedicated `UI_<form>_SUBMIT` events instead of
# routing through `UI_FORM_SUBMIT`, so the convention is enforced via type
# narrowing rather than runtime guard.
HomeForm = Literal[
    "url_create",
    "url_title_edit",
    "url_string_edit",
    "utub_create",
    "utub_name_edit",
    "utub_desc_edit",
    "tag_create",
    "member_invite",
]

# All forms that can surface a client-side validation error — home forms
# plus the splash/contact forms (which DO emit `UI_VALIDATION_ERROR` for
# field-level errors even though their submit path is a dedicated event).
ValidationForm = Literal[
    "url_create",
    "url_title_edit",
    "url_string_edit",
    "utub_create",
    "utub_name_edit",
    "utub_desc_edit",
    "tag_create",
    "member_invite",
    "login",
    "register",
    "forgot_password",
    "reset_password",
    "email_validation",
]


# ---------------------------------------------------------------------------
# Sentinel model — used by `validate_dimensions` to reject non-empty dims
# for events whose `DIMENSION_MODELS` entry is `None`. `_NoDims` has zero
# fields, so any caller-supplied key triggers `extra="forbid"` and a real
# `ValidationError` flows out — same shape as a per-event mismatch.
# ---------------------------------------------------------------------------


class _NoDims(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# UI base dimension model — every UI-category event inherits this so that
# `device_type` (auto-injected by the frontend metrics-client) is required
# uniformly. Adding fields here propagates to all UI events automatically.
# ---------------------------------------------------------------------------


def _reject_string_device_type(raw_value: object) -> object:
    """Block string inputs ("1", "2") for `device_type`.

    Pydantic v2 lax mode coerces stringified ints to `IntEnum` values.
    This before-validator rejects that path so only true int wire values
    (sent by the browser metrics-client) are accepted, matching the intent of
    `_DimApiHit.status_code: Annotated[int, Field(strict=True)]`.
    """
    if isinstance(raw_value, str):
        raise ValueError("device_type must be an integer, not a string")
    return raw_value


# `BeforeValidator` wraps `_reject_string_device_type` in a Pydantic v2
# before-validator that runs before type coercion, blocking string inputs.
_StrictDeviceType = Annotated[DeviceType, BeforeValidator(_reject_string_device_type)]


class UIBaseDimensions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_type: _StrictDeviceType


# ---------------------------------------------------------------------------
# UI dimension models — one per event whose Registry row documents a non-empty
# `Dimensions` cell. Sourced verbatim from
# backend/metrics/event_registry.py § EVENT_REGISTRY.
# ---------------------------------------------------------------------------


class _DimDeviceOnly(UIBaseDimensions):
    """UI event with no per-event dimensions beyond the inherited `device_type`."""


class _DimUtubSelect(UIBaseDimensions):
    search_active: SearchActive


class _DimUtubNameEditOpen(UIBaseDimensions):
    trigger: Literal["pencil_icon", "keyboard"]


class _DimUtubDescEditOpen(UIBaseDimensions):
    trigger: Literal["pencil_icon", "keyboard", "create_button"]


class _DimUrlAccess(UIBaseDimensions):
    trigger: Literal["corner_button", "url_text", "main_button"]
    search_active: SearchActive
    active_tag_count: int


class _DimUrlCardClick(UIBaseDimensions):
    search_active: SearchActive
    active_tag_count: int


class _DimUrlCopy(UIBaseDimensions):
    result: Literal["success", "failure"]


# Each search variant has its own dim class (one per `EventName`) so each
# event has a 1:1 grep-able dim model. UTub-search and URL-search classes
# share the same field shape today but may diverge as the search UI grows;
# keep them split.
class _DimUtubSearchOpen(UIBaseDimensions):
    target: Literal["utubs"]


class _DimUtubSearchClose(UIBaseDimensions):
    target: Literal["utubs"]


class _DimUrlSearchOpen(UIBaseDimensions):
    target: Literal["urls"]


class _DimUrlSearchClose(UIBaseDimensions):
    target: Literal["urls"]


class _DimCrossUtubSearchOpen(UIBaseDimensions):
    target: Literal["cross_utub"]


class _DimCrossUtubSearchClose(UIBaseDimensions):
    target: Literal["cross_utub"]
    trigger: Literal[
        "trigger_icon",
        "escape_key",
        "return_home",
        "deck_switch",
        "result_nav",
        "history_nav",
    ]


class _DimCrossUtubSearchRefresh(UIBaseDimensions):
    target: Literal["cross_utub"]


class _DimCrossUtubSearchResultAccess(UIBaseDimensions):
    target: Literal["cross_utub"]
    trigger: Literal["url_text", "corner_button"]


class _DimTagSearchOpen(UIBaseDimensions):
    target: Literal["tags"]


class _DimTagSearchClose(UIBaseDimensions):
    target: Literal["tags"]


class _DimMemberSearchOpen(UIBaseDimensions):
    target: Literal["members"]


class _DimMemberSearchClose(UIBaseDimensions):
    target: Literal["members"]


class _DimTagCreateOpen(UIBaseDimensions):
    scope: TagScope


class _DimTagDeleteOpen(UIBaseDimensions):
    scope: TagScope


class _DimTagDeleteConfirm(UIBaseDimensions):
    scope: TagScope


class _DimTagDeleteCancel(UIBaseDimensions):
    scope: TagScope


class _DimTagSheetToggle(UIBaseDimensions):
    action: Literal["open", "close"]


class _DimFormSubmit(UIBaseDimensions):
    trigger: Literal["enter_key", "button_click"]
    form: HomeForm


class _DimFormCancel(UIBaseDimensions):
    trigger: Literal["escape_key", "cancel_button", "outside_click", "navigation"]
    form: HomeForm


class _DimValidationError(UIBaseDimensions):
    form: ValidationForm


# `_DimDeckCollapse` and `_DimDeckExpand` share the same field shape today,
# but are deliberately defined as separate classes (one per `EventName`) so
# each event has a 1:1 grep-able dim model. The pair may diverge as the
# deck UI grows; keep them split.
class _DimDeckCollapse(UIBaseDimensions):
    deck: Literal["members", "tags", "utubs"]


class _DimDeckExpand(UIBaseDimensions):
    deck: Literal["members", "tags", "utubs"]


# `_DimLhsCollapse` and `_DimLhsExpand` share the same field shape today,
# but are deliberately defined as separate classes (one per `EventName`) so
# each event has a 1:1 grep-able dim model.
class _DimLhsCollapse(UIBaseDimensions):
    source: Literal["seam", "url_header"]


class _DimLhsExpand(UIBaseDimensions):
    source: Literal["seam", "url_header"]


class _DimMobileNav(UIBaseDimensions):
    target: Literal["utubs", "urls", "members", "tags"]


class _DimAuthFormSwitch(UIBaseDimensions):
    target: Literal["login", "register", "forgot_password"]


class _DimAuthModalOpen(UIBaseDimensions):
    form: Literal["login", "register"]


class _DimAuthCancel(UIBaseDimensions):
    # `trigger` is a single-value Literal — only `navigation` is currently
    # emitted for auth-form abandonment. Widen this Literal and the
    # EVENT_REGISTRY tuple together when more triggers are added.
    form: Literal["login", "register"]
    trigger: Literal["navigation"]


class _DimEmailValidationSubmit(UIBaseDimensions):
    # `manual_click` covers the user explicitly clicking the resend button;
    # `auto_after_register` covers the modal auto-firing the request on
    # `shown.bs.modal` immediately after the post-register flow opens it.
    trigger: Literal["manual_click", "auto_after_register"]


# ---------------------------------------------------------------------------
# API dimension model — `API_HIT` keeps endpoint/method/status_code in dims so
# the `(bucketStart, eventName, dimensions)` unique constraint can distinguish
# per-(endpoint, method, status_code) buckets (D6).
# ---------------------------------------------------------------------------


class _DimApiHit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str
    method: Literal[
        "GET",
        "POST",
        "PATCH",
        "PUT",
        "DELETE",
        "HEAD",
        "OPTIONS",
    ]
    # `strict=True` blocks the default lax-mode coercion of `"200"` → `200`.
    status_code: Annotated[int, Field(strict=True)]
    device_type: _StrictDeviceType = Field(default=DeviceType.DESKTOP)


class _DimApiMetricsIngestBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch_size_bucket: Literal["1", "2-5", "6-25", "26-100"]
    transport: Literal["fetch", "beacon"]
    device_type: _StrictDeviceType = Field(default=DeviceType.DESKTOP)


# ---------------------------------------------------------------------------
# Domain dimension models — domain events with a closed-set non-device_type
# dim use a dedicated BaseModel (e.g. _DimLoginFailure,
# _DimUrlTrackingParamsStripped); all others use _DimDeviceOnly with
# device_type auto-injected by the writer.
# ---------------------------------------------------------------------------


# All domain events with only device_type auto-injection use `_DimDeviceOnly`;
# domain events with closed-set non-device_type dims use a dedicated BaseModel
# (e.g. `_DimTagsAppliedBatch`, `_DimCrossUtubSearchPerformed`).
class _DimTagsAppliedBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Closed set sourced from the same `TAGS_BATCH_SIZE_BUCKETS` constant fed to
    # the registry, so the audit set-compare between this Literal and the
    # registry tuple can never drift.
    batch_size_bucket: Literal[TAGS_BATCH_SIZE_BUCKETS]  # type: ignore[valid-type]
    device_type: _StrictDeviceType = Field(default=DeviceType.DESKTOP)


class _DimUrlAddedToUtub(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Closed set sourced from the same `URL_TAG_COUNT_BUCKETS` constant fed to
    # the registry, so the audit set-compare between this Literal and the
    # registry tuple can never drift.
    tag_count_bucket: Literal[URL_TAG_COUNT_BUCKETS]  # type: ignore[valid-type]
    device_type: _StrictDeviceType = Field(default=DeviceType.DESKTOP)


class _DimCrossUtubSearchPerformed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    has_results: Literal["true", "false"]
    # Closed set built from `SEARCH_FIELD_ORDER_VALUES` (the 15 ordered field
    # subsets) so this Literal can never drift from the registry tuple — both
    # derive from the same constant and the metrics audit set-compares them.
    field_order: Literal[SEARCH_FIELD_ORDER_VALUES]  # type: ignore[valid-type]
    device_type: _StrictDeviceType = Field(default=DeviceType.DESKTOP)


class _DimLoginFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal["unknown_user", "bad_password", "email_unverified", "oauth_only"]
    device_type: _StrictDeviceType = Field(default=DeviceType.DESKTOP)


class _DimUrlCreateRejected(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal[
        "credentials_url",
        "invalid_url",
        "unexpected_error",
        "url_already_in_utub",
    ]
    device_type: _StrictDeviceType = Field(default=DeviceType.DESKTOP)


class _DimUrlTrackingParamsStripped(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stripped: Literal["true", "false"]
    device_type: _StrictDeviceType = Field(default=DeviceType.DESKTOP)


class _DimRegisterRejected(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal["email_taken", "username_taken", "unvalidated_email"]
    device_type: _StrictDeviceType = Field(default=DeviceType.DESKTOP)


# ---------------------------------------------------------------------------
# DIMENSION_MODELS — every member of EventName keyed. `None` for events
# without dimensions. Order mirrors `EventName` for review-friendliness.
# ---------------------------------------------------------------------------


DIMENSION_MODELS: dict[EventName, type[BaseModel] | None] = {
    # API
    EventName.API_HIT: _DimApiHit,
    EventName.API_METRICS_INGEST_BATCH: _DimApiMetricsIngestBatch,
    # Domain events carry only device_type; auto-injected by MetricsWriter.record() from request context.
    # `LOGIN_FAILURE` is the only domain event with a closed-set extra dim (`reason`).
    EventName.CROSS_UTUB_SEARCH_PERFORMED: _DimCrossUtubSearchPerformed,
    EventName.EMAIL_VERIFIED: _DimDeviceOnly,
    EventName.LOGIN_FAILURE: _DimLoginFailure,
    EventName.LOGIN_SUCCESS: _DimDeviceOnly,
    EventName.MEMBER_ADDED: _DimDeviceOnly,
    EventName.MEMBER_REMOVED: _DimDeviceOnly,
    EventName.PASSWORD_RESET_COMPLETED: _DimDeviceOnly,
    EventName.PASSWORD_RESET_REQUESTED: _DimDeviceOnly,
    EventName.REGISTER_REJECTED: _DimRegisterRejected,
    EventName.REGISTER_SUCCESS: _DimDeviceOnly,
    EventName.TAG_APPLIED: _DimDeviceOnly,
    EventName.TAGS_APPLIED_BATCH: _DimTagsAppliedBatch,
    EventName.TAG_DELETED: _DimDeviceOnly,
    EventName.TAG_REMOVED: _DimDeviceOnly,
    EventName.URL_ACCESSED: _DimDeviceOnly,
    EventName.URL_ADDED_TO_UTUB: _DimUrlAddedToUtub,
    EventName.URL_CREATE_REJECTED: _DimUrlCreateRejected,
    EventName.URL_REMOVED_FROM_UTUB: _DimDeviceOnly,
    EventName.URL_STRING_UPDATED: _DimDeviceOnly,
    EventName.URL_TITLE_UPDATED: _DimDeviceOnly,
    EventName.URL_TRACKING_PARAMS_STRIPPED: _DimUrlTrackingParamsStripped,
    EventName.UTUB_CREATED: _DimDeviceOnly,
    EventName.UTUB_DELETED: _DimDeviceOnly,
    EventName.UTUB_DESC_UPDATED: _DimDeviceOnly,
    EventName.UTUB_OPENED: _DimDeviceOnly,
    EventName.UTUB_TAG_CREATED: _DimDeviceOnly,
    EventName.UTUB_TITLE_UPDATED: _DimDeviceOnly,
    # UI — UTubs
    EventName.UI_UTUB_SELECT: _DimUtubSelect,
    EventName.UI_UTUB_CREATE_OPEN: _DimDeviceOnly,
    EventName.UI_UTUB_DELETE_OPEN: _DimDeviceOnly,
    EventName.UI_UTUB_DELETE_CONFIRM: _DimDeviceOnly,
    EventName.UI_UTUB_DELETE_CANCEL: _DimDeviceOnly,
    EventName.UI_UTUB_NAME_EDIT_OPEN: _DimUtubNameEditOpen,
    EventName.UI_UTUB_DESC_EDIT_OPEN: _DimUtubDescEditOpen,
    # UI — URLs
    EventName.UI_URL_ACCESS: _DimUrlAccess,
    EventName.UI_URL_CARD_CLICK: _DimUrlCardClick,
    EventName.UI_URL_CREATE_OPEN: _DimDeviceOnly,
    EventName.UI_URL_TITLE_EDIT_OPEN: _DimDeviceOnly,
    EventName.UI_URL_STRING_EDIT_OPEN: _DimDeviceOnly,
    EventName.UI_URL_DELETE_OPEN: _DimDeviceOnly,
    EventName.UI_URL_DELETE_CONFIRM: _DimDeviceOnly,
    EventName.UI_URL_DELETE_CANCEL: _DimDeviceOnly,
    EventName.UI_URL_COPY: _DimUrlCopy,
    EventName.UI_URL_ACCESS_WARNING: _DimDeviceOnly,
    EventName.UI_URL_ACCESS_WARNING_DISMISS: _DimDeviceOnly,
    # UI — Search
    EventName.UI_UTUB_SEARCH_OPEN: _DimUtubSearchOpen,
    EventName.UI_UTUB_SEARCH_CLOSE: _DimUtubSearchClose,
    EventName.UI_URL_SEARCH_OPEN: _DimUrlSearchOpen,
    EventName.UI_URL_SEARCH_CLOSE: _DimUrlSearchClose,
    EventName.UI_CROSS_UTUB_SEARCH_OPEN: _DimCrossUtubSearchOpen,
    EventName.UI_CROSS_UTUB_SEARCH_CLOSE: _DimCrossUtubSearchClose,
    EventName.UI_CROSS_UTUB_SEARCH_REFRESH: _DimCrossUtubSearchRefresh,
    EventName.UI_CROSS_UTUB_SEARCH_RESULT_ACCESS: _DimCrossUtubSearchResultAccess,
    EventName.UI_TAG_SEARCH_OPEN: _DimTagSearchOpen,
    EventName.UI_TAG_SEARCH_CLOSE: _DimTagSearchClose,
    EventName.UI_MEMBER_SEARCH_OPEN: _DimMemberSearchOpen,
    EventName.UI_MEMBER_SEARCH_CLOSE: _DimMemberSearchClose,
    # UI — Tags
    EventName.UI_TAG_APPLY: _DimDeviceOnly,
    EventName.UI_TAG_REMOVE: _DimDeviceOnly,
    EventName.UI_TAG_CREATE_OPEN: _DimTagCreateOpen,
    EventName.UI_TAG_DELETE_OPEN: _DimTagDeleteOpen,
    EventName.UI_TAG_DELETE_CONFIRM: _DimTagDeleteConfirm,
    EventName.UI_TAG_DELETE_CANCEL: _DimTagDeleteCancel,
    EventName.UI_TAG_FILTER_TOGGLE: _DimDeviceOnly,
    EventName.UI_TAG_SHEET_TOGGLE: _DimTagSheetToggle,
    # UI — Members
    EventName.UI_MEMBER_INVITE_OPEN: _DimDeviceOnly,
    EventName.UI_MEMBER_REMOVE_OPEN: _DimDeviceOnly,
    EventName.UI_MEMBER_REMOVE_CONFIRM: _DimDeviceOnly,
    EventName.UI_MEMBER_REMOVE_CANCEL: _DimDeviceOnly,
    EventName.UI_MEMBER_LEAVE_OPEN: _DimDeviceOnly,
    EventName.UI_MEMBER_LEAVE_CONFIRM: _DimDeviceOnly,
    EventName.UI_MEMBER_LEAVE_CANCEL: _DimDeviceOnly,
    # UI — Forms
    EventName.UI_FORM_SUBMIT: _DimFormSubmit,
    EventName.UI_FORM_CANCEL: _DimFormCancel,
    EventName.UI_VALIDATION_ERROR: _DimValidationError,
    # UI — Layout & Navigation
    EventName.UI_DECK_COLLAPSE: _DimDeckCollapse,
    EventName.UI_DECK_EXPAND: _DimDeckExpand,
    EventName.UI_LHS_COLLAPSE: _DimLhsCollapse,
    EventName.UI_LHS_EXPAND: _DimLhsExpand,
    EventName.UI_NAVBAR_DROPDOWN_OPEN: _DimDeviceOnly,
    EventName.UI_NAVBAR_DROPDOWN_CLOSE: _DimDeviceOnly,
    EventName.UI_MOBILE_NAV: _DimMobileNav,
    # UI — Auth (splash)
    EventName.UI_LOGIN_SUBMIT: _DimDeviceOnly,
    EventName.UI_REGISTER_SUBMIT: _DimDeviceOnly,
    EventName.UI_FORGOT_PASSWORD_SUBMIT: _DimDeviceOnly,
    EventName.UI_AUTH_CANCEL: _DimAuthCancel,
    EventName.UI_AUTH_FORM_SWITCH: _DimAuthFormSwitch,
    EventName.UI_AUTH_MODAL_OPEN: _DimAuthModalOpen,
    EventName.UI_RESET_PASSWORD_SUBMIT: _DimDeviceOnly,
    EventName.UI_EMAIL_VALIDATION_SUBMIT: _DimEmailValidationSubmit,
    # UI — Contact / errors
    EventName.UI_CONTACT_SUBMIT: _DimDeviceOnly,
    EventName.UI_ERROR_PAGE_REFRESH: _DimDeviceOnly,
    EventName.UI_RATE_LIMIT_HIT: _DimDeviceOnly,
}


def get_all_dimension_keys() -> tuple[str, ...]:
    """Return the sorted union of every dimension field name across UI-category DIMENSION_MODELS entries.

    Skips entries where EVENT_CATEGORY[event_name] != EventCategory.UI so that
    non-browser event dimensions (e.g., API-hit endpoint/method/status_code) are
    never shipped to the frontend allow-list.

    Source of truth for the frontend allow-list filter shipped via
    APP_CONFIG.constants.DIMENSION_KEYS. Adding a field to a `_Dim<EventName>`
    model for a UI-category event here auto-propagates to the browser on next page load.
    """
    collected: set[str] = set()
    for event_name, dim_model in DIMENSION_MODELS.items():
        if dim_model is None:
            continue
        if EVENT_CATEGORY[event_name] != EventCategory.UI:
            continue
        collected.update(dim_model.model_fields.keys())
    return tuple(sorted(collected))


def validate_dimensions(event: EventName, dimensions: dict | None) -> None:
    """Validate `dimensions` against the per-event schema.

    Raises `pydantic.ValidationError` on shape mismatch. Returns `None` on
    success. Used by both the HTTP route layer and the `MetricsWriter` so
    internal callers and HTTP callers share the same validation pass.
    """
    model_class = DIMENSION_MODELS[event]
    if model_class is None:
        # No dims model — empty dict / None passes silently. Anything else is
        # rejected via the `_NoDims` sentinel so the caller gets a real
        # `ValidationError` with `Extra inputs are not permitted` rather than
        # a custom raise.
        if not dimensions:
            return
        _NoDims.model_validate(dimensions)
        return

    model_class.model_validate(dimensions or {})


__all__ = [
    "DIMENSION_MODELS",
    "UIBaseDimensions",
    "get_all_dimension_keys",
    "validate_dimensions",
]
