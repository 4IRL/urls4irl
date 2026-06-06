from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner

from backend import db
from backend.extensions.metrics.buckets import (
    _WINDOW_PARSE_ERROR_FMT,
    WINDOW_NAMED,
)
from backend.metrics.events import (
    EVENT_DESCRIPTIONS,
    EventCategory,
    EventName,
)
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.models.event_registry import Event_Registry

pytestmark = pytest.mark.cli


_EMPTY_OUTPUT_SENTINEL = "No metrics rows in the requested window."
_HEADER_LINE = "event_name\tcategory\tdescription\ttotal_count"


def _seed_event_with_count(
    event_name: EventName,
    category: EventCategory,
    bucket_start: datetime,
    count: int,
) -> None:
    """Seed one EventRegistry + AnonymousMetrics row through SQLAlchemy.

    `Anonymous_Metrics.event_name` has a FK constraint against
    `EventRegistry.name`; the `runner` fixture's `clear_database` teardown
    drops both tables between tests, so each test must seed its own
    registry rows before inserting AnonymousMetrics.
    """
    if Event_Registry.query.filter_by(name=event_name.value).one_or_none() is None:
        db.session.add(
            Event_Registry(
                name=event_name.value,
                category=category,
                description=EVENT_DESCRIPTIONS[event_name],
            )
        )
        db.session.flush()
    db.session.add(
        Anonymous_Metrics(
            event_name=event_name.value,
            bucket_start=bucket_start,
            dimensions={},
            count=count,
        )
    )
    db.session.commit()


def _bucket_inside_day_window() -> datetime:
    """Return a UTC-aware bucket_start guaranteed to fall inside a 1-day
    lookback from `utc_now()`. `now - 1h` sits comfortably inside the
    `day` window the CLI exercises.
    """
    return datetime.now(timezone.utc) - timedelta(hours=1)


def test_flask_metrics_top_with_empty_window_prints_sentinel(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN no AnonymousMetrics rows exist
    WHEN `flask metrics top --window=day` is invoked
    THEN the CLI exits 0 and prints the empty-result sentinel.
    """
    app = metrics_enabled_runner_app
    runner: FlaskCliRunner = app.test_cli_runner()

    with app.app_context():
        assert Anonymous_Metrics.query.count() == 0

    result = runner.invoke(args=["metrics", "top", "--window=day"])

    assert result.exit_code == 0, result.output
    assert _EMPTY_OUTPUT_SENTINEL in result.output


def test_flask_metrics_top_prints_header_and_rows_in_descending_total(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN seeded UTUB_OPENED (count 14) and API_HIT (count 100) rows in the window
    WHEN `flask metrics top --window=day` is invoked
    THEN the CLI exits 0, prints the tab-separated header, and the first
        data row is API_HIT (the higher total).
    """
    app = metrics_enabled_runner_app
    inside = _bucket_inside_day_window()

    with app.app_context():
        _seed_event_with_count(
            EventName.UTUB_OPENED, EventCategory.DOMAIN, inside, count=5
        )
        _seed_event_with_count(
            EventName.UTUB_OPENED,
            EventCategory.DOMAIN,
            inside - timedelta(minutes=30),
            count=9,
        )
        _seed_event_with_count(EventName.API_HIT, EventCategory.API, inside, count=100)

    runner: FlaskCliRunner = app.test_cli_runner()
    result = runner.invoke(args=["metrics", "top", "--window=day"])

    assert result.exit_code == 0, result.output
    assert _HEADER_LINE in result.output

    lines = [line for line in result.output.splitlines() if line.strip()]
    header_index = lines.index(_HEADER_LINE)
    data_lines = lines[header_index + 1 :]
    assert len(data_lines) == 2

    first_columns = data_lines[0].split("\t")
    assert first_columns[0] == EventName.API_HIT.value
    assert first_columns[-1] == "100"

    second_columns = data_lines[1].split("\t")
    assert second_columns[0] == EventName.UTUB_OPENED.value
    assert second_columns[-1] == "14"


def test_flask_metrics_top_filters_by_category(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN domain (UTUB_OPENED) and api (API_HIT) rows inside the window
    WHEN `flask metrics top --window=day --category=domain` is invoked
    THEN only domain-category rows appear in the output.
    """
    app = metrics_enabled_runner_app
    inside = _bucket_inside_day_window()

    with app.app_context():
        _seed_event_with_count(
            EventName.UTUB_OPENED, EventCategory.DOMAIN, inside, count=5
        )
        _seed_event_with_count(EventName.API_HIT, EventCategory.API, inside, count=100)

    runner: FlaskCliRunner = app.test_cli_runner()
    result = runner.invoke(args=["metrics", "top", "--window=day", "--category=domain"])

    assert result.exit_code == 0, result.output
    assert EventName.UTUB_OPENED.value in result.output
    assert EventName.API_HIT.value not in result.output


def test_flask_metrics_top_respects_limit_flag(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN five distinct events seeded inside the window
    WHEN `flask metrics top --window=day --limit=2` is invoked
    THEN exactly two data rows appear after the header.
    """
    app = metrics_enabled_runner_app
    inside = _bucket_inside_day_window()

    seeded_events = [
        EventName.UTUB_OPENED,
        EventName.UTUB_CREATED,
        EventName.UTUB_DELETED,
        EventName.URL_ACCESSED,
        EventName.API_HIT,
    ]
    with app.app_context():
        for offset, event_name in enumerate(seeded_events):
            category = (
                EventCategory.API
                if event_name == EventName.API_HIT
                else EventCategory.DOMAIN
            )
            _seed_event_with_count(
                event_name,
                category,
                inside - timedelta(minutes=offset),
                count=offset + 1,
            )

    runner: FlaskCliRunner = app.test_cli_runner()
    result = runner.invoke(args=["metrics", "top", "--window=day", "--limit=2"])

    assert result.exit_code == 0, result.output
    assert _HEADER_LINE in result.output

    lines = [line for line in result.output.splitlines() if line.strip()]
    header_index = lines.index(_HEADER_LINE)
    data_lines = lines[header_index + 1 :]
    assert len(data_lines) == 2


def test_flask_metrics_top_invalid_window_exits_nonzero_with_parse_error(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN an unparseable window string
    WHEN `flask metrics top --window=bogus` is invoked
    THEN the CLI exits non-zero and emits the parse-error message.
    """
    app = metrics_enabled_runner_app
    runner: FlaskCliRunner = app.test_cli_runner()

    result = runner.invoke(args=["metrics", "top", "--window=bogus"])

    expected_message = _WINDOW_PARSE_ERROR_FMT.format(value="bogus", names=WINDOW_NAMED)
    assert result.exit_code != 0
    combined_output = result.output + (result.stderr if result.stderr_bytes else "")
    assert expected_message in combined_output
