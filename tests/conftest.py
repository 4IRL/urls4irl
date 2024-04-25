import os
from typing import Generator, Tuple

from flask import Flask
from flask.testing import FlaskClient
from flask_login import FlaskLoginClient
import pytest
import warnings

from src import create_app, db
from src.config import TestingConfig
from src.models import (
    User,
    Utub,
    Utub_Users,
    URLS,
    Utub_Urls,
    Tags,
    Url_Tags,
    EmailValidation,
)
from src.utils.strings import model_strs
from tests.utils_for_test import get_csrf_token, drop_database
from tests.models_for_test import (
    valid_user_1,
    valid_user_2,
    valid_user_3,
    all_empty_utubs,
    valid_empty_utub_1,
    valid_url_strings,
    all_tags,
)

TEST_SPLIT = (
    {"urls", "members"},
    {"unit", "utubs"},
    {"splash", "tags"},
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
            parent_markers = set([mark.name for mark in item.parent.own_markers])
            if not TEST_SPLIT[current_worker] & parent_markers:
                deselected_items.append(item)
            else:
                selected_items.append(item)

        print(f"Running markers: {', '.join(TEST_SPLIT[current_worker])}")
        config.hook.pytest_deselected(items=deselected_items)
        items[:] = selected_items


warnings.filterwarnings(
    "ignore", category=DeprecationWarning
)  # , message="'flask.Markup' is deprecated and will be removed in Flask 2.4. Import 'markupsafe.Markup' instead.")


@pytest.fixture
def ignore_deprecation_warning():
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    yield
    warnings.resetwarnings()


@pytest.fixture
def app(ignore_deprecation_warning) -> Generator[Flask, None, None]:
    config = TestingConfig()
    app_for_test = create_app(config)
    yield app_for_test
    drop_database(config)


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
) -> Generator[Tuple[dict[str, str | None], User], None, None]:
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
        new_user = User(
            username=valid_user_1[model_strs.USERNAME],
            email=valid_user_1[model_strs.EMAIL].lower(),
            plaintext_password=valid_user_1[model_strs.PASSWORD],
        )

        new_email_validation = EmailValidation(
            confirm_url=new_user.get_email_validation_token()
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
            new_user = User(
                username=user[model_strs.USERNAME],
                email=user[model_strs.EMAIL].lower(),
                plaintext_password=user[model_strs.PASSWORD],
            )

            new_email_validation = EmailValidation(
                confirm_url=new_user.get_email_validation_token()
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
) -> Generator[Tuple[FlaskClient, str, User, Flask], None, None]:
    """
    After registering a User with ID == 1,logs them in and routes them to "/home"
    https://flask-login.readthedocs.io/en/latest/#automated-testing

    Args:
        app (Flask): The Flask client providing an app context
        register_first_user (pytest fixture): Registers the user with ID == 1

    Yields:
        (FlaskLoginClient): Flask client that logs in a user using flask_login
        (str): The CSRF token string
        (User): The User model of currently logged in user
        (Flask): The Flask client for providing an app context
    """

    app.test_client_class = FlaskLoginClient
    with app.app_context():
        user_to_login: User = User.query.get(1)

    with app.test_client(user=user_to_login) as logged_in_client:
        logged_in_response = logged_in_client.get("/home")
        csrf_token_string = get_csrf_token(logged_in_response.get_data(), meta_tag=True)
        yield logged_in_client, csrf_token_string, user_to_login, app


@pytest.fixture
def login_first_user_without_register(
    app: Flask,
) -> Generator[Tuple[FlaskClient, str, User, Flask], None, None]:
    """
    Given a user with ID == 1, logs them in, routes them to "/home",
    https://flask-login.readthedocs.io/en/latest/#automated-testing

    Args:
        app (Flask): The Flask client providing an app context

    Yields:
        (FlaskLoginClient): Flask client that logs in a user using flask_login
        (str): The CSRF token string
        (User): The User model of currently logged in user
        (Flask): The Flask client for providing an app context
    """

    app.test_client_class = FlaskLoginClient
    with app.app_context():
        user_to_login: User = User.query.get(1)

    with app.test_client(user=user_to_login) as logged_in_client:
        logged_in_response = logged_in_client.get("/home")
        csrf_token_string = get_csrf_token(logged_in_response.get_data(), meta_tag=True)
        yield logged_in_client, csrf_token_string, user_to_login, app


@pytest.fixture
def login_second_user_without_register(
    app: Flask,
) -> Generator[Tuple[FlaskClient, str, User, Flask], None, None]:
    """
    Given a user with ID == 2, logs them in, routes them to "/home",
    https://flask-login.readthedocs.io/en/latest/#automated-testing

    Args:
        app (Flask): The Flask client providing an app context

    Yields:
        (FlaskLoginClient): Flask client that logs in a user using flask_login
        (str): The CSRF token string
        (User): The User model of currently logged in user
        (Flask): The Flask client for providing an app context
    """
    app.test_client_class = FlaskLoginClient
    with app.app_context():
        user_to_login = User.query.get(2)

    with app.test_client(user=user_to_login) as logged_in_client:
        logged_in_response = logged_in_client.get("/home")
        csrf_token_string = get_csrf_token(logged_in_response.get_data(), meta_tag=True)
        yield logged_in_client, csrf_token_string, user_to_login, app


@pytest.fixture
def add_single_utub_as_user_without_logging_in(
    app: Flask, register_first_user: Tuple[Tuple[dict[str, str | None]], User]
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
        new_utub = Utub(
            name=valid_empty_utub_1[model_strs.NAME],
            utub_creator=1,
            utub_description=valid_empty_utub_1[model_strs.UTUB_DESCRIPTION],
        )
        creator_to_utub = Utub_Users()
        creator_to_utub.to_user = first_user_object
        new_utub.members.append(creator_to_utub)
        db.session.add(new_utub)
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
        creator = User.query.get(1)
        new_utub = Utub(
            name=valid_empty_utub_1[model_strs.NAME],
            utub_creator=creator.id,
            utub_description=valid_empty_utub_1[model_strs.UTUB_DESCRIPTION],
        )
        creator_to_utub = Utub_Users()
        creator_to_utub.to_user = creator
        new_utub.members.append(creator_to_utub)

        # Grab and add second user
        user_to_utub = User.query.get(2)
        new_user_for_utub = Utub_Users()
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
        creator = User.query.get(1)
        new_utub = Utub(
            name=valid_empty_utub_1[model_strs.NAME],
            utub_creator=creator.id,
            utub_description=valid_empty_utub_1[model_strs.UTUB_DESCRIPTION],
        )
        creator_to_utub = Utub_Users()
        creator_to_utub.to_user = creator
        new_utub.members.append(creator_to_utub)

        # Other users that aren't creators have ID's of 2 and 3 from fixture
        for user_id in (
            2,
            3,
        ):
            user_to_utub = User.query.get(user_id)
            new_user_for_utub = Utub_Users()
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
        other_users = User.query.all()
        for utub_data, other_user in zip(all_empty_utubs, other_users):
            new_utub = Utub(
                name=utub_data[model_strs.NAME],
                utub_creator=other_user.id,
                utub_description=utub_data[model_strs.UTUB_DESCRIPTION],
            )

            creator_to_utub = Utub_Users()
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
        current_utubs: list[Utub] = Utub.query.all()
        current_users = User.query.all()

        for utub in current_utubs:
            current_utub_members = [user.to_user for user in utub.members]

            for user in current_users:
                if user not in current_utub_members:
                    # Found a missing User who should be in a UTub
                    new_utub_user_association = Utub_Users()
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
            new_url = URLS(normalized_url=url, current_user_id=idx + 1)
            db.session.add(new_url)
        db.session.commit()


@pytest.fixture
def add_tags_to_database(app: Flask, register_multiple_users):
    with app.app_context():
        for idx, tag in enumerate(all_tags):
            new_tag = Tags(tag_string=tag[model_strs.TAG_STRING], created_by=idx + 1)
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
        all_urls: list[URLS] = URLS.query.all()
        all_utubs: list[Utub] = Utub.query.all()
        all_users: list[User] = User.query.all()

        for user, url, utub in zip(all_users, all_urls, all_utubs):
            new_utub_url_user_association = Utub_Urls()

            new_utub_url_user_association.standalone_url = url
            new_utub_url_user_association.url_id = url.id

            new_utub_url_user_association.utub = utub
            new_utub_url_user_association.utub_id = utub.id

            new_utub_url_user_association.user_that_added_url = user
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
        current_utubs: list[Utub] = Utub.query.order_by(Utub.id).all()

        # Add a single missing users to this UTub
        for utub in current_utubs:
            current_utub_member = [user.to_user for user in utub.members].pop()
            current_utub_member_id = current_utub_member.id
            next_member_id = (current_utub_member_id + 1) % 4
            next_member_id = 1 if next_member_id == 0 else next_member_id
            new_user: User = User.query.filter_by(id=next_member_id).first()
            new_utub_user_association = Utub_Users()
            new_utub_user_association.to_user = new_user
            utub.members.append(new_utub_user_association)
            db.session.add(new_utub_user_association)

            new_utub_url_user_association = Utub_Urls()
            new_url: URLS = URLS.query.filter_by(id=next_member_id).first()

            new_utub_url_user_association.standalone_url = new_url
            new_utub_url_user_association.url_id = new_url.id

            new_utub_url_user_association.utub = utub
            new_utub_url_user_association.utub_id = utub.id

            new_utub_url_user_association.user_that_added_url = new_user
            new_utub_url_user_association.user_id = next_member_id

            new_utub_url_user_association.url_title = f"This is {new_url.url_string}"

            db.session.add(new_utub_url_user_association)

        db.session.commit()


@pytest.fixture
def add_two_users_and_all_urls_to_each_utub_with_one_tag(
    app: Flask, add_two_users_and_all_urls_to_each_utub_no_tags, add_tags_to_database
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
        add_tags_to_database (pytest.fixture): Adds all tags to the database for easy adding to URLs
    """
    with app.app_context():
        one_tag: Tags = Tags.query.first()
        all_utubs: list[Utub] = Utub.query.all()

        for utub in all_utubs:
            urls_in_utub: list[Utub_Urls] = [utub_url for utub_url in utub.utub_urls]

            for url_in_utub in urls_in_utub:
                url_id = url_in_utub.url_id
                url_in_this_utub = url_in_utub.standalone_url

                new_tag_url_utub_association = Url_Tags()
                new_tag_url_utub_association.utub_containing_this_tag = utub
                new_tag_url_utub_association.tagged_url = url_in_this_utub
                new_tag_url_utub_association.tag_item = one_tag
                new_tag_url_utub_association.utub_id = utub.id
                new_tag_url_utub_association.url_id = url_id
                new_tag_url_utub_association.tag_id = one_tag.id
                utub.utub_url_tags.append(new_tag_url_utub_association)

        db.session.commit()


@pytest.fixture
def add_two_users_and_all_urls_to_each_utub_with_tags(
    app: Flask, add_two_users_and_all_urls_to_each_utub_no_tags, add_tags_to_database
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
        add_tags_to_database (pytest.fixture): Adds all tags to the database for easy adding to URLs
    """
    with app.app_context():
        all_tags: list[Tags] = Tags.query.all()
        all_utubs: list[Utub] = Utub.query.all()

        for utub in all_utubs:
            urls_in_utub: list[Utub_Urls] = [utub_url for utub_url in utub.utub_urls]

            for url_in_utub in urls_in_utub:
                url_id = url_in_utub.url_id
                url_in_this_utub = url_in_utub.standalone_url

                for tag in all_tags:
                    new_tag_url_utub_association = Url_Tags()
                    new_tag_url_utub_association.utub_containing_this_tag = utub
                    new_tag_url_utub_association.tagged_url = url_in_this_utub
                    new_tag_url_utub_association.tag_item = tag
                    new_tag_url_utub_association.utub_id = utub.id
                    new_tag_url_utub_association.url_id = url_id
                    new_tag_url_utub_association.tag_id = tag.id
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
        current_utubs: list[Utub] = Utub.query.all()
        current_users: list[User] = User.query.all()

        # Add all missing users to this UTub
        for utub in current_utubs:
            current_utub_members = [user.to_user for user in utub.members]

            for user in current_users:
                if user not in current_utub_members:
                    # Found a missing User who should be in a UTub
                    new_utub_user_association = Utub_Users()
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
        all_utubs: list[Utub] = Utub.query.all()
        all_urls: list[URLS] = URLS.query.all()

        for utub, url in zip(all_utubs, all_urls):
            for other_url in all_urls:
                if other_url != url:
                    new_url_in_utub = Utub_Urls()
                    new_url_in_utub.standalone_url = other_url
                    new_url_in_utub.user_id = other_url.id
                    new_url_in_utub.utub = utub
                    new_url_in_utub.url_title = f"This is {other_url.url_string}"
                    db.session.add(new_url_in_utub)

        db.session.commit()


@pytest.fixture
def add_all_urls_and_users_to_each_utub_with_one_tag(
    app: Flask, add_tags_to_database, add_all_urls_and_users_to_each_utub_no_tags
):
    """
    Adds a tag to each of the three URLs in each of the three UTubs that contain 3 members

    Utub with ID of 1, created by User ID of 1, with URL ID of 1, now has members 2 and 3 included, as well
    as URLs with ID of 2 and 3. Tag associated with each URL has same ID as the associated URL

    Args:
        app (Flask): The Flask client providing an app context
        add_tags_to_database (pytest.fixture): Adds all tags to the database for querying
        add_all_urls_and_users_to_each_utub_no_tags (pytest fixture): Adds all remaining URLs to each UTUb
    """
    with app.app_context():
        all_utubs: list[Utub] = Utub.query.all()

        for utub in all_utubs:
            for url in utub.utub_urls:
                tag_with_url_id = Tags.query.get(url.url_id)
                new_url_tag = Url_Tags()
                new_url_tag.url_id = url.url_id
                new_url_tag.tagged_url = url.standalone_url
                new_url_tag.utub_containing_this_tag = utub
                new_url_tag.tag_id = url.url_id
                new_url_tag.tag_with_url_id = tag_with_url_id

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
        all_utubs: list[Utub] = Utub.query.all()
        all_tags: list[Tags] = Tags.query.all()

        for utub in all_utubs:
            for single_url_in_utub in utub.utub_urls:
                for tag in all_tags:
                    tags_on_url_in_utub = len(
                        Url_Tags.query.filter(
                            Url_Tags.utub_id == utub.id,
                            Url_Tags.url_id == single_url_in_utub.url_id,
                            Url_Tags.tag_id == tag.id,
                        ).all()
                    )

                    if tags_on_url_in_utub == 0:
                        new_url_tag = Url_Tags()
                        new_url_tag.url_id = single_url_in_utub.url_id
                        new_url_tag.tagged_url = single_url_in_utub.standalone_url
                        new_url_tag.utub_containing_this_tag = utub
                        new_url_tag.tag_id = tag.id
                        new_url_tag.tag_with_url_id = tag

                        db.session.add(new_url_tag)

        db.session.commit()
