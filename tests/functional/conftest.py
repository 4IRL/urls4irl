# Standard library
import multiprocessing
from os import environ
from time import sleep
from typing import Generator, Tuple

# External libraries
from flask import Flask
from flask.testing import FlaskCliRunner
import pytest
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver

from selenium.webdriver.chrome.options import Options

# Internal libraries
from src import create_app
from src.config import ConfigTest
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
def provide_port() -> int:
    open_port = find_open_port()
    print(f"Found an open port: {open_port}")
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
def provide_app_for_session_generation() -> Generator[Flask | None, None, None]:
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
    if config.DOCKER:
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

    if turn_off_headless:
        # Disable Chrome browser pop-up notifications
        # prefs = {"profile.default_content_setting_values.notifications" : 2}
        # options.add_experimental_option("prefs",prefs)
        # options.add_argument("--disable-notifications")
        print("Browser incoming")
    else:
        options.add_argument("--headless")

    if config.DOCKER:
        driver_path = environ.get("CHROMEDRIVER_PATH", "")
        service = webdriver.ChromeService(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)
    driver.set_window_size(width=1400, height=1000)

    # driver.maximize_window()
    ping_server(UI_TEST_STRINGS.BASE_URL + str(open_port))

    yield driver

    # Teardown: Quit the browser after tests
    driver.quit()


@pytest.fixture(scope="session")
def build_driver_mobile(
    provide_port: int, parallelize_app, turn_off_headless
) -> Generator[WebDriver, None, None]:
    """
    Given the Flask app running in parallel, this function gets the browser ready for manipulation and pings server to ensure Flask app is running in parallel.
    """
    open_port = provide_port
    options = Options()

    if turn_off_headless:
        # Disable Chrome browser pop-up notifications
        # prefs = {"profile.default_content_setting_values.notifications" : 2}
        # options.add_experimental_option("prefs",prefs)
        options.add_argument("--disable-notifications")
    else:
        options.add_argument("--headless")

    driver = webdriver.Chrome(options=options)
    driver.set_window_size(width=400, height=600)

    # driver.maximize_window()
    ping_server(UI_TEST_STRINGS.BASE_URL + str(open_port))

    yield driver

    # Teardown: Quit the browser after tests
    driver.quit()


@pytest.fixture
def browser(
    provide_port: int,
    build_driver: WebDriver,
    runner: Tuple[Flask, FlaskCliRunner],
    debug_strings,
):
    """
    This fixture clears cookies, accesses the U4I site and supplies driver for use by the test. A new instance is invoked per test.
    """
    open_port = provide_port
    driver = build_driver

    driver.delete_all_cookies()

    driver.get(UI_TEST_STRINGS.BASE_URL + str(open_port))
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
def browser_mobile(
    provide_port: int,
    build_driver_mobile: WebDriver,
    runner: Tuple[Flask, FlaskCliRunner],
    debug_strings,
):
    """
    This fixture clears cookies, accesses the U4I site and supplies driver for use by the test. A new instance is invoked per test.
    """
    open_port = provide_port
    driver = build_driver

    driver.delete_all_cookies()

    driver.get(UI_TEST_STRINGS.BASE_URL + str(open_port))

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
        print("\nusers, utubs, and members created")


@pytest.fixture
def create_test_tags(runner, debug_strings):
    """
    Assumes users created, each own one UTub, all users are members of each UTub, and URLs added to each UTub. Creates all tags on all URLs.
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "tags"])

    if debug_strings:
        print("\nusers, utubs, and members created")
