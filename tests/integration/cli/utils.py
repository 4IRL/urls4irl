from src.cli.mock_constants import (
    MOCK_TAGS,
    MOCK_URL_STRINGS,
    TEST_USER_COUNT,
    USERNAME_BASE,
    MOCK_UTUB_NAME_BASE,
)
from src.models.utub_tags import Utub_Tags
from src.models.urls import Urls
from src.models.users import Users
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utub_urls import Utub_Urls
from src.models.utubs import Utubs


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
    """Verifies all mock URLs are added to each UTub"""
    all_utubs: list[Utubs] = Utubs.query.all()
    for utub in all_utubs:
        urls_in_utub: list[Utub_Urls] = utub.utub_urls
        assert sorted(
            [url.standalone_url.url_string for url in urls_in_utub]
        ) == sorted(MOCK_URL_STRINGS)


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
    """Verifies all mock tags are associated with each URL in each UTub"""
    all_utubs: list[Utubs] = Utubs.query.all()
    for utub in all_utubs:
        urls_in_utub: list[Utub_Urls] = utub.utub_urls
        for url_in_utub in urls_in_utub:
            tags_on_url: list[Utub_Url_Tags] = url_in_utub.url_tags
            assert sorted(
                [tag.utub_tag_item.tag_string for tag in tags_on_url]
            ) == sorted(MOCK_TAGS)
