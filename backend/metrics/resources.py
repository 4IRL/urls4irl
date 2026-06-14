"""Resource taxonomy for metrics top-events filtering.

Each event in `EventName` belongs to a coarse "resource" bucket — e.g.
`UI_UTUB_DELETE_CONFIRM` and `UTUB_DELETED` both belong to `Resource.UTUB`.
For API-category rows (where the stored event name is always `API_HIT`),
the resource is derived from the request `endpoint` column instead.

This module is the single source of truth for the resource taxonomy:

- `Resource` — canonical enum, shipped to the frontend as a generated TS file
  via `flask metrics generate-resources`.
- `EVENT_NAME_TO_RESOURCE` — explicit per-event lookup for UI + Domain events.
- `API_ROUTE_PREFIX_TO_RESOURCE` — ordered prefix list for API rows.
- `RESOURCE_BY_CATEGORY` — which resources appear in each dashboard tab.
- `resource_filter_clause()` — SQLAlchemy boolean filter for the query layer.
"""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import not_, or_
from sqlalchemy.sql import ColumnElement

from backend.metrics.events import EVENT_CATEGORY, EventCategory, EventName
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.utils.all_routes import (
    ACCOUNT_AND_SETTING_ROUTES,
    ADMIN_ROUTES,
    MEMBER_ROUTES,
    SPLASH_ROUTES,
    URL_ROUTES,
    URL_TAG_ROUTES,
    USER_ROUTES,
    UTUB_ROUTES,
    UTUB_TAG_ROUTES,
)


class Resource(StrEnum):
    UTUB = "utub"
    URL = "url"
    TAG = "tag"
    MEMBER = "member"
    AUTH = "auth"
    SEARCH = "search"
    FORM = "form"
    DECK = "deck"
    NAV = "nav"
    ERROR = "error"
    CONTACT = "contact"
    ADMIN = "admin"
    OTHER = "other"


