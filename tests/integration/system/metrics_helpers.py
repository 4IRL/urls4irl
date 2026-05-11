from __future__ import annotations

import json

from redis import Redis

from backend.metrics.events import EventName
from backend.utils.strings.metrics_strs import METRICS_REDIS


def find_counter_keys(metrics_redis: Redis, event: EventName) -> list[bytes]:
    pattern = f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*:{event.value}:*"
    return list(metrics_redis.scan_iter(match=pattern))


def count_counter_keys(metrics_redis: Redis, event: EventName) -> int:
    pattern = f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*:{event.value}:*"
    return len(list(metrics_redis.scan_iter(match=pattern)))


def parse_dims(counter_key: bytes) -> dict:
    """Extract the trailing canonical-dims JSON segment from a counter key.

    Key shape: `metrics:counter:<bucket>:<event_name>:<canonical_dims_json>`
    The JSON segment is everything after the 4th colon — split with
    `maxsplit=4` so a `:` inside the JSON does not corrupt the parse.
    """
    decoded = counter_key.decode("utf-8")
    parts = decoded.split(":", 4)
    return json.loads(parts[4])


def build_counter_key(bucket_epoch: int, event_value: str, dims: dict) -> str:
    canonical = json.dumps(dims, sort_keys=True, separators=(",", ":"))
    return f"{METRICS_REDIS.COUNTER_KEY_PREFIX}{bucket_epoch}:{event_value}:{canonical}"
