import pytest

from backend.cli.mock_constants import (
    MOCK_ADMIN_USERNAME,
    MOCK_ADMIN_UTUB_NAME,
    MOCK_TAGS,
    MOCK_URL_STRINGS,
    TEST_USER_COUNT,
)
from backend.cli.mock_options import (
    SEED_LATENCY_DEVICE_TYPES,
    SEED_LATENCY_DURATIONS_MS,
    SEED_LATENCY_ENDPOINTS,
    SEED_LATENCY_ROLLUP_DAY_OFFSETS,
    SEED_TEST_DATA_HOUR_OFFSETS,
)
from backend.models.anonymous_latency_rollups import Anonymous_Latency_Daily_Rollups
from backend.models.anonymous_latency_samples import Anonymous_Latency_Samples
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.models.users import User_Role, Users
from backend.models.utub_members import Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from tests.integration.cli.utils import (
    verify_custom_url_added_to_all_utubs,
    verify_custom_url_in_database,
    verify_users_added,
    verify_utubs_added_no_duplicates,
    verify_utubs_added_duplicates,
    verify_utubmembers_added,
    verify_urls_in_database,
    verify_urls_added_to_all_utubs,
    verify_tags_in_utubs,
    verify_tags_added_to_all_urls_in_utubs,
    verify_tracking_seed_urls_added,
)

pytestmark = pytest.mark.cli

DUPLICATE_COUNT = 2
# Three category-anchor events (API_HIT, UI_LOGIN_SUBMIT, UTUB_CREATED) plus
# four `(transport × device_type)` rows for API_METRICS_INGEST_BATCH so the
# Pipeline Health stacked-bar card sees one segment per swatch.
SEEDED_EVENT_COUNT_PER_BUCKET = 7
EXPECTED_SEEDED_ROW_COUNT = (
    len(SEED_TEST_DATA_HOUR_OFFSETS) * SEEDED_EVENT_COUNT_PER_BUCKET
)
# The latency seeder writes one row per
# (hour-offset × endpoint × device-type × duration) tuple (3 × 2 × 2 × 10 = 120
# on a fresh DB). Deriving from the seed constants keeps this in lockstep if the
# distribution changes.
EXPECTED_SEEDED_LATENCY_ROW_COUNT = (
    len(SEED_TEST_DATA_HOUR_OFFSETS)
    * len(SEED_LATENCY_ENDPOINTS)
    * len(SEED_LATENCY_DEVICE_TYPES)
    * len(SEED_LATENCY_DURATIONS_MS)
)
# The rollup seeder writes one row per (day-offset × endpoint) tuple.
# No device_type multiplier — the rollup aggregates across all device types
# (device_type is not stored in the rollup model), unlike the raw latency count
# which uses SEED_TEST_DATA_HOUR_OFFSETS * SEED_LATENCY_ENDPOINTS *
# SEED_LATENCY_DEVICE_TYPES * len(SEED_LATENCY_DURATIONS_MS).
EXPECTED_SEEDED_LATENCY_ROLLUP_ROW_COUNT = len(SEED_LATENCY_ROLLUP_DAY_OFFSETS) * len(
    SEED_LATENCY_ENDPOINTS
)


def test_add_mock_users(runner):
    """
    GIVEN a developer wanting to add mock users to the database
    WHEN the developer provides the following CLI command:
        `flask addmock users`
    THEN verify that mock users are added to the database

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner
    cli_runner.invoke(args=["addmock", "users"])
    with app.app_context():
        verify_users_added()


def test_add_mock_utubs_with_duplicates(runner):
    """
    GIVEN a developer wanting to add mock UTubs to the database
    WHEN the developer provides the following CLI command:
        `flask addmock utubs`
    THEN verify that mock users are added, and that duplicate UTubs are added to the database.

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner

    for count in range(DUPLICATE_COUNT):
        cli_runner.invoke(args=["addmock", "utubs"])
        with app.app_context():
            verify_users_added()
            verify_utubs_added_duplicates(count + 1)


