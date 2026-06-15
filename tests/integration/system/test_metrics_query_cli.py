from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner

from backend import db
from backend.cli.metrics import (
    EMPTY_GAUGE_TIMESERIES_OUTPUT,
    EMPTY_GAUGES_LATEST_OUTPUT,
    EMPTY_TOP_EVENTS_OUTPUT,
    GAUGE_TIMESERIES_HEADER,
    GAUGES_LATEST_HEADER,
    GAUGES_LIST_HEADER,
    TOP_EVENTS_HEADER,
)
from backend.extensions.metrics.buckets import (
    _WINDOW_PARSE_ERROR_FMT,
    WINDOW_NAMED,
)
from backend.metrics.events import (
    EVENT_DESCRIPTIONS,
    EventCategory,
    EventName,
)
from backend.metrics.gauges import GaugeName
from backend.models.anonymous_gauges import Anonymous_Gauges
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.models.event_registry import Event_Registry

pytestmark = pytest.mark.cli

# AVG-kind gauge sample value used to exercise the `_gauge_value_cell(float)`
# TSV-formatting branch end-to-end. `str(4.5)` renders as "4.5".
GAUGE_FLOAT_VALUE: float = 4.5
GAUGE_FLOAT_VALUE_CELL: str = str(GAUGE_FLOAT_VALUE)


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
    assert EMPTY_TOP_EVENTS_OUTPUT in result.output


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
    assert TOP_EVENTS_HEADER in result.output

    lines = [line for line in result.output.splitlines() if line.strip()]
    header_index = lines.index(TOP_EVENTS_HEADER)
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
    assert TOP_EVENTS_HEADER in result.output

    lines = [line for line in result.output.splitlines() if line.strip()]
    header_index = lines.index(TOP_EVENTS_HEADER)
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


