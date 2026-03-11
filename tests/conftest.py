import os
import logging
from typing import Any, Awaitable, Generator, Optional, Tuple, Union

from flask import Flask
from flask.testing import FlaskCliRunner, FlaskClient
from flask_login import FlaskLoginClient
from flask_session.redis import RedisSessionInterface
import pytest
import warnings

import redis
from redis import Redis
from sqlalchemy import create_engine, event, inspect as sa_inspect, text
from sqlalchemy.orm import scoped_session, sessionmaker

from backend import create_app, db
from backend.config import (
    ConfigTest,
    IS_DOCKER,
    POSTGRES_TEST_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    TEST_DB_URI,
    TEST_REDIS_URI,
)
from backend.utils.db_uri_builder import build_db_uri
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.users import Users
from backend.models.utubs import Utubs
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.models.urls import Urls
from backend.utils.strings import model_strs
from backend.utils.strings.config_strs import CONFIG_ENVS
from tests.utils_for_test import clear_database, get_csrf_token
from tests.models_for_test import (
    valid_user_1,
    valid_user_2,
    valid_user_3,
    all_empty_utubs,
    valid_empty_utub_1,
    valid_url_strings,
    all_tags,
    maximum_tags,
)

# Order matters!
TEST_SPLIT = (
    "unit",
    "splash",
    "utubs",
    "members",
    "urls",
    "tags",
    "account_and_support",
    "cli",
    "splash_ui",
    "home_ui",
    "utubs_ui",
    "members_ui",
    "urls_ui",
    "create_urls_ui",
    "update_urls_ui",
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


REDIS_DEFAULT_MAX_DATABASES = 16


def _get_worker_num(worker_id: str) -> Optional[int]:
    """Returns None for 'master' (non-parallel), else the integer worker number."""
    if worker_id == "master":
        return None
    return int(worker_id.replace("gw", ""))


@pytest.fixture(scope="session")
def ignore_deprecation_warning():
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    yield
    warnings.resetwarnings()


@pytest.fixture(scope="session")
def worker_db_uri(worker_id: str) -> Generator[str, None, None]:
    """Provides a per-worker database URI, creating and dropping a worker-specific DB."""
    if worker_id == "master":
        yield TEST_DB_URI
        return

    assert (
        POSTGRES_TEST_DB
    ), "POSTGRES_TEST_DB must be set for parallel integration tests"
    worker_db_name = f"{POSTGRES_TEST_DB}_{worker_id}"
    db_host = "test-db" if IS_DOCKER else "localhost"

    admin_uri = build_db_uri(
        username=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database="postgres",
        database_host=db_host,
    )
    worker_uri = build_db_uri(
        username=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database=worker_db_name,
        database_host=db_host,
    )

    def _drop_worker_db(conn) -> None:
        conn.execute(
            text(
                f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{worker_db_name}' AND pid <> pg_backend_pid()"
            )
        )
        conn.execute(text(f'DROP DATABASE IF EXISTS "{worker_db_name}"'))

    engine = create_engine(admin_uri, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        _drop_worker_db(conn)
        conn.execute(text(f'CREATE DATABASE "{worker_db_name}"'))
    engine.dispose()

    yield worker_uri

    engine = create_engine(admin_uri, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        _drop_worker_db(conn)
    engine.dispose()


@pytest.fixture(scope="session")
def worker_redis_uri(worker_id: str) -> str:
    """Returns a per-worker Redis URI using a unique DB index."""
    if not TEST_REDIS_URI or TEST_REDIS_URI == "memory://":
        return TEST_REDIS_URI
    if worker_id == "master":
        return TEST_REDIS_URI
    base, db_str = TEST_REDIS_URI.rsplit("/", 1)
    base_db = int(db_str) if db_str.isdigit() else 0
    db_index = base_db + 1 + _get_worker_num(worker_id)

    probe = Redis.from_url(f"{base}/0")
    try:
        max_dbs = int(
            probe.config_get("databases").get("databases", REDIS_DEFAULT_MAX_DATABASES)
        )
    finally:
        probe.close()

    if db_index >= max_dbs:
        raise ValueError(
            f"Redis DB index {db_index} is out of range for worker '{worker_id}'. "
            f"Redis only has {max_dbs} databases (0-{max_dbs - 1}). "
            f"TEST_REDIS_URI base DB is {base_db}. "
            f"Either increase Redis 'databases' config or lower the base DB index."
        )

    return f"{base}/{db_index}"


@pytest.fixture(scope="session")
def build_app(
    ignore_deprecation_warning,
    worker_db_uri: str,
    worker_redis_uri: str,
) -> Generator[Tuple[Flask, ConfigTest], None, None]:
    config = ConfigTest()
    config.SQLALCHEMY_DATABASE_URI = worker_db_uri
    config.SQLALCHEMY_BINDS = {"test": worker_db_uri}
    if worker_redis_uri and worker_redis_uri != "memory://":
        config.SESSION_TYPE = "redis"
        config.SESSION_REDIS = Redis.from_url(worker_redis_uri)

    app_for_test = create_app(config)  # type: ignore
    if app_for_test is None:
        return

    # Prevent logs from cluttering test output, while still being captured in caplog
    original_log_handlers = app_for_test.logger.handlers.copy()
    for handler in original_log_handlers:
        is_stream_or_file_handler = isinstance(
            handler, logging.StreamHandler
        ) or isinstance(handler, logging.FileHandler)
        if is_stream_or_file_handler and not isinstance(handler, logging.NullHandler):
            app_for_test.logger.removeHandler(handler)

    app_for_test.logger.propagate = True

    with app_for_test.app_context():
        db.init_app(app_for_test)
        db.create_all()

    yield app_for_test, config

    with app_for_test.app_context():
        db.drop_all()


@pytest.fixture
def db_transaction(build_app: Tuple[Flask, ConfigTest]) -> Generator[Flask, None, None]:
    """
    Wraps each test in an outer transaction + SAVEPOINT.

    session.commit() inside routes/services commits to the SAVEPOINT only.
    The after_transaction_end listener restarts the SAVEPOINT after each commit
    so subsequent commits within the same test also stay within the transaction.
    The outer transaction is rolled back after the test — no DDL needed.

    Note: The double-commit pattern in backend/tags/services/create_url_tag.py
    (_get_or_create_utub_tag commits the Utub_Tags row, then add_tag_to_url_if_valid
    commits the association) is safe here because both commits land in the SAVEPOINT
    and are rolled back together. Tests assert only on response JSON and row counts.
    """
    app, testing_config = build_app
    with app.app_context():
        connection = db.engine.connect()
        trans = connection.begin()

        session = scoped_session(sessionmaker(bind=connection))
        old_session = db.session
        db.session = session

        # Flask-SQLAlchemy registers a teardown_appcontext handler that calls
        # db.session.remove() on every app context pop, including nested ones
        # created by `with app.app_context():` in fixtures and tests. Replacing
        # remove() with a no-op prevents the session from being destroyed (and
        # all loaded objects detached) between inner context blocks within the
        # same test. The real removal happens explicitly below in teardown.
        original_remove = session.remove
        session.remove = lambda: None  # type: ignore[method-assign]

        session.begin_nested()

        @event.listens_for(session, "after_transaction_end")
        def restart_savepoint(sess: object, transaction: object) -> None:
            if transaction.nested and not transaction._parent.nested:
                # expire_on_commit=True only fires on outermost commits, not on
                # SAVEPOINT releases. We must manually expire all objects so the
                # session re-fetches fresh state from the DB on next access.
                # Additionally, objects deleted within the SAVEPOINT are not
                # automatically expunged from the identity map (unlike full
                # commits). Expunge them explicitly so lazy loads do not return
                # stale cached references to deleted rows.
                for instance in list(sess.identity_map.values()):
                    if sa_inspect(instance).was_deleted:
                        sess.expunge(instance)
                sess.expire_all()
                sess.begin_nested()

        yield app

        session.remove = original_remove
        session.remove()
        db.session = old_session
        trans.rollback()
        connection.close()

        # Reset all PostgreSQL sequences so each test starts with IDs from 1,
        # matching the behavior of the old clear_database() approach which
        # dropped and recreated all tables (which resets sequences).
        with db.engine.begin() as reset_conn:
            sequences = reset_conn.execute(
                text(
                    "SELECT sequence_name FROM information_schema.sequences"
                    " WHERE sequence_schema = 'public'"
                )
            ).fetchall()
            for (seq_name,) in sequences:
                reset_conn.execute(text(f'ALTER SEQUENCE "{seq_name}" RESTART WITH 1'))


@pytest.fixture
def app(db_transaction: Flask, caplog) -> Generator[Flask, None, None]:
    caplog.set_level("INFO", logger=CONFIG_ENVS.U4I_LOGGER)
    yield db_transaction
    if isinstance(db_transaction.session_interface, RedisSessionInterface):
        db_transaction.session_interface.client.flushdb()


@pytest.fixture
def runner(
    build_app: Tuple[Flask, ConfigTest],
) -> Generator[Tuple[Flask, FlaskCliRunner], None, None]:
    app, testing_config = build_app
    yield app, app.test_cli_runner()
    clear_database(testing_config)
    if isinstance(app.session_interface, RedisSessionInterface):
        app.session_interface.client.flushdb()


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

        new_user.email_validated = True

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

            new_user.email_validated = True

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
        creator_to_utub = Utub_Members(member_role=Member_Role.CREATOR)
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

            creator_to_utub = Utub_Members(member_role=Member_Role.CREATOR)
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
        other_users = Users.query.order_by(Users.id).all()
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
        current_utubs: list[Utubs] = Utubs.query.order_by(Utubs.id).all()
        current_users = Users.query.order_by(Users.id).all()

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
            )
            db.session.add(new_url)
        db.session.commit()


@pytest.fixture
def add_tags_to_utubs(app: Flask, every_user_makes_a_unique_utub):
    with app.app_context():
        all_utubs: list[Utubs] = Utubs.query.order_by(Utubs.id).all()
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
def add_max_tags_to_utubs(app: Flask, every_user_makes_a_unique_utub):
    with app.app_context():
        all_utubs: list[Utubs] = Utubs.query.order_by(Utubs.id).all()
        for utub in all_utubs:
            for tag in maximum_tags:
                new_tag = Utub_Tags(
                    utub_id=utub.id,
                    tag_string=tag[model_strs.TAG_STRING],
                    created_by=utub.utub_creator,
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
        all_urls: list[Urls] = Urls.query.order_by(Urls.id).all()
        all_utubs: list[Utubs] = Utubs.query.order_by(Utubs.id).all()
        all_users: list[Users] = Users.query.order_by(Users.id).all()

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
        all_utubs: list[Utubs] = Utubs.query.order_by(Utubs.id).all()

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
        all_tags: list[Utub_Tags] = Utub_Tags.query.order_by(Utub_Tags.id).all()
        all_utubs: list[Utubs] = Utubs.query.order_by(Utubs.id).all()

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
        current_utubs: list[Utubs] = Utubs.query.order_by(Utubs.id).all()
        current_users: list[Users] = Users.query.order_by(Users.id).all()

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
        all_utubs: list[Utubs] = Utubs.query.order_by(Utubs.id).all()
        all_urls: list[Urls] = Urls.query.order_by(Urls.id).all()

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
        all_utubs: list[Utubs] = Utubs.query.order_by(Utubs.id).all()

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
        all_utubs: list[Utubs] = Utubs.query.order_by(Utubs.id).all()
        all_tags: list[Utub_Tags] = Utub_Tags.query.order_by(Utub_Tags.id).all()

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


@pytest.fixture
def app_with_server_name(app: Flask) -> Generator[Flask, None, None]:
    app.config["SERVER_NAME"] = "localhost:5000"
    yield app
