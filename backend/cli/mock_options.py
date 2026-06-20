import secrets
from datetime import timedelta

import click
from flask import Flask, current_app, session
from flask.cli import AppGroup, with_appcontext
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from sqlalchemy.exc import ProgrammingError

from backend.utils.db_table_names import TABLE_NAMES
from backend.db import db
from backend.cli.mock_constants import TEST_USER_COUNT
from backend.cli.mock_data.tags import generate_mock_tags
from backend.cli.mock_data.urls import generate_mock_urls, generate_custom_mock_url
from backend.cli.mock_data.users import generate_mock_users
from backend.cli.mock_data.utubmembers import generate_mock_utubmembers
from backend.cli.mock_data.utubs import generate_mock_utubs
from backend.extensions.metrics.registry_sync import sync_event_registry
from backend.metrics.events import DeviceType, EventName
from backend.metrics.gauges import GAUGE_REGISTRY, GaugeKind
from backend.metrics.latency import LatencyMetricName
from backend.models.anonymous_gauges import Anonymous_Gauges
from backend.models.anonymous_latency_samples import Anonymous_Latency_Samples
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.models.users import Users
from backend.utils.datetime_utils import utc_now

SEED_TEST_DATA_HOUR_OFFSETS: tuple[int, ...] = (0, 1, 2)

# Two fixed sample-time offsets (hours back from the current hour) so every
# seeded gauge has at least two timeseries points for the dashboard charts.
SEED_GAUGE_HOUR_OFFSETS: tuple[int, ...] = (0, 1)

# Deterministic sample values per gauge kind, keyed by sample-time offset so the
# seeded series shows movement across the two points. VOLUME / DISTRIBUTION_MAX
# write an integer (valueInt); DISTRIBUTION_AVG writes a float (valueFloat).
SEED_GAUGE_INT_VALUES: dict[int, int] = {0: 42, 1: 40}
SEED_GAUGE_FLOAT_VALUES: dict[int, float] = {0: 4.5, 1: 4.0}

# Two endpoints (each with a method) the latency seeder writes a percentile
# distribution for, so the dashboard's Backend Performance tab renders a
# multi-row table during the Selenium smoke test. Endpoint strings mirror the
# Flask dot-notation route names the flush worker promotes to flat columns.
SEED_LATENCY_ENDPOINTS: tuple[tuple[str, str], ...] = (
    ("utubs.get_utub", "GET"),
    ("urls.add_url", "POST"),
)

# Device types each seeded endpoint gets a sample distribution for, so the
# JSONB `device_type` dimension is populated for both classes.
SEED_LATENCY_DEVICE_TYPES: tuple[DeviceType, ...] = (
    DeviceType.MOBILE,
    DeviceType.DESKTOP,
)

# Ten fixed durationMs values per (endpoint, observed_at, device_type) tuple.
# Chosen so the percentiles are deterministic and easy to assert: linear
# interpolation by `percentile_cont` over a sorted 10-point sample gives
# p50 = 55.0, p95 = 95.5, p99 = 99.1.
SEED_LATENCY_DURATIONS_MS: tuple[float, ...] = (
    10.0,
    20.0,
    30.0,
    40.0,
    50.0,
    60.0,
    70.0,
    80.0,
    90.0,
    100.0,
)

HELP_SUMMARY_MOCKS = """Add mock data to the dev database."""

HELP_SUMMARY_DB = """Clear or drop the dev database. Pass `test` as an argument to perform actions on the test database.\nFor example:\n\n`flask managedb clear test`
    """

USER_ID_INVALID_TO_LOGIN_WITH = "User ID not found, cannot login"

mocks_cli = AppGroup(
    "addmock",
    context_settings={"ignore_unknown_options": True},
    help=HELP_SUMMARY_MOCKS,
)
db_manage_cli = AppGroup(
    "managedb", context_settings={"ignore_unknown_options": True}, help=HELP_SUMMARY_DB
)


