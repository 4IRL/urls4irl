from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.metrics.events import (
    EVENT_CATEGORY,
    DeviceType,
    EventCategory,
    EventName,
)

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
Form = Literal[
    "url_create",
    "url_title_edit",
    "url_string_edit",
    "utub_create",
    "utub_name_edit",
    "utub_desc_edit",
    "tag_create",
    "member_invite",
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


class UIBaseDimensions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_type: DeviceType


# ---------------------------------------------------------------------------
# UI dimension models — one per event whose Registry row documents a non-empty
# `Dimensions` cell. Sourced verbatim from
# plans/anonymous-metrics/anonymous-metrics-master.md § Event Registry.
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


# `_DimSearchOpen` and `_DimSearchClose` share the same field shape today,
# but are deliberately defined as separate classes (one per `EventName`) so
# each event has a 1:1 grep-able dim model. The pair may diverge as the
# search UI grows; keep them split.
class _DimSearchOpen(UIBaseDimensions):
    target: Literal["utubs", "urls"]


class _DimSearchClose(UIBaseDimensions):
    target: Literal["utubs", "urls"]


class _DimTagCreateOpen(UIBaseDimensions):
    scope: TagScope


class _DimTagDeleteOpen(UIBaseDimensions):
    scope: TagScope


class _DimTagDeleteConfirm(UIBaseDimensions):
    scope: TagScope


class _DimTagDeleteCancel(UIBaseDimensions):
    scope: TagScope


class _DimFormSubmit(UIBaseDimensions):
    trigger: Literal["enter_key", "button_click"]
    form: Form


class _DimFormCancel(UIBaseDimensions):
    trigger: Literal["escape_key", "cancel_button"]
    form: Form


class _DimValidationError(UIBaseDimensions):
    form: Form


# `_DimDeckCollapse` and `_DimDeckExpand` share the same field shape today,
# but are deliberately defined as separate classes (one per `EventName`) so
# each event has a 1:1 grep-able dim model. The pair may diverge as the
# deck UI grows; keep them split.
class _DimDeckCollapse(UIBaseDimensions):
    deck: Literal["members", "tags", "urls"]


class _DimDeckExpand(UIBaseDimensions):
    deck: Literal["members", "tags", "urls"]


class _DimMobileNav(UIBaseDimensions):
    target: Literal["utubs", "urls", "members", "tags"]


class _DimAuthFormSwitch(UIBaseDimensions):
    target: Literal["login", "register", "forgot_password"]


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


# ---------------------------------------------------------------------------
# DIMENSION_MODELS — every member of EventName keyed. `None` for events
# without dimensions. Order mirrors `EventName` for review-friendliness.
# ---------------------------------------------------------------------------


DIMENSION_MODELS: dict[EventName, type[BaseModel] | None] = {
    # API
    EventName.API_HIT: _DimApiHit,
    # Domain events carry no per-event dimensions; the MetricsWriter populates them server-side.
    EventName.UTUB_CREATED: None,
    EventName.UTUB_DELETED: None,
    EventName.UTUB_OPENED: None,
    EventName.URL_ACCESSED: None,
    EventName.TAG_APPLIED: None,
    EventName.TAG_REMOVED: None,
    EventName.TAG_DELETED: None,
    EventName.MEMBER_ADDED: None,
    EventName.MEMBER_REMOVED: None,
    EventName.URL_TITLE_UPDATED: None,
    EventName.UTUB_TITLE_UPDATED: None,
    EventName.UTUB_DESC_UPDATED: None,
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
    EventName.UI_SEARCH_OPEN: _DimSearchOpen,
    EventName.UI_SEARCH_CLOSE: _DimSearchClose,
    # UI — Tags
    EventName.UI_TAG_APPLY: _DimDeviceOnly,
    EventName.UI_TAG_REMOVE: _DimDeviceOnly,
    EventName.UI_TAG_CREATE_OPEN: _DimTagCreateOpen,
    EventName.UI_TAG_DELETE_OPEN: _DimTagDeleteOpen,
    EventName.UI_TAG_DELETE_CONFIRM: _DimTagDeleteConfirm,
    EventName.UI_TAG_DELETE_CANCEL: _DimTagDeleteCancel,
    EventName.UI_TAG_FILTER_TOGGLE: _DimDeviceOnly,
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
    EventName.UI_NAVBAR_MOBILE_MENU_OPEN: _DimDeviceOnly,
    EventName.UI_NAVBAR_MOBILE_MENU_CLOSE: _DimDeviceOnly,
    EventName.UI_MOBILE_NAV: _DimMobileNav,
    # UI — Auth (splash)
    EventName.UI_LOGIN_SUBMIT: _DimDeviceOnly,
    EventName.UI_REGISTER_SUBMIT: _DimDeviceOnly,
    EventName.UI_FORGOT_PASSWORD_SUBMIT: _DimDeviceOnly,
    EventName.UI_AUTH_FORM_SWITCH: _DimAuthFormSwitch,
    # UI — Errors
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
