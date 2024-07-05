# Standard library
from typing import Generator, Tuple
import multiprocessing
import time

# External libraries
from flask import Flask
from flask.testing import FlaskCliRunner
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver

from selenium.webdriver.chrome.options import Options

# Internal libraries
from src.config import TestingConfig
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.utils_for_test import (
    clear_db,
    find_open_port,
    ping_server,
    run_app,
)


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
    time.sleep(2)
    return open_port


@pytest.fixture(scope="session")
def parallelize_app(provide_port, init_multiprocessing):
    """
    Starts a parallel process, runs Flask app
    """
    open_port = provide_port
    process = multiprocessing.Process(target=run_app, args=(open_port,))

    process.start()
    time.sleep(5)
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
def add_test_users(runner):
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "users"])
    print("users added")
    # if debug_strings:
    #     print("users added")


@pytest.fixture
# def add_test_utubs(runner, debug_strings):
def add_test_utub(runner):
    """
    Adds test users and a single sample UTub
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "utub"])
    print("utub added")
    # if debug_strings:
    #     print("one utub added")


@pytest.fixture
# def add_test_utubs(runner, debug_strings):
def add_test_utubs(runner):
    """
    Adds test users and sample UTubs
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "utubs"])
    print("utubs added")
    # if debug_strings:
    #     print("utubs added")
