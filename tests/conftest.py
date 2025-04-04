import os
from typing import Any, Awaitable, Generator, Tuple, Union

from flask import Flask
from flask.testing import FlaskCliRunner, FlaskClient
from flask_login import FlaskLoginClient
from flask_session.redis import RedisSessionInterface
import pytest
import warnings

import redis
from redis.client import Redis

from src import create_app, db, environment_assets
from src.config import ConfigTest
from src.models.email_validations import Email_Validations
from src.models.utub_tags import Utub_Tags
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.users import Users
from src.models.utubs import Utubs
from src.models.utub_members import Member_Role, Utub_Members
from src.models.utub_urls import Utub_Urls
from src.models.urls import Possible_Url_Validation, Urls
from src.utils.strings import model_strs
from src.utils.strings.config_strs import CONFIG_ENVS
from tests.utils_for_test import clear_database, get_csrf_token
from tests.models_for_test import (
    valid_user_1,
    valid_user_2,
    valid_user_3,
    all_empty_utubs,
    valid_empty_utub_1,
    valid_url_strings,
    all_tags,
)

# Order matters!
TEST_SPLIT = (
    "unit",
    "splash",
    "utubs",
    "members",
    "urls",
    "tags",
    "cli",
    "splash_ui",
    "home_ui",
    "utubs_ui",
    "members_ui",
    "urls_ui",
    "tags_ui",
    "mobile_ui",
)


def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
) -> None:
    # Change default values to 1 before turning in to GitHub
    current_worker = int(os.getenv("GITHUB_WORKER_ID", -1)) - 1

    if current_worker >= 0:
        deselected_items = []
        selected_items = []

        for item in items:
            if item.get_closest_marker(TEST_SPLIT[current_worker]) is None:
                deselected_items.append(item)
            else:
                selected_items.append(item)

        print(f"Running marker: {TEST_SPLIT[current_worker]}")
        config.hook.pytest_deselected(items=deselected_items)
        items[:] = selected_items


def pytest_addoption(parser):
    """
    Option 1:
    Adds CLI option for headless operation.
    Default runs tests headless; option to observe UI interactions when debugging by assigning False.

    Option 2:
    Adds CLI option for display of pytest debug strings.
    Default keeps all strings hidden from CLI.

    Option 3:
    Adds CLI option for display of Flask logs.
    Default keeps all strings hidden from CLI.
    """

    # Option 1: Headless
    parser.addoption(
        "--show_browser",
        default=False,
        action="store_true",
        help="Show browser when included",
    )

    # Option 2: Show Pytest debug strings
    parser.addoption(
        "--DS",
        default=False,
        action="store_true",
        help="Show debug strings when included",
    )

    # Option 3: Show Flask logs
    parser.addoption(
        "--FL", default=False, action="store_true", help="Show Flask logs when included"
    )


warnings.filterwarnings(
    "ignore", category=DeprecationWarning
)  # , message="'flask.Markup' is deprecated and will be removed in Flask 2.4. Import 'markupsafe.Markup' instead.")


@pytest.fixture(scope="session")
def ignore_deprecation_warning():
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    yield
    warnings.resetwarnings()


@pytest.fixture(scope="session")
def build_app(
    ignore_deprecation_warning,
) -> Generator[Tuple[Flask, ConfigTest], None, None]:
    config = ConfigTest()

    # Clear bundles to avoid re-registering
    environment_assets._named_bundles = {}

    app_for_test = create_app(config)
    if app_for_test is None:
        return

    with app_for_test.app_context():
        db.init_app(app_for_test)
        db.create_all()

    yield app_for_test, config

    with app_for_test.app_context():
        db.drop_all()


@pytest.fixture
def app(build_app: Tuple[Flask, ConfigTest]) -> Generator[Flask, None, None]:
    app, testing_config = build_app
    yield app
    clear_database(testing_config)
    if isinstance(app.session_interface, RedisSessionInterface):
        app.session_interface.client.flushdb()


@pytest.fixture
def runner(app) -> Generator[Tuple[Flask, FlaskCliRunner], None, None]:
    flask_app: Flask = app
    yield flask_app, flask_app.test_cli_runner()


