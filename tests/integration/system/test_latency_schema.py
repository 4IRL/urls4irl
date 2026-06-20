import pytest
from flask import Flask
from sqlalchemy import inspect

from backend import db
from backend.models.anonymous_latency_samples import Anonymous_Latency_Samples

pytestmark = pytest.mark.cli

_EXPECTED_COLUMNS = {
    "id",
    "metricName",
    "endpoint",
    "method",
    "observedAt",
    "durationMs",
    "dimensions",
}
_NULLABLE_COLUMNS = {"endpoint", "method"}
_EXPECTED_INDEXES = {
    "idx_latency_metric_time",
    "idx_latency_endpoint_time",
}


def test_anonymous_latency_samples_columns(app: Flask):
    """
    GIVEN the AnonymousLatencySamples table created by the latency migration
    WHEN the table columns are inspected
    THEN ensure all seven expected columns exist with correct broad SQL types
        and the expected nullability
    """
    with app.app_context():
        inspector = inspect(db.engine)
        columns_by_name = {
            column["name"]: column
            for column in inspector.get_columns(Anonymous_Latency_Samples.__tablename__)
        }

        assert set(columns_by_name.keys()) == _EXPECTED_COLUMNS

        assert "VARCHAR" in str(columns_by_name["metricName"]["type"]).upper()
        assert "VARCHAR" in str(columns_by_name["endpoint"]["type"]).upper()
        assert "VARCHAR" in str(columns_by_name["method"]["type"]).upper()
        assert "NUMERIC" in str(columns_by_name["durationMs"]["type"]).upper()
        observed_at_type = str(columns_by_name["observedAt"]["type"]).upper()
        assert "TIMESTAMP" in observed_at_type or "DATETIME" in observed_at_type
        assert "JSON" in str(columns_by_name["dimensions"]["type"]).upper()

        for column_name in _EXPECTED_COLUMNS:
            expected_nullable = column_name in _NULLABLE_COLUMNS
            assert columns_by_name[column_name]["nullable"] is expected_nullable


def test_anonymous_latency_samples_indexes(app: Flask):
    """
    GIVEN the AnonymousLatencySamples table created by the latency migration
    WHEN the table indexes are inspected
    THEN ensure both expected indexes exist
    """
    with app.app_context():
        inspector = inspect(db.engine)
        actual_indexes = {
            index["name"]
            for index in inspector.get_indexes(Anonymous_Latency_Samples.__tablename__)
        }
        assert _EXPECTED_INDEXES == actual_indexes
