# Standard library
import multiprocessing
from time import sleep
from typing import Generator, Tuple

# External libraries
from flask import Flask, url_for
from flask.testing import FlaskCliRunner
import pytest
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.chrome.options import Options

# Internal libraries
from src import create_app, db, environment_assets
from src.config import ConfigTest
from src.models.email_validations import Email_Validations
from src.models.forgot_passwords import Forgot_Passwords
from src.models.users import Users
from src.utils.all_routes import ROUTES
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.ui_test_utils import clear_db, find_open_port, ping_server, run_app


# CLI commands
@pytest.fixture(scope="session")
def turn_off_headless(request):
    return request.config.getoption("--show_browser")


@pytest.fixture(scope="session")
def debug_strings(request):
    return request.config.getoption("--DS")


@pytest.fixture(scope="session")
def flask_logs(request):
    return request.config.getoption("--FL")


@pytest.fixture(scope="session")
def init_multiprocessing():
    """
    Creates a process separate from pytest to run the app in parallel
    """
    multiprocessing.set_start_method("spawn")


@pytest.fixture(scope="session")
def provide_config() -> Generator[ConfigTest | None, None, None]:
    yield ConfigTest()


@pytest.fixture(scope="session")
def provide_port(flask_logs: bool) -> int:
    open_port = find_open_port()
    if flask_logs:
        print(f"\nFound an open port: {open_port}")
    sleep(2)
    return open_port


@pytest.fixture(scope="session")
def parallelize_app(provide_port, init_multiprocessing, flask_logs):
    """
    Starts a parallel process, runs Flask app
    """
    open_port = provide_port
    process = multiprocessing.Process(
        target=run_app,
        args=(
            open_port,
            flask_logs,
        ),
    )

    process.start()
    sleep(5)
    yield process
    process.kill()
    process.join()


@pytest.fixture(scope="session")
def provide_app() -> Generator[Flask | None, None, None]:
    # Clear bundles to avoid re-registering
    environment_assets._named_bundles = {}

    yield create_app(ConfigTest())


@pytest.fixture(scope="session")
def build_driver(
    provide_port: int, parallelize_app, turn_off_headless
) -> Generator[WebDriver, None, None]:
    """
    Given the Flask app running in parallel, this function gets the browser ready for manipulation and pings server to ensure Flask app is running in parallel.
    """
    config = ConfigTest()
    open_port = provide_port
    options = Options()
    options.add_argument("--disable-notifications")

    if not turn_off_headless:
        options.add_argument("--headless=new")

    if config.DOCKER:
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")

        driver = webdriver.Remote(
            command_executor=config.TEST_SELENIUM_URI, options=options
        )
        url = UI_TEST_STRINGS.DOCKER_BASE_URL
    else:
        driver = webdriver.Chrome(options=options)
        url = UI_TEST_STRINGS.BASE_URL

    driver.set_window_size(width=1920, height=1080)

    ping_server(url + str(open_port))

    yield driver

    # Teardown: Quit the browser after tests
    driver.quit()


@pytest.fixture(scope="session")
def build_driver_mobile_portrait(
    provide_port: int, parallelize_app, turn_off_headless
) -> Generator[WebDriver, None, None]:
    """
    Given the Flask app running in parallel, this function gets the browser ready for manipulation and pings server to ensure Flask app is running in parallel.
    """
    config = ConfigTest()
    open_port = provide_port
    options = Options()
    options.add_argument("--disable-notifications")

    if not turn_off_headless:
        options.add_argument("--headless")

    if config.DOCKER:
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        capabilities = webdriver.ChromeOptions().to_capabilities()
        capabilities["acceptInsecureCerts"] = True

        driver = webdriver.Remote(
            command_executor=config.TEST_SELENIUM_URI, options=options
        )
        url = UI_TEST_STRINGS.DOCKER_BASE_URL
    else:
        driver = webdriver.Chrome(options=options)
        url = UI_TEST_STRINGS.BASE_URL

    driver.set_window_size(width=420, height=900)

    ping_server(url + str(open_port))

    yield driver

    # Teardown: Quit the browser after tests
    driver.quit()


