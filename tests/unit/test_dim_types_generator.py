from __future__ import annotations

from typing import Literal

import pytest

from backend.extensions.metrics.dim_types_generator import (
    _named_alias_annotations,
    _ts_for_annotation,
    generate_dim_types_ts,
    generate_dim_values_ts,
    generate_resources_ts,
    generate_ui_events_ts,
)
from backend.metrics.dimension_models import HomeForm
from backend.metrics.events import EVENT_CATEGORY, EventCategory, EventName
from backend.metrics.resources import RESOURCE_BY_CATEGORY, Resource

pytestmark = pytest.mark.unit

UI_EVENT_NAME_PREFIX = "UI_"
UI_WIRE_PREFIX = "ui_"
UI_EVENT_DIMENSIONS_TYPE = "UIEventDimensions"
DEVICE_TYPE_CONSTANT = "DEVICE_TYPE"
DEVICE_TYPE_ALIAS = "DeviceType"
AS_CONST_SUFFIX = "} as const"


def test_generate_ui_events_ts_only_emits_ui_prefixed_events() -> None:
    """
    GIVEN the EventName enum mixing UI and non-UI categories
    WHEN generate_ui_events_ts() renders the TS source
    THEN every emitted wire value starts with `ui_` and no non-UI EventName
        member appears in the output.
    """
    ts_source = generate_ui_events_ts()

    ui_event_members = [
        event for event in EventName if EVENT_CATEGORY[event] == EventCategory.UI
    ]
    non_ui_event_members = [
        event for event in EventName if EVENT_CATEGORY[event] != EventCategory.UI
    ]

    assert (
        ui_event_members
    ), "Expected at least one UI EventName for the test to be meaningful."
    assert (
        non_ui_event_members
    ), "Expected at least one non-UI EventName for filtering to be testable."

    for ui_event in ui_event_members:
        assert ui_event.name.startswith(UI_EVENT_NAME_PREFIX)
        assert ui_event.value.startswith(UI_WIRE_PREFIX)
        assert f'{ui_event.name}: "{ui_event.value}"' in ts_source

    for non_ui_event in non_ui_event_members:
        assert f"{non_ui_event.name}:" not in ts_source
        assert f'"{non_ui_event.value}"' not in ts_source


def test_generate_dim_types_ts_emits_ui_event_dimensions_and_named_alias_imports() -> (
    None
):
    """
    GIVEN the per-event Pydantic dim models
    WHEN generate_dim_types_ts() renders the TS source
    THEN the output declares the `UIEventDimensions` mapping type, imports
        every named alias from `./metrics-dim-values.js`, and binds each UI
        wire name to a per-event TS type alias.
    """
    ts_source = generate_dim_types_ts()

    assert f"export type {UI_EVENT_DIMENSIONS_TYPE} = {{" in ts_source
    assert 'from "./metrics-dim-values.js";' in ts_source

    expected_imported_aliases = (
        DEVICE_TYPE_ALIAS,
        "HomeForm",
        "SearchActive",
        "TagScope",
        "ValidationForm",
    )
    for alias_name in expected_imported_aliases:
        assert f"  {alias_name}," in ts_source

    ui_event_members = [
        event for event in EventName if EVENT_CATEGORY[event] == EventCategory.UI
    ]
    for ui_event in ui_event_members:
        assert f'"{ui_event.value}":' in ts_source


def test_generate_dim_values_ts_emits_named_alias_constants_and_device_type() -> None:
    """
    GIVEN the named module-level Literal aliases and the DeviceType IntEnum
    WHEN generate_dim_values_ts() renders the TS source
    THEN the output contains DEVICE_TYPE plus every named-alias constant
        (HOME_FORM, VALIDATION_FORM, SEARCH_ACTIVE, TAG_SCOPE) and emits at
        least one `} as const` object closure.
    """
    ts_source = generate_dim_values_ts()

    expected_named_constants = (
        DEVICE_TYPE_CONSTANT,
        "HOME_FORM",
        "VALIDATION_FORM",
        "SEARCH_ACTIVE",
        "TAG_SCOPE",
    )
    for constant_name in expected_named_constants:
        assert f"export const {constant_name} = {{" in ts_source

    assert AS_CONST_SUFFIX in ts_source

    derived_type_declaration = (
        f"export type {DEVICE_TYPE_ALIAS} = "
        f"(typeof {DEVICE_TYPE_CONSTANT})[keyof typeof {DEVICE_TYPE_CONSTANT}];"
    )
    assert derived_type_declaration in ts_source

    assert "MOBILE: 1," in ts_source
    assert "DESKTOP: 2," in ts_source


