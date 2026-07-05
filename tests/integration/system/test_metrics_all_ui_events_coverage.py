from __future__ import annotations

import uuid
from enum import IntEnum
from typing import Annotated, Any, Literal, get_args, get_origin

import psycopg2
import pytest
from flask import Flask
from pydantic import BaseModel
from redis import Redis

from backend import db, metrics_writer as app_metrics_writer
from backend.extensions.metrics.registry_sync import sync_event_registry
from backend.metrics.dimension_models import DIMENSION_MODELS
from backend.metrics.events import EVENT_CATEGORY, EventCategory, EventName
from backend.models.event_registry import Event_Registry
from backend.utils.strings.config_strs import CONFIG_ENVS
from scripts.flush_metrics import run_flush
from tests.integration.system.conftest import reset_postgres_enum_to_lowercase_values

pytestmark = pytest.mark.cli

INGEST_URL = "/api/metrics"


@pytest.fixture
def metrics_enabled_runner_app(
    runner,
    provide_metrics_redis: Redis,
):
    """Mirrors `test_metrics_pipeline_e2e.py::metrics_enabled_runner_app`.

    Uses the `runner` fixture (not the `app` fixture) because this test
    calls into `sync_event_registry(...)` and `run_flush(...)`, both of
    which open their own DB transactions. `app`'s SAVEPOINT wrapping
    deadlocks with the inline psycopg2 connection.
    """
    app = runner[0]

    original_metrics_enabled = app.config.get(CONFIG_ENVS.METRICS_ENABLED, False)
    original_redis = app_metrics_writer._redis
    original_enabled = app_metrics_writer._enabled

    app.config[CONFIG_ENVS.METRICS_ENABLED] = True
    app_metrics_writer.init_app(app)

    yield app

    app.config[CONFIG_ENVS.METRICS_ENABLED] = original_metrics_enabled
    app_metrics_writer._redis = original_redis
    app_metrics_writer._enabled = original_enabled


def _build_pg_conn(app: Flask) -> Any:
    return psycopg2.connect(app.config["SQLALCHEMY_DATABASE_URI"])


def _example_value_for_annotation(annotation: object) -> Any:
    """Return a Pydantic-valid example for a `_Dim*` field annotation.

    Mirrors the annotation-walking logic in
    `backend/extensions/metrics/dim_types_generator.py::ts_for_annotation`
    but produces runtime values instead of TS source. Picking the *first*
    Literal member and the *smallest* IntEnum value keeps the output
    deterministic so a regression in this helper surfaces with a stable
    diff in the assertion failure.
    """
    if get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    origin = get_origin(annotation)
    if origin is Literal:
        return get_args(annotation)[0]
    if isinstance(annotation, type) and issubclass(annotation, IntEnum):
        return int(min(annotation, key=lambda member: member.value))
    if annotation is int:
        return 0
    if annotation is bool:
        return True
    if annotation is str:
        return ""
    raise ValueError(
        f"_example_value_for_annotation: unsupported annotation {annotation!r}. "
        "Extend this helper when a new field type lands in a `_Dim*` model."
    )


def _example_dim_payload(model: type[BaseModel]) -> dict[str, Any]:
    """Build the minimal Pydantic-valid dim payload for a `_Dim*` class.

    The payload always includes `device_type` because every UI dim model
    inherits `UIBaseDimensions`. Caller-supplied keys win at the route
    boundary so the test's payload survives the allow-list filter intact.
    """
    return {
        field_name: _example_value_for_annotation(field_info.annotation)
        for field_name, field_info in model.model_fields.items()
    }