def test_flask_metrics_top_prints_window_bounds_header_for_relative_window(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN any invocation with --window=<relative>
    WHEN `flask metrics top --window=day` runs
    THEN the output starts with a `window: day [<iso-start> .. <iso-end>]`
        header so the resolved bounds are visible in the terminal.
    """
    app = metrics_enabled_runner_app
    runner: FlaskCliRunner = app.test_cli_runner()

    result = runner.invoke(args=["metrics", "top", "--window=day"])

    assert result.exit_code == 0, result.output
    first_line = result.output.splitlines()[0]
    assert first_line.startswith("window: day [")
    assert " .. " in first_line


def test_flask_metrics_top_absolute_range_happy_path(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN seeded UTUB_OPENED rows inside an absolute UTC range
    WHEN `flask metrics top --start=<iso-Z> --end=<iso-Z>` runs
    THEN the CLI exits 0, prints `range: [<iso-start> .. <iso-end>]`,
        and the seeded row appears in the data section.
    """
    app = metrics_enabled_runner_app
    inside = _bucket_inside_day_window()
    range_start = (inside - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    range_end = (inside + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    with app.app_context():
        _seed_event_with_count(
            EventName.UTUB_OPENED, EventCategory.DOMAIN, inside, count=11
        )

    runner: FlaskCliRunner = app.test_cli_runner()
    result = runner.invoke(
        args=[
            "metrics",
            "top",
            f"--start={range_start}",
            f"--end={range_end}",
        ]
    )

    assert result.exit_code == 0, result.output
    first_line = result.output.splitlines()[0]
    assert first_line.startswith("range: [")
    assert TOP_EVENTS_HEADER in result.output
    data_lines = result.output.splitlines()[
        result.output.splitlines().index(TOP_EVENTS_HEADER) + 1 :
    ]
    first_data_columns = data_lines[0].split("\t")
    assert first_data_columns[0] == EventName.UTUB_OPENED.value
    assert first_data_columns[-1] == "11"


def test_flask_metrics_top_naive_datetime_exits_nonzero_with_tz_error(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN ISO-8601 strings WITHOUT a timezone designator
    WHEN `flask metrics top --start=<naive> --end=<naive>` runs
    THEN the CLI exits non-zero and the error mentions the missing timezone
        (the same `AwareDatetime` check the HTTP route enforces).
    """
    app = metrics_enabled_runner_app
    runner: FlaskCliRunner = app.test_cli_runner()

    result = runner.invoke(
        args=[
            "metrics",
            "top",
            "--start=2026-06-06T13:00:00",
            "--end=2026-06-06T17:00:00",
        ]
    )

    assert result.exit_code != 0
    combined_output = result.output + (result.stderr if result.stderr_bytes else "")
    assert "timezone" in combined_output.lower()


def test_flask_metrics_top_window_and_range_together_exits_nonzero(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN both --window and --start/--end supplied
    WHEN `flask metrics top --window=day --start=<iso-Z> --end=<iso-Z>` runs
    THEN the CLI exits non-zero with the XOR validator's verbatim message.
    """
    app = metrics_enabled_runner_app
    runner: FlaskCliRunner = app.test_cli_runner()

    result = runner.invoke(
        args=[
            "metrics",
            "top",
            "--window=day",
            "--start=2026-06-06T13:00:00Z",
            "--end=2026-06-06T17:00:00Z",
        ]
    )

    assert result.exit_code != 0
    combined_output = result.output + (result.stderr if result.stderr_bytes else "")
    assert "Provide either `window` or `start`+`end`, not both." in combined_output


def test_flask_metrics_top_missing_window_and_range_exits_nonzero(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN neither --window nor --start/--end supplied
    WHEN `flask metrics top` runs with no time-spec
    THEN the CLI exits non-zero with the missing-spec validator message.
    """
    app = metrics_enabled_runner_app
    runner: FlaskCliRunner = app.test_cli_runner()

    result = runner.invoke(args=["metrics", "top"])

    assert result.exit_code != 0
    combined_output = result.output + (result.stderr if result.stderr_bytes else "")
    assert "Provide `window` or both `start` and `end`." in combined_output


# ---------------------------------------------------------------------------
# Gauge CLI commands — gauge-timeseries / gauges-latest / gauges-list
# ---------------------------------------------------------------------------


def _seed_gauge_row(
    gauge_name: GaugeName,
    sampled_at: datetime,
    *,
    value_int: int | None = None,
    value_float: float | None = None,
) -> None:
    """Seed one AnonymousGauges row through SQLAlchemy under an app context."""
    db.session.add(
        Anonymous_Gauges(
            gauge_name=gauge_name.value,
            sampled_at=sampled_at,
            value_int=value_int,
            value_float=value_float,
            dimensions={},
        )
    )
    db.session.commit()


def test_flask_metrics_gauge_timeseries_empty_window_prints_sentinel(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN no AnonymousGauges rows exist
    WHEN `flask metrics gauge-timeseries --name=total_users --window=day` runs
    THEN the CLI exits 0 and prints the empty-result sentinel.
    """
    app = metrics_enabled_runner_app

    with app.app_context():
        assert Anonymous_Gauges.query.count() == 0

    runner: FlaskCliRunner = app.test_cli_runner()
    result = runner.invoke(
        args=["metrics", "gauge-timeseries", "--name=total_users", "--window=day"]
    )

    assert result.exit_code == 0, result.output
    assert EMPTY_GAUGE_TIMESERIES_OUTPUT in result.output


def test_flask_metrics_gauge_timeseries_prints_header_and_seeded_values(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN two TOTAL_USERS samples seeded inside the window
    WHEN `flask metrics gauge-timeseries --name=total_users --window=day` runs
    THEN the CLI exits 0, prints the header, and the seeded integer values appear.
    """
    app = metrics_enabled_runner_app
    inside = _bucket_inside_day_window()

    with app.app_context():
        assert Anonymous_Gauges.query.count() == 0
        _seed_gauge_row(
            GaugeName.TOTAL_USERS, inside - timedelta(minutes=30), value_int=10
        )
        _seed_gauge_row(GaugeName.TOTAL_USERS, inside, value_int=12)

    runner: FlaskCliRunner = app.test_cli_runner()
    result = runner.invoke(
        args=["metrics", "gauge-timeseries", "--name=total_users", "--window=day"]
    )

    assert result.exit_code == 0, result.output
    assert GAUGE_TIMESERIES_HEADER in result.output
    lines = [line for line in result.output.splitlines() if line.strip()]
    header_index = lines.index(GAUGE_TIMESERIES_HEADER)
    data_lines = lines[header_index + 1 :]
    assert len(data_lines) == 2
    value_int_cells = [line.split("\t")[1] for line in data_lines]
    assert value_int_cells == ["10", "12"]


def test_flask_metrics_gauge_timeseries_invalid_window_exits_nonzero(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN an unparseable window string
    WHEN `flask metrics gauge-timeseries --name=total_users --window=bogus` runs
    THEN the CLI exits non-zero and emits the parse-error message.
    """
    app = metrics_enabled_runner_app
    runner: FlaskCliRunner = app.test_cli_runner()

    result = runner.invoke(
        args=["metrics", "gauge-timeseries", "--name=total_users", "--window=bogus"]
    )

    expected_message = _WINDOW_PARSE_ERROR_FMT.format(value="bogus", names=WINDOW_NAMED)
    assert result.exit_code != 0
    combined_output = result.output + (result.stderr if result.stderr_bytes else "")
    assert expected_message in combined_output


def test_flask_metrics_gauges_latest_empty_prints_sentinel(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN no AnonymousGauges rows exist
    WHEN `flask metrics gauges-latest` runs
    THEN the CLI exits 0 and prints the empty-result sentinel.
    """
    app = metrics_enabled_runner_app

    with app.app_context():
        assert Anonymous_Gauges.query.count() == 0

    runner: FlaskCliRunner = app.test_cli_runner()
    result = runner.invoke(args=["metrics", "gauges-latest"])

    assert result.exit_code == 0, result.output
    assert EMPTY_GAUGES_LATEST_OUTPUT in result.output


def test_flask_metrics_gauges_latest_prints_newest_per_gauge(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN one gauge with two samples seeded
    WHEN `flask metrics gauges-latest` runs
    THEN the CLI exits 0, prints the header, and the newest value appears.
    """
    app = metrics_enabled_runner_app
    inside = _bucket_inside_day_window()

    with app.app_context():
        assert Anonymous_Gauges.query.count() == 0
        _seed_gauge_row(GaugeName.TOTAL_USERS, inside - timedelta(hours=1), value_int=5)
        _seed_gauge_row(GaugeName.TOTAL_USERS, inside, value_int=9)

    runner: FlaskCliRunner = app.test_cli_runner()
    result = runner.invoke(args=["metrics", "gauges-latest"])

    assert result.exit_code == 0, result.output
    assert GAUGES_LATEST_HEADER in result.output
    lines = [line for line in result.output.splitlines() if line.strip()]
    data_lines = lines[lines.index(GAUGES_LATEST_HEADER) + 1 :]
    total_users_row = next(
        line for line in data_lines if line.startswith(GaugeName.TOTAL_USERS.value)
    )
    assert total_users_row.split("\t")[2] == "9"


def test_flask_metrics_gauges_latest_formats_float_value_cell(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN an AVG-kind gauge seeded with a non-None value_float (and value_int None)
    WHEN `flask metrics gauges-latest` runs
    THEN the CLI exits 0 and the formatted float appears in the value_float cell,
        exercising the `_gauge_value_cell(float)` branch end-to-end.
    """
    app = metrics_enabled_runner_app
    inside = _bucket_inside_day_window()

    with app.app_context():
        assert Anonymous_Gauges.query.count() == 0
        _seed_gauge_row(
            GaugeName.AVG_URLS_PER_UTUB, inside, value_float=GAUGE_FLOAT_VALUE
        )

    runner: FlaskCliRunner = app.test_cli_runner()
    result = runner.invoke(args=["metrics", "gauges-latest"])

    assert result.exit_code == 0, result.output
    assert GAUGES_LATEST_HEADER in result.output
    lines = [line for line in result.output.splitlines() if line.strip()]
    data_lines = lines[lines.index(GAUGES_LATEST_HEADER) + 1 :]
    avg_gauge_row = next(
        line
        for line in data_lines
        if line.startswith(GaugeName.AVG_URLS_PER_UTUB.value)
    )
    columns = avg_gauge_row.split("\t")
    assert columns[2] == ""
    assert columns[3] == GAUGE_FLOAT_VALUE_CELL


def test_flask_metrics_gauge_timeseries_formats_float_value_cell(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN an AVG-kind gauge seeded with a non-None value_float (and value_int None)
    WHEN `flask metrics gauge-timeseries --name=avg_urls_per_utub --window=day` runs
    THEN the CLI exits 0 and the formatted float appears in the value_float cell,
        exercising the `_gauge_value_cell(float)` branch end-to-end.
    """
    app = metrics_enabled_runner_app
    inside = _bucket_inside_day_window()

    with app.app_context():
        assert Anonymous_Gauges.query.count() == 0
        _seed_gauge_row(
            GaugeName.AVG_URLS_PER_UTUB, inside, value_float=GAUGE_FLOAT_VALUE
        )

    runner: FlaskCliRunner = app.test_cli_runner()
    result = runner.invoke(
        args=[
            "metrics",
            "gauge-timeseries",
            "--name=avg_urls_per_utub",
            "--window=day",
        ]
    )

    assert result.exit_code == 0, result.output
    assert GAUGE_TIMESERIES_HEADER in result.output
    lines = [line for line in result.output.splitlines() if line.strip()]
    data_lines = lines[lines.index(GAUGE_TIMESERIES_HEADER) + 1 :]
    assert len(data_lines) == 1
    columns = data_lines[0].split("\t")
    assert columns[1] == ""
    assert columns[2] == GAUGE_FLOAT_VALUE_CELL


def test_flask_metrics_gauges_list_prints_every_gauge(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN any state (gauges-list is a pure registry walk)
    WHEN `flask metrics gauges-list` runs
    THEN the CLI exits 0, prints the header, and one row per GaugeName appears.
    """
    app = metrics_enabled_runner_app
    runner: FlaskCliRunner = app.test_cli_runner()

    result = runner.invoke(args=["metrics", "gauges-list"])

    assert result.exit_code == 0, result.output
    assert GAUGES_LIST_HEADER in result.output
    lines = [line for line in result.output.splitlines() if line.strip()]
    data_lines = lines[lines.index(GAUGES_LIST_HEADER) + 1 :]
    assert len(data_lines) == len(GaugeName)
    listed_names = {line.split("\t")[0] for line in data_lines}
    assert listed_names == {member.value for member in GaugeName}