def test_add_mock_utubs_no_utub_duplicates(runner):
    """
    GIVEN a developer wanting to add mock UTubs to the database without duplicates
    WHEN the developer provides the following CLI command:
        `flask addmock utubs --no-dupes`
    THEN verify that mock users are added, and that UTubs are added to the database without duplicates.

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner

    for _ in range(DUPLICATE_COUNT):
        cli_runner.invoke(args=["addmock", "utubs", "--no-dupes"])
        with app.app_context():
            verify_users_added()
            verify_utubs_added_no_duplicates()


def test_add_mock_utub_members_with_utub_duplicates(runner):
    """
    GIVEN a developer wanting to add mock UTub members to the database containing duplicate UTubs
    WHEN the developer provides the following CLI command:
        `flask addmock utubmembers`
    THEN verify that mock users are added, that UTubs are added to the database with duplicates,
        and that UTub members are added to all created UTubs

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner

    for count in range(DUPLICATE_COUNT):
        cli_runner.invoke(args=["addmock", "utubmembers"])
        with app.app_context():
            verify_users_added()
            verify_utubs_added_duplicates(count + 1)
            verify_utubmembers_added()


def test_add_mock_utub_members_no_utub_duplicates(runner):
    """
    GIVEN a developer wanting to add mock UTub members to the database without duplicate UTubs
    WHEN the developer provides the following CLI command:
        `flask addmock utubmembers --no-dupes`
    THEN verify that mock users are added, that UTubs are added to the database without duplicates,
        and that UTub members are added to all created UTubs

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner

    for _ in range(DUPLICATE_COUNT):
        cli_runner.invoke(args=["addmock", "utubmembers", "--no-dupes"])
        with app.app_context():
            verify_users_added()
            verify_utubs_added_no_duplicates()
            verify_utubmembers_added()


def test_add_mock_admin_full_participant(runner):
    """
    GIVEN a fully seeded dev database (`flask addmock all`)
    WHEN the developer runs the opt-in `flask addmock admin`
    THEN a dedicated admin user u4i_admin1 is created with the ADMIN role, joins
        every existing UTub, owns exactly one new UTub that every other mock user
        is a member of, and that UTub is populated with the standard mock URLs
        and tags — while the default seed's user count is untouched until the
        opt-in command runs, and re-running it adds nothing new (idempotent).

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner

    cli_runner.invoke(args=["addmock", "all"])
    with app.app_context():
        # Assert-before-state: the default seed is unchanged — exactly
        # TEST_USER_COUNT users and no u4i_admin1 until the opt-in command runs.
        assert Users.query.count() == TEST_USER_COUNT
        assert Users.query.filter(Users.username == MOCK_ADMIN_USERNAME).count() == 0
        utub_count_before = Utubs.query.count()

    cli_runner.invoke(args=["addmock", "admin"])
    with app.app_context():
        admin: Users = Users.query.filter(Users.username == MOCK_ADMIN_USERNAME).first()
        assert admin is not None
        assert admin.role == User_Role.ADMIN
        assert admin.email_validated
        assert Users.query.count() == TEST_USER_COUNT + 1

        admin_utubs = Utubs.query.filter(Utubs.name == MOCK_ADMIN_UTUB_NAME).all()
        assert len(admin_utubs) == 1
        admin_utub = admin_utubs[0]
        assert admin_utub.utub_creator == admin.id
        assert Utubs.query.count() == utub_count_before + 1

        # The admin is a member of every UTub in the database.
        for utub in Utubs.query.all():
            assert Utub_Members.query.get((utub.id, admin.id)) is not None

        # Every mock user is a member of the admin's UTub.
        member_ids = {member.user_id for member in admin_utub.members}
        assert member_ids == {user.id for user in Users.query.all()}

        # The admin's UTub is populated like the others: URLs, fully tagged.
        assert Utub_Urls.query.filter(
            Utub_Urls.utub_id == admin_utub.id
        ).count() == len(MOCK_URL_STRINGS)
        assert Utub_Tags.query.filter(
            Utub_Tags.utub_id == admin_utub.id
        ).count() == len(MOCK_TAGS)

    # Idempotent: a second run creates no duplicate admin user or UTub.
    cli_runner.invoke(args=["addmock", "admin"])
    with app.app_context():
        assert Users.query.filter(Users.username == MOCK_ADMIN_USERNAME).count() == 1
        assert Utubs.query.filter(Utubs.name == MOCK_ADMIN_UTUB_NAME).count() == 1
        assert Users.query.count() == TEST_USER_COUNT + 1