@pytest.fixture
def provide_redis(app: Flask) -> Generator[Redis | None, None, None]:
    redis_uri = app.config.get(CONFIG_ENVS.REDIS_URI, None)
    if not redis_uri or redis_uri == "memory://":
        return

    redis_client: Any = redis.Redis.from_url(url=redis_uri)
    assert isinstance(redis_client, Redis)

    before_keys = redis_client.keys()
    yield redis_client
    after_keys: Union[Awaitable, Any] = redis_client.keys()
    assert isinstance(after_keys, list)

    keys_to_delete = []
    for new_key in after_keys:
        if new_key not in before_keys:
            keys_to_delete.append(new_key)

    for key_to_del in keys_to_delete:
        redis_client.delete(key_to_del)


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def load_register_page(
    client: FlaskClient,
) -> Generator[Tuple[FlaskClient, str], None, None]:
    """
    Given a Flask client, performs a GET of the register page using "/register"

    Args:
        client (FlaskClient): A Flask client

    Yields:
        (FlaskClient): A Flask client that has just performed a GET on "/register"
        (str): The CSRF token found on the "/register" page
    """
    with client:
        get_register_response = client.get("/register")
        csrf_token_string = get_csrf_token(get_register_response.get_data())
        yield client, csrf_token_string


@pytest.fixture
def load_login_page(
    client: FlaskClient,
) -> Generator[Tuple[FlaskClient, str], None, None]:
    """
    Given a Flask client, performs a GET of the login page using "/login"

    Args:
        client (FlaskClient): A Flask client

    Yields:
        (FlaskClient): A Flask client that has just performed a GET on "/login"
        (str): The CSRF token found on the "/login" page
    """
    with client:
        get_register_response = client.get("/login")
        csrf_token_string = get_csrf_token(get_register_response.get_data())
        yield client, csrf_token_string


@pytest.fixture
def register_first_user(
    app: Flask,
) -> Generator[Tuple[dict[str, str | None], Users], None, None]:
    """
    Registers a User model with.
    See 'models_for_test.py' for model information.
    The newly registered User's will have ID == 1

    Args:
        app (Flask): The Flask client for providing an app context

    Yields:
        (dict): The information used to generate the new User model
        (User): The newly generated User model
    """
    # Add a new user for testing
    with app.app_context():
        new_user = Users(
            username=valid_user_1[model_strs.USERNAME],
            email=valid_user_1[model_strs.EMAIL].lower(),
            plaintext_password=valid_user_1[model_strs.PASSWORD],
        )

        new_email_validation = Email_Validations(
            validation_token=new_user.get_email_validation_token()
        )
        new_email_validation.is_validated = True
        new_user.email_confirm = new_email_validation

        db.session.add(new_user)
        db.session.commit()

    yield valid_user_1, new_user


@pytest.fixture
def register_multiple_users(
    app: Flask,
) -> Generator[Tuple[dict[str, str | None]], None, None]:
    """
    Registers three User models with unique usernames, emails, passwords, and ID's.
    See 'models_for_test.py' for model information.
    The registered User's will have ID's 1, 2, and 3

    Args:
        app (Flask): The Flask client for providing an app context

    Yields:
        (tuple): Contains models of all valid registered users
    """
    # Add multiple users for testing
    all_users = (
        valid_user_1,
        valid_user_2,
        valid_user_3,
    )
    with app.app_context():
        for user in all_users:
            new_user = Users(
                username=user[model_strs.USERNAME],
                email=user[model_strs.EMAIL].lower(),
                plaintext_password=user[model_strs.PASSWORD],
            )

            new_email_validation = Email_Validations(
                validation_token=new_user.get_email_validation_token()
            )
            new_email_validation.is_validated = True
            new_user.email_confirm = new_email_validation

            db.session.add(new_user)
            db.session.commit()

        # yield app
    yield all_users


@pytest.fixture
def login_first_user_with_register(
    app: Flask, register_first_user
) -> Generator[Tuple[FlaskClient, str, Users, Flask], None, None]:
    """
    After registering a User with ID == 1,logs them in and routes them to "/home"
    https://flask-login.readthedocs.io/en/latest/#automated-testing

    Args:
        app (Flask): The Flask client providing an app context
        register_first_user (pytest fixture): Registers the user with ID == 1

    Yields:
        (FlaskLoginClient): Flask client that logs in a user using flask_login
        (str): The CSRF token string
        (Users): The User model of currently logged in user
        (Flask): The Flask client for providing an app context
    """

    app.test_client_class = FlaskLoginClient
    with app.app_context():
        user_to_login: Users = Users.query.get(1)

    with app.test_client(user=user_to_login) as logged_in_client:
        logged_in_response = logged_in_client.get("/home")
        csrf_token_string = get_csrf_token(logged_in_response.get_data(), meta_tag=True)
        yield logged_in_client, csrf_token_string, user_to_login, app