@pytest.fixture
def browser(
    provide_port: int,
    provide_config: ConfigTest,
    build_driver: WebDriver,
    runner: Tuple[Flask, FlaskCliRunner],
    debug_strings,
):
    """
    This fixture clears cookies, accesses the U4I site and supplies driver for use by the test. A new instance is invoked per test.
    """
    open_port = provide_port
    url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL
        if provide_config.DOCKER
        else UI_TEST_STRINGS.BASE_URL
    )
    driver = build_driver

    driver.delete_all_cookies()

    driver.get(url + str(open_port) + "/")
    init_handle = driver.current_window_handle

    clear_db(runner, debug_strings)

    # Return the driver object to be used in the test functions
    yield driver

    # Clean up any additional tabs that may have been opened during tests
    for handle in driver.window_handles:
        if handle != init_handle:
            driver.switch_to.window(handle)
            driver.close()

    # Return to the initial tab for further tests
    driver.switch_to.window(init_handle)


@pytest.fixture
def browser_mobile_portrait(
    provide_port: int,
    provide_config: ConfigTest,
    build_driver_mobile_portrait: WebDriver,
    runner: Tuple[Flask, FlaskCliRunner],
    debug_strings,
):
    """
    This fixture clears cookies, accesses the U4I site and supplies driver for use by the test. A new instance is invoked per test.
    """
    open_port = provide_port
    url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL
        if provide_config.DOCKER
        else UI_TEST_STRINGS.BASE_URL
    )
    driver = build_driver_mobile_portrait

    driver.delete_all_cookies()

    driver.get(url + str(open_port) + "/")

    clear_db(runner, debug_strings)

    # Return the driver object to be used in the test functions
    yield driver


@pytest.fixture
def create_test_users(runner, debug_strings):
    """
    Assumes nothing created. Creates users
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "users"])

    if debug_strings:
        print("\nusers created")


@pytest.fixture
def create_user_unconfirmed_email(
    runner: Tuple[Flask, FlaskCliRunner], debug_strings
) -> str:
    """
    Assumes nothing created. Creates an a user with an unconfirmed email

    Returns:
        (str): URL to validate the User's email
    """
    app, _ = runner

    with app.app_context():
        new_user = Users(
            username=UI_TEST_STRINGS.TEST_USERNAME_1,
            email=UI_TEST_STRINGS.TEST_PASSWORD_1,
            plaintext_password=UI_TEST_STRINGS.TEST_PASSWORD_1,
        )

        new_email_validation = Email_Validations(
            validation_token=new_user.get_email_validation_token()
        )
        new_email_validation.is_validated = False
        new_user.email_confirm = new_email_validation

        db.session.add(new_user)
        db.session.commit()

        with app.test_request_context():
            return url_for(
                ROUTES.SPLASH.VALIDATE_EMAIL,
                token=new_email_validation.validation_token,
            )


@pytest.fixture
def create_user_resetting_password(
    runner: Tuple[Flask, FlaskCliRunner], debug_strings
) -> str:
    """
    Assumes nothing created. Creates an a user with an unconfirmed email

    Returns:
        (str): URL to validate the User's email
    """
    app, _ = runner

    with app.app_context():
        new_user = Users(
            username=UI_TEST_STRINGS.TEST_USERNAME_1,
            email=UI_TEST_STRINGS.TEST_PASSWORD_1,
            plaintext_password=UI_TEST_STRINGS.TEST_PASSWORD_1,
        )

        new_user.email_validated = True

        new_password_reset = Forgot_Passwords(
            reset_token=new_user.get_password_reset_token()
        )

        new_user.forgot_password = new_password_reset
        db.session.add(new_user)
        db.session.commit()

        with app.test_request_context():
            return url_for(
                ROUTES.SPLASH.RESET_PASSWORD,
                token=new_password_reset.reset_token,
            )


@pytest.fixture
def create_test_utubs(runner: Tuple[Flask, FlaskCliRunner], debug_strings):
    """
    Assumes users created. Creates sample UTubs, each user owns one.
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "utubs"])

    if debug_strings:
        print("\nusers and utubs created")


@pytest.fixture
def create_test_utubmembers(runner, debug_strings):
    """
    Assumes users created, and each own one UTub. Creates all users as members of each UTub.
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "utubmembers"])

    if debug_strings:
        print("\nusers, utubs, and members created")


@pytest.fixture
def create_test_urls(runner, debug_strings):
    """
    Assumes users created, each own one UTub, and all users are members of each UTub. Creates URLs in each UTub.
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "urls"])

    if debug_strings:
        print("\nusers, utubs, members, and urls created")


@pytest.fixture
def create_test_tags(runner, debug_strings):
    """
    Assumes users created, each own one UTub, all users are members of each UTub, and URLs added to each UTub. Creates all tags on all URLs.
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "tags"])

    if debug_strings:
        print("\nusers, utubs, members, urls, and tags created")
