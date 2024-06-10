# Standard library
from typing import Generator
import multiprocessing

# External libraries
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver

# from selenium.webdriver.chrome.options import Options
from sqlalchemy import create_engine

# Internal libraries
from src.config import TestingConfig
import tests.functional.constants as const
from tests.functional.utils_for_test import ping_server, run_app, clear_db


@pytest.fixture(scope="session")
def provide_config() -> TestingConfig:

    config = TestingConfig()

    return config


@pytest.fixture(scope="session")
def provide_engine(provide_config: TestingConfig):
    config = provide_config
    engine = create_engine(config.SQLALCHEMY_DATABASE_URI)

    yield engine


# Creates a process separate from pytest to run the app in parallel
@pytest.fixture(scope="session")
def init_multiprocessing():
    multiprocessing.set_start_method("spawn")


# Manages set up and tear down of app process
@pytest.fixture(scope="session")
def parallelize_app(init_multiprocessing, provide_config):
    config = provide_config
    process = multiprocessing.Process(target=run_app, args=(config,))

    process.start()
    yield process
    process.kill()
    process.join()


# Manages set up and tear down of app process
@pytest.fixture(scope="session")
def build_driver(parallelize_app) -> Generator[WebDriver, None, None]:
    # Uncomment below to hide UI
    # options = Options()
    # options.add_argument("--headless=new")
    # options.add_argument("–-disable-gpu")
    # driver = webdriver.Chrome(options=options)

    # Uncomment below to see UI
    driver = webdriver.Chrome()
    driver.maximize_window()
    ping_server(const.BASE_URL)

    yield driver

    # Teardown: Quit the browser after tests
    driver.quit()


# Setup fixture for the webdriver. Accesses U4I and supplies driver
@pytest.fixture
def browser(build_driver: WebDriver, provide_config: TestingConfig):
    driver = build_driver

    driver.delete_all_cookies()

    driver.get(const.BASE_URL)

    # Clear db
    # driver.get(const.CLEAR_DB_URL)
    # driver.implicitly_wait(3)

    # Load test users
    # driver.get(const.ADD_TEST_USERS_URL)
    # driver.implicitly_wait(3)

    # Return the driver object to be used in the test functions
    yield driver

    clear_db(provide_config)


# This fixture is not yet implemented because I can't figure out how to start each test independently. Currently the implementation of each subsequent test is dependent on the success of its predecessors
# Logs in newly created user
# @pytest.fixture
# def login(browser):
#     # Load U4I
#     browser.get(const.BASE_URL)

#     # Example interaction: Find an element by its tag name and check its text
#     btn_login = browser.find_element(By.CLASS_NAME, "to-login")
#     btn_login.click()

#     # Input login details
#     input_field_username = browser.find_element(By.ID, "username")
#     input_field_username.clear()
#     input_field_username.send_keys(const.USERNAME)

#     input_field_password = browser.find_element(By.ID, "password")
#     input_field_password.clear()
#     input_field_password.send_keys(const.PASSWORD)
