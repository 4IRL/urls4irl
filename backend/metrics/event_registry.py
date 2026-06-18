"""Code-side single source of truth for anonymous-metrics event metadata.

`EVENT_REGISTRY` holds one `EventRegistryEntry` per `EventName` member,
documenting:

- `description` — human-readable summary used by the metrics dashboard and
  any TSV / docstring output. Mirrored by `EVENT_DESCRIPTIONS` in
  `backend/metrics/events.py` as a derived projection.
- `category` — one of `EventCategory.API` / `.DOMAIN` / `.UI`. Mirrored by
  `EVENT_CATEGORY` in `backend/metrics/events.py` as a derived projection.
- `dimensions` — closed-set value lists keyed by dimension field name. Empty
  dict for events with no enumerated dimensions. The metrics audit cross-
  checks this against the Pydantic `Literal[...]` args in
  `DIMENSION_MODELS[event].model_fields[field]` to surface drift.

Adding a new event: append a `EventName` member, then add an entry here with
the same key. The unit test `tests/unit/test_event_coverage.py` asserts
`EVENT_REGISTRY.keys() == set(EventName)`, so a missing entry fails CI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.metrics.events import EventCategory, EventName
from backend.search.constants import SEARCH_FIELD_ORDER_VALUES


@dataclass(frozen=True)
class EventRegistryEntry:
    """One row of the anonymous-metrics event registry."""

    description: str
    category: EventCategory
    dimensions: dict[str, tuple[str, ...]] = field(default_factory=dict)


EVENT_REGISTRY: dict[EventName, EventRegistryEntry] = {
    # -----------------------------------------------------------------------
    # API — auto-instrumented via middleware
    # -----------------------------------------------------------------------
    EventName.API_HIT: EventRegistryEntry(
        description="Every HTTP request (excl. static, health, /metrics)",
        category=EventCategory.API,
        dimensions={},
    ),
    EventName.API_METRICS_INGEST_BATCH: EventRegistryEntry(
        description=(
            "Counter on every accepted POST /api/metrics batch, tagged with "
            "batch_size_bucket × transport × device_type for pipeline-health "
            "telemetry."
        ),
        category=EventCategory.API,
        dimensions={
            "batch_size_bucket": ("1", "2-5", "6-25", "26-100"),
            "transport": ("fetch", "beacon"),
        },
    ),
    # -----------------------------------------------------------------------
    # Domain — explicit record_event() calls in service layer
    # -----------------------------------------------------------------------
    EventName.CROSS_UTUB_SEARCH_PERFORMED: EventRegistryEntry(
        description="Cross-UTub search executed across the user's member UTubs",
        category=EventCategory.DOMAIN,
        dimensions={
            "has_results": ("true", "false"),
            "field_order": SEARCH_FIELD_ORDER_VALUES,
        },
    ),
    EventName.UTUB_CREATED: EventRegistryEntry(
        description="New UTub created",
        category=EventCategory.DOMAIN,
    ),
    EventName.UTUB_DELETED: EventRegistryEntry(
        description="UTub deleted by owner",
        category=EventCategory.DOMAIN,
    ),
    EventName.UTUB_OPENED: EventRegistryEntry(
        description="UTub explicitly opened/selected",
        category=EventCategory.DOMAIN,
    ),
    EventName.URL_ACCESSED: EventRegistryEntry(
        description="URL click-through (distinct from list)",
        category=EventCategory.DOMAIN,
    ),
    EventName.TAG_APPLIED: EventRegistryEntry(
        description="Tag added to a URL",
        category=EventCategory.DOMAIN,
    ),
    EventName.TAG_REMOVED: EventRegistryEntry(
        description="Tag removed from a URL",
        category=EventCategory.DOMAIN,
    ),
    EventName.TAG_DELETED: EventRegistryEntry(
        description="Tag deleted from a UTub (UTub-level destructive)",
        category=EventCategory.DOMAIN,
    ),
    EventName.MEMBER_ADDED: EventRegistryEntry(
        description="Member invited to a UTub",
        category=EventCategory.DOMAIN,
    ),
    EventName.MEMBER_REMOVED: EventRegistryEntry(
        description="Member removed from a UTub",
        category=EventCategory.DOMAIN,
    ),
    EventName.URL_TITLE_UPDATED: EventRegistryEntry(
        description="URL title edited",
        category=EventCategory.DOMAIN,
    ),
    EventName.UTUB_TITLE_UPDATED: EventRegistryEntry(
        description="UTub name changed",
        category=EventCategory.DOMAIN,
    ),
    EventName.UTUB_DESC_UPDATED: EventRegistryEntry(
        description="UTub description changed",
        category=EventCategory.DOMAIN,
    ),
    EventName.URL_ADDED_TO_UTUB: EventRegistryEntry(
        description="URL associated with a UTub (new or existing URL row)",
        category=EventCategory.DOMAIN,
    ),
    EventName.URL_CREATE_REJECTED: EventRegistryEntry(
        description=(
            "URL-create attempt rejected on a service-level failure branch, "
            "tagged with closed-set rejection reason"
        ),
        category=EventCategory.DOMAIN,
        dimensions={
            "reason": (
                "credentials_url",
                "invalid_url",
                "unexpected_error",
                "url_already_in_utub",
            ),
        },
    ),
    EventName.URL_REMOVED_FROM_UTUB: EventRegistryEntry(
        description="URL disassociated from a UTub",
        category=EventCategory.DOMAIN,
    ),
    EventName.URL_STRING_UPDATED: EventRegistryEntry(
        description=("URL string changed on a UTub URL (distinct from title update)"),
        category=EventCategory.DOMAIN,
    ),
    EventName.UTUB_TAG_CREATED: EventRegistryEntry(
        description=("New tag vocabulary added to a UTub (distinct from TAG_APPLIED)"),
        category=EventCategory.DOMAIN,
    ),
    EventName.REGISTER_REJECTED: EventRegistryEntry(
        description=(
            "Registration attempt rejected on a service-level guard, tagged "
            "with closed-set rejection reason"
        ),
        category=EventCategory.DOMAIN,
        dimensions={
            "reason": ("email_taken", "username_taken", "unvalidated_email"),
        },
    ),
    EventName.REGISTER_SUCCESS: EventRegistryEntry(
        description="New user account successfully registered",
        category=EventCategory.DOMAIN,
    ),
    EventName.LOGIN_SUCCESS: EventRegistryEntry(
        description=(
            "Login succeeded on the fully-validated path "
            "(email_validated guard passed)"
        ),
        category=EventCategory.DOMAIN,
    ),
    EventName.LOGIN_FAILURE: EventRegistryEntry(
        description=("Login attempt rejected, tagged with closed-set failure reason"),
        category=EventCategory.DOMAIN,
        dimensions={
            "reason": ("unknown_user", "bad_password", "email_unverified"),
        },
    ),
    EventName.EMAIL_VERIFIED: EventRegistryEntry(
        description=(
            "User email validated via the post-registration confirmation link"
        ),
        category=EventCategory.DOMAIN,
    ),
    EventName.PASSWORD_RESET_REQUESTED: EventRegistryEntry(
        description=(
            "Forgot-password email delivery attempted within the rate-limit " "window"
        ),
        category=EventCategory.DOMAIN,
    ),
    EventName.PASSWORD_RESET_COMPLETED: EventRegistryEntry(
        description="Password successfully reset via the reset-token flow",
        category=EventCategory.DOMAIN,
    ),
    # -----------------------------------------------------------------------
    # UI — browser-side emit() shipped to POST /api/metrics
    # (every UI event also carries the auto-injected `device_type` dimension,
    # tracked on the Pydantic dim models, not duplicated here)
    # -----------------------------------------------------------------------
    EventName.UI_UTUB_SELECT: EventRegistryEntry(
        description="UTub selected in sidebar",
        category=EventCategory.UI,
        dimensions={"search_active": ("true", "false")},
    ),
    EventName.UI_UTUB_CREATE_OPEN: EventRegistryEntry(
        description='"Create UTub" form opened',
        category=EventCategory.UI,
    ),
    EventName.UI_UTUB_DELETE_OPEN: EventRegistryEntry(
        description="UTub delete-confirm modal opened",
        category=EventCategory.UI,
    ),
    EventName.UI_UTUB_DELETE_CONFIRM: EventRegistryEntry(
        description="UTub delete confirmed",
        category=EventCategory.UI,
    ),
    EventName.UI_UTUB_DELETE_CANCEL: EventRegistryEntry(
        description="UTub delete-confirm modal dismissed",
        category=EventCategory.UI,
    ),
    EventName.UI_UTUB_NAME_EDIT_OPEN: EventRegistryEntry(
        description="UTub name edit form opened",
        category=EventCategory.UI,
        dimensions={"trigger": ("pencil_icon", "keyboard")},
    ),
    EventName.UI_UTUB_DESC_EDIT_OPEN: EventRegistryEntry(
        description="UTub description edit form opened",
        category=EventCategory.UI,
        dimensions={"trigger": ("pencil_icon", "keyboard", "create_button")},
    ),
    EventName.UI_URL_ACCESS: EventRegistryEntry(
        description="URL accessed via UI",
        category=EventCategory.UI,
        dimensions={
            "trigger": ("corner_button", "url_text", "main_button"),
            "search_active": ("true", "false"),
        },
    ),
    EventName.UI_URL_CARD_CLICK: EventRegistryEntry(
        description="URL card clicked/expanded",
        category=EventCategory.UI,
        dimensions={"search_active": ("true", "false")},
    ),
    EventName.UI_URL_CREATE_OPEN: EventRegistryEntry(
        description='"Add URL" form opened',
        category=EventCategory.UI,
    ),
    EventName.UI_URL_TITLE_EDIT_OPEN: EventRegistryEntry(
        description="URL title edit form opened",
        category=EventCategory.UI,
    ),
    EventName.UI_URL_STRING_EDIT_OPEN: EventRegistryEntry(
        description="URL string edit form opened",
        category=EventCategory.UI,
    ),
    EventName.UI_URL_DELETE_OPEN: EventRegistryEntry(
        description="URL delete-confirm modal opened",
        category=EventCategory.UI,
    ),
    EventName.UI_URL_DELETE_CONFIRM: EventRegistryEntry(
        description="URL delete confirmed",
        category=EventCategory.UI,
    ),
    EventName.UI_URL_DELETE_CANCEL: EventRegistryEntry(
        description="URL delete-confirm modal dismissed",
        category=EventCategory.UI,
    ),
    EventName.UI_URL_COPY: EventRegistryEntry(
        description="URL copied to clipboard",
        category=EventCategory.UI,
        dimensions={"result": ("success", "failure")},
    ),
    EventName.UI_URL_ACCESS_WARNING: EventRegistryEntry(
        description="Non-HTTP URL warning modal shown",
        category=EventCategory.UI,
    ),
    EventName.UI_URL_ACCESS_WARNING_DISMISS: EventRegistryEntry(
        description="Non-HTTP URL warning dismissed (no access)",
        category=EventCategory.UI,
    ),
    EventName.UI_UTUB_SEARCH_OPEN: EventRegistryEntry(
        description="UTub search box opened",
        category=EventCategory.UI,
        dimensions={"target": ("utubs",)},
    ),
    EventName.UI_UTUB_SEARCH_CLOSE: EventRegistryEntry(
        description="UTub search box closed",
        category=EventCategory.UI,
        dimensions={"target": ("utubs",)},
    ),
    EventName.UI_URL_SEARCH_OPEN: EventRegistryEntry(
        description="URL search box opened",
        category=EventCategory.UI,
        dimensions={"target": ("urls",)},
    ),
    EventName.UI_URL_SEARCH_CLOSE: EventRegistryEntry(
        description="URL search box closed",
        category=EventCategory.UI,
        dimensions={"target": ("urls",)},
    ),
    EventName.UI_CROSS_UTUB_SEARCH_OPEN: EventRegistryEntry(
        description="Cross-UTub search mode opened",
        category=EventCategory.UI,
        dimensions={"target": ("cross_utub",)},
    ),
    EventName.UI_CROSS_UTUB_SEARCH_CLOSE: EventRegistryEntry(
        description="Cross-UTub search mode closed",
        category=EventCategory.UI,
        dimensions={"target": ("cross_utub",)},
    ),
    EventName.UI_TAG_APPLY: EventRegistryEntry(
        description="Tag applied from picker",
        category=EventCategory.UI,
    ),
    EventName.UI_TAG_REMOVE: EventRegistryEntry(
        description="Tag removed from URL",
        category=EventCategory.UI,
    ),
    EventName.UI_TAG_CREATE_OPEN: EventRegistryEntry(
        description='"Create tag" input opened',
        category=EventCategory.UI,
        dimensions={"scope": ("utub", "url")},
    ),
    EventName.UI_TAG_DELETE_OPEN: EventRegistryEntry(
        description="Tag delete-confirm modal opened",
        category=EventCategory.UI,
        dimensions={"scope": ("utub", "url")},
    ),
    EventName.UI_TAG_DELETE_CONFIRM: EventRegistryEntry(
        description="Tag delete confirmed",
        category=EventCategory.UI,
        dimensions={"scope": ("utub", "url")},
    ),
    EventName.UI_TAG_DELETE_CANCEL: EventRegistryEntry(
        description="Tag delete-confirm modal dismissed",
        category=EventCategory.UI,
        dimensions={"scope": ("utub", "url")},
    ),
    EventName.UI_TAG_FILTER_TOGGLE: EventRegistryEntry(
        description="Tag filter toggled on/off",
        category=EventCategory.UI,
    ),
    EventName.UI_MEMBER_INVITE_OPEN: EventRegistryEntry(
        description="Member invite form opened",
        category=EventCategory.UI,
    ),
    EventName.UI_MEMBER_REMOVE_OPEN: EventRegistryEntry(
        description="Member-remove confirm modal opened",
        category=EventCategory.UI,
    ),
    EventName.UI_MEMBER_REMOVE_CONFIRM: EventRegistryEntry(
        description="Member removal confirmed",
        category=EventCategory.UI,
    ),
    EventName.UI_MEMBER_REMOVE_CANCEL: EventRegistryEntry(
        description="Member-remove confirm modal dismissed",
        category=EventCategory.UI,
    ),
    EventName.UI_MEMBER_LEAVE_OPEN: EventRegistryEntry(
        description="Self-leave confirm modal opened",
        category=EventCategory.UI,
    ),
    EventName.UI_MEMBER_LEAVE_CONFIRM: EventRegistryEntry(
        description="Self-removal from UTub confirmed",
        category=EventCategory.UI,
    ),
    EventName.UI_MEMBER_LEAVE_CANCEL: EventRegistryEntry(
        description="Self-leave confirm modal dismissed",
        category=EventCategory.UI,
    ),
    EventName.UI_FORM_SUBMIT: EventRegistryEntry(
        description="Form submitted",
        category=EventCategory.UI,
        dimensions={
            "trigger": ("enter_key", "button_click"),
            "form": (
                "url_create",
                "url_title_edit",
                "url_string_edit",
                "utub_create",
                "utub_name_edit",
                "utub_desc_edit",
                "tag_create",
                "member_invite",
            ),
        },
    ),
    EventName.UI_FORM_CANCEL: EventRegistryEntry(
        description="Form cancelled/dismissed",
        category=EventCategory.UI,
        dimensions={
            "trigger": ("escape_key", "cancel_button", "outside_click", "navigation"),
            "form": (
                "url_create",
                "url_title_edit",
                "url_string_edit",
                "utub_create",
                "utub_name_edit",
                "utub_desc_edit",
                "tag_create",
                "member_invite",
            ),
        },
    ),
    EventName.UI_VALIDATION_ERROR: EventRegistryEntry(
        description="Client-side validation error shown",
        category=EventCategory.UI,
        dimensions={
            "form": (
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
            ),
        },
    ),
    EventName.UI_DECK_COLLAPSE: EventRegistryEntry(
        description="Deck collapsed",
        category=EventCategory.UI,
        dimensions={"deck": ("members", "tags", "utubs")},
    ),
    EventName.UI_DECK_EXPAND: EventRegistryEntry(
        description="Deck expanded",
        category=EventCategory.UI,
        dimensions={"deck": ("members", "tags", "utubs")},
    ),
    EventName.UI_NAVBAR_DROPDOWN_OPEN: EventRegistryEntry(
        description="Navbar dropdown menu opened",
        category=EventCategory.UI,
    ),
    EventName.UI_NAVBAR_DROPDOWN_CLOSE: EventRegistryEntry(
        description="Navbar dropdown menu closed",
        category=EventCategory.UI,
    ),
    EventName.UI_MOBILE_NAV: EventRegistryEntry(
        description="Mobile navbar section switch",
        category=EventCategory.UI,
        dimensions={"target": ("utubs", "urls", "members", "tags")},
    ),
    EventName.UI_LOGIN_SUBMIT: EventRegistryEntry(
        description="Login form submitted",
        category=EventCategory.UI,
    ),
    EventName.UI_REGISTER_SUBMIT: EventRegistryEntry(
        description="Registration form submitted",
        category=EventCategory.UI,
    ),
    EventName.UI_FORGOT_PASSWORD_SUBMIT: EventRegistryEntry(
        description="Forgot password form submitted",
        category=EventCategory.UI,
    ),
    EventName.UI_AUTH_CANCEL: EventRegistryEntry(
        description=(
            "Auth form (login/register) abandoned via page navigation before "
            "submit; tagged with which form was open and the cancel trigger"
        ),
        category=EventCategory.UI,
        dimensions={
            "form": ("login", "register"),
            "trigger": ("navigation",),
        },
    ),
    EventName.UI_AUTH_FORM_SWITCH: EventRegistryEntry(
        description="Auth form switched",
        category=EventCategory.UI,
        dimensions={"target": ("login", "register", "forgot_password")},
    ),
    EventName.UI_AUTH_MODAL_OPEN: EventRegistryEntry(
        description=(
            "Auth modal opened from initial CTA (navbar/header link) — not a "
            "form-to-form switch"
        ),
        category=EventCategory.UI,
        dimensions={"form": ("login", "register")},
    ),
    EventName.UI_RESET_PASSWORD_SUBMIT: EventRegistryEntry(
        description="Reset-password form submitted",
        category=EventCategory.UI,
    ),
    EventName.UI_EMAIL_VALIDATION_SUBMIT: EventRegistryEntry(
        description=(
            "Email-validation request submitted (manual click or post-register "
            "auto-send)"
        ),
        category=EventCategory.UI,
        dimensions={"trigger": ("manual_click", "auto_after_register")},
    ),
    EventName.UI_CONTACT_SUBMIT: EventRegistryEntry(
        description="Contact form submitted",
        category=EventCategory.UI,
    ),
    EventName.UI_ERROR_PAGE_REFRESH: EventRegistryEntry(
        description="User clicked refresh on the error page",
        category=EventCategory.UI,
    ),
    EventName.UI_RATE_LIMIT_HIT: EventRegistryEntry(
        description="429 rate limit response shown to user",
        category=EventCategory.UI,
    ),
}


# Derived projections — kept here (alongside the source dict) to avoid a
# circular import via `backend.metrics.events`. `events.py` re-exports both
# names so existing callers keep working unchanged.
EVENT_DESCRIPTIONS: dict[EventName, str] = {
    event_name: entry.description for event_name, entry in EVENT_REGISTRY.items()
}
EVENT_CATEGORY: dict[EventName, EventCategory] = {
    event_name: entry.category for event_name, entry in EVENT_REGISTRY.items()
}


__all__ = [
    "EVENT_CATEGORY",
    "EVENT_DESCRIPTIONS",
    "EVENT_REGISTRY",
    "EventRegistryEntry",
]