@mocks_cli.command("users", help="Add test users to the database.")
def mock_users():
    print("\n\n--- Adding mock users ---\n")
    generate_mock_users(db)
    print("\n--- Finished adding mock users ---\n\n")


@mocks_cli.command("utubs", help="Adds all users, and has them make UTubs.")
@click.option(
    "--no-dupes", is_flag=True, help="Prevent UTubs being created with the same name"
)
def mock_utubs(no_dupes: bool):
    print("\n\n--- Adding mock UTubs ---\n")
    generate_mock_users(db)
    generate_mock_utubs(db, no_dupes)
    print("\n--- Finished adding mock UTubs ---\n\n")


@mocks_cli.command(
    "utubmembers", help="Adds all users to each UTub. Does all of users/utubs."
)
@click.option(
    "--no-dupes", is_flag=True, help="Prevent UTubs being created with the same name"
)
def mock_members(no_dupes: bool):
    print("\n\n--- Adding mock UTub members ---\n")
    generate_mock_users(db)
    generate_mock_utubs(db, no_dupes)
    generate_mock_utubmembers(db)
    print("\n--- Finished adding mock UTub members ---\n\n")


@mocks_cli.command(
    "url",
    help="Adds a URL to each UTub, added by UTub creator. Does all of users/utubs/utubmembers.",
)
@click.argument("urls", nargs=-1, required=True)
@click.option(
    "--no-dupes", is_flag=True, help="Prevent UTubs being created with the same name"
)
def mock_url(urls: list[str], no_dupes: bool):
    print(f"\n\n--- Adding mock URLs: {urls} to each UTub  ---\n")
    generate_mock_users(db)
    generate_mock_utubs(db, no_dupes)
    generate_mock_utubmembers(db)
    generate_custom_mock_url(db, urls)
    print("\n--- Finished adding mock URLs to each UTub ---\n\n")


@mocks_cli.command(
    "urls", help="Adds URLs to each UTub. Does all of users/utubs/utubmembers."
)
@click.option(
    "--no-dupes", is_flag=True, help="Prevent UTubs being created with the same name"
)
def mock_urls(no_dupes: bool):
    print("\n\n--- Adding mock URLs to each UTub  ---\n")
    generate_mock_users(db)
    generate_mock_utubs(db, no_dupes)
    generate_mock_utubmembers(db)
    generate_mock_urls(db)
    print("\n--- Finished adding mock URLs to each UTub ---\n\n")


@mocks_cli.command(
    "tags", help="Adds tags to each URL. Does all of users/utubs/utubmembers/urls."
)
@click.option(
    "--no-dupes", is_flag=True, help="Prevent UTubs being created with the same name"
)
def mock_tags(no_dupes: bool):
    _add_all(db, no_dupes)


@mocks_cli.command("all", help="Adds all mock data to the database.")
@click.option(
    "--no-dupes", is_flag=True, help="Prevent UTubs being created with the same name"
)
def mock_all(no_dupes: bool):
    _add_all(db, no_dupes)


def _add_all(db: SQLAlchemy, no_dupes: bool):
    print("\n\n--- Adding all mock users, UTubs, members, urls, and tags  ---\n")
    generate_mock_users(db)
    generate_mock_utubs(db, no_dupes)
    generate_mock_utubmembers(db)
    generate_mock_urls(db)
    generate_mock_tags(db)
    rows_written = _seed_uniform_test_data()
    print(
        f"\n--- Seeded {rows_written} AnonymousMetrics + AnonymousGauges rows for UI tests ---"
    )
    print(
        "\n--- Finished adding all mock users, UTubs, members, urls, tags, and metrics ---\n\n"
    )