def test_add_custom_mock_urls_with_utub_duplicates_one_by_one(runner):
    """
    GIVEN a developer wanting to add custom mock URLs to UTubs, including duplicate UTubs
    WHEN the developer provides the following CLI command:
        `flask addmock url foo bar baz`
    THEN verify that mock users are added, that UTubs are added to the database with duplicates,
        that UTub members are added to all created UTubs, and that all URLs are added

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner
    URLS = ["google.com", "macro macro macro", "facebook.com"]

    for count in range(DUPLICATE_COUNT):
        cli_runner.invoke(args=["addmock", "url", URLS[0]])
        with app.app_context():
            verify_users_added()
            verify_utubs_added_duplicates(count + 1)
            verify_custom_url_in_database(URLS[0])
            verify_custom_url_added_to_all_utubs(URLS[0])

    # Add additional URLs
    for url in URLS[1:]:
        cli_runner.invoke(args=["addmock", "url", url])
        with app.app_context():
            verify_custom_url_in_database(url)
            verify_custom_url_added_to_all_utubs(url)


def test_add_custom_mock_urls_with_utub_duplicates_all_at_once(runner):
    """
    GIVEN a developer wanting to add custom mock URLs to UTubs, including duplicate UTubs
    WHEN the developer provides the following CLI command:
        `flask addmock url foo bar baz`
    THEN verify that mock users are added, that UTubs are added to the database with duplicates,
        that UTub members are added to all created UTubs, and that all URLs are added

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner
    URLS = ["google.com", "macro macro macro", "facebook.com"]

    for count in range(DUPLICATE_COUNT):
        cli_runner.invoke(args=["addmock", "url", URLS[0], URLS[1], URLS[2]])
        with app.app_context():
            verify_users_added()
            verify_utubs_added_duplicates(count + 1)
            for url in URLS:
                verify_custom_url_in_database(url)
                verify_custom_url_added_to_all_utubs(url)


def test_add_custom_mock_urls_no_utub_duplicates_one_by_one(runner):
    """
    GIVEN a developer wanting to add custom mock URLs to UTubs, including duplicate UTubs
    WHEN the developer provides the following CLI command:
        `flask addmock url foo bar baz`
    THEN verify that mock users are added, that UTubs are added to the database with duplicates,
        that UTub members are added to all created UTubs, and that all URLs are added

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner
    URLS = ["google.com", "macro macro macro", "facebook.com"]

    cli_runner.invoke(args=["addmock", "url", "--no-dupes", URLS[0]])
    with app.app_context():
        verify_users_added()
        verify_utubs_added_no_duplicates()
        verify_custom_url_in_database(URLS[0])
        verify_custom_url_added_to_all_utubs(URLS[0])

    # Add additional URLs
    for url in URLS[1:]:
        cli_runner.invoke(args=["addmock", "url", url])
        with app.app_context():
            verify_custom_url_in_database(url)
            verify_custom_url_added_to_all_utubs(url)


def test_add_custom_mock_urls_no_utub_duplicates_all_at_once(runner):
    """
    GIVEN a developer wanting to add custom mock URLs to UTubs, including duplicate UTubs
    WHEN the developer provides the following CLI command:
        `flask addmock url foo bar baz`
    THEN verify that mock users are added, that UTubs are added to the database with duplicates,
        that UTub members are added to all created UTubs, and that all URLs are added

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner
    URLS = ["google.com", "macro macro macro", "facebook.com"]

    cli_runner.invoke(args=["addmock", "url", "--no-dupes", URLS[0], URLS[1], URLS[2]])
    with app.app_context():
        verify_users_added()
        verify_utubs_added_no_duplicates()
        for url in URLS:
            verify_custom_url_in_database(url)
            verify_custom_url_added_to_all_utubs(url)


