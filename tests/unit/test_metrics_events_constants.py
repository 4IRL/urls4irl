from __future__ import annotations

import pytest

import backend.extensions.metrics.middleware as metrics_middleware_module
import backend.extensions.metrics.writer as metrics_writer_module
import backend.metrics.query_service as metrics_query_service_module
from backend.metrics.events import DEVICE_TYPE_DIM_KEY

pytestmark = pytest.mark.unit


def test_device_type_dim_key_imported_by_middleware():
    """Middleware module imports DEVICE_TYPE_DIM_KEY from backend.metrics.events."""
    assert hasattr(metrics_middleware_module, "DEVICE_TYPE_DIM_KEY")
    assert metrics_middleware_module.DEVICE_TYPE_DIM_KEY is DEVICE_TYPE_DIM_KEY


def test_device_type_dim_key_imported_by_writer():
    """Writer module imports DEVICE_TYPE_DIM_KEY from backend.metrics.events."""
    assert hasattr(metrics_writer_module, "DEVICE_TYPE_DIM_KEY")
    assert metrics_writer_module.DEVICE_TYPE_DIM_KEY is DEVICE_TYPE_DIM_KEY


def test_device_type_dim_key_imported_by_query_service():
    """Query-service module imports DEVICE_TYPE_DIM_KEY from backend.metrics.events."""
    assert hasattr(metrics_query_service_module, "DEVICE_TYPE_DIM_KEY")
    assert metrics_query_service_module.DEVICE_TYPE_DIM_KEY is DEVICE_TYPE_DIM_KEY
