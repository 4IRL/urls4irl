"""Code-side single source of truth for anonymous-metrics *latency* metadata.

A *latency* metric is a raw request-duration observation (milliseconds) captured
once per non-skipped HTTP request and stored as one row per sample in
``AnonymousLatencySamples``. Unlike counters (occurrence tallies) and gauges
(periodically-sampled scalars), latency retains the full value distribution so
arbitrary quantiles (p50/p95/p99) can be computed exactly at query time with
Postgres ``percentile_cont``.

Each latency metric is one ``LatencyMetricEntry`` in ``LATENCY_REGISTRY`` keyed
by a ``LatencyMetricName`` member. A contributor adds a new latency metric with
exactly one enum member + one registry entry; the unit test
``tests/unit/test_latency.py`` asserts ``set(LATENCY_REGISTRY) ==
set(LatencyMetricName)``, so a missing entry fails CI. (``flask metrics audit``
covers only ``EventName``-based events, not this primitive — same as gauges.)

This module is a **pure leaf**: its only imports are the stdlib ``dataclasses``
and ``enum``. It deliberately imports **no Flask, no SQLAlchemy, and no backend
package** so the standalone psycopg2 flush worker (which side-loads this file by
absolute path inside the workflow container — a venv with only ``redis`` +
``psycopg2``) and the Flask app share the exact same latency definitions and
bounding constants. Any heavy import here would crash the workflow container.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# Per (bucket, metric, dims) Redis list cap: each latency list is LTRIM'd to at
# most this many samples per flush bucket so unbounded raw-sample storage cannot
# grow without limit. Drained samples exceeding the cap are discarded oldest-first.
LATENCY_SAMPLE_CAP_PER_BUCKET: int = 200
# Retention window for flushed rows; the flush worker prunes rows older than this.
LATENCY_RETENTION_DAYS: int = 14
# Minimum spacing between retention prunes, enforced by a daily Redis sentinel so
# the per-minute flush worker prunes at most once per day.
LATENCY_PRUNE_INTERVAL_SECONDS: int = 86_400


class LatencyMetricName(StrEnum):
    API_REQUEST_DURATION = "api_request_duration"


@dataclass(frozen=True)
class LatencyMetricEntry:
    """A flat spec carrying the human-readable description of one latency metric."""

    description: str


LATENCY_REGISTRY: dict[LatencyMetricName, LatencyMetricEntry] = {
    LatencyMetricName.API_REQUEST_DURATION: LatencyMetricEntry(
        description=(
            "End-to-end HTTP request handling time (ms), per endpoint/method/device."
        )
    ),
}


__all__ = [
    "LATENCY_PRUNE_INTERVAL_SECONDS",
    "LATENCY_REGISTRY",
    "LATENCY_RETENTION_DAYS",
    "LATENCY_SAMPLE_CAP_PER_BUCKET",
    "LatencyMetricEntry",
    "LatencyMetricName",
]