def test_ts_for_annotation_raises_value_error_on_unsupported_annotation() -> None:
    """
    GIVEN an annotation type the generator does not know how to map
    WHEN _ts_for_annotation() is called with that annotation
    THEN a ValueError is raised pointing the maintainer at the offending type.
    """
    named_aliases = _named_alias_annotations()

    class _SyntheticUnsupportedAnnotation:
        pass

    with pytest.raises(ValueError, match="Unsupported annotation in dim codegen"):
        _ts_for_annotation(_SyntheticUnsupportedAnnotation, named_aliases)


def test_ts_for_annotation_int_returns_number() -> None:
    """
    GIVEN the primitive `int` annotation
    WHEN _ts_for_annotation() is called with it
    THEN the function returns the TS primitive `'number'`.
    """
    assert _ts_for_annotation(int, {}) == "number"


def test_ts_for_annotation_bool_returns_boolean() -> None:
    """
    GIVEN the primitive `bool` annotation
    WHEN _ts_for_annotation() is called with it
    THEN the function returns the TS primitive `'boolean'`.
    """
    assert _ts_for_annotation(bool, {}) == "boolean"


def test_ts_for_annotation_str_returns_string() -> None:
    """
    GIVEN the primitive `str` annotation
    WHEN _ts_for_annotation() is called with it
    THEN the function returns the TS primitive `'string'`.
    """
    assert _ts_for_annotation(str, {}) == "string"


def test_ts_for_annotation_inline_literal_returns_quoted_union() -> None:
    """
    GIVEN an inline `Literal['a', 'b']` annotation (not a named alias)
    WHEN _ts_for_annotation() is called with an empty named_aliases map
    THEN the function returns the quoted TS string union `'"a" | "b"'`.
    """
    assert _ts_for_annotation(Literal["a", "b"], {}) == '"a" | "b"'


def test_generate_resources_ts_emits_resources_const_type_and_by_category() -> None:
    """
    GIVEN the `Resource` StrEnum and `RESOURCE_BY_CATEGORY` mapping
    WHEN generate_resources_ts() renders the TS source
    THEN the output declares the `RESOURCES` const, the `ResourceName` type
        alias, and the `RESOURCES_BY_CATEGORY` mapping; every Resource member
        appears in `RESOURCES`; and the API category's resources are surfaced
        in the by-category map.
    """
    ts_source = generate_resources_ts()

    assert "export const RESOURCES = {" in ts_source
    assert (
        "export type ResourceName = (typeof RESOURCES)[keyof typeof RESOURCES];"
        in ts_source
    )
    assert "export const RESOURCES_BY_CATEGORY = {" in ts_source

    for resource in Resource:
        assert f'{resource.name}: "{resource.value}",' in ts_source

    assert 'UTUB: "utub",' in ts_source

    api_resources = RESOURCE_BY_CATEGORY[EventCategory.API]
    assert (
        api_resources
    ), "Expected at least one API resource for the test to be meaningful."
    api_values_joined = ", ".join(f'"{resource.value}"' for resource in api_resources)
    assert f"  {EventCategory.API.value}: [{api_values_joined}] as const," in ts_source


def test_ts_for_annotation_named_alias_returns_alias_name() -> None:
    """
    GIVEN a named module-level Pydantic Literal alias (`HomeForm`)
    WHEN _ts_for_annotation() is called with the real
        identity-keyed named_aliases map from `_named_alias_annotations()`
    THEN the function short-circuits the Literal branch and returns the
        alias name (`'HomeForm'`) so the generated TS imports the named type
        from `./metrics-dim-values.js` instead of inlining the union.
    """
    named_aliases = _named_alias_annotations()

    assert _ts_for_annotation(HomeForm, named_aliases) == "HomeForm"