@pytest.fixture
def login_first_user_without_register(
    app: Flask,
) -> Generator[Tuple[FlaskClient, str, Users, Flask], None, None]:
    """
    Given a user with ID == 1, logs them in, routes them to "/home",
    https://flask-login.readthedocs.io/en/latest/#automated-testing

    Args:
        app (Flask): The Flask client providing an app context

    Yields:
        (FlaskLoginClient): Flask client that logs in a user using flask_login
        (str): The CSRF token string
        (Users): The User model of currently logged in user
        (Flask): The Flask client for providing an app context
    """

    app.test_client_class = FlaskLoginClient
    with app.app_context():
        user_to_login: Users = Users.query.get(1)

    with app.test_client(user=user_to_login) as logged_in_client:
        logged_in_response = logged_in_client.get("/home")
        csrf_token_string = get_csrf_token(logged_in_response.get_data(), meta_tag=True)
        yield logged_in_client, csrf_token_string, user_to_login, app


@pytest.fixture
def login_second_user_without_register(
    app: Flask,
) -> Generator[Tuple[FlaskClient, str, Users, Flask], None, None]:
    """
    Given a user with ID == 2, logs them in, routes them to "/home",
    https://flask-login.readthedocs.io/en/latest/#automated-testing

    Args:
        app (Flask): The Flask client providing an app context

    Yields:
        (FlaskLoginClient): Flask client that logs in a user using flask_login
        (str): The CSRF token string
        (Users): The User model of currently logged in user
        (Flask): The Flask client for providing an app context
    """
    app.test_client_class = FlaskLoginClient
    with app.app_context():
        user_to_login = Users.query.get(2)

    with app.test_client(user=user_to_login) as logged_in_client:
        logged_in_response = logged_in_client.get("/home")
        csrf_token_string = get_csrf_token(logged_in_response.get_data(), meta_tag=True)
        yield logged_in_client, csrf_token_string, user_to_login, app


@pytest.fixture
def add_single_utub_as_user_without_logging_in(
    app: Flask, register_first_user: Tuple[Tuple[dict[str, str | None]], Users]
):
    """
    Sets up a single UTub in the database, created by the user with ID == 1
    No members are added to this UTub besides the creator

    Args:
        app (Flask): The Flask client providing an app context
        register_first_user (pytest fixture): Registers the user with ID == 1
    """
    _, first_user_object = register_first_user
    with app.app_context():
        new_utub = Utubs(
            name=valid_empty_utub_1[model_strs.NAME],
            utub_creator=1,
            utub_description=valid_empty_utub_1[model_strs.UTUB_DESCRIPTION],
        )
        creator_to_utub = Utub_Members()
        creator_to_utub.to_user = first_user_object
        new_utub.members.append(creator_to_utub)
        db.session.add(new_utub)
        db.session.commit()


@pytest.fixture
def add_all_utubs_as_user_without_logging_in(
    app: Flask, register_first_user: Tuple[Tuple[dict[str, str | None]], Users]
):
    """
    Sets up three UTubs in the database, created by the user with ID == 1
    No members are added to this UTub besides the creator

    Args:
        app (Flask): The Flask client providing an app context
        register_first_user (pytest fixture): Registers the user with ID == 1
    """
    with app.app_context():
        user: Users = Users.query.first()
        for utub_data in all_empty_utubs:
            new_utub = Utubs(
                name=utub_data[model_strs.NAME],
                utub_creator=user.id,
                utub_description=utub_data[model_strs.UTUB_DESCRIPTION],
            )

            creator_to_utub = Utub_Members()
            creator_to_utub.to_user = user
            new_utub.members.append(creator_to_utub)
            db.session.commit()


