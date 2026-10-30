"""Catalog of the events, dims and API endpoints a custom metric flow may use.

The module exposes exactly what ``validate_flow_payload`` accepts: filter values
come from the same registries and the endpoint list from the same
``allowed_methods_by_endpoint()`` walk. The catalog parity test enforces this.

Each dim carries ``groupable``: true iff it is a valid breakdown ``group_by``
for the event (``single_key_group_by_choices``, or any API_HIT flat column).
Filtering stays independent of grouping.
"""

from __future__ import annotations

from backend.metrics.dimension_models import DIMENSION_MODELS
from backend.metrics.event_registry import EVENT_REGISTRY
from backend.metrics.events import (
    DEVICE_TYPE_DIM_KEY,
    EVENT_CATEGORY,
    DeviceType,
    EventCategory,
    EventName,
)
from backend.metrics.flow_validation import allowed_methods_by_endpoint
from backend.metrics.suppression import single_key_group_by_choices
from backend.schemas.metrics import (
    FlowCatalogApiEndpointSchema,
    FlowCatalogDimSchema,
    FlowCatalogEventGroupSchema,
    FlowCatalogEventSchema,
    FlowCatalogResponseSchema,
)

__all__ = ["build_flow_catalog"]

_STATUS_CODE_KEY = "status_code"
_API_FLAT_COLUMNS = ("endpoint", "method", _STATUS_CODE_KEY)
# Group order in the response; step events must come from the first two.
_CATEGORY_ORDER = (EventCategory.UI, EventCategory.DOMAIN, EventCategory.API)
_STEP_CATEGORIES = frozenset({EventCategory.UI, EventCategory.DOMAIN})
_DEVICE_TYPE_VALUES = [str(member.value) for member in DeviceType]


def _api_dims(event: EventName) -> list[FlowCatalogDimSchema]:
    # Only API_HIT is exempt from the group_by registry; other API events
    # share the flat-column dim list but none of it is groupable.
    groupable = event is EventName.API_HIT
    return [
        FlowCatalogDimSchema(
            key=column,
            groupable=groupable,
            filter_kind="status_code"
            if column == _STATUS_CODE_KEY
            else "group_by_only",
            values=[],
        )
        for column in _API_FLAT_COLUMNS
    ]


def _event_dims(event: EventName) -> list[FlowCatalogDimSchema]:
    if EVENT_CATEGORY[event] is EventCategory.API:
        return _api_dims(event)
    model = DIMENSION_MODELS[event]
    if model is None:
        return []
    closed_sets = EVENT_REGISTRY[event].dimensions
    groupable_keys = single_key_group_by_choices(event)
    dims: list[FlowCatalogDimSchema] = []
    for key in model.model_fields:
        if key == DEVICE_TYPE_DIM_KEY:
            values = list(_DEVICE_TYPE_VALUES)
        else:
            values = list(closed_sets.get(key, ()))
        dims.append(
            FlowCatalogDimSchema(
                key=key,
                groupable=key in groupable_keys,
                filter_kind="values" if values else "group_by_only",
                values=values,
            )
        )
    return dims


def _build_event(event: EventName) -> FlowCatalogEventSchema:
    category = EVENT_CATEGORY[event]
    return FlowCatalogEventSchema(
        event_name=event.value,
        description=EVENT_REGISTRY[event].description,
        category=category.value,
        step_allowed=category in _STEP_CATEGORIES,
        dims=_event_dims(event),
    )


def build_flow_catalog() -> FlowCatalogResponseSchema:
    """Build the full catalog; needs an app context for the ``url_map`` walk."""
    event_groups: list[FlowCatalogEventGroupSchema] = []
    for category in _CATEGORY_ORDER:
        events = sorted(
            (event for event in EventName if EVENT_CATEGORY[event] is category),
            key=lambda event: event.value,
        )
        if events:
            event_groups.append(
                FlowCatalogEventGroupSchema(
                    category=category.value,
                    events=[_build_event(event) for event in events],
                )
            )
    methods_by_endpoint = allowed_methods_by_endpoint()
    api_endpoints = [
        FlowCatalogApiEndpointSchema(
            endpoint=endpoint,
            blueprint=endpoint.split(".", 1)[0],
            methods=sorted(methods_by_endpoint[endpoint]),
        )
        for endpoint in sorted(methods_by_endpoint)
    ]
    return FlowCatalogResponseSchema(
        event_groups=event_groups, api_endpoints=api_endpoints
    )
