from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.metrics.gauges import MIN_GAUGE_POPULATION
from backend.metrics.suppression import (
    MIN_CELL_COUNT,
    SUPPRESSED_DIM_VALUE,
    GroupedRow,
    merge_small_grouped_rows,
    merge_small_labeled_counts,
)

pytestmark = pytest.mark.unit

BUCKET_A = datetime(2026, 6, 8, 10, tzinfo=timezone.utc)
BUCKET_B = BUCKET_A + timedelta(hours=1)


def _total(rows: list[GroupedRow], bucket: datetime) -> int:
    return sum(count for row_bucket, _, count in rows if row_bucket == bucket)


def test_min_cell_count_matches_gauge_floor():
    assert MIN_CELL_COUNT == MIN_GAUGE_POPULATION


def test_count_below_floor_is_merged_into_sentinel():
    rows: list[GroupedRow] = [(BUCKET_A, {"reason": "x"}, MIN_CELL_COUNT - 1)]
    assert merge_small_grouped_rows(rows, group_by=["reason"]) == [
        (BUCKET_A, {"reason": SUPPRESSED_DIM_VALUE}, MIN_CELL_COUNT - 1)
    ]


def test_count_at_floor_survives():
    rows: list[GroupedRow] = [(BUCKET_A, {"reason": "x"}, MIN_CELL_COUNT)]
    assert merge_small_grouped_rows(rows, group_by=["reason"]) == rows


def test_sub_floor_rows_sum_and_sentinel_sorts_last():
    rows: list[GroupedRow] = [
        (BUCKET_A, {"reason": "a"}, 2),
        (BUCKET_A, {"reason": "b"}, 9),
        (BUCKET_A, {"reason": "c"}, 1),
    ]
    merged = merge_small_grouped_rows(rows, group_by=["reason"])
    # Sentinel total 3 < floor, so the smallest kept cell (9) is folded in.
    assert merged == [(BUCKET_A, {"reason": SUPPRESSED_DIM_VALUE}, 12)]
    assert _total(merged, BUCKET_A) == _total(rows, BUCKET_A)


def test_sentinel_at_floor_does_not_fold_kept_cells():
    rows: list[GroupedRow] = [
        (BUCKET_A, {"reason": "a"}, 2),
        (BUCKET_A, {"reason": "b"}, 3),
        (BUCKET_A, {"reason": "c"}, 9),
    ]
    assert merge_small_grouped_rows(rows, group_by=["reason"]) == [
        (BUCKET_A, {"reason": "c"}, 9),
        (BUCKET_A, {"reason": SUPPRESSED_DIM_VALUE}, 5),
    ]


def test_lone_sub_floor_cell_folds_smallest_kept_cell():
    rows: list[GroupedRow] = [
        (BUCKET_A, {"reason": "a"}, 1),
        (BUCKET_A, {"reason": "b"}, 8),
        (BUCKET_A, {"reason": "c"}, 6),
    ]
    assert merge_small_grouped_rows(rows, group_by=["reason"]) == [
        (BUCKET_A, {"reason": "b"}, 8),
        (BUCKET_A, {"reason": SUPPRESSED_DIM_VALUE}, 7),
    ]


def test_all_cells_sub_floor_keeps_sentinel_total():
    rows: list[GroupedRow] = [
        (BUCKET_A, {"reason": "a"}, 1),
        (BUCKET_A, {"reason": "b"}, 2),
    ]
    assert merge_small_grouped_rows(rows, group_by=["reason"]) == [
        (BUCKET_A, {"reason": SUPPRESSED_DIM_VALUE}, 3)
    ]


def test_secondary_fold_stays_within_device_type_partition():
    rows: list[GroupedRow] = [
        (BUCKET_A, {"reason": "a", "device_type": 1}, 2),
        (BUCKET_A, {"reason": "b", "device_type": 2}, 7),
    ]
    merged = merge_small_grouped_rows(rows, group_by=["reason", "device_type"])
    assert merged == [
        (BUCKET_A, {"reason": "b", "device_type": 2}, 7),
        (BUCKET_A, {"reason": SUPPRESSED_DIM_VALUE, "device_type": 1}, 2),
    ]


