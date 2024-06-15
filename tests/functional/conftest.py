# Standard library
from typing import Generator, Tuple
import multiprocessing

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
from tests.functional.utils_for_test import ping_server, run_app


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
def parallelize_app(init_multiprocessing):
    """
    Starts a parallel process, runs Flask app
    """

    process = multiprocessing.Process(target=run_app)

    process.start()
    yield process
    process.kill()
    process.join()


def pytest_addoption(parser):
    parser.addoption(
        "--headless", action="store", default="true", help="my option: true or false"
    )


@pytest.fixture(scope="session")
def headless(request):
    return request.config.getoption("--headless")


@pytest.fixture(scope="session")
def build_driver(parallelize_app, headless) -> Generator[WebDriver, None, None]:
    """
    Given the Flask app running in parallel, this function gets the browser ready for manipulation and pings server to ensure Flask app is running in parallel.
    """

    # Uncomment below to hide UI
    if headless == "false":
        driver = webdriver.Chrome()
    else:
        options = Options()
        options.add_argument("--headless")
        driver = webdriver.Chrome(options=options)

    # Uncomment below to see UI

    driver.maximize_window()
    ping_server(UI_TEST_STRINGS.BASE_URL)

    yield driver

    # Teardown: Quit the browser after tests
    driver.quit()


@pytest.fixture
def browser(build_driver: WebDriver, runner: Tuple[Flask, FlaskCliRunner]):
    """
    This fixture clears cookies, accesses the U4I site and supplies driver for use by the test. A new instance is invoked per test.
    """
    driver = build_driver

    driver.delete_all_cookies()

    driver.get(UI_TEST_STRINGS.BASE_URL)

    # Return the driver object to be used in the test functions
    yield driver


@pytest.fixture
def add_test_users(runner):
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "users"])
    print("users added")
