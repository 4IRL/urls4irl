"""Read-time small-cell suppression for grouped metric queries.

Grouped rows whose count is below `MIN_CELL_COUNT` are merged into a single
sentinel row whose non-`device_type` dims read `SUPPRESSED_DIM_VALUE`. The
sentinel is an output-only constant: it is never a dimension `Literal` and is
never accepted by ingest.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Final

from backend.metrics.events import DEVICE_TYPE_DIM_KEY, EventName
from backend.metrics.gauges import MIN_GAUGE_POPULATION

MIN_CELL_COUNT: Final[int] = MIN_GAUGE_POPULATION
SUPPRESSED_DIM_VALUE: Final[str] = "suppressed"

# Hard cap on one event's dimension-combination space (product of every dim's
# closed-set size). A larger space spreads events over so many cells that most
# fall below `MIN_CELL_COUNT` and get suppressed. Enforced by `make audit`.
# Largest today: `urls_copied_to_utub` (686).
MAX_DIM_COMBINATIONS_PER_EVENT: Final[int] = 700

# `(event, dim)` pairs whose dim is not a closed set (`Literal` / `DeviceType`).
# An exempt dim contributes a factor of 1 to the product; the reason is mandatory.
UNBOUNDED_DIM_EXEMPTIONS: Final[dict[tuple[EventName, str], str]] = {
    (EventName.UI_URL_ACCESS, "active_tag_count"): (
        "Count of active tag filters; small in practice and floored at read "
        "time, so it cannot be enumerated as a closed set."
    ),
    (EventName.UI_URL_CARD_CLICK, "active_tag_count"): (
        "Count of active tag filters; small in practice and floored at read "
        "time, so it cannot be enumerated as a closed set."
    ),
}

# Per event, the only `group_by` key sets a caller may request (exact set,
# order-insensitive). No two sets of one event may nest, so no allowed
# projection can be subtracted from another to recover a merged small cell.
# `EventName.API_HIT` (flat columns, never merged) is exempt and not listed.
# An event absent here has no allowed projection (fail closed). Every new
# groupable dim (master phases 5-6) must be registered here.
ALLOWED_GROUP_BY_PROJECTIONS: Final[dict[EventName, frozenset[frozenset[str]]]] = {
    EventName.API_METRICS_INGEST_BATCH: frozenset(
        {frozenset({"batch_size_bucket", "transport", DEVICE_TYPE_DIM_KEY})}
    ),
    EventName.UI_FORM_CANCEL: frozenset({frozenset({"trigger"})}),
    EventName.UI_AUTH_CANCEL: frozenset({frozenset({"trigger"})}),
    EventName.URL_CREATE_REJECTED: frozenset({frozenset({"reason"})}),
    EventName.REGISTER_REJECTED: frozenset({frozenset({"reason"})}),
    EventName.LOGIN_FAILURE: frozenset({frozenset({"reason"})}),
    EventName.UTUB_OPENED: frozenset(
        {frozenset({"url_count_bucket"}), frozenset({"age_bucket"})}
    ),
    EventName.TAG_APPLIED: frozenset({frozenset({"utub_size_bucket"})}),
}


def _allowed_projection_names(event_name: EventName) -> str:
    projections = ALLOWED_GROUP_BY_PROJECTIONS.get(event_name, frozenset())
    rendered = sorted("[" + ", ".join(sorted(keys)) + "]" for keys in projections)
    return ", ".join(rendered) or "(none)"


def validate_group_by_projection(
    event_name: EventName, group_by_keys: Sequence[str]
) -> None:
    """Raise `ValueError` unless `group_by_keys` is an exact registered projection.

    `API_HIT` is exempt. Echoes only the requested key names.
    """
    if event_name is EventName.API_HIT:
        return
    requested = frozenset(group_by_keys)
    allowed = ALLOWED_GROUP_BY_PROJECTIONS.get(event_name, frozenset())
    # Duplicate keys must not collapse into a registered set (fail closed).
    if len(requested) != len(group_by_keys) or requested not in allowed:
        raise ValueError(
            f"group_by [{', '.join(sorted(requested))}] is not an allowed "
            f"projection for event '{event_name.value}'. Allowed: "
            f"{_allowed_projection_names(event_name)}."
        )


def single_key_group_by_choices(event_name: EventName) -> list[str]:
    """Sorted keys `k` where `{k}` is a registered projection of the event."""
    projections = ALLOWED_GROUP_BY_PROJECTIONS.get(event_name, frozenset())
    return sorted(next(iter(keys)) for keys in projections if len(keys) == 1)


# (bucket, dims, count)
GroupedRow = tuple[datetime, dict[str, str | int], int]


def merge_small_grouped_rows(
    rows: list[GroupedRow], *, group_by: Sequence[str]
) -> list[GroupedRow]:
    """Merge sub-floor rows into one sentinel row per (bucket, device_type).

    A sentinel total still below `MIN_CELL_COUNT` absorbs the smallest kept
    cell of its partition (repeatedly) so it never exposes a lone sub-floor count.
    """
    non_device_keys = [key for key in group_by if key != DEVICE_TYPE_DIM_KEY]
    if not non_device_keys:
        return list(rows)

    kept_by_partition: dict[tuple[datetime, str | int | None], list[GroupedRow]] = {}
    suppressed_totals: dict[tuple[datetime, str | int | None], int] = {}
    for bucket, dims, count in rows:
        partition = (bucket, dims.get(DEVICE_TYPE_DIM_KEY))
        kept_by_partition.setdefault(partition, [])
        if count < MIN_CELL_COUNT:
            suppressed_totals[partition] = suppressed_totals.get(partition, 0) + count
        else:
            kept_by_partition[partition].append((bucket, dims, count))

    # Secondary suppression: a sentinel below the floor would disclose a lone
    # sub-floor count, so fold the smallest kept cell of the same partition in.
    for partition, kept in kept_by_partition.items():
        while 0 < suppressed_totals.get(partition, 0) < MIN_CELL_COUNT and kept:
            smallest = min(kept, key=lambda row: (row[2], repr(sorted(row[1].items()))))
            kept.remove(smallest)
            suppressed_totals[partition] += smallest[2]

    # Re-emit in bucket order, real rows first, sentinel last within a bucket.
    buckets = list(dict.fromkeys(bucket for bucket, _, _ in rows))

    merged: list[GroupedRow] = []
    for bucket in buckets:
        for partition, kept in kept_by_partition.items():
            if partition[0] == bucket:
                merged.extend(kept)
        for partition, total in suppressed_totals.items():
            if partition[0] != bucket:
                continue
            sentinel_dims: dict[str, str | int] = {
                key: SUPPRESSED_DIM_VALUE for key in non_device_keys
            }
            if partition[1] is not None:
                sentinel_dims[DEVICE_TYPE_DIM_KEY] = partition[1]
            merged.append((bucket, sentinel_dims, total))
    return merged


def merge_small_labeled_counts(
    rows: list[tuple[str, int]],
) -> list[tuple[str, int]]:
    """Merge sub-floor `(label, count)` rows into one trailing sentinel."""
    kept = [(label, count) for label, count in rows if count >= MIN_CELL_COUNT]
    suppressed_total = sum(count for _, count in rows if count < MIN_CELL_COUNT)
    has_sentinel = len(kept) != len(rows)
    # Secondary suppression: never emit a lone sub-floor sentinel total.
    while has_sentinel and suppressed_total < MIN_CELL_COUNT and kept:
        smallest = min(kept, key=lambda row: (row[1], row[0]))
        kept.remove(smallest)
        suppressed_total += smallest[1]
    if has_sentinel:
        kept.append((SUPPRESSED_DIM_VALUE, suppressed_total))
    return kept


__all__ = [
    "ALLOWED_GROUP_BY_PROJECTIONS",
    "GroupedRow",
    "MAX_DIM_COMBINATIONS_PER_EVENT",
    "MIN_CELL_COUNT",
    "SUPPRESSED_DIM_VALUE",
    "UNBOUNDED_DIM_EXEMPTIONS",
    "merge_small_grouped_rows",
    "merge_small_labeled_counts",
    "single_key_group_by_choices",
    "validate_group_by_projection",
]