@mocks_cli.command(
    "login",
    help="Logs in user with user_id. Adds all mock users first. Default ID is 1.",
)
@click.argument("user_id", nargs=1, required=True, default=1, type=int)
@with_appcontext
def login_mock_user(user_id: int):
    if not isinstance(user_id, int) or (user_id > TEST_USER_COUNT or user_id <= 0):
        click.echo(message=USER_ID_INVALID_TO_LOGIN_WITH, err=True)
        exception = click.ClickException(message=USER_ID_INVALID_TO_LOGIN_WITH)
        exception.exit_code = 1

    user: Users = Users.query.get(user_id)
    if not user:
        generate_mock_users(db, silent=True)
        user: Users = Users.query.get(user_id)

    with current_app.test_request_context("/"):
        session["_user_id"] = user.get_id()
        session["_fresh"] = True
        session["_id"] = _create_random_identifier()
        session.sid = _create_random_sid()
        session.modified = True

        click.echo(f"{session.sid}")
        current_app.session_interface.save_session(
            current_app, session, response=current_app.make_response("Testing")
        )


def _create_random_identifier() -> str:
    return secrets.token_hex(64)


def _create_random_sid() -> str:
    return secrets.token_urlsafe(32)


@db_manage_cli.command(
    "clear", help="Clear the tables in the database - same schema, empty tables."
)
@click.argument(
    "db_type",
    type=click.Choice(
        (
            "dev",
            "test",
        ),
        case_sensitive=False,
    ),
    default="dev",
)
def clear_db(db_type: str):
    print(f"\n\n--- Emptying each table in {db_type} database ---\n")
    engine = db.engines[db_type]
    con = engine.connect()
    meta = MetaData(engine)
    meta.reflect()
    # Exclude alembic_version from the drop/create cycle so migration state
    # survives `clear` — mirrors the existing --keep-alembic flag on
    # `managedb drop`. Otherwise every dev deploy's post-up `flask managedb
    # clear` wipes the version_num row, leaving the next deploy's `flask db
    # upgrade` trying to re-run from the initial migration and crashing on
    # the already-created enum types.
    if TABLE_NAMES.ALEMBIC_VERSION in meta.tables:
        meta.remove(meta.tables[TABLE_NAMES.ALEMBIC_VERSION])
    meta.drop_all()
    meta.create_all()
    con.close()
    print(f"\n--- Finished emptying each table in {db_type} database ---\n\n")


@db_manage_cli.command(
    "create", help="Create the tables in the database. Only for dev database"
)
@click.argument(
    "db_type",
    type=click.Choice(
        ("dev",),
        case_sensitive=False,
    ),
    default="dev",
)
@with_appcontext
def create_db(db_type: str):
    print(f"\n\n--- Creating each table in {db_type} database ---\n")
    db.create_all()
    print(f"\n--- Finished creating each table in {db_type} database ---\n\n")


@db_manage_cli.command("drop", help="Drop the tables from the database.")
@click.argument(
    "db_type",
    type=click.Choice(
        (
            "dev",
            "test",
        ),
        case_sensitive=False,
    ),
    default="dev",
)
@click.option(
    "--keep-alembic",
    is_flag=True,
    help="Preserve alembic_version table so 'flask db upgrade' remains a no-op",
)
@with_appcontext
def drop_db(db_type: str, keep_alembic: bool):
    """Drop all tables in the specified database.

    By default the alembic_version table is also dropped so that a subsequent
    ``flask db upgrade`` re-runs every migration from scratch.  Pass
    ``--keep-alembic`` to preserve the alembic_version table (useful when you
    want ``flask db upgrade`` to remain a no-op after the drop).
    """
    print(f"\n\n--- Dropping each table in {db_type} database ---\n")
    engine = db.engines[db_type]
    con = engine.connect()
    meta = MetaData(engine)
    meta.reflect()

    if keep_alembic:
        print("\n\nSkipping alembic_version to preserve migrations...\n\n")

        tables_to_drop = []
        for table_to_delete in TABLE_NAMES.SORTED_TABLES_FOR_DELETION:
            for table in meta.sorted_tables:
                if table.name == table_to_delete:
                    tables_to_drop.append(table)

        # Drop only the tables we want
        for table in tables_to_drop:
            table.drop(engine)
    else:
        meta.drop_all()
    con.close()
    print(f"\n--- Dropped each table in {db_type} database ---\n\n")