def test_add_mock_urls_with_utub_duplicates(runner):
    """
    GIVEN a developer wanting to add mock URLs to each UTub within the database containing duplicate UTubs
    WHEN the developer provides the following CLI command:
        `flask addmock urls`
    THEN verify that mock users are added, that UTubs are added to the database with duplicates,
        that UTub members are added to all created UTubs, and that mock URLs are added to each UTub.

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner

    for count in range(DUPLICATE_COUNT):
        cli_runner.invoke(args=["addmock", "urls"])
        with app.app_context():
            verify_users_added()
            verify_utubs_added_duplicates(count + 1)
            verify_urls_in_database()
            verify_urls_added_to_all_utubs()


def test_add_mock_urls_no_utub_duplicates(runner):
    """
    GIVEN a developer wanting to add mock URLs to each UTub within the database without duplicate UTubs
    WHEN the developer provides the following CLI command:
        `flask addmock urls --no-dupes`
    THEN verify that mock users are added, that UTubs are added to the database without duplicates,
        that UTub members are added to all created UTubs, and that mock URLs are added to each UTub.

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner

    for _ in range(DUPLICATE_COUNT):
        cli_runner.invoke(args=["addmock", "urls", "--no-dupes"])
        with app.app_context():
            verify_users_added()
            verify_utubs_added_no_duplicates()
            verify_urls_in_database()
            verify_urls_added_to_all_utubs()


def test_add_tags_to_url_with_utub_duplicates(runner):
    """
    GIVEN a developer wanting to add mock Tags to each URL in a UTub within the database containing duplicate UTubs
    WHEN the developer provides the following CLI command:
        `flask addmock tags`
    THEN verify that mock users are added, that UTubs are added to the database without duplicates,
        that UTub members are added to all created UTubs, that mock URLs are added to each UTub,
        and that tags are added to each URL in each UTub.

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner

    for count in range(DUPLICATE_COUNT):
        cli_runner.invoke(args=["addmock", "tags"])
        with app.app_context():
            verify_users_added()
            verify_utubs_added_duplicates(count + 1)
            verify_urls_in_database()
            verify_urls_added_to_all_utubs()
            verify_tags_in_utubs()
            verify_tags_added_to_all_urls_in_utubs()


def test_add_tags_to_url_no_utub_duplicates(runner):
    """
    GIVEN a developer wanting to add mock Tags to each URL in a UTub within the database without duplicate UTubs
    WHEN the developer provides the following CLI command:
        `flask addmock tags`
    THEN verify that mock users are added, that UTubs are added to the database without duplicates,
        that UTub members are added to all created UTubs, that mock URLs are added to each UTub,
        and that tags are added to each URL in each UTub.

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner

    for _ in range(DUPLICATE_COUNT):
        cli_runner.invoke(args=["addmock", "tags", "--no-dupes"])
        with app.app_context():
            verify_users_added()
            verify_utubs_added_no_duplicates()
            verify_urls_in_database()
            verify_urls_added_to_all_utubs()
            verify_tags_in_utubs()
            verify_tags_added_to_all_urls_in_utubs()


def test_add_all_mock_data_with_utub_duplicates(runner):
    """
    GIVEN a developer wanting to add all mock data with potential duplicate UTubs
    WHEN the developer provides the following CLI command:
        `flask addmock all`
    THEN verify that mock users are added, that UTubs are added to the database with potential duplicates,
        that UTub members are added to all created UTubs, that mock URLs are added to each UTub,
        and that tags are added to each URL in each UTub.

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner

    for count in range(DUPLICATE_COUNT):
        cli_runner.invoke(args=["addmock", "all"])
        with app.app_context():
            verify_users_added()
            verify_utubs_added_duplicates(count + 1)
            verify_urls_in_database()
            verify_urls_added_to_all_utubs()
            verify_tags_in_utubs()
            verify_tags_added_to_all_urls_in_utubs()

    verify_tracking_seed_urls_added(app, cli_runner)


def test_add_all_mock_data_with_no_utub_duplicates(runner):
    """
    GIVEN a developer wanting to add all mock data with no potential duplicate UTubs
    WHEN the developer provides the following CLI command:
        `flask addmock all --no-dupes`
    THEN verify that mock users are added, that UTubs are added to the database without duplicates,
        that UTub members are added to all created UTubs, that mock URLs are added to each UTub,
        and that tags are added to each URL in each UTub.

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner

    for _ in range(DUPLICATE_COUNT):
        cli_runner.invoke(args=["addmock", "all", "--no-dupes"])
        with app.app_context():
            verify_users_added()
            verify_utubs_added_no_duplicates()
            verify_urls_in_database()
            verify_urls_added_to_all_utubs()
            verify_tags_in_utubs()
            verify_tags_added_to_all_urls_in_utubs()

    verify_tracking_seed_urls_added(app, cli_runner)


