import pytest

from src.mocks.mock_constants import (
    MOCK_TAGS,
    MOCK_URL_STRINGS,
    TEST_USER_COUNT,
    USERNAME_BASE,
    MOCK_UTUB_NAME_BASE,
)
from src.models.email_validations import Email_Validations
from src.models.tags import Tags
from src.models.urls import Urls
from src.models.users import Users
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utub_urls import Utub_Urls
from src.models.utubs import Utubs

pytestmark = pytest.mark.cli

DUPLICATE_COUNT = 2


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
        _verify_users_added()


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
            _verify_users_added()
            _verify_utubs_added_duplicates(count + 1)


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
            _verify_users_added()
            _verify_utubs_added_no_duplicates()


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
            _verify_users_added()
            _verify_utubs_added_duplicates(count + 1)
            _verify_utubmembers_added()


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
            _verify_users_added()
            _verify_utubs_added_no_duplicates()
            _verify_utubmembers_added()


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
            _verify_users_added()
            _verify_utubs_added_duplicates(count + 1)
            _verify_urls_in_database()
            _verify_urls_added_to_all_utubs()


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
            _verify_users_added()
            _verify_utubs_added_no_duplicates()
            _verify_urls_in_database()
            _verify_urls_added_to_all_utubs()


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
            _verify_users_added()
            _verify_utubs_added_duplicates(count + 1)
            _verify_urls_in_database()
            _verify_urls_added_to_all_utubs()
            _verify_tags_in_database()
            _verify_tags_added_to_all_urls_in_utubs()


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
            _verify_users_added()
            _verify_utubs_added_no_duplicates()
            _verify_urls_in_database()
            _verify_urls_added_to_all_utubs()
            _verify_tags_in_database()
            _verify_tags_added_to_all_urls_in_utubs()


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
            _verify_users_added()
            _verify_utubs_added_duplicates(count + 1)
            _verify_urls_in_database()
            _verify_urls_added_to_all_utubs()
            _verify_tags_in_database()
            _verify_tags_added_to_all_urls_in_utubs()


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
            _verify_users_added()
            _verify_utubs_added_no_duplicates()
            _verify_urls_in_database()
            _verify_urls_added_to_all_utubs()
            _verify_tags_in_database()
            _verify_tags_added_to_all_urls_in_utubs()


def _verify_users_added():
    """Verifies all unique mock users are in the database with associated validated EmailValidations"""
    for i in range(TEST_USER_COUNT):
        username = f"{USERNAME_BASE}{i + 1}"
        assert Users.query.filter(Users.username == username).count() == 1
        user: Users = Users.query.filter(Users.username == username).first()
        assert (
            Email_Validations.query.filter(Email_Validations.user_id == user.id).count()
            == 1
        )
        email_validation: Email_Validations = Email_Validations.query.filter(
            Email_Validations.user_id == user.id
        ).first()
        assert email_validation.is_validated


def _verify_utubs_added_duplicates(utub_count: int):
    """
    Verifies utubs with a given name exist a given number of times in the database

    Args:
        utub_count (int): How many UTubs exist with a given name
    """
    assert Users.query.count() == TEST_USER_COUNT
    assert Utubs.query.count() == TEST_USER_COUNT * utub_count
    for i in range(TEST_USER_COUNT):
        utub_name = f"{MOCK_UTUB_NAME_BASE}{i + 1}"
        assert Utubs.query.filter(Utubs.name == utub_name).count() == utub_count


def _verify_utubs_added_no_duplicates():
    """Verifies all unique utubs are in the database"""
    for i in range(TEST_USER_COUNT):
        utub_name = f"{MOCK_UTUB_NAME_BASE}{i + 1}"
        assert Utubs.query.filter(Utubs.name == utub_name).count() == 1


def _verify_utubmembers_added():
    """Verifies all Users within the database are members of each UTub"""
    all_utubs: list[Utubs] = Utubs.query.all()
    all_users: list[Users] = Users.query.all()
    for utub in all_utubs:
        assert sorted([member.to_user.username for member in utub.members]) == sorted(
            [user.username for user in all_users]
        )


def _verify_urls_in_database():
    """Verifies all mock URLs are stored in the database"""
    for url in MOCK_URL_STRINGS:
        assert Urls.query.filter(Urls.url_string == url).count() == 1


def _verify_urls_added_to_all_utubs():
    """Verifies all mock URLs are added to each UTub"""
    all_utubs: list[Utubs] = Utubs.query.all()
    for utub in all_utubs:
        urls_in_utub: list[Utub_Urls] = utub.utub_urls
        assert sorted(
            [url.standalone_url.url_string for url in urls_in_utub]
        ) == sorted(MOCK_URL_STRINGS)


def _verify_tags_in_database():
    """Verifies all mock Tags are stored in the database"""
    for tag in MOCK_TAGS:
        assert Tags.query.filter(Tags.tag_string == tag).count() == 1


def _verify_tags_added_to_all_urls_in_utubs():
    """Verifies all mock tags are associated with each URL in each UTub"""
    all_utubs: list[Utubs] = Utubs.query.all()
    for utub in all_utubs:
        urls_in_utub: list[Utub_Urls] = utub.utub_urls
        for url_in_utub in urls_in_utub:
            tags_on_url: list[Utub_Url_Tags] = url_in_utub.url_tags
            assert sorted([tag.tag_item.tag_string for tag in tags_on_url]) == sorted(
                MOCK_TAGS
            )
