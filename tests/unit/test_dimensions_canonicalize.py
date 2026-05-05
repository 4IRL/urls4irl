import json

import pytest

from backend.extensions.metrics.dimensions import canonicalize_dimensions

pytestmark = pytest.mark.unit


def test_empty_dict_canonicalizes_to_braces():
    """An empty dimensions dict serializes to bare braces."""
    assert canonicalize_dimensions({}) == "{}"


def test_keys_are_sorted():
    """Key order in the input dict has no effect on the canonical output."""
    sorted_output = '{"a":2,"b":1}'
    assert canonicalize_dimensions({"b": 1, "a": 2}) == sorted_output
    assert canonicalize_dimensions({"a": 2, "b": 1}) == sorted_output
    assert canonicalize_dimensions({"b": 1, "a": 2}) == canonicalize_dimensions(
        {"a": 2, "b": 1}
    )


def test_no_whitespace_in_output():
    """The compact separators choice eliminates whitespace from the output."""
    canonical = canonicalize_dimensions({"a": 1, "b": 2})
    assert " " not in canonical


def test_unicode_escaped_to_ascii():
    """Non-ASCII characters are escaped (ensure_ascii=True)."""
    assert canonicalize_dimensions({"name": "café"}) == '{"name":"caf\\u00e9"}'


def test_round_trip_through_json_loads():
    """Canonical output round-trips back to the original dict via json.loads."""
    original = {
        "trigger": "corner_button",
        "search_active": True,
        "active_tag_count": 3,
    }
    assert json.loads(canonicalize_dimensions(original)) == original


def test_nested_dicts_keys_also_sorted():
    """Nested dict keys are also sorted recursively."""
    assert (
        canonicalize_dimensions({"outer": {"y": 1, "x": 2}})
        == '{"outer":{"x":2,"y":1}}'
    )