def test_every_ui_event_flows_end_to_end_through_ingest_and_flush(
    metrics_enabled_runner_app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN every UI-category `EventName` member with its matching `_Dim*`
        Pydantic class from `DIMENSION_MODELS`
    WHEN a single batch POST to `/api/metrics` carries one event per UI
        `EventName` with the minimal valid dim payload derived from each
        Pydantic model, followed by a single `run_flush(...)`
    THEN every UI event lands as exactly one `AnonymousMetrics` row.

    Coverage backstop. Any new `EventName.UI_*` member added without a
    corresponding `DIMENSION_MODELS` entry fails this test immediately
    (the `assert ui_events_with_model` check below). Any schema change
    that breaks one event's payload also fails this test, because the
    payload generator walks the live Pydantic class annotations on every
    run. The Selenium per-domain tests prove the browser → DB chain
    works for the diverse-enough sentinel set; this test proves every
    other event's schema is also wired through the same chain at the
    backend boundary.
    """
    app = metrics_enabled_runner_app

    # Step 1 — sync EventRegistry so FK targets exist for the upsert.
    # `reset_postgres_enum_to_lowercase_values` matches the production
    # enum value casing; without it the F1 enum-value mismatch is invisible
    # in test because both SQLAlchemy sides agree on uppercase NAMES.
    setup_conn = _build_pg_conn(app)
    try:
        reset_postgres_enum_to_lowercase_values(setup_conn)
    finally:
        setup_conn.close()

    with app.app_context():
        sync_event_registry(app)
        assert db.session.query(Event_Registry).count() == len(EventName)

    # Step 2 — collect the UI events that have a `_Dim*` model (skip
    # non-UI categories like API_HIT and the domain events). Every UI
    # event must have a model — the assertion below is a hard
    # registration guard.
    ui_events_with_model = [
        event
        for event in EventName
        if EVENT_CATEGORY[event] == EventCategory.UI
        and DIMENSION_MODELS[event] is not None
    ]
    ui_events_in_enum = [
        event for event in EventName if EVENT_CATEGORY[event] == EventCategory.UI
    ]
    assert ui_events_with_model == ui_events_in_enum, (
        "Every UI EventName must have a non-None DIMENSION_MODELS entry. "
        "Missing: "
        f"{[event.value for event in ui_events_in_enum if event not in ui_events_with_model]!r}"
    )

    # Step 3 — build one event per UI EventName.
    events_payload = [
        {
            "event_name": event.value,
            "dimensions": _example_dim_payload(DIMENSION_MODELS[event]),
        }
        for event in ui_events_with_model
    ]

    # Step 4 — POST as a single batch. The route accepts multiple events
    # per call; one batch keeps the test fast and the response shape
    # easy to assert.
    flask_client = app.test_client()
    ingest_response = flask_client.post(
        INGEST_URL,
        json={
            "events": events_payload,
            "batch_id": str(uuid.uuid4()),
        },
    )

    assert (
        ingest_response.status_code == 200
    ), f"Ingest failed: {ingest_response.status_code} {ingest_response.get_data(as_text=True)!r}"
    assert ingest_response.get_json()["accepted"] == len(events_payload), (
        f"Accepted count mismatch: expected {len(events_payload)}, "
        f"got {ingest_response.get_json()['accepted']}"
    )

    # Step 5 — flush Redis into AnonymousMetrics. The flush count is
    # `len(events_payload) + 1` because every ingest attempt also emits the
    # auto-fired API_METRICS_INGEST_BATCH pipeline-health counter.
    inline_conn = _build_pg_conn(app)
    try:
        upserted = run_flush(redis_client=provide_metrics_redis, pg_conn=inline_conn)
        expected_upserts = len(events_payload) + 1
        assert upserted == expected_upserts, (
            f"Flush upserted {upserted} rows; expected {expected_upserts} "
            f"({len(events_payload)} payload events + 1 API_METRICS_INGEST_BATCH counter)"
        )

        with inline_conn.cursor() as cursor:
            cursor.execute(
                'SELECT "eventName", "dimensions", "count"'
                ' FROM "AnonymousMetrics" ORDER BY "eventName"'
            )
            rows = cursor.fetchall()
    finally:
        inline_conn.close()

    # Step 6 — assert every UI event has exactly one row with count=1
    # and the dimensions we sent.
    rows_by_event = {
        event_name: (dimensions, count) for event_name, dimensions, count in rows
    }

    missing_events = [
        event.value
        for event in ui_events_with_model
        if event.value not in rows_by_event
    ]
    assert not missing_events, (
        f"UI events that POSTed successfully but did not flush to "
        f"AnonymousMetrics: {missing_events!r}. All rows present: "
        f"{sorted(rows_by_event.keys())!r}"
    )

    mismatches: list[str] = []
    for event in ui_events_with_model:
        expected_dimensions = _example_dim_payload(DIMENSION_MODELS[event])
        actual_dimensions, actual_count = rows_by_event[event.value]
        if actual_count != 1:
            mismatches.append(f"{event.value}: count expected 1, got {actual_count}")
        if actual_dimensions != expected_dimensions:
            mismatches.append(
                f"{event.value}: dimensions expected {expected_dimensions!r}, "
                f"got {actual_dimensions!r}"
            )
    assert not mismatches, (
        f"Row mismatches after flush ({len(mismatches)} of "
        f"{len(ui_events_with_model)} UI events):\n  " + "\n  ".join(mismatches)
    )
