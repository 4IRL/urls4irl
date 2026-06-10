import pytest

from backend.cli.mock_options import SEED_TEST_DATA_HOUR_OFFSETS
from backend.models.anonymous_metrics import Anonymous_Metrics
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
)

pytestmark = pytest.mark.cli

DUPLICATE_COUNT = 2
SEEDED_EVENT_COUNT_PER_BUCKET = 3
EXPECTED_SEEDED_ROW_COUNT = (
    len(SEED_TEST_DATA_HOUR_OFFSETS) * SEEDED_EVENT_COUNT_PER_BUCKET
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
