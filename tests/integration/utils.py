from __future__ import annotations

from typing import Any, Type

from flask import Flask
from redis import Redis

from backend.schemas.base import BaseSchema
from backend.utils.strings.config_strs import CONFIG_ENVS

_MEMORY_URI = "memory://"
_MEMBER_ADD_LOOKUP_KEY_PATTERN = "member-add-lookup:*"


def flush_member_add_lookup_keys(app: Flask) -> None:
    """Delete every ``member-add-lookup:*`` key from the shared enforcement Redis.

    The per-user add-member daily counter (``create_utub_member``) writes to the
    shared ``REDIS_URI`` DB, which survives DB teardown — so without an explicit
    flush, a daily-cap test can leak its counter and 429/400 an unrelated later
    test on the same xdist worker. Deletes only matching keys (never
    ``flushdb()``) since that DB is shared with other enforcement counters,
    mirroring ``_reset_reauth_failure_counter``
    (tests/integration/account_and_settings/test_account_delete.py). No-op when
    Redis is the in-memory stub (fail-open, same as production).
    """
    redis_uri = app.config.get(CONFIG_ENVS.REDIS_URI)
    if not redis_uri or redis_uri == _MEMORY_URI:
        return
    client = Redis.from_url(redis_uri)
    try:
        keys = client.keys(_MEMBER_ADD_LOOKUP_KEY_PATTERN)
        if keys:
            client.delete(*keys)
    finally:
        client.close()


def assert_response_conforms_to_schema(
    response_json: dict[str, Any],
    schema_class: Type[BaseSchema],
    expected_keys: set[str],
) -> None:
    """Validate that a JSON response conforms to a Pydantic response schema.

    Performs three checks:
    1. ``model_validate`` succeeds (raises ``ValidationError`` on failure).
    2. Response keys exactly match the schema's aliased field names.
    3. All ``expected_keys`` are present in the response.

    Args:
        response_json: The parsed JSON body from the Flask test response.
        schema_class: The Pydantic schema class to validate against.
        expected_keys: Keys that must appear in the response (typically
            constants like ``STD_JSON.STATUS`` and ``STD_JSON.MESSAGE``).
    """
    # Validate response conforms to declared schema
    schema_class.model_validate(response_json)

    # Verify response keys match schema's aliased field names
    aliased_keys = {
        field_info.alias or field_name
        for field_name, field_info in schema_class.model_fields.items()
    }
    assert set(response_json.keys()) == aliased_keys

    # Verify expected keys are present
    for key in expected_keys:
        assert key in response_json
