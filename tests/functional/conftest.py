# Standard library
from typing import Generator, Tuple
import multiprocessing
from time import sleep
import requests
import socket

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


def run_app(port: int):
    """
    Runs app
    """
    config = TestingConfig()
    app_for_test = create_app(config)
    app_for_test.run(debug=False, port=port)


def clear_db(runner: Tuple[Flask, FlaskCliRunner]):
    # Clear db
    _, cli_runner = runner
    cli_runner.invoke(args=["managedb", "clear", "test"])
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
def parallelize_app(provide_port, init_multiprocessing):
    """
    Starts a parallel process, runs Flask app
    """
    open_port = provide_port
    process = multiprocessing.Process(target=run_app, args=(open_port,))

    process.start()
    sleep(5)
    yield process
    process.kill()
    process.join()


# CLI commands


def pytest_addoption(parser):
    """
    Option 1:
    Adds CLI option for headless operation.
    Default runs tests headless; option to observe UI interactions when debugging by assigning False.

    Option 2:
    Adds CLI option for display of debug strings.
    Default keeps all strings hidden from CLI.
    """

    # Option 1: Headless
    parser.addoption(
        "--headless", action="store", default="true", help="my option: true or false"
    )

    # Option 2: Debug strings
    # parser.addoption(
    #     "--debug_strings", action="store", default="false", help="my option: true or false"
    # )


@pytest.fixture(scope="session")
def headless(request):
    return request.config.getoption("--headless")


# @pytest.fixture(scope="session")
# def debug_strings(request):
#     return request.config.getoption("--debug_strings")


@pytest.fixture(scope="session")
def build_driver(
    provide_port: int, parallelize_app, headless
) -> Generator[WebDriver, None, None]:
    """
    Given the Flask app running in parallel, this function gets the browser ready for manipulation and pings server to ensure Flask app is running in parallel.
    """
    open_port = provide_port
    options = Options()

    if headless == "false":
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
    provide_port: int, build_driver: WebDriver, runner: Tuple[Flask, FlaskCliRunner]
):
    """
    This fixture clears cookies, accesses the U4I site and supplies driver for use by the test. A new instance is invoked per test.
    """
    open_port = provide_port
    driver = build_driver

    driver.delete_all_cookies()

    driver.get(UI_TEST_STRINGS.BASE_URL + str(open_port))

    clear_db(runner)

    # Return the driver object to be used in the test functions
    yield driver


@pytest.fixture
# def create_test_users(runner, debug_strings):
def create_test_users(runner):
    """ "
    Assumes nothing created. Creates users
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "users"])
    print("\nusers created")
    # if debug_strings:
    #     print("\nusers created")


@pytest.fixture
# def create_test_utubs(runner, debug_strings):
def create_test_utubs(runner):
    """
    Assumes users created. Creates sample UTubs, each user owns one.
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "utubs"])
    print("\nusers and utubs created")
    # if debug_strings:
    #     print("\nusers and utubs created")


@pytest.fixture
# def create_test_members(runner, debug_strings):
def create_test_utubmembers(runner):
    """
    Assumes users created, and each own one UTub. Creates all users as members of each UTub.
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "utubmembers"])
    print("\nusers, utubs, and members created")
    # if debug_strings:
    #     print("\nusers, utubs, and members created")


@pytest.fixture
# def create_test_urls(runner, debug_strings):
def create_test_urls(runner):
    """
    Assumes users created, each own one UTub, and all users are members of each UTub. Creates URLs in each UTub.
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "urls"])
    print("\nusers, utubs, members, and urls created")
    # if debug_strings:
    #     print("\nusers, utubs, and members created")


@pytest.fixture
# def create_test_tags(runner, debug_strings):
def create_test_tags(runner):
    """
    Assumes users created, each own one UTub, all users are members of each UTub, and URLs added to each UTub. Creates all tags on all URLs.
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "tags"])
    print("\nusers, utubs, members, urls, and tags created")
    # if debug_strings:
    #     print("\nusers, utubs, and members created")
