import pytest

from backend.utils.db_table_names import TABLE_NAMES
from tests.integration.cli.utils import assert_row_counts_match_ignoring_new_tables

pytestmark = pytest.mark.unit

USERS_TABLE = TABLE_NAMES.USERS
METRIC_FLOWS_TABLE = TABLE_NAMES.METRIC_FLOWS


def test_table_present_only_before_is_ignored():
    """
    GIVEN a snapshot with MetricFlows rows and one without the table
    WHEN the counts are compared
    THEN the table missing from the later snapshot is ignored
    """
    assert_row_counts_match_ignoring_new_tables(
        {METRIC_FLOWS_TABLE: 2, USERS_TABLE: 5}, {USERS_TABLE: 5}
    )


def test_dropped_by_downgrade_table_count_difference_is_ignored():
    """
    GIVEN MetricFlows seeded at head and re-created empty on re-upgrade
    WHEN the counts are compared
    THEN the MetricFlows difference does not fail the comparison
    """
    assert_row_counts_match_ignoring_new_tables(
        {METRIC_FLOWS_TABLE: 2}, {METRIC_FLOWS_TABLE: 0}
    )


def test_other_table_count_difference_still_fails():
    """
    GIVEN a Users count that differs between snapshots
    WHEN the counts are compared
    THEN the comparison fails even if MetricFlows also differs
    """
    with pytest.raises(AssertionError):
        assert_row_counts_match_ignoring_new_tables(
            {METRIC_FLOWS_TABLE: 2, USERS_TABLE: 5},
            {METRIC_FLOWS_TABLE: 0, USERS_TABLE: 4},
        )