@pytest.fixture
def add_single_user_to_utub_without_logging_in(app: Flask, register_multiple_users):
    """
    Sets up a single UTub in the database, created by user with ID == 1, and adds
        the user with ID == 2 to the UTub as a member

    Args:
        app (Flask): The Flask client providing an app context
        register_multiple_users (pytest fixture): Registers the users with ID == 1, 2, 3
    """
    with app.app_context():
        creator = Users.query.get(1)
        new_utub = Utubs(
            name=valid_empty_utub_1[model_strs.NAME],
            utub_creator=creator.id,
            utub_description=valid_empty_utub_1[model_strs.UTUB_DESCRIPTION],
        )
        creator_to_utub = Utub_Members()
        creator_to_utub.to_user = creator
        creator_to_utub.member_role = Member_Role.CREATOR
        new_utub.members.append(creator_to_utub)

        # Grab and add second user
        user_to_utub = Users.query.get(2)
        new_user_for_utub = Utub_Members()
        new_user_for_utub.to_user = user_to_utub
        new_utub.members.append(new_user_for_utub)

        db.session.add(new_utub)
        db.session.commit()


@pytest.fixture
def add_multiple_users_to_utub_without_logging_in(app: Flask, register_multiple_users):
    """
    Sets up a single UTub in the database, created by user with ID == 1, and adds
        the other two members to the UTub

    Args:
        app (Flask): The Flask client providing an app context
        register_multiple_users (pytest fixture): Registers the users with ID == 1, 2, 3
    """
    with app.app_context():
        creator = Users.query.get(1)
        new_utub = Utubs(
            name=valid_empty_utub_1[model_strs.NAME],
            utub_creator=creator.id,
            utub_description=valid_empty_utub_1[model_strs.UTUB_DESCRIPTION],
        )
        creator_to_utub = Utub_Members()
        creator_to_utub.to_user = creator
        creator_to_utub.member_role = Member_Role.CREATOR
        new_utub.members.append(creator_to_utub)

        # Other users that aren't creators have ID's of 2 and 3 from fixture
        for user_id in (
            2,
            3,
        ):
            user_to_utub = Users.query.get(user_id)
            new_user_for_utub = Utub_Members()
            new_user_for_utub.to_user = user_to_utub
            new_utub.members.append(new_user_for_utub)

        db.session.add(new_utub)
        db.session.commit()


@pytest.fixture
def every_user_makes_a_unique_utub(app: Flask, register_multiple_users):
    """
    After registering multiple users with ID's 1, 2, 3, has each user make their own unique UTub
    Each UTub has IDs == 1, 2, 3, corresponding with the creator ID

    Args:
        app (Flask): The Flask client providing an app context
        register_multiple_users (pytest fixture): Registers the users with ID == 1, 2, 3
    """
    with app.app_context():
        # Get all other users who aren't logged in
        other_users = Users.query.all()
        for utub_data, other_user in zip(all_empty_utubs, other_users):
            new_utub = Utubs(
                name=utub_data[model_strs.NAME],
                utub_creator=other_user.id,
                utub_description=utub_data[model_strs.UTUB_DESCRIPTION],
            )

            creator_to_utub = Utub_Members()
            creator_to_utub.member_role = Member_Role.CREATOR
            creator_to_utub.to_user = other_user
            new_utub.members.append(creator_to_utub)
            db.session.commit()


@pytest.fixture
def every_user_in_every_utub(app: Flask, every_user_makes_a_unique_utub):
    """
    After registering multiple users with ID's 1, 2, 3, and ensuring each User has their own UTub,
    then adds all other Users as members to each User's UTubs.
    Each of the three User's has ID == 1, 2, 3

    Args:
        app (Flask): The Flask client providing an app context
        every_user_makes_a_unique_utub (pytest fixture): Has each User make their own UTub
    """
    with app.app_context():
        # Ensure each UTub has only one member
        current_utubs: list[Utubs] = Utubs.query.all()
        current_users = Users.query.all()

        for utub in current_utubs:
            current_utub_members = [user.to_user for user in utub.members]

            for user in current_users:
                if user not in current_utub_members:
                    # Found a missing User who should be in a UTub
                    new_utub_user_association = Utub_Members()
                    new_utub_user_association.to_user = user
                    utub.members.append(new_utub_user_association)

        db.session.commit()