def _seed_uniform_test_data() -> int:
    """Insert a deterministic set of AnonymousMetrics rows for UI tests.

    Bypasses Redis and writes directly to Postgres so the admin metrics
    dashboard renders non-empty tables/charts during the Selenium smoke
    test. Covers all three event categories (API, UI, DOMAIN) with known
    hour-bucket-aligned `bucket_start` values. Idempotent on
    `(bucket_start, event_name, dimensions)` via the table's
    `unique_metric_bucket` constraint — repeated runs are safe. Requires
    an active Flask app context.

    Examples:
        Writes nine rows across three hour buckets ending at the current
        hour, one row per bucket for each of: api_hit (API),
        ui_login_submit (UI), utub_created (DOMAIN). Also calls
        `_seed_uniform_gauges()` and `_seed_uniform_latency()` at the end so
        AnonymousGauges and AnonymousLatencySamples are seeded for every
        consumer of `seed-uniform-test-data` (e.g. the Selenium
        `seeded_metrics` autouse fixture). Returns the combined count of
        AnonymousMetrics + AnonymousGauges + AnonymousLatencySamples rows
        actually inserted (zero on a re-run with all rows present).
    """
    sync_event_registry(current_app._get_current_object())  # type: ignore[attr-defined]

    seed_events: tuple[tuple[EventName, dict], ...] = (
        (
            EventName.API_HIT,
            {"endpoint": "/api/utubs", "method": "GET", "status_code": 200},
        ),
        (EventName.UI_LOGIN_SUBMIT, {"device_type": DeviceType.DESKTOP.value}),
        (EventName.UTUB_CREATED, {}),
        # Pipeline-health stacked-bar coverage: four
        # (transport × device_type) combinations at one fixed batch-size
        # bucket so the Selenium dashboard test sees one rect per swatch.
        (
            EventName.API_METRICS_INGEST_BATCH,
            {
                "batch_size_bucket": "2-5",
                "transport": "fetch",
                "device_type": DeviceType.DESKTOP.value,
            },
        ),
        (
            EventName.API_METRICS_INGEST_BATCH,
            {
                "batch_size_bucket": "2-5",
                "transport": "fetch",
                "device_type": DeviceType.MOBILE.value,
            },
        ),
        (
            EventName.API_METRICS_INGEST_BATCH,
            {
                "batch_size_bucket": "2-5",
                "transport": "beacon",
                "device_type": DeviceType.DESKTOP.value,
            },
        ),
        (
            EventName.API_METRICS_INGEST_BATCH,
            {
                "batch_size_bucket": "2-5",
                "transport": "beacon",
                "device_type": DeviceType.MOBILE.value,
            },
        ),
    )

    now = utc_now()
    current_hour_aligned = now.replace(minute=0, second=0, microsecond=0)
    rows_written = 0
    for hour_offset in SEED_TEST_DATA_HOUR_OFFSETS:
        # Hour-aligned bucket start matches the epoch-aligned bucket key
        # written by `MetricsWriter`, so the query service can group rows.
        bucket_start = current_hour_aligned - timedelta(hours=hour_offset)

        for event_name, dimensions in seed_events:
            existing_row = Anonymous_Metrics.query.filter_by(
                bucket_start=bucket_start,
                event_name=event_name.value,
                dimensions=dimensions,
            ).one_or_none()
            if existing_row is not None:
                continue
            # Mirror the flush worker's flat-column promotion: api_hit rows
            # carry endpoint/method/status_code in dedicated columns so the
            # top-events query (which filters on `endpoint IS NOT NULL`) can
            # reach them. Without this, seeded rows would only live in the
            # `dimensions` JSONB and the API tab would render the empty state.
            if event_name is EventName.API_HIT:
                endpoint_value = dimensions.get("endpoint")
                method_value = dimensions.get("method")
                status_code_value = dimensions.get("status_code")
            else:
                endpoint_value = None
                method_value = None
                status_code_value = None
            db.session.add(
                Anonymous_Metrics(
                    event_name=event_name.value,
                    bucket_start=bucket_start,
                    endpoint=endpoint_value,
                    method=method_value,
                    status_code=status_code_value,
                    dimensions=dimensions,
                    count=1 + hour_offset,
                )
            )
            rows_written += 1
    db.session.commit()
    gauge_rows_written = _seed_uniform_gauges()
    latency_rows_written = _seed_uniform_latency()
    return rows_written + gauge_rows_written + latency_rows_written


