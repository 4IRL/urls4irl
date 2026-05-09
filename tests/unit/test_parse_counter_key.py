from __future__ import annotations

import json

import pytest

from backend.utils.strings.metrics_strs import METRICS_REDIS
from scripts.flush_metrics import parse_counter_key

pytestmark = pytest.mark.unit


_VALID_BUCKET_EPOCH = 1735689600
_VALID_EVENT_NAME = "api_hit"
_VALID_DIMS = {"endpoint": "/x", "method": "GET", "status_code": 200}


def _build_valid_key() -> bytes:
    canonical_dims = json.dumps(_VALID_DIMS, sort_keys=True, separators=(",", ":"))
    return (
        f"{METRICS_REDIS.COUNTER_KEY_PREFIX}"
        f"{_VALID_BUCKET_EPOCH}:{_VALID_EVENT_NAME}:{canonical_dims}"
    ).encode("utf-8")


def test_parse_counter_key_returns_tuple_for_valid_key():
    """
    GIVEN a well-formed metrics:counter:<bucket>:<event>:<canonical_dims_json> key
    WHEN parse_counter_key is invoked
    THEN it returns (bucket_epoch, event_name, dims) populated from the key.
    """
    parsed = parse_counter_key(_build_valid_key())
    assert parsed is not None
    bucket_epoch, event_name, dims = parsed
    assert bucket_epoch == _VALID_BUCKET_EPOCH
    assert event_name == _VALID_EVENT_NAME
    assert dims == _VALID_DIMS


@pytest.mark.parametrize(
    "malformed_key, case_label",
    [
        # (a) raw bytes that are not valid UTF-8 — `decode("utf-8")` raises
        #     UnicodeDecodeError and the parser returns None.
        (b"\xff\xfe\xfd", "non_utf8_bytes"),
        # (b) too few colon-delimited parts (only 4 segments instead of 5
        #     because the trailing JSON segment is missing entirely).
        (b"metrics:counter:1735689600:api_hit", "too_few_parts"),
        # (d) wrong namespace prefix (first two segments must be
        #     "metrics" and "counter"). Use a 5-segment shape so the part
        #     count check passes and the prefix check is the actual failure.
        (b"other:counter:1735689600:api_hit:{}", "wrong_first_segment"),
        (b"metrics:other:1735689600:api_hit:{}", "wrong_second_segment"),
        # (e) bucket-epoch segment is non-numeric — `int()` raises ValueError.
        (b"metrics:counter:not-a-number:api_hit:{}", "non_int_bucket_epoch"),
        # (f) trailing JSON segment is invalid JSON — `json.loads` raises.
        (b"metrics:counter:1735689600:api_hit:not{json", "invalid_json"),
        # (g) trailing JSON parses but is not a dict (list shape rejected).
        (b"metrics:counter:1735689600:api_hit:[1,2,3]", "json_not_a_dict"),
        # JSON parses but is not a dict (string shape rejected).
        (b'metrics:counter:1735689600:api_hit:"a string"', "json_string_not_dict"),
    ],
)
def test_parse_counter_key_returns_none_for_malformed_keys(
    malformed_key: bytes, case_label: str
):
    """
    GIVEN a counter key whose shape violates one of the parser's guards
        (non-UTF-8, wrong part count, wrong prefix, non-int bucket epoch,
        invalid JSON, or non-dict JSON)
    WHEN parse_counter_key is invoked
    THEN it returns None for the caller to skip.
    """
    assert (
        parse_counter_key(malformed_key) is None
    ), f"parse_counter_key should return None for case={case_label!r}"


def test_parse_counter_key_returns_none_for_too_many_parts():
    """
    GIVEN a key with extra colon-delimited segments after the JSON
        (because the JSON segment itself contains a colon and split was
        called with maxsplit < 4)
    WHEN parse_counter_key is invoked
    THEN it preserves the JSON intact via split(":", 4) and parses
        successfully — proving the maxsplit guard is correct.

    This is the inverse of the (c) "too many parts" branch noted in the
    review: with `split(":", 4)` the parser cannot encounter "more than 5
    parts" because the JSON tail is captured whole. This test documents
    that explicitly so the (c) case stays intentionally unreachable.
    """
    dims_with_colon = {"endpoint": "/api/v1:foo", "method": "GET", "status_code": 200}
    canonical = json.dumps(dims_with_colon, sort_keys=True, separators=(",", ":"))
    key = (
        f"{METRICS_REDIS.COUNTER_KEY_PREFIX}"
        f"{_VALID_BUCKET_EPOCH}:{_VALID_EVENT_NAME}:{canonical}"
    ).encode("utf-8")

    parsed = parse_counter_key(key)
    assert parsed is not None
    _, _, dims = parsed
    assert dims == dims_with_colon