def test_seed_uniform_test_data_writes_expected_rows_and_is_idempotent(runner):
    """
    GIVEN a developer wanting to seed deterministic AnonymousMetrics rows for UI tests
    WHEN the developer provides the following CLI command:
        `flask addmock seed-uniform-test-data`
    THEN verify the command exits successfully, writes the expected number of rows
        (one row per (hour-offset, event) combination), and is idempotent across
        repeat invocations (no duplicate rows on a second invocation, because the
        seeder skips rows that already exist for the same bucket/event/dimensions).

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner

    with app.app_context():
        assert Anonymous_Metrics.query.count() == 0, (
            "AnonymousMetrics table must be empty before the seed CLI runs so "
            "that the row-count assertion measures only the rows this command "
            "wrote."
        )
        assert Anonymous_Latency_Samples.query.count() == 0, (
            "AnonymousLatencySamples table must be empty before the seed CLI "
            "runs so the latency row-count assertion measures only this "
            "command's writes."
        )
        assert Anonymous_Latency_Daily_Rollups.query.count() == 0, (
            "AnonymousLatencyDailyRollups table must be empty before the seed "
            "CLI runs so the rollup row-count assertion measures only this "
            "command's writes."
        )

    first_result = cli_runner.invoke(args=["addmock", "seed-uniform-test-data"])
    assert first_result.exit_code == 0, (
        f"First seed CLI invocation failed: exit={first_result.exit_code} "
        f"output={first_result.output}"
    )

    with app.app_context():
        rows_after_first_run = Anonymous_Metrics.query.count()
        assert rows_after_first_run == EXPECTED_SEEDED_ROW_COUNT, (
            f"Expected {EXPECTED_SEEDED_ROW_COUNT} seeded rows after first run, "
            f"got {rows_after_first_run}"
        )
        latency_rows_after_first_run = Anonymous_Latency_Samples.query.count()
        assert latency_rows_after_first_run == EXPECTED_SEEDED_LATENCY_ROW_COUNT, (
            f"Expected {EXPECTED_SEEDED_LATENCY_ROW_COUNT} seeded latency rows "
            f"after first run, got {latency_rows_after_first_run}"
        )
        rollup_rows_after_first_run = Anonymous_Latency_Daily_Rollups.query.count()
        assert (
            rollup_rows_after_first_run == EXPECTED_SEEDED_LATENCY_ROLLUP_ROW_COUNT
        ), (
            f"Expected {EXPECTED_SEEDED_LATENCY_ROLLUP_ROW_COUNT} seeded rollup "
            f"rows after first run, got {rollup_rows_after_first_run}"
        )

    second_result = cli_runner.invoke(args=["addmock", "seed-uniform-test-data"])
    assert second_result.exit_code == 0, (
        f"Second seed CLI invocation failed: exit={second_result.exit_code} "
        f"output={second_result.output}"
    )

    with app.app_context():
        rows_after_second_run = Anonymous_Metrics.query.count()
        assert rows_after_second_run == EXPECTED_SEEDED_ROW_COUNT, (
            "Seed CLI must be idempotent: second invocation must not add or "
            f"remove rows. Expected {EXPECTED_SEEDED_ROW_COUNT}, got "
            f"{rows_after_second_run}."
        )
        latency_rows_after_second_run = Anonymous_Latency_Samples.query.count()
        assert latency_rows_after_second_run == EXPECTED_SEEDED_LATENCY_ROW_COUNT, (
            "Seed CLI latency seeding must be idempotent: second invocation "
            "must not add or remove latency rows. Expected "
            f"{EXPECTED_SEEDED_LATENCY_ROW_COUNT}, got "
            f"{latency_rows_after_second_run}."
        )
        rollup_rows_after_second_run = Anonymous_Latency_Daily_Rollups.query.count()
        assert (
            rollup_rows_after_second_run == EXPECTED_SEEDED_LATENCY_ROLLUP_ROW_COUNT
        ), (
            "Seed CLI rollup seeding must be idempotent: second invocation must "
            "not add or remove rollup rows. Expected "
            f"{EXPECTED_SEEDED_LATENCY_ROLLUP_ROW_COUNT}, got "
            f"{rollup_rows_after_second_run}."
        )


def test_add_all_mock_data_also_seeds_anonymous_metrics(runner):
    """
    GIVEN a developer running the catch-all mock seed command
    WHEN the developer provides the following CLI command:
        `flask addmock all`
    THEN verify that the AnonymousMetrics table is also seeded (so
        a clean dev DB renders the admin metrics dashboard with data
        without a follow-up `seed-uniform-test-data` invocation), and
        that repeated invocations remain idempotent on the metrics
        table.

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner

    with app.app_context():
        assert Anonymous_Metrics.query.count() == 0
        assert Anonymous_Latency_Samples.query.count() == 0
        assert Anonymous_Latency_Daily_Rollups.query.count() == 0

    first_result = cli_runner.invoke(args=["addmock", "all"])
    assert first_result.exit_code == 0, (
        f"First `addmock all` invocation failed: exit={first_result.exit_code} "
        f"output={first_result.output}"
    )

    with app.app_context():
        rows_after_first_run = Anonymous_Metrics.query.count()
        assert rows_after_first_run == EXPECTED_SEEDED_ROW_COUNT, (
            f"Expected {EXPECTED_SEEDED_ROW_COUNT} AnonymousMetrics rows "
            f"after `addmock all`, got {rows_after_first_run}"
        )
        latency_rows_after_first_run = Anonymous_Latency_Samples.query.count()
        assert latency_rows_after_first_run == EXPECTED_SEEDED_LATENCY_ROW_COUNT, (
            f"Expected {EXPECTED_SEEDED_LATENCY_ROW_COUNT} "
            f"AnonymousLatencySamples rows after `addmock all`, got "
            f"{latency_rows_after_first_run}"
        )
        rollup_rows_after_first_run = Anonymous_Latency_Daily_Rollups.query.count()
        assert (
            rollup_rows_after_first_run == EXPECTED_SEEDED_LATENCY_ROLLUP_ROW_COUNT
        ), (
            f"Expected {EXPECTED_SEEDED_LATENCY_ROLLUP_ROW_COUNT} "
            f"AnonymousLatencyDailyRollups rows after `addmock all`, got "
            f"{rollup_rows_after_first_run}"
        )

    second_result = cli_runner.invoke(args=["addmock", "all"])
    assert second_result.exit_code == 0, (
        f"Second `addmock all` invocation failed: exit={second_result.exit_code} "
        f"output={second_result.output}"
    )

    with app.app_context():
        rows_after_second_run = Anonymous_Metrics.query.count()
        assert rows_after_second_run == EXPECTED_SEEDED_ROW_COUNT, (
            "`addmock all` metrics seeding must be idempotent: second "
            f"invocation must not add rows. Expected {EXPECTED_SEEDED_ROW_COUNT}, "
            f"got {rows_after_second_run}."
        )
        latency_rows_after_second_run = Anonymous_Latency_Samples.query.count()
        assert latency_rows_after_second_run == EXPECTED_SEEDED_LATENCY_ROW_COUNT, (
            "`addmock all` latency seeding must be idempotent: second "
            "invocation must not add latency rows. Expected "
            f"{EXPECTED_SEEDED_LATENCY_ROW_COUNT}, got "
            f"{latency_rows_after_second_run}."
        )
        rollup_rows_after_second_run = Anonymous_Latency_Daily_Rollups.query.count()
        assert (
            rollup_rows_after_second_run == EXPECTED_SEEDED_LATENCY_ROLLUP_ROW_COUNT
        ), (
            "`addmock all` rollup seeding must be idempotent: second invocation "
            "must not add rollup rows. Expected "
            f"{EXPECTED_SEEDED_LATENCY_ROLLUP_ROW_COUNT}, got "
            f"{rollup_rows_after_second_run}."
        )