def _seed_uniform_gauges() -> int:
    """Insert a deterministic set of AnonymousGauges rows for UI tests.

    Writes two timeseries points (two sample timestamps ending at the current
    hour) for every `GaugeName`, so the admin dashboard's Gauges tab renders a
    non-empty trend chart per gauge during the Selenium smoke test. VOLUME and
    DISTRIBUTION_MAX gauges populate `value_int`; DISTRIBUTION_AVG gauges
    populate `value_float` (the other column stays NULL), matching the
    sampler's per-kind column routing. Idempotent on `(gaugeName, sampledAt)`
    via a `one_or_none()` existence skip — repeated runs insert nothing new.
    Requires an active Flask app context.

    The INSERT/commit body is wrapped in `try/except ProgrammingError`: if the
    `AnonymousGauges` table does not exist yet (e.g. a migration-downgrade
    state before the table was added), the exception is logged as a warning and
    the function returns 0, so `flask addmock all` stays safe at any migration
    revision.

    Examples:
        With two sample offsets and sixteen gauges, writes thirty-two rows on a
        fresh DB (two points per gauge) and returns 32; a re-run with all rows
        already present returns 0.
    """
    now = utc_now()
    current_hour_aligned = now.replace(minute=0, second=0, microsecond=0)
    rows_written = 0
    try:
        for hour_offset in SEED_GAUGE_HOUR_OFFSETS:
            sampled_at = current_hour_aligned - timedelta(hours=hour_offset)
            int_value = SEED_GAUGE_INT_VALUES[hour_offset]
            float_value = SEED_GAUGE_FLOAT_VALUES[hour_offset]

            for gauge_name, definition in GAUGE_REGISTRY.items():
                existing_row = Anonymous_Gauges.query.filter_by(
                    gauge_name=gauge_name.value,
                    sampled_at=sampled_at,
                ).one_or_none()
                if existing_row is not None:
                    continue

                if definition.kind is GaugeKind.DISTRIBUTION_AVG:
                    value_int = None
                    value_float = float_value
                else:
                    value_int = int_value
                    value_float = None

                db.session.add(
                    Anonymous_Gauges(
                        gauge_name=gauge_name.value,
                        sampled_at=sampled_at,
                        value_int=value_int,
                        value_float=value_float,
                        dimensions={},
                    )
                )
                rows_written += 1
        db.session.commit()
    except ProgrammingError:
        db.session.rollback()
        current_app.logger.warning(
            "addmock: AnonymousGauges table missing; skipped gauge seeding"
        )
        return 0
    return rows_written


