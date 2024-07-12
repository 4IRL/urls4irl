# Standard library
import logging
import multiprocessing
import requests
import socket
from time import sleep
from typing import Generator, Tuple

# External libraries
from flask import Flask
from flask.testing import FlaskCliRunner
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver

from selenium.webdriver.chrome.options import Options

# Internal libraries
from src import create_app
from src.config import TestingConfig
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS

# CLI commands


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
        "--show_browser", action="store_true", help="Show browser when included"
    )

    # Option 2: Show Pytest debug strings
    parser.addoption(
        "--DS", action="store_true", help="Show debug strings when included"
    )

    # Option 3: Show Flask logs
    parser.addoption("--FL", action="store_true", help="Show Flask logs when included")


@pytest.fixture(scope="session")
def turn_off_headless(request):
    return request.config.getoption("--show_browser")


@pytest.fixture(scope="session")
def debug_strings(request):
    return request.config.getoption("--DS")


@pytest.fixture(scope="session")
def flask_logs(request):
    return request.config.getoption("--FL")


def run_app(port: int, show_flask_logs: bool):
    """
    Runs app
    """
    config = TestingConfig()
    app_for_test = create_app(config)
    if not show_flask_logs:
        log = logging.getLogger("werkzeug")
        log.disabled = True
    app_for_test.run(debug=False, port=port)


def clear_db(runner: Tuple[Flask, FlaskCliRunner], debug_strings):
    # Clear db
    _, cli_runner = runner
    cli_runner.invoke(args=["managedb", "clear", "test"])
    if debug_strings:
        print("\ndb cleared")


def find_open_port(start_port: int = 1024, end_port: int = 65535) -> int:
    for port in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No available port found in the specified range.")


def ping_server(url: str, timeout: float = 2) -> bool:
    total_time = 0
    max_time = 10
    is_server_ready = False

    # Keep pinging server until status code 200 or time limit is reached
    while not is_server_ready and total_time < max_time:
        try:
            status_code = requests.get(url, timeout=timeout).status_code
        except requests.ConnectTimeout:
            sleep(timeout)
            total_time += timeout
        else:
            is_server_ready = status_code == 200

    return is_server_ready


@pytest.fixture(scope="session")
def provide_config() -> TestingConfig:

    config = TestingConfig()

    return config


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
def build_driver(
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

    driver.maximize_window()
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

    clear_db(runner, debug_strings)

    # Return the driver object to be used in the test functions
    yield driver


@pytest.fixture
def create_test_users(runner, debug_strings):
    """ "
    Assumes nothing created. Creates users
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "users"])

    if debug_strings:
        print("\nusers created")


@pytest.fixture
def create_test_utubs(runner, debug_strings):
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
