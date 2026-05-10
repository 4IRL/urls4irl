from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.metrics.events import EventName

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
# UI dimension models — one per event whose Registry row documents a non-empty
# `Dimensions` cell. Sourced verbatim from
# plans/anonymous-metrics/anonymous-metrics-master.md § Event Registry.
# ---------------------------------------------------------------------------


class _DimUtubSelect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    search_active: SearchActive


class _DimUtubNameEditOpen(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trigger: Literal["pencil_icon", "keyboard"]


class _DimUtubDescEditOpen(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trigger: Literal["pencil_icon", "keyboard", "create_button"]


class _DimUrlAccess(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trigger: Literal["corner_button", "url_text", "main_button"]
    search_active: SearchActive
    active_tag_count: int


class _DimUrlCardClick(BaseModel):
    model_config = ConfigDict(extra="forbid")
    search_active: SearchActive
    active_tag_count: int


class _DimUrlCopy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result: Literal["success", "failure"]


# `_DimSearchOpen` and `_DimSearchClose` share the same field shape today,
# but are deliberately defined as separate classes (one per `EventName`) so
# each event has a 1:1 grep-able dim model. The pair may diverge as the
# search UI grows; keep them split.
class _DimSearchOpen(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: Literal["utubs", "urls"]


class _DimSearchClose(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: Literal["utubs", "urls"]


class _DimTagCreateOpen(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: TagScope


class _DimTagDeleteOpen(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: TagScope


class _DimTagDeleteConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: TagScope


class _DimTagDeleteCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: TagScope


class _DimFormSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trigger: Literal["enter_key", "button_click"]
    form: Form


class _DimFormCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trigger: Literal["escape_key", "cancel_button"]
    form: Form


class _DimValidationError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    form: Form


# `_DimDeckCollapse` and `_DimDeckExpand` share the same field shape today,
# but are deliberately defined as separate classes (one per `EventName`) so
# each event has a 1:1 grep-able dim model. The pair may diverge as the
# deck UI grows; keep them split.
class _DimDeckCollapse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deck: Literal["members", "tags", "urls"]


class _DimDeckExpand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deck: Literal["members", "tags", "urls"]


class _DimMobileNav(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: Literal["utubs", "urls", "members", "tags"]


class _DimAuthFormSwitch(BaseModel):
    model_config = ConfigDict(extra="forbid")
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
    EventName.UI_UTUB_CREATE_OPEN: None,
    EventName.UI_UTUB_DELETE_OPEN: None,
    EventName.UI_UTUB_DELETE_CONFIRM: None,
    EventName.UI_UTUB_DELETE_CANCEL: None,
    EventName.UI_UTUB_NAME_EDIT_OPEN: _DimUtubNameEditOpen,
    EventName.UI_UTUB_DESC_EDIT_OPEN: _DimUtubDescEditOpen,
    # UI — URLs
    EventName.UI_URL_ACCESS: _DimUrlAccess,
    EventName.UI_URL_CARD_CLICK: _DimUrlCardClick,
    EventName.UI_URL_CREATE_OPEN: None,
    EventName.UI_URL_TITLE_EDIT_OPEN: None,
    EventName.UI_URL_STRING_EDIT_OPEN: None,
    EventName.UI_URL_DELETE_OPEN: None,
    EventName.UI_URL_DELETE_CONFIRM: None,
    EventName.UI_URL_DELETE_CANCEL: None,
    EventName.UI_URL_COPY: _DimUrlCopy,
    EventName.UI_URL_ACCESS_WARNING: None,
    EventName.UI_URL_ACCESS_WARNING_DISMISS: None,
    # UI — Search
    EventName.UI_SEARCH_OPEN: _DimSearchOpen,
    EventName.UI_SEARCH_CLOSE: _DimSearchClose,
    # UI — Tags
    EventName.UI_TAG_APPLY: None,
    EventName.UI_TAG_REMOVE: None,
    EventName.UI_TAG_CREATE_OPEN: _DimTagCreateOpen,
    EventName.UI_TAG_DELETE_OPEN: _DimTagDeleteOpen,
    EventName.UI_TAG_DELETE_CONFIRM: _DimTagDeleteConfirm,
    EventName.UI_TAG_DELETE_CANCEL: _DimTagDeleteCancel,
    EventName.UI_TAG_FILTER_TOGGLE: None,
    # UI — Members
    EventName.UI_MEMBER_INVITE_OPEN: None,
    EventName.UI_MEMBER_REMOVE_OPEN: None,
    EventName.UI_MEMBER_REMOVE_CONFIRM: None,
    EventName.UI_MEMBER_REMOVE_CANCEL: None,
    EventName.UI_MEMBER_LEAVE_OPEN: None,
    EventName.UI_MEMBER_LEAVE_CONFIRM: None,
    EventName.UI_MEMBER_LEAVE_CANCEL: None,
    # UI — Forms
    EventName.UI_FORM_SUBMIT: _DimFormSubmit,
    EventName.UI_FORM_CANCEL: _DimFormCancel,
    EventName.UI_VALIDATION_ERROR: _DimValidationError,
    # UI — Layout & Navigation
    EventName.UI_DECK_COLLAPSE: _DimDeckCollapse,
    EventName.UI_DECK_EXPAND: _DimDeckExpand,
    EventName.UI_NAVBAR_MOBILE_MENU_OPEN: None,
    EventName.UI_NAVBAR_MOBILE_MENU_CLOSE: None,
    EventName.UI_MOBILE_NAV: _DimMobileNav,
    # UI — Auth (splash)
    EventName.UI_LOGIN_SUBMIT: None,
    EventName.UI_REGISTER_SUBMIT: None,
    EventName.UI_FORGOT_PASSWORD_SUBMIT: None,
    EventName.UI_AUTH_FORM_SWITCH: _DimAuthFormSwitch,
    # UI — Errors
    EventName.UI_RATE_LIMIT_HIT: None,
}


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
    "validate_dimensions",
]