@pytest.fixture
def add_urls_to_database(app: Flask, every_user_makes_a_unique_utub):
    """
    After registering multiple users with ID's 1, 2, 3, and ensuring each User has their own UTub,
    now creates three unique URLs.
    Each of the three URL's has ID == 1, 2, 3.
    See 'models_for_test.py' for URL definition.
    Each User added one of each URL. The ID of the User corresponds with the ID of the URL.

    Args:
        app (Flask): The Flask client providing an app context
        every_user_makes_a_unique_utub (pytest fixture): Has each User make their own UTub
    """
    with app.app_context():
        for idx, url in enumerate(valid_url_strings):
            new_url = Urls(
                normalized_url=url,
                current_user_id=idx + 1,
                is_validated=Possible_Url_Validation.VALIDATED.value,
            )
            db.session.add(new_url)
        db.session.commit()


@pytest.fixture
def add_tags_to_utubs(app: Flask, every_user_makes_a_unique_utub):
    with app.app_context():
        all_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_utubs:
            for idx, tag in enumerate(all_tags):
                new_tag = Utub_Tags(
                    utub_id=utub.id,
                    tag_string=tag[model_strs.TAG_STRING],
                    created_by=idx + 1,
                )
                db.session.add(new_tag)
        db.session.commit()


@pytest.fixture
def add_one_url_to_each_utub_no_tags(app: Flask, add_urls_to_database):
    """
    Add a single valid URL to each UTub already generated.
    The ID of the UTub, User, and related URL are all the same.

    Utub with ID of 1, created by User ID of 1, with URL ID of 1

    Args:
        app (Flask): The Flask client providing an app context
        add_urls_to_database (pytest fixture): Adds all the test URLs to the database
    """
    with app.app_context():
        all_urls: list[Urls] = Urls.query.all()
        all_utubs: list[Utubs] = Utubs.query.all()
        all_users: list[Users] = Users.query.all()

        for user, url, utub in zip(all_users, all_urls, all_utubs):
            new_utub_url_user_association = Utub_Urls()

            new_utub_url_user_association.standalone_url = url
            new_utub_url_user_association.url_id = url.id

            new_utub_url_user_association.utub = utub
            new_utub_url_user_association.utub_id = utub.id

            new_utub_url_user_association.user_id = user.id

            new_utub_url_user_association.url_title = f"This is {url.url_string}"

            db.session.add(new_utub_url_user_association)

        db.session.commit()


@pytest.fixture
def add_two_users_and_all_urls_to_each_utub_no_tags(
    app: Flask, add_one_url_to_each_utub_no_tags
):
    """
    After each user has made their own UTub, with one URL added by that user to each UTub,
    now add one other user as members to each UTub, and add all other URLs to the UTub

    Utub with ID of 1, created by User ID of 1, with URL ID of 1, now has member 2 and URL with ID of 2 included

    Args:
        app (Flask): The Flask client providing an app context
        add_one_url_to_each_utub_no_tags (pytest fixture): Has each User make their own UTub, and has
            that user add a URL to their UTub
    """
    with app.app_context():
        current_utubs: list[Utubs] = Utubs.query.order_by(Utubs.id).all()

        # Add a single missing users to this UTub
        for utub in current_utubs:
            current_utub_member = [user.to_user for user in utub.members].pop()
            current_utub_member_id = current_utub_member.id
            next_member_id = (current_utub_member_id + 1) % 4
            next_member_id = 1 if next_member_id == 0 else next_member_id
            new_user: Users = Users.query.get(next_member_id)
            new_utub_user_association = Utub_Members()
            new_utub_user_association.to_user = new_user
            utub.members.append(new_utub_user_association)
            db.session.add(new_utub_user_association)

            new_utub_url_user_association = Utub_Urls()
            new_url: Urls = Urls.query.get(next_member_id)

            new_utub_url_user_association.standalone_url = new_url
            new_utub_url_user_association.url_id = new_url.id

            new_utub_url_user_association.utub = utub
            new_utub_url_user_association.utub_id = utub.id

            new_utub_url_user_association.user_id = next_member_id

            new_utub_url_user_association.url_title = f"This is {new_url.url_string}"

            db.session.add(new_utub_url_user_association)

        db.session.commit()