def test_secondary_fold_stays_within_bucket():
    rows: list[GroupedRow] = [
        (BUCKET_A, {"reason": "a"}, 2),
        (BUCKET_B, {"reason": "b"}, 7),
    ]
    merged = merge_small_grouped_rows(rows, group_by=["reason"])
    assert (BUCKET_B, {"reason": "b"}, 7) in merged
    assert (BUCKET_A, {"reason": SUPPRESSED_DIM_VALUE}, 2) in merged


def test_secondary_fold_tie_is_deterministic():
    rows: list[GroupedRow] = [
        (BUCKET_A, {"reason": "z"}, 5),
        (BUCKET_A, {"reason": "y"}, 5),
        (BUCKET_A, {"reason": "a"}, 1),
    ]
    merged = merge_small_grouped_rows(rows, group_by=["reason"])
    assert merged == [
        (BUCKET_A, {"reason": "z"}, 5),
        (BUCKET_A, {"reason": SUPPRESSED_DIM_VALUE}, 6),
    ]


def test_partitions_by_bucket_stay_separate():
    rows: list[GroupedRow] = [
        (BUCKET_A, {"reason": "a"}, 2),
        (BUCKET_B, {"reason": "a"}, 3),
    ]
    merged = merge_small_grouped_rows(rows, group_by=["reason"])
    assert merged == [
        (BUCKET_A, {"reason": SUPPRESSED_DIM_VALUE}, 2),
        (BUCKET_B, {"reason": SUPPRESSED_DIM_VALUE}, 3),
    ]


def test_partitions_by_device_type_stay_separate_and_keep_real_value():
    rows: list[GroupedRow] = [
        (BUCKET_A, {"reason": "a", "device_type": 1}, 2),
        (BUCKET_A, {"reason": "b", "device_type": 2}, 3),
        (BUCKET_A, {"reason": "c", "device_type": 1}, 1),
    ]
    merged = merge_small_grouped_rows(rows, group_by=["reason", "device_type"])
    assert (
        BUCKET_A,
        {"reason": SUPPRESSED_DIM_VALUE, "device_type": 1},
        3,
    ) in merged
    assert (
        BUCKET_A,
        {"reason": SUPPRESSED_DIM_VALUE, "device_type": 2},
        3,
    ) in merged
    assert len(merged) == 2


def test_device_type_only_group_by_is_untouched():
    rows: list[GroupedRow] = [(BUCKET_A, {"device_type": 1}, 1)]
    assert merge_small_grouped_rows(rows, group_by=["device_type"]) == rows


def test_no_sentinel_when_nothing_merged():
    rows: list[GroupedRow] = [(BUCKET_A, {"reason": "a"}, 7)]
    assert merge_small_grouped_rows(rows, group_by=["reason"]) == rows


def test_labeled_counts_merge_keeps_order_and_sentinel_last():
    merged = merge_small_labeled_counts([("a", 12), ("b", 5), ("c", 4), ("d", 2)])
    assert merged == [("a", 12), ("b", 5), (SUPPRESSED_DIM_VALUE, 6)]


def test_labeled_counts_sub_floor_sentinel_folds_smallest_kept():
    merged = merge_small_labeled_counts([("a", 12), ("b", 6), ("c", 5), ("d", 2)])
    assert merged == [("a", 12), ("b", 6), (SUPPRESSED_DIM_VALUE, 7)]


def test_labeled_counts_sentinel_exactly_floor_keeps_kept_rows():
    merged = merge_small_labeled_counts([("a", 12), ("b", 3), ("c", 2)])
    assert merged == [("a", 12), (SUPPRESSED_DIM_VALUE, 5)]


def test_labeled_counts_single_sub_floor_row():
    assert merge_small_labeled_counts([("a", 3)]) == [(SUPPRESSED_DIM_VALUE, 3)]


def test_labeled_counts_no_sentinel_when_nothing_merged():
    rows = [("a", 6), ("b", 5)]
    assert merge_small_labeled_counts(rows) == rows
