from flask import Flask
from flask.testing import FlaskCliRunner

from backend.cli.mock_constants import (
    MOCK_TAGS,
    MOCK_TRACKING_SEED_URL_PAIRS,
    MOCK_URL_STRINGS,
    TEST_USER_COUNT,
    USERNAME_BASE,
    MOCK_UTUB_NAME_BASE,
)
from backend.models.utub_tags import Utub_Tags
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs

TRACKING_SEED_URL_STRINGS: frozenset[str] = frozenset(
    tracking_url for tracking_url, _expected_stripped in MOCK_TRACKING_SEED_URL_PAIRS
)


def verify_users_added():
    """Verifies all unique mock users are in the database with emails validated"""
    for i in range(TEST_USER_COUNT):
        username = f"{USERNAME_BASE}{i + 1}"
        assert Users.query.filter(Users.username == username).count() == 1
        user: Users = Users.query.filter(Users.username == username).first()
        assert user.email_validated


def verify_utubs_added_duplicates(utub_count: int):
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


def verify_utubs_added_no_duplicates():
    """Verifies all unique utubs are in the database"""
    for i in range(TEST_USER_COUNT):
        utub_name = f"{MOCK_UTUB_NAME_BASE}{i + 1}"
        assert Utubs.query.filter(Utubs.name == utub_name).count() == 1


def verify_utubmembers_added():
    """Verifies all Users within the database are members of each UTub"""
    all_utubs: list[Utubs] = Utubs.query.all()
    all_users: list[Users] = Users.query.all()
    for utub in all_utubs:
        assert sorted([member.to_user.username for member in utub.members]) == sorted(
            [user.username for user in all_users]
        )


def verify_urls_in_database():
    """Verifies all mock URLs are stored in the database"""
    for url in MOCK_URL_STRINGS:
        assert Urls.query.filter(Urls.url_string == url).count() == 1


def verify_custom_url_in_database(url: str):
    """Verifies custom URL is stored in the database"""
    assert Urls.query.filter(Urls.url_string == url).count() == 1


def verify_urls_added_to_all_utubs():
    """Verifies all mock URLs are added to each UTub.

    The tracking-param seed URLs (added only to the first UTub by
    ``_add_tracking_seed_urls``) are excluded so this assertion still pins the
    standard ``MOCK_URL_STRINGS`` set per UTub.
    """
    all_utubs: list[Utubs] = Utubs.query.all()
    for utub in all_utubs:
        urls_in_utub: list[Utub_Urls] = utub.utub_urls
        non_tracking_url_strings = [
            url.standalone_url.url_string
            for url in urls_in_utub
            if url.standalone_url.url_string not in TRACKING_SEED_URL_STRINGS
        ]
        assert sorted(non_tracking_url_strings) == sorted(MOCK_URL_STRINGS)


def verify_custom_url_added_to_all_utubs(url: str):
    """Verifies all mock URLs are added to each UTub"""
    all_utubs: list[Utubs] = Utubs.query.all()
    for utub in all_utubs:
        urls_in_utub: list[Utub_Urls] = utub.utub_urls
        assert url in [url.standalone_url.url_string for url in urls_in_utub]


def verify_tags_in_utubs():
    """Verifies all mock Tags are stored in each UTub"""
    utub_count: int = Utubs.query.count()
    for tag in MOCK_TAGS:
        assert (
            Utub_Tags.query.filter(Utub_Tags.tag_string == tag).count()
            == 1 * utub_count
        )


def verify_tags_added_to_all_urls_in_utubs():
    """Verifies all mock tags are associated with each URL in each UTub.

    The tracking-param seed URLs carry only a single seed tag (not the full
    ``MOCK_TAGS`` set), so they are excluded from this exact-set assertion.
    """
    all_utubs: list[Utubs] = Utubs.query.all()
    for utub in all_utubs:
        urls_in_utub: list[Utub_Urls] = utub.utub_urls
        for url_in_utub in urls_in_utub:
            if url_in_utub.standalone_url.url_string in TRACKING_SEED_URL_STRINGS:
                continue
            tags_on_url: list[Utub_Url_Tags] = url_in_utub.url_tags
            assert sorted(
                [tag.utub_tag_item.tag_string for tag in tags_on_url]
            ) == sorted(MOCK_TAGS)


def verify_tracking_seed_urls_added(app: Flask, cli_runner: FlaskCliRunner):
    """Verifies the tracking-param seed URLs are added to the first UTub.

    Asserts that every raw tracking URL in ``MOCK_TRACKING_SEED_URL_PAIRS``
    exists in the ``Urls`` table, that each is associated with the first UTub
    along with the first UTub's seed tag, and that a second ``flask addmock
    all`` invocation adds no duplicate rows (idempotency).

    Args:
        app (Flask): The Flask application providing the app context
        cli_runner (FlaskCliRunner): Runner used to re-invoke `addmock all`
    """
    with app.app_context():
        first_utub: Utubs = Utubs.query.order_by(Utubs.id).first()
        seed_tag: Utub_Tags = (
            Utub_Tags.query.filter(Utub_Tags.utub_id == first_utub.id)
            .order_by(Utub_Tags.id)
            .first()
        )

        url_row_count_before = Urls.query.count()
        utub_url_count_before = Utub_Urls.query.count()
        utub_url_tag_count_before = Utub_Url_Tags.query.count()

        for tracking_url in TRACKING_SEED_URL_STRINGS:
            assert Urls.query.filter(Urls.url_string == tracking_url).count() == 1

            seed_url: Urls = Urls.query.filter(Urls.url_string == tracking_url).first()
            utub_url: Utub_Urls = Utub_Urls.query.filter(
                Utub_Urls.utub_id == first_utub.id,
                Utub_Urls.url_id == seed_url.id,
            ).first()
            assert utub_url is not None
            assert (
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_url_id == utub_url.id,
                    Utub_Url_Tags.utub_tag_id == seed_tag.id,
                ).count()
                == 1
            )

    cli_runner.invoke(args=["addmock", "all"])

    with app.app_context():
        assert Urls.query.count() == url_row_count_before
        assert Utub_Urls.query.count() == utub_url_count_before
        assert Utub_Url_Tags.query.count() == utub_url_tag_count_before

        for tracking_url in TRACKING_SEED_URL_STRINGS:
            assert Urls.query.filter(Urls.url_string == tracking_url).count() == 1

            seed_url: Urls = Urls.query.filter(Urls.url_string == tracking_url).first()
            assert (
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == first_utub.id,
                    Utub_Urls.url_id == seed_url.id,
                ).count()
                == 1
            )