@pytest.fixture
def add_two_users_and_all_urls_to_each_utub_with_one_tag(
    app: Flask, add_two_users_and_all_urls_to_each_utub_no_tags, add_tags_to_utubs
):
    """
    After each user has made their own UTub, with one URL added by that user to each UTub,
    with one other member and URL in each UTub, now add one tag to each URL in each UTub

    Utub with ID of 1, created by User ID of 1, with URL ID of 1, now has member 2 and URL with ID of 2 included
    And each tag is now associated with each URL in each UTUb

    Args:
        app (Flask): The Flask client providing an app context
        add_two_users_and_all_urls_to_each_utub_no_tags (pytest fixture): Has each User make their own UTub, and has
            that user add a URL to their UTub, and has one additional user added to each UTub, with that user adding
            the URL with a matching ID to their user id, to this UTub
        add_tags_to_all_utubs (pytest.fixture): Adds all tags to the database for easy adding to URLs
    """
    with app.app_context():
        one_tag: Utub_Tags = Utub_Tags.query.first()
        all_utubs: list[Utubs] = Utubs.query.all()

        for utub in all_utubs:
            urls_in_utub: list[Utub_Urls] = [utub_url for utub_url in utub.utub_urls]

            for url_in_utub in urls_in_utub:
                url_id = url_in_utub.id

                new_tag_url_utub_association = Utub_Url_Tags()
                new_tag_url_utub_association.utub_containing_this_url_tag = utub
                new_tag_url_utub_association.tagged_url = url_in_utub
                new_tag_url_utub_association.utub_tag_item = one_tag
                new_tag_url_utub_association.utub_id = utub.id
                new_tag_url_utub_association.utub_url_id = url_id
                new_tag_url_utub_association.utub_tag_id = one_tag.id
                utub.utub_url_tags.append(new_tag_url_utub_association)

        db.session.commit()


@pytest.fixture
def add_two_users_and_all_urls_to_each_utub_with_tags(
    app: Flask, add_two_users_and_all_urls_to_each_utub_no_tags, add_tags_to_utubs
):
    """
    After each user has made their own UTub, with one URL added by that user to each UTub,
    with one other member and URL in each UTub, now add all tags to each URL in each UTub

    Utub with ID of 1, created by User ID of 1, with URL ID of 1, now has member 2 and URL with ID of 2 included
    And each tag is now associated with each URL in each UTUb

    Args:
        app (Flask): The Flask client providing an app context
        add_two_users_and_all_urls_to_each_utub_no_tags (pytest fixture): Has each User make their own UTub, and has
            that user add a URL to their UTub, and has one additional user added to each UTub, with that user adding
            the URL with a matching ID to their user id, to this UTub
        add_tags_to_all_utubs (pytest.fixture): Adds all tags to the database for easy adding to URLs
    """
    with app.app_context():
        all_tags: list[Utub_Tags] = Utub_Tags.query.all()
        all_utubs: list[Utubs] = Utubs.query.all()

        for utub in all_utubs:
            urls_in_utub: list[Utub_Urls] = [utub_url for utub_url in utub.utub_urls]

            for url_in_utub in urls_in_utub:
                url_id = url_in_utub.id

                for tag in all_tags:
                    new_tag_url_utub_association = Utub_Url_Tags()
                    new_tag_url_utub_association.utub_containing_this_url_tag = utub
                    new_tag_url_utub_association.tagged_url = url_in_utub
                    new_tag_url_utub_association.utub_tag_item = tag
                    new_tag_url_utub_association.utub_id = utub.id
                    new_tag_url_utub_association.utub_url_id = url_id
                    new_tag_url_utub_association.utub_tag_id = tag.id
                    utub.utub_url_tags.append(new_tag_url_utub_association)

        db.session.commit()


@pytest.fixture
def add_one_url_and_all_users_to_each_utub_no_tags(
    app: Flask, add_one_url_to_each_utub_no_tags
):
    """
    After each user has made their own UTub, with one URL added by that user to each UTub,
    now add all other users as members to each UTub.

    Utub with ID of 1, created by User ID of 1, with URL ID of 1, now has members 2 and 3 included

    Args:
        app (Flask): The Flask client providing an app context
        add_one_url_to_each_utub_no_tags (pytest fixture): Has each User make their own UTub, and has
            that user add a URL to their UTub
    """
    with app.app_context():
        current_utubs: list[Utubs] = Utubs.query.all()
        current_users: list[Users] = Users.query.all()

        # Add all missing users to this UTub
        for utub in current_utubs:
            current_utub_members = [user.to_user for user in utub.members]

            for user in current_users:
                if user not in current_utub_members:
                    # Found a missing User who should be in a UTub
                    new_utub_user_association = Utub_Members()
                    new_utub_user_association.to_user = user
                    utub.members.append(new_utub_user_association)

        db.session.commit()