EVENT_NAME_TO_RESOURCE: dict[EventName, Resource] = {
    # Domain
    EventName.UTUB_CREATED: Resource.UTUB,
    EventName.UTUB_DELETED: Resource.UTUB,
    EventName.UTUB_OPENED: Resource.UTUB,
    EventName.UTUB_TITLE_UPDATED: Resource.UTUB,
    EventName.UTUB_DESC_UPDATED: Resource.UTUB,
    EventName.URL_ACCESSED: Resource.URL,
    EventName.URL_ADDED_TO_UTUB: Resource.URL,
    EventName.URL_CREATE_REJECTED: Resource.URL,
    EventName.URL_REMOVED_FROM_UTUB: Resource.URL,
    EventName.URL_STRING_UPDATED: Resource.URL,
    EventName.URL_TITLE_UPDATED: Resource.URL,
    EventName.TAG_APPLIED: Resource.TAG,
    EventName.TAG_REMOVED: Resource.TAG,
    EventName.TAG_DELETED: Resource.TAG,
    EventName.UTUB_TAG_CREATED: Resource.TAG,
    EventName.MEMBER_ADDED: Resource.MEMBER,
    EventName.MEMBER_REMOVED: Resource.MEMBER,
    EventName.EMAIL_VERIFIED: Resource.AUTH,
    EventName.LOGIN_FAILURE: Resource.AUTH,
    EventName.LOGIN_SUCCESS: Resource.AUTH,
    EventName.PASSWORD_RESET_COMPLETED: Resource.AUTH,
    EventName.PASSWORD_RESET_REQUESTED: Resource.AUTH,
    EventName.REGISTER_REJECTED: Resource.AUTH,
    EventName.REGISTER_SUCCESS: Resource.AUTH,
    # UI — UTubs
    EventName.UI_UTUB_SELECT: Resource.UTUB,
    EventName.UI_UTUB_CREATE_OPEN: Resource.UTUB,
    EventName.UI_UTUB_DELETE_OPEN: Resource.UTUB,
    EventName.UI_UTUB_DELETE_CONFIRM: Resource.UTUB,
    EventName.UI_UTUB_DELETE_CANCEL: Resource.UTUB,
    EventName.UI_UTUB_NAME_EDIT_OPEN: Resource.UTUB,
    EventName.UI_UTUB_DESC_EDIT_OPEN: Resource.UTUB,
    # UI — URLs
    EventName.UI_URL_ACCESS: Resource.URL,
    EventName.UI_URL_CARD_CLICK: Resource.URL,
    EventName.UI_URL_CREATE_OPEN: Resource.URL,
    EventName.UI_URL_TITLE_EDIT_OPEN: Resource.URL,
    EventName.UI_URL_STRING_EDIT_OPEN: Resource.URL,
    EventName.UI_URL_DELETE_OPEN: Resource.URL,
    EventName.UI_URL_DELETE_CONFIRM: Resource.URL,
    EventName.UI_URL_DELETE_CANCEL: Resource.URL,
    EventName.UI_URL_COPY: Resource.URL,
    EventName.UI_URL_ACCESS_WARNING: Resource.URL,
    EventName.UI_URL_ACCESS_WARNING_DISMISS: Resource.URL,
    # UI — Search
    EventName.UI_UTUB_SEARCH_OPEN: Resource.SEARCH,
    EventName.UI_UTUB_SEARCH_CLOSE: Resource.SEARCH,
    EventName.UI_URL_SEARCH_OPEN: Resource.SEARCH,
    EventName.UI_URL_SEARCH_CLOSE: Resource.SEARCH,
    # UI — Tags
    EventName.UI_TAG_APPLY: Resource.TAG,
    EventName.UI_TAG_REMOVE: Resource.TAG,
    EventName.UI_TAG_CREATE_OPEN: Resource.TAG,
    EventName.UI_TAG_DELETE_OPEN: Resource.TAG,
    EventName.UI_TAG_DELETE_CONFIRM: Resource.TAG,
    EventName.UI_TAG_DELETE_CANCEL: Resource.TAG,
    EventName.UI_TAG_FILTER_TOGGLE: Resource.TAG,
    # UI — Members
    EventName.UI_MEMBER_INVITE_OPEN: Resource.MEMBER,
    EventName.UI_MEMBER_REMOVE_OPEN: Resource.MEMBER,
    EventName.UI_MEMBER_REMOVE_CONFIRM: Resource.MEMBER,
    EventName.UI_MEMBER_REMOVE_CANCEL: Resource.MEMBER,
    EventName.UI_MEMBER_LEAVE_OPEN: Resource.MEMBER,
    EventName.UI_MEMBER_LEAVE_CONFIRM: Resource.MEMBER,
    EventName.UI_MEMBER_LEAVE_CANCEL: Resource.MEMBER,
    # UI — Forms
    EventName.UI_FORM_SUBMIT: Resource.FORM,
    EventName.UI_FORM_CANCEL: Resource.FORM,
    EventName.UI_VALIDATION_ERROR: Resource.ERROR,
    # UI — Layout & Navigation
    EventName.UI_DECK_COLLAPSE: Resource.DECK,
    EventName.UI_DECK_EXPAND: Resource.DECK,
    EventName.UI_NAVBAR_DROPDOWN_OPEN: Resource.NAV,
    EventName.UI_NAVBAR_DROPDOWN_CLOSE: Resource.NAV,
    EventName.UI_MOBILE_NAV: Resource.NAV,
    # UI — Auth / splash
    EventName.UI_LOGIN_SUBMIT: Resource.AUTH,
    EventName.UI_REGISTER_SUBMIT: Resource.AUTH,
    EventName.UI_FORGOT_PASSWORD_SUBMIT: Resource.AUTH,
    EventName.UI_AUTH_CANCEL: Resource.AUTH,
    EventName.UI_AUTH_FORM_SWITCH: Resource.AUTH,
    EventName.UI_AUTH_MODAL_OPEN: Resource.AUTH,
    EventName.UI_RESET_PASSWORD_SUBMIT: Resource.AUTH,
    EventName.UI_EMAIL_VALIDATION_SUBMIT: Resource.AUTH,
    # UI — Contact / errors
    EventName.UI_CONTACT_SUBMIT: Resource.CONTACT,
    EventName.UI_ERROR_PAGE_REFRESH: Resource.ERROR,
    EventName.UI_RATE_LIMIT_HIT: Resource.ERROR,
}