def test_seed_uniform_latency_writes_expected_rows_and_is_idempotent(runner):
    """
    GIVEN a developer wanting to seed deterministic AnonymousLatencySamples rows
        for the admin dashboard's Backend Performance tab
    WHEN the developer provides the following CLI command:
        `flask addmock seed-uniform-latency`
    THEN verify the command exits successfully, writes the expected number of
        latency rows (one per (hour-offset × endpoint × device-type × duration)
        tuple), and is idempotent across repeat invocations (the seeder skips
        any (endpoint, observed_at) bucket that already has rows).

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner

    with app.app_context():
        assert Anonymous_Latency_Samples.query.count() == 0, (
            "AnonymousLatencySamples table must be empty before the seed CLI "
            "runs so the row-count assertion measures only this command's "
            "writes."
        )

    first_result = cli_runner.invoke(args=["addmock", "seed-uniform-latency"])
    assert first_result.exit_code == 0, (
        f"First latency seed CLI invocation failed: exit={first_result.exit_code} "
        f"output={first_result.output}"
    )

    with app.app_context():
        latency_rows_after_first_run = Anonymous_Latency_Samples.query.count()
        assert latency_rows_after_first_run == EXPECTED_SEEDED_LATENCY_ROW_COUNT, (
            f"Expected {EXPECTED_SEEDED_LATENCY_ROW_COUNT} seeded latency rows "
            f"after first run, got {latency_rows_after_first_run}"
        )

    second_result = cli_runner.invoke(args=["addmock", "seed-uniform-latency"])
    assert second_result.exit_code == 0, (
        f"Second latency seed CLI invocation failed: "
        f"exit={second_result.exit_code} output={second_result.output}"
    )

    with app.app_context():
        latency_rows_after_second_run = Anonymous_Latency_Samples.query.count()
        assert latency_rows_after_second_run == EXPECTED_SEEDED_LATENCY_ROW_COUNT, (
            "Latency seed CLI must be idempotent: second invocation must not "
            f"add or remove rows. Expected {EXPECTED_SEEDED_LATENCY_ROW_COUNT}, "
            f"got {latency_rows_after_second_run}."
        )


def test_seed_uniform_latency_rollups_writes_expected_rows_and_is_idempotent(runner):
    """
    GIVEN a developer wanting to seed deterministic AnonymousLatencyDailyRollups
        rows for the admin dashboard's rollup-backed long-window path
    WHEN the developer provides the following CLI command:
        `flask addmock seed-uniform-latency-rollups`
    THEN verify the command exits successfully, writes the expected number of
        rollup rows (one per (day-offset × endpoint) tuple, with no device-type
        multiplier because the rollup aggregates across device types), and is
        idempotent across repeat invocations (the seeder skips any
        (metric, endpoint, method, day) key that already has a row).

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner

    with app.app_context():
        assert Anonymous_Latency_Daily_Rollups.query.count() == 0, (
            "AnonymousLatencyDailyRollups table must be empty before the seed "
            "CLI runs so the row-count assertion measures only this command's "
            "writes."
        )

    first_result = cli_runner.invoke(args=["addmock", "seed-uniform-latency-rollups"])
    assert first_result.exit_code == 0, (
        f"First rollup seed CLI invocation failed: exit={first_result.exit_code} "
        f"output={first_result.output}"
    )

    with app.app_context():
        rollup_rows_after_first_run = Anonymous_Latency_Daily_Rollups.query.count()
        assert (
            rollup_rows_after_first_run == EXPECTED_SEEDED_LATENCY_ROLLUP_ROW_COUNT
        ), (
            f"Expected {EXPECTED_SEEDED_LATENCY_ROLLUP_ROW_COUNT} seeded rollup "
            f"rows after first run, got {rollup_rows_after_first_run}"
        )

    second_result = cli_runner.invoke(args=["addmock", "seed-uniform-latency-rollups"])
    assert second_result.exit_code == 0, (
        f"Second rollup seed CLI invocation failed: "
        f"exit={second_result.exit_code} output={second_result.output}"
    )

    with app.app_context():
        rollup_rows_after_second_run = Anonymous_Latency_Daily_Rollups.query.count()
        assert (
            rollup_rows_after_second_run == EXPECTED_SEEDED_LATENCY_ROLLUP_ROW_COUNT
        ), (
            "Rollup seed CLI must be idempotent: second invocation must not add "
            f"or remove rows. Expected {EXPECTED_SEEDED_LATENCY_ROLLUP_ROW_COUNT}, "
            f"got {rollup_rows_after_second_run}."
        )