def _seed_uniform_latency() -> int:
    """Insert a deterministic set of AnonymousLatencySamples rows for UI tests.

    Writes a fixed 10-point `durationMs` distribution per
    (endpoint, observed_at, device_type) tuple across the same hour offsets
    the other seeders use, so the admin dashboard's Backend Performance tab
    renders a non-empty per-endpoint percentile table and a latency-over-time
    chart during the Selenium smoke test. The distribution is chosen so the
    exact `percentile_cont` outputs are stable and assertable (p50 = 55.0,
    p95 = 95.5, p99 = 99.1 for the 10-point linear set). `device_type` is kept
    in the JSONB `dimensions` column, mirroring the flush worker's write shape;
    `endpoint`/`method` are promoted to flat columns. Idempotent on
    `(endpoint, observed_at)` via a `first()` existence skip — each pair writes
    a multi-row (device_type x duration) distribution, so a single-row
    `one_or_none()` would raise `MultipleResultsFound` on the re-run; `first()`
    only probes existence. Repeated runs insert nothing new. Requires an active
    Flask app context.

    The INSERT/commit body is wrapped in `try/except ProgrammingError`: if the
    `AnonymousLatencySamples` table does not exist yet (e.g. a
    migration-downgrade state before the table was added), the exception is
    logged as a warning and the function returns 0, so `flask addmock all`
    stays safe at any migration revision (mirroring `_seed_uniform_gauges`).

    Examples:
        With three hour offsets, two endpoints, two device types, and a
        10-point distribution, writes 3 * 2 * 2 * 10 = 120 rows on a fresh DB
        and returns 120; a re-run with all rows already present returns 0.
    """
    now = utc_now()
    current_hour_aligned = now.replace(minute=0, second=0, microsecond=0)
    rows_written = 0
    metric_name_value = LatencyMetricName.API_REQUEST_DURATION.value
    try:
        for hour_offset in SEED_TEST_DATA_HOUR_OFFSETS:
            observed_at = current_hour_aligned - timedelta(hours=hour_offset)

            for endpoint_value, method_value in SEED_LATENCY_ENDPOINTS:
                # Idempotency: one existence probe per (endpoint, observed_at)
                # bucket. A present row for this pair means a prior seed run
                # already wrote the full distribution for it, so skip the whole
                # (device_type x duration) inner loop.
                existing_row = Anonymous_Latency_Samples.query.filter_by(
                    endpoint=endpoint_value,
                    observed_at=observed_at,
                ).first()
                if existing_row is not None:
                    continue

                for device_type in SEED_LATENCY_DEVICE_TYPES:
                    for duration_ms in SEED_LATENCY_DURATIONS_MS:
                        db.session.add(
                            Anonymous_Latency_Samples(
                                metric_name=metric_name_value,
                                endpoint=endpoint_value,
                                method=method_value,
                                observed_at=observed_at,
                                duration_ms=duration_ms,
                                dimensions={"device_type": device_type.value},
                            )
                        )
                        rows_written += 1
        db.session.commit()
    except ProgrammingError:
        db.session.rollback()
        current_app.logger.warning(
            "addmock: AnonymousLatencySamples table missing; " "skipped latency seeding"
        )
        return 0
    return rows_written


@mocks_cli.command(
    "seed-uniform-test-data",
    help="Seed a small fixed set of AnonymousMetrics rows for Selenium tests.",
)
@with_appcontext
def seed_uniform_test_data_command() -> None:
    rows_written = _seed_uniform_test_data()
    click.echo(f"metrics: seeded {rows_written} AnonymousMetrics rows for UI tests.")


@mocks_cli.command(
    "seed-uniform-gauges",
    help="Seed a small fixed set of AnonymousGauges rows for Selenium tests.",
)
@with_appcontext
def seed_uniform_gauges_command() -> None:
    rows_written = _seed_uniform_gauges()
    click.echo(f"metrics: seeded {rows_written} AnonymousGauges rows for UI tests.")


@mocks_cli.command(
    "seed-uniform-latency",
    help="Seed a small fixed set of AnonymousLatencySamples rows for Selenium tests.",
)
@with_appcontext
def seed_uniform_latency_command() -> None:
    rows_written = _seed_uniform_latency()
    click.echo(
        f"metrics: seeded {rows_written} AnonymousLatencySamples rows for UI tests."
    )


def register_mocks_db_cli(app: Flask):
    app.cli.add_command(mocks_cli)
    app.cli.add_command(db_manage_cli)