# Ordered list — first matching prefix wins. Rows whose `endpoint` matches
# no prefix in this list are bucketed as `Resource.OTHER` (see
# `resource_filter_clause` for the negative-match SQL form).
#
# Matches Flask endpoint names (`<blueprint>.<view_function>`) as stored in
# `Anonymous_Metrics.endpoint` by `backend/extensions/metrics/middleware.py`
# — NOT URL paths. `utub_tags`/`utub_url_tags` both share the `TAG` bucket
# because both are tag-related; `users`+`splash` share `AUTH` because the
# users blueprint is account/profile (auth-adjacent).
#
# All blueprint prefix constants are sourced from `backend/utils/all_routes.py`
# (single source of truth — no bare string literals).
API_ROUTE_PREFIX_TO_RESOURCE: tuple[tuple[str, Resource], ...] = (
    (UTUB_ROUTES._UTUBS, Resource.UTUB),
    (URL_ROUTES._URLS, Resource.URL),
    (UTUB_TAG_ROUTES._UTUB_TAGS, Resource.TAG),
    (URL_TAG_ROUTES._URL_TAGS, Resource.TAG),
    (MEMBER_ROUTES._MEMBERS, Resource.MEMBER),
    (SPLASH_ROUTES._SPLASH, Resource.AUTH),
    (USER_ROUTES._USERS, Resource.AUTH),
    (ADMIN_ROUTES._ADMIN, Resource.ADMIN),
    (ACCOUNT_AND_SETTING_ROUTES._CONTACT, Resource.CONTACT),
)


def _event_names_for_resource_in_category(
    *, category: EventCategory, resource: Resource
) -> tuple[str, ...]:
    return tuple(
        event_name.value
        for event_name, mapped in EVENT_NAME_TO_RESOURCE.items()
        if mapped is resource and EVENT_CATEGORY[event_name] is category
    )


def _resources_for_event_category(category: EventCategory) -> tuple[Resource, ...]:
    seen: list[Resource] = []
    for event_name, resource in EVENT_NAME_TO_RESOURCE.items():
        if EVENT_CATEGORY[event_name] is category and resource not in seen:
            seen.append(resource)
    return tuple(seen)


def _api_resources() -> tuple[Resource, ...]:
    seen: list[Resource] = []
    for _prefix, resource in API_ROUTE_PREFIX_TO_RESOURCE:
        if resource not in seen:
            seen.append(resource)
    seen.append(Resource.OTHER)
    return tuple(seen)


RESOURCE_BY_CATEGORY: dict[EventCategory, tuple[Resource, ...]] = {
    EventCategory.API: _api_resources(),
    EventCategory.DOMAIN: _resources_for_event_category(EventCategory.DOMAIN),
    EventCategory.UI: _resources_for_event_category(EventCategory.UI),
}


def resource_filter_clause(
    *, category: EventCategory, resource: Resource
) -> ColumnElement[bool]:
    """Return a SQLAlchemy boolean filter that narrows AnonymousMetrics rows
    to those belonging to `resource` within `category`.

    For UI and Domain categories, filtering targets `event_name`. For API,
    filtering targets `endpoint` via prefix match (with `OTHER` meaning
    "matches no known prefix").

    Callers MUST cross-validate the (category, resource) pair before calling
    (see `RESOURCE_BY_CATEGORY`) — passing a resource that does not appear
    in the category yields a trivially-false `event_name IN ()` clause that
    SQLAlchemy treats as an empty-result match.

    Examples:
        resource_filter_clause(category=EventCategory.UI, resource=Resource.UTUB)
        # ⇒ AnonymousMetrics.event_name IN ("ui_utub_select", ...)

        resource_filter_clause(category=EventCategory.API, resource=Resource.UTUB)
        # ⇒ AnonymousMetrics.endpoint LIKE "/utubs/%"

        resource_filter_clause(category=EventCategory.API, resource=Resource.OTHER)
        # ⇒ NOT (endpoint LIKE "/utubs/%" OR endpoint LIKE "/urls/%" OR ...)
    """
    if category is EventCategory.API:
        if resource is Resource.OTHER:
            known_prefix_clauses = [
                Anonymous_Metrics.endpoint.like(f"{prefix}%")
                for prefix, _mapped in API_ROUTE_PREFIX_TO_RESOURCE
            ]
            return not_(or_(*known_prefix_clauses))
        matching_prefixes = [
            prefix
            for prefix, mapped in API_ROUTE_PREFIX_TO_RESOURCE
            if mapped is resource
        ]
        # `or_()` with no arguments produces a silent-false clause, which
        # would mask a misconfiguration (e.g. a new resource added to
        # RESOURCE_BY_CATEGORY[API] without a corresponding entry in
        # API_ROUTE_PREFIX_TO_RESOURCE) as zero rows returned. Surface it.
        if not matching_prefixes:
            raise ValueError(f"No API prefix mapping for {resource!r}")
        return or_(
            *(
                Anonymous_Metrics.endpoint.like(f"{prefix}%")
                for prefix in matching_prefixes
            )
        )

    event_names = _event_names_for_resource_in_category(
        category=category, resource=resource
    )
    return Anonymous_Metrics.event_name.in_(event_names)