@pytest.fixture
def add_all_urls_and_users_to_each_utub_no_tags(
    app: Flask, add_one_url_and_all_users_to_each_utub_no_tags
):
    """
    Adds two other URLs to a UTub that contains all 3 test members, but does not have any tags associated with these URLs

    Utub with ID of 1, created by User ID of 1, with URL ID of 1, now has members 2 and 3 included, as well
    as URLs with ID of 2 and 3

    Args:
        app (Flask): The Flask client providing an app context
        add_one_url_and_all_users_to_each_utub_no_tags (pytest fixture): Adds all users to all UTubs, each UTub containing
            a single URL added by the creator
    """
    with app.app_context():
        all_utubs: list[Utubs] = Utubs.query.all()
        all_urls: list[Urls] = Urls.query.all()

        for utub, url in zip(all_utubs, all_urls):
            for other_url in all_urls:
                if other_url != url:
                    new_url_in_utub = Utub_Urls()
                    new_url_in_utub.standalone_url = other_url
                    new_url_in_utub.user_id = other_url.id
                    new_url_in_utub.utub_id = utub.id
                    new_url_in_utub.url_title = f"This is {other_url.url_string}"
                    db.session.add(new_url_in_utub)
                    db.session.commit()


@pytest.fixture
def add_all_urls_and_users_to_each_utub_with_one_tag(
    app: Flask, add_tags_to_utubs, add_all_urls_and_users_to_each_utub_no_tags
):
    """
    Adds a tag to each of the three URLs in each of the three UTubs that contain 3 members

    Utub with ID of 1, created by User ID of 1, with URL ID of 1, now has members 2 and 3 included, as well
    as URLs with ID of 2 and 3. Tag associated with each URL has same ID as the associated URL

    Args:
        app (Flask): The Flask client providing an app context
        add_tags_to_all_utubs (pytest.fixture): Adds all tags to the database for querying
        add_all_urls_and_users_to_each_utub_no_tags (pytest fixture): Adds all remaining URLs to each UTUb
    """
    with app.app_context():
        all_utubs: list[Utubs] = Utubs.query.all()

        for utub in all_utubs:
            for url in utub.utub_urls:
                url_id = url.id
                tag_with_url_id: Utub_Tags = Utub_Tags.query.filter(
                    Utub_Tags.utub_id == utub.id
                ).first()
                new_url_tag = Utub_Url_Tags()
                new_url_tag.utub_url_id = url_id
                new_url_tag.utub_id = utub.id
                new_url_tag.utub_tag_id = tag_with_url_id.id

                db.session.add(new_url_tag)

        db.session.commit()


@pytest.fixture
def add_all_urls_and_users_to_each_utub_with_all_tags(
    app: Flask, add_all_urls_and_users_to_each_utub_with_one_tag
):
    """
    Adds all other tags to each URL in each UTub

    Utub with ID of 1, created by User ID of 1, with URL ID of 1, now has members 2 and 3 included, as well
    as URLs with ID of 2 and 3. All tags, with IDs of 1, 2, 3, are now associated with each URL in each UTub

    Args:
        app (Flask): The Flask client providing an app context
        add_all_urls_and_users_to_each_utub_with_one_tag (pytest fixture): Adds a tag of the same ID as each URL to each URL
            in each UTub
    """
    with app.app_context():
        all_utubs: list[Utubs] = Utubs.query.all()
        all_tags: list[Utub_Tags] = Utub_Tags.query.all()

        for utub in all_utubs:
            for single_url_in_utub in utub.utub_urls:
                for tag in all_tags:
                    if tag.utub_id == utub.id:
                        # Check if tag exists on URL already
                        if (
                            Utub_Url_Tags.query.filter(
                                Utub_Url_Tags.utub_id == utub.id,
                                Utub_Url_Tags.utub_url_id == single_url_in_utub.id,
                                Utub_Url_Tags.utub_tag_id == tag.id,
                            ).count()
                            == 1
                        ):
                            continue

                        new_url_tag = Utub_Url_Tags()
                        new_url_tag.utub_id = utub.id
                        new_url_tag.utub_url_id = single_url_in_utub.id
                        new_url_tag.utub_tag_id = tag.id

                        db.session.add(new_url_tag)

        db.session.commit()
